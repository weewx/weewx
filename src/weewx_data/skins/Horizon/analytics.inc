## Copyright (c) 2026 the WeeWX contributors
## Adapted from the Seasons skin, copyright (c) Tom Keffer and Matthew Wall.
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

## If a Google Analytics GA4 code has been specified, include it.

#if 'googleAnalyticsId' in $Extras
    <script async src="https://www.googletagmanager.com/gtag/js?id=$Extras.googleAnalyticsId"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', '$Extras.googleAnalyticsId');
    </script>
#end if
