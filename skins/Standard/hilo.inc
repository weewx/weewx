<div id='hilo_widget' class="widget">
  <div class="widget_title">
    Highs and Lows
    <a class="widget_control"
      onclick="toggle_widget('hilo')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table class="stats">
    <tbody>
      <tr>
        <th></th>
        <th>Today</th>
        <th>Week</th>
        <th>Month</th>
        <th>Year</th>
        <th></th>
      </tr>
      <tr>
        <td class="label">$obs.label.outTemp</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.outTemp.maxtime">
            $archive.outTemp.max.formatted</span><br/>
          <span title="$archive.outTemp.mintime">
            $archive.outTemp.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.outTemp</td>
      </tr>
      <tr>
        <td class="label">$obs.label.heatindex</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.heatindex.maxtime">
            $archive.heatindex.max.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.heatindex</td>
      </tr>
      <tr>
        <td class="label">$obs.label.windchill</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.windchill.mintime">
            $archive.windchill.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.windchill</td>
      </tr>
      <tr>
        <td class="label">$obs.label.dewpoint</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.dewpoint.maxtime">
            $archive.dewpoint.max.formatted</span><br/>
          <span title="$archive.dewpoint.mintime">
            $archive.dewpoint.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.dewpoint</td>
      </tr>
      <tr>
        <td class="label">$obs.label.outHumidity</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.outHumidity.maxtime">
            $archive.outHumidity.max.formatted</span><br/>
          <span title="$archive.outHumidity.mintime">
            $archive.outHumidity.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.outHumidity</td>
      </tr>
      <tr>
        <td class="label">$obs.label.barometer</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.barometer.maxtime">
            $archive.barometer.max.formatted</span><br/>
          <span title="$archive.barometer.mintime">
            $archive.barometer.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.barometer</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rain</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">$archive.rain.sum.formatted</td>
        #end for
        <td class="units">$unit.label.rain</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rainRate</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.rainRate.maxtime">
            $archive.rainRate.max.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.rainRate</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_max</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.wind.maxtime">
            $archive.wind.max.formatted</span><br/>
          $archive.wind.gustdir.formatted
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_avg</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">$archive.wind.avg.formatted</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_rms</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">$archive.wind.rms.formatted</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>

      <tr>
        <td class="label">
          $obs.label.vecavg<br/>
          $obs.label.vecdir
        </td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          $archive.wind.vecavg.formatted<br/>
          $archive.wind.vecdir.formatted
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>

      #if $day.inTemp.has_data
      <tr>
        <td class="label">$obs.label.inTemp</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.inTemp.maxtime">
            $archive.inTemp.max.formatted</span><br/>
          <span title="$archive.inTemp.mintime">
            $archive.inTemp.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.inTemp</td>
      </tr>
      #end if

      #if $day.extraTemp1.has_data
      <tr>
        <td class="label">$obs.label.extraTemp1</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.extraTemp1.maxtime">
            $archive.extraTemp1.max.formatted</span><br/>
          <span title="$archive.extraTemp1.mintime">
            $archive.extraTemp1.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.extraTemp1</td>
      </tr>
      #end if

      #if $day.UV.has_data
      <tr>
        <td class="label">$obs.label.UV</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.UV.maxtime">
            $archive.UV.max.formatted</span><br/>
          <span title="$archive.UV.mintime">
            $archive.UV.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.UV</td>
      </tr>
      #end if

      #if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
        <td class="label">$obs.label.ET</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.ET.maxtime">
            $archive.ET.max.formatted</span><br/>
          <span title="$archive.ET.mintime">
            $archive.ET.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.ET</td>
      </tr>
      #end if

      #if $day.radiation.has_data
      <tr>
        <td class="label">$obs.label.radiation</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data new_row">
          <span title="$archive.radiation.maxtime">
            $archive.radiation.max.formatted</span><br/>
          <span title="$archive.radiation.mintime">
            $archive.radiation.min.formatted</span>
        </td>
        #end for
        <td class="units">$unit.label.radiation</td>
      </tr>
      #end if
    </tbody>
  </table>
  </div>
</div>
