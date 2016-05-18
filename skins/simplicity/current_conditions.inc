<div id='current_conditions' class="widget">
  <div class="section_heading">
    $Extras.labels.current_conditions
  </div>
      
  <table class="current_conditions">
    <tbody>
      <tr>
	<td class="stats_label">$obs.label.outTemp</td>
	<td class="stats_data">$current.outTemp</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.heatindex</td>
	<td class="stats_data">$current.heatindex</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.windchill</td>
	<td class="stats_data">$current.windchill</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.dewpoint</td>
	<td class="stats_data">$current.dewpoint</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.outHumidity</td>
	<td class="stats_data">$current.outHumidity</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.barometer</td>
	<td class="stats_data">$current.barometer</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.barometer_trend</td>
	<td class="stats_data">$trend.barometer</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.wind</td>
	<td class="stats_data">$current.windSpeed $current.windDir.ordinal_compass ($current.windDir)</td>
      </tr>
      <tr>
	<td class="stats_label">$obs.label.rainRate</td>
	<td class="stats_data">$current.rainRate</td>
      </tr>
      #if $day.UV.has_data
      <tr>
	<td class="stats_label">$obs.label.UV</td>
	<td class="stats_data">$current.UV</td>
      </tr>
      #end if
      #if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
	<td class="stats_label">$obs.label.ET</td>
	<td class="stats_data">$current.ET</td>
      </tr>
      #end if
      #if $day.radiation.has_data
      <tr>
	<td class="stats_label">$obs.label.radiation</td>
	<td class="stats_data">$current.radiation</td>
      </tr>
      #end if
      #if $day.inTemp.has_data
      <tr>
	<td class="stats_label">$obs.label.inTemp</td>
	<td class="stats_data">$current.inTemp</td>
      </tr>
      #end if
      #if $day.extraTemp1.has_data
      <tr>
	<td class="stats_label">$obs.label.extraTemp1</td>
	<td class="stats_data">$current.extraTemp1</td>
      </tr>
      #end if
    </tbody>
  </table>
</div>
