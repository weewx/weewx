# [Units]

This section controls how units are managed and displayed.

## [[Groups]]

This section lists all the *Unit Groups* and specifies which measurement unit is
to be used for each one of them.

As there are many different observational measurement types (such as `outTemp`,
`barometer`, etc.) used in WeeWX (more than 50 at last count), it would be
tedious, not to say possibly inconsistent, to specify a different measurement
system for each one of them. At the other extreme, requiring all of them to be
"U.S. Customary" or "Metric" seems overly restrictive. WeeWX has taken a middle
route and divided all the different observation types into 12 different *unit
groups*. A unit group is something like `group_temperature`. It represents the
measurement system to be used by all observation types that are measured in
temperature, such as inside temperature (type `inTemp`), outside temperature
(`outTemp`), dewpoint (`dewpoint`), wind chill (`windchill`), and so on. If you
decide that you want unit group `group_temperature` to be measured in `degree_C`
then you are saying *all* members of its group will be reported in degrees
Celsius.

Note that the measurement unit is always specified in the singular. That is,
specify `degree_C` or `foot`, not `degrees_C` or `feet`. See the reference
section *[Units](../units.md)* for more information, including a concise summary
of the groups, their members, and which options can be used for each group.

#### group_altitude

Which measurement unit to be used for altitude. Possible options are `foot` or
`meter`.

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

The measurement unit to be used for pressure. Possible options are one of `inHg`
(inches of mercury), `mbar`, `hPa`, or `kPa`.

#### group_pressurerate

The measurement unit to be used for rate of change in pressure. Possible options
are one of `inHg_per_hour` (inches of mercury per hour), `mbar_per_hour`,
`hPa_per_hour`, or `kPa_per_hour`.

#### group_radiation

The measurement unit to be used for radiation. The only option is
`watt_per_meter_squared`.

#### group_rain

The measurement unit to be used for precipitation. Options are `inch`, `cm`, or
`mm`.

#### group_rainrate

The measurement unit to be used for rate of precipitation. Possible options are
one of `inch_per_hour`, `cm_per_hour`, or `mm_per_hour`.

#### group_speed

The measurement unit to be used for wind speeds. Possible options are one of
`mile_per_hour`, `km_per_hour`, `knot`, `meter_per_second`, or `beaufort`.

#### group_speed2

This group is similar to `group_speed`, but is used for calculated wind speeds
which typically have a slightly higher resolution. Possible options are one
`mile_per_hour2`, `km_per_hour2`, `knot2`, or `meter_per_second2`.

#### group_temperature

The measurement unit to be used for temperatures. Options are `degree_C`,
[`degree_E`](https://xkcd.com/1923/), `degree_F`, or `degree_K`.

#### group_volt

The measurement unit to be used for voltages. The only option is `volt`.

## [[StringFormats]]

This section is used to specify what string format is to be used for each unit
when a quantity needs to be converted to a string. Typically, this happens with
y-axis labeling on plots and for statistics in HTML file generation. For
example, the options

``` ini
degree_C = %.1f
inch     = %.2f
```

would specify that the given string formats are to be used when formatting any
temperature measured in degrees Celsius or any precipitation amount measured in
inches, respectively. The [formatting codes are those used by
Python](https://docs.python.org/library/string.html#format-specification-mini-language),
and are very similar to C's `sprintf()` codes.

You can also specify what string to use for an invalid or unavailable
measurement (value `None`). For example,

``` ini
NONE = " N/A "
```

## [[Labels]]

This section specifies what label is to be used for each measurement unit type.
For example, the options

``` ini
degree_F = °F
inch     = ' in'
```

would cause all temperatures to have unit labels `°F` and all precipitation to
have labels `in`. If any special symbols are to be used (such as the degree
sign) they should be encoded in UTF-8. This is generally what most text editors
use if you cut-and-paste from a character map.

If the label includes two values, then the first is assumed to be the singular
form, the second the plural form. For example,

``` ini
foot   = " foot",   " feet"
...
day    = " day",    " days"
hour   = " hour",   " hours"
minute = " minute", " minutes"
second = " second", " seconds"
```

## [[TimeFormats]]

This section specifies what time format to use for different time *contexts*.
For example, you might want to use a different format when displaying the time
in a day, versus the time in a month. It uses
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

The specifiers `%x`, `%X`, and `%A` code locale dependent date, time, and
weekday names, respectively. Hence, if you set an appropriate environment
variable `LANG`, then the date and times should follow local conventions (see
section [Environment variable
LANG](../../custom/localization.md#environment-variable-LANG) for details on
how to do this). However, the results may not look particularly nice, and you
may want to change them. For example, I use this in the U.S.:

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

The last two formats, `ephem_day` and `ephem_year` allow the formatting to be
set for almanac times The first, `ephem_day`, is used for almanac times within
the day, such as sunrise or sunset. The second, `ephem_year`, is used for
almanac times within the year, such as the next equinox or full moon.

##[[DeltaTimeFormats]]

Section `[[DeltaTimeFormats]]` is used to control the formatting of the
`long_form()` suffix, which is used when expressing _delta times_, that
is, elapsed time since some event occurred. For example

    $station.uptime.long_form

will show how long WeeWX has been up:

    9 days, 3 hours, 53 minutes

Because delta times can vary in length from something measured in hours (time
since sunrise), to time measured in days (uptime), each delta time comes with a
_time context_. For example, the context used for time since sunrise is `hour`,
while the context used by station uptime is `month`. 

The default section looks like this:

``` ini
    [[DeltaTimeFormats]]
        current = "%(minute)d%(minute_label)s, %(second)d%(second_label)s"
        hour    = "%(minute)d%(minute_label)s, %(second)d%(second_label)s"
        day     = "%(hour)d%(hour_label)s, %(minute)d%(minute_label)s, %(second)d%(second_label)s"
        week    = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s"
        month   = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s"
        year    = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s"
```

The section is keyed by the time context (_e.g._, `current`, `hour`, _etc._).

The parameter `minute` will be replaced by how many minutes, `second` by how
many seconds, and so on. 

The parameter `minute_label` is the label that will be used for minutes. It is
obtained from section [`[Unit]/[[Labels]]`](#labels).

The formatting can be overridden by supplying an argument to `long_form`. For
example, with the example above, the tag

    $station.uptime.long_form("%(day)d%(day_label)s, %(hour)d%(hour_label)s, and %(minute)d%(minute_label)s")

would give

    9 days, 3 hours, and 53 minutes

Note the addition of the conjuction "and".

## [[Ordinates]]

#### directions

Set to the abbreviations to be used for ordinal directions. By default, this is
`N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW, N`.

## [[DegreeDays]]

#### heating_base
#### cooling_base
#### growing_base

Set to the base temperature for calculating heating, cooling, and growing
degree-days, along with the unit to be used. Examples:

``` ini
heating_base = 65.0, degree_F
cooling_base = 20.0, degree_C
growing_base = 50.0, degree_F
```

## [[Trend]]

#### time_delta

Set to the time difference over which you want trends to be calculated.
Alternatively, a [duration notation](../durations.md) can be used. The default
is 3 hours.

#### time_grace

When searching for a previous record to be used in calculating a trend, a record
within this amount of `time_delta` will be accepted. Default is 300 seconds.
