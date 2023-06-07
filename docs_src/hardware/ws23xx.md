# WS23xx


        <h1 id='ws23xx_notes'>WS23xx</h1>

        <p>The hardware interface is a serial port, but USB-serial converters
            can be used with computers that have no serial port. Beware that
            not every type of USB-serial converter will work. Converters based
            on ATEN UC-232A chipset are known to work.</p>

        <p>The station does not record wind gust or wind gust direction.</p>

        <p>The hardware calculates windchill and dewpoint.</p>

        <p>Sensors can be connected to the console with a wire.  If not wired,
            the sensors will communicate via a wireless interface.  When
            connected by wire, some sensor data are transmitted every 8
            seconds.  With wireless, data are transmitted every 16 to 128
            seconds, depending on wind speed and rain activity.
        </p>

        <table class='station_data'>
            <caption>WS23xx transmission periods</caption>
            <tbody>
                <tr><th>sensor</th><th>period</th></tr>
                <tr><td>Wind</td>
                    <td>32 seconds when wind > 22.36 mph (wireless)<br/>
                        128 seconds when wind > 22.36 mph (wireless)<br/>
                        10 minutes (wireless after 5 failed attempts)<br/>
                        8 seconds (wired)
                    </td></tr>
                <tr><td>Temperature</td><td>15 seconds</td></tr>
                <tr><td>Humidity</td><td>20 seconds</td></tr>
                <tr><td>Pressure</td><td>15 seconds</td></tr>
            </tbody>
        </table>

        <p>The station has 175 history records. That is just over 7 days of
            data with the factory default history recording interval of 60
            minutes, or about 14 hours with a recording interval of 5
            minutes.</p>

        <p>When WeeWX starts up it will attempt to
            download all records from the console since the last record in the
            archive database.</p>

        <h2 id="ws23xx_configuration">Configuring with <span class="code">wee_device</span></h2>

        <p class="note">
            Make sure you stop <span class="code">weewxd</span> before running
            <span class="code">wee_device</span>.
        </p>

        <h3 id="ws23xx_help">
            Action <span class="code">--help</span></h3>

        <p>Invoking <a href="../utilities/utilities.htm#wee_device_utility"><span class='code'>wee_device</span></a> with the
            <span class='code'>--help</span> option</p>

<pre class="tty cmd">wee_device /home/weewx/weewx.conf --help</pre>

        <p>will produce something like this:</p>

    <pre class="tty">
WS23xx driver version 0.21
Usage: wee_device [config_file] [options] [--debug] [--help]

Configuration utility for weewx devices.

Options:
  -h, --help         show this help message and exit
  --debug            display diagnostic information while running
  -y                 answer yes to every prompt
  --info             display weather station configuration
  --current          get the current weather conditions
  --history=N        display N history records
  --history-since=N  display history records since N minutes ago
  --clear-memory     clear station memory
  --set-time         set the station clock to the current time
  --set-interval=N   set the station archive interval to N minutes

Mutating actions will request confirmation before proceeding.</pre>

        <h3>Action <span class="code">--info</span></h3>

        <p>Display the station settings with the
            <span class='code'>--info</span> option.</p>
        <pre class="tty cmd">wee_device --info </pre>
        <p>This will result in something like:</p>
    <pre class='tty'>buzzer: 0
connection time till connect: 1.5
connection type: 15
dew point: 8.88
dew point max: 18.26
dew point max alarm: 20.0
dew point max alarm active: 0
dew point max alarm set: 0
dew point max when: 978565200.0
dew point min: -2.88
dew point min alarm: 0.0
dew point min alarm active: 0
dew point min alarm set: 0
dew point min when: 978757260.0
forecast: 0
history interval: 5.0
history last record pointer: 8.0
history last sample when: 1385564760.0
history number of records: 175.0
history time till sample: 5.0
icon alarm active: 0
in humidity: 48.0
...</pre>
        <p>
            The line <span class='code'>history number of records</span> indicates how many records are in memory. The
            line <span class='code'>history interval</span> indicates the number of minutes between records.
        </p>

        <h3>Action <span class="code">--set-interval</span></h3>

        <p>WS23xx stations ship from the factory with an archive interval of
            60 minutes (3600 seconds). To change the
            station's interval to 5 minutes, do the following:</p>

        <p class="tty cmd">wee_device --set-interval=5</p>

        <p class="warning"><strong>Warning!</strong><br/> Changing the archive
            interval will clear the station memory.
        </p>

        <h3>Action <span class="code">--history</span></h3>

        <p>WS23xx stations store records in a circular buffer &mdash; once the
            buffer fills, the oldest records are replaced by newer records.
            The console stores up to 175 records. </p>

        <p>For example, to display the latest 30 records from the console
            memory:</p>
        <pre class="tty cmd">wee_device --history=30</pre>

        <h3 id="vantage_clear_memory">Action <span class="code">--clear-memory</span></h3>

        <p>To clear the console memory:</p>
        <pre class="tty cmd">wee_device --clear-memory</pre>

        <h2 id="ws23xx_data">Station data</h2>

        <p>The following table shows which data are provided by the station
            hardware and which are calculated by WeeWX.
        </p>

        <table class='station_data'>
            <caption>WS23xx station data</caption>
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
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>pressure</td>
                <td>pressure</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>altimeter</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>inTemp</td>
                <td>temperature_in</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>outTemp</td>
                <td>temperature_out</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>inHumidity</td>
                <td>humidity_in</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>outHumidity</td>
                <td>humidity_out</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windSpeed</td>
                <td>wind_speed</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windDir</td>
                <td>wind_dir</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>rain</td>
                <td>rain</td>
                <td>D</td>
                <td>D</td>
            </tr>
            <tr>
                <td class='first_col'></td>
                <td>rain_total</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>rainRate</td>
                <td>rain_rate</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>dewpoint</td>
                <td>dewpoint</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windchill</td>
                <td>windchill</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>heatindex</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            </tbody>
        </table>

        <p class='station_data_key'>
            <b>H</b> indicates data provided by <b>H</b>ardware<br/>
            <b>D</b> indicates data calculated by the <b>D</b>river<br/>
            <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
        </p>

