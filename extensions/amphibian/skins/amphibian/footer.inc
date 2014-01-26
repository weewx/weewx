## amphibian for weewx - Copyright 2012-2013 Matthew Wall
## $Id$

<div class='wide bordered line cell' style='clear:both'>
  <div class='leftCell'>
    weewx: $station.uptime - server: $station.os_uptime - weewx $station.version with $station.hardware - amphibian $Extras.version
  </div>
</div>

## Include the Google Analytics code if there is an ID available:
#if $Extras.has_key('googleAnalyticsId')
<script type="text/javascript">
  var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
  document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
</script>
<script type="text/javascript">
  try{
  var pageTracker = _gat._getTracker("$Extras.googleAnalyticsId");
  pageTracker._trackPageview();
  } catch(err) {}
</script>
#end if
