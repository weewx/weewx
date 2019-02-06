## satellite module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

#if $Extras.has_key('satellite_img')
<div id='satellite_widget' class="widget">
  <div class="widget_title">
    Satellite
    <a class="widget_control"
      onclick="toggle_widget('satellite')">&diams;</a>
  </div>

  <div class="widget_contents">
    #if $Extras.has_key('satellite_url')
    #set $saturl = $Extras.satellite_url
    #else
    #set $saturl = $Extras.satellite_img
    #end if
    <a href="$saturl">
      <img src="$Extras.satellite_img" alt="Satellite" />
    </a>
  </div>
</div>
#end if
