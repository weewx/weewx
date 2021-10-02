## sensors module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## this is a conditional display of sensor data, including connectivity,
## battery status, and various voltages.  if there are no data available,
## then this degenerates to nothing displayed.

#def get_battery_status($x)
#if $x == 0
<span class="status_ok">OK</span>
#else
<span class="status_low">LOW</span>
#end if
#end def

#set $conns = [ "rxCheckPercent", "signal1", "signal2", "signal3", "signal4", "signal5", "signal6", "signal7", "signal8" ]
#set $battery_statuses = [ "outTempBatteryStatus", "inTempBatteryStatus", "rainBatteryStatus", "hailBatteryStatus", "snowBatteryStatus", "windBatteryStatus", "uvBatteryStatus", "txBatteryStatus", "batteryStatus1", "batteryStatus2", "batteryStatus3", "batteryStatus4", "batteryStatus5", "batteryStatus6", "batteryStatus7", "batteryStatus8" ]
#set $voltages = [ "consBatteryVoltage", "heatingVoltage", "supplyVoltage", "referenceVoltage" ]

## first see what sensor data are available

#set $have_conn = 0
#for $x in $conns
  #if $getattr($current, $x).has_data
    #set $have_conn = 1
  #end if
#end for

#set $have_battery_status = 0
#for $x in $battery_statuses
  #if $getattr($current, $x).has_data
    #set $have_battery_status = 1
  #end if
#end for

#set $have_voltage = 0
#for $x in $voltages
  #if $getattr($current, $x).has_data
    #set $have_voltage = 1
  #end if
#end for


## now display the available data only

#if $have_conn or $have_battery_status or $have_voltage
<div id='sensors_widget' class="widget">
  <div class="widget_title">
    <a href="telemetry.html">$gettext("Sensor Status")</a>
    <a class="widget_control"
      onclick="toggle_widget('sensors')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>

#if $have_conn
    <tr><th>$gettext("Connectivity")</th><th></th></tr>
#for $x in $conns
  #if $getattr($current, $x).has_data
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$getattr($current, $x)</td>
    </tr>
  #end if
#end for
#end if

#if $have_battery_status
    <tr><th>$gettext("Battery Status")</th><th></th></tr>
#for $x in $battery_statuses
  #if $getattr($current, $x).has_data
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$getattr($current, $x)</td>
    </tr>
  #end if
#end for
#end if

#if $have_voltage
    <tr><th>$gettext("Voltage")</th><th></th></tr>
#for $x in $voltages
  #if $getattr($current, $x).has_data
    <tr>
      <td class="label">$obs.label[$x]</td>
      <td class="data">$getattr($current, $x)</td>
    </tr>
  #end if
#end for
#end if

  </table>
  </div>

</div>
#end if
