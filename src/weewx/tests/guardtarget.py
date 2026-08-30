#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""A stand-in station for test_loopguard.py, that misbehaves on request.

In a module of its own because the engine loads a driver by importing the module
the configuration names. Naming the test module there would import it a second
time, which is the trouble stopper.py was split out to avoid.
"""

import threading
import time

import weewx
import weewx.drivers
from weeutil.weeutil import to_int


def loader(config_dict, engine):
    return FakeStation(**config_dict['FakeStation'])


class FakeStation(weewx.drivers.AbstractDevice):
    """A station whose LOOP behaves however a test needs it to.

    Args:
        behaviour (str): What genLoopPackets() does once it has yielded its
            packets. One of:
            'quiet'  - block until closePort() releases it, like a station gone
                       silent whose driver still answers.
            'stuck'  - block on something closePort() does not release, like a
                       driver inside a read that never returns. A test that asks
                       for this must call release_hard() to get the thread back.
            'raise'  - raise weewx.WeeWxIOError, like a driver that notices.
            'return' - return, ending the generator.
        packets (int|str): How many packets to yield first. Comes from the
            configuration, so it may arrive as a string.
        hang_in (str): Name of a driver method or property to block in instead of
            returning. 'getTime' is a method the engine reaches outside the packet
            loop, 'archive_interval' a property it reads at startup.

    Attributes:
        closed (bool): Whether closePort() has been called.
        loops (int): How many times genLoopPackets() has been entered. The engine
            calls it once per archive period.
        closed_loops (int): How many of those generators have been closed again.
        produced (int): How many packets have been handed out in total. Shows how
            far the station has run ahead of whoever is reading.
    """

    def __init__(self, behaviour='quiet', packets=0, hang_in='', **_ignored):
        self.behaviour = behaviour
        self.packets = to_int(packets)
        self.hang_in = hang_in
        self.closed = False
        self.loops = 0
        self.closed_loops = 0
        self.produced = 0
        self._released = threading.Event()
        self._released_hard = threading.Event()

    @property
    def hardware_name(self):
        return 'FakeStation'

    @property
    def archive_interval(self):
        if self.hang_in == 'archive_interval':
            self._wait()
        raise NotImplementedError()

    def genLoopPackets(self):
        self.loops += 1
        try:
            for i in range(self.packets):
                self.produced += 1
                yield {'dateTime': int(time.time()), 'usUnits': weewx.US,
                       'outTemp': float(i)}

            if self.behaviour == 'return':
                return
            if self.behaviour == 'raise':
                raise weewx.WeeWxIOError("the station went away")
            self._wait()
        finally:
            self.closed_loops += 1

    def getTime(self):
        if self.hang_in == 'getTime':
            self._wait()
        raise NotImplementedError()

    def release_hard(self):
        """Free a 'stuck' driver, which closePort() deliberately cannot."""
        self._released_hard.set()

    def closePort(self):
        self.closed = True
        self._released.set()

    def _wait(self):
        """Block the way a driver blocks in a read that has nothing to read."""
        if self.behaviour == 'stuck':
            self._released_hard.wait()
        else:
            self._released.wait()
        # Raise rather than return once released, so that a test tearing down an
        # engine gets it out of its main loop instead of round it again.
        raise weewx.WeeWxIOError("released")
