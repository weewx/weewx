#!/usr/bin/python
# $Id$
#
# Copyright 2013 Matthew Wall
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
# Thanks to Kenneth Lavrsen for the Open2300 implementation:
#   http://www.lavrsen.dk/foswiki/bin/view/Open2300/WebHome
# description of the station communication interface:
#   http://www.lavrsen.dk/foswiki/bin/view/Open2300/OpenWSAPI
# memory map:
#   http://www.lavrsen.dk/foswiki/bin/view/Open2300/OpenWSMemoryMap
#
# Thanks to Russell Stuart for the ws2300 python implementation:
#   http://ace-host.stuart.id.au/russell/files/ws2300/
# and the map of the station memory:
#   http://ace-host.stuart.id.au/russell/files/ws2300/memory_map_2300.txt
#
# This immplementation copies directly from Russell Stuart's implementation,
# but only the parts required to read from and write to the weather station.

"""Classes and functions for interfacing with WS-23xx weather stations.

LaCrosse made a number of stations in the 23xx series, including:

  WS-2300, WS-2308, WS-2310, WS-2315, WS-2317, WS-2357

The stations were also sold as the TFA Dostman and TechnoLine 2350.

Configuration

The station supports both wireless and wired communication between the sensors
and a station console.  Wired connection updates data every 8 seconds.
Wireless connection updates data in 16 to 128 second intervals, depending on
wind speed and rain activity.

It is possible to increase the rate of wireless updates:

  http://www.wikihow.com/Modify-a-Lacrosse-Ws2300-for-Frequent-Wireless-Updates

This implementation polls the station.  Use the polling_interval parameter
to specify how often to poll for data.

The station has a serial connection to the computer.

Instruments are connected by unshielded phone cables.  To reduce the number of
spikes in data, replace with shielded cables.

USB-Serial Converters

With a USB-serial converter one can connect the station to a computer with
only USB ports, but not every converter will work properly.  Perhaps the two
most common converters are based on the Prolific and LTDI chipsets.  Many
people report better luck with the LTDI-based converters.  Some converters
that use the Prolific chipset (PL2303) will work, but not all of them.

Known to work: ATEN UC-232A

"""

# FIXME: add option to calculate dewpoint instead of using station value
# FIXME: add option to calculate windchill instead of using station value

import optparse
import syslog
import time

import fcntl
import math
import os
import select
import struct
import tty

import weeutil
import weewx.abstractstation
import weewx.wxformulas

DRIVER_VERSION = '0.2'

DEFAULT_PORT = '/dev/ttyUSB0'

def logmsg(dst, msg):
    syslog.syslog(dst, 'ws23xx: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def loader(config_dict, engine):
    altitude_m = getaltitudeM(config_dict)
    station = WS23xx(altitude=altitude_m, **config_dict['WS23xx'])
    return station

# FIXME: the pressure calculations belong in wxformulas

# noaa definitions for station pressure, altimeter setting, and sea level
# http://www.crh.noaa.gov/bou/awebphp/definitions_pressure.php

# implementation copied from wview
def sp2ap(sp_mbar, elev_meter):
    """Convert station pressure to sea level pressure.
    http://www.wrh.noaa.gov/slc/projects/wxcalc/formulas/altimeterSetting.pdf

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    ap - sea level pressure (altimeter) in millibars
    """

    if sp_mbar is None or sp_mbar <= 0.3 or elev_meter is None:
        return None
    N = 0.190284
    slp = 1013.25
    ct = (slp ** N) * 0.0065 / 288
    vt = elev_meter / ((sp_mbar - 0.3) ** N)
    ap_mbar = (sp_mbar - 0.3) * ((ct * vt + 1) ** (1/N))
    return ap_mbar

# implementation copied from wview
def etterm(elev_meter, t_C):
    """Calculate elevation/temperature term for sea level calculation."""
    if elev_meter is None or t_C is None:
        return None
    t_K = t_C + 273.15
    return math.exp( - elev_meter / (t_K * 29.263))

def sp2bp(sp_mbar, elev_meter, t_C):
    """Convert station pressure to sea level pressure.

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    t_C - temperature in degrees Celsius

    bp - sea level pressure (barometer) in millibars
    """

    pt = etterm(elev_meter, t_C)
    if sp_mbar is None or pt is None:
        return None
    bp_mbar = sp_mbar / pt if pt != 0 else 0
    return bp_mbar

# FIXME: this goes in weeutil.weeutil or weewx.units
def getaltitudeM(config_dict):
    altitude_t = weeutil.weeutil.option_as_list(
        config_dict['Station'].get('altitude', (None, None)))
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    return altitude_m

# FIXME: this goes in weeutil.weeutil
def calculate_rain(newtotal, oldtotal):
    """Calculate the rain differential given two cumulative measurements."""
    if newtotal is not None and oldtotal is not None:
        if newtotal >= oldtotal:
            delta = newtotal - oldtotal
        else:
            delta = None
            logdbg('ignoring rain counter difference: counter decrement')
    else:
        delta = None
    return delta

class WS23xx(weewx.abstractstation.AbstractStation):
    """Driver for LaCrosse WS23xx stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        altitude: Altitude of the station
        [Required. No default]

        port: The serial port, e.g., /dev/ttyS0 or /dev/ttyUSB0
        [Required. Default is /dev/ttyS0]

        polling_interval: How often to poll the station, in seconds.
        [Optional. Default is 60]

        pressure_offset: Calibration offset in millibars for the station
        pressure sensor.  This offset is added to the station sensor output
        before barometer and altimeter pressures are calculated.
        [Optional. No Default]

        model: Which station model is this?
        [Optional. Default is 'LaCrosse WS23xx']
        """

        self.altitude          = stn_dict['altitude']
        self.port              = stn_dict.get('port', DEFAULT_PORT)
        self.polling_interval  = stn_dict.get('polling_interval', 60)
        self.model             = stn_dict.get('model', 'LaCrosse WS23xx')
        self.pressure_offset   = stn_dict.get('pressure_offset', None)
        if self.pressure_offset is not None:
            self.pressure_offset = float(self.pressure_offset)

        self._last_rain = None

    @property
    def hardware_name(self):
        return self.model

#    def closePort(self):
#        pass

    def genLoopPackets(self):
        while True:
            serial_port = LinuxSerialPort(self.port)
            packet = None
            try:
                data = WS23xx.get_raw_data(serial_port)
                packet = WS23xx.data_to_packet(data,
                                               altitude=self.altitude,
                                               pressure_offset=self.pressure_offset,
                                               last_rain=self._last_rain)
                self._last_rain = packet['rainTotal']
            finally:
                serial_port.close()
            if packet is not None:
                yield packet
            time.sleep(self.polling_interval)

#    def genArchiveRecords(self, since_ts):
#        pass

    @staticmethod
    def get_raw_data(serial_port):
        """get raw data from the station, return as dictionary"""

        ws = Ws2300(serial_port)
        labels = ['it','ih','ot','oh','pa','ws','wsh','w0','rh','rt','dp','wc']
        measures = [ Measure.IDS[m] for m in labels ]
        raw_data = read_measurements(ws, measures)
        data_dict = dict(zip(labels, [ m.conv.binary2value(d) for m, d in zip(measures, raw_data) ]))
        return data_dict

    @staticmethod
    def data_to_packet(data, altitude=0, pressure_offset=None, last_rain=None):
        """convert raw data to format and units required by weewx

                        station      weewx (metric)
        temperature     degree C     degree C
        humidity        percent      percent
        uv index        unitless     unitless
        pressure        mbar         mbar
        wind speed      m/s          km/h
        wind gust       m/s          km/h
        wind dir        degree       degree
        rain            mm           cm
        rain rate                    cm/h
        """

        packet = {}
        packet['usUnits'] = weewx.METRIC
        packet['dateTime'] = int(time.time() + 0.5)
        packet['inTemp'] = data['it']
        packet['inHumidity'] = data['ih']
        packet['outTemp'] = data['ot']
        packet['outHumidity'] = data['oh']
        packet['pressure'] = data['pa']
        packet['windSpeed'] = data['ws']
        if packet['windSpeed'] is not None:
            packet['windSpeed'] *= 3.6 # weewx wants km/h
        packet['windGust'] = data['wsh']
        if packet['windGust'] is not None:
            packet['windGust'] *= 3.6 # weewx wants km/h

        if packet['windSpeed'] is not None and packet['windSpeed'] > 0:
            packet['windDir'] = data['w0']
        else:
            packet['windDir'] = None

        if packet['windGust'] is not None and packet['windGust'] > 0:
            packet['windGustDir'] = data['w0']
        else:
            packet['windGustDir'] = None

        packet['rainTotal'] = data['rt']
        if packet['rainTotal'] is not None:
            packet['rainTotal'] /= 10 # weewx wants cm
        packet['rain'] = calculate_rain(packet['rainTotal'], last_rain)
        packet['rainRate'] = data['rh']
        if packet['rainRate'] is not None:
            packet['rainRate'] /= 10 # weewx wants cm/hr

        packet['heatindex'] = weewx.wxformulas.heatindexC(
            packet['outTemp'], packet['outHumidity'])
        packet['dewpoint'] = data['dp']
        packet['windchill'] = data['wc']

        # station reports gauge pressure, calculate other pressures
        adjp = packet['pressure']
        if pressure_offset is not None and adjp is not None:
            adjp += pressure_offset
        packet['barometer'] = sp2bp(adjp, altitude, packet['outTemp'])
        packet['altimeter'] = sp2ap(adjp, altitude)
        return packet


#==============================================================================
# The following code was adapted from ws2300.py by Russell Stuart
#==============================================================================

VERSION = "1.8 2013-08-26"

#
# Debug options.
#
DEBUG_SERIAL = False

#
# A fatal error.
#
class FatalError(StandardError):
    source = None
    message = None
    cause = None
    def __init__(self, source, message, cause=None):
        self.source = source
        self.message = message
        self.cause = cause
        StandardError.__init__(self, message)

#
# The serial port interface.  We can talk to the Ws2300 over anything
# that implements this interface.
#
class SerialPort(object):
    #
    # Discard all characters waiting to be read.
    #
    def clear(self): raise NotImplementedError()
    #
    # Close the serial port.
    #
    def close(self): raise NotImplementedError()
    #
    # Wait for all characters to be sent.
    #
    def flush(self): raise NotImplementedError()
    #
    # Read a character, waiting for a most timeout seconds.  Return the
    # character read, or None if the timeout occurred.
    #
    def read_byte(self, timeout): raise NotImplementedError()
    #
    # Release the serial port.  Closes it until it is used again, when
    # it is automatically re-opened.  It need not be implemented.
    #
    def release(self): pass
    #
    # Write characters to the serial port.
    #
    def write(self, data): raise NotImplementedError()

#
# A Linux Serial port.  Implements the Serial interface on Linux.
#
class LinuxSerialPort(SerialPort):
    SERIAL_CSIZE  = {
        "7":    tty.CS7,
        "8":    tty.CS8, }
    SERIAL_PARITIES= {
        "e":    tty.PARENB,
        "n":    0,
        "o":    tty.PARENB|tty.PARODD, }
    SERIAL_SPEEDS = {
        "300":    tty.B300,
        "600":    tty.B600,
        "1200":    tty.B1200,
        "2400":    tty.B2400,
        "4800":    tty.B4800,
        "9600":    tty.B9600,
        "19200":    tty.B19200,
        "38400":    tty.B38400,
        "57600":    tty.B57600,
        "115200":    tty.B115200, }
    SERIAL_SETTINGS = "2400,n,8,1"
    device = None        # string, the device name.
    orig_settings = None # class,  the original ports settings.
    select_list = None   # list,   The serial ports
    serial_port = None   # int,    OS handle to device.
    settings = None      # string, the settings on the command line.
    #
    # Initialise ourselves.
    #
    def __init__(self,device,settings=SERIAL_SETTINGS):
        self.device = device
        self.settings = settings.split(",")
        self.settings.extend([None,None,None])
        self.settings[0] = self.__class__.SERIAL_SPEEDS.get(self.settings[0], None)
        self.settings[1] = self.__class__.SERIAL_PARITIES.get(self.settings[1].lower(), None)
        self.settings[2] = self.__class__.SERIAL_CSIZE.get(self.settings[2], None)
        if len(self.settings) != 7 or None in self.settings[:3]:
            raise FatalError(self.device, 'Bad serial settings "%s".' % settings)
        self.settings = self.settings[:4]
        #
        # Open the port.
        #
        try:
            self.serial_port = os.open(self.device, os.O_RDWR)
        except EnvironmentError, e:
            raise FatalError(self.device, "can't open tty device - %s." % str(e))
        try:
            fcntl.flock(self.serial_port, fcntl.LOCK_EX)
            self.orig_settings = tty.tcgetattr(self.serial_port)
            setup = self.orig_settings[:]
            setup[0] = tty.INPCK
            setup[1] = 0
            setup[2] = tty.CREAD|tty.HUPCL|tty.CLOCAL|reduce(lambda x,y: x|y, self.settings[:3])
            setup[3] = 0        # tty.ICANON
            setup[4] = self.settings[0]
            setup[5] = self.settings[0]
            setup[6] = ['\000']*len(setup[6])
            setup[6][tty.VMIN] = 1
            setup[6][tty.VTIME] = 0
            tty.tcflush(self.serial_port, tty.TCIOFLUSH)
            #
            # Restart IO if stopped using software flow control (^S/^Q).  This
            # doesn't work on FreeBSD.
            #
            try:
                tty.tcflow(self.serial_port, tty.TCOON|tty.TCION)
            except termios.error:
                pass
            tty.tcsetattr(self.serial_port, tty.TCSAFLUSH, setup)
            #
            # Set DTR low and RTS high and leave other control lines untouched.
            #
            arg = struct.pack('I', 0)
            arg = fcntl.ioctl(self.serial_port, tty.TIOCMGET, arg)
            portstatus = struct.unpack('I', arg)[0]
            portstatus = portstatus & ~tty.TIOCM_DTR | tty.TIOCM_RTS
            arg = struct.pack('I', portstatus)
            fcntl.ioctl(self.serial_port, tty.TIOCMSET, arg)
            self.select_list = [self.serial_port]
        except Exception:
            os.close(self.serial_port)
            raise
    def close(self):
        if self.orig_settings:
            tty.tcsetattr(self.serial_port, tty.TCSANOW, self.orig_settings)
            os.close(self.serial_port)
    def read_byte(self, timeout):
        ready = select.select(self.select_list, [], [], timeout)
        if not ready[0]:
            return None
        return os.read(self.serial_port, 1)
    #
    # Write a string to the port.
    #
    def write(self, data):
        os.write(self.serial_port, data)
    #
    # Flush the input buffer.
    #
    def clear(self):
        tty.tcflush(self.serial_port, tty.TCIFLUSH)
    #
    # Flush the output buffer.
    #
    def flush(self):
        tty.tcdrain(self.serial_port)

#
# This class reads and writes bytes to a Ws2300.  It is passed something
# that implements the Serial interface.  The major routines are:
#
# Ws2300()     - Create one of these objects that talks over the serial port.
# read_batch() - Reads data from the device using an scatter/gather interface.
# write_safe() - Writes data to the device.
#
class Ws2300(object):
    #
    # An exception for us.
    #
    class Ws2300Exception(StandardError):
        def __init__(self, *args):
            StandardError.__init__(self, *args)
    #
    # Constants we use.
    #
    MAXBLOCK    = 30
    MAXRETRIES    = 50
    MAXWINDRETRIES= 20
    WRITENIB    = 0x42
    SETBIT    = 0x12
    UNSETBIT    = 0x32
    WRITEACK    = 0x10
    SETACK    = 0x04
    UNSETACK    = 0x0C
    RESET_MIN    = 0x01
    RESET_MAX    = 0x02
    MAX_RESETS    = 100
    #
    # Instance data.
    #
    log_buffer    = None    # list,   action log
    log_mode    = None    # string, Log mode
    long_nest    = None    # int,    Nesting of log actions
    serial_port    = None    # string, SerialPort port to use
    #
    # Initialise ourselves.
    #
    def __init__(self,serial_port):
        self.log_buffer = []
        self.log_nest = 0
        self.serial_port = serial_port
    #
    # Write data to the device.
    #
    def write_byte(self,data):
        if self.log_mode != 'w':
            if self.log_mode != 'e':
                self.log(' ')
            self.log_mode = 'w'
        self.log("%02x" % ord(data))
        self.serial_port.write(data)
    #
    # Read a byte from the device.
    #
    def read_byte(self, timeout=1.0):
        if self.log_mode != 'r':
            self.log_mode = 'r'
            self.log(':')
        result = self.serial_port.read_byte(timeout)
        if result == None:
            self.log("--")
        else:
            self.log("%02x" % ord(result))
        return result
    #
    # Remove all pending incoming characters.
    #
    def clear_device(self):
        if self.log_mode != 'e':
            self.log(' ')
        self.log_mode = 'c'
        self.log("C")
        self.serial_port.clear()
    #
    # Write a reset string and wait for a reply.
    #
    def reset_06(self):
        self.log_enter("re")
        try:
            for retry in range(self.__class__.MAX_RESETS):
                self.clear_device()
                self.write_byte('\x06')
                #
                # Occasionally 0, then 2 is returned.  If 0 comes back,
                # continue reading as this is more efficient than sending
                # an out-of sync reset and letting the data reads restore
                # synchronization.  Occasionally, multiple 2's are returned.
                # Read with a fast timeout until all data is exhausted, if
                # we got a 2 back at all, we consider it a success.
                #
                success = False
                answer = self.read_byte()
                while answer != None:
                    if answer == '\x02':
                        success = True
                    answer = self.read_byte(0.05)
                    if success:
                        return
            msg = "Reset failed, %d retries, no response" % self.__class__.MAX_RESETS
            raise self.Ws2300Exception(msg)
        finally:
            self.log_exit()
    #
    # Encode the address.
    #
    def write_address(self,address):
        for digit in range(4):
            byte = chr((address >> (4 * (3-digit)) & 0xF) * 4 + 0x82)
            self.write_byte(byte)
            ack = chr(digit * 16 + (ord(byte) - 0x82) // 4)
            answer = self.read_byte()
            if ack != answer:
                self.log("??")
                return False
        return True
    #
    # Write data, checking the reply.
    #
    def write_data(self,nybble_address,nybbles,encode_constant=None):
        self.log_enter("wd")
        try:
            if not self.write_address(nybble_address):
                return None
            if encode_constant == None:
                encode_constant = self.WRITENIB
            encoded_data = ''.join([
                    chr(nybbles[i]*4 + encode_constant)
                    for i in range(len(nybbles))])
            ack_constant = {
                self.SETBIT:    self.SETACK,
                self.UNSETBIT:    self.UNSETACK,
                self.WRITENIB:    self.WRITEACK
                }[encode_constant]
            self.log(",")
            for i in range(len(encoded_data)):
                self.write_byte(encoded_data[i])
                answer = self.read_byte()
                if chr(nybbles[i] + ack_constant) != answer:
                    self.log("??")
                    return None
            return True
        finally:
            self.log_exit()
    #
    # Reset the device and write a command, verifing it was written correctly.
    #
    def write_safe(self,nybble_address,nybbles,encode_constant=None):
        self.log_enter("ws")
        try:
            for retry in range(self.MAXRETRIES):
                self.reset_06()
                command_data = self.write_data(nybble_address,nybbles,encode_constant)
                if command_data != None:
                    return command_data
            raise self.Ws2300Exception("write_safe failed, retries exceeded")
        finally:
            self.log_exit()
    #
    # A total kuldge this, but its the easiest way to force the 'computer
    # time' to look like a normal ws2300 variable, which it most definitely
    # isn't, of course.
    #
    def read_computer_time(self,nybble_address,nybble_count):
        now = time.time()
        tm = time.localtime(now)
        tu = time.gmtime(now)
        year2 = tm[0] % 100
        datetime_data = (
            tu[5]%10, tu[5]//10, tu[4]%10, tu[4]//10, tu[3]%10, tu[3]//10,
            tm[5]%10, tm[5]//10, tm[4]%10, tm[4]//10, tm[3]%10, tm[3]//10,
            tm[2]%10, tm[2]//10, tm[1]%10, tm[1]//10, year2%10, year2//10)
        address = nybble_address+18
        return datetime_data[address:address+nybble_count]
    #
    # Read 'length' nybbles at address.  Returns: (nybble_at_address, ...).
    # Can't read more than MAXBLOCK nybbles at a time.
    #
    def read_data(self,nybble_address,nybble_count):
        if nybble_address < 0:
            return self.read_computer_time(nybble_address,nybble_count)
        self.log_enter("rd")
        try:
            if nybble_count < 1 or nybble_count > self.MAXBLOCK:
                StatdardError("Too many nybbles requested")
            bytes = (nybble_count + 1) // 2
            if not self.write_address(nybble_address):
                return None
            #
            # Write the number bytes we want to read.
            #
            encoded_data = chr(0xC2 + bytes*4)
            self.write_byte(encoded_data)
            answer = self.read_byte()
            check = chr(0x30 + bytes)
            if answer != check:
                self.log("??")
                return None
            #
            # Read the response.
            #
            self.log(", :")
            response = ""
            for i in range(bytes):
                answer = self.read_byte()
                if answer == None:
                    return None
                response += answer
            #
            # Read and verify checksum
            #
            answer = self.read_byte()
            checksum = sum([ord(b) for b in response]) % 256
            if chr(checksum) != answer:
                self.log("??")
                return None
            flatten = lambda a,b: a + (ord(b) % 16, ord(b) / 16)
            return reduce(flatten, response, ())[:nybble_count]
        finally:
            self.log_exit()
    #
    # Read a batch of blocks.  Batches is a list of data to be read:
    #  [(address_of_first_nybble, length_in_nybbles), ...]
    # returns:
    #  [(nybble_at_address, ...), ...]
    #
    def read_batch(self,batches):
        self.log_enter("rb start")
        self.log_exit()
        try:
            if [b for b in batches if b[0] >= 0]:
                self.reset_06()
            result = []
            for batch in batches:
                address = batch[0]
                data = ()
                for start_pos in range(0,batch[1],self.MAXBLOCK):
                    for retry in range(self.MAXRETRIES):
                        bytes = min(self.MAXBLOCK, batch[1]-start_pos)
                        response = self.read_data(address + start_pos, bytes)
                        if response != None:
                            break
                        self.reset_06()
                    if response == None:
                        raise self.Ws2300Exception("read failed, retries exceeded")
                    data += response
                result.append(data)
            return result
        finally:
            self.log_enter("rb end")
            self.log_exit()
    #
    # Reset the device, read a block of nybbles at the passed address.
    #
    def read_safe(self,nybble_address,nybble_count):
        self.log_enter("rs")
        try:
            return self.read_batch([(nybble_address,nybble_count)])[0]
        finally:
            self.log_exit()
    #
    # Debug logging of serial IO.
    #
    def log(self, str):
        if not DEBUG_SERIAL:
            return
        self.log_buffer[-1] = self.log_buffer[-1] + str
    def log_enter(self, action):
        if not DEBUG_SERIAL:
            return
        self.log_nest += 1
        if self.log_nest == 1:
            if len(self.log_buffer) > 1000:
                del self.log_buffer[0]
            self.log_buffer.append("%5.2f %s " % (time.time() % 100, action))
            self.log_mode = 'e'
    def log_exit(self):
        if not DEBUG_SERIAL:
            return
        self.log_nest -= 1

#
# Print a data block.
#
def bcd2num(nybbles):
    digits = list(nybbles)[:]
    digits.reverse()
    return reduce(lambda a,b: a*10 + b, digits, 0)

def num2bcd(number, nybble_count):
    result = []
    for i in range(nybble_count):
        result.append(int(number % 10))
        number //= 10
    return tuple(result)

def bin2num(nybbles):
    digits = list(nybbles)
    digits.reverse()
    return reduce(lambda a,b: a*16 + b, digits, 0)

def num2bin(number, nybble_count):
    result = []
    number = int(number)
    for i in range(nybble_count):
        result.append(number % 16)
        number //= 16
    return tuple(result)

#
# A "Conversion" encapsulates a unit of measurement on the Ws2300.  Eg
# temperature, or wind speed.
#
class Conversion(object):
    description	= None # Description of the units.
    nybble_count = None # Number of nybbles used on the WS2300
    units = None # Units name (eg hPa).
    #
    # Initialise ourselves.
    #  units	 - text description of the units.
    #  nybble_count- Size of stored value on ws2300 in nybbles
    #  description - Description of the units
    #
    def __init__(self, units, nybble_count, description):
        self.description = description
        self.nybble_count = nybble_count
        self.units = units
    #
    # Convert the nybbles read from the ws2300 to our internal value.
    #
    def binary2value(self, data): raise NotImplementedError()
    #
    # Convert our internal value to nybbles that can be written to the ws2300.
    #
    def value2binary(self, value): raise NotImplementedError()
    #
    # Print value.
    #
    def str(self, value): raise NotImplementedError()
    #
    # Convert the string produced by "str()" back to the value.
    #
    def parse(self, str): raise NotImplementedError()
    #
    # Transform data into something that can be written.  Returns:
    #  (new_bytes, ws2300.write_safe_args, ...)
    # This only becomes tricky when less than a nybble is written.
    #
    def write(self, data, nybble):
        return (data, data)
    #
    # Test if the nybbles read from the Ws2300 is sensible.  Sometimes a
    # communications error will make it past the weak checksums the Ws2300
    # uses.  This optional function implements another layer of checking -
    # does the value returned make sense.  Returns True if the value looks
    # like garbage.
    #
    def garbage(self, data):
        return False

#
# For values stores as binary numbers.
#
class BinConversion(Conversion):
    mult  = None
    scale = None
    units = None
    def __init__(self, units, nybble_count, scale, description, mult=1, check=None):
        Conversion.__init__(self, units, nybble_count, description)
        self.mult    = mult
        self.scale	= scale
        self.units	= units
    def binary2value(self, data):
        return (bin2num(data) * self.mult) / 10.0**self.scale
    def value2binary(self, value):
        return num2bin(int(value * 10**self.scale) // self.mult, self.nybble_count)
    def str(self, value):
        return "%.*f" % (self.scale, value)
    def parse(self, str):
        return float(str)

#
# For values stored as BCD numbers.
#
class BcdConversion(Conversion):
    offset = None
    scale = None
    units = None
    def __init__(self, units, nybble_count, scale, description, offset=0):
        Conversion.__init__(self, units, nybble_count, description)
        self.offset = offset
        self.scale = scale
        self.units = units
    def binary2value(self, data):
        num = bcd2num(data) % 10**self.nybble_count + self.offset
        return float(num) / 10**self.scale
    def value2binary(self, value):
        return num2bcd(int(value * 10**self.scale) - self.offset, self.nybble_count)
    def str(self, value):
        return "%.*f" % (self.scale, value)
    def parse(self, str):
        return float(str)

#
# For pressures.  Add a garbage check.
#
class PressureConversion(BcdConversion):
    def __init__(self):
        BcdConversion.__init__(self, "hPa", 5, 1, "pressure")
    def garbage(self, data):
        value = self.binary2value(data)
        return value < 900 or value > 1200

#
# For values the represent a date.
#
class ConversionDate(Conversion):
    format = None
    def __init__(self, nybble_count, format):
        description =  format
        for xlate in "%Y:yyyy,%m:mm,%d:dd,%H:hh,%M:mm,%S:ss".split(","):
            description = description.replace(*xlate.split(":"))
        Conversion.__init__(self, "", nybble_count, description)
        self.format = format
    def str(self, value):
        return time.strftime(self.format, time.localtime(value))
    def parse(self, str):
        return time.mktime(time.strptime(str, self.format))

class DateConversion(ConversionDate):
    def __init__(self):
        ConversionDate.__init__(self, 6, "%Y-%m-%d")
    def binary2value(self, data):
        x = bcd2num(data)
        return time.mktime((
                x //     10000 % 100,
                x //       100 % 100,
                x              % 100,
                0,
                0,
                0,
                0,
                0,
                0))
    def value2binary(self, value):
        tm = time.localtime(value)
        dt = tm[2] +  tm[1] * 100 + (tm[0]-2000) * 10000
        return num2bcd(dt, self.nybble_count)

class DatetimeConversion(ConversionDate):
    def __init__(self):
        ConversionDate.__init__(self, 11, "%Y-%m-%d %H:%M")
    def binary2value(self, data):
        x = bcd2num(data)
        return time.mktime((
                x // 1000000000 % 100 + 2000,
                x //   10000000 % 100,
                x //     100000 % 100,
                x //        100 % 100,
                x               % 100,
                0,
                0,
                0,
                0))
    def value2binary(self, value):
        tm = time.localtime(value)
        dow = tm[6] + 1
        dt = tm[4]+(tm[3]+(dow+(tm[2]+(tm[1]+(tm[0]-2000)*100)*100)*10)*100)*100
        return num2bcd(dt, self.nybble_count)

class UnixtimeConversion(ConversionDate):
    def __init__(self):
        ConversionDate.__init__(self, 12, "%Y-%m-%d %H:%M:%S")
    def binary2value(self, data):
        x = bcd2num(data)
        return time.mktime((
                x //10000000000 % 100 + 2000,
                x //  100000000 % 100,
                x //    1000000 % 100,
                x //      10000 % 100,
                x //        100 % 100,
                x               % 100,
                0,
                0,
                0))
    def value2binary(self, value):
        tm = time.localtime(value)
        dt = tm[5]+(tm[4]+(tm[3]+(tm[2]+(tm[1]+(tm[0]-2000)*100)*100)*100)*100)*100
        return num2bcd(dt, self.nybble_count)

class TimestampConversion(ConversionDate):
    def __init__(self):
        ConversionDate.__init__(self, 10, "%Y-%m-%d %H:%M")
    def binary2value(self, data):
        x = bcd2num(data)
        return time.mktime((
                x // 100000000 % 100 + 2000,
                x //   1000000 % 100,
                x //     10000 % 100,
                x //       100 % 100,
                x              % 100,
                0,
                0,
                0,
                0))
    def value2binary(self, value):
        tm = time.localtime(value)
        dt = tm[4] + (tm[3] + (tm[2] + (tm[1] +  (tm[0]-2000)*100)*100)*100)*100
        return num2bcd(dt, self.nybble_count)

class TimeConversion(ConversionDate):
    def __init__(self):
        ConversionDate.__init__(self, 6, "%H:%M:%S")
    def binary2value(self, data):
        x = bcd2num(data)
        return time.mktime((
                0,
                0,
                0,
                x //     10000 % 100,
                x //       100 % 100,
                x              % 100,
                0,
                0,
                0)) - time.timezone
    def value2binary(self, value):
        tm = time.localtime(value)
        dt = tm[5] + tm[4]*100 + tm[3]*10000
        return num2bcd(dt, self.nybble_count)
    def parse(self, str):
        return time.mktime((0,0,0) + time.strptime(str, self.format)[3:]) + time.timezone

class WindDirectionConversion(Conversion):
    def __init__(self):
        Conversion.__init__(self, "deg", 1, "North=0 clockwise")
    def binary2value(self, data):
        return data[0] * 22.5
    def value2binary(self, value):
        return (int((value + 11.25) / 22.5),)
    def str(self, value):
        return "%g" % value
    def parse(self, str):
        return float(str)

class WindVelocityConversion(Conversion):
    def __init__(self):
        Conversion.__init__(self, "ms,d", 4, "wind speed and direction")
    def binary2value(self, data):
        return (bcd2num(data[:3])/10.0, bin2num(data[3:4]) * 22.5)
    def value2binary(self, value):
        return num2bcd(value[0]*10, 3) + num2bin((value[1] + 11.5) / 22.5, 1)
    def str(self, value):
        return "%.1f,%g" % value
    def parse(self, str):
        return tuple([float(x) for x in str.split(",")])

#
# For non-numerical values.
#
class TextConversion(Conversion):
    constants = None
    def __init__(self, constants):
        items = constants.items()[:]
        items.sort()
        fullname = ",".join([c[1]+"="+str(c[0]) for c in items]) + ",unknown-X"
        Conversion.__init__(self, "", 1, fullname)
        self.constants = constants
    def binary2value(self, data):
        return data[0]
    def value2binary(self, value):
        return (value,)
    def str(self, value):
        result = self.constants.get(value, None)
        if result != None:
            return result
        return "unknown-%d" % value
    def parse(self, str):
        result = [c[0] for c in self.constants.items() if c[1] == str]
        if result:
            return result[0]
        return int(value[8:],16)

#
# For values that are represented by one bit.
#
class ConversionBit(Conversion):
    bit = None
    desc = None
    def __init__(self, bit, desc):
        self.bit = bit
        self.desc = desc
        Conversion.__init__(self, "", 1, desc[0] + "=0," + desc[1] + "=1")
    def binary2value(self, data):
        return data[0] & (1 << self.bit) and 1 or 0
    def value2binary(self, value):
        return (value << self.bit,)
    def str(self, value):
        return self.desc[value]
    def parse(self, str):
        return [c[0] for c in self.desc.items() if c[1] == str][0]

class BitConversion(ConversionBit):
    def __init__(self, bit, desc):
        ConversionBit.__init__(self, bit, desc)
    #
    # Since Ws2300.write_safe() only writes nybbles and we have just one bit,
    # we have to insert that bit into the data_read so it can be written as
    # a nybble.
    #
    def write(self, data, nybble):
        data = (nybble & ~(1 << self.bit) | data[0],)
        return (data, data)

class AlarmSetConversion(BitConversion):
    bit = None
    desc = None
    def __init__(self, bit):
        BitConversion.__init__(self, bit, {0:"off", 1:"on"})

class AlarmActiveConversion(BitConversion):
    bit = None
    desc = None
    def __init__(self, bit):
        BitConversion.__init__(self, bit, {0:"inactive", 1:"active"})

#
# For values that are represented by one bit, and must be written as
# a single bit.
#
class SetresetConversion(ConversionBit):
    bit = None
    def __init__(self, bit, desc):
        ConversionBit.__init__(self, bit, desc)
    #
    # Setreset bits use a special write mode.
    #
    def write(self, data, nybble):
        if data[0] == 0:
            operation = Ws2300.UNSETBIT
        else:
            operation = Ws2300.SETBIT
        return ((nybble & ~(1 << self.bit) | data[0],), [self.bit], operation)

#
# Conversion for history.  This kludge makes history fit into the framework
# used for all the other measures.
#
class HistoryConversion(Conversion):
    class HistoryRecord(object):
        temp_indoor = None
        temp_outdoor = None
        pressure_absolute = None
        humidity_indoor = None
        humidity_outdoor = None
        rain = None
        wind_speed = None
        wind_direction = None
    def __str__(self):
        return "%4.1fc %2d%% %4.1fc %2d%% %6.1fhPa %6.1fmm %2dm/s %5g" % (
            self.temp_indoor, self.humidity_indoor,
            self.temp_outdoor, self.humidity_outdoor, 
            self.pressure_absolute, self.rain,
            self.wind_speed, self.wind_direction)
    def parse(cls, str):
        rec = cls()
        toks = [tok.rstrip(string.ascii_letters + "%/") for tok in str.split()]
        rec.temp_indoor = float(toks[0])
        rec.humidity_indoor = int(toks[1])
        rec.temp_outdoor = float(toks[2])
        rec.humidity_outdoor = int(toks[3])
        rec.pressure_absolute = float(toks[4])
        rec.rain = float(toks[5])
        rec.wind_speed = int(toks[6])
        rec.wind_direction = int((float(toks[7]) + 11.25) / 22.5) % 16
        return rec
    parse = classmethod(parse)
    def __init__(self):
        Conversion.__init__(self, "", 19, "history")
    def binary2value(self, data):
        value = self.__class__.HistoryRecord()
        n = bin2num(data[0:5])
        value.temp_indoor = (n % 1000) / 10.0 - 30
        value.temp_outdoor = (n - (n % 1000)) / 10000.0 - 30
        n = bin2num(data[5:10])
        value.pressure_absolute = (n % 10000) / 10.0
        if value.pressure_absolute < 500:
            value.pressure_absolute += 1000
        value.humidity_indoor = (n - (n % 10000)) / 10000.0
        value.humidity_outdoor = bcd2num(data[10:12])
        value.rain = bin2num(data[12:15]) * 0.518
        value.wind_speed = bin2num(data[15:18])
        value.wind_direction = bin2num(data[18:19]) * 22.5
        return value
    def value2binary(self, value):
        result = ()
        n = int((value.temp_indoor + 30) * 10.0 + (value.temp_outdoor + 30) * 10000.0 + 0.5)
        result = result + num2bin(n, 5)
        n = value.pressure_absolute % 1000
        n = int(n * 10.0 + value.humidity_indoor * 10000.0 + 0.5)
        result = result + num2bin(n, 5)
        result = result + num2bcd(value.humidity_outdoor, 2)
        result = result + num2bin(int((value.rain + 0.518/2) / 0.518), 3)
        result = result + num2bin(value.wind_speed, 3)
        result = result + num2bin(value.wind_direction, 1)
        return result
    #
    # Print value.
    #
    def str(self, value):
        return str(value)
    #
    # Convert the string produced by "str()" back to the value.
    #
    def parse(self, str):
        return self.__class__.HistoryRecord.parse(str)

#
# Various conversions we know about.
#
conv_ala0 = AlarmActiveConversion(0)
conv_ala1 = AlarmActiveConversion(1)
conv_ala2 = AlarmActiveConversion(2)
conv_ala3 = AlarmActiveConversion(3)
conv_als0 = AlarmSetConversion(0)
conv_als1 = AlarmSetConversion(1)
conv_als2 = AlarmSetConversion(2)
conv_als3 = AlarmSetConversion(3)
conv_buzz = SetresetConversion(3, {0:'on', 1:'off'})
conv_lbck = SetresetConversion(0, {0:'off', 1:'on'})
conv_date = DateConversion()
conv_dtme = DatetimeConversion()
conv_utme = UnixtimeConversion()
conv_hist = HistoryConversion()
conv_stmp = TimestampConversion()
conv_time = TimeConversion()
conv_wdir = WindDirectionConversion()
conv_wvel = WindVelocityConversion()
conv_conn = TextConversion({0:"cable", 3:"lost", 15:"wireless"})
conv_fore = TextConversion({0:"rainy", 1:"cloudy", 2:"sunny"})
conv_spdu = TextConversion({0:"m/s", 1:"knots", 2:"beaufort", 3:"km/h", 4:"mph"})
conv_tend = TextConversion({0:"steady", 1:"rising", 2:"falling"})
conv_wovr = TextConversion({0:"no", 1:"overflow"})
conv_wvld = TextConversion({0:"ok", 1:"invalid", 2:"overflow"})
conv_lcon = BinConversion("",    1, 0, "contrast")
conv_rec2 = BinConversion("",    2, 0, "record number")
conv_humi = BcdConversion("%",   2, 0, "humidity")
conv_pres = PressureConversion()
conv_rain = BcdConversion("mm",  6, 2, "rain")
conv_temp = BcdConversion("C",   4, 2, "temperature",   -3000)
conv_per2 = BinConversion("s",   2, 1, "time interval",  5)
conv_per3 = BinConversion("min", 3, 0, "time interval")
conv_wspd = BcdConversion("m/s", 3, 1, "speed")

#
# Define a measurement on the Ws2300.  This encapsulates:
#  - The names (abbrev and long) of the thing being measured, eg wind speed.
#  - The location it can be found at in the Ws2300's memory map.
#  - The Conversion used to represent the figure.
#
class Measure(object):
    IDS = {}       # map,    Measures defined. {id: Measure, ...}
    NAMES = {}     # map,    Measures defined. {name: Measure, ...}
    address = None # int,    Nybble address in the Ws2300
    conv = None    # object, Type of value
    id = None      # string, Short name
    name = None    # string, Long name
    reset = None   # string, Id of measure used to reset this one
    def __init__(self, address, id, conv, name, reset=None):
        self.address = address
        self.conv = conv
        self.reset = reset
        if id != None:
            self.id = id
            assert not id in self.__class__.IDS
            self.__class__.IDS[id] = self
        if name != None:
            self.name = name
            assert not name in self.__class__.NAMES
            self.__class__.NAMES[name] = self
    def __hash__(self):
        return hash(self.id)
    def __cmp__(self, other):
        if isinstance(other, Measure):
            return cmp(self.id, other.id)
        return cmp(type(self), type(other))


#
# Conversion for raw Hex data.  These are created as needed.
#
class HexConversion(Conversion):
    def __init__(self, nybble_count):
        Conversion.__init__(self, "", nybble_count, "hex data")
    def binary2value(self, data):
        return data
    def value2binary(self, value):
        return value
    def str(self, value):
        return ",".join(["%x" % nybble for nybble in value])
    def parse(self, str):
        toks = str.replace(","," ").split()
        for i in range(len(toks)):
            s = list(toks[i])
            s.reverse()
            toks[i] = ''.join(s)
        list_str = list(''.join(toks))
        self.nybble_count = len(list_str)
        return tuple([int(nybble) for nybble in list_str])

#
# The raw nybble measure.
#
class HexMeasure(Measure):
    def __init__(self, address, id, conv, name):
        self.address = address
        self.name = name
        self.conv = conv

#
# A History record.  Again a kludge to make history fit into the framework
# developed for the other measurements.  History records are identified
# by their record number.  Record number 0 is the most recently written
# record, record number 1 is the next most recently written and so on.
#
class HistoryMeasure(Measure):
    HISTORY_BUFFER_ADDR = 0x6c6 # int,    Address of the first history record
    MAX_HISTORY_RECORDS = 0xaf  # string, Max number of history records stored
    LAST_POINTER = None         # int,    Pointer to last record
    RECORD_COUNT = None         # int,    Number of records in use
    recno = None                # int,    The record number this represents
    conv			= conv_hist
    def __init__(self, recno):
        self.recno = recno
    def set_constants(cls, ws2300):
        measures = [Measure.IDS["hp"], Measure.IDS["hn"]]
        data = read_measurements(ws2300, measures)
        cls.LAST_POINTER = int(measures[0].conv.binary2value(data[0]))
        cls.RECORD_COUNT = int(measures[1].conv.binary2value(data[1]))
    set_constants = classmethod(set_constants)
    def id(self):
        return "h%03d" % self.recno
    id = property(id)
    def name(self):
        return "history record %d" % self.recno
    name = property(name)
    def offset(self):
        if self.LAST_POINTER is None:
            raise StandardError("HistoryMeasure.set_constants hasn't been called")
        return (self.LAST_POINTER - self.recno) % self.MAX_HISTORY_RECORDS
    offset = property(offset)
    def address(self):
        return self.HISTORY_BUFFER_ADDR + self.conv.nybble_count * self.offset
    address = property(address)

#
# The measurements we know about.  This is all of them documented in
# memory_map_2300.txt, bar the history.  History is handled specially.
# And of course, the "c?"'s aren't real measures at all - its the current
# time on this machine.
#
Measure(  -18, "ct",   conv_time, "this computer's time")
Measure(  -12, "cw",   conv_utme, "this computer's date time")
Measure(   -6, "cd",   conv_date, "this computer's date")
Measure(0x006, "bz",   conv_buzz, "buzzer")
Measure(0x00f, "wsu",  conv_spdu, "wind speed units")
Measure(0x016, "lb",   conv_lbck, "lcd backlight")
Measure(0x019, "sss",  conv_als2, "storm warn alarm set")
Measure(0x019, "sts",  conv_als0, "station time alarm set")
Measure(0x01a, "phs",  conv_als3, "pressure max alarm set")
Measure(0x01a, "pls",  conv_als2, "pressure min alarm set")
Measure(0x01b, "oths", conv_als3, "out temp max alarm set")
Measure(0x01b, "otls", conv_als2, "out temp min alarm set")
Measure(0x01b, "iths", conv_als1, "in temp max alarm set")
Measure(0x01b, "itls", conv_als0, "in temp min alarm set")
Measure(0x01c, "dphs", conv_als3, "dew point max alarm set")
Measure(0x01c, "dpls", conv_als2, "dew point min alarm set")
Measure(0x01c, "wchs", conv_als1, "wind chill max alarm set")
Measure(0x01c, "wcls", conv_als0, "wind chill min alarm set")
Measure(0x01d, "ihhs", conv_als3, "in humidity max alarm set")
Measure(0x01d, "ihls", conv_als2, "in humidity min alarm set")
Measure(0x01d, "ohhs", conv_als1, "out humidity max alarm set")
Measure(0x01d, "ohls", conv_als0, "out humidity min alarm set")
Measure(0x01e, "rhhs", conv_als1, "rain 1h alarm set")
Measure(0x01e, "rdhs", conv_als0, "rain 24h alarm set")
Measure(0x01f, "wds",  conv_als2, "wind direction alarm set")
Measure(0x01f, "wshs", conv_als1, "wind speed max alarm set")
Measure(0x01f, "wsls", conv_als0, "wind speed min alarm set")
Measure(0x020, "siv",  conv_ala2, "icon alarm active")
Measure(0x020, "stv",  conv_ala0, "station time alarm active")
Measure(0x021, "phv",  conv_ala3, "pressure max alarm active")
Measure(0x021, "plv",  conv_ala2, "pressure min alarm active")
Measure(0x022, "othv", conv_ala3, "out temp max alarm active")
Measure(0x022, "otlv", conv_ala2, "out temp min alarm active")
Measure(0x022, "ithv", conv_ala1, "in temp max alarm active")
Measure(0x022, "itlv", conv_ala0, "in temp min alarm active")
Measure(0x023, "dphv", conv_ala3, "dew point max alarm active")
Measure(0x023, "dplv", conv_ala2, "dew point min alarm active")
Measure(0x023, "wchv", conv_ala1, "wind chill max alarm active")
Measure(0x023, "wclv", conv_ala0, "wind chill min alarm active")
Measure(0x024, "ihhv", conv_ala3, "in humidity max alarm active")
Measure(0x024, "ihlv", conv_ala2, "in humidity min alarm active")
Measure(0x024, "ohhv", conv_ala1, "out humidity max alarm active")
Measure(0x024, "ohlv", conv_ala0, "out humidity min alarm active")
Measure(0x025, "rhhv", conv_ala1, "rain 1h alarm active")
Measure(0x025, "rdhv", conv_ala0, "rain 24h alarm active")
Measure(0x026, "wdv",  conv_ala2, "wind direction alarm active")
Measure(0x026, "wshv", conv_ala1, "wind speed max alarm active")
Measure(0x026, "wslv", conv_ala0, "wind speed min alarm active")
Measure(0x027, None,   conv_ala3, "pressure max alarm active alias")
Measure(0x027, None,   conv_ala2, "pressure min alarm active alias")
Measure(0x028, None,   conv_ala3, "out temp max alarm active alias")
Measure(0x028, None,   conv_ala2, "out temp min alarm active alias")
Measure(0x028, None,   conv_ala1, "in temp max alarm active alias")
Measure(0x028, None,   conv_ala0, "in temp min alarm active alias")
Measure(0x029, None,   conv_ala3, "dew point max alarm active alias")
Measure(0x029, None,   conv_ala2, "dew point min alarm active alias")
Measure(0x029, None,   conv_ala1, "wind chill max alarm active alias")
Measure(0x029, None,   conv_ala0, "wind chill min alarm active alias")
Measure(0x02a, None,   conv_ala3, "in humidity max alarm active alias")
Measure(0x02a, None,   conv_ala2, "in humidity min alarm active alias")
Measure(0x02a, None,   conv_ala1, "out humidity max alarm active alias")
Measure(0x02a, None,   conv_ala0, "out humidity min alarm active alias")
Measure(0x02b, None,   conv_ala1, "rain 1h alarm active alias")
Measure(0x02b, None,   conv_ala0, "rain 24h alarm active alias")
Measure(0x02c, None,   conv_ala2, "wind direction alarm active alias")
Measure(0x02c, None,   conv_ala2, "wind speed max alarm active alias")
Measure(0x02c, None,   conv_ala2, "wind speed min alarm active alias")
Measure(0x200, "st",   conv_time, "station set time",		reset="ct")
Measure(0x23b, "sw",   conv_dtme, "station current date time")
Measure(0x24d, "sd",   conv_date, "station set date",		reset="cd")
Measure(0x266, "lc",   conv_lcon, "lcd contrast (ro)")
Measure(0x26b, "for",  conv_fore, "forecast")
Measure(0x26c, "ten",  conv_tend, "tendency")
Measure(0x346, "it",   conv_temp, "in temp")
Measure(0x34b, "itl",  conv_temp, "in temp min",		reset="it")
Measure(0x350, "ith",  conv_temp, "in temp max",		reset="it")
Measure(0x354, "itlw", conv_stmp, "in temp min when",		reset="sw")
Measure(0x35e, "ithw", conv_stmp, "in temp max when",		reset="sw")
Measure(0x369, "itla", conv_temp, "in temp min alarm")
Measure(0x36e, "itha", conv_temp, "in temp max alarm")
Measure(0x373, "ot",   conv_temp, "out temp")
Measure(0x378, "otl",  conv_temp, "out temp min",		reset="ot")
Measure(0x37d, "oth",  conv_temp, "out temp max",		reset="ot")
Measure(0x381, "otlw", conv_stmp, "out temp min when",		reset="sw")
Measure(0x38b, "othw", conv_stmp, "out temp max when",		reset="sw")
Measure(0x396, "otla", conv_temp, "out temp min alarm")
Measure(0x39b, "otha", conv_temp, "out temp max alarm")
Measure(0x3a0, "wc",   conv_temp, "wind chill")
Measure(0x3a5, "wcl",  conv_temp, "wind chill min",		reset="wc")
Measure(0x3aa, "wch",  conv_temp, "wind chill max",		reset="wc")
Measure(0x3ae, "wclw", conv_stmp, "wind chill min when",	reset="sw")
Measure(0x3b8, "wchw", conv_stmp, "wind chill max when",	reset="sw")
Measure(0x3c3, "wcla", conv_temp, "wind chill min alarm")
Measure(0x3c8, "wcha", conv_temp, "wind chill max alarm")
Measure(0x3ce, "dp",   conv_temp, "dew point")
Measure(0x3d3, "dpl",  conv_temp, "dew point min",		reset="dp")
Measure(0x3d8, "dph",  conv_temp, "dew point max",		reset="dp")
Measure(0x3dc, "dplw", conv_stmp, "dew point min when",		reset="sw")
Measure(0x3e6, "dphw", conv_stmp, "dew point max when",		reset="sw")
Measure(0x3f1, "dpla", conv_temp, "dew point min alarm")
Measure(0x3f6, "dpha", conv_temp, "dew point max alarm")
Measure(0x3fb, "ih",   conv_humi, "in humidity")
Measure(0x3fd, "ihl",  conv_humi, "in humidity min",		reset="ih")
Measure(0x3ff, "ihh",  conv_humi, "in humidity max",		reset="ih")
Measure(0x401, "ihlw", conv_stmp, "in humidity min when",	reset="sw")
Measure(0x40b, "ihhw", conv_stmp, "in humidity max when",	reset="sw")
Measure(0x415, "ihla", conv_humi, "in humidity min alarm")
Measure(0x417, "ihha", conv_humi, "in humidity max alarm")
Measure(0x419, "oh",   conv_humi, "out humidity")
Measure(0x41b, "ohl",  conv_humi, "out humidity min",		reset="oh")
Measure(0x41d, "ohh",  conv_humi, "out humidity max",		reset="oh")
Measure(0x41f, "ohlw", conv_stmp, "out humidity min when",	reset="sw")
Measure(0x429, "ohhw", conv_stmp, "out humidity max when",	reset="sw")
Measure(0x433, "ohla", conv_humi, "out humidity min alarm")
Measure(0x435, "ohha", conv_humi, "out humidity max alarm")
Measure(0x497, "rd",   conv_rain, "rain 24h")
Measure(0x49d, "rdh",  conv_rain, "rain 24h max",		reset="rd")
Measure(0x4a3, "rdhw", conv_stmp, "rain 24h max when",		reset="sw")
Measure(0x4ae, "rdha", conv_rain, "rain 24h max alarm")
Measure(0x4b4, "rh",   conv_rain, "rain 1h")
Measure(0x4ba, "rhh",  conv_rain, "rain 1h max",		reset="rh")
Measure(0x4c0, "rhhw", conv_stmp, "rain 1h max when",		reset="sw")
Measure(0x4cb, "rhha", conv_rain, "rain 1h max alarm")
Measure(0x4d2, "rt",   conv_rain, "rain total",			reset=0)
Measure(0x4d8, "rtrw", conv_stmp, "rain total reset when",	reset="sw")
Measure(0x4ee, "wsl",  conv_wspd, "wind speed min",		reset="ws")
Measure(0x4f4, "wsh",  conv_wspd, "wind speed max",		reset="ws")
Measure(0x4f8, "wslw", conv_stmp, "wind speed min when",	reset="sw")
Measure(0x502, "wshw", conv_stmp, "wind speed max when",	reset="sw")
Measure(0x527, "wso",  conv_wovr, "wind speed overflow")
Measure(0x528, "wsv",  conv_wvld, "wind speed validity")
Measure(0x529, "wv",   conv_wvel, "wind velocity")
Measure(0x529, "ws",   conv_wspd, "wind speed")
Measure(0x52c, "w0",   conv_wdir, "wind direction")
Measure(0x52d, "w1",   conv_wdir, "wind direction 1")
Measure(0x52e, "w2",   conv_wdir, "wind direction 2")
Measure(0x52f, "w3",   conv_wdir, "wind direction 3")
Measure(0x530, "w4",   conv_wdir, "wind direction 4")
Measure(0x531, "w5",   conv_wdir, "wind direction 5")
Measure(0x533, "wsla", conv_wspd, "wind speed min alarm")
Measure(0x538, "wsha", conv_wspd, "wind speed max alarm")
Measure(0x54d, "cn",   conv_conn, "connection type")
Measure(0x54f, "cc",   conv_per2, "connection time till connect")
Measure(0x5d8, "pa",   conv_pres, "pressure absolute")
Measure(0x5e2, "pr",   conv_pres, "pressure relative")
Measure(0x5ec, "pc",   conv_pres, "pressure correction")
Measure(0x5f6, "pal",  conv_pres, "pressure absolute min",	reset="pa")
Measure(0x600, "prl",  conv_pres, "pressure relative min",	reset="pr")
Measure(0x60a, "pah",  conv_pres, "pressure absolute max",	reset="pa")
Measure(0x614, "prh",  conv_pres, "pressure relative max",	reset="pr")
Measure(0x61e, "plw",  conv_stmp, "pressure min when",		reset="sw")
Measure(0x628, "phw",  conv_stmp, "pressure max when",		reset="sw")
Measure(0x63c, "pla",  conv_pres, "pressure min alarm")
Measure(0x650, "pha",  conv_pres, "pressure max alarm")
Measure(0x6b2, "hi",   conv_per3, "history interval")
Measure(0x6b5, "hc",   conv_per3, "history time till sample")
Measure(0x6b8, "hw",   conv_stmp, "history last sample when")
Measure(0x6c2, "hp",   conv_rec2, "history last record pointer",reset=0)
Measure(0x6c4, "hn",   conv_rec2, "history number of records",	reset=0)

#
# Read the requests.
#
def read_measurements(ws2300, read_requests):
    if not read_requests:
        return []
    #
    # Optimise what we have to read.
    #
    batches = [(m.address, m.conv.nybble_count) for m in read_requests]
    batches.sort()
    index = 1
    addr = {batches[0][0]: 0}
    while index < len(batches):
        same_sign = (batches[index-1][0] < 0) == (batches[index][0] < 0)
        same_area = batches[index-1][0] + batches[index-1][1] + 6 >= batches[index][0]
        if not same_sign or not same_area:
            addr[batches[index][0]] = index
            index += 1
            continue
        addr[batches[index][0]] = index-1
        batches[index-1] = batches[index-1][0], batches[index][0] + batches[index][1] - batches[index-1][0]
        del batches[index]
    #
    # Read the data.
    #
    nybbles = ws2300.read_batch(batches)
    #
    # Return the data read in the order it was requested.
    #
    results = []
    for measure in read_requests:
        index = addr[measure.address]
        offset = measure.address - batches[index][0]
        results.append(nybbles[index][offset:offset+measure.conv.nybble_count])
    return results




# define a main entry point for basic testing of the station without weewx
# engine and service overhead.

usage = """%prog [options] [--debug] [--help]"""

def main():
    syslog.openlog('ws23xx', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
    port = DEFAULT_PORT
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display diagnostic information while running')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='the serial port to which the station is connected')
    (options, args) = parser.parse_args()
    if options.debug is not None:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    if options.port:
        port = options.port

    print "ws23xx driver version %s" % DRIVER_VERSION
    serial_port = LinuxSerialPort(port)
    try:
        data = WS23xx.get_raw_data(serial_port)
        print data
    finally:
        serial_port.close()

if __name__ == '__main__':
    main()
