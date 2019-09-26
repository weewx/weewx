# Extensible types

## Abstract

This proposal allows new derived observation types to be added to WeeWX. 

## Motivation

Right now, the set of observation types is fixed:

- The set of types that `StdWXCalculate` knows how to calculate is limited to a set of "magic types,"
such as `dewpoint`, or `heatindex`.
- Heating and cooling degree days are also special types, defined in subclass `WXDaySummaryManager`.
- There is no way to add new types to the tag system, unless they appear in
the "current" record, or in the database.  

In theory, new types can be introduced by subclassing, but this allows only new types to be accreted in a linear
fashion: it would not be possible for two extensions to both introduce new types. One would have to inherit from the
other.

The goal of XTypes is to allow the user to add new types to the system with a minimum of fuss. 

------------------------

## Proposal

### Summary
- A new module, `weewx.xtypes`, will be introduced. Similar to the existing `weewx.units`, it would be responsible for
managing new types. New types can be added dynamically, using a Python API.

- Simplicity of adding new types is favored over simplicity of using the new types. This is because the end-users
are more likely to be doing the former, rather than the latter.

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
Adding a new observation type is done by writing a class with two methods: `get_scalar()` and `get_series()`.

```python
class MyTypes(object):

    def get_scalar(self, obs_type, record, db_manager):
        """Return a single value of type obs_type."""

    def get_series(self, obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
        """Return a list of type obs_type, bounded in time, and possibly aggregated."""
```

An instance of this type is then registered with module `weewx.xtypes`:

```python
import weewx.xtypes

obj = MyTypes()
weewx.xtypes.xtypes.append(obj)
```

####  Method `get_scalar()`

Calling signature:

    get_scalar(self, obs_type, record, db_manager)

Where

- `obs_type` is the type to be computed.
- `record` is a WeeWX record. It must include types `dateTime` and `usUnits`.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.

Should return:

- A single scalar, possibly `None` of type `obs_type`.

May raise:

- An exception of type `weewx.UnknownType` if the type `obs_type` is unknown to the instance. 

#### Method `get_series()`

Calling signature:

    get_series(self, obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None)
    
Where

- `obs_type` is the type to be computed.
- `timespan` is an instance of `weeutil.weeutil.TimeSpan`. It defines bounding start and ending times of the series,
exclusive on the left, inclusive on the right.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.
- `aggregate_type` defines the (optional) type of aggregation. Typically, it is one of `sum`, `avg`, `min`, or `max`,
although there is nothing stopping the user-defined extension from defining new types of aggregation.
- `aggregate_interval` is an optional aggregation interval. If not supplied, a single value should be returned:
the aggregate value over the entire `timespan`.

Should return:

- A three-way tuple:
    ```(start_list_vt, stop_list_vt, data_list_vt)``` where

    * `start_list_vt` is a `ValueTuple`, whose first element is the list of start times;
    * `stop_list_vt` is a `ValueTuple`, whose first element is the list of stop times;
    * `data_list_vt` is a `ValueTuple`, whose first element is the list of aggregated values.

May raise:

- An exception of type `weewx.UnknownType` if the type `obs_type` is unknown to the instance. 

#### Example
File **user/mytypes.py**
```python
import weewx
import weewx.wxformulas

class MyTypes(object):
   def get_scalar(self, obs_type, record, db_manager):
       """Calculate dewpoint"""
       if obs_type == 'dewpoint':
           if record['usUnits'] == weewx.US:
               return weewx.wxformulas.dewpointF(record.get('outTemp'), record.get('outHumidity'))
           elif record['usUnits'] == weewx.METRIC or record['usUnits'] == weewx.METRICWX:
               return weewx.wxformulas.dewpointC(record.get('outTemp'), record.get('outHumidity'))
           else:
               raise ValueError("Unknown unit system %s" % record['usUnits'])
       else:
           raise weewx.UnknownType(obs_type)
```



### Using the extension

To get a value for a type, say `dewpoint`, the following interface is used:

```python
import weewx.xtypes

record = {'usUnits': 1, 'outTemp': 65.0, 'humidity': 45.0}

dewpoint = weewx.xtypes.get_scalar('dewpoint', record, None)

try:
    foo = weewx.xtypes.get_scalar('risky_type', record, None)
except weewx.UnknownType as e:
    log.error("Unknown type %s" % e)
```

The function `weewx.xtypes.get_scalar()` will try each registered instance in order. If an exception of type
`weewx.UnknownType` is raised, it moves on to the next one, continuing until it receives a value. If no registered
instance knows how to perform the calculation, then `weewx.xtypes.get_scalar()` itself will raise an exception of type
`weewx.UnknownType`. Callers may have to be prepared to catch it, depending on context.

        
## Alternatives

### Alternative: register functions with weewx.conf

This alternative was considered and rejected. The reason is that it requires a rigid API that new types must adhere to.
It is difficult to predict what information they might need. For example, calculating pressure requires altitude, so the
API would need some way of supplying that value.

This is avoided by supplying a Python API that the type must adhere to. The new type can get any information
it wants, then register with the API.

### Alternative: register functions through the API
With this alternative, new types register with a Python API, but register functions, rather than an
instance of a class.

This would work well, but it is desirable to have both the `get_scalar()` and `get_series()` methods
in one class. This way, all information about a new type can be found in one place.

### Alternative: declare types
If an observation type is unknown to a type extension, it should raise an exception of type `weewx.UnknownType`. 
An alternative that was considered is to require extensions to declare what types they can handle. This allows
types to be discoverable.

But, it has a disadvantage that all known types must be declared. That's not always practical. For example,
a type extension would be useful to calculate power from a running aggregate of energy from an energy monitor.
But, some monitors are capable of emitting 48+ channels, each of which would have to be declared. Add polarized
and absolute values, and we are looking at nearly 100 types!

Instead, we allow extensions to recognize what types they know about, possibly from a regular expression of 
the observation type. If they don't recognize the type, they raise `weewx.UnknownType`. 

## Backwards compatibility

## Open issues

