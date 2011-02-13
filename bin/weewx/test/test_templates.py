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
import sys
import os.path
import syslog
import unittest

import Cheetah.Template

import weewx.stats
import weewx.reportengine

from gen_fake_data import StatsTestBase, stop_ts

config_path = None

    
class TemplateTest(StatsTestBase):

    def setUp(self):
        syslog.openlog('test_templates', syslog.LOG_CONS)
        self.config_path = config_path

        # This will generate the test databases if necessary:
        StatsTestBase.setUp(self)

    def testReportEngine(self):
        
        t = weewx.reportengine.StdReportEngine(self.config_path, stop_ts)

        t.config_dict['Reports']['SKIN_ROOT'] = sys.path[0]
        # Switch around the path to the archive and stats databases
        # so they point to the test archive 
        t.config_dict['Archive']['archive_file'] = self.archiveFilename
        t.config_dict['Stats']['stats_file']     = self.statsFilename

        # Although the report engine inherits from Thread, we can just run it in the main thread:
        t.run()


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2 :
        print "Usage: python test_templates.py path-to-configuration-file"
        exit()

    config_path = sys.argv[1]
    del sys.argv[1:]
    unittest.main()
