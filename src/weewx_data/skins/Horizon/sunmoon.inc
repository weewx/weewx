## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The sun and the moon in one panel, side by side where the panel is wide enough.
## The content comes from sun-body.inc and moon-body.inc, which sun.inc and moon.inc
## use as well.
#if $almanac.hasExtras
<section class="panel double" data-live-panel="sunmoon">
  <div class="panel-head">
    <h2><a href="celestial.html">$gettext("Sun and moon")</a></h2>
  </div>
  <div class="panel-body split-two">
    <div>
      #include "sun-body.inc"
    </div>
    <div>
      #include "moon-body.inc"
    </div>
  </div>
</section>
#end if
