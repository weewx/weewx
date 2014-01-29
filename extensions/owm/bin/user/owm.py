# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# OpenWeatherMap.org
#==============================================================================
# Upload data to OpenWeatherMap
#  http://openweathermap.org
#
# Thanks to Antonio Burriel for the dewpoint, longitude, and radiation fixes.
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[OpenWeatherMap]]
#     username = OWM_USERNAME
#     password = OWM_PASSWORD
#     station_name = STATION_NAME

import Queue
import base64
import syslog
import urllib
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'restx: OWM: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class OpenWeatherMap(weewx.restx.StdRESTbase):
    """Upload using the OpenWeatherMap protocol."""
    
    def __init__(self, engine, config_dict):
        """Initialize for posting data.

        username: OpenWeatherMap username

        password: OpenWeatherMap password

        station_name: station name

        latitude: Station latitude in decimal degrees
        Default is station latitude

        longitude: Station longitude in decimal degrees
        Default is station longitude

        altitude: Station altitude in meters
        Default is station altitude

        Optional parameters:
        
        station: station identifier
        Default is None.

        server_url: URL of the server
        Default is the OpenWeatherMap site
        
        log_success: If True, log a successful post in the system log.
        Default is True.

        log_failure: If True, log an unsuccessful post in the system log.
        Default is True.

        max_backlog: How many records are allowed to accumulate in the queue
        before the queue is trimmed.
        Default is 0

        max_tries: How many times to try the post before giving up.
        Default is 3

        stale: How old a record can be and still considered useful.
        Default is None (never becomes too old).

        post_interval: How long to wait between posts.
        Default is None (post every record).

        timeout: How long to wait for the server to respond before giving up.
        Default is 60 seconds

        skip_upload: debugging option to display data but do not upload
        Default is False
        """
        super(OpenWeatherMap, self).__init__(engine, config_dict)        
        try:
            site_dict = dict(config_dict['StdRESTful']['OpenWeatherMap'])
            site_dict['username']
            site_dict['password']
            site_dict['station_name']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('latitude', engine.stn_info.latitude_f)
        site_dict.setdefault('longitude', engine.stn_info.longitude_f)
        site_dict.setdefault('altitude', engine.stn_info.altitude_vt[0])
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = OpenWeatherMapThread(self.archive_queue,
                                                   **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded for station %s" %
               site_dict['station_name'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class OpenWeatherMapThread(weewx.restx.RESTThread):
    """The OpenWeatherMap api does not include timestamp, so we can only
    upload the latest observation.
    """

    _SERVER_URL = 'http://openweathermap.org/data/post'
    _DATA_MAP = {
        'wind_dir':   ('windDir',     '%.0f', 1.0, 0.0), # degrees
        'wind_speed': ('windSpeed',   '%.1f', 0.2777777777, 0.0), # m/s
        'wind_gust':  ('windGust',    '%.1f', 0.2777777777, 0.0), # m/s
        'temp':       ('outTemp',     '%.1f', 1.0, 0.0), # C
        'humidity':   ('outHumidity', '%.0f', 1.0, 0.0), # percent
        'pressure':   ('barometer',   '%.3f', 1.0, 0.0), # mbar?
        'rain_1h':    ('hourRain',    '%.2f', 10.0, 0.0), # mm
        'rain_24h':   ('rain24',      '%.2f', 10.0, 0.0), # mm
        'rain_today': ('dayRain',     '%.2f', 10.0, 0.0), # mm
        'snow':       ('snow',        '%.2f', 10.0, 0.0), # mm
        'lum':        ('radiation',   '%.2f', 1.0, 0.0), # W/m^2
        'dewpoint':   ('dewpoint',    '%.1f', 1.0, 273.15), # K
        'uv':         ('UV',          '%.2f', 1.0, 0.0),
        }

    def __init__(self, queue,
                 username, password, latitude, longitude, altitude,
                 station_name, database_dict,
                 server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True, max_backlog=0,
                 stale=None, max_tries=3, post_interval=None, timeout=60):
        super(OpenWeatherMapThread, self).__init__(queue,
                                                   protocol_name='OWM',
                                                   database_dict=database_dict,
                                                   log_success=log_success,
                                                   log_failure=log_failure,
                                                   max_backlog=max_backlog,
                                                   stale=stale,
                                                   max_tries=max_tries,
                                                   post_interval=post_interval,
                                                   timeout=timeout)
        self.username = username
        self.password = password
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.altitude = float(altitude)
        self.station_name = station_name
        self.server_url = server_url
        self.skip_upload = to_bool(skip_upload)

    def process_record(self, record, archive):
        r = self.get_record(record, archive)
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(self.server_url, urllib.urlencode(data))
        req.get_method = lambda: 'POST'
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        b64s = base64.encodestring('%s:%s' % (self.username, self.password)).replace('\n', '')
        req.add_header("Authorization", "Basic %s" % b64s)
        self.post_with_retries(req)

    def get_data(self, in_record):
        # put everything into the right units
        record = weewx.units.to_METRIC(in_record)

        # put data into expected scaling, structure, and format
        values = {}
        values['name'] = self.station_name
        values['lat']  = str(self.latitude)
        values['long'] = str(self.longitude)
        values['alt']  = str(self.altitude) # meter
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                v = record[rkey] * self._DATA_MAP[key][2] + self._DATA_MAP[key][3]
                values[key] = self._DATA_MAP[key][1] % v

        logdbg('data: %s' % values)
        return values
