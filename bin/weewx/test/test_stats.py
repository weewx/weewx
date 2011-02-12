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
"""Unit test module weewx.stats"""

import time
import math
import syslog
import tempfile
import unittest

import weewx.archive
import weewx.stats
import weeutil.weeutil

stats_types = ['barometer', 'outTemp', 'wind', 'rain']

daily_temp_range = 20.0
annual_temp_range = 40.0

# Four day weather cycle:
weather_cycle = 3600*24.0*4
weather_baro_range = 1.0
weather_wind_range = 10.0
weather_rain_total = 0.5 # This is inches per weather cycle

# Archive interval in seconds:
interval = 600

class StatsTest(unittest.TestCase):

    def setUp(self):
        syslog.openlog('stats_test', syslog.LOG_CONS)

        # Create an archive database
#        fa = tempfile.NamedTemporaryFile()
#        self.archiveFilename = fa.name
        self.archiveFilename = '/home/tkeffer/tmp/archive.sdb'
        try:
            self.archive = weewx.archive.Archive(self.archiveFilename)
        except StandardError:
            weewx.archive.config(self.archiveFilename)
            self.archive = weewx.archive.Archive(self.archiveFilename)
            # Because this can generate voluminous log information,
            # suppress all but the essentials:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_ERR))
            
            t1= time.time()
            self.archive.addRecord(self.genFakeRecords())
            t2 = time.time()
            print "Time to create synthetic archive database = %6.2f" % (t2-t1,)
            # Now go back to regular logging:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # Create a stats database:
#        fs = tempfile.NamedTemporaryFile()
#        self.statsFilename = fs.name
        self.statsFilename = '/home/tkeffer/tmp/stats.sdb'
        try:
            self.stats = weewx.stats.StatsDb(self.statsFilename)
        except:
            weewx.stats.config(self.statsFilename, stats_types = stats_types)
            self.stats = weewx.stats.StatsDb(self.statsFilename)
            t1 = time.time()
            weewx.stats.backfill(self.archive, self.stats)
            t2 = time.time()
            print "Time to backfill stats database from it   = %6.2f" % (t2-t1,)
        
        
    def genFakeRecords(self):
        # Generator function that generates one year of data:
        self.start_ts = int(time.mktime((2010,1,1,0,0,0,0,0,-1)))
        self.stop_ts  = int(time.mktime((2011,1,1,0,0,0,0,0,-1)) - 1)
        self.count = 0
        
        for ts in xrange(self.start_ts, self.stop_ts, interval):
            daily_phase  = (ts - self.start_ts) * 2.0 * math.pi / (3600*24.0)
            annual_phase = (ts - self.start_ts) * 2.0 * math.pi / (3600*24.0*365.0)
            weather_phase= (ts - self.start_ts) * 2.0 * math.pi / weather_cycle
            record = {}
            record['dateTime']  = ts
            record['usUnits']   = weewx.US
            record['interval']  = interval
            record['outTemp']   = daily_temp_range*math.sin(daily_phase) + annual_temp_range*math.sin(annual_phase) + 20.0
            record['barometer'] = weather_baro_range*math.sin(weather_phase) + 30.0
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
        # Make every 100th observation a null. This is a deterministic algorithm, so it
        # can be reproduced.
        for obs_type in filter(lambda x : x not in ['dateTime', 'usUnits', 'interval'], record):
            self.count+=1
            if self.count%100 == 0:
                record[obs_type] = None
                
    def test_types(self):
        self.assertEqual(sorted(self.stats.statsTypes), sorted(stats_types))
        
    def testStatsTally(self):
        # Pick a random day, say 15 March:
        start_ts = int(time.mktime((2010,3,15,0,0,0,0,0,-1)))
        stop_ts  = int(time.mktime((2010,3,16,0,0,0,0,0,-1)))
        # Sanity check that this is truly the start of day:
        self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))

        allStats = self.stats.day(start_ts)

        # Test it against some types
        # Should really do a test for 'wind' as well.
        # Should also test monthly, yearly summaries
        for stats_type in ('barometer', 'outTemp', 'rain'):
            # Get the StatsDict for this day and this stats_type:
            typeStats = self.stats.getStatsForType(stats_type, start_ts)
        
            # Now test all the aggregates:
            for aggregate in ('min', 'max', 'sum', 'count', 'avg'):
                # Compare to the main archive:
                res = self.archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), start_ts, stop_ts)
                # From StatsDb:
                typeStats_res = getattr(typeStats, aggregate)
                allStats_res  = getattr(allStats[stats_type], aggregate)
                self.assertEqual(typeStats_res, res[0])
                self.assertEqual(allStats_res, res[0])
                
                # Check the times of min and max as well:
                if aggregate in ('min','max'):
                    res2 = self.archive.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), res[0], start_ts, stop_ts)
                    stats_time =  getattr(typeStats, aggregate+'time')
                    self.assertEqual(stats_time, res2[0])
        
    def testTags(self):

        spans = {'day'  : weeutil.weeutil.TimeSpan(time.mktime((2010,3,15,0,0,0,0,0,-1)),
                                                   time.mktime((2010,3,16,0,0,0,0,0,-1))),
                 'week' : weeutil.weeutil.TimeSpan(time.mktime((2010,3,14,0,0,0,0,0,-1)),
                                                   time.mktime((2010,3,21,0,0,0,0,0,-1))),
                 'month': weeutil.weeutil.TimeSpan(time.mktime((2010,3,01,0,0,0,0,0,-1)),
                                                   time.mktime((2010,4,01,0,0,0,0,0,-1))),
                 'year' : weeutil.weeutil.TimeSpan(time.mktime((2010,1,01,0,0,0,0,0,-1)),
                                                   time.mktime((2011,1,01,0,0,0,0,0,-1)))}

        # This may not necessarily execute in the order specified above:
        for span in spans:
            
            start_ts = spans[span].start
            stop_ts  = spans[span].stop
            tagStats = weewx.stats.TaggedStats(self.stats, stop_ts, 
                                               rain_year_start=1, 
                                               heatbase=(65.0, 'degree_F', 'group_temperature'),
                                               coolbase=(65.0, 'degree_F', 'group_temperature'))
            
            # Cycle over the statistical types:
            for stats_type in ('barometer', 'outTemp', 'rain'):
            
                # Now test all the aggregates:
                for aggregate in ('min', 'max', 'sum', 'count', 'avg'):
                    # Compare to the main archive:
                    res = self.archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), start_ts, stop_ts)
                    archive_result = res[0]
                    # This is how you form a tag such as tagStats.month.barometer.avg when
                    # all you have is strings holding the attributes:
                    value_helper = getattr(getattr(getattr(tagStats, span), stats_type), aggregate)
                    self.assertAlmostEqual(float(str(value_helper.formatted)), archive_result, 1)
                    
                    # Check the times of min and max as well:
                    if aggregate in ('min','max'):
                        res2 = self.archive.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), archive_result, start_ts, stop_ts)
                        stats_value_helper = getattr(getattr(getattr(tagStats, span), stats_type), aggregate +'time')
                        self.assertEqual(stats_value_helper.raw, res2[0])

        self.assertEqual(str(tagStats.day.barometer.avg), "30.672 inHg")
        self.assertEqual(str(tagStats.day.barometer.min), "30.065 inHg")
        self.assertEqual(str(tagStats.day.barometer.max), "31.000 inHg")
        self.assertEqual(str(tagStats.day.barometer.mintime), "00:00")
        self.assertEqual(str(tagStats.day.barometer.maxtime), "01:00")
        self.assertEqual(str(tagStats.week.barometer.avg), "29.904 inHg")
        self.assertEqual(str(tagStats.week.barometer.min), "29.000 inHg")
        self.assertEqual(str(tagStats.week.barometer.max), "31.000 inHg")
        self.assertEqual(str(tagStats.week.barometer.mintime), "01:00 on Monday")
        self.assertEqual(str(tagStats.week.barometer.maxtime), "01:00 on Wednesday")
        self.assertEqual(str(tagStats.month.barometer.avg), "30.021 inHg")
        self.assertEqual(str(tagStats.month.barometer.min), "29.000 inHg")
        self.assertEqual(str(tagStats.month.barometer.max), "31.000 inHg")
        self.assertEqual(str(tagStats.month.barometer.mintime), "05-Mar-2010 00:00")
        self.assertEqual(str(tagStats.month.barometer.maxtime), "03-Mar-2010 00:00")
        self.assertEqual(str(tagStats.year.barometer.avg), "30.002 inHg")
        self.assertEqual(str(tagStats.year.barometer.min), "29.000 inHg")
        self.assertEqual(str(tagStats.year.barometer.max), "31.000 inHg")
        self.assertEqual(str(tagStats.year.barometer.mintime), "04-Jan-2010 00:00")
        self.assertEqual(str(tagStats.year.barometer.maxtime), "02-Jan-2010 00:00")

if __name__ == '__main__':
    unittest.main()
