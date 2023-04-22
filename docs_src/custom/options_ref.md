# Reference: report options {#report_options}

This section contains the options available in the skin configuration
file, `skin.conf`. The same options apply to the language files
found in the subdirectory `lang`, such as `lang/en.conf` for
English.

We recommend to put

-   options that control the behavior of the skin into
    `skin.conf`; and
-   language dependent labels and texts into the language files.

It is worth noting that, like the main configuration file
`weewx.conf`, UTF-8 is used throughout.

## [Extras]

This section is available to add any static tags you might want to use
in your templates.

As an example, the `skin.conf` file for the *Seasons* skin
includes three options:


| Skin option         | Template tag                |
|---------------------|-----------------------------|
| `radar_img`         | `$Extras.radar_img`         |
| `radar_url`         | `$Extras.radar_url`         |
| `googleAnalyticsId` | `$Extras.googleAnalyticsId` |

If you take a look at the template `radar.inc` you will see
examples of testing for these tags.

#### radar_img

Set to an URL to show a local radar image for your region.

#### radar_url

If the radar image is clicked, the browser will go to this URL. This is
usually used to show a more detailed, close-up, radar picture.

For me in Oregon, setting the two options to:

``` ini
[Extras]
    radar_img = http://radar.weather.gov/ridge/lite/N0R/RTX_loop.gif
    radar_url = http://radar.weather.gov/ridge/radar.php?product=NCR&rid=RTX&loop=yes
```

results in a nice image of a radar centered on Portland, Oregon. When
you click on it, it gives you a detailed, animated view. If you live in
the USA, take a look at the [NOAA radar
website](http://radar.weather.gov/) to find a nice one that will work
for you. In other countries, you will have to consult your local weather
service.

#### googleAnalyticsId

If you have a [Google Analytics ID](https://www.google.com/analytics/),
you can set it here. The Google Analytics Javascript code will then be
included, enabling analytics of your website usage. If commented out,
the code will not be included.

### Extending `[Extras]`

Other tags can be added in a similar manner, including sub-sections. For
example, say you have added a video camera, and you would like to add a
still image with a hyperlink to a page with the video. You want all of
these options to be neatly contained in a sub-section.

``` ini
[Extras]
    [[video]]
        still = video_capture.jpg
        hyperlink = http://www.eatatjoes.com/video.html
      
```

Then in your template you could refer to these as:

``` html
<a href="$Extras.video.hyperlink">
    <img src="$Extras.video.still" alt="Video capture"/>
</a>
```

## [Labels]

This section defines various labels.

#### hemispheres

Comma separated list for the labels to be used for the four hemispheres.
The default is `N, S, E, W`.

#### latlon_formats

Comma separated list for the formatting to be used when converting
latitude and longitude to strings. There should be three elements:

1.  The format to be used for whole degrees of latitude
2.  The format to be used for whole degrees of longitude
3.  The format to be used for minutes.

This allows you to decide whether you want leading zeroes. The
default includes leading zeroes and is `"%02d", "%03d", "%05.2f"`.

### [[Generic]]

This sub-section specifies default labels to be used for each
observation type. For example, options

``` ini
inTemp  = Temperature inside the house
outTemp = Outside Temperature
UV      = UV Index
```

would cause the given labels to be used for plots of `inTemp` and
`outTemp`. If no option is given, then the observation type
itself will be used (*e.g.*, `outTemp`).

## [Almanac]

This section controls what text to use for the almanac. It consists of
only one entry

#### moon_phases

This option is a comma separated list of labels to be used for the eight
phases of the moon. Default is `New, Waxing crescent, First quarter,
Waxing gibbous, Full, Waning gibbous, Last quarter, Waning
crescent`.

## [Units]

This section controls how units are managed and displayed.

### [[Groups]]

This sub-section lists all the *Unit Groups* and specifies which
measurement unit is to be used for each one of them.

As there are many different observational measurement types (such as
`outTemp`, `barometer`, etc.) used in WeeWX (more than 50
at last count), it would be tedious, not to say possibly inconsistent,
to specify a different measurement system for each one of them. At the
other extreme, requiring all of them to be "U.S. Customary" or
"Metric" seems overly restrictive. WeeWX has taken a middle route and
divided all the different observation types into 12 different *unit
groups*. A unit group is something like `group_temperature`. It
represents the measurement system to be used by all observation types
that are measured in temperature, such as inside temperature (type
`inTemp`), outside temperature (`outTemp`), dewpoint
(`dewpoint`), wind chill (`windchill`), and so on. If you
decide that you want unit group `group_temperature` to be
measured in `degree_C` then you are saying *all* members of its
group will be reported in degrees Celsius.

Note that the measurement unit is always specified in the singular. That
is, specify `degree_C` or `foot`, not `degrees_C`
or `feet`. See the *[Appendix: Units](../appendix/#units)* for more
information, including a concise summary of the groups, their members,
and which options can be used for each group.

#### group_altitude

Which measurement unit to be used for altitude. Possible options are
`foot` or `meter`.

#### group_direction

Which measurement unit to be used for direction. The only option is
`degree_compass`.

#### group_distance

Which measurement unit to be used for distance (such as for wind run).
Possible options are `mile` or `km`.

#### group_moisture

The measurement unit to be used for soil moisture. The only option is
`centibar`.

#### group_percent

The measurement unit to be used for percentages. The only option is
`percent`.

#### group_pressure

The measurement unit to be used for pressure. Possible options are one
of `inHg` (inches of mercury), `mbar`, `hPa`, or
`kPa`.

#### group_pressurerate

The measurement unit to be used for rate of change in pressure. Possible
options are one of `inHg_per_hour` (inches of mercury per hour),
`mbar_per_hour`, `hPa_per_hour`, or `kPa_per_hour`.

#### group_radiation

The measurement unit to be used for radiation. The only option is
`watt_per_meter_squared`.

#### group_rain

The measurement unit to be used for precipitation. Options are
`inch`, `cm`, or `mm`.

#### group_rainrate

The measurement unit to be used for rate of precipitation. Possible
options are one of `inch_per_hour`, `cm_per_hour`, or
`mm_per_hour`.

#### group_speed

The measurement unit to be used for wind speeds. Possible options are
one of `mile_per_hour`, `km_per_hour`, `knot`,
`meter_per_second`, or `beaufort`.

#### group_speed2

This group is similar to `group_speed`, but is used for
calculated wind speeds which typically have a slightly higher
resolution. Possible options are one `mile_per_hour2`,
`km_per_hour2`, `knot2`, or `meter_per_second2`.

#### group_temperature

The measurement unit to be used for temperatures. Options are
`degree_C`, [`degree_E`](https://xkcd.com/1923/),
`degree_F`, or `degree_K`.

#### group_volt

The measurement unit to be used for voltages. The only option is
`volt`.

### `[[StringFormats]]` {#Units_StringFormats}

This sub-section is used to specify what string format is to be used for
each unit when a quantity needs to be converted to a string. Typically,
this happens with y-axis labeling on plots and for statistics in HTML
file generation. For example, the options

``` ini
degree_C = %.1f
inch     = %.2f
```

would specify that the given string formats are to be used when
formatting any temperature measured in degrees Celsius or any
precipitation amount measured in inches, respectively. The [formatting
codes are those used by
Python](https://docs.python.org/library/string.html#format-specification-mini-language),
and are very similar to C's `sprintf()` codes.

You can also specify what string to use for an invalid or unavailable
measurement (value `None`). For example,

``` ini
NONE = " N/A "
```

### `[[Labels]]` {#Units_Labels}

This sub-section specifies what label is to be used for each measurement
unit type. For example, the options

``` ini
degree_F = °F
inch     = ' in'
```

would cause all temperatures to have unit labels `°F` and all
precipitation to have labels `in`. If any special symbols are to
be used (such as the degree sign) they should be encoded in UTF-8. This
is generally what most text editors use if you cut-and-paste from a
character map.

If the label includes two values, then the first is assumed to be the
singular form, the second the plural form. For example,

``` ini
foot   = " foot",   " feet"
...
day    = " day",    " days"
hour   = " hour",   " hours"
minute = " minute", " minutes"
second = " second", " seconds"
```

### `[[TimeFormats]]` {#Units_TimeFormats}

This sub-section specifies what time format to use for different time
*contexts*. For example, you might want to use a different format when
displaying the time in a day, versus the time in a month. It uses
[strftime()](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
formats. The default looks like this:

``` ini
    [[TimeFormats]]
        hour        = %H:%M
        day         = %X
        week        = %X (%A)
        month       = %x %X
        year        = %x %X
        rainyear    = %x %X
        current     = %x %X
        ephem_day   = %X
        ephem_year  = %x %X
```

The specifiers `%x`, `%X`, and `%A` code locale
dependent date, time, and weekday names, respectively. Hence, if you set
an appropriate environment variable `LANG`, then the date and
times should follow local conventions (see section [Environment variable
LANG](../localization/#environment_variable_LANG) for details on how to do this).
However, the results may not look particularly nice, and you may want to
change them. For example, I use this in the U.S.:

``` ini
    [[TimeFormats]]
        #
        # More attractive formats that work in most Western countries.
        #
        day        = %H:%M
        week       = %H:%M on %A
        month      = %d-%b-%Y %H:%M
        year       = %d-%b-%Y %H:%M
        rainyear   = %d-%b-%Y %H:%M
        current    = %d-%b-%Y %H:%M
        ephem_day  = %H:%M
        ephem_year = %d-%b-%Y %H:%M
```

The last two formats, `ephem_day` and `ephem_year` allow
the formatting to be set for almanac times The first,
`ephem_day`, is used for almanac times within the day, such as
sunrise or sunset. The second, `ephem_year`, is used for almanac
times within the year, such as the next equinox or full moon.

### `[[Ordinates]]` {#Units_Ordinates}

#### directions

Set to the abbreviations to be used for ordinal directions. By default,
this is `N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW,
NNW, N`.

### `[[DegreeDays]]` {#degreedays}

#### heating_base
#### cooling_base
#### growing_base

Set to the base temperature for calculating heating, cooling, and
growing degree-days, along with the unit to be used. Examples:

``` ini
heating_base = 65.0, degree_F
cooling_base = 20.0, degree_C
growing_base = 50.0, degree_F
```

### `[[Trend]]` {#trend}

#### time_delta

Set to the time difference over which you want trends to be calculated. 
Alternatively, a [duration notation](../appendix#Durations) can be used. The default is 3 hours.

#### time_grace

When searching for a previous record to be used in calculating a trend,
a record within this amount of `time_delta` will be accepted.
Default is 300 seconds.

## `[Texts]` {#texts}

The section `[Texts]` holds static texts that are used in the
templates. Generally there are multiple language files, one for each
supported language, named by the language codes defined in
[ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
The entries give the translation of the texts to the target language.
For example,

``` ini
[Texts]
    "Current Conditions" = "Aktuelle Werte"
```

would cause "Aktuelle Werte" to be used whereever `$gettext("Current
Conditions"` appeared. See the section on
[`$gettext`](../cheetah/#internationalization-support-with-gettext).

!!! Note
    Strings that include commas must be included in single or double quotes. Otherwise they
    will be misinterpreted as a list.


## [CheetahGenerator] {#CheetahGenerator}

This section contains the options for the Cheetah generator. It applies
to `skin.conf` only.

#### search_list

This is the list of search list objects that will be scanned by the
template engine, looking for tags. See the section *[Defining new
tags](../cheetah/#defining_new_tags)* and the [Cheetah
documentation](https://cheetahtemplate.org/) for details on search
lists. If no `search_list` is specified, a default list
will be used.

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
        <td>Non 7-bit characters will be represented as HTML entities (<i>e.g.</i>, the degree sign will be
            represented as "<span class="code">&amp;#176;</span>")
        </td>
    </tr>
    <tr>
        <td class="code first_col">strict_ascii</td>
        <td>Non 7-bit characters will be ignored.</td>
    </tr>
    <tr>
        <td class="code first_col">normalized_ascii</td>
        <td>Replace accented characters with non-accented analogs (<i>e.g.</i>, 'ö' will be replaced with 'o').</td>
    </tr>
    </tbody>
</table>

The encoding `html_entities` is the default. Other common choices
are `utf8`, `cp1252` (*a.k.a.* Windows-1252), and
`latin1`.

#### template

The name of a template file. A template filename must end with
`.tmpl`. Filenames are case-sensitive. If the template filename
has the letters `YYYY`, `MM`, `WW` or `DD`
in its name, these will be substituted for the year, month, week and day
of month, respectively. So, a template with the name
`summary-YYYY-MM.html.tmpl` would have name
`summary-2010-03.html` for the month of March, 2010.

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
    Precise control over when a *[report](../../usersguide/weewx-config-file/stdreport-config/)* is run is
    available through use of the `report_timing` option in
    `weewx.conf`. The `report_timing` option uses a CRON-like
    setting to control precisely when a report is run. See the guide *[Scheduling
    report generation](../../report_scheduling)* for details.

`[[SummaryByDay]]`

The `SummaryByDay` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-day timespan. Be sure to include `YYYY`,
`MM`, and `DD` in the filename of any template in this
section.

`[[SummaryByMonth]]`

The `SummaryByMonth` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-month timespan. Be sure to include `YYYY` and
`MM` in the filename of any template in this section.

`[[SummaryByYear]]`

The `SummaryByYear` section defines some special behavior. Each
template in this section will be used multiple times, each time with a
different per-year timespan. Be sure to include `YYYY` in the
filename of any template in this section.

## `[ImageGenerator]` {#ImageGenerator}

This section describes the various options available to the image
generator.

| ![Part names in a WeeWX image](../images/image_parts.png) |
|-----------------------------------------------------------|
| Part names in a WeeWX image                               |


### Overall options

These are options that affect the overall image.

#### anti_alias

Setting to 2 or more might give a sharper image, with fewer jagged
edges. Experimentation is in order. Default is `1`.

| ![Effect of anti_alias option](../images/antialias.gif)             |
|---------------------------------------------------------------------|
| A GIF showing the same image<br/>with `anti_alias=1`, `2`, and `4`. |

#### chart_background_color

The background color of the chart itself. Optional. Default is
`#d8d8d8`.

#### chart_gridline_color

The color of the chart grid lines. Optional. Default is `#a0a0a0`

| ![Example of day/night bands](../images/weektempdew.png) |
|----------------------------------------------------------|
| Example of day/night bands in a one week image           |

#### daynight_day_color

The color to be used for the daylight band. Optional. Default is
`#ffffff`.

#### daynight_edge_color

The color to be used in the transition zone between night and day.
Optional. Default is `#efefef`, a mid-gray.

#### daynight_night_color

The color to be used for the nighttime band. Optional. Default is
`#f0f0f0`, a dark gray.

#### image_background_color

The background color of the whole image. Optional. Default is
`#f5f5f5` ("SmokeGray")

#### image_width
#### image_height

The width and height of the image in pixels. Optional. Default is 300 x
180 pixels.

#### show_daynight

Set to `true` to show day/night bands in an image. Otherwise, set
to false. This only looks good with day or week plots. Optional. Default
is `false`.

#### skip_if_empty

If set to `true`, then skip the generation of the image if all
data in it are null. If set to a time period, such as `month` or
`year`, then skip the generation of the image if all data in that
period are null. Default is `false`.

#### stale_age

Image file staleness age, in seconds. If the image file is older than
this age it will be generated. If no `stale_age` is specified,
then the image file will be generated every time the generator runs.

#### unit

Normally, the unit used in a plot is set by whatever [unit group the
types are in](../custom_reports/#mixed-units). However, this option allows overriding the
unit used in a specific plot.

### Various label options

These are options for the various labels used in the image.

#### axis_label_font_color

The color of the x- and y-axis label font. Optional. Default is
`black`.

#### axis_label_font_path

The path to the font to be use for the x- and y-axis labels. Optional.
If not given, or if WeeWX cannot find the font, then the default PIL
font will be used.

#### axis_label_font_size

The size of the x- and y-axis labels in pixels. Optional. The default is
`10`.

#### bottom_label_font_color

The color of the bottom label font. Optional. Default is `black`.

#### bottom_label_font_path

The path to the font to be use for the bottom label. Optional. If not
given, or if WeeWX cannot find the font, then the default PIL font will
be used.

#### bottom_label_font_size

The size of the bottom label in pixels. Optional. The default is
`10`.

#### bottom_label_format

The format to be used for the bottom label. It should be a [strftime
format](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior).
Optional. Default is `'%m/%d/%y %H:%M'`.

#### bottom_label_offset

The margin of the bottom label from the bottom of the plot. Default is
3.

#### top_label_font_path

The path to the font to be use for the top label. Optional. If not
given, or if WeeWX cannot find the font, then the default PIL font will
be used.

#### top_label_font_size

The size of the top label in pixels. Optional. The default is
`10`.

#### unit_label_font_color

The color of the unit label font. Optional. Default is `black`.

#### unit_label_font_path

The path to the font to be use for the unit label. Optional. If not
given, or if WeeWX cannot find the font, then the default PIL font will
be used.

#### unit_label_font_size

The size of the unit label in pixels. Optional. The default is
`10`.

#### x_interval

The time interval in seconds between x-axis tick marks. Optional. If not
given, a suitable default will be chosen.

#### x_label_format

The format to be used for the time labels on the x-axis. It should be a
[strftime
format](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior).
Optional. If not given, a sensible format will be chosen automatically.

#### x_label_spacing

Specifies the ordinal increment between labels on the x-axis: For
example, 3 means a label every 3rd tick mark. Optional. The default is
`2`.

#### y_label_side

Specifies if the y-axis labels should be on the left, right, or both
sides of the graph. Valid values are `left`, `right` or `both`. Optional. 
Default is `left`.

#### y_label_spacing

Specifies the ordinal increment between labels on the y-axis: For
example, 3 means a label every 3rd tick mark. Optional. The default is
`2`.

#### y_nticks

The nominal number of ticks along the y-axis. The default is
`10`.

### Plot scaling options

#### time_length

The nominal length of the time period to be covered in seconds. Alternatively, a 
[duration notation](../appendix#Durations) can be used. The
exact length of the x-axis is chosen by the plotting engine to cover
this period. Optional. Default is `86400` (one day).

#### yscale

A 3-way tuple (`ylow`, `yhigh`, `min_interval`),
where `ylow` and `yhigh` are the minimum and maximum
y-axis values, respectively, and `min_interval` is the minimum
tick interval. If set to `None`, the corresponding value will be
automatically chosen. Optional. Default is `None, None, None`.
(Choose the y-axis minimum, maximum, and minimum increment
automatically.)

### Compass rose options

| ![Example of a progressive vector plot](../images/daywindvec.png)  |
|--------------------------------------------------------------------|
| Example of a vector plot with a compass rose<br/>in the lower-left |

#### rose_label

The label to be used in the compass rose to indicate due North.
Optional. Default is `N`.

#### rose_label_font_path

The path to the font to be use for the rose label (the letter "N,"
indicating North). Optional. If not given, or if WeeWX cannot find the
font, then the default PIL font will be used.

#### rose_label_font_size

The size of the compass rose label in pixels. Optional. The default is
`10`.

#### rose_label_font_color

The color of the compass rose label. Optional. Default is the same color
as the rose itself.

#### vector_rotate

Causes the vectors to be rotated by this many degrees. Positive is
clockwise. If westerly winds dominate at your location (as they do at
mine), then you may want to specify `+90` for this option. This
will cause the average vector to point straight up, rather than lie flat
against the x-axis. Optional. The default is `0`.

### Shared plot line options

These are options shared by all the plot lines.

#### chart_line_colors

Each chart line is drawn in a different color. This option is a list of
those colors. If the number of lines exceeds the length of the list,
then the colors wrap around to the beginning of the list. Optional. In
the case of bar charts, this is the color of the outline of the bar.
Default is `#0000ff, #00ff00, #ff0000`.
Individual line color can be overridden by using option [`color`](#color).

#### chart_fill_colors

A list of the color to be used as the fill of the bar charts. Optional.
The default is to use the same color as the outline color (option
[`chart_line_colors`](#chart_line_colors)).

#### chart_line_width

Each chart line can be drawn using a different line width. This option
is a list of these widths. If the number of lines exceeds the length of
the list, then the widths wrap around to the beginning of the list.
Optional. Default is `1, 1, 1`.
Individual line widths can be overridden by using option [`width`](#width).

### Individual line options

These are options that are set for individual lines.

#### aggregate_interval

The time period over which the data should be aggregated, in seconds. 
Alternatively, a [duration notation](../appendix#Durations) can be used. 
Required if `aggregate_type` has been set. 

#### aggregate_type

The default is to plot every data point, but this is probably not a good
idea for any plot longer than a day. By setting this option, you can
*aggregate* data by a set time interval. Available aggregation types
include `avg`, `count`, `cumulative`, `diff`, `last`, `max`, `min`, `sum`,
and `tderiv`.

#### color

This option is to override the color for an individual line. Optional.
Default is to use the color in [`chart_line_colors`](#chart_line_colors).

#### data_type

The SQL data type to be used for this plot line. For more information,
see the section *[Including a type more than once in a
plot](../image_generator#including_same_sql_type_2x)*. Optional. The default is to use the
section name.

#### fill_color

This option is to override the fill color for a bar chart. Optional.
Default is to use the color in [`chart_fill_colors`](#chart_fill_colors).

#### label

The label to be used for this plot line in the top label. Optional. The
default is to use the SQL variable name.

#### line_gap_fraction

If there is a gap between data points bigger than this fractional amount
of the x-axis, then a gap will be drawn, rather than a connecting line.
See Section *[Line gaps](../image_generator/#line_gaps)*. Optional. The default is to
always draw the line.

#### line_type

The type of line to be used. Choices are `solid` or
`none`. Optional. Default is `solid`.

#### marker_size

The size of the marker. Optional. Default is `8`.

#### marker_type

The type of marker to be used to mark each data point. Choices are
`cross`, `x`, `circle`, `box`, or `none`. Optional. Default is `none`.

#### plot_type

The type of plot for this line. Choices are `line`, `bar`,
or `vector`. Optional. Default is `line`.

#### width

This option is to override the line width for an individual line.
Optional. Default is to use the width in [`chart_line_width`](#chart_line_width).

## [CopyGenerator] {#copygenerator}

This section is used by generator
`weewx.reportengine.CopyGenerator` and controls which files are
to be copied over from the skin directory to the destination directory.
Think of it as "file generation," except that rather than going
through the template engine, the files are simply copied over. It is
useful for making sure CSS and Javascript files are in place.

#### copy_once

This option controls which files get copied over on the first invocation
of the report engine service. Typically, this is things such as style
sheets or background GIFs. Wildcards can be used.

#### copy_always

This is a list of files that should be copied on every invocation.
Wildcards can be used.

Here is the `[CopyGenerator]` section from the Standard `skin.conf`

``` ini
[CopyGenerator]
    # This section is used by the generator CopyGenerator

    # List of files to be copied only the first time the generator runs
    copy_once = backgrounds/*, weewx.css, mobile.css, favicon.ico

    # List of files to be copied each time the generator runs
    # copy_always = 
```

The Standard skin includes some background images, CSS files, and icons
that need to be copied once. There are no files that need to be copied
every time the generator runs.

## `[Generators]` {#generators_section }

This section defines the list of generators that should be run.

#### generator_list

This option controls which generators get run for this skin. It is a
comma separated list. The generators will be run in this order.

Here is the `[Generators]` section from the Standard `skin.conf`

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.imagegenerator.ImageGenerator, weewx.reportengine.CopyGenerator
```

The Standard skin uses three generators: `CheetahGenerator`, `ImageGenerator`, 
and `CopyGenerator`.
