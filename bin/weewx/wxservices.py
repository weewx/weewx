#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
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


class StdWXCalculate(weewx.engine.StdService):
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

    def __init__(self, engine, config_dict):
        """Initialize the calculation service.  Sample configuration:

        [StdWXCalculate]
            ignore_zero_wind = True
            rain_period = 900           # for rain rate
            et_period = 3600            # for evapotranspiration
            wind_height = 2.0           # for evapotranspiration
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
        super(StdWXCalculate, self).__init__(engine, config_dict)

        # get any configuration settings
        svc_dict = config_dict.get('StdWXCalculate', {})
        # window of time to measure rain rate, in seconds
        self.rain_period = int(svc_dict.get('rain_period', 900))
        # window of time for evapotranspiration calculation, in seconds
        self.et_period = int(svc_dict.get('et_period', 3600))
        # does zero wind mean no wind direction
        self.ignore_zero_wind = weeutil.weeutil.to_bool(svc_dict.get('ignore_zero_wind', True))
        # atmospheric transmission coefficient [0.7-0.91]
        self.atc = float(svc_dict.get('atc', 0.8))
        if self.atc < 0.7:
            self.atc = 0.7
        elif self.atc > 0.91:
            self.atc = 0.91
        # height above ground at which wind is measured, in meters
        self.wind_height = float(svc_dict.get('wind_height', 2.0))
        # Time window to accept a record 12 hours ago:
        self.max_delta_12h = int(svc_dict.get('max_delta_12h', 1800))

        # find out which calculations should be performed
        self.calculations = dict()
        # look in the 'Calculations' stanza. if no 'Calculations' stanza, then
        # look directly in the service stanza.
        where_to_look = svc_dict.get('Calculations', svc_dict)
        # we recognize only the names in our dispatch list; others are ignored
        for v in self._dispatch_list:
            x = where_to_look.get(v, 'prefer_hardware')
            if x in ('hardware', 'software', 'prefer_hardware'):
                self.calculations[v] = x

        # determine which algorithms to use for the calculations
        self.algorithms = svc_dict.get('Algorithms', {})
        self.algorithms.setdefault('altimeter', 'aaNOAA')
        self.algorithms.setdefault('maxSolarRad', 'RS')

        # various bits we need for internal housekeeping
        self.altitude_ft = weewx.units.convert(
            engine.stn_info.altitude_vt, "foot")[0]
        self.altitude_m = weewx.units.convert(
            engine.stn_info.altitude_vt, "meter")[0]
        self.latitude = engine.stn_info.latitude_f
        self.longitude = engine.stn_info.longitude_f
        self.temperature_12h_ago = None
        self.ts_12h_ago = None
        self.archive_interval = None
        self.rain_events = []

        # report about which values will be calculated...
        syslog.syslog(syslog.LOG_INFO, "wxcalculate: The following values will be calculated: %s" % ','.join(["%s=%s" % (k, self.calculations[k]) for k in self.calculations]))
        # ...and which algorithms will be used.
        syslog.syslog(syslog.LOG_INFO, "wxcalculate: The following algorithms will be used for calculations: %s" % ','.join(["%s=%s" % (k, self.algorithms[k]) for k in self.algorithms]))

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.do_calculations(event.record, 'archive')

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
                getattr(self, 'calc_'+obs)(data_us, data_type)
        data_x = weewx.units.to_std_system(data_us, data_dict['usUnits'])
        data_dict.update(data_x)

    def adjust_winddir(self, data):
        """If there is no wind speed, then the wind direction is undefined."""
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
        if 'inTemp' in data and 'inHumidity' in data:
            data['inDewpoint'] = weewx.wxformulas.dewpointF(
                data['inTemp'], data['inHumidity'])
        else:
            data['inDewpoint'] = None

    def calc_windchill(self, data, data_type):  # @UnusedVariable
        if 'outTemp' in data and 'windSpeed' in data:
            data['windchill'] = weewx.wxformulas.windchillF(
                data['outTemp'], data['windSpeed'])
        else:
            data['windchill'] = None

    def calc_heatindex(self, data, data_type):  # @UnusedVariable
        if 'outTemp' in data and 'outHumidity' in data:
            data['heatindex'] = weewx.wxformulas.heatindexF(
                data['outTemp'], data['outHumidity'])
        else:
            data['heatindex'] = None

    def calc_pressure(self, data, data_type):  # @UnusedVariable
        self._get_archive_interval(data)
        if (self.archive_interval is not None and 'barometer' in data and
            'outTemp' in data and 'outHumidity' in data):
            temperature_12h_ago = self._get_temperature_12h(data['dateTime'], self.archive_interval)
            if (data['barometer'] is not None and
                data['outTemp'] is not None and
                data['outHumidity'] is not None and
                temperature_12h_ago is not None):
                data['pressure'] = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                    data['barometer'], self.altitude_ft,
                    data['outTemp'], temperature_12h_ago, data['outHumidity'])
            else:
                data['pressure'] = None

    def calc_barometer(self, data, data_type):  # @UnusedVariable
        if 'pressure' in data and 'outTemp' in data:
            data['barometer'] = weewx.wxformulas.sealevel_pressure_US(
                data['pressure'], self.altitude_ft, data['outTemp'])
        else:
            data['barometer'] = None

    def calc_altimeter(self, data, data_type):  # @UnusedVariable
        if 'pressure' in data:
            algo = self.algorithms.get('altimeter', 'aaNOAA')
            if not algo.startswith('aa'):
                algo = 'aa%s' % algo
            data['altimeter'] = weewx.wxformulas.altimeter_pressure_US(
                data['pressure'], self.altitude_ft, algorithm=algo)
        else:
            data['altimeter'] = None

    # rainRate is simply the amount of rain in a period scaled to quantity/hr.
    # use a sliding window for the time period and the total rainfall in that
    # period for the amount of rain.  the window size is controlled by the
    # rain_period parameter.
    def calc_rainRate(self, data, data_type):
        # if this is a loop packet then cull and add to the queue
        if data_type == 'loop':
            events = []
            for e in self.rain_events:
                if e[0] > data['dateTime'] - self.rain_period:
                    events.append((e[0], e[1]))
            if 'rain' in data and data['rain']:
                events.append((data['dateTime'], data['rain']))
            self.rain_events = events
        # for both loop and archive, add up the rain...
        rainsum = 0
        for e in self.rain_events:
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
        if 'outTemp' in data and 'outHumidity' in data:        
            data['cloudbase'] = weewx.wxformulas.cloudbase_US(
                data['outTemp'], data['outHumidity'], self.altitude_ft)
        else:
            data['cloudbase'] = None

    def calc_humidex(self, data, data_type):  # @UnusedVariable
        if 'outTemp' in data and 'outHumidity' in data:
            data['humidex'] = weewx.wxformulas.humidexF(
                data['outTemp'], data['outHumidity'])
        else:
            data['humidex'] = None

    def calc_appTemp(self, data, data_type):  # @UnusedVariable
        if 'outTemp' in data and 'outHumidity' in data and 'windSpeed' in data:
            data['appTemp'] = weewx.wxformulas.apptempF(
                data['outTemp'], data['outHumidity'], data['windSpeed'])
        else:
            data['appTemp'] = None

    def calc_beaufort(self, data, data_type):  # @UnusedVariable
        if 'windSpeed' in data:
            vt = (data['windSpeed'], "mile_per_hour", "group_speed")
            ws_kts = weewx.units.convert(vt, "knot")[0]
            data['beaufort'] = weewx.wxformulas.beaufort(ws_kts)

    def calc_ET(self, data, data_type):
        """Get maximum and minimum temperatures and average radiation and
        wind speed for the indicated period then calculate the
        evapotranspiration.  Convert to US units if necessary
        since this service operates in US unit system."""
        # calculate ET only for archive packets
        if data_type == 'loop':
            return
        end_ts = data['dateTime']
        start_ts = end_ts - self.et_period
        try:
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
            r = dbmanager.getSql(
                "SELECT"
                " MAX(outTemp),MIN(outTemp),AVG(radiation),AVG(windSpeed),usUnits"
                " FROM %s WHERE dateTime>? AND dateTime <=?"
                % dbmanager.table_name, (start_ts, end_ts))
            if r is None or None in r:
                data['ET'] = None
            else:
                T_max, T_min, rad_avg, wind_avg, std_unit = r
                if std_unit == weewx.METRIC or std_unit == weewx.METRICWX:
                    T_max = weewx.wxformulas.CtoF(T_max)
                    T_min = weewx.wxformulas.CtoF(T_min)
                    if std_unit == weewx.METRICWX:
                        wind_avg = weewx.wxformulas.mps_to_mph(wind_avg)
                    else:
                        wind_avg = weewx.wxformulas.kph_to_mph(wind_avg)
                data['ET'] = weewx.wxformulas.evapotranspiration_US(
                    T_max, T_min, rad_avg, wind_avg,
                    self.wind_height, self.latitude,
                    data['dateTime'])
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
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
            for row in dbmanager.genSql("SELECT `interval`,windSpeed,usUnits"
                                        " FROM %s"
                                        " WHERE dateTime>? AND dateTime<=?" %
                                        dbmanager.table_name, (sts, ets)):
                if row is None or None in row:
                    continue
                if row[1]:
                    inc_hours = row[0] / 60.0
                    if row[2] == weewx.METRICWX:
                        run += weewx.wxformulas.mps_to_mph(row[1]) * inc_hours
                    elif row[2] == weewx.METRIC:
                        run += weewx.wxformulas.kph_to_mph(row[1]) * inc_hours
                    else:
                        run += row[1] * inc_hours
            data['windrun'] = run
        except weedb.DatabaseError:
            pass

    def _get_archive_interval(self, data):
        if 'interval' in data and self.archive_interval != data['interval'] * 60:
            self.archive_interval = data['interval'] * 60

    def _get_temperature_12h(self, ts, archive_interval):
        """Get the temperature from 12 hours ago.  Return None if no
        temperature is found.  Convert to US if necessary since this
        service operates in US unit system."""

        ts12 = weeutil.weeutil.startOfInterval(ts - 12*3600, archive_interval)

        # No need to look up the temperature if we're still in the same
        # archive interval:
        if ts12 != self.ts_12h_ago:
            # We're in a new interval. Hit the database to get the temperature
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
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
