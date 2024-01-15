# WS28xx {id=ws28xx_notes}

WeeWX communicates with a USB transceiver, which communicates with the station
console, which in turn communicates with the sensors. The transceiver and
console must be paired and synchronized.

The sensors send data at different rates:

<table class='station_data'>
  <caption>WS28xx transmission periods</caption>
  <tbody>
    <tr><th>sensor</th><th>period</th></tr>
    <tr><td>Wind</td><td>17 seconds</td></tr>
    <tr><td>T/H</td><td>13 seconds</td></tr>
    <tr><td>Rain</td><td>19 seconds</td></tr>
    <tr><td>Pressure</td><td>15 seconds</td></tr>
  </tbody>
</table>

The wind and rain sensors transmit to the temperature/humidity device, then
the temperature/humidity device retransmits to the weather station console.
Pressure is measured by a sensor in the console.

The station has 1797 history records. That is just over 6 days of data with
an archive interval of 5 minutes.

When WeeWX starts up it will attempt to download all records from the console
since the last record in the archive database.

The WS28xx driver sets the station archive interval to 5 minutes.

The WS28xx driver does not support hardware archive record generation.

## Pairing {id=ws28xx_pairing}

The console and transceiver must be paired. Pairing ensures that your
transceiver is talking to your console, not your neighbor's console. Pairing
should only have to be done once, although you might have to pair again after
power cycling the console, for example after you replace the batteries.

There are two ways to pair the console and the transceiver:

* _The WeeWX way._ Be sure that WeeWX is not running. Run the configuration
  utility, press and hold the [v] button on the console until you see 'PC'
  in the display, then release the button. If the console pairs with the
  transceiver, 'PC' will go away within a second or two.
```
weectl device --pair

Pairing transceiver with console...
Press and hold the [v] key until "PC" appears (attempt 1 of 3)
Transceiver is paired to console
```

* _The HeavyWeather way._ Follow the pairing instructions that came with the
  station. You will have to run HeavyWeather on a Windows computer with the
  USB transceiver. After HeavyWeather indicates the devices are paired, put
  the USB transceiver in your WeeWX computer and start WeeWX. Do not power
  cycle the station console, or you will have to start over.

If the console does not pair, you will see messages in the log such as this:

    ws28xx: RFComm: message from console contains unknown device ID (id=165a resp=80 req=6)

Either approach to pairing may require multiple attempts.

## Synchronizing {id=ws28xx_synchronizing}

After pairing, the transceiver and console must be synchronized in order to
communicate. Synchronization will happen automatically at the top of each
hour, or you can force synchronization by pressing the [SET] button
momentarily. Do not press and hold the [SET] button &mdash; that modifies
the console alarms.

When the transceiver and console are synchronized, you will see lots of
`ws28xx: RFComm` messages in the log when `debug=1`. When the devices are
not synchronized, you will see messages like this about every 10 minutes:

    Nov  7 19:12:17 raspi weewx[2335]: ws28xx: MainThread: no contact with console

If you see this, or if you see an extended gap in the weather data in the
WeeWX plots, press momentarily the [SET] button, or wait until the top of
the hour.

When the transceiver has not received new data for awhile, you will see
messages like this in the log:

    Nov  7 19:12:17 raspi weewx[2335]: ws28xx: MainThread: no new weather data

If you see 'no new weather data' messages with the 'no contact with console'
messages, it simply means that the transceiver has not been able to
synchronize with the console. If you see only the 'no new weather data'
messages, then the sensors are not communicating with the console, or the
console may be defective.

## Alarms {id=ws28xx_alarms}

When an alarm goes off, communication with the transceiver stops. The WS28xx
driver clears all alarms in the station. It is better to create alarms in
WeeWX, and the WeeWX alarms can do much more than the console alarms anyway.

## Configuring with `weectl device` {id=ws28xx_configuration}

The WS28xx stations can be configured with the utility
[`weectl device`](../utilities/weectl-device.md).

!!! Note
    Make sure you stop `weewxd` before running `weectl device`.

### `--help` {id=ws28xx_help}

Invoking `weectl device` with the `--help` option

    weectl device --help

will produce something like this:

```
  WS28xx driver version 0.33
  Usage: weectl device [config_file] [options] [--debug] [--help]

  Configuration utility for weewx devices.

  Options:
  -h, --help           show this help message and exit
  --debug              display diagnostic information while running
  -y                   answer yes to every prompt
  --check-transceiver  check USB transceiver
  --pair               pair the USB transceiver with station console
  --info               display weather station configuration
  --set-interval=N     set logging interval to N minutes
  --current            get the current weather conditions
  --history=N          display N history records
  --history-since=N    display history records since N minutes ago
  --maxtries=MAXTRIES  maximum number of retries, 0 indicates no max

  Mutating actions will request confirmation before proceeding.
```

### `--pair`

The console and transceiver must be paired. This can be done either
by using this command, or by running the program HeavyWeather on a
Windows PC.

Be sure that WeeWX is not running. Run the command:

```
weectl device --pair

Pairing transceiver with console...
Press and hold the [v] key until "PC" appears (attempt 1 of 3)
Transceiver is paired to console
```

Press and hold the [v] button on the console until you see 'PC' in
the display, then release the button. If the console pairs with
the transceiver, 'PC' will go away within a second or two.

If the console does not pair, you will see messages in the log such as this:

    ws28xx: RFComm: message from console contains unknown device ID (id=165a resp=80 req=6)

Pairing may require multiple attempts.

After pairing, the transceiver and console must be synchronized in
order to communicate. This should happen automatically.

### `--info`

Display the station settings with the `--info` option.

    weectl device --info

This will result in something like:

```
  alarm_flags_other: 0
  alarm_flags_wind_dir: 0
  checksum_in: 1327
  checksum_out: 1327
  format_clock: 1
  format_pressure: 0
  format_rain: 1
  format_temperature: 0
  format_windspeed: 4
  history_interval: 1
  indoor_humidity_max: 70
  indoor_humidity_max_time: None
  indoor_humidity_min: 45
  indoor_humidity_min_time: None
  indoor_temp_max: 40.0
  indoor_temp_max_time: None
  indoor_temp_min: 0.0
  indoor_temp_min_time: None
  lcd_contrast: 4
  low_battery_flags: 0
  outdoor_humidity_max: 70
  outdoor_humidity_max_time: None
  outdoor_humidity_min: 45
  outdoor_humidity_min_time: None
  outdoor_temp_max: 40.0
  outdoor_temp_max_time: None
  outdoor_temp_min: 0.0
  outdoor_temp_min_time: None
  pressure_max: 1040.0
  pressure_max_time: None
  pressure_min: 960.0
  pressure_min_time: None
  rain_24h_max: 50.0
  rain_24h_max_time: None
  threshold_storm: 5
  threshold_weather: 3
  wind_gust_max: 12.874765625
  wind_gust_max_time: None
```

## Station data {id=ws28xx_data}

The following table shows which data are provided by the station
hardware and which are calculated by WeeWX.

<table class='station_data'>
  <caption>WS28xx station data</caption>
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
      <td class='first_col'>windGustDir</td>
      <td>wind_gust_dir</td>
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
      <td></td>
    </tr>
    <tr>
      <td class='first_col'>dewpoint</td>
      <td></td>
      <td>S</td>
      <td>S</td>
    </tr>
    <tr>
      <td class='first_col'>windchill</td>
      <td>windchill</td>
      <td>H</td>
      <td>H</td>
    </tr>
    <tr>
      <td class='first_col'>heatindex</td>
      <td>heatindex</td>
      <td>H</td>
      <td>H</td>
    </tr>
    <tr>
      <td class='first_col'>rxCheckPercent</td>
      <td>rssi</td>
      <td>H</td>
      <td></td>
    </tr>
    <tr>
      <td class='first_col'>windBatteryStatus</td>
      <td>wind_battery_status</td>
      <td>H</td>
      <td></td>
    </tr>
    <tr>
      <td class='first_col'>rainBatteryStatus</td>
      <td>rain_battery_status</td>
      <td>H</td>
      <td></td>
    </tr>
    <tr>
      <td class='first_col'>outTempBatteryStatus</td>
      <td>battery_status_out</td>
      <td>H</td>
      <td></td>
    </tr>
    <tr>
      <td class='first_col'>inTempBatteryStatus</td>
      <td>battery_status_in</td>
      <td>H</td>
      <td></td>
    </tr>
  </tbody>
</table>

<p class='station_data_key'>
  <b>H</b> indicates data provided by <b>H</b>ardware<br/>
  <b>D</b> indicates data calculated by the <b>D</b>river<br/>
  <b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
</p>
