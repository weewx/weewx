# -*- coding: utf-8 -*-
#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Generate fake data used by the tests.

The idea is to create a deterministic database that reports
can be run against, resulting in predictable, expected results"""

from __future__ import with_statement
import math
import syslog
import time

import schemas.wview
import weedb
import weewx.manager

# Roughly nine months of data:
start_tt = (2010,1,1,0,0,0,0,0,-1)
stop_tt  = (2010,9,3,11,20,0,0,0,-1)
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

schema = schemas.wview.schema

def configDatabases(config_dict, database_type):
    config_dict['DataBindings']['wx_binding']['database'] = "archive_" + database_type
    configDatabase(config_dict, 'wx_binding')
    config_dict['DataBindings']['alt_binding']['database'] = "alt_" + database_type
    configDatabase(config_dict, 'alt_binding', amplitude=0.5)

def configDatabase(config_dict, binding, amplitude=1.0, 
                   day_phase_offset=0.0, annual_phase_offset=0.0,
                   weather_phase_offset=0.0):
    """Configures the archive databases."""

    global schema

    # Check to see if it already exists and is configured correctly.
    try:
        with weewx.manager.open_manager_with_config(config_dict, binding)  as archive:
            if archive.firstGoodStamp() == start_ts and archive.lastGoodStamp() == stop_ts:
                # Database already exists. We're done.
                return
    except weedb.DatabaseError:
        pass
        
    # Delete anything that might already be there.
    try:
        weewx.manager.drop_database_with_config(config_dict, binding)
    except weedb.DatabaseError:
        pass
    
    # Need to build a new synthetic database. General strategy is to create the
    # archive data, THEN backfill with the daily summaries. This is faster than
    # creating the daily summaries on the fly. 
    # First, we need to modify the configuration dictionary that was passed in
    # so it uses the DBManager, instead of the daily summary manager
    monkey_dict = config_dict.dict()
    monkey_dict['DataBindings'][binding]['manager'] = 'weewx.manager.Manager'

    with weewx.manager.open_manager_with_config(monkey_dict, binding, initialize=True) as archive:
        
        # Because this can generate voluminous log information,
        # suppress all but the essentials:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_ERR))
        
        # Now generate and add the fake records to populate the database:
        t1= time.time()
        archive.addRecord(genFakeRecords(amplitude=amplitude, 
                                         day_phase_offset=day_phase_offset, 
                                         annual_phase_offset=annual_phase_offset,
                                         weather_phase_offset=weather_phase_offset))
        t2 = time.time()
        print "\nTime to create synthetic archive database = %6.2fs" % (t2-t1,)
        
    with weewx.manager.open_manager_with_config(config_dict, binding, initialize=True) as archive:

        # Now go back to regular logging:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # Backfill with daily summaries:
        t1 = time.time()
        nrecs, ndays = archive.backfill_day_summary()
        tdiff = time.time() - t1
        if nrecs:
            print "\nProcessed %d records to backfill %d day summaries in %.2f seconds" % (nrecs, ndays, tdiff)
        else:
            print "Daily summaries up to date."

    
def genFakeRecords(start_ts=start_ts, stop_ts=stop_ts, interval=interval, 
                   amplitude=1.0, day_phase_offset=0.0, annual_phase_offset=0.0,
                   weather_phase_offset=0.0):
    count = 0
    
    for ts in xrange(start_ts, stop_ts+interval, interval):
        daily_phase  = ((ts - start_ts) * 2.0 * math.pi + day_phase_offset)/ (3600*24.0)
        annual_phase = ((ts - start_ts) * 2.0 * math.pi + annual_phase_offset)/ (3600*24.0*365.0)
        weather_phase= ((ts - start_ts) * 2.0 * math.pi + weather_phase_offset)/ weather_cycle
        record = {}
        record['dateTime']  = ts
        record['usUnits']   = weewx.US
        record['interval']  = interval
        record['outTemp']   = 0.5 * amplitude * (-daily_temp_range * math.sin(daily_phase) - annual_temp_range*math.cos(annual_phase)) + avg_temp
        record['barometer'] = 0.5 * amplitude* weather_baro_range * math.sin(weather_phase) + avg_baro
        record['windSpeed'] = abs(amplitude * weather_wind_range * (1.0 + math.sin(weather_phase)))
        record['windDir'] = math.degrees(weather_phase) % 360.0
        record['windGust'] = 1.2 * record['windSpeed']
        record['windGustDir'] = record['windDir']
        if math.sin(weather_phase) > .95:
            record['rain'] = 0.02 * amplitude if math.sin(weather_phase) > 0.98 else 0.01 * amplitude
        else:
            record['rain'] = 0.0
    
        # Make every 71st observation (a prime number) a null. This is a deterministic algorithm, so it
        # will produce the same results every time.
        for obs_type in filter(lambda x : x not in ['dateTime', 'usUnits', 'interval'], record):
            count += 1
            if count % 71 == 0:
                record[obs_type] = None
                    
        yield record
