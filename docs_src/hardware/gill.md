# Ultimeter {id=ultimeter_notes}

The Gill driver listens for data transmitted via a gill weatherstation over serial approximatley every second. 

The driver ignores gps corrected values but takes compass corrections into account. 

In order to interface with the driver, you need to set up the station with Gill MetSet and get your .mcf config file.

## Configuring with `weectl device` {id=ultimeter_configuration}

The Gill stations cannot be configured with the utility
[`weectl device`](../utilities/weectl-device.md).

## Station data {id=gill_data}

The following table shows which data are provided by the station hardware and which are calculated
by WeeWX.

Only the values you have enabled in gill metset are relevant.

<table class='station_data'>
    <caption>Gill station data</caption>
    <tbody class='code'>
    <tr class="first_row">
        <td style='width:200px'>Database Field</td>
        <td>Observation</td>
        <td>Loop</td>
        <td>Archive</td>
    </tr>
    <tr>
        <td class='first_col'>barometer<sup></sup></td>
        <td>barometer</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>pressure<sup></sup></td>
        <td>pressure</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>altimeter<sup></sup></td>
        <td>altimeter</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>gustdir<sup></sup></td>
        <td>gust_direction</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windDir<sup></sup></td>
        <td>wind_direction</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>outHumidity<sup></sup></td>
        <td>humiditiy_out</td>
        <td>H</td>
        <td></td>
    </tr>
        <tr>
        <td class='first_col'>cloudbase<sup></sup></td>
        <td>cloud_base</td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>rain<sup>1</sup></td>
        <td>rain</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>rainRate<sup>1</sup></td>
        <td>rain_rate</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windSpeed<sup></sup></td>
        <td>wind_speed</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>wind_gust<sup></sup></td>
        <td>wind_gust</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>outTemp<sup></sup></td>
        <td>temperature_out</td>
        <td>H</td>
        <td></td>
    </tr>
        <tr>
        <td class='first_col'>appTemp<sup></sup></td>
        <td>apparent_temperature</td>
        <td>S</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>heatindex<sup></sup></td>
        <td>heat_index</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>windchill<sup></sup></td>
        <td>wind_chill</td>
        <td>H</td>
        <td></td>
    </tr>
        <tr>
        <td class='first_col'>dewpoint<sup></sup></td>
        <td>dew_point</td>
        <td>H</td>
        <td></td>
    </tr>
    <tr>
        <td class='first_col'>supplyVoltage<sup></sup></td>
        <td>supply_voltage</td>
        <td>H</td>
        <td></td>
    </tr>
    </tbody>
</table>
<p class='station_data_key'>
    <sup>1</sup> The <span class='code'>rain</span> and
    <span class='code'>rainRate</span> are
    available only on stations with the optional rain sensor.
</p>


<p class='station_data_key'>
    <b>H</b> indicates data provided by <b>H</b>ardware<br/>
    <b>D</b> indicates data calculated by the <b>D</b>river<br/>
    <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
</p>

