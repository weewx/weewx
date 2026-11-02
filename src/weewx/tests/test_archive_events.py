#
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the accumulator that StdArchive attaches to NEW_ARCHIVE_RECORD events.

An extension that saves archive records to a second database needs the accumulator of the archive
interval. Without it, the daily summaries of the second database can only use the archive record,
which holds averages, so they lose the highs and lows seen in the LOOP packets.

The tests run a real StdConvert and StdArchive in a DummyEngine, against two SQLite databases. The
primary database is managed by StdArchive. The secondary database is written by an event handler,
the way an extension would do it. Its schema lacks 'inTemp', so the extension cannot simply hand
over the archive record unchanged.

All tests feed the same archive interval, which runs from BASE_TIME + 300 to BASE_TIME + 600. Its
two LOOP packets carry 0 and 20 degrees C. The resulting archive record has an average of 10, so
a daily summary that shows a low of 0 and a high of 20 must have come from the accumulator.
"""

import socket

import configobj
import pytest

import weewx.accum
import weewx.engine

# An epoch time on a 300-second boundary, so the archive intervals start at BASE_TIME + k * 300.
BASE_TIME = 1700000100


@pytest.fixture
def archive_engine(tmp_path, monkeypatch):
    """Set up an engine with StdConvert and StdArchive, and two empty databases.

    Yields:
        tuple[weewx.engine.DummyEngine, weewx.engine.StdArchive, list]: A three-way tuple
            (engine, archive, events). The list 'events' collects a two-way tuple
            (dateTime, accumulator) for every NEW_ARCHIVE_RECORD event.
    """
    schema = {'dateTime': 'INTEGER NOT NULL PRIMARY KEY',
              'usUnits': 'INTEGER NOT NULL', 'interval': 'INTEGER NOT NULL',
              'outTemp': 'REAL'}
    primary_schema = dict(schema, inTemp='REAL')
    # No services are loaded from the configuration. The test adds the services it needs below,
    # so it controls the order in which they are bound to events.
    config = configobj.ConfigObj({
        'Station': {'altitude': [0, 'meter'], 'latitude': 0, 'longitude': 0},
        'Engine': {'Services': {group: [] for group in weewx.all_service_groups}},
        'StdConvert': {'target_unit': 'METRICWX'},
        'StdArchive': {'record_generation': 'software', 'archive_interval': 300,
                       'archive_delay': 15, 'no_catchup': True, 'log_success': False},
        'DataBindings': {
            'wx_binding': {'database': 'primary', 'schema': primary_schema},
            'alt_binding': {'database': 'secondary', 'schema': schema}},
        'Databases': {
            name: {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / (name + '.sdb'))}
            for name in ['primary', 'secondary']}})
    # The engine sets a process-wide socket timeout. Restore it when the test is done, so that
    # other test modules are not affected.
    previous_timeout = socket.getdefaulttimeout()
    engine = weewx.engine.DummyEngine(config)
    try:
        engine.service_obj.append(weewx.engine.StdConvert(engine, config))
        events = []
        # Callbacks run in the order they were bound. This one is bound after StdConvert and
        # before StdArchive. So it sees the record already in METRICWX, and it records which
        # accumulator StdArchive gets with the record.
        engine.bind(weewx.NEW_ARCHIVE_RECORD,
                    lambda event: events.append((event.record['dateTime'], event.accumulator)))
        archive = weewx.engine.StdArchive(engine, config)
        engine.service_obj.append(archive)
        # The dummy console has no clock. StdArchive.pre_loop() asks for the time to find the end
        # of the first archive interval. BASE_TIME + 310 makes that BASE_TIME + 600.
        monkeypatch.setattr(engine.console, 'getTime', lambda: BASE_TIME + 310, raising=False)
        engine.db_binder.get_manager('wx_binding', initialize=True)
        engine.db_binder.get_manager('alt_binding', initialize=True)
        yield engine, archive, events
    finally:
        engine.shutDown()
        socket.setdefaulttimeout(previous_timeout)


def feed_loop_interval(engine, unit_system=weewx.METRICWX):
    """Run one pass of the engine's LOOP cycle, for the interval ending at BASE_TIME + 600.

    The packets at offsets 310 and 590 fall into the interval and carry 0 and 20 degrees C. The
    packet at 620 belongs to the next interval. Because 620 is past the end of the archive delay
    (600 + 15), CHECK_LOOP raises BreakLoop, just as it would in the real engine. The caller then
    dispatches POST_LOOP, or inspects the accumulator of the interval first. Until POST_LOOP
    archives the interval, its accumulator is in archive.periods.open[BASE_TIME + 600].

    Args:
        engine (weewx.engine.DummyEngine): The engine from the fixture.
        unit_system (int): The unit system of the packets. StdConvert converts them to METRICWX
            before StdArchive adds them to the accumulator. Default is weewx.METRICWX.
    """
    engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    for offset, temperature in [(310, 0), (590, 20), (620, 100)]:
        packet = {'dateTime': BASE_TIME + offset, 'usUnits': unit_system,
                  'outTemp': temperature * 1.8 + 32 if unit_system == weewx.US else temperature,
                  'inTemp': 69.8 if unit_system == weewx.US else 21}
        engine.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet))
        if offset < 600:
            engine.dispatchEvent(weewx.Event(weewx.CHECK_LOOP, packet=packet))
        else:
            with pytest.raises(weewx.engine.BreakLoop):
                engine.dispatchEvent(weewx.Event(weewx.CHECK_LOOP, packet=packet))


def hardware_record(timestamp):
    """Return an archive record as a console would deliver it.

    The values are in US units. After StdConvert they are 10 and 21 degrees C, the same as the
    software record built from feed_loop_interval(). So the stored values do not depend on
    whether the record came from the hardware or from the accumulator.

    Args:
        timestamp (int): The value for 'dateTime'.

    Returns:
        dict: The archive record.
    """
    return {'dateTime': timestamp, 'usUnits': weewx.US, 'interval': 5,
            'outTemp': 50, 'inTemp': 69.8}


# 'generation' selects where the archive record comes from:
#   software: StdArchive builds it from the accumulator.
#   hardware: the console delivers it. Its timestamp matches the accumulator.
#   fallback: hardware generation is requested, but the console does not support it, so
#             StdArchive falls back to software generation.
# 'augmentation' must not matter. The accumulator goes to the database even if StdArchive does not
# use it to augment the record.
@pytest.mark.parametrize('generation', ['software', 'hardware', 'fallback'])
@pytest.mark.parametrize('unit_system', [weewx.METRICWX, weewx.US])
@pytest.mark.parametrize('augmentation', [True, False])
def test_secondary_database_keeps_loop_extremes(archive_engine, monkeypatch,
                                               generation, unit_system, augmentation):
    """Both databases get the LOOP highs and lows, whatever the source of the record."""
    engine, archive, events = archive_engine
    primary = engine.db_binder.get_manager('wx_binding')
    secondary = engine.db_binder.get_manager('alt_binding')
    archive.record_generation = 'software' if generation == 'software' else 'hardware'
    archive.record_augmentation = augmentation

    def generate_records(_since):
        if generation == 'fallback':
            raise NotImplementedError
        yield hardware_record(BASE_TIME + 600)

    monkeypatch.setattr(engine.console, 'genArchiveRecords', generate_records, raising=False)

    def save_secondary(event):
        # This is what an extension would do: drop the types its database does not hold, then
        # save the record together with the accumulator from the event.
        record = {key: event.record[key] for key in secondary.sqlkeys}
        secondary.addRecord(record, accumulator=event.accumulator, log_success=False)

    # Bound last, so it runs after StdArchive has saved the record to the primary database.
    engine.bind(weewx.NEW_ARCHIVE_RECORD, save_secondary)
    feed_loop_interval(engine, unit_system)
    accumulator = archive.periods.open[BASE_TIME + 600]
    original_stats = accumulator['outTemp'].getStatsTuple()
    engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))

    # The archived average is 10 C, so it cannot supply the LOOP extremes 0 and 20. Only the
    # accumulator has them, and both databases must show them. The sums come from the archive
    # record: one record, average 10, interval 300 seconds.
    for manager in [secondary, primary]:
        minimum, min_timestamp, maximum, max_timestamp, total, count, weighted_total, weight \
            = manager.getSql('SELECT min, mintime, max, maxtime, sum, count, wsum, sumtime '
                              'FROM archive_day_outTemp')
        assert (minimum, maximum, total, weighted_total) == pytest.approx((0, 20, 10, 3000))
        assert (min_timestamp, max_timestamp, count, weight) \
            == (BASE_TIME + 310, BASE_TIME + 590, 1, 300)
        assert manager.getRecord(BASE_TIME + 600)['outTemp'] == pytest.approx(10)
    assert primary.getRecord(BASE_TIME + 600)['inTemp'] == pytest.approx(21)
    assert 'inTemp' not in secondary.sqlkeys
    # StdArchive got the accumulator of the interval, exactly once.
    assert events == [(BASE_TIME + 600, accumulator)]
    # US packets were converted before they were accumulated.
    assert accumulator.unit_system == weewx.METRICWX
    # The accumulator was used by two databases. Neither may change it, or the second database
    # would get different statistics than the first.
    assert accumulator['outTemp'].getStatsTuple() == original_stats
    assert BASE_TIME + 600 not in archive.periods.open


def test_hardware_catchup_only_attaches_matching_accumulator(archive_engine, monkeypatch):
    """During a hardware catchup, only the record that ends the interval gets the accumulator.

    A console can deliver several records in one catchup, and not all of them belong to the
    interval of the accumulator. Here only BASE_TIME + 600 does. The records just before and
    after it must get None, or their daily summaries would get highs and lows from another
    interval.
    """
    engine, archive, events = archive_engine
    archive.record_generation = 'hardware'
    timestamps = [BASE_TIME + offset for offset in [300, 599, 600, 900]]
    monkeypatch.setattr(engine.console, 'genArchiveRecords',
                        lambda since: (hardware_record(timestamp) for timestamp in timestamps),
                        raising=False)
    feed_loop_interval(engine)
    accumulator = archive.periods.open[BASE_TIME + 600]
    engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))
    assert events == list(zip(timestamps, [None, None, accumulator, None]))


def test_startup_records_have_no_accumulator(archive_engine, monkeypatch):
    """Records from the startup catchup get None, because no LOOP data has been seen yet."""
    engine, archive, events = archive_engine
    archive.no_catchup = False
    monkeypatch.setattr(engine.console, 'genStartupRecords',
                        lambda since: iter([hardware_record(BASE_TIME + 300)]), raising=False)
    engine.dispatchEvent(weewx.Event(weewx.STARTUP))
    assert events == [(BASE_TIME + 300, None)]


def test_loop_hilo_disabled_keeps_statistics_unavailable(archive_engine):
    """With loop_hilo=False, the accumulator still arrives, but without highs and lows.

    An extension that uses the accumulator must handle a min and max of None, even though the
    interval had data. The average is still there.
    """
    engine, archive, events = archive_engine
    archive.loop_hilo = False
    feed_loop_interval(engine)
    engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))
    accumulator = events[0][1]
    assert accumulator['outTemp'].min is None
    assert accumulator['outTemp'].max is None
    assert accumulator['outTemp'].avg == pytest.approx(10)
