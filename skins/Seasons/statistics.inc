## statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $time_tags = [$day, $week, $month, $year, $rainyear]

## Get the list of observations from the configuration file, otherwise fallback
## to a very rudimentary set of observations.
#set $observations = $to_list($DisplayOptions.get('observations_stats', ['outTemp', 'windSpeed', 'rain']))
#set $obs_type_sum = $to_list($DisplayOptions.get('obs_type_sum', ['rain']))
#set $obs_type_max = $to_list($DisplayOptions.get('obs_type_max', ['rainRate']))

## use this span to determine whether there are any data to consider.
#set $recent=$span($day_delta=30, boundary='midnight')

<div id="statistics_widget" class="widget">
  <div class="widget_title">
    $gettext("Statistics")
  </div>
  <div class="widget_contents">

    <table>
      <tbody>
        <tr>
          <td></td>
          <td></td>
          <th>$gettext("Today")</th>
          <th class="hilo_week">$gettext("Week")</th>
          <th class="hilo_month">$gettext("Month")</th>
          <th class="hilo_year">$gettext("Year")</th>
          <th class="hilo_rainyear">$gettext("Rain Year")</th>
        </tr>

#for $x in $observations
  #if getattr($recent, $x).has_data
    #if $x == 'windSpeed'
        <tr>
          <td class="label">$gettext("Max Wind")</td>
          <td class="units">
            $unit.label.wind<br/>
            $unit.label.windDir
          </td>
          #for $time_tag in $time_tags
          <td class="data new_row">
            $time_tag.wind.max.format(add_label=False)<br/>
            $time_tag.wind.gustdir.format(add_label=False)<br/>
            <span class="timestamp">$time_tag.wind.maxtime</span>
          </td>
          #end for
        </tr>
        <tr>
          <td class="label">$gettext("Average Wind")</td>
          <td class="units">$unit.label.wind</td>
          #for $time_tag in $time_tags
          <td class="data new_row">
            $time_tag.wind.avg.format(add_label=False)</td>
          #end for
        </tr>
        <tr>
          <td class="label">$gettext("RMS Wind")</td>
          <td class="units">$unit.label.wind</td>
          #for $time_tag in $time_tags
          <td class="data new_row">$time_tag.wind.rms.format(add_label=False)</td>
          #end for
        </tr>

        <tr>
          <td class="label">
            $gettext("Vector Average")<br/>
            $gettext("Vector Direction")
          </td>
          <td class="units">
            $unit.label.wind<br/>
            $unit.label.windDir
          </td>
          #for $time_tag in $time_tags
          <td class="data new_row">
            $time_tag.wind.vecavg.format(add_label=False)<br/>
            $time_tag.wind.vecdir.format(add_label=False)
          </td>
          #end for
        </tr>
    #else
        <tr>
          <td class="label">$obs.label[$x]</td>
          <td class="units">$getattr($unit.label, $x, '')</td>
      #if $x in $obs_type_sum
        #for $time_tag in $time_tags
          <td class="data new_row">$getattr($time_tag, $x).sum.format(add_label=False)</td>
        #end for
      #elif $x in $obs_type_max
        #for $time_tag in $time_tags
          <td class="data new_row">
            $getattr($time_tag, $x).max.format(add_label=False)<br/>
            <span class="timestamp">$getattr($time_tag, $x).maxtime</span>
          </td>
        #end for
      #else
        #for $time_tag in $time_tags
          <td class="data new_row">
            $getattr($time_tag, $x).max.format(add_label=False)<br/>
            <span class="timestamp">$getattr($time_tag, $x).maxtime</span><br/>
            $getattr($time_tag, $x).min.format(add_label=False)<br/>
            <span class="timestamp">$getattr($time_tag, $x).mintime</span>
          </td>
        #end for
      #end if
        </tr>
    #end if
  #end if
#end for

      </tbody>
    </table>

  </div>
</div>
