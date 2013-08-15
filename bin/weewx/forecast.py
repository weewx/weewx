# $Id$
# Copyright 2013 Matthew Wall
"""weewx module that provides forecasts

Database Schema

   The schema is specified in user.schemas.defaultForecastSchema
   It defines the following fields:

   method - forecast method, e.g., Zambretti, NWS
   dateTime - timestamp in seconds when forecast was made

   database     nws                    wu                    zambretti
   field        field                  field                 field
   -----------  ---------------------  --------------------  ---------
   method
   dateTime
   usUnits

   zcode                                                     CODE

   foid
   id
   source
   desc
   ts
   hour         3HRLY | 6HRLY          date.hour
   tempMin      MIN/MAX | MAX/MIN      low.fahrenheit
   tempMax      MIN/MAX | MAX/MIN      high.fahrenheit
   temp         TEMP
   dewpoint     DEWPT
   humidity     RH                     avehumidity
   windDir      WIND DIR | PWIND DIR   avewind.dir
   windSpeed    WIND SPD               avewind.mph
   windGust     WIND GUST              maxwind.mph
   windChar     WIND CHAR
   clouds       CLOUDS | AVG CLOUNDS
   pop          POP 12HR               pop
   qpf          QPF 12HR               qpf_allday.in
   qsf          SNOW 12HR              snow_allday.in
   rain         RAIN
   rainshwrs    RAIN SHWRS
   tstms        TSTMS
   drizzle      DRIZZLE
   snow         SNOW
   snowshwrs    SNOW SHWRS
   flurries     FLURRIES
   sleet        SLEET
   frzngrain    FRZNG RAIN
   frzngdrzl    FRZNG DRZL
   obvis        OBVIS
   windChill    WIND CHILL
   heatIndex    HEAT INDEX

Configuration

   Some parameters can be defined in the Forecast section, then overridden
   for specific forecasting methods as needed.

[Forecast]
    # how often to calculate the forecast, in seconds
    forecast_interval = 300
    # how long to keep old forecasts, in seconds.  use None to keep forever.
    forecast_max_age = 604800
    # the database in which to record forecast information
    forecast_database = forecast_sqlite

    [[Zambretti]]
        # hemisphere can be NORTH or SOUTH
        hemisphere = NORTH

    [[NWS]]
        # first figure out your forecast office identifier (foid), then request
        # a point forecast using a url of this form in a web browser:
        #   http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt&issuedby=YOUR_THREE_LETTER_FOID
        # scan the output for a service location identifier corresponding
        # to your location.

        # how often to download the forecast, in seconds
        forecast_interval = 10800
        # national weather service location identifier
        id = MAZ014
        # national weather service forecast office identifier
        foid = BOX
        # url for point forecast matrix
        url = http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt

    [[WU]]
        # how often to download the forecast, in seconds
        forecast_interval = 10800
        # an api key is required to access the weather underground.
        # obtain an api key here:
        #   http://www.wunderground.com/weather/api/
        api_key = KEY
        # the location for the forecast can be one of the following:
        #   CA/San_Francisco     - US state/city
        #   60290                - US zip code
        #   Australia/Sydney     - Country/City
        #   37.8,-122.4          - latitude,longitude
        #   KJFK                 - airport code
        #   pws:KCASANFR70       - PWS id
        #   autoip               - AutoIP address location
        #   autoip.json?geo_ip=38.102.136.138 - specific IP address location
        # if no location is specified, station latitude and longitude are used
        location = 02139

[Databases]
    ...
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
        service_list = ... , weewx.forecast.ZambrettiForecast, weewx.forecast.NWSForecast, weewx.forecast.WUForecast
"""

# TODO: add option to prune forecast database
# TODO: add forecast data to skin variables

import httplib
import socket
import syslog
import time
import urllib2

import weewx
from weewx.wxengine import StdService
import weeutil.weeutil

try:
    import cjson as json
    setattr(json, 'dumps', json.encode)
    setattr(json, 'loads', json.decode)
except Exception, e:
    try:
        import simplejson as json
    except Exception, e:
        try:
            import json
        except Exception, e:
            json = None

def logdbg(msg):
    syslog.syslog(syslog.LOG_DEBUG, 'forecast: %s' % msg)

def loginf(msg):
    syslog.syslog(syslog.LOG_INFO, 'forecast: %s' % msg)

def logerr(msg):
    syslog.syslog(syslog.LOG_ERR, 'forecast: %s' % msg)

def get_int(config_dict, label, default_value):
    value = config_dict.get(label, default_value)
    if isinstance(value, str) and value.lower() == 'none':
        value = None
    if value is not None:
        try:
            value = int(value)
        except Exception, e:
            logerr("bad value '%s' for %s" % (value, label))
    return value

class Forecast(StdService):
    """Provide forecast."""

    def __init__(self, engine, config_dict, method_id):
        super(Forecast, self).__init__(engine, config_dict)
        d = config_dict['Forecast'] if 'Forecast' in config_dict.keys() else {}
        self.interval = get_int(d, 'forecast_interval', 300)
        self.max_age = get_int(d, 'forecast_max_age', 604800)
        self.method_id = method_id
        self.last_forecast_ts = 0
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.update_forecast)

    def update_forecast(self, event):
        now = time.time()
        if self.last_forecast_ts is not None \
                and self.interval is not None \
                and now - self.interval < self.last_forecast_ts:
            logdbg('not yet time to do the forecast')
            return
        fcast = self.get_forecast(event)
        if fcast is None:
            return
        self.save_forecast(fcast)
        self.last_forecast_ts = now
        if self.max_age is not None:
            self.prune_forecasts(self.method_id, now - self.max_age)

    def get_forecast(self, event):
        """get the forecast, return a forecast record"""
        return None

    def save_forecast(self, record):
        """add a forecast record to the forecast database

        record - dictionary with keys corresponding to database fields
        """
        self.archive.addRecord(record)

    def prune_forecasts(self, method_id, ts):
        """remove old forecasts from the database
        
        method_id - string that indicates the forecast method

        ts - timestamp, in seconds.  records older than this will be deleted.
        """
        sql = "delete * from %s where method = '%s' and dateTime < %d" % (self.table, method_id, ts)
        cursor = self.archive.connection.cursor()
        try:
            cursor.execute(sql)
            loginf('deleted %s forecasts prior to %d', (method_id, ts))
        except Exception, e:
            logerr('unable to delete old %s forecast records: %s' %
                   (method_id, e))

    def setup_database(self, config_dict, forecast_key):
        d = config_dict['Forecast'][forecast_key] \
            if forecast_key in config_dict['Forecast'].keys() else {}
        forecast_schema_str = d['forecast_schema'] \
            if 'forecast_schema' in d.keys() else \
            config_dict['Forecast'].get('forecast_schema',
                                        'user.schemas.defaultForecastSchema')
        forecast_schema = weeutil.weeutil._get_object(forecast_schema_str)
        forecast_db = d['forecast_database'] \
            if 'forecast_database' in d.keys() else \
            config_dict['Forecast']['forecast_database']
        self.archive = weewx.archive.Archive.open_with_create(config_dict['Databases'][forecast_db], forecast_schema)
        loginf('%s forecast using database %s' % (forecast_key, forecast_db))


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
        super(ZambrettiForecast, self).__init__(engine, config_dict, Z_KEY)
        d = config_dict['Forecast'][Z_KEY] \
            if Z_KEY in config_dict['Forecast'].keys() else {}
        self.interval = get_int(d, 'forecast_interval', self.interval)
        self.max_age = get_int(d, 'forecast_max_age', self.max_age)
        self.hemisphere = d.get('hemisphere', 'NORTH')
        self.setup_database(config_dict, Z_KEY)
        loginf('Zambretti: interval=%s max_age=%s hemisphere=%s' %
               (self.interval, self.max_age, self.hemisphere))

    def get_forecast(self, event):
        record = event.record
        ts = record['dateTime']
        if ts is None:
            logerr('skipping forecast: null timestamp in archive record')
            return None
        tt = time.gmtime(ts)
        pressure = record['barometer']
        month = tt.tm_mon - 1 # month is [0-11]
        wind = int(record['windDir'] / 22.5) # wind dir is [0-15]
        north = self.hemisphere.lower() != 'south'
        logdbg('calculate zambretti: pressure=%s month=%s wind=%s north=%s' %
               (pressure, month, wind, north))
        code = ZambrettiCode(pressure, month, wind, north)
        logdbg('zambretti code is %s' % code)
        if code is None:
            return None

        record = {}
        record['usUnits'] = weewx.US
        record['method'] = Z_KEY
        record['dateTime'] = ts
        record['zcode'] = code
        return record

zambretti_dict = {
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
    'Z' : "Stormy, much rain"
    }

def ZambrettiText(code):
    return zambretti_dict[code]

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
#   http://www.srh.noaa.gov/bmx/?n=pfm
#
# For actual forecasts, see:
#   http://www.weather.gov/
#
# codes for clouds:
#   CL - clear
#   FW - mostly clear
#   SC - partly cloudy
#   BK - mostly cloudy
#   OV - cloudy
#   B1 -
#   B2 - 
#
# codes for rain, drizzle, flurries, etc:
#   S - slight chance (< 20%)
#   C - chance (30%-50%)
#   L - likely (60%-70%)
#   O - occasional (80%-100%)
#   D - definite (80%-100%)
#
# codes for obvis (obstruction to visibility):
#   F   - fog
#   PF  - patchy fog
#   F+  - dense fog
#   PF+ - patchy dense fog
#   H   - haze
#   BS  - blowing snow
#   K   - smoke
#   BD  - blowing dust
#
# codes for wind char:
#   LT - 
#   GN - 
#
# -----------------------------------------------------------------------------

# The default URL contains the bare minimum to request a point forecast, less
# the forecast office identifier.
DEFAULT_NWS_PFM_URL = 'http://forecast.weather.gov/product.php?site=NWS&product=PFM&format=txt'

NWS_KEY = 'NWS'

class NWSForecast(Forecast):
    """Download forecast from US National Weather Service."""

    def __init__(self, engine, config_dict):
        super(NWSForecast, self).__init__(engine, config_dict, NWS_KEY)
        d = config_dict['Forecast'][NWS_KEY] \
            if NWS_KEY in config_dict['Forecast'].keys() else {}
        self.interval = get_int(d, 'forecast_interval', self.interval)
        self.max_age = get_int(d, 'forecast_max_age', self.max_age)
        self.url = d.get('url', DEFAULT_NWS_PFM_URL)
        self.max_tries = d.get('max_tries', 3)
        self.id = d.get('id', None)
        self.foid = d.get('foid', None)
        self.setup_database(config_dict, NWS_KEY)

        errmsg = []
        if self.id is None:
            errmsg.append('NWS location ID (id) is not specified')
        if self.foid is None:
            errmsg.append('NWS forecast office ID (foid) is not specified')
        if len(errmsg) > 0:
            raise Exception, '\n'.join(errmsg)

        loginf('NWS: interval=%s max_age=%s id=%s foid=%s' %
               (self.interval, self.max_age, self.id, self.foid))

    def get_forecast(self, event):
        text = DownloadNWSForecast(self.foid, self.url, self.max_tries)
        if text is None:
            logerr('no PFM data for %s from %s' %
                   (self.foid, self.url))
            return None
        matrix = ParseNWSForecast(text, self.id)
        if matrix is None:
            logerr('no PFM found for %s in forecast from %s' %
                   (self.id, self.foid))
            return None
        logdbg('nws forecast matrix: %s' % matrix)

        records = []
        for i,ts in enumerate(matrix['ts']):
            record = {}
            record['usUnits'] = weewx.US
            record['method'] = NWS_KEY
            record['dateTime'] = matrix['dateTime']
            record['ts'] = ts
            record['id'] = self.id
            record['foid'] = self.foid
            for label in matrix.keys():
                if isinstance(matrix[label], list):
                    record[label] = matrix[label][i]
            records.append(record)

        return records

# mapping of NWS names to database fields
nws_label_dict = {
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

def DownloadNWSForecast(foid, url=DEFAULT_NWS_PFM_URL, max_tries=3):
    """Download a point forecast matrix from the US National Weather Service"""

    u = '%s&issuedby=%s' % (url, foid) if url == DEFAULT_NWS_PFM_URL else url
    logdbg("downloading NWS forecast from '%s'" % u)
    for count in range(max_tries):
        try:
            response = urllib2.urlopen(u)
            text = response.read()
            return text
        except (urllib2.URLError, socket.error,
                httplib.BadStatusLine, httplib.IncompleteRead), e:
            logerr('failed attempt %d to download NWS forecast: %s' %
                   (count+1, e))
    else:
        logerr('failed to download NWS forecast')
    return None

def ParseNWSForecast(text, id):
    """Parse a United States National Weather Service point forcast matrix.
    Save it into a dictionary with per-hour elements for wind, temperature,
    etc. extracted from the point forecast.
    """

    alllines = text.splitlines()
    lines = None
    for line in iter(alllines):
        if line.startswith(id):
            lines = []
            lines.append(line)
        elif lines is not None:
            if line.startswith('$$'):
                break
            else:
                lines.append(line)
    if lines is None:
        return None

    rows3 = {}
    rows6 = {}
    ts = date2ts(lines[3])
    day_ts = weeutil.weeutil.startOfDay(ts)
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
        if label in nws_label_dict.keys():
            if mode == 3:
                rows3[nws_label_dict[label]] = line[14:]
            elif mode == 6:
                rows6[nws_label_dict[label]] = line[14:]

    matrix = {}
    matrix['id'] = id
    matrix['desc'] = lines[1]
    matrix['location'] = lines[2]
    matrix['dateTime'] = ts
    matrix['ts'] = []
    matrix['hour'] = []

    idx = 0
    day = day_ts
    lasth = None

    # get the 3-hour indexing
    indices3 = {}
    for i in range(0, len(rows3['hour']), 3):
        h = int(rows3['hour'][i:i+2])
        if lasth is not None and h < lasth:
            day += 24 * 3600
        lasth = h
        matrix['ts'].append(day + h*3600)
        matrix['hour'].append(h)
        indices3[i+1] = idx
        idx += 1
    nidx3 = idx

    # get the 6-hour indexing
    indices6 = {}
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
                indices6[i-1] = idx
                idx += 1
            s = ''
        else:
            s += rows6['hour'][i]
    if len(s) > 0:
        h = int(s)
        matrix['ts'].append(day + h*3600)
        matrix['hour'].append(h)
        indices6[len(rows6['hour'])-1] = idx
        idx += 1

    # get the 3 and 6 hour data
    filldata(matrix, idx, rows3, indices3)
    filldata(matrix, idx, rows6, indices6)
    return matrix

def filldata(matrix, nidx, rows, indices):
    """fill matrix with data from rows"""
    for label in rows.keys():
        if label not in matrix.keys():
            matrix[label] = [None]*nidx
        s = ''
        for i in range(0, len(rows[label])):
            if rows[label][i].isspace():
                if len(s) > 0:
                    matrix[label][indices[i-1]] = s
                s = ''
            else:
                s += rows[label][i]
        if len(s) > 0:
            matrix[label][indices[len(rows[label])-1]] = s

    # deal with min/max temperatures
    if 'tempMin' not in matrix.keys():
        matrix['tempMin'] = [None]*nidx
    if 'tempMax' not in matrix.keys():
        matrix['tempMax'] = [None]*nidx
    if 'tempMinMax' in matrix.keys():
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
    if 'tempMaxMin' in matrix.keys():
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
    s = '%s %s %s %s' % (parts[0], parts[4], parts[5], parts[6])
    ts = time.mktime(time.strptime(s, "%H%M %b %d %Y"))
    if parts[1] == 'PM':
        ts += 12 * 3600
    return int(ts)


# -----------------------------------------------------------------------------
# Weather Underground Forecasts
#
# Forecasts from the weather underground (www.wunderground.com).  WU provides
# an api that returns json/xml data.  This implementation uses the json format.
#
# For the weather underground api, see:
#   http://www.wunderground.com/weather/api/d/docs?MR=1
# -----------------------------------------------------------------------------

WU_KEY = 'WU'

DEFAULT_WU_URL = 'http://api.wunderground.com/api'

class WUForecast(Forecast):
    """Download forecast from Weather Underground."""

    def __init__(self, engine, config_dict):
        super(WUForecast, self).__init__(engine, config_dict, WU_KEY)
        d = config_dict['Forecast'][WU_KEY] \
            if WU_KEY in config_dict['Forecast'].keys() else {}
        self.interval = get_int(d, 'forecast_interval', self.interval)
        self.max_age = get_int(d, 'forecast_max_age', self.max_age)
        self.url = d.get('url', DEFAULT_WU_URL)
        self.max_tries = d.get('max_tries', 3)
        self.api_key = d.get('api_key', None)
        self.location = d.get('location', None)
        self.setup_database(config_dict, WU_KEY)

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
        if len(errmsg) > 0:
            raise Exception, '\n'.join(errmsg)

        loginf('WU: interval=%s max_age=%s api_key=%s location=%s' %
               (self.interval, self.max_age, self.api_key, self.location))

    def get_forecast(self, event):
        text = DownloadWUForecast(self.api_key, self.location, self.url, self.max_tries)
        if text is None:
            logerr('no forecast data for %s from %s' %
                   (self.location, self.url))
            return None
        matrix = ProcessWUForecast(text)
        if matrix is None:
            return None
        logdbg('wu forecast matrix: %s' % matrix)

        records = []
        for i,ts in enumerate(matrix['ts']):
            record = {}
            record['usUnits'] = weewx.US
            record['method'] = WU_KEY
            record['dateTime'] = matrix['dateTime']
            record['ts'] = ts
            for label in matrix.keys():
                if isinstance(matrix[label], list):
                    record[label] = matrix[label][i]
            records.append(record)

        return records

def DownloadWUForecast(api_key, location, url=DEFAULT_WU_URL, max_tries=3):
    """Download a forecast from the Weather Underground"""

    u = '%s/%s/forecast10day/q/%s.json' % (url, api_key, location) \
        if url == DEFAULT_WU_URL else url
    logdbg("downloading WU forecast from '%s'" % u)
    for count in range(max_tries):
        try:
            response = urllib2.urlopen(u)
            text = response.read()
            return text
        except (urllib2.URLError, socket.error,
                httplib.BadStatusLine, httplib.IncompleteRead), e:
            logerr('failed attempt %d to download WU forecast: %s' %
                   (count+1, e))
    else:
        logerr('failed to download WU forecast')
    return None

def ProcessWUForecast(text):
    obj = json.loads(text)
    if not 'response' in obj.keys():
        logerr('unknown format in WU response')
        return None
    response = obj['response']
    if 'error' in response.keys():
        logerr('error in WU response: %s: %s' %
               (response['error']['type'], response['error']['description']))
        return None

    fc = obj['forecast']['simpleforecast']['forecastday']
    tstr = obj['forecast']['txt_forecast']['date']
    ts = int(time.time())

    matrix = {}
    matrix['dateTime'] = ts
    matrix['ts'] = []
    matrix['hour'] = []
    matrix['tempMin'] = []
    matrix['tempMax'] = []
    matrix['humidity'] = []
    matrix['pop'] = []
    matrix['qpf'] = []
    matrix['qsf'] = []
    matrix['windSpeed'] = []
    matrix['windDir'] = []
    matrix['windGust'] = []
    for i,period in enumerate(fc):
        try:
            matrix['ts'].append(int(period['date']['epoch']))
            matrix['hour'].append(period['date']['hour'])
            try:
                matrix['tempMin'].append(float(period['low']['fahrenheit']))
            except Exception, e:
                logerr('bogus tempMin in WU forecast: %s' % e)
            try:
                matrix['tempMax'].append(float(period['high']['fahrenheit']))
            except Exception, e:
                logerr('bogus tempMax in WU forecast: %s' % e)
            matrix['humidity'].append(period['avehumidity'])
            matrix['pop'].append(period['pop'])
            matrix['qpf'].append(period['qpf_allday']['in'])
            matrix['qsf'].append(period['snow_allday']['in'])
            matrix['windSpeed'].append(period['avewind']['mph'])
            matrix['windDir'].append(dirstr(period['avewind']['dir']))
            matrix['windGust'].append(period['maxwind']['mph'])
        except Exception, e:
            logerr('bad timestamp in WU forecast: %s' % e)

    return matrix

def dirstr(s):
    directions = {'North':'N',
                  'South':'S',
                  'East':'E',
                  'West':'W',
                  }
    s = str(s)
    if s in directions.keys():
        s = directions[s]
    return s
