## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## One year, read as climate rather than as weather. The other pages answer "what is
## it doing now"; this one answers "what kind of year was it".
##
## Included by two templates. climate.html.tmpl renders the year in progress on every
## report cycle. climate/climate-%Y.html.tmpl renders one page per year, and WeeWX
## writes a year that has ended only once, so a station with a long record does not
## pay for its history every five minutes. Both leave $year on the year being shown,
## so everything below reads from $year and works either way.
##
## The counted days. Each is a name, an observation, an aggregate and a threshold.
##
##   agg   how the counting is done. WeeWX counts days four ways: max_ge, max_le,
##         min_ge and min_le test the daily maximum or minimum, and sum_ge tests the
##         daily total.
##
## The thresholds are metric whatever the station records in, because that is how the
## definitions read: a summer day is 25 C, and 77 F is the same day under another
## name. WeeWX converts.
## The threshold is a full ValueTuple, (number, unit, group). Two of the three would
## be enough to convert it, but weewx.xtypes reads the group as well.
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
## What the station does not record is left out, so a station without a wind sensor
## shows no storm days rather than a row of zeroes.
##
## No '$' on the loop variable inside the filter. Cheetah would look the name up in
## the calling frame, and until Python 3.12 a comprehension has a frame of its own
## that a '#set' never reaches. Plain Python finds it through the closure, on every
## version. The same rule applies to every comprehension in this skin.
#set $climate_days = [d for d in $climate_days
                      if $getVar('year.%s.has_data' % d['obs'], False)]
##
## The name and the wording of the definition, one entry each, so a translation
## reaches both. The threshold itself is filled in below, formatted by the skin.
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
## Count them. One query against the daily summaries for the year, twelve more for the
## months. Done once here and read twice below, rather than asked again per table.
##
## getattr() twice rather than $getVar(): the month is a loop variable, and getVar
## resolves names against the template's namespace, which a loop variable is not part
## of.
#set $months_of_year = [m for m in $year.months]
#set $day_counts = {}
#set $day_months = {}
#for $spec in $climate_days
#set $of_year = $getattr($getattr($year, $spec['obs']), $spec['agg'])($spec['value'])
#silent $day_counts.__setitem__($spec['key'], $of_year)
## Neither name carries a '$'. Both are resolved inside the comprehension's own
## frame, which a Cheetah '#set' does not reach before Python 3.12. This is the same
## trap that cost a release on 3.7 once already.
#set $per_month = [getattr(getattr(m, spec['obs']), spec['agg'])(spec['value'])
                   for m in $months_of_year]
#silent $day_months.__setitem__($spec['key'], $per_month)
#end for
##
## The months that exist in this year, as short names for the column headings.
#set $month_names = [m.dateTime.format("%b") for m in $months_of_year]
##
## The thresholds are shown in whatever unit the page is written in, so a station
## reporting Fahrenheit reads its summer day as 77 rather than 25. The definition
## stays 25 C. This is the same temperature under the name its reader uses.
##
## $unit.unit_type, $unit.format and $unit.label say what the skin does with that
## observation, so the threshold comes out looking like every other reading on the
## page rather than like a number from the code.
#from weewx.units import ValueTuple, convert
## The threshold, as an element rather than as a number inside a sentence. It carries
## the reading the way every other reading on the page does, so the unit picker
## reaches it: 25 C stays 25 C when the reader asks for Celsius, and reads 77 F when
## they ask for Fahrenheit.
#def threshold_of($spec)
#set $obs = $spec['obs']
#set $vt = $ValueTuple(*$spec['value'])
#set $target = $getVar('unit.unit_type.%s' % $obs)
#set $shown = $convert($vt, $target)
#set $text = ($getVar('unit.format.%s' % $obs) % $shown[0])
#return '<span data-obs="%s" data-value="%s" data-unit="%s"><span data-unit-value>%s</span><small data-unit-label>%s</small></span>' % ($obs, $shown[0], $target, $text, $getVar('unit.label.%s' % $obs))
#end def
##
<section class="panel" data-live-panel="climate-days">
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

## ---------------------------------------------------------------- the year's shape
##
## A climate diagram: the month's mean temperature as a line, the month's rainfall as
## bars behind it. The two share one picture because that is the pair that describes a
## climate, and the shape of the pair is what a reader recognises.
##
## The rainfall axis runs at twice the temperature axis, which is Walter and Lieth's
## convention: where the rain bar falls below the temperature line, the month is dry.
## That crossing is the whole point of drawing them together.
#set $has_temp = $getVar('year.outTemp.has_data', False)
#set $has_rain = $getVar('year.rain.has_data', False)
## Gathered here, before the first panel, because the script block at the end of the
## file reads the same lists. None where the station does not record it, which the
## page reads as "leave that part out".
## In degrees Celsius and millimetres, whatever the page reads in. The climate
## diagram below is defined on those units: Walter and Lieth draw the rainfall axis
## at twice the temperature axis, which is 10 degrees against 20 mm. Plot Fahrenheit
## against inches at 2:1 and the crossing that makes the diagram readable lands
## somewhere else entirely.
##
## The axis labels are converted back, so the reader still sees the unit they set.
#set $month_temp = [m.outTemp.avg.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_low = [m.outTemp.min.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_high = [m.outTemp.max.degree_C.raw for m in $months_of_year] if $has_temp else None
#set $month_rain = [m.rain.sum.mm.raw for m in $months_of_year] if $has_rain else None
## Two lists rather than the SeriesHelper's own JSON: that method returns a string,
## which $jsonize would then quote a second time. The start of each day and the total
## for it is all the picture needs.
#set $rain_series = $year.rain.series(aggregate_type='sum', aggregate_interval='day') if $has_rain else None
#set $daily_start = $rain_series.start.raw if $has_rain else None
## The heatmap has no ratio to honour, so its days stay in the unit the page reads in.
#set $daily_rain = $rain_series.data.raw if $has_rain else None
##
## What fell against what left again. Rain minus evapotranspiration is the water the
## ground actually kept, which is the figure a garden runs on and the one no other
## page here shows. In millimetres, like the diagram above, so that the two pictures
## agree with each other.
#set $has_et = $getVar('year.ET.has_data', False)
#set $month_et = [m.ET.sum.mm.raw for m in $months_of_year] if $has_et else None
##
## The other three the calendar can show. One query each, the same as the rain, and
## the reader picks between them. A year of daily figures is 365 numbers.
#set $temp_series = $year.outTemp.series(aggregate_type='avg', aggregate_interval='day') if $has_temp else None
#set $tmin_series = $year.outTemp.series(aggregate_type='min', aggregate_interval='day') if $has_temp else None
#set $tmax_series = $year.outTemp.series(aggregate_type='max', aggregate_interval='day') if $has_temp else None
#set $daily_temp = $temp_series.data.raw if $has_temp else None
#set $daily_tmin = $tmin_series.data.raw if $has_temp else None
#set $daily_tmax = $tmax_series.data.raw if $has_temp else None
#set $daily_temp_start = $temp_series.start.raw if $has_temp else None
#if $has_temp or $has_rain
<section class="panel" data-live-panel="climate-diagram">
  <div class="panel-head">
    <h2>$gettext("The year's shape")</h2>
  </div>
  <div class="panel-body">
    <div id="climate-diagram" class="climate-chart"></div>
  </div>
</section>
#end if
##
## ------------------------------------------------------------- the water balance
##
## Only where the station records evapotranspiration. Most do not: it is computed
## from radiation, wind and humidity, and a station without those sensors has no
## figure to show.
#if $has_rain and $has_et
<section class="panel" data-live-panel="climate-water">
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
## ------------------------------------------------------------------- day by day
##
## One square per day of the year, laid out as the calendar lays them out: a column
## per week, a row per weekday. A year of weather in one picture, at the only
## resolution where a single day is still visible.
##
## The series is one query. Asking the daily summaries day by day would be 365.
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
<section class="panel" data-live-panel="climate-heatmap">
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
## ------------------------------------------------------------- the whole record
##
## Every year the station has run, month by month. This is the table that answers
## "was this August unusual", which none of the other pages can: they all end at the
## last reading.
##
## Cost: one query per cell. A station with fourteen years pays 168 of them per
## figure, against the daily summaries, once per report cycle for the year in
## progress. The years that have ended are written once and skipped after that.
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
<section class="panel" data-live-panel="climate-record">
  <div class="panel-head">
    <h2>$gettext("The whole record")</h2>
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
## What the two pictures above are drawn from. Written here rather than fetched,
## because it is one year of months and one year of days: a few kilobytes, and the
## page already had to read them to render the tables.
#set $climate_data = {}
#silent $climate_data.update({'year': $int($climate_year), 'months': $month_names})
#silent $climate_data.update({'temp': $month_temp, 'tempLow': $month_low,
                              'tempHigh': $month_high, 'rain': $month_rain,
                              'et': $month_et})
#silent $climate_data.update({'tempLabel': $getVar('unit.label.outTemp', '').strip(),
                              'rainLabel': $getVar('unit.label.rain', '').strip()})
## From Celsius and millimetres back to whatever the page reads in, as a factor and
## an offset. Measured at 0 and at 1, which is exact for a conversion that is linear,
## and every one of these is.
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
## Which unit each of those is in, so the page can show them in another. The daily
## figures are in the unit the report was rendered in, unlike the monthly ones above.
#silent $climate_data.update({'rainUnit': $getVar('unit.unit_type.rain', None),
                              'tempUnit': $getVar('unit.unit_type.outTemp', None)})
## What the tooltips call each figure. In the page's language, like everything else.
#silent $climate_data.update({'meanText': $gettext("Mean temperature"),
                              'rainText': $gettext("Rainfall"),
                              'etText': $gettext("Evapotranspiration"),
                              'keptText': $gettext("Water balance")})
## 'data-live-panel' on a script tag: the live update replaces it like any other
## marked element, which is what carries the new day into the pictures below.
<script id="climate-data" type="application/json"
        data-live-panel="climate-data">$jsonize($climate_data)</script>
