#    Copyright (c) 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Publish weather data to RESTful sites such as the Weather Underground or PWSWeather."""
import Queue
import datetime
import hashlib
import httplib
import platform
import re
import socket
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

class SkippedPost(Exception):
    """Raised when a post is skipped."""

class BadLogin(StandardError):
    """Raised when login information is bad or missing."""
        
#==============================================================================
#                    Class StdRESTbase
#==============================================================================

class StdRESTbase(weewx.wxengine.StdService):
    """Base class for the RESTful weewx services."""

    # This class implements a generic protocol processing model:
    #
    # Step:                                               Function:
    # 1. Extract record or packet from the incoming event
    # 2. Test whether to post                             skip_this_post
    # 3. Augment with data from database                  augment_from_database
    # 4. Augment with protocol-specific entries           augment_protocol
    # 5. Format and convert to outgoing protocol          format_protocol
    # 6. Post to the appropriate queue
    #
    # All these steps are combined in function process_record.

    def __init__(self, engine, config_dict, **protocol_dict):
        """Initialize StdRESTbase.
        
        Named parameters:
        
        stale: If non-None, how "fresh" a post has to be before it is accepted.
        
        interval: If non-None, how long to wait from the last post before
                  accepting a new post.
        
        protocol: A string holding the protocol name I am implementing.
        """
        super(StdRESTbase, self).__init__(engine, config_dict)
        
        self.loop_queue  = None
        self.loop_thread = None
        self.archive_queue  = None
        self.archive_thread = None
        self.stale         = protocol_dict.get('stale')
        self.post_interval = protocol_dict.get('interval')
        self.protocol      = protocol_dict.get('name', "Unknown")
        self.lastpost = 0

        # This option is for debugging/diagnostics when you want to ensure the
        # data are properly formatted but you do not want to upload data.
        self.skip_posting = protocol_dict.get('skip_posting', False)

    def init_info(self, site_dict):
        """Extract information out of the site dictionary or, if unavailable, the engine's  
        station info structure."""
        self.latitude    = float(site_dict.get('latitude',  self.engine.stn_info.latitude_f))
        self.longitude   = float(site_dict.get('longitude', self.engine.stn_info.longitude_f))
        self.station_type  = site_dict.get('station_type', self.config_dict['Station']['station_type'])
        self.station_model = site_dict.get('station_model', self.engine.stn_info.hardware)
        self.location    = site_dict.get('location',     self.engine.stn_info.location)
        self.station_url = site_dict.get('station_url',  self.engine.stn_info.station_url)
        
    def init_loop_queue(self):
        """Initiate the LOOP queue. """
        self.loop_queue = Queue.Queue()

    def init_archive_queue(self):
        """Initiate the archive queue."""
        self.archive_queue = Queue.Queue()

    def shutDown(self):
        """Shut down any threads"""
        StdRESTbase.shutDown_thread(self.loop_queue, self.loop_thread)
        StdRESTbase.shutDown_thread(self.archive_queue, self.archive_thread)

    @staticmethod
    def shutDown_thread(q, t):
        """Function to shut down a thread."""
        if q:
            # Put a None in the queue to signal the thread to shutdown
            q.put(None)
            # Wait up to 20 seconds for the thread to exit:
            t.join(20.0)
            if t.isAlive():
                syslog.syslog(syslog.LOG_ERR, "restx: Unable to shut down %s thread" % t.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "restx: Shut down %s thread." % t.name)

    def skip_this_post(self, time_ts):
        """Check whether the post is current"""
        # Don't post if this record is too old
        _how_old = time.time() - time_ts
        if self.stale and _how_old > self.stale:
            raise SkippedPost("record %s is stale (%d > %d)." % \
                    (timestamp_to_string(time_ts), _how_old, self.stale))
 
        # We don't want to post more often than the post interval
        _how_long = time_ts - self.lastpost
        if _how_long < self.post_interval:
            raise SkippedPost("record %s wait interval (%d < %d) has not passed." % \
                    (timestamp_to_string(time_ts), _how_long, self.post_interval))
    
        self.lastpost = time_ts
        
    def process_record(self, record):
        """Generic processing function that follows the protocol model.
        
        By overriding the appropriate augmentation and formatting functions,
        it can work for many protocols without change.
        """
        # See whether this post should be skipped.
        try:
            self.skip_this_post(record['dateTime'])
        except SkippedPost, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s %s" % (self.protocol, e))
            return
        # Extract the record from the event, then augment it with data from
        # the archive:
        _record = self.augment_from_database(record, self.engine.archive)
        # Then augment it with any protocol-specific data:
        self.augment_protocol(_record)
        # Format and convert to the outgoing protocol
        _request = self.format_protocol(_record)
        # For debugging, skip posting but log what would be posted
        if self.skip_posting:
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: skipping upload" % self.protocol)
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: method: %s" % (self.protocol, _request.get_method()))
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: url: %s" % (self.protocol, _request.get_full_url()))
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: data: %s" % (self.protocol, _request.get_data()))
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: headers: %s" % (self.protocol, _request.header_items()))
            return

        # Stuff it in the archive queue along with the timestamp:
        self.archive_queue.put((_record['dateTime'], _request))

    def augment_from_database(self, record, archive):
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

    def augment_protocol(self, record):
        """Augment a record with any protocol-specific information. Generally,
        this information would not be from the database (use augment_from_database
        for that."""
    
    def format_protocol(self, record):
        """Given a record, format it according to the protocol specification.
        This function should generally return something that can be used by
        one of the weewx RESTful sinks, such as PostRequest or PostTNC.""" 
        raise NotImplementedError("Method 'format_protocol' not implemented")
    
#==============================================================================
#                    Class Ambient
#==============================================================================

class Ambient(StdRESTbase):
    """Base class for weather sites that use the Ambient protocol."""

    # Types and formats of the data to be published, using the Ambient notation
    _formats = {'dateTime'    : ('dateutc',
                                 lambda _v : datetime.datetime.utcfromtimestamp(_v).isoformat(' ')),
                'action'      : ('action', '%s'),
                'station'     : ('ID', '%s'),
                'password'    : ('PASSWORD', '%s'),
                'softwaretype': ('softwaretype', '%s'),
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

    def __init__(self, engine, config_dict, format_dict=_formats, **ambient_dict):
        """Base class that implements the Ambient protocol.
        
        Named parameters:
        format_dict: A dictionary containing the format encodings to be used.
        The default is Ambient._formats
        
        station: The station ID (eg. KORHOODR3)
        [Required]
        
        password: Password for the station
        [Required]
        
        name: The name of the site we are posting to. Something like
        "Wunderground" will do.
        [Required]
        
        rapidfire: Set to true to have every LOOP packet post.
        Default is False.
        
        archive_post: Set to true to have every archive packet post.
        Default is the opposite of rapidfire value.
        
        rapidfire_url: The base URL to be used when posting LOOP packets.
        Required if rapidfire is true.
        
        archive_url: The base URL to be used when posting archive records.
        Required if archive_post is true.
        
        log_success: Set to True if we are to log successful posts to syslog.
        Default is false if rapidfire is true, else true.
        
        log_failure: Set to True if we are to log unsuccessful posts to syslog.
        Default is false if rapidfire is true, else true.
        
        max_tries: The max number of tries allowed when doing archive posts.
        (Always 1 for rapidfire posts) Default is 3
        
        max_backlog: The max number of queued posts that will be allowed to
        accumulate. (Always 0 for rapidfire posts). Default is infinite.
        """
        
        super(Ambient, self).__init__(engine, config_dict,
                                      **ambient_dict)

        # Try extracting the required keywords. If this fails, an exception
        # of type KeyError will be raised. Derived classes should be prepared
        # to catch it.
        self.station = ambient_dict['station']
        self.password = ambient_dict['password']
        site_name = ambient_dict['name']

        # If we got here, we have the minimum necessary.
        
        # Save the format encoding to be used
        self.format_dict = format_dict
        
        # It's not actually used by the Ambient protocol, but, for
        # completeness, initialize the site-specific information:
        self.init_info(ambient_dict)

        # The default is not not do an archive post if a rapidfire post
        # has been specified, but this can be overridden
        do_rapidfire_post = to_bool(ambient_dict.get('rapidfire', False))
        do_archive_post   = to_bool(ambient_dict.get('archive_post', not do_rapidfire_post))

        if do_rapidfire_post:
            self.rapidfire_url = ambient_dict['rapidfire_url']
            self.init_loop_queue()
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            ambient_dict.setdefault('log_success', False)
            ambient_dict.setdefault('log_failure', False)
            ambient_dict.setdefault('max_tries',   1)
            ambient_dict.setdefault('max_backlog', 0)
            self.loop_thread = PostRequest(self.loop_queue, 
                                           site_name + '-Rapidfire',
                                           **ambient_dict)
            self.loop_thread.start()
        if do_archive_post:
            self.archive_url = ambient_dict['archive_url']
            self.init_archive_queue()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            self.archive_thread = PostRequest(self.archive_queue,
                                              site_name,
                                               **ambient_dict)
            self.archive_thread.start()

    def new_loop_packet(self, event):
        """Process a new LOOP event."""
        # Ambient loop posts can almost follow the standard protocol model.
        # The only difference is we have to add the keywords 'realtime' and
        # 'rtfreq'.
        
        try:
            self.skip_this_post(event.packet['dateTime'])
        except SkippedPost, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: %s: %s" % (self.protocol, e))
            return

        # Extract the record from the event, then augment it with data from
        # the archive:
        _record = self.augment_from_database(event.packet, self.engine.archive)
        # Then augment it with any Ambient-specific data:
        self.augment_protocol(_record)
        # Add the Rapidfire-specific keywords:
        _record['realtime'] = '1'
        _record['rtfreq'] = '2.5'
        # Format and convert to the outgoing protocol
        _request = self.format_protocol(_record)
        # Stuff it in the loop queue:
        self.loop_queue.put((_record['dateTime'], _request))

    def new_archive_record(self, event):
        """Process a new archive event."""
        # Ambient archive posts can just follow the standard protocol model:
        return self.process_record(event.record)

    def augment_protocol(self, record):
        """Augment a record with the Ambient-specific data fields."""
        record['action']  = 'updateraw'
        record['station'] = self.station
        record['password'] = self.password
        record['softwaretype'] = "weewx-%s" % weewx.__version__
        
    def format_protocol(self, record):
        """Given a record, format it using the Ambient protocol.
        
        Performs any necessary unit conversions.
        
        Returns:
        A Request object
        """

        # Requires US units.
        if record['usUnits'] == weewx.US:
            # It's already in US units.
            _datadict = record
        else:
            # It's in something else. Perform the conversion
            _datadict = weewx.units.StdUnitConverters[weewx.US].convertDict(record)
            # Add the new unit system
            _datadict['usUnits'] = weewx.US

        # Reformat according to the Ambient protocol:
        _post_dict = reformat_dict(_datadict, self.format_dict)

        # Form the full URL
        _url = self.archive_url + '?' + urllib.urlencode(_post_dict)
        # Convert to a Request object:
        _request = urllib2.Request(_url)
        return _request

#==============================================================================
#                    Class StdWunderground
#==============================================================================

class StdWunderground(Ambient):
    """Specialized version of the Ambient protocol for the Weather Underground."""

    # The URLs used by the WU:
    rapidfire_url = "http://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"
    archive_url = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"

    def __init__(self, engine, config_dict):
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the WU options:
            ambient_dict=dict(config_dict['StdRESTful']['Wunderground'])
            ambient_dict.setdefault('rapidfire_url', StdWunderground.rapidfire_url)
            ambient_dict.setdefault('archive_url',   StdWunderground.archive_url)
            ambient_dict.setdefault('name', 'Wunderground')
            super(StdWunderground, self).__init__(engine, config_dict, 
                                                  **ambient_dict)
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to Wunderground")
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to Wunderground")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: missing parameter %s" % e)

#==============================================================================
#                    Class StdPWS
#==============================================================================

class StdPWSweather(Ambient):
    """Specialized version of the Ambient protocol for PWS"""

    # The URL used by PWS:
    archive_url = "http://www.pwsweather.com/pwsupdate/pwsupdate.php"

    def __init__(self, engine, config_dict):
        
        try:
            ambient_dict=dict(config_dict['StdRESTful']['PWSweather'])
            ambient_dict.setdefault('archive_url',   StdPWSweather.archive_url)
            ambient_dict.setdefault('name', 'PWSweather')
            super(StdPWSweather, self).__init__(engine, config_dict,
                                                **ambient_dict)
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to PWSweather")
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to PWSweather")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: missing parameter %s" % e)

#==============================================================================
#                    Class StdWOW
#==============================================================================

class StdWOW(Ambient):

    """Upload using the UK Met Office's WOW protocol. 
    
    For details of the WOW upload protocol, see 
    http://wow.metoffice.gov.uk/support/dataformats#dataFileUpload
    """

    # Types and formats of the data to be published:
    _formats = {'dateTime'    : ('dateutc', lambda _v : datetime.datetime.utcfromtimestamp(_v).isoformat(' ')),
                'station'     : ('siteid', '%s'),
                'password'    : ('siteAuthenticationKey', '%s'),
                'softwaretype': ('softwaretype', '%s'),
                'barometer'   : ('baromin', '%.1f'),
                'outTemp'     : ('tempf', '%.1f'),
                'outHumidity' : ('humidity', '%.0f'),
                'windSpeed'   : ('windspeedmph', '%.0f'),
                'windDir'     : ('winddir', '%.0f'),
                'windGust'    : ('windgustmph', '%.0f'),
                'windGustDir' : ('windgustdir', '%.0f'),
                'dewpoint'    : ('dewptf', '%.1f'),
                'hourRain'    : ('rainin', '%.2f'),
                'dayRain'     : ('dailyrainin', '%.2f')}
    
    # The URL used by WOW:
    archive_url = "http://wow.metoffice.gov.uk/automaticreading"

    def __init__(self, engine, config_dict):
        
        try:
            ambient_dict=dict(config_dict['StdRESTful']['WOW'])
            ambient_dict.setdefault('archive_url',   StdWOW.archive_url)
            ambient_dict.setdefault('name', 'WOW')
            if ambient_dict.has_key('siteid'):
                ambient_dict['station'] = ambient_dict['siteid']
            if ambient_dict.has_key('siteAuthenticationKey'):
                ambient_dict['password'] = ambient_dict['siteAuthenticationKey']
            super(StdWOW, self).__init__(engine, config_dict, 
                                         format_dict=StdWOW._formats, 
                                         **ambient_dict)
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to WOW")
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to WOW")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: missing parameter %s" % e)
    
#==============================================================================
#                            class StdAWEKAS
#==============================================================================
class StdAWEKAS(StdRESTbase):
    """Upload to AWEKAS - Automatisches WEtterKArten System

    The AWEKAS server expects a single string of values delimited by
    semicolons.  The position of each value matters, for example position 1
    is the awekas username and position 2 is the awekas password.

    Positions 1-25 are defined for the basic API:

    Pos1: user (awekas username)
    Pos2: password (awekas password MD5 Hash)
    Pos3: date (dd.mm.yyyy) (varchar)
    Pos4: time (hh:mm) (varchar)
    Pos5: temperature (C) (float)
    Pos6: humidity (%) (int)
    Pos7: air pressure (hPa) (float)
    Pos8: precipitation (rain at this day) (float)
    Pos9: wind speed (km/h) float)
    Pos10: wind direction (degree) (int)
    Pos11: weather condition (int)
            0=clear warning
            1=clear
            2=sunny sky
            3=partly cloudy
            4=cloudy
            5=heavy cloundy
            6=overcast sky
            7=fog
            8=rain showers
            9=heavy rain showers
           10=light rain
           11=rain
           12=heavy rain
           13=light snow
           14=snow
           15=light snow showers
           16=snow showers
           17=sleet
           18=hail
           19=thunderstorm
           20=storm
           21=freezing rain
           22=warning
           23=drizzle
           24=heavy snow
           25=heavy snow showers
    Pos12: warning text (varchar)
    Pos13: snow high (cm) (int) if no snow leave blank
    Pos14: language (varchar)
           de=german; en=english; it=italian; fr=french; nl=dutch
    Pos15: tendency (int)
           -2 = high falling
           -1 = falling
            0 = steady
            1 = rising
            2 = high rising
    Pos16. wind gust (km/h) (float)
    Pos17: solar radiation (W/m^2) (float) 
    Pos18: UV Index (float)
    Pos19: brightness (LUX) (int)
    Pos20: sunshine hours today (float)
    Pos21: soil temperature (degree C) (float)
    Pos22: rain rate (mm/h) (float)
    Pos23: software flag NNNN_X.Y, for example, WLIP_2.15
    Pos24: longitude (float)
    Pos25: latitude (float)

    positions 26-111 are defined for API2
    """

    _SERVER_URL = 'http://data.awekas.at/eingabe_pruefung.php'
    _FORMATS = {'barometer'   : '%.3f',
                'outTemp'     : '%.1f',
                'outHumidity' : '%.0f',
                'windSpeed'   : '%.1f',
                'windDir'     : '%.0f',
                'windGust'    : '%.1f',
                'dewpoint'    : '%.1f',
                'hourRain'    : '%.2f',
                'dayRain'     : '%.2f',
                'radiation'   : '%.2f',
                'UV'          : '%.2f',
                'rainRate'    : '%.2f'}

    def __init__(self, engine, config_dict):
        """Initialize for posting data to AWEKAS.  The following parameters
        are specified in the AWEKAS section of the configuration.

        username: AWEKAS user name
        [Required]

        password: AWEKAS password
        [Required]

        language: Possible values include de, en, it, fr, nl
        [Optional.  Default is de]

        interval: The interval in seconds between posts.
        AWEKAS requests that uploads happen no more often than 5 minutes, so
        this should be set to no less than 300.
        [Optional.  Default is 300]

        max_tries: Maximum number of tries before giving up
        [Optional.  Default is 3]

        latitude: Station latitude
        [Optional.  Default is latitude from the Station section.]

        longitude: Station longitude
        [Optional.  Default is the longitude from the Station section.]
        
        server_url: Base URL for the AWEKAS server
        [Optional.  Default is http://data.awekas.at/eingabe_pruefung.php]
        """
        
        try:
            # set up the default dict for awekas
            awekas_dict=dict(config_dict['StdRESTful']['AWEKAS'])
            awekas_dict.setdefault('name', 'AWEKAS')
            awekas_dict.setdefault('interval', 300)
            awekas_dict.setdefault('stale', None)
            awekas_dict.setdefault('server_url', StdAWEKAS._SERVER_URL)
            awekas_dict.setdefault('language', 'en')

            # let the super have a go to set member data...
            super(StdAWEKAS, self).__init__(engine, config_dict, **awekas_dict)

            # ...then grab the bits we must have
            self.username = awekas_dict['username']
            self.password = awekas_dict['password']
            self.server_url = awekas_dict['server_url']
            self.language = awekas_dict['language']

            # latitude and longitude are assigned by super
            self.init_info(awekas_dict)
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to AWEKAS")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: missing parameter %s" % e)
            return

        self.init_archive_queue()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        # Add more options needed by the PostRequest thread
        awekas_dict.setdefault('log_success', True)
        awekas_dict.setdefault('log_failure', True)
        awekas_dict.setdefault('max_tries',   5)
        awekas_dict.setdefault('max_backlog', 0)
        self.archive_thread = PostRequest(self.archive_queue,
                                          'AWEKAS',
                                           **awekas_dict)
        self.archive_thread.start()
        syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to AWEKAS")
        
    def new_archive_record(self, event):
        return self.process_record(event.record)

    def format_protocol(self, record):
        """Format data for upload to AWEKAS."""

        # put everything into the units AWEKAS wants
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)
            record['usUnits'] = weewx.METRIC
        if record.has_key('dayRain') and record['dayRain'] is not None:
            record['dayRain'] = record['dayRain'] * 10
        if record.has_key('rainRate') and record['rainRate'] is not None:
            record['rainRate'] = record['rainRate'] * 10

        # assemble an array of values in the order AWEKAS wants
        values = [self.username]
        m = hashlib.md5()
        m.update(self.password)
        values.append(m.hexdigest())
        time_tt = time.gmtime(record['dateTime'])
        values.append(time.strftime("%d.%m.%Y", time_tt))
        values.append(time.strftime("%H:%M", time_tt))
        values.append(self._format(record, 'outTemp')) # C
        values.append(self._format(record, 'outHumidity')) # %
        values.append(self._format(record, 'barometer')) # mbar
        values.append(self._format(record, 'dayRain')) # mm?
        values.append(self._format(record, 'windSpeed')) # km/h
        values.append(self._format(record, 'windDir'))
        values.append('') # weather condition
        values.append('') # warning text
        values.append('') # snow high
        values.append(self.language)
        values.append('') # tendency
        values.append(self._format(record, 'windGust')) # km/h
        values.append(self._format(record, 'radiation')) # W/m^2
        values.append(self._format(record, 'UV')) # uv index
        values.append('') # brightness in lux
        values.append('') # sunshine hours
        values.append('') # soil temperature
        values.append(self._format(record, 'rainRate')) # mm/h
        values.append('weewx_%s' % weewx.__version__)
        values.append(str(self.longitude))
        values.append(str(self.latitude))
        valstr = ';'.join(values)
        _url = self.server_url + '?val=' + valstr
        _request = urllib2.Request(_url)
        return _request

    def _format(self, record, label):
        if record.has_key(label) and record[label] is not None:
            if StdAWEKAS._FORMATS.has_key(label):
                return StdAWEKAS._FORMATS[label] % record[label]
            return str(record[label])
        return ''


#==============================================================================
# StationRegistry
#==============================================================================

class StdStationRegistry(StdRESTbase):
    """Class for phoning home to register a weewx station.

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
         register_this_station = True
    """

    WEEWX_SERVER_URL = 'http://weewx.com/register/register.cgi'

    _formats = {'station_url'   : ('station_url', '%s'),
                'latitude'      : ('latitude',  '%.4f'),
                'longitude'     : ('longitude', '%.4f'),
                'description'   : ('description', '%s'),
                'station_type'  : ('station_type', '%s'),
                'station_model' : ('station_model', '%s'),
                'softwaretype'  : ('weewx_info', '%s'),
                'python_info'   : ('python_info', '%s'),
                'platform_info' : ('platform_info', '%s'),
                'weewx_info'    : ('weewx_info', '%s')}

    # adapted from django URLValidator
    _urlregex = re.compile(r'^(?:http)s?://' # http:// or https://
                           r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                           r'localhost|' #localhost...
                           r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                           r'(?::\d+)?' # optional port
                           r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    def __init__(self, engine, config_dict):
        """
        The following options are accepted in subsection [[StationRegistry]]
        
        register_this_station: indicates whether to run this service
        [Optional. Default is False]

        station_url: URL of the weather station
        [Required. If not specified in this section, the station_url from the
        Station section will be used.]

        interval: time in seconds between posts
        [Optional.  Default is 604800 (once per week)]

        latitude: station latitude
        [Optional. If not specified, the latitude from the Station section
        will be used.]

        longitude: station longitude
        [Optional. If not specified, the longitude from the Station section
        will be used.]
        
        station_type: The generic type of station.
        [Optional. If not specified, the driver name is used. E.g., 'Vantage']

        station_model: The specific type of hardware.
        [Optional. If not specified, the attribute 'hardware' of the console
        will be used. E.g., 'VantagePro2']
        
        description: A short description of the station.
        [Optional. If not specified, the option 'location' in section Station
        will be used.]
        
        server_url - site at which to register
        [Optional.  Default is the weewx.com registry.]

        max_tries: number of attempts to make before giving up
        [Optional.  Default is 5]
        """
        try:
            registry_dict = dict(config_dict['StdRESTful']['StationRegistry'])
        except KeyError, e:
            syslog.syslog(syslog.LOG_INFO, "restx: Station registry will not be run.")
            syslog.syslog(syslog.LOG_INFO, " ****  Reason: missing section '%s'" % (e,))
            return
        
        # Should the service be run?
        _optin = to_bool(registry_dict.get('register_this_station', False))
        if not _optin:
            syslog.syslog(syslog.LOG_INFO, "restx: Station registry not requested.")
            return

        # Set any missing options needed by my base class, then initialize the
        # base class:
        registry_dict.setdefault('name', 'StationRegistry')
        registry_dict['stale']     = to_int(registry_dict.get('stale'))
        registry_dict['interval']  = to_int(registry_dict.get('interval', 604800))
        
        super(StdStationRegistry, self).__init__(engine, config_dict, **registry_dict)

        self.init_info(registry_dict)
        if self.station_url is None:
            syslog.syslog(syslog.LOG_INFO, "restx: Station registry will not be run.")
            syslog.syslog(syslog.LOG_INFO, " ****  Reason: station_url is required.")
            return
        
        self.archive_url = registry_dict.get('server_url', StdStationRegistry.WEEWX_SERVER_URL)
        self.description = registry_dict.get('description', config_dict['Station'].get('location'))

        self.weewx_info = weewx.__version__
        self.python_info = platform.python_version()
        self.platform_info = platform.platform()

        if not self._validateParameters():
            syslog.syslog(syslog.LOG_INFO, 'restx: station will not register')
            return
        
        self.init_archive_queue()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        # Add some more options needed by the PostRequest thread
        registry_dict.setdefault('log_success', True)
        registry_dict.setdefault('log_failure', True)
        registry_dict.setdefault('max_tries',   5)
        registry_dict.setdefault('max_backlog', 0)
        self.archive_thread = PostRequest(self.archive_queue,
                                          'StationRegistry',
                                           **registry_dict)
        self.archive_thread.start()
        syslog.syslog(syslog.LOG_INFO, 'restx: station will register with %s' % self.archive_url)

    def new_archive_record(self, event):
        time_ts = int(time.time())
        try:
            self.skip_this_post(time_ts)
        except SkippedPost, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: StationRegistry %s" % (e,))
            return
        # Start with an empty dictionary
        _record = dict()
        # Add the station registry information
        self.augment_protocol(_record)
        # Encode using registry protocol
        _request = self.format_protocol(_record)
        # Put in the queue
        self.archive_queue.put((time_ts, _request))

    def augment_protocol(self, record):        
        record['station_url']   = self.station_url
        record['latitude']      = self.latitude
        record['longitude']     = self.longitude
        record['station_type']  = self.station_type
        record['station_model'] = self.station_model
        record['weewx_info']    = self.weewx_info
        record['python_info']   = self.python_info
        record['platform_info'] = self.platform_info
        if self.description:
            record['description'] = self.description
            
    def format_protocol(self, record):
        _post_dict = reformat_dict(record, StdStationRegistry._formats)
        # Form the full URL
        _url = self.archive_url + '?' + urllib.urlencode(_post_dict)
        # Convert to a Request object:
        _request = urllib2.Request(_url)
        return _request
                
    @staticmethod
    def _checkURL(url):
        return StdStationRegistry._urlregex.search(url)

    def _validateParameters(self):
        msgs = []

        if self.station_url is None:
            # the station url must be defined
            msgs.append("station_url is not defined")
        elif not StdStationRegistry._checkURL(self.station_url):
            # ensure the url does not have problem characters.  do not check
            # to see whether the site actually exists.
            msgs.append("station_url '%s' is not a valid URL" %
                        self.station_url)

        # check server url just in case someone modified the default
        url = self.archive_url
        if not StdStationRegistry._checkURL(url):
            msgs.append("server_url '%s' is not a valid URL" % self.archive_url)

        if msgs:
            errmsg = 'One or more unusable parameters.'
            syslog.syslog(syslog.LOG_ERR, 'restx: StationRegistry: %s' % errmsg)
            for m in msgs:
                syslog.syslog(syslog.LOG_ERR, '  **** %s' % m)
            return False
        return True


#==============================================================================
#                             class StdCWOP
#==============================================================================

class StdCWOP(StdRESTbase):
    """Upload using the CWOP protocol. """
    
    # Station IDs must start with one of these:
    valid_prefixes = ['CW', 'DW', 'EW']
    default_servers = ['cwop.aprs.net:14580', 'cwop.aprs.net:23']

    def __init__(self, engine, config_dict):
        
        # First extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the CWOP dictionary:
            cwop_dict=dict(config_dict['StdRESTful']['CWOP'])
            cwop_dict.setdefault('name', 'CWOP')
            cwop_dict['stale']    = to_int(cwop_dict.get('stale', 1800))
            cwop_dict['interval'] = to_int(cwop_dict.get('interval'))
            super(StdCWOP, self).__init__(engine, config_dict,
                                          **cwop_dict)

            # Extract the station and (if necessary) passcode
            self.station = cwop_dict['station'].upper()
            if self.station[0:2] in StdCWOP.valid_prefixes:
                self.passcode = "-1"
            else:
                self.passcode = cwop_dict['passcode']
            
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: Data will not be posted to CWOP")
            syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: missing parameter %s" % e)
            return
            
        # If we made it this far, we can post. Everything else is optional.
        self.init_info(cwop_dict)
        
        self.init_archive_queue()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
        # Get the stuff the TNC thread will need....
        cwop_dict.setdefault('max_tries', 3)
        cwop_dict.setdefault('log_success', True)
        cwop_dict.setdefault('log_failure', True)
        if cwop_dict.has_key('server'):
            cwop_dict['server'] = weeutil.weeutil.option_as_list(cwop_dict['server'])
        else:
            cwop_dict['server'] = StdCWOP.default_servers

        # ... launch it ...
        self.archive_thread = PostTNC(self.archive_queue,
                                      cwop_dict['name'],
                                      **cwop_dict)
        # ... then start it
        self.archive_thread.start()
        syslog.syslog(syslog.LOG_DEBUG, "restx: Data will be posted to CWOP station %s" % (self.station,))
        
    def new_archive_record(self, event):
        """Process a new archive event."""
        # CWOP archive posts can just follow the standard protocol model:
        return self.process_record(event.record)

    def get_login_string(self):
        _login = "user %s pass %s vers weewx %s\r\n" % (self.station, self.passcode, weewx.__version__)
        return _login

    def get_tnc_packet(self, in_record):
        """Form the TNC2 packet used by CWOP."""

        # Make sure the record is in US units:
        if in_record['usUnits'] == weewx.US:
            _record = in_record
        else:
            _record = weewx.units.StdUnitConverters[weewx.US].convertDict(in_record)
            _record['usUnits'] = weewx.US

        # Preamble to the TNC packet:
        _prefix = "%s>APRS,TCPIP*:" % (self.station,)

        # Time:
        _time_tt = time.gmtime(_record['dateTime'])
        _time_str = time.strftime("@%d%H%Mz", _time_tt)

        # Position:
        _lat_str = weeutil.weeutil.latlon_string(self.latitude, ('N', 'S'), 'lat')
        _lon_str = weeutil.weeutil.latlon_string(self.longitude, ('E', 'W'), 'lon')
        _latlon_str = '%s%s%s/%s%s%s' % (_lat_str + _lon_str)

        # Wind and temperature
        _wt_list = []
        for _obs_type in ['windDir', 'windSpeed', 'windGust', 'outTemp']:
            _v = _record.get(_obs_type)
            _wt_list.append("%03d" % _v if _v is not None else '...')
        _wt_str = "_%s/%sg%st%s" % tuple(_wt_list)

        # Rain
        _rain_list = []
        for _obs_type in ['hourRain', 'rain24', 'dayRain']:
            _v = _record.get(_obs_type)
            _rain_list.append("%03d" % (_v * 100.0) if _v is not None else '...')
        _rain_str = "r%sp%sP%s" % tuple(_rain_list)

        # Barometer:
        _baro = _record.get('altimeter')
        if _baro is None:
            _baro_str = "b....."
        else:
            # While everything else in the CWOP protocol is in US Customary, they
            # want the barometer in millibars.
            _baro_vt = weewx.units.convert((_baro, 'inHg', 'group_pressure'), 'mbar')
            _baro_str = "b%05d" % (_baro_vt[0] * 10.0)

        # Humidity:
        _humidity = _record.get('outHumidity')
        if _humidity is None:
            _humid_str = "h.."
        else:
            _humid_str = ("h%02d" % _humidity) if _humidity < 100.0 else "h00"

        # Radiation:
        _radiation = _record.get('radiation')
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

        _tnc_packet = _prefix + _time_str + _latlon_str + _wt_str + _rain_str + \
                      _baro_str + _humid_str + _radiation_str + _equipment_str + "\r\n"

        return _tnc_packet

    def format_protocol(self, record):
        # Get the login string
        _login = self.get_login_string()
        # And the TNC packet
        _tnc_packet = self.get_tnc_packet(record)
        
        return (_login, _tnc_packet)

###===========================================================================###
###              Weewx "Sink" classes --- used as sinks for posts             ###
###===========================================================================###


#===============================================================================
#                    Class PostRequest
#===============================================================================

class PostRequest(threading.Thread):
    """Post an urllib2 "Request" object, using a separate thread."""
    
    
    def __init__(self, queue, thread_name, **kwargs):
        threading.Thread.__init__(self, name=thread_name)

        self.queue = queue
        self.log_success = to_bool(kwargs.get('log_success', True))
        self.log_failure = to_bool(kwargs.get('log_failure', True))
        self.max_tries   = to_int(kwargs.get('max_tries', 3))
        self.max_backlog = to_int(kwargs.get('max_backlog'))

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
                    _time_str = timestamp_to_string(_timestamp)
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
            except urllib2.HTTPError, e:
                # WOW signals a bad login with a HTML Error 403 code:
                if e.code == 403:
                    raise BadLogin(e)
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.name))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
            except (urllib2.URLError, socket.error, httplib.BadStatusLine, httplib.IncompleteRead), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.name))
                syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
            else:
                if _response.code != 200:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Failed attempt #%d to upload to %s" % (_count+1, self.name))
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
            raise FailedPost("Failed upload to site %s after %d tries" % (self.name, self.max_tries))

#===============================================================================
#                    Class PostTNC
#===============================================================================

class PostTNC(threading.Thread):
    """Post using the CWOP TNC protocol."""

    def __init__(self, queue, thread_name, **kwargs):
        threading.Thread.__init__(self, name=thread_name)

        self.queue = queue
        self.log_success = to_bool(kwargs.get('log_success', True))
        self.log_failure = to_bool(kwargs.get('log_failure', True))
        self.max_tries   = to_int(kwargs.get('max_tries', 3))
        self.max_backlog = to_int(kwargs.get('max_backlog'))
        self.server = kwargs['server']

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
            _timestamp, (_login, _tnc_packet) = _request_tuple

            try:
                # Now post it
                self.send_packet(_login, _tnc_packet)
            except (FailedPost, IOError), e:
                if self.log_failure:
                    syslog.syslog(syslog.LOG_ERR, "restx: Failed to upload to '%s'" % self.name)
                    syslog.syslog(syslog.LOG_ERR, " ****  Reason: %s" % e)
            else:
                if self.log_success:
                    _time_str = timestamp_to_string(_timestamp)
                    syslog.syslog(syslog.LOG_INFO, "restx: Published record %s to %s" % (_time_str, self.name))

    def send_packet(self, login, tnc_packet):

        # Get a socket connection:
        _sock = self._get_connect()

        try:
            # Send the login:
            self._send(_sock, login)

            # And then the packet
            self._send(_sock, tnc_packet)
        finally:
            _sock.close()

    def _get_connect(self):

        # Go through the list of known server:ports, looking for
        # a connection that works:
        for _serv_addr_str in self.server:
            _server, _port_str = _serv_addr_str.split(":")
            _port = int(_port_str)
            for _count in range(self.max_tries):
                try:
                    _sock = socket.socket()
                    _sock.connect((_server, _port))
                except socket.error, e:
                    # Unsuccessful. Log it and try again
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connection attempt #%d failed to %s server %s:%d" % (_count + 1, self.name, _server, _port))
                    syslog.syslog(syslog.LOG_DEBUG, " ****  Reason: %s" % (e,))
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restx: Connected to %s server %s:%d" % (self.name, _server, _port))
                    return _sock
                # Couldn't connect on this attempt. Close it, try again.
                try:
                    _sock.close()
                except:
                    pass
            # If we got here, that server didn't work. Log it and go on to the next one.
            syslog.syslog(syslog.LOG_DEBUG, "restx: Unable to connect to %s server %s:%d" % (self.name, _server, _port))

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

#===============================================================================
#                           UTILITIES
#===============================================================================
def reformat_dict(record, format_dict):
    """Given a record, reformat it.
    
    record: A dictionary containing observation types
    
    format_dict: A dictionary containing the key and format to be used for the reformatting.
    The format can either be a string format, or a function.
    
    Example:
    >>> form = {'dateTime'    : ('dateutc', lambda _v : datetime.datetime.utcfromtimestamp(_v).isoformat(' ')),
    ...         'barometer'   : ('baromin', '%.3f'),
    ...         'outTemp'     : ('tempf', '%.1f')}
    >>> record = {'dateTime' : 1383755400, 'usUnits' : 16, 'outTemp' : 20.0, 'barometer' : 1020.0}
    >>> print reformat_dict(record, form)
    {'baromin': '1020.000', 'tempf': '20.0', 'dateutc': '2013-11-06 16:30:00'}
    """

    _post_dict = dict()

    # Go through each of the supported types, formatting it, then adding to _post_dict:
    for _key in format_dict:
        _v = record.get(_key)
        # Check to make sure the type is not null
        if _v is None:
            continue
        # Extract the key to be used in the reformatted dictionary, as well
        # as the format to be used.
        _k, _f = format_dict[_key]
        # First try formatting as a string. If that doesn't work, try it as a function.
        try:
            _post_dict[_k] = _f % _v
        except TypeError:
            _post_dict[_k] = _f(_v)

    return _post_dict

if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print "PASSED"
