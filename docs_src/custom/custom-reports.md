# Customizing reports

There are two general mechanisms for customizing reports: change options in
one or more configuration files, or change the template files. The former is
generally easier, but occasionally the latter is necessary.

## How to specify options

Options are used to control how reports will look and what they will contain.
For example, they determine which units to use, how to format dates and times,
which data should be in each plot, the colors of plot elements, _etc_.

Options are read from three different types of _configuration files:_

<table>
    <caption>Configuration files</caption>
    <thead>
    <tr class="first_row">
        <td>File</td>
        <td>Use</td>
    </tr>
    </thead>
    <tbody>
    <tr>
        <td class="code">weewx.conf</td>
        <td>
This is the application configuration file.  It contains general configuration
information, such which drivers and services to load, as well as which reports
to run.  Report options can also be specified in this file.
        </td>
    </tr>
    <tr>
        <td class="code">skin.conf</td>
        <td>
This is the skin configuration file.  It contains information specific to a
<em>skin</em>, in particular, which template files to process, and which plots
to generate. Typically, this file is supplied by the skin author.
        </td>
    </tr>
    <tr>
        <td class="code">en.conf<br/>de.conf<br/>fr.conf<br/><em>etc.</em></td>
        <td>
These are internationalization files.  They contain language and locale
information for a specific <em>skin</em>.
        </td>
    </tr>
    </tbody>
</table>

Configuration files are read and processed using the Python utility
[ConfigObj](https://configobj.readthedocs.io), using a format similar to the
MS-DOS ["INI" format](https://en.wikipedia.org/wiki/INI_file). Here's a
simple example:

```ini
[Section1]
    # A comment
    key1 = value1
    [[SubSectionA]]
        key2 = value2
[Section2]
    key3=value3
```

This example uses two sections at root level (sections `Section1` and
`Section2`), and one subsection (`SubSectionA`), which is nested under
`Section1`. The option `key1` is nested under `Section1`, option `key3` is
nested under `Section2`, while option `key2` is nested under subsection
`SubSectionA`.

Note that while this example indents subsections and options, this is
strictly for readability — this isn't Python! It's the number of brackets
that counts in determining nesting, not the indentation! It would torture
your readers, but the above example could be written

```ini
      [Section1]
# A comment
key1 = value1
[[SubSectionA]]
key2 = value2
[Section2]
key3=value3
```

Configuration files take advantage of ConfigObj's ability to organize options
hierarchically into _stanzas_. For example, the `[Labels]` stanza contains the
text that should be displayed for each observation. The `[Units]` stanza
contains other stanzas, each of which contains parameters that control the
display of units.


## Processing order

Configuration files and their sections are processed in a specific order.
Generally, the values from the skin configuration file (`skin.conf`) are
processed first, then options in the WeeWX configuration file (nominally
`weewx.conf`) are applied last. This order allows skin authors to specify the
basic look and feel of a report, while ensuring that users of the skin have
the final say.

To illustrate the processing order, here are the steps for the skin _Seasons_:

* First, a set of options defined in the Python module `weewx.defaults` serve
as the starting point.

* Next, options from the configuration file for _Seasons_, located in
`skins/Seasons/skin.conf`, are merged.

* Next, any options that apply to all skins, specified in the
`[StdReport] / [[Defaults]]` section of the WeeWX configuration file, are
merged.

* Finally, any skin-specific options, specified in the
`[StdReport] / [[Seasons]]` section of the WeeWX configuration, are merged.
These options have the final say.

At all four steps, if a language specification is encountered (option `lang`),
then the corresponding language file will be read and merged. If a unit
specification (option `unit_system`) is encountered, then the appropriate
unit groups are set. For example, if `unit_system=metricwx`, then the unit
for `group_pressure` will be set to `mbar`, etc.

The result is the following option hierarchy, listed in order of increasing
precedence.

<table>
    <caption>Option hierarchy, lowest to highest</caption>
    <thead>
    <tr class="first_row">
        <td>File</td>
        <td>Example</td>
        <td>Comments</td>
    </tr>
    </thead>
    <tbody>
    <tr>
        <td class="code">weewx/defaults.py</td>
        <td class="code">
            [Units]<br/> &nbsp;&nbsp;[[Labels]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;mbar=" mbar"
        </td>
        <td>
These are the hard-coded default values for every option. They are used when
an option is not specified anywhere else. These should not be modified unless
you propose a change to the WeeWX code; any changes made here will be lost
when the software is updated.
        </td>
    </tr>
    <tr>
        <td class="code">skin.conf</td>
        <td class="code">
            [Units]<br/> &nbsp;&nbsp;[[Labels]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;mbar=" hPa"
        </td>
        <td>
Supplied by the skin author, the skin configuration file,
<span class="code">skin.conf</span>, contains options that define the baseline
behavior of the skin. In this example, for whatever reason, the skin author
has decided that the label for units in millibars should be
<span class="code">" hPa"</span> (which is equivalent).
        </td>
    </tr>
    <tr>
        <td class="code">weewx.conf</td>
        <td class="code">
            [StdReport]<br/> &nbsp;&nbsp;[[Defaults]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;[[[Labels]]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[[[[Generic]]]]<br/>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rain=Rainfall
        </td>
        <td>
Options specified under <span class="code">[[Defaults]]</span> apply to
<em>all</em> reports. This example indicates that the label
<span class="example_text">Rainfall</span> should be used for the observation
<span class="code">rain</span>, in all reports.
        </td>
    </tr>
    <tr>
        <td class="code">weewx.conf</td>
        <td class="code">
            [StdReport]<br/> &nbsp;&nbsp;[[SeasonsReport]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;[[[Labels]]]<br/> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[[[[Generic]]]]<br/>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inTemp=Kitchen&nbsp;temperature
        </td>
        <td>
Highest precedence. Has the final say. Options specified here apply to a
<em>single</em> report. This example indicates that the label
<span class="example_text">Kitchen temperature</span> should be used for the
observation <span class="code">inTemp</span>, but only for the report
<em>SeasonsReport</em>.
        </td>
    </tr>
    </tbody>
</table>

!!! Note
    When specifying options, you must pay attention to the number of brackets!
    In the table above, there are two different nesting depths used: one for
    `weewx.conf`, and one for `weewx/defaults.py` and `skin.conf`. This is
    because the stanzas defined in `weewx.conf` start two levels down in the
    hierarchy `[StdReport]`, whereas the stanzas defined in `skin.conf` and
    `defaults.py` are at the root level. Therefore, options specified in
    `weewx.conf` must use two extra sets of brackets.

Other skins are processed in a similar manner although, of course, their name
will be something other than _Seasons_.

Although it is possible to modify the options at any level, as the user of a
skin, it is usually best to keep your modifications in the WeeWX configuration
file (`weewx.conf`) if you can. That way you can apply any fixes or changes
when the skin author updates the skin, and your customizations will not be
overwritten.

If you are a skin author, then you should provide the skin configuration file
(`skin.conf`), and put in it only the options necessary to make the skin render
the way you intend it. Any options that are likely to be localized for a
specific language (in particular, text), should be put in the appropriate
language file.


## Changing languages

By default, the skins that come with WeeWX are set up for the English language,
but suppose you wish to switch to another language? This is usually easy because
all the WeeWX skins have been _internationalized_. For other skins that have not
been internationalized, see the section [_How to internationalize a
skin_](localization.md#how-to-internationalize-a-skin).

There are two aspects to localizing a skin:

1. Changing the _language_; and
2. Changing the _locale_.

In WeeWX, both are controlled by option `lang`.

The _language_ is the more familiar aspect. It controls what the user will see
for labels such as "Outside temperature", or "Max wind speed."

The _locale_ is less familiar. It has to be with regional conventions for
aspects such as decimal separators, or how dates and times are formatted.

### Language

To switch languages, start by checking whether there is a _language_ file for
your particular language. To do this, look in the contents of subdirectory
`lang` in the skin's subdirectory. For example, if you used a package installer
and are using the _Seasons_ skin, you will want to look in
`/etc/weewx/skins/Seasons/lang`. If you did a pip install, look in
`~/weewx-data/skins/Seasons/lang`. Inside, you will see something like this:

```
ls -l /etc/weewx/skins/Seasons/lang
total 136
-rw-rw-r--  1 weewx weewx  9.6K Jan 17 07:30 cz.conf
-rw-rw-r--  1 weewx weewx  9.5K Jan 17 07:30 de.conf
-rw-rw-r--  1 weewx weewx  9.2K Jan 17 07:30 en.conf
-rw-rw-r--  1 weewx weewx  672B Jan 22 07:23 en_AU.conf
-rw-rw-r--  1 weewx weewx  672B Jan 22 07:23 en_CA.conf
-rw-rw-r--  1 weewx weewx  672B Jan 22 07:20 en_GB.conf
-rw-rw-r--  1 weewx weewx  672B Jan 22 07:23 en_NZ.conf
-rw-rw-r--  1 weewx weewx   10K Jan 17 07:30 es.conf
-rw-rw-r--  1 weewx weewx   10K Jan 17 07:30 fr.conf
-rw-rw-r--  1 weewx weewx   12K Jan 17 07:30 gr.conf
-rw-rw-r--  1 weewx weewx  9.7K Jan 17 07:30 it.conf
-rw-rw-r--  1 weewx weewx  9.3K Jan 17 07:30 nl.conf
-rw-rw-r--  1 weewx weewx   10K Jan 22 04:53 no.conf
-rw-rw-r--  1 weewx weewx   15K Jan 17 07:30 th.conf
-rw-rw-r--  1 weewx weewx  9.1K Jan 22 05:55 zh.conf
-rw-rw-r--  1 weewx weewx  9.5K Jan 22 05:55 zh_CN.conf
```

The file names start with either a two-letter code (for example, `en`), or a
four-letter code separated by an underscore (_e.g._, `en_GB`). The first two
letters (`en` in this case) signify the base _language_. The last two letters,
if present, signify any specialized text for a specific _country_ (`GB`, or
Great Britain, in this case).

Given this, from the file listing above, this means that the _Seasons_ skin 
includes text files for the following languages:

| File         | Language                |
|--------------|-------------------------|
| `cz.conf`    | Czeck                   | 
| `de.conf`    | German                  |
| `en.conf`    | English                 |
| `en_AU.conf` | English (Australia)     |
| `en_CA.conf` | English (Canada)        |
| `en_GB.conf` | English (Great Britain) |
| `en_NZ.conf` | English (New Zealand)   |
| `es.conf`    | Spanish                 |
| `fr.conf`    | French                  |
| `it.conf`    | Italian                 |
| `gr.conf`    | Greek                   |
| `nl.conf`    | Dutch                   |
| `th.conf`    | Thai                    |
| `zh.conf`    | Chinese (Traditional)   |
| `zh_CN.conf` | Simplified Chinese      |

If you want to use the _Seasons_ skin and are working with one of these
languages, then you are in luck: you can simply override the `lang` option.
For example, to change the language displayed by the _Seasons_ skin from
English to German, edit `weewx.conf`, and change the highlighted line:

```ini hl_lines="8"
[StdReport]
    ...
    [[SeasonsReport]]
        # The SeasonsReport uses the 'Seasons' skin, which contains the
        # images, templates and plots for the report.
        skin = Seasons
        enable = true
        lang = de
```

By contrast, if the skin has been internationalized, but there is no
localization file for your language, then you will have to supply one. See
the section [_Internationalized, but your language is missing_](localization.md#internationalized-missing-language).


### Locale

A _locale_ controls conventions such as decimal separators and the formatting
of dates. To change locale, you have two choices:

1. Change it for _all_ programs, not just WeeWX, by using the [command
   `localectl
   set-locale`](https://linuxconfig.org/how-to-install-generate-and-list-locale-on-linux).
   For example,

        localectl set-locale LANG=de_DE.utf8
   
    would change the locale to German system-wide.

2. Change it by using the option `lang` in WeeWX. We saw above how option `lang`
   can be used to change the language. However, if a full locale spec is given
   for the option, instead of just the language, WeeWX will change the locale as
   well. For example,

    ```ini hl_lines="8"
    [StdReport]
        ...
        [[SeasonsReport]]
            # The SeasonsReport uses the 'Seasons' skin, which contains the
            # images, templates and plots for the report.
            skin = Seasons
            enable = true
            lang = de_DE.utf8
    ```

   will not only change the language to German, but will also change the locale as
   well. In particular, the report will use the comma (`,`) for the decimal
   separator, and German dates.

#### Multiple locales

This last feature allows different reports to use different locales. Consider
this example:

```ini
[StdReport]
    ...
    [[USReport]]
        skin = Seasons
        enable = true
        lang = en_US.utf8
        HTML_ROOT = /var/www/html/us
    [[FrenchReport]]
        skin = Seasons
        enable = true
        lang = fr_FR.utf8
        HTML_ROOT = /var/www/html/fr
```

This will run two reports, both using the skin _Seasons_. The first report will
use US English and locale, and will be put the results in `/var/www/html/us`.
The second will the French language and locale and will be put in
`/var/www/html/fr`.

## Changing date and time formats

Date and time formats are specified using the same format strings used by
[strftime()](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior).
For example, `%Y` indicates the 4-digit year, and `%H:%M` indicates the time
in hours:minutes. The default values for date and time formats are generally
`%x %X`, which indicates "use the format for the current locale".

Since date formats default to the locale of the computer, a date might appear
with the format of "month/day/year". What if you prefer dates to have the
format "year.month.day"? How do you indicate 24-hour time format versus
12-hour?

Dates and times generally appear in two places: in plots and in tags.

### Date and time formats in images

Most plots have a label on the horizontal axis that indicates when the plot
was generated. By default, the format for this label uses the locale of the
computer on which WeeWX is running, but you can modify the format by
specifying the option `bottom_label_format`.

For example, this would result in a date/time string such as
"2021.12.13 12:45" no matter what the computer's locale:

```ini
[StdReport]
    ...
    [[Defaults]]
        [[[ImageGenerator]]]
            [[[[day_images]]]]
                bottom_label_format = %Y.%m.%d %H:%M
            [[[[week_images]]]]
                bottom_label_format = %Y.%m.%d %H:%M
            [[[[month_images]]]]
                bottom_label_format = %Y.%m.%d %H:%M
            [[[[year_images]]]]
                bottom_label_format = %Y.%m.%d %H:%M
```

### Date and time formats for tags

Each aggregation period has a format for the times associated with that period.
These formats are defined in the `TimeFormats` section. The default formats
use the date and/or time for the computer of the locale on which WeeWX is
running.

For example, this would result in a date/time string such as
"2021.12.13 12:45" no matter what the computer's locale:

```ini
[StdReport]
    ...
    [[Defaults]]
        [[[Units]]]
            [[[[TimeFormats]]]]
                hour        = %H:%M
                day         = %Y.%m.%d
                week        = %Y.%m.%d (%A)
                month       = %Y.%m.%d %H:%M
                year        = %Y.%m.%d %H:%M
                rainyear    = %Y.%m.%d %H:%M
                current     = %Y.%m.%d %H:%M
                ephem_day   = %H:%M
                ephem_year  = %Y.%m.%d %H:%M
```


## Changing unit systems

Each _unit system_ is a set of units. For example, the `METRIC` unit system
uses centimeters for rain, kilometers per hour for wind speed, and degree
Celsius for temperature. The option
[`unit_system`](../reference/weewx-options/stdreport.md#unit_system)
controls which unit system will be used in your reports. The available choices
are `US`, `METRIC`, or `METRICWX`. The option is case-insensitive. See
[_Units_](../reference/units.md) for the units defined in each of these unit
systems.

By default, WeeWX uses `US` (US Customary) system. Suppose you would rather
use the `METRICWX` system for all your reports? Then change this

```ini hl_lines="7"
[StdReport]
    ...
    [[Defaults]]

        # Which unit system to use for all reports. Choices are 'us', 'metric', or 'metricwx'.
        # You can override this for individual reports.
        unit_system = us
```

to this

```ini hl_lines="7"
[StdReport]
    ...
    [[Defaults]]

        # Which unit system to use for all reports. Choices are 'us', 'metric', or 'metricwx'.
        # You can override this for individual reports.
        unit_system = metricwx
```

### Mixed units

However, what if you want a mix? For example, suppose you generally want US
Customary units, but you want barometric pressures to be in millibars? This
can be done by _overriding_ the appropriate unit group.

```ini hl_lines="12"
[StdReport]
    ...
    [[Defaults]]

        # Which unit system to use for all reports. Choices are 'us', 'metric', or 'metricwx'.
        # You can override this for individual reports.
        unit_system = us

        # Override the units used for pressure:
        [[[Units]]]
            [[[[Groups]]]]
                group_pressure = mbar
```

This says that you generally want the US systems of units for all reports, but
want pressure to be reported in _millibars_. Other units can be overridden in
a similar manner.

### Multiple unit systems

Another example. Suppose we want to generate _two_ reports, one in the `US`
system, the other using the `METRICWX` system. The first, call it
_SeasonsUSReport_, will go in the regular directory `HTML_ROOT`. However, the
latter, call it _SeasonsMetricReport_, will go in a subdirectory,
`HTML_ROOT/metric`. Here's how you would do it

```ini
[StdReport]

    # Where the skins reside, relative to WEEWX_ROOT
    SKIN_ROOT = skins

    # Where the generated reports should go, relative to WEEWX_ROOT
    HTML_ROOT = public_html

    # The database binding indicates which data should be used in reports.
    data_binding = wx_binding

    [[SeasonsUSReport]]
        skin = Seasons
        unit_system = us
        enable = true

    [[SeasonsMetricReport]]
        skin = Seasons
        unit_system = metricwx
        HTML_ROOT = public_html/metric
        enable = true
```

Note how both reports use the same _skin_ (that is, skin _Seasons_), but
different unit systems, and different destinations. The first,
_SeasonsUSReport_ sets option unit_system to `us`, and uses the default
destination. By contrast, the second, _SeasonsMetricReport_, uses unit system
`metricwx`, and a different destination, `public_html/metric`.

## Changing labels

Every observation type is associated with a default _label_. For example, in
the English language, the default label for observation type `outTemp` is
generally "Outside Temperature". You can change this label by _overriding_
the default. How you do so will depend on whether the skin you are using has
been _internationalized_ and, if so, whether it offers your local language.

Let's look at an example. If you take a look inside the file
`skins/Seasons/lang/en.conf`, you will see it contains what looks like a big
configuration file. Among other things, it has two entries that look like this:

```ini
...
[Labels]
    ...
    [[Generic]]
        ...
        inTemp = Inside Temperature
        outTemp = Outside Temperature
        ...
```

This tells the report generators that when it comes time to label the
observation variables `inTemp` and `outTemp`, use the strings
"Inside Temperature" and "Outside Temperature", respectively.

However, let's say that we have actually located our outside temperature sensor
in the barn, and wish to label it accordingly. We need to _override_ the label
that comes in the localization file. We could just change the localization
file `en.conf`, but then if the author of the skin came out with a new version,
our change could get lost. Better to override the default by making the change
in `weewx.conf`. To do this, make the following changes in `weewx.conf`:

```ini
    [[SeasonsReport]]
        # The SeasonsReport uses the 'Seasons' skin, which contains the
        # images, templates and plots for the report.
        skin = Seasons
        lang = en
        unit_system = US
        enable = true
        [[[Labels]]]
            [[[[Generic]]]]
                outTemp = Barn Temperature
```        

This will cause the default label Outside Temperature to be replaced with the
new label "Barn Temperature" everywhere in your report. The label for type
`inTemp` will be untouched.
