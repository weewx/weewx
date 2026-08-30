#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Put a deadline on a driver, so a station that stops answering cannot stall weewxd.

The engine calls its driver on its own thread, and waits as long as the driver
takes. A driver that blocks and never returns therefore stops the archive, the
reports and the uploads, while the process stays alive and the log stays quiet.
Nothing notices, because there is no event left to notice with.

LoopGuard stands between the two. Every call to the driver runs on a thread of
its own, and the engine waits for the answer only until 'timeout' seconds have
passed. After that it gets weewx.WeeWxIOError, which weewxd already knows what to
do with: it waits 'retry_wait' seconds and builds a fresh engine.

The engine puts the guard in place itself, when option 'loop_timeout' is set:

    [Station]
        station_type = Vantage
        loop_timeout = 300

The station type stays the real one, so nothing else changes: 'weectl device'
still finds its configurator, the station's own stanza is untouched, and any
driver that loads through the usual loader() is guarded, whether it ships with
weewx or comes from elsewhere.

The guard never asks the driver for anything on its own. It relays what the
engine asks for, one call at a time, and a generator the driver returns is pulled
one element at a time. So the driver runs exactly as far ahead of the engine as
it does without the guard, which is not at all.

What this cannot do: Python cannot interrupt a blocked thread. If the driver is
stuck in a read that never returns, that thread stays for the life of the process
and keeps the device open. The engine comes free, the thread does not. See
closePort().

What it asks of the driver: it no longer runs on the main thread, so it cannot
register signal handlers. A driver that calls signal.signal() raises ValueError
under 'loop_timeout' and has to run without it. That is no great loss, because a
driver reaching for signal.alarm() is putting a deadline on itself already.
"""

import collections
import functools
import logging
import queue
import threading

import weewx

log = logging.getLogger(__name__)

# Seconds to wait for the worker thread to finish during shutdown.
JOIN_TIMEOUT = 5.0

# 'work' is called on the worker thread. 'answer' receives a (bool, object) pair:
# whether the call returned, and its result or the exception it raised. It is None
# for work whose outcome nobody waits for.
_Job = collections.namedtuple('_Job', ['work', 'answer'])


class LoopGuard:
    """A driver that wraps another one and puts a deadline on every call to it.

    Deliberately not a subclass of weewx.drivers.AbstractDevice. That class
    defines every method of the driver interface, and a defined method is found
    before __getattr__ is consulted, which would leave the guard answering for
    the driver instead of relaying the call.

    Args:
        driver (weewx.drivers.AbstractDevice): The driver to guard, already
            loaded and open.
        timeout (float): Seconds to wait for any one call to the driver. Wants to
            be generous: the point is to catch a driver that has stopped, not one
            that is merely unhurried. A poller on a slow radio link can be quiet
            for minutes and be perfectly well, and the deadline covers the wait
            for a LOOP packet as much as anything else.
    """

    # Everything the guard keeps for itself. Every other name, read or written,
    # belongs to the driver. A test checks that this matches what __init__ sets,
    # so that adding an attribute here cannot silently start writing it to the
    # driver instead.
    _OWN = frozenset(['_driver', '_timeout', '_jobs', '_thread', '_name'])

    def __init__(self, driver, timeout):
        self._driver = driver
        self._timeout = timeout
        self._jobs = queue.Queue()
        self._thread = threading.Thread(target=self._work, name='LoopGuard', daemon=True)
        self._thread.start()
        # Only for messages. Asked through the worker like anything else, so that
        # a driver already wedged at load time is caught here rather than later.
        self._name = self.hardware_name
        self._thread.name = 'LoopGuard-%s' % self._name

    def __getattr__(self, name):
        """Relay everything the engine asks of the driver, except closePort()."""
        # __getattr__ runs only for names the instance does not have, so a lookup
        # before _driver is set would ask for _driver, and ask again, forever.
        if name == '_driver':
            raise AttributeError(name)
        # Ask the class, not the instance: reading a property off the instance
        # would run the driver's code here, on the engine's thread, which is the
        # very thing to be avoided.
        attr = getattr(type(self._driver), name, None)
        if isinstance(attr, property):
            return self._relay(lambda: getattr(self._driver, name))
        if callable(attr):
            return functools.partial(self._call, name)
        # A plain data attribute. Reading it is a dictionary lookup and cannot
        # block, so there is nothing to guard.
        return getattr(self._driver, name)

    def __setattr__(self, name, value):
        """Set on the driver, unless the name is one of the guard's own.

        Nothing in weewx assigns to a driver, but an extension may, and the
        assignment can land on a property with a setter. That runs driver code,
        so it goes through the worker like every other call.
        """
        if name in LoopGuard._OWN:
            object.__setattr__(self, name, value)
        else:
            self._relay(lambda: setattr(self._driver, name, value))

    def closePort(self):
        """Close the driver, then stop the worker.

        The one call that does not go through the worker. It is the only lever
        that might free a driver blocked in a read, so queueing it behind that
        same blocked worker would defeat it.

        A worker that outlives the join is logged, because it still holds the
        device and the next engine will not get it open.
        """
        try:
            self._driver.closePort()
        finally:
            self._jobs.put(None)
            self._thread.join(JOIN_TIMEOUT)
            if self._thread.is_alive():
                log.error("LoopGuard thread for %s did not stop. "
                          "It still holds the device open.", self._name)

    def _call(self, name, *args, **kwargs):
        """Call a method on the driver, on the worker thread.

        Args:
            name (str): Name of the driver method.
            *args: Passed to the method unchanged.
            **kwargs: Passed to the method unchanged.

        Returns:
            object: Whatever the method returned, except that an iterator comes
                back wrapped, so that pulling from it is guarded too.
        """
        return self._relay(lambda: getattr(self._driver, name)(*args, **kwargs))

    def _relay(self, work):
        """Run one piece of driver work under the deadline.

        Args:
            work (Callable[[], object]): Called as ``work()`` on the worker
                thread. Returns whatever the driver returned.

        Returns:
            object: The result, or a guarded iterator standing in for one.
        """
        result = self._await(work)
        # genLoopPackets(), genArchiveRecords() and genStartupRecords() all hand
        # back a generator. Pulling from it runs driver code, so it needs the same
        # treatment as the call that produced it.
        if hasattr(result, '__next__'):
            return self._pull(result)
        return result

    def _await(self, work):
        """Hand work to the worker thread and wait out the deadline for it.

        Args:
            work (Callable[[], object]): Called as ``work()`` on the worker
                thread.

        Returns:
            object: What the work returned.

        Raises:
            weewx.WeeWxIOError: If the deadline passed with no answer.
            Exception: Whatever the driver raised, re-raised here so the engine
                sees the driver's own error rather than a deadline.
        """
        answer = queue.Queue(maxsize=1)
        self._jobs.put(_Job(work, answer))
        try:
            returned, value = answer.get(timeout=self._timeout)
        except queue.Empty:
            raise weewx.WeeWxIOError("No answer from %s in %.0f seconds"
                                     % (self._name, self._timeout))
        if returned:
            return value
        raise value

    def _pull(self, iterator):
        """Yield from an iterator that lives on the worker thread.

        A generator function, so that abandoning it closes the driver's generator
        as well. The engine abandons the LOOP generator at the end of every
        archive period, by raising BreakLoop out of StdArchive.

        Args:
            iterator (Iterator): The driver's own iterator. Only the worker thread
                touches it.

        Yields:
            object: Its elements, one deadline each.
        """
        try:
            while True:
                try:
                    yield self._await(lambda: next(iterator))
                except StopIteration:
                    return
        finally:
            # Nobody waits for this: the engine abandons the LOOP generator every
            # archive period, and it must not have to wait on the driver to do it.
            self._jobs.put(_Job(iterator.close, None))

    def _work(self):
        """Run the driver's calls, one at a time, on this thread.

        Runs as a thread. Every call the engine makes lands here, so the driver
        only ever runs on this one thread, whatever it does with it.
        """
        while True:
            job = self._jobs.get()
            if job is None:
                return
            try:
                outcome = (True, job.work())
            except Exception as e:
                outcome = (False, e)
            if job.answer is not None:
                job.answer.put(outcome)
