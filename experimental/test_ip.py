''' Test a VantagePro IP by doing a DMP command

'''

tcp_port = 22222
tcp_send_delay = 1
timeout = 5

import socket
import struct
import time
import sys

try:
    hostname = sys.argv[1]
except:
    print "usage: test_ip ip-address"
    exit(1)

print "Using host ", hostname

# These are used for serial ports
#port = '/dev/ttyUSB0'
#baudrate=19200
#import serial

class WeeWxIOError(IOError):
    """Base class of exceptions thrown when encountering an I/O error with the console."""

class WakeupError(WeeWxIOError):
    """Exception thrown when unable to wake up the console"""
    
class CRCError(WeeWxIOError):
    """Exception thrown when unable to pass a CRC check."""

class RetriesExceeded(WeeWxIOError):
    """Exception thrown when max retries exceeded."""

class UnknownArchiveType(StandardError):
    """Exception thrown after reading an unrecognized archive type."""

# A few handy constants:
_ack    = chr(0x06)
_resend = chr(0x15) # NB: The Davis documentation gives this code as 0x21, but it's actually decimal 21

class EthernetWrapper(object):
    """Ethernet connection"""

    def __init__(self, host, port, timeout, tcp_send_delay):

        self.host           = host
        self.port           = port
        self.timeout        = timeout
        self.tcp_send_delay = tcp_send_delay

    def wakeup_console(self, max_tries=3, wait_before_retry=1.2):
        """Wake up a Davis VantagePro console.
        
        If unsuccessful, an exception of type weewx.WakeupError is thrown"""
    
        # Wake up the console. Try up to max_tries times
        for unused_count in xrange(max_tries) :
            try:
                # Clear out any pending input or output characters:
                self.flush_output()
                self.flush_input()
                # It can be hard to get the console's attention, particularly
                # when in the middle of a LOOP command. Send a whole bunch of line feeds,
                # then flush everything, then look for the \n\r acknowledgment
                self.write('\n\n\n')
                time.sleep(0.5)
                self.flush_input()
                self.write('\n')
                _resp = self.read(2)
                if _resp == '\n\r':
                    print "successfully woke up console"
                    return
                print "Unable to wake up console... sleeping"
                time.sleep(wait_before_retry)
                print "Unable to wake up console... retrying"
            except WeeWxIOError:
                pass

        print "Unable to wake up console"
        raise WakeupError("Unable to wake up VantagePro console")

    def send_data(self, data):
        """Send data to the Davis console, waiting for an acknowledging <ACK>
        
        If the <ACK> is not received, no retry is attempted. Instead, an exception
        of type weewx.WeeWxIOError is raised
    
        data: The data to send, as a string"""

        self.write(data)
    
        # Look for the acknowledging ACK character
        _resp = self.read()
        if _resp != _ack: 
            print "No <ACK> received from console"
            raise WeeWxIOError("No <ACK> received from VantagePro console")
    
    def send_data_with_crc16(self, data, max_tries=3) :
        """Send data to the Davis console along with a CRC check, waiting for an acknowledging <ack>.
        If none received, resend up to max_tries times.
        
        data: The data to send, as a string"""
        
        #Calculate the crc for the data:
        _crc = crc16(data)

        # ...and pack that on to the end of the data in big-endian order:
        _data_with_crc = data + struct.pack(">H", _crc)
        
        # Retry up to max_tries times:
        for unused_count in xrange(max_tries):
            try:
                self.write(_data_with_crc)
                # Look for the acknowledgment.
                _resp = self.read()
                if _resp == _ack:
                    return
            except WeeWxIOError:
                pass

        print "Unable to pass CRC16 check while sending data"
        raise CRCError("Unable to pass CRC16 check while sending data to VantagePro console")

    def send_command(self, command, max_tries=3, wait_before_retry=1.2):
        """Send a command to the console, then look for the string 'OK' in the response.
        
        Any response from the console is split on \n\r characters and returned as a list."""
        
        for unused_count in xrange(max_tries):
            try :
                self.wakeup_console(max_tries=max_tries, wait_before_retry=wait_before_retry)

                self.write(command)
                # Takes a bit for the VP to react and fill up the buffer. Sleep for a half sec:
                time.sleep(0.5)
                # Can't use function serial.readline() because the VP responds with \n\r, not just \n.
                # So, instead find how many bytes are waiting and fetch them all
                nc = self.queued_bytes()
                _buffer = self.read(nc)
                # Split the buffer on the newlines
                _buffer_list = _buffer.strip().split('\n\r')
                # The first member should be the 'OK' in the VP response
                if _buffer_list[0] == 'OK' :
                    # Return the rest:
                    return _buffer_list[1:]

            except WeeWxIOError:
                # Caught an error. Keep trying...
                continue
        
        print "Max retries exceeded while sending command %s" % command
        raise RetriesExceeded("Max retries exceeded while sending command %s" % command)
    
        
    def get_data_with_crc16(self, nbytes, prompt=None, max_tries=3) :
        """Get a packet of data and do a CRC16 check on it, asking for retransmit if necessary.
        
        It is guaranteed that the length of the returned data will be of the requested length.
        An exception of type CRCError will be thrown if the data cannot pass the CRC test
        in the requested number of retries.
        
        nbytes: The number of bytes (including the 2 byte CRC) to get. 
        
        prompt: Any string to be sent before requesting the data. Default=None
        
        max_tries: Number of tries before giving up. Default=3
        
        returns: the packet data as a string. The last 2 bytes will be the CRC"""
        if prompt:
            self.write(prompt)
            
        first_time = True
            
        for unused_count in xrange(max_tries):
            try:
                if not first_time: 
                    self.write(_resend)
                _buffer = self.read(nbytes)
                if crc16(_buffer) == 0 :
                    return _buffer
            except WeeWxIOError:
                pass
            first_time = False

        print "Unable to pass CRC16 check while getting data"
        raise CRCError("Unable to pass CRC16 check while getting data")

    def openPort(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
        except:
            print "Unable to connect to ethernet host %s on port %d." % (self.host, self.port)
            raise

    def closePort(self):
        try:
            # This will cancel any pending loop:
            self.wakeup_console(max_tries=1)
        except:
            pass
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def flush_input(self):
        """Flush the input buffer from WeatherLinkIP"""
        try:
            # This is a bit of a hack, but there is no analogue to pyserial's flushInput()
            self.socket.settimeout(0)
            self.read(4096)
        except:
            pass
        finally:
            self.socket.settimeout(self.timeout)

    def flush_output(self):
        """Flush the output buffer to WeatherLinkIP

        This function does nothing as there should never be anything left in
        the buffer when using socket.sendall()"""
        pass

    def queued_bytes(self):
        """Determine how many bytes are in the buffer"""
        length = 0
        try:
            self.socket.settimeout(0)
            length = len(self.socket.recv(8192, socket.MSG_PEEK))
        except socket.error:
            pass
        finally:
            self.socket.settimeout(self.timeout)
        return length

    def read(self, chars=1):
        """Read bytes from WeatherLinkIP"""
        try:
            _buffer = self.socket.recv(chars)
            N = len(_buffer)
            if N != chars:
                raise WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
            return _buffer
        except:
            raise WeeWxIOError("Socket read error")
        
    def write(self, data):
        """Write to a WeatherLinkIP"""
        try:
            self.socket.sendall(data)
            time.sleep(self.tcp_send_delay)
        except:
            raise WeeWxIOError("Socket write error")


#===============================================================================
#                         VantagePro class
#===============================================================================

class VantagePro(object):
    """Class that represents a connection to a VantagePro console.
    
    The connection will be opened after initialization"""

    
    def __init__(self, **vp_dict) :
        """Initialize an object of type VantagePro. """

        self.wait_before_retry= float(vp_dict.get('wait_before_retry', 1.2))
        self.max_tries        = int(vp_dict.get('max_tries'    , 4))

        # Get the port:
        self.port = EthernetWrapper(hostname, tcp_port, timeout, tcp_send_delay)
        #self.port = SerialWrapper(port, baudrate, timeout)
        # Open it up:
        self.port.openPort()

    def closePort(self):
        """Close the connection to the console. """
        self.port.closePort()
        

    def genArchivePackets(self):
        """A generator function to return all archive packets on a VP2.
        
        yields: a sequence of dictionaries containing the data
        """
        
        # Wake up the console...
        self.port.wakeup_console()
        # ... request a dump...
        self.port.send_data('DMP\n')
        
        # Cycle through the pages...
        for ipage in range(512):
            # ... get a page of archive data
            _page = self.port.get_data_with_crc16(267, prompt=_ack, max_tries=self.max_tries)
            # Now extract each record from the page
            for _index in xrange(5) :
                # If the console has been recently initialized, there will
                # be unused records, which are filled with 0xff. Detect this
                # by looking at the first 4 bytes (the date and time):
                if _page[1+52*_index:5+52*_index] == 4*chr(0xff) :
                    yield None

                # Unpack the raw archive packet:
                _packet = unpackArchivePacket(_page[1+52*_index:53+52*_index])
                timestamp = _archive_datetime(_packet)
                yield timestamp
            
#===============================================================================
#                                    UTILITIES
#===============================================================================

def timestamp_to_string(ts):
    """Return a string formatted from the timestamp    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(ts)), ts)
    else:
        return "****** N/A ******** (    N/A   )"

# Tuples of all the types held in a VantagePro2 Rev A or Rev B archive packet in their native order.
vp2archA =('date_stamp', 'time_stamp', 'outTemp', 'highOutTemp', 'lowOutTemp',
           'rain', 'rainRate', 'barometer', 'radiation', 'number_of_wind_samples',
           'inTemp', 'inHumidity', 'outHumidity', 'windSpeed', 'windGust', 'windGustDir', 'windDir',
           'UV', 'ET', 'soilMoist1', 'soilMoist2', 'soilMoist3', 'soilMoist4', 
           'soilTemp1', 'soilTemp2', 'soilTemp3','soilTemp4', 
           'leafWet1', 'leafWet2', 'leafWet3', 'leafWet4',
           'extraTemp1', 'extraTemp2',
           'extraHumid1', 'extraHumid2',
           'readClosed', 'readOpened')

vp2archB =('date_stamp', 'time_stamp', 'outTemp', 'highOutTemp', 'lowOutTemp',
           'rain', 'rainRate', 'barometer', 'radiation', 'number_of_wind_samples',
           'inTemp', 'inHumidity', 'outHumidity', 'windSpeed', 'windGust', 'windGustDir', 'windDir',
           'UV', 'ET', 'highRadiation', 'highUV', 'forecastRule',
           'leafTemp1', 'leafTemp2', 'leafWet1', 'leafWet2',
           'soilTemp1', 'soilTemp2', 'soilTemp3','soilTemp4', 'download_record_type',
           'extraHumid1', 'extraHumid2', 'extraTemp1', 'extraTemp2', 'extraTemp3',
           'soilMoist1', 'soilMoist2', 'soilMoist3', 'soilMoist4')

archive_format_revA = struct.Struct("<HHhhhHHHHHhBBBBBBBBx4B4B4B2B2BHHx")
archive_format_revB = struct.Struct("<HHhhhHHHHHhBBBBBBBBHBB2B2B4BB2B3B4B")
    
def unpackArchivePacket(raw_packet):
    """Decode a Davis archive packet, returning the results as a dictionary.
    
    raw_packet: The archive packet data buffer, passed in as a string. This will be unpacked and 
    the results placed a dictionary"""

    # Figure out the packet type:
    packet_type = ord(raw_packet[42])
    
    if packet_type == 0x00 :
        # Rev B packet type:
        archive_format = archive_format_revB
        dataTypes = vp2archB
    elif packet_type == 0xff:
        # Rev A packet type:
        archive_format = archive_format_revA
        dataTypes = vp2archA
    else:
        raise UnknownArchiveType("Unknown archive type = 0x%x" % (packet_type,)) 
        
    data_tuple = archive_format.unpack(raw_packet)
    
    packet = dict(zip(dataTypes, data_tuple))
    
    return packet

def _archive_datetime(packet) :
    """Returns the epoch time of the archive packet."""
    datestamp = packet['date_stamp']
    timestamp = packet['time_stamp']
    
    # Decode the Davis time, constructing a time-tuple from it:
    time_tuple = ((0xfe00 & datestamp) >> 9,    # year
                  (0x01e0 & datestamp) >> 5,    # month
                  (0x001f & datestamp),         # day
                  timestamp // 100,             # hour
                  timestamp % 100,              # minute
                  0,                            # second
                  0, 0, -1)
    # Convert to epoch time:
    try:
        ts = int(time.mktime(time_tuple))
    except (OverflowError, ValueError):
        ts = None
    return ts
    
import array

_table=(
0x0000,  0x1021,  0x2042,  0x3063,  0x4084,  0x50a5,  0x60c6,  0x70e7,  # 0x00
0x8108,  0x9129,  0xa14a,  0xb16b,  0xc18c,  0xd1ad,  0xe1ce,  0xf1ef,  # 0x08  
0x1231,  0x0210,  0x3273,  0x2252,  0x52b5,  0x4294,  0x72f7,  0x62d6,  # 0x10
0x9339,  0x8318,  0xb37b,  0xa35a,  0xd3bd,  0xc39c,  0xf3ff,  0xe3de,  # 0x18
0x2462,  0x3443,  0x0420,  0x1401,  0x64e6,  0x74c7,  0x44a4,  0x5485,  # 0x20
0xa56a,  0xb54b,  0x8528,  0x9509,  0xe5ee,  0xf5cf,  0xc5ac,  0xd58d,  # 0x28
0x3653,  0x2672,  0x1611,  0x0630,  0x76d7,  0x66f6,  0x5695,  0x46b4,  # 0x30
0xb75b,  0xa77a,  0x9719,  0x8738,  0xf7df,  0xe7fe,  0xd79d,  0xc7bc,  # 0x38
0x48c4,  0x58e5,  0x6886,  0x78a7,  0x0840,  0x1861,  0x2802,  0x3823,  # 0x40
0xc9cc,  0xd9ed,  0xe98e,  0xf9af,  0x8948,  0x9969,  0xa90a,  0xb92b,  # 0x48
0x5af5,  0x4ad4,  0x7ab7,  0x6a96,  0x1a71,  0x0a50,  0x3a33,  0x2a12,  # 0x50
0xdbfd,  0xcbdc,  0xfbbf,  0xeb9e,  0x9b79,  0x8b58,  0xbb3b,  0xab1a,  # 0x58
0x6ca6,  0x7c87,  0x4ce4,  0x5cc5,  0x2c22,  0x3c03,  0x0c60,  0x1c41,  # 0x60
0xedae,  0xfd8f,  0xcdec,  0xddcd,  0xad2a,  0xbd0b,  0x8d68,  0x9d49,  # 0x68
0x7e97,  0x6eb6,  0x5ed5,  0x4ef4,  0x3e13,  0x2e32,  0x1e51,  0x0e70,  # 0x70
0xff9f,  0xefbe,  0xdfdd,  0xcffc,  0xbf1b,  0xaf3a,  0x9f59,  0x8f78,  # 0x78
0x9188,  0x81a9,  0xb1ca,  0xa1eb,  0xd10c,  0xc12d,  0xf14e,  0xe16f,  # 0x80
0x1080,  0x00a1,  0x30c2,  0x20e3,  0x5004,  0x4025,  0x7046,  0x6067,  # 0x88
0x83b9,  0x9398,  0xa3fb,  0xb3da,  0xc33d,  0xd31c,  0xe37f,  0xf35e,  # 0x90
0x02b1,  0x1290,  0x22f3,  0x32d2,  0x4235,  0x5214,  0x6277,  0x7256,  # 0x98
0xb5ea,  0xa5cb,  0x95a8,  0x8589,  0xf56e,  0xe54f,  0xd52c,  0xc50d,  # 0xA0
0x34e2,  0x24c3,  0x14a0,  0x0481,  0x7466,  0x6447,  0x5424,  0x4405,  # 0xA8
0xa7db,  0xb7fa,  0x8799,  0x97b8,  0xe75f,  0xf77e,  0xc71d,  0xd73c,  # 0xB0
0x26d3,  0x36f2,  0x0691,  0x16b0,  0x6657,  0x7676,  0x4615,  0x5634,  # 0xB8
0xd94c,  0xc96d,  0xf90e,  0xe92f,  0x99c8,  0x89e9,  0xb98a,  0xa9ab,  # 0xC0
0x5844,  0x4865,  0x7806,  0x6827,  0x18c0,  0x08e1,  0x3882,  0x28a3,  # 0xC8
0xcb7d,  0xdb5c,  0xeb3f,  0xfb1e,  0x8bf9,  0x9bd8,  0xabbb,  0xbb9a,  # 0xD0
0x4a75,  0x5a54,  0x6a37,  0x7a16,  0x0af1,  0x1ad0,  0x2ab3,  0x3a92,  # 0xD8
0xfd2e,  0xed0f,  0xdd6c,  0xcd4d,  0xbdaa,  0xad8b,  0x9de8,  0x8dc9,  # 0xE0
0x7c26,  0x6c07,  0x5c64,  0x4c45,  0x3ca2,  0x2c83,  0x1ce0,  0x0cc1,  # 0xE8
0xef1f,  0xff3e,  0xcf5d,  0xdf7c,  0xaf9b,  0xbfba,  0x8fd9,  0x9ff8,  # 0xF0
0x6e17,  0x7e36,  0x4e55,  0x5e74,  0x2e93,  0x3eb2,  0x0ed1,  0x1ef0,  # 0xF8
)

table = array.array('H',_table)

def crc16(string, crc=0):
    """ Calculate CRC16 sum"""

    for ch in string:
        crc = (table[((crc>>8)^ord(ch)) & 0xff] ^ (crc<<8)) & 0xffff
    return crc

#===============================================================================
#                       SerialWrapper
#===============================================================================


#class SerialWrapper(object):
#    """Wraps a serial connection returned from package serial"""
#    
#    def __init__(self, port, baudrate, timeout):
#        self.port     = port
#        self.baudrate = baudrate
#        self.timeout  = timeout
#
#
#    #===============================================================================
#    #          Primitives for working with the Davis Console
#    #===============================================================================
#
#    def wakeup_console(self, max_tries=3, wait_before_retry=1.2):
#        """Wake up a Davis VantagePro console.
#        
#        If unsuccessful, an exception of type weewx.WakeupError is thrown"""
#    
#        # Wake up the console. Try up to max_tries times
#        for unused_count in xrange(max_tries) :
#            try:
#                # Clear out any pending input or output characters:
#                self.flush_output()
#                self.flush_input()
#                # It can be hard to get the console's attention, particularly
#                # when in the middle of a LOOP command. Send a whole bunch of line feeds,
#                # then flush everything, then look for the \n\r acknowledgment
#                self.write('\n\n\n')
#                time.sleep(0.5)
#                self.flush_input()
#                self.write('\n')
#                _resp = self.read(2)
#                if _resp == '\n\r':
#                    print "successfully woke up console"
#                    return
#                print "Unable to wake up console... sleeping"
#                time.sleep(wait_before_retry)
#                print "Unable to wake up console... retrying"
#            except WeeWxIOError:
#                pass
#
#        print "Unable to wake up console"
#        raise WakeupError("Unable to wake up VantagePro console")
#
#    def send_data(self, data):
#        """Send data to the Davis console, waiting for an acknowledging <ACK>
#        
#        If the <ACK> is not received, no retry is attempted. Instead, an exception
#        of type weewx.WeeWxIOError is raised
#    
#        data: The data to send, as a string"""
#
#        self.write(data)
#    
#        # Look for the acknowledging ACK character
#        _resp = self.read()
#        if _resp != _ack: 
#            print "No <ACK> received from console"
#            raise WeeWxIOError("No <ACK> received from VantagePro console")
#    
#    def send_data_with_crc16(self, data, max_tries=3) :
#        """Send data to the Davis console along with a CRC check, waiting for an acknowledging <ack>.
#        If none received, resend up to max_tries times.
#        
#        data: The data to send, as a string"""
#        
#        #Calculate the crc for the data:
#        _crc = crc16(data)
#
#        # ...and pack that on to the end of the data in big-endian order:
#        _data_with_crc = data + struct.pack(">H", _crc)
#        
#        # Retry up to max_tries times:
#        for unused_count in xrange(max_tries):
#            try:
#                self.write(_data_with_crc)
#                # Look for the acknowledgment.
#                _resp = self.read()
#                if _resp == _ack:
#                    return
#            except WeeWxIOError:
#                pass
#
#        print "VantagePro: Unable to pass CRC16 check while sending data"
#        raise CRCError("Unable to pass CRC16 check while sending data to VantagePro console")
#
#    def send_command(self, command, max_tries=3, wait_before_retry=1.2):
#        """Send a command to the console, then look for the string 'OK' in the response.
#        
#        Any response from the console is split on \n\r characters and returned as a list."""
#        
#        for unused_count in xrange(max_tries):
#            try :
#                self.wakeup_console(max_tries=max_tries, wait_before_retry=wait_before_retry)
#
#                self.write(command)
#                # Takes a bit for the VP to react and fill up the buffer. Sleep for a half sec:
#                time.sleep(0.5)
#                # Can't use function serial.readline() because the VP responds with \n\r, not just \n.
#                # So, instead find how many bytes are waiting and fetch them all
#                nc = self.queued_bytes()
#                _buffer = self.read(nc)
#                # Split the buffer on the newlines
#                _buffer_list = _buffer.strip().split('\n\r')
#                # The first member should be the 'OK' in the VP response
#                if _buffer_list[0] == 'OK' :
#                    # Return the rest:
#                    return _buffer_list[1:]
#
#            except WeeWxIOError:
#                # Caught an error. Keep trying...
#                continue
#        
#        print "Max retries exceeded while sending command %s" % command
#        raise RetriesExceeded("Max retries exceeded while sending command %s" % command)
#    
#        
#    def get_data_with_crc16(self, nbytes, prompt=None, max_tries=3) :
#        """Get a packet of data and do a CRC16 check on it, asking for retransmit if necessary.
#        
#        It is guaranteed that the length of the returned data will be of the requested length.
#        An exception of type CRCError will be thrown if the data cannot pass the CRC test
#        in the requested number of retries.
#        
#        nbytes: The number of bytes (including the 2 byte CRC) to get. 
#        
#        prompt: Any string to be sent before requesting the data. Default=None
#        
#        max_tries: Number of tries before giving up. Default=3
#        
#        returns: the packet data as a string. The last 2 bytes will be the CRC"""
#        if prompt:
#            self.write(prompt)
#            
#        first_time = True
#            
#        for unused_count in xrange(max_tries):
#            try:
#                if not first_time: 
#                    self.write(_resend)
#                _buffer = self.read(nbytes)
#                if crc16(_buffer) == 0 :
#                    return _buffer
#            except WeeWxIOError:
#                pass
#            first_time = False
#
#        print "Unable to pass CRC16 check while getting data"
#        raise CRCError("Unable to pass CRC16 check while getting data")
#
#    def flush_input(self):
#        self.serial_port.flushInput()
#
#    def flush_output(self):
#        self.serial_port.flushOutput()
#
#    def queued_bytes(self):
#        return self.serial_port.inWaiting()
# 
#    def read(self, chars=1):
#        _buffer = self.serial_port.read(chars)
#        N = len(_buffer)
#        if N != chars:
#            raise WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
#        return _buffer
#    
#    def write(self, data):
#        N = self.serial_port.write(data)
#        # Python version 2.5 and earlier returns 'None', so it cannot be used to test for completion.
#        if N is not None and N != len(data):
#            raise WeeWxIOError("Expected to write %d chars; sent %d instead" % (len(data), N))
#
#    def openPort(self):
#        # Open up the port and store it
#        self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
#
#    def closePort(self):
#        try:
#            # This will cancel any pending loop:
#            self.wakeup_console(max_tries=1)
#        except:
#            pass
#        self.serial_port.close()

#===============================================================================
#                               Main test
#===============================================================================

vp = VantagePro()

N=N_none=0
t1=time.time()

try:
    
    for ts in vp.genArchivePackets():
        print timestamp_to_string(ts)
        if ts:
            N += 1
        else:
            N_none += 1
except Exception, e:
    print "Exception:", e
else:
    print "Loop terminated normally"

T = time.time() - t1
print "Timestamps received: ", N
print "Nulls received:      ", N_none
print "Elapsed time (secs): ", T

