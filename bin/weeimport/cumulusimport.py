#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module to interact with Cumulus monthly log files and import raw
observational data for use with weeimport.
"""

from __future__ import with_statement

# Python imports
import csv
import glob
import os
import syslog
import time

# weeWX imports
import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string
from weewx.units import unit_nicknames

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
    # Dict to map all possible Cumulus field names (refer _field_list) to weeWX
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

    def __init__(self, config_dict, config_path, cumulus_config_dict, import_config_path, options, log):

        # call our parents __init__
        super(CumulusSource, self).__init__(config_dict,
                                            cumulus_config_dict,
                                            options,
                                            log)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.cumulus_config_dict = cumulus_config_dict

        # wind dir bounds
        self.wind_dir = [0, 360]

        # field delimiter used in monthly log files, default to comma
        self.delimiter = cumulus_config_dict.get('delimiter', ',')
        # decimal separator used in monthly log files, default to decimal point
        self.decimal = cumulus_config_dict.get('decimal', '.')

        # date separator used in monthly log files, default to solidus
        separator = cumulus_config_dict.get('separator', '/')
        # we combine Cumulus date and time fields to give a fixed format
        # date-time string
        self.raw_datetime_format = separator.join(('%d', '%m', '%y %H:%M'))

        # Cumulus log files provide a number of cumulative rainfall fields. We
        # cannot use the daily rainfall as this may reset at some time of day
        # other than midnight (as required by weeWX). So we use field 26, total
        # rainfall since midnight and treat it as a cumulative value.
        self.rain = 'cumulative'

        # initialise our import field-to-weeWX archive field map
        self.map = None

        # Cumulus log files have a number of 'rain' fields that can be used to
        # derive the weeWX rain field. Which one is available depends on the
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
        except:
            _msg = "No units specified for Cumulus temperature fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if temp_u in weewx.units.default_unit_format_dict:
                self._header_map['cur_out_temp']['units'] = temp_u
                self._header_map['curr_in_temp']['units'] = temp_u
                self._header_map['cur_dewpoint']['units'] = temp_u
                self._header_map['cur_heatindex']['units'] = temp_u
                self._header_map['cur_windchill']['units'] = temp_u
                self._header_map['cur_app_temp']['units'] = temp_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus temperature fields in %s." % (temp_u,
                                                                                               self.import_config_path)
                raise weewx.UnitError(_msg)
        # Pressure
        try:
            press_u = cumulus_config_dict['Units'].get('pressure')
        except:
            _msg = "No units specified for Cumulus pressure fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if press_u in ['inHg', 'mbar', 'hPa']:
                self._header_map['cur_slp']['units'] = press_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus pressure fields in %s." % (press_u,
                                                                                            self.import_config_path)
                raise weewx.UnitError(_msg)
        # Rain
        try:
            rain_u = cumulus_config_dict['Units'].get('rain')
        except:
            _msg = "No units specified for Cumulus rain fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if rain_u in rain_units_dict:
                self._header_map['midnight_rain']['units'] = rain_u
                self._header_map['cur_rain_rate']['units'] = rain_units_dict[rain_u]

            else:
                _msg = "Unknown units '%s' specified for Cumulus rain fields in %s." % (rain_u,
                                                                                        self.import_config_path)
                raise weewx.UnitError(_msg)
        # Speed
        try:
            speed_u = cumulus_config_dict['Units'].get('speed')
        except:
            _msg = "No units specified for Cumulus speed fields in %s." % (self.import_config_path, )
            raise weewx.UnitError(_msg)
        else:
            if speed_u in weewx.units.default_unit_format_dict:
                self._header_map['avg_wind_speed']['units'] = speed_u
                self._header_map['gust_wind_speed']['units'] = speed_u
            else:
                _msg = "Unknown units '%s' specified for Cumulus speed fields in %s." % (speed_u,
                                                                                         self.import_config_path)
                raise weewx.UnitError(_msg)

        # get our source file path
        try:
            self.source = cumulus_config_dict['directory']
        except KeyError:
            raise weewx.ViolatedPrecondition("Cumulus monthly logs directory not specified in '%s'." % import_config_path)

        # Now get a list on monthly log files sorted from oldest to newest
        month_log_list = glob.glob(self.source + '/?????log.txt')
        _temp = [(fn, fn[-9:-7], time.strptime(fn[-12:-9],'%b').tm_mon) for fn in month_log_list]
        self.log_list = [a[0] for a in sorted(_temp,
                                              key = lambda el : (el[1], el[2]))]
        if len(self.log_list) == 0:
            raise weeimport.WeeImportIOError(
                "No Cumulus monthly logs found in directory '%s'." % self.source)

        # tell the user/log what we intend to do
        _msg = "Cumulus monthly log files in the '%s' directory will be imported" % self.source
        self.wlog.printlog(syslog.LOG_INFO, _msg)
        _msg = "The following options will be used:"
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        _msg = "     config=%s, import-config=%s" % (config_path,
                                                     self.import_config_path)
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        if options.date:
            _msg = "     date=%s" % options.date
        else:
            # we must have --from and --to
            _msg = "     from=%s, to=%s" % (options.date_from, options.date_to)
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        _msg = "     dry-run=%s, calc-missing=%s" % (self.dry_run,
                                                     self.calc_missing)
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        _msg = "     tranche=%s, interval=%s" % (self.tranche,
                                                 self.interval)
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        _msg = "     UV=%s, radiation=%s" % (self.UV_sensor, self.solar_sensor)
        self.wlog.verboselog(syslog.LOG_DEBUG, _msg)
        _msg = "Using database binding '%s', which is bound to database '%s'" % (self.db_binding_wx,
                                                                                 self.dbm.database_name)
        self.wlog.printlog(syslog.LOG_INFO, _msg)
        _msg = "Destination table '%s' unit system is '%#04x' (%s)." % (self.dbm.table_name,
                                                                        self.archive_unit_sys,
                                                                        unit_nicknames[self.archive_unit_sys])
        self.wlog.printlog(syslog.LOG_INFO, _msg)
        if self.calc_missing:
            print "Missing derived observations will be calculated."
        if not self.UV_sensor:
            print "All weeWX UV fields will be set to None."
        if not self.solar_sensor:
            print "All weeWX radiation fields will be set to None."
        if options.date or options.date_from:
            print "Observations timestamped after %s and up to and" % (timestamp_to_string(self.first_ts), )
            print "including %s will be imported." % (timestamp_to_string(self.last_ts), )
        if self.dry_run:
            print "This is a dry run, imported data will not be saved to archive."

    def getRawData(self, period):
        """Get raw observation data and construct a map from Cumulus monthly
            log fields to weeWX archive fields.

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
            with open(period, 'r') as f:
                _raw_data = f.readlines()
        else:
            # If it doesn't we can't go on so raise it
            raise weeimport.WeeImportIOError(
                "Cumulus monthly log file '%s' could not be found." % period)

        # Our raw data needs a bit of cleaning up before we can parse/map it.
        _clean_data = []
        for _row in _raw_data:
            # Make sure we have full stops as decimal points
            _line = _row.replace(self.decimal, '.')
            # Ignore any blank lines
            if _line != "\n":
                # Cumulus has separate date and time fields as the first 2
                # fields of a row. It is easier to combine them now into a
                # single date-time field that we can parse later when we map the
                # raw data.
                _datetime_line = _line.replace(self.delimiter, ' ', 1)
                # Save what's left
                _clean_data.append(_datetime_line)

        # if we haven't confirmed our source for the weeWX rain field we need
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
        be imported until the list is exhausted. The generator also sets the
        first_period and last_period properties."""

        # Step through each of our file names
        for month in self.log_list:
            # Set flags for first period (month) and last period (month)
            self.first_period = (month == self.log_list[0])
            self.last_period = (month == self.log_list[-1])
            # Yield the file name
            yield month

    def set_rain_source(self, _data):
        """Set the Cumulus field to be used as the weeWX rain field source."""

        _row = _data.next()
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