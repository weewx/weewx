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
    #set $sun_None='<i>$gettext[$page]["Always down"]</i>'
  #else
    #set $sun_None='<i>$gettext[$page]["Always up"]</i>'
  #end if

  ## For the change in daylight, pick a string to indicate whether it is more or
  ## less than yesterday:
  #set $sun_visible_change = $almanac.sun.visible_change
  #if $sun_visible_change.raw < 0
    #set $change_str = $gettext[$page]["less than yesterday"]
  #else
    #set $change_str = $gettext[$page]["more than yesterday"]
  #end if
#end if

<div id="celestial_widget" class="widget">
  <div class="widget_title">
    $gettext[$page]["Title"]
  </div>
  <div class="widget_contents">
  #if $almanac.hasExtras
    <div id="celestial_details">
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9728; $gettext[$page]["Sun"]</th><th></th></tr>
          <tr>
            <td class="label">$gettext[$page]["Start civil twilight"]</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).rise</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Rise"]</td>
            <td class="data">$almanac.sun.rise.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Transit"]</td>
            <td class="data">$almanac.sun.transit</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Set"]</td>
            <td class="data">$almanac.sun.set.format(None_string=$sun_None)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["End civil twilight"]</td>
            <td class="data">$almanac(horizon=-6).sun(use_center=1).set</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Azimuth"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.az)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["AstroAltitude"]</td>
            <td class="data">$("%.1f&deg;" % $sun_altitude)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Right ascension"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.ra)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Declination"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.sun.dec)</td>
          </tr>
          #if $almanac.next_equinox.raw < $almanac.next_solstice.raw
            ## The equinox is before the solstice. Display them in order.
            <tr>
              <td class="label">$gettext[$page]["Equinox"]</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
            <tr>
              <td class="label">$gettext[$page]["Solstice"]</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
          #else
            ## The solstice is before the equinox. Display them in order.
            <tr>
              <td class="label">$gettext[$page]["Solstice"]</td>
              <td class="data">$almanac.next_solstice</td>
            </tr>
            <tr>
              <td class="label">$gettext[$page]["Equinox"]</td>
              <td class="data">$almanac.next_equinox</td>
            </tr>
          #end if
          <tr>
            <td class="label">$gettext[$page]["Daylight"]</td>
            <td class="data">$almanac.sun.visible<br/>$sun_visible_change $change_str</td>
          </tr>
        </table>
      </div>
      <div class="celestial_body">
        <table class="celestial">
          <tr><th>&#9789; $gettext[$page]["Moon"]</th><th></th></tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">$gettext[$page]["Rise"]</td>
            <td class="data">$almanac.moon.rise</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Transit"]</td>
            <td class="data">$almanac.moon.transit</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Set"]</td>
            <td class="data">$almanac.moon.set</td>
          </tr>
          <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
          <tr>
            <td class="label">$gettext[$page]["Azimuth"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.az)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["AstroAltitude"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.alt)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Right ascension"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.ra)</td>
          </tr>
          <tr>
            <td class="label">$gettext[$page]["Declination"]</td>
            <td class="data">$("%.1f&deg;" % $almanac.moon.dec)</td>
          </tr>
          #if $almanac.next_full_moon.raw < $almanac.next_new_moon.raw
            <tr>
              <td class="label">$gettext[$page]["Full moon"]</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
            <tr>
              <td class="label">$gettext[$page]["New moon"]</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
          #else
            <tr>
              <td class="label">$gettext[$page]["New moon"]</td>
              <td class="data">$almanac.next_new_moon</td>
            </tr>
            <tr>
              <td class="label">$gettext[$page]["Full moon"]</td>
              <td class="data">$almanac.next_full_moon</td>
            </tr>
          #end if
          <tr>
            <td class="label">$gettext[$page]["Phase"]</td>
            <td class="data">$almanac.moon_phase<br/>
              $almanac.moon_fullness% $gettext[$page]["full"]</td>
          </tr>
        </table>
      </div>
    </div>
  #else
    <p>Install <em>pyephem</em> for detailed celestial timings.</p>
  #end if
  </div>
</div>
