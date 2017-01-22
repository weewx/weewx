## sensors module for standard skin
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights

<div id='sensors_widget' class="widget">
  <div class="widget_title">
    Sensors
    <a class="widget_control"
      onclick="toggle_widget('sensors')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>
    <tr><td colspan="2">Connectivity</td></tr>
    <tr>
      <td class="label">Transmitter</td>
      <td class="data">$current.rxCheckPercent</td>
    </tr>

    <tr><td colspan="2">Battery Status</td></tr>
    <tr>
      <td class="label">Transmitter</td>
      <td class="data">$current.txBatteryStatus</td>
    </tr>
    <tr>
      <td class="label">Wind</td>
      <td class="data">$current.windBatteryStatus</td>
    </tr>
    <tr>
      <td class="label">Rain</td>
      <td class="data">$current.rainBatteryStatus</td>
    </tr>
    <tr>
      <td class="label">Outside Temperature</td>
      <td class="data">$current.outTempBatteryStatus</td>
    </tr>
    <tr>
      <td class="label">Inside Temperature</td>
      <td class="data">$current.inTempBatteryStatus</td>
    </tr>

    <tr><td colspan="2">Voltages</td></tr>
    <tr>
      <td class="label">Console</td>
      <td class="data">$current.consBatteryVoltage</td>
    </tr>
    <tr>
      <td class="label">Heating</td>
      <td class="data">$current.heatingVoltage</td>
    </tr>
    <tr>
      <td class="label">Supply</td>
      <td class="data">$current.supplyVoltage</td>
    </tr>
    <tr>
      <td class="label">Reference</td>
      <td class="data">$current.referenceVoltage</td>
    </tr>
  </table>
  </div>

</div>
