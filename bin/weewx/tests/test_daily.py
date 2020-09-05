# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Unit test module weewx.wxstats"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import datetime
import logging
import math
import os.path
import shutil
import sys
import time
import unittest

import six
from six.moves import map
import configobj

import gen_fake_data
import weeutil.logger
import weeutil.weeutil
import weewx.manager
import weewx.tags
from weewx.units import ValueHelper

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_daily', {})

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

day_keys = [x[0] for x in gen_fake_data.schema['day_summaries']]

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")

cwd = None

skin_dict = {'Units': {'Trend': {'time_delta': 3600, 'time_grace': 300},
                       'DegreeDay': {'heating_base': "65, degree_F",
                                     'cooling_base': "65, degree_C"}}}


class Common(object):

    def setUp(self):
        global config_path
        global cwd

        # Save and set the current working directory in case some service changes it.
        if not cwd:
            cwd = os.getcwd()
        else:
            os.chdir(cwd)

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
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
        except OSError as e:
            if os.path.exists(test_html_dir):
                print("\nUnable to remove old test directory %s", test_html_dir, file=sys.stderr)
                print("Reason:", e, file=sys.stderr)
                print("Aborting", file=sys.stderr)
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
            start_ts = int(time.mktime((2010, 3, 15, 0, 0, 0, 0, 0, -1)))
            stop_ts = int(time.mktime((2010, 3, 16, 0, 0, 0, 0, 0, -1)))
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
                    res = manager.getSql(
                        "SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type),
                        (start_ts, stop_ts))
                    # The results from the daily summaries for this aggregation 
                    allStats_res = getattr(allStats[stats_type], aggregate)
                    self.assertAlmostEqual(allStats_res, res[0],
                                           msg="Value check. Failing type %s, aggregate: %s" % (stats_type, aggregate))

                    # Check the times of min and max as well:
                    if aggregate in ['min', 'max']:
                        res2 = manager.getSql(
                            "SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,),
                            (res[0], start_ts, stop_ts))
                        stats_time = getattr(allStats[stats_type], aggregate + 'time')
                        self.assertEqual(stats_time, res2[0],
                                         "Time check. Failing type %s, aggregate: %s" % (stats_type, aggregate))

    def testWindTally(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            # Pick a random day, say 15 March:
            start_ts = int(time.mktime((2010, 3, 15, 0, 0, 0, 0, 0, -1)))
            stop_ts = int(time.mktime((2010, 3, 16, 0, 0, 0, 0, 0, -1)))
            # Sanity check that this is truly the start of day:
            self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))

            allStats = manager._get_day_summary(start_ts)

            # Test all the aggregates:
            for aggregate in ['min', 'max', 'sum', 'count', 'avg']:
                if aggregate == 'max':
                    res = manager.getSql("SELECT MAX(windGust) FROM archive WHERE dateTime>? AND dateTime <=?;",
                                         (start_ts, stop_ts))
                else:
                    res = manager.getSql(
                        "SELECT %s(windSpeed) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate,),
                        (start_ts, stop_ts))

                # From StatsDb:
                allStats_res = getattr(allStats['wind'], aggregate)
                self.assertAlmostEqual(allStats_res, res[0])

                # Check the times of min and max as well:
                if aggregate == 'min':
                    resmin = manager.getSql(
                        "SELECT dateTime FROM archive WHERE windSpeed = ? AND dateTime>? AND dateTime <=?",
                        (res[0], start_ts, stop_ts))
                    self.assertEqual(allStats['wind'].mintime, resmin[0])
                elif aggregate == 'max':
                    resmax = manager.getSql(
                        "SELECT dateTime FROM archive WHERE windGust = ?  AND dateTime>? AND dateTime <=?",
                        (res[0], start_ts, stop_ts))
                    self.assertEqual(allStats['wind'].maxtime, resmax[0])

            # Check RMS:
            (squaresum, count) = manager.getSql(
                "SELECT SUM(windSpeed*windSpeed), COUNT(windSpeed) from archive where dateTime>? AND dateTime<=?;",
                (start_ts, stop_ts))
            rms = math.sqrt(squaresum / count) if count else None
            self.assertAlmostEqual(allStats['wind'].rms, rms)

    def testRebuild(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            # Pick a random day, say 15 March:
            start_d = datetime.date(2010, 3, 15)
            stop_d = datetime.date(2010, 3, 15)
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
                                     getattr(newStats[obstype], prop) \
                                     for prop in ('min', 'mintime', 'max', 'maxtime',
                                                  'sum', 'count', 'wsum', 'sumtime',
                                                  'last', 'lasttime')]))

    def testTags(self):
        """Test common tags."""
        global skin_dict
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:

            spans = {'day': weeutil.weeutil.TimeSpan(time.mktime((2010, 3, 15, 0, 0, 0, 0, 0, -1)),
                                                     time.mktime((2010, 3, 16, 0, 0, 0, 0, 0, -1))),
                     'week': weeutil.weeutil.TimeSpan(time.mktime((2010, 3, 14, 0, 0, 0, 0, 0, -1)),
                                                      time.mktime((2010, 3, 21, 0, 0, 0, 0, 0, -1))),
                     'month': weeutil.weeutil.TimeSpan(time.mktime((2010, 3, 1, 0, 0, 0, 0, 0, -1)),
                                                       time.mktime((2010, 4, 1, 0, 0, 0, 0, 0, -1))),
                     'year': weeutil.weeutil.TimeSpan(time.mktime((2010, 1, 1, 0, 0, 0, 0, 0, -1)),
                                                      time.mktime((2011, 1, 1, 0, 0, 0, 0, 0, -1)))}

            # This may not necessarily execute in the order specified above:
            for span in spans:

                start_ts = spans[span].start
                stop_ts = spans[span].stop
                tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                                 rain_year_start=1,
                                                 skin_dict=skin_dict)

                # Cycle over the statistical types:
                for stats_type in ('barometer', 'outTemp', 'rain'):

                    # Now test all the aggregates:
                    for aggregate in ('min', 'max', 'sum', 'count', 'avg'):
                        # Compare to the main archive:
                        res = manager.getSql(
                            "SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type),
                            (start_ts, stop_ts))
                        archive_result = res[0]
                        value_helper = getattr(getattr(getattr(tagStats, span)(), stats_type), aggregate)
                        self.assertAlmostEqual(float(str(value_helper.formatted)), archive_result, places=1)

                        # Check the times of min and max as well:
                        if aggregate in ('min', 'max'):
                            res2 = manager.getSql(
                                "SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (
                                stats_type,), (archive_result, start_ts, stop_ts))
                            stats_value_helper = getattr(getattr(getattr(tagStats, span)(), stats_type),
                                                         aggregate + 'time')
                            self.assertEqual(stats_value_helper.raw, res2[0])

            # Do the tests for a report time of midnight, 1-Apr-2010
            tagStats = weewx.tags.TimeBinder(db_lookup, spans['month'].stop,
                                             rain_year_start=1,
                                             skin_dict=skin_dict)
            self.assertEqual(six.text_type(tagStats.day().barometer.avg), "29.333 inHg")
            self.assertEqual(six.text_type(tagStats.day().barometer.min), "29.000 inHg")
            self.assertEqual(six.text_type(tagStats.day().barometer.max), "29.935 inHg")
            self.assertEqual(six.text_type(tagStats.day().barometer.mintime), "01:00")
            self.assertEqual(six.text_type(tagStats.day().barometer.maxtime), "00:00")
            self.assertEqual(six.text_type(tagStats.week().barometer.avg), "30.097 inHg")
            self.assertEqual(six.text_type(tagStats.week().barometer.min), "29.000 inHg")
            self.assertEqual(six.text_type(tagStats.week().barometer.max), "31.000 inHg")
            self.assertEqual(six.text_type(tagStats.week().barometer.mintime), "01:00 on Wednesday")
            self.assertEqual(six.text_type(tagStats.week().barometer.maxtime), "01:00 on Monday")
            self.assertEqual(six.text_type(tagStats.month().barometer.avg), "29.979 inHg")
            self.assertEqual(six.text_type(tagStats.month().barometer.min), "29.000 inHg")
            self.assertEqual(six.text_type(tagStats.month().barometer.max), "31.000 inHg")
            self.assertEqual(six.text_type(tagStats.month().barometer.mintime), "03-Mar-2010 00:00")
            self.assertEqual(six.text_type(tagStats.month().barometer.maxtime), "05-Mar-2010 00:00")
            self.assertEqual(six.text_type(tagStats.year().barometer.avg), "29.996 inHg")
            self.assertEqual(six.text_type(tagStats.year().barometer.min), "29.000 inHg")
            self.assertEqual(six.text_type(tagStats.year().barometer.max), "31.000 inHg")
            self.assertEqual(six.text_type(tagStats.year().barometer.mintime), "02-Jan-2010 00:00")
            self.assertEqual(six.text_type(tagStats.year().barometer.maxtime), "04-Jan-2010 00:00")
            self.assertEqual(six.text_type(tagStats.day().outTemp.avg), u"38.4°F")
            self.assertEqual(six.text_type(tagStats.day().outTemp.min), u"18.5°F")
            self.assertEqual(six.text_type(tagStats.day().outTemp.max), u"58.9°F")
            self.assertEqual(six.text_type(tagStats.day().outTemp.mintime), "04:00")
            self.assertEqual(six.text_type(tagStats.day().outTemp.maxtime), "16:00")
            self.assertEqual(six.text_type(tagStats.week().outTemp.avg), u"38.7°F")
            self.assertEqual(six.text_type(tagStats.week().outTemp.min), u"16.5°F")
            self.assertEqual(six.text_type(tagStats.week().outTemp.max), u"60.9°F")
            self.assertEqual(six.text_type(tagStats.week().outTemp.mintime), "04:00 on Sunday")
            self.assertEqual(six.text_type(tagStats.week().outTemp.maxtime), "16:00 on Saturday")
            self.assertEqual(six.text_type(tagStats.month().outTemp.avg), u"28.8°F")
            self.assertEqual(six.text_type(tagStats.month().outTemp.min), u"-1.0°F")
            self.assertEqual(six.text_type(tagStats.month().outTemp.max), u"58.9°F")
            self.assertEqual(six.text_type(tagStats.month().outTemp.mintime), "01-Mar-2010 03:00")
            self.assertEqual(six.text_type(tagStats.month().outTemp.maxtime), "31-Mar-2010 16:00")
            self.assertEqual(six.text_type(tagStats.year().outTemp.avg), u"48.3°F")
            self.assertEqual(six.text_type(tagStats.year().outTemp.min), u"-20.0°F")
            self.assertEqual(six.text_type(tagStats.year().outTemp.max), u"100.0°F")
            self.assertEqual(six.text_type(tagStats.year().outTemp.mintime), "01-Jan-2010 03:00")
            self.assertEqual(six.text_type(tagStats.year().outTemp.maxtime), "02-Jul-2010 16:00")

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
        six_hour_span = weeutil.weeutil.TimeSpan(time.mktime((2010, 3, 14, 1, 0, 0, 0, 0, -1)),
                                                 time.mktime((2010, 3, 14, 8, 0, 0, 0, 0, -1)))

        tsb = weewx.tags.TimespanBinder(six_hour_span, db_lookup)
        self.assertEqual(six.text_type(tsb.outTemp.max), u"17.2°F")
        self.assertEqual(six.text_type(tsb.outTemp.maxtime), "14-Mar-2010 08:00")
        self.assertEqual(six.text_type(tsb.outTemp.min), u"7.1°F")
        self.assertEqual(six.text_type(tsb.outTemp.mintime), "14-Mar-2010 04:00")
        self.assertEqual(six.text_type(tsb.outTemp.avg), u"10.0°F")

        rain_span = weeutil.weeutil.TimeSpan(time.mktime((2010, 3, 14, 20, 10, 0, 0, 0, -1)),
                                             time.mktime((2010, 3, 14, 23, 10, 0, 0, 0, -1)))
        tsb = weewx.tags.TimespanBinder(rain_span, db_lookup)
        self.assertEqual(six.text_type(tsb.rain.sum), "0.36 in")

    def test_agg(self):
        """Test aggregation in the archive table against aggregation in the daily summary"""

        week_start_ts = time.mktime((2010, 3, 14, 0, 0, 0, 0, 0, -1))
        week_stop_ts = time.mktime((2010, 3, 21, 0, 0, 0, 0, 0, -1))

        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            for day_span in weeutil.weeutil.genDaySpans(week_start_ts, week_stop_ts):
                for aggregation in ['min', 'max', 'mintime', 'maxtime', 'avg']:
                    # Get the answer using the raw archive  table:
                    table_answer = ValueHelper(
                        weewx.manager.Manager.getAggregate(manager, day_span, 'outTemp', aggregation))
                    daily_answer = ValueHelper(
                        weewx.manager.DaySummaryManager.getAggregate(manager, day_span, 'outTemp', aggregation))
                    self.assertEqual(six.text_type(table_answer), six.text_type(daily_answer),
                                     msg="aggregation=%s; %s vs %s" % (aggregation, table_answer, daily_answer))

    def test_rainYear(self):
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()

        stop_ts = time.mktime((2011, 1, 1, 0, 0, 0, 0, 0, -1))
        # Check for a rain year starting 1-Jan
        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                         rain_year_start=1)

        self.assertEqual(six.text_type(tagStats.rainyear().rain.sum), "79.36 in")

        # Do it again, for starting 1-Oct:
        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                         rain_year_start=6)
        self.assertEqual(six.text_type(tagStats.rainyear().rain.sum), "30.72 in")

    def test_heatcool(self):
        db_binder = weewx.manager.DBBinder(self.config_dict)
        db_lookup = db_binder.bind_default()
        # Test heating and cooling degree days:
        stop_ts = time.mktime((2011, 1, 1, 0, 0, 0, 0, 0, -1))

        tagStats = weewx.tags.TimeBinder(db_lookup, stop_ts,
                                         skin_dict=skin_dict)

        self.assertEqual(six.text_type(tagStats.year().heatdeg.sum), u"5125.1°F-day")
        self.assertEqual(six.text_type(tagStats.year().cooldeg.sum), u"1026.5°F-day")


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super(TestMySQL, self).setUp()


def suite():
    tests = ['test_create_stats', 'testScalarTally', 'testWindTally', 'testRebuild',
             'testTags', 'test_rainYear', 'test_agg_intervals', 'test_agg', 'test_heatcool']

    # Test both sqlite and MySQL:
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
