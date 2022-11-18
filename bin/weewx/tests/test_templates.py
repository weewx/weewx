# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test tag notation for template generation.

To run standalone, PYTHONPATH must be set to not only the WeeWX code, but also the "stats" example.
Something like:

cd ~/git/weewx
PYTHONPATH="./examples:./bin" python bin/weewx/tests/test_templates.py
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import locale
import logging
import os.path
import shutil
import sys
import time
import unittest

import configobj
from six.moves import map

import gen_fake_data
import weeutil.logger
import weeutil.weeutil
import weeutil.config
import weewx
import weewx.accum
import weewx.reportengine
import weewx.station
import weewx.units

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_templates', {})

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# This will use the locale specified by the environment variable 'LANG'
# Other options are possible. See:
# http://docs.python.org/2/library/locale.html#locale.setlocale
locale.setlocale(locale.LC_ALL, '')

# Find the configuration file. It's assumed to be in the same directory as me, so first figure
# out where that is.
my_dir = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# The full path to the configuration file:
config_path = os.path.join(my_dir, "testgen.conf")

try:
    config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
except IOError:
    sys.stderr.write("Unable to open configuration file %s" % config_path)
    # Reraise the exception (this will eventually cause the program to exit)
    raise
except configobj.ConfigObjError:
    sys.stderr.write("Error while parsing configuration file %s" % config_path)
    raise

# We test accumulator configurations as well, so initialize the Accumulator dictionary:
weewx.accum.initialize(config_dict)

# These tests also test the examples in the 'example' subdirectory.
# Patch PYTHONPATH to find them.
example_dir = os.path.normpath(os.path.join(my_dir, '../../../examples'))
sys.path.append(example_dir)
sys.path.append(os.path.join(example_dir, './colorize'))

import colorize_1
import colorize_2
import colorize_3

# Monkey patch to create SLEs with unambiguous names. We will test using these names.
colorize_1.Colorize.colorize_1 = colorize_1.Colorize.colorize
colorize_2.Colorize.colorize_2 = colorize_2.Colorize.colorize
colorize_3.Colorize.colorize_3 = colorize_3.Colorize.colorize


# We will be testing the ability to extend the unit system, so set that up first:
class ExtraUnits(object):
    def __getitem__(self, obs_type):
        if obs_type.endswith('Temp'):
            # Anything that ends with "Temp" is assumed to be in group_temperature
            return "group_temperature"
        elif obs_type.startswith('current'):
            # Anything that starts with "current" is in group_amperage:
            return "group_amperage"
        else:
            raise KeyError(obs_type)

    def __contains__(self, obs_type):
        return obs_type.endswith('Temp') or obs_type.startswith('current')


extra_units = ExtraUnits()
weewx.units.obs_group_dict.extend(extra_units)

# Add the new group group_amperage to the standard unit systems:
weewx.units.USUnits["group_amperage"] = "amp"
weewx.units.MetricUnits["group_amperage"] = "amp"
weewx.units.MetricWXUnits["group_amperage"] = "amp"

weewx.units.default_unit_format_dict["amp"] = "%.1f"
weewx.units.default_unit_label_dict["amp"] = " A"


class Common(object):

    def setUp(self):
        global config_dict

        self.config_dict = weeutil.config.deep_copy(config_dict)

        # Remove the old directory:
        try:
            test_html_dir = os.path.join(self.config_dict['WEEWX_ROOT'],
                                         self.config_dict['StdReport']['HTML_ROOT'])
            shutil.rmtree(test_html_dir)
        except OSError as e:
            if os.path.exists(test_html_dir):
                print("\nUnable to remove old test directory %s", test_html_dir, file=sys.stderr)
                print("Reason:", e, file=sys.stderr)
                print("Aborting", file=sys.stderr)
                exit(1)

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass

    def test_report_engine(self):

        # The generation time should be the same as the last record in the test database:
        testtime_ts = gen_fake_data.stop_ts
        print("\ntest time is %s" % weeutil.weeutil.timestamp_to_string(testtime_ts))

        stn_info = weewx.station.StationInfo(**self.config_dict['Station'])

        # First run the engine without a current record.
        self.run_engine(stn_info, None, testtime_ts)
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as manager:
            record = manager.getRecord(testtime_ts)
        # Now run the engine again, but this time with a current record:
        self.run_engine(stn_info, record, testtime_ts)

    def run_engine(self, stn_info, record, testtime_ts):
        t = weewx.reportengine.StdReportEngine(self.config_dict, stn_info, record, testtime_ts)

        # Find the test skins and then have SKIN_ROOT point to it:
        test_dir = sys.path[0]
        t.config_dict['StdReport']['SKIN_ROOT'] = os.path.join(test_dir, 'test_skins')

        # Although the report engine inherits from Thread, we can just run it in the main thread:
        print("Starting report engine test")
        t.run()
        print("Done.")

        test_html_dir = os.path.join(t.config_dict['WEEWX_ROOT'],
                                     t.config_dict['StdReport']['HTML_ROOT'])
        expected_dir = os.path.join(test_dir, 'expected')

        # Walk the directory of expected results to discover all the generated files we should
        # be checking
        for dirpath, _, dirfilenames in os.walk(expected_dir):
            for dirfilename in dirfilenames:
                expected_filename_abs = os.path.join(dirpath, dirfilename)
                # Get the file path relative to the directory of expected results
                filename_rel = os.path.relpath(expected_filename_abs, expected_dir)
                # Use that to figure out where the actual results ended up
                actual_filename_abs = os.path.join(test_html_dir, filename_rel)

                with open(actual_filename_abs, 'r') as actual:
                    with open(expected_filename_abs, 'r') as expected:
                        n = 0
                        while True:
                            actual_line = actual.readline()
                            expected_line = expected.readline()
                            if actual_line == '' and expected_line == '':
                                break
                            n += 1
                            self.assertEqual(actual_line,
                                             expected_line,
                                             msg="%s[%d]:\n%r vs\n%r"
                                                 % (actual_filename_abs, n, actual_line,
                                                    expected_line))

                        print("Checked %d lines" % n)


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super(TestMySQL, self).setUp()


def suite():
    tests = ['test_report_engine']
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))
    # return unittest.TestSuite(list(map(TestSqlite, tests)) )


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
