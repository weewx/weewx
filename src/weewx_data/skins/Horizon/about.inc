## about module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

<section class="panel" data-live-panel="about">
  <div class="panel-head">
    <h2>$gettext("About this station")</h2>
  </div>
  <div class="panel-body">
    <dl class="readings">
      <dt>$gettext("Latitude")</dt>
      <dd>$station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2]</dd>
      <dt>$gettext("Longitude")</dt>
      <dd>$station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2]</dd>
      <dt>$pgettext("Geographical", "Altitude")</dt>
      <dd>$station.altitude</dd>
      <dt>$gettext("Hardware")</dt>
      <dd>$station.hardware</dd>
      <dt>$gettext("WeeWX uptime")</dt>
      <dd>$station.uptime.long_form</dd>
      <dt>$gettext("WeeWX version")</dt>
      <dd>$station.version</dd>
    </dl>
  </div>
</section>
