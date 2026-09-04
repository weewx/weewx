## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## What the moon panel holds, without a panel around it.
## Included by moon.inc, which gives it one of its own, and by
## sunmoon.inc, which puts this and the other one in a single panel. The
## figures are worked out here, so either caller gets them.
##
## One of 32 images, chosen by the moon's age since the last new moon. The images are
## NASA's, rendered from Lunar Reconnaissance Orbiter data. See moon/LICENSE.txt.
##
#if $almanac.hasExtras
  #set $AU_KM = 149597870.7
  #set $SYNODIC = 29.530588
  #set $age_days = ($current.dateTime.raw - $almanac.previous_new_moon.raw) / 86400.0
  #set $frame = '%02d' % (int(round($age_days / $SYNODIC * 32)) % 32)

    <img class="moon-image" src="moon/moon-${frame}.webp" width="216" height="216"
         loading="lazy" alt="$almanac.moon_phase, $almanac.moon_fullness%">

    <dl class="readings">
      <dt>$gettext("Illuminated")</dt>
      <dd>$almanac.moon_fullness%</dd>
      <dt>$gettext("Phase")</dt>
      <dd>$almanac.moon_phase</dd>
      <dt>$gettext("Age")</dt>
      <dd>${'%.1f' % $age_days}&thinsp;$gettext("days")</dd>
      <dt>$gettext("Moonrise")</dt>
      <dd>$almanac.moon.rise</dd>
      <dt>$gettext("Moonset")</dt>
      <dd>$almanac.moon.set</dd>
  #set $to_full = int(round(($almanac.next_full_moon.raw - $current.dateTime.raw) / 86400.0))
  #set $to_new = int(round(($almanac.next_new_moon.raw - $current.dateTime.raw) / 86400.0))
      <dt>$gettext("Full moon")</dt>
      <dd>$almanac.next_full_moon <span class="hint">${$to_full == 0 and $gettext("today") or ($gettext("in %d days") % $to_full)}</span></dd>
      <dt>$gettext("New moon")</dt>
      <dd>$almanac.next_new_moon <span class="hint">${$to_new == 0 and $gettext("today") or ($gettext("in %d days") % $to_new)}</span></dd>
      <dt>$gettext("Distance")</dt>
      <dd>${'{:,.0f}'.format($almanac.moon.earth_distance * $AU_KM).replace(',', '&thinsp;')}&thinsp;$gettext("km")</dd>
    </dl>
#end if
