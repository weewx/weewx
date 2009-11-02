#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Publish weather data to the Weather Underground."""
import syslog
import time
import datetime
import threading
import urllib
import urllib2

import weewx
import weeutil.weeutil

def postData(archive, time_ts, station, password) :
    """Posts a data record on the Weather Underground, using their upload protocol.
    
    archive: An instance of weewx.archive.Archive
    
    time_ts: The timestamp of the record to be submitted to the WU.
    If 'None', then the last timestamp in the archive.
    
    station: The Weather Underground station name (e.g., 'KORHOODR3')
    
    password: Password for the station

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

    if not time_ts:
        time_ts = archive.lastGoodStamp()
        
    sod_ts = weeutil.weeutil.startOfDay(time_ts)
    
    sqlrec = archive.getSql("SELECT dateTime, usUnits, interval, barometer, outTemp, outHumidity, "\
                             "windSpeed, windDir, windGust, dewpoint "\
                             "FROM archive WHERE dateTime=?", time_ts)
    
    datarec = dict(sqlrec)

    unitsystem = datarec['usUnits']
    if unitsystem != weewx.IMPERIAL :
        raise weewx.UnsupportedFeature, "Only Imperial Units are supported for the Weather Underground."
    
    # WU says rain should be "accumulated rainfall over the last 60 minutes". Presumably, this
    # is exclusive of the archive record 60 minutes before, so the SQL statement is
    # exclusive on the left, inclusive on the right. Strictly speaking, this may or may not
    # be what they mean over a DST boundary.
    datarec['rain'] = archive.getSql("SELECT SUM(rain) AS rain FROM archive WHERE dateTime>? AND dateTime<=?",
                                     time_ts - 3600.0, time_ts)['rain']
    
    # NB: The WU considers the archive with time stamp 00:00 (midnight) as (wrongly) belonging to
    # the current day (instead of the previous day). But, it's their site, so we'll do it their way.
    # That means the SELECT statement is inclusive on both time ends:
    datarec['dailyrain'] = archive.getSql("SELECT SUM(rain) AS dailyrain FROM archive WHERE dateTime>=? AND dateTime<=?", 
                                          sod_ts, time_ts)['dailyrain']
                                          
    _liststr = ["action=updateraw", "ID=%s" % station, "PASSWORD=%s" % password ]
    
    # Go through each of the supported types, formatting it, then adding to _liststr:
    for _key in _formats.keys() :
        v = datarec[_key]
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

    # This string is just used for logging:
    time_str = weeutil.weeutil.timestamp_to_string(datarec['dateTime'])

    try :
        # Now use an HTTP GET to post the data on the Weather Underground
        _wudata = urllib2.urlopen(_url)
        moreinfo = _wudata.read()
        if moreinfo == 'success\n':
            syslog.syslog(syslog.LOG_INFO, "wunderground: Published record %s to station %s" % (time_str, station))
        else:
            syslog.syslog(syslog.LOG_INFO, "wunderground: Unable to publish record %s to station %s." % (time_str, station))
            syslog.syslog(syslog.LOG_INFO, "wunderground: Reason: %s" % (moreinfo,))
    except urllib2.URLError, e :
        syslog.syslog(syslog.LOG_ERR, "wunderground: Unable to publish record %s to station %s" % (time_str, station))
        if hasattr(e, 'reason'):
            syslog.syslog(syslog.LOG_ERR, "wunderground: Failed to reach server. Reason: %s" % e.reason)
        elif hasattr(e, 'code'):
            syslog.syslog(syslog.LOG_ERR, "wunderground: Failed to reach server. Error code: %s" % e.code)


class WunderThread(threading.Thread):
    """Dedicated thread for publishing weather data on the Weather Underground.
    
    Inherits from threading.Thread. 
    Basically, it watches a queue, and if anything appears it publishes it.
    The queue should be populated with a 2-way tuple, where the first member is
    an instance of weewx.archive.Archive, and the second is a timestamp with the
    time of the data record to be published.
    """
    def __init__(self, station, password, queue):
        threading.Thread.__init__(self, name="WunderThread")
        # In the strange vocabulary of Python, declaring yourself a "daemon thread"
        # allows the program to exit even if this thread is running:
        self.setDaemon(True)
        self.station  = station
        self.password = password
        self.queue    = queue
        self.start()

    def run(self):
        while 1 :
            # This will block until something appears in the queue:
            archive, time_ts = self.queue.get()
            # Post the data to WU:
            postData(archive, time_ts, self.station, self.password)

if __name__ == '__main__':
           
    import sys
    import configobj
    import os.path
    
    import weewx
    import weewx.archive
    import weeutil.weeutil
    
    def backfill_today(config_path):
        
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        stationName = config_dict['Wunderground']['station']
        
        # Open up the main database archive
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
        
        time_ts = archive.lastGoodStamp()
        sod = weeutil.weeutil.startOfDay(time_ts)
        
        for row in archive.genSql("SELECT dateTime FROM archive WHERE dateTime >=? and dateTime <= ?", sod, time_ts):
            ts = row['dateTime']
            print "Posting station %s for time %s" % (stationName, weeutil.weeutil.timestamp_to_string(ts))
            postData(archive, ts, **config_dict['Wunderground'])

        
    if len(sys.argv) < 2 :
        print "Usage: wunderground.py path-to-configuration-file"
        exit()
        
    backfill_today(sys.argv[1])
