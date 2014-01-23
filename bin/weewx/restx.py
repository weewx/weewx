#
#    Copyright (c) 2013-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Publish weather data to RESTful sites such as the Weather Underground or PWSWeather."""
from __future__ import with_statement
import Queue
import datetime
import hashlib
import httplib
import platform
import re
import socket
import sys
import syslog
import threading
import time
import urllib
import urllib2

import weeutil.weeutil
import weewx.wxengine
from weeutil.weeutil import to_int, to_bool, timestamp_to_string
import weewx.units

class FailedPost(IOError):
    """Raised when a post fails after trying the max number of allowed times"""

class BadLogin(StandardError):
    """Raised when login information is bad or missing."""
        
#==============================================================================
#                    Abstract base classes
#==============================================================================

class StdRESTbase(weewx.wxengine.StdService):
    """Abstract base class for RESTful weewx services.
    
    Offers a few common bits of functionality."""
        
    def shutDown(self):
        """Shut down any threads"""
        if hasattr(self, 'loop_queue') and hasattr(self, 'loop_thread'):
            StdRESTbase.shutDown_thread(self.loop_queue, self.loop_thread)
        if hasattr(self, 'archive_queue') and hasattr(self, 'archive_thread'):
            StdRESTbase.shutDown_thread(self.archive_queue, self.archive_thread)

    @staticmethod
    def shutDown_thread(q, t):
        """Function to shut down a thread."""
        if q and t.isAlive():
            # Put a None in the queue to signal the thread to shutdown
            q.put(None)
            # Wait up to 20 seconds for the thread to exit:
            t.join(20.0)
            if t.isAlive():
                syslog.syslog(syslog.LOG_ERR, "restx: Unable to shut down %s thread" % t.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "restx: Shut down %s thread." % t.name)

class RESTThread(threading.Thread):
    """Abstract base class for RESTful protocol threads.
    
    Offers a few bits of common functionality."""

    def __init__(self, queue, restful_site, max_tries, stale, post_interval):
        threading.Thread.__init__(self, name=restful_site)
        self.queue = queue
        self.restful_site = restful_site
        self.max_tries = max_tries
        self.stale = stale
        self.post_interval = post_interval
        
        self.lastpost = 0
            
    def get_record(self, record, archive):
        """Augment record data with additional data from the archive.
        Returns results in the same units as the record and the database.
        
        This is a general version that works for:
          - WeatherUnderground
          - PWSweather
          - WOW
          - CWOP
        It can be overridden and specialized for additional protocols.

        returns: A dictionary of weather values"""
        
        _time_ts = record['dateTime']
        _sod_ts = weeutil.weeutil.startOfDay(_time_ts)
        
        # Make a copy of the record, then start adding to it:
        _datadict = dict(record)
        
        if not _datadict.has_key('hourRain'):
            # CWOP says rain should be "rain that fell in the past hour". WU
            # says it should be "the accumulated rainfall in the past 60 min".
            # Presumably, this is exclusive of the archive record 60 minutes
            # before, so the SQL statement is exclusive on the left, inclusive
            # on the right.
            _result = archive.getSql("SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM archive WHERE dateTime>? AND dateTime<=?",
                                                   (_time_ts - 3600.0, _time_ts))
            if not _result[1] == _result[2] == record['usUnits']:
                raise ValueError("Inconsistent units or units change in database %d vs %d vs %d" % (_result[1], _result[2], record['usUnits']))
            _datadict['hourRain'] = _result[0]

        if not _datadict.has_key('rain24'):
            # Similar issue, except for last 24 hours:
            _result = archive.getSql("SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM archive WHERE dateTime>? AND dateTime<=?",
                                                 (_time_ts - 24*3600.0, _time_ts))
            if not _result[1] == _result[2] == record['usUnits']:
                raise ValueError("Inconsistent units or units change in database %d vs %d vs %d" % (_result[1], _result[2], record['usUnits']))
            _datadict['rain24'] = _result[0]

        if not _datadict.has_key('dayRain'):
            # NB: The WU considers the archive with time stamp 00:00
            # (midnight) as (wrongly) belonging to the current day
            # (instead of the previous day). But, it's their site,
            # so we'll do it their way.  That means the SELECT statement
            # is inclusive on both time ends:
            _result = archive.getSql("SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM archive WHERE dateTime>=? AND dateTime<=?", 
                                                  (_sod_ts, _time_ts))
            if not _result[1] == _result[2] == record['usUnits']:
                raise ValueError("Inconsistent units or units change in database %d vs %d vs %d" % (_result[1], _result[2], record['usUnits']))
            _datadict['dayRain'] = _result[0]
            
        return _datadict

    def run(self):
        """General run() version. It depends on a specializing method "process_record" to
        post a record in accordance with the actual protocol."""
        
        # Open up the archive. Use a 'with' statement. This will automatically close the
        # archive in the case of an exception:
        with weewx.archive.Archive.open(self.database_dict) as _archive:
            self.run_loop(_archive)

    def run_loop(self, archive=None):
            while True :
                while True:
                    # This will block until something appears in the queue:
                    _record = self.queue.get()
                    # A None record is our signal to exit:
                    if _record is None:
                        return
                    # If packets have backed up in the queue, trim it until it's no bigger
                    # than the max allowed backlog:
                    if self.queue.qsize() <= self.max_backlog:
                        break

                if self.skip_this_post(_record['dateTime']):
                    continue

                try:
                    # Process the record, using whatever method the specializing class provides
                    self.process_record(_record, archive)
                except BadLogin, e:
                    syslog.syslog(syslog.LOG_ERR, "restx: Bad login for %s; waiting 60 minutes then retrying" % self.restful_site)
                    time.sleep(3600)
                except FailedPost, e:
                    if self.log_failure:
                        _time_str = timestamp_to_string(_record['dateTime'])
                        syslog.syslog(syslog.LOG_ERR, "restx: Failed to publish record %s to %s" % (_time_str, self.restful_site))
                        syslog.syslog(syslog.LOG_ERR, "****   Reason: %s" % e)
                except Exception, e:
                    syslog.syslog(syslog.LOG_CRIT, "restx: Thread for %s exiting" % self.restful_site)
                    syslog.syslog(syslog.LOG_CRIT, "****   Reason: %s" % e)
                    return
                else:
                    if self.log_success:
                        _time_str = timestamp_to_string(_record['dateTime'])
                        syslog.syslog(syslog.LOG_INFO, "restx: Published record %s to %s" % (_time_str, self.restful_site))

    def post_request(self, request):
        """Post a request, using an HTTP GET
        
        request: An instance of urllib2.Request
        """

        # Retry up to max_tries times:
        for _count in range(self.max_tries):
            # Now use urllib2 to post the data. Wrap in a try block
            # in case there's a network problem.
            try:
                _response = urllib2.urlopen(request)
            except urllib2.HTTPError, e:
                # WOW signals a bad login with a HTML Error 403 code:
                if e.code == 403:
                    raise BadLogin(e)
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.restful_site))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
            except (urllib2.URLError, socket.error, httplib.BadStatusLine, httplib.IncompleteRead), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.restful_site))
                syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
            else:
                if _response.code != 200:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.restful_site))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Response code: %d" % (_response.code,))
                else:
                    # No exception thrown and we got a good response code, but we're still not done.
                    # We have to also check for a bad station ID or password.
                    # It will have the error encoded in the return message:
                    for line in _response:
                        # PWSweather signals with 'ERROR', WU with 'INVALID':
                        if line.startswith('ERROR') or line.startswith('INVALID'):
                            # Bad login. No reason to retry. Raise an exception.
                            raise BadLogin(line)
                        # Station registry indicates something is malformed by signalling "FAIL"
                        elif line.startswith('FAIL'):
                            raise FailedPost(line)
                    # Does not seem to be an error. We're done.
                    return
        else:
            # This is executed only if the loop terminates normally, meaning
            # the upload failed max_tries times. Log it.
            raise FailedPost("Failed upload to site %s after %d tries" % (self.restful_site, self.max_tries))

    def skip_this_post(self, time_ts):
        """Check whether the post is current"""
        # Don't post if this record is too old
        if self.stale:
            _how_old = time.time() - time_ts
            if _how_old > self.stale:
                syslog.syslog(syslog.LOG_DEBUG, "restx: %s record %s is stale (%d > %d)." % \
                        (self.restful_site, timestamp_to_string(time_ts), _how_old, self.stale))
                return True
 
        # We don't want to post more often than the post interval
        _how_long = time_ts - self.lastpost
        if _how_long < self.post_interval:
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s record %s wait interval (%d < %d) has not passed." % \
                    (self.restful_site, timestamp_to_string(time_ts), _how_long, self.post_interval))
            return True
    
        self.lastpost = time_ts
        return False

#==============================================================================
#                    Ambient protocols
#==============================================================================

class StdWunderground(StdRESTbase):
    """Specialized version of the Ambient protocol for the Weather Underground."""
    
    # The URLs used by the WU:
    rapidfire_url = "http://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"
    archive_url   = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"

    def __init__(self, engine, config_dict):
        
        super(StdWunderground, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            _ambient_dict=dict(config_dict['StdRESTful']['Wunderground'])
            _station = _ambient_dict['station']
            _password = _ambient_dict['password']
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to Wunderground")
            syslog.syslog(syslog.LOG_DEBUG, "****   Reason: missing option %s" % e)
            return

        _database_dict= config_dict['Databases'][config_dict['StdArchive']['archive_database']]
        
        # The default is to not do an archive post if a rapidfire post
        # has been specified, but this can be overridden
        do_rapidfire_post = to_bool(_ambient_dict.get('rapidfire', False))
        do_archive_post   = to_bool(_ambient_dict.get('archive_post', not do_rapidfire_post))
        
        if do_archive_post:
            _server_url    = _ambient_dict.get('server_url', StdWunderground.archive_url)
            _log_success   = to_bool(_ambient_dict.get('log_success', True))
            _log_failure   = to_bool(_ambient_dict.get('log_failure', True))
            _max_backlog   = int(_ambient_dict.get('max_backlog', sys.maxint))
            _max_tries     = int(_ambient_dict.get('max_tries', 3))
            _stale         = int(_ambient_dict.get('stale', 0))
            _post_interval = int(_ambient_dict.get('interval', 0))
            self.archive_queue = Queue.Queue()
            self.archive_thread = AmbientThread(self.archive_queue, _station, _password, _database_dict, 
                                                _server_url, 
                                                _log_success, _log_failure, _max_backlog,
                                                "Wunderground - PWS", _max_tries, _stale, _post_interval)
            self.archive_thread.start()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            syslog.syslog(syslog.LOG_INFO, "restx: Data will be posted to WUnderground-PWS station %s" % _station)

        if do_rapidfire_post:
            _server_url    = _ambient_dict.get('server_url', StdWunderground.rapidfire_url)
            _log_success   = to_bool(_ambient_dict.get('log_success', False))
            _log_failure   = to_bool(_ambient_dict.get('log_failure', False))
            _max_backlog   = int(_ambient_dict.get('max_backlog', sys.maxint))
            _max_tries     = int(_ambient_dict.get('max_tries', 1))
            _stale         = int(_ambient_dict.get('stale', 0))
            _post_interval = int(_ambient_dict.get('interval', 0))
            self.loop_queue = Queue.Queue()
            self.loop_thread = AmbientLoopThread(self.archive_queue, _station, _password, _database_dict, 
                                                _server_url, 
                                                _log_success, _log_failure, _max_backlog,
                                                "Wunderground - Rapidfire", _max_tries, _stale, _post_interval)
            self.loop_thread.start()
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            syslog.syslog(syslog.LOG_INFO, "restx: Data will be posted to WUnderground-Rapidfire station %s" % _station)

    def new_loop_packet(self, event):
        self.loop_queue.put(event.packet)

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)
                
class StdPWSWeather(StdRESTbase):
    """Specialized version of the Ambient protocol for PWS"""
    
    # The URL used by PWS:
    archive_url = "http://www.pwsweather.com/pwsupdate/pwsupdate.php"

    def __init__(self, engine, config_dict):
        
        super(StdPWSWeather, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            _ambient_dict=dict(config_dict['StdRESTful']['PWSweather'])
            _station = _ambient_dict['station']
            _password = _ambient_dict['password']
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to PWSWeather")
            syslog.syslog(syslog.LOG_DEBUG, "****   Reason: missing option %s" % e)
            return

        _database_dict= config_dict['Databases'][config_dict['StdArchive']['archive_database']]
        
        _server_url    = _ambient_dict.get('server_url', StdPWSWeather.archive_url)
        _log_success   = to_bool(_ambient_dict.get('log_success', True))
        _log_failure   = to_bool(_ambient_dict.get('log_failure', True))
        _max_backlog   = int(_ambient_dict.get('max_backlog', sys.maxint))
        _max_tries     = int(_ambient_dict.get('max_tries', 3))
        _stale         = int(_ambient_dict.get('stale', 0))
        _post_interval = int(_ambient_dict.get('interval', 0))
        self.archive_queue = Queue.Queue()
        self.archive_thread = AmbientThread(self.archive_queue, _station, _password, _database_dict, 
                                            _server_url, 
                                            _log_success, _log_failure, _max_backlog,
                                            "PWSWeather", _max_tries, _stale, _post_interval)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: Data will be posted to PWSWeather station %s" % _station)

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class StdWOW(StdRESTbase):

    """Upload using the UK Met Office's WOW protocol. 
    
    For details of the WOW upload protocol, see 
    http://wow.metoffice.gov.uk/support/dataformats#dataFileUpload
    """

    # The URL used by WOW:
    archive_url = "http://wow.metoffice.gov.uk/automaticreading"

    def __init__(self, engine, config_dict):
        
        super(StdWOW, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            _ambient_dict=dict(config_dict['StdRESTful']['WOW'])
            _station = _ambient_dict['station']
            _password = _ambient_dict['password']
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to WOW")
            syslog.syslog(syslog.LOG_DEBUG, "****   Reason: missing option %s" % e)
            return

        _database_dict= config_dict['Databases'][config_dict['StdArchive']['archive_database']]
        
        _server_url    = _ambient_dict.get('server_url', StdWOW.archive_url)
        _log_success   = to_bool(_ambient_dict.get('log_success', True))
        _log_failure   = to_bool(_ambient_dict.get('log_failure', True))
        _max_backlog   = int(_ambient_dict.get('max_backlog', sys.maxint))
        _max_tries     = int(_ambient_dict.get('max_tries', 3))
        _stale         = int(_ambient_dict.get('stale', 0))
        _post_interval = int(_ambient_dict.get('interval', 0))
        self.archive_queue = Queue.Queue()
        self.archive_thread = WOWThread(self.archive_queue, _station, _password, _database_dict, 
                                            _server_url, 
                                            _log_success, _log_failure, _max_backlog,
                                            "WOW", _max_tries, _stale, _post_interval)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: Data will be posted to WOW station %s" % _station)
        
    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class AmbientThread(RESTThread):
    """Concrete class for threads posting from the archive queue,
    using the Ambient PWS protocol."""
    
    def __init__(self, queue, station, password, database_dict, 
                 server_url,
                 log_success=True, log_failure=True, max_backlog=0,
                 restful_site='', max_tries=3, stale=None, post_interval=0):

        super(AmbientThread, self).__init__(queue, restful_site, max_tries, stale, post_interval)
        
        self.station       = station
        self.password      = password
        self.database_dict = database_dict
        self.server_url    = server_url
        self.log_success   = log_success
        self.log_failure   = log_failure
        self.max_backlog   = max_backlog

    def process_record(self, record, archive):
        # Get the full record by querying the database ...
        _full_record = self.get_record(record, archive)
        # ... convert to US if necessary ...
        _us_record = to_US(_full_record)
        # ... format the URL, using the Ambient protocol ...
        _url = self.format_url(_us_record)
        # ... convert to a Request object ...
        _request = urllib2.Request(_url)
        # ... then, finally, post it
        self.post_request(_request)

    # Types and formats of the data to be published:
    _formats = {'dateTime'    : 'dateutc=%s',
                'barometer'   : 'baromin=%.3f',
                'outTemp'     : 'tempf=%.1f',
                'outHumidity' : 'humidity=%03.0f',
                'windSpeed'   : 'windspeedmph=%03.0f',
                'windDir'     : 'winddir=%03.0f',
                'windGust'    : 'windgustmph=%03.0f',
                'dewpoint'    : 'dewptf=%.1f',
                'hourRain'    : 'rainin=%.2f',
                'dayRain'     : 'dailyrainin=%.2f',
                'radiation'   : 'solarradiation=%.2f',
                'UV'          : 'UV=%.2f'}
    
    def format_url(self, record):
        """Return an URL for posting using the Ambient protocol."""
    
        _liststr = ["action=updateraw", 
                    "ID=%s" % self.station,
                    "PASSWORD=%s" % self.password,
                    "softwaretype=weewx-%s" % weewx.__version__]
        
        # Go through each of the supported types, formatting it, then adding to _liststr:
        for _key in AmbientThread._formats:
            v = record[_key]
            # Check to make sure the type is not null
            if v is not None :
                if _key == 'dateTime':
                    # For dates, convert from time stamp to a string, using what
                    # the Weather Underground calls "MySQL format." I've fiddled
                    # with formatting, and it seems that escaping the colons helps
                    # its reliability. But, I could be imagining things.
                    v = urllib.quote(datetime.datetime.utcfromtimestamp(v).isoformat('+'), '-+')
                # Format the value, and accumulate in _liststr:
                _liststr.append(AmbientThread._formats[_key] % v)
        # Now stick all the little pieces together with an ampersand between them:
        _urlquery = '&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url = "%s?%s" % (self.server_url, _urlquery)
        return _url
                
class AmbientLoopThread(AmbientThread):
    """Version used for the LOOP thread, that is for the Rapidfire protocol."""

    def get_record(self, record, archive):
        """Prepare a record for the Rapidfire protocol."""

        # Call the regular Ambient PWS version
        _record = AmbientThread.get_record(self, record, archive)
        # Add the Rapidfire-specific keywords:
        _record['realtime'] = '1'
        _record['rtfreq'] = '2.5'

        return _record

class WOWThread(AmbientThread):
    """Class for posting to the WOW variant of the Ambient protocol."""
    
    # Types and formats of the data to be published:
    _formats = {'dateTime'    : 'dateutc=%s',
                'barometer'   : 'baromin=%.1f',
                'outTemp'     : 'tempf=%.1f',
                'outHumidity' : 'humidity=%.0f',
                'windSpeed'   : 'windspeedmph=%.0f',
                'windDir'     : 'winddir=%.0f',
                'windGust'    : 'windgustmph=%.0f',
                'windGustDir' : 'windgustdir=%.0f',
                'dewpoint'    : 'dewptf=%.1f',
                'hourRain'    : 'rainin=%.2f',
                'dayRain'     : 'dailyrainin=%.2f'}
    
    def format_url(self, record):
        """Return an URL for posting using WOW's version of the Ambient protocol."""

        _liststr = ["action=updateraw",
                    "siteid=%s" % self.station,
                    "siteAuthenticationKey=%s" % self.password,
                    "softwaretype=weewx-%s" % weewx.__version__]

        # Go through each of the supported types, formatting it, then adding to _liststr:
        for _key in WOWThread._formats:
            v = record[_key]
            # Check to make sure the type is not null
            if v is not None :
                if _key == 'dateTime':
                    v = urllib.quote_plus(datetime.datetime.utcfromtimestamp(v).isoformat(' '))
                # Format the value, and accumulate in _liststr:
                _liststr.append(WOWThread._formats[_key] % v)
        # Now stick all the little pieces together with an ampersand between them:
        _urlquery = '&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url = "%s?%s" % (self.server_url, _urlquery)
        return _url

#==============================================================================
#                    CWOP
#==============================================================================

class StdCWOP(StdRESTbase):
    """Weewx service for posting using the CWOP protocol.
    
    Manages a separate thread CWOPThread"""
    # Station IDs must start with one of these:
    valid_prefixes = ['CW', 'DW', 'EW']
    default_servers = ['cwop.aprs.net:14580', 'cwop.aprs.net:23']

    def __init__(self, engine, config_dict):
        
        super(StdCWOP, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            _cwop_dict=dict(config_dict['StdRESTful']['CWOP'])
            # Extract the station ID and (if necessary) passcode
            _station = _cwop_dict['station'].upper()
            if _station[0:2] in StdCWOP.valid_prefixes:
                _passcode = "-1"
            else:
                _passcode = _cwop_dict['passcode']
            _station_type  = _cwop_dict.get('station_type', config_dict['Station']['station_type'])
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to CWOP")
            syslog.syslog(syslog.LOG_DEBUG, "****   Reason: missing option %s" % e)
            return

        _database_dict= config_dict['Databases'][config_dict['StdArchive']['archive_database']]
        
        if _cwop_dict.has_key('server'):
            _server_list = weeutil.weeutil.option_as_list(_cwop_dict['server'])
        else:
            _server_list = StdCWOP.default_servers
        _latitude      = float(_cwop_dict.get('latitude',  self.engine.stn_info.latitude_f))
        _longitude     = float(_cwop_dict.get('longitude', self.engine.stn_info.longitude_f))
        _log_success   = to_bool(_cwop_dict.get('log_success', True))
        _log_failure   = to_bool(_cwop_dict.get('log_failure', True))
        _max_backlog   = int(_cwop_dict.get('max_backlog', sys.maxint))
        _max_tries     = int(_cwop_dict.get('max_tries', 3))
        _stale         = int(_cwop_dict.get('stale', 1800))
        _post_interval = int(_cwop_dict.get('interval', 600))
        self.archive_queue = Queue.Queue()
        self.archive_thread = CWOPThread(self.archive_queue, _station, _passcode, _database_dict,
                                         _server_list, _latitude, _longitude, _station_type,
                                         _log_success, _log_failure, _max_backlog,
                                         'CWOP', _max_tries, _stale, _post_interval)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: Data will be posted to CWOP station %s" % _station)

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class CWOPThread(RESTThread):
    """Concrete class for threads posting from the archive queue,
    using the CWOP protocol."""

    def __init__(self, queue, station, password, database_dict,
                 server_list, latitude, longitude, _station_type,
                 log_success=True, log_failure=True, max_backlog=0,
                 restful_site='', max_tries=3, stale=None, post_interval=0):

        # Initialize my superclass
        super(CWOPThread, self).__init__(queue, restful_site, max_tries, stale, post_interval)

        self.station       = station
        self.password      = password
        self.database_dict = database_dict
        self.server_list   = server_list
        self.latitude      = latitude
        self.longitude     = longitude
        self.station_type  = _station_type
        self.log_success   = log_success
        self.log_failure   = log_failure
        self.max_backlog   = max_backlog

    def process_record(self, record, archive):
        """Process a record in accordance with the CWOP protocol."""
        
        # Get the full record by querying the database ...
        _full_record = self.get_record(record, archive)
        # ... convert to US if necessary ...
        _us_record = to_US(_full_record)

        # Get the login and packet strings:
        _login = self.get_login_string()
        _tnc_packet = self.get_tnc_packet(record)

        # Then post them:
        self.send_packet(_login, _tnc_packet)

    def get_login_string(self):
        _login = "user %s pass %s vers weewx %s\r\n" % (self.station, self.password, weewx.__version__)
        return _login

    def get_tnc_packet(self, record):
        """Form the TNC2 packet used by CWOP."""

        # Preamble to the TNC packet:
        _prefix = "%s>APRS,TCPIP*:" % (self.station,)

        # Time:
        _time_tt = time.gmtime(record['dateTime'])
        _time_str = time.strftime("@%d%H%Mz", _time_tt)

        # Position:
        _lat_str = weeutil.weeutil.latlon_string(self.latitude, ('N', 'S'), 'lat')
        _lon_str = weeutil.weeutil.latlon_string(self.longitude, ('E', 'W'), 'lon')
        _latlon_str = '%s%s%s/%s%s%s' % (_lat_str + _lon_str)

        # Wind and temperature
        _wt_list = []
        for _obs_type in ['windDir', 'windSpeed', 'windGust', 'outTemp']:
            _v = record.get(_obs_type)
            _wt_list.append("%03d" % _v if _v is not None else '...')
        _wt_str = "_%s/%sg%st%s" % tuple(_wt_list)

        # Rain
        _rain_list = []
        for _obs_type in ['hourRain', 'rain24', 'dayRain']:
            _v = record.get(_obs_type)
            _rain_list.append("%03d" % (_v * 100.0) if _v is not None else '...')
        _rain_str = "r%sp%sP%s" % tuple(_rain_list)

        # Barometer:
        _baro = record.get('altimeter')
        if _baro is None:
            _baro_str = "b....."
        else:
            # While everything else in the CWOP protocol is in US Customary, they
            # want the barometer in millibars.
            _baro_vt = weewx.units.convert((_baro, 'inHg', 'group_pressure'), 'mbar')
            _baro_str = "b%05d" % (_baro_vt[0] * 10.0)

        # Humidity:
        _humidity = record.get('outHumidity')
        if _humidity is None:
            _humid_str = "h.."
        else:
            _humid_str = ("h%02d" % _humidity) if _humidity < 100.0 else "h00"

        # Radiation:
        _radiation = record.get('radiation')
        if _radiation is None:
            _radiation_str = ""
        elif _radiation < 1000.0:
            _radiation_str = "L%03d" % _radiation
        elif _radiation < 2000.0:
            _radiation_str = "l%03d" % (_radiation - 1000)
        else:
            _radiation_str = ""

        # Station equipment
        _equipment_str = ".weewx-%s-%s" % (weewx.__version__, self.station_type)
        
        _tnc_packet = ''.join([_prefix, _time_str, _latlon_str, _wt_str, _rain_str,
                               _baro_str, _humid_str, _radiation_str, _equipment_str, "\r\n"])

        return _tnc_packet

    def send_packet(self, login, tnc_packet):
        
        # Get a socket connection:
        _sock = self._get_connect()

        try:
            # Send the login ...
            self._send(_sock, login)
            # ... and then the packet
            self._send(_sock, tnc_packet)
            
        finally:
            _sock.close()

    def _get_connect(self):

        # Go through the list of known server:ports, looking for
        # a connection that works:
        for _serv_addr_str in self.server_list:
            _server, _port_str = _serv_addr_str.split(":")
            _port = int(_port_str)
            for _count in range(self.max_tries):
                try:
                    _sock = socket.socket()
                    _sock.connect((_server, _port))
                except socket.error, e:
                    # Unsuccessful. Log it and try again
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connection attempt #%d failed to %s server %s:%d" % (_count + 1, self.restful_site, _server, _port))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connected to %s server %s:%d" % (self.restful_site, _server, _port))
                    return _sock
                # Couldn't connect on this attempt. Close it, try again.
                try:
                    _sock.close()
                except:
                    pass
            # If we got here, that server didn't work. Log it and go on to the next one.
            syslog.syslog(syslog.LOG_DEBUG, "restx: Unable to connect to %s server %s:%d" % (self.restful_site, _server, _port))

        # If we got here. None of the servers worked. Raise an exception
        raise FailedPost, "Unable to obtain a socket connection to %s" % (self.restful_site,)

    def _send(self, sock, msg):

        for _count in range(self.max_tries):

            try:
                sock.send(msg)
            except (IOError, socket.error), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_DEBUG, "restx: Attempt #%d failed to send to %s" % (_count + 1, self.restful_site))
                syslog.syslog(syslog.LOG_DEBUG, "  ***  Reason: %s" % (e,))
            else:
                _resp = sock.recv(1024)
                return _resp
        else:
            # This is executed only if the loop terminates normally, meaning
            # the send failed max_tries times. Log it.
            raise FailedPost, "Failed upload to site %s after %d tries" % (self.restful_site, self.max_tries)

#==============================================================================
#                    Station Registry
#==============================================================================

class StdStationRegistry(StdRESTbase):
    """Class for phoning home to register a weewx station.

    This will periodically do a http GET with the following information:

        station_url      Should be world-accessible. Used as key.
        description      Brief synopsis of the station
        latitude         Station latitude in decimal
        longitude        Station longitude in decimal
        station_type     Generally, the driver type. For example Vantage, FineOffsetUSB
        station_model    hardware_name property from the driver
        weewx_info       weewx version
        python_info
        platform_info

    The station_url is the unique key by which a station is identified.

    To enable this module, add the following to weewx.conf:

 [StdRESTful]
     ...
     [[StationRegistry]]
         register_this_station = True
    """

    archive_url = 'http://weewx.com/register/register.cgi'

    def __init__(self, engine, config_dict):
        
        super(StdStationRegistry, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            _registry_dict = dict(config_dict['StdRESTful']['StationRegistry'])
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to PWSWeather")
            syslog.syslog(syslog.LOG_DEBUG, "****   Reason: missing option %s" % e)
            return

        # Should the service be run?
        if not to_bool(_registry_dict.get('register_this_station', False)):
            syslog.syslog(syslog.LOG_INFO, "restx: Station registry not requested.")
            return

        _station_url   = _registry_dict.get('station_url',  self.engine.stn_info.station_url)
        _description   = _registry_dict.get('description', self.engine.stn_info.location)
        _latitude      = float(_registry_dict.get('latitude',  self.engine.stn_info.latitude_f))
        _longitude     = float(_registry_dict.get('longitude', self.engine.stn_info.longitude_f))
        _station_type  = _registry_dict.get('station_type', config_dict['Station']['station_type'])
        _station_model = _registry_dict.get('station_model', self.engine.stn_info.hardware)

        _server_url    = _registry_dict.get('server_url', StdStationRegistry.archive_url)
        _log_success   = to_bool(_registry_dict.get('log_success', True))
        _log_failure   = to_bool(_registry_dict.get('log_failure', True))
        _max_backlog   = int(_registry_dict.get('max_backlog', 0))
        _max_tries     = int(_registry_dict.get('max_tries', 3))
        _stale         = int(_registry_dict.get('stale', 0))
        _post_interval = int(_registry_dict.get('interval', 604800))
        self.archive_queue = Queue.Queue()
        self.archive_thread = StationRegistryThread(self.archive_queue,
                                                    _station_url, _description, _latitude, _longitude,
                                                    _station_type, _station_model,
                                                    _server_url,
                                                    _log_success, _log_failure, _max_backlog,
                                                    "StationRegistry", _max_tries, _stale, _post_interval)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: Station will be registered.")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)
        
class StationRegistryThread(RESTThread):
    
    def __init__(self, queue,
                 station_url, description, latitude, longitude,
                 station_type, station_model,
                 server_url,
                 log_success=True, log_failure=True, max_backlog=0,
                 restful_site='', max_tries=3, stale=None, post_interval=0):

        super(StationRegistryThread, self).__init__(queue, restful_site, max_tries, stale, post_interval)

        self.station_url   = station_url
        self.description   = description
        self.latitude      = latitude
        self.longitude     = longitude
        self.station_type  = station_type
        self.station_model = station_model
        self.server_url    = server_url
        self.log_success   = log_success
        self.log_failure   = log_failure
        self.max_backlog   = max_backlog
        
    def run(self):
        
        self.run_loop()
        
    def process_record(self, record, archive):
        # Get the full record by querying the database ...
        _full_record = self.get_record(record, archive)
        # ... format the URL ...
        _url = self.format_url(_full_record)
        # ... convert to a Request object ...
        _request = urllib2.Request(_url)
        # ... then, finally, post it
        self.post_request(_request)

    def get_record(self, dummy_record, dummy_archive):
        _record = {}
        _record['station_url']   = self.station_url
        _record['description']   = self.description
        _record['latitude']      = self.latitude
        _record['longitude']     = self.longitude
        _record['station_type']  = self.station_type
        _record['station_model'] = self.station_model
        _record['python_info']   = platform.python_version()
        _record['platform_info'] = platform.platform()
        _record['weewx_info']    = weewx.__version__
        
        return _record
        
    _formats = {'station_url'   : 'station_url=%s',
                'description'   : 'description=%s',
                'latitude'      : 'latitude=%.4f',
                'longitude'     : 'longitude=%.4f',
                'station_type'  : 'station_type=%s',
                'station_model' : 'station_model=%s',
                'python_info'   : 'python_info=%s',
                'platform_info' : 'platform_info=%s',
                'weewx_info'    : 'weewx_info=%s'}

    def format_url(self, record):
        """Return an URL for posting using the StationRegistry protocol."""
    
        _liststr = []
        for _key in StationRegistryThread._formats:
            v = record[_key]
            if v is not None:
                _liststr.append(urllib.quote_plus(StationRegistryThread._formats[_key] % v, '='))
        _urlquery = '&'.join(_liststr)
        _url = "%s?%s" % (self.server_url, _urlquery)
        return _url
    
#==============================================================================
#                    Utility functions
#==============================================================================

def to_US(datadict):
    """Convert units to US Customary."""
    if datadict['usUnits'] == weewx.US:
        # It's already in US units.
        return datadict
    else:
        # It's in something else. Perform the conversion
        _datadict_us = weewx.units.StdUnitConverters[weewx.US].convertDict(datadict)
        # Add the new unit system
        _datadict_us['usUnits'] = weewx.US
        return _datadict_us
