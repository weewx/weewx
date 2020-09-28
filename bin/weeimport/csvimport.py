#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

"""Module to interact with a CSV file and import raw observational data for
use with wee_import.
"""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

# Python imports
import csv
import io
import logging
import os


# WeeWX imports
from . import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string, option_as_list
from weewx.units import unit_nicknames

log = logging.getLogger(__name__)


# ============================================================================
#                             class CSVSource
# ============================================================================


class CSVSource(weeimport.Source):
    """Class to interact with a CSV format text file.

    Handles the import of data from a CSV format data file with known field
    names.
    """

    # Define a dict to map CSV fields to WeeWX archive fields. For a CSV import
    # these details are specified by the user in the wee_import config file.
    _header_map = None
    # define a dict to map cardinal, intercardinal and secondary intercardinal
    # directions to degrees
    wind_dir_map = {'N': 0.0, 'NNE': 22.5, 'NE': 45.0, 'ENE': 67.5,
                    'E': 90.0, 'ESE': 112.5, 'SE': 135.0, 'SSE': 157.5,
                    'S': 180.0, 'SSW': 202.5, 'SW': 225.0, 'WSW': 247.5,
                    'W': 270.0, 'WNW': 292.5, 'NW': 315.0, 'NNW': 337.5,
                    'NORTH': 0.0, 'NORTHNORTHEAST': 22.5,
                    'NORTHEAST': 45.0, 'EASTNORTHEAST': 67.5,
                    'EAST': 90.0, 'EASTSOUTHEAST': 112.5,
                    'SOUTHEAST': 135.0, 'SOUTHSOUTHEAST': 157.5,
                    'SOUTH': 180.0, 'SOUTHSOUTHWEST': 202.5,
                    'SOUTHWEST': 225.0, 'WESTSOUTHWEST': 247.5,
                    'WEST': 270.0, 'WESTNORTHWEST': 292.5,
                    'NORTHWEST': 315.0, 'NORTHNORTHWEST': 337.5
                    }

    def __init__(self, config_dict, config_path, csv_config_dict, import_config_path, options):

        # call our parents __init__
        super(CSVSource, self).__init__(config_dict,
                                        csv_config_dict,
                                        options)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.csv_config_dict = csv_config_dict

        # get a few config settings from our CSV config dict
        # csv field delimiter
        self.delimiter = str(self.csv_config_dict.get('delimiter', ','))
        # string format used to decode the imported field holding our dateTime
        self.raw_datetime_format = self.csv_config_dict.get('raw_datetime_format',
                                                            '%Y-%m-%d %H:%M:%S')
        # is our rain discrete or cumulative
        self.rain = self.csv_config_dict.get('rain', 'cumulative')
        # determine valid range for imported wind direction
        _wind_direction = option_as_list(self.csv_config_dict.get('wind_direction',
                                                                  '0,360'))
        try:
            if float(_wind_direction[0]) <= float(_wind_direction[1]):
                self.wind_dir = [float(_wind_direction[0]),
                                 float(_wind_direction[1])]
            else:
                self.wind_dir = [-360, 360]
        except (KeyError, ValueError):
            self.wind_dir = [-360, 360]
        # get our source file path
        try:
            self.source = csv_config_dict['file']
        except KeyError:
            raise weewx.ViolatedPrecondition("CSV source file not specified "
                                             "in '%s'." % import_config_path)
        # get the source file encoding, default to utf-8-sig
        self.source_encoding = self.csv_config_dict.get('source_encoding',
                                                        'utf-8-sig')
        # initialise our import field-to-WeeWX archive field map
        self.map = None
        # initialise some other properties we will need
        self.start = 1
        self.end = 1
        self.increment = 1

        # tell the user/log what we intend to do
        _msg = "A CSV import from source file '%s' has been requested." % self.source
        print(_msg)
        log.info(_msg)
        _msg = "The following options will be used:"
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     config=%s, import-config=%s" % (config_path,
                                                     self.import_config_path)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        if options.date:
            _msg = "     source=%s, date=%s" % (self.source, options.date)
        else:
            # we must have --from and --to
            _msg = "     source=%s, from=%s, to=%s" % (self.source,
                                                       options.date_from,
                                                       options.date_to)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     dry-run=%s, calc_missing=%s, " \
               "ignore_invalid_data=%s" % (self.dry_run,
                                           self.calc_missing,
                                           self.ignore_invalid_data)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     tranche=%s, interval=%s, " \
               "date/time_string_format=%s" % (self.tranche,
                                               self.interval,
                                               self.raw_datetime_format)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     delimiter='%s', rain=%s, wind_direction=%s" % (self.delimiter,
                                                                    self.rain,
                                                                    self.wind_dir)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     UV=%s, radiation=%s" % (self.UV_sensor, self.solar_sensor)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "Using database binding '%s', which is bound to " \
               "database '%s'" % (self.db_binding_wx,
                                  self.dbm.database_name)
        print(_msg)
        log.info(_msg)
        _msg = "Destination table '%s' unit system " \
               "is '%#04x' (%s)." % (self.dbm.table_name,
                                     self.archive_unit_sys,
                                     unit_nicknames[self.archive_unit_sys])
        print(_msg)
        log.info(_msg)
        if self.calc_missing:
            _msg = "Missing derived observations will be calculated."
            print(_msg)
            log.info(_msg)

        if not self.UV_sensor:
            _msg = "All WeeWX UV fields will be set to None."
            print(_msg)
            log.info(_msg)
        if not self.solar_sensor:
            _msg = "All WeeWX radiation fields will be set to None."
            print(_msg)
            log.info(_msg)
        if options.date or options.date_from:
            _msg = "Observations timestamped after %s and " \
                   "up to and" % timestamp_to_string(self.first_ts)
            print(_msg)
            log.info(_msg)
            _msg = "including %s will be imported." % timestamp_to_string(self.last_ts)
            print(_msg)
            log.info(_msg)
        if self.dry_run:
            _msg = "This is a dry run, imported data will not be saved to archive."
            print(_msg)
            log.info(_msg)

    def getRawData(self, period):
        """Obtain an iterable containing the raw data to be imported.

        Raw data is read and any clean-up/pre-processing carried out before the
        iterable is returned. In this case we will use csv.Dictreader(). The
        iterable should be of a form where the field names in the field map can
        be used to map the data to the WeeWX archive record format.

        Input parameters:

            period: a simple counter that is unused but retained to keep the
                    getRawData() signature the same across all classes.
        """

        # does our source exist?
        if os.path.isfile(self.source):
            # It exists.  The source file may use some encoding, if we can't
            # decode it raise a WeeImportDecodeError.
            try:
                with io.open(self.source, mode='r', encoding=self.source_encoding) as f:
                    _raw_data = f.readlines()
            except UnicodeDecodeError as e:
                # not a utf-8 based encoding, so raise a WeeImportDecodeError
                raise weeimport.WeeImportDecodeError(e)
        else:
            # if it doesn't we can't go on so raise it
            raise weeimport.WeeImportIOError(
                "CSV source file '%s' could not be found." % self.source)

        # just in case the data has been sourced from the web we will remove
        # any HTML tags and blank lines that may exist
        _clean_data = []
        for _row in _raw_data:
            # check for and remove any null bytes
            clean_row = _row
            if "\x00" in _row:
                clean_row = clean_row.replace("\x00", "")
                _msg = "One or more null bytes found in and removed " \
                       "from file '%s'" % self.source
                print(_msg)
                log.info(_msg)
            # get rid of any HTML tags
            _line = ''.join(CSVSource._tags.split(clean_row))
            if _line != "\n":
                # save anything that is not a blank line
                _clean_data.append(_line)

        # create a dictionary CSV reader, using the first line as the set of keys
        _csv_reader = csv.DictReader(_clean_data, delimiter=self.delimiter)

        # finally, get our source-to-database mapping
        self.map = self.parseMap('CSV', _csv_reader, self.csv_config_dict)

        # return our CSV dict reader
        return _csv_reader

    @staticmethod
    def period_generator():
        """Generator function to control CSV import processing loop.

        Since CSV imports import from a single file this generator need only
        return a single value before it is exhausted.
        """

        yield 1

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

        For CSV imports there is only one period so it is always the first.
        """

        return True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

        For CSV imports there is only one period so it is always the last.
        """

        return True
