# [StdTimeSynch]

The `StdTymeSynch` service can synchronize the onboard clock of station with
your computer. Not all weather station hardware supports this.

#### clock_check

How often to check the clock on the weather station in seconds. Default is
`14400` (every 4 hours).

#### max_drift

The maximum amount of clock drift to tolerate, in seconds, before resetting
the clock. Default is `5`.
