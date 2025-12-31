#
#    Copyright (c) 2018-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weewx.xtypes.get_series"""

import functools
import os.path
import sys
import time

import pytest

import weewx
import weewx.units
import weewx.wxformulas
import weewx.xtypes
from parameters import start_ts, stop_ts, interval
from weeutil.weeutil import TimeSpan

month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
month_start_ts = time.mktime(month_start_tt)
month_stop_ts = time.mktime(month_stop_tt)

# We will be using the VaporPressure example, so include it in the path.
import weewx_data
example_dir = os.path.normpath(os.path.join(os.path.dirname(weewx_data.__file__), './examples'))
sys.path.append(example_dir)
# Now we can import it
import vaporpressure

# Register an instance of VaporPressure with the XTypes system:
weewx.xtypes.xtypes.insert(0, vaporpressure.VaporPressure())

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

expected_vapor_pressures = [0.0520073, 0.0516470, None, 0.0532668, 0.0552850, 0.05816286]

expected_aggregate_vapor_pressures = [0.055149, 0.129672, 0.237951,
0.119360, 0.056989, 0.132742, 0.243272, 0.122225, 0.058057,
0.135910, 0.247049, 0.125180, 0.059585, 0.139177, 0.254400,
0.128229, 0.061610, 0.142546, 0.260214, 0.131372, 0.062795,
0.146019, 0.265056, 0.134614, 0.064481, 0.149599, 0.272360,
0.137955, 0.066375, 0.153287, 0.278700, 0.141398, 0.068018,
0.157087, 0.285946, 0.144946, 0.069872, 0.161000, 0.291929,
0.148600, 0.071219, 0.165029, 0.298826, 0.152363, 0.073761,
0.160523, 0.305915, 0.156237, 0.075798, 0.173446, 0.313201,
0.165839, 0.075824, 0.147956, 0.317273, 0.196129, 0.081152,
0.143451, 0.324886, 0.201073, 0.083410, 0.155730, 0.332704,
0.213269, 0.085737, 0.159784, 0.340730, 0.211378, 0.088133,
0.158981, 0.348968, 0.216745, 0.090601, 0.168239, 0.357420,
0.227137, 0.093142, 0.172644, 0.366089, 0.227917, 0.095758,
0.175668, 0.374980, 0.233727, 0.098449, 0.181817, 0.384094,
0.241287, 0.101217, 0.186589, 0.393435, 0.245808, 0.104063,
0.193312, 0.403006, 0.252083, 0.106989, 0.196515, 0.412808,
0.255773, 0.109996, 0.201672, 0.422845, 0.265111, 0.113085,
0.211803, 0.433119, 0.271868, 0.116258, 0.212382, 0.443632,
0.270881, 0.119515, 0.217938, 0.454387, 0.285878, 0.122858,
0.231103, 0.465384, 0.293134, 0.126288, 0.229461, 0.476626,
0.287182]


def test_get_series_archive_outTemp(config_dict):
    """Test a series of outTemp with no aggregation, run against the archive table."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.ArchiveTable.get_series('outTemp',
                                                   TimeSpan(start_ts, stop_ts),
                                                   db_manager)
        assert len(start_vec[0]) == (stop_ts - start_ts) / interval
        assert len(stop_vec[0]) == (stop_ts - start_ts) / interval
        assert len(data_vec[0]) == (stop_ts - start_ts) / interval


def test_get_series_daily_agg_rain_sum(config_dict):
    """Test a series of daily aggregated rain totals, run against the daily summaries"""
    # Calculate the total daily rain
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.DailySummaries.get_series('rain',
                                                     TimeSpan(month_start_ts, month_stop_ts),
                                                     db_manager,
                                                     'sum',
                                                     'day')
    # March has 30 days.
    assert len(start_vec[0]) == 30 + 1
    assert len(stop_vec[0]) == 30 + 1
    assert (["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]) \
           == (["%.2f" % d for d in expected_daily_rain_sum], 'inch', 'group_rain')

def test_get_series_archive_agg_rain_sum(config_dict):
    """Test a series of daily aggregated rain totals, run against the main archive table"""
    # Calculate the total daily rain
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.ArchiveTable.get_series('rain',
                                                   TimeSpan(month_start_ts, month_stop_ts),
                                                   db_manager,
                                                   'sum',
                                                   'day')
    # March has 30 days.
    assert len(start_vec[0]) == 30 + 1
    assert len(stop_vec[0]) == 30 + 1
    assert (["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]) \
                     == (["%.2f" % d for d in expected_daily_rain_sum], 'inch', 'group_rain')

def test_get_series_archive_agg_rain_cum(config_dict):
    """Test a series of daily cumulative rain totals, run against the main archive table."""
    # Calculate the cumulative total daily rain
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.ArchiveTable.get_series('rain',
                                                   TimeSpan(month_start_ts, month_stop_ts),
                                                   db_manager,
                                                   'cumulative',
                                                   24 * 3600)
    # March has 30 days.
    assert len(start_vec[0]) == 30 + 1
    assert len(stop_vec[0]) == 30 + 1
    right_answer = functools.reduce(lambda v, x: v + [v[-1] + x], expected_daily_rain_sum, [0])[1:]
    assert (["%.2f" % d for d in data_vec[0]], data_vec[1], data_vec[2]) \
           ==   (["%.2f" % d for d in right_answer], 'inch', 'group_rain')

def test_get_series_archive_windvec(config_dict):
    """Test a series of 'windvec', with no aggregation, run against the main archive table"""
    # Get a series of wind values
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.WindVec.get_series('windvec',
                                              TimeSpan(start_ts, stop_ts),
                                              db_manager)
    assert len(start_vec[0]) == (stop_ts - start_ts) / interval + 1
    assert len(stop_vec[0]) == (stop_ts - start_ts) / interval + 1
    assert len(data_vec[0]) == (stop_ts - start_ts) / interval + 1

def test_get_series_archive_agg_windvec_avg(config_dict):
    """Test a series of 'windvec', with 'avg' aggregation. This will exercise
    WindVec.get_series(0), which, in turn, will call WindVecDaily.get_aggregate() to get each
    individual aggregate value."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # Get a series of wind values
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.WindVec.get_series('windvec',
                                              TimeSpan(month_start_ts, month_stop_ts),
                                              db_manager,
                                              'avg',
                                              24 * 3600)
    # March has 30 days.
    assert len(start_vec[0]) == 30 + 1
    assert len(stop_vec[0]) == 30 + 1
    assert (["(%.2f, %.2f)" % (x.real, x.imag) for x in data_vec[0]]) \
           == (["(%.2f, %.2f)" % (x[0], x[1]) for x in expected_daily_wind_avg])

def test_get_series_archive_agg_windvec_last(config_dict):
    """Test a series of 'windvec', with 'last' aggregation. This will exercise
    WindVec.get_series(), which, in turn, will call WindVec.get_aggregate() to get each
    individual aggregate value."""
    # Get a series of wind values
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.get_series('windvec',
                                      TimeSpan(month_start_ts, month_stop_ts),
                                      db_manager,
                                      'last',
                                      24 * 3600)
    # March has 30 days.
    assert len(start_vec[0]) == 30 + 1
    assert len(stop_vec[0]) == 30 + 1
    # The round(x, 2) + 0 is necessary to avoid 0.00 comparing different from -0.00.
    assert ["(%.2f, %.2f)" % (round(x.real, 2) + 0, round(x.imag, 2) + 0) for x in data_vec[0]] \
        == ["(%.2f, %.2f)" % (x[0], x[1]) for x in expected_daily_wind_last]

def test_get_aggregate_windvec_last(config_dict):
    """Test getting a windvec aggregation over a period that does not fall on midnight
    boundaries."""

    # This time span was chosen because it includes a null value.
    start_tt = (2010, 3, 2, 12, 0, 0, 0, 0, -1)
    start = time.mktime(start_tt)  # = 1267560000
    stop = start + 6 * 3600

    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # Double check that the null value is in there
        assert db_manager.getRecord(1267570800)['windSpeed'] is None

        # Get a simple 'avg' aggregation over this period
        val_t = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                   TimeSpan(start, stop),
                                                   'avg',
                                                   db_manager)
    assert type(val_t[0]) is complex
    assert val_t[0].real == pytest.approx(15.37441)
    assert val_t[0].imag == pytest.approx(9.79138)
    assert val_t[1] == 'mile_per_hour'
    assert val_t[2] == 'group_speed'

def test_get_series_on_the_fly(config_dict):
    """Test a series of a user-defined type with no aggregation,
    run against the archive table."""

    # This time span was chosen because it includes a null for outTemp at 0330
    start_tt = (2010, 3, 2, 2, 0, 0, 0, 0, -1)
    stop_tt = (2010, 3, 2, 5, 0, 0, 0, 0, -1)
    start = time.mktime(start_tt) # == 1267524000
    stop = time.mktime(stop_tt)   # == 1267534800

    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # Make sure the null outTemp is in there
        assert db_manager.getRecord(1267529400)['outTemp'] is None

        start_vec, stop_vec, data_vec \
            = weewx.xtypes.get_series('vapor_p',
                                      TimeSpan(start, stop),
                                      db_manager)

    for actual, expected in zip(data_vec[0], expected_vapor_pressures):
        assert actual == pytest.approx(expected)
    assert data_vec[1] == 'inHg'
    assert data_vec[2] == 'group_pressure'

def test_get_aggregate_series_on_the_fly(config_dict):
    """Test a series of a user-defined type with aggregation, run against the archive table."""

    start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
    stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
    start = time.mktime(start_tt)
    stop = time.mktime(stop_tt)

    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.get_series('vapor_p',
                                      TimeSpan(start, stop),
                                      db_manager,
                                      aggregate_type='avg',
                                      aggregate_interval=6 * 3600)

    for actual, expected in zip(data_vec[0], expected_aggregate_vapor_pressures):
        assert actual == pytest.approx(expected, abs=1e-6)
    assert data_vec[1] == 'inHg'
    assert data_vec[2] == 'group_pressure'
