# WS23xx {id=ws23xx_notes}

The hardware interface is a serial port, but USB-serial converters
can be used with computers that have no serial port. Beware that
not every type of USB-serial converter will work. Converters based
on ATEN UC-232A chipset are known to work.

The station does not record wind gust or wind gust direction.

The hardware calculates windchill and dewpoint.

Sensors can be connected to the console with a wire.  If not wired,
the sensors will communicate via a wireless interface.  When
connected by wire, some sensor data are transmitted every 8
seconds.  With wireless, data are transmitted every 16 to 128
seconds, depending on wind speed and rain activity.

<table class='station_data'>
  <caption>WS23xx transmission periods</caption>
  <tbody>
    <tr class="first_row"><td>sensor</td><td>period</td></tr>
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

The station has 175 history records. That is just over 7 days of data with the
factory default history recording interval of 60 minutes, or about 14 hours with
a recording interval of 5 minutes.

When WeeWX starts up it will attempt to download all records from the console
since the last record in the archive database.


## Configuring with `weectl device` {id=ws23xx_configuration}

The WS23xx stations can be configured with the utility
[`weectl device`](../utilities/weectl-device.md).

!!! Note
    Make sure you stop `weewxd` before running `weectl device`.

### `--help` {id=ws23xx_help}

Invoking `weectl device` with the `--help` option

    weectl device --help

will produce something like this:

```
  WS23xx driver version 0.21
  Usage: weectl device [config_file] [options] [--debug] [--help]

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

  Mutating actions will request confirmation before proceeding.
```

### `--info` {id=ws23xx_info}

Display the station settings with the `--info` option.

    weectl device --info

This will result in something like:

```
  buzzer: 0
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
```


The line `history number of records` indicates how many records are in memory.
The line `history interval` indicates the number of minutes between records.

### `--set-interval` {id=ws23xx_set_interval}

WS23xx stations ship from the factory with an archive interval of 60 minutes
(3600 seconds). To change the interval to 5 minutes, do the following:

    weectl device --set-interval=5

!!! Warning
    Changing the interval will clear the station memory.

### `--history` {id=ws23xx_history}

WS23xx stations store records in a circular buffer &mdash; once the
buffer fills, the oldest records are replaced by newer records.
The console stores up to 175 records.

For example, to display the latest 30 records from the console memory:

    weectl device --history=30

### `--clear-memory` {id=ws23xx_clear_memory}

To clear the console memory:

    weectl device --clear-memory

## Station data {id=ws23xx_data}

The following table shows which data are provided by the station hardware
and which are calculated by WeeWX.

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

