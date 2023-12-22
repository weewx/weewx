#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module to interact with Cumulus monthly log files and import raw
observational data for use with weeimport.
"""

# Python imports
import csv
import glob
import io
import logging
import os
import time

# WeeWX imports
from . import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string
from weewx.units import unit_nicknames

log = logging.getLogger(__name__)


# ============================================================================
#                             class CumulusSource
# ============================================================================

class CumulusSource(weeimport.Source):
    """Class to interact with a Cumulus generated monthly log files.

    Handles the import of data from Cumulus monthly log files.Cumulus stores
    observation data in monthly log files. Each log file contains a month of
    data in CSV format. The format of the CSV data (e.g., date separator, field
    delimiter, decimal point character) depends upon the settings used in
    Cumulus.

    Data is imported from all month log files found in the source directory one
    log file at a time. Units of measure are not specified in the monthly log
    files so the units of measure must be specified in the wee_import config
    file. Whilst the Cumulus monthly log file format is well-defined, some
    pre-processing of the data is required to provide data in a format the
    suitable for use in the wee_import mapping methods.
    """

    # List of field names used during import of Cumulus log files. These field
    # names are for internal wee_import use only as Cumulus monthly log files
    # do not have a header line with defined field names. Cumulus monthly log
    # field 0 and field 1 are date and time fields respectively. getRawData()
    # combines these fields to return a formatted date-time string that is later
    # converted into a unix epoch timestamp.
    _field_list = ['datetime', 'cur_out_temp', 'cur_out_hum',
                   'cur_dewpoint', 'avg_wind_speed', 'gust_wind_speed',
                   'avg_wind_bearing', 'cur_rain_rate', 'day_rain', 'cur_slp',
                   'rain_counter', 'curr_in_temp', 'cur_in_hum',
                   'latest_wind_gust', 'cur_windchill', 'cur_heatindex',
                   'cur_uv', 'cur_solar', 'cur_et', 'annual_et',
                   'cur_app_temp', 'cur_tmax_solar', 'day_sunshine_hours',
                   'cur_wind_bearing', 'day_rain_rg11', 'midnight_rain']
    # tuple of fields using 'temperature' units
    _temperature_fields = ('cur_out_temp', 'cur_dewpoint', 'curr_in_temp',
                           'cur_windchill', 'cur_heatindex','cur_app_temp')
    # tuple of fields using 'pressure' units
    _pressure_fields = ('cur_slp', )
    # tuple of fields using 'rain' units
    _rain_fields = ('day_rain', 'cur_et', 'annual_et',
                    'day_rain_rg11', 'midnight_rain')
    # tuple of fields using 'rain rate' units
    _rain_rate_fields = ('cur_rain_rate', )
    # tuple of fields using 'speed' units
    _speed_fields = ('avg_wind_speed', 'gust_wind_speed', 'latest_wind_gust')
    # dict to lookup rain rate units given rain units
    rain_units_dict = {'inch': 'inch_per_hour', 'mm': 'mm_per_hour'}
    # Dict containing default mapping of Cumulus fields (refer to _field_list)
    # to WeeWX archive fields. The user may modify this mapping by including a
    # [[FieldMap]] and/or a [[FieldMapExtensions]] stanza in the import config
    # file.
    default_map = {
        'dateTime': {
            'source_field': 'datetime',
            'unit': 'unix_epoch'},
        'outTemp': {
            'source_field': 'cur_out_temp'},
        'inTemp': {
            'source_field': 'cur_in_temp'},
        'outHumidity': {
            'source_field': 'cur_out_hum',
            'unit': 'percent'},
        'inHumidity': {
            'source_field': 'cur_in_hum',
            'unit': 'percent'},
        'dewpoint': {
            'source_field': 'cur_dewpoint'},
        'heatindex': {
            'source_field': 'cur_heatindex'},
        'windchill': {
            'source_field': 'cur_windchill'},
        'appTemp': {
            'source_field': 'cur_app_temp'},
        'barometer': {
            'source_field': 'cur_slp'},
        'rain': {
            'source_field': 'midnight_rain',
            'is_cumulative': True},
        'rainRate': {
            'source_field': 'cur_rain_rate'},
        'windSpeed': {
            'source_field': 'avg_wind_speed'},
        'windDir': {
            'source_field': 'avg_wind_bearing',
            'unit': 'degree_compass'},
        'windGust': {
            'source_field': 'gust_wind_speed'},
        'radiation': {
            'source_field': 'cur_solar',
            'unit': 'watt_per_meter_squared'},
        'UV': {
            'source_field': 'cur_uv',
            'unit': 'uv_index'}
    }

    def __init__(self, config_path, config_dict, import_config_path,
                 cumulus_config_dict, **kwargs):

        # call our parents __init__
        super().__init__(config_dict, cumulus_config_dict, **kwargs)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.cumulus_config_dict = cumulus_config_dict

        # wind dir bounds
        self.wind_dir = [0, 360]

        # field delimiter used in monthly log files, default to comma
        self.delimiter = str(cumulus_config_dict.get('delimiter', ','))

        # date separator used in monthly log files, default to solidus
        separator = cumulus_config_dict.get('separator', '/')
        # we combine Cumulus date and time fields to give a fixed format
        # date-time string
        self.raw_datetime_format = separator.join(('%d', '%m', '%y %H:%M'))

        # initialise our import field-to-WeeWX archive field map
        _map = dict(CumulusSource.default_map)
        # create the final field map based on the default field map and any
        # field map options provided by the user
        self.map = self.parse_map(_map,
                                  self.cumulus_config_dict.get('FieldMap', {}),
                                  self.cumulus_config_dict.get('FieldMapExtensions', {}))

        # Cumulus log files have a number of 'rain' fields that can be used to
        # derive the WeeWX rain field. Which one is available depends on the
        # Cumulus version that created the logs. The preferred field is field
        # 26(AA) - total rainfall since midnight but it is only available in
        # Cumulus v1.9.4 or later. If that field is not available then the
        # preferred field in field 09(J) - total rainfall today then field
        # 11(L) - total rainfall counter. Initialise the rain_source_confirmed
        # property now and we will deal with it later when we have some source
        # data.
        self.rain_source_confirmed = None

        # get our source file path
        try:
            self.source = cumulus_config_dict['directory']
        except KeyError:
            _msg = "Cumulus monthly logs directory not specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # get the source file encoding, default to utf-8-sig
        self.source_encoding = self.cumulus_config_dict.get('source_encoding',
                                                            'utf-8-sig')

        # property holding the current log file name being processed
        self.file_name = None

        # Now get a list on monthly log files sorted from oldest to newest
        month_log_list = glob.glob(self.source + '/?????log.txt')
        _temp = [(fn, fn[-9:-7], time.strptime(fn[-12:-9], '%b').tm_mon) for fn in month_log_list]
        self.log_list = [a[0] for a in sorted(_temp,
                                              key=lambda el: (el[1], el[2]))]
        if len(self.log_list) == 0:
            raise weeimport.WeeImportIOError(
                "No Cumulus monthly logs found in directory '%s'." % self.source)

        # property holding dict of last seen values for cumulative observations
        self.last_values = {}

        # tell the user/log what we intend to do
        _msg = "Cumulus monthly log files in the '%s' directory will be imported" % self.source
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
        _msg = "     dry-run=%s, calc_missing=%s, " \
               "ignore_invalid_data=%s" % (self.dry_run,
                                           self.calc_missing,
                                           self.ignore_invalid_data)
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
        _msg = "Using database binding '%s', which is bound " \
               "to database '%s'" % (self.db_binding_wx,
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
                  "up to and" % timestamp_to_string(self.first_ts))
            print("including %s will be imported." % timestamp_to_string(self.last_ts))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def get_raw_data(self, period):
        """Get raw observation data and construct a map from Cumulus monthly
            log fields to WeeWX archive fields.

        Obtain raw observational data from Cumulus monthly logs. This raw data
        needs to be cleaned of unnecessary characters/codes, a date-time field
        generated for each row and an iterable returned.

        Input parameters:

            period: the file name, including path, of the Cumulus monthly log
                    file from which raw obs data will be read.
        """

        # period holds the filename of the monthly log file that contains our
        # data. Does our source exist?
        if os.path.isfile(period):
            # It exists.  The source file may use some encoding, if we can't
            # decode it raise a WeeImportDecodeError.
            try:
                with io.open(period, mode='r', encoding=self.source_encoding) as f:
                    _raw_data = f.readlines()
            except UnicodeDecodeError as e:
                # not a utf-8 based encoding, so raise a WeeImportDecodeError
                raise weeimport.WeeImportDecodeError(e)
        else:
            # If it doesn't we can't go on so raise it
            raise weeimport.WeeImportIOError(
                "Cumulus monthly log file '%s' could not be found." % period)

        # Our raw data needs a bit of cleaning up before we can parse/map it.
        _clean_data = []
        for _row in _raw_data:
            # check for and remove any null bytes
            clean_row = _row
            if "\x00" in _row:
                clean_row = clean_row.replace("\x00", "")
                _msg = "One or more null bytes found in and removed " \
                       "from monthly log file '%s'" % (period, )
                print(_msg)
                log.info(_msg)
            # make sure we have full stops as decimal points
            _line = clean_row.replace(self.decimal_sep, '.')
            # ignore any blank lines
            if _line != "\n":
                # Cumulus has separate date and time fields as the first 2
                # fields of a row. It is easier to combine them now into a
                # single date-time field that we can parse later when we map the
                # raw data.
                _datetime_line = _line.replace(self.delimiter, ' ', 1)
                # Save what's left
                _clean_data.append(_datetime_line)

        # if we haven't confirmed our source for the WeeWX rain field we need
        # to do so now
        if self.rain_source_confirmed is None:
            # The Cumulus source field depends on the Cumulus version that
            # created the log files. Unfortunately, we can only determine
            # which field to use by looking at the mapped Cumulus data. If we
            # look at our DictReader we have no way to reset it, so we create
            # a one off DictReader to use instead.
            _rain_reader = csv.DictReader(_clean_data, fieldnames=self._field_list,
                                          delimiter=self.delimiter)
            # now that we know what Cumulus fields are available we can set our
            # rain source appropriately
            self.set_rain_source(_rain_reader)

        # Now create a dictionary CSV reader
        _reader = csv.DictReader(_clean_data, fieldnames=self._field_list,
                                 delimiter=self.delimiter)
        # Return our dict reader
        return _reader

    def period_generator(self):
        """Generator function yielding a sequence of monthly log file names.

        This generator controls the FOR statement in the parents run() method
        that loops over the monthly log files to be imported. The generator
        yields a monthly log file name from the list of monthly log files to
        be imported until the list is exhausted.
        """

        # step through each of our file names
        for self.file_name in self.log_list:
            # yield the file name
            yield self.file_name

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

         Return True if the current file name being processed is the first in
         the list, or if it is None (the initialisation value).
         """

        return self.file_name == self.log_list[0] if self.file_name is not None else True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

         Return True if the current file name being processed is the last in
         the list.
         """

        return self.file_name == self.log_list[-1]

    def set_rain_source(self, _data):
        """Set the Cumulus field to be used as the WeeWX rain field source.
        """

        _row = next(_data)
        if _row['midnight_rain'] is not None:
            # we have data in midnight_rain, our default source, so leave
            # things as they are and return
            pass
        elif _row['day_rain'] is not None:
            # we have data in day_rain so use that as our rain source
            self.map['rain']['source'] = 'day_rain'
        elif _row['rain_counter'] is not None:
            # we have data in rain_counter so use that as our rain source
            self.map['rain']['source'] = 'rain_counter'
        else:
            # We should never end up in this state but....
            # We have no suitable rain source so we can't import so remove the
            # rain field entry from the header map.
            del self.map['rain']
        # we only need to do this once so set our flag to True
        self.rain_source_confirmed = True
        return
