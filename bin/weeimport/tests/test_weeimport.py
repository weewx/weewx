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

import six
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


class Options(object):
    """Class to represent wee_import command line options.

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


class TestWeeImport(unittest.TestCase):
    """Test elements of class Source and weeimport utilities.

    weeimport.py provides the base class for source specific classes used to
    import data. Much of the base class functionality can be tested with a base
    class object rather than a source specific object. Utility methods in the
    weeimport.py module are also tested in this test case.
    """

    def setUp(self):
        """Setup the environment for our tests.

        A Source object is required to allow the test to be run. To instantiate
        a Source object we require a WeeWX config dict as well as an import
        source config file. The import source type is not important, in this
        case we will use a CSV source.
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
        self.options = Options()

    def tearDown(self):
        """Clean up after ourselves."""

        pass

    def test_date_options(self):
        """Test processing of date related command line options.

        Test processing of --date, --date-from and --date-to command line
        options. These options are used to determine the first_ts and last_ts
        properties of the source object.
        """

        # tests that check first_ts and last_ts values
        test_data = [
            # neither --date, --date-from nor --date-to were specified; we
            # should see first_ts and last_ts == None
            {'options': {'date': None, 'date_from': None, 'date_to': None},
             'result': {'first_ts': None, 'last_ts': None}},
            # only --date is specified using a valid format (YYYY-MM-DD); we
            # should see valid timestamps
            {'options': {'date': '2022-07-25', 'date_from': None, 'date_to': None},
             'result': {'first_ts': 1658732400, 'last_ts': 1658818800}},
            # a valid format (YYYY-mm-dd) for --date-from and --date-to, --date
            # not specified; we should see valid timestamps
            {'options': {'date': None, 'date_from': '2022-07-21', 'date_to': '2022-08-24'},
             'result': {'first_ts': 1658386800, 'last_ts': 1661410800}},
            # a valid long format (YYYY-mm-ddTHH:MM) for --date-from and
            # --date-to, --date not specified; we should see valid timestamps
            {'options': {'date': None, 'date_from': '2022-07-21T11:00', 'date_to': '2022-08-24T21:55'},
             'result': {'first_ts': 1658426400, 'last_ts': 1661403300}},
            # A valid date format (YYYY-mm-dd) for --date, --date-from and
            # --date-to; we should see --date used to produce first_ts and
            # last_ts as valid timestamps. --date-from and --date-to are
            # ignored.
            {'options': {'date': '2022-07-25', 'date_from': '2022-07-21', 'date_to': '2022-08-24'},
             'result': {'first_ts': 1658732400, 'last_ts': 1658818800}}
        ]
        # tests that raise exceptions
        exception_test_data = [
            # an invalid --date in a valid format (YYYY-mm-dd); we should see a
            # WeeImportOptionError exception
            {'options': {'date': '2022-07-32', 'date_from': None, 'date_to': None},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date in an incorrect format (YYYY-mm-ddTHH:MM); we
            # should see a WeeImportOptionError exception
            {'options': {'date': '2022-07-25T12:55', 'date_from': None, 'date_to': None},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date in an invalid format; we should see a
            # WeeImportOptionError exception
            {'options': {'date': 'some_date', 'date_from': None, 'date_to': None},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date-from in a valid format, --date-to can be
            # anything, no --date; we should see a WeeImportOptionError
            # exception
            {'options': {'date': None, 'date_from': '2022-07-32', 'date_to': None},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date-to in a valid format, valid --date-from, no
            # --date; we should see a WeeImportOptionError exception
            {'options': {'date': None, 'date_from': '2022-07-31', 'date_to': '2022-09-31'},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date-from in an invalid format, --date-to can be
            # anything, no --date; we should see a WeeImportOptionError
            # exception
            {'options': {'date': None, 'date_from': 'some_data', 'date_to': None},
             'result': weeimport.weeimport.WeeImportOptionError},
            # an invalid --date-to in an invalid format, valid --date-from, no
            # --date; we should see a WeeImportOptionError exception
            {'options': {'date': None, 'date_from': '2022-07-31', 'date_to': 'some_date'},
             'result': weeimport.weeimport.WeeImportOptionError},
            # --date-from is not a string or None, --date-to can be anything,
            # no --date; we should see a WeeImportOptionError exception
            {'options': {'date': None, 'date_from': 25, 'date_to': '2022-07-23'},
             'result': weeimport.weeimport.WeeImportOptionError},
            # a valid --date-from, --date-to is not a string or None, no
            # --date; we should see a WeeImportOptionError exception
            {'options': {'date': None, 'date_from': '2022-07-25T12:55', 'date_to': 25},
             'result': weeimport.weeimport.WeeImportOptionError},
            # valid --date-from and --date-to but --date-to is earlier than
            # --date-from, no --date; we should see a WeeImportOptionError
            # exception
            {'options': {'date': None, 'date_from': '2022-07-31', 'date_to': '2022-04-16'},
             'result': weeimport.weeimport.WeeImportOptionError}
        ]

        # we will be doing some date-time epoch conversions so put our system
        # timezone into a known state
        os.environ['TZ'] = 'America/Los_Angeles'
        time.tzset()

        # run the tests that check values
        for params in test_data:
            # set the required command line options
            for option, value in six.iteritems(params['options']):
                setattr(self.options, option, value)
            # get a CsvSource object
            csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                           self.config_path,
                                                           self.import_config_dict,
                                                           self.import_config_path,
                                                           self.options)
            # check the resulting values
            for prop, value in six.iteritems(params['result']):
                # which assert function we use depends on the expected result
                if value is None:
                    self.assertIsNone(getattr(csv_source_obj, prop))
                else:
                    self.assertEqual(getattr(csv_source_obj, prop), value)
        # run the tests that check for exceptions, these tests require a
        # slightly different setup and call
        for params in exception_test_data:
            # set the required command line options
            for option, value in six.iteritems(params['options']):
                setattr(self.options, option, value)
            # obtain a tuple of the arguments to be passed to CsvSource
            args = (self.config_dict, self.config_path, self.import_config_dict,
                    self.import_config_path, self.options)
            # run the test
            self.assertRaises(params['result'],
                              weeimport.csvimport.CSVSource,
                              *args)


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
    test_data_list = [{'Time': '28/11/2017 08:00:00', 'Barometer': '1016.9', 'Temp': '24.6',
                       'Humidity': '84', 'Windspeed': '1.8', 'Dir': '113', 'Gust': '8',
                       'Dayrain': '0', 'Radiation': '359', 'Uv': '3.8',
                       'Comment': 'start of observations'},
                      {'Time': '28/11/2017 08:05:00', 'Barometer': '1016.9', 'Temp': '25.1',
                       'Humidity': '82', 'Windspeed': '4.8', 'Dir': '135', 'Gust': '11.3',
                       'Dayrain': '0', 'Radiation': '775', 'Uv': '4.7', 'Comment': ''},
                      {'Time': '28/11/2017 08:10:00', 'Barometer': '1016.9', 'Temp': '25.4',
                       'Humidity': '80', 'Windspeed': '4.4', 'Dir': '127', 'Gust': '11.3',
                       'Dayrain': '0', 'Radiation': '787', 'Uv': '5.1',
                       'Comment': 'note temperature'},
                      {'Time': '28/11/2017 08:15:00', 'Barometer': '1017', 'Temp': '25.7',
                       'Humidity': '79', 'Windspeed': '3.5', 'Dir': '74', 'Gust': '11.3',
                       'Dayrain': '0', 'Radiation': '800', 'Uv': '5.4', 'Comment': ''},
                      {'Time': '28/11/2017 08:20:00', 'Barometer': '1016.9', 'Temp': '25.9',
                       'Humidity': '79', 'Windspeed': '1.6', 'Dir': '95', 'Gust': '9.7',
                       'Dayrain': '0', 'Radiation': '774', 'Uv': '5.5', 'Comment': ''},
                      {'Time': '28/11/2017 08:25:00', 'Barometer': '1017', 'Temp': '25.5',
                       'Humidity': '78', 'Windspeed': '2.9', 'Dir': '48', 'Gust': '9.7',
                       'Dayrain': '0', 'Radiation': '303', 'Uv': '3.4',
                       'Comment': 'forecast received'},
                      {'Time': '28/11/2017 08:30:00', 'Barometer': '1017.1', 'Temp': '25.1',
                       'Humidity': '80', 'Windspeed': '3.1', 'Dir': '54', 'Gust': '9.7',
                       'Dayrain': '0', 'Radiation': '190', 'Uv': '3.6', 'Comment': ''}
                      ]
    # expected source-to-database map
    map = {'dateTime': {'field_name': 'timestamp', 'units': 'unix_epoch'},
           'usUnits': {'units': None}, 'interval': {'units': 'minute'},
           'barometer': {'field_name': 'barometer', 'units': 'inHg'},
           'outTemp': {'field_name': 'Temp', 'units': 'degree_F'},
           'outHumidity': {'field_name': 'humidity', 'units': 'percent'},
           'windSpeed': {'field_name': 'windspeed', 'units': 'mile_per_hour'},
           'windDir': {'field_name': 'wind', 'units': 'degree_compass'},
           'windGust': {'field_name': 'gust', 'units': 'mile_per_hour'},
           'windGustDir': {'field_name': 'gustDir', 'units': 'degree_compass'},
           'rainRate': {'field_name': 'rate', 'units': 'inch_per_hour'},
           'rain': {'field_name': 'dayrain', 'units': 'inch'}
           }
    # minimal import config to test application of defaults
    default_import_config = """
    file = %s/%s
    [FieldMap]
        dateTime    = timestamp, unix_epoch
        interval    =
        barometer   = barometer, inHg""" % (import_test_working_dir, test_data_file)

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
        # first make sure our path exists
        try:
            os.makedirs(import_test_working_dir)
        except OSError:
            pass
        # now populate the file
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

        Test that the CsvSource object was correctly initialised from our
        config dicts and command line options.

        These tests verify correct object initialisation in class CsvSource.
        test_init() verifies correct object initialisation in the parent class
        (class Source).
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
        # check the _header_map property is None
        self.assertIsNone(csv_source_obj._header_map)

    def test_init(self):
        """Test parent initialisation of CsvSource objects.

        Tests the correct initialisation of CsvSource objects that occurs in
        the parent class Source based on config dicts and command line options.

        These tests verify correct object initialisation in class Source.
        test_csv_init() verifies correct object initialisation in the child
        class (class CsvSource).
        """

        # get a CsvSource object
        csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                       self.config_path,
                                                       self.import_config_dict,
                                                       self.import_config_path,
                                                       self.options)

        # check the config dict is correctly set
        self.assertEqual(csv_source_obj.config_dict, self.config_dict)
        # check the interval property is correctly set
        self.assertEqual(csv_source_obj.interval,
                         self.import_config_dict.get('interval', 'derive'))
        # check the ignore_invalid_data property is correctly set
        self.assertEqual(csv_source_obj.ignore_invalid_data,
                         weeutil.weeutil.tobool(self.import_config_dict.get('ignore_invalid_data',
                                                                            'True')))
        # check the tranche property is correctly set
        self.assertEqual(csv_source_obj.tranche,
                         int(self.import_config_dict.get('tranche', '250')))
        # check the apply_qc property is correctly set
        self.assertEqual(csv_source_obj.apply_qc,
                         weeutil.weeutil.tobool(self.import_config_dict.get('qc', 'True')))
        # check the calc_missing property is correctly set
        self.assertEqual(csv_source_obj.calc_missing,
                         weeutil.weeutil.tobool(self.import_config_dict.get('calc_missing',
                                                                            'True')))
        # check the decimal_sep property is correctly set
        self.assertEqual(csv_source_obj.decimal_sep,
                         self.import_config_dict.get('decimal', '.'))
        # check the UV_sensor property is correctly set
        self.assertEqual(csv_source_obj.UV_sensor,
                         weeutil.weeutil.tobool(self.import_config_dict.get('UV_sensor', 'True')))
        # check the solar_sensor property is correctly set
        self.assertEqual(csv_source_obj.solar_sensor,
                         weeutil.weeutil.tobool(self.import_config_dict.get('solar_sensor',
                                                                            'True')))
        # check the dry_run property is correctly set
        self.assertIsNone(csv_source_obj.dry_run)
        # check the verbose property is correctly set
        self.assertIsNone(csv_source_obj.verbose)
        # check the no_prompt property is correctly set
        self.assertIsNone(csv_source_obj.no_prompt)
        # check the suppress property is correctly set
        self.assertIsNone(csv_source_obj.suppress)
        # check the ans property is correctly set
        self.assertIsNone(csv_source_obj.ans)
        # check the interval_ans property is correctly set
        self.assertIsNone(csv_source_obj.interval_ans)
        # check the period_no property is correctly set
        self.assertIsNone(csv_source_obj.period_no)
        # check the total_rec_proc property is correctly set
        self.assertEqual(csv_source_obj.total_rec_proc, 0)
        # check the total_unique_rec property is correctly set
        self.assertEqual(csv_source_obj.total_unique_rec, 0)
        # check the total_duplicate_rec property is correctly set
        self.assertEqual(csv_source_obj.total_duplicate_rec, 0)
        # check the t1 property is correctly set
        self.assertIsNone(csv_source_obj.t1)
        # check the tdiff property is correctly set
        self.assertIsNone(csv_source_obj.tdiff)
        # check the earliest_ts property is correctly set
        self.assertIsNone(csv_source_obj.earliest_ts)
        # check the latest_ts property is correctly set
        self.assertIsNone(csv_source_obj.latest_ts)
        # check the duplicates property is correctly set
        self.assertEqual(csv_source_obj.duplicates, set())
        # check the period_duplicates property is correctly set
        self.assertEqual(csv_source_obj.period_duplicates, set())

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

    def test_getRawData(self):
        """Test the CsvSource getRawData() method.

        The getRawData() method returns a csv DictReader object containing the
        imported data. This DictReader object is an iterator that yields
        individual rows of data as a dict. The getRawData() method can also
        raise various exceptions.
        """

        # get a CsvSource object
        csv_source_obj = weeimport.csvimport.CSVSource(self.config_dict,
                                                       self.config_path,
                                                       self.import_config_dict,
                                                       self.import_config_path,
                                                       self.options)
        # initialise a counter to count the number of 'rows' returned
        row_count = 0
        # iterate over the 'rows' in the DictReader
        for row in csv_source_obj.getRawData(period=1):
            # check the row data returned by the DictReader matches the source
            # data, there is no unit conversion involved in this process only
            # parsing and formatting source data
            self.assertDictEqual(row, TestCsvImport.test_data_list[row_count])
            # increment the row counter
            row_count += 1
        # check the correct number of rows were returned
        self.assertEqual(row_count, len(TestCsvImport.test_data_list))
        # check the source-to-database map was correctly generated
        self.assertDictEqual(csv_source_obj.map, TestCsvImport.map)

        # check exceptions we should see from getRawData()

        # a non-existent source file
        # first save the source property so we can restore it when we have
        # finished this test
        _source = csv_source_obj.source
        # set the source property to a non-existent path/file
        csv_source_obj.source = "/var/tmp/zzunknown.zzz"
        # check that a WeeImportIOError is raised
        self.assertRaises(weeimport.weeimport.WeeImportIOError,
                          csv_source_obj.getRawData, period=1)
        # restore the source property
        csv_source_obj.source = _source

        # an invalid source encoding
        # first save the source_encoding property so we can restore it when we
        # have finished this test
        _encoding = csv_source_obj.source_encoding
        # set the source_encoding property to an unknown source encoding
        csv_source_obj.source_encoding = "unknown"
        # check that a LookupError is raised
        self.assertRaises(LookupError, csv_source_obj.getRawData, period=1)

        # an incorrect source encoding
        # set the source_encoding property to a valid but incorrect source
        # encoding
        csv_source_obj.source_encoding = "utf-32"
        # check that a WeeImportDecodeError is raised
        self.assertRaises(weeimport.weeimport.WeeImportDecodeError,
                          csv_source_obj.getRawData,
                          period=1)
        # restore the source_encoding property
        csv_source_obj.source_encoding = _encoding

        # missing field map
        # first save the FieldMap stanza so we can restore it when we have
        # finished this test
        _field_map = csv_source_obj.csv_config_dict.pop('FieldMap')
        # check that a WeeImportMapError exception is raised
        self.assertRaises(weeimport.weeimport.WeeImportMapError,
                          csv_source_obj.getRawData,
                          period=1)
        # now restore the FieldMap stanza
        csv_source_obj.csv_config_dict['FieldMap'] = _field_map

    def test_csv_other(self):
        """Test generator and property methods of the CsvSource object.

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
            self.assertEqual(csv_source_obj.first_period, True)
            # test the first_period property is True
            self.assertEqual(csv_source_obj.last_period, True)
        # test the generator yielded one value only
        self.assertEqual(period_count, 1)


def suite():
    """Create a TestSuite object containing the tests to be performed."""

    # the list of test cases to be performed
    tests = [TestCsvImport, TestWeeImport]
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
