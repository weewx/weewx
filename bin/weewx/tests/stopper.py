#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Helper class for stopping the engine after a specified period of time.

Originally, this class was included in test_engine.py. When test_engine.py was run, it would set
up the logger. Then it would run the engine, which would dynamically load "test_engine.Stopper",
which caused test_engine to be loaded *again*, resulting in the logger getting set up a 2nd time.
This resulted in "ResourceWarning" errors because the syslog socket connection from the first
setup was not closed.

So, class Stopper was moved to its own module. Now you know.
"""

import sys
import time
from weeutil.weeutil import to_int

import weewx.engine


class Stopper(weewx.engine.StdService):
    """Special service which stops the engine when it gets to a certain time."""

    def __init__(self, engine, config_dict):
        super(Stopper, self).__init__(engine, config_dict)

        # Fail hard if "run_length" or the "start" time are missing.
        run_length = to_int(config_dict['Stopper']['run_length'])
        start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%dT%H:%M")

        start_ts = time.mktime(start_tt)
        self.last_ts = start_ts + run_length * 3600.0

        self.count = 0

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_archive_record(self, event):
        self.count += 1
        print("~", end='')
        if self.count % 80 == 0:
            print("")
        sys.stdout.flush()
        if event.record['dateTime'] >= self.last_ts:
            raise weewx.StopNow("Time to stop!")
