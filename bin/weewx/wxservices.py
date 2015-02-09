#
#    Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#

"""Services specific to weather."""

import weedb
import weewx
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
        'maxsolarrad',
        'cloudbase',
        'humidex',
        'apptemp',
#        'beaufort',
        'ET',
        'windrun',
        ]

    def __init__(self, engine, config_dict):
        super(StdWXCalculate, self).__init__(engine, config_dict)

        # get any configuration settings
        d = config_dict.get('StdWXCalculate', {})
        # window of time to measure rain rate, in seconds
        self.rain_period = int(d.get('rain_period', 900))
        # window of time for evapotranspiration calculation, in seconds
        self.et_period = int(d.get('et_period', 3600))
        # does zero wind mean no wind direction
        self.ignore_zero_wind = weeutil.weeutil.to_bool(d.get('ignore_zero_wind', True))
        # atmospheric transmission coefficient [0.7-0.91]
        self.atc = float(d.get('atc', 0.8))
        if self.atc < 0.7:
            self.atc = 0.7
        if self.atc > 0.91:
            self.atc = 0.91
        # height above ground at which wind is measured, in meters
        self.wind_height = float(d.get('wind_height', 2.0))

        # find out which calculations should be performed
        # FIXME: these probably belong in a sub-section [[Calculations]]
        self.calculations = dict()
        for v in self._dispatch_list:
            self.calculations[v] = d.get(v, 'prefer_hardware')

        # various bits we need for internal housekeeping
        self.altitude_ft = weewx.units.convert(engine.stn_info.altitude_vt, "foot")[0]
        self.altitude_m = weewx.units.convert(engine.stn_info.altitude_vt, "meter")[0]
        self.latitude = engine.stn_info.latitude_f
        self.longitude = engine.stn_info.longitude_f
        self.t12 = None
        self.last_ts12 = None
        self.arcint = None
        self.rain_events = []

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

    def calc_dewpoint(self, data, data_type):
        if 'outTemp' in data and 'outHumidity' in data:
            data['dewpoint'] = weewx.wxformulas.dewpointF(
                data['outTemp'], data['outHumidity'])

    def calc_inDewpoint(self, data, data_type):
        if 'inTemp' in data and 'inHumidity' in data:
            data['inDewpoint'] = weewx.wxformulas.dewpointF(
                data['inTemp'], data['inHumidity'])

    def calc_windchill(self, data, data_type):
        if 'outTemp' in data and 'windSpeed' in data:
            data['windchill'] = weewx.wxformulas.windchillF(
                data['outTemp'], data['windSpeed'])

    def calc_heatindex(self, data, data_type):
        if 'outTemp' in data and 'outHumidity' in data:
            data['heatindex'] = weewx.wxformulas.heatindexF(
                data['outTemp'], data['outHumidity'])

    def calc_pressure(self, data, data_type):
        self._get_arcint(data)
        if (self.arcint is not None and 'barometer' in data and
            'outTemp' in data and 'outHumidity' in data):
            t12 = self._get_temperature_12h(data['dateTime'], self.arcint)
            if (data['barometer'] is not None and
                data['outTemp'] is not None and
                data['outHumidity'] is not None and
                t12 is not None):
                data['pressure'] = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                    data['barometer'], self.altitude_ft,
                    data['outTemp'], t12, data['outHumidity'])
            else:
                data['pressure'] = None

    def calc_barometer(self, data, data_type):
        if 'pressure' in data and 'outTemp' in data:
            data['barometer'] = weewx.wxformulas.sealevel_pressure_US(
                data['pressure'], self.altitude_ft, data['outTemp'])

    def calc_altimeter(self, data, data_type):
        if 'pressure' in data:
            data['altimeter'] = weewx.wxformulas.altimeter_pressure_US(
                data['pressure'], self.altitude_ft, algorithm='aaNOAA')

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

    def calc_maxsolarrad(self, data, data_type):
        data['maxsolarrad'] = weewx.wxformulas.solar_rad_RS(
            self.latitude, self.longitude, self.altitude_m, data['dateTime'],
            self.atc)

    def calc_cloudbase(self, data, data_type):
        if 'outTemp' in data and 'outHumidity' in data:        
            data['cloudbase'] = weewx.wxformulas.cloudbase_US(
                data['outTemp'], data['outHumidity'], self.altitude_ft)

    def calc_humidex(self, data, data_type):
        if 'outTemp' in data and 'outHumidity' in data:
            data['humidex'] = weewx.wxformulas.humidexF(
                data['outTemp'], data['outHumidity'])

    def calc_apptemp(self, data, data_type):
        if 'outTemp' in data and 'outHumidity' in data and 'windSpeed' in data:
            data['apptemp'] = weewx.wxformulas.apptempF(
                data['outTemp'], data['outHumidity'], data['windSpeed'])

#    def calc_beaufort(self, data, data_type):
#        if 'windSpeed' in data:
#            vt = (data['windSpeed'], "mile_per_hour", "group_speed")
#            ws_kts = weewx.units.convert(vt, "knot")[0]
#            data['beaufort'] = weewx.wxformulas.beaufort(ws_kts)

    def calc_ET(self, data, data_type):
        """Get maximum and minimum temperatures and average radiation and
        wind speed for the indicated period then calculate the
        evapotranspiration.  Convert to US units if necessary
        since this service operates in US unit system."""
        # calculate ET only for archive packets
        if data_type == 'loop':
            return
        ets = data['dateTime']
        sts = ets - self.et_period
        try:
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
            r = dbmanager.getSql(
                "SELECT"
                " MAX(outTemp),MIN(outTemp),AVG(radiation),AVG(windSpeed),usUnits"
                " FROM %s WHERE dateTime>? AND dateTime <=?"
                % dbmanager.table_name, (sts, ets))
            if r[4] == weewx.METRIC or r[4] == weewx.METRICWX:
                r[0] = weewx.wxformulas.CtoF(r[0])
                r[1] = weewx.wxformulas.CtoF(r[1])
                if r[4] == weewx.METRICWX:
                    r[3] = weewx.wxformulas.mps_to_mph(r[3])
                else:
                    r[3] = weewx.wxformulas.kph_to_mph(r[3])
            data['ET'] = weewx.wxformulas.evapotranspiration_US(
                r[0], r[1], r[2], r[3], self.wind_height, self.latitude,
                data['dateTime'])
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
                if row[1]:
                    inc = row[0] / 60.0
                    if row[2] == weewx.METRICWX:
                        run += weewx.wxformulas.mps_to_mph(row[1]) * inc
                    elif row[2] == weewx.METRIC:
                        run += weewx.wxformulas.kph_to_mph(row[1]) * inc
                    else:
                        run += row[1] * inc
            data['windrun'] = run
        except weedb.DatabaseError, e:
            pass

    def _get_arcint(self, data):
        if 'interval' in data and self.arcint != data['interval'] * 60:
            self.arcint = data['interval'] * 60

    def _get_temperature_12h(self, ts, arcint):
        """Get the temperature from 12 hours ago.  Return None if no
        temperature is found.  Convert to US if necessary since this
        service operates in US unit system."""
        ts12 = weeutil.weeutil.startOfInterval(ts - 12*3600, arcint)
        if ts12 != self.last_ts12:
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
            r = dbmanager.getRecord(ts12)
            t = None
            if r is not None:
                t = r.get('outTemp')
                if t is not None and r.get('usUnits') != weewx.US:
                    t = weewx.wxformulas.CtoF(t)
            self.t12 = t
            self.last_ts12 = ts12
        return self.t12
