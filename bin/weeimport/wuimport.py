#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

"""Module to interact with the Weather Underground API and obtain raw
observational data for use with wee_import.
"""

# Python imports
from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

import datetime
import gzip
import json
import logging
import numbers
import socket
import sys

from datetime import datetime as dt

# python3 compatibility shims
import six
from six.moves import urllib

# WeeWX imports
from . import weeimport
import weewx

from weeutil.weeutil import timestamp_to_string, option_as_list, startOfDay
from weewx.units import unit_nicknames

log = logging.getLogger(__name__)

# ============================================================================
#                             class WUSource
# ============================================================================


class WUSource(weeimport.Source):
    """Class to interact with the Weather Underground API.

    Uses PWS history call via http to obtain historical daily weather
    observations for a given PWS. Unlike the previous WU import module the use
    of the API requires an API key.
    """

    # Dict to map all possible WU field names to WeeWX archive field names and
    # units
    _header_map = {'epoch': {'units': 'unix_epoch', 'map_to': 'dateTime'},
                   'tempAvg': {'units': 'degree_F', 'map_to': 'outTemp'},
                   'dewptAvg': {'units': 'degree_F', 'map_to': 'dewpoint'},
                   'heatindexAvg': {'units': 'degree_F', 'map_to': 'heatindex'},
                   'windchillAvg': {'units': 'degree_F', 'map_to': 'windchill'},
                   'pressureAvg': {'units': 'inHg', 'map_to': 'barometer'},
                   'winddirAvg': {'units': 'degree_compass',
                                  'map_to': 'windDir'},
                   'windspeedAvg': {'units': 'mile_per_hour',
                                    'map_to': 'windSpeed'},
                   'windgustHigh': {'units': 'mile_per_hour',
                                    'map_to': 'windGust'},
                   'humidityAvg': {'units': 'percent', 'map_to': 'outHumidity'},
                   'precipTotal': {'units': 'inch', 'map_to': 'rain'},
                   'precipRate': {'units': 'inch_per_hour',
                                  'map_to': 'rainRate'},
                   'solarRadiationHigh': {'units': 'watt_per_meter_squared',
                                          'map_to': 'radiation'},
                   'uvHigh': {'units': 'uv_index', 'map_to': 'UV'}
                   }
    _extras = ['pressureMin', 'pressureMax']

    def __init__(self, config_dict, config_path, wu_config_dict, import_config_path, options):

        # call our parents __init__
        super(WUSource, self).__init__(config_dict,
                                       wu_config_dict,
                                       options)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.wu_config_dict = wu_config_dict

        # get our WU station ID
        try:
            self.station_id = wu_config_dict['station_id']
        except KeyError:
            _msg = "Weather Underground station ID not specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # get our WU API key
        try:
            self.api_key = wu_config_dict['api_key']
        except KeyError:
            _msg = "Weather Underground API key not specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # wind dir bounds
        _wind_direction = option_as_list(wu_config_dict.get('wind_direction',
                                                            '0,360'))
        try:
            if float(_wind_direction[0]) <= float(_wind_direction[1]):
                self.wind_dir = [float(_wind_direction[0]),
                                 float(_wind_direction[1])]
            else:
                self.wind_dir = [0, 360]
        except (IndexError, TypeError):
            self.wind_dir = [0, 360]

        # some properties we know because of the format of the returned WU data
        # WU returns a fixed format date-time string
        self.raw_datetime_format = '%Y-%m-%d %H:%M:%S'
        # WU only provides hourly rainfall and a daily cumulative rainfall.
        # We use the latter so force 'cumulative' for rain.
        self.rain = 'cumulative'

        # initialise our import field-to-WeeWX archive field map
        self.map = None
        # For a WU import we might have to import multiple days but we can only
        # get one day at a time from WU. So our start and end properties
        # (counters) are datetime objects and our increment is a timedelta.
        # Get datetime objects for any date or date range specified on the
        # command line, if there wasn't one then default to today.
        self.start = dt.fromtimestamp(startOfDay(self.first_ts))
        self.end = dt.fromtimestamp(startOfDay(self.last_ts))
        # set our increment
        self.increment = datetime.timedelta(days=1)

        # property holding the current period being processed
        self.period = None

        # tell the user/log what we intend to do
        _msg = "Observation history for Weather Underground station '%s' will be imported." % self.station_id
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
            _msg = "     station=%s, date=%s" % (self.station_id, options.date)
        else:
            # we must have --from and --to
            _msg = "     station=%s, from=%s, to=%s" % (self.station_id,
                                                        options.date_from,
                                                        options.date_to)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _obf_api_key_msg = '='.join(['     apiKey',
                                     '*'*(len(self.api_key) - 4) + self.api_key[-4:]])
        if self.verbose:
            print(_obf_api_key_msg)
        log.debug(_obf_api_key_msg)
        _msg = "     dry-run=%s, calc_missing=%s, ignore_invalid_data=%s" % (self.dry_run,
                                                                             self.calc_missing,
                                                                             self.ignore_invalid_data)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     tranche=%s, interval=%s, wind_direction=%s" % (self.tranche,
                                                                    self.interval,
                                                                    self.wind_dir)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "Using database binding '%s', which is bound to database '%s'" % (self.db_binding_wx,
                                                                                 self.dbm.database_name)
        print(_msg)
        log.info(_msg)
        _msg = "Destination table '%s' unit system is '%#04x' (%s)." % (self.dbm.table_name,
                                                                        self.archive_unit_sys,
                                                                        unit_nicknames[self.archive_unit_sys])
        print(_msg)
        log.info(_msg)
        if self.calc_missing:
            print("Missing derived observations will be calculated.")
        if options.date or options.date_from:
            print("Observations timestamped after %s and up to and" % timestamp_to_string(self.first_ts))
            print("including %s will be imported." % timestamp_to_string(self.last_ts))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def getRawData(self, period):
        """Get raw observation data and construct a map from WU to WeeWX
            archive fields.

        Obtain raw observational data from WU via the WU API. This raw data
        needs some basic processing to place it in a format suitable for
        wee_import to ingest.

        Input parameters:

            period: a datetime object representing the day of WU data from
                    which raw obs data will be read.
        """

        # the date for which we want the WU data is held in a datetime object,
        # we need to convert it to a timetuple
        day_tt = period.timetuple()
        # and then format the date suitable for use in the WU API URL
        day = "%4d%02d%02d" % (day_tt.tm_year,
                               day_tt.tm_mon,
                               day_tt.tm_mday)

        # construct the URL to be used
        url = "https://api.weather.com/v2/pws/history/all?" \
              "stationId=%s&format=json&units=e&numericPrecision=decimal&date=%s&apiKey=%s" \
              % (self.station_id, day, self.api_key)
        # create a Request object using the constructed URL
        request_obj = urllib.request.Request(url)
        # add necessary headers
        request_obj.add_header('Cache-Control', 'no-cache')
        request_obj.add_header('Accept-Encoding', 'gzip')
        # hit the API wrapping in a try..except to catch any errors
        try:
            response = urllib.request.urlopen(request_obj)
        except urllib.error.URLError as e:
            print("Unable to open Weather Underground station " + self.station_id, " or ", e, file=sys.stderr)
            log.error("Unable to open Weather Underground station %s or %s" % (self.station_id, e))
            raise
        except socket.timeout as e:
            print("Socket timeout for Weather Underground station " + self.station_id, file=sys.stderr)
            log.error("Socket timeout for Weather Underground station %s" % self.station_id)
            print("   **** %s" % e, file=sys.stderr)
            log.error("   **** %s" % e)
            raise
        # check the response code and raise an exception if there was an error
        if hasattr(response, 'code') and response.code != 200:
            if response.code == 204:
                _msg = "Possibly a bad station ID, an invalid date or data does not exist for this period."
            else:
                _msg = "Bad response code returned: %d." % response.code
            raise weeimport.WeeImportIOError(_msg)

        # The WU API says that compression is required, but let's be prepared
        # if compression is not used
        if response.info().get('Content-Encoding') == 'gzip':
            buf = six.BytesIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            # but what charset is in use
            try:
                char_set = response.headers.get_content_charset()
            except AttributeError:
                # must be python2
                char_set = response.headers.getparam('charset')
            # get the raw data making sure we decode the charset
            _raw_data = f.read().decode(char_set)
            # decode the json data
            _raw_decoded_data = json.loads(_raw_data)
        else:
            _raw_data = response
            # decode the json data
            _raw_decoded_data = json.load(_raw_data)

        # The raw WU response is not suitable to return as is, we need to
        # return an iterable that provides a dict of observational data for each
        # available timestamp. In this case a list of dicts is appropriate.

        # initialise a list of dicts
        wu_data = []
        # first check we have some observational data
        if 'observations' in _raw_decoded_data:
            # iterate over each record in the WU data
            for record in _raw_decoded_data['observations']:
                # initialise a dict to hold the resulting data for this record
                _flat_record = {}
                # iterate over each WU API response field that we can use
                _fields = list(self._header_map) + self._extras
                for obs in _fields:
                    # The field may appear as a top level field in the WU data
                    # or it may be embedded in the dict in the WU data that
                    # contains variable unit data. Look in the top level record
                    # first. If its there uses it, otherwise look in the
                    # variable units dict. If it can't be fond then skip it.
                    if obs in record:
                        # it's in the top level record
                        _flat_record[obs] = record[obs]
                    else:
                        # it's not in the top level so look in the variable
                        # units dict
                        try:
                            _flat_record[obs] = record['imperial'][obs]
                        except KeyError:
                            # it's not there so skip it
                            pass
                    if obs == 'epoch':
                        # An epoch timestamp could be in seconds or
                        # milliseconds, WeeWX uses seconds. We can check by
                        # trying to convert the epoch value into a datetime
                        # object, if the epoch value is in milliseconds it will
                        # fail. In that case divide the epoch value by 1000.
                        # Note we would normally expect to see a ValueError but
                        # on armhf platforms we might see an OverflowError.
                        try:
                            _date = datetime.date.fromtimestamp(_flat_record['epoch'])
                        except (ValueError, OverflowError):
                            _flat_record['epoch'] = _flat_record['epoch'] // 1000
                # WU in its wisdom provides min and max pressure but no average
                # pressure (unlike other obs) so we need to calculate it. If
                # both min and max are numeric use a simple average of the two
                # (they will likely be the same anyway for non-RF stations).
                # Otherwise use max if numeric, then use min if numeric
                # otherwise skip.
                self.calc_pressure(_flat_record)
                # append the data dict for the current record to the list of
                # dicts for this period
                wu_data.append(_flat_record)
        # finally, get our database-source mapping
        self.map = self.parseMap('WU', wu_data, self.wu_config_dict)
        # return our dict
        return wu_data

    @staticmethod
    def calc_pressure(record):
        """Calculate pressureAvg field.

        The WU API provides min and max pressure but no average pressure.
        Calculate an average pressure to be used in the import using one of the
        following (in order):

        1. simple average of min and max pressure
        2. max pressure
        3. min pressure
        4. None
        """

        if 'pressureMin' in record and 'pressureMax' in record and isinstance(record['pressureMin'], numbers.Number) and isinstance(record['pressureMax'], numbers.Number):
            record['pressureAvg'] = (record['pressureMin'] + record['pressureMax'])/2.0
        elif 'pressureMax' in record and isinstance(record['pressureMax'], numbers.Number):
            record['pressureAvg'] = record['pressureMax']
        elif 'pressureMin' in record and isinstance(record['pressureMin'], numbers.Number):
            record['pressureAvg'] = record['pressureMin']
        elif 'pressureMin' in record or 'pressureMax' in record:
            record['pressureAvg'] = None

    def period_generator(self):
        """Generator function yielding a sequence of datetime objects.

        This generator controls the FOR statement in the parents run() method
        that loops over the WU days to be imported. The generator yields a
        datetime object from the range of dates to be imported."""

        self.period = self.start
        while self.period <= self.end:
            yield self.period
            self.period += self.increment

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

         Return True if the current file name being processed is the first in
         the list or it is None (the initialisation value).
         """

        return self.period == self.start if self.period is not None else True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

         Return True if the current period being processed is >= the end of the
         WU import period. Return False if the current period is None (the
         initialisation value).
         """

        return self.period >= self.end if self.period is not None else False
