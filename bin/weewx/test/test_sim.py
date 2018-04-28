#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the accumulators by using the simulator wx station"""

from __future__ import with_statement
import sys
import syslog
import time
import unittest
import os.path

import configobj

os.environ['TZ'] = 'America/Los_Angeles'

import weedb
import weeutil.weeutil
import weewx.manager
import weewx.drivers.simulator
import weewx.engine

run_length = 48.0      # How long to run the simulator in hours.
# The types to actually test:
test_types = ['outTemp', 'inTemp', 'barometer', 'windSpeed']

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "simgen.conf")

cwd = None

class Common(unittest.TestCase):
    
    def setUp(self):
        global config_path
        global cwd

        weewx.debug = 1

        syslog.openlog('test_sim', syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # Save and set the current working directory in case some service changes it.
        if not cwd:
            cwd = os.getcwd()
        else:
            os.chdir(cwd)

        try :
            self.config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # Fiddle with config_dict to reflect the database in use:
        self.config_dict['DataBindings']['wx_binding']['database'] = self.database
        # Fiddle with config_dict to reflect if we are generating spikes
        self.config_dict['Simulator']['spike'] = self.spike
        
        (first_ts, last_ts) = _get_first_last(self.config_dict)

        try:
            with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as dbmanager:
                if dbmanager.firstGoodStamp() == first_ts and dbmanager.lastGoodStamp() == last_ts:
                    print "\nSimulator need not be run"
                    return 
        except weedb.OperationalError:
            pass
        
        # This will generate the simulator data:
        engine = weewx.engine.StdEngine(self.config_dict)
        try:
            engine.run()
        except weewx.StopNow:
            pass
        
    def tearDown(self):
        pass


    def test_archive_data(self):

        global test_types
        archive_interval = self.config_dict['StdArchive'].as_int('archive_interval')
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as archive:
            for record in archive.genBatchRecords():
                start_ts = record['dateTime'] - archive_interval
                # Calculate the average (throw away min and max):
                (_, _, obs_avg) = calc_stats(self.config_dict, start_ts, record['dateTime'])
                for obs_type in test_types:
                    self.assertAlmostEqual(obs_avg[obs_type], record[obs_type], self.test_decimal_places)
                    
        
class Stopper(weewx.engine.StdService):
    """Special service which stops the engine when it gets to a certain time."""
    
    def __init__(self, engine, config_dict):
        global run_length
        super(Stopper, self).__init__(engine, config_dict)

        (self.first_ts, self.last_ts) = _get_first_last(config_dict)

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
    def new_archive_record(self, event):
        print >>sys.stdout, "Archive record %s" % (weeutil.weeutil.timestamp_to_string(event.record['dateTime']))
        sys.stdout.flush()
        if event.record['dateTime'] >= self.last_ts:
            raise weewx.StopNow("Time to stop!")


class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.database = "archive_sqlite"
        # Plain test without spikes
        self.spike = 0
        # When testing plain simulator without spikes the comparison should be correct to 2 decimal places
        self.test_decimal_places = 2
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestSqliteSpike(Common):

    def __init__(self, *args, **kwargs):
        self.database = "archive_sqlite_spike"
        # Test with spike magnitude of 2
        self.spike = 2
        # When testing with spikes, the database run should have spikes removed.
        # When testing against a plain simulator run the comparison should be correct to one decimal place
        # as the plain simulator will not have spikes
        self.test_decimal_places = 1
        super(TestSqliteSpike, self).__init__(*args, **kwargs)


class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.database = "archive_mysql"
        # Plain test without spikes
        self.spike = 0
        # When testing plain simulator without spikes the comparison should be correct to 2 decimal places
        self.test_decimal_places = 2
        super(TestMySQL, self).__init__(*args, **kwargs)


class TestMySQLSpike(Common):
    def __init__(self, *args, **kwargs):
        self.database = "archive_mysql_spike"
        # Test with spike magnitude of 2
        self.spike = 2
        # When testing with spikes, the database run should have spikes removed.
        # When testing against a plain simulator run the comparison should be correct to one decimal place
        # as the plain simulator will not have spikes
        self.test_decimal_places = 1
        super(TestMySQLSpike, self).__init__(*args, **kwargs)


def _get_first_last(config_dict):
    """Get the first and last archive record timestamps."""
    start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%dT%H:%M")
    start_ts = time.mktime(start_tt)
    first_ts = start_ts + config_dict['StdArchive'].as_int('archive_interval')
    last_ts = start_ts + run_length *3600.0
    return (first_ts, last_ts)


def calc_stats(config_dict, start_ts, stop_ts):
    """Calculate the statistics directly from the simulator output.
    This is always done without spikes which allows checking
    of spike QC code when spikes are generated versus good simulator output."""
    global test_types
    
    sim_start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%dT%H:%M")
    sim_start_ts = time.mktime(sim_start_tt)
            
    simulator = weewx.drivers.simulator.Simulator(loop_interval=config_dict['Simulator'].as_int('loop_interval'),
                                          mode='generator',
                                          start_time=sim_start_ts,
                                          resume_time=start_ts)

    obs_sum = dict(zip(test_types, len(test_types)*(0,)))
    obs_min = dict(zip(test_types, len(test_types)*(None,)))
    obs_max = dict(zip(test_types, len(test_types)*(None,))) 
    count = 0

    for packet in simulator.genLoopPackets():
        if packet['dateTime'] > stop_ts:
            break
        for obs_type in test_types:
            obs_sum[obs_type] += packet[obs_type]
            obs_min[obs_type] =  packet[obs_type] if obs_min[obs_type] is None else min(obs_min[obs_type], packet[obs_type])
            obs_max[obs_type] =  packet[obs_type] if obs_max[obs_type] is None else max(obs_max[obs_type], packet[obs_type])
        count +=1

    obs_avg = {}
    for obs_type in obs_sum:
        obs_avg[obs_type] = obs_sum[obs_type]/count

    return (obs_min, obs_max, obs_avg)


def suite():
    tests = ['test_archive_data']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestSqliteSpike, tests) + map(TestMySQL, tests) + map(TestMySQLSpike, tests))

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
    

