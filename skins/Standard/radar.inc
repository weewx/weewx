#if $Extras.has_key('radar_img')
<div id='radar_widget' class="widget">
  #if $Extras.has_key('radar_url')
  <a  href="$Extras.radar_url">
  #end if
    <img src="$Extras.radar_img" alt="Radar" />
  #if $Extras.has_key('radar_url')
  </a>
  #end if
</div>
#end if
