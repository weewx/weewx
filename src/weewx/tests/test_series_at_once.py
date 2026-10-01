#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""ArchiveTable.get_series() calculates many buckets at once, and must not change a value.

Each test gets a series twice: as get_series() calculates it, and with the calculation at
once turned off, i.e., bucket by bucket through get_aggregate(). The two must be the same.
See weewx.xtypes._at_once().
"""

import time

import pytest

import weedb.sqlite
import weewx
import weewx.manager
import weewx.xtypes
from weeutil.weeutil import TimeSpan
from weewx.units import ValueTuple


class Twice(weewx.xtypes.XType):
    """The type 'twice_outTemp', which is not in the database. XTypeTable aggregates it."""

    def get_scalar(self, obs_type, record, db_manager=None, **option_dict):
        if obs_type != 'twice_outTemp':
            raise weewx.UnknownType(obs_type)
        if record['outTemp'] is None:
            raise weewx.CannotCalculate(obs_type)
        return ValueTuple(2.0 * record['outTemp'], 'degree_F', 'group_temperature')


@pytest.fixture(scope='module', autouse=True)
def twice():
    """Put Twice ahead of every other xtype. It has no get_aggregate() of its own, so it does
    not keep get_series() from calculating at once."""
    xtype = Twice()
    weewx.xtypes.xtypes.insert(0, xtype)
    yield
    weewx.xtypes.xtypes.remove(xtype)


def ts(year, month, day, hour):
    """Return the timestamp of a local time, on the hour."""
    return int(time.mktime((year, month, day, hour, 0, 0, 0, 0, -1)))


# Timespans of the synthetic database, which runs from 2010-01-01 to 2010-09-03 in
# America/Los_Angeles. DST began on 2010-03-14.
SPANS = {
    'a month across a change of DST': TimeSpan(ts(2010, 3, 1, 7), ts(2010, 4, 1, 7)),
    # Its daily buckets begin at midnight, so the daily summaries take most of them.
    'days from midnight': TimeSpan(ts(2010, 3, 10, 0), ts(2010, 3, 20, 5)),
    'from before the first record': TimeSpan(ts(2009, 12, 31, 22), ts(2010, 1, 3, 5)),
}
INTERVALS = (1800, 3 * 3600, 86400)

CASES = [('outTemp', aggregate_type) for aggregate_type in (
    'avg', 'sum', 'count', 'min', 'max', 'not_null', 'first', 'last', 'firsttime', 'lasttime',
    'mintime', 'maxtime', 'diff')] + [
    ('rain', 'sum'), ('rain', 'cumulative'),
    ('wind', 'avg'), ('wind', 'max'), ('wind', 'maxtime'), ('wind', 'vecdir'), ('wind', 'vecavg'),
    ('wind', 'gustdir'),
    ('windvec', 'avg'), ('windvec', 'sum'), ('windvec', 'max'), ('windgustvec', 'avg'),
    ('twice_outTemp', 'avg'), ('twice_outTemp', 'sum'), ('twice_outTemp', 'max'),
    ('twice_outTemp', 'mintime'), ('twice_outTemp', 'not_null'),
]


def both_ways(db_manager, monkeypatch, obs_type, timespan, aggregate_type, aggregate_interval):
    """Return the series as calculated at once, as calculated bucket by bucket, and how many
    buckets were calculated at once. A series that raises is returned as the exception."""
    calculated = []
    at_once = weewx.xtypes._at_once

    def counting(*args):
        for bucket, agg_vt in at_once(*args):
            if agg_vt is not None:
                calculated.append(bucket)
            yield bucket, agg_vt

    def one_by_one(obs_type, buckets, aggregate_type, db_manager):
        for bucket in buckets:
            yield bucket, None

    def series():
        try:
            return weewx.xtypes.get_series(obs_type, timespan, db_manager, aggregate_type,
                                           aggregate_interval)
        except Exception as e:
            return e

    with monkeypatch.context() as patch:
        patch.setattr(weewx.xtypes, '_at_once', counting)
        fast = series()
    with monkeypatch.context() as patch:
        patch.setattr(weewx.xtypes, '_at_once', one_by_one)
        slow = series()
    return fast, slow, len(calculated)


def assert_same(fast, slow, label):
    if isinstance(slow, Exception) or isinstance(fast, Exception):
        # Both fail, and in the same way.
        assert type(fast) is type(slow), (label, fast, slow)
        return
    assert fast[0] == slow[0], label
    assert fast[1] == slow[1], label
    assert fast[2][1:] == slow[2][1:], label
    assert len(fast[2][0]) == len(slow[2][0]), label
    for i, (a, b) in enumerate(zip(fast[2][0], slow[2][0])):
        if isinstance(a, float) and isinstance(b, float):
            # The database may add up in another order.
            assert a == pytest.approx(b, rel=1e-12, abs=1e-12), (label, i)
        else:
            assert a == b, (label, i)


@pytest.mark.parametrize('obs_type, aggregate_type', CASES)
def test_at_once_gives_what_get_aggregate_gives(config_dict, monkeypatch, obs_type,
                                                aggregate_type):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        for name, timespan in SPANS.items():
            for aggregate_interval in INTERVALS:
                fast, slow, _ = both_ways(db_manager, monkeypatch, obs_type, timespan,
                                          aggregate_type, aggregate_interval)
                assert_same(fast, slow, (name, aggregate_interval))


@pytest.mark.parametrize('aggregate_type', ['vecdir', 'vecavg'])
def test_sqlite_without_math_functions(config_dict, monkeypatch, aggregate_type):
    """Without math functions, SQLite cannot take 'vecdir' and 'vecavg'. Python does."""
    if config_dict['DataBindings']['wx_binding']['database'] != 'archive_sqlite':
        pytest.skip('only SQLite can lack math functions')
    monkeypatch.setattr(weedb.sqlite, 'has_math', False)
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        assert not db_manager.connection.has_math
        fast, slow, calculated = both_ways(db_manager, monkeypatch, 'wind',
                                           SPANS['a month across a change of DST'],
                                           aggregate_type, 3600)
    assert calculated > 700
    assert_same(fast, slow, aggregate_type)


@pytest.mark.parametrize('obs_type, aggregate_type, expected', [
    ('outTemp', 'avg', 'all'),
    ('wind', 'vecdir', 'all'),
    ('windvec', 'avg', 'all'),
    ('twice_outTemp', 'avg', 'all'),
    ('outTemp', 'diff', 'none'),
    ('windvec', 'max', 'none'),
])
def test_which_buckets_are_calculated_at_once(config_dict, monkeypatch, obs_type,
                                              aggregate_type, expected):
    """A month of hourly buckets is calculated at once, unless only get_aggregate() can."""
    timespan = SPANS['a month across a change of DST']
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        fast, _, calculated = both_ways(db_manager, monkeypatch, obs_type, timespan,
                                        aggregate_type, 3600)
    assert calculated == (len(fast[0][0]) if expected == 'all' else 0)


def test_an_xtype_with_its_own_aggregates_turns_it_off(config_dict, monkeypatch):
    """An xtype ahead of ArchiveTable that has a get_aggregate() of its own could take any
    bucket. So every bucket goes to get_aggregate()."""

    class Grabby(weewx.xtypes.XType):
        def get_aggregate(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):
            raise weewx.UnknownType(obs_type)

    monkeypatch.setattr(weewx.xtypes, 'xtypes', [Grabby()] + weewx.xtypes.xtypes)
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        _, _, calculated = both_ways(db_manager, monkeypatch, 'outTemp',
                                     SPANS['a month across a change of DST'], 'avg', 3600)
    assert calculated == 0


def test_a_bucket_xtypetable_gives_up_on_goes_to_the_next_xtype(config_dict, monkeypatch):
    """XTypeTable gives up on a bucket as soon as get_scalar() does not know the type for one
    of its records. get_aggregate() then asks the xtypes after it, for that bucket only."""

    class Picky(weewx.xtypes.XType):
        """Knows 'picky_outTemp' only below 40 degrees, and aggregates the rest as -1."""

        def get_scalar(self, obs_type, record, db_manager=None, **option_dict):
            if obs_type != 'picky_outTemp' or (record['outTemp'] or 0.0) >= 40.0:
                raise weewx.UnknownType(obs_type)
            return ValueTuple(record['outTemp'], 'degree_F', 'group_temperature')

    class Rest(weewx.xtypes.XType):
        def get_aggregate(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):
            if obs_type != 'picky_outTemp':
                raise weewx.UnknownType(obs_type)
            return ValueTuple(-1.0, 'degree_F', 'group_temperature')

    monkeypatch.setattr(weewx.xtypes, 'xtypes',
                        [Picky()] + weewx.xtypes.xtypes + [Rest()])
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        fast, slow, calculated = both_ways(db_manager, monkeypatch, 'picky_outTemp',
                                           SPANS['a month across a change of DST'], 'avg', 3600)
    assert_same(fast, slow, 'picky')
    assert -1.0 in fast[2][0] and calculated


def test_a_month_of_hourly_buckets_takes_a_few_queries(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        queries = []
        gen_sql, get_sql = db_manager.genSql, db_manager.getSql
        db_manager.genSql = lambda *args: queries.append(args) or gen_sql(*args)
        db_manager.getSql = lambda *args: queries.append(args) or get_sql(*args)
        try:
            series = weewx.xtypes.get_series('outTemp', SPANS['a month across a change of DST'],
                                             db_manager, 'avg', 3600)
        finally:
            db_manager.genSql, db_manager.getSql = gen_sql, get_sql
    assert len(series[0][0]) > 700
    assert len(queries) <= 3


# ---------------------------------------------------------------------------------------------
# Archive records made for the purpose, in a SQLite database of their own.

@pytest.fixture
def made_db(tmp_path):
    """Return a function that writes archive records into a new database, and opens it."""

    def make(records):
        database_dict = {'database_name': str(tmp_path / 'made.sdb'), 'driver': 'weedb.sqlite'}
        manager = weewx.manager.DaySummaryManager.open_with_create(
            database_dict, schema=[('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                                   ('usUnits', 'INTEGER NOT NULL'),
                                   ('interval', 'INTEGER NOT NULL'),
                                   ('outTemp', 'REAL')])
        manager.addRecord(records)
        return manager

    return make


def test_daily_buckets_keep_the_time_weighted_average(made_db, monkeypatch):
    """The daily summaries weigh each record by its archive interval. A daily bucket they
    take must keep that average, also where the archive interval changes within the day."""
    midnight = ts(2010, 6, 1, 0)
    records = []
    # Five minutes in the morning, at 10 degrees, an hour in the afternoon, at 20.
    for t in range(midnight + 300, midnight + 12 * 3600 + 1, 300):
        records.append({'dateTime': t, 'usUnits': weewx.US, 'interval': 5, 'outTemp': 10.0})
    for t in range(midnight + 13 * 3600, midnight + 86400 + 1, 3600):
        records.append({'dateTime': t, 'usUnits': weewx.US, 'interval': 60, 'outTemp': 20.0})
    for t in range(midnight + 86400 + 300, midnight + 2 * 86400 + 1, 300):
        records.append({'dateTime': t, 'usUnits': weewx.US, 'interval': 5, 'outTemp': 15.0})
    manager = made_db(records)
    try:
        # It ends before midnight, so DailySummaries.get_series() leaves it to ArchiveTable.
        timespan = TimeSpan(midnight, midnight + 2 * 86400 - 3600)
        fast, slow, _ = both_ways(manager, monkeypatch, 'outTemp', timespan, 'avg', 86400)
    finally:
        manager.close()
    assert_same(fast, slow, 'avg')
    # Twelve hours at 10 and twelve at 20, whatever the number of records.
    assert fast[2][0][0] == pytest.approx(15.0)


@pytest.mark.parametrize('aggregate_type', ['mintime', 'maxtime'])
def test_equal_extremes(made_db, monkeypatch, aggregate_type):
    """Of equal extremes in a bucket, the earliest wins, as in the database."""
    start = ts(2010, 6, 1, 0)
    values = [5.0, 1.0, 9.0, 1.0, 9.0, 5.0] * 8
    records = [{'dateTime': start + 300 * (n + 1), 'usUnits': weewx.US, 'interval': 5,
                'outTemp': value} for n, value in enumerate(values)]
    manager = made_db(records)
    try:
        fast, slow, calculated = both_ways(manager, monkeypatch, 'outTemp',
                                           TimeSpan(start + 600, start + 300 * len(values)),
                                           aggregate_type, 1800)
    finally:
        manager.close()
    assert calculated
    assert_same(fast, slow, aggregate_type)
