# Extensible types

## Overview

Right now, the set of observation types is fixed:

- The set of types that `StdWXCalculate` knows how to calculate is limited to a set of "magic types,"
such as `dewpoint`, or `heatindex`.
- Heating and cooling degree days are also special types, defined in subclass `WXDaySummaryManager`.
- There is no way to add new types to the tag system, unless they appear in
the "current" record, or in the database.  

In theory, new types can be introduced by subclassing, but this allows only new types to be accreted 
in a linear fashion: it would not be possible for two extensions to both introduce new types. 
One would have to inherit from the other.

## Strategy

- A new module, `weewx.xtypes`, will be introduced. Similar to the existing `weewx.units`, it would be responsible for
managing new types. It would be initialized by the engine on startup, using directives from `weewx.conf`. It would offer
an interface, to be outlined below, that allows new types to be calculated.

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

## Defining new types
Adding a new observation type is done by writing a class with the following interface:

File **user/mytypes.py**
```python
import weewx
import weewx.wxformulas

class MyTypes(object):
   """Calculate dewpoint"""
   def get_value(self, obs_type, record, db_manager):
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

Note that if an observation type is unknown to the class, it should raise an exception of type `weewx.UnknownType`,
*not* return a value of `None`. A value of `None` is reserved for a known type, but one that the class is unable to
calculate, perhaps because an input values is missing.

## New aggregation types
In a similar manner, a new aggregation is added using a class with the following interface:

```python
class MyVector(object):

    def get_aggregate(self, obs_type, timespan,
                      aggregate_type=None,
                      aggregate_interval=None):

        if obs_type.starts_with('ch'):
            "something"

        else:
            raise weewx.UnknownType(obs_type)
```

## Registering with the engine
The engine becomes aware of new types through entries in `weewx.conf`:

```ini
[XTypes]
    [[MyTypes]]
        types = user.mytypes.MyTypes
        aggregates = user.mytypes.MyVector
```
The subsection name `[[MyTypes]]` is not actually used and is there only to keep additions logically separate.

## New types API

To get a value for a type, say `dewpoint`, the following interface is used:

```python
import weewx.xtypes

record = {'usUnits': 1, 'outTemp': 65.0, 'humidity': 45.0}

dewpoint = weewx.xtypes.get_value('dewpoint', record, None)

try:
    foo = weewx.xtypes.get_value('risky_type', record, None)
except weewx.UnknownType as e:
    log.error("Unknown type %s" % e)
```

The module `weewx.xtypes` will try each registered class listed in `[XTypes]` in order. If an 
exception of type `weewx.UnknownType` is raised, it moves on to the next one, continuing until it 
receives a value. If no registered class knows how to perform the calculation, it too raises
an exception of `weewx.UnknownType`. Callers may have to be prepared to catch it, depending on
context.

        
        