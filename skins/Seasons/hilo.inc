## hilo module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights

#set $archive_data = [('day', $day), ('week', $week), ('month', $month), ('year', $year), ('rainyear', $rainyear)]

<div id='hilo_widget' class="widget">
  <div class="widget_title">
    <a href="statistics.html">High/Low</a>
    <a class="widget_control"
      onclick="toggle_widget('hilo')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table>
    <tbody>
      <tr>
        <td></td>
        <th>&nbsp;<br/>Today</th>
        <th class="hilo_week">&nbsp;<br/>Week</th>
        <th class="hilo_month">&nbsp;<br/>Month</th>
        <th class="hilo_year">
            <a onclick="toggle_rainyear()">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br/>Year</a>
        </th>
        <th class="hilo_rainyear">
            <a onclick="toggle_rainyear()">Rain<br/>Year</a>
        </th>
        <td></td>
      </tr>
      <tr>
        <td class="label">$obs.label.outTemp</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].outTemp.maxtime">
            $archive[1].outTemp.max.format(add_label=False)</span><br/>
          <span title="$archive[1].outTemp.mintime">
            $archive[1].outTemp.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.outTemp</td>
      </tr>
      <tr>
        <td class="label">$obs.label.heatindex</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].heatindex.maxtime" class="hival">
            $archive[1].heatindex.max.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.heatindex</td>
      </tr>
      <tr>
        <td class="label">$obs.label.windchill</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].windchill.mintime" class="loval">
            $archive[1].windchill.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.windchill</td>
      </tr>
      <tr>
        <td class="label">$obs.label.dewpoint</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].dewpoint.maxtime">
            $archive[1].dewpoint.max.format(add_label=False)</span><br/>
          <span title="$archive[1].dewpoint.mintime">
            $archive[1].dewpoint.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.dewpoint</td>
      </tr>
      <tr>
        <td class="label">$obs.label.outHumidity</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].outHumidity.maxtime">
            $archive[1].outHumidity.max.format(add_label=False)</span><br/>
          <span title="$archive[1].outHumidity.mintime">
            $archive[1].outHumidity.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.outHumidity</td>
      </tr>
      <tr>
        <td class="label">$obs.label.barometer</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].barometer.maxtime">
            $archive[1].barometer.max.format(add_label=False)</span><br/>
          <span title="$archive[1].barometer.mintime">
            $archive[1].barometer.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.barometer</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rain</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].rain.sum.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.rain</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rainRate</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].rainRate.maxtime">
            $archive[1].rainRate.max.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.rainRate</td>
      </tr>
      <tr>
        <td class="label">Wind Max</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].wind.maxtime">
            $archive[1].wind.max.format(add_label=False)</span><br/>
          $archive[1].wind.gustdir.format(add_label=False)
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>
      <tr>
        <td class="label">Wind Average</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].wind.avg.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">Wind RMS</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].wind.rms.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>

      <tr>
        <td class="label">
          Vector Average<br/>
          Average Direction
        </td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].wind.vecavg.format(add_label=False)<br/>
          $archive[1].wind.vecdir.format(add_label=False)
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>

      #if $day.UV.has_data
      <tr>
        <td class="label">$obs.label.UV</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].UV.maxtime">
            $archive[1].UV.max.format(add_label=False)</span><br/>
          <span title="$archive[1].UV.mintime">
            $archive[1].UV.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.UV</td>
      </tr>
      #end if

      #if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
        <td class="label">$obs.label.ET</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].ET.maxtime">
            $archive[1].ET.max.format(add_label=False)</span><br/>
          <span title="$archive[1].ET.mintime">
            $archive[1].ET.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.ET</td>
      </tr>
      #end if

      #if $day.radiation.has_data
      <tr>
        <td class="label">$obs.label.radiation</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].radiation.maxtime">
            $archive[1].radiation.max.format(add_label=False)</span><br/>
          <span title="$archive[1].radiation.mintime">
            $archive[1].radiation.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.radiation</td>
      </tr>
      #end if

      #if $day.inTemp.has_data
      <tr>
        <td class="label">$obs.label.inTemp</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].inTemp.maxtime">
            $archive[1].inTemp.max.format(add_label=False)</span><br/>
          <span title="$archive[1].inTemp.mintime">
            $archive[1].inTemp.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.inTemp</td>
      </tr>
      #end if

      #if $day.extraTemp1.has_data
      <tr>
        <td class="label">$obs.label.extraTemp1</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].extraTemp1.maxtime">
            $archive[1].extraTemp1.max.format(add_label=False)</span><br/>
          <span title="$archive[1].extraTemp1.mintime">
            $archive[1].extraTemp1.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.extraTemp1</td>
      </tr>
      #end if

      #if $day.extraTemp2.has_data
      <tr>
        <td class="label">$obs.label.extraTemp2</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].extraTemp2.maxtime">
            $archive[1].extraTemp2.max.format(add_label=False)</span><br/>
          <span title="$archive[1].extraTemp2.mintime">
            $archive[1].extraTemp2.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.extraTemp2</td>
      </tr>
      #end if

      #if $day.extraTemp3.has_data
      <tr>
        <td class="label">$obs.label.extraTemp3</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$archive[1].extraTemp3.maxtime">
            $archive[1].extraTemp3.max.format(add_label=False)</span><br/>
          <span title="$archive[1].extraTemp3.mintime">
            $archive[1].extraTemp3.min.format(add_label=False)</span>
        </td>
        #end for
        <td class="units">$unit.label.extraTemp3</td>
      </tr>
      #end if
    </tbody>
  </table>
  </div>
</div>
