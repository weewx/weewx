# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# SEG
#==============================================================================
# Upload data to Smart Energy Groups
# http://smartenergygroups.com/
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[SmartEnergyGroups]]
#     token = TOKEN
#     station = station_name

import Queue
import sys
import syslog
import urllib
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'restx: SEG: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class SEG(weewx.restx.StdRESTbase):
    """Upload to a smart energy groups server."""

    def __init__(self, engine, config_dict):
        """Initialize for upload to SEG.

        Required parameters:

        token: unique token
        
        station: station identifier - used as the SEG node

        Optional parameters:
        
        station: station identifier
        Default is None.

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
        super(SEG, self).__init__(engine, config_dict)
        try:
            site_dict = weewx.restx.get_dict(config_dict, 'SmartEnergyGroups')
            site_dict['station']
            site_dict['token']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = SEGThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded for station %s" % site_dict['station'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class SEGThread(weewx.restx.RESTThread):

    _SERVER_URL = 'http://api.smartenergygroups.com/api_sites/stream'

    # Types and formats of the data to be published:        weewx  seg default
    _FORMATS = {'barometer'   : 'barometric_pressure %.3f', # inHg   mbar
                'outTemp'     : 'temperature %.1f',         # F      C
                'outHumidity' : 'relative_humidity %.0f',   # %      %
                'inTemp'      : 'temperature_in %.1f',      # F      C
                'inHumidity'  : 'humidity_in %03.0f',       # %      %
                'windSpeed'   : 'wind_speed %.2f',          # mph    m/s
                'windDir'     : 'wind_direction %03.0f',    # compass degree
                'windGust'    : 'wind_gust %.2f',           # mph    m/s
                'dewpoint'    : 'dewpoint %.1f',            # F      C
                'rain24'      : '24hr_rainfall %.2f',       # in     mm
                'hourRain'    : 'hour_rainfall %.2f',       # in     mm
                'dayRain'     : 'day_rainfall %.2f',        # in     mm
                'radiation'   : 'illuminance %.2f',         # W/m^2  W/m^2
                'UV'          : 'UV %.2f'}                  # number

    # unit conversions
    _UNITS = {'barometer' : ['group_pressure','inHg','mbar'],
              'outTemp'   : ['group_temperature','degree_F','degree_C'],
              'windSpeed' : ['group_speed','mile_per_hour','meter_per_second'],
              'windGust'  : ['group_speed','mile_per_hour','meter_per_second'],
              'dewpoint'  : ['group_temperature','degree_F','degree_C'],
              'rain24'    : ['group_rain','inch','mm'],
              'hourRain'  : ['group_rain','inch','mm'],
              'dayRain'   : ['group_rain','inch','mm'] }

    def __init__(self, queue, token, station, database_dict,
                 server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True,
                  post_interval=300, max_backlog=sys.maxint, stale=None,
                 timeout=60, max_tries=3, retry_wait=5):
        super(SEGThread, self).__init__(queue,
                                        protocol_name='SEG',
                                        database_dict=database_dict,
                                        post_interval=post_interval,
                                        max_backlog=max_backlog,
                                        stale=stale,
                                        log_success=log_success,
                                        log_failure=log_failure,
                                        max_tries=max_tries,
                                        timeout=timeout,
                                        retry_wait=retry_wait)
        self.token = token
        self.station = station
        self.server_url = server_url
        self.skip_upload = to_bool(skip_upload)

    def process_record(self, record, archive):
        r = self.get_record(record, archive)
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(self.server_url, data)
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        req.get_method = lambda: 'PUT'
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if txt.find('(status ok)') < 0:
            raise weewx.restx.FailedPost("Server returned '%s'" % txt)

    def get_data(self, record):
        elements = []
        for k in self._FORMATS:
            v = record[k]
            if v is not None:
                if k in self._UNITS:
                    vt = (v, self._UNITS[k][1], self._UNITS[k][0])
                    v = weewx.units.convert(vt, self._UNITS[k][2])[0]
                s = self._FORMATS[k] % v
                elements.append('(%s)' % s)
        if len(elements) == 0:
            return None
        node = urllib.quote_plus(self.station)
        elements.insert(0, '(node %s %s ' % (node, record['dateTime']))
        elements.append(')')
        elements.insert(0, 'data_post=(site %s ' % self.token)
        elements.append(')')
        data = ''.join(elements)
        logdbg('data: %s' % data)
        return data

# for backward compatibility
SmartEnergyGroups = SEG
