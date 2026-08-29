## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The forecast panel. Empty in the page as rendered: what goes in it is not the
## station's own reading but somebody else's model, and it changes on its own
## schedule. forecast.js fills it, from 'data/forecast.json' if that file is
## there and from Open-Meteo if it is not.
##
## The panel takes itself off the page when there is nothing to show, so a
## station with no forecast source has no empty box on it.
<section class="panel" id="forecast-panel" hidden
         aria-label="$gettext('Forecast')">
  <div class="panel-head">
    <h2>$gettext("Forecast")</h2>
    <span class="forecast-run hint"></span>
  </div>
  <div class="panel-body">
    <div class="forecast-days"></div>
    <div class="forecast-hours"></div>
  </div>
</section>
