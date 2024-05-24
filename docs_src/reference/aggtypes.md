# Aggregation types

<table>
    <caption>Aggregation types</caption>
    <tbody>
    <tr>
        <th>Aggregation type</th>
        <th>Meaning</th>
    </tr>
    <tr>
        <td class="first_col code">avg</td>
        <td>The average value in the aggregation period.</td>
    </tr>
    <tr>
        <td class="first_col code">avg_ge(val)</td>
        <td>The number of days when the average value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">avg_le(val)</td>
        <td>The number of days when the average value is less than or equal to <em>val</em>. Aggregation period
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
        <td>Returns <span class="code">True</span> if the observation type 
            exists (either in the database or as an xtype) and has at least one
            non-null value in the aggregation period.
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
        <td>The number of days when the maximum value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">max_le(val)</td>
        <td>The number of days when the maximum value is less than or equal to <em>val</em>. Aggregation period
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
        <td>The number of days when the minimum value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">min_le(val)</td>
        <td>The number of days when the minimum value is less than or equal to <em>val</em>. Aggregation period
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
        <td>The number of days when the sum of value is greater than or equal to <em>val</em>. Aggregation
            period must be one day or longer. The argument <span class="code">val</span> is a
            <a href="#ValueTuple"><span class="code">ValueTuple</span></a>.
        </td>
    </tr>
    <tr>
        <td class="first_col code">sum_le(val)</td>
        <td>The number of days when the sum of value is less than or equal to <em>val</em>. Aggregation period
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
