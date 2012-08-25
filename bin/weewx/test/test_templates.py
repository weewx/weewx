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
import os.path
import sys
import syslog
import time
import unittest

import weewx.reportengine
import weeutil.weeutil

from gen_fake_data import StatsTestBase

config_path = None

    
class TemplateTest(StatsTestBase):

    def setUp(self):
        syslog.openlog('test_templates', syslog.LOG_CONS)
        self.config_path = config_path

        # This will generate the test databases if necessary:
        StatsTestBase.setUp(self)

    def testReportEngine(self):
        
        # Pick a random generation time (3-Sep-2010 11:20:00 local):
        testtime_ts = int(time.mktime((2010,9,3,11,20,0,0,0,-1)))
        print "test time is ", weeutil.weeutil.timestamp_to_string(testtime_ts)

        t = weewx.reportengine.StdReportEngine(self.config_path, testtime_ts)

        # Find the test skins and then have SKIN_ROOT point to it:
        test_dir = sys.path[0]
        t.config_dict['StdReport']['SKIN_ROOT'] = os.path.join(test_dir, 'test_skins')

        # Although the report engine inherits from Thread, we can just run it in the main thread:
        print "Starting report engine test"
        t.run()
        print "Done."
        
        test_html_dir = os.path.join(t.config_dict['Station']['WEEWX_ROOT'], t.config_dict['StdReport']['HTML_ROOT'])
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
            for actual_line in actual:
                n += 1
                expected_line = expected.readline()
                self.assertEqual(actual_line, expected_line)
            
            print "Checked %d lines" % (n,)

if __name__ == '__main__':
    if len(sys.argv) < 2 :
        print "Usage: python test_templates.py path-to-configuration-file"
        exit()

    config_path = sys.argv[1]
    del sys.argv[1:]
    unittest.main()
