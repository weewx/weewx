#
#    Copyright (c) 2019-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test aggregate functions."""

import math
import time

import pytest

import weedb
import weewx
import weewx.manager
import weewx.xtypes
from parameters import synthetic_dict
from weeutil.weeutil import TimeSpan
from weewx.units import ValueTuple


def test_get_aggregate(config_dict):
    # Use the same function to test calculating aggregations from the main archive file, as
    # well as from the daily summaries:
    examine_object(config_dict, weewx.xtypes.ArchiveTable)
    examine_object(config_dict, weewx.xtypes.DailySummaries)


def examine_object(weewx_dict, aggregate_obj):
    with weewx.manager.open_manager_with_config(weewx_dict, 'wx_binding') as db_manager:
        month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
        month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(month_start_tt)
        stop_ts = time.mktime(month_stop_tt)

        avg_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts), 'avg',
                                             db_manager)
        assert avg_vt[0] == pytest.approx(28.77, abs=0.01)
        assert avg_vt[1] == 'degree_F'
        assert avg_vt[2] == 'group_temperature'

        max_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                             'max', db_manager)
        assert max_vt[0] == pytest.approx(58.88, abs=0.01)
        maxtime_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                 'maxtime', db_manager)
        assert maxtime_vt[0] == 1270076400

        min_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                             'min', db_manager)
        assert min_vt[0] == pytest.approx(-1.01, abs=0.01)
        mintime_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                 'mintime', db_manager)
        assert mintime_vt[0] == 1267441200

        count_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                               'count', db_manager)
        assert count_vt[0] == 1465

        sum_vt = aggregate_obj.get_aggregate('rain', TimeSpan(start_ts, stop_ts),
                                             'sum', db_manager)
        assert sum_vt[0] == pytest.approx(10.24, abs=0.01)

        not_null_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                  'not_null', db_manager)
        assert not_null_vt[0]
        assert not_null_vt[1] == 'boolean'
        assert not_null_vt[2] == 'group_boolean'

        null_vt = aggregate_obj.get_aggregate('inTemp', TimeSpan(start_ts, stop_ts),
                                              'not_null', db_manager)
        assert not null_vt[0]

        # Values for inTemp in the test database are null for early May, but not null for later
        # in the month. So, for all of May, the aggregate 'not_null' should be True.
        null_start_ts = time.mktime((2010, 5, 1, 0, 0, 0, 0, 0, -1))
        null_stop_ts = time.mktime((2010, 6, 1, 0, 0, 0, 0, 0, -1))
        null_vt = aggregate_obj.get_aggregate('inTemp', TimeSpan(null_start_ts, null_stop_ts),
                                              'not_null', db_manager)
        assert null_vt[0]

        # The ArchiveTable version has a few extra aggregate types:
        if aggregate_obj == weewx.xtypes.ArchiveTable:
            first_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                   'first', db_manager)
            # Get the timestamp of the first record inside the month
            ts = start_ts + synthetic_dict['interval']
            rec = db_manager.getRecord(ts)
            assert first_vt[0] == rec['outTemp']

            first_time_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                        'firsttime',
                                                        db_manager)
            assert first_time_vt[0] == ts

            last_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                  'last', db_manager)
            # Get the timestamp of the last record of the month
            rec = db_manager.getRecord(stop_ts)
            assert last_vt[0] == rec['outTemp']

            last_time_vt = aggregate_obj.get_aggregate('outTemp', TimeSpan(start_ts, stop_ts),
                                                       'lasttime', db_manager)
            assert last_time_vt[0] == stop_ts

            # Use 'dateTime' to check 'diff' and 'tderiv'. The calculations are super easy.
            diff_vt = aggregate_obj.get_aggregate('dateTime', TimeSpan(start_ts, stop_ts),
                                                  'diff', db_manager)
            assert diff_vt[0] == stop_ts - start_ts

            tderiv_vt = aggregate_obj.get_aggregate('dateTime', TimeSpan(start_ts, stop_ts),
                                                    'tderiv', db_manager)
            assert tderiv_vt[0] == pytest.approx(1.0)


def test_AggregateDaily(config_dict):
    """Test special aggregates that can be used against the daily summaries."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
        month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(month_start_tt)
        stop_ts = time.mktime(month_stop_tt)

        min_ge_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                              TimeSpan(start_ts, stop_ts),
                                                              'min_ge',
                                                              db_manager,
                                                              val=ValueTuple(15,
                                                                             'degree_F',
                                                                             'group_temperature'))
        assert min_ge_vt[0] == 6

        min_le_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                              TimeSpan(start_ts, stop_ts),
                                                              'min_le',
                                                              db_manager,
                                                              val=ValueTuple(0,
                                                                             'degree_F',
                                                                             'group_temperature'))
        assert min_le_vt[0] == 2

        minmax_vt = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                              TimeSpan(start_ts, stop_ts),
                                                              'minmax',
                                                              db_manager)
        assert minmax_vt[0] == pytest.approx(39.28, abs=0.01)

        max_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                                TimeSpan(start_ts, stop_ts),
                                                                'max',
                                                                db_manager)
        assert max_wind_vt[0] == pytest.approx(24.0, abs=0.01)

        avg_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                                TimeSpan(start_ts, stop_ts),
                                                                'avg',
                                                                db_manager)
        assert avg_wind_vt[0] == pytest.approx(10.21, abs=0.01)
        # Double check this last one against the average calculated from the archive
        avg_wind_vt = weewx.xtypes.ArchiveTable.get_aggregate('windSpeed',
                                                              TimeSpan(start_ts, stop_ts),
                                                              'avg',
                                                              db_manager)
        assert avg_wind_vt[0] == pytest.approx(10.21, abs=0.01)

        vecavg_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                                   TimeSpan(start_ts, stop_ts),
                                                                   'vecavg',
                                                                   db_manager)
        assert vecavg_wind_vt[0] == pytest.approx(5.14, abs=0.01)

        vecdir_wind_vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                                   TimeSpan(start_ts, stop_ts),
                                                                   'vecdir',
                                                                   db_manager)
        assert vecdir_wind_vt[0] == pytest.approx(88.77, abs=0.01)


def test_get_aggregate_heatcool(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
        month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(month_start_tt)
        stop_ts = time.mktime(month_stop_tt)

        # First, with the default heating base:
        heatdeg = weewx.xtypes.AggregateHeatCool.get_aggregate('heatdeg',
                                                               TimeSpan(start_ts, stop_ts),
                                                               'sum',
                                                               db_manager)
        assert heatdeg[0] == pytest.approx(1123.12, abs=0.01)
        # Now with an explicit heating base:
        heatdeg = weewx.xtypes.AggregateHeatCool.get_aggregate('heatdeg',
                                                               TimeSpan(start_ts, stop_ts),
                                                               'sum',
                                                               db_manager,
                                                               skin_dict={
                                                                   'Units': {'DegreeDays': {
                                                                       'heating_base': (
                                                                           60.0, "degree_F",
                                                                           "group_temperature")
                                                                   }}})
        assert heatdeg[0] == pytest.approx(968.12, abs=0.01)


def test_get_aggregate_windvec(config_dict):
    """Test calculating special type 'windvec' using a variety of methods."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
        month_stop_tt = (2010, 3, 2, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(month_start_tt)
        stop_ts = time.mktime(month_stop_tt)

        # Calculate the daily wind for 1-March-2010 using the daily summaries, the main archive
        # table, and letting get_aggregate() choose.
        for func in [
            weewx.xtypes.WindVecDaily.get_aggregate,
            weewx.xtypes.WindVec.get_aggregate,
            weewx.xtypes.get_aggregate
        ]:
            windvec = func('windvec', TimeSpan(start_ts, stop_ts), 'avg', db_manager)
            assert windvec[0].real == pytest.approx(-1.390, abs=0.001)
            assert windvec[0].imag == pytest.approx(3.250, abs=0.001)
            assert windvec[1:3] == ('mile_per_hour', 'group_speed')

        # Calculate the wind vector for the hour starting at 1-06-2010 15:00
        hour_start_tt = (2010, 1, 6, 15, 0, 0, 0, 0, -1)
        hour_stop_tt = (2010, 1, 6, 16, 0, 0, 0, 0, -1)
        hour_start_ts = time.mktime(hour_start_tt)
        hour_stop_ts = time.mktime(hour_stop_tt)
        vt = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                TimeSpan(hour_start_ts, hour_stop_ts),
                                                'max', db_manager)
        assert abs(vt[0]) == pytest.approx(15.281, abs=0.001)
        assert vt[0].real == pytest.approx(8.069, abs=0.001)
        assert vt[0].imag == pytest.approx(-12.976, abs=0.001)
        vt = weewx.xtypes.WindVec.get_aggregate('windgustvec',
                                                TimeSpan(hour_start_ts, hour_stop_ts),
                                                'max', db_manager)
        assert abs(vt[0]) == pytest.approx(18.337, abs=0.001)
        assert vt[0].real == pytest.approx(9.683, abs=0.001)
        assert vt[0].imag == pytest.approx(-15.572, abs=0.001)

        vt = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                TimeSpan(hour_start_ts, hour_stop_ts),
                                                'not_null', db_manager)
        assert vt[0]
        assert vt[1] == 'boolean'
        assert vt[2] == 'group_boolean'


def test_get_aggregate_expression(config_dict):
    """Test using an expression in an aggregate"""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        month_start_tt = (2010, 7, 1, 0, 0, 0, 0, 0, -1)
        month_stop_tt = (2010, 8, 1, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(month_start_tt)
        stop_ts = time.mktime(month_stop_tt)

        # This one is a valid expression:
        value = weewx.xtypes.get_aggregate('CASE WHEN rain > ET THEN rain-ET ELSE 0 END', TimeSpan(start_ts, stop_ts),
                                           'sum', db_manager)
        assert value[0] == pytest.approx(9.565, abs=0.01)

        # This one uses a nonsense variable:
        with pytest.raises(weewx.UnknownAggregation):
            value = weewx.xtypes.get_aggregate('rain-foo', TimeSpan(start_ts, stop_ts),
                                               'sum', db_manager)

        # Seek aggregate of a valid function.
        value = weewx.xtypes.get_aggregate('CASE WHEN rain > ET THEN rain-ET ELSE 0 END',
                                           TimeSpan(start_ts, stop_ts),
                                           'sum', db_manager)
        assert value[0] == pytest.approx(9.565, abs=0.01)

        # This one uses a nonsense function
        with pytest.raises(weedb.DatabaseError):
            value = weewx.xtypes.get_aggregate('foo(rain-ET)', TimeSpan(start_ts, stop_ts),
                                               'sum', db_manager)


def test_first_wind(config_dict):
    """Test getting the first non-null wind record in a time range."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # Get the first value for 2-Aug-2010. This date was chosen because the wind speed of
        # the very first record of the day (at 00:30:00) is actually null, so the next value
        # (at 01:00:00) should be the one chosen.
        day_start_tt = (2010, 8, 2, 0, 0, 0, 0, 0, -1)
        day_stop_tt = (2010, 8, 3, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(day_start_tt)
        stop_ts = time.mktime(day_stop_tt)
        # Check the premise of the test, aas well as get the expected results
        results = [x for x in db_manager.genSql("SELECT windSpeed, windDir FROM archive "
                                                "WHERE dateTime > ? "
                                                "ORDER BY dateTime ASC LIMIT 2", (start_ts,))]
        # We expect the first datum to be null
        assert results[0][0] is None
        # This is the expected value: the 2nd datum
        windSpeed, windDir = results[1]
        expected = complex(windSpeed * math.cos(math.radians(90.0 - windDir)),
                           windSpeed * math.sin(math.radians(90.0 - windDir)))
        value = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                   TimeSpan(start_ts, stop_ts),
                                                   'first', db_manager)
        assert value[0] == expected
        assert value[1] == 'mile_per_hour'
        assert value[2] == 'group_speed'


def test_last_wind(config_dict):
    """Test getting the last non-null wind record in a time range."""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        # Get the last value for 18-Apr-2010. This date was chosen because the wind speed of
        # the very last record of the day (at 19-Apr-2010 00:00:00) is actually null, so the
        # previous value (at 18-Apr-2010 23:30:00) should be the one chosen.
        day_start_tt = (2010, 4, 18, 0, 0, 0, 0, 0, -1)
        day_stop_tt = (2010, 4, 19, 0, 0, 0, 0, 0, -1)
        start_ts = time.mktime(day_start_tt)
        stop_ts = time.mktime(day_stop_tt)
        # Check the premise of the test, as well as get the expected results
        results = [x for x in db_manager.genSql("SELECT windSpeed, windDir FROM archive "
                                                "WHERE dateTime <= ? "
                                                "ORDER BY dateTime DESC LIMIT 2", (stop_ts,))]
        # We expect the first record (which is the last record of the day) to be null
        assert results[0][0] is None
        # This is the expected value: the 2nd record
        windSpeed, windDir = results[1]
        expected = complex(windSpeed * math.cos(math.radians(90.0 - windDir)),
                           windSpeed * math.sin(math.radians(90.0 - windDir)))
        value = weewx.xtypes.WindVec.get_aggregate('windvec',
                                                   TimeSpan(start_ts, stop_ts),
                                                   'last', db_manager)
        assert value[0] == pytest.approx(expected)
        assert value[1] == 'mile_per_hour'
        assert value[2] == 'group_speed'
