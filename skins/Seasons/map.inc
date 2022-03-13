## map module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#if 'google_map_apikey' in $Extras
<div id='map_widget' class="widget">
  <div class="widget_title">
    Location
    <a class="widget_control"
      onclick="toggle_widget('map')">&diams;</a>
  </div>
  <div class="widget_contents">
    <div id='map_canvas'"></div>  
  </div>
</div>

<script>
function init_map() {
  var latlng = {lat: $station.latitude_f, lng: $station.longitude_f};
  var map = new google.maps.Map(document.getElementById("map_canvas"), {
    zoom: 8,
    center: latlng
  });
  var marker = new google.maps.Marker({
    position: latlng,
    map: map,
    title: "$station.location"
  });
}
</script>
<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?key=${Extras.google_map_apikey}&callback=init_map" async defer>
</script>
#end if
