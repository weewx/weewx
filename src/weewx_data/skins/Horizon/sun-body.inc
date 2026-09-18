## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## What the sun panel holds, without a panel around it.
## Included by sun.inc, which gives it one of its own, and by
## sunmoon.inc, which puts this and the other one in a single panel. The
## figures are worked out here, so either caller gets them.
##
## The arc is drawn from the sun's declination, which pyephem gives us, and not from
## a reading taken every quarter hour. The height at hour angle H is
##
##     sin(h) = sin(lat) sin(dec) + cos(lat) cos(dec) cos(H)
##
## and the band behind it is the same curve at the two solstices, dec = +/-23.44.
## So the whole picture costs one number.
##
#from math import asin, sin, cos, radians, degrees
#from time import localtime, mktime
#if $almanac.hasExtras
  #set $AU_KM = 149597870.7
  #set $AU_LIGHT_S = 499.005
  #set $lat = $station.latitude_f
  #set $W = 260
  #set $BASE = 76
  #set $SCALE = 0.62
##
## Three curves: the two solstices, and today. #def is no use inside #if, so they
## are built here and read out below.
## The axis is the clock on the wall, midnight to midnight. Each curve is drawn
## for its own day, and takes its declination and its transit from the almanac
## for that day. Two things follow, and both are visible:
##
##   - The sun is not highest at noon. Here it is highest at 13:15, from the time
##     zone, the longitude and the equation of time together.
##   - Summer time moves the clock, not the sun. At the winter solstice the peak
##     is at 12:11, over an hour earlier by the clock than at the summer one.
##
## mktime() with isdst = -1 finds local midnight for whichever day it is given, so a
## December curve is placed in standard time and a June curve in summer time.
## The two curves are named for the month rather than the season. At the June
## solstice the sun stands at dec +23.44 whatever the latitude, and the latitude
## decides which curve comes out on top. South of the equator, June is the low one.
  #set $curves = {}
  #for $name, $when in [('june', $almanac.next_summer_solstice.raw),
                        ('december', $almanac.next_winter_solstice.raw),
                        ('today', $current.dateTime.raw)]
    #set $alm = $almanac(almanac_time=$when)
    #set $lt = localtime($when)
    #set $midnight = mktime(($lt.tm_year, $lt.tm_mon, $lt.tm_mday, 0, 0, 0, 0, 0, -1))
## The day the clocks go forward is 23 hours long, the day they go back is 25.
## Asking mktime() for the next midnight rather than adding 86400 gets both right,
## and the axis keeps meaning "this day, end to end".
    #set $next_mid = mktime(($lt.tm_year, $lt.tm_mon, $lt.tm_mday + 1, 0, 0, 0, 0, 0, -1))
    #set $span_h = ($next_mid - $midnight) / 3600.0
    #set $transit_h = ($alm.sun.transit.raw - $midnight) / 3600.0
    #set $dec = $alm.sun.dec
    #set $pts = []
    #for $i in range(0, 97)
      #set $hour = $i * $span_h / 96.0
      #set $ha = radians(15.0 * ($hour - $transit_h))
      #set $alt = degrees(asin(sin(radians($lat)) * sin(radians($dec))
                             + cos(radians($lat)) * cos(radians($dec)) * cos($ha)))
      #silent $pts.append("%.1f,%.1f" % ($i * $W / 96.0, $BASE - $alt * $SCALE))
    #end for
    #silent $curves[$name] = ' '.join($pts)
    #if $name == 'today'
      #set $day_start = $midnight
      #set $day_seconds = $next_mid - $midnight
      #set $noon_x = $W * (12.0 / $span_h)
    #end if
  #end for
## The band is the area between the two solstices: summer along the top, winter
## back along the bottom.
  #set $band = $curves.june + ' ' + ' '.join(reversed($curves.december.split(' ')))
##
  #set $frac = ($current.dateTime.raw - $day_start) / float($day_seconds)
  #set $today_light = $almanac.sun.visible.raw
  #set $yesterday_light = $almanac(almanac_time=$current.dateTime.raw - 86400).sun.visible.raw
  #set $delta_min = ($today_light - $yesterday_light) / 60.0
  #set $max_alt = degrees(asin(sin(radians($lat)) * sin(radians($almanac.sun.dec))
                              + cos(radians($lat)) * cos(radians($almanac.sun.dec))))
  #set $civil = $almanac(horizon=-6).sun(use_center=1)
  #set $sun_light = $almanac.sun.earth_distance * $AU_LIGHT_S

    <svg class="sunarc" viewBox="0 0 $W 92" role="img"
         aria-label="$gettext('The sun through the day')">
      <clipPath id="sunarc-clip"><rect x="0" y="0" width="$W" height="$BASE"/></clipPath>
      <g clip-path="url(#sunarc-clip)">
        <polygon class="sunarc-band" points="$band"/>
        <polyline class="sunarc-edge" points="$curves.june"/>
        <polyline class="sunarc-edge" points="$curves.december"/>
        <polyline class="sunarc-today" points="$curves.today"/>
      </g>
      <line class="sunarc-horizon" x1="0" y1="$BASE" x2="$W" y2="$BASE"/>
  #if 0 <= $frac <= 1
      <line class="sunarc-now" x1="${'%.1f' % ($frac * $W)}" y1="2"
            x2="${'%.1f' % ($frac * $W)}" y2="$BASE"/>
  #end if
      ## The axis is the local day, so noon is its middle. Sunrise and sunset are
      ## not: they go where the curve actually crosses the horizon.
      ## Not quite the middle on the day the clocks change, when the day is 23 or
      ## 25 hours long.
      <line class="sunarc-noon" x1="${'%.1f' % $noon_x}" y1="${$BASE - 6}" x2="${'%.1f' % $noon_x}" y2="${$BASE + 3}"/>
      <text class="sunarc-label" x="${'%.1f' % $noon_x}" y="88" text-anchor="middle">12</text>
      ## North of the arctic circle there are days with neither, and the almanac
      ## returns None for them.
  #if $almanac.sun.rise.raw is not None and $almanac.sun.set.raw is not None
    #set $x_rise = ($almanac.sun.rise.raw - $day_start) / float($day_seconds) * $W
    #set $x_set = ($almanac.sun.set.raw - $day_start) / float($day_seconds) * $W
      <text class="sunarc-label" x="${'%.1f' % max(16, $x_rise)}" y="88" text-anchor="middle">$almanac.sun.rise</text>
      <text class="sunarc-label" x="${'%.1f' % min($W - 16, $x_set)}" y="88" text-anchor="middle">$almanac.sun.set</text>
  #end if
    </svg>

    <dl class="readings">
      <dt>$gettext("Daylight")</dt>
      <dd>$almanac.sun.visible.long_form(format_string="%(hour)d%(hour_label)s, %(minute)d%(minute_label)s")</dd>
      <dt>$gettext("Since yesterday")</dt>
      <dd>${'%+.1f' % $delta_min}&thinsp;$gettext("min")</dd>
      <dt>$gettext("Highest")</dt>
      <dd>${'%.1f' % $max_alt}&deg;</dd>
      <dt>$gettext("Light enough")</dt>
      <dd>#if $civil.rise.raw is not None then "%s &ndash; %s" % ($civil.rise, $civil.set) else $gettext("not today")#</dd>
      <dt>$gettext("Distance")</dt>
      <dd>${'%.1f' % ($almanac.sun.earth_distance * $AU_KM / 1e6)}&thinsp;$gettext("million km")</dd>
      <dt>$gettext("Light takes")</dt>
      <dd>${'%d' % ($sun_light // 60)}&thinsp;$gettext("min") ${'%d' % ($sun_light % 60)}&thinsp;$gettext("s")</dd>
    </dl>
#end if
