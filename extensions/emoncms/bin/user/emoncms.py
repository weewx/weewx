# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# EmonCMS
#==============================================================================
# Upload data to EmonCMS
# http://emoncms.org
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[EmonCMS]]
#     token = TOKEN

import Queue
import sys
import syslog
import urllib
import urllib2

import weewx
import weewx.restx
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'restx: EmonCMS: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class EmonCMS(weewx.restx.StdRESTbase):
    """Upload to an emoncms server."""

    def __init__(self, engine, config_dict):
        """Initialize for posting to emoncms.

        Required parameters:

        token: unique token

        Optional parameters:
        
        station: station identifier
        Default is None.

        server_url: URL of the server
        Default is the emoncms.org site
        
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
        super(EmonCMS, self).__init__(engine, config_dict)        
        try:
            site_dict = dict(config_dict['StdRESTful']['EmonCMS'])
            site_dict['token']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = EmonCMSThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded using token %s" %
               ('X'*(len(site_dict['token'])-4) + site_dict['token'][-4:]))

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class EmonCMSThread(weewx.restx.RESTThread):

    _SERVER_URL = 'http://emoncms.org/input/post'
    _FORMATS = {'barometer'   : 'barometer_inHg:%.3f',
                'outTemp'     : 'outTemp_F:%.1f',
                'outHumidity' : 'outHumidity:%03.0f',
                'inTemp'      : 'inTemp_F:%.1f',
                'inHumidity'  : 'inHumidity:%03.0f',
                'windSpeed'   : 'windSpeed_mph:%.2f',
                'windDir'     : 'windDir:%03.0f',
                'windGust'    : 'windGust_mph:%.2f',
                'dewpoint'    : 'dewpoint_F:%.1f',
                'rain24'      : 'rain24_in:%.2f',
                'hourRain'    : 'hourRain_in:%.2f',
                'dayRain'     : 'dayRain_in:%.2f',
                'radiation'   : 'radiation:%.2f',
                'UV'          : 'UV:%.2f'}

    def __init__(self, queue, token, database_dict,
                 station=None, server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True, max_backlog=sys.maxint,
                 stale=None, max_tries=3, post_interval=None, timeout=60):
        super(EmonCMSThread, self).__init__(queue,
                                            protocol_name='EmonCMS',
                                            database_dict=database_dict,
                                            log_success=log_success,
                                            log_failure=log_failure,
                                            max_backlog=max_backlog,
                                            stale=stale,
                                            max_tries=max_tries,
                                            post_interval=post_interval,
                                            timeout=timeout)
        self.token = token
        self.station = station
        self.server_url = server_url
        self.skip_upload = to_bool(skip_upload)

    def process_record(self, record, archive):
        r = self.get_record(record, archive)
        url = self.get_url(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url)
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if txt != 'ok' :
            raise weewx.restx.FailedPost("Server returned '%s'" % txt)

    def get_url(self, record):
        prefix = ''
        if self.station is not None:
            prefix = '%s_' % urllib.quote_plus(self.station)
        data = []
        for k in self._FORMATS:
            v = record[k]
            if v is not None:
                s = self._FORMATS[k] % v
                data.append('%s%s' % (prefix, s))
        url = '%s?apikey=%s&time=%s&json={%s}' % (
            self.server_url, self.token, record['dateTime'], ','.join(data))
        logdbg('url: %s' % url)
        return url
