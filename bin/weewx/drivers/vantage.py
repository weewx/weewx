#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with a Davis VantagePro, VantagePro2,
or VantageVue weather station"""

from __future__ import with_statement
import datetime
import struct
import sys
import syslog
import time

from weewx.crc16 import crc16
from weeutil.weeutil import to_int
import weeutil.weeutil
import weewx.drivers
import weewx.units
import weewx.engine

DRIVER_NAME = 'Vantage'
DRIVER_VERSION = '3.0.7'

def loader(config_dict, engine):
    return VantageService(engine, config_dict)

def configurator_loader(config_dict):  # @UnusedVariable
    return VantageConfigurator()

def confeditor_loader():
    return VantageConfEditor()


# A few handy constants:
_ack    = chr(0x06)
_resend = chr(0x15) # NB: The Davis documentation gives this code as 0x21, but it's actually decimal 21

#===============================================================================
#                           class BaseWrapper
#===============================================================================

class BaseWrapper(object):
    """Base class for (Serial|Ethernet)Wrapper"""

    def __init__(self, wait_before_retry, command_delay):
        
        self.wait_before_retry = wait_before_retry
        self.command_delay = command_delay
        
    #===============================================================================
    #          Primitives for working with the Davis Console
    #===============================================================================

    def wakeup_console(self, max_tries=3):
        """Wake up a Davis Vantage console.

        This call has three purposes:
        1. Wake up a sleeping console;
        2. Cancel pending LOOP data (if any);
        3. Flush the input buffer
           Note: a flushed buffer is important before sending a command; we want to make sure
           the next received character is the expected ACK.
        
        If unsuccessful, an exception of type weewx.WakeupError is thrown"""

        for count in xrange(max_tries):
            try:
                # Wake up console and cancel pending LOOP data.
                # First try a gentle wake up
                self.write('\n')
                _resp = self.read(2)
                if _resp == '\n\r':  # LF, CR = 0x0a, 0x0d
                    # We're done; the console accepted our cancel LOOP command; nothing to flush
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: gentle wake up of console successful")
                    return
                # That didn't work. Try a rude wake up.
                # Flush any pending LOOP packets
                self.flush_input()
                # Look for the acknowledgment of the sent '\n'
                _resp = self.read(2)
                if _resp == '\n\r':
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: rude wake up of console successful")
                    return
                print "Unable to wake up console... sleeping"
                time.sleep(self.wait_before_retry)
                print "Unable to wake up console... retrying"
            except weewx.WeeWxIOError:
                pass
            syslog.syslog(syslog.LOG_DEBUG, "vantage: retry  #%d failed" % count)

        syslog.syslog(syslog.LOG_ERR, "vantage: Unable to wake up console")
        raise weewx.WakeupError("Unable to wake up Vantage console")

    def send_data(self, data):
        """Send data to the Davis console, waiting for an acknowledging <ACK>
        
        If the <ACK> is not received, no retry is attempted. Instead, an exception
        of type weewx.WeeWxIOError is raised
    
        data: The data to send, as a string"""

        self.write(data)
    
        # Look for the acknowledging ACK character
        _resp = self.read()
        if _resp != _ack: 
            syslog.syslog(syslog.LOG_ERR, "vantage: No <ACK> received from console")
            raise weewx.WeeWxIOError("No <ACK> received from Vantage console")
    
    def send_data_with_crc16(self, data, max_tries=3):
        """Send data to the Davis console along with a CRC check, waiting for an acknowledging <ack>.
        If none received, resend up to max_tries times.
        
        data: The data to send, as a string"""
        
        # Calculate the crc for the data:
        _crc = crc16(data)

        # ...and pack that on to the end of the data in big-endian order:
        _data_with_crc = data + struct.pack(">H", _crc)
        
        # Retry up to max_tries times:
        for count in xrange(max_tries):
            try:
                self.write(_data_with_crc)
                # Look for the acknowledgment.
                _resp = self.read()
                if _resp == _ack:
                    return
            except weewx.WeeWxIOError:
                pass
            syslog.syslog(syslog.LOG_DEBUG, "vantage: send_data_with_crc16; try #%d" % (count + 1,))

        syslog.syslog(syslog.LOG_ERR, "vantage: Unable to pass CRC16 check while sending data")
        raise weewx.CRCError("Unable to pass CRC16 check while sending data to Vantage console")

    def send_command(self, command, max_tries=3):
        """Send a command to the console, then look for the string 'OK' in the response.
        
        Any response from the console is split on \n\r characters and returned as a list."""
        
        for count in xrange(max_tries):
            try:
                self.wakeup_console(max_tries=max_tries)

                self.write(command)
                # Takes some time for the Vantage to react and fill up the buffer. Sleep for a bit:
                time.sleep(self.command_delay)
                # Can't use function serial.readline() because the VP responds with \n\r, not just \n.
                # So, instead find how many bytes are waiting and fetch them all
                nc = self.queued_bytes()
                _buffer = self.read(nc)
                # Split the buffer on the newlines
                _buffer_list = _buffer.strip().split('\n\r')
                # The first member should be the 'OK' in the VP response
                if _buffer_list[0] == 'OK':
                    # Return the rest:
                    return _buffer_list[1:]

            except weewx.WeeWxIOError:
                # Caught an error. Keep trying...
                pass
            syslog.syslog(syslog.LOG_DEBUG, "vantage: send_command; try #%d failed" % (count + 1,))
        
        syslog.syslog(syslog.LOG_ERR, "vantage: Max retries exceeded while sending command %s" % command)
        raise weewx.RetriesExceeded("Max retries exceeded while sending command %s" % command)
    
        
    def get_data_with_crc16(self, nbytes, prompt=None, max_tries=3):
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
        _buffer = ''

        for count in xrange(max_tries):
            try:
                if not first_time: 
                    self.write(_resend)
                _buffer = self.read(nbytes)
                if crc16(_buffer) == 0:
                    return _buffer
            except weewx.WeeWxIOError:
                pass
            syslog.syslog(syslog.LOG_DEBUG, "vantage: get_data_with_crc16; try #%d failed" % (count + 1,))
            first_time = False

        if _buffer:
            syslog.syslog(syslog.LOG_ERR, "vantage: Unable to pass CRC16 check while getting data")
            raise weewx.CRCError("Unable to pass CRC16 check while getting data")
        else:
            syslog.syslog(syslog.LOG_DEBUG, "vantage: get_data_with_crc16 time out")
            raise weewx.WeeWxIOError("Time out in get_data_with_crc16")

#===============================================================================
#                           class Serial Wrapper
#===============================================================================

def guard_termios(fn):
    """Decorator function that converts termios exceptions into weewx exceptions."""
    # Some functions in the module 'serial' can raise undocumented termios
    # exceptions. This catches them and converts them to weewx exceptions. 
    try:
        import termios
        def guarded_fn(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except termios.error, e:
                raise weewx.WeeWxIOError(e)
    except ImportError:
        def guarded_fn(*args, **kwargs):
            return fn(*args, **kwargs)
    return guarded_fn

class SerialWrapper(BaseWrapper):
    """Wraps a serial connection returned from package serial"""
    
    def __init__(self, port, baudrate, timeout, wait_before_retry, command_delay):
        super(SerialWrapper, self).__init__(wait_before_retry=wait_before_retry,
                                            command_delay=command_delay)
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout

    @guard_termios
    def flush_input(self):
        self.serial_port.flushInput()

    @guard_termios
    def flush_output(self):
        self.serial_port.flushOutput()

    @guard_termios
    def queued_bytes(self):
        return self.serial_port.inWaiting()
 
    def read(self, chars=1):
        import serial
        try:
            _buffer = self.serial_port.read(chars)
        except serial.serialutil.SerialException, e:
            syslog.syslog(syslog.LOG_ERR, "vantage: SerialException.")
            syslog.syslog(syslog.LOG_ERR, "   ****  %s" % e)
            syslog.syslog(syslog.LOG_ERR, "   ****  Is there a competing process running??")
            # Reraise as a Weewx error I/O error:
            raise weewx.WeeWxIOError(e)
        N = len(_buffer)
        if N != chars:
            raise weewx.WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
        return _buffer
    
    def write(self, data):
        N = self.serial_port.write(data)
        # Python version 2.5 and earlier returns 'None', so it cannot be used to test for completion.
        if N is not None and N != len(data):
            raise weewx.WeeWxIOError("Expected to write %d chars; sent %d instead" % (len(data), N))

    def openPort(self):
        import serial
        # Open up the port and store it
        self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        syslog.syslog(syslog.LOG_DEBUG, "vantage: Opened up serial port %s; baud %d; timeout %.2f" % 
                      (self.port, self.baudrate, self.timeout))

    def closePort(self):
        try:
            # This will cancel any pending loop:
            self.write('\n')
        except:
            pass
        self.serial_port.close()

#===============================================================================
#                           class EthernetWrapper
#===============================================================================

class EthernetWrapper(BaseWrapper):
    """Wrap a socket"""

    def __init__(self, host, port, timeout, tcp_send_delay, wait_before_retry, command_delay):
        
        super(EthernetWrapper, self).__init__(wait_before_retry=wait_before_retry, 
                                              command_delay=command_delay)

        self.host           = host
        self.port           = port
        self.timeout        = timeout
        self.tcp_send_delay = tcp_send_delay

    def openPort(self):
        import socket
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
        except (socket.error, socket.timeout, socket.herror), ex:
            syslog.syslog(syslog.LOG_ERR, "vantage: Socket error while opening port %d to ethernet host %s." % (self.port, self.host))
            # Reraise as a weewx I/O error:
            raise weewx.WeeWxIOError(ex)
        except:
            syslog.syslog(syslog.LOG_ERR, "vantage: Unable to connect to ethernet host %s on port %d." % (self.host, self.port))
            raise
        syslog.syslog(syslog.LOG_DEBUG, "vantage: Opened up ethernet host %s on port %d. timeout=%s, tcp_send_delay=%s" %
                      (self.host, self.port, self.timeout, self.tcp_send_delay))

    def closePort(self):
        import socket
        try:
            # This will cancel any pending loop:
            self.write('\n')
        except:
            pass
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def flush_input(self):
        """Flush the input buffer from WeatherLinkIP"""
        import socket
        try:
            # This is a bit of a hack, but there is no analogue to pyserial's flushInput()
            # Set socket timeout to 0 to get immediate result
            self.socket.settimeout(0)
            self.socket.recv(4096)
        except (socket.timeout, socket.error):
            pass
        finally:
            # set socket timeout back to original value
            self.socket.settimeout(self.timeout)

    def flush_output(self):
        """Flush the output buffer to WeatherLinkIP

        This function does nothing as there should never be anything left in
        the buffer when using socket.sendall()"""
        pass

    def queued_bytes(self):
        """Determine how many bytes are in the buffer"""
        import socket
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
        import socket
        _buffer = ''
        _remaining = chars
        while _remaining:
            _N = min(4096, _remaining)
            try:
                _recv = self.socket.recv(_N)
            except (socket.timeout, socket.error), ex:
                syslog.syslog(syslog.LOG_ERR, "vantage: ip-read error: %s" % ex)
                # Reraise as a weewx I/O error:
                raise weewx.WeeWxIOError(ex)
            _nread = len(_recv)
            if _nread == 0:
                raise weewx.WeeWxIOError("vantage: Expected %d characters; got zero instead" % (_N,))
            _buffer += _recv
            _remaining -= _nread
        return _buffer
    
    def write(self, data):
        """Write to a WeatherLinkIP"""
        import socket
        try:
            self.socket.sendall(data)
            # A delay of 0.0 gives socket write error; 0.01 gives no ack error; 0.05 is OK for weewx program
            # Note: a delay of 0.5 s is required for wee_device --logger=logger_info
            time.sleep(self.tcp_send_delay)
        except (socket.timeout, socket.error), ex:
            syslog.syslog(syslog.LOG_ERR, "vantage: ip-write error: %s" % ex)
            # Reraise as a weewx I/O error:
            raise weewx.WeeWxIOError(ex)

#===============================================================================
#                           class Vantage
#===============================================================================

class Vantage(weewx.drivers.AbstractDevice):
    """Class that represents a connection to a Davis Vantage console.
    
    The connection to the console will be open after initialization"""

    # Various codes used internally by the VP2:
    barometer_unit_dict   = {0:'inHg', 1:'mmHg', 2:'hPa', 3:'mbar'}
    temperature_unit_dict = {0:'degree_F', 1:'degree_10F', 2:'degree_C', 3:'degree_10C'}
    altitude_unit_dict    = {0:'foot', 1:'meter'}
    rain_unit_dict        = {0:'inch', 1:'mm'}
    wind_unit_dict        = {0:'mile_per_hour', 1:'meter_per_second', 2:'km_per_hour', 3:'knot'}
    wind_cup_dict         = {0:'small', 1:'large'}
    rain_bucket_dict      = {0: "0.01 inches", 1: "0.2 MM", 2: "0.1 MM"}
    transmitter_type_dict = {0: 'iss', 1: 'temp', 2: 'hum', 3: 'temp_hum', 4: 'wind',
                             5: 'rain', 6: 'leaf', 7: 'soil', 8: 'leaf_soil',
                             9: 'sensorlink', 10: 'none'}
    
    def __init__(self, **vp_dict):
        """Initialize an object of type Vantage.
        
        NAMED ARGUMENTS:
        
        connection_type: The type of connection (serial|ethernet) [Required]

        port: The serial port of the VP. [Required if serial/USB
        communication]

        host: The Vantage network host [Required if Ethernet communication]
        
        baudrate: Baudrate of the port. [Optional. Default 19200]

        tcp_port: TCP port to connect to [Optional. Default 22222]
        
        tcp_send_delay: Block after sending data to WeatherLinkIP to allow it
        to process the command [Optional. Default is 0.5]

        timeout: How long to wait before giving up on a response from the
        serial port. [Optional. Default is 4]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 1.2 seconds]
        
        command_delay: How long to wait after sending a command before looking
        for acknowledgement. [Optional. Default is 0.5 seconds]

        max_tries: How many times to try again before giving up. [Optional.
        Default is 4]
        
        iss_id: The station number of the ISS [Optional. Default is 1]
        """

        syslog.syslog(syslog.LOG_DEBUG, 'vantage: driver version is %s' % DRIVER_VERSION)

        # TODO: These values should really be retrieved dynamically from the VP:
        self.model_type = 2  # = 1 for original VantagePro, = 2 for VP2

        # These come from the configuration dictionary:
        self.max_tries = int(vp_dict.get('max_tries', 4))
        self.iss_id    = to_int(vp_dict.get('iss_id'))
        
        self.save_monthRain = None
        self.max_dst_jump = 7200

        # Get an appropriate port, depending on the connection type:
        self.port = Vantage._port_factory(vp_dict)

        # Open it up:
        self.port.openPort()

        # Read the EEPROM and fill in properties in this instance
        self._setup()
        
    def openPort(self):
        """Open up the connection to the console"""
        self.port.openPort()

    def closePort(self):
        """Close the connection to the console. """
        self.port.closePort()
        
    def genLoopPackets(self):
        """Generator function that returns loop packets"""
        
        for count in range(self.max_tries):
            while True:
                try:
                    # Get LOOP packets in big batches This is necessary because there is
                    # an undocumented limit to how many LOOP records you can request
                    # on the VP (somewhere around 220).
                    for _loop_packet in self.genDavisLoopPackets(200):
                        yield _loop_packet
                except weewx.WeeWxIOError, e:
                    syslog.syslog(syslog.LOG_ERR, "vantage: LOOP try #%d; error: %s" % (count + 1, e))
                    break

        syslog.syslog(syslog.LOG_ERR, "vantage: LOOP max tries (%d) exceeded." % self.max_tries)
        raise weewx.RetriesExceeded("Max tries exceeded while getting LOOP data.")

    def genDavisLoopPackets(self, N=1):
        """Generator function to return N loop packets from a Vantage console
        
        N: The number of packets to generate [default is 1]
        
        yields: up to N loop packets (could be less in the event of a 
        read or CRC error).
        """

        syslog.syslog(syslog.LOG_DEBUG, "vantage: Requesting %d LOOP packets." % N)
        
        self.port.wakeup_console(self.max_tries)
        
        # Request N packets:
        self.port.send_data("LOOP %d\n" % N)

        for loop in range(N):  # @UnusedVariable
            # Fetch a packet...
            _buffer = self.port.read(99)
            # ... see if it passes the CRC test ...
            if crc16(_buffer):
                raise weewx.CRCError("LOOP buffer failed CRC check")
            # ... decode it ...
            loop_packet = self._unpackLoopPacket(_buffer[:95])
            # .. then yield it
            yield loop_packet

    def genArchiveRecords(self, since_ts):
        """A generator function to return archive packets from a Davis Vantage station.
        
        since_ts: A timestamp. All data since (but not including) this time will be returned.
        Pass in None for all data
        
        yields: a sequence of dictionaries containing the data
        """

        count = 0
        while count < self.max_tries:
            try:            
                for _record in self.genDavisArchiveRecords(since_ts):
                    # Successfully retrieved record. Set count back to zero.
                    count = 0
                    since_ts = _record['dateTime']
                    yield _record
                # The generator loop exited. We're done.
                return
            except weewx.WeeWxIOError, e:
                # Problem. Increment retry count
                count += 1
                syslog.syslog(syslog.LOG_ERR, "vantage: DMPAFT try #%d; error: %s" % (count, e))

        syslog.syslog(syslog.LOG_ERR, "vantage: DMPAFT max tries (%d) exceeded." % self.max_tries)
        raise weewx.RetriesExceeded("Max tries exceeded while getting archive data.")

    def genDavisArchiveRecords(self, since_ts):
        """A generator function to return archive records from a Davis Vantage station.
        
        This version does not catch any exceptions."""
        
        if since_ts:
            since_tt = time.localtime(since_ts)
            # NB: note that some of the Davis documentation gives the year offset as 1900.
            # From experimentation, 2000 seems to be right, at least for the newer models:
            _vantageDateStamp = since_tt[2] + (since_tt[1] << 5) + ((since_tt[0] - 2000) << 9)
            _vantageTimeStamp = since_tt[3] * 100 + since_tt[4]
            syslog.syslog(syslog.LOG_DEBUG, 'vantage: Getting archive packets since %s' % weeutil.weeutil.timestamp_to_string(since_ts))
        else:
            _vantageDateStamp = _vantageTimeStamp = 0
            syslog.syslog(syslog.LOG_DEBUG, 'vantage: Getting all archive packets')
     
        # Pack the date and time into a string, little-endian order
        _datestr = struct.pack("<HH", _vantageDateStamp, _vantageTimeStamp)
        
        # Save the last good time:
        _last_good_ts = since_ts if since_ts else 0
        
        # Get the starting page and index. First, wake up the console...
        self.port.wakeup_console(self.max_tries)
        # ... request a dump...
        self.port.send_data('DMPAFT\n')
        # ... from the designated date (allow only one try because that's all the console allows):
        self.port.send_data_with_crc16(_datestr, max_tries=1)
        
        # Get the response with how many pages and starting index and decode it. Again, allow only one try:
        _buffer = self.port.get_data_with_crc16(6, max_tries=1)
      
        (_npages, _start_index) = struct.unpack("<HH", _buffer[:4])
        syslog.syslog(syslog.LOG_DEBUG, "vantage: Retrieving %d page(s); starting index= %d" % (_npages, _start_index))

        # Cycle through the pages...
        for ipage in xrange(_npages):
            # ... get a page of archive data
            _page = self.port.get_data_with_crc16(267, prompt=_ack, max_tries=1)
            # Now extract each record from the page
            for _index in xrange(_start_index, 5):
                # Get the record string buffer for this index:
                _record_string = _page[1 + 52 * _index:53 + 52 * _index]
                # If the console has been recently initialized, there will
                # be unused records, which are filled with 0xff. Detect this
                # by looking at the first 4 bytes (the date and time):
                if _record_string[0:4] == 4 * chr(0xff) or _record_string[0:4] == 4 * chr(0x00):
                    # This record has never been used. We're done.
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: empty record page %d; index %d" \
                                  % (ipage, _index))
                    return
                
                # Unpack the archive packet from the string buffer:
                _record = self._unpackArchivePacket(_record_string)

                # Check to see if the time stamps are declining, which would
                # signal that we are done. 
                if _record['dateTime'] is None or _record['dateTime'] <= _last_good_ts - self.max_dst_jump:
                    # The time stamp is declining. We're done.
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: DMPAFT complete: page timestamp %s less than final timestamp %s"\
                                  % (weeutil.weeutil.timestamp_to_string(_record['dateTime']),
                                     weeutil.weeutil.timestamp_to_string(_last_good_ts)))
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: Catch up complete.")
                    return
                # Set the last time to the current time, and yield the packet
                _last_good_ts = _record['dateTime']
                yield _record

            # The starting index for pages other than the first is always zero
            _start_index = 0

    def genArchiveDump(self):
        """A generator function to return all archive packets in the memory of a Davis Vantage station.
        
        yields: a sequence of dictionaries containing the data
        """
        import weewx.wxformulas
        
        # Wake up the console...
        self.port.wakeup_console(self.max_tries)
        # ... request a dump...
        self.port.send_data('DMP\n')

        syslog.syslog(syslog.LOG_DEBUG, "vantage: Dumping all records.")
        
        # Cycle through the pages...
        for ipage in xrange(512):
            # ... get a page of archive data
            _page = self.port.get_data_with_crc16(267, prompt=_ack, max_tries=self.max_tries)
            # Now extract each record from the page
            for _index in xrange(5):
                # Get the record string buffer for this index:
                _record_string = _page[1 + 52 * _index:53 + 52 * _index]
                # If the console has been recently initialized, there will
                # be unused records, which are filled with 0xff. Detect this
                # by looking at the first 4 bytes (the date and time):
                if _record_string[0:4] == 4 * chr(0xff) or _record_string[0:4] == 4 * chr(0x00):
                    # This record has never been used. Skip it
                    syslog.syslog(syslog.LOG_DEBUG, "vantage: empty record page %d; index %d" \
                                  % (ipage, _index))
                    continue
                # Unpack the raw archive packet:
                _record = self._unpackArchivePacket(_record_string)
                
                # Because the dump command does not go through the normal weewx
                # engine pipeline, we have to add these important software derived
                # variables here.
                try:
                    T = _record['outTemp']
                    R = _record['outHumidity']
                    W = _record['windSpeed']
                
                    _record['dewpoint']  = weewx.wxformulas.dewpointF(T, R)
                    _record['heatindex'] = weewx.wxformulas.heatindexF(T, R)
                    _record['windchill'] = weewx.wxformulas.windchillF(T, W)
                except KeyError:
                    pass

                yield _record

    def genLoggerSummary(self):
        """A generator function to return a summary of each page in the logger. 
        
        yields: A 8-way tuple containing (page, index, year, month, day, hour, minute, timestamp)
        """
        
        # Wake up the console...
        self.port.wakeup_console(self.max_tries)
        # ... request a dump...
        self.port.send_data('DMP\n')

        syslog.syslog(syslog.LOG_DEBUG, "vantage: Starting logger summary.")
        
        # Cycle through the pages...
        for _ipage in xrange(512):
            # ... get a page of archive data
            _page = self.port.get_data_with_crc16(267, prompt=_ack, max_tries=self.max_tries)
            # Now extract each record from the page
            for _index in xrange(5):
                # Get the record string buffer for this index:
                _record_string = _page[1 + 52 * _index:53 + 52 * _index]
                # If the console has been recently initialized, there will
                # be unused records, which are filled with 0xff. Detect this
                # by looking at the first 4 bytes (the date and time):
                if _record_string[0:4] == 4 * chr(0xff) or _record_string[0:4] == 4 * chr(0x00):
                    # This record has never been used.
                    y = mo = d = h = mn = time_ts = None
                else:
                    # Extract the date and time from the raw buffer:
                    datestamp, timestamp = struct.unpack("<HH", _record_string[0:4])
                    time_ts = _archive_datetime(datestamp, timestamp)
                    y  = (0xfe00 & datestamp) >> 9    # year
                    mo = (0x01e0 & datestamp) >> 5    # month
                    d  = (0x001f & datestamp)         # day
                    h  = timestamp // 100             # hour
                    mn = timestamp % 100              # minute
                yield (_ipage, _index, y, mo, d, h, mn, time_ts)
        syslog.syslog(syslog.LOG_DEBUG, "Vantage: Finished logger summary.")

    def getTime(self):
        """Get the current time from the console, returning it as timestamp"""

        time_dt = self.getConsoleTime()
        return time.mktime(time_dt.timetuple())

    def getConsoleTime(self):
        """Return the raw time on the console, uncorrected for DST or timezone."""
        
        # Try up to max_tries times:
        for unused_count in xrange(self.max_tries):
            try:
                # Wake up the console...
                self.port.wakeup_console(max_tries=self.max_tries)
                # ... request the time...
                self.port.send_data('GETTIME\n')
                # ... get the binary data. No prompt, only one try:
                _buffer = self.port.get_data_with_crc16(8, max_tries=1)
                (sec, minute, hr, day, mon, yr, unused_crc) = struct.unpack("<bbbbbbH", _buffer)
                
                return datetime.datetime(yr + 1900, mon, day, hr, minute, sec)
                
            except weewx.WeeWxIOError:
                # Caught an error. Keep retrying...
                continue
        syslog.syslog(syslog.LOG_ERR, "vantage: Max retries exceeded while getting time")
        raise weewx.RetriesExceeded("While getting console time")
            
    def setTime(self):
        """Set the clock on the Davis Vantage console"""

        for unused_count in xrange(self.max_tries):
            try:
                # Wake the console and begin the setTime command
                self.port.wakeup_console(max_tries=self.max_tries)
                self.port.send_data('SETTIME\n')

                # Unfortunately, clock resolution is only 1 second, and transmission takes a
                # little while to complete, so round up the clock up. 0.5 for clock resolution
                # and 0.25 for transmission delay
                newtime_tt = time.localtime(int(time.time() + 0.75))
 
                # The Davis expects the time in reversed order, and the year is since 1900
                _buffer = struct.pack("<bbbbbb", newtime_tt[5], newtime_tt[4], newtime_tt[3], newtime_tt[2],
                                                 newtime_tt[1], newtime_tt[0] - 1900)

                # Complete the setTime command
                self.port.send_data_with_crc16(_buffer, max_tries=1)
                syslog.syslog(syslog.LOG_NOTICE,
                              "vantage: Clock set to %s" % weeutil.weeutil.timestamp_to_string(time.mktime(newtime_tt)))
                return
            except weewx.WeeWxIOError:
                # Caught an error. Keep retrying...
                continue
        syslog.syslog(syslog.LOG_ERR, "vantage: Max retries exceeded while setting time")
        raise weewx.RetriesExceeded("While setting console time")
    
    def setDST(self, dst='auto'):
        """Turn DST on or off, or set it to auto.
        
        dst: One of 'auto', 'on' or 'off' """
        
        _dst = dst.strip().lower()
        if _dst not in ['auto', 'on', 'off']:
            raise weewx.ViolatedPrecondition("Invalid DST setting %s" % dst)

        # Set flag whether DST is auto or manual:        
        man_auto = 0 if _dst == 'auto' else 1
        self.port.send_data("EEBWR 12 01\n")
        self.port.send_data_with_crc16(chr(man_auto))
        
        # If DST is manual, set it on or off:
        if _dst in ['on', 'off']:
            on_off = 0 if _dst == 'off' else 1
            self.port.send_data("EEBWR 13 01\n")
            self.port.send_data_with_crc16(chr(on_off))
            
    def setTZcode(self, code):
        """Set the console's time zone code. See the Davis Vantage manual for the table
        of preset time zones."""
        if code < 0 or code > 46:
            raise weewx.ViolatedPrecondition("Invalid time zone code %d" % code)
        # Set the GMT_OR_ZONE byte to use TIME_ZONE value
        self.port.send_data("EEBWR 16 01\n")
        self.port.send_data_with_crc16(chr(0))
        # Set the TIME_ZONE value
        self.port.send_data("EEBWR 11 01\n")
        self.port.send_data_with_crc16(chr(code))
        
    def setTZoffset(self, offset):
        """Set the console's time zone to a custom offset.
        
        offset: Offset. This is an integer in hundredths of hours. E.g., -175 would be 1h45m negative offset."""
        # Set the GMT_OR_ZONE byte to use GMT_OFFSET value
        self.port.send_data("EEBWR 16 01\n")
        self.port.send_data_with_crc16(chr(1))
        # Set the GMT_OFFSET value
        self.port.send_data("EEBWR 14 02\n")
        self.port.send_data_with_crc16(struct.pack("<h", offset))

    def setBucketType(self, new_bucket_code):
        """Set the rain bucket type.
        
        new_bucket_code: The new bucket type. Must be one of 0, 1, or 2
        """
        if new_bucket_code not in (0, 1, 2):
            raise weewx.ViolatedPrecondition("Invalid bucket code %d" % new_bucket_code)
        old_setup_bits = self._getEEPROM_value(0x2B)[0]
        new_setup_bits = (old_setup_bits & 0xCF) | (new_bucket_code << 4)
        
        # Tell the console to put one byte in hex location 0x2B
        self.port.send_data("EEBWR 2B 01\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_setup_bits), max_tries=1)
        # Then call NEWSETUP to get it to stick:
        self.port.send_data("NEWSETUP\n")
        
        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Rain bucket type set to %d (%s)" % (self.rain_bucket_type, self.rain_bucket_size))

    def setRainYearStart(self, new_rain_year_start):
        """Set the start of the rain season.
        
        new_rain_year_start: Must be in the closed range 1...12
        """
        if new_rain_year_start not in range(1, 13):
            raise weewx.ViolatedPrecondition("Invalid rain season start %d" % (new_rain_year_start,))
        
        # Tell the console to put one byte in hex location 0x2C
        self.port.send_data("EEBWR 2C 01\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_rain_year_start), max_tries=1)

        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Rain year start set to %d" % (self.rain_year_start,))

    def setBarData(self, new_barometer_inHg, new_altitude_foot):
        """Set the internal barometer calibration and altitude settings in the console.
        
        new_barometer_inHg: The local, reference barometric pressure in inHg.
        
        new_altitude_foot: The new altitude in feet."""
        
        new_barometer = int(new_barometer_inHg * 1000.0)
        new_altitude = int(new_altitude_foot)
        
        command = "BAR=%d %d\n" % (new_barometer, new_altitude)
        self.port.send_command(command)
        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Set barometer calibration.")
        
    def setArchiveInterval(self, archive_interval_seconds):
        """Set the archive interval of the Vantage.
        
        archive_interval_seconds: The new interval to use in minutes. Must be one of
        60, 300, 600, 900, 1800, 3600, or 7200 
        """
        if archive_interval_seconds not in (60, 300, 600, 900, 1800, 3600, 7200):
            raise weewx.ViolatedPrecondition, "vantage: Invalid archive interval (%d)" % (archive_interval_seconds,)

        # The console expects the interval in minutes. Divide by 60.
        command = 'SETPER %d\n' % (archive_interval_seconds / 60)
        
        self.port.send_command(command, max_tries=self.max_tries)

        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "vantage: archive interval set to %d seconds" % (archive_interval_seconds,))
    
    def setLamp(self, onoff='OFF'):
        """Set the lamp on or off"""
        try:        
            _setting = {'off': '0', 'on': '1'}[onoff.lower()]
        except KeyError:
            raise ValueError("Unknown lamp setting '%s'" % onoff)

        _command = "LAMPS %s\n" % _setting
        self.port.send_command(_command, max_tries=self.max_tries)

        syslog.syslog(syslog.LOG_NOTICE, "vantage: Lamp set to '%s'" % onoff)
        
    def setTransmitterType(self, new_channel, new_transmitter_type, new_extra_temp, new_extra_hum):
        """Set the transmitter type for one of the eight channels."""
        
        # Default value just for tidiness.
        new_temp_hum_bits = 0xFF

        # Check arguments are consistent.
        if new_channel not in range(0, 8):
            raise weewx.ViolatedPrecondition("Invalid channel %d" % new_channel)
        if new_transmitter_type not in range(0, 11):
            raise weewx.ViolatedPrecondition("Invalid transmitter type %d" % new_transmitter_type)
        if Vantage.transmitter_type_dict[new_transmitter_type] in ['temp', 'temp_hum']:
            if new_extra_temp not in range(1, 9):
                raise weewx.ViolatedPrecondition("Invalid extra temperature number %d" % new_extra_temp)
            # Extra temp is origin 0.
            new_temp_hum_bits = new_temp_hum_bits & 0xF0 | (new_extra_temp - 1)
        if Vantage.transmitter_type_dict[new_transmitter_type] in ['hum', 'temp_hum']:
            if new_extra_hum not in range(1, 9):
                raise weewx.ViolatedPrecondition("Invalid extra humidity number %d" % new_extra_hum)
            # Extra humidity is origin 1.
            new_temp_hum_bits = new_temp_hum_bits & 0x0F | (new_extra_hum << 4)

        # Preserve top nibble, is related to repeaters.
        old_type_bits = self._getEEPROM_value(0x19 + (new_channel - 1) * 2)[0]
        new_type_bits = old_type_bits & 0xF0 | new_transmitter_type
        # Transmitter type 10 is "none"; turn off listening too.
        usetx = 1 if new_transmitter_type != 10 else 0
        old_usetx_bits = self._getEEPROM_value(0x17)[0]
        new_usetx_bits = old_usetx_bits & ~(1 << (new_channel - 1)) | usetx * (1 << new_channel - 1)
        
        # Tell the console to put two bytes in hex location 0x19 or 0x1B or ... depending on channel.
        self.port.send_data("EEBWR %X 02\n" % (0x19 + (new_channel - 1) * 2))
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_type_bits) + chr(new_temp_hum_bits), max_tries=1)
        # Tell the console to put one byte in hex location 0x17
        self.port.send_data("EEBWR 17 01\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_usetx_bits), max_tries=1)
        # Then call NEWSETUP to get it to stick:
        self.port.send_data("NEWSETUP\n")
        
        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Transmitter type for channel %d set to %d (%s)" %
                      (new_channel, new_transmitter_type, Vantage.transmitter_type_dict[new_transmitter_type]))

    def setCalibrationWindDir(self, offset):
        """Set the on-board wind direction calibration."""
        if offset < -359 or offset > 359:
            raise weewx.ViolatedPrecondition("Offset %d out of range [-359, 359]." % offset)
        nbytes = struct.pack("<h", offset)
        # Tell the console to put two bytes in hex location 0x4D
        self.port.send_data("EEBWR 4D 02\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(nbytes, max_tries=1)
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Wind calibration set to %d" % (offset))

    def setCalibrationTemp(self, variable, offset):
        """Set an on-board temperature calibration."""
        # Offset is in tenths of degree Fahrenheit.
        if offset < -12.8 or offset > 12.7:
            raise weewx.ViolatedPrecondition("Offset %.1f out of range [-12.8, 12.7]." % offset)
        byte = struct.pack("b", int(round(offset * 10)))
        variable_dict = { 'outTemp': 0x34 }
        for i in range(1, 8): variable_dict['extraTemp%d' % i] = 0x34 + i 
        for i in range(1, 5): variable_dict['soilTemp%d' % i] = 0x3B + i 
        for i in range(1, 5): variable_dict['leafTemp%d' % i] = 0x3F + i 
        if variable == "inTemp":
            # Inside temp is special, needs ones' complement in next byte.
            complement_byte = struct.pack("B", ~int(round(offset * 10)) & 0xFF)
            self.port.send_data("EEBWR 32 02\n")
            self.port.send_data_with_crc16(byte + complement_byte, max_tries=1)
        elif variable in variable_dict:
            # Other variables are just sent as-is.
            self.port.send_data("EEBWR %X 01\n" % variable_dict[variable])
            self.port.send_data_with_crc16(byte, max_tries=1)
        else:
            raise weewx.ViolatedPrecondition("Variable name %s not known" % variable)
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Temperature calibration %s set to %.1f" % (variable, offset))

    def setCalibrationHumid(self, variable, offset):
        """Set an on-board humidity calibration."""
        # Offset is in percentage points.
        if offset < -100 or offset > 100:
            raise weewx.ViolatedPrecondition("Offset %d out of range [-100, 100]." % offset)
        byte = struct.pack("b", offset)
        variable_dict = { 'inHumid': 0x44, 'outHumid': 0x45 }
        for i in range(1, 8): variable_dict['extraHumid%d' % i] = 0x45 + i 
        if variable in variable_dict:
            self.port.send_data("EEBWR %X 01\n" % variable_dict[variable])
            self.port.send_data_with_crc16(byte, max_tries=1)
        else:
            raise weewx.ViolatedPrecondition("Variable name %s not known" % variable)
        syslog.syslog(syslog.LOG_NOTICE, "vantage: Humidity calibration %s set to %d" % (variable, offset))

    def clearLog(self):
        """Clear the internal archive memory in the Vantage."""
        for unused_count in xrange(self.max_tries):
            try:
                self.port.wakeup_console(max_tries=self.max_tries)
                self.port.send_data("CLRLOG\n")
                syslog.syslog(syslog.LOG_NOTICE, "vantage: Archive memory cleared.")
                return
            except weewx.WeeWxIOError:
                # Caught an error. Keey trying...
                continue
        syslog.syslog(syslog.LOG_ERR, "vantage: Max retries exceeded while clearing log")
        raise weewx.RetriesExceeded("While clearing log")
    
    def getRX(self):
        """Returns reception statistics from the console.
        
        Returns a tuple with 5 values: (# of packets, # of missed packets,
        # of resynchronizations, the max # of packets received w/o an error,
        the # of CRC errors detected.)"""

        rx_list = self.port.send_command('RXCHECK\n')
        if weewx.debug:
            assert(len(rx_list) == 1)
        
        # The following is a list of the reception statistics, but the elements are strings
        rx_list_str = rx_list[0].split()
        # Convert to numbers and return as a tuple:
        rx_list = tuple(int(x) for x in rx_list_str)
        return rx_list

    def getBarData(self):
        """Gets barometer calibration data. Returns as a 9 element list."""
        _bardata = self.port.send_command("BARDATA\n")
        _barometer = float(_bardata[0].split()[1])/1000.0
        _altitude  = float(_bardata[1].split()[1])
        _dewpoint  = float(_bardata[2].split()[2])
        _virt_temp = float(_bardata[3].split()[2])
        _c         = float(_bardata[4].split()[1])
        _r         = float(_bardata[5].split()[1])/1000.0
        _barcal    = float(_bardata[6].split()[1])/1000.0
        _gain      = float(_bardata[7].split()[1])
        _offset    = float(_bardata[8].split()[1])
        
        return (_barometer, _altitude, _dewpoint, _virt_temp,
                _c, _r, _barcal, _gain, _offset)
    
    def getFirmwareDate(self):
        """Return the firmware date as a string. """
        return self.port.send_command('VER\n')[0]
        
    def getFirmwareVersion(self):
        """Return the firmware version as a string."""
        return self.port.send_command('NVER\n')[0]
    
    def getStnInfo(self):
        """Return lat / lon, time zone, etc."""
        
        (stnlat, stnlon) = self._getEEPROM_value(0x0B, "<2h")
        stnlat /= 10.0
        stnlon /= 10.0
        man_or_auto = "MANUAL"     if self._getEEPROM_value(0x12)[0] else "AUTO"
        dst         = "ON"         if self._getEEPROM_value(0x13)[0] else "OFF"
        gmt_or_zone = "GMT_OFFSET" if self._getEEPROM_value(0x16)[0] else "ZONE_CODE"
        zone_code   = self._getEEPROM_value(0x11)[0]
        gmt_offset  = self._getEEPROM_value(0x14, "<h")[0] / 100.0
        
        return (stnlat, stnlon, man_or_auto, dst, gmt_or_zone, zone_code, gmt_offset)

    def getStnTransmitters(self):
        """ Get the types of transmitters on the eight channels."""

        transmitters = [ ]
        use_tx =           self._getEEPROM_value(0x17)[0]
        transmitter_data = self._getEEPROM_value(0x19, "16B")
        
        for transmitter_id in range(8):
            transmitter_type = Vantage.transmitter_type_dict[transmitter_data[transmitter_id * 2] & 0x0F]
            transmitter = {"transmitter_type": transmitter_type,
                           "listen": (use_tx >> transmitter_id) & 1 }
            if transmitter_type in ['temp', 'temp_hum']:
                # Extra temperature is origin 0.
                transmitter['temp'] = (transmitter_data[transmitter_id * 2 + 1] & 0xF) + 1
            if transmitter_type in ['hum', 'temp_hum']:
                # Extra humidity is origin 1.
                transmitter['hum'] = transmitter_data[transmitter_id * 2 + 1] >> 4
            transmitters.append(transmitter)
        return transmitters

    def getStnCalibration(self):
        """ Get the temperature/humidity/wind calibrations built into the console. """
        (inTemp, inTempComp, outTemp,
            extraTemp1, extraTemp2, extraTemp3, extraTemp4, extraTemp5, extraTemp6, extraTemp7,
            soilTemp1, soilTemp2, soilTemp3, soilTemp4, leafTemp1, leafTemp2, leafTemp3, leafTemp4,
            inHumid,
            outHumid, extraHumid1, extraHumid2, extraHumid3, extraHumid4, extraHumid5, extraHumid6, extraHumid7,
            wind) = self._getEEPROM_value(0x32, "<27bh")
        # inTempComp is 1's complement of inTemp.
        if inTemp + inTempComp != -1:
            syslog.syslog(syslog.LOG_ERR, "vantage: Inconsistent EEPROM calibration values")
            return None
        # Temperatures are in tenths of a degree F; Humidity in 1 percent.
        return {
            "inTemp": inTemp / 10,
            "outTemp": outTemp / 10,
            "extraTemp1": extraTemp1 / 10,
            "extraTemp2": extraTemp2 / 10,
            "extraTemp3": extraTemp3 / 10,
            "extraTemp4": extraTemp4 / 10,
            "extraTemp5": extraTemp5 / 10,
            "extraTemp6": extraTemp6 / 10,
            "extraTemp7": extraTemp7 / 10,
            "soilTemp1": soilTemp1 / 10,
            "soilTemp2": soilTemp2 / 10,
            "soilTemp3": soilTemp3 / 10,
            "soilTemp4": soilTemp4 / 10,
            "leafTemp1": leafTemp1 / 10,
            "leafTemp2": leafTemp2 / 10,
            "leafTemp3": leafTemp3 / 10,
            "leafTemp4": leafTemp4 / 10,
            "inHumid": inHumid,
            "outHumid": outHumid,
            "extraHumid1": extraHumid1,
            "extraHumid2": extraHumid2,
            "extraHumid3": extraHumid3,
            "extraHumid4": extraHumid4,
            "extraHumid5": extraHumid5,
            "extraHumid6": extraHumid6,
            "extraHumid7": extraHumid7,
            "wind": wind
            }
      
    def startLogger(self):
        self.port.send_command("START\n")
        
    def stopLogger(self):
        self.port.send_command('STOP\n')

    #===========================================================================
    #              Davis Vantage utility functions
    #===========================================================================

    @property
    def hardware_name(self):    
        if self.hardware_type == 16:
            return "VantagePro2"
        elif self.hardware_type == 17:
            return "VantageVue"
        else:
            raise weewx.UnsupportedFeature("Unknown hardware type %d" % self.hardware_type)

    @property
    def archive_interval(self):
        return self.archive_interval_
    
    def determine_hardware(self):
        # Determine the type of hardware:
        for count in xrange(self.max_tries):
            try:
                self.port.send_data("WRD" + chr(0x12) + chr(0x4d) + "\n")
                self.hardware_type = ord(self.port.read())
                syslog.syslog(syslog.LOG_DEBUG, "vantage: _setup; hardware type is %s" % self.hardware_type)
                # 16 = Pro, Pro2, 17 = Vue
                return self.hardware_type
            except weewx.WeeWxIOError:
                pass
            syslog.syslog(syslog.LOG_DEBUG, "vantage: determine_hardware; retry #%d" % (count,))

        syslog.syslog(syslog.LOG_ERR, "vantage: _setup; unable to read hardware type; raise WeeWxIOError")
        raise weewx.WeeWxIOError("Unable to read hardware type")

    def _setup(self):
        """Retrieve the EEPROM data block from a VP2 and use it to set various properties"""
        
        self.port.wakeup_console(max_tries=self.max_tries)
        self.hardware_type = self.determine_hardware()

        """Retrieve the EEPROM data block from a VP2 and use it to set various properties"""

        unit_bits              = self._getEEPROM_value(0x29)[0]
        setup_bits             = self._getEEPROM_value(0x2B)[0]
        self.rain_year_start   = self._getEEPROM_value(0x2C)[0]
        self.archive_interval_ = self._getEEPROM_value(0x2D)[0] * 60
        self.altitude          = self._getEEPROM_value(0x0F, "<h")[0]
        self.altitude_vt       = weewx.units.ValueTuple(self.altitude, "foot", "group_altitude") 

        barometer_unit_code   =  unit_bits & 0x03
        temperature_unit_code = (unit_bits & 0x0C) >> 2
        altitude_unit_code    = (unit_bits & 0x10) >> 4
        rain_unit_code        = (unit_bits & 0x20) >> 5
        wind_unit_code        = (unit_bits & 0xC0) >> 6

        self.wind_cup_type    = (setup_bits & 0x08) >> 3
        self.rain_bucket_type = (setup_bits & 0x30) >> 4

        self.barometer_unit   = Vantage.barometer_unit_dict[barometer_unit_code]
        self.temperature_unit = Vantage.temperature_unit_dict[temperature_unit_code]
        self.altitude_unit    = Vantage.altitude_unit_dict[altitude_unit_code]
        self.rain_unit        = Vantage.rain_unit_dict[rain_unit_code]
        self.wind_unit        = Vantage.wind_unit_dict[wind_unit_code]
        self.wind_cup_size    = Vantage.wind_cup_dict[self.wind_cup_type]
        self.rain_bucket_size = Vantage.rain_bucket_dict[self.rain_bucket_type]
        
        # Adjust the translation maps to reflect the rain bucket size:
        if self.rain_bucket_type == 1:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _bucket_1
            _loop_map['rainRate'] = _bucket_1_None
        elif self.rain_bucket_type == 2:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _bucket_2
            _loop_map['rainRate'] = _bucket_2_None
        else:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _val100
            _loop_map['rainRate'] = _big_val100

        # Try to guess the ISS ID for gauging reception strength.
        if self.iss_id is None:
            stations = self.getStnTransmitters()
            # Wind retransmitter is best candidate.
            for station_id in range(0, 8):
                if stations[station_id]['transmitter_type'] == 'wind':
                    self.iss_id = station_id + 1  # Origin 1.
                    break
            else:
                # ISS is next best candidate.
                for station_id in range(0, 8):
                    if stations[station_id]['transmitter_type'] == 'iss':
                        self.iss_id = station_id + 1  # Origin 1.
                        break
                else:
                    # On Vue, can use VP2 ISS, which reports as "rain"
                    for station_id in range(0, 8):
                        if stations[station_id]['transmitter_type'] == 'rain':
                            self.iss_id = station_id + 1  # Origin 1.
                            break
                    else:
                        self.iss_id = 1  # Pick a reasonable default.

    def _getEEPROM_value(self, offset, v_format="B"):
        """Return a list of values from the EEPROM starting at a specified offset, using a specified format"""
        
        nbytes = struct.calcsize(v_format)
        # Don't bother waking up the console for the first try. It's probably
        # already awake from opening the port. However, if we fail, then do a
        # wakeup.
        firsttime = True
        
        command = "EEBRD %X %X\n" % (offset, nbytes)
        for unused_count in xrange(self.max_tries):
            try:
                if not firsttime:
                    self.port.wakeup_console(max_tries=self.max_tries)
                    firsttime = False
                self.port.send_data(command)
                _buffer = self.port.get_data_with_crc16(nbytes + 2, max_tries=1)
                _value = struct.unpack(v_format, _buffer[:-2])
                return _value
            except weewx.WeeWxIOError:
                continue
        
        syslog.syslog(syslog.LOG_ERR, "vantage: Max retries exceeded while getting EEPROM data at address 0x%X" % offset)
        raise weewx.RetriesExceeded("While getting EEPROM data value at address 0x%X" % offset)
        
    @staticmethod
    def _port_factory(vp_dict):
        """Produce a serial or ethernet port object"""
        
        timeout           = float(vp_dict.get('timeout', 4.0))
        wait_before_retry = float(vp_dict.get('wait_before_retry', 1.2))
        command_delay     = float(vp_dict.get('command_delay', 0.5))
        
        # Get the connection type. If it is not specified, assume 'serial':
        connection_type = vp_dict.get('type', 'serial').lower()

        if connection_type == "serial":
            port = vp_dict['port']
            baudrate = int(vp_dict.get('baudrate', 19200))
            return SerialWrapper(port, baudrate, timeout,
                                 wait_before_retry, command_delay)
        elif connection_type == "ethernet":
            hostname = vp_dict['host']
            tcp_port = int(vp_dict.get('tcp_port', 22222))
            tcp_send_delay = float(vp_dict.get('tcp_send_delay', 0.5))
            return EthernetWrapper(hostname, tcp_port, timeout, tcp_send_delay,
                                   wait_before_retry, command_delay)
        raise weewx.UnsupportedFeature(vp_dict['type'])

    def _unpackLoopPacket(self, raw_loop_string):
        """Decode a raw Davis LOOP packet, returning the results as a dictionary in physical units.
        
        raw_loop_string: The loop packet data buffer, passed in as a string. 
        
        returns:
        
        A dictionary. The key will be an observation type, the value will be
        the observation in physical units."""
    
        # Unpack the data, using the compiled stuct.Struct string 'loop_fmt'
        data_tuple = loop_fmt.unpack(raw_loop_string)

        # Put the results in a dictionary. The values will not be in physical units yet,
        # but rather using the raw values from the console.
        raw_loop_packet = dict(zip(loop_types, data_tuple))
    
        # Detect the kind of LOOP packet. Type 'A' has the character 'P' in this
        # position. Type 'B' contains the 3-hour barometer trend in this position.
        if raw_loop_packet['loop_type'] == ord('P'):
            raw_loop_packet['trend'] = None
            raw_loop_packet['loop_type'] = 'A'
        else:
            raw_loop_packet['trend'] = raw_loop_packet['loop_type']
            raw_loop_packet['loop_type'] = 'B'
    
        loop_packet = {'dateTime': int(time.time() + 0.5),
                       'usUnits': weewx.US}
        
        for _type in raw_loop_packet:
            # Get the mapping function for this type:
            func = _loop_map.get(_type)
            # It it exists, apply it:
            if func:
                # Call the function, with the value as an argument, storing the result:
                loop_packet[_type] = func(raw_loop_packet[_type])

        # Wind direction is undefined if wind speed is zero:
        if loop_packet['windSpeed'] == 0:
            loop_packet['windDir'] = None
            
        # Adjust sunrise and sunset:
        start_of_day = weeutil.weeutil.startOfDay(loop_packet['dateTime'])
        loop_packet['sunrise'] += start_of_day
        loop_packet['sunset']  += start_of_day
        
        # Because the Davis stations do not offer bucket tips in LOOP data, we
        # must calculate it by looking for changes in rain totals. This won't
        # work for the very first rain packet.
        if self.save_monthRain is None:
            delta = None
        else:
            delta = loop_packet['monthRain'] - self.save_monthRain
            # If the difference is negative, we're at the beginning of a month.
            if delta < 0: delta = None
        loop_packet['rain'] = delta
        self.save_monthRain = loop_packet['monthRain']

        return loop_packet
    
    def _unpackArchivePacket(self, raw_archive_string):
        """Decode a Davis archive packet, returning the results as a dictionary.
        
        raw_archive_string: The archive packet data buffer, passed in as a string. This will be unpacked and 
        the results placed a dictionary"""
    
        # Figure out the packet type:
        packet_type = ord(raw_archive_string[42])
        
        if packet_type == 0xff:
            # Rev A packet type:
            archive_format = rec_fmt_A
            dataTypes = rec_types_A
        elif packet_type == 0x00:
            # Rev B packet type:
            archive_format = rec_fmt_B
            dataTypes = rec_types_B
        else:
            raise weewx.UnknownArchiveType("Unknown archive type = 0x%x" % (packet_type,)) 
            
        data_tuple = archive_format.unpack(raw_archive_string)
        
        raw_archive_packet = dict(zip(dataTypes, data_tuple))
        
        archive_packet = {'dateTime': _archive_datetime(raw_archive_packet['date_stamp'], raw_archive_packet['time_stamp']),
                          'usUnits': weewx.US}
        
        for _type in raw_archive_packet:
            # Get the mapping function for this type:
            func = _archive_map.get(_type)
            # It it exists, apply it:
            if func:
                # Call the function, with the value as an argument, storing the result:
                archive_packet[_type] = func(raw_archive_packet[_type])
                
        # Wind direction is undefined if wind speed is zero:
        if archive_packet['windSpeed'] == 0:
            archive_packet['windDir'] = None
        
        # Divide archive interval by 60 to keep consistent with wview
        archive_packet['interval']   = int(self.archive_interval / 60) 
        archive_packet['rxCheckPercent'] = _rxcheck(self.model_type, archive_packet['interval'], 
                                                    self.iss_id, raw_archive_packet['number_of_wind_samples'])
        return archive_packet
    
#===============================================================================
#                                 LOOP packet
#===============================================================================

# A list of all the types held in a Vantage LOOP packet in their native order.
loop_format = [('loop',              '3s'), ('loop_type',          'b'), ('packet_type',        'B'),
               ('next_record',        'H'), ('barometer',          'H'), ('inTemp',             'h'),
               ('inHumidity',         'B'), ('outTemp',            'h'), ('windSpeed',          'B'),
               ('windSpeed10',        'B'), ('windDir',            'H'), ('extraTemp1',         'B'),
               ('extraTemp2',         'B'), ('extraTemp3',         'B'), ('extraTemp4',         'B'),
               ('extraTemp5',         'B'), ('extraTemp6',         'B'), ('extraTemp7',         'B'), 
               ('soilTemp1',          'B'), ('soilTemp2',          'B'), ('soilTemp3',          'B'),
               ('soilTemp4',          'B'), ('leafTemp1',          'B'), ('leafTemp2',          'B'),
               ('leafTemp3',          'B'), ('leafTemp4',          'B'), ('outHumidity',        'B'),
               ('extraHumid1',        'B'), ('extraHumid2',        'B'), ('extraHumid3',        'B'),
               ('extraHumid4',        'B'), ('extraHumid5',        'B'), ('extraHumid6',        'B'),
               ('extraHumid7',        'B'), ('rainRate',           'H'), ('UV',                 'B'),
               ('radiation',          'H'), ('stormRain',          'H'), ('stormStart',         'H'),
               ('dayRain',            'H'), ('monthRain',          'H'), ('yearRain',           'H'),
               ('dayET',              'H'), ('monthET',            'H'), ('yearET',             'H'),
               ('soilMoist1',         'B'), ('soilMoist2',         'B'), ('soilMoist3',         'B'),
               ('soilMoist4',         'B'), ('leafWet1',           'B'), ('leafWet2',           'B'),
               ('leafWet3',           'B'), ('leafWet4',           'B'), ('insideAlarm',        'B'),
               ('rainAlarm',          'B'), ('outsideAlarm1',      'B'), ('outsideAlarm2',      'B'),
               ('extraAlarm1',        'B'), ('extraAlarm2',        'B'), ('extraAlarm3',        'B'),
               ('extraAlarm4',        'B'), ('extraAlarm5',        'B'), ('extraAlarm6',        'B'),
               ('extraAlarm7',        'B'), ('extraAlarm8',        'B'), ('soilLeafAlarm1',     'B'),
               ('soilLeafAlarm2',     'B'), ('soilLeafAlarm3',     'B'), ('soilLeafAlarm4',     'B'),
               ('txBatteryStatus',    'B'), ('consBatteryVoltage', 'H'), ('forecastIcon',       'B'),
               ('forecastRule',       'B'), ('sunrise',            'H'), ('sunset',             'H')]

# Extract the types and struct.Struct formats for the LOOP packets:
loop_types, fmt = zip(*loop_format)
loop_fmt = struct.Struct('<' + ''.join(fmt))

#===============================================================================
#                              archive packet
#===============================================================================

rec_format_A =[('date_stamp',              'H'), ('time_stamp',    'H'), ('outTemp',    'h'),
               ('highOutTemp',             'h'), ('lowOutTemp',    'h'), ('rain',       'H'),
               ('rainRate',                'H'), ('barometer',     'H'), ('radiation',  'H'),
               ('number_of_wind_samples',  'H'), ('inTemp',        'h'), ('inHumidity', 'B'),
               ('outHumidity',             'B'), ('windSpeed',     'B'), ('windGust',   'B'),
               ('windGustDir',             'B'), ('windDir',       'B'), ('UV',         'B'),
               ('ET',                      'B'), ('invalid_data',  'B'), ('soilMoist1', 'B'),
               ('soilMoist2',              'B'), ('soilMoist3',    'B'), ('soilMoist4', 'B'),
               ('soilTemp1',               'B'), ('soilTemp2',     'B'), ('soilTemp3',  'B'),
               ('soilTemp4',               'B'), ('leafWet1',      'B'), ('leafWet2',   'B'),
               ('leafWet3',                'B'), ('leafWet4',      'B'), ('extraTemp1', 'B'),
               ('extraTemp2',              'B'), ('extraHumid1',   'B'), ('extraHumid2','B'),
               ('readClosed',              'H'), ('readOpened',    'H'), ('unused',     'B')]

rec_format_B = [('date_stamp',             'H'), ('time_stamp',    'H'), ('outTemp',    'h'),
                ('highOutTemp',            'h'), ('lowOutTemp',    'h'), ('rain',       'H'),
                ('rainRate',               'H'), ('barometer',     'H'), ('radiation',  'H'),
                ('number_of_wind_samples', 'H'), ('inTemp',        'h'), ('inHumidity', 'B'),
                ('outHumidity',            'B'), ('windSpeed',     'B'), ('windGust',   'B'),
                ('windGustDir',            'B'), ('windDir',       'B'), ('UV',         'B'),
                ('ET',                     'B'), ('highRadiation', 'H'), ('highUV',     'B'),
                ('forecastRule',           'B'), ('leafTemp1',     'B'), ('leafTemp2',  'B'),
                ('leafWet1',               'B'), ('leafWet2',      'B'), ('soilTemp1',  'B'),
                ('soilTemp2',              'B'), ('soilTemp3',     'B'), ('soilTemp4',  'B'),
                ('download_record_type',   'B'), ('extraHumid1',   'B'), ('extraHumid2','B'),
                ('extraTemp1',             'B'), ('extraTemp2',    'B'), ('extraTemp3', 'B'),
                ('soilMoist1',             'B'), ('soilMoist2',    'B'), ('soilMoist3', 'B'),
                ('soilMoist4',             'B')]

# Extract the types and struct.Struct formats for the two types of archive packets:
rec_types_A, fmt_A = zip(*rec_format_A)
rec_types_B, fmt_B = zip(*rec_format_B)
rec_fmt_A = struct.Struct('<' + ''.join(fmt_A))
rec_fmt_B = struct.Struct('<' + ''.join(fmt_B))

def _rxcheck(model_type, interval, iss_id, number_of_wind_samples):
    """Gives an estimate of the fraction of packets received.
    
    Ref: Vantage Serial Protocol doc, V2.1.0, released 25-Jan-05; p42"""
    # The formula for the expected # of packets varies with model number.
    if model_type == 1:
        _expected_packets = float(interval * 60) / ( 2.5 + (iss_id-1) / 16.0) -\
                            float(interval * 60) / (50.0 + (iss_id-1) * 1.25)
    elif model_type == 2:
        _expected_packets = 960.0 * interval / float(41 + iss_id - 1)
    else:
        return None
    _frac = number_of_wind_samples * 100.0 / _expected_packets
    if _frac > 100.0:
        _frac = 100.0
    return _frac

#===============================================================================
#                      Decoding routines
#===============================================================================

def _archive_datetime(datestamp, timestamp):
    """Returns the epoch time of the archive packet."""
    try:
        # Construct a time tuple from Davis time. Unfortunately, as timestamps come
        # off the Vantage logger, there is no way of telling whether or not DST is
        # in effect. So, have the operating system guess by using a '-1' in the last
        # position of the time tuple. It's the best we can do...
        time_tuple = ((0xfe00 & datestamp) >> 9,    # year
                      (0x01e0 & datestamp) >> 5,    # month
                      (0x001f & datestamp),         # day
                      timestamp // 100,             # hour
                      timestamp % 100,              # minute
                      0,                            # second
                      0, 0, -1)                     # have OS guess DST
        # Convert to epoch time:
        ts = int(time.mktime(time_tuple))
    except (OverflowError, ValueError, TypeError):
        ts = None
    return ts
    
def _loop_date(v):
    """Returns the epoch time stamp of a time encoded in the LOOP packet, 
    which, for some reason, uses a different encoding scheme than the archive packet.
    Also, the Davis documentation isn't clear whether "bit 0" refers to the least-significant
    bit, or the most-significant bit. I'm assuming the former, which is the usual
    in little-endian machines."""
    if v == 0xffff:
        return None
    time_tuple = ((0x007f & v) + 2000,  # year
                  (0xf000 & v) >> 12,   # month
                  (0x0f80 & v) >>  7,   # day
                  0, 0, 0,              # h, m, s
                  0, 0, -1)
    # Convert to epoch time:
    try:
        ts = int(time.mktime(time_tuple))
    except (OverflowError, ValueError):
        ts = None
    return ts
    
def _stime(v):
    h = v / 100
    m = v % 100
    # Return seconds since midnight
    return 3600 * h + 60 * m

def _big_val(v):
    return float(v) if v != 0x7fff else None

def _big_val10(v):
    return float(v) / 10.0 if v != 0x7fff else None

def _big_val100(v):
    return float(v) / 100.0 if v != 0xffff else None

def _val100(v):
    return float(v) / 100.0

def _val1000(v):
    return float(v) / 1000.0

def _val1000Zero(v):
    return float(v) / 1000.0 if v != 0 else None

def _little_val(v):
    return float(v) if v != 0x00ff else None

def _little_val10(v):
    return float(v) / 10.0 if v != 0x00ff else None
    
def _little_temp(v):
    return float(v - 90) if v != 0x00ff else None

def _null(v):
    return v

def _null_float(v):
    return float(v)

def _null_int(v):
    return int(v)

def _windDir(v):
    return float(v) * 22.5 if v != 0x00ff else None

# Rain bucket type "1", a 0.2 mm bucket
def _bucket_1(v):
    return float(v) * 0.00787401575

def _bucket_1_None(v):
    return float(v) * 0.00787401575 if v != 0xffff else None

# Rain bucket type "2", a 0.1 mm bucket
def _bucket_2(v):
    return float(v) * 0.00393700787

def _bucket_2_None(v):
    return float(v) * 0.00393700787 if v != 0xffff else None

# This dictionary maps a type key to a function. The function should be able to
# decode a sensor value held in the LOOP packet in the internal, Davis form into US
# units and return it.
_loop_map = {'barometer'       : _val1000Zero,
             'inTemp'          : _big_val10,
             'inHumidity'      : _little_val,
             'outTemp'         : _big_val10,
             'windSpeed'       : _little_val,
             'windSpeed10'     : _little_val,
             'windDir'         : _big_val,
             'extraTemp1'      : _little_temp,
             'extraTemp2'      : _little_temp,
             'extraTemp3'      : _little_temp,
             'extraTemp4'      : _little_temp,
             'extraTemp5'      : _little_temp,
             'extraTemp6'      : _little_temp,
             'extraTemp7'      : _little_temp,
             'soilTemp1'       : _little_temp,
             'soilTemp2'       : _little_temp,
             'soilTemp3'       : _little_temp,
             'soilTemp4'       : _little_temp,
             'leafTemp1'       : _little_temp,
             'leafTemp2'       : _little_temp,
             'leafTemp3'       : _little_temp,
             'leafTemp4'       : _little_temp,
             'outHumidity'     : _little_val,
             'extraHumid1'     : _little_val,
             'extraHumid2'     : _little_val,
             'extraHumid3'     : _little_val,
             'extraHumid4'     : _little_val,
             'extraHumid5'     : _little_val,
             'extraHumid6'     : _little_val,
             'extraHumid7'     : _little_val,
             'rainRate'        : _big_val100,
             'UV'              : _little_val10,
             'radiation'       : _big_val,
             'stormRain'       : _val100,
             'stormStart'      : _loop_date,
             'dayRain'         : _val100,
             'monthRain'       : _val100,
             'yearRain'        : _val100,
             'dayET'           : _val1000,
             'monthET'         : _val100,
             'yearET'          : _val100,
             'soilMoist1'      : _little_val,
             'soilMoist2'      : _little_val,
             'soilMoist3'      : _little_val,
             'soilMoist4'      : _little_val,
             'leafWet1'        : _little_val,
             'leafWet2'        : _little_val,
             'leafWet3'        : _little_val,
             'leafWet4'        : _little_val,
             'insideAlarm'     : _null,
             'rainAlarm'       : _null,
             'outsideAlarm1'   : _null,
             'outsideAlarm2'   : _null,
             'extraAlarm1'     : _null,
             'extraAlarm2'     : _null,
             'extraAlarm3'     : _null,
             'extraAlarm4'     : _null,
             'extraAlarm5'     : _null,
             'extraAlarm6'     : _null,
             'extraAlarm7'     : _null,
             'extraAlarm8'     : _null,
             'soilLeafAlarm1'  : _null,
             'soilLeafAlarm2'  : _null,
             'soilLeafAlarm3'  : _null,
             'soilLeafAlarm4'  : _null,
             'txBatteryStatus' : _null_int,
             'consBatteryVoltage'  : lambda v : float((v * 300) >> 9) / 100.0,
             'forecastIcon'    : _null,
             'forecastRule'    : _null,
             'sunrise'         : _stime,
             'sunset'          : _stime}

# This dictionary maps a type key to a function. The function should be able to
# decode a sensor value held in the archive packet in the internal, Davis form into US
# units and return it.
_archive_map = {'barometer'      : _val1000Zero,
                'inTemp'         : _big_val10,
                'outTemp'        : _big_val10,
                'highOutTemp'    : lambda v : float(v / 10.0) if v != -32768 else None,
                'lowOutTemp'     : _big_val10,
                'inHumidity'     : _little_val,
                'outHumidity'    : _little_val,
                'windSpeed'      : _little_val,
                'windDir'        : _windDir,
                'windGust'       : _null_float,
                'windGustDir'    : _windDir,
                'rain'           : _val100,
                'rainRate'       : _val100,
                'ET'             : _val1000,
                'radiation'      : _big_val,
                'highRadiation'  : _big_val,
                'UV'             : _little_val10,
                'highUV'         : _little_val10,
                'extraTemp1'     : _little_temp,
                'extraTemp2'     : _little_temp,
                'extraTemp3'     : _little_temp,
                'soilTemp1'      : _little_temp,
                'soilTemp2'      : _little_temp,
                'soilTemp3'      : _little_temp,
                'soilTemp4'      : _little_temp,
                'leafTemp1'      : _little_temp,
                'leafTemp2'      : _little_temp,
                'extraHumid1'    : _little_val,
                'extraHumid2'    : _little_val,
                'soilMoist1'     : _little_val,
                'soilMoist2'     : _little_val,
                'soilMoist3'     : _little_val,
                'soilMoist4'     : _little_val,
                'leafWet1'       : _little_val,
                'leafWet2'       : _little_val,
                'leafWet3'       : _little_val,
                'leafWet4'       : _little_val,
                'forecastRule'   : _null,
                'readClosed'     : _null,
                'readOpened'     : _null}

#===============================================================================
#                      class VantageService
#===============================================================================

# This class uses multiple inheritance:

class VantageService(Vantage, weewx.engine.StdService):
    """Weewx service for the Vantage weather stations."""
    
    def __init__(self, engine, config_dict):
        Vantage.__init__(self, **config_dict[DRIVER_NAME])
        weewx.engine.StdService.__init__(self, engine, config_dict)

        self.bind(weewx.STARTUP, self.startup)        
        self.bind(weewx.NEW_LOOP_PACKET,    self.new_loop_packet)
        self.bind(weewx.END_ARCHIVE_PERIOD, self.end_archive_period)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def startup(self, event):  # @UnusedVariable
        self.max_loop_gust = 0.0
        self.max_loop_gustdir = None
        self.loop_data = {'txBatteryStatus': None,
                          'consBatteryVoltage': None}
        
    def closePort(self):
        # Now close my superclass's port:
        Vantage.closePort(self)

    def new_loop_packet(self, event):
        """Calculate the max gust seen since the last archive record."""
        
        # Calculate the max gust seen since the start of this archive record
        # and put it in the packet.
        windSpeed = event.packet.get('windSpeed')
        windDir   = event.packet.get('windDir')
        if windSpeed is not None and windSpeed > self.max_loop_gust:
            self.max_loop_gust = windSpeed
            self.max_loop_gustdir = windDir
        event.packet['windGust'] = self.max_loop_gust
        event.packet['windGustDir'] = self.max_loop_gustdir
        
        # Save the battery statuses:
        for k in self.loop_data:
            self.loop_data[k] = event.packet[k]
        
    def end_archive_period(self, event):  # @UnusedVariable
        """Zero out the max gust seen since the start of the record"""
        self.max_loop_gust = 0.0
        self.max_loop_gustdir = None
        
    def new_archive_record(self, event):
        """Add the battery status to the archive record."""
        # Add the last battery status:
        event.record.update(self.loop_data)


#===============================================================================
#                      Class VantageConfigurator
#===============================================================================

class VantageConfigurator(weewx.drivers.AbstractConfigurator):
    @property
    def description(self):
        return "Configures the Davis Vantage weather station."

    @property
    def usage(self):
        return """%prog [config_file] [--help] [--info] [--clear]
    [--set-interval=SECONDS] [--set-altitude=FEET] [--set-barometer=inHg] 
    [--set-bucket=CODE] [--set-rain-year-start=MM] 
    [--set-offset=VARIABLE,OFFSET]
    [--set-transmitter-type=CHANNEL,TYPE,TEMP,HUM]
    [--set-time] [--set-dst=[AUTO|ON|OFF]]
    [--set-tz-code=TZCODE] [--set-tz-offset=HHMM]
    [--set-lamp=[ON|OFF]] [--dump] [--logger_summary=FILE]
    [--start | --stop]"""

    def add_options(self, parser):
        super(VantageConfigurator, self).add_options(parser)
        parser.add_option("--info", action="store_true", dest="info",
                          help="To print configuration, reception, and barometer calibration information about your weather station.")
        parser.add_option("--clear", action="store_true", dest="clear",
                          help="To clear the memory of your weather station.")
        parser.add_option("--set-interval", type=int, dest="set_interval",
                          metavar="SECONDS",
                          help="Sets the archive interval to the specified number of seconds. Valid values are 60, 300, 600, 900, 1800, 3600, or 7200.")
        parser.add_option("--set-altitude", type=float, dest="set_altitude",
                          metavar="FEET",
                          help="Sets the altitude of the station to the specified number of feet.") 
        parser.add_option("--set-barometer", type=float, dest="set_barometer",
                          metavar="inHg",
                          help="Sets the barometer reading of the station to a known correct value in inches of mercury. Specify 0 (zero) to have the console pick a sensible value.")
        parser.add_option("--set-bucket", type=int, dest="set_bucket",
                          metavar="CODE",
                          help="Set the type of rain bucket. Specify '0' for 0.01 inches; '1' for 0.2 MM; '2' for 0.1 MM")
        parser.add_option("--set-rain-year-start", type=int,
                          dest="set_rain_year_start", metavar="MM",
                          help="Set the rain year start (1=Jan, 2=Feb, etc.).")
        parser.add_option("--set-offset", type=str,
                          dest="set_offset", metavar="VARIABLE,OFFSET",
                          help="Set the onboard offset for VARIABLE inTemp, outTemp, extraTemp[1-7], inHumid, outHumid, extraHumid[1-7], soilTemp[1-4], leafTemp[1-4], windDir) to OFFSET (Fahrenheit, %, degrees)")
        parser.add_option("--set-transmitter-type", type=str,
                          dest="set_transmitter_type",
                          metavar="CHANNEL,TYPE,TEMP,HUM",
                          help="Set the transmitter type for CHANNEL (1-8), TYPE (0=iss, 1=temp, 2=hum, 3=temp_hum, 4=wind, 5=rain, 6=leaf, 7=soil, 8=leaf_soil, 9=sensorlink, 10=none), as extra TEMP station and extra HUM station (both 1-7, if applicable)")
        parser.add_option("--set-time", action="store_true", dest="set_time",
                          help="Set the onboard clock to the current time.")
        parser.add_option("--set-dst", dest="set_dst",
                          metavar="AUTO|ON|OFF",
                          help="Set DST to 'ON', 'OFF', or 'AUTO'")
        parser.add_option("--set-tz-code", type=int, dest="set_tz_code",
                          metavar="TZCODE",
                          help="Set timezone code to TZCODE. See your Vantage manual for valid codes.")
        parser.add_option("--set-tz-offset", dest="set_tz_offset",
                          help="Set timezone offset to HHMM. E.g. '-0800' for U.S. Pacific Time.", metavar="HHMM")
        parser.add_option("--set-lamp", dest="set_lamp",
                          metavar="ON|OFF",
                          help="Turn the console lamp 'ON' or 'OFF'.")
        parser.add_option("--start", action="store_true",
                          help="Start the logger.")
        parser.add_option("--stop", action="store_true",
                          help="Stop the logger.")
        parser.add_option("--dump", action="store_true",
                          help="Dump all data to the archive. NB: This may result in many duplicate primary key errors.")
        parser.add_option("--logger-summary", type="string",
                          dest="logger_summary", metavar="FILE",
                          help="Save diagnostic summary to FILE (for debugging the logger).")

    def do_options(self, options, parser, config_dict, prompt):  # @UnusedVariable        
        if options.start and options.stop:
            parser.error("Cannot specify both --start and --stop")
        if options.set_tz_code and options.set_tz_offset:
            parser.error("Cannot specify both --set-tz-code and --set-tz-offset")

        station = Vantage(**config_dict[DRIVER_NAME])
        if options.info:
            self.show_info(station)
        if options.clear:
            self.clear_memory(station)
        if options.set_interval is not None:
            self.set_interval(station, options.set_interval)
        if options.set_altitude is not None:
            self.set_altitude(station, options.set_altitude)
        if options.set_barometer is not None:
            self.set_barometer(station, options.set_barometer)
        if options.set_bucket is not None:
            self.set_bucket(station, options.set_bucket)
        if options.set_rain_year_start is not None:
            self.set_rain_year_start(station, options.set_rain_year_start)
        if options.set_offset is not None:
            self.set_offset(station, options.set_offset)
        if options.set_transmitter_type is not None:
            self.set_transmitter_type(station, options.set_transmitter_type)
        if options.set_time:
            self.set_time(station)
        if options.set_dst:
            self.set_dst(station, options.set_dst)
        if options.set_tz_code:
            self.set_tz_code(station, options.set_tz_code)
        if options.set_tz_offset:
            self.set_tz_offset(station, options.set_tz_offset)
        if options.set_lamp:
            self.set_lamp(station, options.set_lamp)
        if options.start:
            self.start_logger(station)
        if options.stop:
            self.stop_logger(station)
        if options.dump:
            self.dump_logger(station, config_dict)
        if options.logger_summary:
            self.logger_summary(station, options.logger_summary)

    @staticmethod           
    def show_info(station, dest=sys.stdout):
        """Query the configuration of the Vantage, printing out status
        information"""

        print "Querying..."
        try:
            _firmware_date = station.getFirmwareDate()
        except Exception:
            _firmware_date = "<Unavailable>"
        try:
            _firmware_version = station.getFirmwareVersion()
        except Exception:
            _firmware_version = '<Unavailable>'
    
        console_time = station.getConsoleTime()
        altitude_converted = weewx.units.convert(station.altitude_vt, station.altitude_unit)[0]
    
        print >> dest, """Davis Vantage EEPROM settings:
    
    CONSOLE TYPE:                   %s
    
    CONSOLE FIRMWARE:
      Date:                         %s
      Version:                      %s
    
    CONSOLE SETTINGS:
      Archive interval:             %d (seconds)
      Altitude:                     %d (%s)
      Wind cup type:                %s
      Rain bucket type:             %s
      Rain year start:              %d
      Onboard time:                 %s
      
    CONSOLE DISPLAY UNITS:
      Barometer:                    %s
      Temperature:                  %s
      Rain:                         %s
      Wind:                         %s
      """ % (station.hardware_name, _firmware_date, _firmware_version,
             station.archive_interval, altitude_converted, station.altitude_unit,
             station.wind_cup_size, station.rain_bucket_size,
             station.rain_year_start, console_time,
             station.barometer_unit, station.temperature_unit,
             station.rain_unit, station.wind_unit)
        try:
            (stnlat, stnlon, man_or_auto, dst, gmt_or_zone, zone_code, gmt_offset) = station.getStnInfo()
            if man_or_auto == 'AUTO':
                dst = 'N/A'
            if gmt_or_zone == 'ZONE_CODE':
                gmt_offset_str = 'N/A'
            else:
                gmt_offset_str = "%+.1f hours" % gmt_offset
                zone_code = 'N/A'
            print >> dest, """    CONSOLE STATION INFO:
      Latitude (onboard):           %+0.1f
      Longitude (onboard):          %+0.1f
      Use manual or auto DST?       %s
      DST setting:                  %s
      Use GMT offset or zone code?  %s
      Time zone code:               %s
      GMT offset:                   %s
        """ % (stnlat, stnlon, man_or_auto, dst, gmt_or_zone, zone_code, gmt_offset_str)
        except:
            pass
    
        # Add transmitter types for each channel, if we can:
        transmitter_list = None
        try:
            transmitter_list = station.getStnTransmitters()
            print >> dest, "    TRANSMITTERS: "
            for transmitter_id in range(0, 8):
                comment = ""
                transmitter_type = transmitter_list[transmitter_id]["transmitter_type"]
                if transmitter_type == 'temp_hum':
                    comment = "(as extra temperature %d and extra humidity %d)" % \
                        (transmitter_list[transmitter_id]["temp"], transmitter_list[transmitter_id]["hum"])
                elif transmitter_type == 'temp':
                    comment = "(as extra temperature %d)" % transmitter_list[transmitter_id]["temp"]
                elif transmitter_type == 'hum':
                    comment = "(as extra humidity %d)" % transmitter_list[transmitter_id]["hum"]
                elif transmitter_type == 'none':
                    transmitter_type = "(N/A)"
                print >> dest, "      Channel %d:                    %s %s" % (transmitter_id + 1, transmitter_type, comment)
            print >> dest, ""
        except:
            pass
    
        # Add reception statistics if we can:
        try:
            _rx_list = station.getRX()
            print >> dest, """    RECEPTION STATS:
      Total packets received:       %d
      Total packets missed:         %d
      Number of resynchronizations: %d
      Longest good stretch:         %d
      Number of CRC errors:         %d
      """ % _rx_list
        except:
            pass

        # Add barometer calibration data if we can.
        try:
            _bar_list = station.getBarData()
            print >> dest, """    BAROMETER CALIBRATION DATA:
      Current barometer reading:    %.3f inHg
      Altitude:                     %.0f feet
      Dew point:                    %.0f F
      Virtual temperature:          %.0f F
      Humidity correction factor:   %.0f
      Correction ratio:             %.3f
      Correction constant:          %+.3f inHg
      Gain:                         %.3f
      Offset:                       %.3f
      """ % _bar_list
        except:
            pass

        # Add temperature/humidity/wind calibration if we can.
        try:
            calibration_dict = station.getStnCalibration()
            print >> dest, """    OFFSETS:
      Wind direction:               %(wind)+.0f deg
      Inside Temperature:           %(inTemp)+.1f F
      Inside Humidity:              %(inHumid)+.0f%%
      Outside Temperature:          %(outTemp)+.1f F
      Outside Humidity:             %(outHumid)+.0f%%""" % calibration_dict
            if transmitter_list is not None:
                # Only print the calibrations for channels that we are
                # listening to.
                for extraTemp in range(1, 8):
                    for t_id in range(0, 8):
                        t_type = transmitter_list[t_id]["transmitter_type"]
                        if t_type in ['temp', 'temp_hum'] and \
                                extraTemp == transmitter_list[t_id]["temp"]:
                            print >> dest, "      Extra Temperature %d:          %+.1f F" % (extraTemp, calibration_dict["extraTemp%d" % extraTemp])
                for extraHumid in range(1, 8):
                    for t_id in range(0, 8):
                        t_type = transmitter_list[t_id]["transmitter_type"]
                        if t_type in ['hum', 'temp_hum'] and \
                                extraHumid == transmitter_list[t_id]["hum"]:
                            print >> dest, "      Extra Humidity %d:             %+.1f F" % (extraHumid, calibration_dict["extraHumid%d" % extraHumid])
                for t_id in range(0, 8):
                    t_type = transmitter_list[t_id]["transmitter_type"]
                    if t_type in ['soil', 'leaf_soil']:
                        for soil in range(1, 5):
                            print >> dest, "      Soil Temperature %d:           %+.1f F" % (soil, calibration_dict["soilTemp%d" % soil])
                for t_id in range(0, 8):
                    t_type = transmitter_list[t_id]["transmitter_type"]
                    if t_type in ['leaf', 'leaf_soil']:
                        for leaf in range(1, 5):
                            print >> dest, "      Leaf Temperature %d:           %+.1f F" % (leaf, calibration_dict["leafTemp%d" % leaf])
            print >> dest, ""
        except:
            raise

    @staticmethod
    def set_interval(station, new_interval_seconds):
        """Set the console archive interval."""
    
        print "Old archive interval is %d seconds, new one will be %d seconds." % (station.archive_interval, new_interval_seconds)
        if station.archive_interval == new_interval_seconds:
            print "Old and new archive intervals are the same. Nothing done."
        else:
            ans = None
            while ans not in ['y', 'n']:
                print "Proceeding will change the archive interval as well as erase all old archive records."
                ans = raw_input("Are you sure you want to proceed (y/n)? ")
                if ans == 'y':
                    try:
                        station.setArchiveInterval(new_interval_seconds)
                    except StandardError, e:
                        print >> sys.stderr, "Unable to set new archive interval. Reason:\n\t****", e
                    else:
                        print "Archive interval now set to %d seconds." % (station.archive_interval,)
                        # The Davis documentation implies that the log is
                        # cleared after changing the archive interval, but that
                        # doesn't seem to be the case. Clear it explicitly:
                        station.clearLog()
                        print "Archive records cleared."
                elif ans == 'n':
                    print "Nothing done."

    @staticmethod    
    def set_altitude(station, altitude_ft):
        """Set the console station altitude"""
        # Hit the console to get the current barometer calibration data:
        _bardata = station.getBarData()

        ans = None
        while ans not in ['y', 'n']:    
            print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (_bardata[0], altitude_ft)
            ans = raw_input("Are you sure you wish to proceed (y/n)? ")
            if ans == 'y':
                station.setBarData(_bardata[0], altitude_ft)
            elif ans == 'n':
                print "Nothing done."

    @staticmethod
    def set_barometer(station, barometer_inHg):
        """Set the barometer reading to a known correct value."""
        # Hit the console to get the current barometer calibration data:
        _bardata = station.getBarData()
    
        ans = None
        while ans not in ['y', 'n']:
            if barometer_inHg:
                print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (barometer_inHg, _bardata[1])
            else:
                print "Proceeding will have the console pick a sensible barometer calibration and set the station altitude to %.1f feet," % (_bardata[1],)
            ans = raw_input("Are you sure you wish to proceed (y/n)? ")
            if ans == 'y':
                station.setBarData(barometer_inHg, _bardata[1])
            elif ans == 'n':
                print "Nothing done."

    @staticmethod
    def clear_memory(station):
        """Clear the archive memory of a VantagePro"""
    
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will erase old archive records."
            ans = raw_input("Are you sure you wish to proceed (y/n)? ")
            if ans == 'y':
                print "Clearing the archive memory ..."
                station.clearLog()
                print "Archive records cleared."
            elif ans == 'n':
                print "Nothing done."

    @staticmethod
    def set_bucket(station, new_bucket_type):
        """Set the bucket type on the console."""

        print "Old rain bucket type is %d (%s), new one is %d (%s)." % (
            station.rain_bucket_type,
            station.rain_bucket_size,
            new_bucket_type,
            Vantage.rain_bucket_dict[new_bucket_type])
        if station.rain_bucket_type == new_bucket_type:
            print "Old and new bucket types are the same. Nothing done."
        else:
            ans = None
            while ans not in ['y', 'n']:
                print "Proceeding will change the rain bucket type."
                ans = raw_input("Are you sure you want to proceed (y/n)? ")
                if ans == 'y':
                    try:
                        station.setBucketType(new_bucket_type)
                    except StandardError, e:
                        print >> sys.stderr, "Unable to set new bucket type. Reason:\n\t****", e
                    else:
                        print "Bucket type now set to %d." % (station.rain_bucket_type,)
                elif ans == 'n':
                    print "Nothing done."

    @staticmethod
    def set_rain_year_start(station, rain_year_start):

        print "Old rain season start is %d, new one is %d." % (station.rain_year_start, rain_year_start)

        if station.rain_year_start == rain_year_start:
            print "Old and new rain season starts are the same. Nothing done."
        else:
            ans = None
            while ans not in ['y', 'n']:
                print "Proceeding will change the rain season start."
                ans = raw_input("Are you sure you want to proceed (y/n)? ")
                if ans == 'y':
                    try:
                        station.setRainYearStart(rain_year_start)
                    except StandardError, e:
                        print >> sys.stderr, "Unable to set new rain year start. Reason:\n\t****", e
                    else:
                        print "Rain year start now set to %d." % (station.rain_year_start,)
                elif ans == 'n':
                    print "Nothing done."

    @staticmethod
    def set_offset(station, offset_list):
        """Set the on-board offset for a temperature, humidity or wind direction variable."""
        (variable, offset_str) = offset_list.split(',')
        # These variables may be calibrated.
        temp_variables = ['inTemp', 'outTemp' ] + \
            ['extraTemp%d' % i for i in range(1, 8)] + \
            ['soilTemp%d' % i for i in range(1, 5)] + \
            ['leafTemp%d' % i for i in range(1, 5)]

        humid_variables = ['inHumid', 'outHumid'] + \
            ['extraHumid%d' % i for i in range(1, 8)]

        # Wind direction can also be calibrated.
        if variable == "windDir":
            offset = int(offset_str)
            if not -359 < offset < 359:
                print >> sys.stderr, "Wind direction offset %d is out of range." % (offset)
            else:
                ans = None
                while ans not in ['y', 'n']:
                    print "Proceeding will set offset for wind direction to %+d." % (offset)
                    ans = raw_input("Are you sure you want to proceed (y/n)? ")
                    if ans == 'y':
                        try:
                            station.setCalibrationWindDir(offset)
                        except StandardError, e:
                            print >> sys.stderr, "Unable to set new wind offset. Reason:\n\t****", e
                        else:
                            print "Wind direction offset now set to %+d." % (offset)
        elif variable in temp_variables:
            offset = float(offset_str)
            if not -12.8 < offset < 12.7:
                print >> sys.stderr, "Temperature offset %+.1f is out of range." % (offset)
            else:
                ans = None
                while ans not in ['y', 'n']:
                    print "Proceeding will set offset for temperature %s to %.1f." % (variable, offset)
                    ans = raw_input("Are you sure you want to proceed (y/n)? ")
                    if ans == 'y':
                        try:
                            station.setCalibrationTemp(variable, offset)
                        except StandardError, e:
                            print >> sys.stderr, "Unable to set new temperature offset. Reason:\n\t****", e
                        else:
                            print "Temperature offset %s now set to %+.1f." % (variable, offset)
        elif variable in humid_variables:
            offset = int(offset_str)
            if not -100 < offset < 100:
                print >> sys.stderr, "Humidity offset %+d is out of range." % (offset)
            else:
                ans = None
                while ans not in ['y', 'n']:
                    print "Proceeding will set offset for humidity %s to %+d." % (variable, offset)
                    ans = raw_input("Are you sure you want to proceed (y/n)? ")
                    if ans == 'y':
                        try:
                            station.setCalibrationHumid(variable, offset)
                        except StandardError, e:
                            print >> sys.stderr, "Unable to set new humidity offset. Reason:\n\t****", e
                        else:
                            print "Humidity offset %s now set to %+d." % (variable, offset)
        else:
            print >> sys.stderr, "Unknown variable %s" % (variable)

    @staticmethod
    def set_transmitter_type(station, transmitter_list):
        """Set the transmitter type for one of the eight channels."""

        transmitter_list = map((lambda x: int(x) if x != "" else None), transmitter_list.split(','))
        channel = transmitter_list[0]
        if not 1 <= channel <= 8:
            print "Channel number must be between 1 and 8"
            return 
        transmitter_type = transmitter_list[1]
        extra_temp = transmitter_list[2] if len(transmitter_list) > 2 else None
        extra_hum = transmitter_list[3] if len(transmitter_list) > 3 else None 

        try:
            transmitter_type_name = Vantage.transmitter_type_dict[transmitter_type]
        except KeyError:
            print "Unknown transmitter type (%s)" % transmitter_type
            return
        if transmitter_type_name in ['temp', 'temp_hum'] and extra_temp not in range(1, 8):
            print "Transmitter type %s requires extra_temp in range 1-7'" % transmitter_type_name
            return
        if transmitter_type_name in ['hum', 'temp_hum'] and extra_hum not in range(1, 8):
            print "Transmitter type %s requires extra_hum in range 1-7'" % transmitter_type_name
            return
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will set channel %d to type %d (%s)." % (channel, transmitter_type, transmitter_type_name)
            ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if ans == 'y':
                try:
                    station.setTransmitterType(channel, transmitter_type, extra_temp, extra_hum)
                except StandardError, e:
                    print >> sys.stderr, "Unable to set transmitter type. Reason:\n\t****", e
                else:
                    print "Transmitter %d now set to type %d." % (channel, transmitter_type)
            else:
                print "Nothing done."

    @staticmethod
    def set_time(station):
        print "Setting time on console..."
        station.setTime()
        newtime_ts = station.getTime()
        print "Current console time is %s" % weeutil.weeutil.timestamp_to_string(newtime_ts)

    @staticmethod
    def set_dst(station, dst):
        station.setDST(dst) 
        print "Set DST on console to '%s'" % dst

    @staticmethod
    def set_tz_code(station, tz_code):
        print "Setting time zone code to %d..." % tz_code
        station.setTZcode(tz_code)
        new_tz_code = station.getStnInfo()[5]
        print "Set time zone code to %s" % new_tz_code

    @staticmethod
    def set_tz_offset(station, tz_offset):
        offset_int = int(tz_offset)
        h = abs(offset_int) // 100
        m = abs(offset_int) % 100
        if h > 12 or m >= 60:
            raise ValueError("Invalid time zone offset: %s" % tz_offset)
        offset = h * 100 + (100 * m / 60)
        if offset_int < 0:
            offset = -offset
        station.setTZoffset(offset)
        new_offset = station.getStnInfo()[6]
        print "Set time zone offset to %+.1f hours" % new_offset

    @staticmethod
    def set_lamp(station, onoff):
        print "Setting lamp on console..."
        station.setLamp(onoff)

    @staticmethod
    def start_logger(station):
        print "Starting logger ..."
        station.startLogger()
        print "Logger started"

    @staticmethod
    def stop_logger(station):
        print "Stopping logger ..."
        station.stopLogger()
        print "Logger stopped"

    @staticmethod
    def dump_logger(station, config_dict):
        import weewx.manager
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will dump all data in the logger."
            ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if ans == 'y':
                with weewx.manager.open_manager_with_config(config_dict, 'wx_binding',
                                                            initialize=True,
                                                            default_binding_dict={'table_name' : 'archive',
                                                                                  'manager' : 'weewx.wxmanager.WXDaySummaryManager',
                                                                                  'schema' : 'schemas.wview.schema'}) as archive:
                    nrecs = 0
                    # Wrap the Vantage generator function in a converter, which will convert the units to the
                    # same units used by the database:
                    converted_generator = weewx.units.GenWithConvert(station.genArchiveDump(), archive.std_unit_system)
                    print "Starting dump ..."
                    for record in converted_generator:
                        archive.addRecord(record)
                        nrecs += 1
                        if nrecs % 10 == 0:
                            print >> sys.stdout, "Records processed: %d; Timestamp: %s\r" % (nrecs, weeutil.weeutil.timestamp_to_string(record['dateTime'])),
                            sys.stdout.flush()
                    print "\nFinished dump. %d records added" % (nrecs,)
            elif ans == 'n':
                print "Nothing done."

    @staticmethod
    def logger_summary(station, dest_path):
        try:
            dest = open(dest_path, mode="w")
        except IOError, e:
            print >> sys.stderr, "Unable to open destination '%s' for write" % dest_path
            print >> sys.stderr, "Reason: %s" % e
            return

        VantageConfigurator.show_info(station, dest)
    
        print "Starting download of logger summary..."
    
        nrecs = 0
        for (page, index, y, mo, d, h, mn, time_ts) in station.genLoggerSummary():
            if time_ts:
                print >> dest, "%4d %4d %4d | %4d-%02d-%02d %02d:%02d | %s" % (nrecs, page, index, y + 2000, mo, d, h, mn, weeutil.weeutil.timestamp_to_string(time_ts))
            else:
                print >> dest, "%4d %4d %4d [*** Unused index ***]" % (nrecs, page, index)
            nrecs += 1
            if nrecs % 10 == 0:
                print >> sys.stdout, "Records processed: %d; Timestamp: %s\r" % (nrecs, weeutil.weeutil.timestamp_to_string(time_ts)),
                sys.stdout.flush()
        print "\nFinished download of logger summary to file '%s'. %d records processed." % (dest_path, nrecs)


# =============================================================================
#                      Class VantageConfEditor
# =============================================================================

class VantageConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[Vantage]
    # This section is for the Davis Vantage series of weather stations.

    # Connection type: serial or ethernet 
    #  serial (the classic VantagePro)
    #  ethernet (the WeatherLinkIP)
    type = serial

    # If the connection type is serial, a port must be specified:
    #   Debian, Ubuntu, Redhat, Fedora, and SuSE:
    #     /dev/ttyUSB0 is a common USB port name
    #     /dev/ttyS0   is a common serial port name
    #   BSD:
    #     /dev/cuaU0   is a common serial port name
    port = /dev/ttyUSB0

    # If the connection type is ethernet, an IP Address/hostname is required:
    host = 1.2.3.4

    ######################################################
    # The rest of this section rarely needs any attention. 
    # You can safely leave it "as is."
    ######################################################

    # Serial baud rate (usually 19200)
    baudrate = 19200

    # TCP port (when using the WeatherLinkIP)
    tcp_port = 22222

    # TCP send delay (when using the WeatherLinkIP):
    tcp_send_delay = 0.5

    # The id of your ISS station (usually 1). If you use a wind meter connected
    # to a anemometer transmitter kit, use its id
    iss_id = 1

    # How long to wait for a response from the station before giving up (in
    # seconds; must be greater than 2)
    timeout = 4

    # How long to wait before trying again (in seconds)
    wait_before_retry = 1.2

    # How many times to try before giving up:
    max_tries = 4

    # The driver to use:
    driver = weewx.drivers.vantage
"""

    def prompt_for_settings(self):
        settings = dict()
        print "Specify the hardware interface, either 'serial' or 'ethernet'."
        print "If the station is connected by serial, USB, or serial-to-USB"
        print "adapter, specify serial.  Specify ethernet for stations with"
        print "WeatherLinkIP interface."
        settings['type'] = self._prompt('type', 'serial', ['serial', 'ethernet'])
        if settings['type'] == 'serial':
            print "Specify a port for stations with a serial interface, for"
            print "example /dev/ttyUSB0 or /dev/ttyS0."
            settings['port'] = self._prompt('port', '/dev/ttyUSB0')
        else:
            print "Specify the IP address (e.g., 192.168.0.10) or hostname"
            print "(e.g., console or console.example.com) for stations with"
            print "an ethernet interface."
            settings['host'] = self._prompt('host')
        return settings
