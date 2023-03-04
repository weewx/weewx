## analytics module weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

## Include the Google Analytics code if an Id has been specified

#if 'googleAnalyticsId' in $Extras
<script type="text/javascript">
var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
</script>
<script type="text/javascript">
try {
  var pageTracker = _gat._getTracker("$Extras.googleAnalyticsId");
  pageTracker._trackPageview();
} catch(err) {}
</script>
#end if
