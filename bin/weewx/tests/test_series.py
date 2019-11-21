#
#    Copyright (c) 2018-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weewx.xtypes.get_series"""

import functools
import os.path
import sys
import time
import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

import weewx
import weewx.wxformulas
import weewx.xtypes
import weewx.units
from weeutil.weeutil import TimeSpan

import configobj

import gen_fake_data

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


class Common(object):
    # These are the expected results for March 2010
    expected_daily_rain_sum = [0.0, 0.49, 0.47, 0.0, 0.0, 0.49, 0.47, 0.0, 0.0, 0.49, 0.47,
                               0.0, 0.0, 0.37, 0.59, 0.0, 0.0, 0.37, 0.59, 0.0, 0.0, 0.37,
                               0.59, 0.0, 0.0, 0.37, 0.59, 0.0, 0.0, 0.37, 0.59]
    expected_daily_wind_avg = [(-1.36, 3.21), (11.43, 9.51), (11.30, -9.58), (-1.36, -3.15), (-1.36, 3.23), (11.46, 9.50),
                               (11.26, -9.60), (-1.37, -3.13), (-1.37, 3.24), (11.49, 9.49), (11.23, -9.62), (-1.38, -3.13),
                               (-1.37, 3.19), (11.06, 9.88), (12.13, -9.17), (-1.35, -3.61), (-1.35, 2.79), (10.54, 9.91),
                               (12.15, -9.11), (-1.35, -3.59), (-1.35, 2.80), (10.58, 9.90), (12.12, -9.12), (-1.35, -3.58),
                               (-1.35, 2.82), (10.61, 9.88), (12.09, -9.14), (-1.35, -3.56), (-1.36, 2.83), (10.64, 9.88),
                               (12.06, -9.17)]
    expected_daily_wind_last = [(0.00, 10.00), (20.00, 0.00), (-0.00, -10.00), (0.00, 0.00), (0.00, 10.00),
                                (20.00, 0.00), (0.00, -10.00), (0.00, 0.00), (0.00, 10.00), (20.00, 0.00),
                                (0.00, -10.00), (0.00, 0.00), (0.00, 10.00), (19.94, 1.31), (0.70, -10.63),
                                (-0.02, -0.00), (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63), (-0.02, -0.00),
                                (-0.61, 9.33), (19.94, 1.31), (0.70, -10.63), (-0.02, -0.00), (-0.61, 9.33),
                                (19.94, 1.31), (0.70, -10.63), (-0.02, -0.00), (-0.61, 9.33), (19.94, 1.31),
                                (0.70, -10.63)]

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
        """Test a series of outTemp with no aggregation"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('outTemp',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager)
        self.assertEqual(len(start_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(stop_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(data_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)

    def test_get_series_archive_agg_rain_sum(self):
        """Test a series of daily aggregated rain totals"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the total daily rain
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('rain',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager,
                                                                    'sum',
                                                                    24 * 3600)
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                         (["%.2f" % d for d in Common.expected_daily_rain_sum], 'inch', 'group_rain'))

    def test_get_series_archive_agg_rain_cum(self):
        """Test a series of daily cumulative rain totals"""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the cumulative total daily rain
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('rain',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager,
                                                                    'cumulative',
                                                                    24 * 3600)
        # March has 30 days.
        self.assertEqual(len(start_vec[0]), 30 + 1)
        self.assertEqual(len(stop_vec[0]), 30 + 1)
        right_answer = functools.reduce(lambda v, x: v + [v[-1] + x], Common.expected_daily_rain_sum, [0])[1:]
        self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                         (["%.2f" % d for d in right_answer], 'inch', 'group_rain'))

    def test_get_series_archive_windvec(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a series of wind values
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('windvec',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager)
        self.assertEqual(len(start_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(stop_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
        self.assertEqual(len(data_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)

    def test_get_series_archive_agg_windvec_avg(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Get a series of wind values
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('windvec',
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
        self.assertEqual((["(%.2f, %.2f)" % (x.real, x.imag) for x in data_vec[0]]),
                         (["(%.2f, %.2f)" % (x[0], x[1]) for x in Common.expected_daily_wind_last]))


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
    tests = [
        'test_get_series_archive_outTemp',
        'test_get_series_archive_agg_rain_sum',
        'test_get_series_archive_agg_rain_cum',
        'test_get_series_archive_windvec',
        'test_get_series_archive_agg_windvec_avg',
        'test_get_series_archive_agg_windvec_last',
    ]
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))
    # return unittest.TestSuite(list(map(TestSqlite, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
