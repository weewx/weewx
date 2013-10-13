#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of vantage.py and wmr100.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Classes and functions for interfacing with Oregon Scientific WM-918, WMR9x8 and WMR-968 weather stations

    See http://wx200.planetfall.com/wx200.txt or http://www.qsl.net/zl1vfo/wx200/wx200.txt or
    http://ed.toton.org/projects/weather/station-protocol.txt for documentation on the WM-918 / WX-200 serial protocol

    See http://www.netsky.org/WMR/Protocol.htm for documentation on the WMR9x8 serial protocol,
    and http://code.google.com/p/wmr968/source/browse/trunk/src/edu/washington/apl/weather/packet/
    for sample (java) code.

"""

import time
import operator
import syslog

import serial

import weeutil.weeutil
import weewx.abstractstation
import weewx.units
import weewx.wxformulas
from math import exp

class WMRx8ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""

# Dictionary that maps a measurement code, to a function that can decode it:
# packet_type_decoder_map and packet_type_size_map are filled out using the @<type>_registerpackettype
# decorator below
wmr9x8_packet_type_decoder_map = {}
wmr9x8_packet_type_size_map = {}

wm918_packet_type_decoder_map = {}
wm918_packet_type_size_map = {}

def wmr9x8_registerpackettype(typecode, size):
    """ Function decorator that registers the function as a handler
        for a particular packet type.  Parameters to the decorator
        are typecode and size (in bytes). """
    def wrap(dispatcher):
        wmr9x8_packet_type_decoder_map[typecode] = dispatcher
        wmr9x8_packet_type_size_map[typecode] = size
    return wrap

def wm918_registerpackettype(typecode, size):
    """ Function decorator that registers the function as a handler
        for a particular packet type.  Parameters to the decorator
        are typecode and size (in bytes). """
    def wrap(dispatcher):
        wm918_packet_type_decoder_map[typecode] = dispatcher
        wm918_packet_type_size_map[typecode] = size
    return wrap

def loader(config_dict, engine):
    # The WMR driver needs the altitude in meters. Get it from the Station data
    # and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', (None, None)))
    # Form a value-tuple:
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    # Now convert to meters, using only the first element of the returned value-tuple:
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]

    return WMR9x8(altitude=altitude_m, **config_dict['WMR9x8'])

class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""

    def __init__(self, port):
        self.port     = port
        # WMR9x8 specific settings
        self.serialconfig = {
            "bytesize":serial.EIGHTBITS,
            "parity":serial.PARITY_NONE,
            "stopbits":serial.STOPBITS_ONE,
            "timeout":None,
            "rtscts":1
        }

    def flush_input(self):
        self.serial_port.flushInput()

    def queued_bytes(self):
        return self.serial_port.inWaiting()

    def read(self, chars=1):
        _buffer = self.serial_port.read(chars)
        N = len(_buffer)
        if N != chars:
            raise weewx.WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
        return _buffer

    def openPort(self):
        # Open up the port and store it
        self.serial_port = serial.Serial(self.port, **self.serialconfig)
        syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Opened up serial port %s" % (self.port))

    def closePort(self):
        self.serial_port.close()

#===============================================================================
#                           Class WMR9x8
#===============================================================================

class WMR9x8(weewx.abstractstation.AbstractStation):
    """Class that represents a connection to a Oregon Scientific WMR9x8 console.

    The connection to the console will be open after initialization"""

    def __init__(self, **stn_dict) :
        """Initialize an object of type WMR9x8.

        NAMED ARGUMENTS:

        port: The serial port of the WM918/WMR918/WMR968. [Required if serial communication]

        baudrate: Baudrate of the port. [Optional. Default 9600]

        timeout: How long to wait before giving up on a response from the
        serial port. [Optional. Default is 5]
        """

        self.altitude       = stn_dict['altitude']
        self.last_totalRain = None

        # Create the specified port
        self.port = WMR9x8._port_factory(stn_dict)

        # Open it up:
        self.port.openPort()

    def openPort(self):
        """Open up the connection to the console"""
        self.port.openPort()

    def closePort(self):
        """Close the connection to the console. """
        self.port.closePort()

    def genLoopPackets(self):
        """Generator function that continuously returns loop packets"""
        buf = []
        # We keep a buffer the size of the largest supported packet
        wmr9x8max = max(wmr9x8_packet_type_size_map.items(), key=operator.itemgetter(1))[1]
        wm918max = max(wm918_packet_type_size_map.items(), key=operator.itemgetter(1))[1]
        preBufferSize = max(wmr9x8max, wm918max)
        while True:
            buf.extend(map(ord, self.port.read(preBufferSize-len(buf))))
            # WMR-9x8/968 packets are framed by 0xFF characters
            if buf[0] == 0xFF and buf[1] == 0xFF and buf[2] in wmr9x8_packet_type_size_map:
                # Look up packet type, the expected size of this packet type
                ptype = buf[2]
                psize = wmr9x8_packet_type_size_map[ptype]
                # Capture only the data belonging to this packet
                pdata = buf[0:psize]
                # Validate the checksum
                sent_checksum = pdata[-1]
                calc_checksum = reduce(operator.add, pdata[0:-1]) & 0xFF
                if sent_checksum == calc_checksum:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Received WMR9x8 data packet.")
                    payload = pdata[2:-1]
                    _record = wmr9x8_packet_type_decoder_map[ptype](self, payload)
                    if _record is not None:
                        yield _record
                    # Eliminate all packet data from the buffer
                    buf = buf[psize:]
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Invalid data packet (%s)." % pdata)
                    # Drop the first byte of the buffer and start scanning again
                    buf.pop(0)
            # WM-918 packets have no framing
            elif buf[0] in wm918_packet_type_size_map:
                # Look up packet type, the expected size of this packet type
                ptype = buf[0]
                psize = wm918_packet_type_size_map[ptype]
                # Capture only the data belonging to this packet
                pdata = buf[0:psize]
                # Validate the checksum
                sent_checksum = pdata[-1]
                calc_checksum = reduce(operator.add, pdata[0:-1]) & 0xFF
                if sent_checksum == calc_checksum:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Received WM-918 data packet.")
                    payload = pdata[0:-1]  #send all of packet but crc
                    _record = wm918_packet_type_decoder_map[ptype](self, payload)
                    if _record is not None:
                        yield _record
                    # Eliminate all packet data from the buffer
                    buf = buf[psize:]
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Invalid data packet (%s)." % pdata)
                    # Drop the first byte of the buffer and start scanning again
                    buf.pop(0)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "WMR9x8: Advancing buffer by one for the next potential packet")
                buf.pop(0)

    #===========================================================================
    #              Oregon Scientific WMR9x8 utility functions
    #===========================================================================

    @staticmethod
    def _port_factory(stn_dict):
        """Produce a serial port object"""

        # Get the connection type. If it is not specified, assume 'serial':
        connection_type = stn_dict.get('type', 'serial').lower()

        if connection_type == "serial":
            port = stn_dict['port']
            return SerialWrapper(port)
        raise weewx.UnsupportedFeature(stn_dict['type'])

    @staticmethod
    def _get_nibble_data(packet):
        nibbles = bytearray()
        for byte in packet:
            nibbles.extend([(byte & 0x0F), (byte & 0xF0) >> 4])
        return nibbles

    @wmr9x8_registerpackettype(typecode=0x00, size=11)
    def _wmr9x8_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""
        null, status, dir1, dir10, dir100, gust10th, gust1, gust10, avg10th, avg1, avg10, chillstatus, chill1, chill10 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = bool(status&0x04)

        # The console returns wind speeds in m/s. Our metric system requires kph,
        # so the result needs to be multiplied by 3.6
        _record = {
            'windBatteryStatus' : battery,
            'windSpeed'         : ((avg10th/10.0) + avg1 + (avg10*10)) * 3.6,
            'windDir'           : dir1 + (dir10 * 10) + (dir100 * 100),
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        # Sometimes the station emits a wind gust that is less than the average wind.
        # Ignore it if this is the case.
        windGustSpeed = ((gust10th/10.0) + gust1 + (gust10*10)) * 3.6
        if windGustSpeed >= _record['windSpeed']:
            _record['windGust'] = windGustSpeed

        # Bit 1 of chillstatus is on if there is no wind chill data;
        # Bit 2 is on if it has overflowed. Check them both:
        if chillstatus & 0x6 == 0:
            chill = chill1 + (10*chill10)
            if chillstatus & 0x8:
                chill = -chill
            _record['windchill'] = chill
        else:
            _record['windchill'] = None
        
        return _record

    @wmr9x8_registerpackettype(typecode=0x01, size=16)
    def _wmr9x8_rain_packet(self, packet):
        null, status, cur1, cur10, cur100, tot10th, tot1, tot10, tot100, tot1000, yest1, yest10, yest100, yest1000, totstartmin1, totstartmin10, totstarthr1, totstarthr10, totstartday1, totstartday10, totstartmonth1, totstartmonth10, totstartyear1, totstartyear10 = self._get_nibble_data(packet[1:]) # @UnusedVariable
        battery = bool(status&0x04)

        # station units are mm and mm/hr while the internal metric units are cm and cm/hr
        # It is reported that total rainfall is biased by +0.5 mm
        _record = {
            'rainBatteryStatus' : battery,
            'rainRate'          : (cur1 + (cur10 * 10) + (cur100 * 100))/10.0,
            'dayRain'           : (yest1 + (yest10 * 10) + (yest100 * 100) + (yest1000 * 1000))/10.0,
            'totalRain'         : (tot10th/10.0 + tot1 + 10.0*tot10 + 100.0*tot100 + 1000.0*tot1000)/10.0,
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        _record['rain'] = (_record['totalRain']-self.last_totalRain) if self.last_totalRain is not None else None
        self.last_totalRain = _record['totalRain']
        return _record

    @wmr9x8_registerpackettype(typecode=0x02, size=9)
    def _wmr9x8_thermohygro_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10 = self._get_nibble_data(packet[1:])

        chan = channel_decoder(chan)

        battery  = bool(status & 0x04)
        _record = {
            'dateTime' : int(time.time() + 0.5),
            'usUnits'  : weewx.METRIC,
            'batteryStatusTH%d' % chan : battery
        }

        _record['extraHumid%d' % chan] = hum1 + (hum10 * 10)

        tempoverunder = temp100etc & 0x04
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
            _record['extraTemp%d' % chan] = temp
        else:
            _record['extraTemp%d' % chan] = None

        dewunder = bool(status & 0x01)
        # If dew point is valid, save it. Otherwise, try calculating it in software
        if not dewunder:
            _record['dewpoint%d' % chan] = dew1 + (dew10 * 10)
        else:
            _record['dewpoint%d' % chan] = weewx.wxformulas.dewpointC(_record['extraTemp%d' % chan], _record['extraHumid%d' % chan])

        return _record

    @wmr9x8_registerpackettype(typecode=0x03, size=9)
    def _wmr9x8_mushroom_packet(self, packet):
        _, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10 = self._get_nibble_data(packet[1:])

        battery  = bool(status & 0x04)
        _record = {
            'dateTime'             : int(time.time() + 0.5),
            'usUnits'              : weewx.METRIC,
            'outTempBatteryStatus' : battery,
            'outHumidity'          : hum1 + (hum10 * 10)
        }

        tempoverunder = temp100etc & 0x04
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
            _record['outTemp'] = temp
            _record['heatindex'] = weewx.wxformulas.heatindexC(temp, _record['outHumidity'])
        else:
            _record['outTemp'] = _record['heatindex'] = None
            
        dewunder = bool(status & 0x01)
        # If dew point is valid, save it. Otherwise, try calculating it in software
        if not dewunder:
            _record['dewpoint'] = dew1 + (dew10 * 10)
        else:
            _record['dewpoint'] = weewx.wxformulas.dewpointC(_record['outTemp'], _record['outHumidity'])

        return _record

    @wmr9x8_registerpackettype(typecode=0x04, size=7)
    def _wmr9x8_therm_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc = self._get_nibble_data(packet[1:])

        chan = channel_decoder(chan)
        battery  = bool(status & 0x04)

        _record = {'dateTime' : int(time.time() + 0.5),
                   'usUnits'  : weewx.METRIC,
                   'batteryStatusT%d' % chan : battery}

        temp = temp10th / 10.0 + temp1 + 10.0 * temp10 + 100.0 * (temp100etc & 0x03)
        if temp100etc & 0x08:
            temp = -temp
        tempoverunder = temp100etc &  0x04
        _record['extraTemp%d' % chan] = temp if not tempoverunder else None

        return _record

    @wmr9x8_registerpackettype(typecode=0x05, size=13)
    def _wmr9x8_in_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = bool(status&0x04)
        hum = hum1 + (hum10 * 10)

        tempoverunder = bool(temp100etc & 0x04)
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc&0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
        else:
            temp = None
            
        dewunder = bool(status&0x01)
        if not dewunder:
            dew = dew1 + (dew10 * 10)
        else:
            dew = weewx.wxformulas.dewpointC(temp, hum)
            
        rawsp = ((baro10&0xF) << 4) | baro1
        sp = rawsp + 795
        pre_slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100)
        slpoff = (1000 + pre_slpoff) if pre_slpoff < 400.0 else pre_slpoff
        sa = weewx.wxformulas.altimeter_pressure_Metric(sp, self.altitude)
        
        _record = {
            'inTempBatteryStatus' : battery,
            'inHumidity'  : hum,
            'inTemp'      : temp,
            'dewpoint'    : dew,
            'barometer'   : rawsp+slpoff,
            'pressure'    : sp,
            'altimeter'   : sa,
            'dateTime'    : int(time.time() + 0.5),
            'usUnits'     : weewx.METRIC
        }

        return _record

    @wmr9x8_registerpackettype(typecode=0x06, size=14)
    def _wmr9x8_in_ext_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, baro100, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100, slpoff1000 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = bool(status&0x04)
        hum = hum1 + (hum10 * 10)

        tempoverunder = bool(temp100etc & 0x04)
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc&0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
        else:
            temp = None

        dewunder = bool(status&0x01)
        if not dewunder:
            dew = dew1 + (dew10 * 10)
        else:
            dew = weewx.wxformulas.dewpointC(temp, hum)

        rawsp = ((baro100&0x01) << 8) | ((baro10&0xF) << 4) | baro1
        sp = rawsp + 600
        slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100) + (slpoff1000 * 1000)
        sa = weewx.wxformulas.altimeter_pressure_Metric(sp, self.altitude)
        
        _record = {
            'inTempBatteryStatus' : battery,
            'inHumidity'  : hum,
            'inTemp'      : temp,
            'inDewpoint'  : dew,
            'barometer'   : rawsp+slpoff,
            'pressure'    : sp,
            'altimeter'   : sa,
            'dateTime'    : int(time.time() + 0.5),
            'usUnits'     : weewx.METRIC
        }

        return _record

    @wmr9x8_registerpackettype(typecode=0x0e, size=5)
    def _wmr9x8_time_packet(self, packet):
        """The (partial) time packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        min1, min10 = self._get_nibble_data(packet[1:])
        minutes = min1 + ((min10&0x07) * 10)

        cur = time.gmtime()
        self.last_time = time.mktime(
            (cur.tm_year, cur.tm_mon, cur.tm_mday,
             cur.tm_hour, minutes, 0,
             cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None

    @wmr9x8_registerpackettype(typecode=0x0f, size=9)
    def _wmr9x8_clock_packet(self, packet):
        """The clock packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        min1, min10, hour1, hour10, day1, day10, month1, month10, year1, year10 = self._get_nibble_data(packet[1:])
        year = year1 + (year10 * 10)
        # The station initializes itself to "1999" as the first year
        # Thus 99 = 1999, 00 = 2000, 01 = 2001, etc.
        year += 1900 if year == 99 else 2000
        month = month1 + (month10 * 10)
        day = day1 + (day10 * 10)
        hour = hour1 + (hour10 * 10)
        minutes = min1 + ((min10&0x07) * 10)
        cur = time.gmtime()
        # TODO: not sure if using tm_isdst is correct here
        self.last_time = time.mktime(
            (year, month, day,
             hour, minutes, 0,
             cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None

    @wmr9x8_registerpackettype(typecode=0xcf, size=27)
    def _wm918_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in m/s"""
        gust1, gust10th, dir1, gust10, dir100, dir10, avg1, avg10th, avgdir1, avg10, avgdir100, avgdir10 = self._get_nibble_data(packet[1:7])
        chill10, chill1 = self._get_nibble_data(packet[16:17])

        # The console returns wind speeds in m/s. Our metric system requires kph,
        # so the result needs to be multiplied by 3.6
        _record = {
            'windSpeed'         : ((avg10th/10.0) + avg1 + (avg10*10)) * 3.6,
            'windDir'           : avgdir1 + (avgdir10 * 10) + (avgdir100 * 100),
            'windGust'          : ((gust10th/10.0) + gust1 + (gust10*10)) * 3.6,
            'windGustDir'       : dir1 + (dir10 * 10) + (dir100 * 100),
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        # Sometimes the station emits a wind gust that is less than the average wind.
        # Ignore it if this is the case.
        if _record['windGust'] < _record['windSpeed']:
            _record['windGust'] = _record['windSpeed']
        # Save the windspeed to be used for windchill and apparent temperature
        self.last_windSpeed = _record['windSpeed']
        return _record

    @wm918_registerpackettype(typecode=0xbf, size=14)
    def _wm918_rain_packet(self, packet):
        cur1, cur10, cur100, stat, yest1, yest10, yest100, yest1000, tot1, tot10, tot100, tot1000 = self._get_nibble_data(packet[1:7])

        # It is reported that total rainfall is biased by +0.5 mm
        _record = {
            'rainRate'          : (cur1 + (cur10 * 10) + (cur100 * 100)) / 10.0,
            'yesterdayRain'     : (yest1 + (yest10 * 10) + (yest100 * 100) + (yest1000 * 1000))/10.0,
            'totalRain'         : (tot1 + (tot10 * 10) + (tot100 * 100) + (tot1000 * 1000))/10.0,
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        # Because the WM does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        # the WM reports rain rate as rain_rate, rain yesterday (updated by wm at midnight) and total rain since last reset
        # weewx needs rain since last packet we need to divide by 10 to mimic Vantage reading
        _record['rain'] = (_record['totalRain'] - self.last_totalRain) if self.last_totalRain is not None else None
        self.last_totalRain = _record['totalRain']
        return _record

    @wm918_registerpackettype(typecode=0x8f, size=35)
    def _wm918_humidity_packet(self, packet):
        hum1, hum10 = self._get_nibble_data(packet[8:9])
        humout1, humout10 = self._get_nibble_data(packet[20:21])

        hum = hum1 + (hum10 * 10)
        humout = humout1 + (humout10 * 10)
        _record = {
            'outHumidity'       : humout,
            'inHumidity'        : hum,
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        self.last_outHumidity = _record['outHumidity']    # save the humidity for the heat index and apparent temp calculation
        return _record

    @wm918_registerpackettype(typecode=0x9f, size=34)
    def _wm918_therm_packet(self, packet):
        temp10th, temp1, temp10, null = self._get_nibble_data(packet[1:3]) # @UnusedVariable
        tempout10th, tempout1, tempout10, null = self._get_nibble_data(packet[16:18]) # @UnusedVariable

        temp = (temp10th/10.0) + temp1 + ((temp10&0x7)*10)
        temp *= -1 if (temp10&0x08) else 1
        tempout = (tempout10th/10.0) + tempout1 + ((tempout10&0x7)*10)
        tempout *= -1 if (tempout10&0x08) else 1
        _record = {
            'inTemp'           : temp,
            'outTemp'          : tempout
        }

        try:
            _record['heatindex'] = weewx.wxformulas.heatindexC(tempout, self.last_outHumidity)
        except AttributeError:
            _record['heatindex'] = None

        try:
            _record['windchill'] = weewx.wxformulas.windchillC(tempout, self.last_windSpeed)
        except AttributeError:
            _record['windchill'] = None

        try:
            _record['dewpoint'] = weewx.wxformulas.dewpointC(tempout, self.last_outHumidity)
        except AttributeError:
            _record['dewpoint'] = None

        try:
            _record['apparentTemp'] = tempout + 0.33 * ((self.last_outHumidity / 100.0) * 6.105 * exp(17.27 * tempout / (237.7 + tempout))) -0.70 * (self.last_windSpeed / 3.6) - 4.00
        except AttributeError:
            _record['apparentTemp'] = None

        _record ['dateTime'] = int(time.time() + 0.5)
        _record ['usUnits'] = weewx.METRIC
        return _record

    @wm918_registerpackettype(typecode=0xaf, size=31)
    def _wm918_baro_dew_packet(self, packet):
        baro1, baro10, baro100, baro1000, slp10th, slp1, slp10, slp100, slp1000, fmt, prediction, trend, dewin1, dewin10 = self._get_nibble_data(packet[1:8]) # @UnusedVariable
        dewout1, dewout10 = self._get_nibble_data(packet[18:19]) # @UnusedVariable

        #dew = dewin1 + (dewin10 * 10)
        #dewout = dewout1 + (dewout10 *10)
        sp = baro1 + (baro10 *10) + (baro100 *100) + (baro1000 * 1000)
        slp = (slp10th / 10.0) + slp1 + (slp10 * 10) + (slp100 * 100) +(slp1000 * 1000)
        sa = weewx.wxformulas.altimeter_pressure_Metric(sp, self.altitude)
        _record = {
            'barometer'   : slp,
            'pressure'    : sp,
            'altimeter'   : sa,
            #'inDewpoint'  : dew,
            #'outDewpoint' : dewout,
            #'dewpoint'    : dewout,
            'dateTime'    : int(time.time() + 0.5),
            'usUnits'     : weewx.METRIC
        }

        return _record

def channel_decoder(chan):
    if 1 <= chan <=2:
        outchan = chan
    elif chan==4:
        outchan = 3
    else:
        raise WMRx8ProtocolError("Bad channel number %d" % chan)
    return outchan