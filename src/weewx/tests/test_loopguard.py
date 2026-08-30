#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.loopguard"""

import logging
import threading
import time

import configobj
import pytest

import guardtarget
import weewx
import weewx.engine
import weewx.loopguard

# Short enough to keep the suite quick, long enough that a loaded machine cannot
# trip it by accident.
TIMEOUT = 0.3

log = logging.getLogger(__name__)


def make_config(behaviour='quiet', packets=0, guarded=True, hang_in=''):
    """Build a configuration whose station is a FakeStation.

    Args:
        behaviour (str): What the station does once out of packets. See
            guardtarget.FakeStation.
        packets (int): How many packets it yields first.
        guarded (bool): Whether to set 'loop_timeout', which is what puts the
            guard in place. False leaves the driver bare, to measure against.
        hang_in (str): A driver method for the station to block in.

    Returns:
        configobj.ConfigObj: A configuration an engine can be built from.
    """
    station = {
        'station_type': 'FakeStation',
        # StationInfo insists on these, whatever the driver is.
        'location': 'Test City',
        'latitude': '45.686',
        'longitude': '-121.566',
        'altitude': ['100', 'meter'],
    }
    if guarded:
        station['loop_timeout'] = str(TIMEOUT)
    return configobj.ConfigObj({
        'Station': station,
        'FakeStation': {
            'driver': 'guardtarget',
            'behaviour': behaviour,
            'packets': str(packets),
            'hang_in': hang_in,
        },
        'Engine': {'Services': {}},
    })


def wait_until(predicate, timeout=2.0):
    """Poll until a predicate holds, so a test never waits on a fixed sleep.

    Args:
        predicate (Callable[[], bool]): Called as ``predicate()``. Returns
            whether the thing being waited for has happened.
        timeout (float): Seconds to keep trying.

    Returns:
        bool: Whether the predicate held before the time ran out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def make_guard():
    """Hand out guarded FakeStations, and take their threads down afterwards."""
    guards = []

    def _make(behaviour='quiet', packets=0, hang_in=''):
        station = guardtarget.FakeStation(behaviour=behaviour, packets=packets,
                                          hang_in=hang_in)
        guard = weewx.loopguard.LoopGuard(station, TIMEOUT)
        guards.append(guard)
        return guard

    yield _make

    for guard in guards:
        # Straight at the station, not through the guard: a 'stuck' station has
        # its worker blocked, so a relayed call would only wait out the deadline.
        guard._driver.release_hard()
        guard.closePort()


def test_packets_reach_the_engine(make_guard):
    guard = make_guard(packets=3)
    packets = []
    for packet in guard.genLoopPackets():
        packets.append(packet)
        if len(packets) == 3:
            break
    assert [p['outTemp'] for p in packets] == [0.0, 1.0, 2.0]


def test_silence_raises_after_the_deadline(make_guard):
    guard = make_guard(behaviour='quiet')
    start = time.time()
    with pytest.raises(weewx.WeeWxIOError, match='No answer'):
        next(guard.genLoopPackets())
    # It waits the deadline out rather than giving up on the first quiet moment.
    assert time.time() - start >= TIMEOUT


def test_the_deadline_runs_from_the_last_packet(make_guard):
    """Packets must not be counted against the deadline that follows them."""
    guard = make_guard(behaviour='quiet', packets=2)
    gen = guard.genLoopPackets()
    start = time.time()
    next(gen)
    next(gen)
    delivered = time.time()
    with pytest.raises(weewx.WeeWxIOError):
        next(gen)

    assert delivered - start < TIMEOUT
    assert time.time() - delivered >= TIMEOUT


def test_a_call_outside_the_loop_has_a_deadline_too(make_guard):
    """The engine asks the driver for more than packets, and waits for all of it.

    StdTimeSynch asks for the clock at STARTUP and every few hours after that
    (engine.py:810), and StdArchive asks before every archive period through
    _get_console_time (engine.py:287).
    """
    guard = make_guard(hang_in='getTime')
    start = time.time()
    with pytest.raises(weewx.WeeWxIOError, match='No answer'):
        guard.getTime()
    assert time.time() - start >= TIMEOUT


def test_a_property_that_hangs_has_a_deadline(make_guard):
    """StdArchive reads archive_interval at startup, and it runs driver code."""
    guard = make_guard(hang_in='archive_interval')
    with pytest.raises(weewx.WeeWxIOError, match='No answer'):
        _ = guard.archive_interval


def test_abandoning_the_loop_closes_the_driver_generator(make_guard):
    """Otherwise every archive period leaves another open generator behind."""
    guard = make_guard(packets=100)
    gen = guard.genLoopPackets()
    next(gen)
    assert guard.closed_loops == 0

    gen.close()
    assert wait_until(lambda: guard.closed_loops == 1)


def test_driver_error_reaches_the_engine(make_guard):
    """The engine must see the driver's own error, not a deadline."""
    guard = make_guard(behaviour='raise')
    with pytest.raises(weewx.WeeWxIOError, match='the station went away'):
        next(guard.genLoopPackets())


def test_a_generator_that_returns_ends_the_loop(make_guard):
    guard = make_guard(behaviour='return')
    assert list(guard.genLoopPackets()) == []


def test_everything_else_reaches_the_driver(make_guard):
    guard = make_guard()
    assert guard.hardware_name == 'FakeStation'
    # An unimplemented part of the driver interface must still read as
    # unimplemented, because StdArchive and StdTimeSynch test for exactly that.
    with pytest.raises(NotImplementedError):
        _ = guard.archive_interval
    with pytest.raises(NotImplementedError):
        guard.getTime()
    # A plain data attribute comes straight back.
    assert guard.behaviour == 'quiet'


def test_an_assignment_reaches_the_driver(make_guard):
    """Nothing in weewx assigns to a driver, but an extension may."""
    guard = make_guard()
    guard.behaviour = 'raise'
    assert guard._driver.behaviour == 'raise'


def test_an_assignment_has_a_deadline_too(make_guard):
    """It can land on a property setter, which runs driver code."""
    guard = make_guard(behaviour='stuck')
    with pytest.raises(weewx.WeeWxIOError):
        next(guard.genLoopPackets())
    # The worker is wedged now, so the assignment cannot get through either.
    with pytest.raises(weewx.WeeWxIOError, match='No answer'):
        guard.packets = 5


def test_the_guard_keeps_only_its_own_attributes(make_guard):
    """Add an attribute without listing it, and it would go to the driver."""
    guard = make_guard()
    assert set(guard.__dict__) == weewx.loopguard.LoopGuard._OWN


def test_close_port_closes_the_driver(make_guard):
    guard = make_guard()
    guard.closePort()
    assert guard.closed


def test_a_thread_that_will_not_stop_is_logged(make_guard, monkeypatch, caplog):
    """The guard's own limit: a driver stuck in a read keeps its thread."""
    monkeypatch.setattr(weewx.loopguard, 'JOIN_TIMEOUT', 0.1)
    guard = make_guard(behaviour='stuck')
    with pytest.raises(weewx.WeeWxIOError):
        next(guard.genLoopPackets())

    with caplog.at_level(logging.ERROR, logger='weewx.loopguard'):
        guard.closePort()

    assert 'still holds the device open' in caplog.text
    assert guard._thread.is_alive()


def test_each_archive_period_gets_a_fresh_generator(make_guard):
    """The driver sees its LOOP restart, exactly as it would without the guard."""
    guard = make_guard(packets=100)
    gen = guard.genLoopPackets()
    next(gen)
    # What StdArchive's BreakLoop does to the generator at the end of a period.
    gen.close()

    gen = guard.genLoopPackets()
    next(gen)
    assert wait_until(lambda: guard.loops == 2)


def test_the_driver_never_runs_ahead(make_guard):
    """It produces a packet because one was asked for, and then stops.

    A packet made before the engine asks would belong to no archive period by the
    time it arrives, and StdArchive files a packet by its own timestamp.
    """
    guard = make_guard(packets=100)
    gen = guard.genLoopPackets()
    next(gen)
    next(gen)
    assert guard.produced == 2

    gen.close()
    # Nothing is pulling now, so nothing more may appear.
    time.sleep(TIMEOUT)
    assert guard.produced == 2


def test_the_engine_guards_only_when_asked():
    """Without 'loop_timeout' nothing is wrapped, and with it nothing else changes."""
    bare = weewx.engine.StdEngine(make_config(guarded=False))
    assert isinstance(bare.console, guardtarget.FakeStation)

    guarded = weewx.engine.StdEngine(make_config())
    assert isinstance(guarded.console, weewx.loopguard.LoopGuard)
    # The station the rest of weewx sees is still the real one.
    assert guarded.stn_info.hardware == 'FakeStation'
    guarded.console.closePort()


def test_the_engine_breaks_out_of_its_main_loop():
    """The whole point: a silent station must reach weewxd as a WeeWxIOError.

    weewxd catches that one, waits 'retry_wait' seconds and builds a new engine.
    """
    engine = weewx.engine.StdEngine(make_config(behaviour='quiet'))
    with pytest.raises(weewx.WeeWxIOError):
        engine.run()


def test_the_engine_breaks_out_when_the_driver_hangs_outside_the_loop():
    """A driver can wedge anywhere it is called, not only in genLoopPackets()."""
    config = make_config(hang_in='getTime')
    config['Engine']['Services'] = {'prep_services': 'weewx.engine.StdTimeSynch'}
    engine = weewx.engine.StdEngine(config)
    with pytest.raises(weewx.WeeWxIOError):
        engine.run()


def test_the_engine_stalls_without_the_guard():
    """The premise, measured: the same station stops the engine dead."""
    engine = weewx.engine.StdEngine(make_config(behaviour='quiet', guarded=False))
    runner = threading.Thread(target=_run_and_swallow, args=(engine,), daemon=True)
    runner.start()
    runner.join(TIMEOUT * 4)

    assert runner.is_alive(), "engine should still be stuck in genLoopPackets()"

    # Let it go, so the thread does not outlive the test.
    engine.console.closePort()
    runner.join(2.0)
    assert not runner.is_alive()


def _run_and_swallow(engine):
    """Run an engine to its end, for a test that only cares whether it got there."""
    try:
        engine.run()
    except Exception as e:
        log.debug("Engine finished with %s", e)
