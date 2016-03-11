#
# Copyright (c) 2013 Chris Manton <cmanton@gmail.com>  www.onesockoff.org
# See the file LICENSE.txt for your full rights.
#
# Special recognition to Lars de Bruin <l...@larsdebruin.net> for contributing
# packet decoding code.
#
# pylint parameters
# suppress global variable warnings
#   pylint: disable-msg=W0603
# suppress weewx driver methods not implemented
#   pylint: disable-msg=W0223  
# suppress weewx driver methods non-conforming name
#   pylint: disable-msg=C0103
# suppress too many lines in module
#   pylint: disable-msg=C0302
# suppress too many instance attributes
#   pylint: disable-msg=R0902
# suppress too many public methods
#   pylint: disable-msg=R0904
# suppress too many statements
#   pylint: disable-msg=R0915
# suppress unused arguments   e.g. loader(...,engine)
#   pylint: disable-msg=W0613
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

import weewx.drivers
import weeutil.weeutil

DRIVER_NAME = 'WMR200'
DRIVER_VERSION = "3.1"


def loader(config_dict, engine):  # @UnusedVariable
    return WMR200(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WMR200ConfEditor()


# General decoding sensor maps.
WIND_DIR_MAP = {0: 'N', 1: 'NNE', 2: 'NE', 3: 'ENE',
                4: 'E', 5: 'ESE', 6: 'SE', 7: 'SSE',
                8: 'S', 9: 'SSW', 10: 'SW', 11: 'WSW',
                12: 'W', 13: 'WNW', 14: 'NW', 15: 'NNW'}
FORECAST_MAP = {0: 'Partly Cloudy', 1: 'Rainy', 2: 'Cloudy',
                3: 'Sunny', 4: 'Clear Night', 5: 'Snowy',
                6: 'Partly Cloudy Night', 7: 'Unknown7'}
TRENDS = {0: 'Stable', 1: 'Rising', 2: 'Falling', 3: 'Undefined'}

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
DEBUG_CHECKSUM = 0

def logmsg(dst, msg):
    """Base syslog helper"""
    syslog.syslog(dst, ('%s: %s: %s' %
                        (_WMR200_DRIVER_NAME,
                         threading.currentThread().getName(), msg)))

def logdbg(msg):
    """Debug syslog helper"""
    logmsg(syslog.LOG_DEBUG, 'D ' + msg)

def loginf(msg):
    """Info syslog helper"""
    logmsg(syslog.LOG_INFO, 'I ' + msg)

def logwar(msg):
    """Warning syslog helper"""
    logmsg(syslog.LOG_WARNING, 'W ' + msg)

def logerr(msg):
    """Error syslog helper"""
    logmsg(syslog.LOG_ERR, 'E ' + msg)

def logcrt(msg):
    """Critical syslog helper"""
    logmsg(syslog.LOG_CRIT, 'C ' + msg)


class WMR200PacketParsingError(Exception):
    """A driver handled recoverable packet parsing error condition."""
    def __init__(self, msg):
        super(WMR200PacketParsingError, self).__init__()
        self._msg = msg

    @property
    def msg(self):
        """Exception message to be logged to console."""
        return self._msg


class WMR200ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""
    def __init__(self, msg):
        super(WMR200ProtocolError, self).__init__()
        self._msg = msg 
        logerr(msg)


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
        # default to a sane endpoint
        self.in_endpoint = usb.ENDPOINT_IN + 1
        # only one interface
        self.interface = 0

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
            raise weewx.WakeupError(exception)
        except AttributeError, exception:
            logcrt('open_device() Device not specified.')
            raise weewx.WakeupError(exception)

        # Detach any old claimed interfaces
        try:
            self.handle.detachKernelDriver(self.interface)
        except usb.USBError:
            pass

        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError, exception:
            logcrt(('open_device() Unable to'
                    ' claim USB interface. Reason: %s' % exception))
            raise weewx.WakeupError(exception)

    def close_device(self):
        """Close a device for access.

        NOTE(CMM) There is no busses[].devices[].close() so under linux the
        file descriptor will remain open for the life of the process.
        An OS independant mechanism is required so 'lsof' and friends will
        not be cross platform."""
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
            msg = 'read_device() No USB handle for usb_device Read'
            logerr(msg)
            raise weewx.WeeWxIOError(msg)

        report = None
        try:
            report = self.handle.interruptRead(self.in_endpoint,
                                               _WMR200_USB_FRAME_SIZE,
                                               int(self.timeout_read) * 1000)

            # I think this value indicates that the buffer has overflowed.
            if report[0] == 8:
                msg = 'USB read_device overflow error'
                logerr(msg)
                raise weewx.WeeWxIOError(msg)

            self.byte_cnt_rd += len(report)
            # The first byte is the size of valid data following.
            # We only want to return the valid data.
            if DEBUG_READS:
                buf = ''
                for byte in report[1:report[0]+1]:
                    buf += '%02x ' % byte
                logdbg('read_device(): %s' % buf)
            return report[1:report[0] + 1]

        except IndexError, e:
            # This indicates we failed an index range above.
            logerr('read_device() Failed the index rage %s: %s' % (report, e))

        except usb.USBError, ex:
            # No data presented on the bus.  This is a normal part of
            # the process that indicates that the current live records
            # have been exhausted.  We have to send a heartbeat command
            # to tell the weather console to start streaming live data
            # again.
            if ex.args[0].find('No data available') == -1:
                msg = 'read_device() USB Error Reason:%s' % ex
                logerr(msg)
                raise weewx.WeeWxIOError(msg)
            else:
                # No data avail...not an error but probably ok.
                logdbg(('No data received in'
                       ' %d seconds' % int(self.timeout_read)))
                return []

    def write_device(self, buf):
        """Writes a command packet to the device."""
        # Unclear how to create this number, but is the wValue portion
        # of the set_configuration() specified in the USB spec.
        value = 0x00000220

        if not self.handle:
            msg = 'No USB handle for usb_device Write'
            logerr(msg)
            raise weewx.WeeWxIOError(msg)

        try:
            if DEBUG_WRITES:
                logdbg('write_device(): %s' % buf)
            self.byte_cnt_wr += len(buf)
            self.handle.controlMsg(
                usb.TYPE_CLASS + usb.RECIP_INTERFACE, # requestType
                0x0000009,                            # request
                buf,
                value,                                # value
                0x0000000,                            # index
                _WMR200_USB_RESET_TIMEOUT)            # timeout
        except usb.USBError, exception:
            msg = ('write_device() Unable to'
                   ' send USB control message %s' % exception)
            logerr(msg)
            # Convert to a Weewx error:
            raise weewx.WeeWxIOError(exception)


class Packet(object):
    """Top level class for all WMR200 packets.

    All wmr200 packets inherit from this class.  The process() method
    is used to provide useful data to the weewx engine.  Some packets
    require special processing due to discontinuities in the wmr200
    protocol."""
    pkt_cmd = 0
    pkt_name = 'AbstractPacket'
    pkt_len = 0
    pkt_id = 0
    def __init__(self, wmr200):
        """Initialize base elements of the packet parser."""
        # Keep reference to the wmr200 for any special considerations
        # or options.
        self.wmr200 = wmr200
        # Accumulated raw byte data from console.
        self._pkt_data = []
        # Record dictionary to pass to weewx engine.
        self._record = {}
        # Add the command byte as the first field
        self.append_data(self.pkt_cmd)
        # Packet identifier
        Packet.pkt_id += 1
        self.pkt_id = Packet.pkt_id

    def append_data(self, char):
        """Appends new data to packet buffer.

        Verifies that the size is a reasonable value.
        Upon startup or other times we can may get out
        of sync with the weather console."""
        self._pkt_data.append(char)
        if len(self._pkt_data) == 2 and \
          self._pkt_data[1] > _WMR200_MAX_PACKET_SIZE:
            raise weewx.WeeWxIOError('Max packet size exceeded')     

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
        
        This method assumes the packet is at least 2 bytes long"""
        if self.size_actual() < 2:
            return False
        return self.size_actual() == self.size_expected()

    def packet_process(self):
        """Process the raw data and creates a record field."""
        # Convention is that this driver only works in metric units.
        self._record.update({'usUnits': weewx.METRIC})
        if DEBUG_PACKETS_RAW or DEBUG_PACKETS_COOKED:
            logdbg('Processing %s' % self.pkt_name)
        if self.pkt_len and self.pkt_len != self.size_actual():
            logwar(('Unexpected packet size act:%d exp:%d' %
                    (self.size_actual(), self.pkt_len)))
        # If applicable calculate time drift between packet and host.
        self.calc_time_drift()

    def packet_record(self):
        """Returns the dictionary of processed records for this packet."""
        return self._record

    def record_get(self, key):
        """Returns the record indexed by the key."""
        try:
            return self._record[key]
        except KeyError:
            logerr('Record get key not found in record key:%s' % key)

    def record_set(self, key, val):
        """Sets the record indexed by the key."""
        try:
            self._record[key] = val
        except KeyError:
            logerr('Record set key not found in record key:%s val:%s'
                   % (key, val))

    def record_update(self, record):
        """Updates record dictionary with additional dictionary."""
        try:
            self._record.update(record)
        except (TypeError, KeyError):
            logerr('Record update failed to apply record:%s' % record)

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
            msg = 'Packet too small to compute 16 bit checksum'
            raise WMR200ProtocolError(msg)

    def _checksum_field(self):
        """Returns the checksum field of the current packet.

        If the entire packet has not been received will simply
        return the last two bytes which are unlikely checksum values."""
        try:
            return (self._pkt_data[-1] << 8) | self._pkt_data[-2]
        except IndexError:
            msg = 'Packet too small to contain 16 bit checksum'
            raise WMR200ProtocolError(msg)

    def verify_checksum(self):
        """Verifies packet for checksum correctness.
        
        Raises exception upon checksum failure unless configured to drop."""
        if self._checksum_calculate() != self._checksum_field():
            msg = ('Checksum miscompare act:0x%04x exp:0x%04x' % 
                (self._checksum_calculate(), self._checksum_field()))
            logerr(self.to_string_raw('%s packet:' % msg))
            if self.wmr200.ignore_checksum:
                raise WMR200PacketParsingError(msg)
            raise weewx.CRCError(msg)

        # Debug test to force checksum recovery testing.
        if DEBUG_CHECKSUM and (self.pkt_id % DEBUG_CHECKSUM) == 0:
            raise weewx.CRCError('Debug forced checksum error')

    @staticmethod
    def timestamp_host():
        """Returns the host epoch timestamp"""
        return int(time.time() + 0.5)

    def timestamp_record(self):
        """Returns the epoch timestamp in the record."""
        try:
            return self._record['dateTime']
        except KeyError:
            msg = 'timestamp_record() Timestamp not set in record'
            logerr(msg)
            raise weewx.ViolatedPrecondition(msg)

    def _timestamp_packet(self, pkt_data):
        """Pulls the epoch timestamp from the packet."""
        try:
            minute = pkt_data[0]
            hour   = pkt_data[1]
            day    = pkt_data[2]
            month  = pkt_data[3]
            year   = 2000 + pkt_data[4]
            return time.mktime((year, month, day, hour, minute,
                                0, -1, -1, -1))
        except IndexError:
            msg = ('Packet length too short to get timestamp len:%d'
                    % len(self._pkt_data))
            raise WMR200ProtocolError(msg)

        except (OverflowError, ValueError), exception:
            msg = ('Packet timestamp with bogus fields min:%d hr:%d day:%d'
	               ' m:%d y:%d %s' % (pkt_data[0], pkt_data[1], 
                   pkt_data[2], pkt_data[3], pkt_data[4], exception))
            raise WMR200PacketParsingError(msg)

    def timestamp_packet(self):
        """Pulls the epoch timestamp from the packet.  
        Must only be called by packets that have timestamps in the
        protocal packet."""
        return self._timestamp_packet(self._pkt_data[2:7])

    def calc_time_drift(self):
        """Calculate time drift between host and packet

        Not all packets have a live timestamp so must be implemented
        by the packet type."""
        pass

    def to_string_raw(self, out=''):
        """Returns raw string of this packet appended to optional
        input string"""
        for byte in self._pkt_data:
            out += '%02x ' % byte
        return out

    def print_cooked(self):
        """Debug method method to print the processed packet.
        
        Must be called after the Process() method."""
        try:
            out = ' Packet cooked: '
            out += 'id:%d ' % self.pkt_id
            out += '%s ' % self.pkt_name
            out += '%s ' % weeutil.weeutil.timestamp_to_string(
                self.timestamp_record())
            out += 'len:%d ' % self.size_actual()
            out += 'fields:%d ' % len(self._record)
            out += str(self._record)
            logdbg(out)
        except KeyError:
            msg = 'print_cooked() called before proper setup'
            logerr(msg)
            raise weewx.ViolatedPrecondition(msg)

class PacketLive(Packet):
    """Packets with live sensor data from console."""
    # Number of live packets received from console.
    pkt_rx = 0
    # Queue of processed packets to be delivered to weewx.
    pkt_queue = []
    def __init__(self, wmr200):
        super(PacketLive, self).__init__(wmr200)
        PacketLive.pkt_rx += 1

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
        self._record.update({'dateTime': self.timestamp_live(), })

    def calc_time_drift(self):
        """Returns the difference between PC time and the packet timestamp.
        This value is approximate as all timestamps from a given archive
        interval will be the same while PC time marches onwards.
        Only done once upon first live packet received."""
        if self.wmr200.time_drift is None:
            self.wmr200.time_drift = self.timestamp_host() \
                - self.timestamp_packet()
            loginf('Time drift between host and console in seconds:%d' %
                   self.wmr200.time_drift)

    def timestamp_live(self):
        """Returns the timestamp from a live packet.

        Caches the last live timestamp to add to packets that do 
        not provide timestamps."""
        if self.wmr200.use_pc_time:
            self.wmr200.last_time_epoch = self.timestamp_host()
        else:
            self.wmr200.last_time_epoch = self.timestamp_packet()
        return self.wmr200.last_time_epoch

class PacketArchive(Packet):
    """Packets with archived sensor data from console."""
    # Number of archive packets received from console.
    pkt_rx = 0
    # Queue of processed packets to be delivered to weewx.
    pkt_queue = []
    def __init__(self, wmr200):
        super(PacketArchive, self).__init__(wmr200)
        PacketArchive.pkt_rx += 1

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
        # If we need to adjust the timestamp if pc time is set we will do it
        # later
        self._record.update({'dateTime': self.timestamp_packet(), })
        # Archive packets have extra field indicating interval time.
        self._record.update({'interval':
                             int(self.wmr200.archive_interval / 60.0), })

    def timestamp_adjust_drift(self):
        """Archive records may need time adjustment when using PC time."""
        try:
            loginf(('Using pc time adjusting archive record time by %d sec'
                    ' %s => %s' % (self.wmr200.time_drift,
                                   weeutil.weeutil.timestamp_to_string\
                                   (self.timestamp_record()),
                                   weeutil.weeutil.timestamp_to_string\
                                   (self.timestamp_record()
                                    + int(self.wmr200.time_drift)))))
            self._record['dateTime'] += int(self.wmr200.time_drift)
        except TypeError:
            logerr('timestamp_adjust_drift() called with invalid time drift')

class PacketControl(Packet):
    """Packets with protocol control info from console."""
    # Number of control packets received from console.
    pkt_rx = 0
    def __init__(self, wmr200):
        super(PacketControl, self).__init__(wmr200)
        PacketControl.pkt_rx += 1

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
        if self.size_actual() == 1:
            return True
        return False

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine.
        
        This packet isn't really passed up to weewx but is assigned a
        timestamp for completeness."""
        self._record.update({'dateTime': self.timestamp_host(), })

    def print_cooked(self):
        """Print the processed packet.
        
        This packet consists of a single byte and thus not much to print."""
        out = ' Packet cooked: '
        out += '%s ' % self.pkt_name
        logdbg(out)

class PacketArchiveReady(PacketControl):
    """Packet parser for control command acknowledge."""
    pkt_cmd = 0xd1
    pkt_name = 'CmdAck'
    pkt_len = 1
    def __init__(self, wmr200):
        super(PacketArchiveReady, self).__init__(wmr200)

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketArchiveReady, self).packet_process()
        # Immediately request to the console a command to send archived data.
        self.wmr200.request_archive_data()

class PacketArchiveData(PacketArchive):
    """Packet parser for archived data."""
    pkt_cmd = 0xd2
    pkt_name = 'Archive Data'

    # Initial console rain total value since 2007-1-1.
    rain_total_last = None

    def __init__(self, wmr200):
        super(PacketArchiveData, self).__init__(wmr200)

    def packet_process(self):
        """Returns a records field to be processed by the weewx engine."""
        super(PacketArchiveData, self).packet_process()
        try:
            self._record.update(decode_rain(self,     self._pkt_data[ 7:20]))
            self._record.update(decode_wind(self,     self._pkt_data[20:27]))
            self._record.update(decode_uvi(self,      self._pkt_data[27:28]))
            self._record.update(decode_pressure(self, self._pkt_data[28:32]))
            # Number of sensors starting at zero inclusive.
            num_sensors = self._pkt_data[32]

            for i in xrange(0, num_sensors+1):
                base = 33 + i*7
                self._record.update(decode_temp(self,
                                                self._pkt_data[base:base+7]))
        except IndexError:
            msg = ('%s decode index failure' % self.pkt_name)
            raise WMR200ProtocolError(msg)

        # Tell wmr200 console we have processed it and can handle more.
        self.wmr200.request_archive_data()

        if DEBUG_PACKETS_ARCHIVE:
            logdbg('  Archive packet num_temp_sensors:%d' % num_sensors)

    def timestamp_last_rain(self):
        """Pulls the epoch timestamp from the packet.  
        Returns the epoch time since last accumualted rainfall."""
        return self._timestamp_packet(self._pkt_data[15:20])

def decode_wind(pkt, pkt_data):
    """Decode the wind portion of a wmr200 packet."""
    try:
        # Low byte of gust speed in 0.1 m/s.
        gust_speed = ((((pkt_data[3]) & 0x0f) << 8)
                      | pkt_data[2]) / 10.0
        # High nibble is low nibble of average speed.
        # Low nibble of high byte and high nibble of low byte
        # of average speed. Value is in 0.1 m/s
        avg_speed = ((pkt_data[3] >> 4)
                     | ((pkt_data[4] << 4))) / 10.0
        # Wind direction in steps of 22.5 degrees.
        # 0 is N, 1 is NNE and so on. See WIND_DIR_MAP for complete list.
        # Default to none unless speed is above zero.
        dir_deg = None
        if avg_speed > 0.0:
            dir_deg = (pkt_data[0] & 0x0f) * 22.5

        # Windchill temperature. The value is in degrees F.
        # Set default to no windchill as it may not exist.
        # Convert to metric for weewx presentation.
        windchill = None
        if pkt_data[6] != 0x20:
            if pkt_data[6] & 0x10:
                # Think it's a flag of some sort
                pass
            elif pkt_data[6] != 0x80:
                windchill = (((pkt_data[6] << 8) | pkt_data[5]) - 320) \
                        * (5.0 / 90.0)
            elif pkt_data[6] & 0x80:
                windchill = ((((pkt_data[5]) * -1) - 320) * (5.0/90.0))

        # The console returns wind speeds in m/s. weewx requires
        # kph, so the speeds needs to be converted.
        record = {'windSpeed'         : avg_speed * 3.60,
                  'windGust'          : gust_speed * 3.60,
                  'windDir'           : dir_deg,
                  'windchill'         : windchill,
                 }
        # Sometimes the station emits a wind gust that is less than the
        # average wind.  weewx requires kph, so the result needs to be 
        # converted.
        if gust_speed < avg_speed:
            record['windGust'] = None
            record['windGustDir'] = None
        else:
            # use the regular wind direction for the gust direction
            record['windGustDir'] = record['windDir']

        if DEBUG_PACKETS_WIND:
            logdbg('  Wind Dir: %s' % (WIND_DIR_MAP[pkt_data[0] & 0x0f]))
            logdbg('  Gust: %.1f m/s Wind:%.1f m/s' % (gust_speed, avg_speed))
            if windchill is not None:
                logdbg('  Windchill: %.1f C' % (windchill))
        return record

    except IndexError:
        msg = ('%s decode index failure' % pkt.pkt_name)
        raise WMR200ProtocolError(msg)

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

def decode_rain(pkt, pkt_data):
    """Decode the rain portion of a wmr200 packet."""
    try:
        # Bytes 0 and 1: high and low byte encode the current rainfall rate
        # in 0.01 in/h.  Convert into metric.
        rain_rate = (((pkt_data[1] & 0x0f) << 8) | pkt_data[0]) / 100.0 * 2.54
        # Bytes 2 and 3: high and low byte encode rain of the last hour in 0.01in
        # Convert into metric.
        rain_hour = ((pkt_data[3] << 8) | pkt_data[2]) / 100.0 * 2.54
        # Bytes 4 and 5: high and low byte encode rain of the last 24 hours, 
        # excluding the current hour, in 0.01in
        # Convert into metric.
        rain_day = ((pkt_data[5] << 8) | pkt_data[4]) / 100.0 * 2.54
        # Bytes 6 and 7: high and low byte encode the total rainfall in 0.01in.
        # Convert into metric.
        rain_total = ((pkt_data[7] << 8) | pkt_data[6]) / 100.0 * 2.54

        record = {'rainRate'          : rain_rate,
                  'hourRain'          : rain_hour,
                  'rain24'            : rain_day + rain_hour,
                  'totalRain'         : rain_total}

        if DEBUG_PACKETS_RAIN:
            try:
                formatted = ["0x%02x" % x for x in pkt_data]
                logdbg('  Rain packets:' + ', '.join(formatted))
                logdbg('  Rain rate:%.02f; hour_rain:%.02f; day_rain:%.02f' %
                       (rain_rate, rain_hour, rain_day))
                logdbg('  Total rain_total:%.02f' % (rain_total))
                logdbg('  Last rain %s' %
                       weeutil.weeutil.timestamp_to_string\
                       (pkt.timestamp_last_rain()))
            except Exception:
                pass

        return record

    except IndexError:
        msg = ('%s decode index failure' % pkt.pkt_name)
        raise WMR200ProtocolError(msg)


def adjust_rain(pkt, packet):
    """Calculate rainfall per poll interval.
    Because the WMR does not offer anything like bucket tips, we must
    calculate it by looking for the change in total rain.
    After driver startup we need to initialize the total rain presented 
    by the console.
      There are two different rain total last values kept.  One for archive
    data and one for live loop data.  They are addressed using a static
    variable within the scope of the respective class name."""
    record = {}

    # Get the total current rain field from the console.
    rain_total = pkt.record_get('totalRain')

    # Calculate the amount of rain occurring for this interval.
    try:
        rain_interval = rain_total - packet.rain_total_last
    except TypeError:
        rain_interval = 0.0

    record['rain'] = rain_interval
    record['totalRainLast'] = packet.rain_total_last

    try:
        logdbg('  adjust_rain rain_total:%.02f %s.rain_total_last:%.02f'
               ' rain_interval:%.02f' % (rain_total, packet.pkt_name,
                                         packet.rain_total_last, rain_interval))
    except TypeError:
        logdbg('  Initializing %s.rain_total_last to %.02f' %
               (packet.pkt_name, rain_total))

    packet.rain_total_last = rain_total

    return record

class PacketRain(PacketLive):
    """Packet parser for rain."""
    pkt_cmd = 0xd4
    pkt_name = 'Rain'
    pkt_len = 0x16

    # Initial console rain total value since 2007-1-1.
    rain_total_last = None

    def __init__(self, wmr200):
        super(PacketRain, self).__init__(wmr200)

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine."""
        super(PacketRain, self).packet_process()
        self._record.update(decode_rain(self, self._pkt_data[7:20]))
        self._record.update(adjust_rain(self, PacketRain))

    def timestamp_last_rain(self):
        """Pulls the epoch timestamp from the packet.  
        Returns the epoch time since last accumualted rainfall."""
        return self._timestamp_packet(self._pkt_data[15:20])

def decode_uvi(pkt, pkt_data):
    """Decode the uvi portion of a wmr200 packet."""
    try:
        record = {'UV': pkt_data[0 & 0x0f]}
        if DEBUG_PACKETS_UVI:
            logdbg("  UV index:%s\n" % record['UV'])
        return record

    except IndexError:
        msg = ('%s index decode index failure' % pkt.pkt_name)
        raise WMR200ProtocolError(msg)


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
        # or "gauge" pressure. We will assume the latter.
        pressure = float(((pkt_data[1] & 0x0f) << 8) | pkt_data[0])
        forecast = (pkt_data[1] >> 4) & 0x7

        # Similar to bytes 0 and 1, but altitude corrected
        # pressure. Upper nibble of byte 3 is still unknown. Seems to
        # be always 3.
        altimeter = float(((pkt_data[3] & 0x0f) << 8)
                                     | pkt_data[2])
        unknown_nibble = (pkt_data[3] >> 4)

        record = {'pressure'    : pressure,
                  'altimeter'   : altimeter,
                  'forecastIcon': forecast}

        if DEBUG_PACKETS_PRESSURE:
            logdbg('  Forecast: %s' % FORECAST_MAP[forecast])
            logdbg('  Raw pressure: %.02f hPa' % pressure)
            if unknown_nibble != 3:
                logdbg('  Pressure unknown nibble: 0x%x' % unknown_nibble)
            logdbg('  Altitude corrected pressure: %.02f hPa console' %
                   altimeter)
        return record

    except IndexError:
        msg = ('%s index decode index failure' % pkt.pkt_name)
        raise WMR200ProtocolError(msg)


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
        # '00 Temp steady
        # '01 Temp rising 
        # '10 Temp falling 
        temp_trend = (pkt_data[0] >> 6) & 0x3
        # '00 Humidity steady
        # '01 Humidity rising 
        # '10 Humidity falling 
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

        # The first high nibble contains the sign indicator.
        # The first low nibble is the high byte of the temperature.
        # The second byte is low byte of the temperature. The value is in 1/10
        # degrees centigrade.
        dew_point = (((pkt_data[5] & 0x0f) << 8)
                     | pkt_data[4]) / 10.0
        if pkt_data[5] & 0x80:
            dew_point *= -1

        # Heat index reported by console.
        heat_index = None
        if pkt_data[6] != 0:
            # For some strange reason it's reported in degF so convert
            # to metric.
            heat_index = (pkt_data[6] - 32) / (9.0 / 5.0)

        if sensor_id == 0:
            # Indoor temperature sensor.
            record['inTemp'] = temp
            record['inHumidity'] = humidity
        elif sensor_id == 1:
            # Outdoor temperature sensor.
            record['outTemp'] = temp
            record['outHumidity'] = humidity
            record['heatindex'] = heat_index
        elif sensor_id >= 2:
            # Extra temperature sensors.
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            record['extraTemp%d' % sensor_id] = temp
            record['extraHumid%d' % sensor_id] = humidity

        if DEBUG_PACKETS_TEMP:
            logdbg('  Temperature id:%d %.1f C trend: %s'
                   % (sensor_id, temp, TRENDS[temp_trend]))
            logdbg('  Humidity id:%d %d%% trend: %s'
                   % (sensor_id, humidity, TRENDS[hum_trend]))
            logdbg(('  Dew point id:%d: %.1f C' % (sensor_id, dew_point)))
            if heat_index:
                logdbg('  Heat id:%d index:%d' % (sensor_id, heat_index))
        return record

    except IndexError:
        msg = ('%s index decode index failure' % pkt.pkt_name)
        raise WMR200ProtocolError(msg)


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
        # Save the temp record for possible windchill calculation.
        self.wmr200.last_temp_record = self._record

class PacketStatus(PacketLive):
    """Packet parser for console sensor status."""
    pkt_cmd = 0xd9
    pkt_name = 'Status'
    pkt_len = 0x08
    def __init__(self, wmr200):
        super(PacketStatus, self).__init__(wmr200)

    def timestamp_live(self):
        """Return timestamp of packet.
        
        This packet does not have a timestamp so we just return the
        previous cached timestamp from the last live packet.
        Note: If there is no previous cached timestamp then we 
        return the initial PC timestamp.  This would occur quite early
        in the driver startup and this time may be quite out of
        sequence from the rest of the packets.  Another option would be
        to simply discard this status packet at this time."""
        return self.wmr200.last_time_epoch

    def packet_process(self):
        """Returns a packet that can be processed by the weewx engine.
        
        Not all console status aligns with the weewx API but we try
        to make it fit."""
        super(PacketStatus, self).packet_process()
        # Setup defaults as good status.
        self._record.update({'outTempFault'         : 0,
                             'windFault'            : 0,
                             'uvFault'              : 0,
                             'rainFault'            : 0,
                             'clockUnsynchronized'  : 0,
                             'outTempBatteryStatus' : 1.0,
                             'windBatteryStatus'    : 1.0,
                             'uvBatteryStatus'      : 1.0,
                             'rainBatteryStatus'    : 1.0,
                            })
        # This information may be sent to syslog
        msg_status = []
        if self._pkt_data[2] & 0x02:
            msg_status.append('Temp outdoor sensor fault')
            self._record['outTempFault'] = 1

        if self._pkt_data[2] & 0x01:
            msg_status.append('Wind sensor fault')
            self._record['windFault'] = 1

        if self._pkt_data[3] & 0x20:
            msg_status.append('UV Sensor fault')
            self._record['uvFault'] = 1

        if self._pkt_data[3] & 0x10:
            msg_status.append('Rain sensor fault')
            self._record['rainFault'] = 1

        if self._pkt_data[4] & 0x80:
            msg_status.append('Clock time unsynchronized')
            self._record['clockUnsynchronized'] = 1

        if self._pkt_data[4] & 0x02:
            msg_status.append('Temp outdoor sensor: Battery low')
            self._record['outTempBatteryStatus'] = 0.0

        if self._pkt_data[4] & 0x01:
            msg_status.append('Wind sensor: Battery low')
            self._record['windBatteryStatus'] = 0.0

        if self._pkt_data[5] & 0x20:
            msg_status.append('UV sensor: Battery low')
            self._record['uvBatteryStatus'] = 0.0

        if self._pkt_data[5] & 0x10:
            msg_status.append('Rain sensor: Battery low')
            self._record['rainBatteryStatus'] = 0.0

        if self.wmr200.sensor_stat:
            while msg_status:
                msg = msg_status.pop(0)
                logwar(msg)

        # Output packet to try to understand other fields.
        if DEBUG_PACKETS_STATUS:
            logdbg(self.to_string_raw(' Sensor packet:'))

    def calc_time_drift(self):
        """Returns the difference between PC time and the packet timestamp.
        This packet has no timestamp so cannot be used to calculate."""
        pass

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

    def num_packets(self):
        """Returns the number of packets handled by the factory."""
        return len(self.subclass)

    def get_packet(self, pkt_cmd, wmr200):
        """Returns a protocol packet instance from initial packet command byte.
       
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
    PacketArchiveReady,
    PacketArchiveData,
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
    """A thread continually polls for data with blocking read from a device.
    
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
        # We don't want to read previous data, if any, until a reset
        # has been sent.
        self._cv_poll = threading.Condition()
        # Gates initial entry into reading from device
        self._ok_to_read = False
        loginf('Created USB polling thread to read block on device')

    def run(self):
        """Polling function to block read the USB device.
        
        This method appends new data after previous buffer
        data in preparation for reads to the main driver
        thread.
        
        Once this thread is started it will be gated by
        a reset to the weather console device to sync it
        up."""
        loginf('USB polling device thread for live data launched')

        # Wait for the main thread to indicate it's safe to read.
        self._cv_poll.acquire()
        while not self._ok_to_read:
            self._cv_poll.wait()
        self._cv_poll.release()
        loginf('USB polling device thread signaled to start')

        # Read and discard next data from weather console device.
        _ = self.usb_device.read_device()
        read_timeout_cnt = 0
        read_reset_cnt = 0

        # Loop indefinitely until main thread indicates time to expire.
        while self.wmr200.poll_usb_device_enable():
            try:
                buf = self.usb_device.read_device()
                if buf:
                    self._append_usb_device(buf)
                    read_timeout_cnt = 0
                    read_reset_cnt = 0
                else:
                    # We timed out here.  We should poke the device
                    # after a read timeout, and also prepare for more
                    # serious measures.
                    self.wmr200.ready_to_poke(True)
                    read_timeout_cnt += 1
                    # If we don't receive any data from the console
                    # after several attempts, send down a reset.
                    if read_timeout_cnt == 4:
                        self.reset_console()
                        read_timeout_cnt = 0
                        read_reset_cnt += 1
                    # If we have sent several resets with no data,
                    # give up and abort.
                    if read_reset_cnt == 2:
                        msg = ('Device unresponsive after multiple resets')
                        logerr(msg)
                        raise weewx.RetriesExceeded(msg)

            except:
                logerr('USB device read error')
                raise

        loginf('USB polling device thread exiting')

    def _append_usb_device(self, buf):
        """Appends data from USB device to shared buffer.
        Called from child thread."""
        self._lock_poll.acquire()
        # Append the list of bytes to this buffer.
        self._buf.append(buf)
        self._lock_poll.release()

    def read_usb_device(self):
        """Reads the buffered USB device data.
        Called from main thread.

        Returns a list of bytes."""
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
        Called from main thread or child thread."""
        buf = [0x20, 0x00, 0x08, 0x01, 0x00, 0x00, 0x00, 0x00]
        try:
            self.usb_device.write_device(buf)
            loginf('Reset console device')
            self._ok_to_read = True
            time.sleep(1)

        except usb.USBError, exception:
            msg = ('reset_console() Unable to send USB control'
                   'message %s' % exception)
            logerr(msg)
            # Convert to a Weewx error:
            raise weewx.WeeWxIOError(exception)

    def notify(self):
        """Gates thread to read of the device.
        Called from main thread."""
        self._cv_poll.acquire()
        self._cv_poll.notify()
        self._cv_poll.release()

class WMR200(weewx.drivers.AbstractDevice):
    """Driver for the Oregon Scientific WMR200 station."""

    def __init__(self, **stn_dict):
        """Initialize the wmr200 driver.
        
        NAMED ARGUMENTS:
        model: Which station model is this? [Optional]
        sensor_status: Print sensor faults or failures to syslog. [Optional]
        use_pc_time: Use the console timestamp or the Pc. [Optional]
        erase_archive:  Erase archive upon startup.  [Optional]
        archive_interval: Time in seconds between intervals [Optional]
        archive_threshold: Max time in seconds between valid archive packets [Optional]
        ignore_checksum: Ignore checksum failures and drop packet.
        archive_startup: Time after startup to await archive data draining.

        --- User should not typically change anything below here ---

        vendor_id: The USB vendor ID for the WMR [Optional]
        product_id: The USB product ID for the WM [Optional]
        interface: The USB interface [Optional]
        in_endpoint: The IN USB endpoint used by the WMR [Optional]
        """
        super(WMR200, self).__init__()

        ## User configurable options
        self._model = stn_dict.get('model', 'WMR200')
        # Provide sensor faults in syslog.
        self._sensor_stat = weeutil.weeutil.tobool(stn_dict.get('sensor_status',
                                                                True))
        # Use pc timestamps or weather console timestamps.
        self._use_pc_time = \
            weeutil.weeutil.tobool(stn_dict.get('use_pc_time', True))

        # Use archive data when possible.
        self._erase_archive = \
            weeutil.weeutil.tobool(stn_dict.get('erase_archive', False))

        # Archive interval in seconds.
        self._archive_interval = int(stn_dict.get('archive_interval', 60))
        if self._archive_interval not in [60, 300]:
            logwar('Unverified archive interval:%d sec'
                   % self._archive_interval)

        # Archive threshold in seconds between archive packets before dropping.
        self._archive_threshold = int(stn_dict.get('archive_threshold',
                                                   3600*24*7))

        # Ignore checksum errors.
        self._ignore_checksum = \
                weeutil.weeutil.tobool(stn_dict.get('ignore_checksum', False))

        # Archive startup time in seconds.
        self._archive_startup = int(stn_dict.get('archive_startup', 120))

        # Device specific hardware options.
        vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        product_id        = int(stn_dict.get('product_id', '0xca01'), 0)
        interface         = int(stn_dict.get('interface', 0))
        in_endpoint       = int(stn_dict.get('IN_endpoint',
                                             usb.ENDPOINT_IN + 1))

        # Buffer of bytes read from weather console device.
        self._buf = []

        # Packet created from the buffer data read from the weather console
        # device.
        self._pkt = None

        # Setup the generator to get a byte stream from the console.
        self.gen_byte = self._generate_bytestream

        # Calculate time delta in seconds between host and console.
        self.time_drift = None

        # Create USB accessor to communiate with weather console device.
        self.usb_device = UsbDevice()

        # Pass USB parameters to the USB device accessor.
        self.usb_device.in_endpoint = in_endpoint
        self.usb_device.interface = interface

        # Locate the weather console device on the USB bus.
        if not self.usb_device.find_device(vendor_id, product_id):
            logcrt('Unable to find device with VendorID=%04x ProductID=%04x' %
                   (vendor_id, product_id))
            raise weewx.WeeWxIOError("Unable to find USB device")

        # Open the weather console USB device for read and writes.
        self.usb_device.open_device()

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
            kwargs = {'wmr200'    : self,
                      'poke_time' : _WMR200_REQUEST_LIVE_DATA_INTERVAL,
                      'sock_rd'   : self.sock_rd})

        # Create the usb polling device thread.
        self._thread_usb_poll = PollUsbDevice(kwargs={'wmr200': self})

        # Start the usb polling device thread.
        self._poll_device_enable = True
        self._thread_usb_poll.start()

        # Send the device a reset
        self._thread_usb_poll.reset_console()
        self._thread_usb_poll.notify()

        # Start the watchdog for live data thread.
        self._thread_watchdog.start()

        # Not all packets from wmr200 have timestamps, yet weewx requires
        # timestamps on all packets pass up the stack.  So we will use the 
        # timestamp from the most recent packet, but still need to see an
        # initial timestamp, so we'll seed this with current PC time.
        self.last_time_epoch = int(time.time() + 0.5)

        # Restart counter when driver crashes and is restarted by the
        # weewx engine.
        global STAT_RESTART
        STAT_RESTART += 1
        if STAT_RESTART > 1:
            logwar(('Restart count: %d') % STAT_RESTART)

        # Reset any other state during startup or after a crash.
        PacketArchiveData.rain_total_last = None

        # Debugging flags
        global DEBUG_WRITES
        DEBUG_WRITES = int(stn_dict.get('debug_writes', 0))
        global DEBUG_COMM
        DEBUG_COMM = int(stn_dict.get('debug_comm', 0))
        global DEBUG_CONFIG_DATA
        DEBUG_CONFIG_DATA = int(stn_dict.get('debug_config_data', 1))
        global DEBUG_PACKETS_RAW
        DEBUG_PACKETS_RAW = int(stn_dict.get('debug_packets_raw', 0))
        global DEBUG_PACKETS_COOKED
        DEBUG_PACKETS_COOKED = int(stn_dict.get('debug_packets_cooked', 0))
        global DEBUG_PACKETS_ARCHIVE
        DEBUG_PACKETS_ARCHIVE = int(stn_dict.get('debug_packets_archive', 0))
        global DEBUG_PACKETS_TEMP
        DEBUG_PACKETS_TEMP = int(stn_dict.get('debug_packets_temp', 0))
        global DEBUG_PACKETS_RAIN
        DEBUG_PACKETS_RAIN = int(stn_dict.get('debug_packets_rain', 0))
        global DEBUG_PACKETS_WIND
        DEBUG_PACKETS_WIND = int(stn_dict.get('debug_packets_wind', 0))
        global DEBUG_PACKETS_STATUS
        DEBUG_PACKETS_STATUS = int(stn_dict.get('debug_packets_status', 0))
        global DEBUG_PACKETS_PRESSURE
        DEBUG_PACKETS_PRESSURE = int(stn_dict.get('debug_packets_pressure', 0))
        global DEBUG_CHECKSUM
        DEBUG_CHECKSUM = int(stn_dict.get('debug_checksum', 0))

        if DEBUG_CONFIG_DATA:
            logdbg('Configuration setup')
            logdbg('  Log sensor faults: %s' % self._sensor_stat)
            logdbg('  Using PC Time: %s' % self._use_pc_time)
            logdbg('  Erase archive data: %s' % self._erase_archive)
            logdbg('  Archive interval: %d' % self._archive_interval)
            logdbg('  Archive threshold: %d' % self._archive_threshold)

    @property
    def hardware_name(self):
        """weewx api."""
        return self._model

    @property
    def sensor_stat(self):
        """Return if sensor status is enabled for device."""
        return self._sensor_stat

    @property
    def use_pc_time(self):
        """Flag to use pc time rather than weather console time."""
        return self._use_pc_time

    @property
    def archive_interval(self):
        """weewx api.  Time in seconds between archive intervals."""
        return self._archive_interval

    @property
    def ignore_checksum(self):
        """Flag to drop rather than fail on checksum errors."""
        return self._ignore_checksum

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
            msg = (('_write_cmd() Unable to send USB cmd:0x%02x control'
                    ' message' % cmd))
            logerr(msg)
            # Convert to a Weewx error:
            raise weewx.WeeWxIOError(exception)

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
            logdbg('Poked device for live data')

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
        if not self._thread_usb_poll.is_alive():
            msg = 'USB polling thread unexpectedly terminated'
            logerr(msg)
            raise weewx.WeeWxIOError(msg)

        for byte in self.gen_byte():
            if self._pkt:
                self._pkt.append_data(byte)
            else:
                # This may return None if we are out of sync
                # with the console.
                self._pkt = PACKET_FACTORY.get_packet(byte, self)

            if self._pkt is not None and self._pkt.packet_complete():
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
        loginf(('Received packet count live:%d archive:%d'
                ' control:%d') % (PacketLive.pkt_rx,
                                      PacketArchive.pkt_rx,
                                      PacketControl.pkt_rx))
        loginf('Received bytes:%d sent bytes:%d' %
               (self.usb_device.byte_cnt_rd,
                self.usb_device.byte_cnt_wr))
        loginf('Packet archive queue len:%d live queue len:%d'
               % (len(PacketArchive.pkt_queue), len(PacketLive.pkt_queue)))

    def _process_packet_complete(self):
        """Process a completed packet from the wmr200 console."""
        if DEBUG_PACKETS_RAW:
            logdbg(self._pkt.to_string_raw('Packet raw:'))

        # This will raise exception if checksum fails.
        self._pkt.verify_checksum()

        try:
            # Process the actual packet.
            self._pkt.packet_process()
            if self._pkt.packet_live_data():
                PacketLive.pkt_queue.append(self._pkt)
                logdbg('  Queuing live packet rx:%d live_queue_len:%d' %
                       (PacketLive.pkt_rx, len(PacketLive.pkt_queue)))
            elif self._pkt.packet_archive_data():
                PacketArchive.pkt_queue.append(self._pkt)
                logdbg('  Queuing archive packet rx:%d archive_queue_len:%d'
                       % (PacketArchive.pkt_rx, len(PacketArchive.pkt_queue)))
            else:
                logdbg(('  Acknowledged control packet'
                        ' rx:%d') % PacketControl.pkt_rx)
        except WMR200PacketParsingError, e:
            # Drop any bogus packets.
            logerr(self._pkt.to_string_raw('Discarding bogus packet: %s ' 
                   % e.msg))

        # Reset this packet to get ready for next one
        self._pkt = None

    def genLoopPackets(self):
        """Main generator function that continuously returns loop packets

        weewx api to return live records."""
        # Reset the current packet upon entry.
        self._pkt = None

        logdbg('genLoop() phase getting live packets')

        while True:
            # Loop through indefinitely generating records to the
            # weewx engine.  This loop may resume at the yield()
            # or upon entry during any exception, even an exception
            # not generated from this driver.  e.g. weewx.service.
            if self._pkt is not None and self._pkt.packet_complete():
                self._process_packet_complete()

            # If it's time to poke the console and we are not
            # in the middle of collecting a packet then do it here.
            if self.is_ready_to_poke() and self._pkt is None:
                self._poke_console()

            # Pull data from the weather console.
            # This may create a packet or append data to existing packet.
            self._poll_for_data()

            # Yield any live packets we may have obtained from this callback
            # or queued from other driver callback services.
            while PacketLive.pkt_queue:
                pkt = PacketLive.pkt_queue.pop(0)
                if DEBUG_PACKETS_COOKED:
                    pkt.print_cooked()
                logdbg('genLoop() Yielding live queued packet id:%d'
                       % pkt.pkt_id)
                yield pkt.packet_record()

    def XXXgenArchiveRecords(self, since_ts=0):
        """A generator function to return archive packets from the wmr200.
        
        weewx api to return archive records.
        since_ts: A timestamp in database time. All data since but not 
        including this time will be returned.
        Pass in None for all data
       
        NOTE: This API is disabled so that the weewx engine will default
        to using sofware archive generation.  There may be a way
        to use hardware generation if one plays with not poking the console
        which would allow archive packets to be created.

        yields: a sequence of dictionary records containing the console 
        data."""
        logdbg('genArchive() phase getting archive packets since %s'
               % weeutil.weeutil.timestamp_to_string(since_ts))

        if self.use_pc_time and self.time_drift is None:
            loginf(('genArchive() Unable to process archive packets'
                    ' until live packet received'))
            return

        while True:
            # Loop through indefinitely generating records to the
            # weewx engine.  This loop may resume at the yield()
            # or upon entry during any exception, even an exception
            # not generated from this driver.  e.g. weewx.service.
            if self._pkt is not None and self._pkt.packet_complete():
                self._process_packet_complete()

            # If it's time to poke the console and we are not
            # in the middle of collecting a packet then do it here.
            if self.is_ready_to_poke() and self._pkt is None:
                self._poke_console()

            # Pull data from the weather console.
            # This may create a packet or append data to existing packet.
            self._poll_for_data()

            # Yield any live packets we may have obtained from this callback
            # or queued from other driver callback services.
            while PacketArchive.pkt_queue:
                pkt = PacketLive.pkt_queue.pop(0)
                # If we are using PC time we need to adjust the record timestamp
                # with the PC drift.
                if self.use_pc_time:
                    pkt.timestamp_adjust_drift()

                if DEBUG_PACKETS_COOKED:
                    pkt.print_cooked()
                if pkt.timestamp_record() > since_ts:
                    logdbg(('genArchive() Yielding received archive record'
                            ' after requested timestamp'))
                    yield pkt.packet_record()
                else:
                    loginf(('genArchive() Ignoring received archive record'
                            ' before requested timestamp'))

    def genStartupRecords(self, since_ts=0):
        """A generator function to present archive packets on start.

        weewx api to return archive records."""
        logdbg('genStartup() phase getting archive packets since %s'
               % weeutil.weeutil.timestamp_to_string(since_ts))

        # Reset the current packet upon entry.
        self._pkt = None

        # Time after last archive packet to indicate there are
        # likely no more archive packets left to drain.
        timestamp_last_archive_rx = int(time.time() + 0.5)

        # Statisics to calculate time in this phase.
        timestamp_packet_first = None
        timestamp_packet_current = None
        timestamp_packet_previous = None
        cnt = 0

        # If no previous database this parameter gets passed as None.
        # Convert to a numerical value representing start of unix epoch.
        if since_ts is None:
            loginf('genStartup() Database initialization')
            since_ts = 0

        while True:
            # Loop through indefinitely generating archive records to the
            # weewx engine.  This loop may resume at the yield()
            # or upon entry during any exception, even an exception
            # not generated from this driver.  e.g. weewx.service.
            if self._pkt is not None and self._pkt.packet_complete():
                self._process_packet_complete()

            # If it's time to poke the console and we are not
            # in the middle of collecting a packet then do it here.
            if self.is_ready_to_poke() and self._pkt is None:
                self._poke_console()

            # Pull data from the weather console.
            # This may create a packet or append data to existing packet.
            self._poll_for_data()

            # If we have archive packets in the queue then yield them here.
            while PacketArchive.pkt_queue:
                timestamp_last_archive_rx = int(time.time() + 0.5)

                # Present archive packets
                # If PC time is set, we must have at least one
                # live packet to calculate timestamps in PC time.
                if self.use_pc_time and self.time_drift is None:
                    loginf(('genStartup() Delaying archive packet processing'
                            ' until live packet received'))
                    break

                loginf(('genStartup() Still receiving archive packets'
                        ' cnt:%d len:%d') % (cnt, len(PacketArchive.pkt_queue)))

                pkt = PacketArchive.pkt_queue.pop(0)
                # If we are using PC time we need to adjust the
                # record timestamp with the PC drift.
                if self.use_pc_time:
                    pkt.timestamp_adjust_drift()

                # Statisics indicating packets sent in this phase.
                if timestamp_packet_first is None:
                    timestamp_packet_first = pkt.timestamp_record()
                if timestamp_packet_previous is None:
                    if since_ts == 0:
                        timestamp_packet_previous = pkt.timestamp_record()
                    else:
                        timestamp_packet_previous = since_ts

                timestamp_packet_current = pkt.timestamp_record()

                # Calculate time interval between archive packets.
                timestamp_packet_interval = timestamp_packet_current \
                        - timestamp_packet_previous

                if pkt.timestamp_record() > (timestamp_packet_previous
                                             + self._archive_threshold):
                    loginf(('genStartup() Discarding received archive'
                            ' record exceeding archive interval cnt:%d'
                            ' threshold:%d timestamp:%s')
                           % (cnt, self._archive_threshold,
                              weeutil.weeutil.timestamp_to_string\
                              (pkt.timestamp_record())))
                elif pkt.timestamp_record() > since_ts:
                    # Calculate the rain accumulation between valid archive 
                    # packets.
                    pkt.record_update(adjust_rain(pkt, PacketArchiveData))

                    timestamp_packet_previous = timestamp_packet_current
                    cnt += 1
                    logdbg(('genStartup() Yielding received archive'
                            ' record cnt:%d after requested timestamp'
                            ':%d pkt_interval:%d pkt:%s')
                           % (cnt, since_ts, timestamp_packet_interval,
                              weeutil.weeutil.timestamp_to_string\
                              (pkt.timestamp_record())))
                    if DEBUG_PACKETS_COOKED:
                        pkt.print_cooked()
                    yield pkt.packet_record()
                else:
                    timestamp_packet_previous = timestamp_packet_current
                    loginf(('genStartup() Discarding received archive'
                            ' record before time requested cnt:%d'
                            ' timestamp:%s')
                           % (cnt, weeutil.weeutil.timestamp_to_string\
                              (since_ts)))

            # Return if we receive not more archive packets in a given time
            # interval.
            if (int(time.time() + 0.5) - timestamp_last_archive_rx >
                self._archive_startup):
                loginf(('genStartup() phase exiting since looks like all'
                        ' archive packets have been retrieved after %d'
                        ' sec cnt:%d')
                       % (self._archive_startup, cnt))
                if timestamp_packet_first is not None:
                    startup_time = timestamp_packet_current \
                        - timestamp_packet_first

                    loginf(('genStartup() Yielded %d packets in %d sec '
                            ' between these dates %s ==> %s' %
                            (cnt, startup_time,
                             weeutil.weeutil.timestamp_to_string\
                             (timestamp_packet_first),
                             weeutil.weeutil.timestamp_to_string\
                             (timestamp_packet_current))))
                    if startup_time > 0:
                        loginf(('genStartup() Average packets per minute:%f' %
                                (cnt/(startup_time/60.0))))
                return

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
        if self._thread_usb_poll.is_alive():
            logerr('USB polling thread still alive')
        else:
            loginf('USB polling thread expired')

        # Shutdown the watchdog thread.
        self.sock_wr.send('shutdown')
        # Join with the watchdog thread.
        self._thread_watchdog.join()
        if self._thread_watchdog.is_alive():
            logerr('Watchdog thread still alive')
        else:
            loginf('Watchdog thread expired')

        self.print_stats()
        # Indicate if queues have not been drained.
        if len(PacketArchive.pkt_queue):
            logwar('Exiting with packets still in archive queue cnt:%d' %
                   len(PacketArchive.pkt_queue))
        if len(PacketLive.pkt_queue):
            logwar('Exiting with packets still in live queue cnt:%d' %
                   len(PacketLive.pkt_queue))

        # Shutdown the USB acccess to the weather console device.
        self.usb_device.close_device()
        loginf('Driver gracefully exiting')


class WMR200ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR200]
    # This section is for the Oregon Scientific WMR200

    # The station model, e.g., WMR200, WMR200A, Radio Shack W200
    model = WMR200

    # The driver to use:
    driver = weewx.drivers.wmr200
"""

    def modify_config(self, config_dict):
        print """
Setting rainRate and windchill calculations to hardware."""
        config_dict['StdWXCalculate']['rainRate'] = 'hardware'
        config_dict['StdWXCalculate']['windchill'] = 'hardware'
