## statistics format B for standard skin
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights

#set $periods = [('Day', $day), ('Week', $week), ('Month', $month), ('Year', $year)]


<div id="statistics_widget" class="widget">
  <div class="widget_title">
    Statistics
    <a class="widget_control"
       onclick="toggle_widget('statistics')">&diams;</a>
  </div>
  <div class="widget_contents">

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.outTemp</th>
          <th>$unit.label.outTemp</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.outTemp.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].outTemp.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].outTemp.max.formatted</td>
          <td class="timestamp">$period[1].outTemp.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].outTemp.min.formatted</td>
          <td class="timestamp">$period[1].outTemp.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.heatindex</th>
          <th>$unit.label.heatindex</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.heatindex.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].heatindex.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].heatindex.max.formatted</td>
          <td class="timestamp">$period[1].heatindex.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].heatindex.min.formatted</td>
          <td class="timestamp">$period[1].heatindex.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.windchill</th>
          <th>$unit.label.windchill</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.windchill.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].windchill.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].windchill.max.formatted</td>
          <td class="timestamp">$period[1].windchill.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].windchill.min.formatted</td>
          <td class="timestamp">$period[1].windchill.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.dewpoint</th>
          <th>$unit.label.dewpoint</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.dewpoint.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].dewpoint.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].dewpoint.max.formatted</td>
          <td class="timestamp">$period[1].dewpoint.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].dewpoint.min.formatted</td>
          <td class="timestamp">$period[1].dewpoint.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.outHumidity</th>
          <th>$unit.label.outHumidity</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.outHumidity.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].outHumidity.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].outHumidity.max.formatted</td>
          <td class="timestamp">$period[1].outHumidity.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].outHumidity.min.formatted</td>
          <td class="timestamp">$period[1].outHumidity.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.barometer</th>
          <th>$unit.label.barometer</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.barometer.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].barometer.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].barometer.max.formatted</td>
          <td class="timestamp">$period[1].barometer.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].barometer.min.formatted</td>
          <td class="timestamp">$period[1].barometer.mintime</td>
        </tr>
        #end for
      </table>
    </div>

    #if $day.inTemp.has_data
    <div class='stats'>
      <table>
        <tr>
          <th colspan="2">$obs.label.inTemp</th>
          <th>$unit.label.inTemp</th>
          <th></th>
        </tr>
        <tr>
          <td class="label" colspan="2">Current</td>
          <td class="data">$current.inTemp.formatted</td>
          <td></td>
        </tr>
        #for $period in $periods
        <tr>
          <td class="label">$period[0]</td>
          <td class="label">Avg</td>
          <td class="data">$period[1].inTemp.avg.formatted</td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td class="label">High</td>
          <td class="data">$period[1].inTemp.max.formatted</td>
          <td class="timestamp">$period[1].inTemp.maxtime</td>
        </tr>
        <tr>
          <td></td>
          <td class="label">Low</td>
          <td class="data">$period[1].inTemp.min.formatted</td>
          <td class="timestamp">$period[1].inTemp.mintime</td>
        </tr>
        #end for
      </table>
    </div>
    #end if

  </div>
</div>
