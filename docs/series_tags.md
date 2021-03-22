# Tags for series

## Overview
WeeWX Version 4.5 introduces limited support for tags that specifies _series_. The results
can be formatted either as JSON, or as a string. This document describes the syntax.

**NOTE:** This syntax is still experimental and subject to change! 

## Syntax
The tags used to specify a series is very similar to tags used for regular scalars, except they
include the keyword `series`:

```
$period.obstype.series[.optional_unit_conversion][.optional_formatting]
```

The tags `.optional_unit_conversion` and `.optional_formatting` are explained below.

## Series with no aggregation
Here's an example of asking for a series with the temperature for all records in the day. We will
display it with an HTML `<pre>` tag so that the embedded newlines work.

```
<pre>
$day.outTemp.series
</pre>
```

This would result in something like this:
```
12:00:00 AM, 12:05:00 AM, 43.8°F
12:05:00 AM, 12:10:00 AM, 43.8°F
12:10:00 AM, 12:15:00 AM, 42.7°F
12:15:00 AM, 12:20:00 AM, 41.3°F
          ...
```
The first column is the start time of each point in the series, the second column is the stop time.
From this example, we can see that the data have a 5 minute archive period.

## Series with aggregation
Suppose you would like the maximum temperature for each day of the month. This is an _aggregation_
(maximum temperature, in this case), over a time period (one day). This can be specified with
optional parameters `aggregate_type` and `aggregate_interval` to the `series` tag. Here's
an example:

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval=86400)
</pre>
```

where `86400` is the number of seconds in the day. As an alternative, you can use the string `day`:

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day')
</pre>
```

Either way, the results would be:

```
03/01/2021 12:00:00 AM, 03/02/2021 12:00:00 AM, 58.2°F
03/02/2021 12:00:00 AM, 03/03/2021 12:00:00 AM, 55.8°F
03/03/2021 12:00:00 AM, 03/04/2021 12:00:00 AM, 59.6°F
03/04/2021 12:00:00 AM, 03/05/2021 12:00:00 AM, 57.8°F
03/05/2021 12:00:00 AM, 03/06/2021 12:00:00 AM, 50.2°F
03/06/2021 12:00:00 AM, 03/07/2021 12:00:00 AM, 42.0°F
  ...
```

The first column is the start of the aggregation period, the second the end of the period, and the
final column the maximum temperature for aggregation period. In this example, because the
aggregation period is one day, the start and stop fall on daily boundaries.

## Optional unit conversion.
Just like scalars, the unit system of the resultant series can be changed. Only the data
part, not the time part, is converted. For example,

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').degree_C
</pre>
```

Results in

```
03/01/2021 12:00:00 AM, 03/02/2021 12:00:00 AM, 14.6°C
03/02/2021 12:00:00 AM, 03/03/2021 12:00:00 AM, 13.2°C
03/03/2021 12:00:00 AM, 03/04/2021 12:00:00 AM, 15.3°C
03/04/2021 12:00:00 AM, 03/05/2021 12:00:00 AM, 14.3°C
03/05/2021 12:00:00 AM, 03/06/2021 12:00:00 AM, 10.1°C
03/06/2021 12:00:00 AM, 03/07/2021 12:00:00 AM, 5.6°C
  ...
```

## Optional formatting
Similar to its scalar cousins, the output can be formatted. At this point, there are
two types of formatting: one for strings, and one for JSON. CSV may be added in the future.

### Optional string formatting
The format of the data can be changed with optional suffix `.format()`. Only the data is affected.
If you want to change the formatting of the start and stop times, you must use iteration. See
the section Iteration below.

Example:
```
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').format("%.2f")
```
yields something like
```
03/01/2021 12:00:00 AM, 03/02/2021 12:00:00 AM, 58.20°F
03/02/2021 12:00:00 AM, 03/03/2021 12:00:00 AM, 55.80°F
03/03/2021 12:00:00 AM, 03/04/2021 12:00:00 AM, 59.60°F
03/04/2021 12:00:00 AM, 03/05/2021 12:00:00 AM, 57.80°F
03/05/2021 12:00:00 AM, 03/06/2021 12:00:00 AM, 50.20°F
03/06/2021 12:00:00 AM, 03/07/2021 12:00:00 AM, 42.00°F
  ...
```

### Optional JSON formatting
By adding the suffix `.json()` to the tag, the results will be formatted as JSON. This option has
several optional parameters, It can also pass on parameters to the `json.loads()` call.
```
.json(ndigits=None,
      order_by=['row'|'column'], 
      time_series=['start'|'stop'|'both'], 
      time_unit=['unix_epoch'|'unix_epoch_ms'|'unix_epoch_ns', 
      **kwargs)
```
`ndigits`: The number of decimal digits to include in the results. Default is `None`, which means
   include all digits.

`order_by`: The returned JSON can either be organized by rows, or by columns. The default 
   is '`row`'.

`time_series`: This option controls which series are emitted for time. Option `start` selects the
   start of each aggregation interval. Option `stop` selects the end of each interval. Option `both`
   causes both to be emitted. Default is '`both`'.

`time_unit`: The unit to be used for the time domain. Choices are `unix_epoch`, `unix_epoch_ms`,
   or `unix_epoch_ns`. Or, I suppose, `dublin_jd` if you're into it.

`kwargs`: These are optional keyword arguments that are passed on to the Python `json.dumps()`
   call. [See the documentation for `json.dumps`](https://docs.python.org/3/library/json.html#basic-usage).

#### Example: series with aggregation, formatted as JSON
Here's an example of the maximum temperature for all days of the current month, formatted in JSON

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').json
</pre>
```

This results in:
```
[[1614585600, 1614672000, 58.2], [1614672000, 1614758400, 55.8], [1614758400, 1614844800, 59.6], [1614844800, 1614931200, 57.8], [1614931200, 1615017600, 50.2], [1615017600, 1615104000, 42.0]]
```
The default is to order by row. If you want it by column:

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').json(order_by='column')
</pre>
```

Results:
```
[[1614585600, 1614672000, 1614758400, 1614844800, 1614931200, 1615017600], [1614672000, 1614758400, 1614844800, 1614931200, 1615017600, 1615104000], [58.2, 55.8, 59.6, 57.8, 50.2, 42.0]]
```

#### Example: series with aggregation, formatted as JSON, selected time series
The above examples include both start and stop times of each interval. 
If you want only the start times, then use the optional argument `time_series`:

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').json(time_series='start')
</pre>
```

Results:
```
[[1614585600, 58.2], [1614672000, 55.8], [1614758400, 59.6], [1614844800, 57.8], [1614931200, 50.2], [1615017600, 42.0]]
```

#### Example: series with aggregation, formatted as JSON, optional time unit
Suppose you want the previous example, except that you want the unix epoch time to be in
miliseconds. To do this, add optional argument `time_unit`:

```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').json(time_series='start'. time_unit='unix_epoch_ms')
</pre>
```

Results:
```
[[1614585600000.0, 58.2], [1614672000000.0, 55.8], [1614758400000.0, 59.6], [1614844800000.0, 57.8], [1614931200000.0, 50.2], [1615017600000.0, 42.0]]
```

#### Example: series with aggregation, formatted as JSON, with unit conversion and rounding
Suppose you want the results in °C, rather than °F. Then including a `.degree_C` between the
`.series` and `.json` tags will give the desired results:
```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').degree_C.json(time_series='start')
</pre>
```
```
[[1614585600, 14.555555555555555], [1614672000, 13.222222222222221], [1614758400, 15.333333333333334], [1614844800, 14.333333333333334], [1614931200, 10.111111111111112], [1615017600, 5.555555555555555]]
```
Note that the unit conversion resulted in many extra decimal digits. It's an accurate representation
of the internal data, but you may not want to transmit that much data over the network. You can
limit the number of decimal digits by using optional parameter `ndigits`:
```
<pre>
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').degree_C.json(ndigits=2, time_series='start')
</pre>
```
This gives a much more compact representation:
```
[[1614585600, 14.56], [1614672000, 13.22], [1614758400, 15.33], [1614844800, 14.33], [1614931200, 10.11], [1615017600, 5.56]]
```


## Working with wind vectors.
A series over types `windvec` and `windgustvec` return a series of _complex_ numbers. For example,

```
<pre>
$month.windvec.series(aggregate_type='max', aggregate_interval='day').json(indent=2)
</pre>
```
yields
```
[
  [
    1614585600,
    1614672000,
    [
      -6.0,
      -7.347880794884119e-16
    ]
  ],
  [
    1614672000,
    1614758400,
    [
      -9.0,
      -1.102182119232618e-15
    ]
  ],
  [
    1614758400,
    1614844800,
    [
      -1.1480502970952693,
      -2.77163859753386
    ]
  ],
   ...
]
```

There are a number of conversion operators that can yield various parts of the complex results. 

| Operator     | Effect                                                     |
|--------------|------------------------------------------------------------|
| `.x`         | Just the x-components                                      |
| `.y`         | Just the y-components                                      |
| `.magnitude` | Just the total (absolute) magnitude                        |
| `.direction` | Just the compass direction (in degrees 0°=N, 90°=E, etc.)  |
| `.polar`     | As polar coordinates (`magnitude`, `direction`)            |

Note that direction uses _compass directions_.

Here's an example. Other operators are similar. Suppose we would like the output in _polar_
notation, that is a 2-way tuple of (`magnitude`, `direction`), where `direction` is the compass
direction. 

```
<pre>
$month.windvec.series(aggregate_type='max', aggregate_interval='day').polar.json(indent=2)
</pre>
```
yields
```
[
  [
    1614585600,
    1614672000,
    [
      6.0,
      270.0
    ]
  ],
  [
    1614672000,
    1614758400,
    [
      9.0,
      270.0
    ]
  ],
  [
    1614758400,
    1614844800,
    [
      2.9999999999999996,
      202.5
    ]
  ],
  ...
```

## Iteration
If you want finer control over formatting, you can iterate over the series and apply precise
formatting. Here's an example:

```
    <table>
      <tr>
        <td>Start date</td>
        <td>Max temperature</td>
      </tr>
    #for ($start, $stop, $data) in $month.outTemp.series(aggregate_type='max', aggregate_interval='day') ## 1
      <tr>
        <td>$start.format("%Y-%m-%d")</td>      ## 2
        <td>$data.format("%.2f")</td>           ## 3
      </tr>
    #end for
    </table>
```
Here, we create a table. Each row is individually formatted. Comments below refer to the marked
lines:

1. Once evaluated, the tag `$month.outTemp.series(aggregate_type='max', aggregate_interval='day')`
   returns a `SeriesHelper`. Normally, Cheetah would try to convert this into a string, in order to
   embed the results in a document. However, in this case we are _iterating_ over the tag. Iteration
   returns a 3-way tuple `start`, `stop`, and `data`, each an instance of `ValueHelper`, each of
   which can be formatted like any other `ValueHelper`.

2. We will work only with the start times and data. On line 2, we apply a custom formatting for the
   start times, so that only the date (no time) is shown.

3. Similarly, we apply some custom formatting for the datum to show two decimal points.
   
The final results look like:
```
 <table>
   <tr>
     <td>Start date</td>
     <td>Max temperature</td>
   </tr>
   <tr>
     <td>2021-03-01</td>
     <td>58.20&#176;F</td>
   </tr>
   <tr>
     <td>2021-03-02</td>
     <td>55.80&#176;F</td>
   </tr>
   <tr>
     <td>2021-03-03</td>
     <td>59.60&#176;F</td>
   </tr>
   <tr>
     <td>2021-03-04</td>
     <td>57.80&#176;F</td>
   </tr>
   <tr>
     <td>2021-03-05</td>
     <td>50.20&#176;F</td>
   </tr>
   <tr>
     <td>2021-03-06</td>
     <td>42.00&#176;F</td>
   </tr>
 </table>
``` 
Unfortunately, this Markdown document cannot show rendered HTML but, once rendered, it would look
something like:
```
Start date	Max temperature
2021-03-01	58.20°F
2021-03-02	55.80°F
2021-03-03	59.60°F
2021-03-04	57.80°F
2021-03-05	50.20°F
2021-03-06	42.00°F
```

## Working with JSON
### Helper function `$jsonize()`
We saw some examples above where the results of a tag can be formatted as JSON. However, there are
cases when you need to combine several queries together to get the results you desire. Here's a
common example: you wish to create a JSON structure with the minimum and maximum temperature for
each day in a month.

Creating separate series of minimums and maximums is easy enough:

```
$month.outTemp.series(aggregate_type='min', aggregate_interval='day').json
$month.outTemp.series(aggregate_type='max', aggregate_interval='day').json
```

but how do you combine them into a single structure? Here's one way to do it:

```
 #set $min = month.outTemp.series(aggregate_type='min', aggregate_interval='day')
 #set $max = $month.outTemp.series(aggregate_type='max', aggregate_interval='day')
 <pre>
 $jsonize($zip($min.start.raw, $min.data.raw, $max.data.raw))
 </pre>
```

This uses the Python function [`zip()`](https://docs.python.org/3/library/functions.html#zip) to
interleave the start times, minimums, and maximums together. This results in a list of 3-way tuples
(time, minimum, maximum). The WeeWX helper function `$jsonize()` is then used to convert this to
JSON. The result looks something like this:

```
[[1609488000, 38.9, 45.6], [1609574400, 41.6, 46.2], [1609660800, 40.7, 49.5], ... ]
```

### Helper function `$rnd()`
Suppose you want the results in degrees Celsius, instead of Fahrenheit? Then add the tag 
`.degree_C`:

```
$jsonize($zip($min.start.raw, $min.data.degree_C.raw, $max.data.degree_C.raw))
```
with results:
```
[[1609488000, 3.8333333333333326, 7.555555555555555], [1609574400, 5.333333333333334, 7.88888888888889], [1609660800, 4.833333333333335, 9.722222222222221], ... ]
```

Unfortunately, the unit conversion resulted in a lot of decimal digits, which we may not want to
transmit over the wire to a Javascript plotting library. We can round the results by using the
WeeWX helper function `$rnd()`:

```
$jsonize($zip($min.start.raw, $rnd($min.data.degree_C.raw, 2), $rnd($max.data.degree_C.raw, 2)))
```

The second argument (`2`, in this example), says to round the results to two decimal digits. 
This results in

```
[[1609488000, 3.83, 7.56], [1609574400, 5.33, 7.89], [1609660800, 4.83, 9.72], ... ]
```
