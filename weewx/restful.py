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

import weewx
import weeutil.weeutil

site_url = {'Wunderground' : "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php?",
            'PWSweather'   : "http://www.pwsweather.com/pwsupdate/pwsupdate.php?"} 

class RESTful(object):
    """Abstract base class for interacting with a RESTful site.
    
    Specializing classes should override member function getURL()
    """

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

    def postData(self, record):
        """Post using a RESTful protocol"""

        _url = self.getURL(record)
        print _url

        for _count in range(self.max_tries):
            # Now use an HTTP GET to post the data on the Weather Underground
            try:
                _response = urllib2.urlopen(_url)
            except (urllib2.URLError, socket.error), e:
                syslog.syslog(syslog.LOG_ERR, "restful: Failed attempt #%d to upload to %s" % (_count+1, self.site))
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: s" % (e,))
                if _count >= self.max_tries -1 :
                    syslog.syslog(syslog.LOG_ERR, "restful: Failed to upload to %s" % self.site)
                    raise
            else:
                if weewx.debug:
                    syslog.syslog(syslog.LOG_DEBUG, "restful: Uploaded to %s" % (self.site,))
                break
    
    @staticmethod
    def extractRecordFrom(archive, time_ts):
        """Get a record from the archive database. 
        
        This version is really designed for the Ambient protocol. If new
        protocols get added, it should probably be at least generalized,
        if not overridden by specializing classes.
        
        archive: An instance of weewx.archive.Archive
        
        time_ts: The record desired as a unix epoch time.
        
        returns: A dictionary containing the values needed for the Ambient protocol"""
        
        sod_ts = weeutil.weeutil.startOfDay(time_ts)
        
        sqlrec = archive.getSql("""SELECT dateTime, usUnits, barometer, outTemp, outHumidity, 
                                windSpeed, windDir, windGust, dewpoint FROM archive WHERE dateTime=?""", time_ts)
    
        datadict = {}
        for (i, _key) in enumerate(('dateTime', 'usUnits', 'barometer', 'outTemp', 'outHumidity', 
                                    'windSpeed', 'windDir', 'windGust', 'dewpoint')):
            datadict[_key] = sqlrec[i]
    
        if datadict['usUnits'] != 1:
            raise NotImplementedError, "Only U.S. Units are supported for the Ambient protocol."
        
        # WU says rain should be "accumulated rainfall over the last
        # 60 minutes". Presumably, this is exclusive of the archive
        # record 60 minutes before, so the SQL statement is exclusive
        # on the left, inclusive on the right. Strictly speaking, this
        # may or may not be what they mean over a DST boundary.
        datadict['rain'] = archive.getSql("SELECT SUM(rain) FROM archive WHERE dateTime>? AND dateTime<=?",
                                         time_ts - 3600.0, time_ts)[0]
        
        # NB: The WU considers the archive with time stamp 00:00
        # (midnight) as (wrongly) belonging to the current day
        # (instead of the previous day). But, it's their site, so
        # we'll do it their way.  That means the SELECT statement is
        # inclusive on both time ends:
        datadict['dailyrain'] = archive.getSql("SELECT SUM(rain) FROM archive WHERE dateTime>=? AND dateTime<=?", 
                                              sod_ts, time_ts)[0]
        return datadict

class Ambient(RESTful):
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

    def getURL(self, record):

        """Return an URL for posting using the Ambient protocol.
        
        record: A dictionary holding the data values.
        """
    
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


class RESTThread(threading.Thread):
    """Dedicated thread for publishing weather data using the Ambient RESTful protocol.
    
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
            
            # Go get the data from the archive for the requested time:
            record = RESTful.extractRecordFrom(self.archive, time_ts)
            
            # This string is just used for logging:
            time_str = weeutil.weeutil.timestamp_to_string(record['dateTime'])
            
            for station in self.station_list:
    
                # Post the data to the upload site. Be prepared to catch any exceptions:
                try :
                    station.postData(record)
                    syslog.syslog(syslog.LOG_INFO, "restful: Published record %s to %s station %s" % (time_str, station.site, station.station))
        
                # The urllib2 library throws exceptions of type urllib2.URLError, a subclass
                # of IOError. Hence all relevant exceptions are caught by catching IOError:
                except IOError, e :
                    syslog.syslog(syslog.LOG_ERR, "restful: Unable to publish record %s to %s station %s" % (time_str, station.site, station.station))
                    if hasattr(e, 'reason'):
                        syslog.syslog(syslog.LOG_ERR, "   ****  Failed to reach server. Reason: %s" % e.reason)
                    if hasattr(e, 'code'):
                        syslog.syslog(syslog.LOG_ERR, "   ****  Failed to reach server. Error code: %s" % e.code)


if __name__ == '__main__':
           
    import sys
    import configobj
    import os.path
    
    import weewx
    import weewx.archive
    import weeutil.weeutil
    
    def backfill_today(config_path, site):
        """Publishes all of today's records to the WU. Makes a useful test."""
        
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        stationName = config_dict['RESTful'][site]['station']
        password    = config_dict['RESTful'][site]['password']
        
        station = Ambient(site, config_dict['RESTful'][site])

        # Open up the main database archive
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
        
        time_ts = archive.lastGoodStamp()
        sod = weeutil.weeutil.startOfDay(time_ts)
        
        for row in archive.genSql("SELECT dateTime FROM archive WHERE dateTime >=? and dateTime <= ?", sod, time_ts):
            ts = row['dateTime']
            print "Posting station %s for time %s" % (stationName, weeutil.weeutil.timestamp_to_string(ts))
            record = RESTful.extractRecordFrom(archive, ts)
            station.postData(record)

        
    if len(sys.argv) < 3 :
        print """Usage: restful.py path-to-configuration-file upload-site\n"""\
              """Where:   upload-site is "Wunderground" or "PWSweather" """
        exit()
        
    backfill_today(sys.argv[1], sys.argv[2])
