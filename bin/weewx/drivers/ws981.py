#!/usr/bin/env python
#
# Copyright 2014 Matthew Wall
# See the file LICENSE.txt for your rights.

"""Driver for Anemo WS981 weather station (http://www.anemo.cz/index.php?section=2&kat=51)

"""

from __future__ import with_statement
import serial
import syslog
import time

import weewx.drivers

DRIVER_NAME = 'WS981'
DRIVER_VERSION = '0.1'


def loader(config_dict, _):
    return WS981Driver(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WS981ConfEditor()

DEFAULT_PORT = '/dev/ttyUSB0'
DEBUG_READ = 0


def logmsg(level, msg):
    syslog.syslog(level, 'ws981: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class WS981Driver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with an Anemo WS981 station
    
    port - serial port
    [Required. Default is /dev/ttyUSB0]

    max_tries - how often to retry serial communication before giving up
    [Optional. Default is 5]

    retry_wait - how long to wait, in seconds, before retrying after a failure
    [Optional. Default is 10]
    """
    def __init__(self, **stn_dict):
        self.port = stn_dict.get('port', DEFAULT_PORT)
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 10))
        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('using serial port %s' % self.port)
        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', DEBUG_READ))
        self.station = Station(self.port)
        self.station.open()

    def closePort(self):
        if self.station is not None:
            self.station.close()
            self.station = None

    @property
    def hardware_name(self):
        return "WS981"

    def genLoopPackets(self):
        while True:
	    readings = self.station.get_readings_with_retry(self.max_tries, self.retry_wait)
            packet = {'dateTime': int(time.time() + 0.5),
                      'usUnits':  weewx.METRICWX}
            data = Station.parse_readings(readings)
            packet.update(data)
            self._augment_packet(packet)
            yield packet

    def _augment_packet(self, packet):
        # no wind direction when wind speed is zero
        if 'windSpeed' in packet and not packet['windSpeed']:
            packet['windDir'] = None


class Station(object):
    def __init__(self, port):
        self.port = port
        self.baudrate = 57600
        self.timeout = 3
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):
        self.close()

    def open(self):
        logdbg("open serial port %s" % self.port)
        self.serial_port = serial.Serial(self.port, self.baudrate,
                                         timeout=self.timeout)

    def close(self):
        if self.serial_port is not None:
            logdbg("close serial port %s" % self.port)
            self.serial_port.close()
            self.serial_port = None

    def get_readings(self):
        msg = None
	while True:
    	    byte = self.serial_port.read(1)
	    if ord(byte) == 0x1E:
		break
        msg = self.serial_port.read(9)
        if DEBUG_READ:
            logdbg("bytes: '%s'" % msg)
        return msg

    def get_readings_with_retry(self, max_tries=10, retry_wait=1):
        for ntries in range(0, max_tries):
            try:
                buf = self.get_readings()
                return buf
            except (serial.serialutil.SerialException, weewx.WeeWxIOError), e:
                loginf("Failed attempt %d of %d to get readings: %s" %
                       (ntries + 1, max_tries, e))
                time.sleep(retry_wait)
        else:
            msg = "Max retries (%d) exceeded for readings" % max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)


    @staticmethod
    def parse_readings(msg):

        data = dict()

        if msg[0] == 'A':                    # Analog input 
            a = msg[1:7]
            if a == '    --':
                a = None
            else:
                a = int(a)/10.0
            data['outTemp'] = a

        elif msg[0] == 'B':                    # Analog input 
            b = msg[1:7]
            if b == '    --':
                b = None
            else:
                b = int(b)/10.0

        elif msg[0] == 'C':                    # Analog input 
            c = msg[1:7]
            if c == '    --':
                c = None
            else:
                c = int(c)/10.0
            data['pressure'] = c

        elif msg[0] == 'D':                    # Analog input 
            d = msg[1:7]
            if d == '    --':
                d = None
            else:
                d = int(d)/10.0
            data['altimeter'] = d
            
        elif msg[0] == 'E':                    # precipitation input
            precipitation = int(msg[1:7])
            
        elif msg[0] == 'G':                    # wind speed and direction
            wind_direction =  int(msg[1:3]) * 10
            wind_speed =  int(msg[3:7])/10.0
            wind = (wind_speed), (wind_direction)
            
        elif msg[0] == 'H':                    # wind speed and direction (2 minutes sliding average)
            wind_direction =  int(msg[1:3]) * 10
            wind_speed =  int(msg[3:7])/10.0
            wind_2min = (wind_speed), (wind_direction)

        elif msg[0] == 'I':                    # wind speed and direction (10 minutes sliding average)
            wind_direction =  int(msg[1:3])* 10
            wind_speed =  int(msg[3:7])/10.0
            wind_10min = (wind_speed), (wind_direction )

        elif msg[0] == 'L':                    # Dewpoint temperature
            dewpoint = msg[1:7]
            if dewpoint == '    --':
                dewpoint = None
            else:
                dewpoint = int(dewpoint)/10.0

        elif msg[0] == 'M':                    # 3hours pressure trend
            pressure_3h = int(msg[1:7])/10.0

        elif msg[0] == 'Q':                    # power status in % (0-100% is internal power capacity) if external power supply present value is greater than 100
            power = int(msg[1:7])

        elif msg[0] == 'R':                    # alarm or relay status
            alarm = int(msg[1:7])

        elif msg[0] == 'S':                    # atmospheric stability
            atmosphere_stability = int(msg[1:7])

        elif msg[0] == 'W':                    # WAD software special format
            wind_direction = 10*(16*(ord(msg[1]) & 0x0F) + (ord(msg[2]) & 0x0F))
            wind_speed =  256*(16*(ord(msg[3]) & 0x0F) + (ord(msg[4]) & 0x0F)) + 16*(ord(msg[5]) & 0x0F) + (ord(msg[6]) & 0x0F)
            wind_speed_ms = wind_speed / 37.38932004
            data['windSpeed'] = wind_speed_ms
            data['windDir'] = wind_direction

        elif msg[0] == 'X':                    # WAD software special format 2 minutes average
            wind_direction = 10*(16*(ord(msg[1]) & 0x0F) + (ord(msg[2]) & 0x0F))
            wind_speed =  256*(16*(ord(msg[3]) & 0x0F) + (ord(msg[4]) & 0x0F)) + 16*(ord(msg[5]) & 0x0F) + (ord(msg[6]) & 0x0F)
            wind_speed_ms = wind_speed / 37.38932004
            data['windSpeed_2min'] = wind_speed_ms
            data['windDir_2min'] = wind_direction

        elif msg[0] == 'Y':                    # WAD software special format 10 minutes average
            wind_direction = 10*(16*(ord(msg[1]) & 0x0F) + (ord(msg[2]) & 0x0F))
            wind_speed =  256*(16*(ord(msg[3]) & 0x0F) + (ord(msg[4]) & 0x0F)) + 16*(ord(msg[5]) & 0x0F) + (ord(msg[6]) & 0x0F)
            wind_speed_ms = wind_speed / 37.38932004
            data['windSpeed_10min'] = wind_speed_ms
            data['windDir_10min'] = wind_direction

        return data


class WS981ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WS981]
    # This section is for the Anemo WS981 series of weather stations.

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The driver to use:
    driver = weewx.drivers.ws981
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/ws981.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    syslog.openlog('WS981', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='serial port to which the station is connected',
                      default=DEFAULT_PORT)
    (options, args) = parser.parse_args()

    if options.version:
        print "Anemo WS981 driver version %s" % DRIVER_VERSION
        exit(0)

    with Station(options.port) as s:
        while True:
            print time.time(), s.parse_readings(s.get_readings_with_retry())
