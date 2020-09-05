#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the accumulators by using the simulator wx station"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import logging
import os.path
import sys
import time
import unittest

import configobj
from six.moves import zip

import weedb
import weeutil.weeutil
import weewx.drivers.simulator
import weewx.engine
import weewx.manager

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_engine', {})

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

RUN_LENGTH = 48.0  # How long to run the simulator in hours.
# The types to actually test:
TEST_TYPES = ['outTemp', 'inTemp', 'barometer', 'windSpeed']

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "simgen.conf")


class TestEngine(unittest.TestCase):
    """Test the engine and accumulators using the simulator."""

    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            print("Unable to open configuration file %s" % config_path, file=sys.stderr)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            print("Error while parsing configuration file %s" % config_path, file=sys.stderr)
            raise

        first_ts, last_ts = _get_first_last(self.config_dict)

        try:
            with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as dbmanager:
                if dbmanager.firstGoodStamp() == first_ts and dbmanager.lastGoodStamp() == last_ts:
                    print("\nSimulator need not be run")
                    return
        except weedb.OperationalError:
            pass

        # This will generate the simulator data:
        engine = weewx.engine.StdEngine(self.config_dict)
        try:
            engine.run()
        except weewx.StopNow:
            pass

    def test_archive_data(self):

        global TEST_TYPES
        archive_interval = self.config_dict['StdArchive'].as_int('archive_interval')
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as archive:
            for record in archive.genBatchRecords():
                start_ts = record['dateTime'] - archive_interval
                # Calculate the average (throw away min and max):
                _, _, obs_avg = calc_stats(self.config_dict, start_ts, record['dateTime'])
                for obs_type in TEST_TYPES:
                    self.assertAlmostEqual(obs_avg[obs_type], record[obs_type], 2)


class Stopper(weewx.engine.StdService):
    """Special service which stops the engine when it gets to a certain time."""

    def __init__(self, engine, config_dict):
        global RUN_LENGTH
        super(Stopper, self).__init__(engine, config_dict)

        self.first_ts, self.last_ts = _get_first_last(config_dict)
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


def _get_first_last(config_dict):
    """Get the first and last archive record timestamps."""
    start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%dT%H:%M")
    start_ts = time.mktime(start_tt)
    first_ts = start_ts + config_dict['StdArchive'].as_int('archive_interval')
    last_ts = start_ts + RUN_LENGTH * 3600.0
    return first_ts, last_ts


def calc_stats(config_dict, start_ts, stop_ts):
    """Calculate the statistics directly from the simulator output."""
    global TEST_TYPES

    sim_start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%dT%H:%M")
    sim_start_ts = time.mktime(sim_start_tt)

    simulator = weewx.drivers.simulator.Simulator(loop_interval=config_dict['Simulator'].as_int('loop_interval'),
                                                  mode='generator',
                                                  start_time=sim_start_ts,
                                                  resume_time=start_ts)

    obs_sum = dict(zip(TEST_TYPES, len(TEST_TYPES) * (0,)))
    obs_min = dict(zip(TEST_TYPES, len(TEST_TYPES) * (None,)))
    obs_max = dict(zip(TEST_TYPES, len(TEST_TYPES) * (None,)))
    count = 0

    for packet in simulator.genLoopPackets():
        if packet['dateTime'] > stop_ts:
            break
        for obs_type in TEST_TYPES:
            obs_sum[obs_type] += packet[obs_type]
            obs_min[obs_type] = packet[obs_type] if obs_min[obs_type] is None \
                else min(obs_min[obs_type], packet[obs_type])
            obs_max[obs_type] = packet[obs_type] if obs_max[obs_type] is None \
                else max(obs_max[obs_type], packet[obs_type])
        count += 1

    obs_avg = {}
    for obs_type in obs_sum:
        obs_avg[obs_type] = obs_sum[obs_type] / count

    return obs_min, obs_max, obs_avg


if __name__ == '__main__':
    unittest.main()
