## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## One card, read from the top: what it is, how warm, where that sits in the day,
## and then everything else in two quiet columns. The reading leads because it is
## what anyone came for; the rest is the same size as itself and does not compete.
##
## What the card shows, and in what order.
##
##   dashboard_lead     the one reading set large at the top
##   dashboard_readings the rows underneath
##
## Where neither option is set, the card falls back to the lists the skin already
## keeps, so a configuration that names neither still gets a sensible card. The
## 'has_data' test drops the rest: a station with no UV sensor never shows that row,
## and nobody has to maintain a second list of what is fitted.
#set $headline = $to_list($DisplayOptions.get('observations_headline', ['outTemp']))
#set $lead = $DisplayOptions.get('dashboard_lead') or ($headline and $headline[0]) or 'outTemp'
#set $wanted = $to_list($DisplayOptions.get('dashboard_readings',
                        $DisplayOptions.get('observations_current', ['outTemp', 'barometer'])))
## 'lead' carries no '$' on purpose. Cheetah would look the name up in the calling
## frame, and until Python 3.12 a comprehension has a frame of its own, which a
## '#set' never reaches. Plain Python finds it through the closure, everywhere.
#set $rest = [$x for $x in $wanted if $x != lead and $getVar('year.%s.has_data' % $x, False)]
## Rain is three readings of one thing: how much today, how hard right now, and
## the hardest it came down. Three rows of mostly zeroes said that badly.
#set $has_rain = 'rain' in $rest
#set $rest = [$x for $x in $rest if $x not in ('rain', 'rainRate')]
##
## A glyph for each reading, from 'icons/'. Only a hint at what the row is about,
## so a reading with no icon of its own simply has none: the label already says
## what it is. Override or extend the list under [DisplayOptions] [[Icons]].
#set $icon_map = {'outTemp': 'temp', 'inTemp': 'temp', 'dewpoint': 'dew-point',
                  'outHumidity': 'humidity', 'inHumidity': 'humidity',
                  'barometer': 'barometer', 'pressure': 'barometer',
                  'windSpeed': 'wind-speed', 'windGust': 'wind-gust',
                  'windchill': 'wind-chill', 'heatindex': 'heat-index',
                  'appTemp': 'app-temp', 'rain': 'rain', 'rainRate': 'rain-rate',
                  'radiation': 'radiation', 'UV': 'uv', 'ET': 'et',
                  'cloudbase': 'cloud-base', 'soilTemp1': 'soil-temp',
                  'soilMoist1': 'soil-moist', 'leafWet1': 'leaf',
                  'lightning_strike_count': 'lightning', 'snowDepth': 'snow'}
#silent $icon_map.update($DisplayOptions.get('Icons', {}))
##
## What each reading did over the longer spans, written into the card so that the
## page can show a week or a year without fetching anything. Three numbers each:
## the mean, and the two ends. The mean is what a card shows for a span -- the
## reading at this instant means nothing once the span is longer than a day.
##
## Raw values, in the unit the database keeps. The page converts them the same way
## it converts everything else, through 'data-value' and 'data-unit'.
#set $spans = {}
#for $obs in $rest + [$lead] + ($has_rain and ['rain'] or [])
  #set $found = {}
  #for $name in ('week', 'month', 'year')
    #set $stats = $getVar('%s.%s' % ($name, $obs), None)
    #if $stats is not None
      #if $obs in ('rain', 'ET')
        #if $stats.sum.raw is not None
          #silent $found[$name] = {'v': round($stats.sum.raw, 4), 'lo': None, 'hi': None}
        #end if
## The wind over a span is three different things, and none of them is the
## reading at this instant. The mean is how windy it was; the highest is the
## number anyone remembers; and the direction that matters is the one it mostly
## came from, which is the vector mean rather than where the vane points now.
      #else if $obs == 'windSpeed'
        #set $vec = $getVar('%s.wind' % $name, None)
        #if $vec is not None and $vec.avg.raw is not None
          #silent $found[$name] = {'v': round($vec.avg.raw, 4), 'lo': None,
                                   'hi': $vec.max.raw is None and None or round($vec.max.raw, 4),
                                   'dir': $str($vec.vecdir.ordinal_compass)}
        #end if
      #else if $stats.avg.raw is not None
        #set $lo_raw = $stats.min.raw
        #set $hi_raw = $stats.max.raw
        #silent $found[$name] = {'v': round($stats.avg.raw, 4),
                                 'lo': $lo_raw is None and None or round($lo_raw, 4),
                                 'hi': $hi_raw is None and None or round($hi_raw, 4)}
      #end if
    #end if
  #end for
  #silent $spans[$obs] = $found
#end for
##
<section class="panel headline" data-live-panel="current" aria-label="$gettext('Current Conditions')">
#if $getVar('year.%s.has_data' % $lead, False)
  <div class="lead-block">
  <h2 class="lead-label">$getVar('obs.label.%s' % $lead)</h2>

  ## The reading. Whole units large, the decimal smaller and hung from the same
  ## top edge, the unit beside it, the direction after. The colour band is in
  ## degrees C whatever the page displays in, so the same weather is the same
  ## colour in Fahrenheit.
  #set $lead_vh = $getVar('current.%s' % $lead)
  #set $shown = $lead_vh.format(add_label=False)
  #set $cut = -1
  #for $i, $ch in enumerate($shown)
    #if $ch in ',.'
      #set $cut = $i
    #end if
  #end for
  #set $band = ''
  #if $lead == 'outTemp' and $current.outTemp.degree_C.raw is not None
    #set $edges = [-10, 0, 5, 12, 18, 23, 28, 33]
    #set $band = ' data-band="%d"' % len([$e for $e in $edges if $current.outTemp.degree_C.raw >= $e])
  #end if
  ## 'data-value' and 'data-unit' carry the reading as the database holds it, so the
  ## page can show it in another unit without asking the server for it again. The
  ## text between the tags is what a reader without JavaScript sees.
  <div class="lead">
  #if $lead in $icon_map
    <span class="tile-icon" style="--icon:url(icons/${icon_map[$lead]}.svg)" aria-hidden="true"></span>
  #end if
    <span class="lead-value"$band data-live="$lead"
          data-spans='$jsonize($spans.get($lead, {}))'
          data-value="$lead_vh.raw" data-unit="$getVar('unit.unit_type.%s' % $lead)">#slurp
  #if $cut > 0
$shown[:$cut]<span class="lead-dec">$shown[$cut:]</span>#slurp
  #else
$shown#slurp
  #end if
</span>
    <span class="lead-unit" data-unit-label>$getVar('unit.label.%s' % $lead)</span>
  #set $tr = $getVar('trend.%s' % $lead, None)
  #if $tr is not None and $tr.raw is not None
    #set $step = $lead == 'barometer' and 0.6 or 0.3
    #set $dir = $tr.raw > $step and 'up' or ($tr.raw < -$step and 'down' or 'flat')
    <svg class="lead-trend trend-$dir" viewBox="0 0 24 24" aria-hidden="true"><title>$tr.formatted $gettext("in 3h")</title><path d="M12 20 L12 4 M5 11 L12 4 L19 11"/></svg>
  #end if
  </div>

  ## Where today has been, and where in that the reading sits now.
  #set $lead_day = $getVar('day.%s' % $lead)
  #set $lo_vt = $lead_day.min
  #set $hi_vt = $lead_day.max
  #if $lo_vt.raw is not None and $hi_vt.raw is not None and $hi_vt.raw > $lo_vt.raw
    #set $now_raw = $lead_vh.raw
    ## The track is the scale, the fill is what has been measured inside it. They
    ## are the same thing today, since the day's own range is all there is. Kept
    ## apart anyway: a forecast would go in the same track, and then they are not.
  <h3 class="span-title">$gettext("Today")</h3>
    ## The track carries its own range in degrees C, so the script can colour it by
    ## the weather it is showing rather than by a fixed sweep. Celsius whatever the
    ## page displays in, so the same weather is the same colour in Fahrenheit.
    #set $span_data = ''
    #if $lead == 'outTemp' and $lead_day.min.degree_C.raw is not None
      #set $span_data = ' data-lo="%.2f" data-hi="%.2f"' % ($lead_day.min.degree_C.raw,
                                                            $lead_day.max.degree_C.raw)
      #if $current.outTemp.degree_C.raw is not None
        #set $span_data = $span_data + ' data-now="%.2f"' % $current.outTemp.degree_C.raw
      #end if
    #end if
  <div class="span-today">
    <div class="span-track"$span_data>
      <span class="span-fill" style="left:0%;width:100%"></span>
    #if $now_raw is not None
      #set $at = max(0.0, min(100.0, ($now_raw - $lo_vt.raw) / ($hi_vt.raw - $lo_vt.raw) * 100.0))
      <span class="span-now" style="left:${'%.1f' % $at}%"></span>
    #end if
    </div>
    <div class="span-ends">
      <span class="span-end" data-value="$lo_vt.raw" data-obs="$lead"
            data-unit="$getVar('unit.unit_type.%s' % $lead)"><b data-unit-value>$lo_vt.format(add_label=False)</b><small data-unit-label>$getVar('unit.label.%s' % $lead)</small>
            <span class="faint">$lead_day.mintime.format("%H:%M")</span></span>
      <span class="span-caption">$gettext("measured")</span>
      <span class="span-end span-end--right" data-value="$hi_vt.raw" data-obs="$lead"
            data-unit="$getVar('unit.unit_type.%s' % $lead)"><b data-unit-value>$hi_vt.format(add_label=False)</b><small data-unit-label>$getVar('unit.label.%s' % $lead)</small>
            <span class="faint">$lead_day.maxtime.format("%H:%M")</span></span>
    </div>
  </div>
  #end if
#end if

  ## The same range the other readings carry, for the one that leads them.
#set $lead_lo = $getVar('day.%s.min' % $lead, None)
#set $lead_hi = $getVar('day.%s.max' % $lead, None)
#if $lead_lo is not None and $lead_hi is not None and $lead_lo.raw is not None and $lead_hi.raw is not None
  <div class="tile-range">
    <span><span class="range-key">$gettext("Min")</span> <span data-obs="$lead"
          data-range="lo" data-value="$lead_lo.raw" data-unit="$getVar('unit.unit_type.%s' % $lead)"><span
          data-unit-value>$lead_lo.format(add_label=False)</span><small data-unit-label>$getVar('unit.label.%s' % $lead)</small></span></span>
    <span><span class="range-key">$gettext("Max")</span> <span data-obs="$lead"
          data-range="hi" data-value="$lead_hi.raw" data-unit="$getVar('unit.unit_type.%s' % $lead)"><span
          data-unit-value>$lead_hi.format(add_label=False)</span><small data-unit-label>$getVar('unit.label.%s' % $lead)</small></span></span>
  </div>
#end if
  </div>

  ## Everything else, two columns, all the same weight.
  <dl class="companions">
#for $x in $rest
    <div>
  #if $x == 'windSpeed'
      <dt>$getVar('obs.label.wind')</dt>
      <dd data-live="windSpeed" data-value="$current.windSpeed.raw"
          data-spans='$jsonize($spans.get('windSpeed', {}))'
          data-unit="$unit.unit_type.windSpeed"><span data-unit-value>$current.windSpeed.format(add_label=False)</span><small data-unit-label>$unit.label.windSpeed</small>
    #if $current.windDir.raw is not None
        <span class="faint wind-now">$current.windDir.ordinal_compass</span>
    #end if
      </dd>
  #elif $x == 'rain'
      <dt>$gettext("Rain Today")</dt>
      <dd data-live="rainToday" data-obs="rain" data-value="$day.rain.sum.raw"
          data-unit="$unit.unit_type.rain"><span data-unit-value>$day.rain.sum.format(add_label=False)</span><small data-unit-label>$unit.label.rain</small></dd>
  #else
      <dt>$getVar('obs.label.%s' % $x)</dt>
    #set $vh = $getVar('current.%s' % $x)
      <dd data-live="$x" data-value="$vh.raw"
          data-spans='$jsonize($spans.get($x, {}))'
          data-unit="$getVar('unit.unit_type.%s' % $x)">
    #if $x in $icon_map
        <span class="tile-icon" style="--icon:url(icons/${icon_map[$x]}.svg)" aria-hidden="true"></span>
    #end if
        <span data-unit-value>$vh.format(add_label=False)</span><small data-unit-label>$getVar('unit.label.%s' % $x)</small>
      #set $tr = $getVar('trend.%s' % $x, None)
      #if $tr is not None and $tr.raw is not None
        #set $step = $x == 'barometer' and 0.6 or 0.3
        #set $dir = $tr.raw > $step and 'up' or ($tr.raw < -$step and 'down' or 'flat')
        <svg class="trend trend-$dir" viewBox="0 0 24 24" aria-hidden="true"><title>$tr.formatted $gettext("in 3h")</title><path d="M12 20 L12 4 M5 11 L12 4 L19 11"/></svg>
      #end if
      </dd>
      ## How far the reading has been today. A number on its own says nothing about
      ## whether it is high or low for the day; these two do.
      #set $lo = $getVar('day.%s.min' % $x, None)
      #set $hi = $getVar('day.%s.max' % $x, None)
      #if $lo is not None and $hi is not None and $lo.raw is not None and $hi.raw is not None
      <dd class="tile-range">
        <span><span class="range-key">$gettext("Min")</span>
        <span data-obs="$x" data-range="lo" data-value="$lo.raw" data-unit="$getVar('unit.unit_type.%s' % $x)">
          <span data-unit-value>$lo.format(add_label=False)</span><small data-unit-label>$getVar('unit.label.%s' % $x)</small></span>
        </span>
        <span><span class="range-key">$gettext("Max")</span> <span data-obs="$x" data-range="hi" data-value="$hi.raw" data-unit="$getVar('unit.unit_type.%s' % $x)">
          <span data-unit-value>$hi.format(add_label=False)</span><small data-unit-label>$getVar('unit.label.%s' % $x)</small></span>
        </span>
      </dd>
      #end if
    #end if
    </div>
#end for
#if $has_rain
    <div>
      <dt data-label-day="$gettext('Rain Today')"
          data-label-span="$getVar('obs.label.rain')">$gettext("Rain Today")</dt>
      <dd data-live="rainToday" data-obs="rain" data-value="$day.rain.sum.raw"
          data-spans='$jsonize($spans.get('rain', {}))'
          data-unit="$unit.unit_type.rain"><span data-unit-value>$day.rain.sum.format(add_label=False)</span><small data-unit-label>$unit.label.rain</small></dd>
  #if $getVar('year.rainRate.has_data', False)
      <dd class="sub-reading" data-value="$current.rainRate.raw" data-obs="rainRate"
          data-unit="$unit.unit_type.rainRate"><span data-unit-value>$current.rainRate.format(add_label=False)</span><small data-unit-label>$unit.label.rainRate</small>#slurp
    #if $day.rainRate.max.raw
       &middot; $gettext("max") $day.rainRate.max.format(add_label=False)#slurp
    #end if
      </dd>
  #end if
    </div>
#end if
  </dl>
</section>
