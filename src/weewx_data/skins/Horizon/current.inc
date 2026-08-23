## Copyright (c) 2026 the WeeWX contributors
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

#set $observations = $to_list($DisplayOptions.get('observations_current', ['outTemp', 'barometer']))
#set $headline = $to_list($DisplayOptions.get('observations_headline', []))

<section class="panel">
  <div class="panel-head">
    <h2>$gettext("Current Conditions")</h2>
  </div>
  <div class="panel-body">
    <dl class="readings">
#for $x in $observations
  ## Skip what is already shown large at the top of the page.
  #if $x not in $headline and $getVar('year.%s.has_data' % $x, False)
    #if $x == 'windSpeed'
      <dt>$obs.label.wind</dt>
      <dd>$current.windSpeed
        #if $current.windDir.raw is not None
        $current.windDir.ordinal_compass
        #end if
      </dd>
    #elif $x == 'rain'
      <dt>$gettext("Rain Today")</dt>
      <dd>$day.rain.sum</dd>
    #elif $x == 'barometer'
      <dt>$obs.label.barometer</dt>
      <dd>$current.barometer ($trend.barometer.formatted)</dd>
    #else
      <dt>$obs.label[$x]</dt>
      <dd data-live="$x">$getVar('current.' + $x)</dd>
    #end if
  #end if
#end for
    </dl>
  </div>
</section>
