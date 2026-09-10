# Customizing the Horizon skin

The Horizon skin draws its charts in the browser with
[ECharts](https://echarts.apache.org/), which ships with it. Its look is settled
before that, in CSS custom properties. Everything you see is one of them: the
surfaces, the type sizes, the corner radius, the colours the charts read for
their grid and axes.

Any of them can be overridden from a stylesheet of your own, so restyling the
skin is a file you keep and not a change to one that the next upgrade will
overwrite.

## Layout

The page is charts and a column of panels beside them. Four options settle the
rest:

``` ini
[DisplayOptions]
    sidebar        = right          # or left, when there is room for two columns
    sidebar_responsive = bottom         # or top, when there is only one

    plot_groups = tempdew, wind, rain, ...
    main_panels = history, hilo
    panels      = current, forecast, sunmoon, planets, imagery, sensors, about
```

`plot_groups` sets which charts appear and in what order. To take something out
and keep it to hand, copy the line, comment one copy out, and edit the other.

The page is two columns of panels, and both are lists: `main_panels` is the wide
one, `panels` the narrower one beside it. `history` is the charts with their span
switcher and `hilo` the statistics table, so those can be moved or left out like
any other. Only one `history` belongs on a page.

A panel is an `.inc` file in the skin directory. Write your own, add its name to
either list, and it appears. No template editing.

## The cards

Each name in `panels` is an `.inc` file in the skin directory. These come with
it:

| Panel | What it shows |
|---|---|
| `current` | The first of `observations_current` set large, the day's range under it, and the rest of the list in two columns. |
| `forecast` | Seven days ahead, and the hours of whichever day is chosen. See [The forecast](#the-forecast) below. |
| `sun` | The sun's arc through the day, with the band behind it covering the year between the solstices. Daylight, how much that has changed since yesterday, the highest the sun reaches, when it is light enough to see by, and the distance. |
| `moon` | The moon as NASA rendered it, one of 32 frames picked by age since the last new moon. Illumination, phase, age, rise and set, and the next full and new moon. |
| `sunmoon` | Both of the above in one panel, side by side where there is room. Name it instead of `sun` and `moon`, not as well as. |
| `planets` | The naked-eye planets, how high each one stands, and when it rises and sets. A filled mark means it is above the horizon. Needs `pyephem`. |
| `imagery` | Radar, satellite and map, where they are configured. |
| `sensors` | Signal strength, batteries and voltages. |
| `about` | Where the station is and what it runs. |

A panel of your own is a file plus its name in `panels`. Nothing else to edit.

The `current` panel follows the span the page is showing. Over a day a card
shows the reading as it stands, with the day's low and high under it. Over a
week, a month or a year it shows the mean of the span instead, because the
reading at this instant says nothing about a year. Rain and evapotranspiration
are summed rather than averaged, and the wind shows the direction it mostly came
from. The figures are written into the page when it is rendered, so switching
spans fetches nothing.

The sun's arc costs one number per curve rather than a reading every quarter
hour: at hour angle H the height of the sun is `sin(h) = sin(lat) sin(dec) +
cos(lat) cos(dec) cos(H)`, and the band is the same curve at the solstices. Each
curve is drawn for its own day, so the axis is the clock on the wall: the sun is
highest at 13:15 rather than at noon in central Europe, and an hour earlier by
the clock at midwinter than at midsummer. North of the arctic circle there are
days with no sunrise, and the card says so.

The moon images are NASA's, rendered from Lunar Reconnaissance Orbiter elevation
data and in the public domain. `moon/LICENSE.txt` has the details. The phase is
right in any year; the libration was computed for 2026 and drifts after that by
an amount nobody will see.

## What the skin adds to [DisplayOptions]

Most of the section is shared with *Seasons* and documented in the reference
under [_[DisplayOptions]_](../reference/skin-options/displayoptions.md):
`plot_groups`, `periods`, `observations_current`, `observations_stats`,
`observations_rss`, `obs_type_sum`, `obs_type_max`, `telemetry_plot_groups`,
`sensor_connections`, `sensor_batteries` and `sensor_voltages`. Horizon reads
them the same way.

These are its own:

| Option | What it does |
|---|---|
| `sidebar` | Which side the panels sit on, `right` or `left`, where there is room for two columns. |
| `sidebar_responsive` | Where they go when there is not: `bottom` or `top`. |
| `main_panels` | Which panels fill the wide column, and in what order. Default is `history, hilo`: the charts, then the statistics table. |
| `panels` | Which panels appear beside them, and in what order. Each name in either list is an `.inc` file in the skin directory, so a panel of your own is a file plus a name in one of them. |
| `refresh_interval` | How often the page re-fetches current conditions, in seconds. `0` turns it off. There is no point going below your archive interval, since nothing new appears until the next record is archived. |
| `show_image_links` | Offer the server-rendered PNG next to each chart. Set it to `False` if you drop the ImageGenerator from `[Generators]`, or the links point at files nobody writes. |
| `planets` | Which planets the planets panel lists, and in what order. Any body `pyephem` knows can be named. Default is `mercury, venus, mars, jupiter, saturn`. |
| `custom_css` | A stylesheet of your own. See below. |
| `custom_js` | A script of your own. See below. |
| `lang_root` | For a rendering in a subdirectory: how it gets back to the top. See the language switcher in `skin.conf`. |

## The forecast

The forecast panel reads `data/forecast.json` if a file is there, and asks
Open-Meteo itself if there is not. Under `[DisplayOptions]`:

``` ini
[DisplayOptions]
    [[Forecast]]
        browser_fetch = true
        days = 7
        hours = 8
```

| Option | What it does |
|---|---|
| `browser_fetch` | Whether the page may ask Open-Meteo directly. Default is `True`. |
| `days` | How many days to show. Default is `7`. |
| `hours` | How many of the hours ahead, shown every third one. Default is `8`. |

Where the page fetches the forecast itself, each reader's browser talks to
Open-Meteo, and their address reaches a third party. On a station published to
the world, consider writing the file instead and setting `browser_fetch` to
`False`.

Anything can write that file. The script `forecast-fetch.py` in the skin
directory does it from Open-Meteo and documents the format, so a cron job, a DWD
MOSMIX feed through *weewx-dwd*, or [*weewx-forecast*][forecast-wiki] can feed
it as well.

  [forecast-wiki]: https://github.com/weewx/weewx/wiki/forecasting

## Icons

Each reading carries a small symbol, chosen by observation type. To change one,
or to name one for a type the skin does not know:

``` ini
[DisplayOptions]
    [[Icons]]
        outTemp = temp
        extraTemp1 = soil-temp
```

The value is the name of a file in `icons/`, without the extension. A type with
no entry simply has no symbol. The symbols are from the IBM Carbon set, under
the Apache 2.0 licence; see `icons/LICENSE-Carbon.txt`.

## The two looks

As it ships, the skin is painted by `horizon.css` and then by `flavor-deck.css`
on top of it: flat and dense, one sans throughout, an edge around every block,
the navigation in a column. `flavor-deck.js` is what moves the navigation and
puts the station's particulars in a footer. Both are named in `skin.conf`:

``` ini
[DisplayOptions]
    custom_css = flavor-deck.css
    custom_js  = flavor-deck.js
```

Take those two lines out and `horizon.css` stands alone: rounded cards with a
shadow, the navigation in a row across the top.

## Changing the colours and fonts

Add a stylesheet of your own after the one the skin ships with:

``` ini
[DisplayOptions]
    custom_css = flavor-deck.css, my-station.css
```

Put the file in the skin directory and add it to `copy_once` in
`[CopyGenerator]`, or it will not be installed. It is loaded last, so whatever
it sets wins. The look is a set of CSS custom properties, and a colour changes
by setting one:

``` css
:root {
  --accent: #7a4b2c;
  --bg: #faf6f2;
  --radius: 2px;
  --font: Georgia, "Times New Roman", serif;
}

/* Where the reader's browser asks for a dark page, or the theme toggle does. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --accent: #d8a77a; --bg: #1a1512; }
}
:root[data-theme="dark"] { --accent: #d8a77a; --bg: #1a1512; }
```

## The names you can set

Each of these is `--name` in the stylesheet.

| Name | What it colours |
|---|---|
| `bg`, `surface`, `surface-sunk` | the page, the cards, inset areas |
| `ink`, `ink-muted`, `ink-faint` | body text, labels, captions |
| `border`, `border-strong` | card edges, table rules |
| `accent`, `accent-bright` | links, the active tab |
| `hi`, `lo`, `ok`, `warn` | highs, lows, good and warning states |
| `chart-grid`, `chart-axis`, `chart-night` | inside the charts, read by `horizon.js` |
| `radius`, `gap`, `shadow` | corners, the space between cards, card shadow |
| `font` | the stack for the whole page |
| `fs-xs` … `fs-huge` | type sizes, from the small print to the headline figure |

The chart *line* colours are not here. They come from `chart_line_colors` in
`[JSONGenerator]`, beside the plot they belong to.

## A script of your own

`custom_js` works the same way:

``` ini
[DisplayOptions]
    custom_js = flavor-deck.js, my-station.js
```

It is deferred, so it runs after the skin's own script has wired up the page.
Use it for the things a stylesheet cannot do, such as moving a part of the page
somewhere else.
