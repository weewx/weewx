## totals module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $archive_data = [('day', $day), ('week', $week), ('month', $month), ('year', $year), ('rainyear', $rainyear)]

<div id='totals_widget' class="widget">
  <div class="widget_title">
    <a href="statistics.html">Totals</a>
    <a class="widget_control"
      onclick="toggle_widget('totals')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table>
    <tbody>
      <tr>
        <td></td>
        <th>&nbsp;<br/>Today</th>
        <th class="totals_week">&nbsp;<br/>Week</th>
        <th class="totals_month">&nbsp;<br/>Month</th>
        <th class="totals_year">
            <a onclick="toggle_rainyear()">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br/>Year</a>
        </th>
        <th class="totals_rainyear">
            <a onclick="toggle_rainyear()">Rain<br/>Year</a>
        </th>
        <td></td>
      </tr>
      <tr>
        <td class="label">$obs.label.rain</td>
        #for $archive in $archive_data
        <td class="data new_row totals_$archive[0]">
          $archive[1].rain.sum.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.rain</td>
      </tr>

      #if $day.ET.has_data and $day.ET.sum.raw > 0.0
      <tr>
        <td class="label">$obs.label.ET</td>
        #for $archive in $archive_data
        <td class="data new_row totals_$archive[0]">
          $archive[1].ET.sum.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.ET</td>
      </tr>
      #end if

    </tbody>
  </table>
  </div>
</div>
