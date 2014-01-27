# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# WeatherBug
#==============================================================================
# Upload data to WeatherBug
# http://weather.weatherbug.com
#
# To enable this module, put this file in bin/user, add the following to
# weewx.conf, then restart weewx.
#
# [[WeatherBug]]
#     publisher_id = WEATHERBUG_ID
#     station_number = WEATHERBUG_STATION_NUMBER
#     password = WEATHERBUG_PASSWORD

import Queue
import sys
import syslog
import time
import urllib
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'wbug: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class WeatherBug(weewx.restx.StdRESTbase):
    """Upload using the WeatherBug protocol."""

    def __init__(self, engine, config_dict):
        """Initialize for upload to WeatherBug.

        Required parameters:

        publisher_id: WeatherBug publisher identifier

        station_number: WeatherBug station number

        password: WeatherBug password

        latitude: Station latitude in decimal degrees
        Default is station latitude

        longitude: Station longitude in decimal degrees
        Default is station longitude

        Optional parameters:

        server_url: URL of the server
        Default is the Smart Energy Groups site
        
        log_success: If True, log a successful post in the system log.
        Default is True.

        log_failure: If True, log an unsuccessful post in the system log.
        Default is True.

        max_backlog: How many records are allowed to accumulate in the queue
        before the queue is trimmed.
        Default is sys.maxint (essentially, allow any number).

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
        super(WeatherBug, self).__init__(engine, config_dict)
        try:
            site_dict = dict(config_dict['StdRESTful']['WeatherBug'])
            site_dict['publisher_id']
            site_dict['station_number']
            site_dict['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('latitude', engine.stn_info.latitude_f)
        site_dict.setdefault('longitude', engine.stn_info.longitude_f)
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = WeatherBugThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to WeatherBug")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class WeatherBugThread(weewx.restx.RESTThread):

    _SERVER_URL = 'http://data.backyard2.weatherbug.com/data/livedata.aspx'
    _DATA_MAP = {'tempf':         ('outTemp',     '%.1f'), # F
                 'humidity':      ('outHumidity', '%.0f'), # percent
                 'winddir':       ('windDir',     '%.0f'), # degree
                 'windspeedmph':  ('windSpeed',   '%.1f'), # mph
                 'windgustmph':   ('windGust',    '%.1f'), # mph
                 'baromin':       ('barometer',   '%.3f'), # inHg
                 'rainin':        ('rain',        '%.2f'), # in
                 'dailyRainin':   ('dayRain',     '%.2f'), # in
                 'monthlyrainin': ('monthRain',   '%.2f'), # in
                 'tempfhi':       ('outTempMax',  '%.1f'), # F
                 'tempflo':       ('outTempMin',  '%.1f'), # F
                 'Yearlyrainin':  ('yearRain',    '%.2f'), # in
                 'dewptf':        ('dewpoint',    '%.1f')} # F

    def __init__(self, queue,
                 publisher_id, station_number, password, latitude, longitude,
                 database_dict,
                 server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True, max_backlog=sys.maxint,
                 stale=None, max_tries=3, post_interval=None, timeout=60):
        super(WeatherBugThread, self).__init__(queue,
                                               protocol_name='WeatherBug',
                                               database_dict=database_dict,
                                               log_success=log_success,
                                               log_failure=log_failure,
                                               max_backlog=max_backlog,
                                               stale=stale,
                                               max_tries=max_tries,
                                               post_interval=post_interval,
                                               timeout=timeout)
        self.publisher_id = publisher_id
        self.station_number = station_number
        self.password = password
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.server_url = server_url
        self.skip_upload = to_bool(skip_upload)

    def process_record(self, record, archive):
        r = self.get_record(record, archive)
        url = self.get_url(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url)
        self.post_with_retries(req)

    def check_response(self, response):
        for line in response:
            if not line.startswith('Successfully Received'):
                raise weewx.restx.FailedPost("Server response: %s" % line)

    def get_url(self, record):
        # put everything into the right units and scaling
        if record['usUnits'] != weewx.US:
            converter = weewx.units.StdUnitConverters[weewx.US]
            record = converter.convertDict(record)

        # put data into expected structure and format
        values = { 'action':'live' }
        values['softwaretype'] = 'weewx_%s' % weewx.__version__
        values['ID'] = self.publisher_id
        values['Num'] = self.station_number
        values['Key'] = self.password
        time_tt = time.gmtime(record['dateTime'])
        values['dateutc'] = time.strftime("%Y-%m-%d %H:%M:%S", time_tt)
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                values[key] = self._DATA_MAP[key][1] % record[rkey]
        url = self.server_url + '?' + urllib.urlencode(values)
        logdbg('url: %s' % url)
        return url
