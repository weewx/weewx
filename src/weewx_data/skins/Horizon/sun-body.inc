## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The content of the sun panel, for sun.inc and sunmoon.inc: a drawing of the sun's
## altitude through the day, and figures on daylight and the sun.
##
## The drawing has three curves. Each curve is computed from the sun's declination
## 'dec' and transit time on the curve's day, which pyephem provides, rather than by
## asking pyephem for the sun's position at each point. The sun's altitude h at the
## hour angle H is
##
##     sin(h) = sin(lat) sin(dec) + cos(lat) cos(dec) cos(H)
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
## The curves are for the June solstice, the December solstice and today. The x axis
## is local time from midnight to midnight, and a curve peaks at the transit time of
## its day, where the time zone, the longitude and the equation of time put the
## transit, not at 12:00. The curve of a day in summer time peaks about an hour later
## by the clock than one in standard time.
##
## mktime() with isdst = -1 finds the local midnight of each day, so the December
## curve is placed in standard time and the June curve in summer time. The curves
## are named for the month rather than the season, because south of the equator the
## June curve is the low one.
  #set $curves = {}
  #for $name, $when in [('june', $almanac.next_summer_solstice.raw),
                        ('december', $almanac.next_winter_solstice.raw),
                        ('today', $current.dateTime.raw)]
    #set $alm = $almanac(almanac_time=$when)
    #set $lt = localtime($when)
    #set $midnight = mktime(($lt.tm_year, $lt.tm_mon, $lt.tm_mday, 0, 0, 0, 0, 0, -1))
## The next midnight comes from mktime() rather than from adding 86400, because the
## days on which summer time starts and ends are 23 and 25 hours long.
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
## The shaded band between the two solstice curves is a polygon that runs along the
## June curve and back along the December curve.
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
## A mark at 12:00 by the clock, which is not in the middle of the axis on a day of
## 23 or 25 hours.
      <line class="sunarc-noon" x1="${'%.1f' % $noon_x}" y1="${$BASE - 6}" x2="${'%.1f' % $noon_x}" y2="${$BASE + 3}"/>
      <text class="sunarc-label" x="${'%.1f' % $noon_x}" y="88" text-anchor="middle">12</text>
## Beyond the polar circles some days have no sunrise or no sunset, and the almanac
## then returns None for that time.
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
