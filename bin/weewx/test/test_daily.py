# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Unit test module weewx.wxstats"""

from __future__ import with_statement
import datetime
import math
import os.path
import shutil
import sys
import syslog
import time
import unittest

import configobj

os.environ['TZ'] = 'America/Los_Angeles'

import weeutil.weeutil
import weewx.tags
import gen_fake_data
from weewx.units import ValueHelper

day_keys = [x[0] for x in gen_fake_data.schema if x[0] not in ['dateTime', 'interval', 'usUnits']] + ['wind']

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")

cwd = None

skin_dict = {'Units' : {'Trend':      {'time_delta': 3600, 'time_grace': 300},
                        'DegreeDay' : {'heating_base' : "65, degree_F",
                                       'cooling_base' : "65, degree_C"} } }

class Common(unittest.TestCase):
    
    def setUp(self):
        global config_path
        global cwd
        
        weewx.debug = 1

        syslog.openlog('test_stats', syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # Save and set the current working directory in case some service changes it.
        if not cwd:
            cwd = os.getcwd()
        else:
            os.chdir(cwd)

        try :
            self.config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % self.config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # Remove the old directory:
        try:
            test_html_dir = os.path.join(self.config_dict['WEEWX_ROOT'], self.config_dict['StdReport']['HTML_ROOT'])
            shutil.rmtree(test_html_dir)
        except OSError, e:
            if os.path.exists(test_html_dir):
                print >>sys.stderr, "\nUnable to remove old test directory %s", test_html_dir
                print >>sys.stderr, "Reason:", e
                print >>sys.stderr, "Aborting"
                exit(1)

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass
    
    def test_create_stats(self):
        global day_keys
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            self.assertEqual(sorted(manager.daykeys), sorted(day_keys))
            self.assertEqual(manager.connection.columnsOf('archive_day_barometer'),
                             ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count', 'wsum', 'sumtime'])
            self.assertEqual(manager.connection.columnsOf('archive_day_wind'), 
                             ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count', 'wsum', 'sumtime', 
                              'max_dir', 'xsum', 'ysum', 'dirsumtime', 'squaresum', 'wsquaresum'])
        
    def testScalarTally(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            # Pick a random day, say 15 March:
            start_ts = int(time.mktime((2010,3,15,0,0,0,0,0,-1)))
            stop_ts  = int(time.mktime((2010,3,16,0,0,0,0,0,-1)))
            # Sanity check that this is truly the start of day:
            self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))
    
            # Get a day's stats from the daily summaries:
            allStats = manager._get_day_summary(start_ts)
    
            # Now calculate the same summaries from the raw data in the archive.
            # Here are some random observation types:
            for stats_type in ['barometer', 'outTemp', 'rain']:
    
                # Now test all the aggregates:
                for aggregate in ['min', 'max', 'sum', 'count', 'avg']:
                    # Compare to the main archive:
                    res = manager.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), (start_ts, stop_ts))
                    # The results from the daily summaries for this aggregation 
                    allStats_res  = getattr(allStats[stats_type], aggregate)
                    self.assertAlmostEqual(allStats_res, res[0], msg="Value check. Failing type %s, aggregate: %s" % (stats_type, aggregate))
                    
                    # Check the times of min and max as well:
                    if aggregate in ['min','max']:
                        res2 = manager.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), (res[0], start_ts, stop_ts))
                        stats_time =  getattr(allStats[stats_type], aggregate+'time')
                        self.assertEqual(stats_time, res2[0], "Time check. Failing type %s, aggregate: %s" % (stats_type, aggregate))
    
    def testWindTally(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            # Pick a random day, say 15 March:
            start_ts = int(time.mktime((2010,3,15,0,0,0,0,0,-1)))
            stop_ts  = int(time.mktime((2010,3,16,0,0,0,0,0,-1)))
            # Sanity check that this is truly the start of day:
            self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))
    
            allStats = manager._get_day_summary(start_ts)
    
            # Test all the aggregates:
            for aggregate in ['min', 'max', 'sum', 'count', 'avg']:
                if aggregate == 'max':
                    res = manager.getSql("SELECT MAX(windGust) FROM archive WHERE dateTime>? AND dateTime <=?;", (start_ts, stop_ts))
                else:
                    res = manager.getSql("SELECT %s(windSpeed) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, ), (start_ts, stop_ts))
    
                # From StatsDb:
                allStats_res  = getattr(allStats['wind'], aggregate)
                self.assertAlmostEqual(allStats_res, res[0])
                
                # Check the times of min and max as well:
                if aggregate == 'min':
                    resmin = manager.getSql("SELECT dateTime FROM archive WHERE windSpeed = ? AND dateTime>? AND dateTime <=?", (res[0], start_ts, stop_ts))
                    self.assertEqual(allStats['wind'].mintime, resmin[0])
                elif aggregate == 'max':
                    resmax = manager.getSql("SELECT dateTime FROM archive WHERE windGust = ?  AND dateTime>? AND dateTime <=?", (res[0], start_ts, stop_ts))
                    self.assertEqual(allStats['wind'].maxtime, resmax[0])
    
            # Check RMS:
            (squaresum, count) = manager.getSql("SELECT SUM(windSpeed*windSpeed), COUNT(windSpeed) from archive where dateTime>? AND dateTime<=?;", (start_ts, stop_ts))
            rms = math.sqrt(squaresum/count) if count else None
            self.assertAlmostEqual(allStats['wind'].rms, rms)

    def testRebuild(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            # Pick a random day, say 15 March:
            start_d = datetime.date(2010, 3, 15)
            stop_d  = datetime.date(2010, 3, 15)
            start_ts = int(time.mktime(start_d.timetuple()))

            # Get the day's statistics:
            origStats = manager._get_day_summary(start_ts)

            # Rebuild that day:
            manager.backfill_day_summary(start_d=start_d, stop_d=stop_d)
            
            # Get the new statistics
            newStats = manager._get_day_summary(start_ts)
            
            # Check for equality
            for obstype in ('outTemp', 'barometer', 'windSpeed'):
                self.assertTrue(all([getattr(origStats[obstype], prop) == \
                                     getattr(newStats[obstype],  prop) \
                                     for prop in ('min', 'mintime', 'max', 'maxtime', 
                                                  'sum', 'count', 'wsum', 'sumtime', 
                                                  'last', 'lasttime')]))
            
    def testTags(self):
        """Test common tags."""
        global skin_dict
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
        
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
                tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                                   rain_year_start=1, 
                                                   skin_dict=skin_dict)
                
                # Cycle over the statistical types:
                for stats_type in ('barometer', 'outTemp', 'rain'):
                
                    # Now test all the aggregates:
                    for aggregate in ('min', 'max', 'sum', 'count', 'avg'):
                        # Compare to the main archive:
                        res = manager.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), (start_ts, stop_ts))
                        archive_result = res[0]
                        value_helper = getattr(getattr(getattr(tagStats, span)(), stats_type), aggregate)
                        self.assertAlmostEqual(float(str(value_helper.formatted)), archive_result, places=1)
                        
                        # Check the times of min and max as well:
                        if aggregate in ('min','max'):
                            res2 = manager.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), (archive_result, start_ts, stop_ts))
                            stats_value_helper = getattr(getattr(getattr(tagStats, span)(), stats_type), aggregate +'time')
                            self.assertEqual(stats_value_helper.raw, res2[0])
    
            # Do the tests for a report time of midnight, 1-Apr-2010
            tagStats = weewx.tags.TimeBinder(db_lookup, spans['month'].stop,
                                             rain_year_start=1,
                                             skin_dict=skin_dict)
            self.assertEqual(str(tagStats.day().barometer.avg), "30.675 inHg")
            self.assertEqual(str(tagStats.day().barometer.min), "30.065 inHg")
            self.assertEqual(str(tagStats.day().barometer.max), "31.000 inHg")
            self.assertEqual(str(tagStats.day().barometer.mintime), "00:00")
            self.assertEqual(str(tagStats.day().barometer.maxtime), "01:00")
            self.assertEqual(str(tagStats.week().barometer.avg), "29.904 inHg")
            self.assertEqual(str(tagStats.week().barometer.min), "29.000 inHg")
            self.assertEqual(str(tagStats.week().barometer.max), "31.000 inHg")
            self.assertEqual(str(tagStats.week().barometer.mintime), "01:00 on Monday")
            self.assertEqual(str(tagStats.week().barometer.maxtime), "01:00 on Wednesday")
            self.assertEqual(str(tagStats.month().barometer.avg), "30.021 inHg")
            self.assertEqual(str(tagStats.month().barometer.min), "29.000 inHg")
            self.assertEqual(str(tagStats.month().barometer.max), "31.000 inHg")
            self.assertEqual(str(tagStats.month().barometer.mintime), "05-Mar-2010 00:00")
            self.assertEqual(str(tagStats.month().barometer.maxtime), "03-Mar-2010 00:00")
            self.assertEqual(str(tagStats.year().barometer.avg), "30.004 inHg")
            self.assertEqual(str(tagStats.year().barometer.min), "29.000 inHg")
            self.assertEqual(str(tagStats.year().barometer.max), "31.000 inHg")
            self.assertEqual(str(tagStats.year().barometer.mintime), "04-Jan-2010 00:00")
            self.assertEqual(str(tagStats.year().barometer.maxtime), "02-Jan-2010 00:00")
            self.assertEqual(str(tagStats.day().outTemp.avg), "38.8°F")
            self.assertEqual(str(tagStats.day().outTemp.min), "18.6°F")
            self.assertEqual(str(tagStats.day().outTemp.max), "59.0°F")
            self.assertEqual(str(tagStats.day().outTemp.mintime), "07:00")
            self.assertEqual(str(tagStats.day().outTemp.maxtime), "19:00")
            self.assertEqual(str(tagStats.week().outTemp.avg), "38.8°F")
            self.assertEqual(str(tagStats.week().outTemp.min), "16.6°F")
            self.assertEqual(str(tagStats.week().outTemp.max), "61.0°F")
            self.assertEqual(str(tagStats.week().outTemp.mintime), "07:00 on Sunday")
            self.assertEqual(str(tagStats.week().outTemp.maxtime), "19:00 on Saturday")
            self.assertEqual(str(tagStats.month().outTemp.avg), "28.7°F")
            self.assertEqual(str(tagStats.month().outTemp.min), "-0.9°F")
            self.assertEqual(str(tagStats.month().outTemp.max), "59.0°F")
            self.assertEqual(str(tagStats.month().outTemp.mintime), "01-Mar-2010 06:00")
            self.assertEqual(str(tagStats.month().outTemp.maxtime), "31-Mar-2010 19:00")
            self.assertEqual(str(tagStats.year().outTemp.avg), "48.3°F")
            self.assertEqual(str(tagStats.year().outTemp.min), "-20.0°F")
            self.assertEqual(str(tagStats.year().outTemp.max), "100.0°F")
            self.assertEqual(str(tagStats.year().outTemp.mintime), "01-Jan-2010 06:00")
            self.assertEqual(str(tagStats.year().outTemp.maxtime), "02-Jul-2010 19:00")
            
            # Check the special aggregate types "exists" and "has_data":
            self.assertTrue(tagStats.year().barometer.exists)
            self.assertTrue(tagStats.year().barometer.has_data)
            self.assertFalse(tagStats.year().bar.exists)
            self.assertFalse(tagStats.year().bar.has_data)
            self.assertTrue(tagStats.year().inHumidity.exists)
            self.assertFalse(tagStats.year().inHumidity.has_data)

    def test_agg_intervals(self):
        """Test aggregation spans that do not span a day"""
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()

        # note that this spans the spring DST boundary:
        six_hour_span =  weeutil.weeutil.TimeSpan(time.mktime((2010,3,14,1,0,0,0,0,-1)),
                                                  time.mktime((2010,3,14,8,0,0,0,0,-1)))
 
        tsb = weewx.tags.TimespanBinder(six_hour_span, db_lookup)
        self.assertEqual(str(tsb.outTemp.max), "21.0°F")
        self.assertEqual(str(tsb.outTemp.maxtime), "14-Mar-2010 01:10")
        self.assertEqual(str(tsb.outTemp.min), "7.1°F")
        self.assertEqual(str(tsb.outTemp.mintime), "14-Mar-2010 07:00")
        self.assertEqual(str(tsb.outTemp.avg), "11.4°F")
        
        rain_span = weeutil.weeutil.TimeSpan(time.mktime((2010,3,14,20,10,0,0,0,-1)),
                                             time.mktime((2010,3,14,23,10,0,0,0,-1)))
        tsb = weewx.tags.TimespanBinder(rain_span, db_lookup)
        self.assertEqual(str(tsb.rain.sum), "0.26 in")
        
    def test_agg(self):
        """Test aggregation in the archive table against aggregation in the daily summary"""
        
        week_start_ts = time.mktime((2010,3,14,0,0,0,0,0,-1))
        week_stop_ts  = time.mktime((2010,3,21,0,0,0,0,0,-1))
        
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            for day_span in weeutil.weeutil.genDaySpans(week_start_ts, week_stop_ts):
                for aggregation in ['min', 'max', 'mintime', 'maxtime', 'avg']:
                    # Get the answer using the raw archive  table:
                    table_answer = ValueHelper(weewx.manager.Manager.getAggregate(manager, day_span, 'outTemp', aggregation))
                    daily_answer = ValueHelper(weewx.manager.DaySummaryManager.getAggregate(manager, day_span, 'outTemp', aggregation))
                    self.assertEqual(str(table_answer), str(daily_answer), 
                                     msg="aggregation=%s; %s vs %s" % (aggregation, table_answer, daily_answer))
            
    def test_rainYear(self):
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()

        stop_ts = time.mktime((2011,1,01,0,0,0,0,0,-1))
        # Check for a rain year starting 1-Jan
        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                           rain_year_start=1)
            
        self.assertEqual(str(tagStats.rainyear().rain.sum), "58.68 in")

        # Do it again, for starting 1-Oct:
        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                           rain_year_start=6)
        self.assertEqual(str(tagStats.rainyear().rain.sum), "22.72 in")


    def test_heatcool(self):
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()
        #Test heating and cooling degree days:
        stop_ts = time.mktime((2011,1,01,0,0,0,0,0,-1))

        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                             skin_dict=skin_dict)
            
        self.assertEqual(str(tagStats.year().heatdeg.sum), "5126.3°F-day")
        self.assertEqual(str(tagStats.year().cooldeg.sum), "1026.2°F-day")
    

class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_create_stats', 'testScalarTally', 'testWindTally', 'testRebuild',
             'testTags', 'test_rainYear', 'test_agg_intervals', 'test_agg', 'test_heatcool']
    
    # Test both sqlite and MySQL:
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))

if __name__ == '__main__':

    unittest.TextTestRunner(verbosity=2).run(suite())
