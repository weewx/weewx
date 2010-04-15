#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Publish weather data to RESTful sites such as the Weather Underground or PWSWeather."""
import syslog
import datetime
import threading
import urllib
import urllib2
import socket
import time

import weewx
import weewx.units
import weeutil.weeutil

site_url = {'Wunderground' : "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php?",
            'PWSweather'   : "http://www.pwsweather.com/pwsupdate/pwsupdate.php?"} 

class FailedPost(IOError):
    """Raised when a post fails, usually because of a login problem"""

class SkippedPost(Exception):
    """Raised when a post is skipped."""

#===============================================================================
#                          Abstract base class REST
#===============================================================================

class REST(object):
    """Abstract base class for RESTful protocols."""
    
    rain_query = "SELECT SUM(rain) FROM archive WHERE dateTime>? AND dateTime<=?"
    
    def extractRecordFrom(self, archive, time_ts):
        """Get a record from the archive database. 
        
        This is a general version that works for:
          - WeatherUnderground
          - PWSweather
          - CWOP
        It can be overridden and specialized for additional protocols.
        
        archive: An instance of weewx.archive.Archive
        
        time_ts: The record desired as a unix epoch time.
        
        returns: A dictionary of weather values"""
        
        sod_ts = weeutil.weeutil.startOfDay(time_ts)
        
        sqlrec = archive.getSql("""SELECT dateTime, usUnits, barometer, outTemp, outHumidity, 
                                windSpeed, windDir, windGust, dewpoint FROM archive WHERE dateTime=?""", time_ts)
    
        datadict = {}
        for (i, _key) in enumerate(('dateTime', 'usUnits', 'barometer', 'outTemp', 'outHumidity', 
                                    'windSpeed', 'windDir', 'windGust', 'dewpoint')):
            datadict[_key] = sqlrec[i]
    
        if datadict['usUnits'] != 1:
            raise NotImplementedError, "Only U.S. Units are supported for the Ambient protocol."
        
        # CWOP says rain should be "rain that fell in the past hour". 
        # Presumably, this is exclusive of the archive
        # record 60 minutes before, so the SQL statement is exclusive
        # on the left, inclusive on the right. Strictly speaking, this
        # may or may not be what they mean over a DST boundary.
        datadict['rain'] = archive.getSql(REST.rain_query,
                                         time_ts - 3600.0, time_ts)[0]
        
        # NB: The WU considers the archive with time stamp 00:00
        # (midnight) as (wrongly) belonging to the current day
        # (instead of the previous day). But, it's their site, so
        # we'll do it their way.  That means the SELECT statement is
        # inclusive on both time ends:
        datadict['dailyrain'] = archive.getSql(REST.rain_query, 
                                              sod_ts, time_ts)[0]
                                              
        datadict['rain24'] = archive.getSql(REST.rain_query,
                                            time_ts - 24*3600.0, time_ts)[0]
        return datadict
    
#===============================================================================
#                             class Ambient
#===============================================================================

class Ambient(REST):
    """Upload using the Ambient protocol. 
    
    For details of the Ambient upload protocol,
    see http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
    
    For details on how urllib2 works, see "urllib2 - The Missing Manual"
    at http://www.voidspace.org.uk/python/articles/urllib2.shtml
    """

    # Types and formats of the data to be published:
    _formats = {'dateTime'    : 'dateutc=%s',
                'barometer'   : 'baromin=%06.3f',
                'outTemp'     : 'tempf=%05.1f',
                'outHumidity' : 'humidity=%03.0f',
                'windSpeed'   : 'windspeedmph=%03.0f',
                'windDir'     : 'winddir=%03.0f',
                'windGust'    : 'windgustmph=%03.0f',
                'dewpoint'    : 'dewptf=%03.0f',
                'rain'        : 'rainin=%04.2f',
                'dailyrain'   : 'dailyrainin=%05.2f'}


    def __init__(self, site, site_dict):
        """Initialize for a given upload site.
        
        site: The upload site ('Wunderground' or 'PWSweather')
        
        site_dict: A dictionary holding any information needed for the upload
        site. Generally, this includes:       
            {'station'   : "The name of the station (e.g., "KORHOODR3") as a string",
             'password'  : "Password for the station",
             'http_prefix: "The URL of the upload point"
             'max_tries' : "Max # of tries before giving up"}
             
        There are defaults for http_prefix and max_tries. Generally, station
        and password are required.
        """
        
        self.site        = site
        self.station     = site_dict['station']
        self.password    = site_dict['password']
        self.http_prefix = site_dict.get('http_prefix', site_url[site])
        self.max_tries   = int(site_dict.get('max_tries', 3))

    def postData(self, archive, time_ts):
        """Post using the Ambient HTTP protocol

        archive: An instance of weewx.archive.Archive
        
        time_ts: The record desired as a unix epoch time."""
        
        _url = self.getURL(archive, time_ts)

        # Retry up to max_tries times:
        for _count in range(self.max_tries):
            # Now use an HTTP GET to post the data. Wrap in a try block
            # in case there's a network problem.
            try:
                _response = urllib2.urlopen(_url)
            except (urllib2.URLError, socket.error), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_ERR, "restful: Failed attempt #%d to upload to %s" % (_count+1, self.site))
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
            else:
                # No exception thrown, but we're still not done.
                # We have to also check for a bad station ID or password.
                # It will have the error encoded in the return message:
                for line in _response:
                    # PWSweather signals with 'ERROR', WU with 'INVALID':
                    if line.startswith('ERROR') or line.startswith('INVALID'):
                        # Bad login. No reason to retry. Log it and raise an exception.
                        syslog.syslog(syslog.LOG_ERR, "restful: %s returns %s. Aborting." % (self.site, line))
                        raise FailedPost, line
                # Does not seem to be an error. We're done.
                return
        else:
            # This is executed only if the loop terminates normally, meaning
            # the upload failed max_tries times. Log it.
            syslog.syslog(syslog.LOG_ERR, "restful: Failed to upload to %s" % self.site)
            raise IOError, "Failed ftp upload to site %s after %d tries" % (self.site, self.max_tries)

    def getURL(self, archive, time_ts):

        """Return an URL for posting using the Ambient protocol.
        
        archive: An instance of weewx.archive.Archive
        
        time_ts: The record desired as a unix epoch time.
        """
    
        record = self.extractRecordFrom(archive, time_ts)
        
        _liststr = ["action=updateraw", "ID=%s" % self.station, "PASSWORD=%s" % self.password ]
        
        # Go through each of the supported types, formatting it, then adding to _liststr:
        for _key in Ambient._formats.keys() :
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
                _liststr.append(Ambient._formats[_key] % v)
        # Add the software type and version:
        _liststr.append("softwaretype=weewx-%s" % weewx.__version__)
        # Now stick all the little pieces together with an ampersand between them:
        _urlquery='&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url=self.http_prefix + _urlquery
        return _url


#===============================================================================
#                             class CWOP
#===============================================================================

class CWOP(REST):
    """Upload using the CWOP protocol. """

    def __init__(self, site, site_dict):
        """Initialize for a post to CWOP.
        
        site: The upload site ("CWOP")
        
        site_dict: A dictionary holding any information needed for the CWOP
        protocol. Generally, this includes:       
            {'station'   : "The name of the station (e.g., "CW1234") as 
                            a string [Required]",
             'server     : "List of APRS server and port in the form 
                            cwop.aprs.net:14580 [Required]", 
             'latitude'  : "station latitude [Required]",
             'longitude' : "station longitude [Required]",
             'hardware'  : "station hardware (eg, VantagePro) [Required]
             'passcode'  : "Passcode for your station [Optional. APRS only]",
             'interval'  : "The interval in seconds between posts [Optional. 
                            Default is 0 (send every post)]",
             'stale'     : "How old a record can be before it will not be 
                            used for a catchup [Optional. Default is 1800]",
             'max_tries' : "Max # of tries before giving up [Optional. Default is 3]",
             }
             
        CWOP does not like heavy traffic on their servers, so they encourage
        posts roughly every 15 minutes and at most every 5 minutes. So,
        key 'interval' should be set to no less than 300, but preferably 900.
        Setting it to zero will cause every archive record to be posted.
        """
        self.site      = site
        self.station   = site_dict['station'].upper()
        if self.station[0:2] in ('CW', 'DW'):
            self.passcode = "-1"
        else:
            self.passcode = site_dict['passcode']
        self.server    = weeutil.weeutil.option_as_list(site_dict['server'])
        self.latitude  = site_dict.as_float('latitude')
        self.longitude = site_dict.as_float('longitude')
        self.hardware  = site_dict['hardware']
        self.interval  = int(site_dict.get('interval', 0))
        self.stale     = int(site_dict.get('stale', 1800))
        self.max_tries = int(site_dict.get('max_tries', 3))
        
        self._lastpost = None
        
    def postData(self, archive, time_ts):
        """Post data to CWOP, using the CWOP protocol."""
        
        _last_ts = archive.lastGoodStamp()

        # There are a variety of reasons to skip a post to CWOP.

        # 1. They do not allow backfilling, so there is no reason
        # to post anything other than the latest record:
        if time_ts != _last_ts:
            raise SkippedPost, "CWOP: Record %s is not last record" %\
                    (weeutil.weeutil.timestamp_to_string(time_ts), )

        # 2. No reason to post an old out-of-date record.
        _how_old = time.time() - time_ts
        if _how_old > self.stale:
            raise SkippedPost, "CWOP: Record %s is stale (%d > %d)." %\
                    (weeutil.weeutil.timestamp_to_string(time_ts), _how_old, self.stale)
        
        # 3. Finally, we don't want to post more often than the interval
        if self._lastpost and time_ts - self._lastpost < self.interval:
            raise SkippedPost, "CWOP: Wait interval (%d) has not passed." %\
                    (self.interval, )
        
        # Get the data record for this time:
        _record = self.extractRecordFrom(archive, time_ts)
        
        # Get the login and packet strings:
        _login = self.getLoginString()
        _tnc_packet = self.getTNCPacket(_record)
        
        # Get a socket connection:
        _sock = self._get_connect()

        # Send the login:
        _resp = self._send(_sock, _login)
        print "Login response:",_resp

        # And now the packet
        _resp = self._send(_sock, _tnc_packet)
        print "Packet response:",_resp
        
        try:
            _sock.close()
        except:
            pass

        self._lastpost = time_ts
        

    def getLoginString(self):
        login = "user %s pass %s vers weewx %s\r\n" % (self.station, self.passcode, weewx.__version__ )
        return login
    
    def getTNCPacket(self, record):
        """Form the TNC2 packet used by CWOP."""
        
        # Preamble to the TNC packet:
        prefix = "%s>APRS,TCPIP*:" % (self.station, )

        # Time:
        time_tt = time.gmtime(record['dateTime'])
        time_str = time.strftime("@%d%H%Mz", time_tt)

        # Position:
        lat_str = weeutil.weeutil.latlon_string(self.latitude, ('N', 'S'), 'lat')
        lon_str = weeutil.weeutil.latlon_string(self.longitude, ('E', 'W'), 'lon')
        latlon_str = '%s%s%s/%s%s%s' % (lat_str + lon_str)

        # Wind and temperature
        wt_list = []
        for obs_type in ('windDir', 'windSpeed', 'windGust', 'outTemp'):
            wt_list.append("%03d" % record[obs_type] if record[obs_type] is not None else '...')
        wt_str = "_%s/%sg%st%s" % tuple(wt_list)

        # Rain
        rain_list = []
        for obs_type in ('rain', 'rain24', 'dailyrain'):
            rain_list.append("%03d" % (record[obs_type]*100.0) if record[obs_type] is not None else '...')
        rain_str = "r%sp%sP%s" % tuple(rain_list)
        
        # Barometer:
        if record['barometer'] is None:
            baro_str = "b....."
        else:
            # Figure out what unit type barometric pressure is in for this record:
            baro_unit = weewx.units.getStandardUnitType(record['usUnits'], 'barometer')
            # Convert to millibars:
            baro = weewx.units.convert((record['barometer'], baro_unit), 'mbar')
            baro_str = "b%5d" % (baro[0]*10.0)

        # Humidity:
        humidity = record['outHumidity']
        if humidity is None:
            humid_str = "h.."
        else:
            humid_str = ("h%2d" % humidity) if humidity != 100.0 else "h00"

        # Station hardware:
        hardware_str = ".DsVP" if self.hardware=="VantagePro" else ".Unkn"
        
        tnc_packet = prefix + time_str + latlon_str + wt_str +\
                     rain_str + baro_str + humid_str + hardware_str + "\r\n"

        return tnc_packet
    

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
                    syslog.syslog(syslog.LOG_ERR, "restful: Connection attempt #%d failed to %s server %s:%d" % (_count+1, self.site, server, port))
                    syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "restful: Connected to %s server %s:%d" % (self.site, server, port))
                    return sock
                # Couldn't connect on this attempt. Close it, try again.
                try:
                    sock.close()
                except:
                    pass
            # If we got here, that server didn't work. Log it and go on to the next one.
            syslog.syslog(syslog.LOG_ERR, "restful: Unable to connect to %s server %s:%d" % (self.site, server, port))

        # If we got here. None of the servers worked. Raise an exception
        raise IOError, "Unable to obtain a socket connection to %s" % (self.site,)
     
    def _send(self, sock, msg):
        
        for _count in range(self.max_tries):

            try:
                sock.send(msg)
            except (IOError, socket.error), e:
                # Unsuccessful. Log it and go around again for another try
                syslog.syslog(syslog.LOG_ERR, "restful: Attempt #%d failed to send to %s" % (_count+1, self.site))
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
            else:
                _resp = sock.recv(1024)
                return _resp
        else:
            # This is executed only if the loop terminates normally, meaning
            # the send failed max_tries times. Log it.
            syslog.syslog(syslog.LOG_ERR, "restful: Failed to upload to %s" % self.site)
            raise IOError, "Failed CWOP upload to site %s after %d tries" % (self.site, self.max_tries)
    

#===============================================================================
#                             class RESTThread
#===============================================================================

class RESTThread(threading.Thread):
    """Dedicated thread for publishing weather data using RESTful protocol.
    
    Inherits from threading.Thread.

    Basically, it watches a queue, and if anything appears in it, it publishes it.
    The queue should be populated with the timestamps of the data records to be published.
    """
    def __init__(self, archive, queue, station_list):
        """Initialize an instance of RESTThread.
        
        archive: The archive database. Usually an instance of weewx.archive.Archive 
        
        queue: An instance of Queue.Queue where the timestamps will appear

        station_list: An iterable list of RESTStations.
        """
        threading.Thread.__init__(self, name="RESTThread")
        # In the strange vocabulary of Python, declaring yourself a "daemon thread"
        # allows the program to exit even if this thread is running:
        self.setDaemon(True)
        self.archive = archive
        self.queue   = queue # Fifo queue where new records will appear
        self.station_list = station_list

    def run(self):
        while True :
            # This will block until something appears in the queue:
            time_ts = self.queue.get()
            
            # A 'None' value appearing in the queue is our signal to exit
            if time_ts is None:
                return
            
            # This string is just used for logging:
            time_str = weeutil.weeutil.timestamp_to_string(time_ts)
            
            # Cycle through all the RESTful stations in the list:
            for station in self.station_list:
    
                # Post the data to the upload site. Be prepared to catch any exceptions:
                try :
                    station.postData(self.archive, time_ts)
                # The urllib2 library throws exceptions of type urllib2.URLError, a subclass
                # of IOError. Hence all relevant exceptions are caught by catching IOError.
                # Starting with Python v2.6, socket.error is a subclass of IOError as well,
                # but we keep them separate to support V2.5:
                except (IOError, socket.error), e:
                    syslog.syslog(syslog.LOG_ERR, "restful: Unable to publish record %s to %s station %s" % (time_str, station.site, station.station))
                    syslog.syslog(syslog.LOG_ERR, "   ****  %s" % e)
                    if hasattr(e, 'reason'):
                        syslog.syslog(syslog.LOG_ERR, "   ****  Failed to reach server. Reason: %s" % e.reason)
                    if hasattr(e, 'code'):
                        syslog.syslog(syslog.LOG_ERR, "   ****  Failed to reach server. Error code: %s" % e.code)
                except SkippedPost, e:
                    syslog.syslog(syslog.LOG_DEBUG, "restful: Skipped record %s to %s station %s" % (time_str, station.site, station.station))
                    syslog.syslog(syslog.LOG_DEBUG, "   ****  %s" % (e,))
                except Exception, e:
                    syslog.syslog(syslog.LOG_CRIT, "restful: Unrecoverable error when posting record %s to %s station %s" % (time_str, station.site, station.station))
                    syslog.syslog(syslog.LOG_CRIT, "   ****  %s" % (e,))
                    syslog.syslog(syslog.LOG_CRIT, "   ****  Thread terminating.")
                    raise
                else:
                    syslog.syslog(syslog.LOG_INFO, "restful: Published record %s to %s station %s" % (time_str, station.site, station.station))


#===============================================================================
#                                 Testing
#===============================================================================

if __name__ == '__main__':
           
    import sys
    import configobj
    import os.path
    from optparse import OptionParser
    import Queue
    
    import weewx.archive
    
    def main():
        usage_string ="""Usage: 
        
        restful.py config_path upload-site [--today] [--last]
        
        Arguments:
        
          config_path: Path to weewx.conf
          
          upload-site: Either "Wunderground", "PWSweather", or "CWOP" 
          
        Options:
        
            --today: Publish all of today's day
            
            --last: Just do the last archive record. [default]
          """
        parser = OptionParser(usage=usage_string)
        parser.add_option("-t", "--today", action="store_true", dest="do_today", help="Publish today\'s records")
        parser.add_option("-l", "--last", action="store_true", dest="do_last", help="Publish the last archive record only")
        (options, args) = parser.parse_args()
        
        if len(args) < 2:
            sys.stderr.write("Missing argument(s).\n")
            sys.stderr.write(parser.parse_args(["--help"]))
            exit()
            
        if options.do_today and options.do_last:
            sys.stderr.write("Choose --today or --last, not both\n")
            sys.stderr.write(parser.parse_args(["--help"]))
            exit()
    
        if not options.do_today and not options.do_last:
            options.do_last = True
            
        config_path = args[0]
        site        = args[1]
        
        weewx.debug = 1
        
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        # Open up the main database archive
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
        
        stop_ts  = archive.lastGoodStamp()
        start_ts = weeutil.weeutil.startOfDay(stop_ts) if options.do_today else stop_ts
        
        publish(config_dict, site, archive, start_ts, stop_ts )

    def publish(config_dict, site, archive, start_ts, stop_ts):
        """Publishes records to site 'site' from start_ts to stop_ts. 
        Makes a useful test."""
        
        site_dict = config_dict['RESTful'][site]
        site_dict['latitude']  = config_dict['Station']['latitude']
        site_dict['longitude'] = config_dict['Station']['longitude']
        site_dict['hardware']  = config_dict['Station']['station_type']

        stationName = site_dict['station']
        
        # Instantiate an instance of the class that implements the
        # protocol used by this site:
        obj_class = 'weewx.restful.' + site_dict['protocol']
        station = weeutil.weeutil._get_object(obj_class, site, site_dict) 

        # Create the queue into which we'll put the timestamps of new data
        queue = Queue.Queue()
        # Start up the thread:
        thread = RESTThread(archive, queue, [station])
        thread.start()

        for row in archive.genSql("SELECT dateTime FROM archive WHERE dateTime >=? and dateTime <= ?", start_ts, stop_ts):
            ts = row['dateTime']
            print "Posting station %s for time %s" % (stationName, weeutil.weeutil.timestamp_to_string(ts))
            queue.put(ts)
            
        # Value 'None' signals to the thread to exit:
        queue.put(None)
        # Wait for exit:
        thread.join()
    
    main()
    