## statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $archive_data = [$day, $week, $month, $year, $rainyear]

## Get the list of observations from the configuration file, otherwise fallback
## to a very rudimentary set of observations.
#if $Extras.has_key('observations')
#set $observations = $Extras.observations
#set $obs_sum = $Extras.obs_sum
#set $obs_max_only = $Extras.obs_max_only
#else
#set $observations = ['outTemp', 'windSpeed', 'rain']
#set $obs_sum = ['rain']
#set $obs_max_only = ['rainRate']
#end if

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
  #if $getattr($year, $x).has_data
    #if $x == 'windSpeed'
        <tr>
          <td class="label">$gettext("Max Wind")</td>
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
          <td class="label">$gettext("Average Wind")</td>
          <td class="units">$unit.label.wind</td>
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.wind.avg.format(add_label=False)</td>
          #end for
        </tr>
        <tr>
          <td class="label">$gettext("RMS Wind")</td>
          <td class="units">$unit.label.wind</td>
          #for $archive in $archive_data
          <td class="data new_row">$archive.wind.rms.format(add_label=False)</td>
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
          #for $archive in $archive_data
          <td class="data new_row">
            $archive.wind.vecavg.format(add_label=False)<br/>
            $archive.wind.vecdir.format(add_label=False)
          </td>
          #end for
        </tr>
    #else
        <tr>
          <td class="label">$obs.label[$x]</td>
          <td class="units">$getattr($unit.label, $x, '')</td>
      #if $x in $obs_sum
        #for $archive in $archive_data
          <td class="data new_row">$getattr($archive, $x).sum.format(add_label=False)</td>
        #end for
      #elif $x in $obs_max_only
        #for $archive in $archive_data
          <td class="data new_row">
            $getattr($archive, $x).max.format(add_label=False)<br/>
            <span class="timestamp">$getattr($archive, $x).maxtime</span>
          </td>
        #end for
      #else
        #for $archive in $archive_data
          <td class="data new_row">
            $getattr($archive, $x).max.format(add_label=False)<br/>
            <span class="timestamp">$getattr($archive, $x).maxtime</span><br/>
            $getattr($archive, $x).min.format(add_label=False)<br/>
            <span class="timestamp">$getattr($archive, $x).mintime</span>
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
