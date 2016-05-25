#if $Extras.has_key('radar_img')
<div id="radar" class="widget">
  #if $Extras.has_key('radar_url')
  <a href="$Extras.radar_url">
  #end if
    <img src="$Extras.radar_img" alt="$Extras.radar_label" />
  #if $Extras.has_key('radar_url')
  </a>
  #end if
</div>
#end if
