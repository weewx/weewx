# FineOffset

        <h1 id='fousb_notes'>FineOffsetUSB</h1>

        <p>The station clock can only be set manually via buttons on the console, or (if the station supports it) by
            WWVB radio. The FineOffsetUSB driver ignores the station clock since it cannot be trusted.</p>

        <p>The station reads data from the sensors every 48 seconds. The 30xx stations read UV data every 60
            seconds.</p>

        <p>The 10xx and 20xx stations can save up to 4080 historical readings. That is about 85 days of data with the
            default recording interval of 30 minutes, or about 14 days with a recording interval of 5 minutes. The 30xx
            stations can save up to 3264 historical readings.</p>

        <p>When WeeWX starts up it will attempt to
            download all records from the console since
            the last record in the archive database.</p>

        <h2 id="polling_mode_and_the_polling_interval">Polling mode and
            interval</h2>

        <p>When reading 'live' data, WeeWX can read
            as fast as possible, or at a user-defined
            period. This is controlled by the option
            <span class='code'>polling_mode</span> in
            <span class="code">weewx.conf</span>.</p>
        <table class='indent'>
            <caption>Polling modes for Fine Offset stations</caption>
            <tr class="first_row">
                <td style="width:15%">Mode</td>
                <td style="width:15%">Configuration</td>
                <td>Notes</td>
            </tr>
            <tr>
                <td class="first_col">ADAPTIVE</td>
                <td>
                <pre class='tty' style='margin:0'>[FineOffsetUSB]
    polling_mode = ADAPTIVE</pre>
                </td>
                <td>
                    <p>In this mode, WeeWX reads data from the station as often as possible,
                        but at intervals that avoid communication between the console and the sensors. Nominally this
                        results in reading data every 48 seconds.</p>
                </td>
            </tr>
            <tr>
                <td class="first_col">PERIODIC</td>
                <td>
                <pre class='tty' style='margin:0'>[FineOffsetUSB]
    polling_mode = PERIODIC
    polling_interval = 60</pre>
                </td>
                <td>
                    <p>In this mode, WeeWX reads data from the station every <span
                            class='code'>polling_interval</span> seconds.</p>

                    <p>The console reads the sensors every 48 seconds (60 seconds for UV), so setting the <span
                            class='code'>polling_interval</span> to a value less than 48 will result in duplicate
                        readings. </p>
                </td>
            </tr>
        </table>


        <h2 id="fousb_data_format">Data format</h2>

        <p>The 10xx/20xx consoles have a data format that is different from
            the 30xx consoles.  All of the consoles recognize wind, rain,
            temperature, and humidity from the same instrument clusters.
            However, some instrument clusters also include a luminosity sensor.
            Only the 30xx consoles recognize the luminosity and UV output
            from these sensors.  As a consequence, the 30xx consoles also have
            a different data format.
        </p>
        <p>Since WeeWX cannot reliably determine
            the data format by communicating with the station, the
            <span class='code'>data_format</span> configuration option
            indicates the station type.  Possible values are
            <span class='code'>1080</span> and <span class='code'>3080</span>.
            Use <span class='code'>1080</span> for the 10xx and 20xx consoles.
            The default value is <span class='code'>1080</span>.
        </p>
        <p>For example, this would indicate that the station is a 30xx
            console:</p>
        <pre class='tty'>[FineOffsetUSB]
    ...
    data_format = 3080
</pre>

        <h2 id="fousb_configuration">Configuring with <span class="code">wee_device</span></h2>

        <p class="note">
            Make sure you stop <span class="code">weewxd</span> before running
            <span class="code">wee_device</span>.
        </p>

        <h3 id="fousb_help">
            Action <span class="code">--help</span></h3>

        <p>Invoking <a href="../utilities/utilities.htm#wee_device_utility"><span class='code'>wee_device</span></a> with the
            <span class='code'>--help</span> option</p>

<pre class="tty cmd">wee_device /home/weewx/weewx.conf --help</pre>

        <p>will produce something like this:</p>

    <pre class="tty">
FineOffsetUSB driver version 1.7
Usage: wee_device [config_file] [options] [--debug] [--help]

Configuration utility for weewx devices.

Options:
-h, --help           show this help message and exit
--debug              display diagnostic information while running
-y                   answer yes to every prompt
--info               display weather station configuration
--current            get the current weather conditions
--history=N          display N records
--history-since=N    display records since N minutes ago
--clear-memory       clear station memory
--set-time           set station clock to computer time
--set-interval=N     set logging interval to N minutes
--live               display live readings from the station
--logged             display logged readings from the station
--fixed-block        display the contents of the fixed block
--check-usb          test the quality of the USB connection
--check-fixed-block  monitor the contents of the fixed block
--format=FORMAT      format for output, one of raw, table, or dict

Mutating actions will request confirmation before proceeding.</pre>

        <h3>Action <span class="code">--info</span></h3>

        <p>Display the station settings with the
            <span class='code'>--info</span> option.</p>
        <pre class="tty cmd">wee_device --info</pre>
        <p>This will result in something like:</p>
    <pre class='tty'>Fine Offset station settings:
                    local time: 2013.02.11 18:34:28 CET
                  polling_mode: ADAPTIVE

                  abs_pressure: 933.3
                   current_pos: 592
                  data_changed: 0
                    <span class="highlight">data_count: 22</span>
                     date_time: 2007-01-01 22:49
                 hum_in_offset: 18722
                hum_out_offset: 257
                            id: None
                 lux_wm2_coeff: 0
                       magic_1: 0x55
                       magic_2: 0xaa
                         model: None
                     rain_coef: None
                   <span class="highlight">read_period: 30</span>
                  <span class="highlight">rel_pressure: 1014.8</span>
                temp_in_offset: 1792
               temp_out_offset: 0
                      timezone: 0
                    unknown_01: 0
                    unknown_18: 0
                       version: 255
                     wind_coef: None
                     wind_mult: 0</pre>

        <p><span class="highlight">Highlighted</span> values can be modified.
        </p>

        <h3>Action <span class="code">--set-interval</span></h3>

        <p>Set the archive interval.  Fine Offset stations ship from the
            factory with an archive interval (read_period) of 30 minutes (1800
            seconds). To change the station's interval to 5 minutes, do the
            following:</p>

        <p class="tty cmd">wee_device --set-interval=5</p>

        <h3>Action <span class="code">--history</span></h3>

        <p>Fine Offset stations store records in a circular buffer &mdash; once the buffer fills, the oldest records are
            replaced by newer records. The 1080 and 2080 consoles store up to 4080 records. The 3080 consoles store up
            to 3264 records. The <span class='code'>data_count</span> indicates how many records are in memory. The
            <span class='code'>read_period</span> indicates the number of minutes between records. <span class='code'>wee_device</span>
            can display these records in space-delimited, raw bytes, or dictionary format.</p>

        <p>For example, to display the most recent 30 records from the console memory:</p>
        <pre class="tty cmd">wee_device --history=30</pre>

        <h3 id="fo_clear_console_memory">
            Action <span class="code">--clear-memory</span></h3>
        <p>To clear the console memory:</p>
        <pre class="tty cmd">wee_device --clear-memory</pre>

        <h3>Action <span class="code">--check-usb</span></h3>

        <p>This command can test the quality of the USB connection between the computer and console. Poor quality USB
            cables, under-powered USB hubs, and other devices on the bus can interfere with communication.</p>

        <p>To test the quality of the USB connection to the console:</p>
        <pre class="tty cmd">wee_device --check-usb</pre>
        <p>Let the utility run for at least a few minutes, or possibly an hour or two. It is not unusual to see a few
            bad reads in an hour, but if you see many bad reads within a few minutes, consider replacing the USB cable,
            USB hub, or removing other devices from the bus.</p>

        <h2 id="fousb_data">Station data</h2>

        <p>The following table shows which data are provided by the station
            hardware and which are calculated by WeeWX.
        </p>

        <table class='station_data'>
            <caption>Fine Offset station data</caption>
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
                <td class='first_col'>windGust</td>
                <td>wind_gust</td>
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
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>dewpoint</td>
                <td>dewpoint</td>
                <td>H</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>windchill</td>
                <td>windchill</td>
                <td>H</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>heatindex</td>
                <td>heatindex</td>
                <td>H</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>radiation<sup>1</sup></td>
                <td>radiation</td>
                <td>D</td>
                <td>D</td>
            </tr>
            <tr>
                <td class='first_col'>luminosity<sup>1</sup></td>
                <td>luminosity</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>rxCheckPercent</td>
                <td>signal</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>outTempBatteryStatus</td>
                <td>battery</td>
                <td>H</td>
                <td></td>
            </tr>
            </tbody>
        </table>
        <p class='station_data_key'>
            <sup>1</sup> The <span class='code'>radiation</span> data are available
            only from 30xx stations.
            These stations include a luminosity sensor, from which the radiation is
            approximated.
        </p>

        <p class='station_data_key'>
            <b>H</b> indicates data provided by <b>H</b>ardware<br/>
            <b>D</b> indicates data calculated by the <b>D</b>river<br/>
            <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
        </p>
