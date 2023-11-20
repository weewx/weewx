# WS1 {id=ws1_notes}


The WS1 stations produce data every 1/2 second or so.

## Configuring with `weectl device` {id=ws1_configuration}

The WS1 stations cannot be configured with the utility
[`weectl device`](../utilities/weectl-device.md).


## Station data {id=ws1_data}

The following table shows which data are provided by the station hardware and which are calculated
by WeeWX.

<table class='station_data'>
    <caption>WS1 station data</caption>
    <tbody class='code'>
    <tr class="first_row">
        <td style='width:200px'>Database Field</td>
        <td>Observation</td>
        <td>Loop</td>
        <td>Archive</td>
    </tr>
    <tr>
        <td class='first_col'>barometer</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>pressure</td>
        <td>pressure</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>altimeter</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>inTemp</td>
        <td>temperature_in</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>outTemp</td>
        <td>temperature_out</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>inHumidity</td>
        <td>humidity_in</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>outHumidity</td>
        <td>humidity_out</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windSpeed</td>
        <td>wind_speed</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windDir</td>
        <td>wind_dir</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>rain</td>
        <td>rain</td>
        <td>D</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'></td>
        <td>rain_total</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>rainRate</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>dewpoint</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windchill</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>heatindex</td>
        <td></td>
        <td>S</td>
        <td></td>
    </tr>
    </tbody>
</table>

<p class='station_data_key'>
    <b>H</b> indicates data provided by <b>H</b>ardware<br/>
    <b>D</b> indicates data calculated by the <b>D</b>river<br/>
    <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
</p>
