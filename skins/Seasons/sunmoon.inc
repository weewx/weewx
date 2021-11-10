## sun/moon rise/set module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## If extended almanac information is available, do extra calculations.
#if $almanac.hasExtras
  #set $sun_altitude = $almanac.sun.alt
  #if $sun_altitude < 0
    #set $sun_None='<i>%s</i>' % $gettext("Always down")
    #set $daylight_str = "00:00"
  #else
    #set $sun_None='<i>%s</i>' % $gettext("Always up")
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

<div id="sunmoon_widget" class="widget">
  <div class="widget_title">
    <a href="celestial.html">$gettext("Celestial")</a>
    <a class="widget_control"
       onclick="toggle_widget('sunmoon')">&diams;</a>
  </div>
  <div class="widget_contents">
    <div id="celestial_summary">
      #if $almanac.hasExtras
      <table class="celestial">
        <tr><th>&#9728;</th><td></td><td></td><th>&#9789;</th><td></td></tr>
        <tr>
          <td class="label">$gettext("Rise")</td>
          <td class="data">$almanac.sun.rise.format(None_string=$sun_None)</td>
          <td>&nbsp;</td>
          <td class="label">$gettext("Rise")</td>
          <td class="data">$almanac.moon.rise</td>
        </tr>
        <tr>
          <td class="label">$gettext("Set")</td>
          <td class="data">$almanac.sun.set.format(None_string=$sun_None)</td>
          <td>&nbsp;</td>
          <td class="label">$gettext("Set")</td>
          <td class="data">$almanac.moon.set</td>
        </tr>
        <tr>
          <td class="label">$gettext("Daylight")</td>
          <td class="data">$daylight_str</td>
          <td>&nbsp;</td>
          <td class="label"></td>
          <td class="data">$almanac.moon_phase<br/>
            $almanac.moon_fullness%</td>
        </tr>
      </table>
      #else
        ## No extended almanac information available. Fall back to basic info.
      <table class="celestial">
        <tr>
          <td class="label">$gettext("Sunrise")</td>
          <td class="data">$almanac.sunrise</td>
        </tr>
        <tr>
          <td class="label">$gettext("Sunset")</td>
          <td class="data">$almanac.sunset</td>
        </tr>
        <tr>
          <td class="label">$gettext("Moon Phase")</td>
          <td class="data">$almanac.moon_phase<br/>
            $almanac.moon_fullness%</td>
        </tr>
      </table>
      #end if
    </div>
  </div>
</div>
