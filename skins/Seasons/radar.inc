## radar module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo

#if $Extras.has_key('radar_img')
<div id='radar_widget' class="widget">
  <div class="widget_title">
    Radar
    <a class="widget_control"
      onclick="toggle_widget('radar')">&diams;</a>
  </div>

  <div class="widget_contents">
    #if $Extras.has_key('radar_url')
    <a  href="$Extras.radar_url">
    #end if
      <img src="$Extras.radar_img" alt="Radar" />
    #if $Extras.has_key('radar_url')
    </a>
    #end if
  </div>
</div>
#end if
