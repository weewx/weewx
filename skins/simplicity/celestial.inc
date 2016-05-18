<div id="celestial" class="widget">
  <div class="section_heading">
    $Extras.labels.almanac
  </div>

  <div class="celestial_group">
    #if $almanac.hasExtras
    ## Extended almanac information is available. Do the full set of tables.
    <div class="celestial_body">
      <table class="celestial">
	<caption>Sun</caption>
	<tr>
	  <td class="label">Start civil twilight</td>
	  <td class="data">$almanac(horizon=-6).sun(use_center=1).rise</td>
	</tr>
	<tr>
	  <td class="label">Sunrise</td>
	  <td class="data">$almanac.sun.rise</td>
	</tr>
	<tr>
	  <td class="label">Sunset</td>
	  <td class="data">$almanac.sun.set</td>
	</tr>
	<tr>
	  <td class="label">End civil twilight</td>
	  <td class="data">$almanac(horizon=-6).sun(use_center=1).set</td>
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
      </table>
    </div>
    <div class="celestial_body">
      <table class="celestial">
	<caption>Moon</caption>	 
	<tr>
	  <td class="label">Rise</td>
	  <td class="data">$almanac.moon.rise</td>
	</tr>
	<tr>
	  <td class="label">Set</td>
	  <td class="data">$almanac.moon.set</td>
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
</div>
