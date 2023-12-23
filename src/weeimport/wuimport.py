#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

"""Module to interact with the Weather Underground API and obtain raw
observational data for use with wee_import.
"""

# Python imports
import datetime
import gzip
import io
import json
import logging
import numbers
import socket
import sys
import urllib.error
import urllib.request

# WeeWX imports
import weewx
from weeutil.weeutil import timestamp_to_string, option_as_list, startOfDay
from weewx.units import unit_nicknames
from . import weeimport

log = logging.getLogger(__name__)


# ============================================================================
#                             class WUSource
# ============================================================================

class WUSource(weeimport.Source):
    """Class to interact with the Weather Underground API.

    Uses the WU PWS history API call via http to obtain historical weather
    observations for a given PWS. Unlike the previous WU import module that
    was based on an earlier API, the use of the v2 API requires an API key.

    The Weather Company PWS historical data API v2 documentation:
    https://docs.google.com/document/d/1w8jbqfAk0tfZS5P7hYnar1JiitM0gQZB-clxDfG3aD0/edit
    """

    # Dict containing default mapping of WU fields to WeeWX archive fields.
    # This mapping may be replaced or modified by including a [[FieldMap]]
    # and/or [[FieldMapExtensions]] stanza in the import config file. Note that
    # Any unit settings in the [[FieldMap]] and/or [[FieldMapExtensions]]
    # stanza in the WU import config file are ignored as the WU API returns
    # data using a specified set of units. These units are set by weectl import
    # and cannot be set by the user (nor do they need to be set by the user).
    # Any necessary unit conversions are performed by weectl import before data
    # is saved to database.
    default_map = {
        'dateTime': {
            'source_field': 'epoch', 
            'unit': 'unix_epoch'},
        'outTemp': {
            'source_field': 'tempAvg', 
            'unit': 'degree_F'},
        'outHumidity': {
            'source_field': 'humidityAvg', 
            'unit': 'percent'},
        'dewpoint': {
            'source_field': 'dewptAvg', 
            'unit': 'degree_F'},
        'heatindex': {
            'source_field': 'heatindexAvg', 
            'unit': 'degree_F'},
        'windchill': {
            'source_field': 'windchillAvg', 
            'unit': 'degree_F'},
        'barometer': {
            'source_field': 'pressureAvg', 
            'unit': 'inHg'},
        'rain': {
            'source_field': 'precipTotal', 
            'unit': 'inch', 
            'is_cumulative': True},
        'rainRate': {
            'source_field': 'precipRate', 
            'unit': 'inch_per_hour'},
        'windSpeed': {
            'source_field': 'windspeedAvg', 
            'unit': 'mile_per_hour'},
        'windDir': {
            'source_field': 'winddirAvg', 
            'unit': 'degree_compass'},
        'windGust': {
            'source_field': 'windgustHigh', 
            'unit': 'mile_per_hour'},
        'radiation': {
            'source_field': 'solarRadiationHigh', 
            'unit': 'watt_per_meter_squared'},
        'UV': {
            'source_field': 'uvHigh',
            'unit': 'uv_index'}
    }
    # additional fields required for (in this case) calculation of barometer
    _extra_fields = ['pressureMin', 'pressureMax']

    def __init__(self, config_path, config_dict, import_config_path,
                 wu_config_dict, **kwargs):

        # call our parents __init__
        super().__init__(config_dict, wu_config_dict, **kwargs)

        # save our import config path
        self.import_config_path = import_config_path
        # save our import config dict
        self.wu_config_dict = wu_config_dict

        # get the WU station ID
        try:
            self.station_id = wu_config_dict['station_id']
        except KeyError:
            _msg = "Weather Underground station ID not specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # get the WU API key
        try:
            self.api_key = wu_config_dict['api_key']
        except KeyError:
            _msg = "Weather Underground API key not specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # Is our rain discrete or cumulative. Legacy import config files used
        # the 'rain' config option to determine whether the imported rainfall
        # value was a discrete per period value or a cumulative value. This is
        # now handled on a per-field basis through the field map; however, we
        # need ot be able to support old import config files that use the
        # legacy rain config option.
        _rain = self.wu_config_dict.get('rain')
        # set our rain property only if the rain config option was explicitly
        # set
        if _rain is not None:
            self.rain = _rain

        # wind direction bounds
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

        # construct our import field-to-WeeWX archive field map
        _default_map = dict(WUSource.default_map)
        # create the final field map based on the default field map and any
        # field map options provided by the user
        _map = self.parse_map(_default_map,
                              self.wu_config_dict.get('FieldMap', {}),
                              self.wu_config_dict.get('FieldMapExtensions', {}))
        # The field map we have now may either include no source field unit
        # settings (the import config file instructions ask that a simplified
        # field map (ie containing source_field only) be specified) or the user
        # may have specified their own possibly inappropriate source field unit
        # settings. The WU data obtained by weectl import is provided using
        # what WU calls 'imperial (english)' units. Accordingly, we need to
        # either add or update the unit setting for each source field to ensure
        # the correct units are specified. To do this we iterate over each
        # field map entry and set/update the unit setting to the unit setting
        # for the corresponding source field in the default field map.

        # first make a copy of the field map as we will likely be changing it
        _map_copy = dict(_map)
        # iterate over the current field map entries
        for w_field, s_config in _map_copy.items():
            # obtain the source field for the current entry
            source_field = s_config['source_field']
            # find source_field in the default field map and obtain the
            # corresponding unit setting
            # first set _unit to None so we know if we found an entry
            _unit = None
            # now iterate over the entries in the default field map looking for
            # the source field we are currently using
            for _field, _config in WUSource.default_map.items():
                # do we have a match
                if _config['source_field'] == source_field:
                    # we have a match, obtain the unit setting and exit the
                    # loop
                    _unit = _config['unit']
                    break
            # we have finished iterating over the default field map, did we
            # find a match
            if _unit is not None:
                # we found a match so update our current map
                _map[w_field]['unit'] = _unit
            else:
                # We did not find a match so we don't know what unit this
                # source field uses, most likely a [[FieldMap]] error but it
                # could be something else. Either way we cannot continue, raise
                # a suitable exception.
                msg = f"Invalid field map. Could not find 'unit' "\
                      f"for source field '{source_field}'"
                raise weeimport.WeeImportMapError(msg)
        # save the updated map
        self.map = _map

        # For a WU import we might have to import multiple days but we can only
        # get one day at a time from WU. So our start and end properties
        # (counters) are datetime objects and our increment is a timedelta.
        # Get datetime objects for any date or date range specified on the
        # command line, if there wasn't one then default to today.
        self.start = datetime.datetime.fromtimestamp(startOfDay(self.first_ts))
        self.end = datetime.datetime.fromtimestamp(startOfDay(self.last_ts))
        # set our increment
        self.increment = datetime.timedelta(days=1)

        # property holding the current period being processed
        self.period = None

        # property holding dict of last seen values for cumulative observations
        self.last_values = {}

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
        if kwargs['date']:
            _msg = "     station=%s, date=%s" % (self.station_id, kwargs['date'])
        else:
            # we must have --from and --to
            _msg = "     station=%s, from=%s, to=%s" % (self.station_id,
                                                        kwargs['from_datetime'],
                                                        kwargs['to_datetime'])
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
        self.print_map()
        if self.calc_missing:
            print("Missing derived observations will be calculated.")
        if kwargs['date'] or kwargs['from_datetime']:
            print("Observations timestamped after %s and up to and" % timestamp_to_string(self.first_ts))
            print("including %s will be imported." % timestamp_to_string(self.last_ts))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def get_raw_data(self, period):
        """Get raw observation data for a WU PWS for a given period.

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
            buf = io.BytesIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            # but what charset is in use
            char_set = response.headers.get_content_charset()
            # get the raw data making sure we decode the charset if required
            if char_set is not None:
                _raw_data = f.read().decode(char_set)
            else:
                _raw_data = f.read()
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
                _fields = [c['source_field'] for c in self.map.values()] + self._extra_fields
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
