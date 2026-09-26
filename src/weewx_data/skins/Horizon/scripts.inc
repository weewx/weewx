## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## Every page loads its scripts at the end of <body>. The markup is then in place, so
## each script calls its start function at once, without waiting for DOMContentLoaded.
## The order matters. horizon.js reads window.HORIZON. forecast.js and climate.js use
## 'units' and 'tempColour', which horizon.js adds to window.HORIZON. The scripts in
## 'custom_js' come last, so they run after the skin has set up the page.
#set $archived = $page == 'climate_year'
#set $charted = $page in ('index', 'telemetry')
#set $forecast = $page == 'index' and 'forecast' in $to_list($DisplayOptions.get('panels', ['forecast']))
## A climate year page has no live update. On a climate year page, '$current' is the
## archive record at the end of the year. For the running year that record does not
## exist yet, so 'generated' takes the latest archive record, '$latest'.
#if $archived
  #set $refresh = 0
  #set $generated = $latest.dateTime.raw
#else
  #set $refresh = $to_int($DisplayOptions.get('refresh_interval', 60))
  #set $generated = $current.dateTime.raw
#end if
    #include "top.inc"
#if $charted or $page in ('climate', 'climate_year')
    <script src="echarts.min.js"></script>
#end if
    <script>
      window.HORIZON = {
        page: "$page",
        dataDir: "data",
        refreshInterval: $refresh,
        generated: #if $generated is None then 'null' else $generated#,
        station: "$station.location",
        weekStart: $station.week_start,
#if $charted
  #if $page == 'telemetry'
    #set $groups = $to_list($DisplayOptions.get('telemetry_plot_groups', ['rx', 'volt']))
  #else
    #set $groups = $to_list($DisplayOptions.get('plot_groups', ['tempdew', 'wind', 'rain']))
  #end if
        periods: $jsonize($to_list($DisplayOptions.get('periods', ['day', 'week', 'month', 'year']))),
        plotGroups: $jsonize($groups),
#end if
#if $forecast
## forecast.js fetches the forecast for the station's position from Open-Meteo.
## Three decimals are about 100 m, finer than any forecast model resolves. The
## rounding keeps the station's exact position out of Open-Meteo's logs.
        latitude: ${'%.3f' % $station.latitude_f},
        longitude: ${'%.3f' % $station.longitude_f},
        forecast: {
  #set $fc = $DisplayOptions.get('Forecast', {})
          fetch: #if $to_bool($fc.get('browser_fetch', True)) then 'true' else 'false'#,
          hours: $to_int($fc.get('hours', 8)),
          days: $to_int($fc.get('days', 7)),
## 'sky' maps each WMO 4677 weather code to its translated name. forecast.js holds
## only the codes and their icons.
  #set $sky = {}
  #for $code, $said in [(0, 'Clear sky'), (1, 'Mainly clear'),
                        (2, 'Partly cloudy'), (3, 'Overcast'),
                        (45, 'Fog'), (48, 'Freezing fog'),
                        (51, 'Light drizzle'), (53, 'Drizzle'),
                        (55, 'Heavy drizzle'), (56, 'Light freezing drizzle'),
                        (57, 'Freezing drizzle'), (61, 'Light rain'),
                        (63, 'Rain'), (65, 'Heavy rain'),
                        (66, 'Light freezing rain'), (67, 'Freezing rain'),
                        (71, 'Light snow'), (73, 'Snow'), (75, 'Heavy snow'),
                        (77, 'Snow grains'), (80, 'Light rain showers'),
                        (81, 'Rain showers'), (82, 'Violent rain showers'),
                        (85, 'Light snow showers'), (86, 'Snow showers'),
                        (95, 'Thunderstorm'), (96, 'Thunderstorm with light hail'),
                        (99, 'Thunderstorm with hail')]
    #silent $sky[$str($code)] = $gettext($said)
  #end for
          sky: $jsonize($sky)
        },
#end if
        text: {
          noData: "$gettext('No data for this period')",
          showData: "$gettext('Show data as table')",
          time: "$gettext('Time')",
          now: "$gettext('Now')",
          today: "$gettext('Today')",
          asConfigured: "$gettext('Default')",
          earlier: "$gettext('Earlier')",
          later: "$gettext('Later')",
          thinned: "$gettext('thinned')",
          linkCopied: "$gettext('Link copied')",
          copyLink: "$gettext('Copy this link:')",
          saveImage: "$gettext('Save image')",
          toDark: "$gettext('Switch to dark theme')",
          toLight: "$gettext('Switch to light theme')"
        }
      };
    </script>
    <script src="horizon.js"></script>
#if $forecast
    <script src="forecast.js"></script>
#end if
#if $page in ('climate', 'climate_year')
    <script src="climate.js"></script>
#end if
#for $js in $to_list($DisplayOptions.get('custom_js', []))
  #if $js
    <script src="$js"></script>
  #end if
#end for
