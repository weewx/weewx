# The JSON generator

The JSON generator writes the numbers behind your plots as JSON files. A web
page that has the numbers can do things that a picture cannot. It can resize the
chart with the window, show the value under the pointer, let the reader switch
from Celsius to Fahrenheit, and step back through the history, all without
asking the server for anything new. The [Horizon](horizon-skin.md) skin works
this way.

The generator does for a page that draws its own charts what the [Image
generator](image-generator.md) does for a page that shows pictures. The two are
independent: they share no files, and either can run without the other.

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

Then define the plots, in a `[JSONGenerator]` section. The structure is the one
of the Image generator: a time period, `[[day_images]]`, holds the plots, and a
plot holds the lines.

``` ini
[JSONGenerator]
    [[day_images]]
        time_length = 27h
        [[[daytempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]
```

The options of a plot are documented in the reference, under
[_[JSONGenerator]_](../reference/skin-options/jsongenerator.md#plot-options).
The files hold what a plot shows: the observation types, their labels, the
aggregation and the y scaling. How it looks, such as the colors, is up to the
page. Horizon takes the colors of its chart lines from its stylesheet. See
[_Changing the colors of the charts_](horizon-skin.md#changing-the-colors-of-the-charts).

A skin with no plots in `[JSONGenerator]` falls back on its `[ImageGenerator]`
plots, so that a skin written for the Image generator keeps working. The
fallback is for skins that exist already. Define the plots of a new skin in
`[JSONGenerator]`.

The files go into a `data` subdirectory of `HTML_ROOT`. The readings are in
`data/archive`, which covers your whole record, back to your first reading.
There is also a `skin.json`, which holds the `time_length` of each time period
and the units the readings can be shown in. A page reads that first.

## Going back through the record

A picture shows a fixed window, such as the last day or the last week, ending
now. It cannot answer *"show me last March"*. The archive can, because it covers
your whole record.

The archive is not one big file. It is cut into pieces, on three levels of
detail, and a page fetches only the pieces it is showing:

| | covers | written |
|---|---|---|
| the last few days | your station's own readings | one file per day |
| the last few months | a shorter aggregation interval | one file per month |
| everything before that | a longer aggregation interval, longer still with age | one file per year |

You do not have to choose between them. The page picks the finest level that
covers the time it is showing.

How far each level reaches is yours to set:
[`days`](../reference/skin-options/jsongenerator.md#days),
[`months`](../reference/skin-options/jsongenerator.md#months) and
[`years`](../reference/skin-options/jsongenerator.md#years).
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

The first report after you add the generator has your whole record in front of
it. On a Raspberry Pi with ten years of data, that is a report that runs for
minutes, and WeeWX skips the reports queued behind a long one.

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

Once the archive exists, none of this applies any more. A file is only rewritten
when it has something new to say, so a report settles down to a fraction of a
second, however long your record is.

## Changing the unit used in a chart

The charts follow whatever unit you have set for the report. See [*Mixed
units*](custom-reports.md#mixed-units).

The difference from a picture is that the reader can change it afterwards.
Alongside the readings, the generator writes the arithmetic needed to convert
between units, so a page can offer a unit picker that works without fetching
anything. The Horizon skin has one, in its navigation.

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
files_](../reference/json-files.md). To use them in a skin other than Horizon,
you do not have to write the code that fetches them. The Horizon skin ships it
as a separate file, `weewx-json.js`, which knows nothing about Horizon or about
the chart library that Horizon uses. It reads `skin.json` and the archive index,
works out which archive files cover a time span, fetches them, joins them into
one series, and converts the readings to another unit system.

Copy `weewx-json.js` from the Horizon skin directory into your skin, list it in
`copy_once` in `[CopyGenerator]`, and load it before your own script:

``` html
<script src="weewx-json.js"></script>
<script src="my-charts.js"></script>
```

Then, in your script:

``` javascript
var data = WeeWXJSON.create({ dataDir: 'data' });

data.loadManifest()
  .then(function () { return data.loadIndex(); })
  .then(function () {
    // The last 27 hours of the plot group 'tempdew'
    var to = Math.floor(Date.now() / 1000);
    return data.plot('tempdew', to - 27 * 3600, to);
  })
  .then(function (plot) {
    if (!plot) return;
    plot.series.forEach(function (series) {
      // series.label, series.time[i], series.values[i], ...
    });
  });
```

The methods are listed in the comment at the top of `weewx-json.js`. The skin
`Horizon` (`horizon.js`) is a full example.
