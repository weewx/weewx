# Customizing units and unit groups

!!! Warning
    This is an area that is changing rapidly in WeeWX. Presently, new units
    and unit groups are added by manipulating the internal dictionaries in
    WeeWX (as described below). In the future, they may be specified in
    `weewx.conf`.

## Assigning a unit group

In the section [Customizing the database](database.md), we created a new
observation type, `electricity`, and added it to the database schema. Now we
would like to recognize that it is a member of the unit group
`group_energy` (which already exists), so it can enjoy the labels
and formats already provided for this group. This is done by extending
the dictionary `weewx.units.obs_group_dict`.

Add the following to our new services file `user/electricity.py`,
just after the last import statement:

``` python
import weewx
from weewx.engine import StdService

import weewx.units
weewx.units.obs_group_dict['electricity'] = 'group_energy'

class AddElectricity(StdService):

   # [...]
```

When our new service gets loaded by the WeeWX engine, these few lines
will get run. They tell WeeWX that our new observation type,
`electricity`, is part of the unit group `group_energy`.
Once the observation has been associated with a unit group, the unit
labels and other tag syntax will work for that observation. So, now a
tag like:

```
$month.electricity.sum
```

will return the total amount of electricity consumed for the month, in
Watt-hours.

## Creating a new unit group

That was an easy one, because there was already an existing group,
`group_energy`, that covered our new observation type. But, what
if we are measuring something entirely new, like force with time? There
is nothing in the existing system of units that covers things like
newtons or pounds. We will have to define these new units, as well as
the unit group they can belong to.

We assume we have a new observation type, `rocketForce`, which we
are measuring over time, for a service named `Rocket`, located in
` user/rocket.py`. We will create a new unit group,
`group_force`, and new units, `newton` and `pound`.
Our new observation, `rocketForce`, will belong to
`group_force`, and will be measured in units of `newton`
or `pound`.

To make this work, we need to add the following to
`user/rocket.py`.

1.  As before, we start by specifying what group our new observation
    type belongs to:

    ``` python
    import weewx.units
    weewx.units.obs_group_dict['rocketForce'] = 'group_force'
    ```

2.  Next, we specify what unit is used to measure force in the three
    standard unit systems used by weewx.

    ``` python
    weewx.units.USUnits['group_force'] = 'pound'
    weewx.units.MetricUnits['group_force'] = 'newton'
    weewx.units.MetricWXUnits['group_force'] = 'newton'
    ```

3.  Then we specify what formats and labels to use for `newton`
    and `pound`:

    ``` python
    weewx.units.default_unit_format_dict['newton'] = '%.1f'
    weewx.units.default_unit_format_dict['pound']  = '%.1f'

    weewx.units.default_unit_label_dict['newton'] = ' newton'
    weewx.units.default_unit_label_dict['pound']  = ' pound'
    ```

4.  Finally, we specify how to convert between them:

    ``` python
    weewx.units.conversionDict['newton'] = {'pound':  lambda x : x * 0.224809}
    weewx.units.conversionDict['pound']  = {'newton': lambda x : x * 4.44822}
    ```

Now, when the service `Rocket` gets loaded, these lines of code
will get executed, adding the necessary unit extensions to WeeWX.

## Using the new units

Now you've added a new type of units. How do you use it?

Pretty much like any other units. For example, to do a plot of the
month's electric consumption, totaled by day, add this section to the
`[[month_images]]` section of `skin.conf`:

``` ini
[[[monthelectric]]]
    [[[[electricity]]]]
        aggregate_type = sum
        aggregate_interval = 1d
        label = Electric consumption (daily total)
```

This will cause the generation of an image `monthelectric.png`,
showing a plot of each day's consumption for the past month.

If you wish to use the new type in the templates, it will be available
using the same syntax as any other type. Here are some other tags that
might be useful:

|  Tag| Meaning                                                                                                                |
|----|------------------------------------------------------------------------------------------------------------------------|
|  `$day.electricity.sum`| Total consumption since midnight                                                                                       |
 | `$year.electricity.sum`| Total consumption since the first of the year                                                                          |
|  `$year.electricity.max`| The most consumed during any archive period                                                                            |
|  `$year.electricity.maxsum`| The most consumed during a day                                                                                         |
|  `$year.electricity.maxsumtime`| The day it happened.                                                                                                   |
|  `$year.electricity.sum_ge((5000.0, 'kWh', 'group_energy'))`| The number of days of the year where<br/>more than 5.0 kWh of energy was consumed.<br/>The argument is a `ValueTuple`. |
