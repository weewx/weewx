# Copyright (c) 2013 Chris Manton <cmanton@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/
#
# Special recognition to Lars de Bruin <l...@larsdebruin.net> for contributing
# packet decoding code.
#
"""Classes and functions to interfacing with an Oregon Scientific WMR200 station

    Oregon Scientific
        http://us.oregonscientific.com/ulimages/manuals2/WMR200.pdf

    Bronberg Weather Station
       For a pretty good summary of what's in these packets see
        http://www.bashewa.com/wmr200-protocol.php
   
"""

import syslog
import threading
import time
import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.units
import weewx.wxformulas

# wmr200 protocol max packet size in bytes.
PACKET_FACTORY_MAX_PACKET_SIZE = 0x40

# General decoding sensor maps.
WIND_DIR_MAP = { 0:'N', 1:'NNE', 2:'NE', 3:'ENE',
                4:'E', 5:'ESE', 6:'SE', 7:'SSE',
                8:'S', 9:'SSW', 10:'SW', 11:'WSW',
                12:'W', 13:'WNW', 14:'NW', 15:'NNW' }
FORECAST_MAP = { 0:'Partly Cloudy', 1:'Rainy', 2:'Cloudy', 3:'Sunny',
                4:'Clear Night', 5:'Snowy',
                6:'Partly Cloudy Night', 7:'Unknown7' }
TRENDS =      { 0:'Stable', 1:'Rising', 2:'Falling', 3:'Undefined' }

# Global debug logging switch for this module.
WMR200_DEBUG = False

def loader(config_dict, engine):
    """Used to load the driver."""
    # The WMR driver needs the altitude in meters. Get it from the Station data
    # and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list( config_dict['Station'].get(
        'altitude', (None, None)))
    # Form a value-tuple:
    altitude_vt = (float(altitude_t[0]), altitude_t[1], 'group_altitude')
    # Now convert to meters, using only the first element of the returned 
    # value-tuple.
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    
    station = WMR200(altitude=altitude_m, **config_dict['WMR-USB'])
    
    return station
            

class UsbDevice(object):
    """General class to handles all access to device via USB bus."""
    def __init__(self, vendor_id, product_id):
        self.vendor_id = vendor_id
        self.product_id = product_id
        # Reset timeout in ms.
        self.reset_timeout = 1000
        # Holds device object
        self.dev = None
        # Holds device handle for access
        self.handle = None
        # Bytes to read per libusb call
        self.bytes_to_read = 8

    def findDevice(self):
        """Find the given vendor and product IDs on the USB bus

        Returns: True if specified device was found, otherwise false.
        """
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.vendor_id \
                   and dev.idProduct == self.product_id:
                    self.dev = dev
                    return True 
        return False

    def openDevice(self):
        """Opens a USB device to read and write."""
        # We must have found a device to open
        if not self.dev:
            return False

        # Open the device and get a handle.
        try:
            self.handle = self.dev.open()
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: Unable to open USB'
                          ' interface.  Reason: %s' % e)
            raise weewx.WeeWxIOError(e)

        # Detach any old claimed interfaces
        try:
            self.handle.detachKernelDriver(self.interface)
        except:
            pass

        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError, e:
            self.closeDevice()
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: Unable to claim USB'
                          ' interface. Reason: %s' % e)
            raise weewx.WeeWxIOError(e)

    def closeDevice(self):
        """Closes a device for access."""
        try:
            self.handle.releaseInterface()
        except:
            pass
        try:
            self.handle.detachKernelDriver(self.interface)
        except:
            pass

    def readDevice(self):
        """Read a stream of data bytes from the device.
        
        Returns a list of valid protocol bytes from the device.
       
        The first byte indicates the number of valid bytes following
        the first byte that are valid protocol bytes.  Only the valid
        protocol bytes are returned.
        """

        if not self.handle:
            raise weewx.WeeWxIOError('No usb handle during usb_device Read')

        try:
            report = self.handle.interruptRead(self.in_endpoint,
                                               self.bytes_to_read,
                                               int(self.timeout)*1000)
            # The first byte is the size of valid data following.
            # We only want to return the valid data.
            return report[1:report[0]+1]
        except (IndexError, usb.USBError), e:
            # No data presented on the bus.  This is a normal part of
            # the process that indicates that the current live records
            # have been exhausted.  We have to send a heartbeat command
            # to tell the weather console to start streaming live data
            # again.
            pass

    def writeDevice(self, buf):
        """Writes a command packet to the device."""
        # Unclear how to create this number, but is the wValue portion
        # of the set_configuration() specified in the USB spec.
        value = 0x00000220

        if not self.handle:
            raise weewx.WeeWxIOError('No usb handle during usb_device Write')
 
        try:
            self.handle.controlMsg(
                usb.TYPE_CLASS + usb.RECIP_INTERFACE, # requestType
                0x0000009,                            # request
                buf,
                value,                                # value
                0x0000000,                            # index
                self.reset_timeout)                   # timeout
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_ERR, 'wmr200: Unable to send USB control'
                          ' message')
            syslog.syslog(syslog.LOG_ERR, '****  %s' % e)
            # Convert to a Weewx error:
            raise weewx.WakeupError(e)

class WMR200ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""

class WMR200CheckSumError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""

class Packet(object):
    """General class for a WMR200 packet.
    
    NOTE(cmanton) Sometimes after a 0xD0 the console will send some bogus
    data in the *second* packet.  This has always manifested itself in a
    duplicate valid protocl command (0xd0-0xdb).
    
    e.g.
        0xd7 0xd7 ...
       
    At this point we are out of sync as the protocol format has been violated
    by the console.  We have a workaround to check for lengths and declare
    a packet bogus at this point. 

    I suspect it has something to do with incorrectly communicating to the
    device causing it to enter this bogus state, but have yet to find
    the magic fix.  """
    pkt_cmd = 0
    pkt_name = 'AbstractPacket'
    pkt_len = 0
    def __init__(self):
        """Initialize base elements of the packet parser."""
        self.pkt_data = []
        self.appendData(self.pkt_cmd)
        # Determines if packet may be sent to weewx engine or not
        self.yieldable = True
        # See not above
        self.bogus_packet = False
        # Use pc time instead of time from weather console.
        self.use_pc_time = False

    @property
    def packetName(self):
        """Common name of the packet parser."""
        return self.pkt_name

    def appendData(self, char):
        """Increments the packet size by one byte."""
        self.pkt_data.append(char)
  
    def _sizeActual(self):
        """Returns actual size of data in packet."""
        if len(self.pkt_data) > PACKET_FACTORY_MAX_PACKET_SIZE:
            print "Illegal actual packet size"
            syslog.syslog(syslog.LOG_INFO, 
                          ('wmr200: Flagged illegal packet actual'
                           'cmd:%x size:%d')
                          % (self.pkt_data[0], len(self.pkt_data)))
            self.bogus_packet = True
        return len(self.pkt_data)

    def _sizeExpected(self):
        """Returns expected size of packet from field."""
        if len(self.pkt_data) > 2:
            if self.pkt_data[1] > PACKET_FACTORY_MAX_PACKET_SIZE:
                print "Illegal protocol packet size"
                syslog.syslog(syslog.LOG_INFO, 
                              ('wmr200: Flagged bogus packet protocol'
                               ' cmd:%x size:%d')
                              % (self.pkt_data[0], self.pkt_data[1]))
                self.bogus_packet = True
            # Return the actual protocol length from packet.  If bogus
            # we will deal with it later.
            return self.pkt_data[1]
        return -1

    def packetVerifyLength(self):
        """Check packet to verify actual length of packet against the
        protocol specified lengthi from the packet, and the expected
        length from the protocol specification."""
        if (self.pkt_len == self._sizeExpected() and 
            self.pkt_len == self._sizeActual()):
            return True
        self.printRaw(True)
        syslog.syslog(syslog.LOG_ERR, ('wmr200: Discarding illegal size packet'
                                       ' act:%d proto:%d exp:%d'
                                       % (self._sizeActual(),
                                          self._sizeExpected(),
                                          self.pkt_len)))
    def packetComplete(self):
        """Determines if packet is complete and ready for weewx engine
        processing"""
        # If we have detected a bogus packet then ensure we drop this
        # packet via this path.
        if self.bogus_packet:
            return True
        return self._sizeActual() == self._sizeExpected()

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        if WMR200_DEBUG:
            print 'Processing %s' % self.packetName

    def packetYieldable(self):
        """Not all packets are accepted by the weewx engine.

        If the packet is yieldable then the weewx engine can
        accept this packet.
        """
        return self.yieldable

    def printRaw(self, override = False):
        """Print the raw packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            for byte in self.pkt_data:
                out += '%02x '% byte 
            print out

    def printCooked(self, override = False):
        """Print the processed packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            out += '%s ' % self.packetName
            out += '%s ' % time.asctime(time.localtime(self.timeStampEpoch()))
            out += 'len:%d' % self._sizeActual()
            print out
            
    def _checkSumCalculate(self):
        """Returns the calculated checksum of the current packet.
        
        If the entire packet has not been received will simply
        return the checksum of whatevent data values exist in the packet."""
        if self._sizeActual() < 2:
            print 'Packet too small to compute 16 bit checksum'
            return
        sum = 0
        # Checksum is last two bytes in packet.
        for byte in self.pkt_data[:-2]:
            sum += byte
        return sum
 
    def _checkSumField(self):
        """Returns the checksum field of the current packet

        If the entire packet has not been received will simply
        return the last two bytes which are not checksum values."""
        if self._sizeActual() < 2:
            print 'Packet too small to contain 16 bit checksum'
            return
        return (self.pkt_data[-1] << 8) | self.pkt_data[-2]

    def verifyCheckSum(self):
        """Verifys packet for checksum correctness
        
        Raises exception upon checksum failure as this is a catastrophic
        event."""
        if self._checkSumCalculate() != self._checkSumField(): 
            str_val =  ('Checksum error act:%x exp:%x' 
                        % (self._checkSumCalculate(), self._checkSumField()))
            print str_val
            self.printRaw(True)
            raise WMR200CheckSumError(str_val)

    def timeStampEpoch(self):
        """The timestamp of the packet in seconds since epoch."""
        if self._sizeActual() < 7:
            print 'Packet length too short to get timestamp'
            raise WMR200ProtocolError(("Packet length too short to get"
                                       "timestamp"))

        # Option to use PC time and not the console time.
        if self.use_pc_time:
            return time.time()

        minute = self.pkt_data[2]
        hour = self.pkt_data[3]
        day = self.pkt_data[4]
        month = self.pkt_data[5]
        year = 2000 + self.pkt_data[6]

        ts = time.mktime((year, month, day, hour, minute, 0, -1, -1, -1))
        return ts

class PacketHistoryReady(Packet):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xd1
    pkt_name = 'Archive Ready'
    pkt_len = 1
    def __init__(self):
        super(PacketHistoryReady, self).__init__()
        self.yieldable = False

    def _sizeExpected(self):
        """The expected packet size is a single byte."""
        return self.pkt_len

    def verifyCheckSum(self):
        """This packet does not have a checksum."""
        pass

    def packetComplete(self):
        """This packet is always complete as it consists of a single byte."""
        return True

    def printCooked(self, override = False):
        """Print the processed packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            out += '%s ' % self.packetName
            print out

    def _sizeExpected(self):
        """Returns expected size of packet from field.
        
        This command violates the <command><len> protocol
        and has no length field.  So just return a single byte lenght here."""
        return 1

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryReady, self).packetProcess()
 
class PacketHistoryData(Packet):
    """Packet parser for archived data."""
    pkt_cmd = 0xd2
    pkt_name = 'Archive Data'
    pkt_len = 0x3f
    def __init__(self):
        super(PacketHistoryData, self).__init__()
        self.yieldable = False

    def printCooked(self, override = False):
        """Print the processed packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            out += '%s ' % self.packetName
            print out

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryData, self).packetProcess()
 
class PacketWind(Packet):
    """Packet parser for wind."""
    pkt_cmd = 0xd3
    pkt_name = 'Wind'
    pkt_len = 0x10
    def __init__(self):
        super(PacketWind, self).__init__()

    def packetProcess(self):
        """Decode a wind packet. Wind speed will be in kph

        Returns a packet that can be processed by the weewx engine."""
        super(PacketWind, self).packetProcess()

        # Wind direction in steps of 22.5 degrees.
        # 0 is N, 1 is NNE and so on. See WIND_DIR_MAP for complete list.
        dirDeg = (self.pkt_data[7] & 0x0f) * 22.5
        # Low byte of gust speed in 0.1 m/s.
        gustSpeed = ((((self.pkt_data[10]) & 0x0f) << 8) 
                     | self.pkt_data[9])/10.0
        
        # High nibble is low nibble of average speed.
        # Low nibble of high byte and high nibble of low byte
        # of average speed. Value is in 0.1 m/s
        avgSpeed = ((self.pkt_data[10] >> 4) 
                    | ((self.pkt_data[11] << 4))) / 10.0
       
        # Low and high byte of windchill temperature. The value is
        # in 0.1F. If no windchill is available byte 5 is 0 and byte 6 0x20.
        # Looks like OS hasn't had their Mars Climate Orbiter experience yet.
        if self.pkt_data[12] != 0 or self.pkt_data[13] != 0x20:
            windchill = (((self.pkt_data[12] << 8) 
                          | self.pkt_data[13]) - 320) * (5.0 / 90.0)
        else:
            windchill = None
      
        if WMR200_DEBUG:
            print 'Wind Dir: %s' % (WIND_DIR_MAP[self.pkt_data[8] & 0x0f])
            print '  Gust: %.1f m/s' % (gustSpeed)
            print '  Wind: %.1f m/s' % (avgSpeed)
            if windchill != None:
                print '  Windchill: %.1f C' % (windchill)

        # The console returns wind speeds in m/s. Our metric system requires 
        # kph, so the result needs to be multiplied by 3.6.
        _record = {'windSpeed'         : avgSpeed * 3.60,
                   'windDir'           : dirDeg,
                   'dateTime'          : self.timeStampEpoch(),
                   'usUnits'           : weewx.METRIC}
        # Sometimes the station emits a wind gust that is less than the
        # average wind.  Ignore it if this is the case.
        if gustSpeed >= _record['windSpeed']:
            _record['windGust'] = gustSpeed * 3.60

        # Save the wind record to be used for windchill and heat index
        self.last_wind_record = _record
        return _record
   
 
class PacketRain(Packet):
    """Packet parser for rain."""
    pkt_cmd = 0xd4
    pkt_name = 'Rain'
    pkt_len = 0x16
    def __init__(self):
        super(PacketRain, self).__init__()

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketRain, self).packetProcess()

        # Bytes 0 and 1: high and low byte of the current rainfall rate
        # in 0.1 in/h
        rain_rate = ((self.pkt_data[9] << 8) | self.pkt_data[8]) / 3.9370078
        # Bytes 2 and 3: high and low byte of the last hour rainfall in 0.1in
        rain_hour = ((self.pkt_data[11] << 8) | self.pkt_data[10]) / 3.9370078
        # Bytes 4 and 5: high and low byte of the last day rainfall in 0.1in
        rain_day = ((self.pkt_data[13] << 8) | self.pkt_data[12]) / 3.9370078
        # Bytes 6 and 7: high and low byte of the total rainfall in 0.1in
        rain_total = ((self.pkt_data[15] << 8) | self.pkt_data[14]) / 3.9370078
        # NB: in my experiments with the WMR100, it registers in increments of
        # 0.04 inches. Per Ejeklint's notes have you divide the packet values by
        # 10, but this would result in an 0.4 inch bucket --- too big. So, I'm
        # dividing by 100.
        _record = {'rainRate'          : rain_rate,
                   'hourRain'          : rain_hour,
                   'dayRain'           : rain_day,
                   'totalRain'         : rain_total,
                   'dateTime'          : self.timeStampEpoch(),
                   'usUnits'           : weewx.US}

        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        # TODO(cmanton) Put this back in
        #_record['rain'] = (_record['totalRain'] - self.last_totalRain) 
        # if self.last_totalRain is not None else None
        # self.last_totalRain = _record['totalRain']
        return _record

     
class PacketUvi(Packet):
    """Packet parser for ultra violet sensor."""
    pkt_cmd = 0xd5
    pkt_name = 'UVI'
    pkt_len = 0x0a
    def __init__(self):
        super(PacketUvi, self).__init__()

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketUvi, self).packetProcess()

        _record = {'UV'              : self.pkt_data[7] & 0xf,
                   'dateTime'        : self.timeStampEpoch(),
                   'usUnits'         : weewx.METRIC}
        return _record
 
class PacketPressure(Packet):
    """Packet parser for barometer sensor."""
    pkt_cmd = 0xd6
    pkt_name = 'Pressure'
    pkt_len = 0x0d
    def __init__(self):
        super(PacketPressure, self).__init__()

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketPressure, self).packetProcess()

        # Low byte of pressure. Value is in hPa.
        # High nibble is forecast
        # Low nibble is high byte of pressure.
        pressure = float(((self.pkt_data[8] & 0x0f) << 8) | self.pkt_data[7])
        forecast = float((self.pkt_data[7] >> 4))

        # Similar to bytes 0 and 1, but altitude corrected
        # pressure. Upper nibble of byte 3 is still unknown. Seems to
        # be always 3.
        altPressure = float(((self.pkt_data[10] & 0x0f) << 8)
                            | self.pkt_data[9])
        unknownNibble = (self.pkt_data[10] >> 4)

        if WMR200_DEBUG:
            print 'Forecast: %s' % (forecast)
            print 'Measured Pressure: %d hPa' % (pressure)
            if unknownNibble != 3:
                print 'Pressure unknown nibble: %d' % (unknownNibble)
            print 'Altitude corrected Pressure: %d hPa' % (altPressure)
       
        _record = {'barometer'   : pressure,
                   'pressure'    : pressure,
                   'altimeter'   : forecast,
                   'dateTime'    : self.timeStampEpoch(),
                   'usUnits'     : weewx.METRIC}
        return _record

class PacketTemperature(Packet):
    """Packet parser for temperature and humidity sensor."""
    pkt_cmd = 0xd7
    pkt_name = 'Temperature'
    pkt_len = 0x10
    def __init__(self):
        super(PacketTemperature, self).__init__()

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketTemperature, self).packetProcess()

        _record = {'dateTime'    : self.timeStampEpoch(),
                   'usUnits'     : weewx.METRIC}
 
        # The historic data can contain data from multiple sensors. I'm not
        # sure if the 0xD7 frames can do too. I've never seen a frame with
        # multiple sensors. But historic data bundles data for multiple
        # sensors.
        # Byte 0: low nibble contains sensor ID. 0 for base station.
        sensor_id = self.pkt_data[7] & 0x0f

        temp_trend = (self.pkt_data[7] >> 6) & 0x3
        hum_trend = (self.pkt_data[7] >> 4) & 0x3

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        temp = (((self.pkt_data[9] & 0x0f) << 8) | self.pkt_data[8])/10.0
        if self.pkt_data[9] & 0x80:
            temp *= -1

        # The humidity in percent.
        humidity = self.pkt_data[10]

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        dew_point = (((self.pkt_data[12] & 0x0f) << 8) | self.pkt_data[11])/10.0
        if self.pkt_data[12] & 0x80:
            dew_point *= -1

        # Heat index
        if self.pkt_data[13] != 0:
            heat_index = (self.pkt_data[13] - 32) / 1.8
        else:
            heat_index = None
        if WMR200_DEBUG:
            print ('Temperature sensor_id:%d %.1f C  Trend: %s' 
                   % (sensor_id, temp,
                      TRENDS[temp_trend]))
            print ('  Humidity %d: %d%%   Trend: %s' % (sensor_id, humidity,
                                                        TRENDS[hum_trend]))
            print ('  Dew point %d: %.1f C' % (sensor_id, dew_point))
            if heat_index:
                print '  Heat index: %d' % (heat_index)

        if sensor_id == 0:
            _record['inTemp']      = temp 
            _record['inHumidity']  = humidity
        elif sensor_id == 1:
            _record['outTemp']     = temp 
            _record['dewpoint']    = weewx.wxformulas.dewpointC(temp, humidity)
            _record['outHumidity'] = humidity 
            _record['heatindex']   = weewx.wxformulas.heatindexC(temp, humidity)
            # The WMR does not provide wind information in a temperature packet,
            # so we have to use old wind data to calculate wind chill, provided
            # it isn't too old and has gone stale. If no wind data has been seen
            # yet, then this will raise an AttributeError exception.
            try:
                if _record['dateTime'] - self.last_wind_record['dateTime'] <= self.stale_wind:
                    _record['windchill'] = weewx.wxformulas.windchillC(T, self.last_wind_record['windSpeed'])
            except AttributeError:
                pass

        elif sensor_id >= 2:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            _record['extraTemp%d'  % sensor_id] = temp
            _record['extraHumid%d' % sensor_id] = humidity 
        return _record

class PacketStatus(Packet):
    """Packet parser for console status."""
    pkt_cmd = 0xd9
    pkt_name = 'Status'
    pkt_len = 0x08
    def __init__(self):
        super(PacketStatus, self).__init__()
        self.yieldable = False

    def printCooked(self, override = False):
        """Print the processed packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            out += '%s ' % self.packetName
            print out

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine.
        
        Currently this console status is not passed to the weewx engine.
        TODO(cmanton) Add way to push bettery status to information to the
        user. """
        super(PacketStatus, self).packetProcess()

        if self.pkt_data[2] & 0x2:
            print 'Sensor 1 fault (temp/hum outdoor)'

        if self.pkt_data[2] & 0x1:
            print 'Wind sensor fault'

        if self.pkt_data[3] & 0x20:
            print 'UV Sensor fault'

        if self.pkt_data[3] & 0x10:
            print 'Rain sensor fault'

        if self.pkt_data[4] & 0x02:
            print 'Sensor 1: Battery low'

        if self.pkt_data[4] & 0x01:
            print 'Wind sensor: Battery low'

        if self.pkt_data[5] & 0x20:
            print 'UV sensor: Battery low'

        if self.pkt_data[5] & 0x10:
            print 'Rain sensor: Battery low'

class PacketEraseAcknowledgement(Packet):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xdb
    pkt_name = 'Erase Acknowledgement'
    pkt_len = 0x01
    def __init__(self):
        super(PacketEraseAcknowledgement, self).__init__()
        self.yieldable = False

    def _sizeExpected(self):
        """The expected packet size is a single byte."""
        return self.pkt_len

    def verifyCheckSum(self):
        """This packet does not have a checksum."""
        pass

    def packetComplete(self):
        """This packet is always complete as it consists of a single byte."""
        return True

    def printCooked(self, override = False):
        """Print the processed packet"""
        if WMR200_DEBUG or override:
            out = ' Packet: '
            out += '%s ' % self.packetName
            print out

    def _sizeExpected(self):
        """Returns expected size of packet from field.
        
        This command violates the <command><len> protocol
        and has no length field.  So just return a single byte lenght here."""
        return 1

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketEraseAcknowledgement, self).packetProcess()
 

class PacketFactory(object):
    """Factory to create proper packet from first command byte from device."""
    def __init__(self, *subclass_list):
        self.subclass = dict((s.pkt_cmd, s) for s in subclass_list)
        self.skipped_bytes = 0

    def getPacket(self, pkt_cmd):
        """Returns an instance of packet parser indexed from packet command
       
        Returns None if there was no mapping for the protocol command.

        Upon startup we may read partial packets. We need to resync to a
        valid packet command from the device if we start reading in the 
        middle of a previous packet. 
       
        We may also get out of sync during operation.
        """
        if pkt_cmd in self.subclass:
            if self.skipped_bytes:
                print "Skipped bytes until re-sync:%d" % self.skipped_bytes
                syslog.syslog(syslog.LOG_INFO, ('wmr200: Skipped bytes before'
                                                ' resync:%d' %
                                                self.skipped_bytes))
                self.skipped_bytes = 0
            return self.subclass[pkt_cmd]()
        self.skipped_bytes += 1
        return None

# Packet factory parser for each packet presented by weather console.
PACKET_FACTORY = PacketFactory(
    PacketHistoryReady,
    PacketHistoryData,
    PacketWind,
    PacketPressure,
    PacketUvi,
    PacketTemperature,
    PacketStatus,
    PacketEraseAcknowledgement,
)

# Watchdog singleton object
watchdog = None
# Polling USB device singleton object
poll_usb_device = None

def getWatchDog(wmr200, poke_time = 30):
    """A singleton to return a thread to handle watchdog.
    
    Should an exception occur the driver is reinstantiated.
    That will respawn new threads but not close out existing
    threads.  This takes care of re-using the same thread."""
    global watchdog
    if watchdog is None:
        # Setup and launch thread to periodically poke the console.
        watchdog = RequestLiveData(kwargs = {'wmr200' :
                                             wmr200,
                                             'poke_time' :
                                             poke_time})
        watchdog.start()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Started watchdog thread'
                                        ' live data'))

    else:
        # If a thread already exists, update the thread with our new
        # device.
        watchdog.wmr200 = wmr200
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Re-seeded watchdog thread for'
                                        ' live data'))



class RequestLiveData(threading.Thread):
    """Watchdog thread to poke the console requesting live data.

    If the console does not receive a request or heartbeat periodically
    for live data then it automatically resets into archive mode."""
    def __init__(self, kwargs):
        super(RequestLiveData, self).__init__()
        self.wmr200 = kwargs['wmr200']
        self.poke_time = kwargs['poke_time']
        # Make sure we pass along the signal to kill the thread when
        # the time comes.
        self.daemon = True
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Created watchdog thread for'
                                        ' live data'))

    def run(self):
        """Simple timer function to inform the main wmr200 driver thread
        that its time to poke the device for live data."""
        log_line = 'wmr200: Poking device every %d seconds.' % self.poke_time
        syslog.syslog(syslog.LOG_INFO, log_line) 
        while self.wmr200.watchdogActive():
            self.wmr200.readyToPoke(True)
            time.sleep(self.poke_time)

        syslog.syslog(syslog.LOG_INFO, ('wmr200: Watchdog thread exiting'))


def getPollUsbDevice(wmr200):
    """A singleton to return a thread to poll the usb device.
    
    Should an exception occur the driver is reinstantiated.
    That will respawn new threads but not close out existing
    threads.  This takes care of re-using the same thread."""
    global poll_usb_device 
    if poll_usb_device is None:
        # Setup and launch thread to read the device on the USB bus.
        poll_usb_device = PollUsbDevice(kwargs = {'wmr200' :
                                                  wmr200})
        poll_usb_device.start()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Started poll_usb_device thread'
                                        ' live data'))

    else:
        # If a thread already exists, update the thread with our new
        # device.
        poll_usb_device.wmr200 = wmr200
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Re-seeded poll_usb_device thread for'
                                        ' live data'))


class PollUsbDevice(threading.Thread):
    """A thread to continually poll for data from a USB device.
    
    Some devices may overflow buffers if not drained within a timely manner.
    
    This thread will blocking read the usb port and buffer data from the
    device for consumption."""
    def __init__(self, kwargs):
        super(PollUsbDevice, self).__init__()
        self.wmr200 = kwargs['wmr200']
        self.usb_device = self.wmr200.usb_device

        # Make sure we pass along the signal to kill the thread when
        # the time comes
        self.daemon = True
        # Buffer list to read data from weather console
        self.buf = []
        # Lock to wrap around the buffer
        self.lock = threading.Lock()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Created usb polling thread for'
                                        ' live data'))

    def run(self):
        """Simple polling function to continually read the usb device and
        buffer the data."""
        while self.wmr200.pollUsbDeviceActive():
            buf = self.usb_device.readDevice()
            if buf:
                self.lock.acquire()
                self.buf.append(buf)
                self.lock.release()

        syslog.syslog(syslog.LOG_INFO, ('wmr200: Usb device polling thread'
                                        ' exiting'))

    def readUsbDevice(self):
        """Reads the buffered usb device data."""
        self.lock.acquire()
        if len(self.buf):
            buf = self.buf.pop(0)
        else:
            buf = None
        self.lock.release()
        return buf


class WMR200(weewx.abstractstation.AbstractStation):
    """Driver for the Oregon Scientific WMR200 station."""
    
    def __init__(self, **stn_dict) :
        """Initialize the wmr200 driver.
        
        NAMED ARGUMENTS:
        altitude: The altitude in meters. Required.
        
        stale_wind: Max time wind speed can be used to calculate wind chill
        before being declared unusable. [Optional. Default is 30 seconds]
        
        timeout: How long to wait, in seconds, before giving up on a response
        # from the USB port. [Optional. Default is 15 seconds]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 5 seconds]

        max_tries: How many times to try before giving up. [Optional.
        Default is 3]
        
        vendor_id: The USB vendor ID for the WMR [Optional. Default is 0xfde.
        
        product_id: The USB product ID for the WM [Optional. Default is 0xca01.
        
        interface: The USB interface [Optional. Default is 0]
        
        in_endpoint: The IN USB endpoint used by the WMR.
            [Optional. Default is usb.ENDPOINT_IN + 1]
        """
        
        self.altitude          = stn_dict['altitude']
        # TODO: Consider changing this so these go in the driver loader instead
        self.record_generation = stn_dict.get('record_generation', 'software')
        self.stale_wind        = float(stn_dict.get('stale_wind', 30.0))
        self.last_totalRain = None

        wait_before_retry = float(stn_dict.get('wait_before_retry', 5.0))
        max_tries         = int(stn_dict.get('max_tries', 3))
        in_endpoint       = int(stn_dict.get('IN_endpoint', 
                                             usb.ENDPOINT_IN + 1))
        vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        product_id        = int(stn_dict.get('product_id', '0xca01'), 0)

        # Buffer of bytes read from console device.
        self.buf = []

        # Access the console via the usb accessor.
        self.usb_device = UsbDevice(vendor_id, product_id)

        self.usb_device.timeout = float(stn_dict.get('timeout', 15.0))

        # Locate the device on the USB bus.
        if not self.usb_device.findDevice():
            syslog.syslog(syslog.LOG_ERR, 'wmr200: Unable to find device')
            print 'Unable to find device'
  
        # Pass some parameters to the usb device module.
        self.usb_device.in_endpoint = in_endpoint
        self.usb_device.max_tries = max_tries
        self.usb_device.wait_before_retry = wait_before_retry
        self.usb_device.interface  = int(stn_dict.get('interface', 0))

        # Setup the packet factory to create packet parser from the
        # weather console.
        self.pkt = None

        # Tickle the weather console to get it up and running.
        self.usb_device.openDevice()

        # Send the device a reeset
        self._resetConsole()

        # Now poke the device
        self._pokeConsole()
        self._rdy_to_poke = False
        # Setup the generator to get a byte stream from the console.
        self.genByte = self._genByte

        # Create the lock to sync between main thread and poke thread.
        self.poke_lock = threading.Lock()
        self.readyToPoke(False)

        # Create or seed watchdog function.
        getWatchDog(self, 30)
        getPollUsbDevice(self)

    @property
    def hardware_name(self):
        """Return the name of the hardware/driver"""
        return 'WMR200'

    def readyToPoke(self, val):
        """Set info that device is ready to be poked"""
        self.poke_lock.acquire()
        self.rdy_to_poke = val
        self.poke_lock.release()
        if WMR200_DEBUG:
            print "Set ready to poke:%r" % val

    def isReadyToPoke(self):
        """Get info that device is ready to be poked"""
        self.poke_lock.acquire()
        val = self.rdy_to_poke
        self.poke_lock.release()
        return val

    def watchdogActive(self):
        """Lets the watchdog thread for live data know if it should
        proceed or not"""
        return True

    def pollUsbDeviceActive(self):
        """Handles reading the console"""
        return True

    def _resetConsole(self):
        """Wake up the device"""
        buf = [0x20, 0x00, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf) 
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_ERR, 
                          'wmr200: Unable to send USB control message')
            syslog.syslog(syslog.LOG_ERR, '****  %s' % e)
            # Convert to a Weewx error:
            raise weewx.WakeupError(e)

        syslog.syslog(syslog.LOG_INFO, 'wmr200: Reset device')

    def _pokeConsole(self):
        """Send a heartbeat command to the weather console

        This is used to inform the weather console to continue streaming
        live data across the USB bus.  Otherwise it enters archive mode
        were data is stored on the weather console."""
        self._writeD0()
        self._writeDB()
        if WMR200_DEBUG:
            print "Poked device for live data"

    def _writeD0(self):
        """Writes a command across the USB bus.
        
        Write a single byte 0xD0 and recieve a single byte back
        acknowledging the command, 0xD1
        """
        buf = [0x01, 0xd0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf) 
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_ERR, 
                          'wmr200: Unable to send USB control message')
            syslog.syslog(syslog.LOG_ERR, '****  %s' % e)
            # Convert to a Weewx error:
            raise weewx.WakeupError(e)

    def _writeDB(self):
        """Writes a command across the USB bus.

        Write a single byte 0xDB and recieve a single byte back
        acknowledging the command, 0xDB
        """
        buf = [0x01, 0xdb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf) 
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_ERR, 
                          'wmr200: Unable to send USB control message')
            syslog.syslog(syslog.LOG_ERR, '****  %s' % e)
            # Convert to a Weewx error:
            raise weewx.WakeupError(e)

    def _genByte(self):
        """Generator to provide byte stream to packet collector."""
        while True:
            # Read WMR200 protocol bytes from the weather console.
            try:
                # buf = self.usb_device.readDevice()
                buf = poll_usb_device.readUsbDevice()
                # Add USB bytes to previous buffer bytes, if any.
                if buf:
                    self.buf.extend(buf)
                else:
                    # We have no more data in this generator so
                    # bail so we can poke console for live data.
                    return
                    yield None

                while self.buf:
                    yield self.buf.pop(0)

            except (IndexError, usb.USBError), e:
                # We timed out during read indicating that the
                # weather console is entering archive mode.
                yield None
         
    def _pollForData(self):
        """Poll for data from the device.

        Generate measurement packets. """

        # Read a bunch of bytes from the weather console.  If we are starting
        # a new packet, get one using that byte from the packet factory.
        # Otherwise add the byte to the current packet.
        # Each USB packet may stradle a protocol packet so make sure
        # we assign the data appropriately.
        for ibyte in self.genByte():
            if ibyte is not None:
                if not self.pkt:
                    # This may return None if we are out of sync
                    # with the console.
                    self.pkt = PACKET_FACTORY.getPacket(ibyte)
                else:
                    self.pkt.appendData(ibyte)
                if self.pkt is not None and self.pkt.packetComplete():
                    # If we have a complete packet then
                    # bail to handle it.
                    return


    def genLoopPackets(self):
        """Main generator function that continuously returns loop packets
        
        Called from weewx engine.
        """
        # Reset the current packet upon entry.
        self.pkt = None

        while True:
            # Loop through indefinitely generating records to the
            # weewx engine.
            if self.pkt is not None and self.pkt.packetComplete():
                # Drop any bogus packets.
                if self.pkt.bogus_packet:
                    syslog.syslog(syslog.LOG_ERR, 
                                  'wmr200: Discarding bogus packet')
                    self.pkt.printRaw(True)
                else:
                    self.pkt.printRaw()
                    self.pkt.printCooked()
                    # The packets are fixed lengths and flag if they
                    # are incorrect.
                    if self.pkt.packetVerifyLength():
                        # This will raise exception if checksum fails.
                        self.pkt.verifyCheckSum()
                        if self.pkt.packetYieldable():
                            # Only send commands weewx engine will handle.
                            yield self.pkt.packetProcess()

                # Reset this packet
                self.pkt = None

            # If we are not in the middle of collecting a packet
            # and it's time to poke the console then do it here.
            if self.pkt is None and self.isReadyToPoke():
                self._pokeConsole()
                self.readyToPoke(False)

            # Pull data from the weather console.
            self._pollForData()

    def closePort(self):
        """Closes the USB port to the device."""
        self.usb_device.closeDevice()

