## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## Up to three panels: radar ('radar_img', linked to 'radar_url' if set), satellite
## ('satellite_img', linked to 'satellite_url' if set) and a map
## ('google_map_apikey'). Each panel appears only if its option is set in [Extras].
##
## The panels have no 'data-live-panel': replacing the map panel would discard the
## Google Maps object in it, and a new <img> with the same URL would show the picture
## from the browser's cache. Instead, on each new archive record, horizon.js requests
## each 'data-live-src' picture again with a new query string.

#if 'radar_img' in $Extras
<section class="panel">
  <div class="panel-head">
    <h2>$gettext("Radar")</h2>
  </div>
  <div class="panel-body imagery">
  #if 'radar_url' in $Extras
    <a href="$Extras.radar_url" rel="noopener">
      <img src="$Extras.radar_img" data-live-src="$Extras.radar_img" alt="$gettext('Radar')" loading="lazy">
    </a>
  #else
    <img src="$Extras.radar_img" data-live-src="$Extras.radar_img" alt="$gettext('Radar')" loading="lazy">
  #end if
  </div>
</section>
#end if

#if 'satellite_img' in $Extras
<section class="panel">
  <div class="panel-head">
    <h2>$gettext("Satellite")</h2>
  </div>
  <div class="panel-body imagery">
  #if 'satellite_url' in $Extras
    <a href="$Extras.satellite_url" rel="noopener">
      <img src="$Extras.satellite_img" data-live-src="$Extras.satellite_img" alt="$gettext('Satellite')" loading="lazy">
    </a>
  #else
    <img src="$Extras.satellite_img" data-live-src="$Extras.satellite_img" alt="$gettext('Satellite')" loading="lazy">
  #end if
  </div>
</section>
#end if

#if 'google_map_apikey' in $Extras
<section class="panel">
  <div class="panel-head">
    <h2>$gettext("Location")</h2>
  </div>
  <div class="panel-body flush">
    <div id="map_canvas" role="img"
         aria-label="$gettext('Map of the station location')"></div>
  </div>
</section>
<script>
  function init_map() {
    var latlng = {lat: $station.latitude_f, lng: $station.longitude_f};
    var map = new google.maps.Map(document.getElementById("map_canvas"), {
      zoom: 9,
      center: latlng,
      mapTypeControl: false,
      streetViewControl: false
    });
    new google.maps.Marker({position: latlng, map: map, title: "$station.location"});
  }
</script>
<script src="https://maps.googleapis.com/maps/api/js?key=${Extras.google_map_apikey}&callback=init_map"
        async defer></script>
#end if
