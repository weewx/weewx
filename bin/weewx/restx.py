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
import time
import urllib
import urllib2

import weeutil.weeutil
import weewx.archive
import weewx.wxengine

class ServiceError(Exception):
    """Raised when not enough info is available to start a service."""
class FailedPost(IOError):
    """Raised when a post fails after trying the max number of allowed times"""
class SkippedPost(Exception):
    """Raised when a post is skipped."""
class BadLogin(StandardError):
    """Raised when login information is bad or missing."""
        
#===============================================================================
#                    Class StdRESTbase
#===============================================================================

class StdRESTbase(weewx.wxengine.StdService):
    """Base class for RESTful weewx services."""

    def __init__(self, engine, config_dict):
        super(StdRESTbase, self).__init__(engine, config_dict)
        self.loop_queue = None
        self.archive_queue = None

    def init_info(self, site_dict):
        self.latitude     = float(site_dict.get('latitude', self.engine.stn_info.latitude_f))
        self.longitude    = float(site_dict.get('longitude', self.engine.stn_info.longitude_f))
        self.hardware     = site_dict.get('station_type', self.engine.stn_info.hardware)
        self.location     = site_dict.get('location',     self.engine.stn_info.location)
        self.station_url  = site_dict.get('station_url',  self.engine.stn_info.station_url)
        
    def init_loop_queue(self):
        self.loop_queue = Queue.Queue()

    def init_archive_queue(self):
        self.archive_queue = Queue.Queue()

    def shutDown(self):
        """Shut down any threads"""
        self.shutDown_thread(self.loop_queue, self.loop_thread)
        self.shutDown_thread(self.archive_queue, self.archive_thread)

    def shutDown_thread(self, q, t):
        if q:
            # Put a None in the queue. This will signal to the thread to shutdown
            q.put(None)
            # Wait up to 20 seconds for the thread to exit:
            t.join(20.0)
            if t.isAlive():
                syslog.syslog(syslog.LOG_ERR, "restx: Unable to shut down %s thread" % t.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "restx: Shut down %s thread." % t.name)
        
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
                                               ambient_dict['name']+'-Rapidfire',
                                               **ambient_dict)
                self.loop_thread.start()
            if do_archive_post:
                self.archive_url = ambient_dict['archive_url']
                self.init_archive_queue()
                self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
                self.archive_thread = PostRequest(self.archive_queue,
                                                  ambient_dict['name'],
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

    def new_archive_record(self, event):
        _record = self.assemble_data(event.record, self.archive)
        _post_dict = self.extract_from(_record)
        _url = self.archive_url + '?' + weeutil.weeutil.urlencode(_post_dict)
        _request = urllib2.Request(_url)
        self.loop_queue.put((_record['dateTime'], _request))

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
            ambient_dict.setdefault('name', 'Wunderground')
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
    
    
    def __init__(self, queue, thread_name, **kwargs):
        threading.Thread.__init__(self, name=thread_name)

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

#===============================================================================
#                             class CWOP
#===============================================================================

class CWOP(StdRESTbase):
    """Upload using the CWOP protocol. """
    
    # Station IDs must start with one of these:
    valid_prefixes = ['CW', 'DW', 'EW']
    
    default_servers = ['cwop.aprs.net:14580', 'cwop.aprs.net:23']

    def __init__(self, engine, config_dict):
        """Initialize for a post to CWOP.
        
        site: The upload site ("CWOP")
        
        station: The name of the station (e.g., "CW1234") as a string [Required]
        
        server: List of APRS servers and ports in the 
        form cwop.aprs.net:14580 [Required]
         
        latitude: Station latitude [Required]
        
        longitude: Station longitude [Required]

        hardware: Station hardware (eg, "VantagePro") [Required]
        
        passcode: Passcode for your station [Optional. APRS only]
        
        interval: The interval in seconds between posts [Optional. 
        Default is 0 (send every post)]
        
        stale: How old a record can be before it will not be 
        used for a catchup [Optional. Default is 1800]
        
        max_tries: Max # of tries before giving up [Optional. Default is 3]

        CWOP does not like heavy traffic on their servers, so they encourage
        posts roughly every 15 minutes and at most every 5 minutes. So,
        key 'interval' should be set to no less than 300, but preferably 900.
        Setting it to zero will cause every archive record to be posted.
        """
        
        super(CWOP, self).__init__(engine, config_dict)
        
        # First extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract the CWOP dictionary:
            cwop_dict=dict(config_dict['StdRESTful']['CWOP'])

            # Extract the station and (if necessary) passcode
            self.station = cwop_dict['station'].upper()
            if self.station[0:2] in CWOP.valid_prefixes:
                self.passcode = "-1"
            else:
                self.passcode = cwop_dict['passcode']
            # Find and open the archive database:
            archive_db_dict = config_dict['Databases'][config_dict['StdArchive']['archive_database']]
            self.archive = weewx.archive.Archive.open(archive_db_dict)
            
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to CWOP")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % e)
            return
            
        # If we made it this far, we can post. Everything else is optional.
        self.interval  = int(cwop_dict.get('interval', 0))
        self.stale     = int(cwop_dict.get('stale', 1800))
        
        self.init_info(cwop_dict)
        
        self._lastpost = None
    
        self.init_archive_queue()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
        # Get the stuff the TNC thread will need....
        cwop_dict.setdefault('max_tries', 3)
        cwop_dict.setdefault('log_success', True)
        cwop_dict.setdefault('log_failure', True)
        cwop_dict.setdefault('name', 'CWOP')
        if cwop_dict.has_key('server'):
            cwop_dict['server'] = weeutil.weeutil.option_as_list(cwop_dict['server'])
        else:
            cwop_dict['server'] = CWOP.default_servers

        # ... launch it ...
        self.archive_thread = PostTNC(self.archive_queue,
                                      cwop_dict['name'],
                                      **cwop_dict)
        # ... then start it
        self.archive_thread.start()

        syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to CWOP station %s" % (self.station,))
        
    def new_archive_record(self, event):
        """Post data to CWOP, using the CWOP protocol."""

        _time_ts = event.record['dateTime']

        # There are a couple of reasons to skip a post to CWOP.

        # 1. They do not allow backfilling, so there is no reason to post
        #    an old out-of-date record.
        _how_old = time.time() - _time_ts
        if self.stale and _how_old > self.stale:
            syslog.syslog(syslog.LOG_DEBUG, "restx: CWOP record %s is stale (%d > %d)." % \
                    (weeutil.weeutil.timestamp_to_string(_time_ts), _how_old, self.stale))
            return
 
        # 2. We don't want to post more often than the interval
        if self._lastpost and _time_ts - self._lastpost < self.interval:
            syslog.syslog(syslog.LOG_DEBUG, "restx: CWOP wait interval (%d) has not passed." % \
                    (self.interval,))
            return
        
        # Get the data record for this time:
        _record = self.assemble_data(event.record, self.archive)
        # Get the login string
        _login = self.get_login_string()
        # And the TNC packet
        _tnc_packet = self.get_tnc_packet(_record)
        # Shove everything into the queue
        self.archive_queue.put((_record['dateTime'], _login, _tnc_packet))

        self._lastpost = _time_ts

    def get_login_string(self):
        login = "user %s pass %s vers weewx %s\r\n" % (self.station, self.passcode, weewx.__version__)
        return login

    def get_tnc_packet(self, record):
        """Form the TNC2 packet used by CWOP."""

        # Preamble to the TNC packet:
        prefix = "%s>APRS,TCPIP*:" % (self.station,)

        # Time:
        time_tt = time.gmtime(record['dateTime'])
        time_str = time.strftime("@%d%H%Mz", time_tt)

        # Position:
        lat_str = weeutil.weeutil.latlon_string(self.latitude, ('N', 'S'), 'lat')
        lon_str = weeutil.weeutil.latlon_string(self.longitude, ('E', 'W'), 'lon')
        latlon_str = '%s%s%s/%s%s%s' % (lat_str + lon_str)

        # Wind and temperature
        wt_list = []
        for obs_type in ['windDir', 'windSpeed', 'windGust', 'outTemp']:
            v = record.get(obs_type)
            wt_list.append("%03d" % v if v is not None else '...')
        wt_str = "_%s/%sg%st%s" % tuple(wt_list)

        # Rain
        rain_list = []
        for obs_type in ['hourRain', 'rain24', 'dayRain']:
            v = record.get(obs_type)
            rain_list.append("%03d" % (v * 100.0) if v is not None else '...')
        rain_str = "r%sp%sP%s" % tuple(rain_list)

        # Barometer:
        baro = record.get('altimeter')
        if baro is None:
            baro_str = "b....."
        else:
            # Figure out what unit type barometric pressure is in for this record:
            (u, g) = weewx.units.getStandardUnitType(record['usUnits'], 'altimeter')
            # Convert to millibars:
            baro_vt = weewx.units.convert((baro, u, g), 'mbar')
            baro_str = "b%05d" % (baro_vt[0] * 10.0)

        # Humidity:
        humidity = record.get('outHumidity')
        if humidity is None:
            humid_str = "h.."
        else:
            humid_str = ("h%02d" % humidity) if humidity < 100.0 else "h00"

        # Radiation:
        radiation = record.get('radiation')
        if radiation is None:
            radiation_str = ""
        elif radiation < 1000.0:
            radiation_str = "L%03d" % radiation
        elif radiation < 2000.0:
            radiation_str = "l%03d" % (radiation - 1000)
        else:
            radiation_str = ""

        # Station equipment
        equipment_str = ".weewx-%s-%s" % (weewx.__version__, self.hardware)

        tnc_packet = prefix + time_str + latlon_str + wt_str + rain_str + \
                     baro_str + humid_str + radiation_str + equipment_str + "\r\n"

        return tnc_packet

#===============================================================================
#                    Class PostTNC
#===============================================================================

class PostTNC(threading.Thread):
    """Post using the CWOP TNC protocol."""

    def __init__(self, queue, thread_name, **kwargs):
        threading.Thread.__init__(self, name=thread_name)

        self.queue = queue
        self.log_success = weeutil.weeutil.tobool(kwargs.get('log_success', True))
        self.log_failure = weeutil.weeutil.tobool(kwargs.get('log_failure', True))
        self.max_tries = int(kwargs.get('max_tries', 3))
        self.max_backlog = kwargs.get('max_backlog')
        self.server = kwargs['server']
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

            # Unpack the timestamp, login, tnc packet:
            _timestamp, _login, _tnc_packet = _request_tuple

            try:
                # Now post it
                self.send_packet(_login, _tnc_packet)
            except (FailedPost, IOError), e:
                if self.log_failure:
                    syslog.syslog(syslog.LOG_ERR, "restx: Failed to upload to '%s'" % self.name)
                    syslog.syslog(syslog.LOG_ERR, " ****  Reason: %s" % e)
            else:
                if self.log_success:
                    _time_str = weeutil.weeutil.timestamp_to_string(_timestamp)
                    syslog.syslog(syslog.LOG_INFO, "restx: Published record %s to %s" % (_time_str, self.name))

    def send_packet(self, _login, _tnc_packet):

        # Get a socket connection:
        _sock = self._get_connect()

        try:
            # Send the login:
            self._send(_sock, _login)

            # And then the packet
            self._send(_sock, _tnc_packet)
        finally:
            _sock.close()

    def _get_connect(self):

        # Go through the list of known server:ports, looking for
        # a connection that works:
        for serv_addr_str in self.server:
            server, port = serv_addr_str.split(":")
            port = int(port)
            for _count in range(self.max_tries):
                try:
                    sock = socket.socket()
                    sock.connect((server, port))
                except socket.error, e:
                    # Unsuccessful. Log it and try again
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connection attempt #%d failed to %s server %s:%d" % (_count + 1, self.name, server, port))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connected to %s server %s:%d" % (self.name, server, port))
                    return sock
                # Couldn't connect on this attempt. Close it, try again.
                try:
                    sock.close()
                except:
                    pass
            # If we got here, that server didn't work. Log it and go on to the next one.
            syslog.syslog(syslog.LOG_DEBUG, "restx: Unable to connect to %s server %s:%d" % (self.name, server, port))

        # If we got here. None of the servers worked. Raise an exception
        raise IOError, "Unable to obtain a socket connection to %s" % (self.name,)

    def _send(self, sock, msg):

        for _count in range(self.max_tries):

            try:
                sock.send(msg)
            except (IOError, socket.error), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_DEBUG, "restx: Attempt #%d failed to send to %s" % (_count + 1, self.name))
                syslog.syslog(syslog.LOG_DEBUG, "  ***  Reason: %s" % (e,))
            else:
                _resp = sock.recv(1024)
                return _resp
        else:
            # This is executed only if the loop terminates normally, meaning
            # the send failed max_tries times. Log it.
            raise FailedPost, "Failed upload to site %s after %d tries" % (self.name, self.max_tries)
