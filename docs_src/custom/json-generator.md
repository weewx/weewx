# The JSON generator

The [Image generator](image-generator.md) renders plots to PNG on the server. The JSON
generator is its data-only counterpart: it reads the *same* plot definitions, fetches the
*same* series, applies the *same* unit conversion and labels — then writes the numbers as
JSON instead of drawing them.

What you do with those numbers is up to the skin. The `Horizon` skin draws them in the browser, which is what makes its charts resize with the window,
show a value under the pointer, and step back through the history.

The generator changes nothing about the Image generator, and the two can run side by
side. If you link your PNGs from a forum signature or an email, keep the Image generator
enabled and add this one alongside.

## Enabling it

Add it to the skin's generator list:

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.jsongenerator.JSONGenerator
```

That is enough. Without any further configuration the generator reads the existing
`[ImageGenerator]` section, so **every plot you have ever defined — including ones you
added by hand years ago — is available as JSON immediately.**

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
  by `weeplot.utilities.scaletime()`. A chart that uses them lines up with the PNG of
  the same plot.
- `yscale` is the y axis from the plot options, as `[min, max, increment]`. Any member
  may be `null`, meaning "work it out from the data". Wind direction is configured
  `0, 360, 45`, and a chart that ignores this runs to 400 degrees.
- `daynight` carries the sunrise and sunset times for the window, so a client can shade
  the night the way the PNGs do — plus the **civil twilight** around each of them, as
  `dawn` and `dusk` bands. Dusk is not an edge, and the PNGs can only approximate it
  with a gradient measured in pixels; with these a client can fade across the time it
  actually takes, which is half an hour in central Europe and hours in a northern
  summer.
- Wind vectors arrive as **magnitude plus compass direction** (`values` and
  `directions`), rather than as raw complex components.

`index.json` lists what was written. A client reads it first and then knows exactly which
files exist — no guessing, and no 404 for every sensor your station does not have.

## The history archive

The files above are snapshots of four fixed windows — the same four the Image generator
draws. They cannot answer *"show me last March"*, because that window was never rendered.

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
  station with fourteen years of data rewrites one file per report cycle, not fourteen.
  The current year is rewritten when the data reach into the next grid slot. There is
  nothing new to say before that.
- **A client fetches only the years it is showing.** Looking at last March costs one
  file, not the whole record.

Within a file the grid is regular, so the timestamps are *implied* by `start` and
`interval` rather than stored:

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

That roughly halves the file. One year of hourly temperature and dew point is about
100 kB, or 35 kB once your web server compresses it.

To rebuild the archive — after importing historical data, for example — delete the
directory and run the report again:

``` bash
rm -r ~/weewx-data/public_html/data/archive
weectl report run HorizonReport
```

## Options

All options go in `[JSONGenerator]` in the skin configuration file, and all are optional.

<table class="indent">
    <tbody>
    <tr><td class="first_col">source</td>
        <td>Which section holds the plot definitions. Default: <span
        class="code">ImageGenerator</span>, so an existing skin needs no new
        configuration.</td></tr>
    <tr><td class="first_col">json_dest_dir</td>
        <td>Subdirectory of <span class="code">HTML_ROOT</span> to write into. Default:
        <span class="code">data</span>.</td></tr>
    <tr><td class="first_col">round</td>
        <td>Decimal places to keep. Default: 3. Set to <span class="code">None</span> for
        full precision.</td></tr>
    <tr><td class="first_col">json_indent</td>
        <td>Indentation for the JSON. Default: none, which is compact. Set to 2 while
        debugging.</td></tr>
    <tr><td class="first_col">include_daynight</td>
        <td>Whether to emit sunrise and sunset times for shading. Default:
        <span class="code">true</span>.</td></tr>
    </tbody>
</table>

And in `[[Archive]]`:

<table class="indent">
    <tbody>
    <tr><td class="first_col">enable</td>
        <td>Whether to write the archive at all. Default:
        <span class="code">false</span>.</td></tr>
    <tr><td class="first_col">resolution</td>
        <td>The grid interval. Default: <span class="code">1h</span>. A finer grid gives
        a sharper zoom at proportionally larger files.</td></tr>
    <tr><td class="first_col">aggregate_type</td>
        <td>How to aggregate onto the grid. Default: <span class="code">avg</span>. Rain,
        ET, hail, snow and lightning counts are always summed.</td></tr>
    <tr><td class="first_col">max_days</td>
        <td>How far back to go. Default: 0, meaning the whole record.</td></tr>
    <tr><td class="first_col">source_group</td>
        <td>Which time-period section defines the plot groups. Default:
        <span class="code">day_images</span>.</td></tr>
    <tr><td class="first_col">strip_prefix</td>
        <td>What to remove from the plot names to get the group name
        (<span class="code">daytempdew</span> → <span class="code">tempdew</span>).
        Default: <span class="code">day</span>.</td></tr>
    <tr><td class="first_col">dest_dir</td>
        <td>Where to write the archive. Default:
        <span class="code">data/archive</span>.</td></tr>
    </tbody>
</table>

## Costs

Measured on a development machine (x86-64, SQLite) against 400 days of synthetic data at
a ten-minute archive interval, with the plot set the Horizon skin ships with — 48 period
files and 11 plot groups spanning two calendar years:

| | first run | every run after |
|---|---|---|
| Period files (48) | 0.6 s | 0.6 s |
| Archive (22 files) | 4.9 s | 0.2 s |

The archive's first build is a one-off, and it scales with the length of your record: a
station with ten years of data pays for ten years once. After that only the current year
is touched, and only once per grid slot. The steady-state figure above is the one that
matters for a station running every five minutes.

These numbers will be several times larger on a Raspberry Pi. They are given to show the
*shape* of the cost — a large one-off, then almost nothing — not as a benchmark.

## What it takes from [ImageGenerator], and what it does not

The generator reads the section the images use, so a plot is defined once.
That cuts both ways, and it is worth knowing which way round.

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

## A picture of the current readings

WeeWX has always been able to draw a time series. It has never been able to draw the
*numbers* — and a picture of the current readings is what people paste into a forum
post, a signature or a chat window. A screenshot goes stale the moment it is taken; a
file at a fixed URL stays current on its own.

`weewx.summaryimage.SummaryImageGenerator` writes one, redrawn each report cycle:

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

Labels, units and formatting come from the skin, so the image says the same thing in the
same language as the page beside it. It is drawn at twice the requested size and then
downsampled, which is what keeps it sharp on a phone.

A type this station does not have costs that one reading, not the image.

<table class="indent">
    <tbody>
    <tr><td class="first_col">enable</td>
        <td>Whether to draw the image at all. Default:
        <span class="code">false</span>.</td></tr>
    <tr><td class="first_col">filename</td>
        <td>Where to write it, relative to <span class="code">HTML_ROOT</span>. Default:
        <span class="code">current.png</span>.</td></tr>
    <tr><td class="first_col">observations</td>
        <td>Which readings, in order. Four to six fit comfortably.</td></tr>
    <tr><td class="first_col">width, columns</td>
        <td>Pixel width and how many readings per row. Defaults: 900 and 2.</td></tr>
    <tr><td class="first_col">scale</td>
        <td>Render at this multiple, then downsample. Default: 2.</td></tr>
    <tr><td class="first_col">background_color, title_color,<br>value_color, label_color,
        sub_color, rule_color</td>
        <td>Colours, as <span class="code">#RRGGBB</span>.</td></tr>
    <tr><td class="first_col">*_font_path, *_font_size</td>
        <td>Fonts, relative to the skin directory. A missing font falls back to PIL's
        built-in one, which cannot render accented characters — so keep the TrueType
        files with the skin.</td></tr>
    </tbody>
    </table>

## Publishing over FTP or rsync

Nothing special is needed: `FtpGenerator` and `RsyncGenerator` walk `HTML_ROOT`, so the
`data/` and `data/archive/` directories go along with everything else.

What matters is how much goes up *each cycle*, because that runs every archive interval:

- **Aggregated plots are skipped when nothing changed.** A year plot built on daily
  averages says the same thing at 10:05 as it did at 10:00, so it is not rewritten — and
  an unchanged file is not uploaded. This is the same `stale_age` / aggregation test the
  Image generator applies to its PNGs.
- **Finished years in the archive are written once.** Their timestamps never change
  again, so `ftpupload` skips them from the second run onwards.

Measured on the demo station (400 days, both a German and an English rendering, so
roughly double a single-language site):

| | files | size |
|---|---|---|
| First upload, everything | 344 | 10.6 MB |
| Each cycle after that | 84 | 1.8 MB |

Two thirds of that steady-state figure is PNGs, because this skin renders them at
1000×360 rather than the classic 500×180 — sharp on a phone, but three times the bytes.
On a slow line, either go back to the old size:

``` ini
[ImageGenerator]
    image_width = 500
    image_height = 180
```

…or drop `weewx.imagegenerator.ImageGenerator` from `[Generators]` entirely, if you do
not link the images anywhere. The page does not need them.

One thing to check on the server: that it serves `.json` as `application/json`. Almost
all do. If yours does not, the charts will still work — `fetch()` does not insist — but
it is worth fixing.
