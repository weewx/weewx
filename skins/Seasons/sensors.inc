## sensors module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

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

## first see what sensor data are available

#set $have_conn = 0
#for $x in [$day.rxCheckPercent]
  #if $x.has_data
    #set $have_conn = 1
  #end if
#end for

#set $have_battery_status = 0
#for $x in [$day.txBatteryStatus, $day.windBatteryStatus, $day.rainBatteryStatus, $day.outTempBatteryStatus, $day.inTempBatteryStatus]
  #if $x.has_data
    #set $have_battery_status = 1
  #end if
#end for

#set $have_voltage = 0
#for $x in [$day.consBatteryVoltage, $day.heatingVoltage, $day.supplyVoltage, $day.referenceVoltage]
  #if $x.has_data
    #set $have_voltage = 1
  #end if
#end for


## now display the available data only

#if $have_conn or $have_battery_status or $have_voltage
<div id='sensors_widget' class="widget">
  <div class="widget_title">
    <a href="telemetry.html">Sensor Status</a>
    <a class="widget_control"
      onclick="toggle_widget('sensors')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>

#if $have_conn
    <tr><th>Connectivity</th></tr>
#if $day.rxCheckPercent.has_data
    <tr>
      <td class="label">$obs.label.rxCheckPercent</td>
      <td class="data">$current.rxCheckPercent</td>
    </tr>
#end if
#end if

#if $have_battery_status
    <tr><th>Battery Status</th></tr>
#if $day.txBatteryStatus.has_data
    <tr>
      <td class="label">$obs.label.txBatteryStatus</td>
      <td class="data">$get_battery_status($current.txBatteryStatus.raw)</td>
    </tr>
#end if
#if $day.windBatteryStatus.has_data
    <tr>
      <td class="label">$obs.label.windBatteryStatus</td>
      <td class="data">$get_battery_status($current.windBatteryStatus.raw)</td>
    </tr>
#end if
#if $day.rainBatteryStatus.has_data
    <tr>
      <td class="label">$obs.label.rainBatteryStatus</td>
      <td class="data">$get_battery_status($current.rainBatteryStatus.raw)</td>
    </tr>
#end if
#if $day.outTempBatteryStatus.has_data
    <tr>
      <td class="label">$obs.label.outTempBatteryStatus</td>
      <td class="data">$get_battery_status($current.outTempBatteryStatus.raw)</td>
    </tr>
#end if
#if $day.inTempBatteryStatus.has_data
    <tr>
      <td class="label">$obs.label.inTempBatteryStatus</td>
      <td class="data">$get_battery_status($current.inTempBatteryStatus.raw)</td>
    </tr>
#end if
#end if

#if $have_voltage
    <tr><th>Voltage</th></tr>
#if $day.consBatteryVoltage.has_data
    <tr>
      <td class="label">$obs.label.consBatteryVoltage</td>
      <td class="data">$current.consBatteryVoltage</td>
    </tr>
#end if
#if $day.heatingVoltage.has_data
    <tr>
      <td class="label">$obs.label.heatingVoltage</td>
      <td class="data">$current.heatingVoltage</td>
    </tr>
#end if
#if $day.supplyVoltage.has_data
    <tr>
      <td class="label">$obs.label.supplyVoltage</td>
      <td class="data">$current.supplyVoltage</td>
    </tr>
#end if
#if $day.referenceVoltage.has_data
    <tr>
      <td class="label">$obs.label.referenceVoltage</td>
      <td class="data">$current.referenceVoltage</td>
    </tr>
#end if
#end if
  </table>
  </div>

</div>
#end if
