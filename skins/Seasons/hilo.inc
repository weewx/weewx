## summary statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $archive_data = [('day', $day), ('week', $week), ('month', $month), ('year', $year), ('rainyear', $rainyear)]

## Get the list of observations from the configuration file, otherwise fallback
## to a very rudimentary set of observations.
#if 'observations' in $Extras
#set $observations = $Extras.observations
#set $obs_sum = $Extras.obs_sum
#set $obs_max_only = $Extras.obs_max_only
#else
#set $observations = ['outTemp', 'windSpeed', 'rain']
#set $obs_sum = ['rain']
#set $obs_max_only = ['rainRate']
#end if

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
  #if $getattr($year, $x).has_data
    #if $x == 'windSpeed'
      <tr>
        <td class="label">$gettext("Max Wind")</td>
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
        <td class="label">$gettext("Average Wind")</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].wind.avg.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>
      <tr>
        <td class="label">$gettext("RMS Wind")</td>
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $archive[1].wind.rms.format(add_label=False)</td>
        #end for
        <td class="units">$unit.label.wind</td>
      </tr>

      <tr>
        <td class="label">
          $gettext("Vector Average")<br/>
          $gettext("Vector Direction")
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
    #else
      <tr>
        <td class="label">$obs.label[$x]</td>
      #if $x in $obs_sum
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          $getattr($archive[1], $x).sum.format(add_label=False)</td>
        #end for
      #elif $x in $obs_max_only
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$getattr($archive[1], $x).maxtime">
            $getattr($archive[1], $x).max.format(add_label=False)</span>
        </td>
        #end for
      #else
        #for $archive in $archive_data
        <td class="data new_row hilo_$archive[0]">
          <span title="$getattr($archive[1], $x).maxtime">
            $getattr($archive[1], $x).max.format(add_label=False)</span><br/>
          <span title="$getattr($archive[1], $x).mintime">
            $getattr($archive[1], $x).min.format(add_label=False)</span>
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
