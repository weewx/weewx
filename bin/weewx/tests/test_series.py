#
#    Copyright (c) 2018-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weewx.xtypes.get_series"""

import functools
import math
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

class VaporPressure(weewx.xtypes.XType):
    """Calculate VaporPressure. Used to test generating series of a user-defined type."""

    def get_scalar(self, obs_type, record, db_manager):
        # We only know how to calculate 'vapor_p'. For everything else, raise an exception
        if obs_type != 'vapor_p':
            raise weewx.UnknownType(obs_type)

        # We need outTemp in order to do the calculation.
        if 'outTemp' not in record or record['outTemp'] is None:
            raise weewx.CannotCalculate(obs_type)

        # We have everything we need. Start by forming a ValueTuple for the outside temperature.
        # To do this, figure out what unit and group the record is in ...
        unit_and_group = weewx.units.getStandardUnitType(record['usUnits'], 'outTemp')
        # ... then form the ValueTuple.
        outTemp_vt = weewx.units.ValueTuple(record['outTemp'], *unit_and_group)

        # We need the temperature in Kelvin
        outTemp_K_vt = weewx.units.convert(outTemp_vt, 'degree_K')

        # Now we can use the formula. Results will be in mmHg. Create a ValueTuple out of it:
        p_vt = weewx.units.ValueTuple(math.exp(20.386 - 5132.0 / outTemp_K_vt[0]),
                                      'mmHg',
                                      'group_pressure')

        # We have the vapor pressure as a ValueTuple. Convert it back to the units used by
        # the incoming record and return it
        return weewx.units.convertStd(p_vt, record['usUnits'])


# Register vapor pressure
weewx.units.obs_group_dict['vapor_p'] = "group_pressure"
# Instantiate and register an instance of VaporPressure:
weewx.xtypes.xtypes.append(VaporPressure())


class Common(object):
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
    expected_aggregate_vapor_pressures = [0.055, 0.130, 0.238, 0.119, None, 0.133, 0.243, 0.122,
                                          0.058, 0.136, None, 0.125, 0.060, 0.139, 0.254, 0.128,
                                          None, 0.143, 0.260, 0.131, 0.063, 0.146, None, 0.135,
                                          0.064, 0.150, 0.272, 0.138, None, 0.153, 0.279, 0.141,
                                          0.068, 0.157, None, 0.145, 0.070, 0.161, 0.292, 0.149,
                                          None, 0.165, 0.299, 0.152, 0.074, None, 0.306, 0.156,
                                          0.076, 0.173, 0.313, None, 0.076, 0.148, 0.317, 0.196,
                                          0.081, None, 0.325, 0.201, 0.083, 0.156, 0.333, None,
                                          0.086, 0.160, 0.341, 0.211, 0.088, None, 0.349, 0.217,
                                          0.091, 0.168, 0.357, None, 0.093, 0.173, 0.366, 0.228,
                                          0.096, None, 0.375, 0.234, 0.098, 0.182, 0.384, None,
                                          0.101, 0.187, 0.393, 0.246, 0.104, None, 0.403, 0.252,
                                          0.107, 0.197, 0.413, None, 0.110, 0.202, 0.423, 0.265,
                                          0.113, None, 0.433, 0.272, 0.116, 0.212, 0.444, None,
                                          0.120, 0.218, 0.454, 0.286, 0.123, None, 0.465, 0.293,
                                          0.126, 0.229, 0.477, None]
    # These are the expected cumulative rain results for 10 March 2010
    expected_hourly_rain_cumulative = [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                       0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.08,
                                       0.20, 0.36, 0.52, 0.68]
    expected_hourly_rain_cumulative_2200_reset = [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                  0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                  0.00, 0.00, 0.00, 0.08, 0.20, 0.00, 0.16, 0.32]
    # These are the expected cumulative rain results for 10-11 March 2010
    expected_hourly_rain_cumulative_midnight_reset = [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                      0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                      0.00, 0.00, 0.00, 0.00, 0.00, 0.08, 0.20,
                                                      0.36, 0.52, 0.00, 0.16, 0.32, 0.48, 0.56,
                                                      0.60, 0.60, 0.60, 0.60, 0.60, 0.60, 0.60,
                                                      0.60, 0.60, 0.60, 0.60, 0.60, 0.60, 0.60,
                                                      0.60, 0.60, 0.60, 0.60, 0.60, 0.60]
    # These are the expected cumulative rain results for 31 March-1 April 2010
    expected_hourly_rain_cumulative_month_reset = [0.16, 0.32, 0.48, 0.64, 0.72, 0.76, 0.76, 0.76,
                                                   0.76, 0.76, 0.76, 0.76, 0.76, 0.76, 0.76, 0.76,
                                                   0.76, 0.76, 0.76, 0.76, 0.76, 0.76, 0.76, 0.00,
                                                   0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                   0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
                                                   0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00]


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

    def test_get_series_agg_rain_cumulative(self):
        """Test a series of cumulative rain totals."""

        day_start_tt = (2010, 3, 10, 0, 0, 0, 0, 0, -1)
        day_stop_tt = (2010, 3, 11, 0, 0, 0, 0, 0, -1)
        day_start_ts = time.mktime(day_start_tt)
        day_stop_ts = time.mktime(day_stop_tt)
        next_day_stop_tt = (2010, 3, 12, 0, 0, 0, 0, 0, -1)
        next_day_stop_ts = time.mktime(next_day_stop_tt)
        last_day_start_tt = (2010, 3, 31, 0, 0, 0, 0, 0, -1)
        first_day_stop_tt = (2010, 4, 2, 0, 0, 0, 0, 0, -1)
        last_day_start_ts = time.mktime(last_day_start_tt)
        first_day_stop_ts = time.mktime(first_day_stop_tt)
        year_start_tt = (2010, 3, 10, 0, 0, 0, 0, 0, -1)
        year_stop_tt = (2012, 7, 21, 0, 0, 0, 0, 0, -1)
        year_start_ts = time.mktime(year_start_tt)
        year_stop_ts = time.mktime(year_stop_tt)
        reset_2011_1_1_tt = (2011, 1, 1, 0, 0, 0, 0, 0, -1)
        reset_2012_1_1_tt = (2012, 1, 1, 0, 0, 0, 0, 0, -1)
        reset_2011_1_1_ts = time.mktime(reset_2011_1_1_tt)
        reset_2012_1_1_ts = time.mktime(reset_2012_1_1_tt)

        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            # Calculate the hourly rain totals for the day
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.Cumulative.get_series('rain',
                                                       TimeSpan(day_start_ts, day_stop_ts),
                                                       db_manager,
                                                       'cumulative',
                                                       3600)
            # There should be 24 elements in each vector, one for each hour of
            # the day
            self.assertEqual(len(start_vec[0]), 24)
            self.assertEqual(len(stop_vec[0]), 24)
            self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                            (["%.2f" % d for d in Common.expected_hourly_rain_cumulative], 'inch',
                             'group_rain'))

            # Test 22:00 reset

            # Calculate the hourly rain totals for the day with a 10pm reset
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.Cumulative.get_series('rain',
                                                     TimeSpan(day_start_ts, day_stop_ts),
                                                     db_manager,
                                                    'cumulative',
                                                    3600,
                                                     reset='22:00')
            # There should be 24 elements in each vector, one for each hour of
            # the day
            self.assertEqual(len(start_vec[0]), 24)
            self.assertEqual(len(stop_vec[0]), 24)
            self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                            (["%.2f" % d for d in Common.expected_hourly_rain_cumulative_2200_reset],
                             'inch', 'group_rain'))

            # Test midnight keyword reset

            # Calculate the hourly rain totals for the two-day period with a
            # midnight reset
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.Cumulative.get_series('rain',
                                                     TimeSpan(day_start_ts, next_day_stop_ts),
                                                     db_manager,
                                                    'cumulative',
                                                    3600,
                                                     reset='midnight')
            # There should be 48 elements in each vector, one for each hour of
            # the two day period
            self.assertEqual(len(start_vec[0]), 48)
            self.assertEqual(len(stop_vec[0]), 48)
            self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                            (["%.2f" % d for d in Common.expected_hourly_rain_cumulative_midnight_reset],
                             'inch', 'group_rain'))

            # Test month keyword reset

            # Calculate the hourly rain totals for the two-day period with a
            # month reset
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.Cumulative.get_series('rain',
                                                     TimeSpan(last_day_start_ts, first_day_stop_ts),
                                                     db_manager,
                                                    'cumulative',
                                                    3600,
                                                     reset='month')
            # There should be 48 elements in each vector, one for each hour of
            # the two day period
            self.assertEqual(len(start_vec[0]), 48)
            self.assertEqual(len(stop_vec[0]), 48)
            self.assertEqual((["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]),
                            (["%.2f" % d for d in Common.expected_hourly_rain_cumulative_month_reset],
                             'inch', 'group_rain'))

            # Limitations of the test database prevent full testing of the
            # 'year' keyword reset. Best we can do is test the parsing of the
            # 'year' keyword reset option.

            res = weewx.xtypes.Cumulative.parse_reset('year',
                                                      TimeSpan(year_start_ts, year_stop_ts))
            self.assertListEqual(res, [reset_2011_1_1_ts, reset_2012_1_1_ts])

            # Test weewx.xtypes.Cumulative supporting methods

            # The tests so far test the supporting methods with valid data.
            # Rather than repeat these expensive tests with corner cases we can
            # test the supporting methods only. parse_time() and get_ts_list()
            # can be adequately tested by testing parse_reset() meaning we only
            # need test parse_reset().

            # Test parse_reset()

            # reset_opt is None, should see None
            res = weewx.xtypes.Cumulative.parse_reset(None,
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertIsNone(res)
            # invalid time format, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('2345',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268208000,])
            # invalid time, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('24:32',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268208000,])
            # invalid day-time format, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('1212:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268208000,])
            # invalid day-time, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('32T12:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268251500,])
            # invalid month, day-time format, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('1/12T12:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268251500,])
            # invalid month, day-time, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('13-01T12:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268251500,])
            # invalid date-time format, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('2023/01/12T12:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268251500,])
            # invalid date-time, we should see midnight
            res = weewx.xtypes.Cumulative.parse_reset('2023-13-05T12:05',
                                                      TimeSpan(day_start_ts, day_stop_ts))
            self.assertListEqual(res, [1268251500,])
            # reset option that cannot be parsed, we should see a
            # weewx.ViolatedPrecondition exception
            self.assertRaises(weewx.ViolatedPrecondition,
                              weewx.xtypes.Cumulative.parse_reset,
                              reset_opt='T201T0-03-32T12:00',
                              timespan=TimeSpan(day_start_ts, day_stop_ts))


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


def suite():
    tests = [
        'test_get_series_archive_outTemp',
        'test_get_series_daily_agg_rain_sum',
        'test_get_series_archive_agg_rain_sum',
        'test_get_series_archive_windvec',
        'test_get_series_archive_agg_windvec_avg',
        'test_get_series_archive_agg_windvec_last',
        'test_get_aggregate_windvec_last',
        'test_get_series_on_the_fly',
        'test_get_aggregate_series_on_the_fly',
        'test_get_series_agg_rain_cumulative',
    ]
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))
    # return unittest.TestSuite(list(map(TestSqlite, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
