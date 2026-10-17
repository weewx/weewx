## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The sun panel. sun-body.inc holds the panel's content, so that sunmoon.inc can
## show the same content beside the moon.
#if $almanac.hasExtras
<section class="panel" data-live-panel="sun">
  <div class="panel-head">
    <h2><a href="celestial.html">$gettext("Sun")</a></h2>
  </div>
  <div class="panel-body">
    #include "sun-body.inc"
  </div>
</section>
#end if
