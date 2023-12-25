#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module for use with wee_import to import observational data from WeatherCat
monthly .cat files.
"""

# Python imports
import glob
import logging
import os
import shlex
import time

# WeeWX imports
import weewx
from weeutil.weeutil import timestamp_to_string
from weewx.units import unit_nicknames
from . import weeimport

log = logging.getLogger(__name__)


# ============================================================================
#                             class WeatherCatSource
# ============================================================================

class WeatherCatSource(weeimport.Source):
    """Class to interact with a WeatherCat monthly data (.cat) files.

    Handles the import of data from WeatherCat monthly data files. WeatherCat
    stores formatted observation data in text files using the .cat extension.
    Each file contains a month of data with one record per line. Fields in each
    record are space delimited with field names and field data separated by a
    colon (:).

    Data files are named 'x_WeatherCatData.cat' where x is the month
    number (1..12). Each year's monthly data files are located in a directory
    named 'YYYY' where YYYY is the year number. wee_import relies on this
    directory structure for successful import of WeatherCat data.

    Data is imported from all monthly data files found in the source directory
    one file at a time. Units of measure are not specified in the monthly data
    files so the units of measure must be specified in the import config file
    being used.

    WeatherCat supports the following units:
    - temperature: °C and °F
    - dewpoint: °C and °F but set independently of temperature
    - pressure: inHg, hPa and mBar
    - rain: inch and mm
    - wind speed: km/hr, mph, knots and m/s
    """

    # dict to map all possible WeatherCat .cat file field names to WeeWX
    # archive field names and units
    default_map = {
        'dateTime': {
            'source_field': 'datetime',
            'unit': 'unix_epoch'},
        'outTemp': {
            'source_field': 'T',
            'unit': 'degree_C'},
        'inTemp': {
            'source_field': 'Ti',
            'unit': 'degree_C'},
        'extraTemp1': {
            'source_field': 'T1',
            'unit': 'degree_C'},
        'extraTemp2': {
            'source_field': 'T2',
            'unit': 'degree_C'},
        'extraTemp3': {
            'source_field': 'T3',
            'unit': 'degree_C'},
        'dewpoint': {
            'source_field': 'D',
            'unit': 'degree_C'},
        'barometer': {
            'source_field': 'Pr',
            'unit': 'mbar'},
        'windSpeed': {
            'source_field': 'W',
            'unit': 'km_per_hour'},
        'windDir': {
            'source_field': 'Wd',
            'unit': 'degree_compass'},
        'windchill': {
            'source_field': 'Wc',
            'unit': 'degree_C'},
        'windGust': {
            'source_field': 'Wg',
            'unit': 'km_per_hour'},
        'rainRate': {
            'source_field': 'Ph',
            'unit': 'mm_per_hour'},
        'rain': {
            'source_field': 'P',
            'unit': 'mm'},
        'outHumidity': {
            'source_field': 'H',
            'unit': 'percent'},
        'inHumidity': {
            'source_field': 'Hi',
            'unit': 'percent'},
        'extraHumid1': {
            'source_field': 'H1',
            'unit': 'percent'},
        'extraHumid2': {
            'source_field': 'H2',
            'unit': 'percent'},
        'radiation': {
            'source_field': 'S',
            'unit': 'watt_per_meter_squared'},
        'soilMoist1': {
            'source_field': 'Sm1',
            'unit': 'centibar'},
        'soilMoist2': {
            'source_field': 'Sm2',
            'unit': 'centibar'},
        'soilMoist3': {
            'source_field': 'Sm3',
            'unit': 'centibar'},
        'soilMoist4': {
            'source_field': 'Sm4',
            'unit': 'centibar'},
        'leafWet1': {
            'source_field': 'Lw1',
            'unit': 'count'},
        'leafWet2': {
            'source_field': 'Lw2',
            'unit': 'count'},
        'soilTemp1': {
            'source_field': 'St1',
            'unit': 'degree_C'},
        'soilTemp2': {
            'source_field': 'St2',
            'unit': 'degree_C'},
        'soilTemp3': {
            'source_field': 'St3',
            'unit': 'degree_C'},
        'soilTemp4': {
            'source_field': 'St4',
            'unit': 'degree_C'},
        'leafTemp1': {
            'source_field': 'Lt1',
            'unit': 'degree_C'},
        'leafTemp2': {
            'source_field': 'Lt2',
            'unit': 'degree_C'},
        'UV': {
            'source_field': 'U',
            'unit': 'uv_index'}
    }
    # unit groups used to specify units used by WeatherCat field
    weathercat_unit_groups = ('temperature', 'dewpoint', 'pressure',
                              'windspeed', 'precipitation')
    # tuple of fields using 'temperature' units
    _temperature_fields = ('T', 'Ti', 'T1', 'T2', 'T3', 'Wc', 'St1', 'St2',
                           'St3', 'St4', 'Lt1', 'Lt2')
    # tuple of fields using 'dewpoint' units
    _dewpoint_fields = ('D', )
    # tuple of fields using 'pressure' units
    _pressure_fields = ('Pr', )
    # tuple of fields using 'precipitation' units
    _precipitation_fields = ('P', )
    # tuple of fields using 'precipitation rate' units
    _precipitation_rate_fields = ('Ph', )
    # tuple of fields using 'windspeed' units
    _windspeed_fields = ('W', 'Wg')

    def __init__(self, config_path, config_dict, import_config_path,
                 weathercat_config_dict, **kwargs):

        # call our parents __init__
        super().__init__(config_dict, weathercat_config_dict, **kwargs)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.weathercat_config_dict = weathercat_config_dict

        # wind dir bounds
        self.wind_dir = [0, 360]

        # The WeatherCatData.cat file structure is well-defined, so we can
        # construct our import field-to-WeeWX archive field map now. The user
        # can specify the units used in the monthly data files, so first
        # construct a default field map then go through and adjust the units
        # where necessary.
        # construct our import field-to-WeeWX archive field map
        _map = dict(WeatherCatSource.default_map)
        # create the final field map based on the default field map and any
        # field map options provided by the user
        self.map = self.parse_map(_map,
                                  self.weathercat_config_dict.get('FieldMap', {}),
                                  self.weathercat_config_dict.get('FieldMapExtensions', {}))

        # property holding the current log file name being processed
        self.file_name = None

        # get our source file path
        try:
            self.source = weathercat_config_dict['directory']
        except KeyError:
            raise weewx.ViolatedPrecondition(
                "WeatherCat directory not specified in '%s'." % import_config_path)

        # Get a list of monthly data files sorted from oldest to newest.
        # Remember the files are in 'year' folders.
        # first get a list of all the 'year' folders including path
        _y_list = [os.path.join(self.source, d) for d in os.listdir(self.source)
                   if os.path.isdir(os.path.join(self.source, d))]
        # initialise our list of monthly data files
        f_list = []
        # iterate over the 'year' directories
        for _dir in _y_list:
            # find any monthly data files in the 'year' directory and add them
            # to the file list
            f_list += glob.glob(''.join([_dir, '/*[0-9]_WeatherCatData.cat']))
        # now get an intermediate list that we can use to sort the file list
        # from oldest to newest
        _temp = [(fn,
                  os.path.basename(os.path.dirname(fn)),
                  os.path.basename(fn).split('_')[0].zfill(2)) for fn in f_list]
        # now do the sorting
        self.cat_list = [a[0] for a in sorted(_temp,
                                              key=lambda el: (el[1], el[2]))]

        if len(self.cat_list) == 0:
            raise weeimport.WeeImportIOError(
                "No WeatherCat monthly .cat files found in directory '%s'." % self.source)

        # property holding dict of last seen values for cumulative observations
        self.last_values = {}

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
        if kwargs['date']:
            _msg = "     date=%s" % kwargs['date']
        else:
            # we must have --from and --to
            _msg = "     from=%s, to=%s" % (kwargs['from_datetime'], kwargs['to_datetime'])
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
        self.print_map()
        if self.calc_missing:
            print("Missing derived observations will be calculated.")
        if not self.UV_sensor:
            print("All WeeWX UV fields will be set to None.")
        if not self.solar_sensor:
            print("All WeeWX radiation fields will be set to None.")
        if kwargs['date'] or kwargs['from_datetime']:
            print("Observations timestamped after %s and "
                  "up to and" % (timestamp_to_string(self.first_ts),))
            print("including %s will be imported." % (timestamp_to_string(self.last_ts),))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def get_raw_data(self, period):
        """Get the raw data and create WeatherCat to WeeWX archive field map.

        Create a WeatherCat to WeeWX archive field map and instantiate a
        generator to yield one row of raw observation data at a time from the
        monthly data file.

        Field names and units are fixed for a WeatherCat monthly data file, so
        we can use a fixed field map.

        Calculating a date-time for each row requires obtaining the year from
        the monthly data file directory, month from the monthly data file name
        and day, hour and minute from the individual rows in the monthly data
        file. This calculation could be performed in the mapRawData() method,
        but it is convenient to do it here as all the source data is readily
        available plus it maintains simplicity in the mapRawData() method.

        Input parameter:

            period: The file name, including path, of the WeatherCat monthly
                    data file from which raw obs data will be read.
        """

        # confirm the source exists
        if os.path.isfile(period):
            # obtain year from the directory containing the monthly data file
            _year = os.path.basename(os.path.dirname(period))
            # obtain the month number from the monthly data filename, we need
            # to zero pad to ensure we get a two character month
            _month = os.path.basename(period).split('_')[0].zfill(2)
            # read the monthly data file line by line
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
                                _row['datetime'] = str(int(time.mktime(_datetm)))
                            except ValueError:
                                raise ValueError("Cannot convert '%s' to timestamp." % _ymt)
                        yield _row
        else:
            # if it doesn't we can't go on so raise it
            _msg = "WeatherCat monthly .cat file '%s' could not be found." % period
            raise weeimport.WeeImportIOError(_msg)

    def period_generator(self):
        """Generator yielding a sequence of WeatherCat monthly data file names.

        This generator controls the FOR statement in the parent's run() method
        that iterates over the monthly data files to be imported. The generator
        yields a monthly data file name from the sorted list of monthly data
        files to be imported until the list is exhausted. The generator also
        sets the first_period and last_period properties."""

        # step through each of our file names
        for self.file_name in self.cat_list:
            # yield the file name
            yield self.file_name

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

         Return True if the current file name being processed is the first in
         the list or if the current period is None (the initialisation value).
         """

        return self.file_name == self.cat_list[0] if self.file_name is not None else True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

         Return True if the current file name being processed is the last in
         the list.
         """

        return self.file_name == self.cat_list[-1]
