# [DisplayOptions]

This section holds options that control what a skin displays, and in what
order. Like [`[Extras]`](extras.md), the options are not interpreted by WeeWX
itself. The section is made available to the templates as the tag
`$DisplayOptions`, and what to do with it is up to the skin.

The *Seasons* skin uses it to decide which observation types, plots, and
sections appear on its pages. The options below are the ones *Seasons*
recognizes. Your own skin is free to use others.

The templates read each option with a fallback, so removing one does not cause
an error: the template's own default is used instead. Those defaults are much
shorter than the lists that ship in `skin.conf`, and are given for each option
below.

!!! Note
    Naming an observation type does not guarantee that it will appear. The
    *Seasons* templates first check whether the type has data in the last 30
    days, and skip it if it does not. This is why a new station shows only a
    few of the many types listed in `skin.conf`.

#### show_rss

Whether to show a link to the RSS feed in the title bar. Default is `True`.

#### show_reports

Whether to show the drop-down list of NOAA-style monthly summary reports in
the title bar. Default is `True`.

#### observations_current

Comma separated list of the observation types to appear in the "Current
Conditions" section, in the order they are to be shown. Default is
`outTemp, barometer`.

#### observations_stats

Comma separated list of the observation types to appear in the "Statistics"
section, in the order they are to be shown. It governs both the summary on the
front page and the fuller table on the statistics page. Default is
`outTemp, windSpeed, rain`.

#### observations_rss

Comma separated list of the observation types to appear in the RSS feed.
Default is `outTemp, inTemp, barometer, windSpeed, rain, rainRate`.

#### obs_type_sum

Comma separated list of the observation types for which a sum is more useful
than a high and a low. Rainfall is the obvious example. Types in this list are
shown as a single total for each time period, rather than as a minimum and a
maximum. Default is `rain`.

#### obs_type_max

Comma separated list of the observation types for which only the maximum is of
interest. Types in this list are shown as a single high for each time period,
with the time it occurred available as a tooltip. Default is `rainRate`.

A type that appears in both `obs_type_sum` and `obs_type_max` is shown as a
sum.

#### sensor_connections

Comma separated list of the observation types to appear under "Connectivity"
in the "Sensor Status" section, in the order they are to be shown. Default is
`rxCheckPercent`.

#### sensor_batteries

Comma separated list of the observation types to appear under "Battery
Status" in the "Sensor Status" section. Default is `outTempBatteryStatus,
inTempBatteryStatus, rainBatteryStatus, windBatteryStatus, uvBatteryStatus,
txBatteryStatus`.

#### sensor_voltages

Comma separated list of the observation types to appear under "Voltage" in
the "Sensor Status" section. Default is `consBatteryVoltage, heatingVoltage,
supplyVoltage, referenceVoltage`.

#### plot_groups

Comma separated list of the plots to appear on the front page, in the order
they are to be shown. The names are those of the plots defined in section
[`[ImageGenerator]`](imagegenerator.md), but without the time period in front:
the name `wind` covers `daywind`, `weekwind`, `monthwind`, and `yearwind`.

Which plot to show is worked out by joining a period from `periods` to a group
from `plot_groups`. For example, period `year` and group `tempdew` give the
plot `yeartempdew`. If `[ImageGenerator]` defines no such plot, nothing is
shown for that combination.

Default is `tempdew, wind, rain`.

#### telemetry_plot_groups

As `plot_groups`, but for the plots on the telemetry page. Default is `rx`.

#### periods

Comma separated list of the time periods offered by the buttons above the
plots, on both the front page and the telemetry page, in the order they are to
be shown. Default is `day, week, month, year`.

#### season_type

Which kind of season the "Season" column of the statistics page covers.
Set to `meteorological` or `astronomical`; either may be abbreviated. Default
is `meteorological`. See the section *[Aggregation
periods](../../custom/cheetah-generator.md#aggregation-periods)* for the
difference between the two.

### Extending `[DisplayOptions]`

Other options can be added in the same way as for `[Extras]`. Read them in a
template with the `get()` method, supplying a default in case the option is
missing:

``` ini
[DisplayOptions]
    show_almanac = True
```

``` html
#if $to_bool($DisplayOptions.get('show_almanac', True))
  #include "almanac.inc"
#end if
```

Use `$to_bool()` for an option that is true or false, and `$to_list()` for one
that is a list. Both are necessary because a value coming out of `skin.conf`
is a string, and a list of one element arrives as that element rather than as
a list of length one. See *[Helper
functions](../../custom/cheetah-generator.md#helper-functions)*.
