#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module for use with wee_import to import observational data from WeatherCat
monthly .cat files.
"""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

# Python imports
import glob
import logging
import os
import shlex
import time

# python 2/3 compatibility shims
import six

# WeeWX imports
from . import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string
from weewx.units import unit_nicknames

log = logging.getLogger(__name__)


# ============================================================================
#                             class WeatherCatSource
# ============================================================================


class WeatherCatSource(weeimport.Source):
    """Class to interact with a WeatherCat monthly .cat files.

    Handles the import of data from Cumulus monthly log files.Cumulus stores
    observation data in monthly log files. Each log file contains a month of
    data in CSV format. The format of the CSV data (eg date separator, field
    delimiter, decimal point character) depends upon the settings used in
    Cumulus.

    Data is imported from all month log files found in the source directory one
    log file at a time. Units of measure are not specified in the monthly log
    files so the units of measure must be specified in the wee_import config
    file. Whilst the Cumulus monthly log file format is well defined, some
    pre-processing of the data is required to provide data in a format the
    suitable for use in the wee_import mapping methods.
    """

    # dict to map all possible WeatherCat .cat file field names to WeeWX
    # archive field names and units
    default_header_map = {'dateTime': {'field_name': 'dateTime',
                                       'units': 'unix_epoch'},
                          'usUnits': {'units': None},
                          'interval': {'units': 'minute'},
                          'outTemp': {'field_name': 'T',
                                      'units': 'degree_C'},
                          'inTemp': {'field_name': 'Ti',
                                     'units': 'degree_C'},
                          'extraTemp1': {'field_name': 'T1',
                                         'units': 'degree_C'},
                          'extraTemp2': {'field_name': 'T2',
                                         'units': 'degree_C'},
                          'extraTemp3': {'field_name': 'T3',
                                         'units': 'degree_C'},
                          'dewpoint': {'field_name': 'D',
                                       'units': 'degree_C'},
                          'barometer': {'field_name': 'Pr',
                                        'units': 'mbar'},
                          'windSpeed': {'field_name': 'W',
                                        'units': 'km_per_hour'},
                          'windDir': {'field_name': 'Wd',
                                      'units': 'degree_compass'},
                          'windchill': {'field_name': 'Wc',
                                        'units': 'degree_C'},
                          'windGust': {'field_name': 'Wg',
                                       'units': 'km_per_hour'},
                          'rainRate': {'field_name': 'Ph',
                                       'units': 'mm_per_hour'},
                          'rain': {'field_name': 'P',
                                   'units': 'mm'},
                          'outHumidity': {'field_name': 'H',
                                          'units': 'percent'},
                          'inHumidity': {'field_name': 'Hi',
                                         'units': 'percent'},
                          'extraHumid1': {'field_name': 'H1',
                                          'units': 'percent'},
                          'extraHumid2': {'field_name': 'H2',
                                          'units': 'percent'},
                          'radiation': {'field_name': 'S',
                                        'units': 'watt_per_meter_squared'},
                          'soilMoist1': {'field_name': 'Sm1',
                                         'units': 'centibar'},
                          'soilMoist2': {'field_name': 'Sm2',
                                         'units': 'centibar'},
                          'soilMoist3': {'field_name': 'Sm3',
                                         'units': 'centibar'},
                          'soilMoist4': {'field_name': 'Sm4',
                                         'units': 'centibar'},
                          'leafWet1': {'field_name': 'Lw1',
                                       'units': 'count'},
                          'leafWet2': {'field_name': 'Lw2',
                                       'units': 'count'},
                          'soilTemp1': {'field_name': 'St1',
                                        'units': 'degree_C'},
                          'soilTemp2': {'field_name': 'St2',
                                        'units': 'degree_C'},
                          'soilTemp3': {'field_name': 'St3',
                                        'units': 'degree_C'},
                          'soilTemp4': {'field_name': 'St4',
                                        'units': 'degree_C'},
                          'leafTemp1': {'field_name': 'Lt1',
                                        'units': 'degree_C'},
                          'leafTemp2': {'field_name': 'Lt2',
                                        'units': 'degree_C'},
                          'UV': {'field_name': 'U',
                                 'units': 'uv_index'}
                          }

    weathercat_unit_groups = {'temperature': ('outTemp', 'inTemp',
                                              'extraTemp1', 'extraTemp2',
                                              'extraTemp3', 'windchill',
                                              'soilTemp1', 'soilTemp2',
                                              'soilTemp3', 'soilTemp4',
                                              'leafTemp1', 'leafTemp2'),
                              'dewpoint': ('dewpoint',),
                              'pressure': ('barometer',),
                              'windspeed': ('windSpeed', 'windGust'),
                              'precipitation': ('rain',)
                              }

    def __init__(self, config_dict, config_path, weathercat_config_dict, import_config_path,
                 options):

        # call our parents __init__
        super(WeatherCatSource, self).__init__(config_dict,
                                               weathercat_config_dict,
                                               options)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.weathercat_config_dict = weathercat_config_dict

        # wind dir bounds
        self.wind_dir = [0, 360]

        # decimal separator used in monthly log files, default to decimal point
        self.decimal = weathercat_config_dict.get('decimal', '.')

        # Cumulus log files provide a number of cumulative rainfall fields. We
        # cannot use the daily rainfall as this may reset at some time of day
        # other than midnight (as required by WeeWX). So we use field 26, total
        # rainfall since midnight and treat it as a cumulative value.
        self.rain = 'cumulative'

        # The WeatherCat .cat file structure is well defined so we can
        # construct our import field-to-WeeWX archive field map now. The user
        # can specify the units used in the WeatherCat .cat file so first
        # construct a default field map then go through and adjust the units
        # where necessary.
        # first initialise with a default field map
        self.map = self.default_header_map
        # now check the [[Units]] stanza in the import config file and adjust
        # any units as required
        if 'Units' in weathercat_config_dict and len(weathercat_config_dict['Units']) > 0:
            # we have [[Units]] settings so iterate over each
            for group, value in six.iteritems(weathercat_config_dict['Units']):
                # is this group (eg 'temperature', 'rain' etc one that we know
                # about
                if group in self.weathercat_unit_groups:
                    # it is, so iterate over each import field that could be affected by
                    # this unit setting
                    for field in self.weathercat_unit_groups[group]:
                        # set the units field accordingly
                        self.map[field]['units'] = value
                    # We have one special 'derived' unit setting, rainRate. The
                    # rainRate units are derived from the rain units by simply
                    # appending '_per_hour'
                    if group == 'precipitation':
                        self.map['rainRate']['units'] = ''.join([value, '_per_hour'])

        # property holding the current log file name being processed
        self.file_name = None

        # get our source file path
        try:
            self.source = weathercat_config_dict['directory']
        except KeyError:
            raise weewx.ViolatedPrecondition(
                "WeatherCat directory not specified in '%s'." % import_config_path)

        # Get a list of monthly .cat files sorted from oldest to newest.
        # Remember the .cat files are in 'year' folders.
        # first get a list of all the 'year' folders including path
        _y_list = [os.path.join(self.source, d) for d in os.listdir(self.source)
                   if os.path.isdir(os.path.join(self.source, d))]
        # initialise our list of .cat files
        f_list = []
        # iterate over the 'year' directories
        for _dir in _y_list:
            # find any .cat files in the 'year' directory and add them to the
            # file list
            f_list += glob.glob(''.join([_dir, '/*[0-9]_WeatherCatData.cat']))
        # now get an intermediate list that we can use to sort the .cat file
        # list from oldest to newest
        _temp = [(fn,
                  os.path.basename(os.path.dirname(fn)),
                  os.path.basename(fn).split('_')[0].zfill(2)) for fn in f_list]
        # now do the sorting
        self.cat_list = [a[0] for a in sorted(_temp,
                                              key=lambda el: (el[1], el[2]))]

        if len(self.cat_list) == 0:
            raise weeimport.WeeImportIOError(
                "No WeatherCat monthly .cat files found in directory '%s'." % self.source)

        # tell the user/log what we intend to do
        _msg = "WeatherCat monthly .cat files in the '%s' directory " \
               "will be imported" % self.source
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
            _msg = "     date=%s" % options.date
        else:
            # we must have --from and --to
            _msg = "     from=%s, to=%s" % (options.date_from, options.date_to)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     dry-run=%s, calc-missing=%s" % (self.dry_run,
                                                     self.calc_missing)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     tranche=%s, interval=%s" % (self.tranche,
                                                 self.interval)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     UV=%s, radiation=%s" % (self.UV_sensor, self.solar_sensor)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "Using database binding '%s', which is " \
               "bound to database '%s'" % (self.db_binding_wx,
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
            print("Missing derived observations will be calculated.")
        if not self.UV_sensor:
            print("All WeeWX UV fields will be set to None.")
        if not self.solar_sensor:
            print("All WeeWX radiation fields will be set to None.")
        if options.date or options.date_from:
            print("Observations timestamped after %s and "
                  "up to and" % (timestamp_to_string(self.first_ts),))
            print("including %s will be imported." % (timestamp_to_string(self.last_ts),))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def getRawData(self, period):
        """Get .cat file raw data and create .cat to WeeWX archive field map.

        Create a .raw field to WeeWX archive field map and instantiate a
        generator to yield one row of raw observation data at a time from the
        .cat file.

        Field names and units are fixed for a WeatherCat monthly .cat file so
        we can use a fixed field map.

        Calculating a date-time for each row requires obtaining the year from
        the .cat file directory, month from the .cat file name and day, hour
        and minute from the individual rows in the .cat file. This calculation
        could be performed in the mapRawData() method but it is convenient to
        do it here as all off the source data is readily available plus it
        maintains simplicity in the mapRawData() method.

        Input parameter:

            period: The file name, including path, of the WeatherCat monthly
                    .cat file from which raw obs data will be read.
        """

        # confirm the source exists
        if os.path.isfile(period):
            # set .cat to WeeWX archive field map
            self.map = dict(self.default_header_map)
            # obtain year from the directory containing the .cat file
            _year = os.path.basename(os.path.dirname(period))
            # obtain the month number from the .cat filename, we need to zero
            # pad to ensure we get a 2 character month
            _month = os.path.basename(period).split('_')[0].zfill(2)
            # read the .cat file line by line
            with open(period, 'r') as f:
                for _raw_line in f:
                    # the line is a data line if it has a t and V key
                    if 't:' in _raw_line and 'V:' in _raw_line:
                        # we have a data line
                        _row = {}
                        # check for and remove any null bytes and strip any
                        # whitespace
                        if "\x00" in _raw_line:
                            _line = _raw_line.replace("\x00", "").strip()
                            _msg = "One or more null bytes found in and removed " \
                                   "from month '%d' year '%d'" % (int(_month), _year)
                            print(_msg)
                            log.info(_msg)
                        else:
                            # strip any whitespace
                            _line = _raw_line.strip()
                        # iterate over the key-value pairs on the line
                        for pair in shlex.split(_line):
                            _split_pair = pair.split(":", 1)
                            # if we have a key-value pair save the data in the
                            # row dict
                            if len(_split_pair) > 1:
                                _row[_split_pair[0]] = _split_pair[1]
                        # calculate an epoch timestamp for the row
                        if 't' in _row:
                            _ymt = ''.join([_year, _month, _row['t']])
                            try:
                                _datetm = time.strptime(_ymt, "%Y%m%d%H%M")
                                _row['dateTime'] = str(int(time.mktime(_datetm)))
                            except ValueError:
                                raise ValueError("Cannot convert '%s' to timestamp." % _ymt)
                        yield _row
        else:
            # if it doesn't we can't go on so raise it
            _msg = "WeatherCat monthly .cat file '%s' could not be found." % period
            raise weeimport.WeeImportIOError(_msg)

    def period_generator(self):
        """Generator yielding a sequence of WeatherCat monthly .cat file names.

        This generator controls the FOR statement in the parent's run() method
        that iterates over the monthly .cat files to be imported. The generator
        yields a monthly .cat file name from the sorted list of monthly .cat
        files to be imported until the list is exhausted. The generator also
        sets the first_period and last_period properties."""

        # Step through each of our file names
        for self.file_name in self.cat_list:
            # Yield the file name
            yield self.file_name

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

         Return True if the current file name being processed is the first in
         the list or it is None (the initialisation value).
         """

        return self.file_name == self.cat_list[0] if self.file_name is not None else True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

         Return True if the current file name being processed is the last in
         the list.
         """

        return self.file_name == self.cat_list[-1]
