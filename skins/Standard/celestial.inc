## celestial module for standard skin
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights

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
#set $daylight_s = $sunset_ts - $sunrise_ts
#set $daylight_hours = int($daylight_s / 3600)
#set $daylight_minutes = int(($daylight_s % 3600) / 60)
#set $daylight_str = "%02d:%02d" % ($daylight_hours, $daylight_minutes)
#end if
#end if

<div id="celestial_widget" class="widget">
  <div class="widget_title">
    Celestial
    #if $almanac.hasExtras
    :&nbsp;&nbsp;
    <a class="button_selected" id="button_celestial_summary"
       onclick="choose_celestial('summary')">Summary</a>
    <a class="button" id="button_celestial_details"
       onclick="choose_celestial('details')">Details</a>
    #end if
    <a class="widget_control"
       onclick="toggle_widget('celestial')">&diams;</a>
  </div>
  <div class="widget_contents">
  <div id="celestial_summary">
    #if $almanac.hasExtras
    <div class="celestial_body">
      <table class="celestial">
	<tr><th>Sun</th><th></th></tr>
	<tr>
	  <td class="label">Rise</td>
	  <td class="data">$almanac.sun.rise.string($sun_None)</td>
	</tr>
	<tr>
	  <td class="label">Set</td>
	  <td class="data">$almanac.sun.set.string($sun_None)</td>
	</tr>
	<tr>
	  <td class="label">Daylight</td>
	  <td class="data">$daylight_str</td>
	</tr>
      </table>
    </div>
    <div class="celestial_body">
      <table class="celestial">
	<tr><th>Moon</th><th></th></tr>
	<tr>
	  <td class="label">Rise</td>
	  <td class="data">$almanac.moon.rise</td>
	</tr>
	<tr>
	  <td class="label">Set</td>
	  <td class="data">$almanac.moon.set</td>
	</tr>
	<tr>
	  <td class="label"></td>
	  <td class="data">$almanac.moon_phase<br/>
            $almanac.moon_fullness% full</td>
	</tr>
      </table>
    </div>
    #else
    ## No extended almanac information available. Fall back to a simple table.
    <table class="celestial">
      <tr>
	<td class="label">Sunrise</td>
	<td class="data">$almanac.sunrise</td>
      </tr>
      <tr>
	<td class="label">Sunset</td>
	<td class="data">$almanac.sunset</td>
      </tr>
      <tr>
	<td class="label">Moon Phase</td>
	<td class="data">$almanac.moon_phase<br/>
          $almanac.moon_fullness% full</td>
      </tr>
    </table>
    #end if
  </div>
  #if $almanac.hasExtras
  <div id="celestial_details" style="display:none">
    <div class="celestial_body">
      <table class="celestial">
	<tr><th>Sun</th><th></th></tr>
	<tr>
	  <td class="label">Start civil twilight</td>
	  <td class="data">$almanac(horizon=-6).sun(use_center=1).rise</td>
	</tr>
	<tr>
	  <td class="label">Rise</td>
	  <td class="data">$almanac.sun.rise.string($sun_None)</td>
	</tr>
        <tr>
          <td class="label">Transit:</td>
          <td class="data">$almanac.sun.transit</td>
        </tr>
	<tr>
	  <td class="label">Set</td>
	  <td class="data">$almanac.sun.set.string($sun_None)</td>
	</tr>
	<tr>
	  <td class="label">End civil twilight</td>
	  <td class="data">$almanac(horizon=-6).sun(use_center=1).set</td>
	</tr>
        <tr>
          <td class="label">Azimuth:</td>
          <td class="data">$("%.1f&deg;" % $almanac.sun.az)</td>
        </tr>
        <tr>
          <td class="label">Altitude:</td>
          <td class="data">$("%.1f&deg;" % $sun_altitude)</td>
        </tr>
        <tr>
          <td class="label">Right ascension:</td>
          <td class="data">$("%.1f&deg;" % $almanac.sun.ra)</td>
        </tr>
        <tr>
          <td class="label">Declination:</td>
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
	  <td class="label">Daylight</td>
	  <td class="data">$daylight_str</td>
	</tr>
      </table>
    </div>
    <div class="celestial_body">
      <table class="celestial">
	<tr><th>Moon</th><th></th></tr>
        <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
	<tr>
	  <td class="label">Rise</td>
	  <td class="data">$almanac.moon.rise</td>
	</tr>
        <tr>
          <td class="label">Transit:</td>
          <td class="data">$almanac.moon.transit</td>
        </tr>
	<tr>
	  <td class="label">Set</td>
	  <td class="data">$almanac.moon.set</td>
	</tr>
        <tr><td class="label">&nbsp;</td><td class="data">&nbsp;</td></tr>
        <tr>
          <td class="label">Azimuth:</td>
          <td class="data">$("%.1f&deg;" % $almanac.moon.az)</td>
        </tr>
        <tr>
          <td class="label">Altitude:</td>
          <td class="data">$("%.1f&deg;" % $almanac.moon.alt)</td>
        </tr>
        <tr>
          <td class="label">Right ascension:</td>
          <td class="data">$("%.1f&deg;" % $almanac.moon.ra)</td>
        </tr>
        <tr>
          <td class="label">Declination:</td>
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
  #end if
  </div>
</div>
