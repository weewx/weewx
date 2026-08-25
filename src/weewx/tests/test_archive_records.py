#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test that StdArchive emits a record for every archive period that has data.

The packets go through the same sequence of events the engine dispatches, and what is
asserted is which records come out the other end.
"""

import time

import configobj
import pytest

import weewx
import weewx.accum
import weewx.engine
from weeutil.weeutil import startOfInterval

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


class Manager:
    """Collects what would go into the database."""

    database_name = 'test.sdb'

    def __init__(self):
        self.records = []

    def lastGoodStamp(self):
        return self.records[-1]['dateTime'] if self.records else None

    def _read_metadata(self, key):
        return None

    def backfill_day_summary(self):
        return 0, 0

    def addRecord(self, record, accumulator=None, log_success=True, log_failure=True):
        self.records.append(record)


class Engine:
    """Just enough engine to dispatch events to one service."""

    def __init__(self):
        self.callbacks = {}
        self.console = Console()
        self.manager = Manager()
        self.db_binder = self

    def get_manager(self, binding, initialize=False):
        return self.manager

    def bind(self, event_type, callback):
        self.callbacks.setdefault(event_type, []).append(callback)

    def dispatchEvent(self, event):
        for callback in self.callbacks.get(event.event_type, []):
            callback(event)

    def _get_console_time(self):
        return START


def config():
    return configobj.ConfigObj({
        'StdArchive': {
            'record_generation': 'software',
            'archive_interval': str(INTERVAL),
            'archive_delay': str(DELAY),
        },
        'Accumulator': {},
    })


def packet(timestamp, **values):
    # 'rain' is a sum, so one tip per packet means the rain in a record counts the
    # packets that reached it.
    p = {'dateTime': int(timestamp), 'usUnits': weewx.US, 'outTemp': 20.0, 'rain': 1.0}
    p.update(values)
    return p


def run(*packets):
    """Feed packets the way StdEngine.run() does. Returns the records written."""
    engine = Engine()
    weewx.engine.StdArchive(engine, config())
    engine.dispatchEvent(weewx.Event(weewx.STARTUP))
    engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    for p in packets:
        try:
            engine.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET, packet=p))
            engine.dispatchEvent(weewx.Event(weewx.CHECK_LOOP, packet=p))
        except weewx.engine.BreakLoop:
            engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))
            engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    return engine.manager.records


def test_a_period_is_not_lost_when_the_loop_runs_past_two_boundaries():
    """The bug.

    The loop is broken 'archive_delay' seconds after a period ends. A packet that
    arrives before that does not break it, so a second period can end while the first
    one's accumulator is still waiting. It used to be replaced, and its record was
    never written.
    """
    records = run(
        packet(START + 30),                      # period 1
        packet(START + INTERVAL + 9),            # period 2 begins, no break yet
        packet(START + INTERVAL + 12),
        packet(START + 2 * INTERVAL + 8),        # period 3 begins, break at last
        packet(START + 2 * INTERVAL + 200),
    )

    assert [r['dateTime'] for r in records] == [START + INTERVAL, START + 2 * INTERVAL]


def test_no_reading_is_dropped_along_the_way():
    """Every packet reaches the record its timestamp belongs to.

    One packet per period, arriving just after the boundary and so before the delay
    that breaks the loop. That is a driver polling an API on the archive interval, and
    it is the shape in which whole periods used to go missing.
    """
    packets = [packet(START + n * INTERVAL + 9) for n in range(12)]
    packets.append(packet(START + 12 * INTERVAL + 200))

    records = run(*packets)
    written = sum(r.get('rain') or 0 for r in records)

    # Twelve periods with a packet each. The thirteenth packet closes the last of
    # them and then waits in a period of its own, which the stream never reaches.
    assert len(records) == 12
    assert written == 12


def test_the_records_come_out_in_order():
    records = run(
        packet(START + 30),
        packet(START + INTERVAL + 9),
        packet(START + 2 * INTERVAL + 8),
        packet(START + 3 * INTERVAL + 7),
        packet(START + 3 * INTERVAL + 200),
    )
    times = [r['dateTime'] for r in records]

    assert times == sorted(times)
    assert len(times) == 3


def test_the_usual_case_is_one_record_per_period():
    """A station reporting every few seconds, which is most of them."""
    packets = [packet(START + n * 10) for n in range(1, 120)]

    records = run(*packets)

    assert [r['dateTime'] for r in records] == [START + INTERVAL, START + 2 * INTERVAL,
                                                START + 3 * INTERVAL]


def test_a_period_with_no_packets_at_all_yields_no_record():
    """Issue #219: an empty period must not raise, and must not invent a record."""
    records = run(
        packet(START + 30),
        packet(START + 3 * INTERVAL + 30),        # two silent periods in between
        packet(START + 3 * INTERVAL + 200),
    )

    assert [r['dateTime'] for r in records] == [START + INTERVAL]


def test_a_single_packet_writes_nothing_yet():
    assert run(packet(START + 30)) == []


def test_an_unknown_generation_still_raises():
    engine = Engine()
    archive = weewx.engine.StdArchive(engine, config())
    engine.dispatchEvent(weewx.Event(weewx.STARTUP))
    engine.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    archive.record_generation = 'nonsense'
    engine.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet(START + 30)))
    engine.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET,
                                     packet=packet(START + INTERVAL + 30)))

    with pytest.raises(ValueError):
        engine.dispatchEvent(weewx.Event(weewx.POST_LOOP))
    assert archive.old_accumulator is None
