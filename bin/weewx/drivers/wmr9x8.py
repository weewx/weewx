# Copyright (c) 2012 Will Page <compenguy@gmail.com>
# See the file LICENSE.txt for your full rights.
#
# Derivative of vantage.py and wmr100.py, credit to Tom Keffer

"""Classes and functions for interfacing with Oregon Scientific WM-918, WMR9x8,
and WMR-968 weather stations

See 
  http://wx200.planetfall.com/wx200.txt
  http://www.qsl.net/zl1vfo/wx200/wx200.txt
  http://ed.toton.org/projects/weather/station-protocol.txt
for documentation on the WM-918 / WX-200 serial protocol

See
   http://www.netsky.org/WMR/Protocol.htm
for documentation on the WMR9x8 serial protocol, and
   http://code.google.com/p/wmr968/source/browse/trunk/src/edu/washington/apl/weather/packet/
for sample (java) code.
"""

import time
import operator
import syslog

import serial

import weewx.drivers

from math import exp

DRIVER_NAME = 'WMR9x8'
DRIVER_VERSION = "3.2.2"
DEFAULT_PORT = '/dev/ttyS0'

def loader(config_dict, engine):  # @UnusedVariable
    return WMR9x8(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WMR9x8ConfEditor()

def logmsg(level, msg):
    syslog.syslog(level, 'wmr9x8: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


class WMR9x8ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""

def channel_decoder(chan):
    if 1 <= chan <= 2:
        outchan = chan
    elif chan == 4:
        outchan = 3
    else:
        raise WMR9x8ProtocolError("Bad channel number %d" % chan)
    return outchan

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


class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""

    def __init__(self, port):
        self.port = port
        # WMR9x8 specific settings
        self.serialconfig = {
            "bytesize": serial.EIGHTBITS,
            "parity": serial.PARITY_NONE,
            "stopbits": serial.STOPBITS_ONE,
            "timeout": None,
            "rtscts": 1
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
        logdbg("Opened up serial port %s" % self.port)

    def closePort(self):
        self.serial_port.close()

#==============================================================================
#                           Class WMR9x8
#==============================================================================

class WMR9x8(weewx.drivers.AbstractDevice):
    """Driver for the Oregon Scientific WMR9x8 console.

    The connection to the console will be open after initialization"""

    DEFAULT_MAP = {
        'barometer': 'barometer',
        'pressure': 'pressure',
        'windSpeed': 'wind_speed',
        'windDir': 'wind_dir',
        'windGust': 'wind_gust',
        'windGustDir': 'wind_gust_dir',
        'windBatteryStatus': 'battery_status_wind',
        'inTemp': 'temperature_in',
        'outTemp': 'temperature_out',
        'extraTemp1': 'temperature_1',
        'extraTemp2': 'temperature_2',
        'extraTemp3': 'temperature_3',
        'extraTemp4': 'temperature_4',
        'extraTemp5': 'temperature_5',
        'extraTemp6': 'temperature_6',
        'extraTemp7': 'temperature_7',
        'extraTemp8': 'temperature_8',
        'inHumidity': 'humidity_in',
        'outHumidity': 'humidity_out',
        'extraHumid1': 'humidity_1',
        'extraHumid2': 'humidity_2',
        'extraHumid3': 'humidity_3',
        'extraHumid4': 'humidity_4',
        'extraHumid5': 'humidity_5',
        'extraHumid6': 'humidity_6',
        'extraHumid7': 'humidity_7',
        'extraHumid8': 'humidity_8',
        'inTempBatteryStatus': 'battery_status_in',
        'outTempBatteryStatus': 'battery_status_out',
        'extraBatteryStatus1': 'battery_status_1', # was batteryStatusTHx
        'extraBatteryStatus2': 'battery_status_2', # or batteryStatusTx
        'extraBatteryStatus3': 'battery_status_3',
        'extraBatteryStatus4': 'battery_status_4',
        'extraBatteryStatus5': 'battery_status_5',
        'extraBatteryStatus6': 'battery_status_6',
        'extraBatteryStatus7': 'battery_status_7',
        'extraBatteryStatus8': 'battery_status_8',
        'inDewpoint': 'dewpoint_in',
        'dewpoint': 'dewpoint_out',
        'dewpoint0': 'dewpoint_0',
        'dewpoint1': 'dewpoint_1',
        'dewpoint2': 'dewpoint_2',
        'dewpoint3': 'dewpoint_3',
        'dewpoint4': 'dewpoint_4',
        'dewpoint5': 'dewpoint_5',
        'dewpoint6': 'dewpoint_6',
        'dewpoint7': 'dewpoint_7',
        'dewpoint8': 'dewpoint_8',
        'rain': 'rain',
        'rainTotal': 'rain_total',
        'rainRate': 'rain_rate',
        'hourRain': 'rain_hour',
        'rain24': 'rain_24',
        'yesterdayRain': 'rain_yesterday',
        'rainBatteryStatus': 'battery_status_rain',
        'windchill': 'windchill'}

    def __init__(self, **stn_dict):
        """Initialize an object of type WMR9x8.

        NAMED ARGUMENTS:

        model: Which station model is this?
        [Optional. Default is 'WMR968']

        port: The serial port of the WM918/WMR918/WMR968.
        [Required if serial communication]

        baudrate: Baudrate of the port.
        [Optional. Default 9600]

        timeout: How long to wait before giving up on a response from the
        serial port.
        [Optional. Default is 5]
        """

        loginf('driver version is %s' % DRIVER_VERSION)
        self.model = stn_dict.get('model', 'WMR968')
        self.sensor_map = dict(self.DEFAULT_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        loginf('sensor map is %s' % self.sensor_map)
        self.last_rain_total = None

        # Create the specified port
        self.port = WMR9x8._port_factory(stn_dict)

        # Open it up:
        self.port.openPort()

    @property
    def hardware_name(self):
        return self.model

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
            buf.extend(map(ord, self.port.read(preBufferSize - len(buf))))
            # WMR-9x8/968 packets are framed by 0xFF characters
            if buf[0] == 0xFF and buf[1] == 0xFF and buf[2] in wmr9x8_packet_type_size_map:
                # Look up packet type, the expected size of this packet type
                ptype = buf[2]
                psize = wmr9x8_packet_type_size_map[ptype]
                # Capture only the data belonging to this packet
                pdata = buf[0:psize]
                if weewx.debug >= 2:
                    self.log_packet(pdata)
                # Validate the checksum
                sent_checksum = pdata[-1]
                calc_checksum = reduce(operator.add, pdata[0:-1]) & 0xFF
                if sent_checksum == calc_checksum:
                    logdbg("Received WMR9x8 data packet.")
                    payload = pdata[2:-1]
                    _record = wmr9x8_packet_type_decoder_map[ptype](self, payload)
                    _record = self._sensors_to_fields(_record, self.sensor_map)
                    if _record is not None:
                        yield _record
                    # Eliminate all packet data from the buffer
                    buf = buf[psize:]
                else:
                    logdbg("Invalid data packet (%s)." % pdata)
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
                    logdbg("Received WM-918 data packet.")
                    payload = pdata[0:-1] # send all of packet but crc
                    _record = wm918_packet_type_decoder_map[ptype](self, payload)
                    _record = self._sensors_to_fields(_record, self.sensor_map)
                    if _record is not None:
                        yield _record
                    # Eliminate all packet data from the buffer
                    buf = buf[psize:]
                else:
                    logdbg("Invalid data packet (%s)." % pdata)
                    # Drop the first byte of the buffer and start scanning again
                    buf.pop(0)
            else:
                logdbg("Advancing buffer by one for the next potential packet")
                buf.pop(0)

    @staticmethod
    def _sensors_to_fields(oldrec, sensor_map):
        # map a record with observation names to a record with db field names
        if oldrec:
            newrec = dict()
            for k in sensor_map:
                if sensor_map[k] in oldrec:
                    newrec[k] = oldrec[sensor_map[k]]
            if newrec:
                newrec['dateTime'] = oldrec['dateTime']
                newrec['usUnits'] = oldrec['usUnits']
                return newrec
        return None

    #==========================================================================
    #              Oregon Scientific WMR9x8 utility functions
    #==========================================================================

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

    def log_packet(self, packet):
        packet_str = ','.join(["x%x" % v for v in packet])
        print "%d, %s, %s" % (int(time.time() + 0.5), time.asctime(), packet_str)

    @wmr9x8_registerpackettype(typecode=0x00, size=11)
    def _wmr9x8_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""
        null, status, dir1, dir10, dir100, gust10th, gust1, gust10, avg10th, avg1, avg10, chillstatus, chill1, chill10 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = (status & 0x04) >> 2

        # The console returns wind speeds in m/s. Our metric system requires
        # kph, so the result needs to be multiplied by 3.6
        _record = {
            'battery_status_wind': battery,
            'wind_speed': ((avg10th / 10.0) + avg1 + (avg10 * 10)) * 3.6,
            'wind_dir': dir1 + (dir10 * 10) + (dir100 * 100),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
        # Sometimes the station emits a wind gust that is less than the
        # average wind. Ignore it if this is the case.
        windGustSpeed = ((gust10th / 10.0) + gust1 + (gust10 * 10)) * 3.6
        if windGustSpeed >= _record['wind_speed']:
            _record['wind_gust'] = windGustSpeed

        # Bit 1 of chillstatus is on if there is no wind chill data;
        # Bit 2 is on if it has overflowed. Check them both:
        if chillstatus & 0x6 == 0:
            chill = chill1 + (10 * chill10)
            if chillstatus & 0x8:
                chill = -chill
            _record['windchill'] = chill
        else:
            _record['windchill'] = None
        
        return _record

    @wmr9x8_registerpackettype(typecode=0x01, size=16)
    def _wmr9x8_rain_packet(self, packet):
        null, status, cur1, cur10, cur100, tot10th, tot1, tot10, tot100, tot1000, yest1, yest10, yest100, yest1000, totstartmin1, totstartmin10, totstarthr1, totstarthr10, totstartday1, totstartday10, totstartmonth1, totstartmonth10, totstartyear1, totstartyear10 = self._get_nibble_data(packet[1:]) # @UnusedVariable
        battery = (status & 0x04) >> 2

        # station units are mm and mm/hr while the internal metric units are
        # cm and cm/hr. It is reported that total rainfall is biased by +0.5 mm
        _record = {
            'battery_status_rain': battery,
            'rain_rate': (cur1 + (cur10 * 10) + (cur100 * 100)) / 10.0,
            'rain_yesterday': (yest1 + (yest10 * 10) + (yest100 * 100) + (yest1000 * 1000)) / 10.0,
            'rain_total': (tot10th / 10.0 + tot1 + 10.0 * tot10 + 100.0 * tot100 + 1000.0 * tot1000) / 10.0,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course,
        # this won't work for the very first rain packet.
        _record['rain'] = (_record['rain_total'] - self.last_rain_total) if self.last_rain_total is not None else None
        self.last_rain_total = _record['rain_total']
        return _record

    @wmr9x8_registerpackettype(typecode=0x02, size=9)
    def _wmr9x8_thermohygro_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10 = self._get_nibble_data(packet[1:])

        chan = channel_decoder(chan)

        battery = (status & 0x04) >> 2
        _record = {
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
            'battery_status_%d' % chan :battery
        }

        _record['humidity_%d' % chan] = hum1 + (hum10 * 10)

        tempoverunder = temp100etc & 0x04
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
            _record['temperature_%d' % chan] = temp
        else:
            _record['temperature_%d' % chan] = None

        dewunder = bool(status & 0x01)
        # If dew point is valid, save it.
        if not dewunder:
            _record['dewpoint_%d' % chan] = dew1 + (dew10 * 10)

        return _record

    @wmr9x8_registerpackettype(typecode=0x03, size=9)
    def _wmr9x8_mushroom_packet(self, packet):
        _, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10 = self._get_nibble_data(packet[1:])

        battery = (status & 0x04) >> 2
        _record = {
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
            'battery_status_out': battery,
            'humidity_out': hum1 + (hum10 * 10)
        }

        tempoverunder = temp100etc & 0x04
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
            _record['temperature_out'] = temp
        else:
            _record['temperature_out'] = None
            
        dewunder = bool(status & 0x01)
        # If dew point is valid, save it.
        if not dewunder:
            _record['dewpoint_out'] = dew1 + (dew10 * 10)

        return _record

    @wmr9x8_registerpackettype(typecode=0x04, size=7)
    def _wmr9x8_therm_packet(self, packet):
        chan, status, temp10th, temp1, temp10, temp100etc = self._get_nibble_data(packet[1:])

        chan = channel_decoder(chan)
        battery = (status & 0x04) >> 2

        _record = {'dateTime': int(time.time() + 0.5),
                   'usUnits': weewx.METRIC,
                   'battery_status_%d' % chan: battery}

        temp = temp10th / 10.0 + temp1 + 10.0 * temp10 + 100.0 * (temp100etc & 0x03)
        if temp100etc & 0x08:
            temp = -temp
        tempoverunder = temp100etc & 0x04
        _record['temperature_%d' % chan] = temp if not tempoverunder else None

        return _record

    @wmr9x8_registerpackettype(typecode=0x05, size=13)
    def _wmr9x8_in_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = (status & 0x04) >> 2
        hum = hum1 + (hum10 * 10)

        tempoverunder = bool(temp100etc & 0x04)
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
        else:
            temp = None

        dewunder = bool(status & 0x01)
        if not dewunder:
            dew = dew1 + (dew10 * 10)
        else:
            dew = None
            
        rawsp = ((baro10 & 0xF) << 4) | baro1
        sp = rawsp + 795
        pre_slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100)
        slpoff = (1000 + pre_slpoff) if pre_slpoff < 400.0 else pre_slpoff
        
        _record = {
            'battery_status_in': battery,
            'humidity_in': hum,
            'temperature_in': temp,
            'dewpoint_in': dew,
            'barometer': rawsp + slpoff,
            'pressure': sp,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record

    @wmr9x8_registerpackettype(typecode=0x06, size=14)
    def _wmr9x8_in_ext_thermohygrobaro_packet(self, packet):
        null, status, temp10th, temp1, temp10, temp100etc, hum1, hum10, dew1, dew10, baro1, baro10, baro100, wstatus, null2, slpoff10th, slpoff1, slpoff10, slpoff100, slpoff1000 = self._get_nibble_data(packet[1:]) # @UnusedVariable

        battery = (status & 0x04) >> 2
        hum = hum1 + (hum10 * 10)

        tempoverunder = bool(temp100etc & 0x04)
        if not tempoverunder:
            temp = (temp10th / 10.0) + temp1 + (temp10 * 10) + ((temp100etc & 0x03) * 100)
            if temp100etc & 0x08:
                temp = -temp
        else:
            temp = None

        dewunder = bool(status & 0x01)
        if not dewunder:
            dew = dew1 + (dew10 * 10)
        else:
            dew = None

        rawsp = ((baro100 & 0x01) << 8) | ((baro10 & 0xF) << 4) | baro1
        sp = rawsp + 600
        slpoff = (slpoff10th / 10.0) + slpoff1 + (slpoff10 * 10) + (slpoff100 * 100) + (slpoff1000 * 1000)
        
        _record = {
            'battery_status_in': battery,
            'humidity_in': hum,
            'temperature_in': temp,
            'dewpoint_in': dew,
            'barometer': rawsp + slpoff,
            'pressure': sp,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record

    @wmr9x8_registerpackettype(typecode=0x0e, size=5)
    def _wmr9x8_time_packet(self, packet):
        """The (partial) time packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        min1, min10 = self._get_nibble_data(packet[1:])
        minutes = min1 + ((min10 & 0x07) * 10)

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
        minutes = min1 + ((min10 & 0x07) * 10)
        cur = time.gmtime()
        # TODO: not sure if using tm_isdst is correct here
        self.last_time = time.mktime(
            (year, month, day,
             hour, minutes, 0,
             cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None

    @wm918_registerpackettype(typecode=0xcf, size=27)
    def _wm918_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in m/s"""
        gust10th, gust1, gust10, dir1, dir10, dir100, avg10th, avg1, avg10, avgdir1, avgdir10, avgdir100 = self._get_nibble_data(packet[1:7])
        _chill10, _chill1 = self._get_nibble_data(packet[16:17])

        # The console returns wind speeds in m/s. Our metric system requires
        # kph, so the result needs to be multiplied by 3.6
        _record = {
            'wind_speed': ((avg10th / 10.0) + avg1 + (avg10 * 10)) * 3.6,
            'wind_dir': avgdir1 + (avgdir10 * 10) + (avgdir100 * 100),
            'wind_gust': ((gust10th / 10.0) + gust1 + (gust10 * 10)) * 3.6,
            'wind_gust_dir': dir1 + (dir10 * 10) + (dir100 * 100),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
        # Sometimes the station emits a wind gust that is less than the
        # average wind. Ignore it if this is the case.
        if _record['wind_gust'] < _record['wind_speed']:
            _record['wind_gust'] = _record['wind_speed']
        return _record

    @wm918_registerpackettype(typecode=0xbf, size=14)
    def _wm918_rain_packet(self, packet):
        cur1, cur10, cur100, _stat, yest1, yest10, yest100, yest1000, tot1, tot10, tot100, tot1000 = self._get_nibble_data(packet[1:7])

        # It is reported that total rainfall is biased by +0.5 mm
        _record = {
            'rain_rate': (cur1 + (cur10 * 10) + (cur100 * 100)) / 10.0,
            'rain_yesterday': (yest1 + (yest10 * 10) + (yest100 * 100) + (yest1000 * 1000)) / 10.0,
            'rain_total': (tot1 + (tot10 * 10) + (tot100 * 100) + (tot1000 * 1000)) / 10.0,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
        # Because the WM does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        # the WM reports rain rate as rain_rate, rain yesterday (updated by
        # wm at midnight) and total rain since last reset
        # weewx needs rain since last packet we need to divide by 10 to mimic
        # Vantage reading
        _record['rain'] = (_record['rain_total'] - self.last_rain_total) if self.last_rain_total is not None else None
        self.last_rain_total = _record['rain_total']
        return _record

    @wm918_registerpackettype(typecode=0x8f, size=35)
    def _wm918_humidity_packet(self, packet):
        hum1, hum10 = self._get_nibble_data(packet[8:9])
        humout1, humout10 = self._get_nibble_data(packet[20:21])

        hum = hum1 + (hum10 * 10)
        humout = humout1 + (humout10 * 10)
        _record = {
            'humidity_out': humout,
            'humidity_in': hum,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
        return _record

    @wm918_registerpackettype(typecode=0x9f, size=34)
    def _wm918_therm_packet(self, packet):
        temp10th, temp1, temp10, null = self._get_nibble_data(packet[1:3]) # @UnusedVariable
        tempout10th, tempout1, tempout10, null = self._get_nibble_data(packet[16:18]) # @UnusedVariable

        temp = (temp10th / 10.0) + temp1 + ((temp10 & 0x7) * 10)
        temp *= -1 if (temp10 & 0x08) else 1
        tempout = (tempout10th / 10.0) + tempout1 + ((tempout10 & 0x7) * 10)
        tempout *= -1 if (tempout10 & 0x08) else 1
        _record = {
            'temperature_in': temp,
            'temperature_out': tempout,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record

    @wm918_registerpackettype(typecode=0xaf, size=31)
    def _wm918_baro_dew_packet(self, packet):
        baro1, baro10, baro100, baro1000, slp10th, slp1, slp10, slp100, slp1000, fmt, prediction, trend, dewin1, dewin10 = self._get_nibble_data(packet[1:8]) # @UnusedVariable
        dewout1, dewout10 = self._get_nibble_data(packet[18:19]) # @UnusedVariable

        #dew = dewin1 + (dewin10 * 10)
        #dewout = dewout1 + (dewout10 *10)
        sp = baro1 + (baro10 * 10) + (baro100 * 100) + (baro1000 * 1000)
        slp = (slp10th / 10.0) + slp1 + (slp10 * 10) + (slp100 * 100) + (slp1000 * 1000)
        _record = {
            'barometer': slp,
            'pressure': sp,
            #'inDewpoint': dew,
            #'outDewpoint': dewout,
            #'dewpoint': dewout,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record


class WMR9x8ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR9x8]
    # This section is for the Oregon Scientific WMR918/968

    # Connection type. For now, 'serial' is the only option. 
    type = serial

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The station model, e.g., WMR918, Radio Shack 63-1016
    model = WMR968

    # The driver to use:
    driver = weewx.drivers.wmr9x8
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}

    def modify_config(self, config_dict):
        print """
Setting rainRate, windchill, and dewpoint calculations to hardware."""
        config_dict.setdefault('StdWXCalculate', {})
        config_dict['StdWXCalculate'].setdefault('Calculations', {})
        config_dict['StdWXCalculate']['Calculations']['rainRate'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['windchill'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['dewpoint'] = 'hardware'

# Define a main entry point for basic testing without the weewx engine.
# Invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/wmr9x8.py

if __name__ == '__main__':
    import optparse

    usage = """Usage: %prog --help
       %prog --version
       %prog --gen-packets [--port=PORT]"""

    syslog.openlog('wmr9x8', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    weewx.debug = 2
    
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='Display driver version')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='The port to use. Default is %s' % DEFAULT_PORT,
                      default=DEFAULT_PORT)
    parser.add_option('--gen-packets', dest='gen_packets', action='store_true',
                      help="Generate packets indefinitely")
    
    (options, args) = parser.parse_args()

    if options.version:
        print "WMR9x8 driver version %s" % DRIVER_VERSION
        exit(0)

    if options.gen_packets:
        syslog.syslog(syslog.LOG_DEBUG, "wmr9x8: Running genLoopPackets()")
        stn_dict = {'port': options.port}
        stn = WMR9x8(**stn_dict)
        
        for packet in stn.genLoopPackets():
            print packet
