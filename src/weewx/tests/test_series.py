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

expected_outTemp_min = [-1.009915, -0.420894, 0.174177, 0.775124, 1.381767, 1.993927, 2.611423,
                        3.234072, 3.861688, 4.494087, 5.13108, 5.77248, 6.418095, 7.067735,
                        7.721207, 8.378318, 9.038872, 9.702674, 10.369528, 11.039235, 11.711598,
                        12.386417, 13.063491, 13.742621, 14.423606, 15.106242, 15.790329,
                        16.475664, 17.162042, 17.849262, 18.537119]

expected_outTemp_max = [39.283828, 39.875896, 40.315346, 41.077745, 41.687169, 42.30202,
                        42.922115, 43.547271, 44.177302, 44.812021, 45.451241, 46.094772,
                        46.742424, 47.394004, 48.04932, 48.708177, 49.370379, 50.035732,
                        50.704037, 51.375097, 52.048713, 52.724684, 53.402812, 54.082894,
                        54.76473, 55.448117, 56.132853, 56.818735, 57.50556, 58.193123,
                        58.881223]

expected_outTemp_count = [48, 47, 47, 48, 47, 47, 48, 47, 47, 48, 47, 47, 47, 46, 47, 47, 48,
                          47, 47, 48, 47, 47, 48, 47, 47, 48, 47, 47, 48, 47, 47]

expected_outTemp_not_null = [True] * 31

expected_outTemp_first = [3.062017, 3.650397, 4.244847, 4.84519, 5.451248, 6.062842, 6.67979,
                          7.301911, 7.929018, 8.560928, 7.757319, 9.838401, 10.483586, 11.132815,
                          15.450449, 16.107041, 16.767106, 17.430446, 18.096867, 18.766171,
                          19.438159, 20.112632, 20.78939, 21.468233, 22.148959, 22.831368,
                          23.515256, 24.200421, 24.88666, 25.573769, 26.261546]

expected_outTemp_last = [5.363008, 5.957333, 6.557555, 7.163496, 7.774976, 8.391815, 9.01383,
                         9.640835, 10.272646, 10.909076, 11.549935, 12.195034, 12.844181,
                         17.612037, 18.268555, 18.928549, 19.591823, 20.258182, 20.927428,
                         21.599362, 22.273785, 22.950497, 23.629299, 24.309988, 24.992364,
                         25.676223, 26.361363, 27.047582, 27.734676, 28.42244, 29.110673]

expected_outTemp_firsttime = [1267432200, 1267518600, 1267605000, 1267691400, 1267777800,
                              1267864200, 1267950600, 1268037000, 1268123400, 1268209800,
                              1268298000, 1268382600, 1268469000, 1268555400, 1268638200,
                              1268724600, 1268811000, 1268897400, 1268983800, 1269070200,
                              1269156600, 1269243000, 1269329400, 1269415800, 1269502200,
                              1269588600, 1269675000, 1269761400, 1269847800, 1269934200,
                              1270020600]

expected_outTemp_lasttime = [1267516800, 1267603200, 1267689600, 1267776000, 1267862400,
                             1267948800, 1268035200, 1268121600, 1268208000, 1268294400,
                             1268380800, 1268467200, 1268553600, 1268636400, 1268722800,
                             1268809200, 1268895600, 1268982000, 1269068400, 1269154800,
                             1269241200, 1269327600, 1269414000, 1269500400, 1269586800,
                             1269673200, 1269759600, 1269846000, 1269932400, 1270018800,
                             1270105200]

expected_outTemp_maxtime = [1267484400, 1267570800, 1267659000, 1267743600, 1267830000,
                            1267916400, 1268002800, 1268089200, 1268175600, 1268262000,
                            1268348400, 1268434800, 1268521200, 1268607600, 1268694000,
                            1268780400, 1268866800, 1268953200, 1269039600, 1269126000,
                            1269212400, 1269298800, 1269385200, 1269471600, 1269558000,
                            1269644400, 1269730800, 1269817200, 1269903600, 1269990000,
                            1270076400]

expected_outTemp_mintime = [1267441200, 1267527600, 1267614000, 1267700400, 1267786800,
                            1267873200, 1267959600, 1268046000, 1268132400, 1268218800,
                            1268305200, 1268391600, 1268478000, 1268564400, 1268650800,
                            1268737200, 1268823600, 1268910000, 1268996400, 1269082800,
                            1269169200, 1269255600, 1269342000, 1269428400, 1269514800,
                            1269601200, 1269687600, 1269774000, 1269860400, 1269946800,
                            1270033200]

expected_outTemp_diff = [0.588252, 0.594325, 0.600222, 0.605941, 0.61148, 0.616839, 0.622015,
                         0.627005, 0.631811, 0.63643, 0.640859, 0.645099, 0.649147, 4.767856,
                         0.656518, 0.659994, 0.663274, 0.666359, 0.669246, 0.671934, 0.674423,
                         0.676712, 0.678802, 0.680689, 0.682376, 0.683859, 0.68514, 0.686219,
                         0.687094, 0.687764, 0.688233]

expected_outTemp_tderiv = [6.808472e-06, 6.878762e-06, 6.947014e-06, 7.013206e-06, 7.077315e-06,
                           7.13934e-06, 7.199248e-06, 7.257002e-06, 7.312627e-06, 7.366088e-06,
                           7.41735e-06, 7.466424e-06, 7.513275e-06, 5.75828e-05, 7.598588e-06,
                           7.638819e-06, 7.676782e-06, 7.712488e-06, 7.745903e-06, 7.777014e-06,
                           7.805822e-06, 7.832315e-06, 7.856505e-06, 7.878345e-06, 7.89787e-06,
                           7.915035e-06, 7.929861e-06, 7.94235e-06, 7.952477e-06, 7.960231e-06,
                           7.96566e-06]

@pytest.mark.parametrize('aggregate_type, expected_values, expected_unit', [
    ('min', expected_outTemp_min, ('degree_F', 'group_temperature')),
    ('max', expected_outTemp_max, ('degree_F', 'group_temperature')),
    ('count', expected_outTemp_count, ('count', 'group_count')),
    ('not_null', expected_outTemp_not_null, ('boolean', 'group_boolean')),
    ('first', expected_outTemp_first, ('degree_F', 'group_temperature')),
    ('last', expected_outTemp_last, ('degree_F', 'group_temperature')),
    ('firsttime', expected_outTemp_firsttime, ('unix_epoch', 'group_time')),
    ('lasttime', expected_outTemp_lasttime, ('unix_epoch', 'group_time')),
    ('maxtime', expected_outTemp_maxtime, ('unix_epoch', 'group_time')),
    ('mintime', expected_outTemp_mintime, ('unix_epoch', 'group_time')),
    ('diff', expected_outTemp_diff, ('degree_F', 'group_temperature')),
    ('tderiv', expected_outTemp_tderiv, ('degree_F', 'group_power')),
])
def test_get_series_archive_agg_outTemp(config_dict, aggregate_type, expected_values,
                                        expected_unit):
    """Test a series of 'outTemp', with daily aggregation, run against the main archive table.
    This exercises the fast, bulk-query path of ArchiveTable.get_series() for the 'core
    scalar' aggregate types. 'diff' and 'tderiv' are not part of the fast path, and instead
    exercise the older, per-bucket fallback loop."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        start_vec, stop_vec, data_vec \
            = weewx.xtypes.ArchiveTable.get_series('outTemp',
                                                   TimeSpan(month_start_ts, month_stop_ts),
                                                   db_manager,
                                                   aggregate_type,
                                                   24 * 3600)
    # March has 31 days.
    assert len(start_vec[0]) == 31
    assert len(stop_vec[0]) == 31
    assert len(data_vec[0]) == 31
    for actual, expected in zip(data_vec[0], expected_values):
        if actual is None or expected is None:
            assert actual == expected
        else:
            assert actual == pytest.approx(expected, abs=1e-6)
    assert (data_vec[1], data_vec[2]) == expected_unit


def test_get_series_archive_agg_query_count(config_dict):
    """Regression test: a fast-path aggregated get_series() call should issue a small, constant
    number of SQL queries, not one per aggregation bucket."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        call_count = [0]
        orig_genSql = db_manager.genSql

        def counting_genSql(*args, **kwargs):
            call_count[0] += 1
            return orig_genSql(*args, **kwargs)

        db_manager.genSql = counting_genSql
        try:
            # Hourly aggregation over a month means about 744 buckets. The fast path should
            # issue only a handful of queries, not one per bucket.
            start_vec, stop_vec, data_vec \
                = weewx.xtypes.ArchiveTable.get_series('outTemp',
                                                       TimeSpan(month_start_ts, month_stop_ts),
                                                       db_manager,
                                                       'avg',
                                                       3600)
        finally:
            db_manager.genSql = orig_genSql

    assert len(data_vec[0]) > 100
    assert call_count[0] < 10


# Page spans used to exercise the paging logic of ArchiveTable.get_series(). A span of 1 second
# results in one bucket per page. A span of 5000 seconds is not a multiple of either the archive
# interval or the aggregation interval.
page_spans = [1, 3600, 5000, 24 * 3600, weewx.xtypes.ArchiveTable.series_page_span]


def _get_hourly_series(db_manager, obs_type, aggregate_type):
    return weewx.xtypes.ArchiveTable.get_series(obs_type,
                                                TimeSpan(month_start_ts, month_stop_ts),
                                                db_manager,
                                                aggregate_type,
                                                3600)


def _assert_series_equal(actual, expected):
    for actual_vt, expected_vt in zip(actual, expected):
        assert actual_vt[1:] == expected_vt[1:]
        assert len(actual_vt[0]) == len(expected_vt[0])
        for a, e in zip(actual_vt[0], expected_vt[0]):
            if a is None or e is None:
                assert a == e
            else:
                assert a == pytest.approx(e, abs=1e-6)


@pytest.mark.parametrize('obs_type', ['outTemp', 'rain', 'wind'])
@pytest.mark.parametrize('aggregate_type',
                         sorted(weewx.xtypes.ArchiveTable._fast_aggregate_types)
                         + ['cumulative'])
def test_get_series_archive_agg_paged(config_dict, monkeypatch, obs_type, aggregate_type):
    """The paged fast path of ArchiveTable.get_series() must give the same results as the
    per-bucket fallback, no matter what the page span is."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # First, get the reference results by forcing the per-bucket fallback.
        with monkeypatch.context() as m:
            m.setattr(weewx.xtypes.ArchiveTable, '_fast_aggregate_types', set())
            expected = _get_hourly_series(db_manager, obs_type, aggregate_type)
        # March has 31 days, less one hour for the DST change.
        assert len(expected[0][0]) == 31 * 24 - 1

        for page_span in page_spans:
            with monkeypatch.context() as m:
                m.setattr(weewx.xtypes.ArchiveTable, 'series_page_span', page_span)
                actual = _get_hourly_series(db_manager, obs_type, aggregate_type)
            _assert_series_equal(actual, expected)


@pytest.mark.parametrize('page_span', page_spans)
def test_get_series_archive_agg_page_bounds(config_dict, monkeypatch, page_span):
    """The number of queries issued by the paged fast path should be about the timespan divided
    by the page span, and no single query should return more than about a page of rows."""
    monkeypatch.setattr(weewx.xtypes.ArchiveTable, 'series_page_span', page_span)
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        row_counts = []
        orig_genSql = db_manager.genSql

        def counting_genSql(*args, **kwargs):
            row_counts.append(0)
            for row in orig_genSql(*args, **kwargs):
                row_counts[-1] += 1
                yield row

        db_manager.genSql = counting_genSql
        try:
            start_vec, stop_vec, data_vec = _get_hourly_series(db_manager, 'outTemp', 'avg')
        finally:
            db_manager.genSql = orig_genSql

    n_buckets = len(data_vec[0])
    assert n_buckets == 31 * 24 - 1
    # Each page holds a whole number of hourly buckets: just enough to span page_span seconds.
    buckets_per_page = max(1, -(-page_span // 3600))
    expected_pages = n_buckets / buckets_per_page
    assert expected_pages - 1 <= len(row_counts) <= expected_pages + 1
    # No single query returns more than a page of rows.
    assert max(row_counts) <= buckets_per_page * 3600 / interval + 1
    if page_span == 24 * 3600:
        assert 30 <= len(row_counts) <= 32


def test_gen_pages():
    """Test grouping buckets into pages."""
    buckets = [TimeSpan(t, t + 10) for t in range(0, 100, 10)]
    pages = list(weewx.xtypes.ArchiveTable._gen_pages(buckets, 25))
    assert pages == [buckets[0:3], buckets[3:6], buckets[6:9], buckets[9:10]]
    pages = list(weewx.xtypes.ArchiveTable._gen_pages(buckets, 1))
    assert pages == [[b] for b in buckets]
    pages = list(weewx.xtypes.ArchiveTable._gen_pages(buckets, 1000))
    assert pages == [buckets]
    assert list(weewx.xtypes.ArchiveTable._gen_pages([], 1000)) == []


def test_get_series_archive_agg_unknown_type(config_dict):
    """A type that is not in the database should fall back to the per-bucket loop, which
    raises UnknownAggregation because no XType can calculate it."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        with pytest.raises(weewx.UnknownAggregation):
            _get_hourly_series(db_manager, 'fooBar', 'avg')
