# The JSON generator

The [Image generator](image-generator.md) draws your plots on the server and
saves them as PNG files. The JSON generator does the same work, but instead of
drawing the plot, it writes the numbers behind it.

Why would you want that? Because a web page that has the numbers can do things
a picture cannot. It can resize the chart with the window, show the value under
the pointer, let the reader switch from Celsius to Fahrenheit, and step back
through the history, all without asking the server for anything new. The
[Horizon](horizon-skin.md) skin works this way.

The JSON generator is controlled by the configuration options in the reference
[_[JSONGenerator]_](../reference/skin-options/jsongenerator.md). These options
are specified in the `[JSONGenerator]` section of a skin configuration file.

It changes nothing about the Image generator, and the two happily run side by
side. If you link your PNGs from a forum signature or an email, keep the Image
generator enabled and add this one alongside it.

Let's take a look at how this works.

## Turning it on

Add the generator to the skin's generator list:

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.jsongenerator.JSONGenerator
```

That is all it takes. Without any further configuration, the generator reads
your existing `[ImageGenerator]` section, so every plot you have ever defined,
including ones you added by hand years ago, is available as JSON straight away.

The files go into a `data` subdirectory of `HTML_ROOT`, one per plot, named
after the plot. There is also an `index.json`, which lists what was written. A
page reads that first, and then knows exactly which files exist. It never has
to guess, and it never asks for a sensor your station does not have.

## What the charts take from the images

Sharing the `[ImageGenerator]` section means you define a plot once. That cuts
both ways, and it is worth knowing which way round.

**What the plot is** comes from there. The time span, the aggregation, the data
binding, the observation types, their labels, the line colors, the y scaling:
change any of these and the chart follows, exactly as the PNG does.

**What the picture looks like** does not. Fonts, image dimensions, background
colors, anti-aliasing, marker shapes, label formats: these all describe how to
draw an image on a canvas of a given size, and a browser is not doing that.

So if you set `chart_background_color` and the charts stay as they were, this
is why. Their colors come from the page, through `[[Theme]]` under
`[DisplayOptions]`.

The full split is listed in the skin's own `skin.conf`, with the plot
definitions in `[JSONGenerator]`.

## Using a different set of plots

Suppose you want the charts and the PNGs to show different things. Or suppose
you run no Image generator at all, and would rather not keep a section named
after one. Put the definitions in `[JSONGenerator]` and they are used instead:

``` ini hl_lines="2"
[JSONGenerator]
    chart_line_colors = "#118844"
    [[day_images]]
        [[[mything]]]
            time_length = 6h
            [[[[outTemp]]]]
```

`[ImageGenerator]` is read only where this section holds no plots at all, so
there is no mixing the two.

Same syntax, same option names, nothing shared with the images.

## Showing more than the last four spans

The files above cover the same four windows the Image generator draws: the last
day, week, month and year, each ending now. None of them can answer *"show me
last March"*, because last March was never one of the four.

The archive covers your whole record instead. Turn it on with:

``` ini hl_lines="3"
[JSONGenerator]
    [[Archive]]
        enable = true
```

Now a page can show any span you have data for, back to your first reading.

The archive is not one big file. It is cut into pieces, on three levels of
detail, and a page fetches only the pieces it is showing:

| | covers | written |
|---|---|---|
| the last few days | your station's own readings | one file per day |
| the last few months | a closer grid | one file per month |
| everything before that | a coarser grid, coarser still with age | one file per year |

You do not have to choose between them. The page picks the finest level that
covers the span it is showing.

How far each level reaches is yours to set:
[`raw_days`](../reference/skin-options/jsongenerator.md#raw_days),
[`fine_months`](../reference/skin-options/jsongenerator.md#fine_months) and
[`recent_years`](../reference/skin-options/jsongenerator.md#recent_years).
The defaults suit a station reporting every five minutes.

Because a year that has ended never changes, its file is written once and then
left alone. A station with fourteen years of data rewrites one file per report,
not fourteen.

If you ever import historical data, delete the directory and run the report
again to build it afresh:

``` bash
rm -r ~/weewx-data/public_html/data/archive
weectl report run HorizonReport
```

## Reports that take too long

The first report after you enable the archive has your whole record in front of
it. On a Raspberry Pi with ten years of data, that is a report that runs for
minutes, and WeeWX skips the reports queued behind a long one.

Option [`budget`](../reference/skin-options/jsongenerator.md#budget) is the way
out. It caps how many seconds a report may spend building the archive:

``` ini hl_lines="4"
[JSONGenerator]
    [[Archive]]
        enable = true
        budget = 30
```

A report that runs out of budget writes what it has worked out so far, and the
next report carries on from where it stopped. Your history builds itself over
the next few reports instead of blocking one of them. Set it to `0` if your
machine can afford to do the lot in one go.

The day view is never deferred, whatever the budget says, so today's charts are
complete after the very first report.

Once the archive exists, none of this applies any more. A file is only rewritten
when it has something new to say, so a report settles down to a fraction of a
second, however long your record is.

## Changing the unit used in a chart

The charts follow whatever unit you have set for the report, the same as the
PNGs do. See [*Mixed units*](custom-reports.md#mixed-units).

The difference is that the reader can change it afterwards. Alongside the
readings, the generator writes the arithmetic needed to convert between units,
so a page can offer a unit switch that works without fetching anything. The
Horizon skin puts one in its masthead.

Nothing needs configuring for this. If you would rather not have it, drop the
switch from the template.

## Publishing over FTP or rsync

Nothing special is needed. `FtpGenerator` and `RsyncGenerator` walk
`HTML_ROOT`, so the `data` directory goes along with everything else.

What matters is how much goes up *each cycle*, because that happens every
archive interval. Two things keep it small. A plot built on aggregated data
says the same thing at 10:05 as it did at 10:00, so it is not rewritten, and an
unchanged file is not uploaded. And a finished year in the archive is written
once, so it is uploaded once.

On a slow line, the PNGs are usually the thing to look at first, not the JSON.
The Horizon skin renders them at 1000×360 rather than the classic 500×180,
which is three times the bytes. Either put the old size back:

``` ini
[ImageGenerator]
    image_width = 500
    image_height = 180
```

or drop `weewx.imagegenerator.ImageGenerator` from `[Generators]` altogether,
if you do not link the images anywhere. The page does not need them.

One thing to check on your web server: that it serves `.json` as
`application/json`. Almost all do. If yours does not, the charts will still
work, because `fetch()` does not insist, but it is worth fixing.

## What is inside the files

You do not need to know this to use the generator, or to write a skin that
draws its own charts from `index.json`. If you are writing something that reads
the files directly, the format is documented in the wiki, under [The JSON
generator file
format](https://github.com/weewx/weewx/wiki/The-JSON-generator-file-format).
