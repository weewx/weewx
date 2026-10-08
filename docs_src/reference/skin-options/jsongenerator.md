# [JSONGenerator]

This section is used by generator `weewx.jsongenerator.JSONGenerator`. The JSON
generator works independently of the Image generator. It reads the same kind of
plot definitions, but instead of drawing a plot it writes the numbers behind it,
as JSON files that a web page can read. This section holds both the options of the
generator and the plot definitions it draws from.

A skin that draws its charts with JavaScript needs this generator. The
*Horizon* skin is the one that ships with WeeWX. See [_The JSON
generator_](../../custom/json-generator.md) for how it works, and [_JSON data
files_](../json-files.md) for what the files look like.

## Plot definitions

The plots are defined in this section, with the same structure as the plots of
the Image generator. A subsection for each time period, such as `[[day_images]]`,
holds a subsection for each plot, and that holds a subsection for each line:

``` ini
[JSONGenerator]
    [[day_images]]
        time_length = 27h
        [[[daytempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]
        [[[dayrain]]]
            plot_type = bar
            [[[[rain]]]]
                aggregate_type = sum
                aggregate_interval = 1h
                label = Rain (hourly total)
```

The archive is made from the plots of `[[day_images]]`. A plot named `daytempdew`
becomes the plot group `tempdew`. The other time periods, e.g., `[[week_images]]`,
set only how long a time span is. See [`time_length`](#time_length).

An option that is set above a plot, on the time period or directly in this
section, applies to every plot and line below it. An option set lower down wins.

If this section holds no plots, the generator falls back on the plots of
`[ImageGenerator]`, so that a skin written for the Image generator still works.
This is a stopgap for existing skins. Define the plots here.

## Plot options

These options describe what a plot shows. They are not about how it looks. The JSON
files hold the data, and the page that reads them decides on colors, fonts and
sizes. An option not listed here has no effect.

#### data_binding

The database the plot reads from, by the name of its binding. Optional. Default
is `wx_binding`.

#### time_length

The nominal length of the time period, in seconds. Alternatively, a [duration
notation](../durations.md) can be used. A page reads it from `skin.json` to
decide how much time its chart shows. Set it on a time period, such as
`[[week_images]]`. Optional. Default is `86400` (one day).

#### unit

Normally, the unit used in a plot is set by whatever [unit group the types are
in](../../custom/custom-reports.md#mixed-units). This option overrides the
unit of a plot, e.g., `degree_C`. Optional.

#### y_nticks

The nominal number of ticks along the y axis, which decides the step of the
axis the generator suggests. Optional. Default is `10`.

#### yscale

A 3-way tuple (`ylow`, `yhigh`, `min_interval`), where `ylow` and `yhigh` are
the minimum and maximum y-axis values, and `min_interval` is the minimum tick
interval. A value of `None` is chosen from the data. The archive files carry the
result, as `yscale`. Optional. Default is `None, None, None`.

## Line options

These options are set on a line, or above it for all the lines below.

#### aggregate_interval

The time over which a line is aggregated, in seconds. Alternatively, a [duration
notation](../durations.md) can be used. The archive files already hold an
aggregate for each of their own aggregation intervals, so this option applies
only to a bar (`plot_type = bar`) that is to total over a longer time, such as
the rain of each hour in a file of minutes. Optional. Without it, a line takes the
aggregation interval of the file.

#### aggregate_type

How the readings of an aggregation interval are combined. Choices include `avg`,
`max`, `min`, `sum` and `last`. Optional. Default is `avg`. Types that are
totals, such as `rain` and `ET`, are always summed, and `windDir` and
`windGustDir` always take the direction of the average wind vector, whatever this
option says. The value `none`, which the Image generator reads as "every
reading", is treated like the default, since a file holds one value for each
aggregation interval.

#### data_type

The observation type of the line, for when it is not the name of the line's
section. This allows a type to appear in a plot more than once, e.g., with
different aggregate types. Optional. Default is the name of the section.

#### label

The label of the line, which a page shows in a legend and in a tooltip. If it
names an entry under `[Texts]`, the translation is used. Optional. Default is
the generic label of the type under `[Labels]` / `[[Generic]]`, or else the
name of the type.

#### plot_type

The type of plot for a line. Choices are `line`, `bar` and `vector`. A page draws
a `bar` as bars, and a `vector` as arrows. A `vector` line needs a type that
holds a wind vector, such as `windvec`. Optional. Default is `line`.

#### vector_rotate

Rotates the vectors by this many degrees, positive being clockwise. If westerly
winds dominate at your location, you may want to specify `+90`, so that the
average vector points straight up, rather than lies flat along the x axis. The
archive file carries the angle in the opposite sense, as the series property
`vector_rotate`, ready for a page to apply. Optional. Default is `0`.

## General options

#### json_dest_dir

Where the files go, relative to `HTML_ROOT`. Default is `data`.

#### round

How many decimal places a reading is written with. Default is `2`.

#### include_daynight

Whether to write the times of sunrise and sunset, so a chart can shade the
night. Requires `pyephem`. Default is `True`.

## [[Archive]]

The archive is the whole database, cut into files the browser can fetch one at a
time. There are three tiers: one file per day for the last few days, at the
archive interval; one file per month, at a shorter aggregation interval than the
years; and one file per calendar year, at an aggregation interval that grows
with age. The browser picks the tier with the shortest aggregation interval that
covers the time it is showing.

The archive holds the plots of `[[day_images]]`, named without the prefix
`day`, e.g., `tempdew` for `daytempdew`. A line without an `aggregate_type` of
its own is averaged over each aggregation interval. The files go into
`archive`, below [`json_dest_dir`](#json_dest_dir).

#### years

How many calendar years, counting back from this one, are written at
[`year_resolution`](#year_resolution). Older years use
[`old_year_resolution`](#old_year_resolution). Default is `2`.

#### year_resolution

The aggregation interval of the year files, for the years named by
[`years`](#years). May be a number of seconds or a duration such as `1h`.
Default is `1h`.

#### old_year_resolution

The aggregation interval of the older year files. A year at four hours holds
about 2,200 values per series. Default is `4h`.

#### months

How many calendar months, counting back from this one, are written at a shorter
aggregation interval than the year files, one file per month. Default is `2`.

#### month_resolution

The aggregation interval of the month files. Default is `900`, that is, fifteen
minutes.

#### days

How many days are written at the station's own archive interval, one file per
day. This is what the day view is drawn from. Default is `30`.

Files older than this are removed on the next run, so the disk cost of this
tier does not grow.

#### day_resolution

The aggregation interval of the day files. `0`, the default, uses the archive
interval that most archive records of the day have. The day files then hold the
values of the archive records as they are.

#### budget

How many seconds a report may spend building the archive, as a number or a
duration. Default is `30`. `0` removes the limit.

A report that runs out of budget starts no further file, and the next report
carries on where it stopped. The newest files come first, so the older years
fill in over the next reports.

The day tier is never deferred. It is what the day view is drawn from, and a
page without today is of little use.

#### extremes

Comma separated list of observation types that also carry their lowest and
highest value in each aggregation interval, not only the aggregate. An average
is the wrong thing to remember for a gust: averaged over four hours, a storm
turns into a breeze. Each name costs two more queries per aggregation interval.
Default is `windGust, windSpeed, rainRate, UV`.

#### rebuild

How often every file is built from the whole database again, rather than
carried forward from the one already on disk. Default is `0`, which never does.

A file that has been written is correct for the time it covers, and the archive
index is checked against the directory on every run. Set it to a number of hours to
have the files rewritten anyway, for a station whose history has been edited.
