# The JSON generator

The [Image generator](image-generator.md) renders plots to PNG on the server.
The JSON generator is its data-only counterpart: it reads the *same* plot
definitions, fetches the *same* series, applies the *same* unit conversion and
labels, then writes the numbers as JSON instead of drawing them.

What you do with those numbers is up to the skin. The `Horizon` skin draws them
in the browser, which is what makes its charts resize with the window, show a
value under the pointer, and step back through the history.

The generator changes nothing about the Image generator, and the two can run
side by side. If you link your PNGs from a forum signature or an email, keep the
Image generator enabled and add this one alongside.

## Enabling it

Add it to the skin's generator list:

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.jsongenerator.JSONGenerator
```

That is enough. Without any further configuration the generator reads the
existing `[ImageGenerator]` section, so **every plot you have ever defined,
including ones you added by hand years ago, is available as JSON immediately.**

## What it writes

For each plot with data, one file named after the plot:

```
public_html/
└── data/
    ├── index.json          ← what exists
    ├── daytempdew.json
    ├── weektempdew.json
    └── …
```

A plot file looks like this:

``` json
{
  "name": "daytempdew",
  "generated": 1787518200,
  "start": 1787420400, "stop": 1787518200, "x_interval": 10800,
  "yscale": [null, null, null],
  "unit": "degree_C", "unit_label": "°C",
  "daynight": {"first": "day", "transitions": [1787430000, 1787479000],
               "twilight": [{"from": 1787428000, "to": 1787430000, "dir": "dawn"}]},
  "series": [
    {"obs_type": "outTemp", "label": "Outside Temperature", "plot_type": "line",
     "color": "#4282b4", "time": [1787420400, …], "values": [15.2, …]}
  ]
}
```

A few things worth knowing:

- Times and values are **parallel arrays**, not a list of pairs. It is smaller on the
wire and is the shape charting libraries want.
- Gaps in the data are `null`, so a chart can break the line rather than draw through
the gap.
- `color` comes from `chart_line_colors` in the skin, so the charts inherit whatever
palette you configured for the PNGs.
- `start`, `stop` and `x_interval` are the axis the ImageGenerator would draw, snapped
by `weeplot.utilities.scaletime()`. A chart that uses them lines up with the PNG
of the same plot.
- `yscale` is the y axis from the plot options, as `[min, max, increment]`. Any member
may be `null`, meaning "work it out from the data". Wind direction is configured
`0, 360, 45`, and a chart that ignores this runs to 400 degrees.
- `daynight` carries the sunrise and sunset times for the window, so a client can shade
the night the way the PNGs do, plus the **civil twilight** around each of them,
as `dawn` and `dusk` bands. Dusk is not an edge, and the PNGs can only
approximate it with a gradient measured in pixels; with these a client can fade
across the time it actually takes, which is half an hour in central Europe and
hours in a northern summer.
- Wind vectors arrive as **magnitude plus compass direction** (`values` and
`directions`), rather than as raw complex components.

`index.json` lists what was written. A client reads it first and then knows
exactly which files exist. There is no guessing, and no 404 for every sensor
your station does not have.

## The history archive

The files above are snapshots of four fixed windows, the same four the Image
generator draws. They cannot answer *"show me last March"*, because that window
was never rendered.

The archive covers the whole record instead, split by calendar year:

``` ini
[JSONGenerator]
    [[Archive]]
        enable = true
        resolution = 1h
```

```
data/archive/
├── index.json
├── daynight-2025.json
├── tempdew-2025.json
├── tempdew-2026.json
└── …
```

Two properties of that split matter on the small machines WeeWX usually runs on:

- **A finished year never changes.** It is written once and then skipped forever. A
station with fourteen years of data rewrites one file per report cycle, not
fourteen. The current year is rewritten when the data reach into the next grid
slot. There is nothing new to say before that.
- **A client fetches only the years it is showing.** Looking at last March costs one
file, not the whole record.

Within a file the grid is regular, so the timestamps are *implied* by `start`
and `interval` rather than stored:

``` json
{
  "name": "tempdew",
  "start": 1735686000, "interval": 3600, "count": 8760,
  "unit": "degree_C", "unit_label": "°C",
  "series": [
    {"obs_type": "outTemp", "label": "Outside Temperature",
     "aggregate_type": "avg", "values": [3.1, 2.8, null, …]}
  ]
}
```

That roughly halves the file. One year of hourly temperature and dew point is
about 100 kB, or 35 kB once your web server compresses it.

To rebuild the archive, after importing historical data for example, delete the
directory and run the report again:

``` bash
rm -r ~/weewx-data/public_html/data/archive
weectl report run HorizonReport
```

## Options

The generator is controlled by the configuration options in the reference
[_[JSONGenerator]_](../reference/skin-options/jsongenerator.md). They are
specified in the `[JSONGenerator]` section of a skin configuration file, and all
of them are optional.

Two of them decide how much work a report does, and are worth reading together.
[`periods`](../reference/skin-options/jsongenerator.md#periods) writes one file
per plot per span, which a skin that reads those four files by name needs. Where
`[[Archive]]` is enabled it can be turned off: the archive covers the same spans
and more. [`budget`](../reference/skin-options/jsongenerator.md#budget) caps how
long a report may spend building the archive, which is what keeps a first run on
a small machine from taking minutes.

## Costs

Measured on a development machine (x86-64, SQLite) against 400 days of synthetic
data at a half-hourly archive interval, with the plot set the Horizon skin ships
with. That is 175321 records, 44 period files and 125 archive files spanning
eleven calendar years:

| | first run | every run after |
|---|---|---|
| Period files (44) | 1.9 s | 0.02 to 0.14 s |
| Archive (125 files) | 20.6 s | 0.16 s |

The three grids are what keep the first figure down: at one hour for every year
it is 46.8 s instead of 20.6 s, for a file set nobody reads that closely.

That first figure is still a report that runs for half a minute here, and for
minutes on a Raspberry Pi. WeeWX skips the reports behind a long one, and after
`max_wait` (600 s) it launches a second report thread on top of it. `budget` is
the way out: set it, and no report runs longer than that, because a file that
runs out of budget is written holding what was worked out and continued by the
next one. The history builds itself over a few reports instead of blocking one.

The archive's first build is a one-off, and it scales with the length of your
record: a station with ten years of data pays for ten years once. After that a
finished year is skipped altogether, and the year in progress is carried forward
rather than worked out again: the file on disk already holds every slot but its
last, so only the slots since the last report are read from the database. That
is why the steady-state figure does not grow with the length of the record, and
it is the figure that matters for a station reporting every five minutes.

A month or a year that has ended never changes, so its file is written once and
then kept, whatever the current settings say should be written now. The index is
checked against the directory on every run, so a file that survives is a file
that stays in use, and losing the index costs a directory listing rather than
the whole record.

These numbers will be several times larger on a Raspberry Pi. They are given to
show the *shape* of the cost: a large one-off, then almost nothing. It is not a
benchmark.

## What it takes from [ImageGenerator], and what it does not

The generator reads the section the images use, so a plot is defined once. That
cuts both ways, and it is worth knowing which way round.

**What the plot is** comes from there: the time span, the aggregation, the data
binding, the observation types, their labels, the line colours, the y scaling.
Change any of those and the chart follows, as the PNG does.

**What the picture looks like** does not. Fonts, image dimensions, background
colours, anti-aliasing, marker shapes, label formats: those describe how to draw
an image on a canvas of a given size, and a browser is not doing that. Setting
`chart_background_color` leaves the charts as they were; their colours come from
the page, through `[[Theme]]` under `[DisplayOptions]`.

The full split is listed in the skin's own `skin.conf`, at the head of the
`[ImageGenerator]` section.

### Keeping them apart

Sharing the section is the default because it saves defining a plot twice. Point
`source` somewhere else and it stops:

``` ini
[JSONGenerator]
    source = MyPlots

[MyPlots]
    chart_line_colors = "#118844"
    [[day_images]]
        [[[mything]]]
            time_length = 6h
            [[[[outTemp]]]]
```

Same syntax, same option names, nothing shared with the images. Useful if you
want charts and PNGs to differ, or if you run no ImageGenerator at all and would
rather not keep a section named after it.

## A picture of the current readings

WeeWX has always been able to draw a time series. It has never been able to draw
the *numbers*. A picture of the current readings is what people paste into a
forum post, a signature or a chat window. A screenshot goes stale the moment it
is taken; a file at a fixed URL stays current on its own.

`weewx.summaryimage.SummaryImageGenerator` writes one, redrawn each report
cycle:

``` ini
[Generators]
    generator_list = …, weewx.summaryimage.SummaryImageGenerator

[SummaryImageGenerator]
    enable = true
    filename = current.png
    observations = outTemp, windSpeed, rain, barometer
    width = 900
    columns = 2
```

Labels, units and formatting come from the skin, so the image says the same
thing in the same language as the page beside it. It is drawn at twice the
requested size and then downsampled, which is what keeps it sharp on a phone.

A type this station does not have costs that one reading, not the image.

The options are in the reference,
[_[SummaryImageGenerator]_](../reference/skin-options/summaryimagegenerator.md).

## Publishing over FTP or rsync

Nothing special is needed: `FtpGenerator` and `RsyncGenerator` walk `HTML_ROOT`,
so the `data/` and `data/archive/` directories go along with everything else.

What matters is how much goes up *each cycle*, because that runs every archive
interval:

- **Aggregated plots are skipped when nothing changed.** A year plot built on daily
averages says the same thing at 10:05 as it did at 10:00, so it is not
rewritten, and an unchanged file is not uploaded. This is the same `stale_age` /
aggregation test the Image generator applies to its PNGs.
- **Finished years in the archive are written once.** Their timestamps never change
again, so `ftpupload` skips them from the second run onwards.

Measured on the demo station (400 days, both a German and an English rendering,
so roughly double a single-language site):

| | files | size |
|---|---|---|
| First upload, everything | 344 | 10.6 MB |
| Each cycle after that | 84 | 1.8 MB |

Two thirds of that steady-state figure is PNGs, because this skin renders them
at 1000×360 rather than the classic 500×180: sharp on a phone, but three times
the bytes. On a slow line, either go back to the old size:

``` ini
[ImageGenerator]
    image_width = 500
    image_height = 180
```

…or drop `weewx.imagegenerator.ImageGenerator` from `[Generators]` entirely, if
you do not link the images anywhere. The page does not need them.

One thing to check on the server: that it serves `.json` as `application/json`.
Almost all do. If yours does not, the charts will still work, since `fetch()`
does not insist, but it is worth fixing.
