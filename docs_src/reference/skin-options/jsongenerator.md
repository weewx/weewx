# [JSONGenerator]

This section is used by generator `weewx.jsongenerator.JSONGenerator`. The JSON
generator writes JSON files containing the numbers that a web page can use to
draw charts. It writes the readings and nothing about how they look. Labels, the
type of a chart and the y axis are up to the skin. The *Horizon* skin sets them
under
[`[DisplayOptions]`](../../custom/horizon-skin.md#changing-what-a-chart-shows).
This section holds both the options of the generator and the list of files it
writes.

A skin that draws its charts with JavaScript needs this generator. The
*Horizon* skin is the one that ships with WeeWX. See [_The JSON
generator_](../../custom/json-generator.md) for how it works, and [_JSON data
files_](../json-files.md) for what the files look like.

## [[JSONFiles]]

The files to write. A subsection is a plot group, which is a family of files. Its
name begins the names of the files: the plot group `tempdew` writes
`tempdew-2026-10-03.json` and so on. It is also the name that a skin refers to,
e.g., in the option `plot_groups` of Horizon. A subsection of a plot group is a
series, named after its observation type:

``` ini
[JSONGenerator]
    [[JSONFiles]]
        aggregate_type = none
        [[[tempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]
        [[[rain]]]
            aggregate_type = sum
            aggregate_interval = 1h
            [[[[rain]]]]
```

An option that is set above a plot group or a series, directly in `[[JSONFiles]]`,
applies to everything below it. An option set lower down wins.

The generator does not read the plots of `[ImageGenerator]`. A plot says how a
chart looks, and this generator writes no such thing.

## Plot group and series options

These options describe which numbers a file holds. An option that is not listed
here has no effect.

#### aggregate_interval

The time over which a series is aggregated, in seconds. Alternatively, a
[duration notation](../durations.md) can be used. The archive files already hold
an aggregate for each of their own aggregation intervals, so this option applies
only where it is longer than the aggregation interval of a file, such as the
rain of each hour in a file of minutes. The aggregates then sit at every _n_-th
position of the series. Optional. Without it, a series takes the aggregation
interval of the file.

#### aggregate_type

How the readings of an aggregation interval are combined. Choices include `avg`,
`max`, `min`, `sum` and `last`. Optional. Default is `avg`. Types that are
totals, such as `rain` and `ET`, are always summed, and `windDir` and
`windGustDir` always take the direction of the average wind vector, whatever this
option says. The value `none`, which the Image generator reads as "every
reading", is treated like the default, since a file holds one value for each
aggregation interval.

#### data_binding

The database the series reads from, by the name of its binding. Optional. Default
is `wx_binding`.

#### data_type

The observation type of the series, for when it is not the name of the series'
section. This allows a type to appear in a plot group more than once, e.g., with
different aggregate types. Optional. Default is the name of the section.

The types `windvec` and `windgustvec` are wind vectors. A file holds their
components as well as their speed. See [_JSON data files_](../json-files.md).

#### unit

Normally, the unit used in a file is set by whatever [unit group the types are
in](../../custom/custom-reports.md#mixed-units). This option overrides the
unit of a plot group, e.g., `degree_C`. Optional.

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

The archive holds the plot groups of [`[[JSONFiles]]`](#jsonfiles). A series
without an `aggregate_type` of its own is averaged over each aggregation
interval. The files go into `archive`, below [`json_dest_dir`](#json_dest_dir).

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
