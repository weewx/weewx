#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Services specific to weather."""

from __future__ import absolute_import
from __future__ import print_function

import logging
from configobj import ConfigObj

import weedb
import weeutil.logger
import weeutil.weeutil
import weewx.aggregate
import weewx.engine
import weewx.units
import weewx.wxformulas
import weewx.xtypes
from six.moves import StringIO
from weeutil.weeutil import to_int, to_float, to_bool, TimeSpan
from weewx.units import CtoF, mps_to_mph, kph_to_mph, METER_PER_FOOT

log = logging.getLogger(__name__)

DEFAULTS = u"""
[StdWXCalculate]
    data_binding = wx_binding
    ignore_zero_wind = True
    rain_period = 900           # Rain rate window
    retain_period = 930         # How long to retain rain events. Should be >= rain_period + archive_delay
    et_period = 3600            # For evapotranspiration
    wind_height = 2.0           # For evapotranspiration. In meters.
    atc = 0.8                   # For solar radiation RS
    nfac = 2                    # Atmospheric turbidity (2=clear, 4-5=smoggy)
    max_delta_12h = 1800        # When looking up a temperature in the past, how close does the time have to be?
    [[Calculations]]
        dewpoint = prefer_hardware
        inDewpoint = prefer_hardware
        windchill = prefer_hardware
        heatindex = prefer_hardware
        pressure = prefer_hardware
        barometer = prefer_hardware
        altimeter = prefer_hardware
        rainRate = prefer_hardware
        maxSolarRad = prefer_hardware
        cloudbase = prefer_hardware
        humidex = prefer_hardware
        appTemp = prefer_hardware
        ET = prefer_hardware
        windrun = prefer_hardware
        beaufort = prefer_hardware        
    [[Algorithms]]
        altimeter = aaASOS
        maxSolarRad = RS
"""


class StdWXCalculate(weewx.engine.StdService):
    """Wrapper class for WXCalculate.

    A StdService wrapper for a WXCalculate object so it may be called as a 
    service. This also allows the WXCalculate class to be used elsewhere 
    without the overheads of running it as a weewx service.
    """

    def __init__(self, engine, config_dict):
        """Initialize the service.

        Create a WXCalculate object and initialise our bindings.
        """
        super(StdWXCalculate, self).__init__(engine, config_dict)

        wxcalc_dict = ConfigObj(StringIO(DEFAULTS))
        wxcalc_dict.merge(config_dict)

        db_manager = engine.db_binder.get_manager(data_binding=wxcalc_dict['StdWXCalculate']['data_binding'],
                                                  initialize=True)

        self.calc = WXCalculate(wxcalc_dict['StdWXCalculate'],
                                engine.stn_info.altitude_vt,
                                engine.stn_info.latitude_f,
                                engine.stn_info.longitude_f,
                                db_manager)

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.calc.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.calc.do_calculations(event.record, 'archive')

    def shutDown(self):
        self.calc.shutDown()


class WXCalculate(object):
    """Add derived quantities to a record.

    Derived quantities should depend only on independent observations.
    They should not depend on other derived quantities.

    There is one situation where dependencies matter: pressure.  In the case
    where the hardware reports barometer, we must calculate pressure and
    altimeter.  Since altimeter depends on pressure, pressure must be
    calculated before altimeter.

    We do not handle the situation where hardware reports altimeter and
    we must calculate barometer and pressure.
    """

    def __init__(self, svc_dict, altitude_vt, latitude, longitude, db_manager):
        """Initialize the calculation service."""

        self.svc_dict = svc_dict
        self.altitude_vt = altitude_vt
        self.latitude = latitude
        self.longitude = longitude
        self.db_manager = db_manager

        # window of time for evapotranspiration calculation, in seconds
        self.et_period = to_int(svc_dict['et_period'])
        # does zero wind mean no wind direction
        self.ignore_zero_wind = to_bool(svc_dict['ignore_zero_wind'])
        # atmospheric transmission coefficient [0.7-0.91]
        self.atc = to_float(svc_dict['atc'])
        # Fail hard if out of range:
        if not 0.7 <= self.atc <= 0.91:
            raise weewx.ViolatedPrecondition("Atmospheric transmission "
                                             "coefficient (%f) out of "
                                             "range [.7-.91]" % self.atc)
        # atmospheric turbidity (2=clear, 4-5=smoggy)
        self.nfac = to_float(svc_dict['nfac'])
        # height above ground at which wind is measured, in meters
        self.wind_height = to_float(svc_dict['wind_height'])

        # Instantiate a PressureCooker to calculate various kinds of pressure
        self.pressure_cooker = weewx.wxformulas.PressureCooker(altitude_vt,
                                                               to_int(svc_dict['max_delta_12h']),
                                                               self.svc_dict['Algorithms']['altimeter'])
        # Instantiate a RainRater to calculate rainRate
        self.rain_rater = weewx.wxformulas.RainRater(to_int(svc_dict['rain_period']),
                                                     to_int(svc_dict['retain_period']),)

        # Add the various types we need to the list of extendable types
        for xt in [self.calc_maxSolarRad, self.calc_cloudbase, self.calc_ET, self.pressure_cooker.get_scalar,
                   self.rain_rater.rain_rate]:
            weewx.xtypes.scalar_types.append(xt)

        # report about which values will be calculated...
        log.info("The following values will be calculated: %s",
                 ', '.join(["%s=%s" % (k, self.svc_dict['Calculations'][k]) for k in self.svc_dict['Calculations']]))
        # ...and which algorithms will be used.
        log.info("The following algorithms will be used for calculations: %s",
                 ', '.join(["%s=%s" % (k, self.svc_dict['Algorithms'][k]) for k in self.svc_dict['Algorithms']]))

    def shutDown(self):
        # In case of shutdown, we need to remove any extensible types we added. This prevents them from
        # appearing twice in case the shutdown was really just a reload (signal HUP)
        for xt in [self.calc_maxSolarRad, self.calc_cloudbase, self.calc_ET, self.pressure_cooker.get_scalar,
                   self.rain_rater]:
            try:
                weewx.xtypes.scalar_types.remove(xt)
            except ValueError:
                pass

    def do_calculations(self, data_dict, data_type):
        """Perform the calculations.

        data_dict: The incoming LOOP packet or archive record.

        data_type: = "loop" if LOOP packet;
                   = "record" if archive record.
        """
        if self.ignore_zero_wind:
            self.adjust_winddir(data_dict)

        # Can't find a way around this hack. So be it...
        if data_type == 'loop':
            self.rain_rater.add_loop_packet(data_dict, self.db_manager)

        # Go through the list of potential calculations and see which ones need to be done
        for obs in self.svc_dict['Calculations']:
            directive = self.svc_dict['Calculations'][obs]
            if directive == 'software' \
                    or directive == 'prefer_hardware' and (obs not in data_dict or data_dict[obs] is None):
                try:
                    # We need to do a calculation for type 'obs'
                    new_value = weewx.xtypes.get_scalar(obs, data_dict, self.db_manager)
                    data_dict[obs] = new_value
                except weewx.CannotCalculate:
                    pass
                except weewx.UnknownType as e:
                    log.debug("Unknown extensible type '%s'" % e)
                except weewx.UnknownAggregation as e:
                    log.debug("Unknown aggregation '%s'" % e)

    @staticmethod
    def adjust_winddir(data):
        """If windSpeed is in the data stream, and it is either zero or None, then the wind direction is undefined."""
        if 'windSpeed' in data and not data['windSpeed']:
            data['windDir'] = None
        if 'windGust' in data and not data['windGust']:
            data['windGustDir'] = None

    def calc_maxSolarRad(self, key, data, db_manager):
        if key != 'maxSolarRad':
            raise weewx.UnknownType(key)
        algo = self.svc_dict['Algorithms'].get('maxSolarRad', 'RS').lower()
        altitude_m = weewx.units.convert(self.altitude_vt, 'meter')[0]
        if algo == 'bras':
            return weewx.wxformulas.solar_rad_Bras(self.latitude, self.longitude, altitude_m,
                                                   data['dateTime'], self.nfac)
        elif algo == 'rs':
            return weewx.wxformulas.solar_rad_RS(self.latitude, self.longitude, altitude_m,
                                                 data['dateTime'], self.atc)
        else:
            raise weewx.ViolatedPrecondition("Unknown solar algorithm '%s'"
                                             % self.svc_dict['Algorithms']['maxSolarRad'])

    def calc_cloudbase(self, key, data, db_manager):
        if key != 'cloudbase':
            raise weewx.UnknownType(key)
        if 'outTemp' not in data or 'outHumidity' not in data:
            raise weewx.CannotCalculate(key)
        # Convert altitude to the same unit system as the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, data['usUnits'])
        # Use the appropriate formula
        if data['usUnits'] == weewx.US:
            formula = weewx.wxformulas.cloudbase_US
        else:
            formula = weewx.wxformulas.cloudbase_Metric
        return formula(data['outTemp'], data['outHumidity'], altitude[0])

    def calc_ET(self, key, data, db_manager):
        """Get maximum and minimum temperatures and average radiation and
        wind speed for the indicated period then calculate the amount of
        evapotranspiration during the interval.  Convert to US units if necessary
        since this service operates in US unit system."""

        if key != 'ET':
            raise weewx.UnknownType(key)
        if 'interval' not in data:
            raise weewx.CannotCalculate(key)

        interval = data['interval']
        end_ts = data['dateTime']
        start_ts = end_ts - self.et_period
        try:
            r = db_manager.getSql("SELECT MAX(outTemp), MIN(outTemp), "
                                  "AVG(radiation), AVG(windSpeed), "
                                  "MAX(outHumidity), MIN(outHumidity), "
                                  "MAX(usUnits), MIN(usUnits) FROM %s WHERE dateTime>? AND dateTime <=?"
                                  % db_manager.table_name, (start_ts, end_ts))
        except weedb.DatabaseError:
            return None

        # Make sure everything is there:
        if r is None or None in r:
            return None

        # Unpack the results
        T_max, T_min, rad_avg, wind_avg, rh_max, rh_min, std_unit_min, std_unit_max = r

        # Check for mixed units
        if std_unit_min != std_unit_max:
            log.info("Mixed unit system not allowed in ET calculation")
            return None
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
                self.latitude, self.longitude, altitude_ft, end_ts)
        except ValueError as e:
            log.error("Calculation of evapotranspiration failed: %s", e)
            weeutil.logger.log_traceback(log.error)
            ET_rate = None
        # The formula returns inches/hour. We need the total ET over the interval, so multiply by the length of the
        # interval in hours.
        ET_inch = ET_rate * interval / 3600.0 if ET_rate is not None else None

        # Convert back to the unit system of the incoming record:
        ET = weewx.units.convertStd((ET_inch, 'inch', 'group_rain'), data['usUnits'])
        return ET

    # ********** Various simple functions to calculate extended types ************* #


def calc_dewpoint(key, data, db_manager=None):
    if key != 'dewpoint':
        raise weewx.UnknownType(key)
    if 'outTemp' not in data or 'outHumidity' not in data:
        raise weewx.CannotCalculate(key)
    formula = weewx.wxformulas.dewpointF if data['usUnits'] == weewx.US else weewx.wxformulas.dewpointC
    return formula(data['outTemp'], data['outHumidity'])


def calc_inDewpoint(key, data, db_manager=None):
    if key != 'inDewpoint':
        raise weewx.UnknownType(key)
    if 'inTemp' not in data or 'inHumidity' not in data:
        raise weewx.CannotCalculate(key)
    formula = weewx.wxformulas.dewpointF if data['usUnits'] == weewx.US else weewx.wxformulas.dewpointC
    return formula(data['inTemp'], data['inHumidity'])


def calc_windchill(key, data, db_manager=None):
    if key != 'windchill':
        raise weewx.UnknownType(key)
    if 'outTemp' not in data or 'windSpeed' not in data:
        raise weewx.CannotCalculate(key)
    formula = weewx.wxformulas.windchillF if data['usUnits'] == weewx.US else weewx.wxformulas.windchillC
    return formula(data['outTemp'], data['windSpeed'])


def calc_heatindex(key, data, db_manager=None):
    if key != 'heatindex':
        raise weewx.UnknownType(key)
    if 'outTemp' not in data or 'outHumidity' not in data:
        raise weewx.CannotCalculate(key)
    formula = weewx.wxformulas.heatindexF if data['usUnits'] == weewx.US else weewx.wxformulas.heatindexC
    return formula(data['outTemp'], data['outHumidity'])


def calc_humidex(key, data, db_manager=None):
    if key != 'humidex':
        raise weewx.UnknownType(key)
    if 'outTemp' not in data or 'outHumidity' not in data:
        raise weewx.CannotCalculate(key)
    formula = weewx.wxformulas.humidexF if data['usUnits'] == weewx.US else weewx.wxformulas.humidexC
    return formula(data['outTemp'], data['outHumidity'])


def calc_appTemp(key, data, db_manager=None):
    if key != 'appTemp':
        raise weewx.UnknownType(key)
    if 'outTemp' not in data or 'outHumidity' not in data or 'windSpeed' not in data:
        raise weewx.CannotCalculate(key)
    if data['usUnits'] == weewx.US:
        return weewx.wxformulas.apptempF(data['outTemp'], data['outHumidity'], data['windSpeed'])
    windspeed_vt = weewx.units.as_value_tuple(data, 'windSpeed')
    windspeed_mps = weewx.units.convert(windspeed_vt, 'meter_per_second')[0]
    return weewx.wxformulas.apptempC(data['outTemp'], data['outHumidity'], windspeed_mps)


def calc_beaufort(key, data, db_manager=None):
    if key != 'beaufort':
        raise weewx.UnknownType(key)
    if 'windSpeed' not in data:
        raise weewx.CannotCalculate
    windspeed_vt = weewx.units.as_value_tuple(data, 'windSpeed')
    windspeed_kn = weewx.units.convert(windspeed_vt, 'knot')[0]
    return weewx.wxformulas.beaufort(windspeed_kn)


def calc_windrun(key, data, db_manager=None):
    """Calculate wind run. Requires key 'interval'"""
    if key != 'windrun':
        raise weewx.UnknownType(key)
    if 'windSpeed' not in data or 'interval' not in data:
        raise weewx.CannotCalculate(key)

    if data['windSpeed'] is not None:
        # System METRICWX requires windrun in km. See issue #452 https://github.com/weewx/weewx/issues/452
        if data['usUnits'] == weewx.METRICWX:
            # Answer will be in km
            run = data['windSpeed'] * data['interval'] * 60.0 / 1000.0
        else:
            # Answer will be miles or km
            run = data['windSpeed'] * data['interval'] / 60.0
    else:
        run = None
    return run


# Add all the simple functions to the list of extensible types
for fn in [calc_dewpoint, calc_inDewpoint,
           calc_windchill, calc_heatindex,
           calc_humidex, calc_appTemp,
           calc_beaufort, calc_windrun]:
    weewx.xtypes.scalar_types.append(fn)
