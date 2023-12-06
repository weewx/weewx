# [StdCalibrate]

The `StdCalibrate` service offers an opportunity to correct for any
calibration errors in your instruments. It is very general and flexible.

Because this service is normally run after `StdConvert`, the units to be used
should be the same as the target unit system chosen in
[`StdConvert`](stdconvert.md). It is also important that this service be run
before the archiving service `StdArchive`, so that it is the corrected data
that are stored.

In a default configuration, calibrations are applied to all LOOP packets.
They are applied to archive records only if the records were not software
generated (because, presumably, the correction was already applied in the
LOOP packets).

Because `StdCalibrate` runs _before_ `StdWXCalculate`, correction are also not
applied to derived calculations.

## [[Corrections]]

In this section you list all correction expressions. The section looks like
this:
```ini
[StdCalibrate]
  [[Corrections]]
    obs_type = expression[, loop][, archive]
```

Where:

_`expression`_ is a valid Python expression involving any observation types
in the same record, or functions in the [`math`
module](https://docs.python.org/3/library/math.html). More below.

_`loop`_ is a directive that tells `StdCalibrate` to always apply the 
correction to LOOP packets.

_`archive`_ is a directive that tells `StdCalibrate` to always apply the
correction to archive records.

Details below.

### Expressions

For example, say that you know your outside thermometer reads high by 0.2°F. You
could use the expression:

    outTemp = outTemp - 0.2

Perhaps you need a linear correction around a reference temperature of 68°F:

    outTemp = outTemp + (outTemp-68) * 0.02

or perhaps a non-linear correction, using the math function `math.pow()`:

    radiation = math.pow(radiation, 1.02)

It is also possible to do corrections involving more than one variable. Suppose
you have a temperature sensitive barometer:

    barometer = barometer + (outTemp-32) * 0.0091

All correction expressions are run in the order given.

### Directives

Directives are separated by a comma from the expression, and tell `StdCalibrate`
whether to apply the correction to LOOP packets, archive records, or both. 

If not supplied, the correction will be applied to all LOOP packets. They will
also be applied to archive records, but only if they came from hardware[^1].
This is usually what you want.

Here are examples:

    humidity = humidity - 3                      # 1
    outTemp = outTemp + 0.4, loop                # 2
    barometer = barometer + .3, archive          # 3
    windSpeed = windSpeed * 1.05, loop, archive  # 4

1. Apply the correction to all LOOP packets. Apply the correction to archive
   records only if they came from hardware. This is usually what you want.
2. Apply the correction only to LOOP packets. Do not apply to archive records.
3. Apply the correction only to archive records. Do not apply to LOOP packets.
4. Apply the correction to both LOOP packets and archive records all the time,
   even if the archive record came from software.


[^1]:
    Corrections are not applied to software-generated reocords because the
    correction has already been applied to its constitutent LOOP packets.