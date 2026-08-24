## summary statistics module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

#set $timespans = ['day', 'week', 'month', 'year']
#set $observations = $to_list($DisplayOptions.get('observations_stats', ['outTemp', 'windSpeed', 'rain']))
#set $obs_type_sum = $to_list($DisplayOptions.get('obs_type_sum', ['rain']))
#set $obs_type_max = $to_list($DisplayOptions.get('obs_type_max', ['rainRate']))

## Use a recent span to decide whether an observation is worth a row at all.
#set $recent = $span($day_delta=30, boundary='midnight')

<section class="panel">
  <div class="panel-head">
    <h2><a href="statistics.html">$gettext("Statistics")</a></h2>
  </div>
  <div class="panel-body flush">
    <div class="table-scroll">
      <table class="data-table stats">
        <caption class="visually-hidden">$gettext("Minimum and maximum values by time span")</caption>
        <thead>
          <tr>
            <th scope="col">$gettext("Metric")</th>
#for $timespan in $timespans
            <th scope="col">$gettext($timespan.capitalize())</th>
#end for
          </tr>
        </thead>
        <tbody>

#for $x in $observations
  #if $getattr($recent, $x, None) and $getattr($recent, $x).has_data
    #if $x == 'windSpeed'
          <tr>
            <th scope="row" class="metric">$gettext("Max Wind")</th>
      #for $timespan in $timespans
            <td class="num stat-hi" data-label="$gettext($timespan.capitalize())">$getVar($timespan).wind.max.format(add_label=False)
              <span class="when">$getVar($timespan).wind.maxtime</span>
            </td>
      #end for
          </tr>
          <tr>
            <th scope="row" class="metric">$gettext("Average Wind")</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">$getVar($timespan).wind.avg.format(add_label=False)</td>
      #end for
          </tr>
    #elif $x in $obs_type_sum
          <tr>
            <th scope="row" class="metric">$obs.label[$x]</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">$getVar('%s.%s.sum' % ($timespan, $x)).format(add_label=False)</td>
      #end for
          </tr>
    #elif $x in $obs_type_max
          <tr>
            <th scope="row" class="metric">$obs.label[$x]</th>
      #for $timespan in $timespans
            <td class="num stat-hi" data-label="$gettext($timespan.capitalize())">$getVar('%s.%s.max' % ($timespan, $x)).format(add_label=False)
              <span class="when">$getVar('%s.%s.maxtime' % ($timespan, $x))</span>
            </td>
      #end for
          </tr>
    #else
          <tr>
            <th scope="row" class="metric">$obs.label[$x]</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">
              <span class="stat-hi">$getVar('%s.%s.max' % ($timespan, $x)).format(add_label=False)</span> /
              <span class="stat-lo">$getVar('%s.%s.min' % ($timespan, $x)).format(add_label=False)</span>
              <span class="when">$getVar('%s.%s.maxtime' % ($timespan, $x))</span>
            </td>
      #end for
          </tr>
    #end if
  #end if
#end for

        </tbody>
      </table>
    </div>
  </div>
</section>
