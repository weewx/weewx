

        <h1 id='ultimeter_notes'>Ultimeter</h1>
        <p>The Ultimeter driver operates the Ultimeter in Data Logger Mode,
            which results in sensor readings every 1/2 second or so.</p>

        <p>The Ultimeter driver ignores the maximum, minimum, and average
            values recorded by the station.</p>

        <h2 id='ultimeter_configuration'>Configuring with <span class="code">wee_device</span></h2>

        <p>The <a href="../utilities/utilities.htm#wee_device_utility"><span class='code'>wee_device</span></a> utility
            cannot be used to configure Ultimeter stations.</p>

        <h2 id="ultimeter_data">Station data</h2>

        <p>The following table shows which data are provided by the station
            hardware and which are calculated by WeeWX.
        </p>

        <table class='station_data'>
            <caption>Ultimeter station data</caption>
            <tbody class='code'>
            <tr class="first_row">
                <td style='width:200px'>Database Field</td>
                <td>Observation</td>
                <td>Loop</td>
                <td>Archive</td>
            </tr>
            <tr>
                <td class='first_col'>barometer<sup>2</sup></td>
                <td>barometer</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>pressure<sup>2</sup></td>
                <td></td>
                <td>S</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>altimeter<sup>2</sup></td>
                <td></td>
                <td>S</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>inTemp<sup>2</sup></td>
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
                <td class='first_col'>inHumidity<sup>2</sup></td>
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
                <td class='first_col'>rain<sup>1</sup></td>
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
                <td class='first_col'>rainRate<sup>1</sup></td>
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
            <sup>1</sup> The <span class='code'>rain</span> and
            <span class='code'>rainRate</span> are
            available only on stations with the optional rain sensor.
        </p>

        <p class='station_data_key'>
            <sup>2</sup> Pressure, inside temperature, and inside humidity
            data are not available on all types of Ultimeter stations.
        </p>

        <p class='station_data_key'>
            <b>H</b> indicates data provided by <b>H</b>ardware<br/>
            <b>D</b> indicates data calculated by the <b>D</b>river<br/>
            <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
        </p>

