# [StdCalibrate]

This section is for configuring the `StdCalibrate` service. This service offers an opportunity to correct for any calibration errors in your instruments. It is very general and flexible.

Because this service is normally run after `StdConvert`, the units to be used should be the same as the target unit system chosen in [`StdConvert`](../stdconvert-config). It is also important that this service be run before the archiving service `StdArchive`, so that it is the corrected data that are stored.

In a default configuration, calibrations are applied to observations from the hardware. They are not applied to derived calculations since the `StdWXCalculate` service runs after `StdCalibrate`.

## [[Corrections]]

In this section you list all correction expressions. For example, say that you know your outside thermometer reads high by 0.2°F. You could add the expression:

```
outTemp = outTemp - 0.2
```

Perhaps you need a linear correction around a reference temperature of 68°F:

```
outTemp = outTemp + (outTemp-68) * 0.02
```

It is even possible to do corrections involving more than one variable. Suppose you have a temperature sensitive barometer:

```
barometer = barometer + (outTemp-32) * 0.0091
```

All correction expressions are run in the order given.

Both LOOP data and archive data will be corrected.

If you are using a Davis Vantage instrument and all you require is a simple correction offset, this can also be done in the hardware. See your manual for instructions.