#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author: tkeffer $
#    $Date$
#
"""Test the accumulators by using the simulator wx station"""

from __future__ import with_statement
import sys
import syslog
import time
import unittest
import os

import configobj

import weeutil.weeutil
import weewx.wxengine
import weedb

run_length = .5      # How long to run the simulator in hours.
config_path = "simgen.conf"
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
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        (first_ts, last_ts) = _get_first_last(config_dict)

        # Set the database to be used in the configuration dictionary
        config_dict['StdArchive']['archive_database'] = self.archive_db
        config_dict['StdArchive']['stats_database']   = self.stats_db
        archive_db_dict = config_dict['Databases'][self.archive_db]

        try:
            with weewx.archive.Archive.open(archive_db_dict) as archive:
                if archive.firstGoodStamp() == first_ts and archive.lastGoodStamp() == last_ts:
                    print "Simulator need not be run"
                    return 
        except weedb.OperationalError:
            pass
        
        # This will generate the simulator data:
        engine = weewx.wxengine.StdEngine(config_dict)
        try:
            engine.run()
        except weewx.StopNow:
            pass
        
    def tearDown(self):
        pass


    def test_create_sim(self):
        print "testing..."
        

class Stopper(weewx.wxengine.StdService):
    """Special service which stops the engine when it gets to a certain time."""
    
    def __init__(self, engine, config_dict):
        global run_length
        super(Stopper, self).__init__(engine, config_dict)

        (self.first_ts, self.last_ts) = _get_first_last(config_dict)

        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
        self.nloop = self.nrecords = 0
        
    def new_loop_packet(self, event):
        if self.nloop % 10 == 0:
            print >>sys.stdout, "LOOP packets processed: %d; Last date: %s\r" % (self.nloop, weeutil.weeutil.timestamp_to_string(event.packet['dateTime'])),
            sys.stdout.flush()
        self.nloop += 1
            
    def new_archive_record(self, event):
        if event.record['dateTime'] >= self.last_ts:
            raise weewx.StopNow("Time to stop!")
        
class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_sqlite"
        self.stats_db   = "stats_sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_mysql"
        self.stats_db   = "stats_mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)
        
def _get_first_last(config_dict):
    """Get the first and last archive record timestamps."""
    start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%d %H:%M")
    start_ts = time.mktime(start_tt)
    first_ts = start_ts + config_dict['StdArchive'].as_int('archive_interval')
    last_ts = start_ts + run_length *3600.0
    return (first_ts, last_ts)

def suite():
    tests = ['test_create_sim']
#    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))
    return unittest.TestSuite(map(TestSqlite, tests))

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
    

