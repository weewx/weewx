# [StdQC]

The `StdQC` service offers a very simple _Quality Control_ that only checks
that values are within a minimum and maximum range.

Because this service is normally run after `StdConvert`, the units to be used
should be the same as the target unit system chosen in `StdConvert`. It is
also important that it be run after the calibration service, `StdCalibrate`
and before the archiving service `StdArchive`, so that it is the calibrated
and corrected data that are stored.

In a default configuration, quality control checks are applied to observations
from the hardware. They are not applied to derived calculations since the
`StdWXCalculate` service runs after the quality control.

## [[MinMax]]

In this section you list the observation types you wish to have checked, along
with their minimum and maximum values. If not specified, the units should are
in the same unit system as specified in [`[StdConvert]`](stdconvert.md).

For example,

``` ini
[[MinMax]]
    outTemp = -40, 120
    barometer = 28, 32.5
    outHumidity = 0, 100 
```

With `target_unit=US` (the default), if a temperature should fall outside
the inclusive range -40 °F through 120 °F, then it will be set to the null
value, `None`, and ignored. In a similar manner, the acceptable values for
barometric pressure would be 28 through 32.5 inHg, for humidity 0 through 100%.

You can also specify units.

For example,

``` ini
[[MinMax]]
    outTemp = -40, 60, degree_C
    barometer = 28, 32.5, inHg
```

In this example, if a temperature should fall outside the inclusive range
-40 °C through 60 °C, then it will be set to the null value, `None`, and
ignored. In a similar manner, the acceptable values for barometric pressure
would be 28 through 32.5 inHg. Since the units have been specified, these
values apply no matter what the `target_unit`.

Both LOOP and archive data will be checked.

Knowing the details of how your hardware encodes data helps to minimize the
number of observations that need to be checked. For example, the VP2 devotes
only one unsigned byte to storing wind speed, and even then `0xff` is devoted
to a bad value, so the only possible values that could appear are 0 through
126 mph, a reasonable range. So, for the VP2, there is no real point in
checking wind speed.
