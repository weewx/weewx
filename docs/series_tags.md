# Tags for series

## Overview
WeeWX Version 4.5 introduces limited support for tags that specifies _series_. The results
can be formatted either as JSON, or as a string. This document describes the syntax.

**NOTE:** This syntax is still experimental and subject to change! 

## Syntax
The tags used to specify a series is very similar to tags used for regular scalars, except they
include the keyword `series`:

```
$period($data_binding=binding_name, $optional_ago=delta).obstype.series[.optional_unit_conversion][.optional_formatting]
```

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
optional parameters `aggregation_type` and `aggregation_interval` to the `series` tag. Here's
an example:

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval=86400)
</pre>
```

where `86400` is the number of seconds in the day. As an alternative, you can use the string `day`:

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day')
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
Just like scalars, the unit system of the resultant series can be changed. For example,

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').degree_C
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
two types of formatting: one for strings, one for JSON. CSV may be added in the future.

### Optional string formatting
The format of the data can be changed with optional suffix `.format()`. Only the data is affected.
If you want to change the formatting of the start and stop times, you must use iteration. See
the section Iteration below.

Example:
```
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').format("%.2f")
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
two optional parameters, `order_by` and `time_series`. It can also pass on parameters to the 
`json.loads()` call.
```
.json(order_by=['row'|'column'], time_series=['start'|'stop'|'both'], **kwargs)
```
`order_by`: The returned JSON can either be organized by rows, or by columns. The default 
   is '`row`'.

`time_series`: This option controls which series are emitted for time. Option `start` selects the
   start of each aggregation interval. Option `stop` selects the end of each interval. Option `both`
   causes both to be emitted. Default is '`both`'.

`kwargs`: These are optional keyword arguments that are passed on to the Python `json.dumps()`
call. [See the documentation for `json.dumps`](https://docs.python.org/3/library/json.html#basic-usage).

#### Example: series with aggregation, formatted as JSON
Here's an example of the maximum temperature for all days of the current month, formatted in JSON

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').json
</pre>
```

This results in:
```
[[1614585600, 1614672000, 58.2], [1614672000, 1614758400, 55.8], [1614758400, 1614844800, 59.6], [1614844800, 1614931200, 57.8], [1614931200, 1615017600, 50.2], [1615017600, 1615104000, 42.0]]
```
The default is to order by row. If you want it by column:

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').json(order_by='column')
</pre>
```

Results:
```
[[1614585600, 1614672000, 1614758400, 1614844800, 1614931200, 1615017600], [1614672000, 1614758400, 1614844800, 1614931200, 1615017600, 1615104000], [58.2, 55.8, 59.6, 57.8, 50.2, 42.0]]
```

The above examples include both start and stop times of each interval. 
If you want only the start times, then use the optional argument `time_series`:

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').json(time_series='start')
</pre>
```

Results:
```
[[1614585600, 58.2], [1614672000, 55.8], [1614758400, 59.6], [1614844800, 57.8], [1614931200, 50.2], [1615017600, 42.0]]
```


## Working with wind vectors.
A series over types `windvec` and `windgustvec` return a series of _complex_ numbers. For example,

```
<pre>
$month.windvec.series(aggregation_type='max', aggregation_interval='day').json(indent=2)
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
$month.windvec.series(aggregation_type='max', aggregation_interval='day').polar.json(indent=2)
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
    #for ($start, $stop, $data) in $month.outTemp.series(aggregation_type='max', aggregation_interval='day') ## 1
      <tr>
        <td>$start.format("%Y-%m-%d")</td>      ## 2
        <td>$data.format("%.2f")</td>           ## 3
      </tr>
    #end for
    </table>
```
Here, we create a table. Each row is individually formatted. Comments below refer to the marked
lines:

1. Once evaluated, the tag `$month.outTemp.series(aggregation_type='max', aggregation_interval='day')`
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
