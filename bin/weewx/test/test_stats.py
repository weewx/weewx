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

import syslog
import time
import unittest

import weeutil.weeutil
import weewx.stats
from gen_fake_data import StatsTestBase, stats_types

class StatsTest(StatsTestBase):

    def setUp(self):
        syslog.openlog('test_stats', syslog.LOG_CONS)
        # This will generate the test databases if necessary:
        StatsTestBase.setUp(self)
        
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

        self.assertEqual(str(tagStats.day.barometer.avg), "30.675 inHg")
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
        
        # Check the special aggregate types "exists" and "has_data":
        self.assertTrue(tagStats.year.barometer.exists)
        self.assertTrue(tagStats.year.barometer.has_data)
        self.assertFalse(tagStats.year.bar.exists)
        self.assertFalse(tagStats.year.bar.has_data)
        self.assertTrue(tagStats.year.foo.exists)
        self.assertFalse(tagStats.year.foo.has_data)

if __name__ == '__main__':
    unittest.main()
