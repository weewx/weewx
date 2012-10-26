# -*- coding: utf-8 -*-
#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Generate fake data used by the tests.

The idea is to create a deterministic database that reports
can be run against, resulting in predictable, expected results"""

from __future__ import with_statement
import math
import syslog
import time

import user.schemas
import weedb
import weewx.archive
import weewx.stats

# One year of data:
start_tt = (2010,1,1,0,0,0,0,0,-1)
stop_tt  = (2011,1,1,0,0,0,0,0,-1)
start_ts = int(time.mktime(start_tt))
stop_ts  = int(time.mktime(stop_tt))

daily_temp_range = 40.0
annual_temp_range = 80.0
avg_temp = 40.0

# Four day weather cycle:
weather_cycle = 3600*24.0*4
weather_baro_range = 2.0
weather_wind_range = 10.0
weather_rain_total = 0.5 # This is inches per weather cycle
avg_baro = 30.0

# Archive interval in seconds:
interval = 600

def configDatabases(archive_db_dict, stats_db_dict):
    """Configures the main and stats databases."""

    # Check to see if it already exists and is configured correctly.
    try:
        with weewx.archive.Archive.open(archive_db_dict) as archive:
            if archive.firstGoodStamp() == start_ts and archive.lastGoodStamp() == stop_ts:
                # Database already exists. We're done.
                return
    except:
        pass
        
    # Delete anything that might already be there.
    try:
        weedb.drop(archive_db_dict)
    except:
        pass
    
    # Now build a new one:
    with weewx.archive.Archive.open_with_create(archive_db_dict, user.schemas.defaultArchiveSchema) as archive:
    
        # Because this can generate voluminous log information,
        # suppress all but the essentials:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_ERR))
        
        # Now generate and add the fake records to populate the database:
        t1= time.time()
        archive.addRecord(genFakeRecords())
        t2 = time.time()
        print "Time to create synthetic archive database = %6.2fs" % (t2-t1,)
        # Now go back to regular logging:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    
        # Delete any old stats database:
        try:
            weedb.drop(stats_db_dict)
        except weedb.NoDatabase:
            pass
        # Now create and configure a new one:
        with weewx.stats.StatsDb.open_with_create(stats_db_dict, user.schemas.defaultStatsTypes) as stats:
            t1 = time.time()
            # Now backfill the stats database from the main archive database.
            nrecs = stats.backfillFrom(archive)
            t2 = time.time()
            print "Time to backfill stats database with %d records: %6.2fs" % (nrecs, t2-t1)
    
def genFakeRecords():
    count = 0
    
    for ts in xrange(start_ts, stop_ts+interval, interval):
        daily_phase  = (ts - start_ts) * 2.0 * math.pi / (3600*24.0)
        annual_phase = (ts - start_ts) * 2.0 * math.pi / (3600*24.0*365.0)
        weather_phase= (ts - start_ts) * 2.0 * math.pi / weather_cycle
        record = {}
        record['dateTime']  = ts
        record['usUnits']   = weewx.US
        record['interval']  = interval
        record['outTemp']   = 0.5 * (-daily_temp_range*math.sin(daily_phase) - annual_temp_range*math.cos(annual_phase)) + avg_temp
        record['barometer'] = 0.5 * weather_baro_range*math.sin(weather_phase) + avg_baro
        record['windSpeed'] = abs(weather_wind_range*(1.0 + math.sin(weather_phase)))
        record['windDir'] = math.degrees(weather_phase) % 360.0
        record['windGust'] = 1.2*record['windSpeed']
        record['windGustDir'] = record['windDir']
        if math.sin(weather_phase) > .95:
            record['rain'] = 0.02 if math.sin(weather_phase) > 0.98 else 0.01
        else:
            record['rain'] = 0.0
    
        # Make every 71st observation (a prime number) a null. This is a deterministic algorithm, so it
        # will produce the same results every time.
        for obs_type in filter(lambda x : x not in ['dateTime', 'usUnits', 'interval'], record):
            count+=1
            if count%71 == 0:
                record[obs_type] = None
                    
        yield record
    
