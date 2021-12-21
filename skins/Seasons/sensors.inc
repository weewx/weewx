## sensors module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## this is a conditional display of sensor data, including connectivity,
## battery status, and various voltages.  if there are no data available,
## then this degenerates to nothing displayed.

#import time
#set $now = time.time()

#def get_battery_status($x)
#if $x is None
<span class="status_unknown">UNKNOWN</span>
#elif $x == 1
<span class="status_low">LOW</span>
#else
<span class="status_ok">OK</span>
#end if
#end def

## provide an indication of how much time has passed since the last sensor
## reading.
#def get_time_delta($last_ts, $now)
  #if $last_ts
    #set $delta = int($now - $last_ts)
    #if $delta < 60
 
#elif $delta < 3600
      #set $minutes = int($delta / 60)
$minutes $gettext('minutes ago')
    #elif $delta < 86400
      #set $hours = int($delta / 3600)
$hours $gettext('hours ago')
    #else
      #set $days = int($delta / 86400)
$days $gettext('days ago')
    #end if
  #else
never
  #end if
#end def


## Get the list of sensor observations from the configuration file, otherwise
## fallback to a very rudimentary set.
#set $sensor_connections = $DisplayOptions.get('sensor_connections', ['rxCheckPercent'])
#set $sensor_batteries = $DisplayOptions.get('sensor_batteries', ['outTempBatteryStatus', 'inTempBatteryStatus', 'rainBatteryStatus', 'windBatteryStatus', 'uvBatteryStatus', 'txBatteryStatus'])
#set $sensor_voltages = $DisplayOptions.get('sensor_voltages', ['consBatteryVoltage', 'heatingVoltage', 'supplyVoltage', 'referenceVoltage'])

## first see what sensor data are available

#set $have_conn = 0
#for $x in $sensor_connections
  #if $getVar('year.%s.has_data' % $x)
    #set $have_conn = 1
  #end if
#end for

#set $have_battery = 0
#for $x in $sensor_batteries
  #if $getVar('year.%s.has_data' % $x)
    #set $have_battery = 1
  #end if
#end for

#set $have_voltage = 0
#for $x in $sensor_voltages
  #if $getVar('year.%s.has_data' % $x)
    #set $have_voltage = 1
  #end if
#end for


## now display the available data only

#if $have_conn or $have_battery or $have_voltage
<div id='sensors_widget' class="widget">
  <div class="widget_title">
    <a href="telemetry.html">$gettext("Sensor Status")</a>
    <a class="widget_control" onclick="toggle_widget('sensors')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>

#if $have_conn
    <tr><th>$gettext("Connectivity")</th><th></th></tr>
#for $x in $sensor_connections
  #if $getVar('year.%s.has_data' % $x)
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$getVar('current.' + $x)</td>
      <td class="timestamp">$get_time_delta($getVar('year.%s.lasttime.raw' % $x), $now)</td>
    </tr>
  #end if
#end for
#end if

#if $have_battery
    <tr><th>$gettext("Battery Status")</th><th></th></tr>
#for $x in $sensor_batteries
  #if $getVar('year.%s.has_data' % $x)
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$get_battery_status($getVar('current.%s.raw' % $x))</td>
      <td class="timestamp">$get_time_delta($getVar('year.%s.lasttime.raw' % $x), $now)</td>
    </tr>
  #end if
#end for
#end if

#if $have_voltage
    <tr><th>$gettext("Voltage")</th><th></th></tr>
#for $x in $sensor_voltages
  #if $getVar('year.%s.has_data' % $x)
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$getVar('current.' + $x)</td>
      <td class="timestamp">$get_time_delta($getVar('year.%s.lasttime.raw' % $x), $now)</td>
    </tr>
  #end if
#end for
#end if

  </table>
  </div>

</div>
#end if
