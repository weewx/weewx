## sensors module for standard skin
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights

## this is a conditional display of sensor data, including connectivity,
## battery status, and various voltages.  if there are no data available,
## then this degenerates to nothing displayed.


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
    Sensors
    <a class="widget_control"
      onclick="toggle_widget('sensors')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>

#if $have_conn
    <tr><td colspan="2">Connectivity</td></tr>
#if $day.rxCheckPercent.has_data
    <tr>
      <td class="label">Transmitter</td>
      <td class="data">$current.rxCheckPercent</td>
    </tr>
#end if
#end if

#if $have_battery_status
    <tr><td colspan="2">Battery Status</td></tr>
#if $day.txBatteryStatus.has_data
    <tr>
      <td class="label">Transmitter</td>
      <td class="data">$current.txBatteryStatus</td>
    </tr>
#end if
#if $day.windBatteryStatus.has_data
    <tr>
      <td class="label">Wind</td>
      <td class="data">$current.windBatteryStatus</td>
    </tr>
#end if
#if $day.rainBatteryStatus.has_data
    <tr>
      <td class="label">Rain</td>
      <td class="data">$current.rainBatteryStatus</td>
    </tr>
#end if
#if $day.outTempBatteryStatus.has_data
    <tr>
      <td class="label">Outside Temperature</td>
      <td class="data">$current.outTempBatteryStatus</td>
    </tr>
#end if
#if $day.inTempBatteryStatus.has_data
    <tr>
      <td class="label">Inside Temperature</td>
      <td class="data">$current.inTempBatteryStatus</td>
    </tr>
#end if
#end if

#if $have_voltage
    <tr><td colspan="2">Voltages</td></tr>
#if $day.consBatteryVoltage.has_data
    <tr>
      <td class="label">Console</td>
      <td class="data">$current.consBatteryVoltage</td>
    </tr>
#end if
#if $day.heatingVoltage.has_data
    <tr>
      <td class="label">Heating</td>
      <td class="data">$current.heatingVoltage</td>
    </tr>
#end if
#if $day.supplyVoltage.has_data
    <tr>
      <td class="label">Supply</td>
      <td class="data">$current.supplyVoltage</td>
    </tr>
#end if
#if $day.referenceVoltage.has_data
    <tr>
      <td class="label">Reference</td>
      <td class="data">$current.referenceVoltage</td>
    </tr>
#end if
#end if
  </table>
  </div>

</div>
#end if
