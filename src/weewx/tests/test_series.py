#
#    Copyright (c) 2018-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weewx.xtypes.get_series"""

import functools
import os.path
import sys
import time
import unittest

import configobj

import gen_fake_data
import weewx
import weewx.units
import weewx.wxformulas
import weewx.xtypes
from weeutil.weeutil import TimeSpan

# We will be using the VaporPressure example, so include it in the path
import weewx_data
example_dir = os.path.normpath(os.path.join(os.path.dirname(weewx_data.__file__),
                                            './examples'))
sys.path.append(example_dir)
# Now we can import it
import vaporpressure
# Register an instance of VaporPressure with the XTypes system:
weewx.xtypes.xtypes.insert(0, vaporpressure.VaporPressure())

weewx.debug = 1

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")
cwd = None

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()
month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
start_ts = time.mktime(month_start_tt)
stop_ts = time.mktime(month_stop_tt)



class Common:
    # These are the expected results for March 2010
    expected_daily_rain_sum = [0.00, 0.68, 0.60, 0.00, 0.00, 0.68, 0.60, 0.00, 0.00, 0.68, 0.60,
                               0.00, 0.00, 0.52, 0.76, 0.00, 0.00, 0.52, 0.76, 0.00, 0.00, 0.52,
                               0.76, 0.00, 0.00, 0.52, 0.76, 0.00, 0.00, 0.52, 0.76]

    expected_daily_wind_avg = [(-1.39, 3.25), (11.50, 9.43), (11.07, -9.64), (-1.39, -3.03),
                               (-1.34, 3.29), (11.66, 9.37), (11.13, -9.76), (-1.35, -3.11),
                               (-1.38, 3.35), (11.68, 9.48), (11.14, -9.60), (-1.37, -3.09),
                               (-1.34, 3.24), (11.21, 9.78), (12.08, -9.24), (-1.37, -3.57),
                               (-1.35, 2.91), (10.70, 9.93), (12.07, -9.13), (-1.33, -3.50),
                               (-1.38, 2.84), (10.65, 9.82), (11.89, -9.21), (-1.38, -3.47),
                               (-1.34, 2.88), (10.83, 9.77), (11.97, -9.31), (-1.35, -3.54),
                               (-1.37, 2.93), (10.82, 9.88), (11.97, -9.16)]

    expected_daily_wind_last = [(0.00, 10.00), (20.00, 0.00), (0.00, -10.00), (0.00, 0.00),
                                (0.00, 10.00), (20.00, 0.00), (0.00, -10.00), (0.00, 0.00),
                                (0.00, 10.00), (20.00, 0.00), (0.00, -10.00), (0.00, 0.00),
                                (0.00, 10.00), (19.94, 1.31), (0.70, -10.63), (-0.02, 0.00),
                                (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63), (-0.02, 0.00),
                                (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63), (-0.02, 0.00),
                                (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63), (-0.02, 0.00),
                                (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63)]

    expected_vapor_pressures = [0.052, 0.052, None, 0.053, 0.055, 0.058]
    expected_aggregate_vapor_pressures = [0.055, 0.130, 0.238, 0.119, 0.057, 0.133, 0.243, 0.122,
                                          0.058, 0.136, 0.247, 0.125, 0.060, 0.139, 0.254, 0.128,
                                          0.062, 0.143, 0.260, 0.131, 0.063, 0.146, 0.265, 0.135,
                                          0.064, 0.150, 0.272, 0.138, 0.066, 0.153, 0.279, 0.141,
                                          0.068, 0.157, 0.286, 0.145, 0.070, 0.161, 0.292, 0.149,
                                          0.071, 0.165, 0.299, 0.152, 0.074, 0.161, 0.306, 0.156,
                                          0.076, 0.173, 0.313, 0.166, 0.076, 0.148, 0.317, 0.196,
                                          0.081, 0.143, 0.325, 0.201, 0.083, 0.156, 0.333, 0.213,
                                          0.086, 0.160, 0.341, 0.211, 0.088, 0.159, 0.349, 0.217,
                                          0.091, 0.168, 0.357, 0.227, 0.093, 0.173, 0.366, 0.228,
                                          0.096, 0.176, 0.375, 0.234, 0.098, 0.182, 0.384, 0.241,
                                          0.101, 0.187, 0.393, 0.246, 0.104, 0.193, 0.403, 0.252,
                                          0.107, 0.197, 0.413, 0.256, 0.110, 0.202, 0.423, 0.265,
                                          0.113, 0.212, 0.433, 0.272, 0.116, 0.212, 0.444, 0.271,
                                          0.120, 0.218, 0.454, 0.286, 0.123, 0.231, 0.465, 0.293,
                                          0.126, 0.229, 0.477, 0.287]

    def setUp(self):
        global config_path
        global cwd

        # Save and set the current working directory in case some service changes it.
        if cwd:
            os.chdir(cwd)
        else:
            cwd = os.getcwd()

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass

    def test_get_series_archive_outTemp(self):
        """Test a series of outTemp with no aggregation, run against the archive table."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.ArchiveTable.get_series('outTemp',
                                                       TimeSpan(start_ts, stop_ts),
                                                       db_manager)
        self.assertEqual(len(start_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval)
        self.assertEqual(len(stop_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval)
        self.assertEqual(len(data_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval)

    def test_get_series_daily_agg_rain_sum(self):
        """Test a series of daily aggregated rain totals, run against the daily summaries"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the total daily rain
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.DailySummaries.get_series('rain',
                                                         TimeSpan(start_ts, stop_ts),
                                                         db_manager,
                                                         'sum',
                                                         'day')
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                         (["%.2f" % d for d in Common.expected_daily_rain_sum], 'inch',
                          'group_rain'))

    def test_get_series_archive_agg_rain_sum(self):
        """Test a series of daily aggregated rain totals, run against the main archive table"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the total daily rain
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.ArchiveTable.get_series('rain',
                                                       TimeSpan(start_ts, stop_ts),
                                                       db_manager,
                                                       'sum',
                                                       'day')
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                         (["%.2f" % d for d in Common.expected_daily_rain_sum], 'inch',
                          'group_rain'))

    def test_get_series_archive_agg_rain_cum(self):
        """Test a series of daily cumulative rain totals, run against the main archive table."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the cumulative total daily rain
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.ArchiveTable.get_series('rain',
                                                       TimeSpan(start_ts, stop_ts),
                                                       db_manager,
                                                       'cumulative',
                                                       24 * 3600)
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        right_answer = functools.reduce(lambda v, x: v + [v[-1] + x],
                                        Common.expected_daily_rain_sum, [0])[1:]
        self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                         (["%.2f" % d for d in right_answer], 'inch', 'group_rain'))

    def test_get_series_archive_windvec(self):
        """Test a series of 'windvec', with no aggregation, run against the main archive table"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a series of wind values
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.WindVec.get_series('windvec',
                                                  TimeSpan(start_ts, stop_ts),
                                                  db_manager)
        self.assertEqual(len(start_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(stop_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(data_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)

    def test_get_series_archive_agg_windvec_avg(self):
        """Test a series of 'windvec', with 'avg' aggregation. This will exercise
        WindVec.get_series(0), which, in turn, will call WindVecDaily.get_aggregate() to get each
        individual aggregate value."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a series of wind values
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.WindVec.get_series('windvec',
                                                  TimeSpan(start_ts, stop_ts),
                                                  db_manager,
                                                  'avg',
                                                  24 * 3600)
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        self.assertEqual((["(%.2f, %.2f)" % (x.real, x.imag) for x in data_vec[0]]),
                         (["(%.2f, %.2f)" % (x[0], x[1]) for x in Common.expected_daily_wind_avg]))

    def test_get_series_archive_agg_windvec_last(self):
        """Test a series of 'windvec', with 'last' aggregation. This will exercise
        WindVec.get_series(), which, in turn, will call WindVec.get_aggregate() to get each
        individual aggregate value."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a series of wind values
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('windvec',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager,
                                                                    'last',
                                                                    24 * 3600)
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        # The round(x, 2) + 0 is necessary to avoid 0.00 comparing different from -0.00.
        self.assertEqual(
            (["(%.2f, %.2f)" % (round(x.real, 2) + 0, round(x.imag, 2) + 0) for x in data_vec[0]]),
            (["(%.2f, %.2f)" % (x[0], x[1]) for x in Common.expected_daily_wind_last]))

    def test_get_aggregate_windvec_last(self):
        """Test getting a windvec aggregation over a period that does not fall on midnight
        boundaries."""
        # This time span was chosen because it includes a null value.
        start_tt = (2010, 3, 2, 12, 0, 0, 0, 0, -1)
        start = time.mktime(start_tt)  # = 1267560000
        stop = start + 6 * 3600
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a simple 'avg' aggregation over this period
            val_t = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                       TimeSpan(start, stop),
                                                       'avg',
                                                       db_manager)
            self.assertEqual(type(val_t[0]), complex)
            self.assertAlmostEqual(val_t[0].real, 15.37441, 5)
            self.assertAlmostEqual(val_t[0].imag, 9.79138, 5)
            self.assertEqual(val_t[1], 'mile_per_hour')
            self.assertEqual(val_t[2], 'group_speed')

    def test_get_series_on_the_fly(self):
        """Test a series of a user-defined type with no aggregation,
        run against the archive table."""
        # This time span was chosen because it includes a null for outTemp at 0330
        start_tt = (2010, 3, 2, 2, 0, 0, 0, 0, -1)
        stop_tt = (2010, 3, 2, 5, 0, 0, 0, 0, -1)
        start = time.mktime(start_tt)
        stop = time.mktime(stop_tt)

        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.get_series('vapor_p',
                                          TimeSpan(start, stop),
                                          db_manager)

            for actual, expected in zip(data_vec[0], Common.expected_vapor_pressures):
                self.assertAlmostEqual(actual, expected, 3)
            self.assertEqual(data_vec[1], 'inHg')
            self.assertEqual(data_vec[2], 'group_pressure')

    def test_get_aggregate_series_on_the_fly(self):
        """Test a series of a user-defined type with aggregation, run against the archive table."""

        start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
        stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
        start = time.mktime(start_tt)
        stop = time.mktime(stop_tt)

        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.get_series('vapor_p',
                                          TimeSpan(start, stop),
                                          db_manager,
                                          aggregate_type='avg',
                                          aggregate_interval=6 * 3600)

            for actual, expected in zip(data_vec[0], Common.expected_aggregate_vapor_pressures):
                self.assertAlmostEqual(actual, expected, 3)
            self.assertEqual(data_vec[1], 'inHg')
            self.assertEqual(data_vec[2], 'group_pressure')


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super().__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super().__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super().setUp()


if __name__ == '__main__':
    unittest.main()
