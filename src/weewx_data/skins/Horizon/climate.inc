## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The panels of a climate page. climate.html.tmpl includes this file for the year in
## progress, and climate-%Y.html.tmpl for each year of the archive. On both pages
## '$year' is the year shown. Every panel reads from '$year' except climate-record,
## which lists every year of '$alltime'.
##
## ------------------------------------------------------------------ climate-days
##
## The kinds of day that the panel climate-days counts. 'agg' and 'value' are an
## aggregation type and its ValueTuple argument, as described under "Aggregation
## types" in the Reference Guide. The thresholds are in metric units because the
## definitions are metric, e.g., a summer day reaches 25 degree_C. A page in US units
## therefore shows the summer day's threshold as 77 degree_F.
#set $climate_days = [
  {'key': 'rain_day',     'obs': 'rain',     'agg': 'sum_ge',
   'value': (0.2, 'mm', 'group_rain')},
  {'key': 'summer_day',   'obs': 'outTemp',  'agg': 'max_ge',
   'value': (25.0, 'degree_C', 'group_temperature')},
  {'key': 'hot_day',      'obs': 'outTemp',  'agg': 'max_ge',
   'value': (30.0, 'degree_C', 'group_temperature')},
  {'key': 'desert_day',   'obs': 'outTemp',  'agg': 'max_ge',
   'value': (35.0, 'degree_C', 'group_temperature')},
  {'key': 'tropic_night', 'obs': 'outTemp',  'agg': 'min_ge',
   'value': (20.0, 'degree_C', 'group_temperature')},
  {'key': 'storm_day',    'obs': 'windGust', 'agg': 'max_ge',
   'value': (17.2, 'meter_per_second', 'group_speed')},
  {'key': 'ice_day',      'obs': 'outTemp',  'agg': 'max_le',
   'value': (0.0, 'degree_C', 'group_temperature')},
  {'key': 'frost_day',    'obs': 'outTemp',  'agg': 'min_le',
   'value': (0.0, 'degree_C', 'group_temperature')},
]
## A kind of day whose type has no data this year is left out, so that a station
## without a wind sensor shows no row of zero storm days.
#set $climate_days = [d for d in $climate_days
                      if $getVar('year.%s.has_data' % d['obs'], False)]
##
## The name and the definition of each kind of day, both translated. threshold_of()
## below fills in the '%s'.
#set $day_text = {
  'rain_day':     ($gettext("Rain days"),       $gettext("Daily rainfall at or above %s")),
  'summer_day':   ($gettext("Summer days"),     $gettext("Daily maximum at or above %s")),
  'hot_day':      ($gettext("Hot days"),        $gettext("Daily maximum at or above %s")),
  'desert_day':   ($gettext("Desert days"),     $gettext("Daily maximum at or above %s")),
  'tropic_night': ($gettext("Tropical nights"), $gettext("Daily minimum at or above %s")),
  'storm_day':    ($gettext("Storm days"),      $gettext("Gusts at or above %s")),
  'ice_day':      ($gettext("Ice days"),        $gettext("Daily maximum at or below %s")),
  'frost_day':    ($gettext("Frost days"),      $gettext("Daily minimum at or below %s")),
}
##
## The number of days of each kind in the year and in each month: one query on the
## daily summaries for the year, and one for each month.
#set $months_of_year = [m for m in $year.months]
#set $day_counts = {}
#set $day_months = {}
#for $spec in $climate_days
#set $of_year = $getattr($getattr($year, $spec['obs']), $spec['agg'])($spec['value'])
#silent $day_counts.__setitem__($spec['key'], $of_year)
## Inside the comprehension, 'spec' is written without '$'. On Python before 3.12 a
## comprehension runs in a frame of its own. Cheetah looks up a '$' name in that
## frame, which does not hold the template's '#set' and '#for' names, so the lookup
## fails with NotFound. Without '$', Python finds 'spec' in the template's frame on
## every version. The same holds for every '#set' or '#for' name inside a
## comprehension in this skin. Only the iterable after the first 'in', e.g.,
## '$months_of_year' below, may keep its '$', because Python evaluates that iterable
## in the template's frame.
##
## getattr() rather than $getVar(): $getVar() looks only in the searchList, and the
## month 'm' is a loop variable, which is not in it.
#set $per_month = [getattr(getattr(m, spec['obs']), spec['agg'])(spec['value'])
                   for m in $months_of_year]
#silent $day_months.__setitem__($spec['key'], $per_month)
#end for
##
#set $month_names = [m.dateTime.format("%b") for m in $months_of_year]
#from weewx.units import ValueTuple, convert
##
## threshold_of() returns the threshold of a kind of day as an element with
## 'data-value' and 'data-unit', like every other reading on the page. The threshold
## is converted to the report unit system and formatted with '$unit.format' for its
## type, and the unit picker can convert it further.
#def threshold_of($spec)
#set $obs = $spec['obs']
#set $vt = $ValueTuple(*$spec['value'])
#set $target = $getVar('unit.unit_type.%s' % $obs)
#set $shown = $convert($vt, $target)
#set $text = ($getVar('unit.format.%s' % $obs) % $shown[0])
#return '<span data-obs="%s" data-value="%s" data-unit="%s"><span data-unit-value>%s</span><small data-unit-label>%s</small></span>' % ($obs, $shown[0], $target, $text, $getVar('unit.label.%s' % $obs))
#end def
##
<section class="panel wide" data-live-panel="climate-days">
  <div class="panel-head">
    <h2>$gettext("Climatological days")</h2>
  </div>
  <div class="panel-body flush">
#if not $climate_days
    <p class="chart-empty">$gettext("No data for this period")</p>
#else
    <div class="table-scroll">
      <table class="data-table climate-days">
        <caption class="visually-hidden">$gettext("Climatological days")</caption>
        <thead>
          <tr>
            <th scope="col">$gettext("Kind of day")</th>
            <th scope="col" class="num">$gettext("Days")</th>
  #for $name in $month_names
            <th scope="col" class="num">$name</th>
  #end for
          </tr>
        </thead>
        <tbody>
  #for $spec in $climate_days
    #set $name, $wording = $day_text[$spec['key']]
          <tr>
            <th scope="row" class="metric">
              $name
              <span class="climate-rule">$(wording % $threshold_of($spec))</span>
            </th>
            <td class="num climate-total">$day_counts[$spec['key']].format(add_label=False)</td>
    #for $count in $day_months[$spec['key']]
      #set $n = $count.raw
            <td class="num#if not $n then ' climate-none' else ''#">#slurp
      #if $n then $count.format(add_label=False) else '&ndash;'#</td>
    #end for
          </tr>
  #end for
        </tbody>
      </table>
    </div>
#end if
  </div>
</section>

## --------------------------------------------------------------- climate-diagram
##
## A climate diagram after Walter and Lieth: each month's mean temperature as a line
## and its rainfall as bars. The rainfall axis has 2 mm for each degree_C, so a month
## whose bar stays below the line is dry.
#set $has_temp = $getVar('year.outTemp.has_data', False)
#set $has_rain = $getVar('year.rain.has_data', False)
## The monthly figures go into the script element at the end of this file, and are
## None where the type has no data; climate.js then leaves that part out. The figures
## are in degree_C and mm whatever the report unit system, because the diagram's 2:1
## ratio holds only in those units.
#set $month_temp = [m.outTemp.avg.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_low = [m.outTemp.min.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_high = [m.outTemp.max.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_rain = [m.rain.sum.mm.raw for m in $months_of_year] if $has_rain else None
## The daily figures for the heat map take one query for each series rather than one
## for each day. The script element gets the start times of the days as one list and
## the values of each series as another, because a series' own json() returns a
## string, which $jsonize would quote a second time.
#set $rain_series = $year.rain.series(aggregate_type='sum', aggregate_interval='day') if $has_rain else None
#set $daily_start = $rain_series.start.raw if $has_rain else None
#set $daily_rain = $rain_series.data.raw if $has_rain else None
##
## The monthly evapotranspiration for the water balance is in mm, like the monthly
## rain, so that climate.js can subtract one from the other.
#set $has_et = $getVar('year.ET.has_data', False)
#set $month_et = [m.ET.sum.mm.raw for m in $months_of_year] if $has_et else None
##
## The daily mean, lowest and highest temperature for the heat map.
#set $temp_series = $year.outTemp.series(aggregate_type='avg', aggregate_interval='day') if $has_temp else None
#set $tmin_series = $year.outTemp.series(aggregate_type='min', aggregate_interval='day') if $has_temp else None
#set $tmax_series = $year.outTemp.series(aggregate_type='max', aggregate_interval='day') if $has_temp else None
#set $daily_temp = $temp_series.data.raw if $has_temp else None
#set $daily_tmin = $tmin_series.data.raw if $has_temp else None
#set $daily_tmax = $tmax_series.data.raw if $has_temp else None
#set $daily_temp_start = $temp_series.start.raw if $has_temp else None
#if $has_temp or $has_rain
<section class="panel wide" data-live-panel="climate-diagram">
  <div class="panel-head">
    <h2>$gettext("The year's shape")</h2>
  </div>
  <div class="panel-body">
    <div id="climate-diagram" class="climate-chart"></div>
  </div>
</section>
#end if
##
## ----------------------------------------------------------------- climate-water
#if $has_rain and $has_et
<section class="panel wide" data-live-panel="climate-water">
  <div class="panel-head">
    <h2>$gettext("Water balance")</h2>
  </div>
  <div class="panel-body">
    <div id="climate-water" class="climate-chart"></div>
    <p class="climate-note">$gettext("Rainfall above the line, evapotranspiration below it. The line is what the ground kept.")</p>
  </div>
</section>
#end if
##
## --------------------------------------------------------------- climate-heatmap
##
## A heat map with one square for each day of the year, a column for each week and a
## row for each weekday. The tabs choose the type that the squares show.
#if $has_rain or $has_temp
  #set $heat_kinds = []
  #if $has_rain
    #silent $heat_kinds.append(('rain', $gettext("Rainfall")))
  #end if
  #if $has_temp
    #silent $heat_kinds.append(('temp', $gettext("Mean temperature")))
    #silent $heat_kinds.append(('tmin', $gettext("Lowest temperature")))
    #silent $heat_kinds.append(('tmax', $gettext("Highest temperature")))
  #end if
<section class="panel wide" data-live-panel="climate-heatmap">
  <div class="panel-head">
    <h2>$gettext("Day by day")</h2>
    <div class="tabs" id="heat-tabs" role="tablist" aria-label="$gettext('Metric')">
  #for $i, $kind in $enumerate($heat_kinds)
      <button type="button" role="tab" data-heat="$kind[0]"
              aria-selected="#if $i == 0 then 'true' else 'false'#">$kind[1]</button>
  #end for
    </div>
  </div>
  <div class="panel-body">
    <div id="climate-heatmap" class="climate-heatmap"></div>
  </div>
</section>
#end if
##
## ---------------------------------------------------------------- climate-record
##
## Every year of the archive, month by month, in one table for each type. Each cell
## is one query on the daily summaries, i.e., 13 for each year and type. WeeWX writes
## climate.html and the climate year page of the year in progress on every report
## cycle, and both pages run these queries each time.
#set $record_rows = [y for y in $alltime.years]
#if len($record_rows) > 0
  #set $matrix = [
    {'key': 'temp_avg', 'title': $gettext("Mean temperature"), 'obs': 'outTemp', 'agg': 'avg'},
    {'key': 'temp_min', 'title': $gettext("Lowest temperature"), 'obs': 'outTemp', 'agg': 'min'},
    {'key': 'temp_max', 'title': $gettext("Highest temperature"), 'obs': 'outTemp', 'agg': 'max'},
    {'key': 'rain_sum', 'title': $gettext("Rainfall"), 'obs': 'rain', 'agg': 'sum'},
    {'key': 'et_sum', 'title': $gettext("Evapotranspiration"), 'obs': 'ET', 'agg': 'sum'},
  ]
  #set $matrix = [x for x in $matrix if $getVar('alltime.%s.has_data' % x['obs'], False)]
<section class="panel wide" data-live-panel="climate-record">
  <div class="panel-head">
    <h2>$gettext("The whole archive")</h2>
    <div class="tabs" id="record-tabs" role="tablist" aria-label="$gettext('Metric')">
  #for $i, $spec in $enumerate($matrix)
      <button type="button" role="tab" data-record="$spec['key']"
              aria-selected="#if $i == 0 then 'true' else 'false'#">$spec['title']</button>
  #end for
    </div>
  </div>
  <div class="panel-body flush">
  #for $i, $spec in $enumerate($matrix)
    <div class="table-scroll" data-record-panel="$spec['key']"#if $i > 0 then ' hidden' else ''#>
      <table class="data-table climate-record">
        <caption class="visually-hidden">$spec['title']</caption>
        <thead>
          <tr>
            <th scope="col">$gettext("Year")
              <span class="climate-rule" data-obs="$spec['obs']"
                    data-unit="$getVar('unit.unit_type.%s' % $spec['obs'])"><small
                    data-unit-label>$getVar('unit.label.%s' % $spec['obs'])</small></span>
            </th>
    #for $name in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            <th scope="col" class="num">$gettext($name)</th>
    #end for
            <th scope="col" class="num">$gettext("Year")</th>
          </tr>
        </thead>
        <tbody>
    #for $y in $record_rows
          <tr>
            <th scope="row" class="metric">$y.dateTime.format("%Y")</th>
      #set $by_month = {}
      #for $m in $y.months
        #silent $by_month.__setitem__($int($m.dateTime.format("%m")),
                                      $getattr($getattr($m, $spec['obs']), $spec['agg']))
      #end for
      #set $cell_unit = $getVar('unit.unit_type.%s' % $spec['obs'])
      #for $mon in range(1, 13)
        #set $cell = $by_month.get($mon)
        #if $cell is None or $cell.raw is None
            <td class="num climate-none">&ndash;</td>
        #else
            <td class="num" data-obs="$spec['obs']" data-value="$cell.raw"
                data-unit="$cell_unit"><span data-unit-value>$cell.format(add_label=False)</span></td>
        #end if
      #end for
      #set $whole = $getattr($getattr($y, $spec['obs']), $spec['agg'])
            <td class="num climate-total"#if $whole.raw is not None then ' data-obs="%s" data-value="%s" data-unit="%s"' % ($spec['obs'], $whole.raw, $cell_unit) else ''#><span data-unit-value>$whole.format(add_label=False)</span></td>
          </tr>
    #end for
        </tbody>
      </table>
    </div>
  #end for
  </div>
</section>
#end if
##
## climate.js draws the charts from '$climate_data'. The data goes into the page
## rather than into a file of its own, because one year of months and days is only a
## few kilobytes.
#set $climate_data = {}
#silent $climate_data.update({'year': $int($climate_year), 'months': $month_names})
#silent $climate_data.update({'temp': $month_temp, 'tempLow': $month_low,
                              'tempHigh': $month_high, 'rain': $month_rain,
                              'et': $month_et})
#silent $climate_data.update({'tempLabel': $getVar('unit.label.outTemp', '').strip(),
                              'rainLabel': $getVar('unit.label.rain', '').strip()})
## 'tempBack' and 'rainBack' convert degree_C and mm to the report unit system, as
## [factor, offset], so that climate.js can label the charts in that unit system. Two
## points, 0 and 1, give the exact factor and offset, because both conversions are
## linear.
#set $t_unit = $getVar('unit.unit_type.outTemp')
#set $r_unit = $getVar('unit.unit_type.rain')
#set $t0 = $convert($ValueTuple(0.0, 'degree_C', 'group_temperature'), $t_unit)[0]
#set $t1 = $convert($ValueTuple(1.0, 'degree_C', 'group_temperature'), $t_unit)[0]
#set $r0 = $convert($ValueTuple(0.0, 'mm', 'group_rain'), $r_unit)[0]
#set $r1 = $convert($ValueTuple(1.0, 'mm', 'group_rain'), $r_unit)[0]
#silent $climate_data.update({'tempBack': [$t1 - $t0, $t0], 'rainBack': [$r1 - $r0, $r0]})
#silent $climate_data.update({'dayStart': $daily_start or $daily_temp_start,
                              'dayRain': $daily_rain, 'dayTemp': $daily_temp,
                              'dayMin': $daily_tmin, 'dayMax': $daily_tmax,
                              'weekStart': $station.week_start})
## The daily figures are in the report unit system, unlike the monthly ones.
## 'rainUnit' and 'tempUnit' name those units, so that the unit picker can convert
## the daily figures.
#silent $climate_data.update({'rainUnit': $getVar('unit.unit_type.rain', None),
                              'tempUnit': $getVar('unit.unit_type.outTemp', None)})
## The translated names that climate.js shows in its tooltips.
#silent $climate_data.update({'meanText': $gettext("Mean temperature"),
                              'rainText': $gettext("Rainfall"),
                              'etText': $gettext("Evapotranspiration"),
                              'keptText': $gettext("Water balance")})
## The script element has 'data-live-panel', so that horizon.js replaces the element
## on each new archive record like a panel, and climate.js redraws the charts from
## the new data.
<script id="climate-data" type="application/json"
        data-live-panel="climate-data">$jsonize($climate_data)</script>
