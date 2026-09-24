## footer module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The footer of every page: the station's particulars, the WeeWX line and the RSS
## link. 'data-live-panel' makes horizon.js replace the footer on each new archive
## record, which keeps the uptime current on a page that is left open.
##
## On a climate year page the footer has only the WeeWX line and the RSS link (see
## climate-%Y.html.tmpl).
      <footer class="site-footer"#if $page != 'climate_year' then ' data-live-panel="about"' else ''#>
#if $page != 'climate_year'
        <h2 class="visually-hidden">$gettext("About this station")</h2>
        <dl class="station-facts">
          <div><dt>$gettext("Latitude")</dt><dd>$station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2]</dd></div>
          <div><dt>$gettext("Longitude")</dt><dd>$station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2]</dd></div>
          <div><dt>$pgettext("Geographical", "Altitude")</dt><dd>$station.altitude</dd></div>
          <div><dt>$gettext("Hardware")</dt><dd>$station.hardware</dd></div>
          <div><dt>$gettext("WeeWX uptime")</dt><dd>$station.uptime.long_form</dd></div>
          <div><dt>$gettext("WeeWX version")</dt><dd>$station.version</dd></div>
        </dl>
#end if
        <p class="colophon">$gettext("This station is controlled by <a href='https://weewx.com'>WeeWX</a>, an experimental weather software system written in Python.")
          <a href="rss.xml">$gettext("RSS")</a></p>
      </footer>
