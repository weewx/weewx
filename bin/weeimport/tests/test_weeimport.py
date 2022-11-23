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

import_test_working_dir = '/var/tmp/import_test'
# Find the config files used by the tests. they are assumed to be in the same
# directory as me, so first figure out where that is.
my_dir = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# the full path to the configuration file
test_import_config_path = os.path.join(my_dir, "test_import.conf")
# the full path to the csv import configuration file
test_import_csv_import_config_path = os.path.join(my_dir, "test_csv_import.conf")


class TestCsvImport(unittest.TestCase):
    """Test CSV import."""

    test_data_file = 'test_data.csv'
    test_data = """Time,Barometer,Temp,Humidity,Windspeed,Dir,Gust,Dayrain,Radiation,Uv,Comment
28/11/2017 08:00:00,1016.9,24.6,84,1.8,113,8,0,359,3.8,"start of observations"
28/11/2017 08:05:00,1016.9,25.1,82,4.8,135,11.3,0,775,4.7,
28/11/2017 08:10:00,1016.9,25.4,80,4.4,127,11.3,0,787,5.1,"note temperature"
28/11/2017 08:15:00,1017,25.7,79,3.5,74,11.3,0,800,5.4,
28/11/2017 08:20:00,1016.9,25.9,79,1.6,95,9.7,0,774,5.5,
28/11/2017 08:25:00,1017,25.5,78,2.9,48,9.7,0,303,3.4,"forecast received"
28/11/2017 08:30:00,1017.1,25.1,80,3.1,54,9.7,0,190,3.6,"""

    # minimal import config to test application of defaults
    default_import_config = """
    file = %s/%s
    [FieldMap]
        dateTime    = timestamp, unix_epoch
        interval    =
        barometer   = barometer, inHg""" % (import_test_working_dir, TestCsvImport.test_data_file)

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
        # generate the file containing the CSV test data to be imported
        with open(os.path.join(import_test_working_dir, TestCsvImport.test_data_file), 'w') as f:
            f.write(TestCsvImport.test_data)

    def tearDown(self):
        """Clean up after ourselves."""

        # delete the CSV import test data
        try:
            os.remove(os.path.join(import_test_working_dir, TestCsvImport.test_data_file))
        except (OSError, FileNotFoundError):
            pass

    def test_csv_init(self):
        """Test CsvSource object initialisation.

        Test that the CsvSource object was correctly initialise from our config
        dicts and command line options.
        """

        # get a CsvSource object
        csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                       self.config_path,
                                                       self.import_config_dict,
                                                       self.import_config_path,
                                                       self.options)

        # check the import_config_path property is correctly set
        self.assertEqual(csv_source_obj.import_config_path, self.import_config_path)
        # check the csv import config dict is correctly set
        self.assertEqual(csv_source_obj.csv_config_dict, self.import_config_dict)
        # check the delimiter property is correctly set
        self.assertEqual(csv_source_obj.delimiter, ',')
        # check the raw_datetime_format property is correctly set
        self.assertEqual(csv_source_obj.raw_datetime_format, '%Y-%m-%d %H:%M:%S')
        # check the rain property is correctly set
        self.assertEqual(csv_source_obj.rain, 'cumulative')
        # check the wind_dir property is correctly set
        self.assertEqual(csv_source_obj.wind_dir, [-360, 360])
        # check the source property is correctly set
        self.assertEqual(csv_source_obj.source, self.import_config_dict.get('file'))
        # check the source_encoding property is correctly set
        self.assertEqual(csv_source_obj.source_encoding, 'utf-8-sig')
        # check the map property is correctly set
        self.assertIsNone(csv_source_obj.map)
        # check the start property is correctly set
        self.assertEqual(csv_source_obj.start, 1)
        # check the end property is correctly set
        self.assertEqual(csv_source_obj.end, 1)
        # check the increment property is correctly set
        self.assertEqual(csv_source_obj.increment, 1)
        # check the verbose property is correctly set
        self.assertIsNone(csv_source_obj.verbose)

    def test_csv_defaults(self):
        """Test CsvSource object defaults.

        Test that class CsvSource defaults are correctly applied.
        """

        # get a CsvSource object based upon defaults only, first get a minimal
        # import config
        minimal_import_config = configobj.ConfigObj(StringIO(TestCsvImport.default_import_config))
        # now get a CsvSource object based on this minimal import config
        csv_source_obj_defaults = weeimport.csvimport.CSVSource(self.config_dict,
                                                                self.config_path,
                                                                minimal_import_config,
                                                                self.import_config_path,
                                                                self.options)
        # check the delimiter property is set to the default
        self.assertEqual(csv_source_obj_defaults.delimiter, ',')
        # check the raw_datetime_format property is set to the default
        self.assertEqual(csv_source_obj_defaults.raw_datetime_format, '%Y-%m-%d %H:%M:%S')
        # check the rain property is set to the default
        self.assertEqual(csv_source_obj_defaults.rain, 'cumulative')
        # check the wind_dir property is set to the default
        self.assertEqual(csv_source_obj_defaults.wind_dir, [0, 360])
        # check the source_encoding property is set to the default
        self.assertEqual(csv_source_obj_defaults.source_encoding, 'utf-8-sig')
        # check the interval property is set to the default
        self.assertEqual(csv_source_obj_defaults.interval, 'derive')
        # check the ignore_invalid_data property is set to the default
        self.assertEqual(csv_source_obj_defaults.ignore_invalid_data, True)
        # check the tranche property is set to the default
        self.assertEqual(csv_source_obj_defaults.tranche, 250)
        # check the apply_qc property is set to the default
        self.assertEqual(csv_source_obj_defaults.apply_qc, True)
        # check the calc_missing property is set to the default
        self.assertEqual(csv_source_obj_defaults.calc_missing, True)
        # check the decimal_sep property is set to the default
        self.assertEqual(csv_source_obj_defaults.decimal_sep, '.')
        # check the UV_sensor property is set to the default
        self.assertEqual(csv_source_obj_defaults.UV_sensor, True)
        # check the solar_sensor property is set to the default
        self.assertEqual(csv_source_obj_defaults.solar_sensor, True)

    def test_csv_other(self):
        """Test CsvSource object generators and property methods.

        Tests the following CsvSource object methods:

        period_generator(). Generator method yielding the import period number.
                            For a CSV import there is always only one import
                            period so the generator yields the integer 1 once.
        first_period. Boolean property that indicates if the current import
                      period is the first import period. A CSV import has only
                      one import period so the property is always True.
        last_period. Boolean property that indicates if the current import
                     period is the last import period. A CSV import has only
                     one import period so the property is always True.
        """

        # get a CsvSource object
        csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                       self.config_path,
                                                       self.import_config_dict,
                                                       self.import_config_path,
                                                       self.options)
        period_count = 0
        for period in csv_source_obj.period_generator():
            period_count += 1
            # test the generator yields the integer 1
            self.assertEqual(period, 1)
            # test the first_period property is True
            self.assertTrue(csv_source_obj.first_period)
            # test the first_period property is True
            self.assertTrue(csv_source_obj.last_period)
        # test the generator yielded one value only
        self.assertEqual(period_count, 1)


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
