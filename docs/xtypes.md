# Extensible types (XTypes)

## Abstract

This proposal allows new derived observation types to be added to WeeWX. 

## Motivation

Right now, the set of observation types is fixed:

- The set of types that `StdWXCalculate` knows how to calculate is limited to a set of "magic 
types," such as `dewpoint`, or `heatindex`.
- Heating and cooling degree days are also special types, defined in subclass 
`WXDaySummaryManager`.
- There is no way to add new types to the tag system, unless they appear in the "current" record, 
or in the database.

In theory, new types can be introduced by subclassing, but this allows only new types to be
accreted in a linear fashion: it would not be possible for two extensions to both introduce new
types. One would have to inherit from the other.

The goal of XTypes is to allow the user to add new types to the system with a minimum of fuss. 

------------------------

## Summary
- A new module, `weewx.xtypes`, will be introduced. Similar to the existing `weewx.units`, it would
be responsible for managing new types. New types can be added dynamically, using a Python API.

- The service `StdWXCalculate` will no longer have a fixed set of "special" types. Instead, it will
be extensible, by using `weewx.xtypes`. The existing options of `hardware`, `prefer_hardware`, and
`software` would continue. It would come out-of-the-box with the existing types it now handles
(`dewpoint`, `heatindex`, etc.), but new types could be added by the user. This allows new types to
appear in the current LOOP packet or archive record, allowing their use elsewhere in WeeWX.

- When resolving tags, the Cheetah generator would first look in the present record, then in the
database, as it does now. But, then it would look to `weewx.types` to try and calculate any
unresolved types. This would allow the products of `StdWXCalculate` to be used by `wee_reports`,
resolving [Issue #95](https://github.com/weewx/weewx/issues/95)

- In a similar manner, the Image generator would first try the database to resolve any series. If
that doesn't work, it would then try `weewx.xtypes`.

- The class `WXDaySummaryManager` would be deprecated, and the two types `heatdeg` and `cooldeg`
would no longer depend on it. Instead, the tag system would use `weewx.xtypes` to calculate them.

- The schema system would be expanded to allow explicit declaration of the schema for the daily
summaries. This replaces some functionality presently done by `WXDaySummaryManager`.

------------------------

## Overview of adding new types
Adding a new observation type is done by subclassing the abstract base class `XTypes`, then
overriding one to three functions:

```python
class XTypes:
    get_scalar(obs_type, record, db_manager=None)
    get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None)
    get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict)
```

An instance of the subclass is then instantiated and registered with `weewx.xtypes`. Note that it
is not always necessary to supply all three functions. Details follow

###  Calculating scalars

To calculate a custom scalar value, the user should subclass `XTypes`, then override the member
function `get_scalar`:

    class MyTypes(XTypes):
    
        def get_scalar(obs_type, record, db_manager):
            ...

Where

- `obs_type` is the name of type to be computed.
- `record` is a WeeWX record. It will include at least types `dateTime` and `usUnits`.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be 
open and usable.

The function should return:

- A `ValueTuple` scalar. The value held by the `ValueTuple` can be `None`.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is not known to the function. 
- An exception of type `weewx.CannotCalculate` if the type is known to the function, but all the 
information necessary to calculate the type is not there.  

### Calculating series

The user should subclass `XTypes`, then override the member function `get_series`:

    class MyTypes(XTypes):
    
        def get_series(obs_type, timespan, db_manager, aggregate_type, aggregate_interval):
           ...
    
Where

- `obs_type` is the name of type to be computed.
- `timespan` is an instance of `weeutil.weeutil.TimeSpan`. It defines bounding start and ending
  times of the series, exclusive on the left, inclusive on the right.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be
  open and usable.
- `aggregate_type` defines the type of aggregation, if any. Typically, it is one of `sum`, `avg`,
  `min`, or `max`, although there is nothing stopping the user-defined extension from defining
  new types of aggregation. If set to `None`, then no aggregation should occur, and the full series
  should be returned.
- `aggregate_interval` is an aggregation interval. If aggregation is to be done (*i.e.*,
  `aggregate_type` is not `None`), then the series should be grouped by the aggregation interval.

The function should return:

- A three-way tuple:
    `(start_list_vt, stop_list_vt, data_list_vt)` where

    * `start_list_vt` is a `ValueTuple`, whose first element is a list of start times;
    * `stop_list_vt` is a `ValueTuple`, whose first element is a list of stop times;
    * `data_list_vt` is a `ValueTuple`, whose first element is a list of aggregated values.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is not known to the function. 
- An exception of type `weewx.UnknownAggregation` if the aggregation `aggregate_type` is not known
  to the function. 
- An exception of type `weewx.CannotCalculate` if the type and aggregation are known to the 
  function, but all the information necessary to perform the calculate is not there.

### Calculating aggregates

To calculate a custom aggregation, the user should override the member function `get_aggregate`:

    class MyTypes(XTypes):
    
        def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
            ...
        
Where

- `obs_type` is the type over which the aggregation is to be computed.
- `timespan` is an instance of `weeutil.weeutil.TimeSpan`. It defines bounding start and ending 
times of the aggregation, exclusive on the left, inclusive on the right.
- `aggregate_type` is the type of aggregation to be performed, such as `avg`, or `last`, or it can
be some new, user-defined aggregation.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be 
open and usable.
- `option_dict` is a dictionary containing any extra parameters used in the aggregation. For example, suppose you have
defined a new aggregation that gives the percentage of observations greater than a specified number of standard 
deviations from the mean:
    ```
    $year.outTemp.deviation_percentage(sd=2.0)
    ```
    then the parameter `option_dict` would include a key of `sd`, with a value of `2`.

The function should return:

- A `ValueTuple` holding the aggregated value.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is not known to the function.
- An exception of type `weewx.UnknownAggregation` if the aggregation `aggregate_type` is not known 
to the function. 
- An exception of type `weewx.CannotCalculate` if the type and aggregation are known to the 
function, but all the information necessary to perform the aggregation is not there.

See the extension [weewx-xaggs](https://github.com/tkeffer/weewx-xaggs) for an example of how to
add a new aggregate type.

### Registering your subclass

The next step is to tell the XTypes system about the existence of your extension. The module
`weewx.xtypes` keeps a simple list of extensions. When it comes time to evaluate a derived
type, the list is scanned, and the first entry that successfully resolves a type, is the one
that is used.

_Order matters!_ Your new class should be prepended or appended to the list, depending on whether
you want it to override other extensions. If it is at the front of the list (prepended), it will be
the first to be tried, and so will take precedence over anything further back in the list.
See the section [XTypes API](#xtypes-api).

There are two general ways of arranging to have your XTypes extension registered.

#### Statically
In this approach, you create an instance of your class in a file, then add it to the `xtypes` list.
This works well when a file is likely to get loaded for some other reasons, perhaps because
a WeeWX service extension is in it. It does not work so well if it needs special
information, such as information that can only be obtained from the configuration
file `weewx.conf`.

```python
import weewx.xtypes

class MyXType(weewx.xtypes.XType):
    def get_scalar(self, obs_type, record, db_manager=None):
        # Perform some calculation...
        ...
        return value

# Instantiate an instance, and append it to the list:
weewx.xtypes.xtypes.append(MyXType())
```

#### As a service
In this approach, you explicitly create a WeeWX service, which will load and unload your extension.
This is a good approach when you need information out of `weewx.conf`.

Here's the general pattern. Take a look in the files `weewx/wxxtypes.py` for some other
comprehensive examples used internally by WeeWX.

```python
from weewx.engine import StdService
import weewx.xtypes

# This is the actual XTypes extension:
class OtherXType(weewx.xtypes.XType):
    def __init__(self, info1=1, info2=2):
        self.info1 = info1
        self.info2 = info2
    def get_scalar(self, obs_type, record, db_manager=None):
        # Perform some calculation involving info1 and info2
        ...
        return value

# This is a WeeWX service, whose only job is to register and unregister the extension:
class MyService(StdService):
    def __init__(self, engine, config_dict):
        super(MyService, self).__init__(engine, config_dict)

        # Get some options out of the configuration dictionary
        info1 = config_dict['OtherXType']['info1']
        info2 = config_dict['OtherXtype']['info2']

        # Instantiate an instance of the class OtherXType, using the options:
        self.xt = OtherXType(info1, info2)

        # Register the class
        weewx.xtypes.xtypes.append(self.xt)

    def shutDown(self):
        # Engine is shutting down. Remove the registration
        weewx.xtypes.xtypes.remove(self.xt)
```

### Including in loop packets and archive records

With the previous step, the defined values can be used in templates (such as `index.html.tmpl`) and
plots. However, if you want to see the values in loop packets and/or archive records, or want to
publish them by MQTT, then you need to extend the section `[StdWXCalculate]`, subsection
[`[[Calculations]]`](http://www.weewx.com/docs/usersguide.htm#[[Calculations]]), in `weewx.conf`.

For example, say the name of the new observation type defined in your extension is "bore_pressure", then you could
write:

```ini
[StdWXCalculate]
    [[Calculations]]
        ...
        bore_pressure = prefer_hardware
        ...
```

where `prefer_hardware` means the value will be calculated by the extension if the hardware does not
supply a value. See the section
[_[[Calculations]]_](http://www.weewx.com/docs/usersguide.htm#[[Calculations]]) in the User's Guide
for other options.

With this addition, if a record comes in that does not include a value for `bore_pressure`, the record will be handed
off to the XTypes system with a request to calculate `bore_pressure`. Because you registered your
extension with the system, it will find your extension and calculate the value. The new value will then be put into the
record, where it can be used like any other value.


------------------------

## A comprehensive example

In this example, we are going to write an extension to calculate the 
[vapor pressure of water](https://en.wikipedia.org/wiki/Vapour_pressure_of_water). The observation
type will be called `vapor_p`, and we will offer two algorithms for calculating it. This example is
included in WeeWX V4.3 and later in the `examples` subdirectory.

### The extension
Here's what the XTypes extension looks like:

```python
# File user/vaporpressure.py

import math

import weewx
import weewx.units
import weewx.xtypes
from weewx.units import ValueTuple

class VaporPressure(weewx.xtypes.XType):

    def __init__(self, algorithm='simple'):
        # Save the algorithm to be used.
        self.algorithm = algorithm.lower()

    def get_scalar(self, obs_type, record, db_manager):
        # We only know how to calculate 'vapor_p'. For everything else, raise an exception UnknownType
        if obs_type != 'vapor_p':
            raise weewx.UnknownType(obs_type)

        # We need outTemp in order to do the calculation.
        if 'outTemp' not in record or record['outTemp'] is None:
            raise weewx.CannotCalculate(obs_type)

        # We have everything we need. Start by forming a ValueTuple for the outside temperature.
        # To do this, figure out what unit and group the record is in ...
        unit_and_group = weewx.units.getStandardUnitType(record['usUnits'], 'outTemp')
        # ... then form the ValueTuple.
        outTemp_vt = ValueTuple(record['outTemp'], *unit_and_group)

        # Both algorithms need temperature in Celsius, so let's make sure our incoming temperature
        # is in that unit. Use function convert(). The results will be in the form of a ValueTuple
        outTemp_C_vt = weewx.units.convert(outTemp_vt, 'degree_C')
        # Get the first element of the ValueTuple. This will be in Celsius:
        outTemp_C = outTemp_C_vt[0]

        if self.algorithm == 'simple':
            # Use the "Simple" algorithm.
            # We need temperature in Kelvin.
            outTemp_K = weewx.units.CtoK(outTemp_C)
            # Now we can use the formula. Results will be in mmHg. Create a ValueTuple out of it:
            p_vt = ValueTuple(math.exp(20.386 - 5132.0 / outTemp_K), 'mmHg', 'group_pressure')
        elif self.algorithm == 'teters':
            # Use Teter's algorithm.
            # Use the formula. Results will be in kPa:
            p_kPa = 0.61078 * math.exp(17.27 * outTemp_C_vt[0] / (outTemp_C_vt[0] + 237.3))
            # Form a ValueTuple
            p_vt = ValueTuple(p_kPa, 'kPa', 'group_pressure')
        else:
            # Don't recognize the exception. Fail hard:
            raise ValueError(self.algorithm)

        # If we got this far, we were able to calculate a value. Return it.
        return p_vt
```

We have subclassed `XTypes` as a class called `VaporPressure`. By default, it uses a "simple"
algorithm to calculate the vapor pressure, but the constructor for the class gives us a chance
to use another algorithm, *Teter's* algorithm.

### Registering the extension
Now we need to register the extension with the XTypes system, and to provide some way of specifying
which algorithm we want to use. We can accomplish both by writing a simple WeeWX service. Here's
what it looks like:

```python
from weewx.engine import StdService

class VaporPressureService(StdService):
    def __init__(self, engine, config_dict):
        super(VaporPressureService, self).__init__(engine, config_dict)
        
        # Get the desired algorithm. Default to "simple".
        try:
            algorithm = config_dict['VaporPressure']['algorithm']
        except KeyError:
            algorithm = 'simple'
            
        # Instantiate an instance of VaporPressure:
        self.vp = VaporPressure(algorithm)
        # Register it with the XTypes system:
        weewx.xtypes.xtypes.append(self.vp)
        
    def shutDown(self):
        # Remove the registered instance:
        weewx.xtypes.xtypes.remove(self.vp)
```

Like any other WeeWX service, `VaporPressureService` needs to be added to the list of services to
be run, so that the engine will instantiate it. We do this by adding it to the end of the service 
group `xtype_services`.

```ini
[Engine]

    [[Services]]
        # This section specifies the services that should be run. They are
        # grouped by type, and the order of services within each group
        # determines the order in which the services will be run.
        xtype_services = weewx.wxxtypes.StdWXXTypes, weewx.wxxtypes.StdPressureCooker, weewx.wxxtypes.StdRainRater, user.vaporpressure.VaporPressureService
        ...
```

The final step is to tell the unit system what group our new observation type, `vapor_p`, is in:

```python
weewx.units.obs_group_dict['vapor_p'] = "group_pressure"
```
  
The resultant file, `vaporpressure.py`, can be found in the `examples` subdirectory.

### Using the extension
There are several different ways you can use your extension:
1. In an expression in a Cheetah template;
2. As a type to be plotted;
3. To populate data packets and records;
4. In other extensions.

#### Cheetah
Suppose we want to show the current vapor pressure in a Cheetah template:

```
<p>The current vapor pressure is $current.vapor_p </p>
```

The Cheetah engine will first look for the type `vapor_p` in the current record. It won't be there,
because it's a derived type. Then it will look in the database. Unless we've made other
arrangements, it won't be there either. Finally, the Cheetah engine invokes the XTypes system to
see if it can calculate it. Because of our extension, this works.

#### Plot images

We can also use our XTypes extension in a plot. For example, suppose we wanted to plot today's
vapor pressure. Here's what the entry in the skin configuration file, `skin.conf` would look like:
```ini
    ...
    [[day_images]]
        ...
        [[[dayvaporp]]]
            [[[[vapor_p]]]]
```

This would instruct the plotting engine to create an image file `dayvaporp.png` containing a 
plot with a single variable: `vapor_p`:

![image](images/dayvaporp.png)

How does this work? The XTypes system includes a version of `get_series()`, which in the absence of
a specialized version of `get_series()`, repeatedly calls our version of `get_scalar()`,
synthesizing a series. However, this version _does not_ know how to calculate aggregations
(although there's no reason why this couldn't be added in the future).

#### Populate packets and records

In the above examples, the type `vapor_p` was evaluated "just in time" to be used in a template or
plot. If you want `vapor_p` to appear in packets and records, perhaps  because you want to store it
in a database, you can ask the service `StdWXCalculate` to calculate it for you and put it in the
packet / record.

```ini
[StdWXCalculate]
    [[Calculations]]
        ...
        vapor_p = prefer_hardware
        ...
```

Like any other derived type, this will cause `StdWXCalculate` to first look in the packet or record
to see if it already has a value for `vapor_p` from your hardware station. Most likely, it doesn't,
so `StdWXCalculate` will arrange for the XTypes system to calculate a value, then puts it in
record.

If your database schema includes a slot for `vapor_p`, then the value would be put in the database.

#### XTypes API

Getting a value from the XTypes system can also be useful inside an extension. Most XTypes users
will not need to do this, but if you're writing an extension, it can be helpful.

Module `weewx.xtypes` supplies 3 functions for using user-supplied extensions:

```python
get_scalar(obs_type, record, db_manager=None)
get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None)
get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict)
```

Example: function `weewx.xtypes.get_scalar()` searches the list `weewx.xtypes.xtypes`, trying
member function `get_scalar()` of each object in turn. If the member function raises
`weewx.UnknownType` or `weewx.CannotCalculate`, then `weewx.xtypes.get_scalar()` moves on to the
next object in the list. If no function can be found to do the evaluation, it raises
`weewx.UnknownType`.

The other functions work in a similar manner.


### Subtlety
One must be careful when sharing data structures across threads. Most of the time, this is not a
problem in WeeWX because the only thing that is shared is the configuration dictionary, and it is
treated as readonly.

However, because XType extensions can be used within the main thread (by `StdWXCalculate`), and the
reporting thread (by Cheetah, and the image generator), it is possible to end up sharing a data
structure. In particular, this can happen when you use a WeeWX service to initialize the extension.

For an example of this, see the class `wxxtypes.RainRater`. Its job is to calculate the rainfall
rate, by calculating the amount of rain received per unit time. It binds to loop events, and uses
it to update an internal cache of rain events. This happens in the main thread.

However, it is possible that it could get used in the reporting thread if, say, the Cheetah
template engine needs to evaluate `rainRate`, and it's not available in the database, nor in the
present record. In this case, the extension will attempt to calculate `rainRate`, which involves
scanning the internally cached list of rain events.

The danger is if a thread context switch happens in the middle of that scan. The cached data
structure could be in an unstable state. To guard agains this, `RainRater` locks the structure
before using or changing it.

This is a problem only because `RainRater` binds to something in the main thread. Most of the time,
this is not an issue.


## Other examples
It's worth taking a look in file `weewx/wxxtypes.py` for examples of XTypes used by WeeWX itself.

See the project [`weewx-xaggs`](https://github.com/tkeffer/weewx-xaggs) for examples of adding
new aggregation types, such as the historical highs and lows for a date.

The repository [weepwr](https://github.com/tkeffer/weepwr) contains a more complex example. This is
a device driver for the Brultech energy monitors. It registers many new types, and does this
dynamically.

------------------------

## Alternatives to the chosen design

### Alternative: register functions with weewx.conf

The chosen design registered new types through a Python API. An alternative is to declare the types
and function to be called in `weewx.conf`, in a manner similar to search list extensions. This
approach has the advantage that it requires a bit less programming and, most importantly, it leaves
a concise record of what extensions are being used in the configuration file `weewx.conf`.

However, it has a big disadvantage: it is difficult to predict what data a user might need to write
an extension. For example, what if we needed to know the station's altitude? WeeWX obtains this
from the hardware, with a fallback to the configuration file. Information like this would have to
be supplied by a standardized interface that would make all manner of information available to the
extension. This means the user might potentially have to know everything, so you end up with a
system where everything is connected to everything.

This is avoided by supplying a Python API that the type must adhere to. The new type can get any
information it wants, then register with the API.

### Alternative: register functions through the API
With this alternative, new types register with a Python API, but register functions, rather than
instances of classes.

The disadvantage is that this results in a proliferation of small functions. The chosen method has
the advantage that all the functions needed for a type can be held held under one roof.

### Alternative: declare types
In the chosen design, if an observation type is not known to a type extension, it raises an
exception of type `weewx.UnknownType`. An alternative that was considered is to require extensions
to declare what types they can handle in advance, much like a dictionary. This allows types to be
discoverable.

But, it has a disadvantage that all known types must be declared. That's not always practical. For
example, a type extension would be useful to calculate power from a running aggregate of energy
from an energy monitor. But, some monitors are capable of emitting 48+ channels, each of which
would have to be declared. Add polarized and absolute values, and we are looking at nearly 100
types!

Instead, we allow extensions to recognize what types they know about, possibly from a regular
expression of the observation type. If they don't recognize the type, they raise
`weewx.UnknownType`. Types do not have to be declared in advance.

------------------------

## Open issues

