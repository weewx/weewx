#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test that archive record generation and database storage work apart, and together.

The two halves talk over the NEW_ARCHIVE_RECORD event and nothing else. What is asserted
here is that either one can be run without the other, that replacing one of them serves
the other, and that a configuration naming the old combined service behaves as it did.
"""

import time

import configobj
import pytest

import weewx
import weewx.accum
import weewx.engine
from weeutil.weeutil import startOfInterval, to_int

INTERVAL = 300
DELAY = 15
START = int(startOfInterval(time.mktime((2026, 3, 10, 12, 0, 0, 0, 0, -1)), INTERVAL))


class Console:
    """A console with no archive of its own, i.e. software record generation."""

    archive_interval = INTERVAL

    def genArchiveRecords(self, since_ts):
        raise NotImplementedError("No hardware archive")

    def genStartupRecords(self, since_ts):
        raise NotImplementedError("No hardware archive")


class HardwareConsole(Console):
    """A console that keeps its own archive and hands records over on request."""

    def __init__(self, records=()):
        self.records = list(records)
        self.asked_from = []

    def genArchiveRecords(self, since_ts):
        self.asked_from.append(since_ts)
        for record in self.records:
            yield dict(record)

    genStartupRecords = genArchiveRecords


class Manager:
    """Collects what would go into the database, and what came with it."""

    database_name = 'test.sdb'

    def __init__(self):
        self.records = []
        self.accumulators = []
        self.backfilled = 0
        self.initialized = False

    def lastGoodStamp(self):
        return self.records[-1]['dateTime'] if self.records else None

    def _read_metadata(self, key):
        return None

    def backfill_day_summary(self):
        self.backfilled += 1
        return 0, 0

    def addRecord(self, record, accumulator=None, log_success=True, log_failure=True):
        self.records.append(record)
        self.accumulators.append(accumulator)


class Engine:
    """Just enough engine to dispatch events to a handful of services."""

    def __init__(self, console=None):
        self.callbacks = {}
        self.console = console or Console()
        self.manager = Manager()
        self.db_binder = self

    def get_manager(self, binding, initialize=False):
        if initialize:
            self.manager.initialized = True
        return self.manager

    def bind(self, event_type, callback):
        self.callbacks.setdefault(event_type, []).append(callback)

    def dispatchEvent(self, event):
        for callback in self.callbacks.get(event.event_type, []):
            callback(event)

    def _get_console_time(self):
        return START


def config(**overrides):
    archive = {
        'record_generation': 'software',
        'archive_interval': str(INTERVAL),
        'archive_delay': str(DELAY),
    }
    archive.update(overrides)
    return configobj.ConfigObj({'StdArchive': archive, 'Accumulator': {}})


def packet(timestamp, **values):
    # 'rain' is a sum, so one tip per packet means the rain in a record counts the
    # packets that reached it.
    p = {'dateTime': int(timestamp), 'usUnits': weewx.US, 'outTemp': 20.0, 'rain': 1.0}
    p.update(values)
    return p


def feed(engine, packets):
    """Push packets through the way StdEngine.run() does."""
    engine.dispatchEvent(weewx.Event(weewx.STARTUP))
    engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    for p in packets:
        try:
            engine.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET, packet=p))
            engine.dispatchEvent(weewx.Event(weewx.CHECK_LOOP, packet=p))
        except weewx.engine.BreakLoop:
            engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))
            engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    return engine.manager


# Four packets that close two archive periods: the first two periods end and are
# written, the third is still being filled when the stream runs out.
A_DAY = [packet(START + 30), packet(START + INTERVAL + 9),
         packet(START + INTERVAL + 30), packet(START + 2 * INTERVAL + 20)]
TWO_PERIODS = [START + INTERVAL, START + 2 * INTERVAL]


class TestTheHalvesTogether:
    """Both services present, which is what a stock installation runs."""

    def test_records_reach_the_database(self):
        engine = Engine()
        weewx.engine.StdArchiveCreator(engine, config())
        weewx.engine.StdArchiveStore(engine, config())

        manager = feed(engine, A_DAY)

        assert [r['dateTime'] for r in manager.records] == TWO_PERIODS

    def test_the_combined_service_does_the_same(self):
        """A configuration written before the split names StdArchive."""
        engine = Engine()
        weewx.engine.StdArchive(engine, config())

        manager = feed(engine, A_DAY)

        assert [r['dateTime'] for r in manager.records] == TWO_PERIODS

    def test_the_database_is_prepared_once(self):
        engine = Engine()
        weewx.engine.StdArchiveCreator(engine, config())
        weewx.engine.StdArchiveStore(engine, config())

        feed(engine, A_DAY)

        assert engine.manager.initialized
        assert engine.manager.backfilled == 1


class TestEitherHalfAlone:

    def test_the_generator_writes_nothing(self):
        """It emits the event. Without a store, nothing reaches the database."""
        engine = Engine()
        weewx.engine.StdArchiveCreator(engine, config())
        seen = []
        engine.bind(weewx.NEW_ARCHIVE_RECORD, lambda e: seen.append(e.record))

        manager = feed(engine, A_DAY)

        assert [r['dateTime'] for r in seen] == TWO_PERIODS
        assert manager.records == []

    def test_the_store_saves_what_it_is_given(self):
        """No generator at all: anything that emits the event is served."""
        engine = Engine()
        weewx.engine.StdArchiveStore(engine, config())
        engine.dispatchEvent(weewx.Event(weewx.STARTUP))

        record = {'dateTime': START + INTERVAL, 'usUnits': weewx.US, 'outTemp': 4.0}
        engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                                         record=record, origin='software'))

        assert engine.manager.records == [record]
        # Nothing said an accumulator was involved, so none is passed on.
        assert engine.manager.accumulators == [None]

    def test_a_replacement_generator_serves_the_store(self):
        """The point of the split: swap the half that makes records, keep the half
        that saves them."""

        class EveryPacketIsARecord(weewx.engine.StdService):
            """A generator that does no accumulating at all."""

            def __init__(self, engine, config_dict):
                super().__init__(engine, config_dict)
                self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

            def new_loop_packet(self, event):
                self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                                                      record=dict(event.packet),
                                                      origin='software'))

        engine = Engine()
        EveryPacketIsARecord(engine, config())
        weewx.engine.StdArchiveStore(engine, config())

        manager = feed(engine, A_DAY)

        assert [r['dateTime'] for r in manager.records] == [p['dateTime'] for p in A_DAY]


class TestTheAccumulatorTravels:
    """The store needs the accumulator for the daily summary's high/lows, and can only
    have it if the generator sends it along."""

    def test_it_arrives_with_the_record(self):
        engine = Engine()
        weewx.engine.StdArchiveCreator(engine, config())
        weewx.engine.StdArchiveStore(engine, config())

        manager = feed(engine, A_DAY)

        assert len(manager.accumulators) == len(TWO_PERIODS)
        for record, accumulator in zip(manager.records, manager.accumulators):
            assert accumulator is not None
            assert accumulator.timespan.stop == record['dateTime']

    def test_a_hardware_record_for_another_period_travels_without_one(self):
        """A catchup after an outage brings records the accumulator knows nothing
        about. Passing it along anyway would credit them with the wrong high/lows."""
        old = {'dateTime': START - 10 * INTERVAL, 'usUnits': weewx.US,
               'outTemp': 1.0, 'interval': INTERVAL / 60}
        engine = Engine(console=HardwareConsole([old]))
        weewx.engine.StdArchiveCreator(engine, config(record_generation='hardware'))
        weewx.engine.StdArchiveStore(engine, config(record_generation='hardware'))

        manager = feed(engine, A_DAY)

        by_time = dict(zip((r['dateTime'] for r in manager.records), manager.accumulators))
        assert by_time[old['dateTime']] is None


class TestAugmentation:

    def test_a_hardware_record_is_augmented_before_it_is_sent(self):
        """Every listener sees the same record, not just the one that saves it."""
        ends_at = START + INTERVAL
        from_console = {'dateTime': ends_at, 'usUnits': weewx.US, 'interval': INTERVAL / 60}
        engine = Engine(console=HardwareConsole([from_console]))
        weewx.engine.StdArchiveCreator(engine, config(record_generation='hardware',
                                                        no_catchup='true'))
        seen = []
        engine.bind(weewx.NEW_ARCHIVE_RECORD, lambda e: seen.append(dict(e.record)))

        feed(engine, A_DAY)

        augmented = [r for r in seen if r['dateTime'] == ends_at]
        assert augmented, "no record for the period that ended"
        # The console sent no outTemp. The accumulator has one, from the LOOP packets.
        assert 'outTemp' in augmented[0]

    def test_it_can_be_turned_off(self):
        ends_at = START + INTERVAL
        from_console = {'dateTime': ends_at, 'usUnits': weewx.US, 'interval': INTERVAL / 60}
        engine = Engine(console=HardwareConsole([from_console]))
        weewx.engine.StdArchiveCreator(engine, config(record_generation='hardware',
                                                     record_augmentation='false',
                                                     no_catchup='true'))
        seen = []
        engine.bind(weewx.NEW_ARCHIVE_RECORD, lambda e: seen.append(dict(e.record)))

        feed(engine, A_DAY)

        augmented = [r for r in seen if r['dateTime'] == ends_at]
        assert augmented
        assert 'outTemp' not in augmented[0]


class TestConfiguration:

    def test_an_unknown_generation_is_refused_at_startup(self):
        engine = Engine()
        with pytest.raises(ValueError):
            weewx.engine.StdArchiveCreator(engine, config(record_generation='nonsense'))

    def test_a_delay_of_zero_is_refused(self):
        engine = Engine()
        with pytest.raises(weewx.ViolatedPrecondition):
            weewx.engine.StdArchiveCreator(engine, config(archive_delay='0'))

    def test_no_catchup_leaves_the_console_alone(self):
        console = HardwareConsole([{'dateTime': START - INTERVAL, 'usUnits': weewx.US}])
        engine = Engine(console=console)
        weewx.engine.StdArchiveCreator(engine, config(record_generation='hardware',
                                                     no_catchup='true'))
        engine.dispatchEvent(weewx.Event(weewx.STARTUP))

        assert console.asked_from == []

    def test_the_store_needs_no_generation_settings(self):
        """It is the half that a replacement creator keeps, so it must not depend on
        how records are made."""
        engine = Engine()
        store = weewx.engine.StdArchiveStore(engine, config(record_generation='nonsense'))

        assert not hasattr(store, 'record_generation')
        assert not hasattr(store, 'archive_interval')


class TestAnExtensionOfEitherHalf:
    """What a replacement does about options that [StdArchive] does not have.

    Nothing in the two services provides for this, and nothing needs to: a subclass
    calls up to the constructor it is replacing, which reads [StdArchive], and then
    reads its own stanza for whatever else it wants. The shared options stay shared.
    """

    def test_it_keeps_the_shared_options_and_adds_its_own(self):
        class Creator(weewx.engine.StdArchiveCreator):
            def __init__(self, engine, config_dict):
                super().__init__(engine, config_dict)
                mine = config_dict.get('MyCreator', {})
                self.smoothing = to_int(mine.get('smoothing', 0))

        cfg = config()
        cfg['MyCreator'] = {'smoothing': '3'}
        creator = Creator(Engine(), cfg)

        assert creator.smoothing == 3
        assert creator.archive_delay == DELAY          # from [StdArchive]
        assert creator.data_binding == 'wx_binding'

    def test_it_can_override_a_shared_option_for_itself(self):
        class Store(weewx.engine.StdArchiveStore):
            def __init__(self, engine, config_dict):
                super().__init__(engine, config_dict)
                mine = config_dict.get('MyStore', {})
                self.data_binding = mine.get('data_binding', self.data_binding)

        cfg = config()
        cfg['MyStore'] = {'data_binding': 'other_binding'}
        store = Store(Engine(), cfg)

        assert store.data_binding == 'other_binding'

    def test_a_replacement_that_shares_nothing_still_serves_the_other_half(self):
        """The event is the whole contract, so a replacement need not inherit at all."""
        class Creator(weewx.engine.StdService):
            def __init__(self, engine, config_dict):
                super().__init__(engine, config_dict)
                self.mine = config_dict['MyCreator']['whatever']

        cfg = config()
        cfg['MyCreator'] = {'whatever': 'yes'}
        engine = Engine()
        creator = Creator(engine, cfg)
        weewx.engine.StdArchiveStore(engine, cfg)

        assert creator.mine == 'yes'
        engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                                         record={'dateTime': START, 'usUnits': weewx.US},
                                         origin='software'))
        assert len(engine.manager.records) == 1
