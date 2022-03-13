#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""A set of XTypes extensions for calculating weather-related derived observation types."""
from __future__ import absolute_import

import logging
import threading

import weedb
import weeutil.config
import weeutil.logger
import weewx.engine
import weewx.units
import weewx.wxformulas
import weewx.xtypes
from weeutil.weeutil import to_int, to_float, to_bool
from weewx.units import ValueTuple, mps_to_mph, kph_to_mph, METER_PER_FOOT, CtoF

log = logging.getLogger(__name__)

DEFAULTS_INI = """
[StdWXCalculate]
  [[WXXTypes]]
    [[[windDir]]]
       force_null = True
    [[[maxSolarRad]]]
      algorithm = rs
      atc = 0.8
      nfac = 2
    [[[ET]]]
      wind_height = 2.0
      et_period = 3600
    [[[heatindex]]]
      algorithm = new
  [[PressureCooker]]
    max_delta_12h = 1800
    [[[altimeter]]]
      algorithm = aaASOS    # Case-sensitive!
  [[RainRater]]
    rain_period = 900
    retain_period = 930
  [[Delta]]
    [[[rain]]]
      input = totalRain
"""
defaults_dict = weeutil.config.config_from_str(DEFAULTS_INI)

first_time = True


class WXXTypes(weewx.xtypes.XType):
    """Weather extensions to the WeeWX xtype system that are relatively simple. These types
    are generally stateless, such as dewpoint, heatindex, etc. """

    def __init__(self, altitude_vt, latitude_f, longitude_f,
                 et_period=3600,
                 atc=0.8,
                 nfac=2,
                 wind_height=2.0,
                 force_null=True,
                 maxSolarRad_algo='rs',
                 heat_index_algo='new'
                 ):
        # Fail hard if out of range:
        if not 0.7 <= atc <= 0.91:
            raise weewx.ViolatedPrecondition("Atmospheric transmission coefficient (%f) "
                                             "out of range [.7-.91]" % atc)
        self.altitude_vt = altitude_vt
        self.latitude_f = latitude_f
        self.longitude_f = longitude_f
        self.et_period = et_period
        self.atc = atc
        self.nfac = nfac
        self.wind_height = wind_height
        self.force_null = force_null
        self.maxSolarRad_algo = maxSolarRad_algo.lower()
        self.heat_index_algo = heat_index_algo.lower()

    def get_scalar(self, obs_type, record, db_manager, **option_dict):
        """Invoke the proper method for the desired observation type."""
        try:
            # Form the method name, then call it with arguments
            return getattr(self, 'calc_%s' % obs_type)(obs_type, record, db_manager)
        except AttributeError:
            raise weewx.UnknownType(obs_type)

    def calc_windDir(self, key, data, db_manager):
        """ Set windDir to None if windSpeed is zero. Otherwise, raise weewx.NoCalculate. """
        if 'windSpeed' not in data \
                or not self.force_null\
                or data['windSpeed']:
            raise weewx.NoCalculate
        return ValueTuple(None, 'degree_compass', 'group_direction')

    def calc_windGustDir(self, key, data, db_manager):
        """ Set windGustDir to None if windGust is zero. Otherwise, raise weewx.NoCalculate.If"""
        if 'windGust' not in data \
                or not self.force_null\
                or data['windGust']:
            raise weewx.NoCalculate
        return ValueTuple(None, 'degree_compass', 'group_direction')

    def calc_maxSolarRad(self, key, data, db_manager):
        altitude_m = weewx.units.convert(self.altitude_vt, 'meter')[0]
        if self.maxSolarRad_algo == 'bras':
            val = weewx.wxformulas.solar_rad_Bras(self.latitude_f, self.longitude_f, altitude_m,
                                                  data['dateTime'], self.nfac)
        elif self.maxSolarRad_algo == 'rs':
            val = weewx.wxformulas.solar_rad_RS(self.latitude_f, self.longitude_f, altitude_m,
                                                data['dateTime'], self.atc)
        else:
            raise weewx.ViolatedPrecondition("Unknown solar algorithm '%s'"
                                             % self.maxSolarRad_algo)
        return ValueTuple(val, 'watt_per_meter_squared', 'group_radiation')

    def calc_cloudbase(self, key, data, db_manager):
        if 'outTemp' not in data or 'outHumidity' not in data:
            raise weewx.CannotCalculate(key)
        # Convert altitude to the same unit system as the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, data['usUnits'])
        # Use the appropriate formula
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.cloudbase_US(data['outTemp'],
                                                data['outHumidity'], altitude[0])
            u = 'foot'
        else:
            val = weewx.wxformulas.cloudbase_Metric(data['outTemp'],
                                                    data['outHumidity'], altitude[0])
            u = 'meter'
        return ValueTuple(val, u, 'group_altitude')

    def calc_ET(self, key, data, db_manager):
        """Get maximum and minimum temperatures and average radiation and wind speed for the
        indicated period then calculate the amount of evapotranspiration during the interval.
        Convert to US units if necessary since this service operates in US unit system.
        """

        if 'interval' not in data:
            # This will cause LOOP data not to be processed.
            raise weewx.CannotCalculate(key)

        interval = data['interval']
        end_ts = data['dateTime']
        start_ts = end_ts - self.et_period
        try:
            r = db_manager.getSql("SELECT MAX(outTemp), MIN(outTemp), "
                                  "AVG(radiation), AVG(windSpeed), "
                                  "MAX(outHumidity), MIN(outHumidity), "
                                  "MAX(usUnits), MIN(usUnits) FROM %s "
                                  "WHERE dateTime>? AND dateTime <=?"
                                  % db_manager.table_name, (start_ts, end_ts))
        except weedb.DatabaseError:
            return ValueTuple(None, None, None)

        # Make sure everything is there:
        if r is None or None in r:
            return ValueTuple(None, None, None)

        # Unpack the results
        T_max, T_min, rad_avg, wind_avg, rh_max, rh_min, std_unit_min, std_unit_max = r

        # Check for mixed units
        if std_unit_min != std_unit_max:
            log.info("Mixed unit system not allowed in ET calculation. Skipped.")
            return ValueTuple(None, None, None)
        std_unit = std_unit_min
        if std_unit == weewx.METRIC or std_unit == weewx.METRICWX:
            T_max = CtoF(T_max)
            T_min = CtoF(T_min)
            if std_unit == weewx.METRICWX:
                wind_avg = mps_to_mph(wind_avg)
            else:
                wind_avg = kph_to_mph(wind_avg)
        # Wind height is in meters, so convert it:
        height_ft = self.wind_height / METER_PER_FOOT
        # Get altitude in feet
        altitude_ft = weewx.units.convert(self.altitude_vt, 'foot')[0]

        try:
            ET_rate = weewx.wxformulas.evapotranspiration_US(
                T_min, T_max, rh_min, rh_max, rad_avg, wind_avg, height_ft,
                self.latitude_f, self.longitude_f, altitude_ft, end_ts)
        except ValueError as e:
            log.error("Calculation of evapotranspiration failed: %s", e)
            weeutil.logger.log_traceback(log.error)
            ET_inch = None
        else:
            # The formula returns inches/hour. We need the total ET over the interval, so multiply
            # by the length of the interval in hours. Remember that 'interval' is actually in
            # minutes.
            ET_inch = ET_rate * interval / 60.0 if ET_rate is not None else None

        # Convert back to the unit system of the incoming record:
        ET = weewx.units.convertStd((ET_inch, 'inch', 'group_rain'), data['usUnits'])
        return ET

    @staticmethod
    def calc_dewpoint(key, data, db_manager=None):
        if 'outTemp' not in data or 'outHumidity' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.dewpointF(data['outTemp'], data['outHumidity'])
            u = 'degree_F'
        else:
            val = weewx.wxformulas.dewpointC(data['outTemp'], data['outHumidity'])
            u = 'degree_C'
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    @staticmethod
    def calc_inDewpoint(key, data, db_manager=None):
        if 'inTemp' not in data or 'inHumidity' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.dewpointF(data['inTemp'], data['inHumidity'])
            u = 'degree_F'
        else:
            val = weewx.wxformulas.dewpointC(data['inTemp'], data['inHumidity'])
            u = 'degree_C'
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    @staticmethod
    def calc_windchill(key, data, db_manager=None):
        if 'outTemp' not in data or 'windSpeed' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.windchillF(data['outTemp'], data['windSpeed'])
            u = 'degree_F'
        elif data['usUnits'] == weewx.METRIC:
            val = weewx.wxformulas.windchillMetric(data['outTemp'], data['windSpeed'])
            u = 'degree_C'
        elif data['usUnits'] == weewx.METRICWX:
            val = weewx.wxformulas.windchillMetricWX(data['outTemp'], data['windSpeed'])
            u = 'degree_C'
        else:
            raise weewx.ViolatedPrecondition("Unknown unit system %s" % data['usUnits'])
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    def calc_heatindex(self, key, data, db_manager=None):
        if 'outTemp' not in data or 'outHumidity' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.heatindexF(data['outTemp'], data['outHumidity'],
                                              algorithm=self.heat_index_algo)
            u = 'degree_F'
        else:
            val = weewx.wxformulas.heatindexC(data['outTemp'], data['outHumidity'],
                                              algorithm=self.heat_index_algo)
            u = 'degree_C'
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    @staticmethod
    def calc_humidex(key, data, db_manager=None):
        if 'outTemp' not in data or 'outHumidity' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.humidexF(data['outTemp'], data['outHumidity'])
            u = 'degree_F'
        else:
            val = weewx.wxformulas.humidexC(data['outTemp'], data['outHumidity'])
            u = 'degree_C'
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    @staticmethod
    def calc_appTemp(key, data, db_manager=None):
        if 'outTemp' not in data or 'outHumidity' not in data or 'windSpeed' not in data:
            raise weewx.CannotCalculate(key)
        if data['usUnits'] == weewx.US:
            val = weewx.wxformulas.apptempF(data['outTemp'], data['outHumidity'],
                                            data['windSpeed'])
            u = 'degree_F'
        else:
            # The metric equivalent needs wind speed in mps. Convert.
            windspeed_vt = weewx.units.as_value_tuple(data, 'windSpeed')
            windspeed_mps = weewx.units.convert(windspeed_vt, 'meter_per_second')[0]
            val = weewx.wxformulas.apptempC(data['outTemp'], data['outHumidity'], windspeed_mps)
            u = 'degree_C'
        return weewx.units.convertStd((val, u, 'group_temperature'), data['usUnits'])

    @staticmethod
    def calc_beaufort(key, data, db_manager=None):
        global first_time
        if first_time:
            print("Type beaufort has been deprecated. Use unit beaufort instead.")
            log.info("Type beaufort has been deprecated. Use unit beaufort instead.")
            first_time = False
        if 'windSpeed' not in data:
            raise weewx.CannotCalculate
        windspeed_vt = weewx.units.as_value_tuple(data, 'windSpeed')
        windspeed_kn = weewx.units.convert(windspeed_vt, 'knot')[0]
        return ValueTuple(weewx.wxformulas.beaufort(windspeed_kn), None, None)

    @staticmethod
    def calc_windrun(key, data, db_manager=None):
        """Calculate wind run. Requires key 'interval'"""
        if 'windSpeed' not in data or 'interval' not in data:
            raise weewx.CannotCalculate(key)

        if data['windSpeed'] is not None:
            if data['usUnits'] == weewx.US:
                val = data['windSpeed'] * data['interval'] / 60.0
                u = 'mile'
            elif data['usUnits'] == weewx.METRIC:
                val = data['windSpeed'] * data['interval'] / 60.0
                u = 'km'
            elif data['usUnits'] == weewx.METRICWX:
                val = data['windSpeed'] * data['interval'] * 60.0 / 1000.0
                u = 'km'
            else:
                raise weewx.ViolatedPrecondition("Unknown unit system %s" % data['usUnits'])
        else:
            val = None
            u = 'mile'
        return weewx.units.convertStd((val, u, 'group_distance'), data['usUnits'])


#
# ######################## Class PressureCooker ##############################
#

class PressureCooker(weewx.xtypes.XType):
    """Pressure related extensions to the WeeWX type system. """

    def __init__(self, altitude_vt,
                 max_delta_12h=1800,
                 altimeter_algorithm='aaASOS'):

        # Algorithms can be abbreviated without the prefix 'aa':
        if not altimeter_algorithm.startswith('aa'):
            altimeter_algorithm = 'aa%s' % altimeter_algorithm

        self.altitude_vt = altitude_vt
        self.max_delta_12h = max_delta_12h
        self.altimeter_algorithm = altimeter_algorithm

        # Timestamp (roughly) 12 hours ago
        self.ts_12h = None
        # Temperature 12 hours ago as a ValueTuple
        self.temp_12h_vt = None

    def _get_temperature_12h(self, ts, dbmanager):
        """Get the temperature as a ValueTuple from 12 hours ago.  The value will
         be None if no temperature is available.
         """

        ts_12h = ts - 12 * 3600

        # Look up the temperature 12h ago if this is the first time through,
        # or we don't have a usable temperature, or the old temperature is too stale.
        if self.ts_12h is None \
                or self.temp_12h_vt is None \
                or abs(self.ts_12h - ts_12h) < self.max_delta_12h:
            # Hit the database to get a newer temperature.
            record = dbmanager.getRecord(ts_12h, max_delta=self.max_delta_12h)
            if record and 'outTemp' in record:
                # Figure out what unit the record is in ...
                unit = weewx.units.getStandardUnitType(record['usUnits'], 'outTemp')
                # ... then form a ValueTuple.
                self.temp_12h_vt = weewx.units.ValueTuple(record['outTemp'], *unit)
            else:
                # Invalidate the temperature ValueTuple from 12h ago
                self.temp_12h_vt = None
            # Save the timestamp
            self.ts_12h = ts_12h

        return self.temp_12h_vt

    def get_scalar(self, key, record, dbmanager, **option_dict):
        if key == 'pressure':
            return self.pressure(record, dbmanager)
        elif key == 'altimeter':
            return self.altimeter(record)
        elif key == 'barometer':
            return self.barometer(record)
        else:
            raise weewx.UnknownType(key)

    def pressure(self, record, dbmanager):
        """Calculate the observation type 'pressure'."""

        # All of the following keys are required:
        if any(key not in record for key in ['usUnits', 'outTemp', 'barometer', 'outHumidity']):
            raise weewx.CannotCalculate('pressure')

        # Get the temperature in Fahrenheit from 12 hours ago
        temp_12h_vt = self._get_temperature_12h(record['dateTime'], dbmanager)
        if temp_12h_vt is None \
                or temp_12h_vt[0] is None \
                or record['outTemp'] is None \
                or record['barometer'] is None \
                or record['outHumidity'] is None:
            pressure = None
        else:
            # The following requires everything to be in US Customary units.
            # Rather than convert the whole record, just convert what we need:
            record_US = weewx.units.to_US({'usUnits': record['usUnits'],
                                           'outTemp': record['outTemp'],
                                           'barometer': record['barometer'],
                                           'outHumidity': record['outHumidity']})
            # Get the altitude in feet
            altitude_ft = weewx.units.convert(self.altitude_vt, "foot")
            # The outside temperature in F.
            temp_12h_F = weewx.units.convert(temp_12h_vt, "degree_F")
            pressure = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                record_US['barometer'],
                altitude_ft[0],
                record_US['outTemp'],
                temp_12h_F[0],
                record_US['outHumidity']
            )

        # Convert to target unit system and return
        return weewx.units.convertStd((pressure, 'inHg', 'group_pressure'), record['usUnits'])

    def altimeter(self, record):
        """Calculate the observation type 'altimeter'."""
        if 'pressure' not in record:
            raise weewx.CannotCalculate('altimeter')

        # Convert altitude to same unit system of the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, record['usUnits'])

        # Figure out which altimeter formula to use, and what unit the results will be in:
        if record['usUnits'] == weewx.US:
            formula = weewx.wxformulas.altimeter_pressure_US
            u = 'inHg'
        else:
            formula = weewx.wxformulas.altimeter_pressure_Metric
            u = 'mbar'
        # Apply the formula
        altimeter = formula(record['pressure'], altitude[0], self.altimeter_algorithm)
        # Convert to the target unit system
        return weewx.units.convertStd((altimeter, u, 'group_pressure'), record['usUnits'])

    def barometer(self, record):
        """Calculate the observation type 'barometer'"""

        if 'pressure' not in record or 'outTemp' not in record:
            raise weewx.CannotCalculate('barometer')

        # Convert altitude to same unit system of the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, record['usUnits'])

        # Figure out what barometer formula to use:
        if record['usUnits'] == weewx.US:
            formula = weewx.wxformulas.sealevel_pressure_US
            u = 'inHg'
        else:
            formula = weewx.wxformulas.sealevel_pressure_Metric
            u = 'mbar'
        # Apply the formula
        barometer = formula(record['pressure'], altitude[0], record['outTemp'])
        # Convert to the target unit system:
        return weewx.units.convertStd((barometer, u, 'group_pressure'), record['usUnits'])


#
# ######################## Class RainRater ##############################
#

class RainRater(weewx.xtypes.XType):

    def __init__(self, rain_period=900, retain_period=930):

        self.rain_period = rain_period
        self.retain_period = retain_period
        # This will be a list of two-way tuples (timestamp, rain)
        self.rain_events = []
        self.unit_system = None
        self.augmented = False
        self.run_lock = threading.Lock()

    def add_loop_packet(self, packet):
        """Process LOOP packets, adding them to the list of recent rain events."""
        with self.run_lock:
            self._add_loop_packet(packet)

    def _add_loop_packet(self, packet):
        # Was there any rain? If so, convert the rain to the unit system we are using,
        # then intern it
        if 'rain' in packet and packet['rain']:
            if self.unit_system is None:
                # Adopt the unit system of the first record.
                self.unit_system = packet['usUnits']
            # Get the unit system and group of the incoming rain. In theory, this should be
            # the same as self.unit_system, but ...
            u, g = weewx.units.getStandardUnitType(packet['usUnits'], 'rain')
            # Convert to the unit system that we are using
            rain = weewx.units.convertStd((packet['rain'], u, g), self.unit_system)[0]
            # Add it to the list of rain events
            self.rain_events.append((packet['dateTime'], rain))

            # Trim any old packets:
            self.rain_events = [x for x in self.rain_events
                                if x[0] >= packet['dateTime'] - self.rain_period]

    def get_scalar(self, key, record, db_manager, **option_dict):
        """Calculate the rainRate"""
        if key != 'rainRate':
            raise weewx.UnknownType(key)

        with self.run_lock:
            # First time through, augment the event queue from the database
            if not self.augmented:
                self._setup(record['dateTime'], db_manager)
                self.augmented = True

            # Sum the rain events within the time window...
            rainsum = sum(x[1] for x in self.rain_events
                          if x[0] > record['dateTime'] - self.rain_period)
            # ...then divide by the period and scale to an hour
            val = 3600 * rainsum / self.rain_period
            # Get the unit and unit group for rainRate
            u, g = weewx.units.getStandardUnitType(self.unit_system, 'rainRate')
            # Form a ValueTuple, then convert it to the unit system of the incoming record
            rr = weewx.units.convertStd(ValueTuple(val, u, g), record['usUnits'])
            return rr

    def _setup(self, stop_ts, db_manager):
        """Initialize the rain event list"""

        # Beginning of the window
        start_ts = stop_ts - self.retain_period

        # Query the database for only the events before what we already have
        if self.rain_events:
            first_event = min(x[0] for x in self.rain_events)
            stop_ts = min(first_event, stop_ts)

        # Get all rain events since the window start from the database. Put it in
        # a 'try' block because the database may not have a 'rain' field.
        try:
            for row in db_manager.genSql("SELECT dateTime, usUnits, rain FROM %s "
                                         "WHERE dateTime>? AND dateTime<=?;"
                                         % db_manager.table_name, (start_ts, stop_ts)):
                # Unpack the row:
                time_ts, unit_system, rain = row
                # Skip the row if we already have it in rain_events
                if not any(x[0] == time_ts for x in self.rain_events):
                    self._add_loop_packet({'dateTime': time_ts,
                                           'usUnits': unit_system,
                                           'rain': rain})
        except weedb.DatabaseError as e:
            log.debug("Database error while initializing rainRate: '%s'" % e)

        # It's not strictly necessary to sort the rain event list for things to work, but it
        # makes things easier to debug
        self.rain_events.sort(key=lambda x: x[0])


#
# ######################## Class Delta ##############################
#

class Delta(weewx.xtypes.XType):
    """Derived types that are the difference between two adjacent measurements.

    For example, this is useful for calculating observation type 'rain' from a daily total,
    such as 'dayRain'. In this case, the configuration would look like:

    [StdWXCalculate]
        [[Calculations]]
            ...
        [[Delta]]
            [[[rain]]]
                input = totalRain
    """

    def __init__(self, delta_config={}):
        # The dictionary 'totals' will hold two-way lists. The first element of the list is the key
        # to be used for the cumulative value. The second element holds the previous total (None
        # to start). The result will be something like
        #   {'rain' : ['totalRain', None]}
        self.totals = {k: [delta_config[k]['input'], None] for k in delta_config}

    def get_scalar(self, key, record, db_manager, **option_dict):
        # See if we know how to handle this type
        if key not in self.totals:
            raise weewx.UnknownType(key)

        # Get the key of the type to be used for the cumulative total. This is
        # something like 'totalRain':
        total_key = self.totals[key][0]
        if total_key not in record:
            raise weewx.CannotCalculate(key)
        # Calculate the delta
        delta = weewx.wxformulas.calculate_delta(record[total_key],
                                                 self.totals[key][1],
                                                 total_key)
        # Save the new total
        self.totals[key][1] = record[total_key]

        # Get the unit and group of the key. This will be the same as for the result
        unit_and_group = weewx.units.getStandardUnitType(record['usUnits'], key)
        # ... then form and return the ValueTuple.
        delta_vt = ValueTuple(delta, *unit_and_group)

        return delta_vt


#
# ########## Services that instantiate the above XTypes extensions ##########
#

class StdWXXTypes(weewx.engine.StdService):
    """Instantiate and register the xtype extension WXXTypes."""

    def __init__(self, engine, config_dict):
        """Initialize an instance of StdWXXTypes"""
        super(StdWXXTypes, self).__init__(engine, config_dict)

        altitude_vt = engine.stn_info.altitude_vt
        latitude_f = engine.stn_info.latitude_f
        longitude_f = engine.stn_info.longitude_f

        # These options were never documented. They have moved. Fail hard if they are present.
        if 'StdWXCalculate' in config_dict \
                and any(key in config_dict['StdWXCalculate']
                        for key in ['rain_period', 'et_period', 'wind_height',
                                    'atc', 'nfac', 'max_delta_12h']):
            raise ValueError("Undocumented options for [StdWXCalculate] have moved. "
                             "See User's Guide.")

        # Get any user-defined overrides
        try:
            override_dict = config_dict['StdWXCalculate']['WXXTypes']
        except KeyError:
            override_dict = {}
        # Get the default values, then merge the user overrides into it
        option_dict = weeutil.config.deep_copy(defaults_dict['StdWXCalculate']['WXXTypes'])
        option_dict.merge(override_dict)

        # Get force_null from the option dictionary
        force_null = to_bool(option_dict['windDir'].get('force_null', True))

        # Option ignore_zero_wind has also moved, but we will support it in a backwards-compatible
        # way, provided that it doesn't conflict with any setting of force_null.
        try:
            # Is there a value for ignore_zero_wind as well?
            ignore_zero_wind = to_bool(config_dict['StdWXCalculate']['ignore_zero_wind'])
        except KeyError:
            # No. We're done
            pass
        else:
            # No exception, so there must be a value for ignore_zero_wind.
            # Is there an explicit value for 'force_null'? That is, a default was not used?
            if 'force_null' in override_dict:
                # Yes. Make sure they match
                if ignore_zero_wind != to_bool(override_dict['force_null']):
                    raise ValueError("Conflicting values for "
                                     "ignore_zero_wind (%s) and force_null (%s)"
                                     % (ignore_zero_wind, force_null))
            else:
                # No explicit value for 'force_null'. Use 'ignore_zero_wind' in its place
                force_null = ignore_zero_wind

        # maxSolarRad-related options
        maxSolarRad_algo = option_dict['maxSolarRad'].get('algorithm', 'rs').lower()
        # atmospheric transmission coefficient [0.7-0.91]
        atc = to_float(option_dict['maxSolarRad'].get('atc', 0.8))
        # atmospheric turbidity (2=clear, 4-5=smoggy)
        nfac = to_float(option_dict['maxSolarRad'].get('nfac', 2))

        # ET-related options
        # height above ground at which wind is measured, in meters
        wind_height = to_float(weeutil.config.search_up(option_dict['ET'], 'wind_height', 2.0))
        # window of time for evapotranspiration calculation, in seconds
        et_period = to_int(option_dict['ET'].get('et_period', 3600))

        # heatindex-related options
        heatindex_algo = option_dict['heatindex'].get('algorithm', 'new').lower()

        self.wxxtypes = WXXTypes(altitude_vt, latitude_f, longitude_f,
                                 et_period,
                                 atc,
                                 nfac,
                                 wind_height,
                                 force_null,
                                 maxSolarRad_algo,
                                 heatindex_algo)
        # Add to the xtypes system
        weewx.xtypes.xtypes.append(self.wxxtypes)

    def shutDown(self):
        """Engine shutting down. """
        # Remove from the XTypes system:
        weewx.xtypes.xtypes.remove(self.wxxtypes)


class StdPressureCooker(weewx.engine.StdService):
    """Instantiate and register the XTypes extension PressureCooker"""

    def __init__(self, engine, config_dict):
        """Initialize the PressureCooker. """
        super(StdPressureCooker, self).__init__(engine, config_dict)

        try:
            override_dict = config_dict['StdWXCalculate']['PressureCooker']
        except KeyError:
            override_dict = {}

        # Get the default values, then merge the user overrides into it
        option_dict = weeutil.config.deep_copy(defaults_dict['StdWXCalculate']['PressureCooker'])
        option_dict.merge(override_dict)

        max_delta_12h = to_float(option_dict.get('max_delta_12h', 1800))
        altimeter_algorithm = option_dict['altimeter'].get('algorithm', 'aaASOS')

        self.pressure_cooker = PressureCooker(engine.stn_info.altitude_vt,
                                              max_delta_12h,
                                              altimeter_algorithm)

        # Add pressure_cooker to the XTypes system
        weewx.xtypes.xtypes.append(self.pressure_cooker)

    def shutDown(self):
        """Engine shutting down. """
        weewx.xtypes.xtypes.remove(self.pressure_cooker)


class StdRainRater(weewx.engine.StdService):
    """"Instantiate and register the XTypes extension RainRater."""

    def __init__(self, engine, config_dict):
        """Initialize the RainRater."""
        super(StdRainRater, self).__init__(engine, config_dict)

        # Get any user-defined overrides
        try:
            override_dict = config_dict['StdWXCalculate']['RainRater']
        except KeyError:
            override_dict = {}

        # Get the default values, then merge the user overrides into it
        option_dict = weeutil.config.deep_copy(defaults_dict['StdWXCalculate']['RainRater'])
        option_dict.merge(override_dict)

        rain_period = to_int(option_dict.get('rain_period', 900))
        retain_period = to_int(option_dict.get('retain_period', 930))

        self.rain_rater = RainRater(rain_period, retain_period)
        # Add to the XTypes system
        weewx.xtypes.xtypes.append(self.rain_rater)

        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

    def shutDown(self):
        """Engine shutting down. """
        # Remove from the XTypes system:
        weewx.xtypes.xtypes.remove(self.rain_rater)

    def new_loop_packet(self, event):
        self.rain_rater.add_loop_packet(event.packet)


class StdDelta(weewx.engine.StdService):
    """Instantiate and register the XTypes extension Delta."""

    def __init__(self, engine, config_dict):
        super(StdDelta, self).__init__(engine, config_dict)

        # Get any user-defined overrides
        try:
            override_dict = config_dict['StdWXCalculate']['Delta']
        except KeyError:
            override_dict = {}

        # Get the default values, then merge the user overrides into it
        option_dict = weeutil.config.deep_copy(defaults_dict['StdWXCalculate']['Delta'])
        option_dict.merge(override_dict)

        self.delta = Delta(option_dict)
        weewx.xtypes.xtypes.append(self.delta)

    def shutDown(self):
        weewx.xtypes.xtypes.remove(self.delta)
