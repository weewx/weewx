#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""classes and functions for interfacing with a Davis VantagePro or VantagePro2"""
from __future__ import with_statement
import serial
import struct
import syslog
import time

from weewx.crc16 import crc16
import weeutil.weeutil
import weewx
import weewx.accum
import weewx.wxformulas
    
# A few handy constants:
_ack    = chr(0x06)
_resend = chr(0x21)

# Unfortunately, package serial does not take advantage of the "with" transaction
# semantics. So, we'll provide it ourself. This will insure that the serial connection
# to the VP2 gets closed despite any exceptions
class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""
    
    def __init__(self, port, baudrate, timeout):
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        
    def __enter__(self):
        self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        return self.serial_port
    
    def __exit__(self, etyp, einst, etb):
        try:
            # This will cancel any pending loop:
            _wakeup_console(self.serial_port)
            self.serial_port.close()
        except:
            pass

class VantagePro (object) :
    """Class that represents a connection to a VantagePro console."""

    # List of types for which archive records will be explicitly calculated
    # from LOOP data:
    special = ['consBatteryVoltage']

    def __init__(self, **vp_dict) :
        """Initialize an object of type VantagePro. 
        
        NAMED ARGUMENTS:
        
        port: The serial port of the VP. [Required]
        
        baudrate: Baudrate of the port. [Optional. Default 19200]
        
        timeout: How long to wait before giving up on a response from the
        serial port. [Optional. Default is 5]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 1.2 seconds]

        max_tries: How many times to try again before giving up. [Optional.
        Default is 4]
        
        archive_delay: How long to wait after an archive record is due
        before retrieving it. [Optional. Default is 15 seconds]
        
        max_drift: Maximum drift allowed on the on board VP clock before
        it will be corrected. [Optional. Default is 5 seconds]

        iss_id: The station number of the ISS [Optional. Default is 1]
        
        unit_system: What unit system to use on the VP. [Optional.
        Default is 1 (US Customary), and the only system supported
        in this version.]
        """
        # TODO: These values should really be retrieved dynamically from the VP:
        self.iss_id           = int(vp_dict.get('iss_id', 1))
        self.model_type       = 2 # = 1 for original VantagePro, = 2 for VP2

        # These come from the configuration dictionary:
        self.port             = vp_dict['port']
        self.baudrate         = int(vp_dict.get('baudrate'     , 19200))
        self.timeout          = float(vp_dict.get('timeout', 5.0))
        self.wait_before_retry= float(vp_dict.get('wait_before_retry', 1.2))
        self.max_tries        = int(vp_dict.get('max_tries'    , 4))
        self.archive_delay    = int(vp_dict.get('archive_delay', 15))
        self.max_drift        = int(vp_dict.get('max_drift'    , 5))
        self.unit_system      = int(vp_dict.get('unit_system'  , 1))

        # Get the archive interval dynamically:
        self.archive_interval = self.getArchiveInterval()
        
    def genLoopPackets(self):
        """Generator function that returns loop packets until the next archive record is due."""

        # Next time to ask for archive records:
        nextArchive_ts = (int(time.time() / self.archive_interval) + 1) *\
                            self.archive_interval + self.archive_delay
        
        while True:
            # Get LOOP packets in big batches, then cancel as necessary when the expiration
            # time is up. This is necessary because there is an undocumented limit to how
            # many LOOP records you can for on the VP (somewhere around 220).
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

    def genDavisLoopPackets(self, N = 1):
        """Generator function to return N LoopPacket objects from a VantagePro console
        
        N: The number of packets to generate [default is 1]
        
        yields: up to N DavisLoopPacket objects
        """

        syslog.syslog(syslog.LOG_DEBUG, "VantagePro: Requesting %d LOOP packets." % N)
        
        # Open up the serial port. It will automatically be closed if an 
        # exception is raised:
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:

            _wakeup_console(serial_port, self.max_tries, self.wait_before_retry)
            
            # Request N packets:
            _send_data(serial_port, "LOOP %d\n" % N)
            
            for loop in xrange(N) :
                
                for count in xrange(self.max_tries):
                    # Fetch a packet
                    buffer = serial_port.read(99)
                    if len(buffer) != 99 :
                        syslog.syslog(syslog.LOG_DEBUG, 
                                      "VantagePro: LOOP #%d; buffer not full (%d)... retrying" % (loop,len(buffer)))
                        continue
                    # ... decode it
                    pkt_dict = DavisLoopPacket(buffer[:89])
                    # Yield it
                    yield pkt_dict
                    break
                else:
                    syslog.syslog(syslog.LOG_ERR, 
                                  "VantagePro: Max retries exceeded while getting LOOP packets")
                    raise weewx.RetriesExceeded, "While getting LOOP packets"

    def genArchivePackets(self, since_ts):
        """A generator function to return archive packets from a VantagePro station.
        
        since_ts: A timestamp. All data since (but not including) this time will be returned.
        Pass in None for all data
        
        yields: a sequence of DavisArchivePackets containing the data
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
        
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:

            # Retry the dump up to max_tries times
            for _count in xrange(self.max_tries) :
                try :
                    # Wake up the console...
                    _wakeup_console(serial_port, self.max_tries, self.wait_before_retry)
                    # ... request a dump...
                    _send_data(serial_port, 'DMPAFT\n')
                    # ... from the designated date:
                    _send_data_with_crc16(serial_port, _datestr, self.max_tries)
                    
                    # Get the response with how many pages and starting index and decode it:
                    _buffer = _get_data_with_crc16(serial_port, 6, max_tries=self.max_tries)
                    (_npages, _start_index) = struct.unpack("<HH", _buffer[:4])
                  
                    syslog.syslog(syslog.LOG_DEBUG, "VantagePro: Retrieving %d page(s); starting index= %d" % (_npages, _start_index))
                    
                    # Cycle through the pages...
                    for _ipage in xrange(_npages) :
                        # ... get a page of archive data
                        _page = _get_data_with_crc16(serial_port, 267, prompt=_ack, max_tries=self.max_tries)
                        # Now extract each record from the page
                        for _index in xrange(_start_index, 5) :
                            # If the console has been recently initialized, there will
                            # be unused records, which are filled with 0xff:
                            if _page[1+52*_index:53+52*_index] == 52*chr(0xff) :
                                # This record has never been used. We're done.
                                return
                            # Create a new instance to hold the data
                            _packet = DavisArchivePacket(_page[1+52*_index:53+52*_index], self)
                            _record = self.translateArchivePacket(_packet)
                            # Check to see if the time stamps are declining, which would
                            # signal this is a wrap around record on the last page
                            if _record['dateTime'] <= _last_good_ts :
                                # The time stamp is declining. We're done.
                                return
                            # Add any LOOP data we've been accumulating:
                            self.archiveAccumulators(_record)
                            # Set the last time to the current time, and yield the packet
                            _last_good_ts = _record['dateTime']
                            yield _record
                        _start_index = 0
                    return
                except weewx.WeeWxIOError:
                    # Caught an error. Keep retrying...
                    continue
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting archive packets")
            raise weewx.RetriesExceeded, "Max retries exceeded while getting archive packets"

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
            # Try again, calling myself recursively:
            self.accumulateLoop(physicalLOOPPacket)
            
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
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
    
            # Try up to 3 times:
            for _count in xrange(self.max_tries) :
                try :
                    # Wake up the console...
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    # ... request the time...
                    _send_data(serial_port, 'GETTIME\n')
                    # ... get the binary data. No prompt, only one try:
                    _buffer = _get_data_with_crc16(serial_port, 8, max_tries=1)
                    (sec, min, hr, day, mon, yr, crc) = struct.unpack("<bbbbbbH", _buffer)
                    time_tt = (yr+1900, mon, day, hr, min, sec, 0, 0, -1)
                    return time_tt
                except weewx.WeeWxIOError :
                    # Caught an error. Keep retrying...
                    continue
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting time")
            raise weewx.RetriesExceeded, "While getting console time"
            
    def setTime(self, newtime_tt = None) :
        """Set the clock on the Davis VantagePro console
        
        newtime_tt: A time tuple with the time to which the
        clock should be set. If 'None', then the host's time will 
        be used. In this case, if the clock has drifted less than
        maxdiff seconds, nothing is done. """
        # Unfortunately, this algorithm takes a little while to execute, so the clock
        # usually ends up a few hundred milliseconds slow
        if newtime_tt is None:
            _hosttime_ts = time.time()
            _diff = time.mktime(self.getTime()) - _hosttime_ts
            syslog.syslog(syslog.LOG_INFO, 
                          "VantagePro: Clock error is %.2f seconds (positive is fast)" % _diff)
            if abs(_diff) < self.max_drift:
                return
            newtime_tt = time.localtime(int(_hosttime_ts + 0.5))
            
        # The Davis expects the time in reversed order, and the year is since 1900
        _buffer = struct.pack("<bbbbbb", newtime_tt[5], newtime_tt[4], newtime_tt[3], newtime_tt[2],
                                         newtime_tt[1], newtime_tt[0] - 1900)
            
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
            for _count in xrange(self.max_tries) :
                try :
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    _send_data(serial_port, 'SETTIME\n')
                    _send_data_with_crc16(serial_port, _buffer, max_tries=self.max_tries)
                    syslog.syslog(syslog.LOG_NOTICE,
                                  "VantagePro: Clock set to %s (%d)" % (time.asctime(newtime_tt), 
                                                                       time.mktime(newtime_tt)) )
                    return
                except weewx.WeeWxIOError :
                    # Caught an error. Keep retrying...
                    continue
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while setting time")
            raise weewx.RetriesExceeded, "While setting console time"
    
    def setArchiveInterval(self, archive_interval):
        """Set the archive interval of the VantagePro.
        
        archive_interval_sec: The new interval to use. Must be one of 
        1, 5, 10, 15, 30, 60, or 120.
        """
        
        # Convert to minutes:
        archive_interval_minutes = int(archive_interval / 60)
        
        if archive_interval_minutes not in (1, 5, 10, 15, 30, 60, 120):
            raise weewx.ViolatedPrecondition, "VantagePro: Invalid archive interval (%f)" % archive_interval

        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
            for _count in xrange(self.max_tries):
                try :
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                
                    # The Davis documentation is wrong about the SETPER command.
                    # It actually returns an 'OK', not an <ACK>
                    serial_port.write('SETPER %d\n' % archive_interval_minutes)
                    # Takes a bit for the VP to react and fill up the buffer. Sleep for a sec
                    time.sleep(1)
                    # Can't use function serial.readline() because the VP responds with \n\r, not just \n.
                    # So, instead find how many bytes are waiting and fetch them all
                    nc = serial_port.inWaiting()
                    _buffer = serial_port.read(nc)
                    # Split the buffer on white space
                    rx_list = _buffer.split()
                    # The first member should be the 'OK' in the VP response
                    if len(rx_list) == 1 and rx_list[0] == 'OK' :
                        self.archive_interval = archive_interval_minutes * 60
                        syslog.syslog(syslog.LOG_NOTICE, "VantagePro: archive interval set to %d" % (self.archive_interval,))
                        return
    
                except weewx.WeeWxIOError:
                    # Caught an error. Keep trying...
                    continue
            
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while setting archive interval")
            raise weewx.RetriesExceeded, "While setting archive interval"
    
    def clearLog(self):
        """Clear the internal archive memory in the VantagePro."""
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
            for _count in xrange(self.max_tries):
                try:
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    _send_data(serial_port, "CLRLOG\n")
                    syslog.syslog(syslog.LOG_NOTICE, "VantagePro: Archive memory cleared.")
                    return
                except weewx.WeeWxIOError:
                    #Caught an error. Keey trying...
                    continue
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while clearing log")
            raise weewx.RetriesExceeded
    
    def getArchiveInterval(self):
        """Return the present archive interval in seconds."""
        
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
            for _count in xrange(self.max_tries):
                try :
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    _send_data(serial_port, "EEBRD 2D 01\n")
                    # ... get the binary data. No prompt, only one try:
                    _buffer = _get_data_with_crc16(serial_port, 3, max_tries=1)
                    _archive_interval = ord(_buffer[0]) * 60
                    return _archive_interval
                except weewx.WeeWxIOError:
                    # Caught an error. Keep trying...
                    continue
            
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting archive interval")
            raise weewx.RetriesExceeded, "While getting archive interval"
        
        
    def getRX(self) :
        """Returns reception statistics from the console.
        
        Returns a tuple with 5 values: (# of packets, # of missed packets,
        # of resynchronizations, the max # of packets received w/o an error,
        the # of CRC errors detected.)"""
        
        with SerialWrapper(self.port, self.baudrate, self.timeout) as serial_port:
            for _count in xrange(self.max_tries) :
                try :
                    _wakeup_console(serial_port, max_tries=self.max_tries, wait_before_retry=self.wait_before_retry)
                    # Can't use function _send_data because the VP doesn't respond with an 
                    # ACK for this command, it responds with 'OK'. Go figure.
                    serial_port.write('RXCHECK\n')
                    # Takes a bit for the VP to react and fill up the buffer. Sleep for 
                    # half a sec
                    time.sleep(0.5)
                    # Can't use function serial.readline() because the VP responds with \n\r, not just \n.
                    # So, instead find how many bytes are waiting and fetch them all
                    nc=serial_port.inWaiting()
                    _buffer = serial_port.read(nc)
                    # Split the buffer on white space
                    rx_list = _buffer.split()
                    # The first member should be the 'OK' in the VP response
                    if len(rx_list) == 6 and rx_list[0] == 'OK' : return rx_list[1:]
                except weewx.WeeWxIOError:
                    # Caught an error. Keep retrying...
                    continue
            syslog.syslog(syslog.LOG_ERR, "VantagePro: Max retries exceeded while getting RX data")
            raise weewx.RetriesExceeded, "While getting RX data"

    def config(self, config_dict):
        
        _archive_interval = int(config_dict.get('archive_interval', 300))
        _old_interval = self.getArchiveInterval()
        if _old_interval != _archive_interval:
            self.setArchiveInterval(_archive_interval)
            self.clearLog()

        # TODO: This would be the place to set latitude, longitude, and altitude
        
    def translateLoopPacket(self, loopPacket):
        """Given a LOOP packet in vendor units, this function translates to physical units.
        
        loopPacket: An instance of DavisLoopPacket
        
        returns: A dictionary with the values in physical units.
        """
        # Right now, only US customary units are supported
        if self.unit_system == weewx.US :
            _record = self.translateLoopToUS(loopPacket)
        else :
            raise weewx.UnsupportedFeature, "Only US Customary Units are supported on the Davis VP2."
        
        return _record
    

    def translateLoopToUS(self, packet):
        """Translates a loop packet from the internal units used by Davis, into US Customary Units.
        
        packet: An instance of DavisLoopPacket.
        
        returns: A dictionary with the values in US Customary Units.
        """
        # This dictionary maps a type key to a function. The function should be able to
        # decode a sensor value held in the loop packet in the internal, Davis form into US
        # units and return it. From the Davis documentation, it's not clear what the
        # 'dash' value is for some of these, so I'm assuming it's the same as for an archive
        # packet.
    
        _loop_map = {'dateTime'        : lambda v : v,
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
                     'UV'              : _little_val, 
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
                     'txBatteryStatus' : _null_int, 
                     'consBatteryVoltage'  : lambda v : float((v * 300) >> 9) / 100.0
                     }        
    
        if packet['usUnits'] != weewx.US :
            raise weewx.ViolatedPrecondition, "Unit system on the VantagePro must be US Customary Units only"
    
        record = {}
        
        for _type in _loop_map.keys() :    
            # Get the mapping function needed for this key
            func = _loop_map[_type]
            # Call it, with the value as an argument
            fv = func(packet[_type])
            # Store the results
            record[_type] = fv
    
        # Add a few derived values that are not in the packet itself.
        T = record['outTemp']
        R = record['outHumidity']
        W = record['windSpeed']
    
        record['dewpoint']    = weewx.wxformulas.dewpointF(T, R)
        record['heatindex']   = weewx.wxformulas.heatindexF(T, R)
        record['windchill']   = weewx.wxformulas.windchillF(T, W)
        
        final_record = self.errorCheck(record)
        
        return final_record

    def errorCheck(self, record):
        """Final (optional) sanity check of any data before being returned."""
        
        # This would be the place to do any processing for crazy numbers
        # (e.g., temperatures in hundreds) and replace them with None.
        return record
    
    def translateArchivePacket(self, packet):
        """Translates an archive packet from the internal units used by Davis, into physical units.
        
        packet: An instance of DavisArchivePacket.
        
        returns: A dictionary with the values in physical units.
        """
        
        # Right now, only US units are supported
        if self.unit_system == weewx.US :
            _record = self.translateArchiveToUS(packet)
        else :
            raise weewx.UnsupportedFeature, "Only US Units are supported on the Davis VP2."
        
        return _record
    
    def translateArchiveToUS(self, packet):
        """Translates an archive packet from the internal units used by Davis, into US units.
        
        packet: An instance of DavisArchivePacket.
        
        returns: A dictionary with the values in US units.
        
        """
        # This dictionary maps a type key to a function. The function should be able to
        # decode a sensor value held in the archive packet in the internal, Davis form into US
        # units and return it. Some of these functions use a short hand 'lambda' form because 
        # they are trivial and because I think lambda functions are cool.
        _archive_map={'interval'       : lambda v : int(v),
                      'barometer'      : _val1000Zero, 
                      'inTemp'         : _big_val10,
                      'outTemp'        : _big_val10,
                      'inHumidity'     : _little_val,
                      'outHumidity'    : _little_val,
                      'windSpeed'      : _little_val,
                      'windDir'        : _windDir,
                      'windGust'       : _null,
                      'windGustDir'    : _windDir,
                      'rain'           : _val100,
                      'rainRate'       : _val100,
                      'ET'             : _val1000,
                      'radiation'      : _big_val,
                      'UV'             : _little_val10,
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
                      'rxCheckPercent' : _null}
    
        if packet['usUnits'] != weewx.US :
            raise weewx.ViolatedPrecondition, "Unit system on the VantagePro must be U.S. units only"
    
        record = {}
        
        for _type in _archive_map.keys() :    
            # Get the mapping function needed for this key
            func = _archive_map[_type]
            # Call it, with the value as an argument
            fv = func(packet[_type])
            # Store the results
            record[_type] = fv
    
        # Add a few derived values that are not in the packet itself.
        T = record['outTemp']
        R = record['outHumidity']
        W = record['windSpeed']
    
        record['dewpoint']    = weewx.wxformulas.dewpointF(T, R)
        record['heatindex']   = weewx.wxformulas.heatindexF(T, R)
        record['windchill']   = weewx.wxformulas.windchillF(T, W)
        record['dateTime']    = _archive_datetime(packet)
        record['dateTimeStr'] = time.ctime(record['dateTime'])
        record['usUnits']     = weewx.US
        
        # This would be the place to do any processing for crazy numbers
        # (e.g., temperatures in hundreds) and replace them with None.
        
        return record

#===============================================================================
#          Primitives for working with the Davis Console
#===============================================================================

def _wakeup_console(serial_port, max_tries=3, wait_before_retry=1.2):
    """ Wake up a Davis VantagePro console."""
    
    # Wake up the console. Try up to max_tries times
    for _count in xrange(max_tries) :
        # Clear out any pending input or output characters:
        serial_port.flushOutput()
        serial_port.flushInput()
        # It can be hard to get the console's attention, particularly
        # when in the middle of a LOOP command. Send a whole bunch of line feeds,
        # then flush everything, then look for the \n\r acknowledgment
        serial_port.write('\n\n\n')
        time.sleep(0.5)
        serial_port.flushInput()
        serial_port.write('\n')
        _resp = serial_port.read(2)
        if _resp == '\n\r' : break
        print "Unable to wake up console... sleeping"
        time.sleep(wait_before_retry)
        print "Unable to wake up console... retrying"
    else :
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to wake up console")
        raise weewx.WakeupError, "Unable to wake up VantagePro console"

    syslog.syslog(syslog.LOG_DEBUG, "VantagePro: successfully woke up console")


def _send_data(serial_port, data):
    """Send data to the Davis console, waiting for an acknowledging <ack> 
    
    data: The data to send, as a string
    """
    serial_port.write(data)
    
    # Look for the acknowledging ACK character
    _resp = serial_port.read()
    if _resp != _ack : 
        syslog.syslog(syslog.LOG_ERR, "VantagePro: No <ACK> received from console")
        raise weewx.AckError, "No <ACK> received from VantagePro console"
    
def _send_data_with_crc16(serial_port, data, max_tries=3) :
    """Send data to the Davis console along with a CRC check, waiting for an acknowledging <ack>.
    If none received, resend up to 3 times.
    
    data: The data to send, as a string
    
    """
    
    #Calculate the crc for the data:
    _crc = crc16(data)
    
    # ...and pack that on to the end of the data in big-endian order:
    _data_with_crc = data + struct.pack(">H", _crc)
    
    # Retry up to max_tries times:
    for _count in xrange(max_tries) :
        serial_port.write(_data_with_crc)
        # Look for the acknowledgment.
        _resp = serial_port.read()
        if _resp == _ack : break
    else :
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to pass CRC16 check while sending data")
        raise weewx.CRCError, "Unable to pass CRC16 check while sending data to VantagePro console"


def _get_data_with_crc16(serial_port, nbytes, prompt=None, max_tries=3) :
    """Get a packet of data and do a CRC16 check on it, asking for retransmit if necessary.
    
    It is guaranteed that the length of the returned data will be of the requested length.
    An exception of type CRCError will be thrown if the data cannot pass the CRC test
    in the requested number of retries.
    
    nbytes: The number of bytes (including the 2 byte CRC) to get. 
    
    prompt: Any string to be sent before requesting the data. Default=None
    
    max_tries: Number of tries before giving up. Default=3
    
    returns: the packet data as a string
    
    """
    if prompt :
        serial_port.write(prompt)
        
    for _count in xrange(max_tries):
        _buffer = serial_port.read(nbytes)
        # If the right amount of data was returned and it passes the CRC check,
        # return it. Otherwise, signal to resend
        if len(_buffer) == nbytes and crc16(_buffer) == 0 : 
            return _buffer
        serial_port.write(_resend)
    else :
        syslog.syslog(syslog.LOG_ERR, "VantagePro: Unable to pass CRC16 check while getting data")
        raise weewx.CRCError, "Unable to pass CRC16 check while getting data from VantagePro console"


#===============================================================================
#                         class DavisLoopPacket
#===============================================================================

class DavisLoopPacket(dict) :
    """Holds a loop packet's worth of data as a dictionary.
    
    """

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
               'txBatteryStatus', 'consBatteryVoltage')

    loop_format = struct.Struct("<3sbBHHHBHBBH7B4B4BB7BHBHHHHHHHHH4B4B16xBH")
    
    def __init__(self, packet):
        """Create a new DavisLoopPacket from a buffer's worth of data from a Davis VantagePro
    
        packet: The loop packet data as a string. This will be unpacked and the results placed
        in the dictionary inherited by LoopPacket
    
        """
        # Unpack the data, using the compiled stuct.Struct string 'loop_format'
        data_tuple = DavisLoopPacket.loop_format.unpack(packet)
        
        assert(len(data_tuple) == len(DavisLoopPacket.vp2loop))
        
        for k,v in zip(DavisLoopPacket.vp2loop, data_tuple) :
            self[k] = v

        # Detect the kind of LOOP packet. Type 'A' has the character 'P' in this
        # position. Type 'B' contains the 3-hour barometer trend in this position.
        if self['loop_type'] == ord('P'):
            self['trend'] = None
            self['loop_type'] = 'A'
        else :
            self['trend'] = self['loop_type']
            self['loop_type'] = 'B'

        # Add a timestamp:
        self['dateTime'] = int(time.time() + 0.5)

        # As far as I know, the Davis supports only US units:
        self['usUnits'] = weewx.US



#===============================================================================
#                         class DavisArchivePacket
#===============================================================================

class DavisArchivePacket(dict):
    """Decode a Davis archive packet, holding the results as a dictionary. 
    
    """
    
    # A tuple of all the types held in a VantagePro2 Rev B archive record in their native order.
    # TODO: Extend to Rev A type archive records
    vp2archB =('date_stamp', 'time_stamp', 'outTemp', 'high_outside_temperature', 'low_outside_temperature',
               'rain', 'rainRate', 'barometer', 'radiation', 'number_of_wind_samples',
               'inTemp', 'inHumidity', 'outHumidity', 'windSpeed', 'windGust', 'windGustDir', 'windDir',
               'UV', 'ET', 'high_solar_radiation', 'high_uv_index', 'forecast_rule',
               'leafTemp1', 'leafTemp2', 'leafWet1', 'leafWet2',
               'soilTemp1', 'soilTemp2', 'soilTemp3','soilTemp4', 'download_record_type',
               'extraHumid1', 'extraHumid2', 'extraTemp1', 'extraTemp2', 'extraTemp3',
               'soilMoist1', 'soilMoist2', 'soilMoist3', 'soilMoist4')
    
    loop_format = struct.Struct("<HHHHHHHHHHHBBBBBBBBHBB2B2B4BB2B3B4B")
    
    def __init__(self, packet, station):
        """Create a new DavisArchivePacket from a buffer's worth of data from a Davis VantagePro
    
        packet: The loop packet data buffer, passed in as a string. This will be unpacked and 
        the results placed in the dictionary inherited by DavisArchivePacket"""
        # TODO: Add Rev A style packets.
        
        # Check that this is a Rev B style packet. We don't know how to handle any others
        record_type = ord(packet[42])
        if record_type != 0x0000 :
            raise weewx.UnknownArchiveType, "Unknown archive type = 0x%x" % record_type 
        
        data_tuple = DavisArchivePacket.loop_format.unpack(packet)
        
        assert(len(data_tuple) == len(DavisArchivePacket.vp2archB))
        
        for k,v in zip(DavisArchivePacket.vp2archB, data_tuple) :
            self[k] = v
            
        # Augment the data types with these extras
        
        # Divide archive interval by 60 to keep consistent with wview
        self['interval']       = station.archive_interval / 60 
        # As far as I know, the Davis supports only US units:
        self['usUnits']        = weewx.US
        self['model_type']     = station.model_type
        self['iss_id']         = station.iss_id
        self['rxCheckPercent'] = self._rxcheck()
        
        # Sanity check that this is in fact a Rev B archive:
        assert(self['download_record_type'] == 0)

    def _rxcheck(self):
        """Gives an estimate of the fraction of packets received.
        
        Ref: Vantage Serial Protocol doc, V2.1.0, released 25-Jan-05; p42
        
        """
        # The formula for the expected # of packets varies with model number.
        if self['model_type'] == 1 :
            _expected_packets = float(self['interval'] * 60) / ( 2.5 + (self['iss_id']-1) / 16.0) -\
                                float(self['interval'] * 60) / (50.0 + (self['iss_id']-1) * 1.25)
        if self['model_type'] == 2 :
            _expected_packets = 960.0 * self['interval'] / float(41 + self['iss_id'] - 1)
        else :
            return None
        _frac = self['number_of_wind_samples'] * 100.0 / _expected_packets
        if _frac > 100.0 :
            _frac = 100.0
        return _frac

#===============================================================================
#                      Decoding routines
#===============================================================================

def _archive_datetime(packet) :
    """Returns the epoch time of the archive packet.
    
    """
    datestamp = packet['date_stamp']
    timestamp = packet['time_stamp']
    
    # Decode the Davis time, constructing a time-tuple from it:
    time_tuple = ((0xfe00 & datestamp) >> 9,    # year
                  (0x01e0 & datestamp) >> 5,    # month
                  (0x001f & datestamp),         # day
                  timestamp / 100,              # hour
                  timestamp % 100,              # minute
                  0,                            # second
                  0, 0, -1)
    # Convert to epoch time:
    return int(time.mktime(time_tuple))
    
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
    return int(time.mktime(time_tuple))
    
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

def _null(v) :
    return float(v)

def _null_int(v):
    return int(v)

def _windDir(v):
    return float(v) * 22.5 if v!= 0x00ff else None

if __name__ == '__main__':
    import configobj
    from optparse import OptionParser
    
    usagestr = """%prog: config_path

    Configuration utility for a Davis VantagePro.
    
    Sets the archive time interval. In the future, may set other
    things such as altitude, lat, lon, etc.

    Arguments:
        config_path: Path to the configuration file to be used."""
    parser = OptionParser(usage=usagestr)
    (options, args) = parser.parse_args()

    if len(args) < 1:
        print "Missing argument(s)."
        print parser.parse_args(["--help"])
        exit()
    
    config_path = args[0]

    syslog.openlog('VantagePro_configuration', syslog.LOG_PID|syslog.LOG_CONS, syslog.LOG_USER|syslog.LOG_INFO)

    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print "Unable to open configuration file ", config_path
        exit()
        
    ans = raw_input("about to configure VantagePro. OK (y/n)? ")
    if ans == 'y' :
        # Open up the weather station:
        station = VantagePro(config_dict['VantagePro'])
        station.config(config_dict)
        print "Done."
    else :
        print "Nothing done."



