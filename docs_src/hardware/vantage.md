

        <h1 id='vantage_notes'>Vantage</h1>

        <p>The Davis Vantage stations include a variety of models and
            configurations.  The WeeWX driver
            can communicate with a console or envoy using serial, USB,
            or TCP/IP interface.</p>

        <h2 id="vantage_configuration">Configuring with <span class="code">wee_device</span></h2>

        <p class="note">
            Make sure you stop <span class="code">weewxd</span> before running
            <span class="code">wee_device</span>.
        </p>

        <h3 id="vantage_help">
            Action <span class="code">--help</span></h3>

        <p>Invoking <a href="../utilities/utilities.htm#wee_device_utility"><span class='code'>wee_device</span></a> with the
            <span class='code'>--help</span> option</p>

<pre class="tty cmd">wee_device /home/weewx/weewx.conf --help</pre>

        <p>will produce something like this:</p>

    <pre class="tty">
Using configuration file /home/weewx/weewx.conf
Using driver weewx.drivers.vantage.
Using Vantage driver version 3.6.2 (weewx.drivers.vantage)
Usage: wee_device --help
       wee_device --info [config_file]
       wee_device --current [config_file]
       wee_device --clear-memory [config_file] [-y]
       wee_device --set-interval=MINUTES [config_file] [-y]
       wee_device --set-latitude=DEGREE [config_file] [-y]
       wee_device --set-longitude=DEGREE [config_file] [-y]
       wee_device --set-altitude=FEET [config_file] [-y]
       wee_device --set-barometer=inHg [config_file] [-y]
       wee_device --set-wind-cup=CODE [config_file] [-y]
       wee_device --set-bucket=CODE [config_file] [-y]
       wee_device --set-rain-year-start=MM [config_file] [-y]
       wee_device --set-offset=VARIABLE,OFFSET [config_file] [-y]
       wee_device --set-transmitter-type=CHANNEL,TYPE,TEMP,HUM,REPEATER_ID [config_file] [-y]
       wee_device --set-retransmit=[OFF|ON|ON,CHANNEL] [config_file] [-y]
       wee_device --set-temperature-logging=[LAST|AVERAGE] [config_file] [-y]
       wee_device --set-time [config_file] [-y]
       wee_device --set-dst=[AUTO|ON|OFF] [config_file] [-y]
       wee_device --set-tz-code=TZCODE [config_file] [-y]
       wee_device --set-tz-offset=HHMM [config_file] [-y]
       wee_device --set-lamp=[ON|OFF] [config_file]
       wee_device --dump [--batch-size=BATCH_SIZE] [config_file] [-y]
       wee_device --logger-summary=FILE [config_file] [-y]
       wee_device [--start | --stop] [config_file]

Configures the Davis Vantage weather station.

Options:
  -h, --help            show this help message and exit
  --debug               display diagnostic information while running
  -y                    answer yes to every prompt
  --info                To print configuration, reception, and barometer
                        calibration information about your weather station.
  --current             To print current LOOP information.
  --clear-memory        To clear the memory of your weather station.
  --set-interval=MINUTES
                        Sets the archive interval to the specified number of
                        minutes. Valid values are 1, 5, 10, 15, 30, 60, or
                        120.
  --set-latitude=DEGREE
                        Sets the latitude of the station to the specified
                        number of tenth degree.
  --set-longitude=DEGREE
                        Sets the longitude of the station to the specified
                        number of tenth degree.
  --set-altitude=FEET   Sets the altitude of the station to the specified
                        number of feet.
  --set-barometer=inHg  Sets the barometer reading of the station to a known
                        correct value in inches of mercury. Specify 0 (zero)
                        to have the console pick a sensible value.
  --set-wind-cup=CODE   Set the type of wind cup. Specify '0' for small size;
                        '1' for large size
  --set-bucket=CODE     Set the type of rain bucket. Specify '0' for 0.01
                        inches; '1' for 0.2 mm; '2' for 0.1 mm
  --set-rain-year-start=MM
                        Set the rain year start (1=Jan, 2=Feb, etc.).
  --set-offset=VARIABLE,OFFSET
                        Set the onboard offset for VARIABLE inTemp, outTemp,
                        extraTemp[1-7], inHumid, outHumid, extraHumid[1-7],
                        soilTemp[1-4], leafTemp[1-4], windDir) to OFFSET
                        (Fahrenheit, %, degrees)
  --set-transmitter-type=CHANNEL,TYPE,TEMP,HUM,REPEATER_ID
                        Set the transmitter type for CHANNEL (1-8), TYPE
                        (0=iss, 1=temp, 2=hum, 3=temp_hum, 4=wind, 5=rain,
                        6=leaf, 7=soil, 8=leaf_soil, 9=sensorlink, 10=none),
                        as extra TEMP station and extra HUM station (both 1-7,
                        if applicable), REPEATER_ID (A-H, or 0=OFF)
  --set-retransmit=OFF|ON|ON,CHANNEL
                        Turn console retransmit function 'ON' or 'OFF'.
  --set-temperature-logging=LAST|AVERAGE
                        Set console temperature logging to either 'LAST' or
                        'AVERAGE'.
  --set-time            Set the onboard clock to the current time.
  --set-dst=AUTO|ON|OFF
                        Set DST to 'ON', 'OFF', or 'AUTO'
  --set-tz-code=TZCODE  Set timezone code to TZCODE. See your Vantage manual
                        for valid codes.
  --set-tz-offset=HHMM  Set timezone offset to HHMM. E.g. '-0800' for U.S.
                        Pacific Time.
  --set-lamp=ON|OFF     Turn the console lamp 'ON' or 'OFF'.
  --dump                Dump all data to the archive. NB: This may result in
                        many duplicate primary key errors.
  --batch-size=BATCH_SIZE
                        Use with option --dump. Pages are read off the console
                        in batches of BATCH_SIZE. A BATCH_SIZE of zero means
                        dump all data first, then put it in the database. This
                        can improve performance in high-latency environments,
                        but requires sufficient memory to hold all station
                        data. Default is 1 (one).
  --logger-summary=FILE
                        Save diagnostic summary to FILE (for debugging the
                        logger).
  --start               Start the logger.
  --stop                Stop the logger.

Be sure to stop weewx first before using. Mutating actions will request
confirmation before proceeding.
</pre>

        <h3 id="vantage_info">
            Action <span class="code">--info</span></h3>

        <p>Use the <span class="code">--info</span> option to display the current EEPROM settings: </p>
        <pre class="tty cmd">wee_device --info</pre>
        <p>This will result in something like:</p>
    <pre class="tty">Using configuration file /home/weewx/weewx.conf
Using driver weewx.drivers.vantage.
Using Vantage driver version 3.6.2 (weewx.drivers.vantage)
Querying...
Davis Vantage EEPROM settings:

    CONSOLE TYPE:                   Vantage Pro2

    CONSOLE FIRMWARE:
      Date:                         Dec 11 2012
      Version:                      3.12

    CONSOLE SETTINGS:
      <span class="highlight">Archive interval:             300 (seconds)</span>
      <span class="highlight">Altitude:                     700 (foot)</span>
      <span class="highlight">Wind cup type:                large</span>
      <span class="highlight">Rain bucket type:             0.01 inches</span>
      <span class="highlight">Rain year start:              10</span>
      Onboard time:                 2023-05-01 07:35:25

    CONSOLE DISPLAY UNITS:
      Barometer:                    mbar
      Temperature:                  degree_F
      Rain:                         inch
      Wind:                         mile_per_hour

    CONSOLE STATION INFO:
      <span class="highlight">Latitude (onboard):           +46.0</span>
      <span class="highlight">Longitude (onboard):          -121.6</span>
      <span class="highlight">Use manual or auto DST?       AUTO</span>
      <span class="highlight">DST setting:                  N/A</span>
      <span class="highlight">Use GMT offset or zone code?  ZONE_CODE</span>
      <span class="highlight">Time zone code:               4</span>
      <span class="highlight">GMT offset:                   N/A</span>
      <span class="highlight">Temperature logging:          AVERAGE</span>

    TRANSMITTERS:
      Channel   Receive     Retransmit  Repeater  Type
         <span class="highlight">1      inactive    N           NONE      iss</span>
         <span class="highlight">2      inactive    N           NONE      (N/A)</span>
         <span class="highlight">3      active      N           NONE      temp (as extra temperature 1)</span>
         <span class="highlight">4      active      N           8         temp_hum (as extra temperature 4 and extra humidity 1)</span>
         <span class="highlight">5      inactive    N           NONE      (N/A)</span>
         <span class="highlight">6      inactive    Y           NONE      (N/A)</span>
         <span class="highlight">7      inactive    N           NONE      (N/A)</span>
         <span class="highlight">8      inactive    N           NONE      (N/A)</span>

    RECEPTION STATS:
      Total packets received:       2895
      Total packets missed:         82
      Number of resynchronizations: 0
      Longest good stretch:         330
      Number of CRC errors:         134

    BAROMETER CALIBRATION DATA:
      <span class="highlight">Current barometer reading:    29.821 inHg</span>
      <span class="highlight">Altitude:                     700 feet</span>
      Dew point:                    43 F
      Virtual temperature:          56 F
      Humidity correction factor:   1.7
      Correction ratio:             1.026
      <span class="highlight">Correction constant:          +0.036 inHg</span>
      Gain:                         0.000
      Offset:                       -47.000

    OFFSETS:
      <span class="highlight">Wind direction:               +0 deg</span>
      <span class="highlight">Inside Temperature:           +0.0 F</span>
      <span class="highlight">Inside Humidity:              +0 %</span>
      <span class="highlight">Outside Temperature:          +0.0 F</span>
      <span class="highlight">Outside Humidity:             +0 %</span>
      <span class="highlight">Extra Temperature 1:          +0.0 F</span>
      <span class="highlight">Extra Temperature 4:          +0.0 F</span>
      <span class="highlight">Extra Humidity 1:             +0.0 F</span>
</pre>
        <p>The console version number is available only on consoles with firmware dates after about 2006.</p>

        <p><span class="highlight">Highlighted</span> values can be modified using the
            various <a href="../utilities/utilities.htm#wee_device_utility"><span class='code'>wee_device</span></a>
            commands below.</p>

        <h3 id="vantage_current">
            Action <span class="code">--current</span></h3>
        <p>This command will print a single LOOP packet.</p>

        <h3 id="vantage_clear_console_memory">
            Action <span class="code">--clear-memory</span></h3>
        <p>This command will clear the logger memory after asking for confirmation.</p>

        <h3 id="vantage_archive_interval">
            Action <span class="code">--set-interval</span></h3>

        <p>Use this command to change the archive interval of the internal logger. Valid intervals are 1, 5, 10,
            15, 30, 60, or 120 minutes. However, if you are ftp&#39;ing lots of files to a server, setting it to
            one minute may not give enough time to have them all uploaded before the next archive record is due. If this
            is the case, you should pick a longer archive interval, or trim the number of files you
            are using.</p>

        <p>An archive interval of five minutes works well for the Vantage stations. Because of the large
            amount of onboard memory they carry, going to a larger interval does not have any real advantages. </p>

        <p>Example: to change the archive interval to 10 minutes:</p>
        <pre class="tty cmd">wee_device --set-interval=10</pre>

        <h3>Action <span class="code">--set-altitude</span></h3>

        <p>Use this command to set the console's stored altitude. The altitude must be in <em>feet</em>. Example:</p>
        <pre class="tty cmd">wee_device --set-altitude=700</pre>

        <h3>Action <span class="code">--set-barometer</span></h3>

        <p>Use this command to calibrate the barometer in your Vantage weather station. To use it, you must have a known
            correct barometer reading <em>for your altitude</em>. In practice, you will either have to move your console
            to a known-correct station (perhaps a nearby airport) and perform the calibration there, or reduce the
            barometer reading to your altitude. Otherwise, specify the value zero and the station will pick a sensible
            value.</p>

        <h3 id="vantage_rain_bucket_type">
            Action <span class="code">--set-bucket</span></h3>

        <p>Normally, this is set by Davis, but if you have replaced your bucket with a different kind, you might want to
            reconfigure. For example, to change to a 0.1 mm bucket (bucket code &quot;2&quot;), use the following:</p>
        <pre class="tty cmd">wee_device --set-bucket=2</pre>

        <h3>Action <span class="code">--set-rain-year-start</span></h3>

        <p>The Davis Vantage series allows the start of the rain year to be something other than 1 January. For example,
            to set it to 1 October:</p>
        <pre class="tty cmd">wee_device --set-rain-year-start=10</pre>

        <h3 id="vantage_setting_offsets">
            Action <span class="code">--set-offset</span></h3>

        <p>The Davis instruments can correct sensor errors by adding an <em>offset</em> to their emitted values. This is
            particularly useful for Southern Hemisphere users. Davis fits the wind vane to the Integrated Sensor Suite
            (ISS) in a position optimized for Northern Hemisphere users, who face the solar panel to the south. Users
            south of the equator must orient the ISS's solar panel to the north to get maximal insolation, resulting in
            a 180&deg; error in the wind direction. The solution is to add a 180&deg; offset correction. You can do this
            with the following command:</p>

        <pre class="tty cmd">wee_device --set-offset=windDir,180</pre>

        <h3 id="vantage_configuring_additional_sensors">
            Action <span class="code">--set-transmitter-type</span></h3>

        <p>If you have additional sensors and/or repeaters for your Vantage station, you can configure them using your console.
           However, if you have a
           <a href="https://www.davisinstruments.com/product/wireless-weather-envoy/">Davis Weather Envoy receiver</a>,
           it will not have a console! As an alternative,
           <span class="code">wee_device</span> can do this using the command <span class="code">--set-transmitter-type</span>.
        </p>

        <p>For example, to add an extra temperature sensor to channel 3 and no repeater is used, do the following:</p>
        <pre class="tty cmd">wee_device --set-transmitter-type=3,1,2</pre>
        <p>This says to turn on channel 3, set its type to 1 ("Temperature only"), without repeater use and it will show up in the database
            as <span class="code">extraTemp2</span>.</p>
        <p class="note">If you omit the repeater id, repeater id will be: 'no repeater'.</p>

        <p>Here's another example, this time for a combined temperature /
            humidity sensor retransmitted via repeater A:</p>
        <pre class="tty cmd">wee_device --set-transmitter-type=5,3,2,4,a</pre>
        <p>This will add the combined sensor to channel 5, set its type to 3 ("Temperature and humidity"), via Repeater A and it will
            show up in the database as <span class="code">extraTemp2</span> and <span class="code">extraHumid4</span>.
        </p>

        <p>The <span class="code">--help</span> option will give you the code for each sensor type and repeater id.</p>
        <p>If you have to use repeaters with your Vantage Pro2 station, please take a look at
            <a href="http://www.davisnet.com/product_documents/weather/app_notes/AN_25-data-repeater-network.pdf">
                Installing Repeater Networks for Vantage Pro2</a> how to setup.</p>

        <p class="warning">You can only use channels not actively used for retransmission. The command checks for this and will not
            accept channel numbers actively used for retransmission.</p>

        <h3 id="vantage_retransmit">
            Action <span class="code">--set-retransmit</span></h3>

        <p>Use this command to tell your console whether or not to act as a retransmitter.</p>
        <p>Example: Tell your console to turn retransmission 'ON' and let the software select the first available channel:</p>
        <pre class="tty cmd">wee_device --set-retransmit=on</pre>

        <p>Another example: Tell your console to turn retransmission 'OFF':</p>
        <pre class="tty cmd">wee_device --set-retransmit=off</pre>

        <p>Last example: Tell your console to turn retransmission 'ON' at channel 4:</p>
        <pre class="tty cmd">wee_device --set-retransmit=on,4</pre>
        <p class="warning">You only can use channels not actively used for reception. The command checks for this and will not accept channel numbers actively used for reception of senor stations.</p>

        <h3>Action <span class="code">--set-dst</span></h3>

        <p>Use the command to tell your console whether or not daylight savings time is in effect, or to have it set
            automatically based on the time zone.</p>

        <h3 id="vantage_time_zone">
            Action <span class="code">--set-tz-code</span></h3>

        <p>This command can be used to change the time zone. Consult the
            Vantage manual for the code that corresponds to
            your time zone.</p>

        <p class="warning">You can set either the time zone code <em>or</em>
            the time zone offset, but not both. </p>

        <p>For example, to set the time zone code to Central European Time
            (code 20):</p>
        <pre class="tty cmd">wee_device --set-tz-code=20</pre>

        <h3>Action <span class="code">--set-tz-offset</span></h3>

        <p>If you live in an odd time zone that is perhaps not covered by the
            "canned" Davis time zones, you can set the
            offset from UTC using this command.</p>

        <p class="warning">You can set either the time zone code <em>or</em>
            the time zone offset, but not both. </p>

        <p>For example, to set the time zone offset for Newfoundland Standard
            Time (UTC-03:30), use the following:</p>
        <pre class="tty cmd">wee_device --set-tz-offset=-0330</pre>

        <h3>Action <span class="code">--set-lamp</span></h3>

        <p>Use this command to turn the console lamp on or off.</p>

        <h3 id="vantage_dumping_the_logger_memory">
            Action <span class="code">--dump</span></h3>

        <p>
            Generally, WeeWX downloads only new archive records from the on-board logger in the Vantage. However,
            occasionally the memory in the Vantage will get corrupted, making this impossible. See the section <em><a
            href="https://github.com/weewx/weewx/wiki/Troubleshooting-the-Davis-Vantage-station#weewx-generates-html-pages-but-it-does-not-update-them">WeeWX
            generates HTML pages, but it does not update them</a></em> in the Wiki. The fix involves clearing the memory
            but, unfortunately, this means you may lose any data which might have accumulated in the logger memory, but
            not yet downloaded. By using the <span class="code">--dump</span> command before clearing the memory, you
            might be able to save these data. Stop WeeWX first, then
        </p>
        <pre class="tty cmd">wee_device --dump</pre>
        <p>This will dump all data archived in the Vantage memory directly to the database, without regard to whether or
            not they have been seen before. Because the command dumps <em>all</em> data, it may result in many duplicate
            primary key errors. These can be ignored.</p>

        <h3>Action <span class="code">--logger-summary FILE</span></h3>
        <p>This command is useful for debugging the console logger. It will scan the logger memory, recording the
            timestamp in each page and index slot to the file <span class="code">FILE</span>.</p>
        <p>Example:</p>
        <pre class="tty cmd">wee_device --logger-summary=/var/tmp/summary.txt</pre>

        <h3>Action <span class="code">--start</span></h3>

        <p>Use this command to start the logger. There are occasions when an
            out-of-the-box logger needs this command.</p>

        <h3>Action <span class="code">--stop</span></h3>

        <p>Use this command to stop the logger. I can't think of a good reason
            why you would need to do this, but the
            command is included for completeness.</p>

        <h2 id="vantage_data">Station data</h2>

        <p>The following table shows which data are provided by the station
            hardware and which are calculated by WeeWX.
        </p>

        <table class='station_data'>
            <caption>Vantage station data</caption>
            <tbody class='code'>
            <tr class="first_row">
                <td style='width:200px'>Database Field</td>
                <td>Observation</td>
                <td>Loop</td>
                <td>Archive</td>
            </tr>
            <tr>
                <td class='first_col'>barometer</td>
                <td>barometer</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>pressure</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>altimeter</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>inTemp</td>
                <td>inTemp</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>outTemp</td>
                <td>outTemp</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>inHumidity</td>
                <td>inHumidity</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>outHumidity</td>
                <td>outHumidity</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windSpeed</td>
                <td>windSpeed</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windDir</td>
                <td>windDir</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windGust</td>
                <td>windGust</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>windGustDir</td>
                <td>windGustDir</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>rain</td>
                <td>rain</td>
                <td>D</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'></td>
                <td>monthRain</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>rainRate</td>
                <td>rainRate</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>dewpoint</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>windchill</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>heatindex</td>
                <td></td>
                <td>S</td>
                <td>S</td>
            </tr>
            <tr>
                <td class='first_col'>radiation</td>
                <td>radiation</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>UV</td>
                <td>UV</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp1</td>
                <td>extraTemp1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp2</td>
                <td>extraTemp2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp3</td>
                <td>extraTemp3</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp4</td>
                <td>extraTemp4</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp5</td>
                <td>extraTemp5</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp6</td>
                <td>extraTemp6</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraTemp7</td>
                <td>extraTemp7</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>soilTemp1</td>
                <td>soilTemp1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilTemp2</td>
                <td>soilTemp2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilTemp3</td>
                <td>soilTemp3</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilTemp4</td>
                <td>soilTemp4</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafTemp1</td>
                <td>leafTemp1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafTemp2</td>
                <td>leafTemp2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafTemp3</td>
                <td>leafTemp3</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafTemp4</td>
                <td>leafTemp4</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid1</td>
                <td>extraHumid1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid2</td>
                <td>extraHumid2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid3</td>
                <td>extraHumid3</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid4</td>
                <td>extraHumid4</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid5</td>
                <td>extraHumid5</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid6</td>
                <td>extraHumid6</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>extraHumid7</td>
                <td>extraHumid7</td>
                <td>H</td>
                <td></td>
            </tr>
            <tr>
                <td class='first_col'>soilMoist1</td>
                <td>soilMoist1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilMoist2</td>
                <td>soilMoist2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilMoist3</td>
                <td>soilMoist3</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>soilMoist4</td>
                <td>soilMoist4</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafWet1</td>
                <td>leafWet1</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafWet2</td>
                <td>leafWet2</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafWet3</td>
                <td>leafWet3</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>leafWet4</td>
                <td>leafWet4</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>txBatteryStatus</td>
                <td>txBatteryStatus</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'>consBatteryVoltage</td>
                <td>consBatteryVoltage</td>
                <td>H</td>
                <td>H</td>
            </tr>
            <tr>
                <td class='first_col'></td>
                <td>wind_samples</td>
                <td></td>
                <td>H</td>
            </tr>
            </tbody>
        </table>

        <p class='station_data_key'>
            <b>H</b> indicates data provided by <b>H</b>ardware<br/>
            <b>D</b> indicates data calculated by the <b>D</b>river<br/>
            <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
        </p>
