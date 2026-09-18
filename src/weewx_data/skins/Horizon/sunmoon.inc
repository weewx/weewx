## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## Sun and moon in one panel, side by side where there is room for two columns and
## stacked where there is not. Both halves are the same files the separate panels
## use, so there is one place to change either of them.
##
## Name "sunmoon" in 'panels' instead of "sun" and "moon" to use this.
#if $almanac.hasExtras
<section class="panel" data-live-panel="sunmoon">
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
