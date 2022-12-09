## satellite module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#if 'satellite_img' in $Extras
<div id='satellite_widget' class="widget">
  <div class="widget_title">
    Satellite
    <a class="widget_control"
      onclick="toggle_widget('satellite')">&diams;</a>
  </div>

  <div class="widget_contents">
    #if 'satellite_url' in $Extras
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
