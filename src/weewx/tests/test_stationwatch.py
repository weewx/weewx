#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.stationwatch"""

import time

import configobj
import pytest

import weewx
import weewx.manager
import weewx.stationwatch

MAX_AGE = 600


class FakeEngine:
    """Just enough engine to bind to and to catch what gets dispatched.

    Attributes:
        events (list[weewx.Event]): Everything dispatched, in order.
        callbacks (dict[type, list[Callable]]): What has bound to what.
    """

    def __init__(self):
        self.events = []
        self.callbacks = {}

    def bind(self, event_type, callback):
        self.callbacks.setdefault(event_type, []).append(callback)

    def dispatchEvent(self, event):
        self.events.append(event)


def make_config(tmp_path, max_age=MAX_AGE):
    """Build a configuration with an empty SQLite database.

    Args:
        tmp_path (pathlib.Path): Where the database goes.
        max_age (int): The deadline. Zero leaves the service switched off.

    Returns:
        configobj.ConfigObj: A configuration StdStationWatch can be built from.
    """
    watch = {'max_age': str(max_age)} if max_age else {}
    return configobj.ConfigObj({
        'WEEWX_ROOT': str(tmp_path),
        'Station': {'location': 'Test City'},
        'StdStationWatch': watch,
        'DataBindings': {
            'wx_binding': {
                'database': 'archive_sqlite',
                'table_name': 'archive',
                'manager': 'weewx.manager.DaySummaryManager',
                'schema': 'schemas.wview_extended.schema',
            },
        },
        'Databases': {
            'archive_sqlite': {'database_name': 'test.sdb', 'database_type': 'SQLite'},
        },
        'DatabaseTypes': {
            'SQLite': {'driver': 'weedb.sqlite', 'SQLITE_ROOT': str(tmp_path)},
        },
    })


def add_record(config_dict, timestamp):
    """Put one archive record into the database, creating it if need be.

    Args:
        config_dict (configobj.ConfigObj): The configuration naming the database.
        timestamp (int): The record's dateTime.
    """
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding',
                                                initialize=True) as dbmanager:
        dbmanager.addRecord({'dateTime': timestamp, 'usUnits': weewx.US,
                             'interval': 5, 'outTemp': 20.0})


@pytest.fixture
def make_watch():
    """Build watchers, and stop any thread they started."""
    built = []

    def _make(config_dict):
        engine = FakeEngine()
        watch = weewx.stationwatch.StdStationWatch(engine, config_dict)
        built.append(watch)
        return engine, watch

    yield _make

    for watch in built:
        watch.shutDown()


def test_it_stays_out_of_the_way_unless_asked(tmp_path, make_watch):
    """Without max_age it binds to nothing and starts nothing."""
    engine, watch = make_watch(make_config(tmp_path, max_age=0))

    assert engine.callbacks == {}
    assert watch.thread is None


def test_it_binds_to_startup_when_asked(tmp_path, make_watch):
    engine, _ = make_watch(make_config(tmp_path))

    assert list(engine.callbacks) == [weewx.STARTUP]


def test_a_fresh_record_dispatches_nothing(tmp_path, make_watch):
    config = make_config(tmp_path)
    add_record(config, int(time.time()))
    engine, watch = make_watch(config)

    watch.check()
    assert engine.events == []


def test_an_old_record_dispatches_station_down(tmp_path, make_watch):
    config = make_config(tmp_path)
    last_ts = int(time.time()) - MAX_AGE - 60
    add_record(config, last_ts)
    engine, watch = make_watch(config)

    watch.check()

    assert len(engine.events) == 1
    event = engine.events[0]
    assert event.event_type == weewx.STATION_DOWN
    assert event.last_record == last_ts
    assert event.age >= MAX_AGE + 60


def test_it_dispatches_station_down_once(tmp_path, make_watch):
    """However long the station stays away, it is one event."""
    config = make_config(tmp_path)
    add_record(config, int(time.time()) - MAX_AGE - 60)
    engine, watch = make_watch(config)

    watch.check()
    watch.check()
    watch.check()
    assert len(engine.events) == 1


def test_recovery_dispatches_station_up_with_the_gap(tmp_path, make_watch):
    config = make_config(tmp_path)
    old_ts = int(time.time()) - MAX_AGE - 1200
    add_record(config, old_ts)
    engine, watch = make_watch(config)

    watch.check()
    new_ts = int(time.time())
    add_record(config, new_ts)
    watch.check()

    assert [e.event_type for e in engine.events] == [weewx.STATION_DOWN,
                                                     weewx.STATION_UP]
    assert engine.events[1].gap == new_ts - old_ts


def test_an_empty_database_dispatches_nothing(tmp_path, make_watch):
    """There is nothing to have stopped until there has been data."""
    config = make_config(tmp_path)
    engine, watch = make_watch(config)

    watch.check()
    assert engine.events == []


def test_a_missing_database_dispatches_nothing(tmp_path, make_watch):
    """The engine may not have created it yet when the first check comes round."""
    config = make_config(tmp_path)
    _, watch = make_watch(config)

    assert watch.last_record_time() is None


def test_the_thread_starts_at_startup_and_stops_on_shutdown(tmp_path, make_watch):
    config = make_config(tmp_path)
    add_record(config, int(time.time()))
    engine, watch = make_watch(config)

    for callback in engine.callbacks[weewx.STARTUP]:
        callback(weewx.Event(weewx.STARTUP))
    assert watch.thread.is_alive()

    watch.shutDown()
    assert not watch.thread.is_alive()
