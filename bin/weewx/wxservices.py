#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Services specific to weather."""

import syslog

import weedb
import weewx.units
import weewx.engine
import weewx.wxformulas
import weeutil.weeutil

from weewx.units import CtoF, mps_to_mph, kph_to_mph, METER_PER_FOOT

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

        self.calc = WXCalculate(config_dict, 
                                engine.stn_info.altitude_vt, 
                                engine.stn_info.latitude_f, 
                                engine.stn_info.longitude_f,
                                engine.db_binder)

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.calc.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.calc.do_calculations(event.record, 'archive')

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

    # these are the quantities that this service knows how to calculate
    _dispatch_list = [
        'pressure', # pressure must be before altimeter
        'barometer',
        'altimeter',
        'windchill',
        'heatindex',
        'dewpoint',
        'inDewpoint',
        'rainRate',
        'maxSolarRad',
        'cloudbase',
        'humidex',
        'appTemp',
#        'beaufort',
        'ET',
        'windrun',
        ]

    def __init__(self, config_dict, alt_vt, lat_f, long_f, db_binder=None):
        """Initialize the calculation service.  Sample configuration:

        [StdWXCalculate]
            data_binding = wx_binding
            ignore_zero_wind = True
            rain_period = 900           # for rain rate
            et_period = 3600            # for evapotranspiration
            wind_height = 2.0           # for evapotranspiration. In meters.
            atc = 0.8                   # for solar radiation RS
            nfac = 2                    # for solar radiation Bras
            max_delta_12h = 1800
            [[Calculations]]
                windchill = hardware
                heatindex = prefer_hardware
                dewpoint = software
                humidex = None
            [[Algorithms]]
                altimeter = aaASOS
                maxSolarRad = RS
        """
        
        # get any configuration settings
        svc_dict = config_dict.get('StdWXCalculate', {'Calculations':{}})
        # if there is no Calculations section, then make an empty one
        if not 'Calculations' in svc_dict:
            svc_dict['Calculations'] = dict()
        # database binding for any calculations that need database queries
        if db_binder is None:
            db_binder = weewx.manager.DBBinder(config_dict)
        self.db_binder = db_binder
        self.binding = svc_dict.get('data_binding', 'wx_binding')
        # window of time to measure rain rate, in seconds
        self.rain_period = int(svc_dict.get('rain_period', 900))
        # window of time for evapotranspiration calculation, in seconds
        self.et_period = int(svc_dict.get('et_period', 3600))
        # does zero wind mean no wind direction
        self.ignore_zero_wind = weeutil.weeutil.to_bool(svc_dict.get('ignore_zero_wind', True))
        # atmospheric transmission coefficient [0.7-0.91]
        self.atc = float(svc_dict.get('atc', 0.8))
        # Fail hard if out of range:
        if not 0.7 <= self.atc <= 0.91:
            raise weewx.ViolatedPrecondition("Atmospheric transmission "
                                             "coefficient (%f) out of "
                                             "range [.7-.91]" % self.atc)
        # atmospheric turbidity (2=clear, 4-5=smoggy)
        self.nfac = float(svc_dict.get('nfac', 2))

        # height above ground at which wind is measured, in meters
        self.wind_height = float(svc_dict.get('wind_height', 2.0))
        # Time window to accept a record 12 hours ago:
        self.max_delta_12h = int(svc_dict.get('max_delta_12h', 1800))
        # cache the archive interval.  nominally the interval is included in
        # each record for which calculations are being done.  however, if the
        # calculation is being done on a loop packet, there will probably be no
        # interval field in that packet.  the archive_interval is the value
        # from the last archive record encountered.  the alternative to
        # caching is to hard-fail - if a calculation depends on archive
        # interval, it would be calculated only for archive records, not
        # loop packets.  currently this applies only to pressure calculation.
        self.archive_interval = None

        self.calculations = dict()
        # Find out which calculations should be performed.
        # We recognize only the names in our dispatch list; others are ignored.
        for k in self._dispatch_list:
            x = svc_dict['Calculations'].get(k, 'prefer_hardware').lower()
            if x in ('hardware', 'software', 'prefer_hardware', 'none'):
                self.calculations[k] = x

        # determine which algorithms to use for the calculations
        self.algorithms = svc_dict.get('Algorithms', {})
        self.algorithms.setdefault('altimeter', 'aaNOAA')
        self.algorithms.setdefault('maxSolarRad', 'RS')

        # various bits we need for internal housekeeping
        self.altitude_ft = weewx.units.convert(alt_vt, "foot")[0]
        self.altitude_m = weewx.units.convert(alt_vt, "meter")[0]
        self.latitude = lat_f
        self.longitude = long_f
        self.temperature_12h_ago = None
        self.ts_12h_ago = None
        self.rain_events = []
        self.archive_rain_events = []

        # report about which values will be calculated...
        syslog.syslog(syslog.LOG_INFO, "wxcalculate: The following values will be calculated: %s" %
                      ', '.join(["%s=%s" % (k, self.calculations[k]) for k in self.calculations]))
        # ...and which algorithms will be used.
        syslog.syslog(syslog.LOG_INFO, "wxcalculate: The following algorithms will be used for calculations: %s" %
                      ', '.join(["%s=%s" % (k, self.algorithms[k]) for k in self.algorithms]))

    def do_calculations(self, data_dict, data_type):
        if self.ignore_zero_wind:
            self.adjust_winddir(data_dict)
        data_us = weewx.units.to_US(data_dict)
        for obs in self._dispatch_list:
            calc = False
            if obs in self.calculations:
                if self.calculations[obs] == 'software':
                    calc = True
                elif (self.calculations[obs] == 'prefer_hardware' and
                      (obs not in data_us or data_us[obs] is None)):
                    calc = True
            elif obs not in data_us or data_us[obs] is None:
                calc = True
            if calc:
                getattr(self, 'calc_' + obs)(data_us, data_type)
        data_x = weewx.units.to_std_system(data_us, data_dict['usUnits'])
        data_dict.update(data_x)

    def adjust_winddir(self, data):
        """If wind speed is zero, then the wind direction is undefined.
        If there is no wind speed, then there is no wind direction."""
        if 'windSpeed' in data and not data['windSpeed']:
            data['windDir'] = None
        if 'windGust' in data and not data['windGust']:
            data['windGustDir'] = None

    def calc_dewpoint(self, data, data_type):  # @UnusedVariable
        if 'outTemp' in data and 'outHumidity' in data:
            data['dewpoint'] = weewx.wxformulas.dewpointF(
                data['outTemp'], data['outHumidity'])
        else:
            data['dewpoint'] = None

    def calc_inDewpoint(self, data, data_type):  # @UnusedVariable
        data['inDewpoint'] = None
        if 'inTemp' in data and 'inHumidity' in data:
            data['inDewpoint'] = weewx.wxformulas.dewpointF(
                data['inTemp'], data['inHumidity'])

    def calc_windchill(self, data, data_type):  # @UnusedVariable
        data['windchill'] = None
        if 'outTemp' in data and 'windSpeed' in data:
            data['windchill'] = weewx.wxformulas.windchillF(
                data['outTemp'], data['windSpeed'])

    def calc_heatindex(self, data, data_type):  # @UnusedVariable
        data['heatindex'] = None
        if 'outTemp' in data and 'outHumidity' in data:
            data['heatindex'] = weewx.wxformulas.heatindexF(
                data['outTemp'], data['outHumidity'])

    def calc_pressure(self, data, data_type):  # @UnusedVariable
        interval = self._get_archive_interval(data)
        data['pressure'] = None
        if (interval is not None and 'barometer' in data and
            'outTemp' in data and 'outHumidity' in data):
            temperature_12h_ago = self._get_temperature_12h(
                data['dateTime'], interval)
            if (data['barometer'] is not None and
                data['outTemp'] is not None and
                data['outHumidity'] is not None and
                temperature_12h_ago is not None):
                data['pressure'] = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                    data['barometer'], self.altitude_ft,
                    data['outTemp'], temperature_12h_ago, data['outHumidity'])

    def calc_barometer(self, data, data_type):  # @UnusedVariable
        data['barometer'] = None
        if 'pressure' in data and 'outTemp' in data:
            data['barometer'] = weewx.wxformulas.sealevel_pressure_US(
                data['pressure'], self.altitude_ft, data['outTemp'])

    def calc_altimeter(self, data, data_type):  # @UnusedVariable
        data['altimeter'] = None
        if 'pressure' in data:
            algo = self.algorithms.get('altimeter', 'aaNOAA')
            if not algo.startswith('aa'):
                algo = 'aa%s' % algo
            data['altimeter'] = weewx.wxformulas.altimeter_pressure_US(
                data['pressure'], self.altitude_ft, algorithm=algo)

    # rainRate is simply the amount of rain in a period scaled to quantity/hr.
    # use a sliding window for the time period and the total rainfall in that
    # period for the amount of rain.  the window size is controlled by the
    # rain_period parameter.
    def calc_rainRate(self, data, data_type):
        # if this is a loop packet then cull and add to the queue
        if data_type == 'loop':
            # punt any old events from the loop event list...
            if (self.rain_events and self.rain_events[0][0] <= data['dateTime'] - self.rain_period):
                events = []
                for e in self.rain_events:
                    if e[0] > data['dateTime'] - self.rain_period:
                        events.append((e[0], e[1]))
                self.rain_events = events
            # ...then add new rain event if there is one
            if 'rain' in data and data['rain']:
                self.rain_events.append((data['dateTime'], data['rain']))
        elif data_type == 'archive':
            # punt any old events from the archive event list...
            if (self.archive_rain_events and self.archive_rain_events[0][0] <= data['dateTime'] - self.rain_period):
                events = []
                for e in self.archive_rain_events:
                    if e[0] > data['dateTime'] - self.rain_period:
                        events.append((e[0], e[1]))
                self.archive_rain_events = events
            # ...then add new rain event if there is one
            if 'rain' in data and data['rain']:
                self.archive_rain_events.append((data['dateTime'], data['rain']))
        # for both loop and archive, add up the rain...
        rainsum = 0
        if len(self.rain_events) != 0:
            # we have loop rain events so add them up
            for e in self.rain_events:
                rainsum += e[1]
        elif data_type == 'archive':
            # no loop rain events but do we have any archive rain events
            for e in self.archive_rain_events:
                rainsum += e[1]
        # ...then divide by the period and scale to an hour
        data['rainRate'] = 3600 * rainsum / self.rain_period

    def calc_maxSolarRad(self, data, data_type):  # @UnusedVariable
        algo = self.algorithms.get('maxSolarRad', 'RS')
        if algo == 'Bras':
            data['maxSolarRad'] = weewx.wxformulas.solar_rad_Bras(
                self.latitude, self.longitude, self.altitude_m,
                data['dateTime'], self.nfac)
        else:
            data['maxSolarRad'] = weewx.wxformulas.solar_rad_RS(
                self.latitude, self.longitude, self.altitude_m,
                data['dateTime'], self.atc)

    def calc_cloudbase(self, data, data_type):  # @UnusedVariable
        data['cloudbase'] = None
        if 'outTemp' in data and 'outHumidity' in data:        
            data['cloudbase'] = weewx.wxformulas.cloudbase_US(
                data['outTemp'], data['outHumidity'], self.altitude_ft)

    def calc_humidex(self, data, data_type):  # @UnusedVariable
        data['humidex'] = None
        if 'outTemp' in data and 'outHumidity' in data:
            data['humidex'] = weewx.wxformulas.humidexF(
                data['outTemp'], data['outHumidity'])

    def calc_appTemp(self, data, data_type):  # @UnusedVariable
        data['appTemp'] = None
        if 'outTemp' in data and 'outHumidity' in data and 'windSpeed' in data:
            data['appTemp'] = weewx.wxformulas.apptempF(
                data['outTemp'], data['outHumidity'], data['windSpeed'])

    def calc_beaufort(self, data, data_type):  # @UnusedVariable
        if 'windSpeed' in data:
            vt = (data['windSpeed'], "mile_per_hour", "group_speed")
            ws_kts = weewx.units.convert(vt, "knot")[0]
            data['beaufort'] = weewx.wxformulas.beaufort(ws_kts)

    def calc_ET(self, data, data_type):
        """Get maximum and minimum temperatures and average radiation and
        wind speed for the indicated period then calculate the amount of
        evapotranspiration during the interval.  Convert to US units if necessary
        since this service operates in US unit system."""
        # calculate ET only for archive packets
        if data_type != 'archive':
            return
        end_ts = data['dateTime']
        start_ts = end_ts - self.et_period
        interval = self._get_archive_interval(data)
        try:
            dbmanager = self.db_binder.get_manager(self.binding)
            r = dbmanager.getSql(
                "SELECT"
                " MAX(outTemp), MIN(outTemp), AVG(radiation), AVG(windSpeed),"
                " MAX(outHumidity), MIN(outHumidity), MAX(usUnits), MIN(usUnits)"
                " FROM %s WHERE dateTime>? AND dateTime <=?"
                % dbmanager.table_name, (start_ts, end_ts))
            # Make sure everything is there:
            if r is None or None in r:
                data['ET'] = None
                return
            # Unpack the results
            T_max, T_min, rad_avg, wind_avg, rh_max, rh_min, std_unit_min, std_unit_max = r
            # Check for mixed units
            if std_unit_min != std_unit_max:
                syslog.syslog(syslog.LOG_NOTICE, "wxservices: Mixed unit system not allowed in ET calculation")
                data['ET'] = None
                return
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

            ET_rate = weewx.wxformulas.evapotranspiration_US(T_min, T_max, 
                                                             rh_min, rh_max, 
                                                             rad_avg, wind_avg, height_ft, 
                                                             self.latitude, self.longitude, self.altitude_ft, 
                                                             end_ts)
            # The formula returns inches/hour. We need the total ET over the archive
            # interval, so multiply by the length of the archive interval in hours.
            data['ET'] = ET_rate * interval / 3600.0 if ET_rate is not None else None
        except ValueError, e:
            weeutil.weeutil.log_traceback()
            syslog.syslog(syslog.LOG_ERR, "wxservices: Calculation of evapotranspiration failed: %s" % e)
        except weedb.DatabaseError:
            pass

    def calc_windrun(self, data, data_type):
        """Calculate the wind run since the beginning of the day.  Convert to
        US if necessary since this service operates in US unit system."""
        # calculate windrun only for archive packets
        if data_type == 'loop':
            return
        ets = data['dateTime']
        sts = weeutil.weeutil.startOfDay(ets)
        try:
            run = 0.0
            dbmanager = self.db_binder.get_manager(self.binding)
            for row in dbmanager.genSql("SELECT `interval`,windSpeed,usUnits"
                                        " FROM %s"
                                        " WHERE dateTime>? AND dateTime<=?" %
                                        dbmanager.table_name, (sts, ets)):
                if row is None or None in row:
                    continue
                if row[1]:
                    inc_hours = row[0] / 60.0
                    if row[2] == weewx.METRICWX:
                        run += mps_to_mph(row[1]) * inc_hours
                    elif row[2] == weewx.METRIC:
                        run += kph_to_mph(row[1]) * inc_hours
                    else:
                        run += row[1] * inc_hours
            data['windrun'] = run
        except weedb.DatabaseError:
            pass

    def _get_archive_interval(self, data):
        if 'interval' in data and data['interval']:
            # cache the interval so it can be used for loop calculations
            self.archive_interval = data['interval'] * 60
        return self.archive_interval

    def _get_temperature_12h(self, ts, archive_interval):
        """Get the temperature from 12 hours ago.  Return None if no
        temperature is found.  Convert to US if necessary since this
        service operates in US unit system."""

        ts12 = weeutil.weeutil.startOfInterval(ts - 12 * 3600, archive_interval)

        # No need to look up the temperature if we're still in the same
        # archive interval:
        if ts12 != self.ts_12h_ago:
            # We're in a new interval. Hit the database to get the temperature
            dbmanager = self.db_binder.get_manager(self.binding)
            record = dbmanager.getRecord(ts12, max_delta=self.max_delta_12h)
            if record is None:
                # Nothing in the database. Set temperature to None.
                self.temperature_12h_ago = None
            else:
                # Convert to US if necessary:
                record_US = weewx.units.to_US(record)
                self.temperature_12h_ago = record_US['outTemp']
            # Save the timestamp
            self.ts_12h_ago = ts12

        return self.temperature_12h_ago
