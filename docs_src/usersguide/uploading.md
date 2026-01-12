# Uploading to other sites

WeeWX comes with a number of 'uploaders', which can be enabled in
order to periodically upload your web pages and/or data to other
sites.

A long list of third-party uploaders is available in the 
[wiki](https://github.com/weewx/weewx/wiki#uploaders).

The built-in uploaders are briefly discussed here. 

<!---------------------------->

## RESTful Services

These are located in the [`[StdRESTful]`](../../reference/weewx-options/stdrestful/) 
section of `weewx.conf`.

<!---------------------------->

### StationRegistry

Adds your system to the public weewx map of registered sites at
[https://weewx.com/stations.html](https://weewx.com/stations.html).

If enabled, the station will periodically register with the
weewx station registry to keep its registration active.  Stale
registrations are automatically removed from the registry and map
eventually if they are not reregistered.

This is disabled by default.

For configuration details consult the 
[`[[StationRegistry]]`](../../reference/weewx-options/stdrestful/#stationregistry)
section of the Reference Guide.

### AWEKAS

Posts your weather data to the 
[AWEKAS - Automatisches WEtterKArten System](http://www.awekas.at).

From their web site:

_AWEKAS is an abbrevation for “Automatic WEather map (german: KArten)
System”. It is a system that processes indicated values of private
weather stations graphically, generates weather maps and evaluates
the data.

This is disabled by default.

For configuration details consult the
[`[[AWEKAS]]`](../../reference/weewx-options/stdrestful/#awekas) section of the
Reference Guide.

### CWOP

Posts your weather data to the 
[Citizen Weather Observer Program (CWOP)](http://wxqa.com/).

From their web site:

_The Citizen Weather Observer Program (CWOP) is a public-private
partnership with three goals: 1) to collect weather data contributed
by citizens; 2) to make these data available for weather services
and homeland security; and 3) to provide feedback to the data
contributors so they have the tools to check and improve their data
quality. In fact, the web address, wxqa.com, stands for weather
quality assurance._

This is disabled by default.

For configuration details consult the
[`[[CWOP]]`](../../reference/weewx-options/stdrestful/#cwop) section of the
Reference Guide.

### PWSWeather

Posts your weather data to the [PWSweather service](https://www.pwsweather.com).

From their web site:

_AerisWeather owns and operates PWSweather - a community that
provides personal weather station owners with a user-friendly
dashboard to monitor, manage, and archive their data. Each contributor's
data is also made available in AerisWeather's API via the PWSweather
Contributor Plan._

This is disabled by default.

For configuration details consult the
[`[[PWSweather]]`](../../reference/weewx-options/stdrestful/#pwsweather)
section of the Reference Guide.

### WOW 
Posts your weather data to the [WOW service](https://wow.metoffice.gov.uk).

This legacy uploader supports the Met Office Weather Observations
Website (WOW), which is being decommissioned beginning in January
2026.

From their web site:

_After more than a decade of supporting crowd-sourced weather observations
and citizen science, the Met Office will begin retiring the Weather
Observations Website (WOW) from January, with full decommissioning
planned for late 2026.....there will be no direct replacement for WOW
 in the UK._

This is disabled by default.

For configuration details consult the
[`[[WOW]]`](../../reference/weewx-options/stdrestful/#wow)
section of the Reference Guide.

### WOW-BE
Posts your weather data to the [WOW-BE service](https://wow.meteo.be).

This is a relaunched variant of the legacy WOW service above, with a
stated goal to have more open software and data according to their
web site.

This is disabled by default.

For configuration details consult the
[`[[WOW-BE]]`](../../reference/weewx-options/stdrestful/#wow-be)
section of the Reference Guide.

### Wunderground
Posts your weather data to the 
[Weather Underground service](https://www.wunderground.com).  The 
uploader supports both regular and rapidfire posting.

Weather Underground claims to be the "Internet's 1st weather service"
dating back to 1993.

This is disabled by default.

For configuration details consult the 
[`[[Wunderground]]`](../../reference/weewx-options/stdrestful/#wunderground)
section of the Reference Guide.

<!---------------------------->
## StdReport Services

These are located in the [`[StdReport]`](../../reference/weewx-options/stdreport/) section of `weewx.conf`.

<!---------------------------->

### FTP

Uploads selected pieces of your output data via FTP protocol to a
remote system.

This is disabled by default.

For configuration details, see the
  [`[[FTP]]`](../../reference/weewx-options/stdreport/#ftp)
section of the Reference Guide.

### RSYNC

Uploads selected pieces of your output data via RSYNC protocol over
a SSH transport layer to a remote system.  The RSYNC uploader is
generally considered to be faster and more stable than the FTP
uploader, although it does require some one-time setup by the user.

This is disabled by default.

For configuration details, consult the 
[`[[RSYNC]]`](../../reference/weewx-options/stdreport/#rsync)
section of the Reference Guide.


