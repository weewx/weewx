# Appendix

## Aggregation types {#aggregation_types}

<table>
    <caption>Aggregation types</caption>
    <tbody>
    <tr class="first_row">
        <td>Aggregation type</td>
        <td>Meaning</td>
    </tr>
    <tr>
        <td class="first_col code">avg</td>
        <td>The average value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">avg_ge(val)</td>
        <td>The number of days where the average value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">avg_le(val)</td>
        <td>The number of days where the average value is less than or equal to <em>val</em>. Aggregation period
            must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">count</td>
        <td>The number of non-null values in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">diff</td>
        <td>The difference between the last and first value in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">exists</td>
        <td>Returns <span class="code">True</span> if the observation type exists in the database.</td>
    </tr>
    <tr>
        <td class="first_col code">first</td>
        <td>The first non-null value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">firsttime</td>
        <td>The time of the first non-null value in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">gustdir</td>
        <td>The direction of the max gust in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">has_data</td>
        <td>Returns <span class="code">True</span> if the observation type exists in the database and is
            non-null.
        </td>
    </tr>
    <tr>
        <td class="first_col code">last</td>
        <td>The last non-null value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">lasttime</td>
        <td>The time of the last non-null value in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">max</td>
        <td>The maximum value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">maxmin</td>
        <td>The maximum daily minimum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">maxmintime</td>
        <td>The time of the maximum daily minimum.</td>
    </tr>
    <tr>
        <td class="first_col code">maxsum</td>
        <td>The maximum daily sum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">maxsumtime</td>
        <td>The time of the maximum daily sum.</td>
    </tr>
    <tr>
        <td class="first_col code">maxtime</td>
        <td>The time of the maximum value.</td>
    </tr>
    <tr>
        <td class="first_col code">max_ge(val)</td>
        <td>The number of days where the maximum value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">max_le(val)</td>
        <td>The number of days where the maximum value is less than or equal to <em>val</em>. Aggregation period
            must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">meanmax</td>
        <td>The average daily maximum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">meanmin</td>
        <td>The average daily minimum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">min</td>
        <td>The minimum value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">minmax</td>
        <td>The minimum daily maximum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">minmaxtime</td>
        <td>The time of the minimum daily maximum.</td>
    </tr>
    <tr>
        <td class="first_col code">minsum</td>
        <td>The minimum daily sum in the aggregation period. Aggregation period must be one day or longer.
        </td>
    </tr>
    <tr>
        <td class="first_col code">minsumtime</td>
        <td>The time of the minimum daily sum.</td>
    </tr>
    <tr>
        <td class="first_col code">mintime</td>
        <td>The time of the minimum value.</td>
    </tr>
    <tr>
        <td class="first_col code">min_ge(val)</td>
        <td>The number of days where the minimum value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">min_le(val)</td>
        <td>The number of days where the minimum value is less than or equal to <em>val</em>. Aggregation period
            must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">not_null</td>
        <td>
            Returns truthy if any value over the aggregation period is non-null.
        </td>
    </tr>
    <tr>
        <td class="first_col code">rms</td>
        <td>The root mean square value in the aggregation period.
        </td>
    </tr>
    <tr>
        <td class="first_col code">sum</td>
        <td>The sum of values in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">sum_ge(val)</td>
        <td>The number of days where the sum of value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">sum_le(val)</td>
        <td>The number of days where the sum of value is less than or equal to <em>val</em>. Aggregation period
            must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">tderiv</td>
        <td>
            The time derivative between the last and first value in the aggregation period. This is the
            difference in value divided by the difference in time.
        </td>
    </tr>
    <tr>
        <td class="first_col code">vecavg</td>
        <td>The vector average speed in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">vecdir</td>
        <td>The vector averaged direction during the aggregation period.
        </td>
    </tr>
    </tbody>
</table>

## Units {#units}

WeeWX offers three different *unit systems*:

<table>
    <caption>The standard unit systems used within WeeWX</caption>
    <tr class="first_row">
        <td>Name</td>
        <td>Encoded value</td>
        <td>Note</td>
    </tr>
    <tr>
        <td class="first_col code">US</td>
        <td>0x01</td>
        <td>U.S. Customary</td>
    </tr>
    <tr>
        <td class="first_col code">METRICWX</td>
        <td>0x11</td>
        <td>Metric, with rain related measurements in <span class="code">mm</span> and speeds in <span
            class="code">m/s</span>
        </td>
    </tr>
    <tr>
        <td class="first_col code">METRIC</td>
        <td>0x10</td>
        <td>Metric, with rain related measurements in <span class="code">cm</span> and speeds in <span
            class="code">km/hr</span>
        </td>
    </tr>
</table>

The table below lists all the unit groups, their members, which units
are options for the group, and what the defaults are for each standard
unit system.

<table>
    <caption>Unit groups, members and options</caption>
    <tbody class="code">
    <tr class="first_row">
        <td>Group</td>
        <td>Members</td>
        <td>Unit options</td>
        <td><span class="code">US</span></td>
        <td><span class="code">METRICWX</span></td>
        <td><span class="code">METRIC</span></td>
    </tr>
    <tr>
        <td class="first_col">group_altitude</td>
        <td>altitude<br/> cloudbase
        </td>
        <td>foot <br/> meter
        </td>
        <td>foot</td>
        <td>meter</td>
        <td>meter</td>
    </tr>
    <tr>
        <td class="first_col">group_amp</td>
        <td></td>
        <td>amp</td>
        <td>amp</td>
        <td>amp</td>
        <td>amp</td>
    </tr>
    <tr>
        <td class="first_col">group_angle</td>
        <td></td>
        <td>degree_angle<br/>radian</td>
        <td>degree_angle</td>
        <td>degree_angle</td>
        <td>degree_angle</td>
    </tr>
    <tr>
        <td class="first_col">group_boolean</td>
        <td></td>
        <td>boolean</td>
        <td>boolean</td>
        <td>boolean</td>
        <td>boolean</td>
    </tr>
    <tr>
        <td class="first_col">group_concentration</td>
        <td>no2<br/>pm1_0<br/>pm2_5<br/>pm10_0</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
    </tr>
    <tr>
        <td class="first_col">group_count</td>
        <td>leafWet1<br/>leafWet2<br/>lightning_disturber_count<br/>lightning_noise_count<br/>lightning_strike_count<br/></td>
        <td>count</td>
        <td>count</td>
        <td>count</td>
        <td>count</td>
    </tr>
    <tr>
        <td class="first_col">group_data</td>
        <td></td>
        <td>byte<br/> bit</td>
        <td>byte</td>
        <td>byte</td>
        <td>byte</td>
    </tr>
    <tr>
        <td class="first_col">group_db</td>
        <td>noise</td>
        <td>dB</td>
        <td>dB</td>
        <td>dB</td>
        <td>dB</td>
    </tr>
    <tr>
        <td class="first_col">group_delta_time</td>
        <td>daySunshineDur<br/>rainDur<br/>sunshineDurDoc</td>
        <td>second<br/> minute<br/>hour<br/>day<br/></td>
        <td>second</td>
        <td>second</td>
        <td>second</td>
    </tr>
    <tr>
        <td class="first_col">group_degree_day</td>
        <td>cooldeg<br/> heatdeg<br/> growdeg
        </td>
        <td>degree_F_day<br/> degree_C_day</td>
        <td>degree_F_day</td>
        <td>degree_C_day</td>
        <td>degree_C_day</td>
    </tr>
    <tr>
        <td class="first_col">group_direction</td>
        <td>gustdir <br/> vecdir <br/> windDir <br/> windGustDir</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
    </tr>
    <tr>
        <td class="first_col">group_distance</td>
        <td>windrun<br/>lightning_distance</td>
        <td>mile<br/>km</td>
        <td>mile</td>
        <td>km</td>
        <td>km</td>
    </tr>
    <tr>
        <td class="first_col">group_energy</td>
        <td></td>
        <td>kilowatt_hour<br/>mega_joule<br/>watt_hour<br/>watt_second</td>
        <td>watt_hour</td>
        <td>watt_hour</td>
        <td>watt_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_energy2</td>
        <td></td>
        <td>kilowatt_hour<br/>watt_hour<br/>watt_second</td>
        <td>watt_second</td>
        <td>watt_second</td>
        <td>watt_second</td>
    </tr>
    <tr>
        <td class="first_col">group_fraction</td>
        <td>co<br/>co2<br/>nh3<br/>o3<br/>pb<br/>so2</td>
        <td>ppm</td>
        <td>ppm</td>
        <td>ppm</td>
        <td>ppm</td>
    </tr>
    <tr>
        <td class="first_col">group_frequency</td>
        <td></td>
        <td>hertz</td>
        <td>hertz</td>
        <td>hertz</td>
        <td>hertz</td>
    </tr>
    <tr>
        <td class="first_col">group_illuminance</td>
        <td>illuminance</td>
        <td>lux</td>
        <td>lux</td>
        <td>lux</td>
        <td>lux</td>
    </tr>
    <tr>
        <td class="first_col">group_interval</td>
        <td>interval</td>
        <td>minute</td>
        <td>minute</td>
        <td>minute</td>
        <td>minute</td>
    </tr>
    <tr>
        <td class="first_col">group_length</td>
        <td></td>
        <td>inch<br/> cm
        </td>
        <td>inch</td>
        <td>cm</td>
        <td>cm</td>
    </tr>
    <tr>
        <td class="first_col">group_moisture</td>
        <td>soilMoist1 <br/> soilMoist2 <br/> soilMoist3 <br/> soilMoist4
        </td>
        <td>centibar</td>
        <td>centibar</td>
        <td>centibar</td>
        <td>centibar</td>
    </tr>
    <tr>
        <td class="first_col">group_percent</td>
        <td>
            cloudcover<br/>extraHumid1 <br/> extraHumid2 <br/> inHumidity <br/> outHumidity <br/>pop<br/>
            rxCheckPercent<br/>snowMoisture
        </td>
        <td>percent</td>
        <td>percent</td>
        <td>percent</td>
        <td>percent</td>
    </tr>
    <tr>
        <td class="first_col">group_power</td>
        <td></td>
        <td>kilowatt<br/>watt</td>
        <td>watt</td>
        <td>watt</td>
        <td>watt</td>
    </tr>
    <tr>
        <td class="first_col">group_pressure</td>
        <td>
            barometer <br/> altimeter <br/> pressure
        </td>
        <td>
            inHg<br/>mbar<br/>hPa<br/>kPa
        </td>
        <td>inHg</td>
        <td>mbar</td>
        <td>mbar</td>
    </tr>
    <tr>
        <td class="first_col">group_pressurerate</td>
        <td>
            barometerRate <br/> altimeterRate <br/> pressureRate
        </td>
        <td>
            inHg_per_hour <br/> mbar_per_hour <br/> hPa_per_hour <br/> kPa_per_hour
        </td>
        <td>inHg_per_hour</td>
        <td>mbar_per_hour</td>
        <td>mbar_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_radiation</td>
        <td>maxSolarRad <br/> radiation</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
    </tr>
    <tr>
        <td class="first_col">group_rain</td>
        <td>rain<br/>ET<br/>hail<br/>snowDepth<br/>snowRate</td>
        <td>inch <br/> cm <br/> mm
        </td>
        <td>inch</td>
        <td>mm</td>
        <td>cm</td>
    </tr>
    <tr>
        <td class="first_col">group_rainrate</td>
        <td>rainRate <br/> hailRate
        </td>
        <td>inch_per_hour <br/> cm_per_hour <br/> mm_per_hour
        </td>
        <td>inch_per_hour</td>
        <td>mm_per_hour</td>
        <td>cm_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_speed</td>
        <td>wind <br/> windGust <br/> windSpeed <br/> windgustvec <br/> windvec
        </td>
        <td>mile_per_hour <br/> km_per_hour <br/> knot <br/> meter_per_second <br/> beaufort
        </td>
        <td>mile_per_hour</td>
        <td>meter_per_second</td>
        <td>km_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_speed2</td>
        <td>rms <br/> vecavg
        </td>
        <td>mile_per_hour2 <br/> km_per_hour2 <br/> knot2 <br/> meter_per_second2
        </td>
        <td>mile_per_hour2</td>
        <td>meter_per_second2</td>
        <td>km_per_hour2</td>
    </tr>
    <tr>
        <td class="first_col">group_temperature</td>
        <td>appTemp <br/> dewpoint <br/> extraTemp1 <br/> extraTemp2 <br/> extraTemp3 <br/> heatindex <br/>
            heatingTemp <br/> humidex <br/> inTemp <br/> leafTemp1 <br/> leafTemp2 <br/> outTemp <br/> soilTemp1
            <br/> soilTemp2 <br/> soilTemp3 <br/> soilTemp4 <br/> windchill <br/> THSW
        </td>
        <td>degree_C<br/> degree_F <br/> degree_E<br/> degree_K
        </td>
        <td>degree_F</td>
        <td>degree_C</td>
        <td>degree_C</td>
    </tr>
    <tr>
        <td class="first_col">group_time</td>
        <td>dateTime</td>
        <td>unix_epoch <br/> dublin_jd
        </td>
        <td>unix_epoch</td>
        <td>unix_epoch</td>
        <td>unix_epoch</td>
    </tr>
    <tr>
        <td class="first_col">group_uv</td>
        <td>UV</td>
        <td>uv_index</td>
        <td>uv_index</td>
        <td>uv_index</td>
        <td>uv_index</td>
    </tr>
    <tr>
        <td class="first_col">group_volt</td>
        <td>consBatteryVoltage <br/> heatingVoltage <br/> referenceVoltage <br/> supplyVoltage
        </td>
        <td>volt</td>
        <td>volt</td>
        <td>volt</td>
        <td>volt</td>
    </tr>
    <tr>
        <td class="first_col">group_volume</td>
        <td></td>
        <td>cubic_foot<br/> gallon<br/> liter
        </td>
        <td>gallon</td>
        <td>liter</td>
        <td>liter</td>
    </tr>
    <tr>
        <td class="first_col">group_NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
    </tr>
    </tbody>
</table>

## Durations {#Durations}

Rather than give a value in seconds, many durations can be expressed using a shorthand notation.
For example, in a skin configuration file `skin.conf`, a value for `aggregate_interval` can be 
given as either

    aggregate_interval = 3600

or

    aggregate_interval = 1h

The same notation can be used in trends. For example:

    <p>Barometer trend over the last 2 hours: $trend(time_delta='2h').barometer</p>

Here is a summary of the notation:

| Example | Meaning            |
|---------|--------------------|
| `10800` | 3 hours            |
| `3h`    | 3 hours            |
| `1d`    | 1 day              |
| `2w`    | 2 weeks            |
| `1m`    | 1 month            |
| `1y`    | 1 year             |
| `hour`  | Synonym for `1h`   |
| `day`   | Synonym for `1d`   |
| `week`  | Synonym for `1w`   |
| `month` | Synonym for `1m`   |
| `year`  | Synonym for `1y`   |



## Class `ValueTuple` {#ValueTuple}

A value, along with the unit it is in, can be represented by a 3-way
tuple called a "value tuple". They are used throughout WeeWX. All
WeeWX routines can accept a simple unadorned 3-way tuple as a value
tuple, but they return the type `ValueTuple`. It is useful
because its contents can be accessed using named attributes. You can
think of it as a unit-aware value, useful for converting to and from
other units.

The following attributes, and their index, are present:

<table>
    <tr class="first_row">
        <td>Index</td>
        <td>Attribute</td>
        <td>Meaning</td>
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
body_temperature_vt = ValueTuple(98.6, "degree_F", group_temperature")
station_altitude_vt = ValueTuple(120.0, "meter", "group_altitude")
        
```

## Class `ValueHelper` {#ValueHelper}

Class `ValueHelper` contains all the information necessary to do
the proper formatting of a value, including a unit label.

### Instance attribute

#### ValueHelper.value_t

Returns the `ValueTuple` instance held internally.

### Instance methods

#### ValueHelper.__str__()

Formats the value as a string, including a unit label, and returns it.

#### ValueHelper.format(format_string=None, None_string=None, add_label=True, localize=True)

Format the value as a string, using various specified options, and
return it. Unless otherwise specified, a label is included.

Its parameters:

- `format_string` A string to be used for formatting. It must
include one, and only one, [format
specifier](https://docs.python.org/3/library/string.html#formatspec).

- `None_string` In the event of a value of Python `None`, this string
will be substituted. If `None`, then a default string from
`skin.conf` will be used.

- `add_label` If truthy, then an appropriate unit label will be
attached. Otherwise, no label is attached.

- `localize` If truthy, then the results will be localized. For
example, in some locales, a comma will be used as the decimal specifier.
