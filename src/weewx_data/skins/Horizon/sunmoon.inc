## sun/moon rise/set module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

#if $almanac.hasExtras
<section class="panel">
  <div class="panel-head">
    <h2><a href="celestial.html">$gettext("Celestial")</a></h2>
  </div>
  <div class="panel-body">
    <dl class="readings">
      <dt>$gettext("Sunrise")</dt>
      <dd>$almanac.sun.rise</dd>
      <dt>$gettext("Sunset")</dt>
      <dd>$almanac.sun.set</dd>
      <dt>$gettext("Total daylight")</dt>
      <dd>$almanac.sun.visible.long_form(format_string="%(hour)d%(hour_label)s, %(minute)d%(minute_label)s")</dd>
      <dt>$gettext("Moon Phase")</dt>
      <dd>$almanac.moon_phase, $almanac.moon_fullness%</dd>
    </dl>
  </div>
</section>
#end if
