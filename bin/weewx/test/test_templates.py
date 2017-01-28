# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test tag notation for template generation."""
from __future__ import with_statement
import locale
import os.path
import shutil
import sys
import syslog
import unittest

import configobj

os.environ['TZ'] = 'America/Los_Angeles'

# This will use the locale specified by the environment variable 'LANG'
# Other options are possible. See:
# http://docs.python.org/2/library/locale.html#locale.setlocale
locale.setlocale(locale.LC_ALL, '')


import weewx.reportengine
import weewx.station
import weeutil.weeutil

import gen_fake_data  # @UnresolvedImport

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")
cwd = None

# We will be testing the ability to extend the unit system, so set that up first:
class ExtraUnits(dict):
    def __getitem__(self, obs_type):
        if obs_type.endswith('Temp'):
            # Anything that ends with "Temp" is assumed to be in group_temperature
            return "group_temperature"
        elif obs_type.startswith('current'):
            # Anything that starts with "current" is in group_amperage:
            return "group_amperage"
        else:
            # Otherwise, consult the underlying dictionary:
            return dict.__getitem__(self, obs_type)
 
extra_units = ExtraUnits()
import weewx.units
weewx.units.obs_group_dict.extend(extra_units)

# Add the new group group_amperage to the standard unit systems:
weewx.units.USUnits["group_amperage"] = "amp"
weewx.units.MetricUnits["group_amperage"] = "amp"
weewx.units.MetricWXUnits["group_amperage"] = "amp"

weewx.units.default_unit_format_dict["amp"] = "%.1f"
weewx.units.default_unit_label_dict["amp"] = " A"

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

        # Remove the old directory:
        try:
            test_html_dir = os.path.join(self.config_dict['WEEWX_ROOT'], self.config_dict['StdReport']['HTML_ROOT'])
            shutil.rmtree(test_html_dir)
        except OSError, e:
            if os.path.exists(test_html_dir):
                print >> sys.stderr, "\nUnable to remove old test directory %s", test_html_dir
                print >> sys.stderr, "Reason:", e
                print >> sys.stderr, "Aborting"
                exit(1)

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass
    
    def test_report_engine(self):
        
        # The generation time should be the same as the last record in the test database:
        testtime_ts = gen_fake_data.stop_ts
        print "\ntest time is ", weeutil.weeutil.timestamp_to_string(testtime_ts)

        stn_info = weewx.station.StationInfo(**self.config_dict['Station'])
        
        # First run the engine without a current record.
        self.run_engine(stn_info, None, testtime_ts)
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding')  as manager:
            record = manager.getRecord(testtime_ts)
        # Now run the engine again, but this time with a current record:
        self.run_engine(stn_info, record, testtime_ts)
        
    def run_engine(self, stn_info, record, testtime_ts):
        t = weewx.reportengine.StdReportEngine(self.config_dict, stn_info, record, testtime_ts)

        # Find the test skins and then have SKIN_ROOT point to it:
        test_dir = sys.path[0]
        t.config_dict['StdReport']['SKIN_ROOT'] = os.path.join(test_dir, 'test_skins')
        
        # Although the report engine inherits from Thread, we can just run it in the main thread:
        print "Starting report engine test"
        t.run()
        print "Done."
        
        test_html_dir = os.path.join(t.config_dict['WEEWX_ROOT'], t.config_dict['StdReport']['HTML_ROOT'])
        expected_dir  = os.path.join(test_dir, 'expected')

        # Walk the directory of expected results to discover all the generated files we should
        # be checking
        for dirpath, _, dirfilenames in os.walk(expected_dir):
            for dirfilename in dirfilenames:
                expected_filename_abs = os.path.join(dirpath, dirfilename)
                # Get the file path relative to the directory of expected results
                filename_rel = weeutil.weeutil.relpath(expected_filename_abs, expected_dir)
                # Use that to figure out where the actual results ended up
                actual_filename_abs = os.path.join(test_html_dir, filename_rel)
#                 print "Checking file: ", actual_filename_abs
#                 print "  against file:", expected_filename_abs
                actual = open(actual_filename_abs)
                expected = open(expected_filename_abs)
    
                n = 0
                while True:
                    actual_line = actual.readline()
                    expected_line = expected.readline()
                    if actual_line == '' or expected_line == '':
                        break
                    n += 1
                    self.assertEqual(actual_line, expected_line, msg="%s[%d]:\n%r vs\n%r" % 
                                     (actual_filename_abs, n, actual_line, expected_line))
                
                print "Checked %d lines" % (n,)

class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)
        
        
    
def suite():
    tests = ['test_report_engine']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
