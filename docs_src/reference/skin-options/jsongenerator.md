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

## General options

#### json_dest_dir

Where the files go, relative to `HTML_ROOT`. Default is `data`.

#### periods

Whether to write one file per plot per time span, holding every reading in it.
These are the four files named after the spans in `[[day_images]]`,
`[[week_images]]` and so on. Default is `True`.

Set it to `False` where `[[Archive]]` is enabled. The archive covers the same
spans on grids chosen to suit them, and reaches back as far as the record goes.

#### round

How many decimal places a reading is written with. Three is plenty for weather
data and keeps the files small. Default is `3`.

#### include_daynight

Whether to write the times of sunrise and sunset, so a chart can shade the
night. Requires `pyephem`. Default is `True`.

## [[Archive]]

The archive is the whole record, cut into files a page can fetch one at a time.
It is written on three grids: the station's own readings for the last few days,
a closer grid per month, and one per calendar year that coarsens with age. A
page picks the finest grid that covers the span it is showing.

#### enable

Whether to write the archive at all. Default is `False`.

#### aggregate_type

How readings are combined into a slot. Default is `avg`.

#### resolution

The grid a year file is written on, for the years named by
[`recent_years`](#recent_years). May be a number of seconds or a duration such
as `1h`. Default is `1h`.

#### recent_years

How many calendar years, counting back from this one, are written at
[`resolution`](#resolution). Older years use
[`coarse_resolution`](#coarse_resolution). Default is `2`.

#### coarse_resolution

The grid the older year files are written on. A year at four hours is about
2,200 slots. Default is `4h`.

#### fine_months

How many calendar months, counting back from this one, are written on a closer
grid than the year files. This is what a week or a month view is drawn from.
Default is `2`.

#### fine_resolution

The grid those months are written on. Default is `900`, that is, fifteen
minutes.

#### raw_days

How many days are written at the station's own archive interval, one file per
day. This is what the day view is drawn from. Default is `30`.

Files older than this are removed on the next run, so the disk cost of this
tier does not grow.

#### raw_resolution

The grid the raw files are written on. `0`, the default, uses the station's
archive interval, which is what makes the tier raw.

#### budget

How many seconds a report may spend building the archive, as a number or a
duration. Default is `30`. `0` removes the limit.

Where a report runs out of budget, the file it was working on is written
holding what was worked out, and the next report carries on from there. No
single report runs long, however much history there is behind it.

The raw tier is never deferred. It is what the day view is drawn from, and a
page without today is of little use.

#### extremes

Comma separated list of observation types that also carry their lowest and
highest reading in each slot, not only the aggregate. An average is the wrong
thing to remember for a gust: averaging it into a four hour slot turns a storm
into a breeze. Each name costs two more queries per slot. Default is
`windGust, windSpeed, rainRate, radiation, UV`.

#### rebuild

How often every file is built from the whole database again, rather than
carried forward from the one already on disk. Default is `0`, which never does.

A file that has been written is correct for the span it covers, and the index
is checked against the directory on every run. Set it to a number of hours to
have the files rewritten anyway, for a station whose history has been edited.

#### source_group

The subsection of the plot definitions the groups are taken from. The archive
covers every span itself, so one set of definitions is enough. Default is
`day_images`.

#### strip_prefix

Text to remove from the front of each plot name, so that `daytempdew` becomes
`tempdew`. Default is `day`.

#### max_days

How far back the archive reaches, in days. Default is `0`, the whole record.

#### dest_dir

Where the archive files go, relative to `HTML_ROOT`. Default is
`data/archive`.

#### round

How many decimal places an archive reading is written with. Default is `2`.
