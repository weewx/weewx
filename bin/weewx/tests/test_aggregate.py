#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test aggregate functions."""

from __future__ import absolute_import
from __future__ import print_function

import logging
import os.path
import sys
import time
import unittest

import configobj

import weedb
import gen_fake_data
import weeutil.logger
import weewx
import weewx.manager
import weewx.xtypes
from weeutil.weeutil import TimeSpan
from weewx.units import ValueTuple

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_aggregate', {})

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")


class TestAggregate(unittest.TestCase):

    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # This will generate the test databases if necessary. Use the SQLite database: it's faster.
        gen_fake_data.configDatabases(self.config_dict, database_type='sqlite')

    def tearDown(self):
        pass

    def test_get_aggregate(self):
        # Use the same function to test calculating aggregations from the main archive file, as well
        # as from the daily summaries:
        self.examine_object(weewx.xtypes.ArchiveTable)
        self.examine_object(weewx.xtypes.DailySummaries)

    def examine_object(self, aggregate_obj):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
            month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
            start_ts = time.mktime(month_start_tt)
            stop_ts = time.mktime(month_stop_tt)

            avg_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'avg', db_manager)
            self.assertAlmostEqual(avg_vt[0], 28.77, 2)
            self.assertEqual(avg_vt[1], 'degree_F')
            self.assertEqual(avg_vt[2], 'group_temperature')

            max_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'max', db_manager)
            self.assertAlmostEqual(max_vt[0], 58.88, 2)
            maxtime_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'maxtime', db_manager)
            self.assertEqual(maxtime_vt[0], 1270076400)

            min_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'min', db_manager)
            self.assertAlmostEqual(min_vt[0], -1.01, 2)
            mintime_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'mintime', db_manager)
            self.assertEqual(mintime_vt[0], 1267441200)

            count_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'count', db_manager)
            self.assertEqual(count_vt[0], 1465)

            sum_vt = aggregate_obj.get_aggregate('rain', TimeSpan(start_ts, stop_ts), 'sum', db_manager)
            self.assertAlmostEqual(sum_vt[0], 10.24, 2)

            # The ArchiveTable version has a few extra aggregate types:
            if aggregate_obj == weewx.xtypes.ArchiveTable:
                first_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'first', db_manager)
                # Get the timestamp of the first record inside the month
                ts = start_ts + gen_fake_data.interval
                rec = db_manager.getRecord(ts)
                self.assertEqual(first_vt[0], rec['outTemp'])

                first_time_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'firsttime',
                                                            db_manager)
                self.assertEqual(first_time_vt[0], ts)

                last_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'last', db_manager)
                # Get the timestamp of the last record of the month
                rec = db_manager.getRecord(stop_ts)
                self.assertEqual(last_vt[0], rec['outTemp'])

                last_time_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'lasttime',
                                                           db_manager)
                self.assertEqual(last_time_vt[0], stop_ts)

                # Use 'dateTime' to check 'diff' and 'tderiv'. The calculations are super easy.
                diff_vt = aggregate_obj.get_aggregate('dateTime', TimeSpan(start_ts, stop_ts), 'diff', db_manager)
                self.assertEqual(diff_vt[0], stop_ts - start_ts)

                tderiv_vt = aggregate_obj.get_aggregate('dateTime', TimeSpan(start_ts, stop_ts), 'tderiv', db_manager)
                self.assertAlmostEqual(tderiv_vt[0], 1.0)

    def test_AggregateDaily(self):
        """Test special aggregates that can be used against the daily summaries."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
            month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
            start_ts = time.mktime(month_start_tt)
            stop_ts = time.mktime(month_stop_tt)

            min_ge_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'min_ge',
                                                                  db_manager,
                                                                  val=ValueTuple(15, 'degree_F', 'group_temperature'))
            self.assertEqual(min_ge_vt[0], 6)

            min_le_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'min_le',
                                                                  db_manager,
                                                                  val=ValueTuple(0, 'degree_F', 'group_temperature'))
            self.assertEqual(min_le_vt[0], 2)

            minmax_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'minmax',
                                                                  db_manager)
            self.assertAlmostEqual(minmax_vt[0], 39.28, 2)

            max_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind', TimeSpan(start_ts, stop_ts), 'max',
                                                                    db_manager)
            self.assertAlmostEqual(max_wind_vt[0], 24.0, 2)

            avg_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind', TimeSpan(start_ts, stop_ts), 'avg',
                                                                    db_manager)
            self.assertAlmostEqual(avg_wind_vt[0], 10.21, 2)
            # Double check this last one against the average calculated from the archive
            avg_wind_vt = weewx.xtypes.ArchiveTable.get_aggregate('windSpeed', TimeSpan(start_ts, stop_ts), 'avg',
                                                                  db_manager)
            self.assertAlmostEqual(avg_wind_vt[0], 10.21, 2)

            vecavg_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind', TimeSpan(start_ts, stop_ts), 'vecavg',
                                                                       db_manager)
            self.assertAlmostEqual(vecavg_wind_vt[0], 5.14, 2)

            vecdir_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind', TimeSpan(start_ts, stop_ts), 'vecdir',
                                                                       db_manager)
            self.assertAlmostEqual(vecdir_wind_vt[0], 88.77, 2)

    def test_get_aggregate_heatcool(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
            month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
            start_ts = time.mktime(month_start_tt)
            stop_ts = time.mktime(month_stop_tt)

            # First, with the default heating base:
            heatdeg = weewx.xtypes.AggregateHeatCool.get_aggregate('heatdeg', TimeSpan(start_ts, stop_ts), 'sum',
                                                                   db_manager)
            self.assertAlmostEqual(heatdeg[0], 1123.12, 2)
            # Now with an explicit heating base:
            heatdeg = weewx.xtypes.AggregateHeatCool.get_aggregate('heatdeg', TimeSpan(start_ts, stop_ts), 'sum',
                                                                   db_manager,
                                                                   skin_dict={'Units': {'DegreeDays': {
                                                                       'heating_base': (
                                                                           60.0, "degree_F", "group_temperature")
                                                                   }}})
            self.assertAlmostEqual(heatdeg[0], 968.12, 2)

    def test_get_aggregate_windvec(self):
        """Test calculating special type 'windvec' using a variety of methods."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
            month_stop_tt = (2010, 3, 2, 0, 0, 0, 0, 0, -1)
            start_ts = time.mktime(month_start_tt)
            stop_ts = time.mktime(month_stop_tt)

            # Calculate the daily wind for 1-March-2010 using the daily summaries, the main archive table,
            # and letting get_aggregate() choose.
            for func in [
                weewx.xtypes.WindVecDaily.get_aggregate,
                weewx.xtypes.WindVec.get_aggregate,
                weewx.xtypes.get_aggregate
            ]:
                windvec = func('windvec', TimeSpan(start_ts, stop_ts), 'avg', db_manager)
                self.assertAlmostEqual(windvec[0].real, -1.390, 3)
                self.assertAlmostEqual(windvec[0].imag, 3.250, 3)
                self.assertEqual(windvec[1:3], ('mile_per_hour', 'group_speed'))

    def test_get_aggregate_expression(self):
        """Test using an expression in an aggregate"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            month_start_tt = (2010, 7, 1, 0, 0, 0, 0, 0, -1)
            month_stop_tt = (2010, 8, 1, 0, 0, 0, 0, 0, -1)
            start_ts = time.mktime(month_start_tt)
            stop_ts = time.mktime(month_stop_tt)

            # This one is a valid expression:
            value = weewx.xtypes.get_aggregate('rain-ET', TimeSpan(start_ts, stop_ts), 'sum', db_manager)
            self.assertAlmostEqual(value[0], 2.94, 2)

            # This one uses a nonsense variable:
            with self.assertRaises(weewx.UnknownAggregation):
                value = weewx.xtypes.get_aggregate('rain-foo', TimeSpan(start_ts, stop_ts), 'sum', db_manager)

            # A valid function
            value = weewx.xtypes.get_aggregate('max(rain-ET, 0)', TimeSpan(start_ts, stop_ts), 'sum', db_manager)
            self.assertAlmostEqual(value[0], 9.57, 2)

            # This one uses a nonsense function
            with self.assertRaises(weedb.OperationalError):
                value = weewx.xtypes.get_aggregate('foo(rain-ET)', TimeSpan(start_ts, stop_ts), 'sum', db_manager)




if __name__ == '__main__':
    unittest.main()
