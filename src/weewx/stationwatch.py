#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Watch the age of the archive data, and say when it stops moving.

Every other engine event follows something happening: a packet arrived, a record
was written, the period ended. There is no event for nothing happening, which is
why a station that stops delivering data goes unremarked. WeeWX keeps running,
the log stays quiet, and the web page keeps showing the last reading it had.

StdStationWatch checks how old the newest archive record is, and dispatches
STATION_DOWN when it gets older than 'max_age', STATION_UP when records come
back. It also logs both. What to do beyond that is left to whoever binds to the
events.

It is off unless 'max_age' is set:

    [StdStationWatch]
        max_age = 1800
"""

import logging
import threading
import time

import weedb
import weewx
import weewx.manager
from weeutil.weeutil import timestamp_to_string, to_int
from weewx.engine import StdService

log = logging.getLogger(__name__)

# Seconds between checks. The deadline is in minutes at least, so there is
# nothing to gain from looking more often than this.
CHECK_INTERVAL = 60


class StdStationWatch(StdService):
    """Dispatch STATION_DOWN and STATION_UP as the archive data stops and starts.

    The checking runs on a thread of its own, so both events are dispatched from
    that thread rather than from the main loop. They have to be: the main loop
    only comes round when a LOOP packet arrives, which during an outage is
    exactly what does not happen. Anything bound to these two events therefore
    runs off the main thread, and must not touch the console.
    """

    def __init__(self, engine, config_dict):
        super().__init__(engine, config_dict)

        watch_dict = config_dict.get('StdStationWatch', {})
        self.max_age = to_int(watch_dict.get('max_age', 0))
        self.thread = None
        if not self.max_age:
            return

        self.data_binding = watch_dict.get('data_binding', 'wx_binding')
        self.config_dict = config_dict
        # Whether the station was quiet when last looked at. Held in memory
        # only, so a restarted engine reports an outage that is still going on.
        self.down = False
        self.last_seen = None
        self.stopping = threading.Event()

        self.bind(weewx.STARTUP, self.startup)

    def startup(self, _event):
        """Start watching. The database exists by the time this runs."""
        self.thread = threading.Thread(target=self.watch, name='StdStationWatch',
                                       daemon=True)
        self.thread.start()
        log.info("Watching the station, deadline %d seconds", self.max_age)

    def shutDown(self):
        """Stop the watching thread. Called by the engine as it shuts down."""
        if self.thread is not None:
            self.stopping.set()
            self.thread.join(CHECK_INTERVAL)

    def watch(self):
        """Check the record age until the engine shuts down. Runs as a thread."""
        while not self.stopping.wait(CHECK_INTERVAL):
            try:
                self.check()
            except Exception as e:
                log.error("Station watch failed: %s", e)

    def check(self):
        """Compare the newest record against the deadline, and dispatch a change."""
        last_ts = self.last_record_time()
        if last_ts is None:
            # An empty database. There is nothing to have stopped yet.
            return

        age = time.time() - last_ts
        down = age > self.max_age
        if down == self.down:
            self.last_seen = last_ts
            return

        if down:
            log.warning("No archive record from the station since %s, %d seconds ago",
                        timestamp_to_string(last_ts), age)
            self.engine.dispatchEvent(weewx.Event(weewx.STATION_DOWN,
                                                  last_record=last_ts,
                                                  age=int(age),
                                                  gap=0))
        else:
            gap = last_ts - self.last_seen if self.last_seen else 0
            log.info("Archive records from the station have resumed. %d seconds missing",
                     gap)
            self.engine.dispatchEvent(weewx.Event(weewx.STATION_UP,
                                                  last_record=last_ts,
                                                  age=int(age),
                                                  gap=int(gap)))

        self.down = down
        self.last_seen = last_ts

    def last_record_time(self):
        """Ask the database for the timestamp of its newest record.

        Opens its own connection, because this runs on the watching thread and a
        database connection belongs to the thread that opened it.

        Returns:
            int|None: The timestamp, or None if there are no records to have one.
        """
        try:
            with weewx.manager.open_manager_with_config(self.config_dict,
                                                        self.data_binding) as dbmanager:
                return dbmanager.lastGoodStamp()
        except weedb.NoDatabaseError:
            # The engine has not got as far as creating it. Nothing to watch yet.
            return None
