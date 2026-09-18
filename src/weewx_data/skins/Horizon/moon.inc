## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The moon on its own. To have both in one panel, name
## "sunmoon" in the 'panels' list instead of "sun" and "moon".
#if $almanac.hasExtras
<section class="panel" data-live-panel="moon">
  <div class="panel-head">
    <h2><a href="celestial.html">$gettext("Moon")</a></h2>
  </div>
  <div class="panel-body">
    #include "moon-body.inc"
  </div>
</section>
#end if
