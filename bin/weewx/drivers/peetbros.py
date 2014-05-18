# Peet Bros-Ultimeter driver for weewx
# $Id$
#
# Copyright 2014 Matthew Wall
# Copyright 2014 Nate Bargmann <n0nb@n0nb.us>
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

"""Driver for Peet Bros Ultimeter weather stations (except the Ultimeter II).

This driver assumes the Ultimeter is emitting data in Peet Bros Data Logger
mode format.

Resources for the Ultimeter stations

Ultimeter Models 2100, 2000, 800, & 100 serial specifications:
  http://www.peetbros.com/shop/custom.aspx?recid=29

Ultimeter 2000 Pinouts and Parsers:
  http://www.webaugur.com/ham-radio/52-ultimeter-2000-pinouts-and-parsers.html

Ultimeter II:
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

import weewx
import weewx.abstractstation
import weewx.units
import weewx.uwxutils
import weewx.wxformulas

INHG_PER_MBAR = 0.0295333727
METER_PER_FOOT = 0.3048
MILE_PER_KM = 0.621371

DRIVER_VERSION = '0.10'
DEFAULT_PORT = '/dev/ttyS0'
DEBUG_READ = 0

def logmsg(level, msg):
    syslog.syslog(level, 'peetbros: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def loader(config_dict, engine):
    """Get the altitude, in feet, from the Station section of the dict."""
    altitude_m = weewx.units.getAltitudeM(config_dict)
    altitude_ft = altitude_m / METER_PER_FOOT
    station = PeetBros(altitude=altitude_ft, **config_dict['Ultimeter'])
    return station

class PeetBros(weewx.abstractstation.AbstractStation):
    '''weewx driver that communicates with a Peet Bros Ultimeter station

    port - serial port
    [Required. Default is /dev/ttyS0]

    model - station model, e.g., 'Ultimeter 2000' or 'Ultimeter 100'
    [Optional. Default is Ultimeter]

    polling_interval - how often to query the serial interface, seconds
    [Optional. Default is 1]

    max_tries - how often to retry serial communication before giving up
    [Optional. Default is 5]

    pressure_offset - pressure calibration, mbar
    [Optional. Default is 0]

    '''
    def __init__(self, **stn_dict):
        self.altitude = stn_dict['altitude']
        self.port = stn_dict.get('port', DEFAULT_PORT)
        self.polling_interval = float(stn_dict.get('polling_interval', 1))
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.pressure_offset = float(stn_dict.get('pressure_offset', 0))
        self.model = stn_dict.get('model', 'Ultimeter')
        self.last_rain = None
        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('using serial port %s' % self.port)
        loginf('polling interval is %s' % self.polling_interval)
        loginf('pressure offset is %s' % self.pressure_offset)
        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', DEBUG_READ))

    def getTime(self):
        with Ultimeter(self.port) as station:
            return station.get_time()

    def setTime(self, ts):
        with Ultimeter(self.port) as station:
            station.set_modem_mode()
            station.set_time(ts)

    def genLoopPackets(self):
        ntries = 0
        with Ultimeter(self.port) as station:
            station.set_logger_mode()
        while ntries < self.max_tries:
            ntries += 1
            try:
                packet = {'dateTime': int(time.time()+0.5),
                          'usUnits' : weewx.US }
                # open a new connection to the station for each reading
                with Ultimeter(self.port) as station:
                    bytes = station.get_readings()
                data = Ultimeter.parse_readings(bytes)
                packet.update(data)
                self._augment_packet(packet)
                ntries = 0
                yield packet
                if self.polling_interval:
                    time.sleep(self.polling_interval)
            except weewx.WeeWxIOError, e:
                logerr("Failed attempt %d of %d to get LOOP data: %s" %
                       (ntries, self.max_tries, e))
        else:
            msg = "Max retries (%d) exceeded for LOOP data" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    @property
    def hardware_name(self):
        return self.model

    def _augment_packet(self, packet):
        """add derived metrics to a packet"""
        # the ultimeter appears to report a (calculated) sea-level pressure
        # rather than a raw station (sensor) pressure.  so we must
        # back-calculate to find the station pressure.
        adjp = packet['barometer']
        if self.pressure_offset is not None and adjp is not None:
            adjp += self.pressure_offset * INHG_PER_MBAR # convert to inHg
        # FIXME: second temperature should be 12-hour mean temperature
        packet['pressure'] = weewx.uwxutils.TWxUtilsUS.SeaLevelToStationPressure(adjp, self.altitude, packet['outTemp'], packet['outTemp'], packet['outHumidity'])
        packet['altimeter'] = weewx.wxformulas.altimeter_pressure_US(
            packet['pressure'], self.altitude, algorithm='aaNOAA')
        packet['windchill'] = weewx.wxformulas.windchillF(
            packet['outTemp'], packet['windSpeed'])
        packet['heatindex'] = weewx.wxformulas.heatindexF(
            packet['outTemp'], packet['outHumidity'])
        packet['dewpoint'] = weewx.wxformulas.dewpointF(
            packet['outTemp'], packet['outHumidity'])

        # calculate the rain
        if self.last_rain is not None:
            packet['rain'] = packet['long_term_rain'] - self.last_rain
        else:
            packet['rain'] = None
        self.last_rain = packet['long_term_rain']

        # no wind direction when wind speed is zero
        if not packet['windSpeed']:
            packet['windDir'] = None

class Ultimeter(object):
    def __init__(self, port):
        self.port = port
        self.baudrate = 2400
        self.timeout = 30
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
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

    def read(self, nchar=1):
        try:
            buf = self.serial_port.read(nchar)
        except serial.serialutil.SerialException, e:
            raise weewx.WeeWxIOError(e)
        n = len(buf)
        if n != nchar:
            if DEBUG_READ and n:
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

    def get_time(self):
        self.set_logger_mode()
        bytes = self.get_readings()
        data = Ultimeter.parse_readings(bytes)
        d = data['day_of_year']
        m = data['minute_of_day']
        tstr = time.localtime()
        y = tstr.tm_year
        s = tstr.tm_sec
        ts = time.mktime(y,0,0,0,0,s,0,0,0) + d * 86400 + m * 60
        return ts

    def set_time(self, ts):
        tstr = time.localtime(ts)
        tcmd = ">A%04d%04d\r" % (
            tstr.tm_yday - 1, tstr.tm_min + tstr.tm_hour * 60)
        logdbg("set station time to %d (%s)" % (ts, tcmd))
        self.write(tcmd)

    def set_logger_mode(self):
        logdbg("set station to logger mode")
        self.write(">I\r")

    def set_modem_mode(self):
        logdbg("set station to modem mode")
        self.write(">\r")

    def get_readings(self):
        bytes = []
        while True:
            c = self.read(1)
            if c == "\r" or c == "\n":
                break
            elif c == '!' and len(bytes) > 0:
                break
            elif c == '!':
                bytes = []
            elif c == '-':
                bytes.append('0')
            else:
                bytes.append(c)
        if DEBUG_READ:
            logdbg("bytes: '%s'" % ' '.join(["%0.2X" % ord(c) for c in bytes]))
        if len(bytes) != 48:
            raise weewx.WeeWxIOError("Got %d bytes, expected 48" % len(bytes))
        return ''.join(bytes)

    @staticmethod
    def parse_readings(bytes):
        '''Parse the bytes in data logger format.  Each line has 2 header
        bytes, 48 data bytes, and a carriage return and newline:

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
        '''
        data = {}
        data['windSpeed'] = int(bytes[0:4], 16) * 0.1  * MILE_PER_KM # mph
        data['windDir'] = int(bytes[6:8], 16) * 1.411764 # compass degrees
        data['outTemp'] = int(bytes[8:12], 16) * 0.1 # degree_F
        data['long_term_rain'] = int(bytes[12:16], 16) * 0.01 # inch
        data['barometer'] = int(bytes[16:20], 16) * 0.1  * INHG_PER_MBAR # inHg
        data['inTemp'] = int(bytes[20:24], 16) * 0.1 # degree_F
        data['outHumidity'] = int(bytes[24:28], 16) * 0.1 # percent
        data['inHumidity'] = int(bytes[28:32], 16) * 0.1 # percent
        data['day_of_year'] = int(bytes[32:36], 16)
        data['minute_of_day'] = int(bytes[36:40], 16)
        data['daily_rain'] = int(bytes[40:44], 16) * 0.01 # inch
        data['wind_average'] = int(bytes[44:48], 16) * 0.1 * MILE_PER_KM # mph
        return data

# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/user/peetbros.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    def main():
        syslog.openlog('peetbros', syslog.LOG_PID | syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        parser = optparse.OptionParser(usage=usage)
        parser.add_option('--version', dest='version', action='store_true',
                          help='display driver version')
        parser.add_option('--port', dest='port', metavar='PORT',
                          help='serial port to which the station is connected',
                          default=DEFAULT_PORT)
        (options, args) = parser.parse_args()

        if options.version:
            print "peetbros driver version %s" % DRIVER_VERSION
            exit(0)

        with Ultimeter(options.port) as s:
            s.set_logger_mode()
            bytes = s.get_readings()
            print bytes
            data = Ultimeter.parse_readings(bytes)
            print data

if __name__ == '__main__':
    main()
