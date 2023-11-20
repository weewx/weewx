# [CheetahGenerator]

This section contains the options for the Cheetah generator. It applies
to `skin.conf` only.

#### search_list

This is the list of search list objects that will be scanned by the
template engine, looking for tags. See the section *[Defining new
tags](../../custom/cheetah-generator.md#defining-new-tags)* and the [Cheetah
documentation](https://cheetahtemplate.org/) for details on search
lists. If no `search_list` is specified, a default list will be used.

#### search_list_extensions

This defines one or more search list objects that will be appended to
the `search_list`. For example, if you are using the
"seven day" and "forecast" search list extensions, the option would
look like

``` ini
search_list_extensions = user.seven_day.SevenDay, user.forecast.ForecastVariables
```

#### encoding

As Cheetah goes through the template, it substitutes strings for all tag
values. This option controls which encoding to use for the new strings.
The encoding can be chosen on a per-file basis. All the encodings
listed in the Python documentation [*Standard
Encodings*](https://docs.python.org/3/library/codecs.html#standard-encodings)
are available, as well as these WeeWX-specific encodings:

<table class="indent">
    <tbody>
    <tr class="first_row">
        <td>Encoding</td>
        <td>Comments</td>
    </tr>
    <tr>
        <td class="code first_col">html_entities</td>
        <td>
Non 7-bit characters will be represented as HTML entities (<i>e.g.</i>, the
degree sign will be represented as "<span class="code">&amp;#176;</span>")
        </td>
    </tr>
    <tr>
        <td class="code first_col">strict_ascii</td>
        <td>Non 7-bit characters will be ignored.</td>
    </tr>
    <tr>
        <td class="code first_col">normalized_ascii</td>
        <td>
Replace accented characters with non-accented analogs (<i>e.g.</i>, 'ö' will
be replaced with 'o').
        </td>
    </tr>
    </tbody>
</table>

The encoding `html_entities` is the default. Other common choices are `utf8`,
`cp1252` (*a.k.a.* Windows-1252), and `latin1`.

#### template

The name of a template file. A template filename must end with `.tmpl`.
Filenames are case-sensitive. If the template filename has the letters `YYYY`,
`MM`, `WW` or `DD` in its name, these will be substituted for the year, month,
week and day of month, respectively. So, a template with the name
`summary-YYYY-MM.html.tmpl` would have name `summary-2010-03.html` for the
month of March 2010.

#### generate_once

When set to `True`, the template is processed only on the first
invocation of the report engine service. This feature is useful for
files that do not change when data values change, such as HTML files
that define a layout. The default is `False`.

#### stale_age

File staleness age, in seconds. If the file is older than this age it
will be generated from the template. If no `stale_age` is
specified, then the file will be generated every time the generator
runs.

!!! Note
    Precise control over when a run is available through use of the
    `report_timing` option. The `report_timing` option uses a CRON-like
    syntax to specify precisely when a report should be run. See the guide
    *[Scheduling report generation](../../custom/report-scheduling.md)*
    for details.

## [[SummaryByDay]]

The `SummaryByDay` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-day timespan. Be sure to include `YYYY`,
`MM`, and `DD` in the filename of any template in this
section.

## [[SummaryByMonth]]

The `SummaryByMonth` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-month timespan. Be sure to include `YYYY` and
`MM` in the filename of any template in this section.

## [[SummaryByYear]]

The `SummaryByYear` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-year timespan. Be sure to include `YYYY` in the
filename of any template in this section.
