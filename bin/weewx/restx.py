#
#    Copyright (c) 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
from __future__ import with_statement
import Queue
import datetime
import httplib
import socket
import syslog
import threading
import urllib
import urllib2

import weeutil.weeutil
import weewx.archive
import weewx.wxengine

class ServiceError(Exception):
    """Raised when not enough info is available to start a service."""
class FailedPost(IOError):
    """Raised when a post fails, usually because of a login problem"""
class SkippedPost(Exception):
    """Raised when a post is skipped."""
class BadLogin(StandardError):
    """Raised when login information is bad or missing."""
class TimeToExit(Exception):
    """Raised when it's time for a threaded queue to exit."""
        
#===============================================================================
#                    Class StdRESTbase
#===============================================================================

class StdRESTbase(weewx.wxengine.StdService):
    """Base class for RESTful weewx services."""

    def __init__(self, engine, config_dict):
        super(StdRESTbase, self).__init__(engine, config_dict)
        self.loop_queue = None
        self.archive_queue = None

    def init_loop_queue(self):
        self.loop_queue = Queue.Queue()

    def init_archive_queue(self):
        self.archive_queue = Queue.Queue()

    def assemble_data(self, record, archive):
        """Augment record data with additional data from the archive
        
        This is a general version that works for:
          - WeatherUnderground
          - PWSweather
          - CWOP
        It can be overridden and specialized for additional protocols.

        returns: A dictionary of weather values"""
        
        _time_ts = record['dateTime']
        
        _sod_ts = weeutil.weeutil.startOfDay(_time_ts)
        
        # Make a copy of the record, then start adding to it:
        _datadict = dict(record)
        
        if not _datadict.has_key('hourRain'):
            # CWOP says rain should be "rain that fell in the past hour".  WU says
            # it should be "the accumulated rainfall in the past 60 min".
            # Presumably, this is exclusive of the archive record 60 minutes before,
            # so the SQL statement is exclusive on the left, inclusive on the right.
            _datadict['hourRain'] = archive.getSql("SELECT SUM(rain) FROM archive WHERE dateTime>? AND dateTime<=?",
                                                   (_time_ts - 3600.0, _time_ts))[0]

        if not _datadict.has_key('rain24'):
            # Similar issue, except for last 24 hours:
            _datadict['rain24'] = archive.getSql("SELECT SUM(rain) FROM archive WHERE dateTime>? AND dateTime<=?",
                                                 (_time_ts - 24*3600.0, _time_ts))[0]

        if not _datadict.has_key('dayRain'):
            # NB: The WU considers the archive with time stamp 00:00 (midnight) as
            # (wrongly) belonging to the current day (instead of the previous
            # day). But, it's their site, so we'll do it their way.  That means the
            # SELECT statement is inclusive on both time ends:
            _datadict['dayRain'] = archive.getSql("SELECT SUM(rain) FROM archive WHERE dateTime>=? AND dateTime<=?", 
                                                  (_sod_ts, _time_ts))[0]

        # All these online weather sites require US units. 
        if _datadict['usUnits'] == weewx.US:
            # It's already in US units.
            return _datadict
        else:
            # It's in something else. Perform the conversion
            _datadict_us = weewx.units.StdUnitConverters[weewx.US].convertDict(_datadict)
            # Add the new unit system
            _datadict_us['usUnits'] = weewx.US
            return _datadict_us
                
#===============================================================================
#                    Class Ambient
#===============================================================================

class Ambient(StdRESTbase):
    """Base class for weather sites that use the Ambient protocol."""

    # Types and formats of the data to be published:
    _formats = {'dateTime'    : ('dateutc', '%s'),
                'barometer'   : ('baromin', '%.3f'),
                'outTemp'     : ('tempf', '%.1f'),
                'outHumidity' : ('humidity', '%03.0f'),
                'windSpeed'   : ('windspeedmph', '%03.0f'),
                'windDir'     : ('winddir', '%03.0f'),
                'windGust'    : ('windgustmph', '%03.0f'),
                'dewpoint'    : ('dewptf', '%.1f'),
                'hourRain'    : ('rainin', '%.2f'),
                'dayRain'     : ('dailyrainin', '%.2f'),
                'radiation'   : ('solarradiation', '%.2f'),
                'UV'          : ('UV', '%.2f')}

    def __init__(self, engine, ambient_dict):
        super(Ambient, self).__init__(engine, ambient_dict)

        try:
            self.station = ambient_dict['station']
            self.password = ambient_dict['password']

            do_rapidfire_post = weeutil.weeutil.tobool(ambient_dict.get('rapidfire', False))
            do_archive_post = weeutil.weeutil.tobool(ambient_dict.get('archive_post', not do_rapidfire_post))
            if do_rapidfire_post:
                self.rapidfire_url = ambient_dict['rapidfire_url']
                self.init_loop_queue()
                self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
                ambient_dict.setdefault('log_success', False)
                ambient_dict.setdefault('log_failure', False)
                ambient_dict.setdefault('max_tries',   1)
                ambient_dict.setdefault('max_backlog', 0)
                self.loop_thread = PostRequest(self.loop_queue,
                                               name="Wunderground-Rapidfire",
                                               **ambient_dict)
                self.loop_thread.start()
            if do_archive_post:
                self.archive_url = ambient_dict['archive_url']
                self.init_archive_queue()
                self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
                self.archive_thread = PostRequest(self.archive_queue,
                                                  name="Wunderground",
                                                  **ambient_dict)
                self.archive_thread.start()

            if do_rapidfire_post or do_archive_post:
                self.archive = weewx.archive.Archive.open(ambient_dict['archive_db_dict'])

        except KeyError, e:
            raise ServiceError("No keyword: %s" % (e,))

    def new_loop_packet(self, event):
        _record = self.assemble_data(event.packet, self.archive)
        _post_dict = self.extract_from(_record)
        # Add the rapidfire specific keywords:
        _post_dict['realtime'] = '1'
        _post_dict['rtfreq'] = '2.5'
        _url = self.rapidfire_url + '?' + weeutil.weeutil.urlencode(_post_dict)
        _request = urllib2.Request(_url)
        self.loop_queue.put((_record['dateTime'], _request))
        pass

    def new_archive_record(self, event):
        _record = self.assemble_data(event.record, self.archive)
        _post_dict = self.extract_from(_record)
        _url = self.archive_url + '?' + weeutil.weeutil.urlencode(_post_dict)
        _request = urllib2.Request(_url)
        self.loop_queue.put((_record['dateTime'], _request))
        pass

    def extract_from(self, record):
        """Given a record, format it using the Ambient protocol.
        
        Returns:
        A dictionary where the keys are the Ambient keywords, and the values
        are strings formatted according to the Ambient protocol."""
        
        if record['usUnits'] != weewx.US:
            raise weewx.ViolatedPrecondition("Unit system (%d) must be in US Customary" % record['usUnits'])

        _post_dict = {
                      'action'   : 'updateraw',
                      'ID'       : self.station,
                      'PASSWORD' : self.password,
                      'softwaretype' : "weewx-%s" % weewx.__version__
                      }        

        # Go through each of the supported types, formatting it, then adding to _post_dict:
        for _weewx_key in Ambient._formats:
            _v = record.get(_weewx_key)
            # Check to make sure the type is not null
            if _v is None:
                continue
            # This will be the key and format used by the Ambient protocol:
            _k, _f = Ambient._formats[_weewx_key]
            if _weewx_key == 'dateTime':
                # For dates, convert from time stamp to a string, using what
                # the Weather Underground calls "MySQL format." I've fiddled
                # with formatting, and it seems that escaping the colons helps
                # its reliability. But, I could be imagining things.
                _v = urllib.quote(datetime.datetime.utcfromtimestamp(_v).isoformat('+'), '-+')
            # Format the value, and accumulate in _post_dict:
            _post_dict[_k] = _f % _v

        return _post_dict

#===============================================================================
#                    Class Wunderground
#===============================================================================

class Wunderground(Ambient):
    """Specialized version of the Ambient protocol for the Weather Underground."""

    # The URLs used by the WU:
    rapidfire_url = "http://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"
    archive_url = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"

    def __init__(self, engine, config_dict):
        
        try:
            ambient_dict=dict(config_dict['StdRESTful']['Wunderground'])
            ambient_dict['archive_db_dict'] = config_dict['Databases'][config_dict['StdArchive']['archive_database']]
            ambient_dict.setdefault('rapidfire_url', Wunderground.rapidfire_url)
            ambient_dict.setdefault('archive_url',   Wunderground.archive_url)
            super(Wunderground, self).__init__(engine, ambient_dict)
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to Wunderground")
        except ServiceError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to Wunderground")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % e)

#===============================================================================
#                    Class PostRequest
#===============================================================================

class PostRequest(threading.Thread):
    """Post an urllib2 "Request" object, using a separate thread."""
    
    
    def __init__(self, queue, **kwargs):
        name  = kwargs.get('name', 'Unknown')
        threading.Thread.__init__(self, name=name)

        self.queue = queue
        self.log_success = weeutil.weeutil.tobool(kwargs.get('log_success', True))
        self.log_failure = weeutil.weeutil.tobool(kwargs.get('log_failure', True))
        self.max_tries = int(kwargs.get('max_tries', 3))
        self.max_backlog = kwargs.get('max_backlog')
        if self.max_backlog is not None:
            self.max_backlog = int(self.max_backlog)

        self.setDaemon(True)
        
    def run(self):

        while True:

            while True:
                # This will block until a request shows up.
                _request_tuple = self.queue.get()
                # If a "None" value appears in the pipe, it's our signal to exit:
                if _request_tuple is None:
                    return
                # If packets have backed up in the queue, trim it until it's no bigger
                # than the max allowed backlog:
                if self.max_backlog is None or self.queue.qsize() <= self.max_backlog:
                    break

            # Unpack the timestamp and Request object
            _timestamp, _request = _request_tuple

            try:
                # Now post it
                self.post_request(_request)
            except FailedPost:
                if self.log_failure:
                    syslog.syslog(syslog.LOG_ERR, "restx: Failed to upload to '%s'" % self.name)
            except BadLogin, e:
                syslog.syslog(syslog.LOG_CRIT, "restx: Failed to post to '%s'" % self.name)
                syslog.syslog(syslog.LOG_CRIT, " ****  Reason: %s" % e)
                syslog.syslog(syslog.LOG_CRIT, " ****  Terminating %s thread" % self.name)
                return
            else:
                if self.log_success:
                    _time_str = weeutil.weeutil.timestamp_to_string(_timestamp)
                    syslog.syslog(syslog.LOG_INFO, "restx: Published record %s to %s" % (_time_str, self.name))

    def post_request(self, request):
        """Post a request.
        
        request: An instance of urllib2.Request
        """

        # Retry up to max_tries times:
        for _count in range(self.max_tries):
            # Now use urllib2 to post the data. Wrap in a try block
            # in case there's a network problem.
            try:
                _response = urllib2.urlopen(request)
            except (urllib2.URLError, socket.error, httplib.BadStatusLine), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.name))
                syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
            else:
                # No exception thrown, but we're still not done.
                # We have to also check for a bad station ID or password.
                # It will have the error encoded in the return message:
                for line in _response:
                    # PWSweather signals with 'ERROR', WU with 'INVALID':
                    if line.startswith('ERROR') or line.startswith('INVALID'):
                        # Bad login. No reason to retry. Raise an exception.
                        raise BadLogin, line
                # Does not seem to be an error. We're done.
                return
        else:
            # This is executed only if the loop terminates normally, meaning
            # the upload failed max_tries times. Log it.
            raise FailedPost("Failed upload to site %s after %d tries" % (self.name, self.max_tries))
