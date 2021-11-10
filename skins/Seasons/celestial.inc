## celestial module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## If extended almanac information is available, do extra calculations.
#if $almanac.hasExtras
  ## Pick a "None string" on the basis of whether the sun is above or below the horizon
  #set $sun_altitude = $almanac.sun.alt
  #if $sun_altitude < 0
    #set $sun_None='<i>%s</i>' % $gettext("Always down")
  #else
    #set $sun_None='<i>%s</i>' % $gettext("Always up")
  #end if

  ## For the change in daylight, pick a string to indicate whether it is more or
  ## less than yesterday:
  #set $sun_visible_change = $almanac.sun.visible_change
  #if $sun_visible_change.raw < 0
    #set $change_str = $gettext("less than yesterday")
  #else
    #set $change_str = $gettext("more than yesterday")
  #end if
#end if

<div id="celestial_widget" class="widget">
  <div class="widget_title">
    $gettext("Celestial")
  </div>
  <div class="widget_contents">
  #if $almanac.hasExtras
    <div id="celestial_details">
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9728; $gettext("Sun")</th><th></th></tr>
          <tr>
            <td class="label">$gettext("Start civil twilight")</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).rise</td>
          </tr>
          <tr>
            <td class="label">$gettext("Rise")</td>
            <td class="data">$almanac.sun.rise.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">$gettext("Transit")</td>
            <td class="data">$almanac.sun.transit</td>
          </tr>
          <tr>
            <td class="label">$gettext("Set")</td>
            <td class="data">$almanac.sun.set.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">$gettext("End civil twilight")</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).set</td>
          </tr>
          <tr>
            <td class="label">$gettext("Azimuth")</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.az)</td>
          </tr>
          <tr>
            <td class="label">$pgettext("Astronomical", "Altitude")</td>
            <td class="data">$("%.1f&deg;" % $sun_altitude)</td>
          </tr>
          <tr>
            <td class="label">$gettext("Right ascension")</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.ra)</td>
          </tr>
          <tr>
            <td class="label">$gettext("Declination")</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.dec)</td>
          </tr>
          #if $almanac.next_equinox.raw < $almanac.next_solstice.raw
            ## The equinox is before the solstice. Display them in order.
            <tr>
              <td class="label">$gettext("Equinox")</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
            <tr>
              <td class="label">$gettext("Solstice")</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
          #else
            ## The solstice is before the equinox. Display them in order.
            <tr>
              <td class="label">$gettext("Solstice")</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
            <tr>
              <td class="label">$gettext("Equinox")</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
          #end if
          <tr>
            <td class="label">$gettext("Total daylight")</td>
            <td class="data">$almanac.sun.visible<br/>$sun_visible_change $change_str</td>
          </tr>
        </table>
      </div>
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9789; $gettext("Moon")</th><th></th></tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">$gettext("Rise")</td>
            <td class="data">$almanac.moon.rise</td>
          </tr>
          <tr>
            <td class="label">$gettext("Transit")</td>
            <td class="data">$almanac.moon.transit</td>
          </tr>
          <tr>
            <td class="label">$gettext("Set")</td>
            <td class="data">$almanac.moon.set</td>
          </tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">$gettext("Azimuth")</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.az)</td>
          </tr>
          <tr>
            <td class="label">$pgettext("Astronomical", "Altitude")</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.alt)</td>
          </tr>
          <tr>
            <td class="label">$gettext("Right ascension")</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.ra)</td>
          </tr>
          <tr>
            <td class="label">$gettext("Declination")</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.dec)</td>
          </tr>
          #if $almanac.next_full_moon.raw < $almanac.next_new_moon.raw
            <tr>
              <td class="label">$gettext("Full moon")</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
            <tr>
              <td class="label">$gettext("New moon")</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
          #else
            <tr>
              <td class="label">$gettext("New moon")</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
            <tr>
              <td class="label">$gettext("Full moon")</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
          #end if
          <tr>
            <td class="label">$gettext("Phase")</td>
            <td class="data">$almanac.moon_phase<br/>
              $almanac.moon_fullness% $gettext("full")</td>
          </tr>
        </table>
      </div>
    </div>
  #else
    <p>Install <em>pyephem</em> for detailed celestial timings.</p>
  #end if
  </div>
</div>
