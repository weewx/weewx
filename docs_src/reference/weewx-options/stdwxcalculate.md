# [StdWXCalculate]

Some hardware provides derived quantities, such as `dewpoint`, `windchill`,
and `heatindex`, while other hardware does not. This service can be used to
fill in any missing quantities, or to substitute a software-calculated value
for hardware that has unreliable or obsolete calculations.

By default, the service can calculate the following values, although the list
can be extended:

* altimeter
* appTemp
* barometer
* cloudbase
* dewpoint
* ET
* heatindex
* humidex
* inDewpoint
* maxSolarRad
* pressure 
* rainRate
* windchill
* windrun

The configuration section `[StdWXCalculate]` consists of two different parts:

1. The subsection `[[Calculations]]`, which specifies which derived types are
to be calculated and under what circumstances.
2. Zero or more subsections, which specify what parameters are to be used for
the calculation. These are described below.

The service `StdWXCalculate` can be extended by the user to add new, derived
types by using the XTypes system. See the wiki article
[*Extensible types (XTypes)*](https://github.com/weewx/weewx/wiki/xtypes)
for how to do this.

#### data_binding

The data source to be used for historical data when calculating derived
quantities. It should match a binding given in section `[DataBindings]`.
Optional. Default is `wx_binding`.

!!! Note
    The data binding used by the `StdWXCalculate` service should normally
    match the data binding used by the `StdArchive` service. Users who use
    custom or additional data bindings should take care to ensure the correct
    data bindings are used by both services.

## [[Calculations]]

This section specifies which strategy is to be used to provide values for
derived variables. It consists of zero or more options with the syntax:

```ini
obs_type = directive[, optional_bindings]...
```
where `directive` is one of `prefer_hardware`, `hardware`, or `software`:

| directive         | Definition                                                                |
|-------------------|---------------------------------------------------------------------------|
| `prefer_hardware` | Calculate the value in software only if it is not provided by hardware.   |
| `hardware`        | Hardware values only are accepted: never calculate the value in software. |
| `software`        | Always calculate the value in software.                                   |

The option `optional_binding` is optional, and consists of either `loop`, or
`archive`. If `loop`, then the calculation will be done only for LOOP packets.
If `archive`, then the calculation will be done only for archive records. If
no binding is specified, then it will be done for both LOOP packets and
archive records.

Example 1: if your weather station calculates windchill using the pre-2001
algorithm, and you prefer to have WeeWX calculate it using a modern algorithm,
specify the following:

``` ini
[StdWXCalculate]
    [[Calculations]]
      windchill = software
```

This will force WeeWX to always calculate a value for `windchill`,
regardless of whether the hardware provides one.

Example 2: suppose you want ET to be calculated, but only for archive records.
The option would look like:

``` ini
[StdWXCalculate]
    [[Calculations]]
      ET = software, archive
```

### Defaults

In the absence of a `[[Calculations]]` section, no values will be calculated!

However, the version of `weewx.conf` that comes with the WeeWX distribution
includes a `[[Calculations]]` section that looks like this:

``` ini
[StdWXCalculate]
    [[Calculations]]
        pressure = prefer_hardware
        altimeter = prefer_hardware
        appTemp = prefer_hardware
        barometer = prefer_hardware
        cloudbase = prefer_hardware
        dewpoint = prefer_hardware
        ET = prefer_hardware
        heatindex = prefer_hardware
        humidex = prefer_hardware
        inDewpoint = prefer_hardware
        maxSolarRad = prefer_hardware
        rainRate = prefer_hardware
        windchill = prefer_hardware
        windrun = prefer_hardware
```

## [[WXXTypes]]

The `StdWXXTypes` class is responsible for calculating the following simple,
derived types:

* appTemp
* cloudbase
* dewpoint
* ET
* heatindex
* humidex
* inDewpoint
* maxSolarRad
* windchill
* windDir
* windRun

A few of these types have an option or two that can be set. These are
described below.

### [[[ET]]]

This subsection contains several options used when calculating ET
(evapotranspiration). See the document [*Step by Step Calculation of the Penman-Monteith Evapotranspiration*](https://www.agraria.unirc.it/documentazione/materiale_didattico/1462_2016_412_24509.pdf)
for the definitions of `cn` and `cd`.

#### et_period

The length of time in seconds over which evapotranspiration is calculated.
Default is `3600` (one hour).

#### wind_height

The height in meters of your anemometer. Default is `2.0`.

#### albedo

The albedo to be used in the calculations. Default is `0.23`.

#### cn

The numerator constant for the reference crop type and time step. Default
is `37`.

#### cd

The denominator constant for the reference crop type and time step. Default
is `0.34`.

### [[[heatindex]]]

#### algorithm

Controls which algorithm will be used to calculate heat-index. Choices are
`new` (see https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml), or
`old`. The newer algorithm will give results down to 40°F, which are sometimes
less than the sensible temperature. For this reason, some people prefer the
older algorithm, which applies only to temperatures above 80°F. Default is
`new`.

### [[[maxSolarRad]]]

This section is used for specifying options when calculating `maxSolarRad`,
the theoretical maximum solar radiation.

#### algorithm

Controls which algorithm will be used to calculate maxSolarRad. Choices are
`bras` [("Bras")](http://www.ecy.wa.gov/programs/eap/models.html), or `rs`
[(Ryan-Stolzenbach)](http://www.ecy.wa.gov/programs/eap/models.html). Default
is `rs`.

#### atc

The coefficient `atc` is the "atmospheric transmission coefficient" used by
the 'Ryan-Stolzenbach' algorithm for calculating maximum solar radiation.
Value must be between `0.7` and `0.91`. Default is `0.8`.

#### nfac

The coefficient `nfac` is "atmospheric turbidity" used by the 'Bras' algorithm
for calculating maximum solar radiation. Values must be between `2` (clear)
and `5` (smoggy). Default is `2`.

### [[[windDir]]]

#### force_null

Indicates whether the wind direction should be undefined when the wind speed
is zero. The default value is `true`: when the wind speed is zero, the wind
direction will be set to undefined (Python `None`).

To report the wind vane direction even when there is no wind speed, change
this to `false`:

``` ini
[StdWXCalculate]
    [[WXXTypes]]
      [[[windDir]]]
        force_null = false
```

### [[PressureCooker]]
This class is responsible for calculating pressure-related values. Given the
right set of input types, it can calculate `barometer`, `pressure`, and
`altimeter`. See the Wiki article [Barometer, pressure, and altimeter](https://github.com/weewx/weewx/wiki/Barometer,-pressure,-and-altimeter)
for the differences between these three types.

#### max_delta_12h

Some of the calculations require the temperature 12 hours ago (to compensate
for tidal effects), which requires a database lookup. There may or may not be
a temperature exactly 12 hours ago. This option sets how much of a time
difference in seconds is allowed. The default is `1800`.

#### [[[altimeter]]]

#### algorithm

Which algorithm to use when calculating altimeter from gauge pressure.
Possible choices are `ASOS`, `ASOS2`, `MADIS`, `NOAA`, `WOB`, and `SMT`.
The default is `ASOS`.

### [[RainRater]]

This class calculates `rainRate` from recent rain events.

#### rain_period

The algorithm calculates a running average over a period of time in the past.
This option controls how far back to go in time in seconds. Default is `1800`.
