## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## One card, read from the top: what it is, how warm, where that sits in the day,
## and then everything else in two quiet columns. The reading leads because it is
## what anyone came for; the rest is the same size as itself and does not compete.
##
#set $headline = $to_list($DisplayOptions.get('observations_headline', ['outTemp', 'windSpeed', 'rain', 'barometer']))
#set $lead = $headline and $headline[0] or 'outTemp'
#set $rest = [$x for $x in $headline[1:] if $getVar('year.%s.has_data' % $x, False)]
#set $summary_image = $to_bool($DisplayOptions.get('show_summary_image', True))
##
<section class="panel headline" aria-label="$gettext('Current Conditions')">
#if $summary_image
  <a class="headline-share" href="current.png"
     title="$gettext('An image of these readings, for sharing')">
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/><path d="M21 16l-5-5-4 4-2-2-7 6"/></svg>
    <span class="visually-hidden">$gettext("An image of these readings, for sharing")</span>
  </a>
#end if

#if $getVar('year.%s.has_data' % $lead, False)
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
  <div class="lead">
    <span class="lead-value"$band data-live="$lead">#slurp
#if $cut > 0
$shown[:$cut]<span class="lead-dec">$shown[$cut:]</span>#slurp
#else
$shown#slurp
#end if
</span>
    <span class="lead-unit">$getVar('unit.label.%s' % $lead)</span>
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
  <div class="span-today">
    <div class="span-track">
      <span class="span-fill" style="left:0%;width:100%"></span>
      #if $now_raw is not None
      #set $at = max(0.0, min(100.0, ($now_raw - $lo_vt.raw) / ($hi_vt.raw - $lo_vt.raw) * 100.0))
      <span class="span-now" style="left:${'%.1f' % $at}%"></span>
      #end if
    </div>
    <div class="span-ends">
      <span class="span-end"><b>$lo_vt.format(add_label=False)</b><small>$getVar('unit.label.%s' % $lead)</small>
            <span class="faint">$lead_day.mintime.format("%H:%M")</span></span>
      <span class="span-caption">$gettext("measured")</span>
      <span class="span-end span-end--right"><b>$hi_vt.format(add_label=False)</b><small>$getVar('unit.label.%s' % $lead)</small>
            <span class="faint">$lead_day.maxtime.format("%H:%M")</span></span>
    </div>
  </div>
  #end if
#end if

  ## Everything else, two columns, all the same weight.
  <dl class="companions">
#if $current.dewpoint.raw is not None and 'dewpoint' not in $headline
    <div>
      <dt>$obs.label.dewpoint</dt>
      <dd>$current.dewpoint.format(add_label=False)<small>$unit.label.dewpoint</small></dd>
    </div>
#end if
#for $x in $rest
    <div>
    #if $x == 'windSpeed'
      <dt>$obs.label.wind</dt>
      <dd data-live="windSpeed">$current.windSpeed.format(add_label=False)<small>$unit.label.windSpeed</small>
        #if $current.windDir.raw is not None
        <span class="faint">$current.windDir.ordinal_compass</span>
        #end if
      </dd>
    #elif $x == 'rain'
      <dt>$gettext("Rain Today")</dt>
      <dd data-live="rainToday">$day.rain.sum.format(add_label=False)<small>$unit.label.rain</small></dd>
    #else
      <dt>$getVar('obs.label.%s' % $x)</dt>
      #set $vh = $getVar('current.%s' % $x)
      <dd data-live="$x">$vh.format(add_label=False)<small>$getVar('unit.label.%s' % $x)</small>#slurp
      #set $tr = $getVar('trend.%s' % $x, None)
      #if $tr is not None and $tr.raw is not None
        #set $step = $x == 'barometer' and 0.6 or 0.3
        #set $dir = $tr.raw > $step and 'up' or ($tr.raw < -$step and 'down' or 'flat')
      <svg class="trend trend-$dir" viewBox="0 0 24 24" aria-hidden="true"><title>$tr.formatted $gettext("in 3h")</title><path d="M12 20 L12 4 M5 11 L12 4 L19 11"/></svg>#slurp
      #end if
      </dd>
    #end if
    </div>
#end for
#if $day.rainRate.max.raw
    <div>
      <dt>$gettext("Max rate")</dt>
      <dd>$day.rainRate.max.format(add_label=False)<small>$unit.label.rainRate</small></dd>
    </div>
#end if
  </dl>
</section>
