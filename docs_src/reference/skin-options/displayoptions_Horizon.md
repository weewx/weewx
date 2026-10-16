# [DisplayOptions] for the *Horizon* skin

This section holds the options that control what the *Horizon* skin displays,
and in what order. Like [`[Extras]`](extras.md), the options are not
interpreted by WeeWX itself. The section is made available to the templates as
the tag `$DisplayOptions`, and the skin decides what to do with it.

*Horizon* shares many options with the *Seasons* skin, which are described in
[`[DisplayOptions]` for the *Seasons* skin](displayoptions.md). Some of them
have
a different meaning in *Horizon*. They are described again here, together with
the options that are *Horizon*'s own.

The templates read each option with a fallback, so removing an option from
`skin.conf` does not cause an error. The template's own default is used
instead. The defaults given below are those of the templates. They are often
much shorter than the lists that ship in `skin.conf`.

!!! Note
Naming an observation type does not guarantee that it will appear. The
templates skip a type that has no data. This is why a new station shows only
a few of the many types listed in `skin.conf`.

``` ini
[DisplayOptions]
    refresh_interval = 60
    panels = current, forecast, sunmoon, planets, imagery, sensors, history, hilo
    ...
    [[TimeLengths]]
        ...
    [[Charts]]
        ...
    [[Forecast]]
        ...
```

## General options

#### refresh_interval

How often, in seconds, the page asks for `current.json`, to learn whether a new
archive record has arrived (the "live update"). The value `0` turns the live
update off. Default is `60`.

#### panels

Comma separated list of the panels that the front page shows, in the order in
which they are to be shown. Each name is the name of an `.inc` file in the skin
directory, without the extension. The choices that come with the skin are:

| Panel      | Shows                                                          |
|------------|----------------------------------------------------------------|
| `current`  | The current conditions                                         |
| `forecast` | The forecast for the next few days                             |
| `sun`      | The sun's height through the day                               |
| `moon`     | The moon's phase, rise and set, and so on                      |
| `sunmoon`  | `sun` and `moon` combined. Use it instead of `sun` plus `moon` |
| `planets`  | The planets named in the option `planets`                      |
| `imagery`  | Radar, satellite and map, if set in [`[Extras]`](extras.md)    |
| `sensors`  | Signal strength, batteries and voltages                        |
| `history`  | The charts. A page can have only one.                          |
| `hilo`     | The statistics table                                           |

Default is `current, forecast, sunmoon, planets, imagery, sensors, history,
hilo`.

A panel of your own can be added by writing an `.inc` file and adding its name
to this list. See [*Adding a panel of your
own*](../../custom/horizon-skin.md#adding-a-panel-of-your-own).

Two other things depend on this option. The *Conditions* entries in the
navigation appear only when `panels` includes `history`. The forecast script,
`forecast.js`, loads only when it includes `forecast`.

#### planets

Comma separated list of the bodies that the `planets` panel lists, in the order
in which they are to be shown. Any body that `pyephem` knows can be named.
Default is `mercury, venus, mars, jupiter, saturn`.

#### custom_css

Comma separated list of stylesheets of your own. They load after `horizon.css`,
so their rules take precedence. Each file must be in the skin directory, and
must also be listed in `copy_once` in [`[CopyGenerator]`](copygenerator.md).
Default is none.

#### custom_js

Comma separated list of scripts of your own. They load at the end of the page,
after the skin's own scripts, in the order of the list. As for `custom_css`,
each file must be in the skin directory and listed in `copy_once`. Default is
none.

#### lang_root

For a report whose `HTML_ROOT` is a subdirectory of another report's
`HTML_ROOT`, the path back to that top directory, e.g., "`..`". The language
picker uses it to build its links. Default is "`.`". See [*Choosing the
language*](../../custom/horizon-skin.md#choosing-the-language).

## Which observation types to show

All of these are comma separated lists of observation types. A type without
data is not shown.

#### observations_current

The types to appear in the "current conditions" panel, in the order in which
they are to be shown. Each type gets a tile. The `rain` tile always comes last,
and `rainRate` has no tile of its own, because the `rain` tile shows it.
Default is `outTemp, barometer`.

#### observations_stats

The types to appear in the statistics table on the front page and on the
statistics page, in the order in which they are to be shown. Default is
`outTemp, windSpeed, rain`.

#### observations_rss

The types to appear in the RSS feed. Defaultt is `outTemp, inTemp, barometer, 
windSpeed, rain, rainRate`.

#### obs_type_sum

The types for which a sum is shown, rather than a minimum and a maximum.
Default is `rain`.

#### obs_type_max

The types for which only the maximum is shown. Default is `rainRate`.

A type that is in both `obs_type_sum` and `obs_type_max` is shown as a sum.

#### sensor_connections

The types to appear under connectivity on the `sensors` panel and the
telemetry page, in the order in which they are to be shown. Default is an empty
list.

#### sensor_batteries

The types to appear under battery status on the `sensors` panel and the
telemetry page. Default is an empty list.

#### sensor_voltages

The types to appear under voltage on the `sensors` panel and the telemetry
page. Default is an empty list.

## Charts

In *Horizon*, the options `plot_groups` and `telemetry_plot_groups` name the
plot groups under [`[[JSONFiles]]`](./jsongenerator/#jsonfiles) that are to be
drawn. If they do not exist under `[[JSONFiles]]`, then there will not be any
data available, and so they will not be drawn.

#### plot_groups

The plot groups that the `history` panel will show, in the order in which they
are to be shown. How each group looks is set under [`[[Charts]]`](#charts_1).
Default is `tempdew, wind, rain`.

#### telemetry_plot_groups

The same for the telemetry page. Default is `rx, volt`.

#### periods

The time spans offered for the charts, and for the tiles of the current
conditions, in the order in which they are to be shown. The choices are `day`,
`week`, `month` and `year`. They appear as the *Conditions* entries in the
navigation. Default is `day, week, month, year`.

## [[TimeLengths]]

How far back each time span in `periods` reaches from the newest reading. The
options are named after the time spans. The value is a number of seconds, or a
[duration](../durations.md) such as `27h` or `1y`. A time span without an entry
here is left out of `display.json`. In this case, the display page provides its
own default.

``` ini
[[TimeLengths]]
    day   = 27h
    week  = 7d
    month = 30d
    year  = 1y
```

#### day

Default in `skin.conf` is `27h`. The day has 27 hours so that the evening
before is still in view shortly after midnight.

#### week

Default in `skin.conf` is `7d`.

#### month

Default in `skin.conf` is `30d`.

#### year

Default in `skin.conf` is `1y`.

## [[Charts]]

How the charts look. The labels, type and y-axis of a chart are set here, not
in `[JSONGenerator]`, which writes only the data.

A subsection is named after a plot group, and its subsections after the series
(observation types), as under `[[JSONFiles]]`. Options set higher up are the
defaults of those below. Hence, a chart that is not listed takes the default
options listed directly under `[[Charts]]`. The colors of the charts are not set
here, but in `horizon.css`. See [*Changing the colors of the
charts*](../../custom/horizon-skin.md#changing-the-colors-of-the-charts).

``` ini
[[Charts]]
    plot_type = line
    [[[rain]]]
        plot_type = bar
        [[[[rain]]]]
            label = Rain (hourly total)
```

#### plot_type

How the series are drawn: `line`, `bar` or `vector`. A `vector` chart needs a
series of the type `windvec` or `windgustvec`. May be set directly under
`[[Charts]]`, on a plot group, or on a series. Default is `line`.

#### yscale

The y axis, as a 3-way tuple `ylow, yhigh, min_interval`: the minimum and the
maximum of the axis, and the smallest allowed step. `None` means that the value
is calculated from the data. May be set directly under `[[Charts]]` or on a plot
group. Default is `None, None, None`.

#### vector_rotate

For a `vector` chart, the angle in degrees by which the arrows are turned.
Default is `0`.

#### label

Only on a series. The label shown in the legend and in the tooltip. It is
translated through the `[Texts]` section of the language file. Without it, a
series takes the generic label of its type.

## [[Forecast]]

Controls the `forecast` panel. If the file `data/forecast.json` exists under
`HTML_ROOT`, it takes precedence. See [*Section
[[Forecast]]*](../../custom/horizon-skin.md#section-forecast).

#### browser_fetch

Whether the browser may fetch the forecast from Open-Meteo, `true` or `false`.
Default is `true`.

#### days

How many days to ask Open-Meteo for. Default is `7`.

#### hours

How many forecast times, three hours apart, to show for the day that the reader
selects. Default is `8`, that is, 24 hours.

## [[Languages]]

Lists the languages of the station's pages, for the language picker in the
navigation. The picker appears only with two or more entries. Each subsection
is named after the `lang` of its report, so that the picker can mark the
current page's language as selected.

``` ini
[[Languages]]
    [[[de]]]
        label = Deutsch
        path = .
    [[[en]]]
        label = English
        path = en
```

#### label

The text shown in the picker. Default is the name of the subsection.

#### path

The directory of the pages of that language, relative to the top directory of
the station's pages. `.` means the top directory itself. Default is the name of
the subsection.

See [*Choosing the
language*](../../custom/horizon-skin.md#choosing-the-language)
for how to set up one report per language.

## [[Icons]]

Not present in the shipped `skin.conf`. Chooses the icon of a tile in the
current conditions. Each option is named after an observation type, and its
value is the name of an SVG file in `icons/`, without the extension. An entry
here adds an icon or replaces the built-in one:

``` ini
[[Icons]]
    extraTemp1 = temp
    extraHumid1 = humidity
```

## Other sections in the shipped `skin.conf`

These sections do not belong to `[DisplayOptions]`, but they interact with it:

* **`[Extras]`** holds `radar_img`, `radar_url`, `satellite_img`,
  `satellite_url`, `google_map_apikey` and `googleAnalyticsId`, all commented
  out. The `imagery` panel shows radar, satellite and map only for the options
  that are set. See [`[Extras]`](extras.md).
* **`[CopyGenerator]`** must list in `copy_once` every file named in
  `custom_css` and `custom_js`. See [`[CopyGenerator]`](copygenerator.md).
* **`[JSONGenerator]`** defines the plot groups that `plot_groups` and
  `telemetry_plot_groups` refer to. See [`[JSONGenerator]`](jsongenerator.md).
* **`[Units]` `[[TimeFormats]]`** sets how the times of highs and lows are
  written for each time span. See [`[Units]`](units.md).

## Extending `[DisplayOptions]`

Other options can be added in the same way as for `[Extras]`. Read them in a
template with the `get()` method, supplying a default in case the option is
missing. Use `$to_bool()` for an option that is true or false, and `$to_list()`
for one that is a list.

```