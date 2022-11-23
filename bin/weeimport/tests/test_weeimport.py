# -*- coding: utf-8 -*-
#
#    Copyright (c) 2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test wee_import modules"""
from __future__ import with_statement
from __future__ import absolute_import

import unittest
import time

from six.moves import StringIO
from six.moves import map
from six.moves import range

import configobj
import os

import weecfg
import weeimport.weeimport
import weeimport.csvimport
import weewx.manager
import weedb
import weeutil.weeutil
import weeutil.logger

weeutil.logger.setup('test_weeimport',{})

archive_sqlite = {'database_name': '/var/tmp/weewx_test/weedb.sdb', 'driver':'weedb.sqlite'}
archive_mysql  = {'database_name': 'test_weedb', 'user':'weewx1', 'password':'weewx1', 'driver':'weedb.mysql'}

archive_schema = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                  ('usUnits',              'INTEGER NOT NULL'),
                  ('interval',             'INTEGER NOT NULL'),
                  ('barometer',            'REAL'),
                  ('inTemp',               'REAL'),
                  ('outTemp',              'REAL'),
                  ('windSpeed',            'REAL')]

std_unit_system = 1
interval = 3600     # One hour
nrecs = 48          # Two days
start_ts = int(time.mktime((2012, 7, 1, 00, 00, 0, 0, 0, -1))) # 1 July 2012
stop_ts = start_ts + interval * (nrecs-1)
timevec = [start_ts+i*interval for i in range(nrecs)]

# Find the configuration file. It's assumed to be in the same directory as me, so first figure
# out where that is.
my_dir = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# The full path to the configuration file:
test_import_config_path = os.path.join(my_dir, "test_import.conf")
test_import_csv_import_config_path = os.path.join(my_dir, "test_csv_import.conf")


def timefunc(i):
    return start_ts + i * interval


def barfunc(i):
    return 30.0 + 0.01 * i


def temperfunc(i):
    return 68.0 + 0.1 * i


def expected_record(irec):
    _record = {'dateTime': timefunc(irec), 'interval': int(interval / 60), 'usUnits': 1,
               'outTemp': temperfunc(irec), 'barometer': barfunc(irec),
               'inTemp': 70.0 + 0.1 * irec}
    return _record


def gen_included_recs(timevec, start_ts, stop_ts, agg_interval):
    """Generator function that marches down a set of aggregation intervals. Each yield returns
     the set of records included in that interval."""
    for span in weeutil.weeutil.intervalgen(start_ts, stop_ts, agg_interval):
        included = set()
        for (irec, ts) in enumerate(timevec):
            if span[0] < ts <= span[1]:
                included.add(irec)
        yield included


def genRecords():
    for irec in range(nrecs):
        _record = expected_record(irec)
        yield _record


class TestCsvImport(unittest.TestCase):
    """Test CSV import."""

    # cut down import config to test application of defaults
    default_import_config = """
    file = /var/tmp/data.csv
    [FieldMap]
        dateTime    = timestamp, unix_epoch
        interval    =
        barometer   = barometer, inHg"""

    class Options(object):
        """Class to represent command line options fed to wee_import.

        Refer to wee_import parser options for details.
        """

        def __init__(self):
            self.config_path = None
            self.import_config_path = None
            self.dry_run = None
            self.date = None
            self.date_from = None
            self.date_to = None
            self.verbose = None
            self.no_prompt = None
            self.suppress = None
            self.version = None

    def setUp(self):
        """Setup the environment for our tests.

        A CsvSource object is required to allow the test to be run. To
        initialise a CsvSource object we require a WeeWX config dict as well as
        a CSV import source config file.
        """

        # obtain path and content of our WeeWX test config file
        self.config_path, self.config_dict = weecfg.read_config(test_import_config_path,
                                                                file_name="test_import.conf")
        # obtain path and content of our WeeWX test import config file
        self.import_config_path, import_config_dict = weecfg.read_config(test_import_csv_import_config_path,
                                                                         file_name="test_csv_import.conf")
        # but our csv import config sits under [CSV]
        self.import_config_dict = import_config_dict.get('CSV')
        # obtain an Options object to hold any 'wee_import' command line
        # options
        self.options = TestCsvImport.Options()
        # now we can get a CsvSource object
        self.csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                            self.config_path,
                                                            self.import_config_dict,
                                                            self.import_config_path,
                                                            self.options)
        # get a CsvSource object based upon defaults only, first get a minimal
        # import config
        minimal_import_config_dict = configobj.ConfigObj(StringIO(TestCsvImport.default_import_config))
        # now get a CsvSource object based on this minimal import config
        self.csv_source_obj_defaults = weeimport.csvimport.CSVSource(self.config_dict,
                                                                     self.config_path,
                                                                     minimal_import_config_dict,
                                                                     self.import_config_path,
                                                                     self.options)

    def test_csv_init(self):
        """Test CsvSource object initialisation.

        Test that the CsvSource object was correctly initialise from our config
        dicts and command line options.
        """

        # check the import_config_path property is correctly set
        self.assertEqual(self.csv_source_obj.import_config_path, self.import_config_path)
        # check the csv import config dict is correctly set
        self.assertEqual(self.csv_source_obj.csv_config_dict, self.import_config_dict)
        # check the delimiter property is correctly set
        self.assertEqual(self.csv_source_obj.delimiter, ',')
        # check the raw_datetime_format property is correctly set
        self.assertEqual(self.csv_source_obj.raw_datetime_format, '%Y-%m-%d %H:%M:%S')
        # check the rain property is correctly set
        self.assertEqual(self.csv_source_obj.rain, 'cumulative')
        # check the wind_dir property is correctly set
        self.assertEqual(self.csv_source_obj.wind_dir, [-360, 360])
        # check the source property is correctly set
        self.assertEqual(self.csv_source_obj.source, self.import_config_dict.get('file'))
        # check the source_encoding property is correctly set
        self.assertEqual(self.csv_source_obj.source_encoding, 'utf-8-sig')
        # check the map property is correctly set
        self.assertIsNone(self.csv_source_obj.map)
        # check the start property is correctly set
        self.assertEqual(self.csv_source_obj.start, 1)
        # check the end property is correctly set
        self.assertEqual(self.csv_source_obj.end, 1)
        # check the increment property is correctly set
        self.assertEqual(self.csv_source_obj.increment, 1)
        # check the verbose property is correctly set
        self.assertIsNone(self.csv_source_obj.verbose)

    def test_csv_defaults(self):
        """Test CsvSource object defaults.

        Test that class CsvSource defaults are correctly applied.
        """

        # check the delimiter property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.delimiter, ',')
        # check the raw_datetime_format property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.raw_datetime_format, '%Y-%m-%d %H:%M:%S')
        # check the rain property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.rain, 'cumulative')
        # check the wind_dir property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.wind_dir, [0, 360])
        # check the source_encoding property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.source_encoding, 'utf-8-sig')
        # check the interval property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.interval, 'derive')
        # check the ignore_invalid_data property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.ignore_invalid_data, True)
        # check the tranche property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.tranche, 250)
        # check the apply_qc property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.apply_qc, True)
        # check the calc_missing property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.calc_missing, True)
        # check the decimal_sep property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.decimal_sep, '.')
        # check the UV_sensor property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.UV_sensor, True)
        # check the solar_sensor property is set to the default
        self.assertEqual(self.csv_source_obj_defaults.solar_sensor, True)


def suite():
    """Create a TestSuite object containing the tests to be performed."""

    # the list of test cases to be performed
    tests = [TestCsvImport, ]
    # get a test loader
    loader = unittest.TestLoader()
    # create an empty test suite
    test_suite = unittest.TestSuite()
    # iterate over the test cases we are to add
    for test_class in tests:
        # get the tests from the test case
        tests = loader.loadTestsFromTestCase(test_class)
        # and add the tests to the test suite
        test_suite.addTests(tests)
    # finally return the populated test suite
    return test_suite

if __name__ == '__main__':
    # obtain a TestSuite containing the test to be run and then run the tests
    unittest.TextTestRunner(verbosity=2).run(suite())
