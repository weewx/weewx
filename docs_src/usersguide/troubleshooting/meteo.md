# Meteorological problems

## The pressure reported by WeeWX does not match the pressure on the console

Be sure that you are comparing the right values. There are three different types
of pressure:

* **Station Pressure**: The _Station Pressure_ (SP), which is the raw, absolute
  pressure measured by the station. This is `pressure` in WeeWX packets and
  archive records.

* **Sea Level Pressure**: The _Sea Level Pressure_ (SLP) is obtained by
  correcting the Station Pressure for altitude and local temperature. This is
  `barometer` in WeeWX packets and archive records.

* **Altimeter**: The _Altimeter Setting_ (AS) is obtained by correcting the 
Station Pressure for altitude. This is `altimeter` in WeeWX packets and archive
records. Any station might require calibration. For some hardware, this can be
done at the weather station console. Alternatively, use the `StdCalibrate`
section to apply an offset.

If your station is significantly above (or below) sea level, be sure that the
station altitude is specified properly. Also, be sure that any calibration
results in a station pressure and/or barometric pressure that matches those
reported by other stations in your area.

## Calibrating barometer does not change the pressure displayed by WeeWX

Be sure that the calibration is applied to the correct quantity.

The corrections in the `StdCalibrate` section apply only to raw values from the
hardware; corrections are not applied to derived quantities.

The station hardware matters. Some stations report gauge pressure (`pressure`)
while other stations report sea-level pressure (`barometer`). For example, if
the hardware is a Vantage station, the correction must be applied to `barometer`
since the Vantage station reports `barometer` and WeeWX calculates `pressure`.
However, if the hardware is a FineOffset station, the correction must be applied
to `pressure` since the FineOffset stations report `pressure` and WeeWX
calculates `barometer`.

## The rainfall and/or rain rate reported by WeeWX do not match the console

First of all, be sure that you are comparing the right quantities. The value
`rain` is the amount of rainfall observed in a period of time. The period of
time might be a LOOP interval, in which case the `rain` is the amount of rain
since the last LOOP packet. Because LOOP packets arrive quite frequently, this
value is likely to be very small. Or the period of time might be an archive
interval, in which case `rain` is the total amount of rain reported since the
last archive record.

Some consoles report the amount of rain in the past hour, or the amount of rain
since midnight.

The rain rate is a derived quantity. Some stations report a rain rate, but for
those that do not, WeeWX will calculate the rain rate.

Finally, beware of calibration factors specific to the hardware. For example,
the bucket type on a Vantage station must be specified when you set up the
weather station. If you modify the rain bucket with a larger collection area,
then you will have to add a multiplier in the `StdCalibrate` section.

To diagnose rain issues, run WeeWX directly so that you can see each LOOP packet
and REC archive record. Tip the bucket to verify that each bucket tip is
detected and reported by WeeWX. Verify that each bucket tip is converted to the
correct rainfall amount. Then check the database to verify that the values are
properly added and recorded.

## There is no wind direction when wind speed is zero

This is by design &mdash; if there is no wind, then the wind direction is
undefined, represented by NULL in the database or `None` in Python. This policy
is enforced by the `StdWXCalculate` service. If necessary, it can be overridden.
See option [force_null](../../reference/weewx-options/stdwxcalculate.md#force_null)
in the [[StdWXCalculate]](../../reference/weewx-options/stdwxcalculate.md)
section.

WeeWX distinguishes between a value of zero and no value (NULL or None).
However, some services do not make this distinction and replace a NULL or None
with a clearly invalid value such as -999.