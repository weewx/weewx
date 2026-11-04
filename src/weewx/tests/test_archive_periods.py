#
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test how StdArchive collects LOOP packets into archive periods."""

import configobj

import weewx
import weewx.accum
import weewx.engine


class FakeEngine:
    """Just enough of an engine to drive StdArchive, keeping the archive records it emits."""

    class Console:
        archive_interval = 300

    def __init__(self):
        self.console = FakeEngine.Console()
        self.callbacks = {}
        self.records = []

    def bind(self, event_type, callback):
        self.callbacks.setdefault(event_type, []).append(callback)

    def dispatchEvent(self, event):
        if event.event_type == weewx.NEW_ARCHIVE_RECORD:
            self.records.append(event.record)
        else:
            for callback in self.callbacks.get(event.event_type, []):
                callback(event)


def make_archive():
    """Return an engine and a StdArchive in software generation, primed for the period
    (900, 1200]."""
    config_dict = configobj.ConfigObj({'StdArchive': {'record_generation': 'software',
                                                      'archive_interval': 300,
                                                      'archive_delay': 15}})
    engine = FakeEngine()
    archive = weewx.engine.StdArchive(engine, config_dict)
    archive.end_archive_period_ts = 1200
    archive.end_archive_delay_ts = 1215
    return engine, archive


def archived(engine):
    """Return a two-way tuple (dateTime, rain) for every archive record the engine received."""
    return [(record['dateTime'], record['rain']) for record in engine.records]


def send_packet(archive, timestamp):
    """Send a LOOP packet with one unit of rain through the loop events of StdArchive."""
    packet = {'dateTime': timestamp, 'usUnits': weewx.US, 'rain': 1.0}
    archive.new_loop_packet(weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet))
    try:
        archive.check_loop(weewx.Event(weewx.CHECK_LOOP, packet=packet))
    except weewx.engine.BreakLoop:
        archive.post_loop(weewx.Event(weewx.POST_LOOP))


def test_late_packet_counts_in_its_own_period():
    engine, archive = make_archive()
    for timestamp in range(910, 1200, 30):
        send_packet(archive, timestamp)
    send_packet(archive, 1203)
    # Arrives after the first packet of the next period, but within the archive delay.
    send_packet(archive, 1198)
    send_packet(archive, 1216)

    assert archived(engine) == [(1200, 11.0)]


def test_one_packet_per_period_loses_no_record():
    """A driver that polls once per archive interval sends one packet just after each boundary.
    The loop then breaks only every other period, so two periods end at some breaks."""
    engine, archive = make_archive()
    for timestamp in range(1203, 4804, 300):
        send_packet(archive, timestamp)

    assert archived(engine) == [(stop_ts, 1.0) for stop_ts in range(1500, 4501, 300)]


def test_early_break_does_not_archive_running_period():
    engine, archive = make_archive()
    for timestamp in range(910, 1100, 30):
        send_packet(archive, timestamp)
    # Another service breaks the loop in the middle of the period.
    archive.post_loop(weewx.Event(weewx.POST_LOOP))
    for timestamp in range(1120, 1200, 30):
        send_packet(archive, timestamp)
    send_packet(archive, 1216)

    assert archived(engine) == [(1200, 10.0)]


def test_corrected_clock_does_not_archive_running_period():
    """One packet from the future must not make StdArchive think that the running period has
    ended, after the station clock has been corrected."""
    engine, archive = make_archive()
    send_packet(archive, 910)
    send_packet(archive, 3601)
    send_packet(archive, 1216)
    # Another service breaks the loop.
    archive.post_loop(weewx.Event(weewx.POST_LOOP))
    for timestamp in (1240, 1270, 1300, 1490, 1516):
        send_packet(archive, timestamp)

    assert archived(engine) == [(1200, 1.0), (1500, 5.0)]


def test_clock_set_back_keeps_archiving():
    """If the station clock is set back, the packets fall behind the time the loop is due to
    break. The periods must still be archived, rather than pile up in memory."""
    engine, archive = make_archive()
    for timestamp in range(-2700, 901, 300):
        send_packet(archive, timestamp)

    assert archived(engine) == [(stop_ts, 1.0) for stop_ts in range(-2700, 601, 300)]
    assert len(archive.periods.open) == 1


def test_packet_for_archived_period_is_refused():
    periods = weewx.engine.ArchivePeriods(300)
    periods.add_packet({'dateTime': 1100, 'usUnits': weewx.US, 'rain': 1.0})
    periods.add_packet({'dateTime': 1210, 'usUnits': weewx.US, 'rain': 1.0})

    ended = periods.pop_ended(1215)

    assert [accumulator.timespan.stop for accumulator in ended] == [1200]
    # A timestamp on the boundary belongs to the period that stops there, which is archived.
    assert not periods.add_packet({'dateTime': 1200, 'usUnits': weewx.US, 'rain': 1.0})
    assert periods.add_packet({'dateTime': 1201, 'usUnits': weewx.US, 'rain': 1.0})


def test_initialize_replaces_earlier_configuration():
    try:
        weewx.accum.initialize({'Accumulator': {'myType': {'extractor': 'sum'}}})
        weewx.accum.initialize({'Accumulator': {}})

        assert weewx.accum.get_extract_function('myType') is weewx.accum.Accum.extract_avg
    finally:
        weewx.accum.initialize({})


def test_configuration_overrides_prepended_options():
    """A driver or extension may prepend its own options. The [Accumulator] section of the
    configuration still wins, as it always has."""
    prepended = {'myType': {'extractor': 'max'}}
    weewx.accum.accum_dict.prepend(prepended)
    try:
        weewx.accum.initialize({'Accumulator': {'myType': {'extractor': 'sum'}}})

        assert weewx.accum.get_extract_function('myType') is weewx.accum.Accum.extract_sum
    finally:
        weewx.accum.accum_dict.maps.remove(prepended)
        weewx.accum.initialize({})
