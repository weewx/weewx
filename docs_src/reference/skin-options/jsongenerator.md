# [JSONGenerator]

This section is used by generator `weewx.jsongenerator.JSONGenerator` and
controls the JSON files it writes. The plots are not defined here. They are
taken from another section, normally `[ImageGenerator]`, so that a chart drawn
in the browser and the PNG of the same chart show the same thing.

A skin that draws its charts with JavaScript needs this generator. The
*Horizon* skin is the one that ships with WeeWX. See [_The JSON
generator_](../../custom/json-generator.md) for what the files look like and
how a page reads them.

## Where the plots are defined

In this section, or in `[ImageGenerator]`, whichever holds them. This one is
looked at first, so a skin that draws only charts keeps its plots here and needs
no section named after a generator it does not run. A skin that draws both keeps
them in `[ImageGenerator]`, where each plot is then defined once and the chart
and the PNG show the same thing.

Either way the syntax is the Image generator's. See
[_[ImageGenerator]_](imagegenerator.md).

## Which plot options apply

A plot definition can carry any option the Image generator knows. This
generator reads the ones that say what the plot is: `time_length`,
`aggregate_type`, `aggregate_interval`, `data_binding`, `data_type`, `unit`,
`label`, `plot_type`, `color`, `chart_line_colors`, `yscale`, `y_nticks` and
`vector_rotate`.

Everything else describes how to draw an image, such as fonts, image sizes and
marker shapes, and is ignored.

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
