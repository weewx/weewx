## current module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

<div id='current_widget' class="widget">
  <div class="widget_title">
    Current Conditions
    <a class="widget_control"
      onclick="toggle_widget('current')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table>
    <tbody>
      <tr>
        <td class="label">$obs.label.outTemp</td>
        <td class="data">$current.outTemp</td>
      </tr>
      <tr>
        <td class="label">$obs.label.heatindex</td>
        <td class="data">$current.heatindex</td>
      </tr>
      <tr>
        <td class="label">$obs.label.windchill</td>
        <td class="data">$current.windchill</td>
      </tr>
      <tr>
        <td class="label">$obs.label.dewpoint</td>
        <td class="data">$current.dewpoint</td>
      </tr>
      <tr>
        <td class="label">$obs.label.outHumidity</td>
        <td class="data">$current.outHumidity</td>
      </tr>
      <tr>
        <td class="label">$obs.label.barometer</td>
        <td class="data">$current.barometer ($trend.barometer.formatted)</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind</td>
        <td class="data">$current.windSpeed $current.windDir.ordinal_compass ($current.windDir)</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rainRate</td>
        <td class="data">$current.rainRate</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rain_today</td>
        <td class="data">$day.rain.sum</td>
      </tr>
#if $day.UV.has_data
      <tr>
        <td class="label">$obs.label.UV</td>
        <td class="data">$current.UV</td>
      </tr>
#end if
#if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
        <td class="label">$obs.label.ET</td>
        <td class="data">$current.ET</td>
      </tr>
#end if
#if $day.radiation.has_data
      <tr>
        <td class="label">$obs.label.radiation</td>
        <td class="data">$current.radiation</td>
      </tr>
#end if
#if $day.inTemp.has_data
      <tr>
        <td class="label">$obs.label.inTemp</td>
        <td class="data">$current.inTemp</td>
      </tr>
#end if
#if $day.inHumidity.has_data
      <tr>
        <td class="label">$obs.label.inHumidity</td>
        <td class="data">$current.inHumidity</td>
      </tr>
#end if
#if $day.extraTemp1.has_data
      <tr>
        <td class="label">$obs.label.extraTemp1</td>
        <td class="data">$current.extraTemp1</td>
      </tr>
#end if
#if $day.extraTemp2.has_data
      <tr>
        <td class="label">$obs.label.extraTemp2</td>
        <td class="data">$current.extraTemp2</td>
      </tr>
#end if
#if $day.extraTemp3.has_data
      <tr>
        <td class="label">$obs.label.extraTemp3</td>
        <td class="data">$current.extraTemp3</td>
      </tr>
#end if
    </tbody>
  </table>
  </div>

</div>
