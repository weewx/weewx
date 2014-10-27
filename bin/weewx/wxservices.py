# $Id$
# Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
"""Services specific to weather."""

from __future__ import with_statement
import syslog
import weewx
import weewx.archive
import weewx.units
import weewx.engine
import weewx.wxformulas
import weeutil.weeutil

INHG_PER_MBAR = 33.863886666
KPH_PER_MPS = 3.6
FOOT_TO_METER = 0.3048

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
    _DERIVED = [
        'pressure', # pressure must be before altimeter
        'barometer',
        'altimeter',
        'windchill',
        'heatindex',
        'dewpoint',
        'inDewpoint',
        'rainRate',
        ]

    def __init__(self, engine, config_dict):
        super(StdWXCalculate, self).__init__(engine, config_dict)

        # get any configuration settings
        self.calculations = {}
        d = config_dict.get('StdWXCalculate', {})
        for obs in d:
            self.calculations[obs] = d[obs]

        # various bits we need for internal housekeeping
        self.altitude_ft = weewx.units.getAltitudeFt(config_dict)
        self.t12 = None
        self.last_ts12 = None
        self.arcint = None
        self.last_rain_ts = None
        self.rain_period = 1800 # 15 minute period for rain calculation
        self.config_dict = config_dict

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.do_calculations(event.record)

    def do_calculations(self, data_dict, data_type='archive'):
        for obs in self._DERIVED:
            calc = False
            if obs in self.calculations:
                if self.calculations[obs] == 'software':
                    calc = True
                elif (self.calculations[obs] == 'prefer_hardware' and
                      (obs not in data_dict or data_dict[obs] is None)):
                    calc = True
            elif obs not in data_dict or data_dict[obs] is None:
                calc = True
            if calc:
                self.calculate(obs, data_dict, data_type)

    def calculate(self, obs, data, data_type):
        if obs == 'dewpoint':
            if 'outTemp' in data and 'outHumidity' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.dewpointF(
                        data['outTemp'], data['outHumidity'])
                else:
                    data[obs] = weewx.wxformulas.dewpointC(
                        data['outTemp'], data['outHumidity'])
        elif obs == 'inDewpoint':
            if 'outTemp' in data and 'inHumidity' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.dewpointF(
                        data['outTemp'], data['inHumidity'])
                else:
                    data[obs] = weewx.wxformulas.dewpointC(
                        data['outTemp'], data['inHumidity'])
        elif obs == 'windchill':
            if 'outTemp' in data and 'windSpeed' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.windchillF(
                        data['outTemp'], data['windSpeed'])
                else:
                    if data['usUnits'] == weewx.METRICWX:
                        ws = data['windSpeed'] * KPH_PER_MPS
                    else:
                        ws = data['windSpeed']
                    data[obs] = weewx.wxformulas.windchillC(
                        data['outTemp'], ws)
        elif obs == 'heatindex':
            if 'outTemp' in data and 'outHumidity' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.heatindexF(
                        data['outTemp'], data['outHumidity'])
                else:
                    data[obs] = weewx.wxformulas.heatindexC(
                        data['outTemp'], data['outHumidity'])
        elif obs == 'pressure':
            self.get_arcint(data)
            if (self.arcint is not None and
                'barometer' in data and
                'outTemp' in data and
                'outHumidity' in data):
                t12 = self.get_temperature_1h2(data['dateTime'], self.arcint)
                if (data['barometer'] is not None and
                    data['outTemp'] is not None and
                    data['outHumidity'] is not None and
                    t12 is not None):
                    if data['usUnits'] == weewx.US:
                        barometer_inHg = data['barometer']
                        t_F = data['outTemp']
                        t12_F = t12
                    else:
                        barometer_inHg = data['barometer'] * INHG_PER_MBAR
                        t_F = data['outTemp'] * (9.0/5.0) + 32.0
                        t12_F = t12 * (9.0/5.0) + 32.0
                    p = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                        barometer_inHg, altitude_ft,
                        t_F, t12_F, data['outHumidity'])
                    if data['usUnits'] == weewx.US:
                        data[obs] = p
                    else:
                        data[obs] = p / INHG_PER_MBAR
                else:
                    data[obs] = None
        elif obs == 'barometer':
            if 'pressure' in data and 'outTemp' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.sealevel_pressure_US(
                        data['pressure'], self.altitude_ft, data['outTemp'])
                else:
                    altitude_m = self.altitude_ft * FOOT_TO_METER
                    data[obs] = weewx.wxformulas.sealevel_pressure_Metric(
                        data['pressure'], altitude_m, data['outTemp'])
        elif obs == 'altimeter':
            if 'pressure' in data:
                if data['usUnits'] == weewx.US:
                    data[obs] = weewx.wxformulas.altimeter_pressure_US(
                        data['pressure'], self.altitude_ft, algorithm='aaNOAA')
                else:
                    altitude_m = self.altitude_ft * FOOT_TO_METER
                    data[obs] = weewx.wxformulas.altimeter_pressure_Metric(
                        data['pressure'], altitude_m, algorithm='aaNOAA')
        elif obs == 'rainRate':
            if 'rain' in data:
                if data_type == 'archive':
                    # for archive records, use window of data from database
                    # projected to rain/hour.  we must add rain from this
                    # record since database may not yet contain data from
                    # this record (and our query intentionally neglects it).
                    oldrain = self.get_rain(data['dateTime'], self.rain_period)
                    if oldrain is not None and data['rain'] is not None:
                        allrain = oldrain + data['rain']
                    elif data['rain'] is not None:
                        allrain = data['rain']
                    elif oldrain is not None:
                        allrain = oldrain
                    else:
                        allrain = None
                    data[obs] = weewx.wxformulas.calculate_rain_rate(
                        allrain, data['dateTime'],
                        data['dateTime'] - self.rain_period)
                else:
                    # for loop packets, use rain since last packet projected
                    # to rain/hour.
                    data[obs] = weewx.wxformulas.calculate_rain_rate(
                        data['rain'], data['dateTime'], self.last_rain_ts)
                    self.last_rain_ts = data['dateTime']

    def get_arcint(self, data):
        if 'interval' in data and self.arcint != data['interval']*60:
            self.arcint = data['interval'] * 60
            # warn if rain period is not multiple of archive interval
            if self.arcint is not None and self.rain_period % self.arcint != 0:
                syslog.syslog(syslog.LOG_INFO, "StdWXCalculate: rain_period (%s) is not a multiple of archive_interval (%s)" % (self.rain_period, self.arcint))

    def get_rain(self, ts, interval=3600):
        """Get the quantity of rain from the past interval seconds.  We
        do not include the latest timestamp so that we do not get the latest
        interval (if it even exists).  We do not include the first timestamp
        because we do not want the interval before that timestamp."""
        sts = ts - interval
        with weewx.archive.open_database(self.config_dict, 'wx_binding') as db:
            r = db.getSql("SELECT SUM(rain) FROM archive "
                          "WHERE dateTime>? AND dateTime<?",
                          (sts, ts))
        if r is None:
            return None
        return r[0]

    def get_temperature_12h(self, ts, arcint):
        """Get the temperature from 12 hours ago.  Return None if no
        temperature is found."""
        ts12 = weeutil.weeutil.startOfInterval(ts - 12*3600, arcint)
        if ts12 != self.last_ts12:
            with weewx.archive.open_database(self.config_dict, 'wx_binding') as db:
                r = db.getRecord(ts12)
                self.t12 = r.get('outTemp') if r is not None else None
                self.last_ts12 = ts12
        return self.t12
