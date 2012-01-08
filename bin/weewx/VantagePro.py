#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""classes and functions for interfacing with a Davis VantagePro or VantagePro2"""

import datetime
import serial
import socket
import struct
import syslog
import time

from weewx.crc16 import crc16
import weeutil.weeutil
import weewx.accum
import weewx.wxformulas

# A few handy constants:
_ack    = chr(0x06)
_resend = chr(0x21)

class BaseWrapper(object):
    """Base class for (Serial|Ethernet)Wrapper"""

    #===============================================================================
    #          Primitives for working with the Davis Console
    #===============================================================================

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
                    syslog.syslog(syslog.LOG_DEBUG, "VantagePro: successfully woke up console")
                    return
                print "Unable to wake up console... sleeping"
                time.sleep(wait_before_retry)
                print "Unable to wake up console... retrying"
            except weewx.WeeWxIOError:
                pass

        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to wake up console")
        raise weewx.WakeupError("Unable to wake up VantagePro console")

    def send_data(self, data):
        """Send data to the Davis console, waiting for an acknowledging <ACK>
        
        If the <ACK> is not received, no retry is attempted. Instead, an exception
        of type weewx.WeeWxIOError is raised
    
        data: The data to send, as a string"""

        self.write(data)
    
        # Look for the acknowledging ACK character
        _resp = self.read()
        if _resp != _ack: 
            syslog.syslog(syslog.LOG_ERR, "VantagePro: No <ACK> received from console")
            raise weewx.WeeWxIOError("No <ACK> received from VantagePro console")
    
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
            except weewx.WeeWxIOError:
                pass

        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to pass CRC16 check while sending data")
        raise weewx.CRCError("Unable to pass CRC16 check while sending data to VantagePro console")

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

            except weewx.WeeWxIOError:
                # Caught an error. Keep trying...
                continue
        
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while sending command %s" % command)
        raise weewx.RetriesExceeded("Max retries exceeded while sending command %s" % command)
    
        
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
            except weewx.WeeWxIOError:
                pass
            first_time = False

        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to pass CRC16 check while getting data")
        raise weewx.CRCError("Unable to pass CRC16 check while getting data")

class SerialWrapper(BaseWrapper):
    """Wraps a serial connection returned from package serial"""
    
    def __init__(self, port, baudrate, timeout):
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout

    def flush_input(self):
        self.serial_port.flushInput()

    def flush_output(self):
        self.serial_port.flushOutput()

    def queued_bytes(self):
        return self.serial_port.inWaiting()
 
    def read(self, chars=1):
        _buffer = self.serial_port.read(chars)
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
        # Open up the port and store it
        self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def closePort(self):
        try:
            # This will cancel any pending loop:
            self.wakeup_console()
        except:
            pass
        self.serial_port.close()

class EthernetWrapper(BaseWrapper):
    """Wrap a socket"""

    def __init__(self, host, port, timeout, tcp_send_delay):

        self.host           = host
        self.port           = port
        self.timeout        = timeout
        self.tcp_send_delay = tcp_send_delay

    def openPort(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
        except:
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to connect to ethernet host %s on port %d." % (self.host, self.port))
            raise

    def closePort(self):
        try:
            # This will cancel any pending loop:
            self.wakeup_console()
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
                raise weewx.WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
            return _buffer
        except:
            raise weewx.WeeWxIOError("Socket read error")
        
    def write(self, data):
        """Write to a WeatherLinkIP"""
        try:
            self.socket.sendall(data)
            time.sleep(self.tcp_send_delay)
        except:
            raise weewx.WeeWxIOError("Socket write error")

class VantagePro(object):
    """Class that represents a connection to a VantagePro console.
    
    The connection will be opened after initialization"""

    # List of types for which archive records will be explicitly calculated
    # from LOOP data. Right now there is only one, but if we ever support weather
    # stations that do not have onboard storage of archive data (and most don't),
    # this could be expanded, probably to include virtually every type.
    special = ['consBatteryVoltage']

    # Various codes used internally by the VP2:
    barometer_unit_dict   = {0:'inHg', 1:'mmHg', 2:'hPa', 3:'mbar'}
    temperature_unit_dict = {0:'degree_F', 1:'degree_10F', 2:'degree_C', 3:'degree_10C'}
    elevation_unit_dict   = {0:'foot', 1:'meter'}
    rain_unit_dict        = {0:'inch', 1:'mm'}
    wind_unit_dict        = {0:'mile_per_hour', 1:'meter_per_second', 2:'km_per_hour', 3:'knot'}
    wind_cup_dict         = {0:'small', 1:'large'}
    rain_bucket_dict      = {0: "0.01 inches", 1: "0.2 MM", 2: "0.1 MM"}
    
    def __init__(self, **vp_dict) :
        """Initialize an object of type VantagePro.
        
        NAMED ARGUMENTS:
        
        connection_type: The type of connection (serial|ethernet) [Required]

        port: The serial port of the VP. [Required if serial/USB
        communication]

        host: The VantagePro network host [Required if Ethernet communication]
        
        baudrate: Baudrate of the port. [Optional. Default 19200]

        tcp_port: TCP port to connect to [Optional. Default 22222]
        
        tcp_send_delay: Block after sending data to WeatherLinkIP to allow it
        to process the command [Optional. Default is 1]

        timeout: How long to wait before giving up on a response from the
        serial port. [Optional. Default is 5]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 1.2 seconds]

        max_tries: How many times to try again before giving up. [Optional.
        Default is 4]
        
        archive_delay: How long to wait after an archive record is due
        before retrieving it. [Optional. Default is 15 seconds]
        
        iss_id: The station number of the ISS [Optional. Default is 1]
        
        unit_system: What unit system to use on the VP. [Optional.
        Default is 1 (US Customary), and the only system supported
        in this version.]
        """

        # TODO: These values should really be retrieved dynamically from the VP:
        self.iss_id           = int(vp_dict.get('iss_id', 1))
        self.model_type       = 2 # = 1 for original VantagePro, = 2 for VP2

        # These come from the configuration dictionary:
        self.wait_before_retry= float(vp_dict.get('wait_before_retry', 1.2))
        self.max_tries        = int(vp_dict.get('max_tries'    , 4))
        self.archive_delay    = int(vp_dict.get('archive_delay', 15))
        self.unit_system      = int(vp_dict.get('unit_system'  , 1))
        self.dst_delta        = 3600

        # Get an appropriate port, depending on the connection type:
        self.port = VantagePro._port_factory(vp_dict)
        
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
        """Generator function that returns loop packets until the next archive record is due."""

        # Next time to ask for archive records:
        nextArchive_ts = (int(time.time() / self.archive_interval) + 1) *\
                            self.archive_interval + self.archive_delay
        
        while True:
            # Get LOOP packets in big batches, then cancel as necessary when the expiration
            # time is up. This is necessary because there is an undocumented limit to how
            # many LOOP records you can request for on the VP (somewhere around 220).
            for _loopPacket in self.genDavisLoopPackets(200):
                # Translate the LOOP packet to one with physical units:
                _physicalPacket = self.translateLoopPacket(_loopPacket)
                self.accumulateLoop(_physicalPacket)
                yield _physicalPacket
                
                # Check to see if it's time to get new archive data. If so, cancel the loop
                # and return
                if time.time() >= nextArchive_ts:
                    syslog.syslog(syslog.LOG_DEBUG, "VantagePro: new archive record due. Canceling loop")
                    return

    def genDavisLoopPackets(self, N=1):
        """Generator function to return N LoopPacket objects from a VantagePro console
        
        N: The number of packets to generate [default is 1]
        
        yields: up to N DavisLoopPacket objects
        """

        syslog.syslog(syslog.LOG_DEBUG, "VantagePro: Requesting %d LOOP packets." % N)
        
        self.port.wakeup_console(self.max_tries, self.wait_before_retry)
        
        # Request N packets:
        self.port.send_data("LOOP %d\n" % N)
        
        for loop in xrange(N) :
            
            for unused_count in xrange(self.max_tries):
                try:
                    # Fetch a packet
                    _buffer = self.port.read(99)
                except weewx.WeeWxIOError, e:
                    syslog.syslog(syslog.LOG_ERR, "VantagePro: LOOP #%d; read error" % (loop,))
                    syslog.syslog(syslog.LOG_ERR, "      ****  %s" % e)
                    continue
                if crc16(_buffer) :
                    syslog.syslog(syslog.LOG_ERR,
                                  "VantagePro: LOOP #%d; CRC error... retrying" % loop)
                    continue
                # ... decode it
                pkt_dict = unpackLoopPacket(_buffer[:95])
                # Yield it
                yield pkt_dict
                break
            else:
                syslog.syslog(syslog.LOG_ERR, 
                              "VantagePro: Max retries exceeded while getting LOOP packets")
                raise weewx.RetriesExceeded("While getting LOOP packets")

    def genArchivePackets(self, since_ts):
        """A generator function to return archive packets from a VantagePro station.
        
        since_ts: A timestamp. All data since (but not including) this time will be returned.
        Pass in None for all data
        
        yields: a sequence of dictionaries containing the data
        """
        
        if since_ts :
            since_tt = time.localtime(since_ts)
            # NB: note that some of the Davis documentation gives the year offset as 1900.
            # From experimentation, 2000 seems to be right, at least for the newer models:
            _vantageDateStamp = since_tt[2] + (since_tt[1]<<5) + ((since_tt[0]-2000)<<9)
            _vantageTimeStamp = since_tt[3] *100 + since_tt[4]
            syslog.syslog(syslog.LOG_DEBUG, 'VantagePro: Getting archive packets since %s' % weeutil.weeutil.timestamp_to_string(since_ts))
        else :
            _vantageDateStamp = _vantageTimeStamp = 0
            syslog.syslog(syslog.LOG_DEBUG, 'VantagePro: Getting all archive packets')
     
        #Pack the date and time into a string, little-endian order
        _datestr = struct.pack("<HH", _vantageDateStamp, _vantageTimeStamp)
        
        # Save the last good time:
        _last_good_ts = since_ts if since_ts else 0
        
        # Retry the dump up to max_tries times
        for unused_count in xrange(self.max_tries) :
            try :
                # Wake up the console...
                self.port.wakeup_console(self.max_tries, self.wait_before_retry)
                # ... request a dump...
                self.port.send_data('DMPAFT\n')
                # ... from the designated date (allow only one try because that's all the console allows):
                self.port.send_data_with_crc16(_datestr, max_tries=1)
                
                # Get the response with how many pages and starting index and decode it. Again, allow only one try:
                _buffer = self.port.get_data_with_crc16(6, max_tries=1)
                (_npages, _start_index) = struct.unpack("<HH", _buffer[:4])
              
                syslog.syslog(syslog.LOG_DEBUG, "VantagePro: Retrieving %d page(s); starting index= %d" % (_npages, _start_index))
                
                # Cycle through the pages...
                for unused_ipage in xrange(_npages) :
                    # ... get a page of archive data
                    _page = self.port.get_data_with_crc16(267, prompt=_ack, max_tries=self.max_tries)
                    # Now extract each record from the page
                    for _index in xrange(_start_index, 5) :
                        # If the console has been recently initialized, there will
                        # be unused records, which are filled with 0xff. Detect this
                        # by looking at the first 4 bytes (the date and time):
                        if _page[1+52*_index:5+52*_index] == 4*chr(0xff) :
                            # This record has never been used. We're done.
                            syslog.syslog(syslog.LOG_DEBUG, "VantagePro: empty record page %d; index %d" \
                                          % (unused_ipage, _index))
                            return
                        # Unpack the raw archive packet:
                        _packet = unpackArchivePacket(_page[1+52*_index:53+52*_index])
                        # Divide archive interval by 60 to keep consistent with wview
                        _packet['interval']   = self.archive_interval / 60 
                        _packet['model_type'] = self.model_type
                        _packet['iss_id']     = self.iss_id
                        _packet['rxCheckPercent'] = _rxcheck(_packet)

                        # Convert from the internal, Davis encoding to physical units:
                        _record = self.translateArchivePacket(_packet)
                        # Check to see if the time stamps are declining, which would
                        # signal this is a wrap around record on the last page.
                        # However, the time stamps may be declining just because of the
                        # "fall back" from DST in the Fall, so allow times stamps to
                        # decline up to the DST delta.
                        if _record['dateTime'] is None or _record['dateTime'] + self.dst_delta <= _last_good_ts :
                            # The time stamp is declining. We're done.
                            syslog.syslog(syslog.LOG_DEBUG, "VantagePro: time stamps declining. Record timestamp %s" \
                                          % weeutil.weeutil.timestamp_to_string(_record['dateTime']))
                            syslog.syslog(syslog.LOG_DEBUG, "      ****  Last good timestamp %s" \
                                          % weeutil.weeutil.timestamp_to_string(_last_good_ts))
                            return
                        # Augment the record with the data from the accumulators:
                        self.archiveAccumulators(_record)
                        # Set the last time to the current time, and yield the packet
                        _last_good_ts = _record['dateTime']
                        yield _record
                    _start_index = 0
                return
            except weewx.WeeWxIOError:
                # Caught an error. Keep retrying...
                continue
        
        # All of the retries have failed. Declare an error
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting archive packets")
        raise weewx.RetriesExceeded("Max retries exceeded while getting archive packets")

    def accumulateLoop(self, physicalLOOPPacket):
        """Process LOOP data, calculating averages within an archive period."""
        try:
            # Gather the LOOP data for each special type. An exception
            # will be thrown if either the accumulators have not been initialized 
            # yet, or if the timestamp of the packet is outside the timespan held
            # by the accumulator.
            for obs_type in self.special:
                self.current_accumulators[obs_type].addToSum(physicalLOOPPacket)
            # For battery status, OR every status field together:
            self.txBatteryStatus |= physicalLOOPPacket['txBatteryStatus']
        except (AttributeError, weewx.accum.OutOfSpan):
            # Initialize the accumulators:
            self.clearAccumulators(physicalLOOPPacket['dateTime'])
            # Try again:
            try:
                for obs_type in self.special:
                    self.current_accumulators[obs_type].addToSum(physicalLOOPPacket)
                # For battery status, OR every status field together:
                self.txBatteryStatus |= physicalLOOPPacket['txBatteryStatus']
            except weewx.accum.OutOfSpan:
                # Failed again. There's something wrong. Log it.
                syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to initialize accumulators.")
            
    def clearAccumulators(self, time_ts):
        """Initialize or clear the accumulators"""
        try:
            # Shuffle accumulators. An exception will be thrown
            # if they have never been initialized.
            self.last_accumulators=self.current_accumulators
        except:
            pass
        # Calculate the interval timespan that contains time_ts
        start_of_interval = weeutil.weeutil.startOfInterval(time_ts, self.archive_interval)
        timespan = weeutil.weeutil.TimeSpan(start_of_interval, start_of_interval+self.archive_interval)
        # Initialize current_accumulators with instances of StdAccum
        self.current_accumulators = {}
        for obs_type in VantagePro.special:
            self.current_accumulators[obs_type] = weewx.accum.StdAccum(obs_type, timespan)
        self.txBatteryStatus = 0  

    def archiveAccumulators(self, record):
        """Add the results of the accumulators to the current archive record."""
        try:
            # For each special type, add its average to the archive record. An exception
            # will be thrown if there is no accumulator (first time through).
            for obs_type in VantagePro.special:
                # Make sure the times match:
                if self.last_accumulators[obs_type].timespan.stop == record['dateTime']:
                    record[obs_type] = self.last_accumulators[obs_type].avg
            # Save the battery status:
            record['txBatteryStatus'] = self.txBatteryStatus
        except AttributeError:
            pass
        
    def getTime(self) :
        """Get the current time from the console and decode it, returning it as a time-tuple
        
        returns: the time as a time-tuple
        """
        # Try up to 3 times:
        for unused_count in xrange(self.max_tries) :
            try :
                # Wake up the console...
                self.port.wakeup_console(max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                # ... request the time...
                self.port.send_data('GETTIME\n')
                # ... get the binary data. No prompt, only one try:
                _buffer = self.port.get_data_with_crc16(8, max_tries=1)
                (sec, minute, hr, day, mon, yr, unused_crc) = struct.unpack("<bbbbbbH", _buffer)
                time_tt = (yr+1900, mon, day, hr, minute, sec, 0, 0, -1)
                return time_tt
            except weewx.WeeWxIOError :
                # Caught an error. Keep retrying...
                continue
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting time")
        raise weewx.RetriesExceeded("While getting console time")
            
    def setTime(self, newtime_ts, max_drift):
        """Set the clock on the Davis VantagePro console

        newtime_ts: The time the internal clock should be set to.
        
        max_drift: The request to set the time will be ignored
        if the clock error is less than this value."""
        
        # Unfortunately, this algorithm takes a little while to execute, so the clock
        # usually ends up a few hundred milliseconds slow
        _diff = time.mktime(self.getTime()) - newtime_ts
        syslog.syslog(syslog.LOG_INFO, 
                      "VantagePro: Clock error is %.2f seconds (positive is fast)" % _diff)
        if abs(_diff) < max_drift:
            return
        newtime_tt = time.localtime(int(newtime_ts + 0.5))
            
        # The Davis expects the time in reversed order, and the year is since 1900
        _buffer = struct.pack("<bbbbbb", newtime_tt[5], newtime_tt[4], newtime_tt[3], newtime_tt[2],
                                         newtime_tt[1], newtime_tt[0] - 1900)
            
        for unused_count in xrange(self.max_tries) :
            try :
                self.port.wakeup_console(max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                self.port.send_data('SETTIME\n')
                self.port.send_data_with_crc16(_buffer, max_tries=self.max_tries)
                syslog.syslog(syslog.LOG_NOTICE,
                              "VantagePro: Clock set to %s (%d)" % (time.asctime(newtime_tt), 
                                                                   time.mktime(newtime_tt)) )
                return
            except weewx.WeeWxIOError :
                # Caught an error. Keep retrying...
                continue
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while setting time")
        raise weewx.RetriesExceeded("While setting console time")
    
    def setBucketType(self, new_bucket_code):
        """Set the rain bucket type.
        
        new_bucket_code: The new bucket type. Must be one of 0, 1, or 2
        """
        if new_bucket_code not in (0, 1, 2):
            raise weewx.ViolatedPrecondition("Invalid bucket code %d" % new_bucket_code)
        old_setup_bits = self._getEEPROM_value(0x2B)
        new_setup_bits = (old_setup_bits & 0xCF) | (new_bucket_code << 4)
        
        # Tell the console to put one byte in hex location 0x2B
        self.port.send_data("EEBWR 2B 01\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_setup_bits), max_tries=1)
        # Then call NEWSETUP to get it to stick:
        self.port.send_data("NEWSETUP\n")
        
        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "VantagePro: Rain bucket type set to %d (%s)" %(self.rain_bucket_type, self.rain_bucket_size))

    def setRainSeasonStart(self, new_rain_season_start):
        """Set the start of the rain season.
        
        new_rain_season_start: Must be in the closed range 1...12
        """
        if new_rain_season_start not in range(1,13):
            raise weewx.ViolatedPrecondition("Invalid rain season start %d" % (new_rain_season_start,))
        
        # Tell the console to put one byte in hex location 0x2C
        self.port.send_data("EEBWR 2C 01\n")
        # Follow it up with the data:
        self.port.send_data_with_crc16(chr(new_rain_season_start), max_tries=1)

        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "VantagePro: Rain season start set to %d" % (self.rain_season_start,))

    def setBarData(self, new_barometer_inHg, new_altitude_foot):
        """Set the internal barometer calibration and altitude settings in the console.
        
        new_barometer_inHg: The local, reference barometric pressure in inHg.
        
        new_altitude_foot: The new altitude in feet."""
        
        new_barometer = int(new_barometer_inHg*1000.0)
        new_altitude = int(new_altitude_foot)
        
        command = "BAR=%d %d\n" % (new_barometer, new_altitude)
        self.port.send_command(command)
        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "VantagePro: Set barometer calibration.")
        
    def setArchiveInterval(self, archive_interval_seconds):
        """Set the archive interval of the VantagePro.
        
        archive_interval_seconds: The new interval to use in minutes. Must be one of
        60, 300, 600, 900, 1800, 3600, or 7200 
        """
        if archive_interval_seconds not in (60, 300, 600, 900, 1800, 3600, 7200):
            raise weewx.ViolatedPrecondition, "VantagePro: Invalid archive interval (%f)" % (self.archive_interval,)

        # The console expects the interval in minutes. Divide by 60.
        command = 'SETPER %d\n' % (archive_interval_seconds / 60)
        
        self.port.send_command(command, max_tries=self.max_tries)

        self._setup()
        syslog.syslog(syslog.LOG_NOTICE, "VantagePro: archive interval set to %d seconds" % (self.archive_interval_seconds,))
    
    def clearLog(self):
        """Clear the internal archive memory in the VantagePro."""
        for unused_count in xrange(self.max_tries):
            try:
                self.port.wakeup_console(max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                self.port.send_data("CLRLOG\n")
                syslog.syslog(syslog.LOG_NOTICE, "VantagePro: Archive memory cleared.")
                return
            except weewx.WeeWxIOError:
                #Caught an error. Keey trying...
                continue
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while clearing log")
        raise weewx.RetriesExceeded("While clearing log")
    
    def getRX(self) :
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
        
    def translateLoopPacket(self, loopPacket):
        """Given a LOOP packet in vendor units, this function translates to physical units.
        
        loopPacket: A dictionary holding the LOOP data in the internal units used by Davis.
        
        returns: A dictionary with the values in physical units."""
        # Right now, only US customary units are supported
        if self.unit_system != weewx.US :
            raise weewx.UnsupportedFeature("Only US Customary Units are supported on the Davis VP2.")

        _packet = self.translateLoopToUS(loopPacket)

        return _packet
    

    def translateArchivePacket(self, archivePacket):
        """Translates an archive packet from the internal units used by Davis, into physical units.
        
        archivePacket: A dictionary holding an archive packet in the internal, Davis encoding
        
        returns: A dictionary with the values in physical units."""
        
        # Right now, only US units are supported
        if self.unit_system != weewx.US :
            raise weewx.UnsupportedFeature("Only US Units are supported on the Davis VP2.")

        _packet = self.translateArchiveToUS(archivePacket)
        return _packet
    
    #===========================================================================
    #              VantagePro utility functions
    #===========================================================================
    
    def translateLoopToUS(self, packet):
        """Translates a loop packet from the internal units used by Davis, into US Customary Units.
        
        packet: A dictionary holding the LOOP data in the internal units used by Davis.
        
        returns: A dictionary with the values in US Customary Units."""
        # This dictionary maps a type key to a function. The function should be able to
        # decode a sensor value held in the loop packet in the internal, Davis form into US
        # units and return it. From the Davis documentation, it's not clear what the
        # 'dash' value is for some of these, so I'm assuming it's the same as for an archive
        # packet.
    
        if packet['usUnits'] != weewx.US :
            raise weewx.ViolatedPrecondition("Unit system on the VantagePro must be US Customary Units only")
    
        record = {}
        
        for _type in _loop_map:    
            # Get the mapping function needed for this key
            func = _loop_map[_type]
            # Call it, with the value as an argument, storing the result:
            record[_type] = func(packet[_type])
    
        # Add a few derived values that are not in the packet itself.
        T = record['outTemp']
        R = record['outHumidity']
        W = record['windSpeed']
    
        record['dewpoint']  = weewx.wxformulas.dewpointF(T, R)
        record['heatindex'] = weewx.wxformulas.heatindexF(T, R)
        record['windchill'] = weewx.wxformulas.windchillF(T, W)
        
        return record
    

    def translateArchiveToUS(self, packet):
        """Translates an archive packet from the internal units used by Davis, into US units.
        
        packet: A dictionary holding an archive packet in the internal, Davis encoding
        
        returns: A dictionary with the values in US units."""
    
        if packet['usUnits'] != weewx.US :
            raise weewx.ViolatedPrecondition("Unit system on the VantagePro must be U.S. units only")
    
        record = {}
        
        for _type in packet:
            
            # Get the mapping function needed for this key
            func = _archive_map.get(_type)
            if func:
                # Call it, with the value as an argument, storing the results:
                record[_type] = func(packet[_type])
    
        # Add a few derived values that are not in the packet itself.
        T = record['outTemp']
        R = record['outHumidity']
        W = record['windSpeed']
        
        record['dewpoint']  = weewx.wxformulas.dewpointF(T, R)
        record['heatindex'] = weewx.wxformulas.heatindexF(T, R)
        record['windchill'] = weewx.wxformulas.windchillF(T, W)
        record['dateTime']  = _archive_datetime(packet)
        record['usUnits']   = weewx.US
        
        return record

    def _setup(self):
        """Retrieve the EEPROM data block from a VP2 and use it to set various properties"""
        
        self.port.wakeup_console(max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)

        unit_bits              = self._getEEPROM_value(0x29)
        setup_bits             = self._getEEPROM_value(0x2B)
        self.rain_season_start = self._getEEPROM_value(0x2C)
        self.archive_interval  = self._getEEPROM_value(0x2D) * 60
        self.elevation         = self._getEEPROM_value(0x0F, "<H") 

        barometer_unit_code   =  unit_bits & 0x03
        temperature_unit_code = (unit_bits & 0x0C) >> 3
        elevation_unit_code   = (unit_bits & 0x10) >> 4
        rain_unit_code        = (unit_bits & 0x20) >> 5
        wind_unit_code        = (unit_bits & 0xC0) >> 6

        self.wind_cup_type    = (setup_bits & 0x08) >> 3
        self.rain_bucket_type = (setup_bits & 0x30) >> 4

        self.barometer_unit   = VantagePro.barometer_unit_dict[barometer_unit_code]
        self.temperature_unit = VantagePro.temperature_unit_dict[temperature_unit_code]
        self.elevation_unit   = VantagePro.elevation_unit_dict[elevation_unit_code]
        self.rain_unit        = VantagePro.rain_unit_dict[rain_unit_code]
        self.wind_unit        = VantagePro.wind_unit_dict[wind_unit_code]
        self.wind_cup_size    = VantagePro.wind_cup_dict[self.wind_cup_type]
        self.rain_bucket_size = VantagePro.rain_bucket_dict[self.rain_bucket_type]
        
        # Adjust the translation maps to reflect the rain bucket size:
        if self.rain_bucket_type == 1:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _bucket_1
            _loop_map['rainRate']    = _bucket_1_None
        elif self.rain_bucket_type == 2:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _bucket_2
            _loop_map['rainRate']    = _bucket_2_None
        else:
            _archive_map['rain'] = _archive_map['rainRate'] = _loop_map['stormRain'] = _loop_map['dayRain'] = \
                _loop_map['monthRain'] = _loop_map['yearRain'] = _val100
            _loop_map['rainRate']    = _big_val100

    def _getEEPROM_value(self, offset, v_format="B"):
        """Get the value located at a specified offset in the EEPROM."""
        
        nbytes = struct.calcsize(v_format)
        firsttime=True
        
        command = "EEBRD %X %d\n" % (offset, nbytes)
        for unused_count in xrange(self.max_tries):
            try:
                if not firsttime:
                    self.port.wakup_console(max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    firsttime = False
                self.port.send_data(command)
                _buffer = self.port.get_data_with_crc16(nbytes+2, max_tries=1)
                _value = struct.unpack(v_format, _buffer[:-2])
                return _value[0]
            except weewx.WeeWxIOError:
                continue
        
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting EEPROM data at address %X" % offset)
        raise weewx.RetriesExceeded("While getting EEPROM data value at address %X" % offset)
        
    @staticmethod
    def _port_factory(vp_dict):
        """Produce a serial or ethernet port object"""
        
        timeout = float(vp_dict.get('timeout', 5.0))
        
        # Get the connection type. If it is not specified, assume 'serial':
        connection_type = vp_dict.get('type', 'serial').lower()

        if connection_type == "serial":
            port = vp_dict['port']
            baudrate = int(vp_dict.get('baudrate', 19200))
            return SerialWrapper(port, baudrate, timeout)
        elif connection_type == "ethernet":
            hostname = vp_dict['host']
            tcp_port = int(vp_dict.get('tcp_port', 22222))
            tcp_send_delay = int(vp_dict.get('tcp_send_delay', 1))
            return EthernetWrapper(hostname, tcp_port, timeout, tcp_send_delay)
        raise weewx.UnsupportedFeature(vp_dict['type'])

#===============================================================================
#                         LOOP packet helper functions
#===============================================================================

# A tuple of all the types held in a VantagePro2 LOOP packet in their native order.
vp2loop = ('loop',            'loop_type',     'packet_type', 'next_record', 'barometer', 
           'inTemp',          'inHumidity',    'outTemp', 
           'windSpeed',       'windSpeed10',   'windDir', 
           'extraTemp1',      'extraTemp2',    'extraTemp3',  'extraTemp4',
           'extraTemp5',      'extraTemp6',    'extraTemp7', 
           'soilTemp1',       'soilTemp2',     'soilTemp3',   'soilTemp4',
           'leafTemp1',       'leafTemp2',     'leafTemp3',   'leafTemp4',
           'outHumidity',     'extraHumid1',   'extraHumid2', 'extraHumid3',
           'extraHumid4',     'extraHumid5',   'extraHumid6', 'extraHumid7',
           'rainRate',        'UV',            'radiation',   'stormRain',   'stormStart',
           'dayRain',         'monthRain',     'yearRain',    'dayET',       'monthET',    'yearET',
           'soilMoist1',      'soilMoist2',    'soilMoist3',  'soilMoist4',
           'leafWet1',        'leafWet2',      'leafWet3',    'leafWet4',
           'insideAlarm',     'rainAlarm',     'outsideAlarm1', 'outsideAlarm2',
           'extraAlarm1',     'extraAlarm2',   'extraAlarm3', 'extraAlarm4',
           'extraAlarm5',     'extraAlarm6',   'extraAlarm7', 'extraAlarm8',
           'soilLeafAlarm1',  'soilLeafAlarm2', 'soilLeafAlarm3', 'soilLeafAlarm4',
           'txBatteryStatus', 'consBatteryVoltage', 'forecastIcon', 'forecastRule',
           'sunrise',         'sunset')

loop_format = struct.Struct("<3sbBHHhBhBBH7B4B4BB7BHBHHHHHHHHH4B4B16BBHBBHH")

def unpackLoopPacket(raw_packet) :
    """Decode a Davis LOOP packet, returning the results as a dictionary.
    
    raw_packet: The loop packet data buffer, passed in as a string. This will be unpacked and 
    the results placed a dictionary"""

    # Unpack the data, using the compiled stuct.Struct string 'loop_format'
    data_tuple = loop_format.unpack(raw_packet)

    packet = dict(zip(vp2loop, data_tuple))

    # Detect the kind of LOOP packet. Type 'A' has the character 'P' in this
    # position. Type 'B' contains the 3-hour barometer trend in this position.
    if packet['loop_type'] == ord('P'):
        packet['trend'] = None
        packet['loop_type'] = 'A'
    else :
        packet['trend'] = packet['loop_type']
        packet['loop_type'] = 'B'

    # Add a timestamp:
    packet['dateTime'] = int(time.time() + 0.5)

    # As far as I know, the Davis supports only US units:
    packet['usUnits'] = weewx.US
    
    return packet

#===============================================================================
#                         archive packet helper functions
#===============================================================================

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
        raise weewx.UnknownArchiveType("Unknown archive type = 0x%x" % (packet_type,)) 
        
    data_tuple = archive_format.unpack(raw_packet)
    
    packet = dict(zip(dataTypes, data_tuple))
    
    # As far as I know, the Davis supports only US units:
    packet['usUnits'] = weewx.US

    return packet

def _rxcheck(packet):
    """Gives an estimate of the fraction of packets received.
    
    Ref: Vantage Serial Protocol doc, V2.1.0, released 25-Jan-05; p42"""
    # The formula for the expected # of packets varies with model number.
    if packet['model_type'] == 1 :
        _expected_packets = float(packet['interval'] * 60) / ( 2.5 + (packet['iss_id']-1) / 16.0) -\
                            float(packet['interval'] * 60) / (50.0 + (packet['iss_id']-1) * 1.25)
    elif packet['model_type'] == 2 :
        _expected_packets = 960.0 * packet['interval'] / float(41 + packet['iss_id'] - 1)
    else :
        return None
    _frac = packet['number_of_wind_samples'] * 100.0 / _expected_packets
    if _frac > 100.0 :
        _frac = 100.0
    return _frac

#===============================================================================
#                      Decoding routines
#===============================================================================

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
    
def _loop_date(v):
    """Returns the epoch time stamp of a time encoded in the LOOP packet, 
    which, for some reason, uses a different encoding scheme than the archive packet.
    Also, the Davis documentation isn't clear whether "bit 0" refers to the least-significant
    bit, or the most-significant bit. I'm assuming the former, which is the usual
    in little-endian machines."""
    if v == 0xffff :
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
    return datetime.time(v//100, v%100)

def _big_val(v) :
    return float(v) if v != 0x7fff else None

def _big_val10(v) :
    return float(v)/10.0 if v != 0x7fff else None

def _big_val100(v):
    return float(v)/100.0 if v != 0xffff else None

def _val100(v):
    return float(v)/100.0

def _val1000(v) :
    return float(v)/1000.0

def _val1000Zero(v):
    return float(v)/1000.0 if v != 0 else None

def _little_val(v) :
    return float(v) if v != 0x00ff else None

def _little_val10(v) :
    return float(v)/10.0 if v != 0x00ff else None
    
def _little_temp(v) :
    return float(v-90) if v != 0x00ff else None

def _null(v):
    return v

def _null_float(v) :
    return float(v)

def _null_int(v):
    return int(v)

def _windDir(v):
    return float(v) * 22.5 if v!= 0x00ff else None

# Rain bucket type "1", a 0.2 mm bucket
def _bucket_1(v):
    return float(v)*0.00787401575

def _bucket_1_None(v):
    return float(v)*0.00787401575 if v != 0xffff else None

# Rain bucket type "2", a 0.1 mm bucket
def _bucket_2(v):
    return float(v)*0.00393700787

def _bucket_2_None(v):
    return float(v)*0.00393700787 if v != 0xffff else None

# This dictionary maps a type key to a function. The function should be able to
# decode a sensor value held in the LOOP packet in the internal, Davis form into US
# units and return it.
_loop_map = {'dateTime'        : _null,
             'barometer'       : _val1000Zero, 
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
             'dayET'           : _val100, 
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
_archive_map={'interval'       : _null_int,
              'barometer'      : _val1000Zero, 
              'inTemp'         : _big_val10,
              'outTemp'        : _big_val10,
              'highOutTemp'    : lambda v : float(v/10.0) if v != -32768 else None,
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
              'highRadiation'  : lambda v : float(v) if v else None,
              'UV'             : _little_val10,
              'highUV'         : _little_val10, # TODO: not sure about this one. 
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
              'rxCheckPercent' : _null_float,
              'forecastRule'   : _null,
              'readClosed'     : _null,
              'readOpened'     : _null}

#===============================================================================
#     Routines for configuring and querying the VP2.
#     These are called dynamically from the configure.py utility.
#===============================================================================

import optparse

import weewx.units

def getOptionGroup(parser):
    
    group = optparse.OptionGroup(parser,"Options for Davis weather stations", 
                                 "These options are specific to the Davis Vantage series of weather stations.")
    group.add_option("--info", action="store_true", dest="info",
                     help="To print configuration, reception, and barometer calibration information about your weather station.")
    group.add_option("--configure", action="store_true", dest="configure",
                     help="To configure your weather station using settings in the specified configuration file.")
    group.add_option("--clear", action="store_true", dest="clear",
                     help="To clear the memory of your weather station.")
    parser.add_option_group(group)

def runOptions(config_dict, options, args):
    
    if options.info:
        info(config_dict)
    if options.configure:
        configure(config_dict)
    if options.clear:
        clear(config_dict)
        
def info(config_dict):
    """Query the configuration of the VantagePro, printing out status information"""
    
    print "Querying..."
    
    # Open up the weather station:
    station = weewx.VantagePro.VantagePro(**config_dict['VantagePro'])

    try:
        try:
            _firmware_date = station.getFirmwareDate()
        except:
            _firmware_date = "<Unavailable>"
        
        console_time = time.strftime("%x %X", station.getTime())
        
        print  """VantagePro EEPROM settings:
        
        CONSOLE FIRMWARE DATE: %s
        
        CONSOLE SETTINGS:
          Archive interval: %d (seconds)
          Altitude:         %d (%s)
          Wind cup type:    %s
          Rain bucket type: %s
          Rain year start:  %d
          Onboard time:     %s
          
        CONSOLE DISPLAY UNITS:
          Barometer:   %s
          Temperature: %s
          Rain:        %s
          Wind:        %s
          """ % (_firmware_date,
                 station.archive_interval, station.elevation, station.elevation_unit,
                 station.wind_cup_size, station.rain_bucket_size, station.rain_season_start, console_time,
                 station.barometer_unit, station.temperature_unit, 
                 station.rain_unit, station.wind_unit)
        
        # Add reception statistics if we can:
        try:
            _rx_list = station.getRX()
            print """        RECEPTION STATS:
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
            print """        BAROMETER CALIBRATION DATA:
          Current barometer reading:    %.3f inHg
          Altitude:                     %.0f feet
          Dew point:                    %.0f F
          Virtual temperature:          %.0f F
          Humidity correction factor:   %.0f
          Correction ratio:             %.3f
          Correction constant:          %+.3f inHg
          Gain:                         %.3f
          Offset:                       %.3f
          """   % tuple(_bar_list)
        except:
            pass
    
    finally:
        try:
            station.closePort()
        except:
            pass

def configure(config_dict):
    """Configure a VP using settings in a configuration dictionary"""
    
    print "Configuring weather station in the Davis Vantage family..."
    
    # Open up the weather station:
    station = weewx.VantagePro.VantagePro(**config_dict['VantagePro'])

    try:
        #=======================================================================
        # Configure the archive interval        
        #=======================================================================
        new_interval = config_dict['VantagePro'].get('archive_interval')
        if new_interval is None:
            print "Archive interval not found in configuration file. Nothing done."
        else:
            new_interval_seconds = int(new_interval)
            print "Old archive interval is %d seconds, new one is %d seconds." % (station.archive_interval, new_interval_seconds)
            if station.archive_interval == new_interval_seconds:
                print "Old and new archive intervals are the same. Nothing done."
            else:
                print "Proceeding will erase old archive records."
                ans = raw_input("Are you sure you want to proceed? (Y/n) ")
                if ans == 'Y' :
                    station.setArchiveInterval(new_interval_seconds)
                    print "Archive interval now set to %d seconds." % (station.archive_interval,)
                    # The Davis documentation implies that the log is cleared after
                    # changing the archive interval, but that doesn't seem to be the
                    # case. Clear it explicitly:
                    station.clearLog()
                    print "Archive records cleared."
                else:
                    print "Nothing done."
    
        print "---"
        #=======================================================================
        # Configure the bucket type
        #=======================================================================
        new_bucket = config_dict['VantagePro'].get('rain_bucket_type')
        if new_bucket is None:
            print "No rain bucket type found in configuration file. Nothing done."
        else:
            new_bucket_type = int(new_bucket)
            print "Old rain bucket type is %d (%s), new one is %d (%s)." % (station.rain_bucket_type, station.rain_bucket_size,
                                                                                      new_bucket_type, VantagePro.rain_bucket_dict[new_bucket_type])
            if station.rain_bucket_type == new_bucket_type:
                print "Old and new bucket types are the same. Nothing done."
            else:
                print "Proceeding will change the rain bucket type."
                ans = raw_input("Are you sure you want to proceed? (Y/n) ")
                if ans == 'Y' :
                    station.setBucketType(new_bucket_type)
                    print "Bucket type now set to %d." % (station.rain_bucket_type,)
                else:
                    print "Nothing done."

        print "---"
        #=======================================================================
        # Configure the rain season start
        #=======================================================================
        rain_year_start = config_dict['Station'].get('rain_year_start')
        if rain_year_start is None:
            print "No rain year start found in configuration file. Nothing done."
        else:
            rain_year_start = int(rain_year_start)
            print "Old rain season start is %d, new one is %d." % (station.rain_season_start, rain_year_start)
            if station.rain_season_start == rain_year_start:
                print "Old and new rain season starts are the same. Nothing done."
            else:
                print "Proceeding will change the rain season start."
                ans = raw_input("Are you sure you want to proceed? (Y/n) ")
                if ans == 'Y' :
                    station.setRainSeasonStart(rain_year_start)
                    print "Rain season start now set to %d." % (station.rain_season_start,)
                else:
                    print "Nothing done."

    
        print "---"

        #=======================================================================
        # Configure the barometer calibrations
        #=======================================================================
        print "BAROMETER AND ALTITUDE CALIBRATION"
        altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', None))
        if altitude_t is None:
            print "No altitude information found in configuration file. Nothing done."
        else:
            # This test is in here to catch any old-style altitudes:
            if len(altitude_t) < 2:
                altitude_t=(float(altitude_t[0]), 'foot')
            
            # Form a value-tuple:
            altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
            # Convert to feet, if necessary:
            new_altitude = int(weewx.units.convert(altitude_vt, 'foot')[0])

            # Hit the console to get the current barometer calibration data:
            _bardata = station.getBarData()
            
            old_altitude = _bardata[1]

            current_barometer_inHg = _bardata[0]
            current_barometer_mbar = weewx.units.convert((current_barometer_inHg, 'inHg', 'group_pressure'), 'mbar')[0]

            print "For the following, you have three choices:\n"\
            " 1. If you have a current barometer reading from a very reliable nearby\n"\
            "    reference, you can use it to calibrate the barometer in your station.\n"\
            "    In this case, give the value and the unit it is in.\n"\
            "       Examples: \'30.15 inHg\'\n"\
            "                 \'1024.5 mbar\'\n"\
            "    (The console is currently reading %.3f inHg or %.1f mbar)\n"\
            " 2. If you do not have such a reading, then you can use a value of zero,\n"\
            "    which will result in a default, sensible calibration.\n"\
            " 3. Finally, you can simply hit <enter>, which will leave the current calibration\n"\
            "    value unchanged." % (current_barometer_inHg, current_barometer_mbar)
            while True:
                ans = raw_input("""Response: """)
                if ans.strip()=='':
                    new_barometer_inHg = current_barometer_inHg
                    break
                else:
                    ans_t = ans.split()
                    new_val = float(ans_t[0])
                    if new_val == 0:
                        new_barometer_inHg = 0
                        break
                    else:
                        try:
                            new_barometer_inHg = weewx.units.convert((new_val, ans_t[1], 'group_pressure'), 'inHg')[0]
                            break
                        except:
                            print "Invalid or missing units. Try again."
                    
            if new_barometer_inHg == 0:
                print "A sensible calibration will be picked."
            else:
                print "Calibrated pressure will be %.3f inHg" % (new_barometer_inHg,)

            print "Altitude will be %d feet." % int(new_altitude)
            if old_altitude == new_altitude and new_barometer_inHg == current_barometer_inHg:
                print "Old and new altitudes and barometer settings are the same. Nothing done."
            else:
                print "Proceeding will change the altitude and/or barometer calibration."
                ans = raw_input("Are you sure you want to proceed? (Y/n) ")
                if ans == 'Y' :
                    station.setBarData(new_barometer_inHg, new_altitude)
                    # Hit the console again and print out the new results:
                    _bardata = station.getBarData()
                    print "New altitude is %.0f feet, new barometer reading is %.3f inHg" % (_bardata[1], _bardata[0])
                else:
                    print "Nothing done."
    
    finally:
        try:
            station.closePort()
        except:
            pass

def clear(config_dict):
    """Clear the archive memory of a VantagePro"""
    
    print "Clearing the archive memory ..."
    # Open up the weather station:
    station = weewx.VantagePro.VantagePro(**config_dict['VantagePro'])
    try:
        print "Proceeding will erase old archive records."
        ans = raw_input("Are you sure you wish to proceed? (Y/n) ")
        if ans == 'Y':
            station.clearLog()
            print "Archive records cleared."
        else:
            print "Nothing done."
    finally:
        try:
            station.closePort()
        except:
            pass
