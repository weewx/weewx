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
        self.rain_period = 900 # in seconds
        self.rain_events = []

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, 'loop')

    def new_archive_record(self, event):
        self.do_calculations(event.record)

    def do_calculations(self, data_dict, data_type='archive'):
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
        sum = 0
        for e in self.rain_events:
            sum += e[1]
        # ...then divide by the period and scale to an hour
        data['rainRate'] = 3600 * sum / self.rain_period

    def get_arcint(self, data):
        if 'interval' in data and self.arcint != data['interval'] * 60:
            self.arcint = data['interval'] * 60

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
