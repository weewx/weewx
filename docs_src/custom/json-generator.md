# The JSON generator

The JSON generator writes the numbers behind your plots as JSON files. A web
page that has the numbers can do things that a static image cannot. It can resize the
chart with the window, show the value under the pointer, let the reader switch
from Celsius to Fahrenheit, and step back through the history, all without
asking the server for anything new. The [*Horizon*](horizon-skin.md) skin works
this way.

The generator does for a page that draws its own charts what the [Image
generator](image-generator.md) does for a page that shows images. The two are
independent: they share no files, and either can run without the other. The
difference is that the files hold the readings and nothing about how they look.
A skin sets the labels, the type of each chart and the y-axis itself.

The JSON generator is controlled by the configuration options in the reference
[_[JSONGenerator]_](../reference/skin-options/jsongenerator.md). These options
are specified in the `[JSONGenerator]` section of a skin configuration file.

Let's take a look at how this works.

## Turning it on

Add the generator to the skin's generator list:

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.jsongenerator.JSONGenerator
```

Then list the files to write, in a `[JSONGenerator]` section. A plot group, such
as `[[[tempdew]]]`, is a family of files, ordered by date granularity such as
day, month, or year.

``` ini
[JSONGenerator]
    [[JSONFiles]]
        [[[tempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]
```

The options are documented in the reference, under
[_[JSONGenerator]_](../reference/skin-options/jsongenerator.md#jsonfiles). They
are about which numbers a file holds: the observation types, the aggregation,
and the unit. How the numbers are shown, such as the labels, the type of the
chart, the y-axis and the colors, is up to the page. *Horizon* sets the first
three in its [`[DisplayOptions]`](horizon-skin.md#changing-what-a-chart-shows),
and takes the colors of its chart lines from its stylesheet. See
[_Changing the colors of the charts_](horizon-skin.md#changing-the-colors-of-the-charts).

The generated files go into a `data` subdirectory of `HTML_ROOT`. The archived
JSON data are in `data/archive`, which goes back to the beginning of your
database. There is also a `meta.json`, which holds the units the readings can be
shown in.

## Going back through the record

A static image shows a fixed window, such as the last day or the last week. It
cannot answer *"show me last March"*. The archive can, because it covers your
entire database.

The archive is not one big file. Instead, it is cut into pieces, on three levels
of detail. A page fetches only the pieces it is showing:

|                        | covers                                               | written            |
|------------------------|:-----------------------------------------------------|:-------------------|
| the last few days      | your station's own readings                          | one file per day   |
| the last few months    | a shorter aggregation interval                       | one file per month |
| everything before that | a longer aggregation interval, longer still with age | one file per year  |

You do not have to choose between them. The page picks the finest level that
covers the time it is showing.

How far each level reaches is yours to set:
[`days`](../reference/skin-options/jsongenerator.md#days),
[`months`](../reference/skin-options/jsongenerator.md#months) and
[`years`](../reference/skin-options/jsongenerator.md#years).
The defaults suit a station that reports every five minutes.

Because a year that has ended never changes, its file is written once and then
left alone. A station with fourteen years of data rewrites one file per report,
not fourteen.

If you ever import historical data, delete the directory and run the report
again to build it afresh. For example:

``` bash
rm -r ~/weewx-data/public_html/data/archive
weectl report run HorizonReport
```

## Reports that take too long

The first report needs to process your entire database. On a Raspberry Pi with
ten years of data, that can take many minutes. If it takes too long, WeeWX will
skip subsequent reports until the report clears.

Option [`budget`](../reference/skin-options/jsongenerator.md#budget) is the way
out. It caps how many seconds a report may spend building the archive:

``` ini hl_lines="3"
[JSONGenerator]
    [[Archive]]
        budget = 30
```

A report that runs out of budget starts no further file, and the next report
carries on from where it stopped. Your history builds itself over the next few
reports instead of blocking one of them. Set it to `0` if your
machine can afford to do the lot in one go.

The day view is never deferred, whatever the budget says, so today's charts are
complete after the very first report.

Once the archive exists, none of this applies anymore. A file is only rewritten
when it has something new to say, so a report settles down to a fraction of a
second, however big your database is.

## Changing the unit used in a chart

The charts follow whatever unit you have set for the report. See [*Mixed
units*](custom-reports.md#mixed-units).

The difference from an image is that the reader can change it afterward.
Alongside the readings, the generator writes the arithmetic needed to convert
between units, so a page can offer a unit picker that works without fetching
anything. The *Horizon* skin has one in its navigation.

Nothing needs configuring for this. If you would rather not have it, drop the
unit picker from the template.

## Publishing the files

Nothing special is needed. `FtpGenerator` and `RsyncGenerator` walk `HTML_ROOT`,
so the `data` directory goes along with everything else.

What matters is how much goes up *each cycle*, because that happens every
archive interval. A file is rewritten only when it has a new reading, and an
unchanged file is not uploaded. A finished year is written once, so it is
uploaded once.

One thing to check on your web server: that it serves `.json` as
`application/json`. Almost all do. If yours does not, the charts will still
work, because `fetch()` does not insist, but it is worth fixing.

## Reading the files in a skin of your own

The structure of the files is documented in [_JSON data
files_](../reference/json-files.md). To use them in a skin other than *Horizon*,
you do not have to write the code that fetches them. The *Horizon* skin ships it
as a separate file, `weewx-json.js`, which knows nothing about Horizon or about
the chart library that *Horizon* uses. It reads `meta.json`, the archive index and
the file `display.json` of the skin, works out which archive files cover a time
span, fetches them, joins them into one series, and converts the readings to
another unit system. What a skin has to say about its charts, e.g., a label, is
in `display.json`. Without that file, `weewx-json.js` draws every plot group as
a line, labelled with the name of its observation type.

Copy `weewx-json.js` from the *Horizon* skin directory into your skin, list it in
`copy_once` in `[CopyGenerator]`, and load it before your own script:

``` html
<script src="weewx-json.js"></script>
<script src="my-charts.js"></script>
```

Then, in your script:

``` javascript
var data = WeeWXJSON.create({ dataDir: 'data' });

data.load()
  .then(function () {
    // The last 27 hours of the plot group 'tempdew'
    var to = Math.floor(Date.now() / 1000);
    return data.chart('tempdew', to - 27 * 3600, to);
  })
  .then(function (chart) {
    if (!chart) return;
    chart.series.forEach(function (series) {
      // series.label, series.time[i], series.values[i], ...
    });
    // [minimum, maximum, step] of a y axis that holds 8 gridlines
    var axis = data.yAxis(chart, 8);
  });
```

The methods are listed in the comment at the top of `weewx-json.js`. The skin
*Horizon* (`horizon.js`) is a full example.
