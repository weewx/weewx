## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## Current conditions: one tile for each type in 'observations_current', in that
## order, except that the rain tile comes last. A tile shows the reading and, where
## they exist, the day's low and high and the trend over the last three hours. A type
## without data this year gets no tile.
#set $wanted = $to_list($DisplayOptions.get('observations_current', ['outTemp', 'barometer']))
#set $shown = [$x for $x in $wanted if $getVar('year.%s.has_data' % $x, False)]
## 'rain' gets one tile, with today's total, which comes last whatever the order in
## 'observations_current'. The rain tile also shows the current 'rainRate' when the
## station has rain rate data this year. 'rainRate' gets no tile of its own.
#set $tiles = [$x for $x in $shown if $x not in ('rain', 'rainRate')]
#if 'rain' in $shown
  #silent $tiles.append('rain')
#end if
##
## The icon of each type, a file name in 'icons/' without '.svg'. A type without an
## entry gets no icon. [[Icons]] under [DisplayOptions] adds entries or replaces them.
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
## Each tile carries, as 'data-spans', its figures for the week, the month and the
## year so far, so that horizon.js can switch the time span without fetching anything.
## For outTemp:
##
##   {"week": {"v": 39.53, "t": "39.5", "lo": 18.54, "lot": "18.5",
##             "hi": 61.63, "hit": "61.6"}, "month": {...}, "year": {...}}
##
## 'v', 'lo' and 'hi' are the mean, the low and the high as numbers in the unit that
## 'data-unit' names; 't', 'lot' and 'hit' are the same figures as the report formats
## them. Rain and any type in 'obs_type_sum' have only 'v' and 't', the total. A time
## span without data is left out, and the tile then keeps showing the day's figures.
#set $sums = $to_list($DisplayOptions.get('obs_type_sum', ['rain']))
#set $spans = {}
#for $x in $tiles
  #set $found = {}
  #for $name in ('week', 'month', 'year')
## For the wind, 'v' and 't' are the mean speed, and 'dir' is the compass point of
## the vector averaged direction ('vecdir').
    #if $x == 'windSpeed'
      #set $vec = $getVar('%s.wind' % $name, None)
      #if $vec is not None and $vec.avg.raw is not None
        #set $entry = {'v': round($vec.avg.raw, 4), 't': $vec.avg.format(add_label=False)}
        #if $vec.vecdir.raw is not None
          #silent $entry['dir'] = $str($vec.vecdir.ordinal_compass)
        #end if
        #silent $found[$name] = $entry
      #end if
    #else
      #set $stats = $getVar('%s.%s' % ($name, $x), None)
      #if $stats is not None and ($x == 'rain' or $x in $sums)
        #if $stats.sum.raw is not None
          #silent $found[$name] = {'v': round($stats.sum.raw, 4), 't': $stats.sum.format(add_label=False)}
        #end if
      #elif $stats is not None and $stats.avg.raw is not None
        #set $entry = {'v': round($stats.avg.raw, 4), 't': $stats.avg.format(add_label=False)}
        #if $stats.min.raw is not None
          #silent $entry.update({'lo': round($stats.min.raw, 4), 'lot': $stats.min.format(add_label=False)})
        #end if
        #if $stats.max.raw is not None
          #silent $entry.update({'hi': round($stats.max.raw, 4), 'hit': $stats.max.format(add_label=False)})
        #end if
        #silent $found[$name] = $entry
      #end if
    #end if
  #end for
  #silent $spans[$x] = $found
#end for
##
## 'data-value' and 'data-unit' carry each reading as a number and its unit in the
## report unit system, so that horizon.js can convert the reading to the unit system
## the reader chose. The element's text is the reading as the report formats it.
<section class="tiles wide" data-live-panel="current" data-span="day"
         aria-labelledby="current-heading">
  <h2 class="visually-hidden" id="current-heading">$gettext("Current Conditions")</h2>
  <dl class="tile-grid">
#for $i, $x in $enumerate($tiles)
## When the first tile is 'outTemp', the tile gets 'data-band', 0 to 8, which
## horizon.css uses to tint the tile on the Day time span. The band edges are in
## degree_C whatever the report unit system, so that a temperature gets the same
## colour in every unit system.
  #set $band = ''
  #if $i == 0 and $x == 'outTemp' and $current.outTemp.degree_C.raw is not None
    #set $edges = [-10, 0, 5, 12, 18, 23, 28, 33]
    #set $band = ' data-band="%d"' % len([$e for $e in $edges if $current.outTemp.degree_C.raw >= $e])
  #end if
  #set $icon = ''
  #if $x in $icon_map
    #set $icon = '<span class="tile-icon" style="--icon:url(icons/%s.svg)" aria-hidden="true"></span>' % $icon_map[$x]
  #end if
    <div class="tile"$band>
  #if $x == 'windSpeed'
      <dt>$obs.label.wind <span class="badge">$gettext("Live")</span></dt>
      <dd class="tile-value" data-live="windSpeed" data-obs="windSpeed"
          data-value="$current.windSpeed.raw" data-unit="$unit.unit_type.windSpeed"
          data-spans='$jsonize($spans.get('windSpeed', {}))'>
        $icon<span data-unit-value>$current.windSpeed.format(add_label=False)</span><small data-unit-label>$unit.label.windSpeed</small>
    #if $current.windDir.raw is not None
        <span class="wind-dir">$current.windDir.ordinal_compass</span>
    #end if
      </dd>
  #elif $x == 'rain'
## The label "Rain Today" fits the Day time span only. horizon.js switches between
## 'data-label-day' and 'data-label-span' when the reader changes the time span.
      <dt><span data-label-day="$gettext('Rain Today')" data-label-span="$obs.label.rain">$gettext("Rain Today")</span> <span class="badge">$gettext("Live")</span></dt>
      <dd class="tile-value" data-live="rainToday" data-obs="rain"
          data-value="$day.rain.sum.raw" data-unit="$unit.unit_type.rain"
          data-spans='$jsonize($spans.get('rain', {}))'>
        $icon<span data-unit-value>$day.rain.sum.format(add_label=False)</span><small data-unit-label>$unit.label.rain</small>
      </dd>
    #if $getVar('year.rainRate.has_data', False)
      <dd class="tile-sub" data-obs="rainRate" data-value="$current.rainRate.raw"
          data-unit="$unit.unit_type.rainRate"><span data-unit-value>$current.rainRate.format(add_label=False)</span><small data-unit-label>$unit.label.rainRate</small></dd>
    #end if
  #else
    #set $vh = $getVar('current.%s' % $x)
    #set $unit_type = $getVar('unit.unit_type.%s' % $x)
    #set $unit_label = $getVar('unit.label.%s' % $x)
      <dt>$obs.label[$x] <span class="badge">$gettext("Live")</span></dt>
      <dd class="tile-value" data-live="$x" data-obs="$x"
          data-value="$vh.raw" data-unit="$unit_type"
          data-spans='$jsonize($spans.get($x, {}))'>
        $icon<span data-unit-value>$vh.format(add_label=False)</span><small data-unit-label>$unit_label</small>
    #set $tr = $getVar('trend.%s' % $x, None)
    #if $tr is not None and $tr.raw is not None
      #set $step = $x == 'barometer' and 0.6 or 0.3
      #set $way = $tr.raw > $step and 'up' or ($tr.raw < -$step and 'down' or 'flat')
        <svg class="trend trend-$way" viewBox="0 0 24 24" aria-hidden="true"><title>$tr.formatted $gettext("in 3h")</title><path d="M12 20 L12 4 M5 11 L12 4 L19 11"/></svg>
    #end if
      </dd>
    #set $lo = $getVar('day.%s.min' % $x, None)
    #set $hi = $getVar('day.%s.max' % $x, None)
    #if $lo is not None and $hi is not None and $lo.raw is not None and $hi.raw is not None
      <dd class="tile-range">
        <span><span class="range-key">$gettext("Min")</span>
          <span data-obs="$x" data-range="lo" data-value="$lo.raw" data-unit="$unit_type"><span data-unit-value>$lo.format(add_label=False)</span><small data-unit-label>$unit_label</small></span></span>
        <span><span class="range-key">$gettext("Max")</span>
          <span data-obs="$x" data-range="hi" data-value="$hi.raw" data-unit="$unit_type"><span data-unit-value>$hi.format(add_label=False)</span><small data-unit-label>$unit_label</small></span></span>
      </dd>
    #end if
  #end if
    </div>
#end for
  </dl>
</section>
