## about module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

<div id='about_widget' class="widget">
  <div class="widget_title">
    About this weather station
    <a class="widget_control"
      onclick="toggle_widget('about')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table>
    <tr>
      <td class="label">Hardware</td>
      <td class="data">$station.hardware</td>
    </tr>
    <tr>
      <td class="label">Latitude</td>
      <td class="data">$station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2]</td>
    </tr>
    <tr>
      <td class="label">Longitude</td>
      <td class="data">$station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2]</td>
    </tr>
    <tr>
      <td class="label">Altitude</td>
      <td class="data">$station.altitude</td>
    </tr>
    <tr>
      <td class="label">Server uptime</td>
      <td class="data">$station.os_uptime</td>
    </tr>
    <tr>
      <td class="label">WeeWX uptime</td>
      <td class="data">$station.uptime</td>
    </tr>
    <tr>
      <td class="label">WeeWX version</td>
      <td class="data">$station.version</td>
    </tr>
  </table>
  </div>

</div>
