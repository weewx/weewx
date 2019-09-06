#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

"""Module to interact with Weather Underground PWS history and import raw
observational data for use with weeimport.
"""

# Python imports
from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function
import csv
import datetime
import logging
import socket
from datetime import datetime as dt

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
    """Class to interact with the Weather Underground.

    Uses WXDailyHistory.asp call via http to obtain historical daily weather
    observations for a given PWS. WU uses geolocation of the requester to
    determine the units to use when providing historical PWS records. Fields
    that can be provided with multiple possible units have the units in use
    appended to the returned field name. This means that a request for a user
    in a given location for historical data from a given station may well
    return different results to the same request being made from another
    location. This requires a mechanism to both determine the units in use from
    returned data as well as mapping a number of different possible field names
    to a given WeeWX archive field name.
    """

    # Dict to map all possible WU field names to WeeWX archive field names and
    # units
    _header_map = {'Time': {'units': 'unix_epoch', 'map_to': 'dateTime'},
                   'TemperatureC': {'units': 'degree_C', 'map_to': 'outTemp'},
                   'TemperatureF': {'units': 'degree_F', 'map_to': 'outTemp'},
                   'DewpointC': {'units': 'degree_C', 'map_to': 'dewpoint'},
                   'DewpointF': {'units': 'degree_F', 'map_to': 'dewpoint'},
                   'PressurehPa': {'units': 'hPa', 'map_to': 'barometer'},
                   'PressureIn': {'units': 'inHg', 'map_to': 'barometer'},
                   'WindDirectionDegrees': {'units': 'degree_compass',
                                            'map_to': 'windDir'},
                   'WindSpeedKMH': {'units': 'km_per_hour',
                                    'map_to': 'windSpeed'},
                   'WindSpeedMPH': {'units': 'mile_per_hour',
                                    'map_to': 'windSpeed'},
                   'WindSpeedGustKMH': {'units': 'km_per_hour',
                                        'map_to': 'windGust'},
                   'WindSpeedGustMPH': {'units': 'mile_per_hour',
                                        'map_to': 'windGust'},
                   'Humidity': {'units': 'percent', 'map_to': 'outHumidity'},
                   'dailyrainMM': {'units': 'mm', 'map_to': 'rain'},
                   'dailyrainin': {'units': 'inch', 'map_to': 'rain'},
                   'SolarRadiationWatts/m^2': {'units': 'watt_per_meter_squared',
                                               'map_to': 'radiation'}
                   }

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

        Obtain raw observational data from WU using a http WXDailyHistory
        request. This raw data needs to be cleaned of unnecessary
        characters/codes and an iterable returned.

        Since WU geolocates any http request we do not know what units our WU
        data will use until we actually receive the data. A further
        complication is that WU appends the unit abbreviation to the end of the
        returned field name for fields that can have different units. So once
        we have the data have received the response we need to determine the
        units and create a dict to map the WU fields to WeeWX archive fields.

        Input parameters:

            period: a datetime object representing the day of WU data from
                    which raw obs data will be read.
        """

        # the date for which we want the WU data is held in a datetime object,
        # we need to convert it to a timetuple
        date_tt = period.timetuple()
        # construct our URL using station ID and day, month, year
        _url = "http://www.wunderground.com/weatherstation/WXDailyHistory.asp?ID=%s&" \
               "month=%d&day=%d&year=%d&format=1" % (self.station_id,
                                                     date_tt[1],
                                                     date_tt[2],
                                                     date_tt[0])
        # hit the WU site, wrap in a try..except so we can catch any errors
        try:
            _wudata = urllib.request.urlopen(_url)
        except urllib.error.URLError as e:
            _msg = "Unable to open Weather Underground station %s" % self.station_id
            print(_msg)
            log.error(_msg)
            _msg = "   **** %s" % e
            print(_msg)
            log.error(_msg)
            raise
        except socket.timeout as e:
            _msg = "Socket timeout for Weather Underground station %s" % self.station_id
            print(_msg)
            log.error(_msg)
            _msg = "   **** %s" % e
            print(_msg)
            log.error(_msg)
            raise

        # because the data comes back with lots of HTML tags and whitespace we
        # need a bit of logic to clean it up.
        _cleanWUdata = []
        for _row in _wudata:
            # Convert from byte-string to string
            _urow = _row.decode('ascii')
            # get rid of any HTML tags
            _line = ''.join(WUSource._tags.split(_urow))
            # get rid of any blank lines
            if _line != "\n":
                # save what's left
                _cleanWUdata.append(_line)

        # now create a dictionary CSV reader, the first line is used as keys to
        # the dictionary
        _reader = csv.DictReader(_cleanWUdata)
        # finally, get our database-source mapping
        self.map = self.parseMap('WU', _reader, self.wu_config_dict)
        # return our dict reader
        return _reader

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
