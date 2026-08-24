## Copyright (c) 2026 the WeeWX contributors
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

#set $headline = $to_list($DisplayOptions.get('observations_headline', ['outTemp', 'windSpeed', 'rain', 'barometer']))
#set $summary_image = $to_bool($DisplayOptions.get('show_summary_image', True))

<section class="headline" aria-label="$gettext('Current Conditions')">
#if $summary_image
  <a class="headline-share" href="current.png"
     title="$gettext('An image of these readings, for sharing')">
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/><path d="M21 16l-5-5-4 4-2-2-7 6"/></svg>
    <span class="visually-hidden">$gettext("An image of these readings, for sharing")</span>
  </a>
#end if
#for $x in $headline
  #if $getVar('year.%s.has_data' % $x, False)
  <div class="headline-item">
    #if $x == 'windSpeed'
    <span class="label">$obs.label.wind</span>
    <span class="value" data-live="windSpeed">$current.windSpeed.format(add_label=False)<span class="unit">$unit.label.windSpeed</span></span>
    <span class="sub">
      #if $current.windDir.raw is not None
      $current.windDir.ordinal_compass ($current.windDir)
      #end if
      #if $current.windGust.raw is not None
      &middot; $gettext("Gust") $current.windGust
      #end if
    </span>
    #elif $x == 'rain'
    <span class="label">$gettext("Rain Today")</span>
    <span class="value" data-live="rainToday">$day.rain.sum.format(add_label=False)<span class="unit">$unit.label.rain</span></span>
    <span class="sub">
      #if $day.rainRate.max.raw
      $gettext("Max rate") $day.rainRate.max
      #else
      $gettext("Yesterday"): $yesterday.rain.sum
      #end if
    </span>
    #elif $x == 'barometer'
    <span class="label">$obs.label.barometer</span>
    <span class="value" data-live="barometer">$current.barometer.format(add_label=False)<span class="unit">$unit.label.barometer</span></span>
    <span class="sub">
      #if $trend.barometer.raw is not None
        #set $trend_class = 'trend-flat'
        #if $trend.barometer.raw > 0
          #set $trend_class = 'trend-up'
        #elif $trend.barometer.raw < 0
          #set $trend_class = 'trend-down'
        #end if
      <span class="$trend_class">$trend.barometer.formatted</span>
      $gettext("in 3h")
      #end if
    </span>
    #elif $x == 'outTemp'
    <span class="label">$obs.label.outTemp</span>
    <span class="value" data-live="outTemp">$current.outTemp.format(add_label=False)<span class="unit">$unit.label.outTemp</span></span>
    <span class="sub">
      #if $current.dewpoint.raw is not None
      $obs.label.dewpoint $current.dewpoint &middot;
      #end if
      <span class="stat-lo">$day.outTemp.min.format(add_label=False)</span> /
      <span class="stat-hi">$day.outTemp.max</span>
    </span>
    #else
    <span class="label">$obs.label[$x]</span>
    <span class="value" data-live="$x">$getVar('current.%s.format' % $x)(add_label=False)<span class="unit">$unit.label[$x]</span></span>
    <span class="sub">
      <span class="stat-lo">$getVar('day.%s.min' % $x).format(add_label=False)</span> /
      <span class="stat-hi">$getVar('day.%s.max' % $x)</span>
    </span>
    #end if
  </div>
  #end if
#end for
</section>
