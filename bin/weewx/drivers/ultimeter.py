#!/usr/bin/env python
# $Id$
# Copyright 2014 Matthew Wall
# Copyright 2014 Nate Bargmann <n0nb@n0nb.us>
# See the file LICENSE.txt for your full rights.
#
# Credit to and contributions from:
#   Jay Nugent (WB8TKL) and KRK6 for weather-2.kr6k-V2.1
#     http://server1.nuge.com/~weather/
#   Steve (sesykes71) for testing the first implementations of this driver
#   Garret Power for decoding improvements and testing

"""Driver for Peet Bros Ultimeter weather stations except the Ultimeter II

This driver assumes the Ultimeter is emitting data in Peet Bros Data Logger
mode format.

Resources for the Ultimeter stations

Ultimeter Models 2100, 2000, 800, & 100 serial specifications:
  http://www.peetbros.com/shop/custom.aspx?recid=29

Ultimeter 2000 Pinouts and Parsers:
  http://www.webaugur.com/ham-radio/52-ultimeter-2000-pinouts-and-parsers.html

Ultimeter II
  not supported by this driver

All models communicate over an RS-232 compatible serial port using three
wires--RXD, TXD, and Ground (except Ultimeter II which omits TXD).  Port
parameters are 2400, 8N1, with no flow control.

The Ultimeter hardware supports several "modes" for providing station data
to the serial port.  This driver utilizes the "modem mode" to set the date
and time of the Ultimeter upon initialization and then sets it into Data
Logger mode for continuous updates.

Modem Mode commands used by the driver
    >Addddmmmm  Set Date and Time (decimal digits dddd = day of year,
                mmmm = minute of day; Jan 1 = 0000, Midnight = 0000)

    >I          Set output mode to Data Logger Mode (continuous output)

"""

from __future__ import with_statement
import serial
import syslog
import time

import weewx.drivers

DRIVER_NAME = 'Ultimeter'
DRIVER_VERSION = '0.11'

INHG_PER_MBAR = 0.0295333727
METER_PER_FOOT = 0.3048
MILE_PER_KM = 0.621371

def loader(config_dict, engine):
    return Ultimeter(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return UltimeterConfEditor()


DEFAULT_PORT = '/dev/ttyS0'
DEBUG_READ = 0

def logmsg(level, msg):
    syslog.syslog(level, 'ultimeter: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


class Ultimeter(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with a Peet Bros Ultimeter station

    model: station model, e.g., 'Ultimeter 2000' or 'Ultimeter 100'
    [Optional. Default is 'Ultimeter']

    port - serial port
    [Required. Default is /dev/ttyS0]

    polling_interval - how often to query the serial interface, seconds
    [Optional. Default is 1]

    max_tries - how often to retry serial communication before giving up
    [Optional. Default is 5]
    """
    def __init__(self, **stn_dict):
        self.model = stn_dict.get('model', 'Ultimeter')
        self.port = stn_dict.get('port', DEFAULT_PORT)
        self.polling_interval = float(stn_dict.get('polling_interval', 1))
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 10))
        self.last_rain = None
        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('using serial port %s' % self.port)
        loginf('polling interval is %s' % str(self.polling_interval))
        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', DEBUG_READ))

    def genLoopPackets(self):
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                packet = {'dateTime': int(time.time() + 0.5),
                          'usUnits': weewx.US}
                # open a new connection to the station for each reading
                with Station(self.port) as station:
                    readings = station.get_readings()
                data = Station.parse_readings(readings)
                packet.update(data)
                self._augment_packet(packet)
                ntries = 0
                yield packet
                if self.polling_interval:
                    time.sleep(self.polling_interval)
            except (serial.serialutil.SerialException, weewx.WeeWxIOError), e:
                logerr("Failed attempt %d of %d to get LOOP data: %s" %
                       (ntries, self.max_tries, e))
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for LOOP data" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    @property
    def hardware_name(self):
        return self.model

    def _augment_packet(self, packet):
        # calculate the rain
        if self.last_rain is not None:
            packet['rain'] = packet['long_term_rain'] - self.last_rain
        else:
            packet['rain'] = None
        self.last_rain = packet['long_term_rain']

        # no wind direction when wind speed is zero
        if not packet['windSpeed']:
            packet['windDir'] = None

def _is_valid_char(c):
    """See whether a character is a valid hexadecimal digit or hyphen."""
    if c == '-':
        return True
    try:
        int(c, 16)
        return True
    except ValueError:
        return False

def _decode(s, multiplier=None):
    """Ultimeter puts hyphens in the string when a sensor is not installed.
    When we get a hyphen or any other non-hex character, return None.
    Negative values are represented in twos complement format.
    """
    v = None
    try:
        v = int(s, 16)
        bits = 4 * len(s)
        if v & (1<<(bits-1)) != 0:
            v = v - (1<<bits)
        if multiplier is not None:
            v *= multiplier
    except ValueError:
        pass
    return v

class Station(object):
    def __init__(self, port):
        self.port = port
        self.baudrate = 2400
        self.timeout = 30
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

        # Set date and time as internal clock skews.
        self.serial_port.write(">A%04d%04d\r"
            % (time.localtime().tm_yday - 1, time.localtime().tm_min
            + time.localtime().tm_hour * 60))

        # Set to Data Logger Mode
        self.serial_port.write(">I\r")

    def close(self):
        if self.serial_port is not None:
            logdbg("close serial port %s" % self.port)

            # Set to Modem Mode (stops Data Logger output)
            self.serial_port.write(">\r")

            self.serial_port.close()
            self.serial_port = None

    def read(self, nchar=1):
        buf = self.serial_port.read(nchar)
        n = len(buf)
        if n != nchar:
            if DEBUG_READ:
                logdbg("partial buffer: '%s'" %
                       ' '.join(["%0.2X" % ord(c) for c in buf]))
            raise weewx.WeeWxIOError("Read expected %d chars, got %d" %
                                     (nchar, n))
        return buf

    def write(self, data):
        n = self.serial_port.write(data)
        if n is not None and n != len(data):
            raise weewx.WeeWxIOError("Write expected %d chars, sent %d" %
                                     (len(data), n))

    def get_readings(self):
        buf = []
        while True:
            c = self.read(1)
            if c == "\r" or c == "\n":
                break
            elif c == '!' and len(buf) > 0:
                break
            elif c == '!':
                buf = []
            elif _is_valid_char(c):
                buf.append(c)
            else:
                buf = []
        if DEBUG_READ:
            logdbg("bytes: '%s'" % ' '.join(["%0.2X" % ord(c) for c in buf]))
        if len(buf) != 48:
            raise weewx.WeeWxIOError("Got %d bytes, expected 48" % len(buf))
        return ''.join(buf)

    @staticmethod
    def parse_readings(buf):
        """Ultimeter stations emit data in PeetBros format.  Each line has 52
        characters - 2 header bytes, 48 data bytes, and a carriage return
        and line feed (new line):

        !!000000BE02EB000027700000023A023A0025005800000000\r\n
          SSSSXXDDTTTTLLLLPPPPttttHHHHhhhhddddmmmmRRRRWWWW

          SSSS - wind speed (0.1 kph)
          XX   - wind direction calibration
          DD   - wind direction (0-255)
          TTTT - outdoor temperature (0.1 F)
          LLLL - long term rain (0.01 in)
          PPPP - pressure (0.1 mbar)
          tttt - indoor temperature (0.1 F)
          HHHH - outdoor humidity (0.1 %)
          hhhh - indoor humidity (0.1 %)
          dddd - date (day of year)
          mmmm - time (minute of day)
          RRRR - daily rain (0.01 in)
          WWWW - one minute wind average (0.1 kph)

        "pressure" reported by the Ultimeter 2000 is correlated to the local
        official barometer reading as part of the setup of the station
        console so this value is assigned to the 'barometer' key and
        the pressure and altimeter values are calculated from it.
        """
        data = dict()
        data['windSpeed'] = _decode(buf[0:4], 0.1 * MILE_PER_KM)  # mph
        data['windDir'] = _decode(buf[6:8], 1.411764)  # compass degrees
        data['outTemp'] = _decode(buf[8:12], 0.1)  # degree_F
        data['long_term_rain'] = _decode(buf[12:16], 0.01)  # inch
        data['barometer'] = _decode(buf[16:20], 0.1 * INHG_PER_MBAR)  # inHg
        data['inTemp'] = _decode(buf[20:24], 0.1)  # degree_F
        data['outHumidity'] = _decode(buf[24:28], 0.1)  # percent
        data['inHumidity'] = _decode(buf[28:32], 0.1)  # percent
        data['day_of_year'] = _decode(buf[32:36])
        data['minute_of_day'] = _decode(buf[36:40])
        data['daily_rain'] = _decode(buf[40:44], 0.01)  # inch
        data['wind_average'] = _decode(buf[44:48], 0.1 * MILE_PER_KM)  # mph
        return data


class UltimeterConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[Ultimeter]
    # This section is for the PeetBros Ultimeter series of weather stations.

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The station model, e.g., Ultimeter 2000, Ultimeter 100
    model = Ultimeter

    # The driver to use:
    driver = weewx.drivers.ultimeter
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/ultimeter.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    syslog.openlog('ultimeter', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='serial port to which the station is connected',
                      default=DEFAULT_PORT)
    (options, args) = parser.parse_args()

    if options.version:
        print "ultimeter driver version %s" % DRIVER_VERSION
        exit(0)

    with Station(options.port) as s:
        print s.get_readings()
