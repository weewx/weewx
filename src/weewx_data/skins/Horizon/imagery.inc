## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## All three are opt-in: they only appear if the corresponding entry exists in
## [Extras]. See skin.conf for the option names.
##
## These panels carry no 'data-live-panel', unlike the others. Replacing the map
## panel would throw away the Google Maps object inside it. The radar and satellite
## pictures come from someone else's server, with cache headers of their own, so
## re-rendering this panel would not fetch a newer one. 'data-live-src' names the
## picture to request again, which the script does under a fresh query string once
## a new record arrives.

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
