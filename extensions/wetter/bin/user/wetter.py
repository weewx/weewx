# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# wetter.com
#==============================================================================
# Upload data to wetter.com
#  http://wetter.com
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [Wetter]
#     username = USERNAME
#     password = PASSWORD

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
    syslog.syslog(level, 'restx: Wetter: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class Wetter(weewx.restx.StdRESTbase):
    """Upload using the wetter.com protocol."""

    def __init__(self, engine, config_dict):
        """Initialize for posting data to wetter.com.

        Required parameters:

        username: username

        password: password

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
        super(Wetter, self).__init__(engine, config_dict)        
        try:
            site_dict = dict(config_dict['StdRESTful']['Wetter'])
            site_dict['username']
            site_dict['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = WetterThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded for username %s" % site_dict['username'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class WetterThread(weewx.restx.RESTThread):

    _SERVER_URL = 'http://www.wetterarchiv.de/interface/http/input.php'
    _DATA_MAP = {'windrichtung': ('windDir',     '%.0f', 1.0), # degrees
                 'windstaerke':  ('windSpeed',   '%.1f', 0.2777777777), # m/s
                 'temperatur':   ('outTemp',     '%.1f', 1.0), # C
                 'feuchtigkeit': ('outHumidity', '%.0f', 1.0), # percent
                 'luftdruck':    ('barometer',   '%.3f', 1.0), # mbar?
                 'niederschlagsmenge': ('hourRain',    '%.2f', 10.0), # mm
                 }

    def __init__(self, queue, username, password, database_dict,
                 server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True, max_backlog=sys.maxint,
                 stale=None, max_tries=3, post_interval=None, timeout=60):
        super(WetterThread, self).__init__(queue,
                                           protocol_name='Wetter',
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
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if not txt.startswith('status=SUCCESS'):
            raise weewx.restx.FailedPost("Server returned '%s'" % txt)

    def get_data(self, record):
        # put everything into the right units
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)

        # put data into expected scaling, structure, and format
        values = {}
        values['benutzername'] = self.username
        values['passwort'] = self.password
        values['niederschlagsmenge_zeit'] = 60
        values['datum'] = time.strftime('%Y%m%d%H%M',
                                        time.localtime(record['dateTime']))
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                v = record[rkey] * self._DATA_MAP[key][2]
                values[key] = self._DATA_MAP[key][1] % v

        logdbg('data: %s' % values)
        return values
