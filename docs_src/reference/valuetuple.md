# Class ValueTuple

A value, along with the unit it is in, can be represented by a 3-way
tuple called a "value tuple". They are used throughout WeeWX. All
WeeWX routines can accept a simple unadorned 3-way tuple as a value
tuple, but they return the type `ValueTuple`. It is useful
because its contents can be accessed using named attributes. You can
think of it as a unit-aware value, useful for converting to and from
other units.

The following attributes, and their index, are present:

<table>
    <tr>
        <th>Index</th>
        <th>Attribute</th>
        <th>Meaning</th>
    </tr>
    <tr>
        <td>0</td>
        <td class="code">value</td>
        <td>The data value(s). Can be a series (e.g., <span class="code">[20.2, 23.2, ...]</span>) or a scalar
            (e.g., <span class="code">20.2</span>)
        </td>
    </tr>
    <tr>
        <td>1</td>
        <td class="code">unit</td>
        <td>The unit it is in (<span class="code">"degree_C"</span>)</td>
    </tr>
    <tr>
        <td>2</td>
        <td class="code">group</td>
        <td>The unit group (<span class="code">"group_temperature"</span>)</td>
    </tr>
</table>

It is valid to have a datum value of `None`.

It is also valid to have a unit type of `None` (meaning there is no
information about the unit the value is in). In this case, you won't be
able to convert it to another unit.

Here are some examples:

``` python
from weewx.units import ValueTuple

freezing_vt = ValueTuple(0.0, "degree_C", "group_temperature")
body_temperature_vt = ValueTuple(98.6, "degree_F", "group_temperature")
station_altitude_vt = ValueTuple(120.0, "meter", "group_altitude")
        
```
