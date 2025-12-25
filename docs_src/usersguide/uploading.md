# Uploading to other sites

WeeWX comes with a number of 'uploaders' which can be enabled in
order to periodically upload your web pages and/or data to other
sites.

A long list of third-party uploaders is available in the 
[wiki](https://github.com/weewx/weewx/wiki#uploaders).

The built-in uploaders are briefly discussed here. Each is 'disabled'
by default and may be optionally enabled by editing weewx.conf to
set 'enable=true' and setting any required parameters for the
uploader.

<!---------------------------->

## RESTful Services

These are located in the [StdRESTful] section of weewx.conf with more
details in the WeeWX [Reference](../reference/weewx-options/stdrestful/)
documentation.

<!---------------------------->

### StationRegistry

Adds your system to the public weewx map of registered sites at
[https://weewx.com/stations.html](https://weewx.com/stations.html).

Individual weather stations periodically contact the registry. Each
station provides a unique URL to identify itself, plus other
information such as the station type and WeeWX version. No personal
information, nor any meteorological data, is sent.

This is disabled by default.

### AWEKAS

Posts your weather data to the 
[AWEKAS - Automatisches WEtterKArten System](http://www.awekas.at).

From their web site:

_AWEKAS is an abbrevation for “Automatic WEather map (german: KArten)
System”. It is a system that processes indicated values of private
weather stations graphically, generates weather maps and evaluates
the data._

### CWOP

Posts your weather data to the 
[Citizen Weather Observer Program (CWOP)](cwop.aprs.net).

From their web site:

_The Citizen Weather Observer Program (CWOP) is a public-private
partnership with three goals: 1) to collect weather data contributed
by citizens; 2) to make these data available for weather services
and homeland security; and 3) to provide feedback to the data
contributors so they have the tools to check and improve their data
quality. In fact, the web address, wxqa.com, stands for weather
quality assurance._

### PWSWeather

Posts your weather data to the [PWSweather service](https://www.pwsweather.com).

From their web site:

_AerisWeather owns and operates PWSweather - a community that
provides personal weather station owners with a user-friendly
dashboard to monitor, manage, and archive their data. Each contributor's
data is also made available in AerisWeather's API via the PWSweather
Contributor Plan._

### WOW 
Posts your weather data to the [WOW service](https://wow.metoffice.gov.uk).

This legacy uploader supports the Met Office Weather Observations
Website (WOW) which is being decommissioned beginning in January
2026.

### WOW-BE
Posts your weather data to the [WOW-BE service](https://wow.meteo.be).

This is a relaunched more open data and open software update of the
WOW service that is being decommissioned beginning early 2026.


### Wunderground
Posts your weather data to the 
[Weather Underground service](https://www.wunderground.com).  The 
uploader supports both regular and rapidfire posting.

Weather Underground claims to be the "Internet's 1st weather service"
dating back to 1993.

<!---------------------------->
## StdReport Services

These are located in the [StdReport] section of weewx.conf with more
details in the WeeWX [Reference](../reference/weewx-options/stdreport/)
documentation.


<!---------------------------->

### FTP

Uploads selected pieces of your output data via FTP protocol to a
remote system.

### RSYNC

Uploads selected pieces of your output data via RSYNC protocol over
a SSH transport layer to a remote system.  The RSYNC uploader is
generally considered to be faster and more stable than the FTP
uploader, although it does require some one-time setup by the user.



