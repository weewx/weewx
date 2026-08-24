# [Accumulator]

As LOOP packets arrive, WeeWX holds the values for each observation type in an
*accumulator*. At the end of the archive interval the accumulator is asked for
one value per type, and those values become the archive record.

How that happens is settable per observation type. The defaults suit the types
WeeWX knows about: temperatures are averaged over the interval, rain is
totalled, `txBatteryStatus` reports its last reading. A type WeeWX has not seen
before, one that your driver or a service adds, is averaged. That is wrong for
anything that counts or accumulates.

This section is not in the distributed `weewx.conf`. Add it only for the types
whose treatment you need to change:

``` ini
[Accumulator]
    [[lightning_strike_count]]
        extractor = sum
    [[lightning_distance]]
        extractor = min
```

Each subsection is named after an observation type and takes any of four
options. Nothing else needs to be given: what you leave out keeps its default.

!!! Note
    An unrecognized value raises a `KeyError` naming it, rather than a message
    saying what is wrong. It is not raised at startup either, but the first time
    the type turns up in a packet, or at the end of the first archive interval.
    The names below are the whole of what is accepted.

#### accumulator

Which kind of accumulator to use, and therefore what it is able to remember.

| Value       | Keeps                                                        |
|-------------|--------------------------------------------------------------|
| `scalar`    | Sum, count, first, last, minimum and maximum, with their times |
| `vector`    | As `scalar`, plus direction. Used by `wind`                   |
| `firstlast` | The first and last value only. The only one that accepts strings |

Default is `scalar`. Use `firstlast` for a type whose values are text: the
others do arithmetic on what they are given.

#### adder

What to do with each value as it arrives.

| Value         | Effect                                                       |
|---------------|--------------------------------------------------------------|
| `add`         | Add the value to the accumulator                              |
| `add_wind`    | Add a wind speed, keeping direction and gust with it          |
| `check_units` | Do not accumulate; check that the unit system has not changed |
| `noop`        | Discard the value                                             |

Default is `add`. The other three exist for `windSpeed`, `usUnits` and
`dateTime` respectively, and are unlikely to be useful elsewhere.

#### merger

What to do when two accumulators are combined, which happens when statistics
are rolled up over a longer period.

| Value    | Effect                                                     |
|----------|-------------------------------------------------------------|
| `minmax` | Keep the lowest minimum and the highest maximum              |
| `avg`    | Keep the lowest minimum, but use the average as the maximum  |

Default is `minmax`. Use `avg` for a type whose maximum is meaningless on its
own, such as a wind speed that is already an average.

#### extractor

What the accumulator contributes to the archive record. This is the option you
are most likely to want.

| Value   | Puts into the record                                             |
|---------|-------------------------------------------------------------------|
| `avg`   | The average over the interval                                     |
| `sum`   | The total. `None` if nothing arrived, rather than zero            |
| `min`   | The lowest value seen                                             |
| `max`   | The highest value seen                                            |
| `first` | The first value seen                                              |
| `last`  | The last value seen                                               |
| `count` | How many values arrived                                           |
| `wind`  | Fans out into `windSpeed`, `windDir`, `windGust` and `windGustDir` |
| `noop`  | Nothing. The type does not reach the archive record               |

Default is `avg`.

Which one to pick follows from what the number means. A reading taken at a
moment, such as temperature or pressure, averages. Something counted during the
interval, such as rainfall or lightning strikes, sums. A running total that the
hardware maintains, such as `dayRain`, takes `last`: adding those up would count
the same rain many times over. A status or a serial number takes `last` too.

A text field needs both options. Averaging is impossible for it, so say which
accumulator to use as well as what to extract:

``` ini
[Accumulator]
    [[forecastText]]
        accumulator = firstlast
        extractor = last
```

The settings WeeWX ships with are at the top of `weewx/accum.py`, and are worth
reading before overriding one. Whether the accumulator is asked for a record at
all depends on `record_generation` in
[`[StdArchive]`](stdarchive.md#record_generation).
