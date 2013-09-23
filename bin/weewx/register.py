# $Id: register.py 1384 2013-09-23 17:08:37Z mwall $
# Copyright 2013 Matthew Wall
"""Periodically 'phone home' to register a weewx station.

  This will periodically do a http GET with the following information:

    station_url           should be world-accessible
    description           description of station
    latitude, longitude   must be in decimal format
    station_type          for example Vantage, FineOffsetUSB

  The station_url is the unique key by which a station is identified.

  To enable this module, add the following to weewx.conf:

[StdRESTful]
  ...
  [[StationRegistry]]
    #description = My Little Weather Station
    station_url = http://example.com/weather/
    driver = weewx.register.StationRegistry

"""

# FIXME: the REST base class has stuff we do not need (e.g. archive)

import httplib
import platform
import re
import socket
import sys
import syslog
import urllib
import urllib2
import time
import weewx.restful

WEEWX_SERVER_URL = 'http://weewx.com/register/register.cgi'

def logdbg(msg):
    syslog.syslog(syslog.LOG_DEBUG, 'register: %s' % msg)

def loginf(msg):
    syslog.syslog(syslog.LOG_INFO, 'register: %s' % msg)

def logcrt(msg):
    syslog.syslog(syslog.LOG_CRIT, 'register: %s' % msg)

def logerr(msg):
    syslog.syslog(syslog.LOG_ERR, 'register: %s' % msg)

class StationRegistry(weewx.restful.REST):
    """Class for phoning home to register a weewx station.

      station_url: URL of the weather station
      [Required]

      description: description of station location
      [Optional.  Default is None]

      latitude: station latitude
      [Optional.  Default is latitude from weewx.conf]

      longitude: station longitude
      [Optional.  Default is longitude from weewx.conf]

      hardware: station hardware
      [Optional.  Default is station_type from weewx.conf]

      server_url - site at which to register
      [Optional.  Default is weewx.com]

      interval: time in seconds between posts
      [Optional.  Default is 604800 (once per week)]

      max_tries: number of attempts to make before giving up
      [Optional.  Default is 5]
      """

    def __init__(self, site, **kwargs):
        self.server_url = kwargs.get('server_url', WEEWX_SERVER_URL)
        self.station_url = kwargs['station_url']

        # these are defined by RESTful
        self.latitude = float(kwargs['latitude'])
        self.longitude = float(kwargs['longitude'])
        self.hardware = kwargs['hardware']

        # these are optional
        self.interval = int(kwargs.get('interval', 604800))
        self.max_tries = int(kwargs.get('max_tries', 5))
        self.description = kwargs.get('description', None)
        if self.description is None:
            self.description = kwargs.get('location', None)

        self.weewx_info = weewx.__version__
        self.python_info = sys.version
        self.platform_info = platform.platform()
        self._last_ts = None

        # these two must be defined to keep RESTful happy
        self.site = 'StationRegistry'
        self.station = self.station_url

        # adapted from django URLValidator
        self._urlregex = re.compile(
            r'^(?:http)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
            r'localhost|' #localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        self._validateParameters()

        loginf('station will register with %s' % self.server_url)

    def postData(self, archive, time_ts):
        now = time.time()
        if self._last_ts is not None and now - self._last_ts < self.interval:
            msg = 'registration interval (%d) has not passed.' % self.interval
            logdbg(msg)
            raise weewx.restful.SkippedPost, msg

        url = self.getURL()
        for _count in range(self.max_tries):
            # Use HTTP GET to convey the station data
            try:
                logdbg("attempt to register using '%s'" % url)
                _response = urllib2.urlopen(url)
            except (urllib2.URLError, socket.error,
                    httplib.BadStatusLine, httplib.IncompleteRead), e:
                # Unsuccessful. Log it and try again
                logerr('failed attempt %d of %d: %e' %
                       (_count+1, self.max_tries, e))
            else:
                # Check for the server response
                for line in _response:
                    # Registration failed, log it and bail out
                    if line.startswith('FAIL'):
                        logerr("registration server returned %s" % line)
                        raise weewx.restful.FailedPost, line
                # Registration was successful
                logdbg('registration successful')
                self._last_ts = time.time()
                return
        else:
            # The upload failed max_tries times. Log it.
            msg = 'failed to register after %d tries' % self.max_tries
            logerr(msg)
            raise IOError, msg

    def getURL(self):
        args = {
            'station_url' : self.station_url,
            'latitude' : self.latitude,
            'longitude' : self.longitude,
            'station_type' : self.hardware,
            'weewx_info' : self.weewx_info,
            'python_info' : self.python_info,
            'platform_info' : self.platform_info,
            }
        if self.description is not None:
            args['description'] = self.description
        return '%s?%s' % (self.server_url, urllib.urlencode(args))

    def _checkURL(self, url):
        return self._urlregex.search(url)

    def _validateParameters(self):
        msgs = []
        # ensure the url does not have problem characters.  do not check
        # to see whether the site actually exists.
        if not self._checkURL(self.station_url):
            msgs.append("station_url '%s' is not a valid URL" % self.station_url)

        # check server url just in case someone modified the default
        url = self.server_url
        if not self._checkURL(url):
            msgs.append("server_url '%s' is not a valid URL" % self.server_url)

        if len(msgs) > 0:
            errmsg = 'One or more unusable parameters.'
            logerr(errmsg)
            for m in msgs:
                logerr('   **** %s' % m)
            raise ValueError(errmsg)
