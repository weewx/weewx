# Copyright (c) 2013 Chris Manton <cmanton@gmail.com>  www.onesockoff.org
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
#    $Revision$
#    $Date$
#
# pylint parameters
# suppress global variable warnings
#   pylint: disable-msg=W0603
# suppress weewx driver methods not implemented
#   pylint: disable-msg=W0223  
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

# General decoding sensor maps.
WIND_DIR_MAP = { 0:'N', 1:'NNE', 2:'NE', 3:'ENE',
                4:'E', 5:'ESE', 6:'SE', 7:'SSE',
                8:'S', 9:'SSW', 10:'SW', 11:'WSW',
                12:'W', 13:'WNW', 14:'NW', 15:'NNW' }
FORECAST_MAP = { 0:'Partly Cloudy', 1:'Rainy', 2:'Cloudy', 3:'Sunny',
                4:'Clear Night', 5:'Snowy',
                6:'Partly Cloudy Night', 7:'Unknown7' }
TRENDS =      { 0:'Stable', 1:'Rising', 2:'Falling', 3:'Undefined' }

# Size of USB frame to read from weather console.
_WMR200_USB_FRAME_SIZE = 8

# Time to sleep in seconds between querying usb device thread
# for data.  This should be non-zero and reduces load on the machine.
_WMR200_USB_POLL_INTERVAL = 1

# Time interval in secs to send data to the wmr200 to request live data.
_WMR200_REQUEST_LIVE_DATA_INTERVAL = 30

# Time in secs to block and wait for data from the weather console device.
# Related to time to request live data.
_WMR200_USB_READ_DATA_INTERVAL = _WMR200_REQUEST_LIVE_DATA_INTERVAL / 2

# Time in ms to wait for USB reset to complete.
_WMR200_USB_RESET_TIMEOUT = 1000

# Guessed wmr200 protocol max packet size in bytes.
# This is only a screen to differentiate between good and
# bad packets.
_WMR200_MAX_PACKET_SIZE = 0x80

# Driver name.
_WMR200_DRIVER_NAME = 'wmr200'

# weewx configurable flags for enabling/disabling debug verbosity.
# Prints processed packets with context from console.
DEBUG_PACKETS_COOKED = 0
# Prints raw pre-processed packets from console.
DEBUG_PACKETS_RAW = 0
# Prints respective packets individually.
DEBUG_PACKETS_ARCHIVE = 0
DEBUG_PACKETS_PRESSURE = 0
DEBUG_PACKETS_RAIN = 0
DEBUG_PACKETS_STATUS = 0
DEBUG_PACKETS_TEMP = 0
DEBUG_PACKETS_UVI = 0
DEBUG_PACKETS_WIND = 0
# Print communication messages 
DEBUG_COMM = 0
# Print weather station configuration.
DEBUG_CONFIG_DATA = 0
# Print all writes to weather console.
DEBUG_WRITES = 0
DEBUG_READS = 0

def logmsg(dst, msg):
    """Base syslog helper"""
    syslog.syslog(dst, ('%s: %s: %s' %
                        (_WMR200_DRIVER_NAME,
                         threading.currentThread().getName(), msg)))


def logdbg(msg):
    """Debug syslog helper"""
    logmsg(syslog.LOG_DEBUG, msg)


def loginf(msg):
    """Info syslog helper"""
    logmsg(syslog.LOG_INFO, msg)


def logwar(msg):
    """Warning syslog helper"""
    logmsg(syslog.LOG_WARNING, msg)


def logerr(msg):
    """Error syslog helper"""
    logmsg(syslog.LOG_ERR, msg)


def logcrt(msg):
    """Critical syslog helper"""
    logmsg(syslog.LOG_CRIT, msg)


def loader(config_dict, engine):
    """Used to load the driver."""
    # The driver needs the altitude in meters. Get it from the Station data
    # and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get(
        'altitude', (None, None)))
    # Form a value-tuple
    altitude_vt = (float(altitude_t[0]), altitude_t[1], 'group_altitude')
    # Now convert to meters, using only the first element of the returned
    # value-tuple.
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    station = WMR200(altitude=altitude_m, **config_dict['WMR200'])
    return station


class UsbDevice(object):
    """General class to handles all access to device via USB bus."""
    def __init__(self):
        # Polling read timeout.
        self.timeout_read = _WMR200_USB_READ_DATA_INTERVAL
        # USB device used for libusb
        self.dev = None
        # Holds device handle for access
        self.handle = None
        # debug byte count
        self.byte_cnt_rd = 0
        self.byte_cnt_wr = 0

    def find_device(self, vendor_id, product_id):
        """Find the given vendor and product IDs on the USB bus

        Returns: True if specified device was found, otherwise false.  """
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id \
                   and dev.idProduct == product_id:
                    self.dev = dev
                    return True
        return False

    def open_device(self):
        """Opens a USB device and get a handle to read and write.
       
        A specific device must have been found."""
        try:
            self.handle = self.dev.open()
        except usb.USBError, exception:
            logcrt(('open_device() Unable to open USB interface.'
                    ' Reason: %s' % exception))
            raise weewx.WeeWxIOError(exception)
        except AttributeError, exception:
            logcrt('open_device() Device not specified.')
            raise weewx.WeeWxIOError(exception)

        # Detach any old claimed interfaces
        try:
            self.handle.detachKernelDriver(self.interface)
        except usb.USBError, exception:
            pass

        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError, exception:
            logcrt('open_device() Unable to'
                   ' claim USB interface. Reason: %s' % exception)
            raise weewx.WeeWxIOError(exception)

    def close_device(self):
        """Closes a device for access."""
        try:
            self.handle.releaseInterface()
        except usb.USBError, exception:
            logcrt('close_device() Unable to'
                   ' release device interface. Reason: %s' % exception)

    def read_device(self):
        """Read a stream of data bytes from the device.
        
        Returns a list of valid protocol bytes from the device.
       
        The first byte indicates the number of valid bytes following
        the first byte that are valid protocol bytes.  Only the valid
        protocol bytes are returned.  """
        if not self.handle:
            logerr(('read_device() No USB handle'
                                           ' for usb_device Read'))
            raise weewx.WeeWxIOError('No USB handle for usb_device Read')

        try:
            report = self.handle.interruptRead(self.in_endpoint,
                                               _WMR200_USB_FRAME_SIZE,
                                               int(self.timeout_read) * 1000)

            # I think this value indicates that the buffer has overflowed.
            if report[0] == 8:
                log_msg = 'USB read_device overflow error'
                logerr(log_msg)
                raise WMR200AccessError(log_msg)

            self.byte_cnt_rd += len(report)
            # The first byte is the size of valid data following.
            # We only want to return the valid data.
            if DEBUG_READS:
                buf = ''
                for byte in report[1:report[0]+1]:
                    buf += '%02x ' % byte
                loginf('read_device(): %s' % buf)
            return report[1:report[0] + 1]

        except IndexError:
            # This indicates we failed an index range above.
            pass

        except usb.USBError, ex:
            # No data presented on the bus.  This is a normal part of
            # the process that indicates that the current live records
            # have been exhausted.  We have to send a heartbeat command
            # to tell the weather console to start streaming live data
            # again.
            log_msg = 'read_device() USB Error Reason:%s' % ex
            if ex.args[0].find('No data available') == -1:
                logerr(log_msg)
                return None
            else:
                # No data avail...not an error but probably ok.
                logdbg('No data received in'
                              ' %d seconds' % int(self.timeout_read))
                return []

    def write_device(self, buf):
        """Writes a command packet to the device."""
        # Unclear how to create this number, but is the wValue portion
        # of the set_configuration() specified in the USB spec.
        value = 0x00000220

        if not self.handle:
            log_msg = 'No USB handle for usb_device Write'
            logerr(log_msg)
            raise weewx.WeeWxIOError(log_msg)

        try:
            if DEBUG_WRITES:
                loginf('write_device(): %s' % buf)
            self.byte_cnt_wr += len(buf)
            self.handle.controlMsg(
                usb.TYPE_CLASS + usb.RECIP_INTERFACE, # requestType
                0x0000009,                            # request
                buf,
                value,                                # value
                0x0000000,                            # index
                _WMR200_USB_RESET_TIMEOUT)            # timeout
        except usb.USBError, exception:
            logerr(('write_device() Unable to'
                          ' send USB control message'))
            logerr('****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)


class WMR200ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""
    def __init__(self, msg):
        super(WMR200ProtocolError, self).__init__()
        self._msg = msg


class WMR200CheckSumError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""
    def __init__(self, msg):
        super(WMR200CheckSumError, self).__init__()
        self._msg = msg


class WMR200AccessError(weewx.WeeWxIOError):
    """Used to signal a USB or device access error condition"""
    def __init__(self, msg):
        super(WMR200AccessError, self).__init__()
        self._msg = msg


class Packet(object):
    """Top level class for all WMR200 packets.

    All wmr200 packets inherit from this class.  The process() method
    is used to provide useful data to the weewx engine.  Some packets
    require special processing due to discontinuities in the wmr200
    protocol."""
    pkt_cmd = 0
    pkt_name = 'AbstractPacket'
    pkt_len = 0
    def __init__(self, wmr200):
        """Initialize base elements of the packet parser."""
        # Keep reference to the wmr200 for any special considerations
        # or options.
        self.wmr200 = wmr200
        # Accumulated raw byte data from console.
        self._pkt_data = []
        # Record dictionary to pass to weewx engine.
        self._record = {}
        # Determines if a bogus packet has been detected.
        self._bogus_packet = False
        # Add the command byte as the first field
        self.append_data(self.pkt_cmd)

    @staticmethod
    def host_timestamp():
        """Returns the host timestamp"""
        return int(time.time() + 0.5)

    @property
    def is_bogus(self):
        """Returns boolean if detected bogus packet."""
        return self._bogus_packet

    def append_data(self, char):
        """Appends new data to packet buffer.

        Verifies that the size is a reasonable value.
        Upon startup or other times we can may get out
        of sync with the weather console."""
        self._pkt_data.append(char)
        # We do an immediate check to toss bogus packets should
        # they ve encountered.
        if len(self._pkt_data) == 2 and \
           self._pkt_data[1] > _WMR200_MAX_PACKET_SIZE:
            self._bogus_packet = True

    def size_actual(self):
        """Size of bytes of data in packet received from console."""
        return len(self._pkt_data)

    def size_expected(self):
        """Expected size of packet from packet protocol field."""
        try:
            return self._pkt_data[1]
        except IndexError:
            logerr('Failed to extract size from packet')
            return 0

    def packet_complete(self):
        """Determines if packet is complete and ready for weewx engine
        processing.
        
        This assumes the packet is at least 2 bytes long"""
        # If we have detected a bogus packet then ensure we drop this
        # packet via this path.
        if self.size_actual() < 2:
            return False
        return self._bogus_packet or self.size_actual() == self.size_expected()

    def packet_process(self):
        """Process the raw data and creates a record field."""
        if DEBUG_PACKETS_RAW or DEBUG_PACKETS_COOKED:
            logdbg('Processing %s' % self.pkt_name)
        self._record.update({'usUnits' : weewx.METRIC})
        if self.pkt_len and self.pkt_len != self.size_actual():
            logwar(('Unexpected packet size act:%d exp:%d' %
                    (self.size_actual(), self.pkt_len)))

    def packet_record(self):
        """Returns the processed record of this packet."""
        return self._record

    def _checksum_calculate(self):
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
            logerr(str_val)
            raise WMR200CheckSumError(str_val)

    def _checksum_field(self):
        """Returns the checksum field of the current packet.

        If the entire packet has not been received will simply
        return the last two bytes which are unlikely checksum values."""
        try:
            return (self._pkt_data[-1] << 8) | self._pkt_data[-2]
        except IndexError:
            str_val = 'Packet too small to contain 16 bit checksum'
            logerr(str_val)
            raise WMR200CheckSumError(str_val)

    def verify_checksum(self):
        """Verifies packet for checksum correctness.
        
        Raises exception upon checksum failure as this is a catastrophic
        event."""
        if self._checksum_calculate() != self._checksum_field():
            str_val = ('Checksum error act:%x exp:%x'
                        % (self._checksum_calculate(), self._checksum_field()))
            logerr(str_val)
            logerr(self.to_string_raw('  packet:'))
            raise WMR200CheckSumError(str_val)

    def packet_timestamp(self):
        """Pulls the timestamp from the packet.  
        Must only be called by packets that have timestamps in the
        protocal packet."""
        try:
            minute = self._pkt_data[2]
            hour   = self._pkt_data[3]
            day    = self._pkt_data[4]
            month  = self._pkt_data[5]
            year   = 2000 + self._pkt_data[6]
            return time.mktime((year, month, day, hour, minute, \
                                0, -1, -1, -1))
        except IndexError:
            log_msg = ('Packet length too short to get timestamp len:%d'
                       % len(self._pkt_data))
            logerr(log_msg)
            raise WMR200ProtocolError(log_msg)

        except (OverflowError, ValueError), exception:
            log_msg = ('Packet timestamp with bogus fields %s' % exception)
            logerr(log_msg)
            raise WMR200ProtocolError(log_msg)

    def timestamp(self):
        """Returns either that timestamp or the PC time based upon
        configuration.  Caches the last timestamp to add to packets that do 
        not provide timestamps."""
        # Calculate the drift between pc time and the console time.
        # Only done first time through.
        if self.wmr200.time_delta is None:
            # This value is approximate as all timestamps from a given archive
            # interval will be the same while host time marches onwards.
            self.wmr200.time_delta = self.host_timestamp() - \
                    self.packet_timestamp()
            loginf('Time drift in seconds between host and console:%d' %
                   self.wmr200.time_delta)

        if self.wmr200.use_pc_time:
            self.wmr200.last_time_epoch = self.host_timestamp()
        else:
            self.wmr200.last_time_epoch = self.packet_timestamp()
        return self.wmr200.last_time_epoch

    def to_string_raw(self, out=''):
        """Returns raw string of this packet appended to optional
        input string"""
        for byte in self._pkt_data:
            out += '%02x ' % byte
        return out

    def print_cooked(self):
        """Debug method method to print the processed packet.
        
        Must be called after the Process() method."""
        out = ' Packet cooked: '
        out += '%s ' % self.pkt_name
        out += '%s ' % weeutil.weeutil.timestamp_to_string\
                (self.timestamp())
        out += 'len:%d ' % self.size_actual()
        out += 'fields:%d ' % len(self._record)
        out += str(self._record)
        logdbg(out)

class PacketLive(Packet):
    """Packets with live sensor data from console."""
    pkt_cnt = 0
    def __init__(self, wmr200):
        super(PacketLive, self).__init__(wmr200)
        PacketLive.pkt_cnt += 1

    @staticmethod
    def packet_live_data():
        """Yield live data packets to interface on the weewx engine."""
        return True

    @staticmethod
    def packet_archive_data():
        """Yield archived data packets to interface on the weewx engine."""
        return False

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketLive, self).packet_process()
        self._record.update({'dateTime' : self.timestamp(), })


class PacketArchive(Packet):
    """Packets with archived sensor data from console."""
    pkt_cnt = 0
    def __init__(self, wmr200):
        super(PacketArchive, self).__init__(wmr200)
        PacketArchive.pkt_cnt += 1

    @staticmethod
    def packet_live_data():
        """Yield live data packets to interface on the weewx engine."""
        return False

    @staticmethod
    def packet_archive_data():
        """Yield archived data packets to interface on the weewx engine."""
        return True

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketArchive, self).packet_process()
        self._record.update({'dateTime' : self.packet_timestamp(), })


class PacketControl(Packet):
    """Packets with protocol control info from console."""
    pkt_cnt = 0
    def __init__(self, wmr200):
        super(PacketControl, self).__init__(wmr200)
        PacketControl.pkt_cnt += 1

    @staticmethod
    def packet_live_data():
        """Yield live data packets to interface on the weewx engine."""
        return False

    @staticmethod
    def packet_archive_data():
        """Yield archived data packets to interface on the weewx engine."""
        return False

    def size_expected(self):
        """Control packets do not have length field and are only one byte."""
        return 1

    def verify_checksum(self):
        """This packet does not have a checksum."""
        pass

    def packet_complete(self):
        """Determines if packet is complete and ready for weewx engine
        processing."""
        # If we have detected a bogus packet then ensure we drop this
        # packet via this path.
        if self.size_actual() == 1:
            return True
        return False

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        self._record.update({'dateTime' : self.host_timestamp(), })

    def print_cooked(self):
        """Print the processed packet.
        
        This packet consists of a single byte and thus not much to print."""
        out = ' Packet cooked: '
        out += '%s ' % self.pkt_name
        logdbg(out)


class PacketHistoryReady(PacketControl):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xd1
    pkt_name = 'Archive Avail'
    pkt_len = 1
    def __init__(self, wmr200):
        super(PacketHistoryReady, self).__init__(wmr200)

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryReady, self).packet_process()
        # Immediately request to the console a command to send archived data.
        self.wmr200.request_archive_data()

class PacketHistoryData(PacketArchive):
    """Packet parser for archived data."""
    pkt_cmd = 0xd2
    pkt_name = 'Archive Data'
    # This is a variable length packet and this is the minimum length.
    # pkt_len = 0x31
    def __init__(self, wmr200):
        super(PacketHistoryData, self).__init__(wmr200)

    def timestamp(self):
        """This packet has a timestamp that must not be overridden by the
        potential configuration option of using pc time.
        So we always use the packet time stamp here and don't cache
        this timestamp either."""
        return self.packet_timestamp()

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketHistoryData, self).packet_process()

        self._record.update(decode_rain(self,     self._pkt_data[ 7:20]))
        self._record.update(decode_wind(self,     self._pkt_data[20:27]))
        self._record.update(decode_uvi(self,      self._pkt_data[27:28]))
        self._record.update(decode_pressure(self, self._pkt_data[28:32]))
        num_sensors = self._pkt_data[32]
        if DEBUG_PACKETS_ARCHIVE:
            loginf('Detected temp sensors:%d' % num_sensors)

        for i in xrange(0, num_sensors):
            base = 33 + i*7
            self._record.update(decode_temp(self, self._pkt_data[base:base+7]))

        # Tell wmr200 console we have processed it and can handle more.
        self.wmr200.request_archive_data()

        if DEBUG_PACKETS_ARCHIVE:
            loginf('  Archive packet')


def decode_wind(pkt, pkt_data):
    """Decode the wind portion of a wmr200 packet."""
    try:
        # Wind direction in steps of 22.5 degrees.
        # 0 is N, 1 is NNE and so on. See WIND_DIR_MAP for complete list.
        dir_deg = (pkt_data[0] & 0x0f) * 22.5
        # Low byte of gust speed in 0.1 m/s.
        gust_speed = ((((pkt_data[3]) & 0x0f) << 8)
                      | pkt_data[2]) / 10.0
        # High nibble is low nibble of average speed.
        # Low nibble of high byte and high nibble of low byte
        # of average speed. Value is in 0.1 m/s
        avg_speed = ((pkt_data[3] >> 4)
                     | ((pkt_data[4] << 4))) / 10.0
        # Windchill temperature. The value is in degrees F. If no windchill is
        # available byte 12 is zero.
        if pkt_data[5] != 0:
            windchill = (pkt_data[5] - 32.0) * (5.0 / 9.0)
        else:
            windchill = None
            # The console returns wind speeds in m/s. Our metric system requires
            # kph, so the result needs to be multiplied by 3.6.
        record = {'windSpeed'         : avg_speed * 3.60,
                  'windDir'           : dir_deg,
                  'usUnits'           : weewx.METRIC,
                  'windchill'         : windchill,
                 }
        # Sometimes the station emits a wind gust that is less than the
        # average wind.  Ignore it if this is the case.
        if gust_speed >= record['windSpeed']:
            record['windGust'] = gust_speed * 3.60

        if DEBUG_PACKETS_WIND:
            loginf('  Wind Dir: %s' % (WIND_DIR_MAP[pkt_data[0] & 0x0f]))
            loginf('  Gust: %.1f m/s Wind:%.1f m/s' % (gust_speed, avg_speed))
            if windchill != None:
                loginf('  Windchill: %.1f C' % (windchill))
        return record

    except IndexError:
        str_val = ('%s decode index failure' % pkt.pkt_name())
        logerr(str_val)
        raise WMR200ProtocolError(str_val)

class PacketWind(PacketLive):
    """Packet parser for wind."""
    pkt_cmd = 0xd3
    pkt_name = 'Wind'
    pkt_len = 0x10
    def __init__(self, wmr200):
        super(PacketWind, self).__init__(wmr200)

    def packet_process(self):
        """Decode a wind packet. Wind speed will be in kph

        Returns a packet that can be processed by the weewx engine."""
        super(PacketWind, self).packet_process()
        self._record.update(decode_wind(self, self._pkt_data[7:14]))
        # Save the wind record to be used for windchill and heat index
        self.wmr200.last_wind_record = self._record

def decode_rain(pkt, pkt_data):
    """Decode the rain portion of a wmr200 packet."""
    try:
        # Bytes 0 and 1: high and low byte of the current rainfall rate
        # in 0.1 in/h
        rain_rate = ((pkt_data[1] << 8) | pkt_data[0]) / 100.0
        # Bytes 2 and 3: high and low byte of the last hour rainfall in 0.1in
        rain_hour = ((pkt_data[3] << 8) | pkt_data[2]) / 100.0
        # Bytes 4 and 5: high and low byte of the last day rainfall in 0.1in
        rain_day = ((pkt_data[5] << 8) | pkt_data[4]) / 100.0
        # Bytes 6 and 7: high and low byte of the total rainfall in 0.1in
        rain_total = ((pkt_data[7] << 8) | pkt_data[6]) / 100.0
        # NB: in my experiments with the WMR100, it registers in increments of
        # 0.04 inches. Per Ejeklint's notes have you divide the packet values by
        # 10, but this would result in an 0.4 inch bucket --- too big. So, I'm
        # dividing by 100.
        record = {'rainRate'          : rain_rate,
                  'hourRain'          : rain_hour,
                  'dayRain'           : rain_day,
                  'totalRain'         : rain_total,
                  'usUnits'           : weewx.US}
        if DEBUG_PACKETS_RAIN:
            loginf("  Rain rate:%.02f hour_rain:%.02f day_rain:%.02f" %
                   (rain_rate, rain_hour, rain_day))
            loginf("  Total rain:%.02f" % rain_total)
        return record

    except IndexError:
        str_val = ('%s decode index failure' % pkt.pkt_name())
        logerr(str_val)
        raise WMR200ProtocolError(str_val)


class PacketRain(PacketLive):
    """Packet parser for rain."""
    pkt_cmd = 0xd4
    pkt_name = 'Rain'
    pkt_len = 0x16

    # Calibrates console rain values.
    rain_base_totalRain = None
    rain_last_totalRain = 0

    def __init__(self, wmr200):
        super(PacketRain, self).__init__(wmr200)

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketRain, self).packet_process()
        self._record.update(decode_rain(self, self._pkt_data[7:20]))
        # Upon start we need to calibrate the total rain presented by the
        # console.  This is used to calculate rain deltas between
        # polling periods.
        if PacketRain.rain_base_totalRain is None:
            PacketRain.rain_base_totalRain = self._record['totalRain']
        # Normalize rain total to value since last driver boot.
        self._record['totalRain'] -= PacketRain.rain_base_totalRain
        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain.
        # This record is the amount of rain occuring since last poll time.
        self._record['rain'] = \
                self._record['totalRain'] - PacketRain.rain_last_totalRain
        PacketRain.rain_last_totalRain = self._record['totalRain']


def decode_uvi(pkt, pkt_data):
    """Decode the uvi portion of a wmr200 packet."""
    try:
        record = { 'UV' : pkt_data[0 & 0x0f] }
        if DEBUG_PACKETS_UVI:
            loginf("  UV index:%s\n" % record['UV'])
        return record

    except IndexError:
        str_val = ('%s index decode index failure' % pkt.pkt_name())
        logerr(str_val)
        raise WMR200ProtocolError(str_val)


class PacketUvi(PacketLive):
    """Packet parser for ultra violet sensor."""
    pkt_cmd = 0xd5
    pkt_name = 'UVI'
    pkt_len = 0x0a
    def __init__(self, wmr200):
        super(PacketUvi, self).__init__(wmr200)

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketUvi, self).packet_process()
        self._record.update(decode_uvi(self, self._pkt_data[7:8]))

def decode_pressure(pkt, pkt_data):
    """Decode the pressure portion of a wmr200 packet."""
    try:
        # Low byte of pressure. Value is in hPa.
        # High nibble is forecast
        # Low nibble is high byte of pressure.
        # Unfortunately, we do not know if this is MSLP corrected pressure,
        # or "gauge" pressure. We will assume the former.
        pressure = float(((pkt_data[1] & 0x0f) << 8) | pkt_data[0])
        forecast = (pkt_data[1] >> 4) & 0x7

        # Similar to bytes 0 and 1, but altitude corrected
        # pressure. Upper nibble of byte 3 is still unknown. Seems to
        # be always 3.
        alt_pressure_console = float(((pkt_data[3] & 0x0f) << 8)
                                     | pkt_data[2])
        unknown_nibble = (pkt_data[3] >> 4)

        alt_pressure_weewx = \
                weewx.wxformulas.altimeter_pressure_Metric\
                (pressure, pkt.wmr200.altitude)

        record = {'barometer'   : alt_pressure_console,
                  'altimeter'   : pressure,
                  'pressure'    : alt_pressure_weewx,
                  'forecastIcon': forecast}

        if DEBUG_PACKETS_PRESSURE:
            loginf('  Forecast: %s' % FORECAST_MAP[forecast])
            loginf('  Raw pressure: %.02f hPa' % (pressure))
            if unknown_nibble != 3:
                loginf('  Pressure unknown nibble: 0x%x' % (unknown_nibble))
            loginf('  Altitude corrected pressure: %.02f hPa console' %
                   (alt_pressure_console))
            loginf('  Altitude corrected pressure: %.02f hPa weewx' %
                   (alt_pressure_weewx))
        return record

    except IndexError:
        str_val = ('%s index decode index failure' % pkt.pkt_name())
        logerr(str_val)
        raise WMR200ProtocolError(str_val)


class PacketPressure(PacketLive):
    """Packet parser for barometer sensor."""
    pkt_cmd = 0xd6
    pkt_name = 'Pressure'
    pkt_len = 0x0d
    def __init__(self, wmr200):
        super(PacketPressure, self).__init__(wmr200)

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketPressure, self).packet_process()
        self._record.update(decode_pressure(self, self._pkt_data[7:11]))


def decode_temp(pkt, pkt_data):
    """Decode the temperature portion of a wmr200 packet."""
    try:
        record = {}
        # The historic data can contain data from multiple sensors. I'm not
        # sure if the 0xD7 frames can do too. I've never seen a frame with
        # multiple sensors. But historic data bundles data for multiple
        # sensors.
        # Byte 0: low nibble contains sensor ID. 0 for base station.
        sensor_id = pkt_data[0] & 0x0f
        temp_trend = (pkt_data[0] >> 6) & 0x3
        hum_trend = (pkt_data[0] >> 4) & 0x3

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        temp = (((pkt_data[2] & 0x0f) << 8) | pkt_data[1]) / 10.0
        if pkt_data[2] & 0x80:
            temp *= -1

        # The humidity in percent.
        humidity = pkt_data[3]

        # The high nible contains the sign indicator.
        # The low nibble is the high byte of the temperature.
        # The low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        dew_point = (((pkt_data[5] & 0x0f) << 8)
                     | pkt_data[4]) / 10.0
        if pkt_data[5] & 0x80:
            dew_point *= -1

        # Heat index
        if pkt_data[6] != 0:
            heat_index = (pkt_data[6] - 32) / 1.8
        else:
            heat_index = None

        if sensor_id == 0:
            record['inTemp']      = temp
            record['inHumidity']  = humidity
        elif sensor_id == 1:
            record['outTemp']     = temp
            record['dewpoint'] = \
                    weewx.wxformulas.dewpointC(temp, humidity)
            record['outHumidity'] = humidity
            record['heatindex'] = \
                    weewx.wxformulas.heatindexC(temp, humidity)
        elif sensor_id >= 2:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            record['extraTemp%d'  % sensor_id] = temp
            record['extraHumid%d' % sensor_id] = humidity

        if DEBUG_PACKETS_TEMP:
            loginf(('  Temperature id:%d %.1f C trend: %s'
                    % (sensor_id, temp,
                       TRENDS[temp_trend])))
            loginf('  Humidity id:%d %d%% trend: %s' % (sensor_id, humidity,
                                                        TRENDS[hum_trend]))
            loginf(('  Dew point id:%d: %.1f C' % (sensor_id, dew_point)))
            if heat_index:
                loginf('  Heat id:%d index:%d' % (sensor_id, heat_index))
        return record

    except IndexError:
        str_val = ('%s index decode index failure' % pkt.pkt_name())
        logerr(str_val)
        raise WMR200ProtocolError(str_val)


class PacketTemperature(PacketLive):
    """Packet parser for temperature and humidity sensor."""
    pkt_cmd = 0xd7
    pkt_name = 'Temperature'
    pkt_len = 0x10
    def __init__(self, wmr200):
        super(PacketTemperature, self).__init__(wmr200)

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketTemperature, self).packet_process()
        self._record.update(decode_temp(self, self._pkt_data[7:14]))


class PacketStatus(PacketLive):
    """Packet parser for console sensor status."""
    pkt_cmd = 0xd9
    pkt_name = 'Status'
    pkt_len = 0x08
    def __init__(self, wmr200):
        super(PacketStatus, self).__init__(wmr200)

    def timestamp(self):
        """This packet does not have a timestamp so we just return the
        last timestamp from the previous packet read.  
        If there is no previous timestamp then we return the initial PC
        timestamp."""
        return self.wmr200.last_time_epoch

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine.
        
        Not all console status aligns with the weewx API but we try
        to make it fit."""
        super(PacketStatus, self).packet_process()
        # Setup defaults as good status.
        self._record.update({'inTempBatteryStatus'  : 1.0,
                             'OutTempBatteryStatus' : 1.0,
                             'rainBatteryStatus'    : 1.0,
                             'windBatteryStatus'    : 1.0,
                             'txBatteryStatus'      : 1.0,
                             'rxCheckPercent'       : 1.0 })

        # This information is sent to syslog
        if self.wmr200.sensor_stat:
            if self._pkt_data[2] & 0x2:
                logwar('Sensor 1 fault (temp/hum outdoor)')

            if self._pkt_data[2] & 0x1:
                logwar('Wind sensor fault')

            if self._pkt_data[3] & 0x20:
                logwar('UV Sensor fault')

            if self._pkt_data[3] & 0x10:
                logwar('Rain sensor fault')

            if self._pkt_data[5] & 0x20:
                logwar('UV sensor: Battery low')

        # This information can be passed up to weewx.
        if self._pkt_data[4] & 0x02:
            self._record['outTempBatteryStatus'] = 0.0
            if self.wmr200.sensor_stat:
                logwar('Sensor 1: Battery low')

        if self._pkt_data[4] & 0x01:
            self._record['windBatteryStatus'] = 0.0
            if self.wmr200.sensor_stat:
                logwar('Wind sensor: Battery low')

        if self._pkt_data[5] & 0x10:
            self._record['rainBatteryStatus'] = 0.0
            if self.wmr200.sensor_stat:
                logwar('Rain sensor: Battery low')

        # Output packet to try to understand other fields.
        if DEBUG_PACKETS_STATUS:
            loginf(self.to_string_raw(' Sensor packet:'))


class PacketEraseAcknowledgement(PacketControl):
    """Packet parser for archived data is ready to receive."""
    pkt_cmd = 0xdb
    pkt_name = 'Erase Acknowledgement'
    pkt_len = 0x01
    def __init__(self, wmr200):
        super(PacketEraseAcknowledgement, self).__init__(wmr200)


class PacketFactory(object):
    """Factory to create proper packet from first command byte from device."""
    def __init__(self, *subclass_list):
        self.subclass = dict((s.pkt_cmd, s) for s in subclass_list)
        self.skipped_bytes = 0

    def get_packet(self, pkt_cmd, wmr200):
        """Returns an instance of packet parser indexed from packet command.
       
        Returns None if there was no mapping for the protocol command.

        Upon startup we may read partial packets. We need to resync to a
        valid packet command from the weather console device if we start
        reading in the middle of a previous packet. 
       
        We may also get out of sync during operation."""
        if pkt_cmd in self.subclass:
            if self.skipped_bytes:
                logwar(('Skipped bytes before resync:%d' %
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

        loginf(('Created watchdog thread to poke for live data every %d'
                ' seconds') % self.poke_time)

    def run(self):
        """Periodically inform the main driver thread to request live data.

        When its time to shutdown this thread, the main thread will send any
        string across the socket.  This both wakes up this timer thread and
        also tells it to expire."""
        loginf('Started watchdog thread live data')
        while True:
            self.wmr200.ready_to_poke(True)
            main_thread_comm = \
                    select.select([self.sock_rd], [], [], self.poke_time)
            if main_thread_comm[0]:
                # Data is ready to read on socket to indicate thread teardown.
                buf = self.sock_rd.recv(4096)
                loginf('Watchdog received %s' % buf)
                break

        loginf('Watchdog thread exiting')


class PollUsbDevice(threading.Thread):
    """A thread to continually poll for data from a USB device.
    
    Some devices may overflow buffers if not drained within a timely manner.
    
    This thread will read block on the USB port and buffer data from the
    device for consumption."""
    def __init__(self, kwargs):
        super(PollUsbDevice, self).__init__()
        self.wmr200 = kwargs['wmr200']
        self.usb_device = self.wmr200.usb_device

        # Buffer list to read data from weather console
        self._buf = []
        # Lock to wrap around the buffer
        self._lock_poll = threading.Lock()
        # Conditional variable to gate thread after reset applied.
        self._cv_poll = threading.Condition()
        # One thread is created for each reset sequence.
        self._reset_sent = False
        loginf('Created USB polling thread to read block on device')

    def run(self):
        """Polling function to block read the USB device.
        
        This method appends new data after previous buffer
        data in preparation for reads to the main driver
        thread.
        
        Once this thread is started it will be gated by
        a reset to the weather console device to sync it
        up."""
        loginf('Started poll_usb_device thread live data')

        # Wait for a reset to occur from the main thread.
        self._cv_poll.acquire()
        while not self._reset_sent:
            self._cv_poll.wait()
        self._cv_poll.release()
        loginf('USB polling thread started after console reset')

        # Read and discard next data from weather console device.
        buf = self.usb_device.read_device()

        # Loop indefinitely until main thread indicates time to expire.
        while self.wmr200.poll_usb_device_enable():
            try:
                buf = self.usb_device.read_device()
                if buf:
                    self._lock_poll.acquire()
                    # Append the list of bytes to this buffer.
                    self._buf.append(buf)
                    self._lock_poll.release()
                else:
                    # We probably could poke the device after
                    # a read timeout.
                    self.wmr200.ready_to_poke(True)

            except WMR200ProtocolError:
                logerr('USB overflow')
        loginf('USB device polling thread exiting')

    def read_usb_device(self):
        """Reads the buffered USB device data.
        
        Returns a list of bytes.
        Called from main thread.  """
        buf = []
        self._lock_poll.acquire()
        if len(self._buf):
            buf = self._buf.pop(0)
        self._lock_poll.release()
        return buf

    def flush_usb_device(self):
        """Flush any previous USB device data.
        Called from main thread."""
        self._lock_poll.acquire()
        self._buf = []
        self._lock_poll.release()
        loginf('Flushed USB device')

    def reset_console(self):
        """Send a reset to wake up the weather console device

        Flush any previous USB device data.
        Called from main thread."""
        buf = [0x20, 0x00, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.write_device(buf)
            if DEBUG_COMM:
                loginf('Reset device')
            self._reset_sent = True
            time.sleep(1)
            # Tell thread it can proceed
            self._cv_poll.acquire()
            self._cv_poll.notify()
            self._cv_poll.release()

        except usb.USBError, exception:
            logerr(('reset_console() Unable to send USB control'
                           'message'))
            logerr('****  %s' % exception)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)


class WMR200(weewx.abstractstation.AbstractStation):
    """Driver for the Oregon Scientific WMR200 station."""

    def __init__(self, **stn_dict) :
        """Initialize the wmr200 driver.
        
        NAMED ARGUMENTS:
        altitude: The altitude in meters. [Required]
        sensor_status: Print sensor faults or failures to syslog. [Optional]
          Default is True.
        use_pc_time: Use the console timestamp or the Pc. [Optional]
          Default is False
        erase_archive:  Erasae archive upon startup.  [Optional]
          Default is False 

        --- User should not typically change anything below here ---

        vendor_id: The USB vendor ID for the WMR [Optional]
          Default is 0xfde.
        product_id: The USB product ID for the WM [Optional]
          Default is 0xca01.
        interface: The USB interface [Optional]
          Default is 0]
        in_endpoint: The IN USB endpoint used by the WMR [Optional]
          Default is usb.ENDPOINT_IN + 1]
        """
        super(WMR200, self).__init__()

        ## User configurable options
        self._altitude     = stn_dict['altitude']
        # Provide sensor faults in syslog.
        self._sensor_stat = weeutil.weeutil.tobool(stn_dict.get('sensor_status',
                                                                True))
        # Use pc timestamps or weather console timestamps.
        self._use_pc_time = \
                weeutil.weeutil.tobool(stn_dict.get('use_pc_time', False))

        # Use archive data when possible.
        self._erase_archive = \
                weeutil.weeutil.tobool(stn_dict.get('erase_archive', False))

        # User configurable options but not recommended
        vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        product_id        = int(stn_dict.get('product_id', '0xca01'), 0)
        interface         = int(stn_dict.get('interface', 0))
        in_endpoint       = int(stn_dict.get('IN_endpoint',
                                             usb.ENDPOINT_IN + 1))

        # Buffer of bytes read from weather console device.
        self._buf = []

        # Packet created from the buffer data read from the weather console
        # device.
        self.pkt = None

        # Setup the generator to get a byte stream from the console.
        self.genByte = self._generate_bytestream

        # Calculate time delta in seconds between host and console.
        self.time_delta = None

        # Create USB accessor to communiate with weather console device.
        self.usb_device = UsbDevice()

        # Pass USB parameters to the USB device accessor.
        self.usb_device.in_endpoint = in_endpoint
        self.usb_device.interface  = interface

        # Locate the weather console device on the USB bus.
        if not self.usb_device.find_device(vendor_id, product_id):
            logcrt('Unable to find device %x %x' % (vendor_id, product_id))

        # Open the weather console USB device for read and writes.
        self.usb_device.open_device()

        # Initialize watchdog to poke device to request live
        # data stream.
        self._rdy_to_poke = True

        # Archived packets.
        self._pkt_archive = []

        # Create the lock to sync between main thread and watchdog thread.
        self._poke_lock = threading.Lock()

        # Create a socket pair to communicate with the watchdog thread.
        (self.sock_rd, self.sock_wr) = \
                socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM, 0)

        # Create the watchdog thread to request live data.
        self._thread_watchdog = RequestLiveData(
            kwargs = {'wmr200'    : self,
                      'poke_time' : _WMR200_REQUEST_LIVE_DATA_INTERVAL,
                      'sock_rd'   : self.sock_rd})

        # Create the usb polling device thread.
        self._thread_usb_poll = PollUsbDevice(kwargs={'wmr200' :
                                                        self})

        # Start the usb polling device thread.
        self._poll_device_enable = True
        self._thread_usb_poll.start()

        # Send the device a reset
        self._thread_usb_poll.reset_console()

        # Start the watchdog for live data thread.
        self._thread_watchdog.start()

        # Not all packets from wmr200 have timestamps, yet weewx requires
        # timestamps on all packets pass up the stack.  So we will use the 
        # timestamp from the most recent packet, but still need to see an
        # initial timestamp, so we'll just use PC time.
        self.last_time_epoch = int(time.time() + 0.5)

        # Restart counter in case driver crashes and is restarted by the
        # weewx engine.
        global STAT_RESTART
        STAT_RESTART += 1
        if STAT_RESTART > 1:
            logwar(('Restart count: %d') % STAT_RESTART)

        # Debugging flags
        global DEBUG_WRITES
        DEBUG_WRITES = int(stn_dict.get('debug_writes', 0))
        global DEBUG_COMM
        DEBUG_COMM = int(stn_dict.get('debug_comm', 0))
        global DEBUG_CONFIG_DATA
        DEBUG_CONFIG_DATA = int(stn_dict.get('debug_config_data', 0))
        global DEBUG_PACKETS_RAW
        DEBUG_PACKETS_RAW = int(stn_dict.get('debug_packets_raw', 0))
        global DEBUG_PACKETS_COOKED
        DEBUG_PACKETS_COOKED = int(stn_dict.get('debug_packets_cooked', 0))
        global DEBUG_PACKETS_ARCHIVE
        DEBUG_PACKETS_ARCHIVE = int(stn_dict.get('debug_packets_archive', 0))
        global DEBUG_PACKETS_TEMP
        DEBUG_PACKETS_TEMP = int(stn_dict.get('debug_packets_temp', 0))
        global DEBUG_PACKETS_WIND
        DEBUG_PACKETS_WIND = int(stn_dict.get('debug_packets_wind', 0))
        global DEBUG_PACKETS_STATUS
        DEBUG_PACKETS_STATUS = int(stn_dict.get('debug_packets_status', 0))
        global DEBUG_PACKETS_PRESSURE
        DEBUG_PACKETS_PRESSURE = int(stn_dict.get('debug_packets_pressure', 0))

        if DEBUG_CONFIG_DATA:
            loginf('Configuration setup')
            loginf('  Altitude:%d' % self._altitude)
            loginf('  Log sensor faults: %s' % self._sensor_stat)
            loginf('  Using PC Time: %s' % self._use_pc_time)
            loginf('  Erase archive data: %s' % self._erase_archive)


    @property
    def altitude(self):
        """Return the altitude in meters for various calculations."""
        return self._altitude

    @property
    def sensor_stat(self):
        """Return if sensor status is enabled for device."""
        return self._sensor_stat

    @property
    def use_pc_time(self):
        """Flag to use pc time rather than weather console time."""
        return self._use_pc_time

    def ready_to_poke(self, val):
        """Set info that device is ready to be poked."""
        self._poke_lock.acquire()
        self._rdy_to_poke = val
        self._poke_lock.release()

    def is_ready_to_poke(self):
        """Get info that device is ready to be poked."""
        self._poke_lock.acquire()
        val = self._rdy_to_poke
        self._poke_lock.release()
        return val

    def poll_usb_device_enable(self):
        """The USB thread calls this to enable data reads from the console."""
        return self._poll_device_enable

    def _write_cmd(self, cmd):
        """Writes a single command to the wmr200 console."""
        buf = [0x01, cmd, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.write_device(buf)
        except usb.USBError, exception:
            msg = ('Write_cmd() Unable to send USB cmd:0x%02x control message' %
                   cmd)
            logerr(msg)
            # Convert to a Weewx error:
            raise weewx.WakeupError(exception)

    def _poke_console(self):
        """Send a heartbeat command to the weather console.

        This is used to inform the weather console to continue streaming
        live data across the USB bus.  Otherwise it enters archive mode
        were data is stored on the weather console."""
        self._write_cmd(0xD0)

        if self._erase_archive:
            self._write_cmd(0xDB)

        # Reset the ready to poke flag.
        self.ready_to_poke(False)
        if DEBUG_COMM:
            loginf('Poked device for live data')

    def _generate_bytestream(self):
        """Generator to provide byte stream to packet collector.
        
        We need to return occasionally to handle both reading data
        from the weather console and handing that data."""
        while True:
            # Read WMR200 protocol bytes from the weather console
            # via a proxy thread that ensure we drain the USB
            # fifo data from the weather console.
            buf = self._thread_usb_poll.read_usb_device()

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

    def _poll_for_data(self):
        """Poll for data from the weather console device.
        
        Read a byte from the weather console.  If we are starting
        a new packet, get one using that byte from the packet factory.
        Otherwise add the byte to the current packet.
        Each USB packet may stradle a protocol packet so make sure
        we assign the data appropriately."""
        for byte in self.genByte():
            if self.pkt:
                self.pkt.append_data(byte)
            else:
                # This may return None if we are out of sync
                # with the console.
                self.pkt = PACKET_FACTORY.get_packet(byte, self)

            if self.pkt is not None and self.pkt.packet_complete():
                # If we have a complete packet then bail to handle it.
                return

        # Prevent busy loop by suspending process a bit to
        # wait for usb read thread to accumulate data from the
        # weather console.
        time.sleep(_WMR200_USB_POLL_INTERVAL)

    def request_archive_data(self):
        """Request archive packets from console."""
        self._write_cmd(0xDA)

    def print_stats(self):
        """Print summary of driver statistics."""
        loginf('Received live packets:%d archive_packets:%d'
               ' control_packets:%d' % (PacketLive.pkt_cnt,
               PacketArchive.pkt_cnt, PacketControl.pkt_cnt))
        loginf('Received bytes:%d sent bytes:%d' %
               (self.usb_device.byte_cnt_rd,
                self.usb_device.byte_cnt_wr))

    def genLoopPackets(self):
        """Main generator function that continuously returns loop packets

        weewx api to return live records."""
        # Reset the current packet upon entry.
        self.pkt = None

        while True:
            # Loop through indefinitely generating records to the
            # weewx engine.  This loop may resume at the yield()
            # or upon entry during any exception, even an exception
            # not generated from this driver.  e.g. weewx.service.
            if self.pkt is not None and self.pkt.packet_complete():
                if DEBUG_PACKETS_RAW:
                    loginf(self.pkt.to_string_raw(' Packet Raw:'))

                # Drop any bogus packets.
                if self.pkt.is_bogus:
                    logerr(self.pkt.to_string_raw('Discarding bogus packet:'))
                else:
                    # This will raise exception if checksum fails.
                    self.pkt.verify_checksum()
                    self.pkt.packet_process()
                    if DEBUG_PACKETS_COOKED:
                        self.pkt.print_cooked()
                    if self.pkt.packet_live_data():
                        logdbg('Presenting weewx live packet %d' %
                               PacketLive.pkt_cnt)
                        yield self.pkt.packet_record()
                    elif self.pkt.packet_archive_data():
                        # Append to archive list for next time weewx engine
                        # requests archived packets.
                        self._pkt_archive.append(self.pkt)
                        logdbg(('Retrieved archive packet rx:%d cnt:%d' %
                                (PacketArchive.pkt_cnt,
                                 len(self._pkt_archive))))
                    else:
                        logdbg('Acknowledged control packet cnt:%d' %
                               PacketControl.pkt_cnt)

                # Reset this packet to get ready for next one
                self.pkt = None

            # If we are not in the middle of collecting a packet
            # and it's time to poke the console then do it here.
            if self.pkt is None and self.is_ready_to_poke():
                self._poke_console()

            # Pull data from the weather console.
            self._poll_for_data()

    def hardware_name(self):
        """weewx api."""
        return _WMR200_DRIVER_NAME

    def XXXgenArchiveRecords(self, since_ts):
    ##def genArchiveRecords(self, since_ts):
        """A generator function to return archive packets from the wmr200.
        
        weewx api to return archive records.
        since_ts: A timestamp. All data since (but not including) this time
        will be returned.
        Pass in None for all data
        
        yields: a sequence of dictionaries containing the data
        """
        if since_ts:
            loginf('genArchiveRecords() Getting archive packets since %s'
                   % weeutil.weeutil.timestamp_to_string(since_ts))
        else :
            loginf('genArchiveRecords() Getting all archive packets')

        cnt = 0
        loginf(('genArchiveRecords() archive packets:%d' %
                len(self._pkt_archive)))
        while len(self._pkt_archive):
            pkt = self._pkt_archive.pop(0)
            pkt.print_cooked()
            cnt += 1
            if since_ts and pkt.packet_timestamp() > since_ts:
                loginf(('genArchiveRecords() yielding archive record:%s' %
                        weeutil.weeutil.timestamp_to_string(
                            pkt.packet_timestamp())))
                yield pkt.packet_record()
            else:
                loginf(('genArchiveRecords() dropping archive records:%s' %
                        weeutil.weeutil.timestamp_to_string(
                            pkt.packet_timestamp())))
            loginf(('genArchiveRecords() Handled archive record cnt:%d' %
                    cnt))

    def closePort(self):
        """Closes the USB port to the device.
        
        weewx api to shutdown the weather console."""
        # Send a command to the wmr200 console indicating
        # we are leaving.
        self._write_cmd(0xDF)
        # Let the polling thread die off.
        self._poll_device_enable = False
        # Join with the polling thread.
        self._thread_usb_poll.join()
        if self._thread_usb_poll.isAlive():
            logerr('USB polling thread still alive')
        else:
            loginf('USB polling thread expired')

        # Shutdown the watchdog thread.
        self.sock_wr.send('shutdown')
        # Join with the watchdog thread.
        self._thread_watchdog.join()
        if self._thread_watchdog.isAlive():
            logerr('Watchdog thread still alive')
        else:
            loginf('Watchdog thread expired')

        self.print_stats()

        # Shutdown the USB acccess to the weather console device.
        self.usb_device.close_device()
        loginf('Driver gracefully exiting')

