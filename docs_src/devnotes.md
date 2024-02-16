# Notes for WeeWX developers

This guide is intended for developers contributing to the open source
project WeeWX.

## Goals

The primary design goals of WeeWX are:

- Architectural simplicity. No semaphores, no named pipes, no
  inter-process communications, no complex multi-threading to manage.

- Extensibility. Make it easy for the user to add new features or to
  modify existing features.

- *Fast enough* In any design decision, architectural simplicity and
  elegance trump speed.

- One code base. A single code base should be used for all platforms,
  all weather stations, all reports, and any combination of features.
  Ample configuration and customization options should be provided so
  the user does not feel tempted to start hacking code. At worse, the
  user may have to subclass, which is much easier to port to newer
  versions of the code base, than customizing the base code.

- Minimal dependencies. The code should rely on a minimal number of
  external packages, so the user does not have to go chase them down
  all over the Web before getting started.

- Simple data model. The implementation should use a very simple data
  model that is likely to support many different types of hardware.

- A *pythonic* code base. The code should be written in a style that
  others will recognize.

## Strategies

To meet these goals, the following strategies were used:

- A *micro-kernel* design. The WeeWX engine actually does very
  little. Its primary job is to load and run *services* at runtime,
  making it easy for users to add or subtract features.

- A largely stateless design style. For example, many of the
  processing routines read the data they need directly from the
  database, rather than caching it and sharing with other routines.
  While this means the same data may be read multiple times, it also
  means the only point of possible cache incoherence is through the
  database, where transactions are easily controlled. This greatly
  reduces the chances of corrupting the data, making it much easier to
  understand and modify the code base.

- Isolated data collection and archiving. The code for collecting and
  archiving data run in a single thread that is simple enough that it
  is unlikely to crash. The report processing is where most mistakes
  are likely to happen, so isolate that in a separate thread. If it
  crashes, it will not affect the main data thread.

- A powerful configuration parser. The
  [ConfigObj](https://configobj.readthedocs.io) module, by Michael
  Foord and Nicola Larosa, was chosen to read the configuration file.
  This allows many options that might otherwise have to go in the
  code, to be in a configuration file.

- A powerful templating engine. The
  [Cheetah](https://cheetahtemplate.org/) module was chosen for
  generating html and other types of files from templates. Cheetah
  allows *search list extensions* to be defined, making it easy to
  extend WeeWX with new template tags.

- Pure Python. The code base is 100% Python &mdash; no underlying C
  libraries need be built to install WeeWX. This also means no
  Makefiles are needed.

While WeeWX is nowhere near as fast at generating images and HTML as its
predecessor, *wview* (this is partially because WeeWX uses
fancier fonts and a much more powerful templating engine), it is fast
enough for all platforms but the slowest. I run it regularly on a 500
MHz machine where generating the 9 images used in the *Current
Conditions* page takes just under 2 seconds (compared with 0.4 seconds
for wview).

All writes to the databases are protected by transactions. You can kill
the program at any time without fear of corrupting the databases.

The code makes ample use of exceptions to insure graceful recovery from
problems such as network outages. It also monitors socket and console
timeouts, restarting whatever it was working on several times before
giving up. In the case of an unrecoverable console error (such as the
console not responding at all), the program waits 60 seconds then
restarts the program from the top.

Any *hard* exceptions, that is those that do not involve network and
console timeouts and are most likely due to a logic error, are logged,
reraised, and ultimately cause thread termination. If this happens in
the main thread (not likely due to its simplicity), then this causes
program termination. If it happens in the report processing thread (much
more likely), then only the generation of reports will be affected &mdash;
the main thread will continue downloading data off the instrument and
putting them in the database.

## Units

In general, there are three different areas where the unit system makes
a difference:

1. On the weather station hardware. Different manufacturers use
   different unit systems for their hardware. The Davis Vantage series
   use U.S. Customary units exclusively, Fine Offset and LaCrosse
   stations use metric, while Oregon Scientific, Peet Bros, and Hideki
   stations use a mishmash of US and metric.

2. In the database. Either US or Metric can be used.

3. In the presentation (i.e., html and image files).

The general strategy is that measurements are converted by service
`StdConvert` as they come off the weather station into a target
unit system, then stored internally in the database in that unit system.
Then, as they come off the database to be used for a report, they are
converted into a target unit, specified by a combination of the
configuration file `weewx.conf` and the skin configuration file
`skin.conf`.

## Value `None`

The Python special value `None` is used throughout to signal an
invalid or bad data point. All functions must be written to expect it.

Device drivers should be written to emit `None` if a data value
is bad (perhaps because of a failed checksum). If the hardware simply
doesn't support a data type, then the driver should not emit a value at
all.

The same rule applies to derived values. If the input data for a derived
value are missing, then no derived value should be emitted. However, if
the input values are present, but have value `None`, then the
derived value should be set to `None`.

However, the time value must never be `None`. This is because it
is used as the primary key in the SQL database.

## Time

WeeWX stores all data in UTC (roughly, *Greenwich* or *Zulu*) time.
However, usually one is interested in weather events in local time and
want image and HTML generation to reflect that. Furthermore, most
weather stations are configured in local time. This requires that many
data times be converted back and forth between UTC and local time. To
avoid tripping up over time zones and daylight savings time, WeeWX
generally uses Python routines to do this conversion. Nowhere in the
code base is there any explicit recognition of DST. Instead, its
presence is implicit in the conversions. At times, this can cause the
code to be relatively inefficient.

For example, if one wanted to plot something every 3 hours in UTC time,
it would be very simple: to get the next plot point, just add 10,800 to
the epoch time:

```
next_ts = last_ts + 10800 
```

But, if one wanted to plot something for every 3 hours *in local time*
(that is, at 0000, 0300, 0600, etc.), despite a possible DST change in
the middle, then things get a bit more complicated. One could modify the
above to recognize whether a DST transition occurs sometime between
`last_ts` and the next three hours and, if so, make the necessary
adjustments. This is generally what `wview` does. WeeWX takes a
different approach and converts from UTC to local, does the arithmetic,
then converts back. This is inefficient, but bulletproof against changes
in DST algorithms, etc.:

```
time_dt = datetime.datetime.fromtimestamp(last_ts)
delta = datetime.timedelta(seconds=10800)
next_dt = time_dt + delta
next_ts = int(time.mktime(next_dt.timetuple()))
```

Other time conversion problems are handled in a similar manner.

For astronomical calculations, WeeWX uses the latitude and longitude
specified in the configuration file. If that location does not
correspond to the computer's local time, reports with astronomical
times will probably be incorrect.

## Archive records

An archive record's timestamp, whether in software or in the database,
represents the *end time* of the record. For example, a record
timestamped 05-Feb-2016 09:35, includes data from an instant after
09:30, through 09:35. Another way to think of it is that it is exclusive
on the left, inclusive on the right. Schematically:

```
09:30 < dateTime <= 09:35
```

Database queries should reflect this. For example, to find the maximum
temperature for the hour between timestamps 1454691600 and 1454695200,
the query would be:

```
SELECT MAX(outTemp) FROM archive 
  WHERE dateTime > 1454691600 and dateTime <= 1454695200;
```

This ensures that the record at the beginning of the hour (1454691600)
does not get included (it belongs to the previous hour), while the
record at the end of the hour (1454695200) does.

One must be constantly be aware of this convention when working with
timestamped data records.

Better yet, if you need this kind of information, use an
[xtypes](https://github.com/weewx/weewx/wiki/WeeWX-V4-user-defined-types)
call:

```
max_temp = weewx.xtypes.get_aggregate('outTemp',
                                      (1454691600, 1454695200),
                                      'max',
                                      db_manager)
```

It will not only make sure the limits of the query are correct, but will
also decide whether the daily summary optimization can be used
([details below](#daily-summaries)). If not, it will use the regular
archive table.

## Internationalization

Generally, WeeWX is locale aware. It will emit reports using the local
formatting conventions for date, times, and values.

## Exceptions

In general, your code should not simply swallow an exception. For
example, this is bad form:

```
    try:
        os.rename(oldname, newname)
    except:
        pass
```

While the odds are that if an exception happens it will be because the
file `oldname` does not exist, that is not guaranteed. It could
be because of a keyboard interrupt, or a corrupted file system, or
something else. Instead, you should test explicitly for any expected
exception, and let the rest go by:

```
    try:
        os.rename(oldname, newname)
    except OSError:
        pass
```

WeeWX has a few specialized exception types, used to rationalize all
the different types of exceptions that could be thrown by the underlying
libraries. In particular, low-level I/O code can raise a myriad of
exceptions, such as USB errors, serial errors, network connectivity
errors, *etc.* All device drivers should catch these exceptions and
convert them into an exception of type `WeeWxIOError` or one of
its subclasses.

## Naming conventions

How you name variables makes a big difference in code readability. In
general, long names are preferable to short names. Instead of this,

```
p = 990.1
```

use this,

```
pressure = 990.1
```

or, even better, this:

```
pressure_mbar = 990.1
```

WeeWX uses a number of conventions to signal the variable type, although
they are not used consistently.

<table class="no_indent">
  <caption>Variable suffix conventions</caption>
  <tr class="first_row">
    <td>Suffix</td>
    <td>Example</td>
    <td>Description</td>
  </tr>
  <tr>
    <td class="code">_ts</td>
    <td class="code">first_ts</td>
    <td>Variable is a timestamp in <a href="https://en.wikipedia.org/wiki/Unix_time">unix epoch time</a>.</td>
  </tr>
  <tr>
    <td class="code">_dt</td>
    <td class="code">start_dt</td>
    <td>Variable is an instance of <a href="https://docs.python.org/3/library/datetime.html#datetime-objects"><span class="code">datetime.datetime</span></a>, usually in <em>local time</em>.</td>
  </tr>
  <tr>
    <td class="code">_d</td>
    <td class="code">end_d</td>
    <td>Variable is an instance of <a href="https://docs.python.org/3/library/datetime.html#date-objects"><span class="code">datetime.date</span></a>, usually in <em>local time</em>.</td>
  </tr>
  <tr>
    <td class="code">_tt</td>
    <td class="code">sod_tt</td>
    <td>Variable is an instance of <span class="code">time.struct_time</span> (a <a href="https://docs.python.org/3/library/time.html#time.struct_time"><em>time tuple</em>)</a>, usually in <em>local time</em>.</td>
  </tr>
  <tr>
    <td class="code">_vh</td>
    <td class="code">pressure_vh</td>
    <td>Variable is an instance of <span class="code">weewx.units.ValueHelper</span>.</td>
  </tr>
  <tr>
    <td class="code">_vt</td>
    <td class="code">speed_vt</td>
    <td>Variable is an instance of <span class="code">weewx.units.ValueTuple</span>.</td>
  </tr>
</table>

## Code style

Generally, we try to follow the [PEP 8 style
guide](https://www.python.org/dev/peps/pep-0008/), but there are *many*
exceptions. In particular, many older WeeWX function names use
camelCase, but PEP 8 calls for snake_case. Please use snake_case for new
code.

Most modern code editors, such as Eclipse, or PyCharm, have the ability
to automatically format code. Resist the temptation and *don't use this
feature!* Two reasons:

- Unless all developers use the same tool, using the same settings, we
  will just thrash back and forth between slightly different versions.

- Automatic formatters play a useful role, but some of what they do
  are really trivial changes, such as removing spaces in otherwise
  blank lines. Now if someone is trying to figure out what real,
  syntactic, changes you have made, s/he will have to wade through all
  those extraneous *changed lines,* trying to find the important
  stuff.

If you are working with a file where the formatting is so ragged that
you really must do a reformat, then do it as a separate commit. This
allows the formatting changes to be clearly distinguished from more
functional changes.

When invoking functions or instantiating classes, use the fully
qualified name. Don't do this:

```
from datetime import datetime
now = datetime()
```

Instead, do this:

```
import datetime
now = datetime.datetime()
```

## Git work flow

We use Git as the source control system. If Git is still mysterious to
you, bookmark this: [*Pro Git*](https://git-scm.com/book/en/v2), then
read the chapter *Git Basics*. Also recommended is the article [*How to
Write a Git Commit Message*](https://cbea.ms/git-commit/).

The code is hosted on [GitHub](https://github.com/weewx/weewx). Their
[documentation](https://docs.github.com/en/get-started) is very
extensive and helpful.

We generally follow Vincent Driessen's [branching
model](http://nvie.com/posts/a-successful-git-branching-model/). Ignore
the complicated diagram at the beginning of the article, and just focus
on the text. In this model, there are two key branches:

- 'master'. Fixes go into this branch. We tend to use fewer
  *hot fix* branches and, instead, just incorporate any fixes
  directly into the branch. Releases are tagged relative to this
  branch.

- 'development' (called `develop` in Vince's article).
  This is where new features go. Before a release, they will be merged
  into the `master` branch.

What this means to you is that if you submit a pull request that
includes a new feature, make sure you commit your changes relative to
the *development* branch. If it is just a bug fix, it should be
committed against the `master` branch.

### Forking the repository

The WeeWX GitHub repository is configured to use
[GitHub Actions](https://docs.github.com/en/actions/learn-github-actions/understanding-github-actions)
to run Continuous Integration (CI) workflows automatically if certain
`git` operations are done on branches under active development.

This means that CI workflows will also be run on any forks that you may have
made if the configured `git` action is done. This can be confusing if you get
an email from GitHub if these tasks fail for some reason on your fork.

To control GitHub Actions for your fork, see the recommended solutions in this
[GitHub discussion](https://github.com/orgs/community/discussions/26704#discussioncomment-3252979)
on this topic.

## Tools

### Python

[JetBrain's PyCharm](http://www.jetbrains.com/pycharm/) is exellent,
and now there's a free Community Edition. It has many advanced
features, yet is structured that you need not be exposed to them until
you need them. Highly recommended.

### HTML and Javascript

For Javascript, [JetBrain's
WebStorm](http://www.jetbrains.com/webstorm/) is excellent, particularly
if you will be using a framework such as Node.js or Express.js.

## Daily summaries {#daily-summaries}

This section builds on the section [*The database*](custom/introduction.md#the-database)
in the *Customization Guide*. Read it first.

The big flat table in the database (usually called table
`archive`) is the definitive table of record. While it includes a
lot of information, querying it can be slow. For example, to find the
maximum temperature of the year would require scanning the entire table,
which might include 100,000 or more records. To speed things up, WeeWX
includes *daily summaries* in the database as an optimization.

In the daily summaries, each observation type gets its own table, which
holds a statistical summary for the day. For example, for outside
temperature observation type `outTemp`, this table would be
named `archive_day_outTemp`. This is what it would look like:

<table>
  <caption>Structure of the <span class="code">archive_day_outTemp</span> daily summary</caption>
  <tr class="code first_row">
    <td>dateTime</td>
    <td>min</td>
    <td>mintime</td>
    <td>max</td>
    <td>maxtime</td>
    <td>sum</td>
    <td>count</td>
    <td>wsum</td>
    <td>sumtime</td>
  </tr>
  <tr class="code">
  <td>1652425200</td>
    <td>44.7</td>
    <td>1652511600</td>
    <td>56.0</td>
    <td>1652477640</td>
    <td>38297.0</td>
    <td>763</td>
    <td>2297820.0</td>
    <td>45780</td>
  </tr>
  <tr class="code">
    <td>1652511600</td>
    <td>44.1</td>
    <td>1652531280</td>
    <td>66.7</td>
    <td>1652572500</td>
    <td>76674.4</td>
    <td>1433</td>
    <td>4600464.0</td>
    <td>85980</td>
  </tr>
  <tr class="code">
    <td>1652598000</td>
    <td>50.3</td>
    <td>1652615220</td>
    <td>59.8</td>
    <td>1652674320</td>
    <td>32903.0</td>
    <td>611</td>
    <td>1974180.0</td>
    <td>36660</td>
  </tr>
  <tr class="code">
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
    <td>...</td>
  </tr>
</table>

This is what the table columns mean:

<table class="no_indent">
  <tr class="first_row">
    <td>Name</td>
    <td>Meaning</td>
  </tr>
  <tr>
    <td class="first_col code">dateTime</td>
    <td>The time of the start of day in <a href="https://en.wikipedia.org/wiki/Unix_time">unix epoch time</a>. This is the <em>primary key</em> in the database. It must be unique, and it cannot be null.</td>
  </tr>
  <tr>
    <td class="first_col code">min</td>
    <td>The minimum temperature seen for the day. The unit is whatever unit system the main archive table uses (generally given by the first record in the table).</td>
  </tr>
  <tr>
    <td class="first_col code">mintime</td>
    <td>The time in unix epoch time of the minimum temperature.</td>
  </tr>
  <tr>
    <td class="first_col code">max</td>
    <td>The maximum temperature seen for the day. The unit is whatever unit system the main archive table uses (generally given by the first record in the table).</td>
  </tr>
  <tr>
    <td class="first_col code">maxtime</td>
    <td>The time in unix epoch time of the maximum temperature.</td>
  </tr>
  <tr>
    <td class="first_col code">sum</td>
    <td>The sum of all the temperatures for the day.</td>
  </tr>
  <tr>
    <td class="first_col code">count</td>
    <td>The number of records in the day.</td>
  </tr>
  <tr>
    <td class="first_col code">wsum</td>
    <td>The weighted sum of all the temperatures for the day. The weight is the
        archive interval in seconds. That is, for each record, the temperature
        is multiplied by the length of the archive record in seconds, then 
        summed up.</td>
  </tr>
  <tr>
    <td class="first_col code">sumtime</td>
    <td>The sum of all the archive intervals for the day in seconds. If the 
        archive interval didn't change during the day, then this number would
        be <span class="code">interval * 60 * count</span>.</td>
  </tr>
</table>

Note how the average temperature for the day can be calculated as `wsum
/ sumtime`. This will be true even if the archive interval
changes during the day.

Now consider an extensive variable such as `rain`. The total
rainfall for the day will be given by the field `sum`. So,
calculating the total rainfall for the year can be done by scanning and
summing only 365 records, instead of potentially tens, or even hundreds,
of thousands of records. This results in a dramatic speed up for report
generation, particularly on slower machines such as the Raspberry Pi,
working off an SD card.

### Wind summaries

The daily summary for wind includes six additional fields. This is what
they mean:

<table class="no_indent">
  <tr class="first_row">
    <td>Name</td>
    <td>Meaning</td>
  </tr>
  <tr>
    <td class="first_col code">max_dir</td>
    <td>The direction of the maximum wind seen for the day.</td>
  </tr>
  <tr>
    <td class="first_col code">xsum</td>
    <td>The sum of the x-component (east-west) of the wind for the day.</td>
  </tr>
  <tr>
    <td class="first_col code">ysum</td>
    <td>The sum of the y-component (north-south) of the wind for the day.</td>
  </tr>
  <tr>
    <td class="first_col code">dirsumtime</td>
    <td>The sum of all the archive intervals for the day in seconds,
        <em>which contributed to <span class="code">xsum</span> 
        and <span class="code">ysum</span></em>.</td>
  </tr>
  <tr>
    <td class="first_col code">squaresum</td>
    <td>The sum of the wind speed squared for the day.</td>
  </tr>
  <tr>
    <td class="first_col code">wsquaresum</td>
    <td>The sum of the weighted wind speed squared for the day. That is the
        wind speed is squared, then multiplied by the archive interval in 
        seconds, then summed for the day. This is useful for calculating
        RMS wind speed.</td>
  </tr>
</table>

Note that the RMS wind speed can be calculated as

```
math.sqrt(wsquaresum / sumtime)
```

## Glossary

This is a glossary of terminology used throughout the code.

<table class='no_indent'>
  <caption>Terminology used in WeeWX</caption>
  <tr class="first_row">
    <td>Name</td>
    <td>Description</td>
  </tr>
  <tr>
    <td class="text_highlight">archive interval</td>
    <td>
WeeWX does not store the raw data that comes off a weather station. Instead,
it aggregates the data over a length of time, the <em>archive interval</em>,
and then stores that.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">archive record</td>
    <td>
While <em>packets</em> are raw data that comes off the weather station,
<em>records</em> are data aggregated by time. For example, temperature may be
the average temperature over an <em>archive interval</em>. These are the data
stored in the SQL database
    </td>
  </tr>
  <tr>
    <td class="text_highlight code">config_dict</td>
    <td>
All configuration information used by WeeWX is stored in the <em>configuration
file</em>, usually with the name <span class="code">weewx.conf</span>. By
convention, when this file is read into the program, it is called 
<span class="code">config_dict</span>, an instance of the class
<span class="code">configobj.ConfigObj</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">datetime</td>
    <td>
An instance of the Python object <span class="code">datetime.datetime</span>.
Variables of type datetime usually have a suffix <span class="code">_dt</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">db_dict</td>
    <td>
A dictionary with all the data necessary to bind to a database. An example for
SQLite would be
<pre>
{
  'driver':'db.sqlite',
  'SQLITE_ROOT':'/home/weewx/archive',
  'database_name':'weewx.sdb'
 }</pre>
 An example for MySQL would be
 <pre>
 {
   'driver':'db.mysql',
   'host':'localhost',
   'user':'weewx',
   'password':'mypassword',
   'database_name':'weewx'
 }</pre>
    </td>
  </tr>
  <tr>
    <td class="text_highlight">epoch time</td>
    <td>
Sometimes referred to as &quot;unix time,&quot; or &quot;unix epoch time.&quot;
The number of seconds since the epoch, which is 1 Jan 1970 00:00:00 UTC. Hence,
it always represents UTC (well... after adding a few leap seconds... but, close
enough). This is the time used in the databases and appears as type
<span class="code">dateTime</span> in the SQL schema, perhaps an unfortunate
name because of the similarity to the completely unrelated Python type <span
class="code">datetime</span>. Very easy to manipulate, but it is a big opaque
number.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">LOOP packet</td>
    <td>
The real-time data coming off the weather station. The terminology "LOOP" comes
from the Davis series of weather stations. A LOOP packet can contain all
observation types, or it may contain only some of them ("Partial packet").
    </td>
  </tr>
  <tr>
    <td class="text_highlight">observation&nbsp;type</td>
    <td>
A physical quantity measured by a weather station (<i>e.g.</i>,
<span class="code">outTemp</span>) or something derived from it (<i>e.g.</i>,
<span class="code">dewpoint</span>).
    </td>
  </tr>
  <tr>
    <td class="text_highlight code">skin_dict</td>
    <td>
All configuration information used by a particular skin is stored in the
<em>skin configuration file</em>, usually with the name
<span class="code">skin.conf</span>. By convention, when this file is read
into the program, it is called <span class="code">skin_dict</span>, an
instance of the class <span class="code">configobj.ConfigObj</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">SQL type</td>
    <td>
A type that appears in the SQL database. This usually looks something like
<span class="code">outTemp</span>, <span class="code">barometer</span>,
<span class="code">extraTemp1</span>, and so on.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">standard unit system</td>
    <td>
A complete set of units used together. Either <span class="code">US</span>,
<span class="code">METRIC</span>, or <span class="code">METRICWX</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">time stamp</td>
    <td>
A variable in unix epoch time. Always in UTC. Variables carrying a time stamp
usually have a suffix <span class="code">_ts</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">tuple-time</td>
    <td>
An instance of the Python object <span class="code">
<a href="http://docs.python.org/2/library/time.html#time.struct_time">
time.struct_time</a></span>. This is a 9-way tuple that represent a time. It
could be in either local time or UTC, though usually the former. See module
<span class="code"><a href="http://docs.python.org/2/library/time.html">time</a></span>
for more information. Variables carrying tuple time usually have a suffix
<span class="code">_tt</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight">value tuple</td>
    <td>
A 3-way tuple. First element is a value, second element the unit type the value
is in, the third the unit group. An example would be <span class="code">(21.2,
&#39;degree_C&#39;, &#39;group_temperature&#39;)</span>.
    </td>
  </tr>
  <tr>
    <td class="text_highlight"><span class="code">WEEWX_ROOT</span></td>
    <td>
The location of the station data area. Unfortunately, due to legacy reasons, 
its value can be interpreted two different ways. In the 
configuration file <span class="code">weewx.conf</span>, its value
is relative to the location of the configuration file. In memory, in the 
data structure <span class="code">config_dict</span>, it is an absolute path.
</td>
  </tr>
</table>
