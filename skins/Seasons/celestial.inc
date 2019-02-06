## celestial module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

## If extended almanac information is available, do extra calculations.
#if $almanac.hasExtras

  #set $sun_altitude = $almanac.sun.alt
  #if $sun_altitude < 0
    #set $sun_None="<i>(Always down)</i>"
    #set $daylight_str = "00:00"
  #else
    #set $sun_None="<i>(Always up)</i>"
    #set $daylight_str = "24:00"
  #end if

  #set $sunrise_ts = $almanac.sun.rise.raw
  #set $sunset_ts = $almanac.sun.set.raw
  #if $sunrise_ts and $sunset_ts

    #set $now = $current.dateTime.raw
    #set $today_daylight = $sunset_ts -  $sunrise_ts

    #set $seconds = $today_daylight
    #set $hours = $seconds //3600
    #set $seconds %= 3600
    #set $minutes = $seconds//60
    #set $seconds %= 60
    #set $daylight_str = "%d hours, %d minutes, %d seconds" % ($hours, $minutes, $seconds)

    #set $yesterday = $now - 24*3600
    #set $yesterday_daylight = $almanac($almanac_time=$yesterday).sun.set.raw - $almanac($almanac_time=$yesterday).sun.rise.raw
    #set $difference = $today_daylight - $yesterday_daylight
    #if $difference
      #set $delta = abs($difference)
      #set $amt_str = "%s%d seconds" % (str(int($delta) // 60) + ' minutes, ' if ($delta // 60) > 0 else '', $delta % 60 if ($delta // 60) > 0 else $delta)
      #if $difference > 0
        #set $delta_str = "%s more than yesterday" % $amt_str
      #else
        #set $delta_str = "%s less than yesterday" % $amt_str
      #end if
      #set $daylight_str = "%s<br/>%s" % ($daylight_str, $delta_str)
    #end if

  #end if
#end if

<div id="celestial_widget" class="widget">
  <div class="widget_title">
    Celestial
  </div>
  <div class="widget_contents">
  #if $almanac.hasExtras
    <div id="celestial_details">
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9728; Sun</th><th></th></tr>
          <tr>
            <td class="label">Start civil twilight</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).rise</td>
          </tr>
          <tr>
            <td class="label">Rise</td>
            <td class="data">$almanac.sun.rise.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">Transit</td>
            <td class="data">$almanac.sun.transit</td>
          </tr>
          <tr>
            <td class="label">Set</td>
            <td class="data">$almanac.sun.set.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">End civil twilight</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).set</td>
          </tr>
          <tr>
            <td class="label">Azimuth</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.az)</td>
          </tr>
          <tr>
            <td class="label">Altitude</td>
            <td class="data">$("%.1f&deg;" % $sun_altitude)</td>
          </tr>
          <tr>
            <td class="label">Right ascension</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.ra)</td>
          </tr>
          <tr>
            <td class="label">Declination</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.dec)</td>
          </tr>
          #if $almanac.next_equinox.raw < $almanac.next_solstice.raw
            ## The equinox is before the solstice. Display them in order.
            <tr>
              <td class="label">Equinox</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
            <tr>
              <td class="label">Solstice</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
          #else
            ## The solstice is before the equinox. Display them in order.
            <tr>
              <td class="label">Solstice</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
            <tr>
              <td class="label">Equinox</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
          #end if
          <tr>
            <td class="label">Total daylight</td>
            <td class="data">$daylight_str</td>
          </tr>
        </table>
      </div>
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9789; Moon</th><th></th></tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">Rise</td>
            <td class="data">$almanac.moon.rise</td>
          </tr>
          <tr>
            <td class="label">Transit</td>
            <td class="data">$almanac.moon.transit</td>
          </tr>
          <tr>
            <td class="label">Set</td>
            <td class="data">$almanac.moon.set</td>
          </tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">Azimuth</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.az)</td>
          </tr>
          <tr>
            <td class="label">Altitude</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.alt)</td>
          </tr>
          <tr>
            <td class="label">Right ascension</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.ra)</td>
          </tr>
          <tr>
            <td class="label">Declination</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.dec)</td>
          </tr>
          #if $almanac.next_full_moon.raw < $almanac.next_new_moon.raw
            <tr>
              <td class="label">Full moon</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
            <tr>
              <td class="label">New moon</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
          #else
            <tr>
              <td class="label">New moon</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
            <tr>
              <td class="label">Full moon</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
          #end if
          <tr>
            <td class="label">Phase</td>
            <td class="data">$almanac.moon_phase<br/>
              $almanac.moon_fullness% full</td>
          </tr>
        </table>
      </div>
    </div>
  #else
    <p>Install <em>pyephem</em> for detailed celestial timings.</p>
  #end if
  </div>
</div>
