# -*- coding: utf-8 -*-
#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Test tag notation for template generation."""
from __future__ import with_statement
import os.path
import sys
import syslog
import time
import unittest

import configobj

import weewx.reportengine
import weewx.station
import weeutil.weeutil

import gen_fake_data    # @UnresolvedImport

config_path = "testgen.conf"
cwd = None

class Common(unittest.TestCase):

    def setUp(self):
        global config_path
        global cwd
        
        weewx.debug = 1

        syslog.openlog('test_templates', syslog.LOG_CONS)
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

        self.archive_db_dict = self.config_dict['Databases'][self.archive_db]        
        self.stats_db_dict   = self.config_dict['Databases'][self.stats_db]

        # Remove the old directory:
        try:
            os.rmdir(self.config_dict['StdReport']['HTML_ROOT'])
        except OSError:
            pass

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.archive_db_dict, self.stats_db_dict)

    def tearDown(self):
        pass
    
    def test_report_engine(self):
        
        # Pick a random generation time (3-Sep-2010 11:20:00 local):
        testtime_ts = int(time.mktime((2010,9,3,11,20,0,0,0,-1)))
        print "test time is ", weeutil.weeutil.timestamp_to_string(testtime_ts)

        stn_info = weewx.station.StationInfo(**self.config_dict['Station'])
    
        t = weewx.reportengine.StdReportEngine(self.config_dict, stn_info, testtime_ts)

        # Find the test skins and then have SKIN_ROOT point to it:
        test_dir = sys.path[0]
        t.config_dict['StdReport']['SKIN_ROOT'] = os.path.join(test_dir, 'test_skins')

        # Although the report engine inherits from Thread, we can just run it in the main thread:
        print "Starting report engine test"
        t.run()
        print "Done."
        
        test_html_dir = os.path.join(t.config_dict['WEEWX_ROOT'], t.config_dict['StdReport']['HTML_ROOT'])
        expected_dir  = os.path.join(test_dir, 'expected')
        
        for file_name in ['index.html', 'bymonth.txt', 'byyear.txt', 
                     'metric/index.html', 'metric/bymonth.txt', 'metric/byyear.txt']:
            actual_file   = os.path.join(test_html_dir, file_name)
            expected_file = os.path.join(expected_dir, file_name)
            print "Checking file: ", actual_file
            print "  against file:", expected_file
            actual   = open(actual_file)
            expected = open(expected_file)

            n = 0
            while True:
                n += 1
                actual_line   = actual.readline()
                expected_line = expected.readline()
                if actual_line == '' or expected_line == '':
                    break
                self.assertEqual(actual_line, expected_line, "Line %d: %r vs %r" % (n, actual_line, expected_line))
            
            print "Checked %d lines" % (n,)

class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_sqlite"
        self.stats_db   = "stats_sqlite"
        self.HTML_ROOT  = 'test_skins_sqlite'
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_mysql"
        self.stats_db   = "stats_mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_report_engine']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
