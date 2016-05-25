<div id='historical_summary' class="widget">
  <div class="section_heading">
    $Extras.labels.historical_summary
  </div>

  <table class="historical_summary">
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
        <td class="data">
          $archive.outTemp.max.formatted<br/>
          $archive.outTemp.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.outTemp</td>
      </tr>
      <tr>
        <td class="label">$obs.label.heatindex</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.heatindex.max.formatted</td>
        #end for
        <td class="units">$unit.label.heatindex</td>
      </tr>
      <tr>
        <td class="label">$obs.label.windchill</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.windchill.min.formatted</td>
        #end for
        <td class="units">$unit.label.windchill</td>
      </tr>
      <tr>
        <td class="label">$obs.label.dewpoint</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.dewpoint.max.formatted<br/>
          $archive.dewpoint.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.dewpoint</td>
      </tr>
      <tr>
        <td class="label">$obs.label.outHumidity</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.outHumidity.max.formatted<br/>
          $archive.outHumidity.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.outHumidity</td>
      </tr>
      <tr>
        <td class="label">$obs.label.barometer</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.barometer.max.formatted<br/>
          $archive.barometer.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.barometer</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rain</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.rain.sum.formatted</td>
        #end for
        <td class="units">$unit.label.rain</td>
      </tr>
      <tr>
        <td class="label">$obs.label.rainRate</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.rainRate.max.formatted</td>
        #end for
        <td class="units">$unit.label.rainRate</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_max</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.wind.max.formatted<br/>
          $archive.wind.gustdir
        </td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_average</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.wind.avg.formatted</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">$obs.label.wind_rms</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">$archive.wind.rms.formatted</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>

      <tr>
        <td class="label">
          $obs.label.vec_avg_speed<br/>
          $obs.label.vec_avg_dir
        </td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
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
        <td class="data">
          $archive.inTemp.max.formatted<br/>
          $archive.inTemp.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.inTemp</td>
      </tr>
      #end if

      #if $day.extraTemp1.has_data
      <tr>
        <td class="label">$obs.label.extraTemp1</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.extraTemp1.max.formatted<br/>
          $archive.extraTemp1.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.extraTemp1</td>
      </tr>
      #end if

      #if $day.UV.has_data
      <tr>
        <td class="label">$obs.label.UV</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.UV.max.formatted<br/>
          $archive.UV.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.UV</td>
      </tr>
      #end if

      #if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
        <td class="label">$obs.label.ET</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.ET.max.formatted<br/>
          $archive.ET.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.ET</td>
      </tr>
      #end if

      #if $day.radiation.has_data
      <tr>
        <td class="label">$obs.label.radiation</td>
        #for $archive in [$day, $week, $month, $year]
        <td class="data">
          $archive.radiation.max.formatted<br/>
          $archive.radiation.min.formatted
        </td>
        #end for
        <td class="units">$unit.label.radiation</td>
      </tr>
      #end if
    </tbody>
  </table>
</div>
