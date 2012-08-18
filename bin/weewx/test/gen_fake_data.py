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
import math
import os.path
import sys
import syslog
import time
import unittest

import configobj

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

class StatsTestBase(unittest.TestCase):

    def setUp(self):

        weewx.debug = 1
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        try :
            config_dict = configobj.ConfigObj(self.config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % self.config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % self.config_path)
            raise
        else:
            print "Using configuration file:  ", self.config_path

        self.archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                            config_dict['StdArchive']['archive_file'])
        self.statsFilename   = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                            config_dict['StdArchive']['stats_file'])
        
        print "Test archive database path:", self.archiveFilename
        print "Test stats database path:  ", self.statsFilename

        # If the archive has not been configured, an exception will be raised:
        try:
            self.archive = weewx.archive.Archive(self.archiveFilename)
        except StandardError:
            # The archive was not configured. Go configure it:
            self.configDatabases(stats_types=config_dict['StdArchive']['stats_types'])

        self.stats = weewx.stats.StatsDb(self.statsFilename)
        self.assertEqual(sorted(self.stats.statsTypes), sorted(config_dict['StdArchive']['stats_types']))

    def configDatabases(self, stats_types):
        """Configures the main and stats databases."""

        # Configure the main database:            
        weewx.archive.config(self.archiveFilename)
        # Now open it
        self.archive = weewx.archive.Archive(self.archiveFilename)
        # Because this can generate voluminous log information,
        # suppress all but the essentials:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_ERR))
        
        # Now generate the fake records to populate the database:
        t1= time.time()
        self.archive.addRecord(self.genFakeRecords())
        t2 = time.time()
        print "Time to create synthetic archive database = %6.2fs" % (t2-t1,)
        # Now go back to regular logging:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        
        # Remove any old stats database
        try:
            os.remove(self.statsFilename)
        except:
            pass

        # Configure a new stats databsae:            
        weewx.stats.config(self.statsFilename, stats_types=stats_types)
        self.stats = weewx.stats.StatsDb(self.statsFilename)
        t1 = time.time()
        # Now backfill the stats database from the main archive database.
        weewx.stats.backfill(self.archive, self.stats)
        t2 = time.time()
        print "Time to backfill stats database from it =   %6.2fs" % (t2-t1,)
        
    def genFakeRecords(self):
        self.count = 0
        
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
        
            self.saltWithNulls(record)
                        
            yield record
        
    def saltWithNulls(self, record):
        # Make every 71st observation (a prime number) a null. This is a deterministic algorithm, so it
        # will produce the same results every time.
        for obs_type in filter(lambda x : x not in ['dateTime', 'usUnits', 'interval'], record):
            self.count+=1
            if self.count%71 == 0:
                record[obs_type] = None
            
