# [StdStationWatch]

This service watches how old the newest archive record is. When it gets older
than `max_age`, WeeWX logs a warning and issues a `STATION_DOWN` event. When
records arrive again, it logs and issues `STATION_UP`.

Both events are issued from the service's own thread, not from the main loop.
Anything bound to them must not use the console.

#### max_age

Seconds the newest archive record may be, before the station counts as having
stopped reporting. Make it a multiple of the archive interval, so that a single
missing record does not trip it. No default: without this option WeeWX does not
watch at all.

``` ini
[StdStationWatch]
    max_age = 1800
```

#### data_binding

The binding to watch. Default is `wx_binding`.

``` ini
[StdStationWatch]
    data_binding = wx_binding
```
