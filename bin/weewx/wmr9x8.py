#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of VantagePro.py and wmrx.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Classes and functions for interfacing with an Oregon Scientific WMR-918 and WMR-968 weather stations

    See http://www.netsky.org/WMR/Protocol.htm for documentation on the WMR-918 serial protocol,
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

# Dictionary that maps a measurement code, to a function that can decode it:
# packet_type_decoder_map and packet_type_size_map are filled out using the @registerpackettype
# decorator below
packet_type_decoder_map = {}
packet_type_size_map = {}

def registerpackettype(typecode, size):
    """ Function decorator that registers the function as a handler
        for a particular packet type.  Parameters to the decorator
        are typecode and size (in bytes). """
    def wrap(dispatcher):
        packet_type_decoder_map[typecode] = dispatcher
        packet_type_size_map[typecode] = size
    return wrap

def loader(config_dict, engine):
    # The WMR driver needs the altitude in meters. Get it from the Station data
    # and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', (None, None)))
    # Form a value-tuple:
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    # Now convert to meters, using only the first element of the returned value-tuple:
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]

    return WMR918(altitude=altitude_m, **config_dict['WMR-918'])

class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""

    def __init__(self, port):
        self.port     = port
        # WMR-918 specific settings
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
        syslog.syslog(syslog.LOG_DEBUG, "WMR-918: Opened up serial port %s" % (self.port))

    def closePort(self):
        self.serial_port.close()

#===============================================================================
#                           Class WMR-918
#===============================================================================

class WMR918(weewx.abstractstation.AbstractStation):
    """Class that represents a connection to a Oregon Scientific WMR-918 console.

    The connection to the console will be open after initialization"""

    def __init__(self, **stn_dict) :
        """Initialize an object of type WMR-918.

        NAMED ARGUMENTS:

        port: The serial port of the WMR918/968. [Required if serial communication]

        baudrate: Baudrate of the port. [Optional. Default 9600]

        timeout: How long to wait before giving up on a response from the
        serial port. [Optional. Default is 5]
        """

        self.altitude       = stn_dict['altitude']
        self.last_totalRain = None

        # Create the specified port
        self.port = WMR918._port_factory(stn_dict)

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
        preBufferSize = max(packet_type_size_map.items(), key=operator.itemgetter(1))[1]
        while True:
            buf.extend(map(ord, self.port.read(preBufferSize-len(buf))))
            if buf[0] == 0xFF and buf[1] == 0xFF and buf[2] in packet_type_size_map:
                # Look up packet type, the expected size of this packet type
                ptype = buf[2]
                psize = packet_type_size_map[ptype]
                # Capture only the data belonging to this packet
                pdata = buf[0:psize]
                # Validate the checksum
                sent_checksum = pdata[-1]
                calc_checksum = reduce(operator.add, pdata[0:-1]) & 0xFF
                if sent_checksum == calc_checksum:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR-918: Received data packet.")
                    payload = pdata[2:-1]
                    _record = packet_type_decoder_map[ptype](self, payload)
                    if _record is not None:
                        yield _record
                    # Eliminate all packet data from the buffer
                    buf = buf[psize:]
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "WMR-918: Invalid data packet (%s)." % pdata)
                    # Drop the first byte of the buffer and start scanning again
                    buf.pop(0)
            elif buf[1:].count(0xFF) > 0:
                syslog.syslog(syslog.LOG_DEBUG, "WMR-918: Advancing to the next potential header location")
                buf.pop(0)
                buf = buf[buf.index(0xFF):]
            else:
                syslog.syslog(syslog.LOG_DEBUG, "WMR-918: No potential headers found in buf.  Discarding %d bytes..." % len(buf))
                buf = []

    #===========================================================================
    #              Oregon Scientific WMR-918 utility functions
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

    @registerpackettype(typecode=0x00, size=11)
    def _wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""
        null, status, dir1, dir10, dir100, gust10th, gust1, gust10, avg10th, avg1, avg10, chillstatus, chill1, chill10 = WMR918._get_nibble_data(packet[1:])

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
        # Save the wind record to be used for windchill and heat index
        self.last_wind_record = _record
        return _record

    @registerpackettype(typecode=0x01, size=16)
    def _rain_packet(self, packet):
        null, status, cur1, cur10, cur100, tot10th, tot1, tot10, tot100, tot1000, yest1, yest10, yest100, yest1000, totstartmin1, totstartmin10, totstarthr1, totstarthr10, totstartday1, totstartday10, totstartmonth1, totstartmonth10, totstartyear1, totstartyear10 = WMR918._get_nibble_data(packet[1:])
        battery = bool(status&0x04)

        # station units are mm and mm/hr while the internal metric units are cm and cm/hr
        # It is reported that total rainfall is biased by +0.5 mm
        _record = {
            'rainBatteryStatus' : battery,
            'rainRate'          : (cur1 + (cur10 * 10) + (cur100 * 100))/10.0,
            'dayRain'           : (yest1 + (yest10 * 10) + (yest100 * 100) + (yest1000 * 1000))/10.0,
            'totalRain'         : ((tot10th / 10.0) + tot1 + (tot10 * 10) + (tot100 * 100) + (tot1000 * 1000) - 0.5)/10.0,
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }
        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        _record['rain'] = (_record['totalRain']-self.last_totalRain) if self.last_totalRain is not None else None
        self.last_totalRain = _record['totalRain']
        return _record

    @registerpackettype(typecode=0x02, size=9)
    @registerpackettype(typecode=0x03, size=9)
    def _thermohygro_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10 = WMR918._get_nibble_data(packet[1:])

        battery = bool(status&0x04)
        dewunder = bool(status&0x01)
        _record = {
            'dateTime'          : int(time.time() + 0.5),
            'usUnits'           : weewx.METRIC
        }

        temp = (temp10th/10.0) + temp1 + (temp10*10) + ((temp100etc&0x03) * 100)
        temp *= -1 if (temp100etc&0x08) else 1
        tempoverunder = temp100etc&0x04
        dew = dew1 + (dew10 * 10)
        hum = hum1 + (hum10 * 10)
        if chan <= 1:
            _record['outTempBatteryStatus'] = battery
            _record['outHumidity']   = hum
            if not tempoverunder:
                _record['outTemp']   = temp
                _record['heatindex'] = weewx.wxformulas.heatindexC(temp, hum)
            if not dewunder:
                _record['dewpoint']  = dew
            if dewunder and not tempoverunder:
                _record['dewpoint']  = weewx.wxformulas.dewpointC(temp, hum)
            # The WMR does not provide wind information in a temperature packet,
            # so we have to use old wind data to calculate wind chill, provided
            # it isn't too old and has gone stale. If no wind data has been seen
            # yet, then this will raise an AttributeError exception.
            try:
                if _record['dateTime'] - self.last_wind_record['dateTime'] <= self.stale_wind:
                    _record['windchill'] = weewx.wxformulas.windchillC(temp, self.last_wind_record['windSpeed'])
            except AttributeError:
                pass
        else:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            _record['extraHumid%d' % chan] = hum
            if not tempoverunder:
                _record['extraTemp%d' % chan] = temp
        return _record

    @registerpackettype(typecode=0x04, size=7)
    def _therm_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc = WMR918._get_nibble_data(packet[1:])

        _record = {'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}

        temp = (temp10th/10.0) + temp1 + (temp10*10) + ((temp100etc&0x03) * 100)
        temp *= -1 if (temp100etc&0x08) else 1
        tempoverunder = temp100etc&0x04
        battery = bool(status&0x04)
        if chan <= 1:
            _record['outTempBatteryStatus'] = battery
            if not tempoverunder:
                _record['outTemp']          = temp
        else:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            if not tempoverunder:
                _record['extraTemp%d'  % chan] = temp
        return _record

    @registerpackettype(typecode=0x05, size=13)
    def _in_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100 = WMR918._get_nibble_data(packet[1:])
        battery = bool(status&0x04)

        temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc&0x03) * 100)
        temp *= -1 if (temp100etc&0x08) else 1
        tempoverunder = bool(temp100etc & 0x04)
        hum = hum1 + (hum10 * 10)
        dew = dew1 + (dew10 * 10)
        dewunder = bool(status&0x01)
        rawsp = ((baro10&0xF) << 4) | baro1
        sp = rawsp + 795
        pre_slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100)
        slpoff = (1000 + pre_slpoff) if pre_slpoff < 400.0 else pre_slpoff
        sa = weewx.wxformulas.altimeter_pressure_Metric(sp, self.altitude)
        _record = {
            'inTempBatteryStatus' : battery,
            'inHumidity'  : hum,
            'barometer'   : rawsp+slpoff,
            'pressure'    : sp,
            'altimeter'   : sa,
            'dateTime'    : int(time.time() + 0.5),
            'usUnits'     : weewx.METRIC
        }
        if not tempoverunder:
            _record['inTemp']     = temp
        if not dewunder:
            _record['inDewpoint'] = dew
        if dewunder and not tempoverunder:
            _record['inDewpoint'] = weewx.wxformulas.dewpointC(temp, hum)
        return _record

    @registerpackettype(typecode=0x06, size=14)
    def _in_ext_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, baro100, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100, slpoff1000 = WMR918._get_nibble_data(packet[1:])
        battery = bool(status&0x04)
        temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc&0x03) * 100)
        temp *= -1 if (temp100etc&0x08) else 1
        tempoverunder = bool(temp100etc & 0x04)
        hum = hum1 + (hum10 * 10)
        dew = dew1 + (dew10 * 10)
        dewunder = bool(status&0x01)

        rawsp = ((baro100&0x01) << 8) | ((baro10&0xF) << 4) | baro1
        sp = rawsp + 600
        slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100) + (slpoff1000 * 1000)
        sa = weewx.wxformulas.altimeter_pressure_Metric(sp, self.altitude)
        _record = {
            'inTempBatteryStatus' : battery,
            'inHumidity'  : hum,
            'barometer'   : rawsp+slpoff,
            'pressure'    : sp,
            'altimeter'   : sa,
            'dateTime'    : int(time.time() + 0.5),
            'usUnits'     : weewx.METRIC
        }
        if not tempoverunder:
            _record['inTemp']     = temp
        if not dewunder:
            _record['inDewpoint'] = dew
        if dewunder and not tempoverunder:
            _record['inDewpoint'] = weewx.wxformulas.dewpointC(temp, hum)
        return _record

    @registerpackettype(typecode=0x0e, size=5)
    def _time_packet(self, packet):
        """The (partial) time packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        min1, min10 = WMR918._get_nibble_data(packet[1:])
        minutes = min1 + ((min10&0x07) * 10)

        cur = time.gmtime()
        self.last_time = time.mktime(
            (cur.tm_year, cur.tm_mon, cur.tm_mday,
             cur.tm_hour, minutes, 0,
             cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None

    @registerpackettype(typecode=0x0f, size=9)
    def _clock_packet(self, packet):
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

