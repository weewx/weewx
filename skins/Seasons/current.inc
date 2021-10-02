## current module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## The list of observations determines which database fields will be shown in
## the summary as well as the order in which they will be displayed.
#set $observations = ['outTemp', 'heatindex', 'windchill', 'dewpoint', 'outHumidity', 'barometer', 'rain', 'rainRate', 'windSpeed', 'UV', 'radiation', 'inTemp', 'inHumidity', 'extraTemp1', 'extraHumid1', 'extraTemp2', 'extraHumid2', 'extraTemp3', 'extraHumid3', 'extraTemp4', 'extraHumid4', 'extraTemp5', 'extraHumid5', 'extraTemp6', 'extraHumid6', 'extraTemp7', 'extraHumid7', 'extraTemp8', 'extraHumid8', 'leafTemp1', 'leafTemp2', 'leafWet1', 'leafWet2', 'soilTemp1', 'soilTemp2', 'soilTemp3', 'soilTemp4', 'soilMoist1', 'soilMoist2', 'soilMoist3', 'soilMoist4', 'pm1_0', 'pm2_5', 'pm10_0', 'co', 'co2', 'nh3', 'no2', 'o3', 'so2']

<div id='current_widget' class="widget">
  <div class="widget_title">
    $gettext("Current Conditions")
    <a class="widget_control"
      onclick="toggle_widget('current')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table>
    <tbody>

#for $x in $observations
  #if $getattr($year, $x).has_data
    #if $x == 'barometer'
      <tr>
        <td class="label">$obs.label.barometer</td>
        <td class="data">$current.barometer ($trend.barometer.formatted)</td>
      </tr>
    #elif $x == 'windSpeed'
      <tr>
        <td class="label">$obs.label.wind</td>
        <td class="data">$current.windSpeed $current.windDir.ordinal_compass ($current.windDir)</td>
      </tr>
    #elif $x == 'rain'
      <tr>
        <td class="label">$obs.label.rain_today</td>
        <td class="data">$day.rain.sum</td>
      </tr>
    #else
      <tr>
        <td class="label">$obs.label[$x]</td>
        <td class="data">$getattr($current, $x)</td>
      </tr>
    #end if
  #end if
#end for

    </tbody>
  </table>
  </div>

</div>
