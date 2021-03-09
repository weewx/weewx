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
Suppose you would like the maximum temperature for each day of the month. This can be specified as

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
01/01/2021 12:00:00 AM, 01/02/2021 12:00:00 AM, 45.6°F
01/02/2021 12:00:00 AM, 01/03/2021 12:00:00 AM, 46.2°F
01/03/2021 12:00:00 AM, 01/04/2021 12:00:00 AM, 49.5°F
  ...
```
Again, the first column is the start of the day, the second column the end of the day, the
final column the maximum temperature for the day.

## Optional unit conversion.
Just like scalars, the unit system of the resultant series can be changed. For example,

```
<pre>
$month.outTemp.series(aggregation_type='max', aggregation_interval='day').degree_C
</pre>
```

Results in

```
01/01/2021 12:00:00 AM, 01/02/2021 12:00:00 AM, 7.6°C
01/02/2021 12:00:00 AM, 01/03/2021 12:00:00 AM, 7.9°C
01/03/2021 12:00:00 AM, 01/04/2021 12:00:00 AM, 9.7°C
  ...
```

## Optional formatting
Similar to its scalar cousins, the output can be formatted. At this point, JSON formatting is
supported. CSV may be added in the future.

### JSON formatting
By adding the suffix `.json()` to the tag, the results will be formatted as JSON. This option has
two optional parameters, `order_by` and `time_series`:
```
.json(order_by=['row'|'column'], time_series=['start'|'stop'|'both'])
```
`order_by`: The returned JSON can either be organized by rows, or by columns. The default is `row`.

`time_series`: This option controls which series are emitted for time. Option `start` selects the
start of each aggregation interval. Option `stop` selects the end of each interval. Option `both`
causes both to be emitted.

## Example: series with aggregation, formatted as JSON
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


## Iteration
If you want finer control over formatting, you can iterate over the series and apply precise
formatting. Here's an example:

```
    #set ($start, $stop, $data) = $month.outTemp.series(aggregation_type='max', aggregation_interval='day') ## 1
    <table>
    #for ($time_vh, $data_vh) in $zip($start, $data)                       ## 2
    <tr>
    <td>$time_vh.format("%Y-%m-%d")</td><td>$data_vh.format("%.2f")</td>   ## 3
    </tr>
    #end for
    </table>
```
Here, we create a table. Each row is individually formatted. Comments below refer to the marked
lines:

1. Normally, if the tag `$month.outTemp.series(aggregation_type='max', aggregation_interval='day')`
occurs in a document, Cheetah will try and convert it into a string in order to embed the results
in the generated file. However, if it is not converted into a string, the expression actually
returns a 3-way tuple of `ValueHelpers`. The data in each `ValueHelper` is a series. The first one
holds the start times of the aggregation intervals, the second the stop times, and the third
the actual data. So, in this line, we store the three `ValueHelpers` separately as variables
`$start`, `$stop`, and `$data`, respectively. 

2. We will work only with the start times and data. We
[zip](https://docs.python.org/3/library/functions.html#zip) `$start` and `$data` together in order
to convert the "by column" ordering into "by row", then iterate over the results, assigning
   them to variables `$time_vh` and `$data_vh`. It's important to note, that both of these
   variables are garden-variety `ValueHelpers` and can be formatted accordingly.
   
3. In line 3, we apply some custom formatting. The time is formatted to show only the day. The
datum formatted to show two decimal points.
   
The final results look like:
```
2021-01-01	45.60°F
2021-01-02	46.20°F
2021-01-03	49.50°F
2021-01-04	46.90°F
2021-01-05	42.60°F
...
