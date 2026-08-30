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
##
## Two helpers, so that every number in this table carries the reading behind it
## and the unit that reading is in. The unit picker converts whatever does.
#def stat_cell($vh, $obs)
#if $vh.raw is None
#return $vh.format(add_label=False)
#end if
#return '<span data-obs="%s" data-value="%s" data-unit="%s"><span data-unit-value>%s</span></span>' % ($obs, $vh.raw, $getVar('unit.unit_type.%s' % $obs), $vh.format(add_label=False))
#end def
#def stat_unit($obs)
#return '<span class="stat-unit" data-obs="%s" data-unit="%s"><small data-unit-label>%s</small></span>' % ($obs, $getVar('unit.unit_type.%s' % $obs), $getVar('unit.label.%s' % $obs).strip())
#end def


<section class="panel" data-live-panel="stats">
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
            <th scope="row" class="metric">$gettext("Max Wind") $stat_unit('windSpeed')</th>
      #for $timespan in $timespans
            <td class="num stat-hi" data-label="$gettext($timespan.capitalize())">$stat_cell($getVar($timespan).wind.max, 'windSpeed')
              <span class="when">$getVar($timespan).wind.maxtime</span>
            </td>
      #end for
          </tr>
          <tr>
            <th scope="row" class="metric">$gettext("Average Wind") $stat_unit('windSpeed')</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">$stat_cell($getVar($timespan).wind.avg, 'windSpeed')</td>
      #end for
          </tr>
    #elif $x in $obs_type_sum
          <tr>
            <th scope="row" class="metric">$obs.label[$x] $stat_unit($x)</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">$stat_cell($getVar('%s.%s.sum' % ($timespan, $x)), $x)</td>
      #end for
          </tr>
    #elif $x in $obs_type_max
          <tr>
            <th scope="row" class="metric">$obs.label[$x] $stat_unit($x)</th>
      #for $timespan in $timespans
            <td class="num stat-hi" data-label="$gettext($timespan.capitalize())">$stat_cell($getVar('%s.%s.max' % ($timespan, $x)), $x)
              <span class="when">$getVar('%s.%s.maxtime' % ($timespan, $x))</span>
            </td>
      #end for
          </tr>
    #else
          <tr>
            <th scope="row" class="metric">$obs.label[$x] $stat_unit($x)</th>
      #for $timespan in $timespans
            <td class="num" data-label="$gettext($timespan.capitalize())">
              <span class="stat-pair"><span class="stat-hi">$stat_cell($getVar('%s.%s.max' % ($timespan, $x)), $x)</span><span class="when">$getVar('%s.%s.maxtime' % ($timespan, $x))</span></span>
              <span class="stat-slash">/</span>
              <span class="stat-pair"><span class="stat-lo">$stat_cell($getVar('%s.%s.min' % ($timespan, $x)), $x)</span><span class="when">$getVar('%s.%s.mintime' % ($timespan, $x))</span></span>
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
