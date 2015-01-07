# $Id$
# Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
# See the file LICENSE.txt for your full rights.

"""Services specific to weather."""

import syslog

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
        ]

    def __init__(self, engine, config_dict):
        super(StdWXCalculate, self).__init__(engine, config_dict)

        # get any configuration settings
        self.calculations = config_dict.get('StdWXCalculate', {})

        # various bits we need for internal housekeeping
        self.altitude_ft = weewx.units.convert(engine.stn_info.altitude_vt, "foot")[0]
        self.t12 = None
        self.last_ts12 = None
        self.arcint = None
        self.last_rain_arc_ts = None
        self.last_rain_loop_ts = None
        self.rain_period = None # specify in seconds to use db query

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.do_calculations(event.record)

    def do_calculations(self, data_dict, data_type='archive'):
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
        self.adjust_winddir(data_dict)
        data_x = weewx.units.to_std_system(data_us, data_dict['usUnits'])
        data_dict.update(data_x)

    def adjust_winddir(self, data):
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
        self.get_arcint(data)
        if (self.arcint is not None and 'barometer' in data and
            'outTemp' in data and 'outHumidity' in data):
            t12 = self.get_temperature_12h(data['dateTime'], self.arcint)
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
    # if the rain_period is defined, then that period is used for archive
    # records instead of the archive interval.  this will result in a smaller
    # rainRate that ramps up and ramps down over time.
    def calc_rainRate(self, data, data_type):
        if 'rain' in data:
            if data_type == 'archive' and self.rain_period is not None:
                # use window of data from database projected to rain/hour.
                # we must add rain from this record since database may not
                # yet contain data from this record (and our query
                # intentionally neglects it).
                oldrain = self.get_rain(data['dateTime'], self.rain_period)
                if oldrain is not None and data['rain'] is not None:
                    allrain = oldrain + data['rain']
                elif data['rain'] is not None:
                    allrain = data['rain']
                elif oldrain is not None:
                    allrain = oldrain
                else:
                    allrain = None
                data['rainRate'] = weewx.wxformulas.calculate_rain_rate(
                    allrain,data['dateTime'],data['dateTime']-self.rain_period)
            elif data_type == 'archive':
                # for archive records, use rain since last record projected
                # to amount/hour.
                data['rainRate'] = weewx.wxformulas.calculate_rain_rate(
                    data['rain'], data['dateTime'], self.last_rain_arc_ts)
                self.last_rain_arc_ts = data['dateTime']
            else:
                # for loop packets, use rain since last packet projected
                # to amount/hour.
                data['rainRate'] = weewx.wxformulas.calculate_rain_rate(
                    data['rain'], data['dateTime'], self.last_rain_loop_ts)
                self.last_rain_loop_ts = data['dateTime']

    def get_arcint(self, data):
        if 'interval' in data and self.arcint != data['interval'] * 60:
            self.arcint = data['interval'] * 60
            # warn if rain period is not multiple of archive interval
            if self.arcint is not None and self.rain_period is not None and self.rain_period % self.arcint != 0:
                syslog.syslog(syslog.LOG_INFO, "StdWXCalculate: rain_period (%s) is not a multiple of archive_interval (%s)" % (self.rain_period, self.arcint))

    def get_rain(self, ts, interval=3600):
        """Get the quantity of rain from the past interval seconds.  We
        do not include the latest timestamp so that we do not get the latest
        interval (if it even exists).  We do not include the first timestamp
        because we do not want the interval before that timestamp."""
        dbmanager = self.engine.db_binder.get_manager('wx_binding')
        sts = ts - interval
        r = dbmanager.getSql("SELECT SUM(rain) FROM %s "
                             "WHERE dateTime>? AND dateTime<?" % dbmanager.table_name,
                             (sts, ts))
        return r[0] if r is not None else None

    def get_temperature_12h(self, ts, arcint):
        """Get the temperature from 12 hours ago.  Return None if no
        temperature is found."""
        ts12 = weeutil.weeutil.startOfInterval(ts - 12*3600, arcint)
        if ts12 != self.last_ts12:
            dbmanager = self.engine.db_binder.get_manager('wx_binding')
            r = dbmanager.getRecord(ts12)
            self.t12 = r.get('outTemp') if r is not None else None
            self.last_ts12 = ts12
        return self.t12
