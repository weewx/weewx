# AcuRite {id=acurite_notes}

According to Acurite, the wind speed updates every 18 seconds.
The wind direction updates every 30 seconds. Other sensors update
every 60 seconds.

In fact, because of the message structure and the data logging
design, these are the actual update frequencies:

<table>
<caption>AcuRite transmission periods</caption>
<tbody>
<tr class='first_row'><td>sensor</td><td>period</td></tr>
<tr><td>Wind speed</td><td>18 seconds</td></tr>
<tr><td>Outdoor temperature, outdoor humidity</td><td>36 seconds</td></tr>
<tr><td>Wind direction, rain total</td><td>36 seconds</td></tr>
<tr><td>Indoor temperature, pressure</td><td>60 seconds</td></tr>
<tr><td>Indoor humidity</td><td>12 minutes (only when in USB mode 3)</td></tr>
</tbody>
</table>

The station emits partial packets, which may confuse some online
services.

The AcuRite stations do not record wind gusts.

Some consoles have a small internal logger.  Data in the logger
are erased when power is removed from the station.

The console has a sensor for inside humidity, but the values from
that sensor are available only by reading from the console logger.
Due to instability of the console firmware, the
WeeWX driver does not read the console
logger.

## USB Mode {id=acurite_usb_mode}

Some AcuRite consoles have a setting called "USB Mode" that controls
how data are saved and communicated:

<table id='usbmode' class='station_data'>
<caption>AcuRite USB mode</caption>
<tbody>
<tr>
<th>Mode</th>
<th>Show data<br/>in display</th>
<th>Store data<br/>in logger</th>
<th>Send data<br/>over USB</th>
</tr>
<tr><td>1</td><td>yes</td><td>yes</td><td></td></tr>
<tr><td>2</td><td>yes</td><td></td><td></td></tr>
<tr><td>3</td><td>yes</td><td>yes</td><td>yes</td></tr>
<tr><td>4</td><td>yes</td><td></td><td>yes</td></tr>
</tbody>
</table>

If the AcuRite console has multiple USB modes, it must be set to
USB mode 3 or 4 in order to work with the WeeWX driver.

Communication via USB is disabled in modes 1 and 2. Mode 4 is more reliable
than mode 3; mode 3 enables logging of data, mode 4 does not. When the
console is logging it frequently causes USB communication
problems.

The default mode is 2, so after a power failure one must use the
console controls to change the mode before
WeeWX can resume data collection.

The 01025, 01035, 01036, 01525, and 02032 consoles have a USB mode setting.

The 02064 and 01536 consoles do not have a mode setting; these
consoles are always in USB mode 4.

## Configuring with `weectl device` {id=acurite_configuration}

The [`weectl device`](../utilities/weectl-device.md) utility cannot be used to
configure AcuRite stations.

## Station data {id=acurite_data}

The following table shows which data are provided by the station
hardware and which are calculated by WeeWX.

<table class='station_data'>
<caption>AcuRite station data</caption>
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
<td></td>
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
<tr>
<td class='first_col'>rxCheckPercent</td>
<td>rssi</td>
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
Each packet contains a subset of all possible readings. For example, one type
of packet contains <span class='code'>windSpeed</span>,
<span class='code'>windDir</span> and <span class='code'>rain</span>.
A different type of packet contains <span class='code'>windSpeed</span>,
<span class='code'>outTemp</span> and <span class='code'>outHumidity</span>.
</p>

<p class='station_data_key'>
<b>H</b> indicates data provided by <b>H</b>ardware<br/>
<b>D</b> indicates data calculated by the <b>D</b>river<br/>
<b>S</b> indicates data calculated by the StdWXCalculate <b>S</b>ervice<br/>
</p>

