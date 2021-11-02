#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module to interact with Cumulus monthly log files and import raw
observational data for use with weeimport.
"""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

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

# Dict to lookup rainRate units given rain units
rain_units_dict = {'inch': 'inch_per_hour', 'mm': 'mm_per_hour'}


# ============================================================================
#                             class CumulusSource
# ============================================================================


class CumulusSource(weeimport.Source):
    """Class to interact with a Cumulus generated monthly log files.

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
                   'lastest_wind_gust', 'cur_windchill', 'cur_heatindex',
                   'cur_uv', 'cur_solar', 'cur_et', 'annual_et',
                   'cur_app_temp', 'cur_tmax_solar', 'day_sunshine_hours',
                   'cur_wind_bearing', 'day_rain_rg11', 'midnight_rain']
    # Dict to map all possible Cumulus field names (refer _field_list) to WeeWX
    # archive field names and units.
    _header_map = {'datetime': {'units': 'unix_epoch', 'map_to': 'dateTime'},
                   'cur_out_temp': {'map_to': 'outTemp'},
                   'curr_in_temp': {'map_to': 'inTemp'},
                   'cur_dewpoint': {'map_to': 'dewpoint'},
                   'cur_slp': {'map_to': 'barometer'},
                   'avg_wind_bearing': {'units': 'degree_compass',
                                        'map_to': 'windDir'},
                   'avg_wind_speed': {'map_to': 'windSpeed'},
                   'cur_heatindex': {'map_to': 'heatindex'},
                   'gust_wind_speed': {'map_to': 'windGust'},
                   'cur_windchill': {'map_to': 'windchill'},
                   'cur_out_hum': {'units': 'percent', 'map_to': 'outHumidity'},
                   'cur_in_hum': {'units': 'percent', 'map_to': 'inHumidity'},
                   'midnight_rain': {'map_to': 'rain'},
                   'cur_rain_rate': {'map_to': 'rainRate'},
                   'cur_solar': {'units': 'watt_per_meter_squared',
                                 'map_to': 'radiation'},
                   'cur_uv': {'units': 'uv_index', 'map_to': 'UV'},
                   'cur_app_temp': {'map_to': 'appTemp'}
                   }

    def __init__(self, config_dict, config_path, cumulus_config_dict, import_config_path, options):

        # call our parents __init__
        super(CumulusSource, self).__init__(config_dict,
                                            cumulus_config_dict,
                                            options)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.cumulus_config_dict = cumulus_config_dict

        # wind dir bounds
        self.wind_dir = [0, 360]

        # field delimiter used in monthly log files, default to comma
        self.delimiter = str(cumulus_config_dict.get('delimiter', ','))
        # decimal separator used in monthly log files, default to decimal point
        self.decimal = cumulus_config_dict.get('decimal', '.')

        # date separator used in monthly log files, default to solidus
        separator = cumulus_config_dict.get('separator', '/')
        # we combine Cumulus date and time fields to give a fixed format
        # date-time string
        self.raw_datetime_format = separator.join(('%d', '%m', '%y %H:%M'))

        # Cumulus log files provide a number of cumulative rainfall fields. We
        # cannot use the daily rainfall as this may reset at some time of day
        # other than midnight (as required by WeeWX). So we use field 26, total
        # rainfall since midnight and treat it as a cumulative value.
        self.rain = 'cumulative'

        # initialise our import field-to-WeeWX archive field map
        self.map = None

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

        # Units of measure for some obs (eg temperatures) cannot be derived from
        # the Cumulus monthly log files. These units must be specified by the
        # user in the import config file. Read these units and fill in the
        # missing unit data in the header map. Do some basic error checking and
        # validation, if one of the fields is missing or invalid then we need
        # to catch the error and raise it as we can't go on.
        # Temperature
        try:
            temp_u = cumulus_config_dict['Units'].get('temperature')
        except KeyError:
            _msg = "No units specified for Cumulus temperature " \
                   "fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            # temperature units vary between unit systems so we can verify a
            # valid temperature unit simply by checking for membership of
            # weewx.units.conversionDict keys
            if temp_u in weewx.units.conversionDict.keys():
                self._header_map['cur_out_temp']['units'] = temp_u
                self._header_map['curr_in_temp']['units'] = temp_u
                self._header_map['cur_dewpoint']['units'] = temp_u
                self._header_map['cur_heatindex']['units'] = temp_u
                self._header_map['cur_windchill']['units'] = temp_u
                self._header_map['cur_app_temp']['units'] = temp_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus " \
                       "temperature fields in %s." % (temp_u,
                                                      self.import_config_path)
                raise weewx.UnitError(_msg)
        # Pressure
        try:
            press_u = cumulus_config_dict['Units'].get('pressure')
        except KeyError:
            _msg = "No units specified for Cumulus pressure " \
                   "fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if press_u in ['inHg', 'mbar', 'hPa']:
                self._header_map['cur_slp']['units'] = press_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus " \
                       "pressure fields in %s." % (press_u,
                                                   self.import_config_path)
                raise weewx.UnitError(_msg)
        # Rain
        try:
            rain_u = cumulus_config_dict['Units'].get('rain')
        except KeyError:
            _msg = "No units specified for Cumulus " \
                   "rain fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if rain_u in rain_units_dict:
                self._header_map['midnight_rain']['units'] = rain_u
                self._header_map['cur_rain_rate']['units'] = rain_units_dict[rain_u]

            else:
                _msg = "Unknown units '%s' specified for Cumulus " \
                       "rain fields in %s." % (rain_u,
                                               self.import_config_path)
                raise weewx.UnitError(_msg)
        # Speed
        try:
            speed_u = cumulus_config_dict['Units'].get('speed')
        except KeyError:
            _msg = "No units specified for Cumulus " \
                   "speed fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            # speed units vary between unit systems so we can verify a valid
            # speed unit simply by checking for membership of
            # weewx.units.conversionDict keys
            if speed_u in weewx.units.conversionDict.keys():
                self._header_map['avg_wind_speed']['units'] = speed_u
                self._header_map['gust_wind_speed']['units'] = speed_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus " \
                       "speed fields in %s." % (speed_u,
                                                self.import_config_path)
                raise weewx.UnitError(_msg)

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
        if options.date:
            _msg = "     date=%s" % options.date
        else:
            # we must have --from and --to
            _msg = "     from=%s, to=%s" % (options.date_from, options.date_to)
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
        if self.calc_missing:
            print("Missing derived observations will be calculated.")
        if not self.UV_sensor:
            print("All WeeWX UV fields will be set to None.")
        if not self.solar_sensor:
            print("All WeeWX radiation fields will be set to None.")
        if options.date or options.date_from:
            print("Observations timestamped after %s and "
                  "up to and" % timestamp_to_string(self.first_ts))
            print("including %s will be imported." % timestamp_to_string(self.last_ts))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def getRawData(self, period):
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
            _line = clean_row.replace(self.decimal, '.')
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
        # Finally, get our database-source mapping
        self.map = self.parseMap('Cumulus', _reader, self.cumulus_config_dict)
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
         the list or it is None (the initialisation value).
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
            self._header_map['day_rain'] = self._header_map['midnight_rain']
            del self._header_map['midnight_rain']
        elif _row['rain_counter'] is not None:
            # we have data in rain_counter so use that as our rain source
            self._header_map['rain_counter'] = self._header_map['midnight_rain']
            del self._header_map['midnight_rain']
        else:
            # We should never end up in this state but....
            # We have no suitable rain source so we can't import so remove the
            # rain field entry from the header map.
            del self._header_map['midnight_rain']
        # we only need to do this once so set our flag to True
        self.rain_source_confirmed = True
        return
