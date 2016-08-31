#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Module to interract with a CSV file and import raw observational data for 
use with weeimport.
"""

# Python imports
import csv
import os
import syslog

# weewx imports
import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string, option_as_list


# ============================================================================
#                             class CSVSource
# ============================================================================


class CSVSource(weeimport.Source):
    """Class to interact with a CSV format text file.

    Handles the import of data from a CSV format data file with known field
    names.
    """

    # Define a dict to map CSV fields to weewx archive fields. For a CSV import
    # these details are specified by the user in the wee_import config file.
    _header_map = None

    def __init__(self, config_dict, config_path, csv_config_dict, import_config_path, options, log):

        # call our parents __init__
        super(CSVSource, self).__init__(config_dict,
                                        csv_config_dict,
                                        options,
                                        log)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.csv_config_dict = csv_config_dict

        # get a few config settings from our CSV config dict
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
        except:
            self.wind_dir = [-360, 360]
        # get our source file path
        try:
            self.source = csv_config_dict['file']
        except KeyError:
            raise weewx.ViolatedPrecondition("CSV source file not specified in '%s'." % import_config_path)
        # initialise our import field-to-weewx archive field map
        self.map = None
        # initialise some other properties we will need
        self.start = 1
        self.end = 1
        self.increment = 1

        # tell the user/log what we intend to do
        _msg = "A CSV import from source file '%s' has been requested." % self.source
        self.wlog.printlog(logging.INFO, _msg)
        _msg = "The following options will be used:"
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     config=%s, import-config=%s" % (config_path,
                                                     self.import_config_path)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     source=%s, date=%s" % (self.source, options.date)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     dry-run=%s, calc-missing=%s" % (self.dry_run,
                                                     self.calc_missing)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     tranche=%s, interval=%s, date/time_string_format=%s" % (self.tranche,
                                                                             self.interval,
                                                                             self.raw_datetime_format)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     rain=%s, wind_direction=%s" % (self.rain, self.wind_dir)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "     UV=%s, radiation=%s" % (self.UV_sensor, self.solar_sensor)
        self.wlog.verboselog(logging.DEBUG, _msg, self.verbose)
        _msg = "Using database binding '%s', which is bound to database '%s'" % (self.db_binding_wx,
                                                                                 self.dbm.database_name)
        self.wlog.printlog(logging.INFO, _msg)
        if self.dry_run:
            print "This is a dry run, imported data WILL NOT be saved to archive."
        else:
            print "This is NOT a dry run, imported data WILL be saved to archive."
        if self.calc_missing:
            print "Any missing derived observations WILL be calculated."
        else:
            print "Any missing derived observations WILL NOT be calculated."
        if self.UV_sensor:
            print "All weewx UV fields will be set to None."
        else:
            print "weewx UV field will use CSV UV index field value (if it exists)."
        if self.solar_sensor:
            print "All weewx radiation fields will be set to None."
        else:
            print "weewx radiation field will use CSV solar radiation field value (if it exists)."
        if options.date:
            print "Observations timestamped after %s and up to and" % (timestamp_to_string(self.first_ts), )
            print "including %s will be imported." % (timestamp_to_string(self.last_ts), )

    def getRawData(self, period):
        """Obtain an iterable containing the raw data to be imported.

        Raw data is read and any clean-up/pre-processing carried out before the
        iterable is returned. In this case we will use csv.Dictreader(). The
        iterable should be of a form where the field names in the field map can
        be used to map the data to the weewx archive record format.

        Input parameters:

            period: a simple counter that is unused but retained to keep the
                    getRawData() signature the same across all classes.
        """

        # does our source exist?
        if os.path.isfile(self.source):
            with open(self.source, 'r') as f:
                _raw_data = f.readlines()
        else:
            # if it doesn't we can't go on so raise it
            raise weeimport.WeeImportIOError(
                "CSV source file '%s' could not be found." % self.source)

        # just in case the data has been sourced from the web we will remove
        # any HTML tags and blank lines that may exist
        _clean_data = []
        for _row in _raw_data:
            # get rid of any HTML tags
            _line = ''.join(CSVSource._tags.split(_row))
            if _line != "\n":
                # save anything that is not a blank line
                _clean_data.append(_line)

        # create a dictionary CSV reader, using the first line as the set of keys
        _csv_reader = csv.DictReader(_clean_data)

        # finally, get our source-to-database mapping
        self.map = self.parseMap('CSV', _csv_reader, self.csv_config_dict)

        # return our CSV dict reader
        return _csv_reader

    def period_generator(self):
        """Generator function to control import processing in run() for CSV
            imports.

        Since CSV imports import from a single file this generator need only
        return a single value before it is exhausted.
        """

        yield 1
