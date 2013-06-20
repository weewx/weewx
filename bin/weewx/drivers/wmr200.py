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

import select
import socket
import syslog
import threading
import time
import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.units
import weewx.wxformulas

# wmr200 protocol max packet size in bytes.
# This is only a screen to differentiate between good and  
# bad packets.
PACKET_FACTORY_MAX_PACKET_SIZE = 0x80

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

# Size of USB frame to read from weather console.
WMR200_USB_FRAME_SIZE = 8

# Time to sleep in seconds between querying usb device thread
# for data.  This should be non-zero and reduces load on the machine.
WMR200_USB_POLL_INTERVAL = 1

# Time interval in secs to send data to the wmr200 to request live data.
WMR200_REQUEST_LIVE_DATA_INTERVAL = 30

# Time in secs to block and wait for data from the weather console device.
# Related to time to request live data.
WMR200_USB_READ_DATA_INTERVAL = WMR200_REQUEST_LIVE_DATA_INTERVAL / 2

# Time in ms to wait for USB reset to complete.
WMR200_USB_RESET_TIMEOUT = 1000

def dprint(log_msg, override = False):
    """Debug print helper for non-daemon execution.
    
    Can also be overridden to provide additional failure
    information when error occurs."""
    if WMR200_DEBUG or override:
        print 'wmr200: %s' % log_msg

def loader(config_dict, engine):
    """Used to load the driver."""
    # The WMR driver needs the altitude in meters. Get it from the Station data
    # and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list( config_dict['Station'].get(
        'altitude', (None, None)))
    # Form a value-tuple
    altitude_vt = (float(altitude_t[0]), altitude_t[1], 'group_altitude')
    # Now convert to meters, using only the first element of the returned 
    # value-tuple.
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]

    station = WMR200(altitude=altitude_m, **config_dict['WMR-USB'])

    return station


class UsbDevice(object):
    """General class to handles all access to device via USB bus."""
    def __init__(self):
        # Reset timeout in ms.
        self.timeout_reset = WMR200_USB_RESET_TIMEOUT
        # Polling read timeout.
        self.timeout_read = WMR200_USB_READ_DATA_INTERVAL

        # USB device used for libusb
        self.dev = None
        # Holds device handle for access
        self.handle = None

        # debug byte count
        self.debug_byte_cnt = 0

    def findDevice(self, vendor_id, product_id):
        """Find the given vendor and product IDs on the USB bus

        Returns: True if specified device was found, otherwise false.  """
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id \
                   and dev.idProduct == product_id:
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
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: openDevice() Unable to'
                          ' open USB interface.  Reason: %s' % exception)
            raise weewx.WeeWxIOError(exception)

        # Detach any old claimed interfaces
        try:
            self.handle.detachKernelDriver(self.interface)
        except usb.USBError, exception:
            pass

        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: openDevice() Unable to'
                          ' claim USB interface. Reason: %s' % exception)
            raise weewx.WeeWxIOError(exception)

    def closeDevice(self):
        """Closes a device for access."""
        try:
            self.handle.releaseInterface()
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: closeDevice() Unable to'
                          ' release device interface. Reason: %s' % exception)

        try:
            self.handle.detachKernelDriver(self.interface)
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_CRIT, 'wmr200: closeDevice() Unable to'
                          ' detach driver interface. Reason: %s' % exception)

    def readDevice(self):
        """Read a stream of data bytes from the device.
        
        Returns a list of valid protocol bytes from the device.
       
        The first byte indicates the number of valid bytes following
        the first byte that are valid protocol bytes.  Only the valid
        protocol bytes are returned.  """
        if not self.handle:
            syslog.syslog(syslog.LOG_ERR, ('wmr200: readDevice() No USB handle'
                                           ' for usb_device Read'))
            raise weewx.WeeWxIOError('No USB handle for usb_device Read')

        try:
            report = self.handle.interruptRead(self.in_endpoint,
                                               WMR200_USB_FRAME_SIZE,
                                               int(self.timeout_read)*1000)

            # I think this value indicates that the buffer has overflowed.
            if report[0] == 8:
                log_msg = 'USB readDevice overflow error'
                syslog.syslog(syslog.LOG_ERR, 'wmr200: %s' % log_msg)
                raise WMR200ProtocolError(log_msg)

            self.debug_byte_cnt += 1
            # The first byte is the size of valid data following.
            # We only want to return the valid data.
            return report[1:report[0]+1]
        except IndexError:
            # This indicates we failed an index range above.
            pass

        except usb.USBError as exception:
            # No data presented on the bus.  This is a normal part of
            # the process that indicates that the current live records
            # have been exhausted.  We have to send a heartbeat command
            # to tell the weather console to start streaming live data
            # again.
            log_msg = 'readDevice() USB Error Reason:%s' % exception
            print log_msg
            syslog.syslog(syslog.LOG_ERR, 'wmr200: %s' % log_msg)

    def writeDevice(self, buf):
        """Writes a command packet to the device."""
        # Unclear how to create this number, but is the wValue portion
        # of the set_configuration() specified in the USB spec.
        value = 0x00000220

        if not self.handle:
            log_msg = 'No USB handle for usb_device Write'
            print log_msg
            syslog.syslog(syslog.LOG_ERR, ('wmr200: %s') % log_msg)
            raise weewx.WeeWxIOError(log_msg)

        try:
            self.handle.controlMsg(
                usb.TYPE_CLASS + usb.RECIP_INTERFACE, # requestType
                0x0000009,                            # request
                buf,
                value,                                # value
                0x0000000,                            # index
                self.timeout_reset)                   # timeout
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_ERR, ('wmr200: writeDevice() Unable to'
                          ' send USB control message'))
            syslog.syslog(syslog.LOG_ERR, '****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)


class WMR200ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""


class WMR200CheckSumError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""


class WMR200AccessError(weewx.WeeWxIOError):
    """Used to signal a USB or device access error condition"""


class Packet(object):
    """General class for a WMR200 packet.

    All wmr200 packets inherit from this class.  The process() method
    is used to provide useful data to the weewx engine.  Some packets
    require special processing due to discontinuities in the wmr200
    protocol."""
    pkt_cmd = 0
    pkt_name = 'AbstractPacket'
    pkt_len = 0
    def __init__(self, wmr200):
        """Initialize base elements of the packet parser."""
        self._pkt_data = []
        # Record to pass to weewx engine.
        self._record = None
        # Determines if packet may be sent to weewx engine or not
        self._yieldable = True
        # See note above
        self._bogus_packet = False
        # Add the command byte as the first field
        self.appendData(self.pkt_cmd)
        # Keep reference to the wmr200 for any special considerations
        # or options.
        self._wmr200 = wmr200

    @property
    def packetName(self):
        """Common name of the packet parser."""
        return self.pkt_name

    @property
    def isBogus(self):
        """Returns boolean if detected bogus packet."""
        return self._bogus_packet

    def appendData(self, char):
        """Increments the packet size by one byte."""
        self._pkt_data.append(char)
        # The second field indicates the packet length
        if len(self._pkt_data) == 2:
            self._sizeCheckBogus()

    def _sizeCheckBogus(self):
        """Verifies that the size is a reasonable value.

        Often upon startup or other times we can get out
        of sync with the weather console."""
        if self._pkt_data[1] > PACKET_FACTORY_MAX_PACKET_SIZE:
            log_msg = 'Discarding bogus packet cmd:%x size:%d' \
                    % (self._pkt_data[0], self._pkt_data[1])
            print log_msg
            syslog.syslog(syslog.LOG_INFO, 'wmr200: %s' % log_msg)
            self._bogus_packet = True

    def _sizeActual(self):
        """Returns actual size of data in packet."""
        if len(self._pkt_data) > PACKET_FACTORY_MAX_PACKET_SIZE:
            log_msg = 'llegal actual packet size cmd:%x size:%d' \
                    % (self._pkt_data[0], len(self._pkt_data))
            print log_msg
            syslog.syslog(syslog.LOG_INFO, 'wmr200: %s' % log_msg)
            self._bogus_packet = True
        return len(self._pkt_data)

    def _sizeExpected(self):
        """Returns expected size of packet from protocol field."""
        if len(self._pkt_data) > 2:
            if self._pkt_data[1] > PACKET_FACTORY_MAX_PACKET_SIZE:
                log_msg = 'Illegal protocol packet size cmd:%x size:%d' \
                        % (self._pkt_data[0], self._pkt_data[1])
                print log_msg
                syslog.syslog(syslog.LOG_INFO, 'wmr200: %s' % log_msg)
                self._bogus_packet = True
            # Return the actual protocol length from packet.  If bogus
            # we will deal with it later.
            return self._pkt_data[1]
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
        processing."""
        # If we have detected a bogus packet then ensure we drop this
        # packet via this path.
        if self._bogus_packet:
            return True
        return self._sizeActual() == self._sizeExpected()

    def packetProcess(self):
        """Process the raw data and creates a record field.
        
        This is a parent class method and all derivative children
        must define this method."""
        dprint('Processing %s' % self.packetName)
        # Promote this field to an empty dictionary.
        self._record = {}

    def _packetBeenProcessed(self):
        """Indication if packet has been processed.
        
        Returns: True if packet has been processed."""
        if self._record is None:
            return False
        return True

    def packetRecord(self):
        """Returns the processed record to the weewx engine."""
        if not self._packetBeenProcessed():
            print 'WARN packetRecord() Packet has not been proccessed.'
        return self._record

    def packetYieldable(self):
        """Not all packets are accepted by the weewx engine.

        If the packet is yieldable then the weewx engine can
        accept this packet."""
        return self._yieldable

    def _checkSumCalculate(self):
        """Returns the calculated checksum of the current packet.
        
        If the entire packet has not been received will simply
        return the checksum of whatever data values exist in the packet."""
        try:
            cksum = 0
            # Checksum is last two bytes in packet.
            for byte in self._pkt_data[:-2]:
                cksum += byte
            return cksum

        except IndexError:
            str_val = 'Packet too small to compute 16 bit checksum'
            print str_val
            raise WMR200CheckSumError(str_val)

    def _checkSumField(self):
        """Returns the checksum field of the current packet.

        If the entire packet has not been received will simply
        return the last two bytes which are unlikely checksum values."""
        try:
            return (self._pkt_data[-1] << 8) | self._pkt_data[-2]

        except IndexError:
            str_val = 'Packet too small to contain 16 bit checksum'
            print str_val
            raise WMR200CheckSumError(str_val)

    def verifyCheckSum(self):
        """Verifies packet for checksum correctness.
        
        Raises exception upon checksum failure as this is a catastrophic
        event."""
        if self._checkSumCalculate() != self._checkSumField():
            str_val =  ('Checksum error act:%x exp:%x'
                        % (self._checkSumCalculate(), self._checkSumField()))
            print str_val
            self.printRaw(True)
            syslog.syslog(syslog.LOG_ERR, 'wmr200: %s' % str_val)
            raise WMR200CheckSumError(str_val)

    def _timeStampEpoch(self):
        """The timestamp of the packet in seconds since epoch.
        
        Must only be called by packets that have timestamps in the
        protocal packet."""
        try:
            minute = self._pkt_data[2]
            hour = self._pkt_data[3]
            day = self._pkt_data[4]
            month = self._pkt_data[5]
            year = 2000 + self._pkt_data[6]

            self._wmr200.last_time_epoch = \
                    time.mktime((year, month, day, hour, minute, 0, -1, -1, -1))

            # Option to use PC time and not the console time.
            # Done here so that any error conditions associated with the
            # time fields will cause the same error as using pc time would.
            # Drawback is making sure the record interval boundaries that
            # weewx keeps # per loop packet are satisfied.
            if self._wmr200.usePcTime:
                self._wmr200.last_time_epoch = time.time()

            return self._wmr200.last_time_epoch

        except IndexError:
            log_msg = 'Packet length too short to get timestamp len:%d' % len(self._pkt_data)
            print log_msg
            syslog.syslog(syslog.LOG_ERR, ('wmr200: %s') % log_msg)
            raise WMR200ProtocolError(log_msg)

        except (OverflowError, ValueError), exception:
            log_msg = 'Packet timestamp with bogus fields %s' % exception
            syslog.syslog(syslog.LOG_ERR, ('wmr200: %s') % log_msg)
            raise WMR200ProtocolError(log_msg)

    def printRaw(self, override = False):
        """Debug method to print the raw packet.
        
        May be called anytime during packet accumulation."""
        out = ' Packet Raw: '
        for byte in self._pkt_data:
            out += '%02x '% byte
        dprint(out, override)

    def printCooked(self, override = False):
        """Debug method method to print the processed packet.
        
        Must be called after the Process() method."""
        if self._packetBeenProcessed():
            out = ' Packet: '
            out += '%s ' % self.packetName
            out += '%s ' % time.asctime(time.localtime(self._timeStampEpoch()))
            out += 'len:%d' % self._sizeActual()
            out += str(self._record)
        else:
            out = 'WARN: printCooked() Packet has not been processed'
        dprint(out, override)


class PacketHistoryReady(Packet):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xd1
    pkt_name = 'Archive Ready'
    pkt_len = 1
    def __init__(self, wmr200):
        super(PacketHistoryReady, self).__init__(wmr200)
        self._yieldable = False

    def _sizeExpected(self):
        """The expected packet size is a single byte.

        This command violates the <command><len> protocol
        and has no length field.  So just return a single byte lenght here."""
        return self.pkt_len

    def verifyCheckSum(self):
        """This packet does not have a checksum."""
        pass

    def packetComplete(self):
        """This packet is always complete as it consists of a single byte."""
        return True

    def printCooked(self, override = False):
        """Print the processed packet.
        
        Not much processing is done in this packet so not much
        cooked data to print."""
        out = ' Packet: '
        out += '%s ' % self.packetName
        dprint(out, override)

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryReady, self).packetProcess()


class PacketHistoryData(Packet):
    """Packet parser for archived data."""
    pkt_cmd = 0xd2
    pkt_name = 'Archive Data'
    # This is a variable length packet and this is the minimum length.
    pkt_len = 0x31
    def __init__(self, wmr200):
        super(PacketHistoryData, self).__init__(wmr200)
        self._yieldable = False

    def printCooked(self, override = False):
        """Print the processed packet.
        
        Not much processing is done in this packet so not much
        cooked data to print."""
        out = ' Packet: '
        out += '%s ' % self.packetName
        dprint(out, override)

    def packetVerifyLength(self):
        """Check packet to verify actual length of packet against the
        protocol specified lengthi from the packet, and the expected
        length from the protocol specification.
        
        This packet can be variable length, so we just need to make
        sure the packet is at least as big."""
        if (self._sizeExpected() >= self.pkt_len and self._sizeActual() >=
            self.pkt_len):
            return True
        self.printRaw(True)
        syslog.syslog(syslog.LOG_ERR, ('wmr200: Discarding illegal size packet'
                                       ' act:%d proto:%d min_exp:%d'
                                       % (self._sizeActual(),
                                          self._sizeExpected(),
                                          self.pkt_len)))

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryData, self).packetProcess()


class PacketWind(Packet):
    """Packet parser for wind."""
    pkt_cmd = 0xd3
    pkt_name = 'Wind'
    pkt_len = 0x10
    def __init__(self, wmr200):
        super(PacketWind, self).__init__(wmr200)

    def packetProcess(self):
        """Decode a wind packet. Wind speed will be in kph

        Returns a packet that can be processed by the weewx engine."""
        super(PacketWind, self).packetProcess()

        # Wind direction in steps of 22.5 degrees.
        # 0 is N, 1 is NNE and so on. See WIND_DIR_MAP for complete list.
        dirDeg = (self._pkt_data[7] & 0x0f) * 22.5
        # Low byte of gust speed in 0.1 m/s.
        gustSpeed = ((((self._pkt_data[10]) & 0x0f) << 8)
                     | self._pkt_data[9])/10.0

        # High nibble is low nibble of average speed.
        # Low nibble of high byte and high nibble of low byte
        # of average speed. Value is in 0.1 m/s
        avgSpeed = ((self._pkt_data[10] >> 4)
                    | ((self._pkt_data[11] << 4))) / 10.0

        # Low and high byte of windchill temperature. The value is
        # in 0.1F. If no windchill is available byte 5 is 0 and byte 6 0x20.
        # Looks like OS hasn't had their Mars Climate Orbiter experience yet.
        if self._pkt_data[12] != 0 or self._pkt_data[13] != 0x20:
            windchill = (((self._pkt_data[12] << 8)
                          | self._pkt_data[13]) - 320) * (5.0 / 90.0)
        else:
            windchill = None

        dprint('Wind Dir: %s' % (WIND_DIR_MAP[self._pkt_data[8] & 0x0f]))
        dprint('  Gust: %.1f m/s' % (gustSpeed))
        dprint('  Wind: %.1f m/s' % (avgSpeed))
        if windchill != None:
            dprint('  Windchill: %.1f C' % (windchill))

        # The console returns wind speeds in m/s. Our metric system requires 
        # kph, so the result needs to be multiplied by 3.6.
        self._record = {'windSpeed'         : avgSpeed * 3.60,
                        'windDir'           : dirDeg,
                        'dateTime'          : self._timeStampEpoch(),
                        'usUnits'           : weewx.METRIC,
                        'windChill'         : windchill,
                       }
        # Sometimes the station emits a wind gust that is less than the
        # average wind.  Ignore it if this is the case.
        if gustSpeed >= self._record['windSpeed']:
            self._record['windGust'] = gustSpeed * 3.60

        # Save the wind record to be used for windchill and heat index
        self._wmr200.last_wind_record = self._record


class PacketRain(Packet):
    """Packet parser for rain."""
    pkt_cmd = 0xd4
    pkt_name = 'Rain'
    pkt_len = 0x16
    def __init__(self, wmr200):
        super(PacketRain, self).__init__(wmr200)

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketRain, self).packetProcess()

        # Bytes 0 and 1: high and low byte of the current rainfall rate
        # in 0.1 in/h
        rain_rate = ((self._pkt_data[9] << 8) | self._pkt_data[8]) / 3.9370078
        # Bytes 2 and 3: high and low byte of the last hour rainfall in 0.1in
        rain_hour = ((self._pkt_data[11] << 8) | self._pkt_data[10]) / 3.9370078
        # Bytes 4 and 5: high and low byte of the last day rainfall in 0.1in
        rain_day = ((self._pkt_data[13] << 8) | self._pkt_data[12]) / 3.9370078
        # Bytes 6 and 7: high and low byte of the total rainfall in 0.1in
        rain_total = ((self._pkt_data[15] << 8)
                      | self._pkt_data[14]) / 3.9370078
        # NB: in my experiments with the WMR100, it registers in increments of
        # 0.04 inches. Per Ejeklint's notes have you divide the packet values by
        # 10, but this would result in an 0.4 inch bucket --- too big. So, I'm
        # dividing by 100.
        self._record = {'rainRate'          : rain_rate,
                        'hourRain'          : rain_hour,
                        'dayRain'           : rain_day,
                        'totalRain'         : rain_total,
                        'dateTime'          : self._timeStampEpoch(),
                        'usUnits'           : weewx.US}


class PacketUvi(Packet):
    """Packet parser for ultra violet sensor."""
    pkt_cmd = 0xd5
    pkt_name = 'UVI'
    pkt_len = 0x0a
    def __init__(self, wmr200):
        super(PacketUvi, self).__init__(wmr200)

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketUvi, self).packetProcess()

        self._record = {'UV'              : self._pkt_data[7] & 0xf,
                        'dateTime'        : self._timeStampEpoch(),
                        'usUnits'         : weewx.METRIC}


class PacketPressure(Packet):
    """Packet parser for barometer sensor."""
    pkt_cmd = 0xd6
    pkt_name = 'Pressure'
    pkt_len = 0x0d
    def __init__(self, wmr200):
        super(PacketPressure, self).__init__(wmr200)

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketPressure, self).packetProcess()

        # Low byte of pressure. Value is in hPa.
        # High nibble is forecast
        # Low nibble is high byte of pressure.
        pressure = float(((self._pkt_data[8] & 0x0f) << 8) | self._pkt_data[7])
        forecast = float((self._pkt_data[7] >> 4))

        # Similar to bytes 0 and 1, but altitude corrected
        # pressure. Upper nibble of byte 3 is still unknown. Seems to
        # be always 3.
        altPressure = float(((self._pkt_data[10] & 0x0f) << 8)
                            | self._pkt_data[9])
        unknownNibble = (self._pkt_data[10] >> 4)

        dprint('Forecast: %s' % (forecast))
        dprint('Measured Pressure: %d hPa' % (pressure))
        if unknownNibble != 3:
            dprint('Pressure unknown nibble: %d' % (unknownNibble))
        dprint('Altitude corrected Pressure: %d hPa' % (altPressure))

        self._record = {'barometer'   : pressure,
                        'pressure'    : pressure,
                        'altimeter'   : forecast,
                        'dateTime'    : self._timeStampEpoch(),
                        'usUnits'     : weewx.METRIC}


class PacketTemperature(Packet):
    """Packet parser for temperature and humidity sensor."""
    pkt_cmd = 0xd7
    pkt_name = 'Temperature'
    pkt_len = 0x10
    def __init__(self, wmr200):
        super(PacketTemperature, self).__init__(wmr200)

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketTemperature, self).packetProcess()

        self._record = {'dateTime'    : self._timeStampEpoch(),
                        'usUnits'     : weewx.METRIC}

        # The historic data can contain data from multiple sensors. I'm not
        # sure if the 0xD7 frames can do too. I've never seen a frame with
        # multiple sensors. But historic data bundles data for multiple
        # sensors.
        # Byte 0: low nibble contains sensor ID. 0 for base station.
        sensor_id = self._pkt_data[7] & 0x0f

        temp_trend = (self._pkt_data[7] >> 6) & 0x3
        hum_trend = (self._pkt_data[7] >> 4) & 0x3

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        temp = (((self._pkt_data[9] & 0x0f) << 8) | self._pkt_data[8])/10.0
        if self._pkt_data[9] & 0x80:
            temp *= -1

        # The humidity in percent.
        humidity = self._pkt_data[10]

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        dew_point = (((self._pkt_data[12] & 0x0f) << 8)
                     | self._pkt_data[11])/10.0
        if self._pkt_data[12] & 0x80:
            dew_point *= -1

        # Heat index
        if self._pkt_data[13] != 0:
            heat_index = (self._pkt_data[13] - 32) / 1.8
        else:
            heat_index = None

        dprint(('Temperature sensor_id:%d %.1f C  Trend: %s'
                % (sensor_id, temp,
                   TRENDS[temp_trend])))
        dprint('  Humidity %d: %d%%   Trend: %s' % (sensor_id, humidity,
                                                    TRENDS[hum_trend]))
        dprint(('  Dew point %d: %.1f C' % (sensor_id, dew_point)))
        if heat_index:
            dprint('  Heat index: %d' % (heat_index))

        if sensor_id == 0:
            self._record['inTemp']      = temp
            self._record['inHumidity']  = humidity
        elif sensor_id == 1:
            self._record['outTemp']     = temp
            self._record['dewpoint']    = weewx.wxformulas.dewpointC(temp, humidity)
            self._record['outHumidity'] = humidity
            self._record['heatindex']   = weewx.wxformulas.heatindexC(temp, humidity)
        elif sensor_id >= 2:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            self._record['extraTemp%d'  % sensor_id] = temp
            self._record['extraHumid%d' % sensor_id] = humidity


class PacketStatus(Packet):
    """Packet parser for console status."""
    pkt_cmd = 0xd9
    pkt_name = 'Status'
    pkt_len = 0x08
    def __init__(self, wmr200):
        super(PacketStatus, self).__init__(wmr200)

    def packetProcess(self):
        """Returns a packet that can be processed by the weewx engine.
        
        Not all console status aligns with the weewx API but we try
        to make it fit."""
        super(PacketStatus, self).packetProcess()

        # Setup defaults as good.  This packet does not have
        # a timestamp so we put in the PC timestamp.
        # This may be a problem if using console timestamps.
        self._record = {
            'dateTime'          : self._wmr200.last_time_epoch,
            'usUnits'           : weewx.METRIC,
            'inTempBatteryStatus' : 1.0,
            'OutTempBatteryStatus' : 1.0,
            'rainBatteryStatus' : 1.0,
            'windBatteryStatus' : 1.0,
            'txBatteryStatus' : 1.0,
            'rxCheckPercent' : 1.0
        }

        if self._pkt_data[2] & 0x2:
            dprint('Sensor 1 fault (temp/hum outdoor)')

        if self._pkt_data[2] & 0x1:
            dprint('Wind sensor fault')

        if self._pkt_data[3] & 0x20:
            dprint('UV Sensor fault')

        if self._pkt_data[3] & 0x10:
            dprint('Rain sensor fault')

        if self._pkt_data[4] & 0x02:
            dprint('Sensor 1: Battery low')
            self._record['outTempBatteryStatus'] = 0.0

        if self._pkt_data[4] & 0x01:
            dprint('Wind sensor: Battery low')
            self._record['windBatteryStatus'] = 0.0

        if self._pkt_data[5] & 0x20:
            dprint('UV sensor: Battery low')

        if self._pkt_data[5] & 0x10:
            dprint('Rain sensor: Battery low')
            self._record['rainBatteryStatus'] = 0.0

        # Output packet to try to understand other fields.
        self.printRaw(True)

    def printCooked(self, override = False):
        """Print the cooked packet."""
        if self._packetBeenProcessed():
            out = ' Packet: '
            out += '%s ' % self.packetName
            out += 'len:%d' % self._sizeActual()
            out += str(self._record)
        else:
            out = 'WARN: printCooked() Packet has not been processed'
        dprint(out, override)


class PacketEraseAcknowledgement(Packet):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xdb
    pkt_name = 'Erase Acknowledgement'
    pkt_len = 0x01
    def __init__(self, wmr200):
        super(PacketEraseAcknowledgement, self).__init__(wmr200)
        self._yieldable = False

    def _sizeExpected(self):
        """The expected packet size is a single byte.

        This command violates the <command><len> protocol
        and has no length field.  So just return a single byte lenght here.
        """
        return self.pkt_len

    def verifyCheckSum(self):
        """This packet does not have a checksum."""
        pass

    def packetComplete(self):
        """This packet is always complete as it consists of a single byte."""
        return True

    def printCooked(self, override = False):
        """Print the processed packet.
        
        This packet consists of a single byte and thus not much to print."""
        out = ' Packet: '
        out += '%s ' % self.packetName
        dprint(out, override)

    def packetProcess(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketEraseAcknowledgement, self).packetProcess()


class PacketFactory(object):
    """Factory to create proper packet from first command byte from device."""
    def __init__(self, *subclass_list):
        self.subclass = dict((s.pkt_cmd, s) for s in subclass_list)
        self.skipped_bytes = 0

    def getPacket(self, pkt_cmd, wmr200):
        """Returns an instance of packet parser indexed from packet command.
       
        Returns None if there was no mapping for the protocol command.

        Upon startup we may read partial packets. We need to resync to a
        valid packet command from the weather console device if we start
        reading in the middle of a previous packet. 
       
        We may also get out of sync during operation."""
        if pkt_cmd in self.subclass:
            if self.skipped_bytes:
                print 'Skipped bytes until re-sync:%d' % self.skipped_bytes
                syslog.syslog(syslog.LOG_INFO, ('wmr200: Skipped bytes before'
                                                ' resync:%d' %
                                                self.skipped_bytes))
                self.skipped_bytes = 0
            return self.subclass[pkt_cmd](wmr200)
        self.skipped_bytes += 1
        return None


# Packet factory parser for each packet presented by weather console.
PACKET_FACTORY = PacketFactory(
    PacketHistoryReady,
    PacketHistoryData,
    PacketWind,
    PacketRain,
    PacketPressure,
    PacketUvi,
    PacketTemperature,
    PacketStatus,
    PacketEraseAcknowledgement,
)

# Count of restarts
STAT_RESTART = 0

class RequestLiveData(threading.Thread):
    """Watchdog thread to poke the console requesting live data.

    If the console does not receive a request or heartbeat periodically
    for live data then it automatically resets into archive mode."""
    def __init__(self, kwargs):
        super(RequestLiveData, self).__init__()
        self.wmr200 = kwargs['wmr200']
        self.poke_time = kwargs['poke_time']
        self.sock_rd = kwargs['sock_rd']

        # Make sure we pass along the signal to kill the thread when
        # the time comes.
        self.daemon = True
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Created watchdog thread to'
                                        ' poke for live data every %d seconds')
                      % self.poke_time)

    def run(self):
        """Periodically inform the main driver thread to request live data.

        When its time to shutdown this thread, the main thread will send any
        string across the socket.  This both wakes up this timer thread and
        also tells it to expire."""
        while True:
            self.wmr200.readyToPoke(True)
            main_thread_comm \
                    = select.select([self.sock_rd], [], [], self.poke_time)
            if main_thread_comm[0]:
                # Data is reeady to read on socket.
                buf = self.sock_rd.recv(4096)
                syslog.syslog(syslog.LOG_INFO, ('wmr200: Watchdog'
                                                ' received %s') % buf)
                break

        syslog.syslog(syslog.LOG_INFO, ('wmr200: Watchdog thread exiting'))


class PollUsbDevice(threading.Thread):
    """A thread to continually poll for data from a USB device.
    
    Some devices may overflow buffers if not drained within a timely manner.
    
    This thread will blocking read the USB port and buffer data from the
    device for consumption."""
    def __init__(self, kwargs):
        super(PollUsbDevice, self).__init__()
        self.wmr200 = kwargs['wmr200']
        self.usb_device = self.wmr200.usb_device

        # Make sure we pass along the signal to kill the thread when
        # the time comes
        self.daemon = True
        # Buffer list to read data from weather console
        self._buf = []
        # Any exceptions on this thread are passed here.
        self.exception = None
        # Lock to wrap around the buffer
        self._lock_poll = threading.Lock()
        # Conditional variable to gate thread after reset applied.
        self._cv_poll = threading.Condition()

        # One thread is created for each reset sequence.
        self._reset_sent = False

        syslog.syslog(syslog.LOG_INFO, ('wmr200: Created USB polling thread to'
                                        ' read block on device'))

    def run(self):
        """Polling function to block read the USB device.
        
        This method appends new data after previous buffer
        data in preparation for reads to the main driver
        thread.
        
        Once this thread is started it will be gated by
        a reset to the weather console device to sync it
        up."""
        # Wait for a reset to occur from the main thread.
        self._cv_poll.acquire()
        while not self._reset_sent:
            self._cv_poll.wait()
        self._cv_poll.release()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: USB polling thread'
                                        ' reset sent'))

        # Read and discard next data from weather console device.
        buf = self.usb_device.readDevice()

        # Loop indefinitely until main thread indicates time to expire.
        while self.wmr200.pollUsbDeviceEnable():
            try:
                buf = self.usb_device.readDevice()
                if buf:
                    self._lock_poll.acquire()
                    # Append the list of bytes to this buffer.
                    self._buf.append(buf)
                    self._lock_poll.release()
            except WMR200ProtocolError as exception:
                syslog.syslog(syslog.LOG_INFO, ('wmr200: USB overflow'))
                self.exception = exception

        syslog.syslog(syslog.LOG_INFO, ('wmr200: USB device polling thread'
                                        ' exiting'))

    def readUsbDevice(self):
        """Reads the buffered USB device data.
        
        Returns a list of bytes.
        Called from main thread.  """
        buf = []
        self._lock_poll.acquire()
        if len(self._buf):
            buf = self._buf.pop(0)
        self._lock_poll.release()
        return buf

    def flushUsbDevice(self):
        """Flush any previous USB device data.
        Called from main thread."""
        self._lock_poll.acquire()
        self._buf = []
        self._lock_poll.release()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Flushed USB device'))

    def checkException(self):
        """Called my main thread to check if any exceptions occurred.
        Called from main thread."""
        if self.exception:
            log_msg = 'Detected exception in USB layer'
            print log_msg
            syslog.syslog(syslog.LOG_ERR, ('wmr200: %s' % log_msg))
            raise WMR200AccessError(self.exception)

    def resetConsole(self):
        """Send a reset to wake up the weather console device

        Flush any previous USB device data.
        Called from main thread."""
        buf = [0x20, 0x00, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf)
            syslog.syslog(syslog.LOG_INFO, 'wmr200: Reset device')
            self._reset_sent = True
            time.sleep(1)
            # Tell thread it can proceed
            self._cv_poll.acquire()
            self._cv_poll.notify()
            self._cv_poll.release()
            dprint('Reset device')

        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_ERR,
                          ('wmr200: resetConsole() Unable to send USB control'
                           'message'))
            syslog.syslog(syslog.LOG_ERR, '****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)


class WMR200(weewx.abstractstation.AbstractStation):
    """Driver for the Oregon Scientific WMR200 station."""

    def __init__(self, **stn_dict) :
        """Initialize the wmr200 driver.
        
        NAMED ARGUMENTS:
        altitude: The altitude in meters. Required.
        
        vendor_id: The USB vendor ID for the WMR [Optional. Default is 0xfde.
        product_id: The USB product ID for the WM [Optional. Default is 0xca01.
        
        interface: The USB interface [Optional. Default is 0]
        
        in_endpoint: The IN USB endpoint used by the WMR.
            [Optional. Default is usb.ENDPOINT_IN + 1]"""
        self.altitude     = stn_dict['altitude']

        vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        product_id        = int(stn_dict.get('product_id', '0xca01'), 0)
        interface         = int(stn_dict.get('interface', 0))
        in_endpoint       = int(stn_dict.get('IN_endpoint',
                                             usb.ENDPOINT_IN + 1))

        # Boolean to use pc timestamps or weather console timestamps.
        self._use_pc_time = int(stn_dict.get('use_pc_time', '0'), 0) == 1
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Using PC Time:'
                                        '%d') % self._use_pc_time);

        # Buffer of bytes read from weather console device.
        self._buf = []

        # Packet created from the buffer data read from the weather console
        # device.
        self.pkt = None

        # Setup the generator to get a byte stream from the console.
        self.genByte = self._genByte

        # Create USB accessor to communiate with weather console device.
        self.usb_device = UsbDevice()

        # Pass USB parameters to the USB device accessor.
        self.usb_device.in_endpoint = in_endpoint
        self.usb_device.interface  = interface

        # Locate the weather console device on the USB bus.
        if not self.usb_device.findDevice(vendor_id, product_id):
            syslog.syslog(syslog.LOG_ERR, 'wmr200: Unable to find device')
            print 'Unable to find device %x %x' % (vendor_id, product_id)

        # Open the weather console USB device for read and writes.
        self.usb_device.openDevice()

        # Initialize watchdog to poke device to request live
        # data stream.
        self._rdy_to_poke = True

        # Create the lock to sync between main thread and watchdog thread.
        self._poke_lock = threading.Lock()

        # Create a socket pair to communicate with the watchdog thread.
        (self.sock_rd, self.sock_wr) = \
                socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM, 0)

        # Create the watchdog thread to request live data.
        self._thread_watchdog = RequestLiveData(
            kwargs = {'wmr200' :
                      self,
                      'poke_time' :
                      WMR200_REQUEST_LIVE_DATA_INTERVAL,
                      'sock_rd' :
                      self.sock_rd})

        # Create the usb polling device thread.
        self._thread_usb_poll = PollUsbDevice(kwargs = {'wmr200' :
                                                        self})

        # Start the usb polling device thread.
        self._poll_device_enable = True
        self._thread_usb_poll.start()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Started poll_usb_device'
                                        ' thread live data'))

        # Send the device a reset
        self._thread_usb_poll.resetConsole()

        # Start the watchdog for live data thread.
        self._thread_watchdog.start()
        syslog.syslog(syslog.LOG_INFO, ('wmr200: Started watchdog thread'
                                        ' live data'))

        # Stats
        self._stat_bytes_read = 0
        self._stat_pkts_sent = 0

        # General restart counter.
        global STAT_RESTART
        STAT_RESTART += 1
        if STAT_RESTART > 1:
            syslog.syslog(syslog.LOG_INFO, ('wmr200: Restart count:'
                                            '%d') % STAT_RESTART)

    @property
    def hardware_name(self):
        """Return the name of the hardware/driver."""
        return 'WMR200'

    @property
    def usePcTime(self):
        """Flag to use pc time rather than weather console time."""
        return self._use_pc_time

    def readyToPoke(self, val):
        """Set info that device is ready to be poked."""
        self._poke_lock.acquire()
        self._rdy_to_poke = val
        self._poke_lock.release()
        dprint('Set ready to poke:%r' % val)

    def isReadyToPoke(self):
        """Get info that device is ready to be poked."""
        self._poke_lock.acquire()
        val = self._rdy_to_poke
        self._poke_lock.release()
        return val

    def pollUsbDeviceEnable(self):
        """Enabled polling the USB for reading data from the console."""
        return self._poll_device_enable

    def _pokeConsole(self):
        """Send a heartbeat command to the weather console.

        This is used to inform the weather console to continue streaming
        live data across the USB bus.  Otherwise it enters archive mode
        were data is stored on the weather console."""
        self._writeD0()
        self._writeDB()
        # Reset the ready to poke flag.
        self.readyToPoke(False)
        dprint('Poked device for live data')

    def _writeD0(self):
        """Write a command across the USB bus.
        
        Write a single byte 0xD0 and receive a single byte back
        acknowledging the command, 0xD1
        """
        buf = [0x01, 0xd0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf)
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_ERR,
                          ('wmr200: writeD0() Unable to send USB control'
                           ' message'))
            syslog.syslog(syslog.LOG_ERR, '****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)

    def _writeDB(self):
        """Write a command across the USB bus.

        Write a single byte 0xDB and receive a single byte back
        acknowledging the command, 0xDB
        """
        buf = [0x01, 0xdb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.writeDevice(buf)
        except usb.USBError, exception:
            syslog.syslog(syslog.LOG_ERR,
                          ('wmr200: writeDB() Unable to send USB control'
                          ' message'))
            syslog.syslog(syslog.LOG_ERR, '****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)

    def _genByte(self):
        """Generator to provide byte stream to packet collector.
        
        We need to return occasionally to handle both reading data
        from the weather console and handing that data."""
        while True:
            # Read WMR200 protocol bytes from the weather console
            # via a proxy thread that ensure we drain the USB
            # fifo data from the weather console.
            buf = self._thread_usb_poll.readUsbDevice()

            # Add list of new USB bytes to previous buffer byte
            # array, if any.
            if buf:
                self._buf.extend(buf)

            while self._buf:
                # Generate one byte at a time.
                yield self._buf.pop(0)

            # Bail if there is a lull in data from the weather console
            # If we don't bail we won't be able to do other processing
            # required to keep the weather console operating.
            # e.g. poking the console to maintain live data stream.
            if not buf and not self._buf:
                return

    def _pollForData(self):
        """Poll for data from the weather console device.
        
        Read a byte from the weather console.  If we are starting
        a new packet, get one using that byte from the packet factory.
        Otherwise add the byte to the current packet.
        Each USB packet may stradle a protocol packet so make sure
        we assign the data appropriately."""
        for byte in self.genByte():
            self._stat_bytes_read += 1
            if self.pkt:
                self.pkt.appendData(byte)
            else:
                # This may return None if we are out of sync
                # with the console.
                self.pkt = PACKET_FACTORY.getPacket(byte, self)

            if self.pkt is not None and self.pkt.packetComplete():
                # If we have a complete packet then
                # bail to handle it.
                return

        # Prevent busy loop by suspending process a bit to
        # wait for usb read thread to accumulate data from the
        # weather console.
        time.sleep(WMR200_USB_POLL_INTERVAL)

    def genLoopPackets(self):
        """Main generator function that continuously returns loop packets
        
        Called from weewx engine."""
        # Reset the current packet upon entry.
        self.pkt = None

        while True:
            # Loop through indefinitely generating records to the
            # weewx engine.  This loop may resume at the yield()
            # or upon entry during any exception, even an exception
            # not generated from this driver.  e.g. weewx.service.
            if self.pkt is not None and self.pkt.packetComplete():
                # Drop any bogus packets.
                if self.pkt.isBogus:
                    syslog.syslog(syslog.LOG_ERR,
                                  'wmr200: Discarding bogus packet')
                    self.pkt.printRaw(True)
                else:
                    self.pkt.printRaw()
                    # The packets are fixed lengths and flag if they
                    # are incorrect.
                    if self.pkt.packetVerifyLength():
                        # This will raise exception if checksum fails.
                        self.pkt.verifyCheckSum()
                        if self.pkt.packetYieldable():
                            # Only send commands weewx engine will handle.
                            self._stat_pkts_sent += 1
                            self.pkt.packetProcess()
                            self.pkt.printCooked(override=True)
                            yield self.pkt.packetRecord()

                # Reset this packet as its complete or bogus.
                self.pkt = None

            # If we are not in the middle of collecting a packet
            # and it's time to poke the console then do it here.
            if self.pkt is None and self.isReadyToPoke():
                self._pokeConsole()

            # Pull data from the weather console.
            self._pollForData()

            # Check polled device for any exceptions.
            # If any, they will be raised in this method.
            #self._thread_poll_sub.checkException()

        syslog.syslog(syslog.LOG_ERR, 'wmr200: Exited genloop packets')

    def closePort(self):
        """Closes the USB port to the device."""
        # Let the polling thread die off.
        self._poll_device_enable = False
        # Join with the polling thread.
        self._thread_usb_poll.join()
        if self._thread_usb_poll.isAlive():
            syslog.syslog(syslog.LOG_INFO, 'wmr200: USB polling thread still'
                          ' alive')
        else:
            syslog.syslog(syslog.LOG_INFO, 'wmr200: USB polling thread'
                          ' expired')

        # Shutdown the wathdog thread.
        self.sock_wr.send('shutdown')
        # Join with the polling thread.
        self._thread_watchdog.join()
        if self._thread_watchdog.isAlive():
            syslog.syslog(syslog.LOG_INFO, 'wmr200: watchdog thread still'
                          ' alive')
        else:
            syslog.syslog(syslog.LOG_INFO, 'wmr200: watchdog thread'
                          ' expired')

        # Shutdown the USB acccess to the weather console device.
        self.usb_device.closeDevice()

