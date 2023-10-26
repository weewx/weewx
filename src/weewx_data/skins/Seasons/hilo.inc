## summary statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $timespans = ['day', 'week', 'month', 'year', 'rainyear']

## Get the list of observations from the configuration file, otherwise fallback
## to a very rudimentary set of observations.
#set $observations = $to_list($DisplayOptions.get('observations_stats', ['outTemp', 'windSpeed', 'rain']))
#set $obs_type_sum = $to_list($DisplayOptions.get('obs_type_sum', ['rain']))
#set $obs_type_max = $to_list($DisplayOptions.get('obs_type_max', ['rainRate']))

## use this span to determine whether there are any data to consider.
#set $recent=$span($day_delta=30, boundary='midnight')

<div id='hilo_widget' class="widget">
  <div class="widget_title">
    <a href="statistics.html">$gettext("Statistics")</a>
    <a class="widget_control"
      onclick="toggle_widget('hilo')">&diams;</a>
  </div>

  <div class="widget_contents">
  <table>
    <tbody>
      <tr>
        <td></td>
        <th>&nbsp;<br/>$gettext("Today")</th>
        <th class="hilo_week">&nbsp;<br/>$gettext("Week")</th>
        <th class="hilo_month">&nbsp;<br/>$gettext("Month")</th>
        <th class="hilo_year">
          <a onclick="toggle_rainyear()">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br/>$gettext("Year")</a>
        </th>
        <th class="hilo_rainyear">
          <a onclick="toggle_rainyear()">$gettext("Rain<br/>Year")</a>
        </th>
        <td></td>
      </tr>

#for $x in $observations
  #if getattr($recent, $x).has_data
    #if $x == 'windSpeed'
      <tr>
        <td class="label">$gettext("Max Wind")</td>
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          <span title="$getVar($timespan).wind.maxtime">
            $getVar($timespan).wind.max.format(add_label=False)</span><br/>
          $getVar($timespan).wind.gustdir.format(add_label=False)
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>
      <tr>
        <td class="label">$gettext("Average Wind")</td>
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          $getVar($timespan).wind.avg.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">$gettext("RMS Wind")</td>
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          $getVar($timespan).wind.rms.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>

      <tr>
        <td class="label">
          $gettext("Vector Average")<br/>
          $gettext("Vector Direction")
        </td>
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          $getVar($timespan).wind.vecavg.format(add_label=False)<br/>
          $getVar($timespan).wind.vecdir.format(add_label=False)
        </td>
        #end for
        <td class="units">
          $unit.label.wind<br/>
          $unit.label.windDir
        </td>
      </tr>
    #else
      <tr>
        <td class="label">$obs.label[$x]</td>
      #if $x in $obs_type_sum
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          $getVar('%s.%s' % ($timespan, $x)).sum.format(add_label=False)</td>
        #end for
      #elif $x in $obs_type_max
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          <span title="$getVar('%s.%s' % ($timespan, $x)).maxtime">
            $getVar('%s.%s' % ($timespan, $x)).max.format(add_label=False)</span>
        </td>
        #end for
      #else
        #for $timespan in $timespans
        <td class="data new_row hilo_$timespan">
          <span title="$getVar('%s.%s' % ($timespan, $x)).maxtime">
            $getVar('%s.%s' % ($timespan, $x)).max.format(add_label=False)</span><br/>
          <span title="$getVar('%s.%s' % ($timespan, $x)).mintime">
            $getVar('%s.%s' % ($timespan, $x)).min.format(add_label=False)</span>
        </td>
        #end for
      #end if
        <td class="units">$getattr($unit.label, $x, '')</td>
      </tr>
    #end if
  #end if
#end for

    </tbody>
  </table>
  </div>
</div>
