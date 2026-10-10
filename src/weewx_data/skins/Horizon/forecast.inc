## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The forecast panel. WeeWX writes the panel empty and hidden, and forecast.js fills
## the panel in the browser and shows it once there is a forecast. The head of
## forecast.js says where the forecast comes from.
<section class="panel wide" id="forecast-panel" hidden
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
