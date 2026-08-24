# Customizing the Horizon skin

The Horizon skin draws its charts in the browser, but its look is settled before that,
in CSS custom properties. Everything you see is one of them: the surfaces, the type
sizes, the corner radius, the colours the charts read for their grid and axes.

Any of them can be overridden from `skin.conf`, so restyling the skin is a change to
your configuration and not to a file that the next upgrade will overwrite.

## Layout

The page is charts and a column of panels beside them. Four options settle the rest:

``` ini
[DisplayOptions]
    sidebar        = right          # or left, when there is room for two columns
    sidebar_responsive = bottom         # or top, when there is only one

    plot_groups = tempdew, wind, rain, ...
    panels      = current, sunmoon, imagery, sensors, about

    hide_plot_groups = tempin, humin
    hide_panels      = imagery
```

`plot_groups` and `panels` set what appears and in what order. `hide_plot_groups` and
`hide_panels` take things out without editing those lists, so you still have them to
put back.

A panel is an `.inc` file in the skin directory. Write your own, add its name to
`panels`, and it appears. No template editing.

## The cards

Each name in `panels` is an `.inc` file in the skin directory. These come with it:

| Panel | What it shows |
|---|---|
| `current` | The reading set large, the day's range under it, and everything else the station records in two columns. `dashboard_lead` and `dashboard_readings` decide what. |
| `sun` | The sun's arc through the day, with the band behind it covering the year between the solstices. Daylight, how much that has changed since yesterday, the highest the sun reaches, when it is light enough to see by, and the distance. |
| `moon` | The moon as NASA rendered it, one of 32 frames picked by age since the last new moon. Illumination, phase, age, rise and set, and the next full and new moon. |
| `imagery` | Radar, satellite and map, where they are configured. |
| `sensors` | Signal strength, batteries and voltages. |
| `about` | Where the station is and what it runs. |

A panel of your own is a file plus its name in `panels`. Nothing else to edit.

The sun's arc costs one number per curve rather than a reading every quarter
hour: at hour angle H the height of the sun is `sin(h) = sin(lat) sin(dec) +
cos(lat) cos(dec) cos(H)`, and the band is the same curve at the solstices. Each
curve is drawn for its own day, so the axis is the clock on the wall: the sun is
highest at 13:15 rather than at noon in central Europe, and an hour earlier by
the clock at midwinter than at midsummer. North of the arctic circle there are
days with no sunrise, and the card says so.

The moon images are NASA's, rendered from Lunar Reconnaissance Orbiter
elevation data and in the public domain. `moon/LICENSE.txt` has the details.
The phase is right in any year; the libration was computed for 2026 and drifts
after that by an amount nobody will see.

## What the skin adds to [DisplayOptions]

Most of the section is shared with *Seasons* and documented in the reference under
[_[DisplayOptions]_](../reference/skin-options/displayoptions.md): `plot_groups`,
`periods`, `observations_current`, `observations_stats`, `observations_rss`,
`obs_type_sum`, `obs_type_max`, `telemetry_plot_groups`, `sensor_connections`,
`sensor_batteries`, `sensor_voltages`, `show_rss` and `show_reports`. Horizon reads
them the same way.

These are its own:

| Option | What it does |
|---|---|
| `sidebar` | Which side the panels sit on, `right` or `left`, where there is room for two columns. |
| `sidebar_responsive` | Where they go when there is not: `bottom` or `top`. |
| `panels` | Which panels appear beside the charts, and in what order. Each name is an `.inc` file in the skin directory, so a panel of your own is a file plus a name in this list. |
| `hide_panels` | Panels to leave out, without editing the list above. |
| `hide_plot_groups` | Charts to leave out, without editing `plot_groups`. |
| `dashboard_lead` | The one reading set large at the top of the current conditions card. Defaults to the first entry in `observations_headline`. |
| `dashboard_readings` | The rows underneath it, in order. Defaults to `observations_current`. Anything the station does not record is skipped, so the list may name more than you have. |
| `observations_headline` | The types shown large at the top of the page. Three or four is about right on a phone. |
| `refresh_interval` | How often the page re-fetches current conditions, in seconds. `0` turns it off. There is no point going below your archive interval, since nothing new appears until the next record is archived. |
| `show_image_links` | Offer the server-rendered PNG next to each chart. Set it to `False` if you drop the ImageGenerator from `[Generators]`, or the links point at files nobody writes. |
| `custom_css` | A stylesheet of your own. See below. |
| `lang_root` | For a rendering in a subdirectory: how it gets back to the top. See the language switcher in `skin.conf`. |

## Theming: how it works

Under `[DisplayOptions]`:

``` ini
[DisplayOptions]
    [[Theme]]
        [[[Light]]]
            accent  = "#7a4b2c"
            bg      = "#faf6f2"
            radius  = 2px
            font    = Georgia, "Times New Roman", serif
        [[[Dark]]]
            accent  = "#d8a77a"
            bg      = "#1a1512"
```

There is no fixed list of names. Whatever you write becomes `--name`, so anything
`horizon.css` defines can be replaced, and nothing else is emitted. `[[[Light]]]`
applies everywhere; `[[[Dark]]]` overrides it where the reader's browser or the theme
toggle asks for a dark page.

## What there is

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
`[ImageGenerator]`, where the PNGs take them too, so a chart and the image of the same
plot stay the same colour.

## When the names are not enough

Name a stylesheet of your own:

``` ini
[DisplayOptions]
    custom_css = my-station.css
```

It is loaded after `horizon.css` and after `[[Theme]]`, so it wins over both. Put the
file in the skin directory and add it to `copy_once` in `[CopyGenerator]`, or it will
not be installed.
