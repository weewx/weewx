## statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $archive_data = [$day, $week, $month, $year, $rainyear]

## The list of observations determines which database fields will be shown in
## the summary as well as the order in which they will be displayed.
#set $observations = ['outTemp', 'heatindex', 'windchill', 'dewpoint', 'outHumidity', 'barometer', 'rain', 'rainRate', 'ET', 'hail', 'hailRate', 'snow', 'wind', 'UV', 'radiation', 'inTemp', 'inHumidity', 'extraTemp1', 'extraHumid1', 'extraTemp2', 'extraHumid2', 'extraTemp3', 'extraHumid3', 'extraTemp4', 'extraHumid4', 'extraTemp5', 'extraHumid5', 'extraTemp6', 'extraHumid6', 'extraTemp7', 'extraHumid7', 'extraTemp8', 'extraHumid8', 'leafTemp1', 'leafTemp2', 'leafWet1', 'leafWet2', 'soilTemp1', 'soilTemp2', 'soilTemp3', 'soilTemp4', 'soilMoist1', 'soilMoist2', 'soilMoist3', 'soilMoist4', 'pm1_0', 'pm2_5', 'pm10_0', 'co', 'co2', 'nh3', 'no2', 'o3', 'so2']

## Some observations display a sum rather than min/max values
#set $obs_sum = ['rain', 'ET', 'hail', 'snow']

## Some observations display only the max value
  #set $obs_max_only = ['rainRate', 'hailRate', 'snowRate', 'UV']

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
    #if $x == 'wind'
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
