# [StdRESTful]

This section is for configuring the StdRESTful services, which upload to simple
[RESTful](https://en.wikipedia.org/wiki/Representational_State_Transfer)
services such as:

* [Weather Underground](https://www.wunderground.com/)
* [PWSweather.com](https://www.pwsweather.com/)
* [CWOP](http://www.wxqa.com/)
* [British Weather Observations Website (WOW)](https://wow.metoffice.gov.uk/)
* [Automatisches Wetterkarten System (AWEKAS)](https://www.awekas.at/)


## General options for each RESTful Service

#### log_success

If you set a value for `log_success` here, it will override the value set at
the [top-level](general.md#log_success) and will apply only to RESTful
services. In addition, `log_success` can be set for individual services by
putting them under the appropriate subsection (*e.g.*, under `[[CWOP]]`).

#### log_failure

If you set a value for `log_failure` here, it will override the value set at
the [top-level](general.md#log_failure) and will apply only to RESTful
services. In addition, `log_failure` can be set for individual services by
putting them under the appropriate subsection (*e.g.*, under `[[CWOP]]`).


## [[StationRegistry]]

A registry of WeeWX weather stations is maintained at `weewx.com`. Stations
are displayed on a map and a list at
[https://weewx.com/stations.html](https://weewx.com/stations.html).

How does the registry work? Individual weather stations periodically contact
the registry. Each station provides a unique URL to identify itself, plus 
other information such as the station type, Python version, WeeWX version
and installation method. No personal information, nor any meteorological data,
is sent.

To add your station to this list, you must do two things:

1. Enable the station registry by setting option `register_this_station` to
`true`. Your station will contact the registry once per day. If your station
does not contact the registry for about a month, it will be removed from the
list.

2. Provide a value for option `station_url`. This value must be unique, so
choose it carefully.

``` ini
[StdRestful]
    [[StationRegistry]]
        register_this_station = True
        description="Beach side weather"
        station_url = https://acme.com
```

#### ==register_this_station==

Set this to `true` to register the weather station.

#### description

A description of the station. If no description is specified, the 
[`location`](stations.md#location) from section `[Station]` will be used.

#### station_url

The URL to the weather station. If no URL is specified, the
[`station_url`](stations.md#station_url) from section `[Station]`
will be used. It must be a valid URL. In particular, it must start with either
`http://` or `https://`.

#### log_success

If you set a value here, it will apply only to the station registry.

#### log_failure

If you set a value here, it will apply only to the station registry.


## [[AWEKAS]]

WeeWX can send your current data to the [Automatisches Wetterkarten System
(AWEKAS)](https://www.awekas.at/). If you wish to do this, set the option
`enable` to `true`, then set options `username` and `password` appropriately.
When you are done, it will look something like this:

``` ini
[StdRestful]
    [[AWEKAS]]
        enable = true
        username = joeuser
        password = XXX 
```

#### enable

Set to `true` to enable posting to AWEKAS. Optional. Default is `false`.

#### username

Set to your AWEKAS username (e.g., `joeuser`). Required.

#### password

Set to your AWEKAS password. Required.

#### language

Set to your preferred language. Default is `en`.

#### log_success

If you set a value here, it will apply only to logging for AWEKAS.

#### log_failure

If you set a value here, it will apply only to logging for AWEKAS.

#### retry_login

How long to wait in seconds before retrying a bad login. If set to zero, no
retry will be attempted. Default is `3600`.

#### post_interval

The interval in seconds between posts. Setting this value to zero will cause
every archive record to be posted. Optional. Default is zero.



## [[CWOP]]

WeeWX can send your current data to the
[Citizen Weather Observer Program](http://www.wxqa.com/). If you wish to do
this, set the option `enable` to `true`, then set the option `station` to
your CWOP station code. If your station is an amateur radio APRS station,
you will have to set `passcode` as well. When you are done, it will look
something like

``` ini
[StdRestful]
    [[CWOP]]
        enable = true
        station = CW1234
        passcode = XXX    # Replace with your passcode (APRS stations only)
        post_interval = 600
```

#### enable

Set to `true` to enable posting to the CWOP. Optional. Default is `false`.

#### station

Set to your CWOP station ID (e.g., CW1234) or amateur radio callsign (APRS).
Required.

#### passcode

This is used for APRS (amateur radio) stations only. Set to the passcode given
to you by the CWOP operators. Required for APRS stations, ignored for others.

#### post_interval

The interval in seconds between posts. Because CWOP is heavily used, the
operators discourage very frequent posts. Every 5 minutes (300 seconds) is
fine, but they prefer every 10 minutes (600 s) or even longer. Setting this
value to zero will cause every archive record to be posted. Optional. Default
is `600`.

#### stale

How old a record can be in seconds before it will not be used for a catch-up.
CWOP does not use the timestamp on a posted record. Instead, they use the wall
clock time that it came in. This means that if your station is off the air for
a long period of time, then when WeeWX attempts a catch-up, old data could be
interpreted as the current conditions. Optional. Default is `600`.

#### server_list

A comma-delimited list of the servers that should be tried for uploading data.
Optional. Default is: `cwop.aprs.net:14580, cwop.aprs.net:23`

#### log_success

If you set a value here, it will apply only to logging for CWOP.

#### log_failure

If you set a value here, it will apply only to logging for CWOP.


## [[PWSweather]]

WeeWX can send your current data to the
[PWSweather.com](https://www.pwsweather.com/) service. If you wish to do this,
set the option `enable` to `true`, then set the options `station` and
`password` appropriately. When you are done, it will look something like this:

``` ini
[StdRestful]
    [[PWSweather]]
        enable = true
        station = BOISE
        password = XXX
```

#### enable

Set to `true` to enable posting to the PWSweather. Optional. Default is
`false`.

#### station

Set to your PWSweather station ID (e.g., `BOISE`). Required.

#### password

Set to your PWSweather password. Required.

#### log_success

If you set a value here, it will apply only to logging for PWSweather.

#### log_failure

If you set a value here, it will apply only to logging for PWSweather.

#### retry_login

How long to wait in seconds before retrying a bad login. Default is `3600`
(one hour).

#### post_interval

The interval in seconds between posts. Setting this value to zero will cause
every archive record to be posted. Optional. Default is zero.


## [[WOW]]
WeeWX can send your current data to the
[British Weather Observations Website (WOW)](https://wow.metoffice.gov.uk/)
service. If you wish to do this, set the option `enable` to `true`, then set
options `station` and `password` appropriately. Read [Importing Weather Data
into WOW](https://wow.metoffice.gov.uk/support/dataformats#automatic) on how
to find your site's username and how to set the password for your site. When
you are done, it will look something like this:

``` ini
[StdRestful]
    [[WOW]]
        enable = true
        station = 12345678
        password = XXX
```

#### enable

Set to `true` to enable posting to WOW. Optional. Default is `false`.

#### station

Set to your WOW station ID (e.g., `12345678` for Pre June 1996 sites, or
`6a571450-df53-e611-9401-0003ff5987fd` for later ones). Required.

#### password

Set to your WOW Authentication Key. Required. This is not the same as your
WOW user password. It is a 6 digit numerical PIN, unique for your station.

#### log_success

If you set a value here, it will apply only to logging for WOW.

#### log_failure

If you set a value here, it will apply only to logging for WOW.

#### retry_login

How long to wait in seconds before retrying a bad login. Default is `3600`
(one hour).

#### post_interval

The interval in seconds between posts. Setting this value to zero will cause
every archive record to be posted. Optional. Default is zero.


## [[Wunderground]] 

WeeWX can send your current data to the
[Weather Underground](https://www.wunderground.com/). If you wish to post to
do this, set the option `enable` to `true`,  then specify a station (e.g.,
`KORBURNS99`). Use the station key for the password.

When you are done, it will look something like this:

``` ini
[StdRestful]
    [[Wunderground]]
        enable = true
        station = KORBURNS99
        password = A331D1SIm
        rapidfire = false
```

#### enable

Set to `true` to enable posting to the Weather Underground. Optional. Default
is `false`.

#### station

Set to your Weather Underground station ID (e.g., `KORBURNS99`). Required.

#### password

Set to the station "key". You can find this at:

https://www.wunderground.com/member/devices.

#### rapidfire

Set to `true` to have WeeWX post using the [Weather Underground's "Rapidfire"
protocol](https://www.wunderground.com/weatherstation/rapidfirehelp.asp). This
will send a post to the WU site with every LOOP packet, which can be as often
as every 2.5 seconds in the case of the Vantage instruments. Not all
instruments support this. Optional. Default is `false`.

#### rtfreq

When rapidfire is set, the `rtfreq` parameter is sent, and should correspond
to "the frequency of updates in seconds". Optional. Default is `2.5`.

#### archive_post

This option tells WeeWX to post on every archive record, which is the normal
"PWS" mode for the Weather Underground. Because they prefer that you either
use their "Rapidfire" protocol, or their PWS mode, but not both, the default
for this option is the opposite for whatever you choose above for option
rapidfire. However, if for some reason you want to do both, then you may
set both options to `true`.

#### post_indoor_observations

In the interest of respecting your privacy, WeeWX does not post indoor
temperature or humidity to the Weather Underground unless you set this
option to `true`. Default is `false`.

#### log_success

If you set a value here, it will apply only to logging for the Weather
Underground.

#### log_failure

If you set a value here, it will apply only to logging for the Weather
Underground.

#### retry_login

How long to wait in seconds before retrying a bad login. Default is `3600`
(one hour).

#### post_interval

The interval in seconds between posts. Setting this value to zero will cause
every archive record to be posted. Optional. Default is zero.

#### force_direction

The Weather Underground has a bug where they will claim that a station is
"unavailable" if it sends a null wind direction, even when the wind speed is
zero. Setting this option to `true` causes the software to cache the last
non-null wind direction and use that instead of sending a null value. Default
is `False`.

#### [[[Essentials]]]

Occasionally (but not always!) when the Weather Underground is missing a data
point it will substitute the value zero (0.0), thus messing up statistics and
plots. For all observation types listed in this section, the post will be
skipped if that type is missing. For example:

``` ini
[StdRestful]
    [[Wunderground]]
        ...
        [[[Essentials]]]
            outTemp = True
```

would cause the post to be skipped if there is no outside temperature
(observation type `outTemp`).
