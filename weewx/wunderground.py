#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Publish weather data to the Weather Underground."""
import syslog
import datetime
import threading
import urllib
import urllib2

import weewx
import weeutil.weeutil

class WunderStation(object):
    """Manages interactions with the Weather Underground"""

    def __init__(self, station, password):
        """Initialize with a given station.
        
        station: The name of the Weather Underground station (e.g., "KORHOODR3") as a string

        password: Password for the station"""
        
        self.station  = station
        self.password = password

    def extractRecordFrom(self, archive, time_ts):
        """Get a record from the archive database.
        
        archive: An instance of weewx.archive.Archive
        
        time_ts: The record desired as a unix epoch time.
        
        returns: A dictionary containing the values needed to post to the Weather Underground"""
        
        sod_ts = weeutil.weeutil.startOfDay(time_ts)
        
        sqlrec = archive.getSql("""SELECT dateTime, usUnits, barometer, outTemp, outHumidity, 
                                windSpeed, windDir, windGust, dewpoint FROM archive WHERE dateTime=?""", time_ts)

        datadict = {}
        for (i, _key) in enumerate(('dateTime', 'usUnits', 'barometer', 'outTemp', 'outHumidity', 
                                    'windSpeed', 'windDir', 'windGust', 'dewpoint')):
            datadict[_key] = sqlrec[i]

        if datadict['usUnits'] != 1:
            raise NotImplementedError, "Only U.S. Units are supported for the Weather Underground."
        
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


    def postData(self, record) :
        """Posts a data record on the Weather Underground, using their upload protocol.
        
        record: A dictionary holding the data values.
        
        For details of the Weather Underground upload protocol,
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
                    'dailyrain'   : 'dailyrainin=%05.2f'
                    }

        _liststr = ["action=updateraw", "ID=%s" % self.station, "PASSWORD=%s" % self.password ]
        
        # Go through each of the supported types, formatting it, then adding to _liststr:
        for _key in _formats.keys() :
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
                _liststr.append(_formats[_key] % v)
        # Add the software type and version:
        _liststr.append("softwaretype=weewx-%s" % weewx.__version__)
        # Now stick all the little pieces together with an ampersand between them:
        _urlquery='&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url="http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php?" + _urlquery

        # Now use an HTTP GET to post the data on the Weather Underground
        _wudata = urllib2.urlopen(_url)
        moreinfo = _wudata.read()
        if moreinfo == 'success\n':
            return
        else:
            raise IOError, "Weather Underground returns: \"%s\"" % (moreinfo.strip(),)
    
class WunderThread(threading.Thread):
    """Dedicated thread for publishing weather data on the Weather Underground.
    
    Inherits from threading.Thread.

    Basically, it watches a queue, and if anything appears in it, it publishes it.
    The queue should be populated with the timestamps of the data records to be published.
    """
    def __init__(self, archive, queue, station, password):
        """Initialize an instance of WunderThread.
        
        archive: The archive database. Usually an instance of weewx.archive.Archive 
        
        queue: An instance of Queue.Queue where the timestamps will appear
        
        station: The Weather Underground station to which data is to be published
        (e.g., 'KORHOODR3')
        
        password: The password for the station.
        """
        threading.Thread.__init__(self, name="WunderThread")
        # In the strange vocabulary of Python, declaring yourself a "daemon thread"
        # allows the program to exit even if this thread is running:
        self.setDaemon(True)
        self.WUstation = WunderStation(station, password)
        self.archive   = archive
        self.queue     = queue # Fifo queue where new records will appear

    def run(self):
        while True :
            # This will block until something appears in the queue:
            time_ts = self.queue.get()
            
            # Go get the data from the archive for the requested time:
            record = self.WUstation.extractRecordFrom(self.archive, time_ts)
            
            # This string is just used for logging:
            time_str = weeutil.weeutil.timestamp_to_string(record['dateTime'])
    
            # Post the data to the WU. Be prepared to catch any exceptions:
            try :
                self.WUstation.postData(record)
                syslog.syslog(syslog.LOG_INFO, "wunderground: Published record %s to station %s" % (time_str, self.WUstation.station))
    
            # The urllib2 library throws exceptions of type urllib2.URLError, a subclass
            # of IOError. Hence all relevant exceptions are caught by catching IOError:
            except IOError, e :
                syslog.syslog(syslog.LOG_ERR, "wunderground: Unable to publish record %s to station %s" % (time_str, self.WUstation.station))
                if hasattr(e, 'reason'):
                    syslog.syslog(syslog.LOG_ERR, "wunderground: Failed to reach server. Reason: %s" % e.reason)
                if hasattr(e, 'code'):
                    syslog.syslog(syslog.LOG_ERR, "wunderground: Failed to reach server. Error code: %s" % e.code)


if __name__ == '__main__':
           
    import sys
    import configobj
    import os.path
    
    import weewx
    import weewx.archive
    import weeutil.weeutil
    
    def backfill_today(config_path):
        """Publishes all of today's records to the WU. Makes a useful test."""
        
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        stationName = config_dict['Wunderground']['station']
        password    = config_dict['Wunderground']['password']
        
        wustation = WunderStation(stationName, password)

        # Open up the main database archive
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
        
        time_ts = archive.lastGoodStamp()
        sod = weeutil.weeutil.startOfDay(time_ts)
        
        for row in archive.genSql("SELECT dateTime FROM archive WHERE dateTime >=? and dateTime <= ?", sod, time_ts):
            ts = row['dateTime']
            print "Posting station %s for time %s" % (stationName, weeutil.weeutil.timestamp_to_string(ts))
            record = wustation.extractRecordFrom(archive, ts)
            wustation.postData(record)

        
    if len(sys.argv) < 2 :
        print "Usage: wunderground.py path-to-configuration-file"
        exit()
        
    backfill_today(sys.argv[1])
