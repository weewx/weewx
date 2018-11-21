## statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

#set $archive_data = [$day, $week, $month, $year, $rainyear]

<div id="statistics_widget" class="widget">
  <div class="widget_title">
    Statistics
  </div>
  <div class="widget_contents">

    <table>
      <tbody>
        <tr>
          <td></td>
          <td></td>
          <th>Today</th>
          <th class="hilo_week">Week</th>
          <th class="hilo_month">Month</th>
          <th class="hilo_year">Year</th>
          <th class="hilo_rainyear">Rain year</th>
        </tr>
        <tr>
          <td class="label">$obs.label.outTemp</td>
          <td class="units">$unit.label.outTemp</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.outTemp.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.outTemp.maxtime</span><br/>
            $archive.outTemp.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.outTemp.mintime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.heatindex</td>
          <td class="units">$unit.label.heatindex</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.heatindex.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.heatindex.maxtime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.windchill</td>
          <td class="units">$unit.label.windchill</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.windchill.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.windchill.mintime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.dewpoint</td>
          <td class="units">$unit.label.dewpoint</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.dewpoint.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.dewpoint.maxtime</span><br/>
            $archive.dewpoint.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.dewpoint.mintime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.outHumidity</td>
          <td class="units">$unit.label.outHumidity</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.outHumidity.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.outHumidity.maxtime</span><br/>
            $archive.outHumidity.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.outHumidity.mintime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.barometer</td>
          <td class="units">$unit.label.barometer</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.barometer.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.barometer.maxtime</span><br/>
            $archive.barometer.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.barometer.mintime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.rain</td>
          <td class="units">$unit.label.rain</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.rain.sum.format(add_label=False)</td>
          #end for
        </tr>
        <tr>
          <td class="label">$obs.label.rainRate</td>
          <td class="units">$unit.label.rainRate</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.rainRate.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.rainRate.maxtime</span>
          </td>
          #end for
        </tr>
		#if $day.ET.has_data and $day.ET.sum.raw > 0.0
          <tr>
	      <td class="label">$obs.label.ET</td>
          <td class="units">$unit.label.ET</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.ET.sum.format(add_label=False)</td>
          #end for
          </tr>
		#end if
        <tr>
          <td class="label">Wind Max</td>
          <td class="units">
            $unit.label.wind<br/>
            $unit.label.windDir
          </td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.wind.max.format(add_label=False)<br/>
            $archive.wind.gustdir.format(add_label=False)<br/>
            <span class="timestamp">$archive.wind.maxtime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">Wind Average</td>
          <td class="units">$unit.label.wind</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.wind.avg.format(add_label=False)</td>
          #end for
        </tr>
        <tr>
          <td class="label">Wind RMS</td>
          <td class="units">$unit.label.wind</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.wind.rms.format(add_label=False)</td>
          #end for
        </tr>

        <tr>
          <td class="label">
            Vector Average<br/>
            Average Direction
          </td>
          <td class="units">
            $unit.label.wind<br/>
            $unit.label.windDir
          </td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.wind.vecavg.format(add_label=False)<br/>
            $archive.wind.vecdir.format(add_label=False)
          </td>
          #end for
        </tr>

        #if $day.UV.has_data
        <tr>
          <td class="label">$obs.label.UV</td>
          <td class="units">$unit.label.UV</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.UV.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.UV.maxtime</span><br/>
            $archive.UV.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.UV.mintime</span>
          </td>
          #end for
        </tr>
        #end if

        #if $day.radiation.has_data
        <tr>
          <td class="label">$obs.label.radiation</td>
          <td class="units">$unit.label.radiation</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.radiation.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.radiation.maxtime</span><br/>
            $archive.radiation.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.radiation.mintime</span>
          </td>
          #end for
        </tr>
        #end if

        #if $day.inTemp.has_data
        <tr>
          <td class="label">$obs.label.inTemp</td>
          <td class="units">$unit.label.inTemp</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.inTemp.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.inTemp.maxtime</span><br/>
            $archive.inTemp.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.inTemp.mintime</span>
          </td>
          #end for
        </tr>
        #end if

        #if $day.extraTemp1.has_data
        <tr>
          <td class="label">$obs.label.extraTemp1</td>
          <td class="units">$unit.label.extraTemp1</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.extraTemp1.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp1.maxtime</span><br/>
            $archive.extraTemp1.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp1.mintime</span>
          </td>
          #end for
        </tr>
        #end if

        #if $day.extraTemp2.has_data
        <tr>
          <td class="label">$obs.label.extraTemp2</td>
          <td class="units">$unit.label.extraTemp2</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.extraTemp2.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp2.maxtime</span><br/>
            $archive.extraTemp2.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp2.mintime</span>
          </td>
          #end for
        </tr>
        #end if

        #if $day.extraTemp3.has_data
        <tr>
          <td class="label">$obs.label.extraTemp3</td>
          <td class="units">$unit.label.extraTemp3</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.extraTemp3.max.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp3.maxtime</span><br/>
            $archive.extraTemp3.min.format(add_label=False)<br/>
            <span class="timestamp">$archive.extraTemp3.mintime</span>
          </td>
          #end for
        </tr>
        #end if
      </tbody>
    </table>

  </div>
</div>
