# $Id$
# Copyright 2013 Matthew Wall
"""weewx module that provides forecasts

API_VERSION: 2

Design

   The forecasting module supports various forecast methods for weather and
   tides.  Weather forecasting can be downloaded (NWS, WU) or generated
   (Zambretti).  Tide forecasting is generated using XTide.

   To enable forecasting, add a [Forecast] section to weewx.conf, add a
   section to [Databases] to indicate where forecast data should be stored,
   then append user.forecast.XXXForecast to the WxEngine service_list for each
   forecasting method that should be enabled.  Details in the Configuration
   section below.

   A single table stores all forecast information.  This means that each record
   may have many unused fields, but it makes querying and database management
   a bit easier.  It also minimizes the number of variables needed for use in
   templates.  There are a few fields in each record that are common to every
   forecast method.  See the Database section in this file for details.

   The forecasting runs in a separate thread.  It is fire-and-forget - the
   main thread starts a forecasting thread and does not bother to check its
   status.  The main thread will never run more than one thread per forecast
   method.

Prerequisites

   The XTide forecast requires xtide.  On debian systems, do this:
     sudo apt-get install xtide

   The WU forecast requires json.  json should be included in python 2.6 and
   2.7.  For python 2.5 on debian systems, do this:
     sudo apt-get install python-cjson

Configuration

   Some parameters can be defined in the Forecast section of weewx.conf, then
   overridden for specific forecasting methods as needed.  In the sample
   configuration below, the commented parameters will default to the indicated
   values.  Uncommented parameters must be specified.

[Forecast]
    # The database in which to record forecast information, defined in the
    # 'Databases' section of the weewx configuration.
    database = forecast_sqlite

    # How often to calculate/download the forecast, in seconds
    #interval = 1800

    # How long to keep old forecasts, in seconds.  use None to keep forever.
    #max_age = 604800

    [[XTide]]
        # Location for which tides are desired
        location = Boston

        # How often to generate the tide forecast, in seconds
        #interval = 1209600

        # How often to prune old tides from database, None to keep forever
        #max_age = 2419200

    [[Zambretti]]
        # hemisphere can be NORTH or SOUTH
        #hemisphere = NORTH

        # The interval determines how often the trend is calculated
        #interval = 600

        # The lower and upper pressure define the range to which the forecaster
        # should be calibrated, in units of millibar (hPa).  The 'barometer'
        # pressure (not station pressure) is used to calculate the forecast.
        #lower_pressure = 950.0
        #upper_pressure = 1050.0

    [[NWS]]
        # First figure out your forecast office identifier (foid), then request
        # a point forecast using a url of this form in a web browser:
        #   http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt&issuedby=YOUR_THREE_LETTER_FOID
        # Scan the output for a service location identifier corresponding
        # to your location.

        # National Weather Service location identifier
        lid = MAZ014

        # National Weather Service forecast office identifier
        foid = BOX

        # URL for point forecast matrix
        #url = http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt

        # How often to download the forecast, in seconds
        #interval = 10800

    [[WU]]
        # An API key is required to access the weather underground.
        # obtain an API key here:
        #   http://www.wunderground.com/weather/api/
        api_key = KEY

        # The location for the forecast can be one of the following:
        #   CA/San_Francisco     - US state/city
        #   60290                - US zip code
        #   Australia/Sydney     - Country/City
        #   37.8,-122.4          - latitude,longitude
        #   KJFK                 - airport code
        #   pws:KCASANFR70       - PWS id
        #   autoip               - AutoIP address location
        #   autoip.json?geo_ip=38.102.136.138 - specific IP address location
        # If no location is specified, station latitude and longitude are used
        #location = 02139

        # There are two types of forecast available, daily for 10 days and
        # hourly for 10 days.  Default is hourly for 10 days.
        #forecast_type = forecast10day
        #forecast_type = hourly10day

        # How often to download the forecast, in seconds
        #interval = 10800

[Databases]
    ...
    # a typical installation will use either sqlite or mysql

    [[forecast_sqlite]]
        root = %(WEEWX_ROOT)s
        database = archive/forecast.sdb
        driver = weedb.sqlite

    [[forecast_mysql]]
        host = localhost
        user = weewx
        password = weewx
        database = forecast
        driver = weedb.mysql

[Engines]
    [[WxEngine]]
        # append only the forecasting service(s) that you need
        service_list = ... , user.forecast.ZambrettiForecast, user.forecast.NWSForecast, user.forecast.WUForecast, user.forecast.XTideForecast


Skin Configuration

  To use the forecast variables in a skin, extend the search_list by adding
  something like this to weewx.conf:

[StdReport]
    [[StandardReport]]
        [[[CheetahGenerator]]]
            search_list_extensions = user.forecast.ForecastVariables

   Here are the options that can be specified in the skin.conf file.  The
   values below are the defaults.  Add these only to override the defaults.

[Forecast]
    [[Labels]]
        [[[Directions]]]
            # labels for compass directions
            N = N
            NNE = NNE
            NE = NE
            ENE = ENE
            E = E
            ESE = ESE
            SE = SE
            SSE = SSE
            S = S
            SSW = SSW
            SW = SW
            WSW = WSW
            W = W
            WNW = WNW
            NW = NW
            NNW = NNW

        [[[Tide]]]
            # labels for tides
            H = High Tide
            L = Low Tide

        [[[Zambretti]]]
            # mapping between zambretti codes and descriptive labels
            A = Settled fine
            B = Fine weather
            C = Becoming fine
            D = Fine, becoming less settled
            E = Fine, possible showers
            F = Fairly fine, improving
            G = Fairly fine, possible showers early
            H = Fairly fine, showery later
            I = Showery early, improving
            J = Changeable, mending
            K = Fairly fine, showers likely
            L = Rather unsettled clearing later
            M = Unsettled, probably improving
            N = Showery, bright intervals
            O = Showery, becoming less settled
            P = Changeable, some rain
            Q = Unsettled, short fine intervals
            R = Unsettled, rain later
            S = Unsettled, some rain
            T = Mostly very unsettled
            U = Occasional rain, worsening
            V = Rain at times, very unsettled
            W = Rain at frequent intervals
            X = Rain, very unsettled
            Y = Stormy, may improve
            Z = Stormy, much rain

        [[[Weather]]]
            # labels for components of a weather forecast
            temp = Temperature
            dewpt = Dewpoint
            humidity = Relative Humidity
            winddir = Wind Direction
            windspd = Wind Speed
            windchar = Wind Character
            windgust = Wind Gust
            clouds = Sky Coverage
            windchill = Wind Chill
            heatindex = Heat Index
            obvis = Obstructions to Visibility

            # types of precipitation
            rain = Rain
            rainshwrs = Rain Showers
            sprinkles = Rain Sprinkles
            tstms = Thunderstorms
            drizzle = Drizzle
            snow = Snow
            snowshwrs = Snow Showers
            flurries = Snow Flurries
            sleet = Ice Pellets
            frzngrain = Freezing Rain
            frzngdrzl = Freezing Drizzle
            hail = Hail

            # codes for sky cover
            CL = Clear
            FW = Few Clouds
            SC = Scattered Clouds
            BK = Broken Clouds
            B1 = Mostly Cloudy
            B2 = Considerable Cloudiness
            OV = Overcast

            # codes for precipitation
            S = Slight Chance
            C = Chance
            L = Likely
            O = Occasional
            D = Definite

            IS = Isolated
            #SC = Scattered      # conflicts with scattered clouds
            NM = Numerous
            EC = Extensive Coverage
            PA = Patchy
            AR = Areas
            WD = Widespread

            # quantifiers for the precipitation codes
            Sq  = '<20%'
            Cq  = '30-50%'
            Lq  = '60-70%'
            Oq  = '80-100%'
            Dq  = '80-100%'

            ISq = '<20%'
            SCq = '30-50%'
            NMq = '60-70%'
            ECq = '80-100%'
            PAq = '<25%'
            ARq = '25-50%'
            WDq = '>50%'

            # codes for obstructions to visibility
            F = Fog
            PF = Patchy Fog
            F+ = Dense Fog
            PF+ = Patchy Dense Fog
            H = Haze
            BS = Blowing Snow
            K = Smoke
            BD = Blowing Dust
            AF = Volcanic Ash
            M = Mist
            FF = Freezing Fog
            DST = Dust
            SND = Sand
            SP = Spray
            DW = Dust Whirls
            SS = Sand Storm
            LDS = Low Drifting Snow
            LDD = Low Drifting Dust
            LDN = Low Drifting Sand
            BN = Blowing Sand
            SF = Shallow Fog

            # codes for wind character:
            LT = Light
            GN = Gentle
            BZ = Breezy
            WY = Windy
            VW = Very Windy
            SD = Strong/Damaging
            HF = Hurricane Force

Variables for Templates

  Here are the variables that can be used in template files.

$forecast.label(module, key)

XTide

  The index is the nth event from the current time.

$forecast.xtide(0).dateTime     date/time that the forecast was requested
$forecast.xtide(0).issued_ts    date/time that the forecast was created
$forecast.xtide(0).event_ts     date/time of the event
$forecast.xtide(0).hilo         H or L
$forecast.xtide(0).offset       depth above/below mean low tide
$forecast.xtide(0).location     where the tide is forecast

for tide in $forecast.xtides
  $tide.event_ts $tide.hilo $tide.offset

Zambretti

  The Zambretti forecast is typically good for up to 6 hours from when the
  forecast was made.  The time the forecast was made and the time of the
  forecast are always the same.  The forecast consists of a code and an
  associated textual description.

$forecast.zambretti.dateTime    date/time that the forecast was requested
$forecast.zambretti.issued_ts   date/time that the forecast was created
$forecast.zambretti.event_ts    date/time of the forecast
$forecast.zambretti.code        zambretti forecast code (A-Z)

NWS, WU

  Elements of a weather forecast are referred to by period or daily summary.
  A forecast source must be specified.

for $period in $forecast.weather_periods('NWS')
  $period.dateTime
  $period.event_ts
  ...

  The summary is a single-day aggregate of any periods in that day.

$summary = $forecast.weather_summary('NWS')
$summary.dateTime
$summary.event_ts
$summary.location
$summary.clouds
$summary.temp
$summary.tempMin
$summary.tempMax
$summary.dewpoint
$summary.dewpointMin
$summary.dewpointMax
$summary.humidity
$summary.humidityMin
$summary.humidityMax
$summary.windSpeed
$summary.windSpeedMin
$summary.windSpeedMax
$summary.windGust
$summary.windDir
$summary.windDirs        dictionary
$summary.windChar
$summary.windChars       dictionary
$summary.pop
$summary.precip          array
$summary.obvis           array
"""


# here are a few web sites with weather/tide summaries, some more concise than
# others, none quite what we want:
#
# http://www.tides4fishing.com/
# http://www.surf-forecast.com/
# http://ocean.peterbrueggeman.com/tidepredict.html

# FIXME: 'method' should be called 'source'

import httplib
import socket
import string
import subprocess
import syslog
import threading
import time
import urllib2

import weewx
import weeutil.weeutil
from weewx.wxengine import StdService
from weewx.cheetahgenerator import SearchList

try:
    import cjson as json    # @UnresolvedImport
    # rename methods to maintain compatibility w/ json module 
    setattr(json, 'dumps', json.encode)
    setattr(json, 'loads', json.decode)
except Exception, e:
    try:
        import simplejson as json  # @Reimport @UnusedImport
    except Exception, e:
        try:
            import json  # @Reimport
        except Exception, e:
            json = None

def logmsg(level, msg):
    syslog.syslog(level, 'forecast: %s: %s' % 
                  (threading.currentThread().getName(), msg))

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def get_int(config_dict, label, default_value):
    value = config_dict.get(label, default_value)
    if isinstance(value, str) and value.lower() == 'none':
        value = None
    if value is not None:
        try:
            value = int(value)
        except Exception, e:
            logerr("bad value '%s' for %s" % (value, label))
            value = default_value
    return value

# FIXME: WU defines the following:
#  maxhumidity
#  minhumidity
#  feelslike
#  uvi - uv index
#  mslp - mean sea level pressure
#  condition
#  wx - imported from us nws forecast
#  fctcode - forecast code
# there is overlap between condition, wx, and fctcode.  also, each may contain
# any combination of precip, obvis, and sky cover.

# FIXME: ensure compatibility with uk met office
# http://www.metoffice.gov.uk/datapoint/product/uk-3hourly-site-specific-forecast
# forecast in 3-hour increments for up to 5 days in the future
# UVIndex (1-11)
# feels like temperature
# weather type (0-30)
# visibility (UN, VP, PO, MO, GO, VG, EX)
# textual description
# wind direction is 16-point compass
# air quality index
# also see icons used for uk metoffice

"""Database Schema

   The schema assumes that forecasts are deterministic - a forecast made at
   time t will always return the same results.

   For most use cases, the database will contain only the latest forecast or
   perhaps the latest plus one or two previous forecasts.  However there is
   also a use case in which forecasts are retained indefinitely for analysis.

   The names in the schema are based on NWS point and area forecasts, plus
   extensions to include additional information from Weather Underground.

   When deciding what to store in the database, try to focus on just the facts.
   There is room for interpretation in the description field, but otherwise
   leave the interpretation out.  For example, storm surge warnings, small
   craft advisories are derivative - they are based on wind/wave levels.

   This schema captures all forecasts and defines the following fields:

   method     - forecast method, e.g., Zambretti, NWS, XTide
   usUnits    - units of the forecast, either US or METRIC
   dateTime   - timestamp in seconds when forecast was obtained
   issued_ts  - timestamp in seconds when forecast was made
   event_ts   - timestamp in seconds for the event
   duration   - length of the forecast period
   location
   desc       - textual description of the forecast

   database     nws                    wu-daily           wu-hourly
   -----------  ---------------------  -----------------  ----------------

   hour         3HRLY | 6HRLY          date.hour          FCTTIME.hour
   tempMin      MIN/MAX | MAX/MIN      low.fahrenheit
   tempMax      MIN/MAX | MAX/MIN      high.fahrenheit
   temp         TEMP                                      temp.english
   dewpoint     DEWPT                                     dewpoint.english
   humidity     RH                     avehumidity        humidity
   windDir      WIND DIR | PWIND DIR   avewind.dir        wdir.dir
   windSpeed    WIND SPD               avewind.mph        wspd.english
   windGust     WIND GUST              maxwind.mph
   windChar     WIND CHAR
   clouds       CLOUDS | AVG CLOUNDS   skyicon            sky
   pop          POP 12HR               pop                pop
   qpf          QPF 12HR               qpf_allday.in      qpf.english
   qsf          SNOW 12HR              snow_allday.in     qsf.english
   rain         RAIN                                      wx/condition
   rainshwrs    RAIN SHWRS                                wx/condition
   tstms        TSTMS                                     wx/condition
   drizzle      DRIZZLE                                   wx/condition
   snow         SNOW                                      wx/condition
   snowshwrs    SNOW SHWRS                                wx/condition
   flurries     FLURRIES                                  wx/condition
   sleet        SLEET                                     wx/condition
   frzngrain    FRZNG RAIN                                wx/condition
   frzngdrzl    FRZNG DRZL                                wx/condition
   hail                                                   wx/condition
   obvis        OBVIS                                     wx/condition
   windChill    WIND CHILL                                windchill
   heatIndex    HEAT INDEX                                heatindex
   uvIndex                                                uvi
   airQuality

   hilo         indicates whether this is a high or low tide
   offset       how high or low the tide is relative to mean low
   waveheight   average wave height
   waveperiod   average wave period

   zcode        used only by zambretti forecast
"""

# FIXME: obvis should be an array?
# FIXME: add field for tornado, hurricane/cyclone?

defaultForecastSchema = [('method',     'VARCHAR(10) NOT NULL'),
                         ('usUnits',    'INTEGER NOT NULL'),  # weewx.US
                         ('dateTime',   'INTEGER NOT NULL'),  # epoch
                         ('issued_ts',  'INTEGER NOT NULL'),  # epoch
                         ('event_ts',   'INTEGER NOT NULL'),  # epoch
                         ('duration',   'INTEGER'),           # seconds
                         ('location',   'VARCHAR(64)'),
                         ('desc',       'VARCHAR(256)'),

                         # Zambretti fields
                         ('zcode',      'CHAR(1)'),

                         # weather fields
                         ('hour',       'INTEGER'),     # 00 to 23
                         ('tempMin',    'REAL'),        # degree F
                         ('tempMax',    'REAL'),        # degree F
                         ('temp',       'REAL'),        # degree F
                         ('dewpoint',   'REAL'),        # degree F
                         ('humidity',   'REAL'),        # percent
                         ('windDir',    'VARCHAR(3)'),  # N,NE,E,SE,S,SW,W,NW
                         ('windSpeed',  'REAL'),        # mph
                         ('windGust',   'REAL'),        # mph
                         ('windChar',   'VARCHAR(2)'),  # GN,LT,BZ,WY,VW,SD,HF
                         ('clouds',     'VARCHAR(2)'),  # CL,FW,SC,BK,OV,B1,B2
                         ('pop',        'REAL'),        # percent
                         ('qpf',        'VARCHAR(8)'),  # range or value (inch)
                         ('qsf',        'VARCHAR(5)'),  # range or value (inch)
                         ('rain',       'VARCHAR(2)'),  # S,C,L,O,D
                         ('rainshwrs',  'VARCHAR(2)'),  # S,C,L,O,D
                         ('tstms',      'VARCHAR(2)'),  # S,C,L,O,D
                         ('drizzle',    'VARCHAR(2)'),  # S,C,L,O,D
                         ('snow',       'VARCHAR(2)'),  # S,C,L,O,D
                         ('snowshwrs',  'VARCHAR(2)'),  # S,C,L,O,D
                         ('flurries',   'VARCHAR(2)'),  # S,C,L,O,D
                         ('sleet',      'VARCHAR(2)'),  # S,C,L,O,D
                         ('frzngrain',  'VARCHAR(2)'),  # S,C,L,O,D
                         ('frzngdrzl',  'VARCHAR(2)'),  # S,C,L,O,D
                         ('hail',       'VARCHAR(2)'),  # S,C,L,O,D
                         ('obvis',      'VARCHAR(3)'),  # F,PF,F+,PF+,H,BS,K,BD
                         ('windChill',  'REAL'),        # degree F
                         ('heatIndex',  'REAL'),        # degree F

                         ('uvIndex',    'INTEGER'),     # 1-15
                         ('airQuality', 'INTEGER'),     # 1-10

                         # tide fields
                         ('hilo',       'CHAR(1)'),     # H or L
                         ('offset',     'REAL'),        # relative to mean low

                         # marine-specific conditions
                         ('waveheight', 'REAL'),
                         ('waveperiod', 'REAL'),
                         ]

precip_types = [
    'rain',
    'rainshwrs',
    'tstms',
    'drizzle',
    'snow',
    'snowshwrs',
    'flurries',
    'sleet',
    'frzngrain',
    'frzngdrzl',
    'hail'
    ]

directions_label_dict = {
    'N':'N',
    'NNE':'NNE',
    'NE':'NE',
    'ENE':'ENE',
    'E':'E',
    'ESE':'ESE',
    'SE':'SE',
    'SSE':'SSE',
    'S':'S',
    'SSW':'SSW',
    'SW':'SW',
    'WSW':'WSW',
    'W':'W',
    'WNW':'WNW',
    'NW':'NW',
    'NNW':'NNW',
    }

tide_label_dict = {
    'H': 'High Tide',
    'L': 'Low Tide',
    }

weather_label_dict = {
    'temp'      : 'Temperature',
    'dewpt'     : 'Dewpoint',
    'humidity'  : 'Relative Humidity',
    'winddir'   : 'Wind Direction',
    'windspd'   : 'Wind Speed',
    'windchar'  : 'Wind Character',
    'windgust'  : 'Wind Gust',
    'clouds'    : 'Sky Coverage',
    'windchill' : 'Wind Chill',
    'heatindex' : 'Heat Index',
    'obvis'     : 'Obstructions to Visibility',
    # types of precipitation
    'rain'      : 'Rain',
    'rainshwrs' : 'Rain Showers',
    'sprinkles' : 'Rain Sprinkles',     # FIXME: no db field
    'tstms'     : 'Thunderstorms',
    'drizzle'   : 'Drizzle',
    'snow'      : 'Snow',
    'snowshwrs' : 'Snow Showers',
    'flurries'  : 'Snow Flurries',
    'sleet'     : 'Ice Pellets',
    'frzngrain' : 'Freezing Rain',
    'frzngdrzl' : 'Freezing Drizzle',
    'hail'      : 'Hail',
    # codes for clouds
    'CL' : 'Clear',
    'FW' : 'Few Clouds',
#    'SC' : 'Scattered Clouds',
    'BK' : 'Broken Clouds',
    'B1' : 'Mostly Cloudy',
    'B2' : 'Considerable Cloudiness',
    'OV' : 'Overcast',
    # codes for precipitation
    'S'  : 'Slight Chance',      'Sq'  : '<20%',
    'C'  : 'Chance',             'Cq'  : '30-50%',
    'L'  : 'Likely',             'Lq'  : '60-70%',
    'O'  : 'Occasional',         'Oq'  : '80-100%',
    'D'  : 'Definite',           'Dq'  : '80-100%',
    'IS' : 'Isolated',           'ISq' : '<20%',
    'SC' : 'Scattered',          'SCq' : '30-50%',
    'NM' : 'Numerous',           'NMq' : '60-70%',
    'EC' : 'Extensive',          'ECq' : '80-100%',
    'PA' : 'Patchy',             'PAq' : '<25%',
    'AR' : 'Areas',              'ARq' : '25-50%',
    'WD' : 'Widespread',         'WDq' : '>50%',
    # codes for obstructed visibility
    'F'   : 'Fog',
    'PF'  : 'Patchy Fog',
    'F+'  : 'Dense Fog',
    'PF+' : 'Patchy Dense Fog',
    'H'   : 'Haze',
    'BS'  : 'Blowing Snow',
    'K'   : 'Smoke',
    'BD'  : 'Blowing Dust',
    'AF'  : 'Volcanic Ash',
    'M'   : 'Mist',              # WU extension
    'FF'  : 'Freezing Fog',      # WU extension
    'DST' : 'Dust',              # WU extension
    'SND' : 'Sand',              # WU extension
    'SP'  : 'Spray',             # WU extension
    'DW'  : 'Dust Whirls',       # WU extension
    'SS'  : 'Sand Storm',        # WU extension
    'LDS' : 'Low Drifting Snow', # WU extension
    'LDD' : 'Low Drifting Dust', # WU extension
    'LDN' : 'Low Drifting Sand', # WU extension
    'BN'  : 'Blowing Sand',      # WU extension
    'SF'  : 'Shallow Fog',       # WU extension
    # codes for wind character
    'LT' : 'Light',
    'GN' : 'Gentle',
    'BZ' : 'Breezy',
    'WY' : 'Windy',
    'VW' : 'Very Windy',
    'SD' : 'Strong/Damaging',
    'HF' : 'Hurricane Force',
    }

class ForecastThread(threading.Thread):
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)

class Forecast(StdService):
    """Provide a forecast for weather or tides."""

    def __init__(self, engine, config_dict, fid,
                 interval=1800, max_age=604800):
        super(Forecast, self).__init__(engine, config_dict)

        d = config_dict.get('Forecast', {})
        self.interval = int(d.get('interval', interval))
        self.max_age = get_int(d, 'max_age', max_age)

        dd = config_dict['Forecast'].get(fid, {})
        self.interval = int(dd.get('interval', self.interval))
        self.max_age = get_int(dd, 'max_age', self.max_age)

        schema_str = d.get('schema', None)
        self.schema = weeutil.weeutil._get_object(schema_str) \
            if schema_str is not None else defaultForecastSchema

        self.database = d['database']
        self.table = d.get('table', 'archive')

        # use single_thread for debugging
        self.single_thread = weeutil.weeutil.tobool(d.get('single_thread', False))
        self.updating = False

        # option to vacuum the sqlite database when pruning
        self.vacuum = weeutil.weeutil.tobool(d.get('vacuum', False))
        # how often to retry database failures
        self.database_max_tries = int(d.get('database_max_tries', 3))
        # how long to wait between retries, in seconds
        self.database_retry_wait = int(d.get('database_retry_wait', 10))

        self.method_id = fid
        self.last_ts = 0

        # setup database
        with Forecast.setup_database(self.database,
                                     self.table, self.method_id,
                                     self.config_dict, self.schema) as archive:
            # ensure schema on disk matches schema in memory
            dbcol = archive.connection.columnsOf(self.table)
            memcol = [x[0] for x in self.schema]
            if dbcol != memcol:
                raise Exception('%s: schema mismatch: %s != %s' %
                                (self.method_id, dbcol, memcol))
            # find out when the last forecast happened
            self.last_ts = Forecast.get_last_forecast_ts(archive,
                                                         self.table,
                                                         self.method_id)

        # ensure that the forecast has a chance to update on each new record
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.update_forecast)

    def update_forecast(self, event):
        if self.single_thread:
            self.do_forecast(event)
        elif self.updating:
            logdbg('%s: update thread already running' % self.method_id)
        elif time.time() - self.interval > self.last_ts:
            t = ForecastThread(self.do_forecast, event)
            t.setName(self.method_id + 'Thread')
            logdbg('%s: starting thread' % self.method_id)
            t.start()
        else:
            logdbg('%s: not yet time to do the forecast' % self.method_id)

    def do_forecast(self, event):
        self.updating = True
        try:
            records = self.get_forecast(event)
            if records is None:
                return
            for count in range(self.database_max_tries):
                try:
                    with Forecast.setup_database(self.database,
                                                 self.table,
                                                 self.method_id,
                                                 self.config_dict,
                                                 self.schema) as archive:
                        logdbg('%s: saving %d forecast records' %
                               (self.method_id, len(records)))
                        archive.addRecord(records, log_level=syslog.LOG_DEBUG)
                        self.last_ts = int(time.time())
                        if self.max_age is not None:
                            Forecast.prune_forecasts(archive,
                                                     self.table,
                                                     self.method_id,
                                                     now - self.max_age,
                                                     vacuum=self.vacuum)
                    break
                except Exception, e:
                    logerr('%s: save/prune failed (attempt %d of %d): %s' %
                           (self.method_id, (count+1),
                            self.database_max_tries, e))
                    logdbg('%s: waiting %d seconds before retry' %
                           (self.method_id, self.database_retry_wait))
                    time.sleep(self.database_retry_wait)
        except Exception, e:
            logerr('%s: forecast failure: %s' % (self.method_id, e))
        finally:
            logdbg('%s: terminating thread' % self.method_id)
            self.updating = False

    def get_forecast(self, event):
        """get the forecast, return an array of forecast records."""
        return None

    @staticmethod
    def get_last_forecast_ts(archive, table, method_id):
        sql = "select dateTime,issued_ts from %s where method = '%s' and dateTime = (select dateTime from %s where method = '%s' order by dateTime desc limit 1) limit 1" % (table, method_id, table, method_id)
        r = archive.getSql(sql)
        if r is None:
            return None
        logdbg('%s: last forecast issued %s, requested %s' % 
               (method_id,
                weeutil.weeutil.timestamp_to_string(r[1]),
                weeutil.weeutil.timestamp_to_string(r[0])))
        return int(r[0])

    @staticmethod
    def prune_forecasts(archive, table, method_id, ts, vacuum=False):
        """remove forecasts older than ts from the database"""
        logdbg('%s: deleting forecasts prior to %d' (method_id, ts))
        sql = "delete from %s where method = '%s' and dateTime < %d" % (table, method_id, ts)
        archive.getSql(sql)
        loginf('%s: deleted forecasts prior to %d' % (method_id, ts))

        # vacuum will only work on sqlite databases.  it will compact the
        # database file.  if we do not do this, the file grows even though
        # we prune records from the database.  it should be ok to run this
        # on a mysql database - it will silently fail.
        if vacuum:
            try:
                logdbg('vacuuming')
                archive.getSql('vacuum')
            except Exception, e:
                logdbg('vacuuming failed: %s' % e)
                pass

    @staticmethod
    def setup_database(database, table, method_id, config_dict, schema):
        archive = weewx.archive.Archive.open_with_create(config_dict['Databases'][database], schema, table)
        loginf("%s: using table '%s' in database '%s'" %
               (method_id, table, database))
        return archive


# -----------------------------------------------------------------------------
# Zambretti Forecaster
#
# The zambretti forecast is based upon recent weather conditions.  Supposedly
# it is about 90% to 94% accurate.  It is simply a table of values based upon
# the current barometric pressure, pressure trend, winter/summer, and wind
# direction.
#
# http://www.meteormetrics.com/zambretti.htm
# -----------------------------------------------------------------------------

Z_KEY = 'Zambretti'

class ZambrettiForecast(Forecast):
    """calculate zambretti code"""

    def __init__(self, engine, config_dict):
        super(ZambrettiForecast, self).__init__(engine, config_dict, Z_KEY,
                                                interval=600)
        d = config_dict['Forecast'].get(Z_KEY, {})
        self.hemisphere = d.get('hemisphere', 'NORTH')
        self.lower_pressure = float(d.get('lower_pressure', 950.0))
        self.upper_pressure = float(d.get('upper_pressure', 1050.0))
        self.last_pressure = None
        loginf('%s: interval=%s max_age=%s hemisphere=%s lower_pressure=%s upper_pressure=%s' %
               (Z_KEY, self.interval, self.max_age, self.hemisphere,
                self.lower_pressure, self.upper_pressure))

    def get_forecast(self, event):
        logdbg('%s: generating zambretti forecast' % Z_KEY)
        rec = event.record
        if rec['barometer'] is None or rec['windDir'] is None:
            return None
        pressure = float(rec['barometer'])
        if rec['usUnits'] == weewx.US:
            vt = (float(pressure), "inHg", "group_pressure")
            pressure = weewx.units.convert(vt, 'mbar')[0]
        ts = rec['dateTime']
        tt = time.gmtime(ts)
        month = tt.tm_mon - 1 # month is [0-11]
        wind = int(rec['windDir'] / 22.5) # wind dir is [0-15]
        if self.last_pressure is not None:
            trend = self.last_pressure - pressure
        else:
            trend = None
        self.last_pressure = pressure
        north = self.hemisphere.lower() != 'south'
        logdbg('%s: pressure=%s month=%s wind=%s trend=%s north=%s' %
               (Z_KEY, pressure, month, wind, trend, north))
        code = ZambrettiCode(pressure, month, wind, trend, north,
                             baro_bottom=self.lower_pressure,
                             baro_top=self.upper_pressure)
        logdbg('%s: code is %s' % (Z_KEY, code))
        if code is None:
            return None

        record = {}
        record['method'] = Z_KEY
        record['usUnits'] = weewx.US
        record['dateTime'] = ts
        record['issued_ts'] = ts
        record['event_ts'] = ts
        record['zcode'] = code
        loginf('%s: generated 1 forecast record' % Z_KEY)
        return [record]

zambretti_label_dict = {
    'A' : "Settled fine",
    'B' : "Fine weather",
    'C' : "Becoming fine",
    'D' : "Fine, becoming less settled",
    'E' : "Fine, possible showers",
    'F' : "Fairly fine, improving",
    'G' : "Fairly fine, possible showers early",
    'H' : "Fairly fine, showery later",
    'I' : "Showery early, improving",
    'J' : "Changeable, mending",
    'K' : "Fairly fine, showers likely",
    'L' : "Rather unsettled clearing later",
    'M' : "Unsettled, probably improving",
    'N' : "Showery, bright intervals",
    'O' : "Showery, becoming less settled",
    'P' : "Changeable, some rain",
    'Q' : "Unsettled, short fine intervals",
    'R' : "Unsettled, rain later",
    'S' : "Unsettled, some rain",
    'T' : "Mostly very unsettled",
    'U' : "Occasional rain, worsening",
    'V' : "Rain at times, very unsettled",
    'W' : "Rain at frequent intervals",
    'X' : "Rain, very unsettled",
    'Y' : "Stormy, may improve",
    'Z' : "Stormy, much rain",
    }

def ZambrettiText(code):
    return zambretti_label_dict[code]

def ZambrettiCode(pressure, month, wind, trend,
                  north=True, baro_top=1050.0, baro_bottom=950.0):
    """Simple implementation of Zambretti forecaster algorithm based on
    implementation in pywws, inspired by beteljuice.com Java algorithm,
    as converted to Python by honeysucklecottage.me.uk, and further
    information from http://www.meteormetrics.com/zambretti.htm

    pressure - barometric pressure in millibars

    month - month of the year as number in [0,11]

    wind - wind direction as number in [0,16]

    trend - pressure change in millibars
    """

    if pressure is None:
        return None
    if trend is None:
        return None
    if month < 0 or month > 11:
        return None
    if wind < 0 or wind > 15:
        return None

    # normalise pressure
    pressure = 950.0 + ((1050.0 - 950.0) *
                        (pressure - baro_bottom) / (baro_top - baro_bottom))
    # adjust pressure for wind direction
    if wind is not None:
        if not north:
            # southern hemisphere, so add 180 degrees
            wind = (wind + 8) % 16
        pressure += (  5.2,  4.2,  3.2,  1.05, -1.1, -3.15, -5.2, -8.35,
                     -11.5, -9.4, -7.3, -5.25, -3.2, -1.15,  0.9,  3.05)[wind]
    # compute base forecast from pressure and trend (hPa / hour)
    if trend >= 0.1:
        # rising pressure
        if north == (month >= 4 and month <= 9):
            pressure += 3.2
        F = 0.1740 * (1031.40 - pressure)
        LUT = ('A','B','B','C','F','G','I','J','L','M','M','Q','T','Y')
    elif trend <= -0.1:
        # falling pressure
        if north == (month >= 4 and month <= 9):
            pressure -= 3.2
        F = 0.1553 * (1029.95 - pressure)
        LUT = ('B','D','H','O','R','U','V','X','X','Z')
    else:
        # steady
        F = 0.2314 * (1030.81 - pressure)
        LUT = ('A','B','B','B','E','K','N','N','P','P','S','W','W','X','X','X','Z')
    # clip to range of lookup table
    F = min(max(int(F + 0.5), 0), len(LUT) - 1)
    # convert to letter code
    return LUT[F]


# -----------------------------------------------------------------------------
# US National Weather Service Point Forecast Matrix
#
# For an explanation of point forecasts, see:
#   http://www.srh.weather.gov/jetstream/webweather/pinpoint_max.htm
#
# For details about how to decode the NWS point forecast matrix, see:
#   http://www.srh.noaa.gov/mrx/?n=pfm_explain
#   http://www.srh.noaa.gov/bmx/?n=pfm
#  For details about the NWS area forecast matrix, see:
#   http://www.erh.noaa.gov/car/afmexplain.htm
#
# For actual forecasts, see:
#   http://www.weather.gov/
#
# For example:
#   http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt&issuedby=BOX
#
# 12-hour:
# pop12hr: likelihood of measurable precipitation (1/100 inch)
# qpf12hr: quantitative precipitation forecast; amount or range in inches
# snow12hr: snowfall accumulation; amount or range in inches; T indicates trace
# mx/mn: temperature in degrees F
#
# 3-hour:
# temp - degrees F
# dewpt - degrees F
# rh - relative humidity %
# winddir - 8 compass points
# windspd - miles per hour
# windchar - wind character
# windgust - only displayed if gusts exceed windspd by 10 mph
# clouds - sky coverage
# precipitation types
#   rain      - rain
#   rainshwrs - rain showers
#   sprinkles - sprinkles
#   tstms     - thunderstorms
#   drizzle   - drizzle
#   snow      - snow, snow grains/pellets
#   snowshwrs - snow showers
#   flurries  - snow flurries
#   sleet     - ice pellets
#   frzngrain - freezing rain
#   frzngdrzl - freezing drizzle
# windchill
# heatindex
# minchill
# maxheat
# obvis - obstructions to visibility
#
# codes for clouds:
#   CL - clear (0 <= 6%)
#   FW - few - mostly clear (6% <= 31%)
#   SC - scattered - partly cloudy (31% <= 69%)
#   BK - broken - mostly cloudy (69% <= 94%)
#   OV - overcast - cloudy (94% <= 100%)
#
#   CL - sunny or clear (0% <= x <= 5%)
#   FW - sunny or mostly clear (5% < x <= 25%)
#   SC - mostly sunny or partly cloudy (25% < x <= 50%)
#   B1 - partly sunny or mostly cloudy (50% < x <= 69%)
#   B2 - mostly cloudy or considerable cloudiness (69% < x <= 87%)
#   OV - cloudy or overcast (87% < x <= 100%)
#
# PFM/AFM codes for precipitation types (rain, drizzle, flurries, etc):
#   S - slight chance (< 20%)
#   C - chance (30%-50%)
#   L - likely (60%-70%)
#   O - occasional (80%-100%)
#   D - definite (80%-100%)
#
#   IS - isolated < 20%
#   SC - scattered 30%-50%
#   NM - numerous 60%-70%
#   EC - extensive coverage 80%-100%
#
#   PA - patchy < 25%
#   AR - areas 25%-50%
#   WD - widespread > 50%
#
# codes for obstructions to visibility:
#   F   - fog
#   PF  - patchy fog
#   F+  - dense fog
#   PF+ - patchy dense fog
#   H   - haze
#   BS  - blowing snow
#   K   - smoke
#   BD  - blowing dust
#   AF  - volcanic ashfall
#
# codes for wind character:
#   LT - light < 8 mph
#   GN - gentle 8-14 mph
#   BZ - breezy 15-22 mph
#   WY - windy 23-30 mph
#   VW - very windy 31-39 mph
#   SD - strong/damaging >= 40 mph
#   HF - hurricane force >= 74 mph
#
# -----------------------------------------------------------------------------

# The default URL contains the bare minimum to request a point forecast, less
# the forecast office identifier.
NWS_DEFAULT_PFM_URL = 'http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt'

NWS_KEY = 'NWS'

class NWSForecast(Forecast):
    """Download forecast from US National Weather Service."""

    def __init__(self, engine, config_dict):
        super(NWSForecast, self).__init__(engine, config_dict, NWS_KEY,
                                          interval=10800)
        d = config_dict['Forecast'].get(NWS_KEY, {})
        self.url = d.get('url', NWS_DEFAULT_PFM_URL)
        self.max_tries = int(d.get('max_tries', 3))
        self.lid = d.get('lid', None)
        self.foid = d.get('foid', None)

        errmsg = []
        if self.lid is None:
            errmsg.append('NWS location ID (lid) is not specified')
        if self.foid is None:
            errmsg.append('NWS forecast office ID (foid) is not specified')
        if errmsg:
            raise Exception, '\n'.join(errmsg)

        loginf('%s: interval=%s max_age=%s lid=%s foid=%s' %
               (NWS_KEY, self.interval, self.max_age, self.lid, self.foid))

    def get_forecast(self, event):
        text = NWSDownloadForecast(self.foid, url=self.url,
                                   max_tries=self.max_tries)
        if text is None:
            logerr('%s: no PFM data for %s from %s' %
                   (NWS_KEY, self.foid, self.url))
            return None
        matrix = NWSParseForecast(text, self.lid)
        if matrix is None:
            logerr('%s: no PFM found for %s in forecast from %s' %
                   (NWS_KEY, self.lid, self.foid))
            return None
        logdbg('%s: forecast matrix: %s' % (NWS_KEY, matrix))
        records = NWSProcessForecast(self.foid, self.lid, matrix)
        msg = 'got %d forecast records' % len(records)
        if 'desc' in matrix or 'location' in matrix:
            msg += ' for %s %s' % (matrix.get('desc',''),
                                   matrix.get('location',''))
        loginf('%s: %s' % (NWS_KEY, msg))
        return records

# mapping of NWS names to database fields
nws_schema_dict = {
    'HOUR'       : 'hour',
    'MIN/MAX'    : 'tempMinMax',
    'MAX/MIN'    : 'tempMaxMin',
    'TEMP'       : 'temp',
    'DEWPT'      : 'dewpoint',
    'RH'         : 'humidity',
    'WIND DIR'   : 'windDir',
    'PWIND DIR'  : 'windDir',
    'WIND SPD'   : 'windSpeed',
    'WIND GUST'  : 'windGust',
    'WIND CHAR'  : 'windChar',
    'CLOUDS'     : 'clouds',
    'AVG CLOUDS' : 'clouds',
    'POP 12HR'   : 'pop',
    'QPF 12HR'   : 'qpf',
    'SNOW 12HR'  : 'qsf',
    'RAIN'       : 'rain',
    'RAIN SHWRS' : 'rainshwrs',
    'TSTMS'      : 'tstms',
    'DRIZZLE'    : 'drizzle',
    'SNOW'       : 'snow',
    'SNOW SHWRS' : 'snowshwrs',
    'FLURRIES'   : 'flurries',
    'SLEET'      : 'sleet',
    'FRZNG RAIN' : 'frzngrain',
    'FRZNG DRZL' : 'frzngdrzl',
    'OBVIS'      : 'obvis',
    'WIND CHILL' : 'windChill',
    'HEAT INDEX' : 'heatIndex',
    }

def NWSDownloadForecast(foid, url=NWS_DEFAULT_PFM_URL, max_tries=3):
    """Download a point forecast matrix from the US National Weather Service"""

    u = '%s&issuedby=%s' % (url, foid) if url == NWS_DEFAULT_PFM_URL else url
    loginf("%s: downloading forecast from '%s'" % (NWS_KEY, u))
    for count in range(max_tries):
        try:
            response = urllib2.urlopen(u)
            text = response.read()
            return text
        except (urllib2.URLError, socket.error,
                httplib.BadStatusLine, httplib.IncompleteRead), e:
            logerr('%s: failed attempt %d to download NWS forecast: %s' %
                   (NWS_KEY, count+1, e))
    else:
        logerr('%s: failed to download forecast' % NWS_KEY)
    return None

def NWSExtractLocation(text, lid):
    """Extract a single location from a US National Weather Service PFM."""

    alllines = text.splitlines()
    lines = None
    for line in iter(alllines):
        if line.startswith(lid):
            lines = []
            lines.append(line)
        elif lines is not None:
            if line.startswith('$$'):
                break
            else:
                lines.append(line)
    return lines

def NWSParseForecast(text, lid):
    """Parse a United States National Weather Service point forcast matrix.
    Save it into a dictionary with per-hour elements for wind, temperature,
    etc. extracted from the point forecast.
    """

    lines = NWSExtractLocation(text, lid)
    if lines is None:
        return None

    rows3 = {}
    rows6 = {}
    ts = date2ts(lines[3])
    day_ts = weeutil.weeutil.startOfDay(ts)
#    loginf("%s: tstr='%s' ts=%s day_ts=%s" % (NWS_KEY, lines[3], ts, day_ts))
    for line in lines:
        label = line[0:14].strip()
        if label.startswith('UTC'):
            continue
        if label.endswith('3HRLY'):
            label = 'HOUR'
            mode = 3
        elif label.endswith('6HRLY'):
            label = 'HOUR'
            mode = 6
        if label in nws_schema_dict:
            if mode == 3:
                rows3[nws_schema_dict[label]] = line[14:]
            elif mode == 6:
                rows6[nws_schema_dict[label]] = line[14:]

    matrix = {}
    matrix['lid'] = lid
    matrix['desc'] = lines[1]
    matrix['location'] = lines[2]
    matrix['issued_ts'] = ts
    matrix['ts'] = []
    matrix['hour'] = []
    matrix['duration'] = []

    idx = 0
    day = day_ts
    lasth = None

    # get the 3-hour indexing
    indices3 = {} # index in the hour string mapped to index of the hour
    idx2hr3 = []  # index of the hour mapped to location in the hour string
    for i in range(0, len(rows3['hour']), 3):
        h = int(rows3['hour'][i:i+2])
        if lasth is not None and h < lasth:
            day += 24 * 3600
        lasth = h
        matrix['ts'].append(day + h*3600)
        matrix['hour'].append(h)
        matrix['duration'].append(3*3600)
        indices3[i+1] = idx
        idx += 1
        idx2hr3.append(i+1)

    # get the 6-hour indexing
    indices6 = {} # index in the hour string mapped to index of the hour
    idx2hr6 = []  # index of the hour mapped to location in the hour string
    s = ''
    for i in range(0, len(rows6['hour'])):
        if rows6['hour'][i].isspace():
            if len(s) > 0:
                h = int(s)
                if lasth is not None and h < lasth:
                    day += 24 * 3600
                lasth = h
                matrix['ts'].append(day + h*3600)
                matrix['hour'].append(h)
                matrix['duration'].append(6*3600)
                indices6[i-1] = idx
                idx += 1
                idx2hr6.append(i-1)
            s = ''
        else:
            s += rows6['hour'][i]
    if len(s) > 0:
        h = int(s)
        matrix['ts'].append(day + h*3600)
        matrix['hour'].append(h)
        matrix['duration'].append(3*3600)
        indices6[len(rows6['hour'])-1] = idx
        idx += 1
        idx2hr6.append(len(rows6['hour'])-1)

    # get the 3 and 6 hour data
    filldata(matrix, idx, rows3, indices3, idx2hr3)
    filldata(matrix, idx, rows6, indices6, idx2hr6)
    return matrix

def filldata(matrix, nidx, rows, indices, i2h):
    """fill matrix with data from rows"""
    n = { 'qpf' : 8, 'qsf' : 5 }
    for label in rows:
        if label not in matrix:
            matrix[label] = [None]*nidx
        l = n.get(label, 3)
        q = 0
        for i in reversed(i2h):
            if l == 3 or q % 4 == 0:
                s = 0 if i-l+1 < 0 else i-l+1
                chunk = rows[label][s:i+1].strip()
                if len(chunk) > 0:
                    matrix[label][indices[i]] = chunk
            q += 1

    # deal with min/max temperatures
    if 'tempMin' not in matrix:
        matrix['tempMin'] = [None]*nidx
    if 'tempMax' not in matrix:
        matrix['tempMax'] = [None]*nidx
    if 'tempMinMax' in matrix:
        state = 0
        for i in range(nidx):
            if matrix['tempMinMax'][i] is not None:
                if state == 0:
                    matrix['tempMin'][i] = matrix['tempMinMax'][i]
                    state = 1
                else:
                    matrix['tempMax'][i] = matrix['tempMinMax'][i]
                    state = 0
        del matrix['tempMinMax']
    if 'tempMaxMin' in matrix:
        state = 1
        for i in range(nidx):
            if matrix['tempMaxMin'][i] is not None:
                if state == 0:
                    matrix['tempMin'][i] = matrix['tempMaxMin'][i]
                    state = 1
                else:
                    matrix['tempMax'][i] = matrix['tempMaxMin'][i]
                    state = 0
        del matrix['tempMaxMin']

def date2ts(tstr):
    """Convert NWS date string to timestamp in seconds.
    sample format: 418 PM EDT SAT MAY 11 2013
    """

    parts = tstr.split(' ')
    s = '%s %s %s %s %s' % (parts[0], parts[1], parts[4], parts[5], parts[6])
    ts = time.mktime(time.strptime(s, "%I%M %p %b %d %Y"))
    return int(ts)

def NWSProcessForecast(foid, lid, matrix):
    '''convert NWS matrix to records'''
    now = int(time.time())
    records = []
    if matrix is not None:
        for i,ts in enumerate(matrix['ts']):
            record = {}
            record['method'] = NWS_KEY
            record['usUnits'] = weewx.US
            record['dateTime'] = now
            record['issued_ts'] = matrix['issued_ts']
            record['event_ts'] = ts
            record['location'] = '%s %s' % (foid, lid)
            for label in matrix:
                if isinstance(matrix[label], list):
                    record[label] = matrix[label][i]
            records.append(record)
    return records


# -----------------------------------------------------------------------------
# Weather Underground Forecasts
#
# Forecasts from the weather underground (www.wunderground.com).  WU provides
# an api that returns json/xml data.  This implementation uses the json format.
#
# For the weather underground api, see:
#   http://www.wunderground.com/weather/api/d/docs?MR=1
#
# There are two WU forecasts - daily (forecast10day) and hourly (hourly10day)
#
# forecast10day
#
# date
# period
# high
# low
# conditions
# icon
# icon_url
# skyicon
# pop
# qpf_allday
# qpf_day
# qpf_night
# snow_allday
# snow_day
# snow_night
# maxwind
# avewind
# avehumidity
# maxhumidity
# minhumidity
#
# hourly10day
#
# fcttime
# dewpoint
# condition
# icon
# icon_url
# fctcode
#    1 clear
#    2 partly cloudy
#    3 mostly cloudy
#    4 cloudy
#    5 hazy
#    6 foggy
#    7 very hot
#    8 very cold
#    9 blowing snow
#   10 chance of showers
#   11 showers
#   12 chance of rain
#   13 rain
#   14 chance of a thunderstorm
#   15 thunderstorm
#   16 flurries
#   17
#   18 chance of snow showers
#   19 snow showers
#   20 chance of snow
#   21 snow
#   22 chance of ice pellets
#   23 ice pellets
#   24 blizzard
# sky
# wspd
# wdir
# wx
# uvi
# humidity
# windchill
# heatindex
# feelslike
# qpf
# snow
# pop
# mslp
#
# codes for condition
#   [Light/Heavy] Drizzle
#   [Light/Heavy] Rain
#   [Light/Heavy] Snow
#   [Light/Heavy] Snow Grains
#   [Light/Heavy] Ice Crystals
#   [Light/Heavy] Ice Pellets
#   [Light/Heavy] Hail
#   [Light/Heavy] Mist
#   [Light/Heavy] Fog
#   [Light/Heavy] Fog Patches
#   [Light/Heavy] Smoke
#   [Light/Heavy] Volcanic Ash
#   [Light/Heavy] Widespread Dust
#   [Light/Heavy] Sand
#   [Light/Heavy] Haze
#   [Light/Heavy] Spray
#   [Light/Heavy] Dust Whirls
#   [Light/Heavy] Sandstorm
#   [Light/Heavy] Low Drifting Snow
#   [Light/Heavy] Low Drifting Widespread Dust
#   [Light/Heavy] Low Drifting Sand
#   [Light/Heavy] Blowing Snow
#   [Light/Heavy] Blowing Widespread Dust
#   [Light/Heavy] Blowing Sand
#   [Light/Heavy] Rain Mist
#   [Light/Heavy] Rain Showers
#   [Light/Heavy] Snow Showers
#   [Light/Heavy] Snow Blowing Snow Mist
#   [Light/Heavy] Ice Pellet Showers
#   [Light/Heavy] Hail Showers
#   [Light/Heavy] Small Hail Showers
#   [Light/Heavy] Thunderstorm
#   [Light/Heavy] Thunderstorms and Rain
#   [Light/Heavy] Thunderstorms and Snow
#   [Light/Heavy] Thunderstorms and Ice Pellets
#   [Light/Heavy] Thunderstorms with Hail
#   [Light/Heavy] Thunderstorms with Small Hail
#   [Light/Heavy] Freezing Drizzle
#   [Light/Heavy] Freezing Rain
#   [Light/Heavy] Freezing Fog
#   Patches of Fog
#   Shallow Fog
#   Partial Fog
#   Overcast
#   Clear
#   Partly Cloudy
#   Mostly Cloudy
#   Scattered Clouds
#   Small Hail
#   Squalls
#   Funnel Cloud
#   Unknown Precipitation
#   Unknown
# -----------------------------------------------------------------------------

WU_KEY = 'WU'
WU_DIR_DICT = {
    'North':'N',
    'South':'S',
    'East':'E',
    'West':'W',
    }
WU_SKY_DICT = {
    'sunny':'CL',
    'mostlysunny':'FW',
    'partlysunny':'SC',
    'FIXME':'BK',
    'partlycloudy':'B1',
    'mostlycloudy':'B2',
    'cloudy':'OV',
    }

WU_DEFAULT_URL = 'http://api.wunderground.com/api'

class WUForecast(Forecast):
    """Download forecast from Weather Underground."""

    def __init__(self, engine, config_dict):
        super(WUForecast, self).__init__(engine, config_dict, WU_KEY,
                                         interval=10800)
        d = config_dict['Forecast'].get(WU_KEY, {})
        self.url = d.get('url', WU_DEFAULT_URL)
        self.max_tries = int(d.get('max_tries', 3))
        self.api_key = d.get('api_key', None)
        self.location = d.get('location', None)
        self.forecast_type = d.get('forecast_type', 'hourly10day')
        self.save_failed = weeutil.weeutil.tobool(d.get('save_failed', False))

        if self.location is None:
            lat = config_dict['Station'].get('latitude', None)
            lon = config_dict['Station'].get('longitude', None)
            if lat is not None and lon is not None:
                self.location = '%s,%s' % (lat,lon)

        errmsg = []
        if json is None:
            errmsg.appen('json is not installed')
        if self.api_key is None:
            errmsg.append('WU API key (api_key) is not specified')
        if self.location is None:
            errmsg.append('WU location is not specified')
        if errmsg:
            raise Exception, '\n'.join(errmsg)

        loginf('%s: interval=%s max_age=%s api_key=%s location=%s fc=%s' %
               (WU_KEY, self.interval, self.max_age, self.api_key,
                self.location, self.forecast_type))

    def get_forecast(self, event):
        text = WUDownloadForecast(self.api_key, self.location,
                                  url=self.url, fc_type=self.forecast_type,
                                  max_tries=self.max_tries)
        if text is None:
            logerr('%s: no forecast data for %s from %s' %
                   (WU_KEY, self.location, self.url))
            return None
        records = WUParseForecast(text, location=self.location,
                                  save_failed=self.save_failed)
        loginf('%s: got %d forecast records' % (WU_KEY, len(records)))
        return records

def WUDownloadForecast(api_key, location,
                       url=WU_DEFAULT_URL, fc_type='hourly10day', max_tries=3):
    """Download a forecast from the Weather Underground

    api_key - key for downloading from WU

    location - lat/lon, post code, or other location identifier

    url - URL to the weather underground service.  if anything other than the
          default is specified, that entire URL is used.  if the default is
          specified, it is used as the base and other items are added to it.

    fc_type - forecast type, one of hourly10day or forecast10day

    max_tries - how many times to try before giving up
    """

    u = '%s/%s/%s/q/%s.json' % (url, api_key, fc_type, location) \
        if url == WU_DEFAULT_URL else url
    loginf("%s: downloading forecast from '%s'" % (WU_KEY, u))
    for count in range(max_tries):
        try:
            response = urllib2.urlopen(u)
            text = response.read()
            return text
        except (urllib2.URLError, socket.error,
                httplib.BadStatusLine, httplib.IncompleteRead), e:
            logerr('%s: failed attempt %d to download WU forecast: %s' %
                   (WU_KEY, count+1, e))
    else:
        logerr('%s: failed to download forecast' % WU_KEY)
    return None

def WUParseForecast(text, issued_ts=None, now=None, location=None,
                    save_failed=False):
    obj = json.loads(text)
    if not 'response' in obj:
        logerr('%s: unknown format in response' % WU_KEY)
        return []
    response = obj['response']
    if 'error' in response:
        logerr('%s: error in response: %s: %s' %
               (WU_KEY,
                response['error']['type'], response['error']['description']))
        return []

    if issued_ts is None or now is None:
        n = int(time.time())
        if issued_ts is None:
            issued_ts = n
        if now is None:
            now = n

    if 'hourly_forecast' in obj:
        records = WUCreateRecordsFromHourly(obj, issued_ts, now,
                                            location=location,
                                            save_failed=save_failed)
    elif 'forecast' in obj:
        records = WUCreateRecordsFromDaily(obj, issued_ts, now,
                                           location=location,
                                           save_failed=save_failed)
    else:
        records = []
    return records

def sky2clouds(sky):
    if 0 <= sky <= 5:
        return 'CL'
    elif 5 < sky <= 25:
        return 'FW'
    elif 25 < sky <= 50:
        return 'SC'
    elif 50 < sky <= 69:
        return 'B1'
    elif 69 < sky <= 87:
        return 'B2'
    elif 87 < sky <= 100:
        return 'OV'
    return None

str2precip_dict = {
# nws precip strings
    'Rain': 'rain',
    'Rain Showers': 'rainshwrs',
    'Thunderstorms': 'tstms',
    'Drizzle': 'drizzle',
    'Snow': 'snow',
    'Snow Showers': 'snowshwrs',
    'Flurries': 'flurries',
    'Sleet': 'sleet',
    'Freezing Rain': 'frzngrain',
    'Freezing Drizzle': 'frzngdrzl',
# precip strings supported by wu but not nws
    'Snow Grains': 'snow',
    'Ice Crystals': 'sleet',
    'Hail': 'hail',
    'Thunderstorm': 'tstms',
    'Rain Mist': 'rain',
    'Ice Pellets': 'sleet',
    'Ice Pellet Showers': 'sleet',
    'Hail Showers': 'hail',
    'Small Hail': 'hail',
    'Small Hail Showers': 'hail',
}

str2obvis_dict = {
# nws obvis strings
    'Fog': 'F',
    'Patchy Fog': 'PF',
    'Dense Fog': 'F+',
    'Patchy Dense Fog': 'PF+',
    'Haze': 'H',
    'Blowing Snow': 'BS',
    'Smoke': 'K',
    'Blowing Dust': 'BD',
    'Volcanic Ash': 'AF',
# obvis strings supported by wu but not nws
    'Mist': 'M',
    'Fog Patches': 'PF',
    'Freezing Fog': 'FF',
    'Widespread Dust': 'DST',
    'Sand': 'SND',
    'Spray': 'SP',
    'Dust Whirls': 'DW',
    'Sandstorm': 'SS',
    'Low Drifting Snow': 'LDS',
    'Low Drifting Widespread Dust': 'LDD',
    'Low Drifting Sand': 'LDs',
    'Blowing Widespread Dust': 'BD',
    'Blowing Sand': 'Bs',
    'Snow Blowing Snow Mist': 'BS',
    'Patches of Fog': 'PF',
    'Shallow Fog': 'SF',
    'Partial Fog': 'PF',
    'Blizzard': 'BS',
    'Rain Mist': 'M',
}

# mapping from string to probability code
wx2chance_dict = {
    'Slight Chance': 'S',
    'Chance': 'C',
    'Likely': 'L',
    'Occasional': 'O',
    'Definite': 'D',
    'Isolated': 'IS',
    'Scattered': 'SC',
    'Numerous': 'NM',
    'Extensive': 'EC',
}

def str2pc(s):
    '''parse a wu wx string for the precipitation type and likeliehood

    Slight Chance Light Rain Showers -> rainshwrs,S
    Chance of Light Rain Showers     -> rainshwrs,C
    Isolated Thunderstorms           -> tstms,IS
    '''
    for x in str2precip_dict:
        if s.endswith(x):
            for y in wx2chance_dict:
                if s.startswith(y):
                    return str2precip_dict[x],wx2chance_dict[y]
            return str2precip_dict[x],''
    return None, 0

# mapping from wu fctcode to a precipitation,chance tuple
fct2precip_dict = {
    '10': ('rainshwrs','C'),
    '11': ('rainshwrs','L'),
    '12': ('rain','C'),
    '13': ('rain','L'),
    '14': ('tstms','C'),
    '15': ('tstms','L'),
    '16': ('flurries','L'),
    '18': ('snowshwrs','C'),
    '19': ('snowshwrs','L'),
    '20': ('snow','C'),
    '21': ('snow','L'),
    '22': ('sleet','C'),
    '23': ('sleet','L'),
    '24': ('snowshwrs','L'),
}

def wu2precip(period):
    '''return a dictionary of precipitation with corresponding likeliehoods.
    precipitation information may be in the fctcode, condition, or wx field,
    so look at each one and extract precipitation.'''

    p = {}
    # first try the condition field
    if period['condition'].find(' and ') >= 0:
        for w in period['condition'].split(' and '):
            precip,chance = str2pc(w.strip())
            if precip is not None:
                p[precip] = chance
    elif period['condition'].find(' with ') >= 0:
        for w in period['condition'].split(' with '):
            precip,chance = str2pc(w.strip())
            if precip is not None:
                p[precip] = chance
    else:
        precip,chance = str2pc(period['condition'])
        if precip is not None:
            p[precip] = chance
    # then augment or possibly override with precip info from the fctcode
    if period['fctcode'] in fct2precip_dict:
        precip,chance = fct2precip_dict[period['fctcode']]
        p[precip] = chance
    # wx has us nws forecast strings, so trust it the most
    if len(period['wx']) > 0:
        for w in period['wx'].split(','):
            precip,chance = str2pc(w.strip())
            if precip is not None:
                p[precip] = chance
    return p

# mapping from wu fctcode to obvis code
fct2obvis_dict = {
    '5': 'H',
    '6': 'F',
    '9': 'BS',
    '24': 'BS',
}

def wu2obvis(period):
    '''return a single obvis type.  look in the wx, fctcode, then condition.'''

    if len(period['wx']) > 0:
        for x in [w.strip() for w in period['wx'].split(',')]:
            if x in str2obvis_dict:
                return str2obvis_dict[x]
    if period['fctcode'] in fct2obvis_dict:
        return fct2obvis_dict[period['fctcode']]
    if period['condition'] in str2obvis_dict:
        return str2obvis_dict[period['condition']]
    return None

def str2int(n, s):
    if s == '':
        return None
    try:
        return int(s)
    except Exception, e:
        logerr("%s: conversion error for %s from '%s': %s" % (WU_KEY, n, s, e))
    return None

def str2float(n, s):
    if s == '':
        return None
    try:
        return float(s)
    except Exception, e:
        logerr("%s: conversion error for %s from '%s': %s" % (WU_KEY, n, s, e))
    return None

def save_failed_forecast(fc, msgs):
    ts = int(time.time())
    fn = time.strftime('/var/tmp/failure-%Y%m%d.%H%M', time.localtime(ts))
    with open(fn, 'w') as f:
        for m in msgs:
            f.write("%s\n" % m)
        f.write("%s" % fc)

def WUCreateRecordsFromHourly(fc, issued_ts, now, location=None,
                              save_failed=False):
    '''create from hourly10day'''
    msgs = []
    records = []
    for period in fc['hourly_forecast']:
        try:
            r = {}
            r['method'] = WU_KEY
            r['usUnits'] = weewx.US
            r['dateTime'] = now
            r['issued_ts'] = issued_ts
            r['event_ts'] = str2int('epoch', period['FCTTIME']['epoch'])
            r['hour'] = str2int('hour', period['FCTTIME']['hour'])
            r['duration'] = 3600
            r['clouds'] = sky2clouds(int(period['sky']))
            r['temp'] = str2float('temp', period['temp']['english'])
            r['dewpoint'] = str2float('dewpoint',period['dewpoint']['english'])
            r['humidity'] = str2int('humidity', period['humidity'])
            r['windSpeed'] = str2float('wspd', period['wspd']['english'])
            r['windDir'] = WU_DIR_DICT.get(period['wdir']['dir'],
                                           period['wdir']['dir'])
            r['pop'] = str2int('pop', period['pop'])
            r['qpf'] = str2float('qpf', period['qpf']['english'])
            r['qsf'] = str2float('snow', period['snow']['english'])
            r['obvis'] = wu2obvis(period)
            r['uvIndex'] = str2int('uvi', period['uvi'])
            r.update(wu2precip(period))
            if location is not None:
                r['location'] = location
            records.append(r)
        except Exception, e:
            msg = '%s: failure in hourly forecast: %s' % (WU_KEY, e)
            msgs.append(msg)
            logerr(msg)
    if msgs and save_failed:
        save_failed_forecast(fc, msgs)
    return records

def WUCreateRecordsFromDaily(fc, issued_ts, now, location=None,
                             save_failed=False):
    '''create from forecast10day data'''
    msgs = []
    records = []
    for period in fc['forecast']['simpleforecast']['forecastday']:
        try:
            r = {}
            r['method'] = WU_KEY
            r['usUnits'] = weewx.US
            r['dateTime'] = now
            r['issued_ts'] = issued_ts
            r['event_ts'] = str2int('epoch', period['date']['epoch'])
            r['hour'] = str2int('hour', period['date']['hour'])
            r['duration'] = 24*3600
            r['clouds'] = WU_SKY_DICT.get(period['skyicon'], None)
            r['tempMin'] = str2float('low', period['low']['fahrenheit'])
            r['tempMax'] = str2float('high', period['high']['fahrenheit'])
            r['temp'] = (r['tempMin'] + r['tempMax']) / 2
            r['humidity'] = str2int('humidity', period['avehumidity'])
            r['pop'] = str2int('pop', period['pop'])
            r['qpf'] = str2float('qpf', period['qpf_allday']['in'])
            r['qsf'] = str2float('qsf', period['snow_allday']['in'])
            r['windSpeed'] = str2float('avewind', period['avewind']['mph'])
            r['windDir'] = WU_DIR_DICT.get(period['avewind']['dir'],
                                           period['avewind']['dir'])
            r['windGust'] = str2float('maxwind', period['maxwind']['mph'])
            if location is not None:
                r['location'] = location
            records.append(r)
        except Exception, e:
            msg = '%s: failure in daily forecast: %s' % (WU_KEY, e)
            msgs.append(msg)
            logerr(msg)
    if msgs and save_failed:
        save_failed_forecast(fc, msgs)
    return records


# -----------------------------------------------------------------------------
# xtide tide predictor
#
# The xtide application must be installed for this to work.  For example, on
# debian systems do this:
#
#   sudo apt-get install xtide
#
# This forecasting module uses the command-line 'tide' program, not the
# x-windows application.
# -----------------------------------------------------------------------------

XT_KEY = 'XTide'
XT_PROG = '/usr/bin/tide'
XT_ARGS = '-fc -df"%Y.%m.%d" -tf"%H:%M"'
XT_HILO = {'High Tide' : 'H', 'Low Tide' : 'L'}

class XTideForecast(Forecast):
    """generate tide forecast using xtide"""

    def __init__(self, engine, config_dict):
        super(XTideForecast, self).__init__(engine, config_dict, XT_KEY,
                                            interval=1209600, max_age=2419200)
        d = config_dict['Forecast'].get(XT_KEY, {})
        self.tideprog = d.get('prog', XT_PROG)
        self.tideargs = d.get('args', XT_ARGS)
        self.location = d['location']
        loginf("%s: interval=%s max_age=%s location='%s'" %
               (XT_KEY, self.interval, self.max_age, self.location))

    def get_forecast(self, event):
        lines = self.generate_tide()
        if lines is None:
            return None
        records = self.parse_forecast(lines)
        if records is None:
            return None
        logdbg('%s: tide matrix: %s' % (self.method_id, records))
        return records

    def generate_tide(self, sts=None, ets=None):
        '''Generate tide information from the indicated period.  If no start
        and end time are specified, start with the start of the day of the 
        current time and end at twice the interval.'''
        if sts is None:
            sts = weeutil.weeutil.startOfDay(int(time.time()))
        if ets is None:
            ets = sts + 2 * self.interval
        st = time.strftime('%Y-%m-%d %H:%M', time.localtime(sts))
        et = time.strftime('%Y-%m-%d %H:%M', time.localtime(ets))
        cmd = "%s %s -l'%s' -b'%s' -e'%s'" % (
            self.tideprog, self.tideargs, self.location, st, et)
        try:
            loginf('%s: generating tides for %s days' %
                   (XT_KEY, self.interval / (24*3600)))
            logdbg("%s: running command '%s'" % (XT_KEY, cmd))
            p = subprocess.Popen(cmd, shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            rc = p.returncode
            if rc is not None:
                logerr('%s: generate tide failed: code=%s' % (XT_KEY, -rc))
                return None
            out = []
            for line in p.stdout:
                if string.find(line, self.location) >= 0:
                    out.append(line)
            if out:
                return out
            err = []
            for line in p.stderr:
                line = string.rstrip(line)
                err.append(line)
            errmsg = ' '.join(err)
            idx = errmsg.find('XTide Error:')
            if idx >= 0:
                errmsg = errmsg[idx:]
            idx = errmsg.find('XTide Fatal Error:')
            if idx >= 0:
                errmsg = errmsg[idx:]
            logerr('%s: generate tide failed: %s' % (XT_KEY, errmsg))
            return None
        except OSError, e:
            logerr('%s: generate tide failed: %s' % (XT_KEY, e))
        return None

    def parse_forecast(self, lines, now=None):
        '''Convert the text output into an array of records.'''
        if now is None:
            now = int(time.time())
        records = []
        for line in lines:
            line = string.rstrip(line)
            fields = string.split(line, ',')
            if fields[4] == 'High Tide' or fields[4] == 'Low Tide':
                s = '%s %s' % (fields[1], fields[2])
                tt = time.strptime(s, '%Y.%m.%d %H:%M')
                ts = time.mktime(tt)
                ofields = string.split(fields[3], ' ')
                record = {}
                record['method'] = XT_KEY
                if ofields[1] == 'ft':
                    record['usUnits'] = weewx.US
                elif ofields[1] == 'm':
                    record['usUnits'] = weewx.METRIC
                else:
                    record['usUnits'] = None
                    logerr("%s: unknown units '%s'" % (XT_KEY, ofields[1]))
                record['dateTime'] = int(now)
                record['issued_ts'] = int(now)
                record['event_ts'] = int(ts)
                record['hilo'] = XT_HILO[fields[4]]
                record['offset'] = ofields[0]
                record['location'] = self.location
                records.append(record)
        return records



# -----------------------------------------------------------------------------
# ForecastVariables
# -----------------------------------------------------------------------------

TRACE_AMOUNT = 0.001

# FIXME: weewx should define 'length' rather than (as well as?) 'altitude'
DEFAULT_UNITS = {
    weewx.US: {
        'group_time': 'unix_epoch',
        'group_altitude': 'foot',
        'group_temperature': 'degree_F',
        'group_speed': 'mile_per_hour',
        'group_rain': 'inch',
        'group_percent': 'percent',
        },
    weewx.METRIC: {
        'group_time': 'unix_epoch',
        'group_altitude': 'meter',
        'group_temperature': 'degree_C',
        'group_speed': 'km_per_hour',
        'group_rain': 'mm',
        'group_percent': 'percent',
        }
    }

UNIT_GROUPS = {
    'dateTime':     'group_time',
    'issued_ts':    'group_time',
    'event_ts':     'group_time',
    'temp':         'group_temperature',
    'tempMin':      'group_temperature',
    'tempMax':      'group_temperature',
    'dewpoint':     'group_temperature',
    'dewpointMin':  'group_temperature',
    'dewpointMax':  'group_temperature',
    'humidity':     'group_percent',
    'humidityMin':  'group_percent',
    'humidityMax':  'group_percent',
    'windSpeed':    'group_speed',
    'windSpeedMin': 'group_speed',
    'windSpeedMax': 'group_speed',
    'windGust':     'group_speed',
    'pop':          'group_percent',
    'qpf':          'group_rain',
    'qpfMin':       'group_rain',
    'qpfMax':       'group_rain',
    'qsf':          'group_rain',
    'qsfMin':       'group_rain',
    'qsfMax':       'group_rain',
    'windChill':    'group_temperature',
    'heatIndex':    'group_temperature',
    }

PERIOD_FIELDS_WITH_UNITS = [
    'dateTime',
    'issued_ts',
    'event_ts',
    'temp',
    'tempMin',
    'tempMax',
    'dewpoint',
    'humidity',
    'windSpeed',
    'windGust',
    'pop',
    'qpf',
    'qpfMin',
    'qpfMax',
    'qsf',
    'qsfMin',
    'qsfMax',
    'windChill',
    'heatIndex',
    ]

SUMMARY_FIELDS_WITH_UNITS = [
    'dateTime',
    'issued_ts',
    'event_ts',
    'temp',
    'tempMin',
    'tempMax',
    'dewpoint',
    'dewpointMin',
    'dewpointMax',
    'humidity',
    'humidityMin',
    'humidityMax',
    'windSpeed',
    'windSpeedMin',
    'windSpeedMax',
    'windGust',
    'pop',
    'qpf',
    'qpfMin',
    'qpfMax',
    'qsf',
    'qsfMin',
    'qsfMax',
    ]

def _parse_precip_qty(s):
    '''convert the string to a qty,min,max tuple

    0.4       -> 0.4,0.4,0.4
    0.5-0.8   -> 0.65,0.5,0.8
    0.00-0.00 -> 0,0,0
    00-00     -> 0,0,0
    T         -> 0
    '''
    if s is None or s == '':
        return None,None,None
    elif s.find('T') >= 0:
        return TRACE_AMOUNT,TRACE_AMOUNT,TRACE_AMOUNT
    elif s.find('-') >= 0:
        try:
            [lo,hi] = s.split('-')
            xmin = float(lo)
            xmax = float(hi)
            x = (xmax + xmin) / 2
            return x,xmin,xmax
        except Exception, e:
            logerr("unrecognized precipitation quantity '%s': %s" % (s,e))
    else:
        try:
            x = float(s)
            xmin = x
            xmax = x
            return x,xmin,xmax
        except Exception, e:
            logerr("unrecognized precipitation quantity '%s': %s" % (s,e))
    return None,None,None

def _create_from_histogram(histogram):
    '''use the item with highest count in the histogram'''
    x = None
    cnt = 0
    for key in histogram:
        if histogram[key] > cnt:
            x = key
            cnt = histogram[key]
    return x

def _get_stats(key, a, b):
    try:
        s = a.get(key, None)
        if type(s) == weewx.units.ValueHelper:
            x = weewx.units.convertStd(s.getValueTuple(), weewx.US)[0]
        else:
            x = float(s)
        if b[key] is None:
            b[key] = x
            b[key+'N'] = 1
            b[key+'Min'] = x
            b[key+'Max'] = x
        else:
            n = b[key+'N'] + 1
            b[key] = (b[key] * b[key+'N'] + x) / n
            b[key+'N'] = n
            if x < b[key+'Min']:
                b[key+'Min'] = x
            if x > b[key+'Max']:
                b[key+'Max'] = x
    except Exception, e:
        pass

def _get_sum(key, a, b):
    try:
        s = a.get(key, None)
        if type(s) == weewx.units.ValueHelper:
            x = weewx.units.convertStd(s.getValueTuple(), weewx.US)[0]
        else:
            x = float(s)
        if b.get(key, None) is None:
            b[key] = 0
        return b[key] + x
    except Exception, e:
        pass
    return b.get(key, None)

def _get_min(key, a, b):
    try:
        s = a.get(key, None)
        if type(s) == weewx.units.ValueHelper:
            x = weewx.units.convertStd(s.getValueTuple(), weewx.US)[0]
        else:
            x = float(s)
        if b.get(key, None) is None or x < b[key]:
            return x
    except Exception, e:
        pass
    return b.get(key, None)

def _get_max(key, a, b):
    try:
        s = a.get(key, None)
        if type(s) == weewx.units.ValueHelper:
            x = weewx.units.convertStd(s.getValueTuple(), weewx.US)[0]
        else:
            x = float(s)
        if b.get(key, None) is None or x > b[key]:
            return x
    except Exception, e:
        pass
    return b.get(key, None)


class ForecastVariables(SearchList):
    """Bind forecast variables to database records."""

    def __init__(self, generator):
        '''
        generator - the FileGenerator that uses this extension

        fd - the 'Forecast' section of weewx.conf
        sd - the 'Forecast' section of skin.conf
        '''
        fd = generator.config_dict.get('Forecast', {})
        sd = generator.skin_dict.get('Forecast', {})

        self.database = generator._getArchive(fd['database'])
        self.table = fd.get('table','archive')

        self.latitude = generator.stn_info.latitude_f
        self.longitude = generator.stn_info.longitude_f
        self.altitude = generator.stn_info.altitude_vt[0]
        self.moon_phases = generator.skin_dict.get('Almanac', {}).get('moon_phases', weeutil.Moon.moon_phases)
        self.formatter = generator.formatter
        self.converter = generator.converter

        label_dict = sd.get('Labels', {})
        self.labels = {}
        self.labels['Directions'] = dict(directions_label_dict.items() + label_dict.get('Directions', {}).items())
        self.labels['Tide'] = dict(tide_label_dict.items() + label_dict.get('Tide', {}).items())
        self.labels['Weather'] = dict(weather_label_dict.items() + label_dict.get('Weather', {}).items())
        self.labels['Zambretti'] = dict(zambretti_label_dict.items() + label_dict.get('Zambretti', {}).items())

        self.database_max_tries = 3
        self.database_retry_wait = 5 # seconds

    def get_extension(self, timespan, archivedb, statsdb):
        return {'forecast': self}

    def _getTides(self, context, from_ts=int(time.time()), max_events=1):
        sql = "select dateTime,issued_ts,event_ts,hilo,offset,usUnits,location from %s where method = 'XTide' and dateTime = (select dateTime from %s where method = 'XTide' order by dateTime desc limit 1) and event_ts >= %d order by dateTime asc" % (self.table, self.table, from_ts)
        if max_events is not None:
            sql += ' limit %d' % max_events
        records = []
        for count in range(self.database_max_tries):
            try:
                records = []
                for rec in self.database.genSql(sql):
                    r = {}
                    r['dateTime'] = self._create_value(context,
                                                       rec[0], 'group_time')
                    r['issued_ts'] = self._create_value(context,
                                                        rec[1], 'group_time')
                    r['event_ts'] = self._create_value(context,
                                                       rec[2], 'group_time')
                    r['hilo'] = rec[3]
                    r['offset'] = self._create_value(context,
                                                     rec[4], 'group_altitude',
                                                     unit_system=rec[5])
                    r['location'] = rec[6]
                    records.append(r)
                break
            except Exception, e:
                logerr('get tides failed (attempt %d of %d): %s' %
                       ((count+1), self.database_max_tries, e))
                logdbg('waiting %d seconds before retry' %
                       self.database_retry_wait)
                time.sleep(self.database_retry_wait)
        return records

    def _getRecords(self, fid, from_ts, to_ts, max_events=1):
        '''get the latest requested forecast of indicated type for the
        indicated period of time, limiting to max_events records'''
        # NB: this query assumes that forecasting is deterministic, i.e., two
        # queries to a single forecast will always return the same results.
        sql = "select * from %s where method = '%s' and event_ts >= %d and event_ts <= %d and dateTime = (select dateTime from %s where method = '%s' order by dateTime desc limit 1) order by event_ts asc" % (self.table, fid, from_ts, to_ts, self.table, fid)
        if max_events is not None:
            sql += ' limit %d' % max_events
        records = []
        for count in range(self.database_max_tries):
            try:
                records = []
                columns = self.database.connection.columnsOf(self.table)
                for rec in self.database.genSql(sql):
                    r = {}
                    for i,f in enumerate(columns):
                        r[f] = rec[i]
                    records.append(r)
                break
            except Exception, e:
                logerr('get %s failed (attempt %d of %d): %s' %
                       (fid, (count+1), self.database_max_tries, e))
                logdbg('waiting %d seconds before retry' %
                       self.database_retry_wait)
                time.sleep(self.database_retry_wait)
        return records

    def _create_value(self, context, value_str, group,
                      units=None, unit_system=weewx.US):
        '''create a value with units from the specified string'''
        v = None
        if value_str is not None:
            try:
                if group == 'group_time':
                    v = int(value_str)
                else:
                    v = float(value_str)
            except Exception, e:
                logerr("cannot create value from '%s': %s" % (value_str,e))
        if units is None:
            units = DEFAULT_UNITS[unit_system][group]
        vt = weewx.units.ValueTuple(v, units, group)
        vh = weewx.units.ValueHelper(vt, context,
                                     self.formatter, self.converter)
        return vh

    def label(self, module, txt):
        if module == 'NWS':  # for backward compatibility
            module = 'Weather'
        return self.labels.get(module, {}).get(txt, txt)

    def xtide(self, index, from_ts=int(time.time())):
        records = self._getTides('xtide', from_ts=from_ts, max_events=index+1)
        if 0 <= index < len(records):
            return records[index]
        return { 'dateTime' : '',
                 'issued_ts' : '',
                 'event_ts' : '',
                 'hilo' : '',
                 'offset' : '',
                 'location' : '' }

    def xtides(self, from_ts=int(time.time()), max_events=40):
        '''The tide forecast returns tide events into the future from the
        indicated time using the latest tide forecast.

        from_ts - timestamp in epoch seconds.  if nothing is specified, the
                  current time is used.

        max_events - maximum number of events to return.  default to 10 days'
                     worth of tides.'''
        records = self._getTides('xtides', from_ts=from_ts, max_events=max_events)
        return records

    def zambretti(self):
        '''The zambretti forecast applies at the time at which it was created,
        and is good for about 6 hours.  So there is no difference between the
        created timestamp and event timestamp.'''
        sql = "select dateTime,zcode from %s where method = 'Zambretti' order by dateTime desc limit 1" % self.table
        record = None
        for count in range(self.database_max_tries):
            try:
                record = self.database.getSql(sql)
                break
            except Exception, e:
                logerr('get zambretti failed (attempt %d of %d): %s' %
                       ((count+1), self.database_max_tries, e))
                logdbg('waiting %d seconds before retry' %
                       self.database_retry_wait)
                time.sleep(self.database_retry_wait)
        if record is None:
            return { 'dateTime' : '', 'issued_ts' : '', 'event_ts' : '',
                     'code' : '', 'text' : '' }
        th = self._create_value('zambretti', record[0], 'group_time')
        code = record[1]
        text = self.labels['Zambretti'].get(code, code)
        return { 'dateTime' : th, 'issued_ts' : th, 'event_ts' : th,
                 'code' : code, 'text' : text, }

    def weather_periods(self, fid, from_ts=None, to_ts=None, max_events=240):
        '''Returns forecast records for the indicated source from the 
        specified time.  For quantities that have units, create an appropriate
        ValueHelper so that units conversions can happen.

        fid - a weather forecast identifier, e.g., 'NWS', 'WU'

        from_ts - timestamp in epoch seconds.  if None specified then the
                  current time is used.

        to_ts - timestamp in epoch seconds.  if None specified then 14
                days from the from_ts is used.

        max_events - maximum number of events to return.  None is no limit.
                     default to 240 (24 hours * 10 days).
        '''
        if from_ts is None:
            from_ts = int(time.time())
        if to_ts is None:
            to_ts = from_ts + 14 * 24 * 3600 # 14 days into the future
        records = self._getRecords(fid, from_ts, to_ts, max_events=max_events)
        for r in records:
            r['qpf'],r['qpfMin'],r['qpfMax'] = _parse_precip_qty(r['qpf'])
            r['qsf'],r['qsfMin'],r['qsfMax'] = _parse_precip_qty(r['qsf'])
            for f in PERIOD_FIELDS_WITH_UNITS:
                r[f] = self._create_value('weather_periods',
                                          r[f], UNIT_GROUPS[f],
                                          unit_system=r['usUnits'])
            r['precip'] = {}
            for p in precip_types:
                v = r.get(p, None)
                if v is not None:
                    r['precip'][p] = v
            # all other fields are strings
        return records

    # the 'periods' option is a weak attempt to reduce database hits when
    # the summary is used in tables.  early testing shows a reduction in
    # time to generate 'toDate' files from about 40s to about 16s on a slow
    # arm cpu for the exfoliation skin (primarily the forecast.html page).
    def weather_summary(self, fid, ts=None, periods=None):
        '''Create a weather summary from periods for the day of the indicated
        timestamp.  If the timestamp is None, use the current time.

        fid - forecast identifier, e.g., 'NWS', 'XTide'

        ts - timestamp in epoch seconds during desired day
        '''
        if ts is None:
            ts = int(time.time())
        from_ts = weeutil.weeutil.startOfDay(ts)
        dur = 24 * 3600 # one day
        rec = {
            'dateTime' : ts,
            'usUnits' : weewx.US,
            'issued_ts' : None,
            'event_ts' : int(from_ts),
            'duration' : dur,
            'location' : None,
            'clouds' : None,
            'temp' : None, 'tempMin' : None, 'tempMax' : None,
            'dewpoint' : None, 'dewpointMin' : None, 'dewpointMax' : None,
            'humidity' : None, 'humidityMin' : None, 'humidityMax' : None,
            'windSpeed' : None, 'windSpeedMin' : None, 'windSpeedMax' : None,
            'windGust' : None,
            'windDir' : None, 'windDirs' : {},
            'windChar' : None, 'windChars' : {},
            'pop' : None,
            'qpf' : None, 'qpfMin' : None, 'qpfMax' : None,
            'qsf' : None, 'qsfMin' : None, 'qsfMax' : None,
            'precip' : [],
            'obvis' : [],
            }
        outlook_histogram = {}
        if periods is not None:
            for p in periods:
                if from_ts <= p['event_ts'].raw <= from_ts + dur:
                    if rec['location'] is None:
                        rec['location'] = p['location']
                    if rec['issued_ts'] is None:
                        rec['issued_ts'] = p['issued_ts'].raw
                    rec['usUnits'] = p['usUnits']
                    x = p['clouds']
                    if x is not None:
                        outlook_histogram[x] = outlook_histogram.get(x,0) + 1
                    for s in ['temp', 'dewpoint', 'humidity', 'windSpeed']:
                        _get_stats(s, p, rec)
                    rec['windGust'] = _get_max('windGust', p, rec)
                    x = p['windDir']
                    if x is not None:
                        rec['windDirs'][x] = rec['windDirs'].get(x,0) + 1
                    x = p['windChar']
                    if x is not None:
                        rec['windChars'][x] = rec['windChars'].get(x,0) + 1
                    rec['pop'] = _get_max('pop', p, rec)
                    for s in ['qpf','qsf']:
                        rec[s] = _get_sum(s, p, rec)
                    for s in ['qpfMin','qsfMin']:
                        rec[s] = _get_min(s, p, rec)
                    for s in ['qpfMax','qsfMax']:
                        rec[s] = _get_max(s, p, rec)
                    for pt in p['precip']:
                        if pt not in rec['precip']:
                            rec['precip'].append(pt)
                    if p['obvis'] is not None and p['obvis'] not in rec['obvis']:
                        rec['obvis'].append(p['obvis'])
        else:
            records = self._getRecords(fid, from_ts, from_ts+dur, max_events=40)
            for r in records:
                if rec['location'] is None:
                    rec['location'] = r['location']
                if rec['issued_ts'] is None:
                    rec['issued_ts'] = r['issued_ts']
                rec['usUnits'] = r['usUnits']
                x = r['clouds']
                if x is not None:
                    outlook_histogram[x] = outlook_histogram.get(x,0) + 1
                for s in ['temp', 'dewpoint', 'humidity', 'windSpeed']:
                    _get_stats(s, r, rec)
                rec['windGust'] = _get_max('windGust', r, rec)
                x = r['windDir']
                if x is not None:
                    rec['windDirs'][x] = rec['windDirs'].get(x,0) + 1
                x = r['windChar']
                if x is not None:
                    rec['windChars'][x] = rec['windChars'].get(x,0) + 1
                rec['pop'] = _get_max('pop', r, rec)
                r['qpf'],r['qpfMin'],r['qpfMax'] = _parse_precip_qty(r['qpf'])
                r['qsf'],r['qsfMin'],r['qsfMax'] = _parse_precip_qty(r['qsf'])
                for s in ['qpf', 'qsf']:
                    rec[s] = _get_sum(s, r, rec)
                for s in ['qpfMin', 'qsfMin']:
                    rec[s] = _get_min(s, r, rec)
                for s in ['qpfMax', 'qsfMax']:
                    rec[s] = _get_max(s, r, rec)
                for pt in precip_types:
                    if r.get(pt, None) is not None and pt not in rec['precip']:
                        rec['precip'].append(pt)
                if r['obvis'] is not None and r['obvis'] not in rec['obvis']:
                    rec['obvis'].append(r['obvis'])

        for f in SUMMARY_FIELDS_WITH_UNITS:
            rec[f] = self._create_value('weather_summary',
                                        rec[f], UNIT_GROUPS[f],
                                        unit_system=rec['usUnits'])
        rec['clouds']   = _create_from_histogram(outlook_histogram)
        rec['windDir']  = _create_from_histogram(rec['windDirs'])
        rec['windChar'] = _create_from_histogram(rec['windChars'])
        return rec

    # FIXME: this is more appropriately called astronomy, at least from
    #        the template point of view.
    def almanac(self, ts=int(time.time())):
        '''Returns the almanac object for the indicated timestamp.'''
        return weewx.almanac.Almanac(ts,
                                     self.latitude, self.longitude,
                                     self.altitude,
                                     moon_phases=self.moon_phases,
                                     formatter=self.formatter)
