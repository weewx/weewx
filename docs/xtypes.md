# Extensible types

## Abstract

This proposal allows new derived observation types to be added to WeeWX. 

## Motivation

Right now, the set of observation types is fixed:

- The set of types that `StdWXCalculate` knows how to calculate is limited to a set of "magic types," such as
`dewpoint`, or `heatindex`.
- Heating and cooling degree days are also special types, defined in subclass `WXDaySummaryManager`.
- There is no way to add new types to the tag system, unless they appear in the "current" record, or in the database.

In theory, new types can be introduced by subclassing, but this allows only new types to be accreted in a linear
fashion: it would not be possible for two extensions to both introduce new types. One would have to inherit from the
other.

The goal of XTypes is to allow the user to add new types to the system with a minimum of fuss. 

------------------------

## Proposal

### Summary
- A new module, `weewx.xtypes`, will be introduced. Similar to the existing `weewx.units`, it would be responsible for
managing new types. New types can be added dynamically, using a Python API.

- The service `StdWXCalculate` will no longer have a fixed set of "special" types. Instead, it will be extensible, by
using `weewx.xtypes`. The existing options of `hardware`, `prefer_hardware`, and `software` would continue. It would
come out-of-the-box with the existing types it now handles (`dewpoint`, `heatindex`, etc.), but new types could be added
by the user. This allows new types to appear in the current LOOP packet or archive record, allowing their use elsewhere
in WeeWX.

- The tag system and the image generator would use `weewx.xtypes` to calculate aggregates of all values. NB: they could
also use `weewx.xtypes` to calculate regular, scalar values, but that shouldn't be necessary 
after `StdWXCalculate` is done.

- The class `WXDaySummaryManager` would go away, and the two types `heatdeg` and `cooldeg` would no longer depend on it.
Instead, the tag system would use `weewx.xtypes` to calculate them.

### Adding new types
Adding a new observation type is done with two functions, one for calculating scalars, the other for calculating 
series.

The functions are then registered with module `weewx.xtypes`.

Note that it is not always necessary to supply both functions.

####  Calculating scalars

The user should write a function with the signature

    fn(obs_type, record, db_manager)

Where

- `obs_type` is the type to be computed.
- `record` is a WeeWX record. It will include at least types `dateTime` and `usUnits`.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.

Note that the signature can be satisfied by using Python closures, or by using
[`functools.partial`](https://docs.python.org/3/library/functools.html#functools.partial), or by similar strategies.

The function should return:

- A single scalar, possibly `None`, of type `obs_type`.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the function. 
- An exception of type `weewx.CannotCalculate` if the type is known to the function, but all the information
necessary to calculate the type is not there.  

#### Calculating series

The user should write a function with the signature

    fn(obs_type, timespan, db_manager, aggregate_type, aggregate_interval)
    
Where

- `obs_type` is the type to be computed.
- `timespan` is an instance of `weeutil.weeutil.TimeSpan`. It defines bounding start and ending times of the series,
exclusive on the left, inclusive on the right.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.
- `aggregate_type` defines the type of aggregation. Typically, it is one of `sum`, `avg`, `min`, or `max`,
although there is nothing stopping the user-defined extension from defining new types of aggregation. If
set to `None`, then no aggregation should occur, and the full series should be returned.
- `aggregate_interval` is an aggregation interval. If set to `None`, then a single value should be returned: the
aggregate value over the entire `timespan`. Otherwise, the series should be grouped by the aggregation interval.

The function should return:

- A three-way tuple:
    ```(start_list_vt, stop_list_vt, data_list_vt)``` where

    * `start_list_vt` is a `ValueTuple`, whose first element is the list of start times;
    * `stop_list_vt` is a `ValueTuple`, whose first element is the list of stop times;
    * `data_list_vt` is a `ValueTuple`, whose first element is the list of aggregated values.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the instance. 
- An exception of type `weewx.CannotCalculate` if the type is known to the function, but all the information
necessary to calculate the type is not there.  


#### Registering functions

The module `weewx.xtypes` keeps two simple lists, one for scalar functions, one for series functions. The user-supplied
function should be inserted into the appropriate list, usually by appending.

List of scalar functions:
```python
weewx.xtypes.scalar_types
```

List of series functions:
```python
weewx.xtypes.series_types
```

#### Example
File **user/pressure.py**
```python
import weewx.units
import weewx.uwxutils

class Pressure(object):

    def __init__(self, altitude_ft):
        """Initialize  with the altitude in feet"""
        self.altitude_ft = altitude_ft

    def _get_temperature_12h(self, ts, dbmanager):
        """Get the temperature from 12 hours ago."""

        # ... details elided

    def pressure(self, obs_type, record, dbmanager):
        """Calculate the observation type 'pressure'."""

        if obs_type != 'pressure':
            raise weewx.UnknownType

        # Get the temperature in Fahrenheit from 12 hours ago
        temp_12h_F = self._get_temperature_12h(record['dateTime'], dbmanager)
        if temp_12h_F is not None:
            try:
                # The following requires everything to be in US Customary units.
                record_US = weewx.units.to_US(record)
                pressure = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                    record_US['barometer'],
                    self.altitude_ft,
                    record_US['outTemp'],
                    temp_12h_F,
                    record_US['outHumidity']
                )

                if record['usUnits'] == weewx.METRIC or record['usUnits'] == weewx.METRICWX:
                    pressure /= weewx.units.INHG_PER_MBAR
                return pressure

            except KeyError:
                # Don't have everything we need. Raise an exception.
                raise weewx.CannotCalculate(obs_type)

        # Else, fall off the end and return None
```
Note how the method `pressure()` raises an exception of type `weewx.UnknownType` for any types it does not
recognize. 

Also, note that the method requires observation types `barometer`, `outTemp`, and `outHumidity` in order 
to perform the calculation, and raises an exception of type `weewx.CannotCalculate` if one of them is missing.

### Registering the extension
Continuing our example above:

```python
import weewx.xtypes

# Create an instance of the Pressure class, initializing it with the altitude in feet:
pobj = Pressure(700.0)
# Register the method pressure() as a scalar type
weewx.xtypes.scalar_types.append(pobj.pressure)
```

Note how this example registers a *method* of class `Pressure` by using Python closures. This allows state variables to
be stored in the class, in this case the altitude, and a cached value of the temperature from 12 hours ago.

### Using the extension

To use the above example:

```python
import weewx.manager

archive_sqlite = {'database_name': '/home/weewx/archive/weewx.sdb', 'driver': 'weedb.sqlite'}

with weewx.manager.Manager.open_with_create(archive_sqlite) as db_manager:
    # Work with the last record in the database:
    timestamp = db_manager.lastGoodStamp()
    record = db_manager.getRecord(timestamp)
    p = weewx.xtypes.get_scalar('pressure', record, db_manager)
    print("Pressure = %s" % p)

    # Try again, but missing outTemp:
    del record['outTemp']
    try:
        p = weewx.xtypes.get_scalar('pressure', record, db_manager)
    except weewx.CannotCalculate as e:
        print("Unable to calculate type '%s'" % e)

    # Try calculating a type we know nothing about
    try:
        q = weewx.xtypes.get_scalar('foo', record, db_manager)
    except weewx.UnknownType as e:
        print("Unknown type: '%s'" % e)
```

Results of running the program:
```
Pressure = 29.4539701889
Unable to calculate type `pressure`
Unknown type: 'foo'
```

The function `weewx.xtypes.get_scalar()` will try each registered function in order. If an exception of type
`weewx.UnknownType` is raised, it moves on to the next one, continuing until it receives a value. If no registered
instance knows how to perform the calculation, then `weewx.xtypes.get_scalar()` itself will raise an exception of type
`weewx.UnknownType`. Callers should be prepared to catch it, depending on context.

        
## Alternatives to the chosen design

### Alternative: register functions with weewx.conf

This approach has the advantage that it requires a bit less programming and, most importantly, it leaves a concise
record of what extensions are being used in the configuration file `weewx.conf`.

However, it has a big disadvantage. The example above shows why. It is difficult to predict what data a user might need
to write an extension. In our example, we needed the altitude of the station. Where would that come from? The answer is
that it would have to be supplied by a standardized interface to the user function. This means the user might
potentially have to know everything, so you end up with a system where everything is connected to everything.

This is avoided by supplying a Python API that the type must adhere to. The new type can get any information it wants,
then register with the API, perhaps using Python closures. This is what our example does.

### Alternative: register classes through the API
With this alternative, new types register with a Python API, but register classes, rather than functions.
The class would then be required to supply two methods, say `get_scalar()` and `get_series()`, that the extensible API
would call. This has the advantage that all information about a new type can be found in one place.

However, it has the disadvantage that it requires a class where one might not be needed, complicating implementations
("Push policy up, implementation down", in this case, the policy being that the functions must have well-known
names and must be in a class).

### Alternative: declare types
If an observation type is unknown to a type extension, it should raise an exception of type `weewx.UnknownType`. An
alternative that was considered is to require extensions to declare what types they can handle. This allows types to be
discoverable.

But, it has a disadvantage that all known types must be declared. That's not always practical. For example, a type
extension would be useful to calculate power from a running aggregate of energy from an energy monitor. But, some
monitors are capable of emitting 48+ channels, each of which would have to be declared. Add polarized and absolute
values, and we are looking at nearly 100 types!

Instead, we allow extensions to recognize what types they know about, possibly from a regular expression of the
observation type. If they don't recognize the type, they raise `weewx.UnknownType`. Types do not have to be declared
in advance.

## Open issues

