"""Check query counts without discarding binding, calendar, or weighting semantics."""

import datetime
import os
import time
import tracemalloc

import pytest

import weeutil.weeutil
import weewx.manager
import weewx.tags
import weewx.units
import weewx.xtypes


@pytest.fixture(autouse=True)
def local_timezone():
    previous = os.environ.get('TZ')
    os.environ['TZ'] = 'Europe/Berlin'
    time.tzset()
    yield
    if previous is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = previous
    time.tzset()


@pytest.fixture
def managers():
    schema = {'table': [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
                        ('usUnits', 'INTEGER NOT NULL'), ('interval', 'INTEGER NOT NULL'),
                        ('outTemp', 'REAL'), ('outHumidity', 'REAL'), ('windSpeed', 'REAL')],
              'day_summaries': [('outTemp', 'scalar'), ('outHumidity', 'scalar'),
                                ('windSpeed', 'scalar')]}
    result = {}
    for name, offset in [('wx_binding', 0), ('alt_binding', 100)]:
        manager = weewx.manager.DaySummaryManager.open_with_create(
            {'driver': 'weedb.sqlite', 'database_name': ':memory:'}, schema=schema)
        manager.addRecord([{'dateTime': stamp, 'usUnits': weewx.METRICWX, 'interval': 5,
                            'outTemp': value + offset if value is not None else None,
                            'outHumidity': 50, 'windSpeed': 0}
                           for stamp, value in [(300, 0), (600, None), (900, 20)]],
                          log_success=False, log_failure=False)
        result[name] = manager
    yield result
    for manager in result.values():
        manager.close()


@pytest.mark.parametrize('binding', [None, 'wx_binding', 'alt_binding'])
def test_record_iteration_reuses_rows_from_its_binding(managers, binding):
    manager = managers[binding or 'wx_binding']
    statements = []
    manager.connection.connection.set_trace_callback(statements.append)
    binder = weewx.tags.TimespanBinder(weeutil.weeutil.TimeSpan(0, 900),
                                      lambda name: managers[name or 'wx_binding'],
                                      data_binding=binding,
                                      converter=weewx.units.StdUnitConverters[weewx.METRICWX])
    actual = [(record.outTemp.raw, record.outHumidity.raw, record.windSpeed.raw)
              for record in binder.records()]
    offset = 100 if binding == 'alt_binding' else 0
    assert actual == [(offset, 50, 0), (None, 50, 0), (20 + offset, 50, 0)]
    assert len(statements) == 1, 'Iteration re-read archive rows for individual fields'


def test_default_record_cannot_supply_an_explicit_other_binding(managers):
    record = managers['wx_binding'].getRecord(300)
    current = weewx.tags.CurrentObj(lambda name: managers[name or 'wx_binding'],
                                    'alt_binding', 300, None, None, record=record)
    assert current.outTemp.raw == 100


def test_record_iteration_does_not_keep_rows_between_calls(managers):
    binder = weewx.tags.TimespanBinder(weeutil.weeutil.TimeSpan(0, 300),
                                      lambda name: managers['alt_binding'],
                                      data_binding='alt_binding',
                                      converter=weewx.units.StdUnitConverters[weewx.METRICWX])
    assert next(binder.records()).outTemp.raw == 100
    managers['alt_binding'].updateValue(300, 'outTemp', 123)
    assert next(binder.records()).outTemp.raw == 123


def test_wrong_timestamp_does_not_use_supplied_record(managers):
    record = managers['wx_binding'].getRecord(300)
    current = weewx.tags.CurrentObj(lambda name: managers['wx_binding'],
                                    None, 900, None, None, record=record)
    assert current.outTemp.raw == 20


@pytest.mark.parametrize('units', [weewx.US, weewx.METRICWX])
@pytest.mark.parametrize('first_date', [datetime.date(2025, 3, 29), datetime.date(2025, 10, 25)])
@pytest.mark.parametrize('observation,total', [('heatdeg', 21), ('cooldeg', 8), ('growdeg', 25)])
@pytest.mark.parametrize('aggregate', ['sum', 'avg', 'not_null'])
def test_degree_days_batch_weighted_days(units, first_date,
                                         observation, total, aggregate):
    records = []
    # Two unequal weights make the first day's mean 15 C, rather than 10 C.
    for day, celsius, interval in [(0, 0, 5), (0, 20, 15), (1, 0, 5),
                                    (2, None, 5), (4, 30, 5)]:
        date = first_date + datetime.timedelta(days=day)
        stamp = int(time.mktime(date.timetuple())) + 12 * 3600 + interval * 60
        value = celsius if celsius is None or units != weewx.US else celsius * 1.8 + 32
        records.append({'dateTime': stamp, 'usUnits': units, 'interval': interval,
                         'outTemp': value})
    # Use a separate archive so unit changes are not mixed into one database.
    schema = {'table': [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
                        ('usUnits', 'INTEGER NOT NULL'), ('interval', 'INTEGER NOT NULL'),
                        ('outTemp', 'REAL')], 'day_summaries': [('outTemp', 'scalar')]}
    with weewx.manager.DaySummaryManager.open_with_create(
            {'driver': 'weedb.sqlite', 'database_name': ':memory:'}, schema=schema) as manager:
        manager.addRecord(records, log_success=False)
        statements = []
        manager.connection.connection.set_trace_callback(statements.append)
        options = {'skin_dict': {'Units': {'DegreeDays': {
            'heating_base': ('18', 'degree_C'), 'cooling_base': ('22', 'degree_C'),
            'growing_base': ('10', 'degree_C')}}}}
        span = weeutil.weeutil.TimeSpan(records[0]['dateTime'], records[-1]['dateTime'])
        actual = weewx.xtypes.AggregateHeatCool.get_aggregate(
            observation, span, aggregate, manager, **options)
        expected = True if aggregate == 'not_null' else total / (3 if aggregate == 'avg' else 1)
        if units == weewx.US and aggregate != 'not_null':
            expected *= 1.8
        assert actual[0] == pytest.approx(expected)
        assert actual[1:] == (('boolean', 'group_boolean') if aggregate == 'not_null'
                              else ('degree_F_day' if units == weewx.US else 'degree_C_day',
                                    'group_degree_day'))
        assert len(statements) == 1, 'Degree days issued one query per calendar day'


@pytest.mark.parametrize('aggregate,expected', [('sum', 0), ('avg', None), ('not_null', False)])
@pytest.mark.parametrize('span', [(-3600, -3600), (86400, 86400), (172800, 259200)])
def test_degree_days_empty_days(managers, aggregate, expected, span):
    result = weewx.xtypes.AggregateHeatCool.get_aggregate(
        'heatdeg', span, aggregate, managers['wx_binding'])
    assert result[0] == expected


def test_degree_days_memory_does_not_grow_with_calendar_length(managers):
    manager = managers['wx_binding']
    expected = weewx.xtypes.AggregateHeatCool.get_aggregate('heatdeg', (0, 900), 'sum', manager)
    start = time.mktime(datetime.date(1930, 1, 1).timetuple())
    stop = time.mktime(datetime.date(2030, 1, 1).timetuple())
    tracemalloc.start()
    try:
        actual = weewx.xtypes.AggregateHeatCool.get_aggregate(
            'heatdeg', (start, stop), 'sum', manager)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert actual == expected
    assert peak < 128 * 1024, 'Degree days materialized the calendar instead of its bounds'


@pytest.mark.parametrize('span', [(-3600, -3600), (-3600, -3599.5), (-3600, -3599),
                                 (0, 0), (0, 82800), (0, 82800.5), (0, 82801),
                                 (82800, 82800.5), (82800, 82801), (86400, 86400)])
def test_degree_day_bounds_match_calendar_iteration(managers, span):
    manager = managers['wx_binding']
    manager.addRecord({'dateTime': 86400, 'usUnits': weewx.METRICWX, 'interval': 5,
                       'outTemp': 0}, log_success=False)
    base = weewx.units.convertStd(weewx.xtypes.AggregateHeatCool.default_heatbase,
                                  manager.std_unit_system)[0]
    expected = 0.0
    for day in weeutil.weeutil.genDaySpans(*span):
        average = weewx.xtypes.DailySummaries.get_aggregate('outTemp', day, 'avg', manager)[0]
        if average is not None:
            expected += max(base - average, 0)
    assert weewx.xtypes.AggregateHeatCool.get_aggregate(
        'heatdeg', span, 'sum', manager)[0] == pytest.approx(expected)


@pytest.mark.parametrize('target,delta,expected', [
    (300, None, 300), (300, 0, 300), (301, 0, None), (300, 300, 300),
    (450, 300, 300), (451, 300, 600), (449.5, 300.5, 300),
    (150, 150, 300), (150, 149, None), (1050, 150, 900), (1050, 149, None),
    (-100, 50, None), (300, -1, None)])
def test_nearest_record_boundaries(managers, target, delta, expected):
    result = managers['wx_binding'].getRecord(target, delta)
    assert (result['dateTime'] if result else None) == expected


def test_wide_nearest_lookup_does_not_scan_the_time_window(managers):
    manager = managers['wx_binding']
    manager.addRecord([{'dateTime': stamp, 'usUnits': weewx.METRICWX, 'interval': 5,
                        'outTemp': 1} for stamp in range(1200, 301200, 300)],
                      log_success=False)
    steps = []
    raw = manager.connection.connection
    raw.set_progress_handler(lambda: steps.append(1), 100)
    try:
        assert manager.getRecord(150001, 1000000)['dateTime'] == 150000
    finally:
        raw.set_progress_handler(None, 0)
    assert len(steps) < 50, 'Nearest lookup scanned and sorted the full time window'
