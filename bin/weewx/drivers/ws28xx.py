#!/usr/bin/python
# $Id: ws28xx.py 563 2013-03-31 16:10:16Z mwall $
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
# Thanks to Eddie De Pieri for the first Python implementation for WS-28xx.
# Eddie did the difficult work of decompiling HeavyWeather then converting
# and reverse engineering into a functional Python implementation.  Eddie's
# work was based on reverse engineering of HeavyWeather 2800 v 1.54
#
# Thanks to Luc for enumerating the console message types and for debugging
# the transceiver/console communication timing issues.

"""Classes and functions for interfacing with WS-28xx weather stations.

LaCrosse makes a number of stations in the 28xx series, including:

  WS-2810, WS-2810U-IT
  WS-2811, WS-2811SAL-IT,  WS-2811BRN-IT,  WS-2811OAK-IT
  WS-2812, WS-2812U-IT
  WS-2813
  WS-2814, WS-2814U-IT
  WS-2815, WS-2815U-IT
  C86234

The station is also sold as the TFA Primus and TechnoLine.

HeavyWeather is the software provided by LaCrosse.

There are two versions of HeavyWeather for the WS-28xx series: 1.5.4 and 1.5.4b
Apparently there is a difference between TX59UN-1-IT and TX59U-IT models (this
identifier is printed on the thermo-hygro sensor).

   HeavyWeather Version    Firmware Version    Thermo-Hygro Model
   1.54                    333 or 332          TX59UN-1-IT
   1.54b                   288, 262, 222       TX59U-IT

HeavyWeather provides the following weather station settings:

  time display: 12|24 hour
  temperature display: C|F
  air pressure display: inhg|hpa
  wind speed display: m/s|knos|bft|km/h|mph
  rain display: mm|inch
  recording interval: 1m
  keep weather station in hi-speed communication mode: true/false

According to the HeavyWeatherPro User Manual (1.54, rev2), "Hi speed mode wears
down batteries on your display much faster, and similarly consumes more power
on the PC.  We do not believe most users need to enable this setting.  It was
provided at the request of users who prefer ultra-frequent uploads."

The HeavyWeatherPro 'CurrentWeather' view is updated as data arrive from the
console.  The consonle sends current weather data approximately every 13
seconds.

Historical data are updated less frequently - every 2 hours in the default
HeavyWeatherPro configuration.

According to the User Manual, "The 2800 series weather station uses the
'original' wind chill calculation rather than the 2001 'North American'
formula because the original formula is international."

Apparently the station console determines when data will be sent, and, once
paired, the transceiver is always listening.  The station console sends a
broadcast on the hour.  If the transceiver responds, the station console may
continue to broadcast data, depending on the transceiver response and the
timing of the transceiver response.

According to the C86234 Operations Manual (Revision 7):
 - Temperature and humidity data are sent to the console every 13 seconds.
 - Wind data are sent to the temperature/humidity sensor every 17 seconds.
 - Rain data are sent to the temperature/humidity sensor every 19 seconds.
 - Air pressure is measured every 15 seconds.

The following information was obtained by logging messages from the ws28xx.py
driver in weewx and by capturing USB messages between Heavy Weather Pro for
ws2800 and the TFA Primus Weather Station via windows program USB sniffer
busdog64_v0.2.1.

Pairing

The transceiver must be paired with a console before it can receive data.  Each
frame sent by the console includes the device identifier of the transceiver
with which it is paired.

Synchronizing

When the console and transceiver stop communicating, they can be synchronized
by one of the following methods:

- Push the SET button on the console
- Wait till the next full hour when the console sends a clock message

In each case a Request Time message is received by the transceiver from the
console. The 'Send Time to WS' message should be sent within ms (10 ms
typical). The transceiver should handle the 'Time SET' message about 125 ms
after the 'Send Time to WS' message. When complete, the console and transceiver
will have been synchronized.

Timing

Outstanding history messages follow each other after 300 - 2600 ms (typical
500 ms). The best polling period appears to be 50 ms, with an average duration
of the polling loop of 3 - 4 ms. This will catch both Clock SET and History
messages. A longer polling period will catch some messages, but often misses
History messages and results in console and transceiver becoming out of synch.

Message Types

The first byte of a message determines the message type.

ID   Type               Length

01   ?                  0x0f  (15)
d0   SetRX              0x15  (21)
d1   SetTX              0x15  (21)
d5   SetFrame           0x111 (273)
d6   GetFrame           0x111 (273)
d7   SetState           0x15  (21)
d8   SetPreamblePattern 0x15  (21)
d9   Execute            0x0f  (15)
dc   ReadConfigFlash<   0x15  (21)   
dd   ReadConfigFlash>   0x15  (21)   
de   GetState           0x0a  (10)
f0   WriteReg           0x05  (5)

1. 01 message

Examples:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

01 15 00 0b 08 58 3f 53 00 00 00 00 ff 15 0b (detected via USB sniffer)
01 15 00 57 01 92 3f 53 00 00 00 00 ff 15 0a (detected via USB sniffer)

01:    messageID
02-15: ??

2. SetRX message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 - SetRX

01:    messageID
02-15: 00

3. SetTX message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d1 00 00 00 00 00 00 00 00 00 00 00 00 00 00 - SetTX

01:    messageID
02-15: 00

4. SetFrame message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d5 00 09 01 2e 05 04 cb 00 40 4e 20 .. .. .. .. .. - rtGetCurrent
d5 00 09 01 2e 00 04 cb 00 40 4e 20 .. .. .. .. .. - rtGetHistory 
d5 00 09 01 2e 01 04 cb 00 40 4e 20 .. .. .. .. .. - rtSetTime
d5 00 0c 01 2e c0 04 cb 06 28 09 75 51 30 01 .. .. - Send Time (2013-05-15 09:28:06)

01:    messageID
02:    00
03:    Message Length (starting with next byte)
04-05: DeviceID   
06:    Action
07-08: Checksum

rtGetCurrent, rtGetHistory, rtSetTime:
09:    ComInt-high byte
10:    ComInt-low byte / LatestHistoryIndex-high byte
11-12: LatestHistoryIndex-low bytes

Send Time:
09:    seconds
10:    minutes
11:    hours
12:    DayOfWeek / day-low byte
13:    month-low byte / day-high byte
14:    (year-2000)-low byte / month-high byte
15:    (year-2000)-high byte

Action:
00: rtGetHistory       
01: rtSetTime (ask console to send Request Time message)
??: rtGetConfig
??: rtSetConfig
??: rtFirstConfig 
05: rtGetCurrent
c0: Send Time to WS console

5. GetFrame message

Examples:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1  1  1  1  1  2  2 .. ..
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6  7  8  9  0  1 .. ..

00 00 06 01 2e 20 64 04 cb .. .. .. .. .. .. .. .. - clock SET
00 00 1e 01 2e 80 64 04 cb 00 4e 20 00 4d fc .. .. - Outstanding History
00 00 1e 01 2e 80 64 04 cb 00 4e 20 00 4e 20 .. .. - Actual History
00 00 d7 01 2e 60 64 04 cb .. .. .. .. .. .. .. .. - Current Weather
00 00 06 01 2e a3 64 04 cb .. .. .. .. .. .. .. .. - Request Time

01:    messageID
02:    00
03:    Message Length (starting with next byte)
04-05: DeviceID       
06:    responseType / BatteryStat
07:    Quality (in steps of 5)
08-09: Checksum

Outstanding History:
10-12: LatestHistoryIndex (Latest to sent)
13-15: ThisHistoryIndex   (Outstanding)

Actual History:
10-12: LatestHistoryIndex (same as ThisHistoryIndex)
13-15: ThisHistoryIndex

responsetype:
20: Clock SET (WsAck)
40: Config
60: CurrentData
80: HistoryData
a0: Request Time (NextAction)

6. SetState message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d7 00 00 00 00 00 00 00 00 00 00 00 00 00 00

01:    messageID
02-15: 00

7. SetPreablePattern message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d8 aa 00 00 00 00 00 00 00 00 00 00 00 00 00

01:    messageID
02:    ??
03-15: 00

8. Execute message

Example:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

d9 05 00 00 00 00 00 00 00 00 00 00 00 00 00

01:    messageID
02:    ??
03-15: 00

9. ReadConfigFlash< message

Examples:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

dc 0a 01 f5 00 01 78 a0 01 02 0a 0c 0c 01 2e
dc 0a 01 f9 01 02 0a 0c 0c 01 2e ff ff ff ff

01:    messageID
02-15: ??

10. ReadConfigFlash> message

Examples:
 0  0  0  0  0  0  0  0  0  1  1  1  1  1  1
 1  2  3  4  5  6  7  8  9  0  1  2  3  4  5

dd 0a 01 f5 cc cc cc cc cc cc cc cc cc cc cc
dd 0a 01 f9 cc cc cc cc cc cc cc cc cc cc cc

01:    messageID
02-15: ??

11. GetState message

Examples:
 0  0  0  0  0  0
 1  2  3  4  5  6

de 14 00 00 00 00 (between SetPreamblePattern and first de16 message)
de 15 00 00 00 00 Idle message
de 16 00 00 00 00 Normal message
de 0b 00 00 00 00 (detected via USB sniffer)

01:    messageID
02:    stateID
03-06: 00

12. Writereg message

Example:
 0  0  0  0  0
 1  2  3  4  5 

01:    messageID
02-05: ??
"""

# TODO: how often is currdat.lst modified with/without hi-speed mode?
# TODO: add conditionals around DataStore and LastStat

from datetime import datetime
from datetime import timedelta
from configobj import ConfigObj

import copy
import math
import platform
import syslog
import threading
import time
import traceback
import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.units

DRIVER_VERSION = '0.2'

# name of the pseudo configuration filename
# FIXME: consolidate with stats cache, since config comes from weewx
CFG_CACHE = '/tmp/ws28xx.cfg'

# location of the 'last status' cache file
STATS_CACHE = '/tmp/ws28xx.tmp'

# flags for enabling/disabling debug verbosity
DEBUG_WRITES = 0
DEBUG_COMM = 0

def logdbg(msg):
    syslog.syslog(syslog.LOG_DEBUG, 'ws28xx: %s: %s' %
                  (threading.current_thread().name, msg))

def loginf(msg):
    syslog.syslog(syslog.LOG_INFO, 'ws28xx: %s: %s' %
                  (threading.current_thread().name, msg))

def logcrt(msg):
    syslog.syslog(syslog.LOG_CRIT, 'ws28xx: %s: %s' %
                  (threading.current_thread().name, msg))

def logerr(msg):
    syslog.syslog(syslog.LOG_ERR, 'ws28xx: %s: %s' %
                  (threading.current_thread().name, msg))

# noaa definitions for station pressure, altimeter setting, and sea level
# http://www.crh.noaa.gov/bou/awebphp/definitions_pressure.php

# FIXME: this goes in wxformulas
# implementation copied from wview
def sp2ap(sp_mbar, elev_meter):
    """Convert station pressure to sea level pressure.
    http://www.wrh.noaa.gov/slc/projects/wxcalc/formulas/altimeterSetting.pdf

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    ap - sea level pressure (altimeter) in millibars
    """

    if sp_mbar is None or elev_meter is None:
        return None
    N = 0.190284
    slp = 1013.25
    ct = (slp ** N) * 0.0065 / 288
    vt = elev_meter / ((sp_mbar - 0.3) ** N)
    ap_mbar = (sp_mbar - 0.3) * ((ct * vt + 1) ** (1/N))
    return ap_mbar

# FIXME: this goes in wxformulas
# implementation copied from wview
def sp2bp(sp_mbar, elev_meter, t_C):
    """Convert station pressure to sea level pressure.

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    t_C - temperature in degrees Celsius

    bp - sea level pressure (barometer) in millibars
    """

    if sp_mbar is None or elev_meter is None or t_C is None:
        return None
    t_K = t_C + 273.15
    pt = math.exp( - elev_meter / (t_K * 29.263))
    bp_mbar = sp_mbar / pt if pt != 0 else 0
    return bp_mbar

# FIXME: this goes in weeutil.weeutil or weewx.units
def getaltitudeM(config_dict):
    # The driver needs the altitude in meters in order to calculate relative
    # pressure. Get it from the Station data and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(
        config_dict['Station'].get('altitude', (None, None)))
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    return altitude_m

# FIXME: this goes in weeutil.weeutil
# let QC handle rainfall that is too big
def calculate_rain(newtotal, oldtotal, maxsane=2):
    """Calculate the rain differential given two cumulative measurements."""
    if newtotal is not None and oldtotal is not None:
        if newtotal >= oldtotal:
            delta = newtotal - oldtotal
        else:  # wraparound
            logerr('rain counter wraparound detected: new: %s old: %s' % (newtotal, oldtotal))
            delta = None
    else:
        delta = None
    return delta

def loader(config_dict, engine):
    altitude_m = getaltitudeM(config_dict)
    station = WS28xx(altitude=altitude_m, **config_dict['WS28xx'])
    return station

class WS28xx(weewx.abstractstation.AbstractStation):
    """Driver for LaCrosse WS28xx stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        altitude: Altitude of the station
        [Required. No default]

        pressure_offset: Calibration offset in millibars for the station
        pressure sensor.  This offset is added to the station sensor output
        before barometer and altimeter pressures are calculated.
        [Optional. No Default]

        model: Which station model is this?
        [Optional. Default is 'LaCrosse WS28xx']

        transceiver_frequency: Frequency for transceiver-to-console.  Specify
        either US or EU.
        [Required. Default is US]

        polling_interval: How often to sample the USB interface for data.
        [Optional. Default is 30 seconds]

        vendor_id: The USB vendor ID for the transceiver.
        [Optional. Default is 6666]

        product_id: The USB product ID for the transceiver.
        [Optional. Default is 5555]
        """

        self.altitude          = stn_dict['altitude']
        self.model             = stn_dict.get('model', 'LaCrosse WS28xx')
        self.cfgfile           = CFG_CACHE
        self.polling_interval  = int(stn_dict.get('polling_interval', 30))
        self.frequency         = stn_dict.get('transceiver_frequency', 'US')
        self.vendor_id         = int(stn_dict.get('vendor_id',  '0x6666'), 0)
        self.product_id        = int(stn_dict.get('product_id', '0x5555'), 0)
        self.pressure_offset   = stn_dict.get('pressure_offset', None)
        if self.pressure_offset is not None:
            self.pressure_offset = float(self.pressure_offset)

        self._service = None
        self._last_rain = None
        self._last_obs_ts = None

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('frequency is %s' % self.frequency)
        loginf('altitude is %s meters' % str(self.altitude))
        loginf('pressure offset is %s' % str(self.pressure_offset))

    @property
    def hardware_name(self):
        return self.model

    def openPort(self):
        # FIXME: init the usb here
        pass

    def closePort(self):
        # FIXME: shutdown the usb port here
        pass

    def genLoopPackets(self):
        """Generator function that continuously returns decoded packets"""

        self.startup()
        maxnodata = 20
        nodata = 0
        while True:
            try:
                packet = self.get_observation()
                if packet is not None:
                    yield packet
                    nodata = 0
                else:
                    nodata += 1
                if nodata >= maxnodata:
                    dur = nodata * self.polling_interval
                    logerr('no new data after %d seconds' % dur)
                    nodata = 0
                time.sleep(self.polling_interval)
            except KeyboardInterrupt:
                self.shutdown()
                raise
            except Exception, e:
                logerr('exception in genLoopPackets: %s' % e)
                if weewx.debug:
                    traceback.print_exc()
                raise

    def startup(self):
        if self._service is not None:
            return
        self._service = CCommunicationService(self.cfgfile)
        self._service.setup(self.frequency)
        self._service.startRFThread()

    def shutdown(self):
        self._service.stopRFThread()
        self._service.teardown()
        self._service = None

    def pair(self, msg_to_console=False, maxtries=0):
        ntries = 0
        while ntries < maxtries or maxtries == 0:
            if self._service.DataStore.getDeviceRegistered():
                return
            ntries += 1
            msg = 'press [v] key on station console'
            if maxtries > 0:
                msg += ' (attempt %d of %d)' % (ntries, maxtries)
            else:
                msg += ' (attempt %d)' % ntries
            if msg_to_console:
                print msg
            logerr(msg)
            timeout = 30000 # milliseconds
            self._service.DataStore.FirstTimeConfig(timeout)
        else:
            raise Exception('Transceiver not paired to console.')

    def check_transceiver(self, msg_to_console=False, maxtries=3):
        ntries = 0
        while ntries < maxtries:
            ntries += 1
            t = self._service.DataStore.getFlag_FLAG_TRANSCEIVER_PRESENT()
            if t:
                msg = 'transceiver is present'
            else:
                msg = 'transceiver not found (attempt %d of %d)' % (
                    ntries, maxtries)
            if msg_to_console:
                print msg
            loginf(msg)
            if t:
                return
            time.sleep(5)
        else:
            raise Exception('Transceiver not responding.')

    def get_datum_diff(self, v, np):
        if abs(np - v) > 0.001:
            return v
        return None

    def get_datum_match(self, v, np):
        if np != v:
            return v
        return None

    def get_observation(self):
        ts = self._service.DataStore.CurrentWeather._timestamp
        if ts is None:
            return None
        if self._last_obs_ts is not None and self._last_obs_ts == ts:
            return None
        self._last_obs_ts = ts

        # add elements required for weewx LOOP packets
        packet = {}
        packet['usUnits'] = weewx.METRIC
        packet['dateTime'] = int(ts + 0.5)

        # data from the station sensors
        packet['inTemp'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._IndoorTemp,
            CWeatherTraits.TemperatureNP())
        packet['inHumidity'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._IndoorHumidity,
            CWeatherTraits.HumidityNP())
        packet['outTemp'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._OutdoorTemp,
            CWeatherTraits.TemperatureNP())
        packet['outHumidity'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._OutdoorHumidity,
            CWeatherTraits.HumidityNP())
        packet['pressure'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._PressureRelative_hPa,
            CWeatherTraits.PressureNP())
        packet['windSpeed'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._WindSpeed,
            CWeatherTraits.WindNP())
        packet['windGust'] = self.get_datum_diff(
            self._service.DataStore.CurrentWeather._Gust,
            CWeatherTraits.WindNP())

        if packet['windSpeed'] is not None:
            packet['windSpeed'] *= 3.6 # weewx wants km/h
            packet['windDir'] = self._service.DataStore.CurrentWeather._WindDirection * 360 / 16
        else:
            packet['windDir'] = None

        if packet['windGust'] is not None:
            packet['windGust'] *= 3.6 # weewx wants km/h
            packet['windGustDir'] = self._service.DataStore.CurrentWeather._GustDirection * 360 / 16
        else:
            packet['windGustDir'] = None

        # calculated elements not directly reported by station
        packet['rainRate'] = self.get_datum_match(
            self._service.DataStore.CurrentWeather._Rain1H,
            CWeatherTraits.RainNP())
        rain_total = self.get_datum_match(
            self._service.DataStore.CurrentWeather._RainTotal,
            CWeatherTraits.RainNP())
        delta = calculate_rain(rain_total, self._last_rain)
        packet['rain'] = delta
        self._last_rain = rain_total

        packet['heatindex'] = weewx.wxformulas.heatindexC(
            packet['outTemp'], packet['outHumidity'])
        packet['dewpoint'] = weewx.wxformulas.dewpointC(
            packet['outTemp'], packet['outHumidity'])
        packet['windchill'] = weewx.wxformulas.windchillC(
            packet['outTemp'], packet['windSpeed'])

        # station reports gauge pressure, must calculate other pressures
        adjp = packet['pressure']
        if self.pressure_offset is not None and adjp is not None:
            adjp += self.pressure_offset
        packet['barometer'] = sp2bp(adjp, self.altitude, packet['outTemp'])
        packet['altimeter'] = sp2ap(adjp, self.altitude)

        # track the signal strength and battery levels
        packet['signal'] = self._service.DataStore.LastStat.LastLinkQuality
        packet['battery'] = self._service.DataStore.LastStat.LastBatteryStatus

        return packet

    def get_config(self):
        logdbg('get station configuration')
        self._service.DataStore.GetConfig()

# The following classes and methods are adapted from the implementation by
# eddie de pieri, which is in turn based on the HeavyWeather implementation.

def frame2str(n, buf):
    strbuf = ''
    for i in xrange(0,n):
        strbuf += str('%.2x' % buf[i])
    return strbuf

class BitHandling:
    # return a nonzero result, 2**offset, if the bit at 'offset' is one.
    @staticmethod
    def testBit(int_type, offset):
        mask = 1 << offset
        return(int_type & mask)

    # return an integer with the bit at 'offset' set to 1.
    @staticmethod
    def setBit(int_type, offset):
        mask = 1 << offset
        return(int_type | mask)

    # return an integer with the bit at 'offset' set to 1.
    @staticmethod
    def setBitVal(int_type, offset, val):
        mask = val << offset
        return(int_type | mask)

    # return an integer with the bit at 'offset' cleared.
    @staticmethod
    def clearBit(int_type, offset):
        mask = ~(1 << offset)
        return(int_type & mask)

    # return an integer with the bit at 'offset' inverted, 0->1 and 1->0.
    @staticmethod
    def toggleBit(int_type, offset):
        mask = 1 << offset
        return(int_type ^ mask)

class EHistoryInterval:
    hi01Min          = 0
    hi05Min          = 1
    hi10Min          = 2
    hi15Min          = 3
    hi20Min          = 4
    hi30Min          = 5
    hi60Min          = 6
    hi02Std          = 7
    hi04Std          = 8
    hi06Std          = 9
    hi08Std          = 0xA
    hi12Std          = 0xB
    hi24Std          = 0xC

class EWindspeedFormat:
    wfMs             = 0
    wfKnots          = 1
    wfBFT            = 2
    wfKmh            = 3
    wfMph            = 4

class ERainFormat:
    rfMm             = 0
    rfInch           = 1

class EPressureFormat:
    pfinHg           = 0
    pfHPa            = 1

class ETemperatureFormat:
    tfFahrenheit     = 0
    tfCelsius        = 1

class EClockMode:
    ct24H            = 0
    ctAmPm           = 1

class EWeatherTendency:
    TREND_NEUTRAL    = 0
    TREND_UP         = 1
    TREND_DOWN       = 2
    TREND_ERR        = 3

class EWeatherState:
    WEATHER_BAD      = 0
    WEATHER_NEUTRAL  = 1
    WEATHER_GOOD     = 2
    WEATHER_ERR      = 3

class EWindDirection:
    wdN              = 0
    wdNNE            = 1
    wdNE             = 2
    wdENE            = 3
    wdE              = 4
    wdESE            = 5
    wdSE             = 6
    wdSSE            = 7
    wdS              = 8
    wdSSW            = 9
    wdSW             = 0x0A
    wdWSW            = 0x0B
    wdW              = 0x0C
    wdWNW            = 0x0D
    wdNW             = 0x0E
    wdNNW            = 0x0F
    wdERR            = 0x10
    wdInvalid        = 0x11

class EResetMinMaxFlags:
    rmTempIndoorHi   = 0
    rmTempIndoorLo   = 1
    rmTempOutdoorHi  = 2
    rmTempOutdoorLo  = 3
    rmWindchillHi    = 4
    rmWindchillLo    = 5
    rmDewpointHi     = 6
    rmDewpointLo     = 7
    rmHumidityIndoorLo  = 8
    rmHumidityIndoorHi  = 9
    rmHumidityOutdoorLo  = 0x0A
    rmHumidityOutdoorHi  = 0x0B
    rmWindspeedHi    = 0x0C
    rmWindspeedLo    = 0x0D
    rmGustHi         = 0x0E
    rmGustLo         = 0x0F
    rmPressureLo     = 0x10
    rmPressureHi     = 0x11
    rmRain1hHi       = 0x12
    rmRain24hHi      = 0x13
    rmRainLastWeekHi  = 0x14
    rmRainLastMonthHi  = 0x15
    rmRainTotal      = 0x16
    rmInvalid        = 0x17

class ERequestType:
    rtGetCurrent     = 0
    rtGetHistory     = 1
    rtGetConfig      = 2
    rtSetConfig      = 3
    rtSetTime        = 4
    rtFirstConfig    = 5
    rtINVALID        = 6

class ERequestState:
    rsQueued         = 0
    rsRunning        = 1
    rsFinished       = 2
    rsPreamble       = 3
    rsWaitDevice     = 4
    rsWaitConfig     = 5
    rsError          = 6
    rsChanged        = 7
    rsINVALID        = 8

# frequency standards and their associated transmission frequencies
class EFrequency:
    fsUS             = 'US'
    tfUS             = 905000000
    fsEU             = 'EU'
    tfEU             = 868300000

def getFrequency(standard):
    if standard == EFrequency.fsUS:
        return EFrequency.tfUS
    elif standard == EFrequency.fsEU:
        return EFrequency.tfEU
    logerr("unknown frequency standard '%s', using US" % standard)
    return EFrequency.tfUS

def getFrequencyStandard(frequency):
    if frequency == EFrequency.tfUS:
        return EFrequency.fsUS
    elif frequency == EFrequency.tfEU:
        return EFrequency.fsEU
    logerr("unknown frequency '%s', using US" % frequency)
    return EFrequency.fsUS

class CWeatherTraits(object):
    windDirMap = {
        0:"N", 1:"NNE", 2:"NE", 3:"ENE", 4:"E", 5:"ESE", 6:"SE", 7:"SSE",
        8:"S", 9:"SSW", 10:"SW", 11:"WSW", 12:"W", 13:"WNW", 14:"NW",
        15:"NWN", 16:"err", 17:"inv" }
    forecastMap = {
        0:"Rainy(Bad)", 1:"Cloudy(Neutral)", 2:"Sunny(Good)",  3:"Error" }
    trends = {
        0:"Stable(Neutral)", 1:"Rising(Up)", 2:"Falling(Down)", 3:"Error" }

    @staticmethod
    def TemperatureNP():
        return 81.099998

    @staticmethod
    def TemperatureOFL():
        return 136.0

    @staticmethod
    def PressureNP():
        return 10101010.0

    @staticmethod
    def PressureOFL():
        return 16666.5

    @staticmethod
    def HumidityNP():
        return 110.0

    @staticmethod
    def HumidityOFL():
        return 121.0

    @staticmethod
    def RainNP():
        return -0.2

    @staticmethod
    def RainOFL():
        return 16666.664

    @staticmethod
    def WindNP():
        return 51.0

    @staticmethod
    def WindOFL():
        return 51.099998

    @staticmethod
    def TemperatureOffset():
        return 40.0

class CMeasurement:
    _Value = 0.0
    _ResetFlag = 23
    _IsError = 1
    _IsOverflow = 1
    _Time = time.time()

    def Reset(self):
        self._Value = 0.0
        self._ResetFlag = 23
        self._IsError = 1
        self._IsOverflow = 1

class CMinMaxMeasurement(object):
    def __init__(self):
        self._Min = CMeasurement()
        self._Max = CMeasurement()

class USBHardware(object):
    @staticmethod
    def IsOFL2(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =   (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+0] >>  4) == 15
        else:
            result =   (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15
        return result

    @staticmethod
    def IsOFL3(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =   (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15
        else:
            result =   (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15
        return result

    @staticmethod
    def IsOFL5(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =     (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15 \
                or (buf[0][start+2] & 0xF) == 15
        else:
            result =     (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15 \
                or (buf[0][start+2] & 0xF) == 15 \
                or (buf[0][start+2] >>  4) == 15
        return result

    @staticmethod
    def IsErr2(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =    (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15
        else:
            result =    (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15
        return result
        
    @staticmethod
    def IsErr3(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =     (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or  (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15
        else:
            result =     (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or  (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 10
        return result
        
    @staticmethod
    def IsErr5(buf, start, startOnLowNibble):
        if startOnLowNibble :
            result =     (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15 \
                or (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15 \
                or (buf[0][start+2] & 0xF) >= 10 \
                and (buf[0][start+2] & 0xF) != 15
        else:
            result =     (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15 \
                or (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15 \
                or (buf[0][start+2] & 0xF) >= 10 \
                and (buf[0][start+2] & 0xF) != 15 \
                or (buf[0][start+2] >>  4) >= 10 \
                and (buf[0][start+2] >>  4) != 15
        return result

    @staticmethod
    def ToCurrentTempBytes(bufer, c, d):
        logdbg('ToCurrentTempBytes: NOT IMPLEMENTED')

    @staticmethod
    def To2Pre(buf, start, startOnLowNibble):
        if startOnLowNibble:
            rawpre  = (buf[0][start+0] & 0xf)*  1 \
                + (buf[0][start+0]  >> 4)* 10
        else:
            rawpre  = (buf[0][start+0]  >> 4)*  1 \
                + (buf[0][start+1] & 0xf)* 10
        return rawpre

    @staticmethod
    def ToRainAlarmBytes(buf,alarm):
        logdbg('ToRainAlarmBytes: NOT IMPLEMENTED')

    @staticmethod
    def ToDateTime(buf, start, startOnLowNibble, label):
        result = None
        if ( USBHardware.IsErr2(buf, start+0, startOnLowNibble)
             or USBHardware.IsErr2(buf, start+1, startOnLowNibble)
             or USBHardware.IsErr2(buf, start+2, startOnLowNibble)
             or USBHardware.IsErr2(buf, start+3, startOnLowNibble)
             or USBHardware.IsErr2(buf, start+4, startOnLowNibble)
             or USBHardware.To2Pre(buf, start+3, startOnLowNibble) > 12):
            logerr('ToDateTime: bogus date for %s: error status in buffer' %
                   label)
        else:
            minutes = USBHardware.To2Pre(buf, start+0, startOnLowNibble)
            hours   = USBHardware.To2Pre(buf, start+1, startOnLowNibble)
            days    = USBHardware.To2Pre(buf, start+2, startOnLowNibble)
            month   = USBHardware.To2Pre(buf, start+3, startOnLowNibble)
            year    = USBHardware.To2Pre(buf, start+4, startOnLowNibble) + 2000
            try:
                result = datetime(year, month, days, hours, minutes)
            except:
                logerr(('ToDateTime: bogus date for %s:'
                        ' bad date conversion from'
                        ' %s %s %s %s %s') %
                       (label, minutes, hours, days, month, year))
        if result is None:
            # FIXME: use None instead of a really old date to indicate invalid
            result = datetime(1900, 01, 01, 00, 00)
        return result
        
    @staticmethod
    def ToHumidity(buf, start, startOnLowNibble):
        if USBHardware.IsErr2(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.HumidityNP()
        else:
            if USBHardware.IsOFL2(buf, start+0, startOnLowNibble) :
                result = CWeatherTraits.HumidityOFL()
            else:
                result = USBHardware.To2Pre(buf, start, startOnLowNibble)
        return result

    @staticmethod
    def ToTemperature(buf, start, startOnLowNibble):
        if USBHardware.IsErr5(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.TemperatureNP()
        elif USBHardware.IsOFL5(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.TemperatureOFL()
        else:
            if startOnLowNibble:
                rawtemp = (buf[0][start+0] & 0xf)*  0.001 \
                    + (buf[0][start+0] >>  4)*  0.01  \
                    + (buf[0][start+1] & 0xf)*  0.1   \
                    + (buf[0][start+1] >>  4)*  1     \
                    + (buf[0][start+2] & 0xf)* 10
            else:
                rawtemp = (buf[0][start+0] >>  4)*  0.001 \
                    + (buf[0][start+1] & 0xf)*  0.01  \
                    + (buf[0][start+1] >>  4)*  0.1   \
                    + (buf[0][start+2] & 0xf)*  1     \
                    + (buf[0][start+2] >>  4)* 10
            result = rawtemp - CWeatherTraits.TemperatureOffset()
        return result

    @staticmethod
    def To4Pre3Post(buf, start):
        if ( USBHardware.IsErr5(buf, start+0, 1) or
             USBHardware.IsErr2(buf, start+2, 0) ):
            result = CWeatherTraits.RainNP()
        elif ( USBHardware.IsOFL5(buf, start+1, 1) or
               USBHardware.IsOFL2(buf, start+2, 0) ):
            result = CWeatherTraits.RainOFL()
        else:
            result  = (buf[0][start+0] & 0xf)*  0.001 \
                + (buf[0][start+0] >>  4)*  0.01  \
                + (buf[0][start+1] & 0xf)*  0.1   \
                + (buf[0][start+1] >>  4)*   1    \
                + (buf[0][start+2] & 0xf)*  10    \
                + (buf[0][start+2] >>  4)* 100    \
                + (buf[0][start+3] & 0xf)*1000
        return result

    @staticmethod
    def To4Pre2Post(buf, start):
        if ( USBHardware.IsErr2(buf,start+0,1) or
             USBHardware.IsErr2(buf,start+1, 1) or
             USBHardware.IsErr2(buf, start+2, 1) ):
            result = CWeatherTraits.RainNP()
        elif ( USBHardware.IsOFL2(buf,start+0, 1) or
               USBHardware.IsOFL2(buf, start+1, 1) or
               USBHardware.IsOFL2(buf, start+2, 1) ):
            result = CWeatherTraits.RainOFL()
        else:
            result  = (buf[0][start+0] & 0xf)*  0.01 \
                + (buf[0][start+0] >>  4)*  0.1  \
                + (buf[0][start+1] & 0xf)*   1   \
                + (buf[0][start+1] >>  4)*  10   \
                + (buf[0][start+2] & 0xf)* 100   \
                + (buf[0][start+2] >>  4)*1000
        return result

    @staticmethod
    def ToWindspeed(buf, start): #m/s
        val = USBHardware.ByteToFloat(buf, start, 1, 16, 6)
        val = val / 256.0
        val = val / 100.0              #km/h
        val = val / 3.599999904632568  #m/s
        return val

    @staticmethod
    def ByteToFloat(buf, start,startOnLowNibble, base, pre):
        lowNibble = startOnLowNibble
        val = 0
        byteCounter = 0
        i = 0
        while i < pre:
            if pre > 0 :
                digit = 0
                if lowNibble :
                    digit = buf[0][start+byteCounter] & 0xF
                else:
                    digit = buf[0][start+byteCounter] >> 4
                if not lowNibble :
                    byteCounter += 1
                if lowNibble == 0:
                    lowNibble=1
                else:
                    lowNibble=0
                power = base**i
                val += digit * power
            i += 1
        return val

    @staticmethod
    def ReverseByteOrder(buf, start, Count):
        nbuf=buf[0]
        for i in xrange(0, Count >> 1):
            tmp = nbuf[start + i]
            nbuf[start + i] = nbuf[start + Count - i - 1]
            nbuf[start + Count - i - 1 ] = tmp
        buf[0]=nbuf

    @staticmethod
    def ReadWindDirectionShared(buf, start):
        return (buf[0][0+start] & 0xf, buf[0][start] >> 4)

    @staticmethod
    def ReadPressureShared(buf, start):
        return ( USBHardware.ToPressure(buf,start,1) ,
                 USBHardware.ToPressureInhg(buf,start+2,0))

    @staticmethod
    def ToPressure(buf, start, startOnLowNibble):
        if USBHardware.IsErr5(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.PressureNP()
        elif USBHardware.IsOFL5(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.PressureOFL()
        else:
            if startOnLowNibble :
                rawresult = (buf[0][start+2] & 0xF)* 1000   \
                    + (buf[0][start+1] >>  4)*  100   \
                    + (buf[0][start+1] & 0xF)*   10   \
                    + (buf[0][start+0] >>  4)*    1   \
                    + (buf[0][start+0] & 0xF)*    0.1
            else:
                rawresult = (buf[0][start+2] >>  4)* 1000   \
                    + (buf[0][start+2] & 0xF)*  100   \
                    + (buf[0][start+1] >>  4)*   10   \
                    + (buf[0][start+1] & 0xF)*    1   \
                    + (buf[0][start+0] >>  4)*    0.1
            result = rawresult
        return result

    @staticmethod
    def ToPressureInhg(buf, start, startOnLowNibble):
        if USBHardware.IsErr5(buf, start+0, startOnLowNibble) :
            rawresult = CWeatherTraits.PressureNP()
        elif USBHardware.IsOFL5(buf, start+0, startOnLowNibble) :
            rawresult = CWeatherTraits.PressureOFL()
        else:
            if startOnLowNibble :
                rawresult = (buf[0][start+2] & 0xF)* 100    \
                    + (buf[0][start+1] >>  4)*  10    \
                    + (buf[0][start+1] & 0xF)*   1    \
                    + (buf[0][start+0] >>  4)*   0.1  \
                    + (buf[0][start+0] & 0xF)*   0.01
            else:
                rawresult = (buf[0][start+2] >>  4)* 100    \
                    + (buf[0][start+2] & 0xF)*  10    \
                    + (buf[0][start+1] >>  4)*   1    \
                    + (buf[0][start+0] & 0xF)*   0.1  \
                    + (buf[0][start+0] >>  4)*   0.01
            result = rawresult
        return result

    @staticmethod
    def ToTemperatureRingBuffer(buf, start, startOnLowNibble):
        if USBHardware.IsErr3(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.TemperatureNP()
        elif USBHardware.IsOFL3(buf, start+0, startOnLowNibble) :
            result = CWeatherTraits.TemperatureOFL()
        else:
            if startOnLowNibble :
                    #rawtemp   =  (buf[0][start+0] & 0xF)* 10   \
                    #	  +  (buf[0][start+0] >>  4)*  1   \
                    #	  +  (buf[0][start+1] & 0xF)*  0.1
                rawtemp   =  (buf[0][start+0] & 0xF)*  0.1 \
                    +  (buf[0][start+0] >>  4)*  1   \
                    +  (buf[0][start+1] & 0xF)* 10
            else:
                    #rawtemp   =  (buf[0][start+0] >>  4)* 10   \
                    #	  +  (buf[0][start+1] & 0xF)*  1   \
                    #	  +  (buf[0][start+1] >>  4)*  0.1
                rawtemp   =  (buf[0][start+0] >>  4)*  0.1 \
                    +  (buf[0][start+1] & 0xF)*  1   \
                    +  (buf[0][start+1] >>  4)* 10  
            result = rawtemp - CWeatherTraits.TemperatureOffset()
        return result

    @staticmethod
    def ToWindspeedRingBuffer(buf, start):
        if buf[0][start+0] != 254 or (buf[0][start+1] & 0xF) != 1 :
            if buf[0][start+0] != 255 or (buf[0][start+1] & 0xF) != 1 :
                val = USBHardware.ByteToFloat(buf, start, 1, 16, 3)
                val = val / 10.0
                result = val
            else:
                result = CWeatherTraits.WindOFL()
        else:
            result = CWeatherTraits.WindNP()
        return result


def get_temperature(buf, label):
    tbuf = [0]
    tbuf[0] = buf
    v = USBHardware.ToTemperature(tbuf, 0, True)
    vmin = USBHardware.ToTemperature(tbuf, 2, False)
    vmax = USBHardware.ToTemperature(tbuf, 5, True)
    mm = CMinMaxMeasurement()
    mm._Min._Value = vmin
    mm._Min._IsError = 1 if vmin == CWeatherTraits.TemperatureNP() else 0
    mm._Min._IsOverflow = 1 if vmin == CWeatherTraits.TemperatureOFL() else 0
    mm._Max._Value = vmax
    mm._Max._IsError = 1 if vmax == CWeatherTraits.TemperatureNP() else 0
    mm._Max._IsOverflow = 1 if vmax == CWeatherTraits.TemperatureOFL() else 0
    if mm._Min._IsError or mm._Min._IsOverflow:
        mm._Min._Time = None
    else:
        mm._Min._Time = USBHardware.ToDateTime(tbuf, 7, False, label)
    if mm._Max._IsError or mm._Max._IsOverflow:
        mm._Max._Time = None
    else:
        mm._Max._Time = USBHardware.ToDateTime(tbuf, 12, False, label)
    return (v,mm)

def get_humidity(buf, label):
    tbuf = [0]
    tbuf[0] = buf
    v = USBHardware.ToHumidity(tbuf, 0, True)
    vmin = USBHardware.ToHumidity(tbuf, 1, True)
    vmax = USBHardware.ToHumidity(tbuf, 2, True)
    mm = CMinMaxMeasurement()
    mm._Min._Value = vmin
    mm._Min._IsError = 1 if vmin == CWeatherTraits.HumidityNP() else 0
    mm._Min._IsOverflow = 1 if vmin == CWeatherTraits.HumidityOFL() else 0
    mm._Max._Value = vmax
    mm._Max._IsError = 1 if vmax == CWeatherTraits.HumidityNP() else 0
    mm._Max._IsOverflow = 1 if vmax == CWeatherTraits.HumidityOFL() else 0
    if mm._Min._IsError or mm._Min._IsOverflow:
        mm._Min._Time = None
    else:
        mm._Min._Time = USBHardware.ToDateTime(tbuf, 3, True, label)
    if mm._Max._IsError or mm._Max._IsOverflow:
        mm._Max._Time = None
    else:
        mm._Max._Time = USBHardware.ToDateTime(tbuf, 8, True, label)
    return (v,mm)

def get_time(buf, pos, startOnLowNibble, v, vnp, vofl, label):
    if v == vnp or v == vofl:
        return None
    return USBHardware.ToDateTime(buf, pos, startOnLowNibble, label)

def reverse_byte_order(buf):
    nbuf = []
    for i in xrange(len(buf)):
        nbuf.append(buf[len(buf)-i-1])
    return nbuf

class CCurrentWeatherData(object):

    def __init__(self):
        self._timestamp = None
        self._PressureRelative_hPa = CWeatherTraits.PressureNP()
        self._PressureRelative_hPaMinMax = CMinMaxMeasurement()
        self._PressureRelative_inHg = CWeatherTraits.PressureNP()
        self._PressureRelative_inHgMinMax = CMinMaxMeasurement()
        self._WindSpeed = CWeatherTraits.WindNP()
        self._WindSpeedMinMax = CMinMaxMeasurement()
        self._WindDirection = EWindDirection.wdERR
        self._WindDirection1 = EWindDirection.wdERR
        self._WindDirection2 = EWindDirection.wdERR
        self._WindDirection3 = EWindDirection.wdERR
        self._WindDirection4 = EWindDirection.wdERR
        self._WindDirection5 = EWindDirection.wdERR
        self._Gust = CWeatherTraits.WindNP()
        self._GustMinMax = CMinMaxMeasurement()
        self._GustDirection = EWindDirection.wdERR
        self._GustDirection1 = EWindDirection.wdERR
        self._GustDirection2 = EWindDirection.wdERR
        self._GustDirection3 = EWindDirection.wdERR
        self._GustDirection4 = EWindDirection.wdERR
        self._GustDirection5 = EWindDirection.wdERR
        self._Rain1H = CWeatherTraits.RainNP()
        self._Rain1HMax = CMinMaxMeasurement()
        self._Rain24H = CWeatherTraits.RainNP()
        self._Rain24HMax = CMinMaxMeasurement()
        self._RainLastWeek = CWeatherTraits.RainNP()
        self._RainLastWeekMax = CMinMaxMeasurement()
        self._RainLastMonth = CWeatherTraits.RainNP()
        self._RainLastMonthMax = CMinMaxMeasurement()
        self._RainTotal = CWeatherTraits.RainNP()
        self._LastRainReset = None
        self._IndoorTemp = CWeatherTraits.TemperatureNP()
        self._IndoorTempMinMax = CMinMaxMeasurement()
        self._OutdoorTemp = CWeatherTraits.TemperatureNP()
        self._OutdoorTempMinMax = CMinMaxMeasurement()
        self._IndoorHumidity = CWeatherTraits.HumidityNP()
        self._IndoorHumidityMinMax = CMinMaxMeasurement()
        self._OutdoorHumidity = CWeatherTraits.HumidityNP()
        self._OutdoorHumidityMinMax = CMinMaxMeasurement()
        self._Dewpoint = CWeatherTraits.TemperatureNP()
        self._DewpointMinMax = CMinMaxMeasurement()
        self._Windchill = CWeatherTraits.TemperatureNP()
        self._WindchillMinMax = CMinMaxMeasurement()
        self._WeatherState = EWeatherState.WEATHER_ERR
        self._WeatherTendency = EWeatherTendency.TREND_ERR
        self._AlarmRingingFlags = 0
        self._AlarmMarkedFlags = 0

    def read(self, buf, pos):
        logdbg('CCurrentWeatherData::read')
        newbuf = [0]
        newbuf[0] = buf[0]

        #CCurrentWeatherData::readAlarmFlags(thisa, buf, &thisa->_AlarmRingingFlags);

        self._timestamp = time.time()

        USBHardware.ReverseByteOrder(newbuf, pos + 0, 2);
        self._WeatherState = newbuf[0][pos + 2] & 0xF;
        self._WeatherTendency = (newbuf[0][pos + 2] >> 4) & 0xF;

        (self._IndoorTemp, self._IndoorTempMinMax) = get_temperature(
            reverse_byte_order(newbuf[0][pos+3:pos+21]), 'IndoorTemp')
        (self._OutdoorTemp, self._OutdoorTempMinMax) = get_temperature(
            reverse_byte_order(newbuf[0][pos+21:pos+39]), 'OutdoorTemp')
        (self._Windchill, self._WindchillMinMax) = get_temperature(
            reverse_byte_order(newbuf[0][pos+39:pos+57]), 'Windchill')
        (self._Dewpoint, self._DewpointMinMax) = get_temperature(
            reverse_byte_order(newbuf[0][pos+57:pos+75]), 'Dewpoint')
        (self._IndoorHumidity, self._IndoorHumidityMinMax) = get_humidity(
            reverse_byte_order(newbuf[0][pos+75:pos+88]), 'IndoorHumidity')
        (self._OutdoorHumidity, self._OutdoorHumidityMinMax) = get_humidity(
            reverse_byte_order(newbuf[0][pos+88:pos+101]), 'OutdoorHumidity')

        USBHardware.ReverseByteOrder(newbuf, pos + 101, 0xB)
        self._RainLastMonth = USBHardware.To4Pre2Post(newbuf, pos+101)
        self._RainLastMonthMax._Max._Value = USBHardware.To4Pre2Post(
            newbuf, pos+104)
        self._RainLastMonthMax._Max._Time = get_time(
            newbuf, pos+107, True,
            self._RainLastMonthMax._Max._Value,
            CWeatherTraits.RainNP(),
            CWeatherTraits.RainOFL(),
            'RainLastMonthMax')

        USBHardware.ReverseByteOrder(newbuf, pos + 112, 0xB)
        self._RainLastWeek = USBHardware.To4Pre2Post(newbuf, pos+112)
        self._RainLastWeekMax._Max._Value = USBHardware.To4Pre2Post(
            newbuf, pos+115)
        self._RainLastWeekMax._Max._Time = get_time(
            newbuf, pos+118, True,
            self._RainLastWeekMax._Max._Value,
            CWeatherTraits.RainNP(),
            CWeatherTraits.RainOFL(),
            'RainLastWeekMax')

        USBHardware.ReverseByteOrder(newbuf, pos + 123, 0xB)
        self._Rain24H = USBHardware.To4Pre2Post(newbuf, pos+123)
        self._Rain24HMax._Max._Value = USBHardware.To4Pre2Post(newbuf, pos+126)
        self._Rain24HMax._Max._Time = get_time(newbuf, pos+129, True,
                                               self._Rain24HMax._Max._Value,
                                               CWeatherTraits.RainNP(),
                                               CWeatherTraits.RainOFL(),
                                               'Rain24HMax')

        USBHardware.ReverseByteOrder(newbuf, pos + 134, 0xB)
        self._Rain1H = USBHardware.To4Pre2Post(newbuf,pos + 134)
        self._Rain1HMax._Max._Value = USBHardware.To4Pre2Post(newbuf,pos + 137)
        self._Rain1HMax._Max._Time = get_time(newbuf, pos+140, True,
                                              self._Rain1HMax._Max._Value,
                                              CWeatherTraits.RainNP(),
                                              CWeatherTraits.RainOFL(),
                                              'Rain1HMax')

        USBHardware.ReverseByteOrder(newbuf, pos + 145, 9)
        self._RainTotal = USBHardware.To4Pre3Post(newbuf, pos + 145)
        self._LastRainReset = USBHardware.ToDateTime(newbuf, pos+148, False, 'LastRainReset')

        USBHardware.ReverseByteOrder(newbuf, pos + 154, 0xF);
        self._WindSpeed = USBHardware.ToWindspeed(newbuf,pos + 154)
        self._WindSpeedMinMax._Max._Value = USBHardware.ToWindspeed(newbuf, pos + 157)
        self._WindSpeedMinMax._Max._Time = get_time(
            newbuf, pos+160, True,
            self._WindSpeedMinMax._Max._Value,
            CWeatherTraits.WindNP(),
            CWeatherTraits.WindOFL(),
            'WindSpeedMax')
        self._WindSpeedMinMax._Max._IsError = (
            self._WindSpeedMinMax._Max._Value == CWeatherTraits.WindNP())
        self._WindSpeedMinMax._Max._IsOverflow = (
            self._WindSpeedMinMax._Max._Value == CWeatherTraits.WindOFL())

        #  WindErrFlags = buf[165]
        (w ,w1) = USBHardware.ReadWindDirectionShared(newbuf, pos + 166)
        (w2,w3) = USBHardware.ReadWindDirectionShared(newbuf, pos + 167)
        (w4,w5) = USBHardware.ReadWindDirectionShared(newbuf, pos + 168)
        self._WindDirection = w;
        self._WindDirection1 = w1;
        self._WindDirection2 = w2;
        self._WindDirection3 = w3;
        self._WindDirection4 = w4;
        self._WindDirection5 = w5;
        #  CCurrentWeatherData::CheckWindErrFlags(
        #    thisa,
        #    WindErrFlags,
        #    &thisa->_WindSpeed,
        #    &thisa->_WindSpeedMinMax,
        #    &thisa->_WindDirection,
        #    &thisa->_WindDirection1,
        #    &thisa->_WindDirection2,
        #    &thisa->_WindDirection3,
        #    &thisa->_WindDirection4,
        #    &thisa->_WindDirection5)

        USBHardware.ReverseByteOrder(newbuf, pos + 169, 0xF)
        self._Gust = USBHardware.ToWindspeed(newbuf, pos + 169)
        self._GustMinMax._Max._Value = USBHardware.ToWindspeed(newbuf, pos+172)
        self._GustMinMax._Max._Time = get_time(newbuf, pos+175, True,
                                               self._GustMinMax._Max._Value,
                                               CWeatherTraits.WindNP(),
                                               CWeatherTraits.WindOFL(),
                                               'GustMax')
        self._GustMinMax._Max._IsError = (
            self._GustMinMax._Max._Value == CWeatherTraits.WindNP())
        self._GustMinMax._Max._IsOverflow = (
            self._GustMinMax._Max._Value == CWeatherTraits.WindOFL())

        GustErrFlags = newbuf[0][180];
        (g ,g1) = USBHardware.ReadWindDirectionShared(newbuf, pos + 181)
        (g2,g3) = USBHardware.ReadWindDirectionShared(newbuf, pos + 182)
        (g4,g5) = USBHardware.ReadWindDirectionShared(newbuf, pos + 183)
        self._GustDirection = g;
        self._GustDirection1 = g1;
        self._GustDirection2 = g2;
        self._GustDirection3 = g3;
        self._GustDirection4 = g4;
        self._GustDirection5 = g5;
        #  CCurrentWeatherData::CheckWindErrFlags(
        #    thisa,
        #    GustErrFlags,
        #    &thisa->_Gust,
        #    &thisa->_GustMinMax,
        #    &thisa->_GustDirection,
        #    &thisa->_GustDirection1,
        #    &thisa->_GustDirection2,
        #    &thisa->_GustDirection3,
        #    &thisa->_GustDirection4,
        #    &thisa->_GustDirection5)

        USBHardware.ReverseByteOrder(newbuf, pos + 184, 0x19)
        (self._PressureRelative_hPa, self._PressureRelative_inHg) = USBHardware.ReadPressureShared(newbuf, pos + 184)
        (self._PressureRelative_hPaMinMax._Min._Value, self._PressureRelative_inHgMinMax._Min._Value) = USBHardware.ReadPressureShared(newbuf, pos + 189)
        (self._PressureRelative_hPaMinMax._Max._Value, self._PressureRelative_inHgMinMax._Max._Value) = USBHardware.ReadPressureShared(newbuf, pos + 194)
        t = get_time(
            newbuf, pos+199, True,
            self._PressureRelative_hPaMinMax._Min._Value,
            CWeatherTraits.PressureNP(),
            CWeatherTraits.PressureOFL(),
            'PressureRelativeMin')
        self._PressureRelative_hPaMinMax._Min._Time = t
        self._PressureRelative_inHgMinMax._Min._Time = t
        t = get_time(
            newbuf, pos+204, True,
            self._PressureRelative_hPaMinMax._Max._Value,
            CWeatherTraits.PressureNP(),
            CWeatherTraits.PressureOFL(),
            'PressureRelativeMax')
        self._PressureRelative_hPaMinMax._Max._Time = t
        self._PressureRelative_inHgMinMax._Max._Time = t

        logdbg("_WeatherState=%s _WeatherTendency=%s" % ( CWeatherTraits.forecastMap[self._WeatherState], CWeatherTraits.trends[self._WeatherTendency]))
        logdbg("_IndoorTemp=     %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._IndoorTemp, self._IndoorTempMinMax._Min._Value, self._IndoorTempMinMax._Min._Time, self._IndoorTempMinMax._Max._Value, self._IndoorTempMinMax._Max._Time))
        logdbg("_IndoorHumidity= %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._IndoorHumidity, self._IndoorHumidityMinMax._Min._Value, self._IndoorHumidityMinMax._Min._Time, self._IndoorHumidityMinMax._Max._Value, self._IndoorHumidityMinMax._Max._Time))
        logdbg("_OutdoorTemp=    %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._OutdoorTemp, self._OutdoorTempMinMax._Min._Value, self._OutdoorTempMinMax._Min._Time, self._OutdoorTempMinMax._Max._Value, self._OutdoorTempMinMax._Max._Time))
        logdbg("_OutdoorHumidity=%7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._OutdoorHumidity, self._OutdoorHumidityMinMax._Min._Value, self._OutdoorHumidityMinMax._Min._Time, self._OutdoorHumidityMinMax._Max._Value, self._OutdoorHumidityMinMax._Max._Time))
        logdbg("_Windchill=      %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._Windchill, self._WindchillMinMax._Min._Value, self._WindchillMinMax._Min._Time, self._WindchillMinMax._Max._Value, self._WindchillMinMax._Max._Time))
        logdbg("_Dewpoint=       %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._Dewpoint, self._DewpointMinMax._Min._Value, self._DewpointMinMax._Min._Time, self._DewpointMinMax._Max._Value, self._DewpointMinMax._Max._Time))
        logdbg("_WindSpeed=      %7.2f                                   _Max=%7.2f(%s)" % (self._WindSpeed * 3.6, self._WindSpeedMinMax._Max._Value * 3.6, self._WindSpeedMinMax._Max._Time))
        logdbg("_Gust=           %7.2f                                   _Max=%7.2f(%s)" % (self._Gust * 3.6,      self._GustMinMax._Max._Value * 3.6, self._GustMinMax._Max._Time))
        logdbg("_Pressure_hPa=   %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._PressureRelative_hPa, self._PressureRelative_hPaMinMax._Min._Value, self._PressureRelative_hPaMinMax._Min._Time, self._PressureRelative_hPaMinMax._Max._Value, self._PressureRelative_hPaMinMax._Max._Time))
        logdbg("_Pressure_inHg=  %7.2f _Min=%7.2f(%s) _Max=%7.2f(%s)" % (self._PressureRelative_inHg, self._PressureRelative_inHgMinMax._Min._Value, self._PressureRelative_inHgMinMax._Min._Time, self._PressureRelative_inHgMinMax._Max._Value, self._PressureRelative_inHgMinMax._Max._Time))
        logdbg("_Rain1H=         %7.2f                                   _Max=%7.2f(%s)" % (self._Rain1H, self._Rain1HMax._Max._Value, self._Rain1HMax._Max._Time))
        logdbg("_Rain24H=        %7.2f                                   _Max=%7.2f(%s)" % (self._Rain24H, self._Rain24HMax._Max._Value, self._Rain24HMax._Max._Time))
        logdbg("_RainLastWeek=   %7.2f                                   _Max=%7.2f(%s)" % (self._RainLastWeek, self._RainLastWeekMax._Max._Value, self._RainLastWeekMax._Max._Time))
        logdbg("_RainLastMonth=  %7.2f                                   _Max=%7.2f(%s)" % (self._RainLastMonth, self._RainLastMonthMax._Max._Value, self._RainLastMonthMax._Max._Time))
        logdbg("_RainTotal=      %7.2f" % self._RainTotal)


class CWeatherStationConfig(object):
    def __init__(self, cfgfn):
        self.filename = cfgfn
        config = ConfigObj(cfgfn)
        config.filename = cfgfn
        try:
            self._CheckSumm = int(config['ws28xx']['CheckSumm'])
        except:
            self._CheckSumm = 0

        self._ClockMode = 0
        self._TemperatureFormat = 0
        self._PressureFormat = 0
        self._RainFormat = 0
        self._WindspeedFormat = 0
        self._WeatherThreshold = 0
        self._StormThreshold = 0
        self._LCDContrast = 0
        self._LowBatFlags = 0
        self._ResetMinMaxFlags = 0
        self._HistoryInterval = 0

    def readAlertFlags(self,buf):
        logdbg('readAlertFlags')

    def GetResetMinMaxFlags(self):
        logdbg('GetResetMinMaxFlags')

    def GetCheckSum(self):
        self.CalcCheckSumm()
        logdbg('_CheckSum=%s' % self._CheckSumm)
        return self._CheckSumm

    def CalcCheckSumm(self):
#        logdbg('CalcCheckSum')
        t = [0]
        t[0] = [0]*1024
#self._ = self.write(t);
#print "CWeatherStationConfig._CheckSumm (should be retrieved) --> 0x%x" % self._CheckSumm

    def CWeatherStationConfig_buf(self,buf,start):
        newbuf=[0]
        newbuf[0] = buf[0]
#CWeatherStationHighLowAlarm::CWeatherStationHighLowAlarm(&this->_AlarmTempIndoor);
#v4 = 0;
#CWeatherStationHighLowAlarm::CWeatherStationHighLowAlarm(&thisa->_AlarmTempOutdoor);
#LOBYTE(v4) = 1;
#CWeatherStationHighLowAlarm::CWeatherStationHighLowAlarm(&thisa->_AlarmHumidityOutdoor);
#LOBYTE(v4) = 2;
#CWeatherStationHighLowAlarm::CWeatherStationHighLowAlarm(&thisa->_AlarmHumidityIndoor);
#LOBYTE(v4) = 3;
#CWeatherStationWindAlarm::CWeatherStationWindAlarm(&thisa->_AlarmGust);
#LOBYTE(v4) = 4;
#CWeatherStationHighLowAlarm::CWeatherStationHighLowAlarm(&thisa->_AlarmPressure);
#LOBYTE(v4) = 5;
#CWeatherStationHighAlarm::CWeatherStationHighAlarm(&thisa->_AlarmRain24H);
#LOBYTE(v4) = 6;
#CWeatherStationWindDirectionAlarm::CWeatherStationWindDirectionAlarm(&thisa->_AlarmWindDirection);
#LOBYTE(v4) = 7;
#std::bitset<23>::bitset<23>(&thisa->_ResetMinMaxFlags);
        self.read(newbuf,start);

    def read(self,buf,start):
        logdbg('CWeatherStationConfig::read')
        nbuf=[0]
        nbuf[0]=buf[0]
#print "read",nbuf[0]
        CheckSumm = nbuf[0][43+start] | (nbuf[0][42+start] << 8);
        self._CheckSumm = CheckSumm;
        CheckSumm -= 7;
        self._ClockMode = nbuf[0][0+start] & 1;
        self._TemperatureFormat = (nbuf[0][0+start] >> 1) & 1;
        self._PressureFormat = (nbuf[0][0+start] >> 2) & 1;
        self._RainFormat = (nbuf[0][0+start] >> 3) & 1;
        self._WindspeedFormat = (nbuf[0][0+start] >> 4) & 0xF;
        self._WeatherThreshold = nbuf[0][1+start] & 0xF;
        self._StormThreshold = (nbuf[0][1+start] >> 4) & 0xF;
        self._LCDContrast = nbuf[0][2+start] & 0xF;
        self._LowBatFlags = (nbuf[0][2+start] >> 4) & 0xF;

        USBHardware.ReverseByteOrder(nbuf,3+start, 4)
#buf=nbuf[0]
#CWeatherStationConfig::readAlertFlags(thisa, buf + 3+start);
        USBHardware.ReverseByteOrder(nbuf, 7+start, 5);
#v2 = USBHardware.ToTemperature(nbuf, 7+start, 1);
#CWeatherStationHighLowAlarm::SetLowAlarm(&self._AlarmTempIndoor, v2);
#v3 = USBHardware.ToTemperature(nbuf + 9+start, 0);
#self._AlarmTempIndoor.baseclass_0.baseclass_0.vfptr[2].__vecDelDtor(
#  (CWeatherStationAlarm *)&self._AlarmTempIndoor,
#  LODWORD(v3));
#j___RTC_CheckEsp(v4);
        USBHardware.ReverseByteOrder(nbuf, 12+start, 5);
#v5 = USBHardware.ToTemperature(nbuf, 12+start, 1);
#CWeatherStationHighLowAlarm::SetLowAlarm(&self._AlarmTempOutdoor, v5);
#v6 = USBHardware.ToTemperature(nbuf, 14+start, 0);
#self._AlarmTempOutdoor.baseclass_0.baseclass_0.vfptr[2].__vecDelDtor(
#  (CWeatherStationAlarm *)&self._AlarmTempOutdoor,
#  LODWORD(v6));
        USBHardware.ReverseByteOrder(nbuf, 17+start, 2);
#v8 = USBHardware.ToHumidity(nbuf, 17+start, 1);
#CWeatherStationHighLowAlarm::SetLowAlarm(&self._AlarmHumidityIndoor, v8);
#v9 = USBHardware.ToHumidity(nbuf, 18+start, 1);
#self._AlarmHumidityIndoor.baseclass_0.baseclass_0.vfptr[2].__vecDelDtor(
#  (CWeatherStationAlarm *)&self._AlarmHumidityIndoor,
#  LODWORD(v9));
        USBHardware.ReverseByteOrder(nbuf, 19+start, 2);
#v11 = USBHardware.ToHumidity(nbuf, 19+start, 1);
#CWeatherStationHighLowAlarm::SetLowAlarm(&self._AlarmHumidityOutdoor, v11);
#v12 = USBHardware.ToHumidity(nbuf, 20+start, 1);
#self._AlarmHumidityOutdoor.baseclass_0.baseclass_0.vfptr[2].__vecDelDtor(
#  (CWeatherStationAlarm *)&self._AlarmHumidityOutdoor,
#  LODWORD(v12));
        USBHardware.ReverseByteOrder(nbuf, 21+start, 4);
#v14 = USBHardware.To4Pre3Post(nbuf, 21+start);
#self._AlarmRain24H.baseclass_0.vfptr[2].__vecDelDtor((CWeatherStationAlarm *)&self._AlarmRain24H, LODWORD(v14));
        self._HistoryInterval = nbuf[0][25+start] & 0xF;
#USBHardware.ReverseByteOrder(nbuf, 26+start, 3u);
##v16 = USBHardware._ToWindspeed(nbuf, 26+start);
#CWeatherStationWindAlarm::SetHighAlarmRaw(&self._AlarmGust, v16);
#USBHardware.ReverseByteOrder(nbuf, 29+start, 5u);
#USBHardware.ReadPressureShared(nbuf, 29+start, &a, &b);
#v17 = Conversions::ToInhg(a);
#v25 = b - v17;
#if ( fabs(v25) > 1.0 )
#{
#  Conversions::ToInhg(a);
#  v18 = CTracer::Instance();
#  CTracer::WriteTrace(v18, 30, "low pressure alarm difference: %f");
#}
#CWeatherStationHighLowAlarm::SetLowAlarm(&self._AlarmPressure, a);
        USBHardware.ReverseByteOrder(nbuf, 34+start, 5);
#USBHardware.ReadPressureShared(nbuf, 34+start, &a, &b);
#v19 = Conversions::ToInhg(a);
#v25 = b - v19;
#if ( fabs(v25) > 1.0 )
#{
#  Conversions::ToInhg(a);
#  v20 = CTracer::Instance();
#  CTracer::WriteTrace(v20, 30, "high pressure alarm difference: %f");
#}
#self._AlarmPressure.baseclass_0.baseclass_0.vfptr[2].__vecDelDtor(
#  (CWeatherStationAlarm *)&self._AlarmPressure,
#  LODWORD(a));
        t = nbuf[0][39+start];
        t <<= 8;
        t |= nbuf[0][40+start];
        t <<= 8;
        t |= nbuf[0][41+start];
#std::bitset<23>::bitset<23>((std::bitset<23> *)&v26, t);
#self._ResetMinMaxFlags._Array[0] = v22;
#for ( i = 0; i < 0x27; ++i )
        for i in xrange(0, 38):
            CheckSumm -= nbuf[0][i+start];
#if ( CheckSumm ): for now is better to comment it
#self._CheckSumm = -1;

        config = ConfigObj(self.filename)
        config.filename = self.filename
        config['ws28xx'] = {}
        config['ws28xx']['CheckSumm'] = str(self._CheckSumm)
        config['ws28xx']['ClockMode'] = str(self._ClockMode)
        
        config['ws28xx']['TemperatureFormat'] = str(self._TemperatureFormat)
        config['ws28xx']['PressureFormat'] = str(self._PressureFormat)
        config['ws28xx']['RainFormat'] = str(self._RainFormat)
        config['ws28xx']['WindspeedFormat'] = str(self._WindspeedFormat)
        config['ws28xx']['WeatherThreshold'] = str(self._WeatherThreshold)
        config['ws28xx']['StormThreshold'] = str(self._StormThreshold)
        config['ws28xx']['LCDContrast'] = str(self._LCDContrast)
        config['ws28xx']['LowBatFlags'] = str(self._LowBatFlags)
        config['ws28xx']['HistoryInterval'] = str(self._HistoryInterval)
        if DEBUG_WRITES > 0:
            logdbg('read: write to %s' % self.filename)
        config.write()

        return 1;

    def write(self,buf):
        logdbg('write')
        new_buf = [0]
        new_buf[0]=buf[0]
        CheckSumm = 7;
        new_buf[0][0] = 16 * (self._WindspeedFormat & 0xF) + 8 * (self._RainFormat & 1) + 4 * (self._PressureFormat & 1) + 2 * (self._TemperatureFormat & 1) + self._ClockMode & 1;
        new_buf[0][1] = self._WeatherThreshold & 0xF | 16 * self._StormThreshold & 0xF0;
        new_buf[0][2] = self._LCDContrast & 0xF | 16 * self._LowBatFlags & 0xF0;
#CWeatherStationConfig::writeAlertFlags(nbuf, 3);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmTempIndoor.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmTempIndoor);
#v25 = v2;
#v24 = CWeatherTraits.TemperatureOffset() + v2;
#v21 = v24;
#v22 = CWeatherTraits.TemperatureOffset() + CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmTempIndoor);
#v4 = v22;
#USBHardware::ToTempAlarmBytes(nbuf, 7, v22, v21);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmTempOutdoor.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmTempOutdoor);
#v25 = v4;
#v24 = CWeatherTraits.TemperatureOffset() + v4;
#v21 = v24;
#v22 = CWeatherTraits.TemperatureOffset() + CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmTempOutdoor);
#v6 = v22;
#USBHardware::ToTempAlarmBytes(nbuf, 12, v22, v21);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmHumidityIndoor.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmHumidityIndoor);
#v21 = v6;
#v8 = CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmHumidityIndoor);
#v9 = v8;
#USBHardware::ToHumidityAlarmBytes(nbuf, 17, v9, v21);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmHumidityOutdoor.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmHumidityOutdoor);
#v21 = v8;
#v11 = CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmHumidityOutdoor);
#v12 = v11;
#USBHardware::ToHumidityAlarmBytes(nbuf, 19, v12, v21);
#((void (__thiscall *)(CWeatherStationHighAlarm *))thisa->_AlarmRain24H.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmRain24H);
#v21 = v11;
#USBHardware::ToRainAlarmBytes(nbuf, 21, v21);
        new_buf[0][25] = self._HistoryInterval & 0xF;
#v21 = CWeatherStationWindAlarm::GetHighAlarmRaw(&thisa->_AlarmGust);
#USBHardware::_ToWindspeedAlarmBytes(nbuf, 26, v21);
#v21 = CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmPressure);
#v21 = Conversions::ToInhg(v21);
#v14 = CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmPressure);
#v15 = CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmPressure);
#USBHardware::ToPressureBytesShared(nbuf, 29, v15, v21);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmPressure.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmPressure);
#((void (__thiscall *)(CWeatherStationHighLowAlarm *))thisa->_AlarmPressure.baseclass_0.baseclass_0.vfptr[1].__vecDelDtor)(&thisa->_AlarmPressure);
#USBHardware::ToPressureBytesShared(nbuf, 34, Conversions::ToInhg(CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmPressure)), Conversions::ToInhg(CWeatherStationHighLowAlarm::GetLowAlarm(&thisa->_AlarmPressure)))

#print "debugxxx ", type(self._ResetMinMaxFlags)
        new_buf[0][39] = (self._ResetMinMaxFlags >>  0) & 0xFF;
        new_buf[0][40] = (self._ResetMinMaxFlags >>  8) & 0xFF; #BYTE1(self._ResetMinMaxFlags);
        new_buf[0][41] = (self._ResetMinMaxFlags >> 16) & 0xFF;

#for ( i = 0; i < 39; ++i )
        for i in xrange(0, 38):
            CheckSumm += new_buf[0][i];
        new_buf[0][42] = (CheckSumm >> 8) & 0xFF #BYTE1(CheckSumm);
        new_buf[0][43] = (CheckSumm >> 0) & 0xFF #CheckSumm;
        buf[0] = new_buf[0]
        return CheckSumm


class CHistoryDataSet(object):

    def __init__(self):
        self.m_Time = None
        self.m_IndoorTemp = CWeatherTraits.TemperatureNP()
        self.m_IndoorHumidity = CWeatherTraits.HumidityNP()
        self.m_OutdoorTemp = CWeatherTraits.TemperatureNP()
        self.m_OutdoorHumidity = CWeatherTraits.HumidityNP()
        self.m_PressureRelative = None
        self.m_WindDirection = 16
        self.m_RainCounterRaw = 0
        self.m_WindSpeed = CWeatherTraits.WindNP()
        self.m_Gust = CWeatherTraits.WindNP()

    def read(self, buf, pos):
        logdbg('CHistoryDataSet::read')

        USBHardware.ReverseByteOrder(buf, pos + 0, 0x12)
        self.m_Time = USBHardware.ToDateTime(buf, pos, 1, 'History')
        self.m_IndoorTemp = USBHardware.ToTemperatureRingBuffer(buf, pos+5, 1)
        self.m_OutdoorTemp = USBHardware.ToTemperatureRingBuffer(buf, pos+6, 0)
        self.m_PressureRelative = USBHardware.ToPressure(buf, pos+8 , 1)
        self.m_IndoorHumidity = USBHardware.ToHumidity(buf, pos+10, 0)
        self.m_OutdoorHumidity = USBHardware.ToHumidity(buf, pos+11, 0)
        self.m_RainCounterRaw = USBHardware.ByteToFloat(buf, pos+12, 0, 16, 3)
        self.m_WindSpeed = USBHardware.ToWindspeedRingBuffer(buf, pos+14)
        self.m_WindDirection = (buf[0][pos + 15] >> 4) & 0xF
        if ( self.m_WindSpeed == CWeatherTraits.WindNP() ):
            self.m_WindDirection = 16
        if ( self.m_WindDirection < 0 or self.m_WindDirection > 16 ):
            self.m_WindDirection = 16
        self.m_Gust = USBHardware.ToWindspeedRingBuffer(buf, pos + 16)

        logdbg("Time              %s"    % self.m_Time)
        logdbg("IndoorTemp=       %7.2f" % self.m_IndoorTemp)
        logdbg("IndoorHumidity=   %7.2f" % self.m_IndoorHumidity)
        logdbg("OutdoorTemp=      %7.2f" % self.m_OutdoorTemp)
        logdbg("OutdoorHumidity=  %7.2f" % self.m_OutdoorHumidity)
        logdbg("PressureRelative= %7.2f" % self.m_PressureRelative)
        logdbg("RainCounterRaw=   %7.2f" % self.m_RainCounterRaw)
        logdbg("WindDirection=    %7.2f" % self.m_WindDirection)
        logdbg("WindSpeed=        %7.2f" % self.m_WindSpeed)
        logdbg("Gust=             %7.2f" % self.m_Gust)


class CDataStore(object):

    class TTransceiverSettings(object): 
        def __init__(self):
            self.VendorId	= 0x6666
            self.ProductId	= 0x5555
            self.VersionNo	= 1
            self.manufacturer	= "LA CROSSE TECHNOLOGY"
            self.product        = "Weather Direct Light Wireless Device"
            self.FrequencyStandard = EFrequency.fsUS
            self.Frequency	= getFrequency(self.FrequencyStandard)
            self.SerialNumber   = None
            self.DeviceID       = None

    class TRequest(object):
        def __init__(self):
            self.Type = 6
            self.State = ERequestState.rsError
            self.TTL = 90000
            self.Lock = threading.Lock()
            self.CondFinish = threading.Condition()

    class TLastStat(object):
        def __init__(self):
            self.LastBatteryStatus = [0]
            self.LastLinkQuality = 0
            self.OutstandingHistorySets = -1
            self.LastCurrentWeatherTime = datetime(1900, 01, 01, 00, 00)
            self.LastHistoryDataTime = datetime(1900, 01, 01, 00, 00)
            self.LastConfigTime = datetime(1900, 01, 01, 00, 00)
            self.LastSeen = None
            self.LastHistoryIndex = 0xffff

            filename = STATS_CACHE
            config = ConfigObj(filename)
            config.filename = filename
            try:
                self.LastHistoryIndex = int(config['LastStat']['HistoryIndex'])
            except:
                pass

    class TSettings(object):
        def __init__(self):
            self.CommModeInterval = 3
            self.PreambleDuration = 5000
            self.RegisterWaitTime = 20000
            self.DeviceID = None

    def __init__(self, cfgfn):
        self.filename = cfgfn
        self.Guards = 0
        self.Flags = 0
        self.FrontEndConfig = 0
        self.LastHistTimeStamp = 0
        self.BufferCheck = 0

        self.Request = CDataStore.TRequest()
        self.LastStat = CDataStore.TLastStat()
        self.Settings = CDataStore.TSettings()
        self.TransceiverSettings = CDataStore.TTransceiverSettings()
        self.DeviceConfig = CWeatherStationConfig(cfgfn)
        self.HistoryData = CHistoryDataSet();
        self.CurrentWeather = CCurrentWeatherData();

    def writeLastStat(self):
        filename = STATS_CACHE
        config = ConfigObj(filename)
        config.filename = filename
        config['LastStat'] = {}
        config['LastStat']['LastSeen'] = str(self.LastStat.LastSeen)
        config['LastStat']['LinkQuality'] = str(self.LastStat.LastLinkQuality)
        config['LastStat']['BatteryStatus'] = str(self.LastStat.LastBatteryStatus)
        config['LastStat']['HistoryIndex'] = str(self.LastStat.LastHistoryIndex)
        config['LastStat']['CurrentWeatherTime'] = str(self.LastStat.LastCurrentWeatherTime)
        config['LastStat']['HistoryDataTime'] = str(self.LastStat.LastHistoryDataTime)
        config['LastStat']['ConfigTime'] = str(self.LastStat.LastConfigTime)
        if DEBUG_WRITES > 0:
            logdbg('writeLastStat: write to %s' % filename)
        config.write()

    def writeTransceiverSettings(self):
        config = ConfigObj(self.filename)
        config.filename = self.filename
        config['TransceiverSettings'] = {}
        config['TransceiverSettings']['SerialNumber'] = self.TransceiverSettings.SerialNumber
        config['TransceiverSettings']['DeviceID'] = self.TransceiverSettings.DeviceID
        config['TransceiverSettings']['FrequencyStandard'] = self.TransceiverSettings.FrequencyStandard
        if DEBUG_WRITES > 0:
            logdbg('writeTransceiverSettings: write to %s' % self.filename)
        config.write()        

    def getFrequencyStandard(self):
        config = ConfigObj(self.filename)
        config.filename = self.filename
        try:
            self.TransceiverSettings.FrequencyStandard = config['TransceiverSettings'].get('FrequencyStandard', EFrequency.fsUS)
        except:
            pass
        return self.TransceiverSettings.FrequencyStandard

    def setFrequencyStandard(self, val):
        logdbg('setFrequency: %s' % val)
        self.TransceiverSettings.FrequencyStandard = val
        self.TransceiverSettings.Frequency = getFrequency(val)
        self.writeTransceiverSettings()

    def getDeviceID(self):
        config = ConfigObj(self.filename)
        config.filename = self.filename
        try:
            self.TransceiverSettings.DeviceID = int(config['TransceiverSettings']['DeviceID'])
        except:
            pass
        return self.TransceiverSettings.DeviceID

    def setDeviceID(self,val):
        logdbg("setDeviceID: %x" % val)
        self.TransceiverSettings.DeviceID = val
        self.writeTransceiverSettings()

    def getRegisteredDeviceID(self):
        return self.Settings.DeviceID

    def setRegisteredDeviceID(self, val):
        if val != self.Settings.DeviceID:
            loginf("console is paired to device with ID %x" % val)
        self.Settings.DeviceID = val

    def getFlag_FLAG_TRANSCEIVER_SETTING_CHANGE(self):  # <4>
        flag = BitHandling.testBit(self.Flags, 4)
        #std::bitset<5>::at(thisa->Flags, &result, 4u);
        return flag

    def getFlag_FLAG_FAST_CURRENT_WEATHER(self):        # <2>
        flag = BitHandling.testBit(self.Flags, 2)
        #return self.Flags_FLAG_SERVICE_RUNNING
        #std::bitset<5>::at(thisa->Flags, &result, 2u);
        return flag

    def getFlag_FLAG_TRANSCEIVER_PRESENT(self):         # <0>
        flag = BitHandling.testBit(self.Flags, 0)
        #return self.Flags_FLAG_TRANSCEIVER_PRESENT
        return flag

    def getFlag_FLAG_SERVICE_RUNNING(self):             # <3>
        flag = BitHandling.testBit(self.Flags, 3)
        #return self.Flags_FLAG_SERVICE_RUNNING
        return flag

    def setFlag_FLAG_TRANSCEIVER_SETTING_CHANGE(self,val):  # <4>
        logdbg('set FLAG_TRANSCEIVER_SETTING_CHANGE to %s' % val)
        #std::bitset<5>::set(thisa->Flags, 4u, val);
        self.Flags = BitHandling.setBitVal(self.Flags,4,val)

    def setFlag_FLAG_FAST_CURRENT_WEATHER(self,val):        # <2>
        logdbg('set FLAG_FAST_CURRENT_WEATHER to %s' % val)
        #std::bitset<5>::set(thisa->Flags, 2u, val);
        self.Flags = BitHandling.setBitVal(self.Flags,2,val)

    def setFlag_FLAG_TRANSCEIVER_PRESENT(self,val):         # <0>
        logdbg('set FLAG_TRANSCEIVER_PRESENT to %s' % val)
        #std::bitset<5>::set(thisa->Flags, 0, val);
        self.Flags = BitHandling.setBitVal(self.Flags,0,val)

    def setFlag_FLAG_SERVICE_RUNNING(self,val):             # <3>
        logdbg('set FLAG_SERVICE_RUNNING to %s' % val)
        #std::bitset<5>::set(thisa->Flags, 3u, val);
        self.Flags = BitHandling.setBitVal(self.Flags,3,val)

    def setLastLinkQuality(self, val):
        logdbg("setLastLinkQuality: quality=%d" % val)
        self.LastStat.LastLinkQuality = val
        self.writeLastStat()

    def setLastSeen(self, val):
        logdbg("setLastSeen: time=%s" % val)
        self.LastStat.LastSeen = val
        self.writeLastStat()

    def getLastSeen(self):
        return self.LastStat.LastSeen

    def setLastBatteryStatus(self, status):
        logdbg('setLastBatteryStatus: 3=%d 0=%d 1=%d 2=%d' %
               (BitHandling.testBit(status,3),
                BitHandling.testBit(status,0),
                BitHandling.testBit(status,1),
                BitHandling.testBit(status,2)))
        self.LastStat.LastBatteryStatus = status
        self.writeLastStat()

    def setCurrentWeather(self, data):
        logdbg('setCurrentWeather')
        self.CurrentWeather = data

    def setHistoryData(self, data):
        logdbg('setHistoryData')
        self.HistoryData = data

    def getHistoryData(self,clear):
        logdbg('getHistoryData')
        self.Request.Lock.acquire()
        History = copy.copy(self.HistoryData)
        self.Request.Lock.release()
        return History
    
    def RequestNotify(self):
        logdbg('RequestNotify: not implemented')
#ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
#    &FuncName,
#    "void __thiscall CDataStore::RequestNotify(void) const");
#v6 = 0;
#ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
#    &Name,
#    "Request->Lock");
#LOBYTE(v6) = 1;
#CScopedLock::CScopedLock(&lock, &thisa->Request->Lock, &Name, &FuncName);
#LOBYTE(v6) = 3;
#ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::_CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(&Name);
#LOBYTE(v6) = 4;
#ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::_CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(&FuncName);
#boost::interprocess::interprocess_condition::notify_all(&thisa->Request->CondFinish);
#v6 = -1;
#self.Request.CondFinish.notifyAll()
#CScopedLock::_CScopedLock(&lock);

    def setLastCurrentWeatherTime(self, val):
        logdbg("setLastCurrentWeatherTime to %s" % val)
        self.LastStat.LastCurrentWeatherTime = val
        self.writeLastStat()

    def setLastHistoryDataTime(self, val):
        logdbg("setLastHistoryDataTime to %s" % val)
        self.LastStat.LastHistoryDataTime = val
        self.writeLastStat()

    def setLastConfigTime(self, val):
        logdbg("setLastConfigTime to %s" % val)
        self.LastStat.LastConfigTime = val
        self.writeLastStat()

    def getBufferCheck(self):
        logdbg("BufferCheck=%x" % self.BufferCheck)
        return self.BufferCheck

    def setBufferCheck(self, val):
        logdbg("setBufferCheck to %x" % val)
        self.BufferCheck = val

    def operator(self):
        logdbg('operator')
        return (self.Guards
                and self.HistoryData
                and self.Flags
                and self.Settings
                and self.TransceiverSettings
                and self.LastSeen
                and self.CurrentWeather
                and self.DeviceConfig
                and self.FrontEndConfig
                and self.LastStat
                and self.Request
                and self.LastHistTimeStamp
                and self.BufferCheck);

    def getDeviceRegistered(self):
        if ( self.Settings.DeviceID is None
             or self.TransceiverSettings.DeviceID is None
             or self.Settings.DeviceID != self.TransceiverSettings.DeviceID ):
            return False
        return True

    def getRequestType(self):
        return self.Request.Type

    def setRequestType(self, val):
        logdbg('setRequestType to %s' % val)
        self.Request.Type = val

    def getRequestState(self):
        return self.Request.State

    def setRequestState(self,state):
        logdbg("setRequestState to %x" % state)
        self.Request.State = state;

    def getPreambleDuration(self):
        return self.Settings.PreambleDuration

    def getRegisterWaitTime(self):
        return self.Settings.RegisterWaitTime

    def getCommModeInterval(self):
#        logdbg("Settings.CommModeInterval=%x" % self.Settings.CommModeInterval)
        return self.Settings.CommModeInterval

    def setCommModeInterval(self,val):
        logdbg("setCommModeInterval to %x" % val)
        self.Settings.CommModeInterval = val

    def setOutstandingHistorySets(self,val):
        logdbg("setOutstandingHistorySets to %d" % val)
        self.LastStat.OutstandingHistorySets = val
        pass

    def setTransceiverSerNo(self,val):
        logdbg("setTransceiverSerialNumber to %s" % val)
        self.TransceiverSettings.SerialNumber = val
        self.writeTransceiverSettings()

    def getTransceiverSerNo(self):
        logdbg("TransceiverSerNo=%s" % self.TransceiverSerNo)
        return self.TransceiverSettings.SerialNumber

    def setLastHistoryIndex(self,val):
        logdbg("setLastHistoryIndex to %x" % val)
        self.LastStat.LastHistoryIndex = val
        self.writeLastStat()

    def getLastHistoryIndex(self):
        logdbg("LastHistoryIndex=%x" % self.LastStat.LastHistoryIndex)
        return self.LastStat.LastHistoryIndex

    def FirstTimeConfig(self, timeout):
        logdbg('FirstTimeConfig: timeout=%s' % timeout)
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('FirstTimeConfig: no transceiver')
            return

        self.DataStore.DeviceID = None
        self.Request.Type = ERequestType.rtFirstConfig
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000
        self.BufferCheck = 0

        try:
            self.Request.CondFinish.acquire()
        except:
            pass

        if self.Request.CondFinish.wait(timedelta(milliseconds=timeout).seconds):
            logdbg('FirstTimeConfig: wait completed with state %s' %
                   self.Request.State)
            if self.Request.State == ERequestState.rsFinished: #2
                tid = self.DataStore.getDeviceID()
                rid = self.DataStore.getRegisteredDeviceID()
                if tid == rid:
                    loginf('FirstTimeConfig: found device ID %s' % tid)
                else:
                    logerr('FirstTimeConfig: pairing failed')
            else:
                logerr('FirstTimeConfig: failed to obtain device ID')
            self.Request.Type = ERequestType.rtINVALID #6;
            self.Request.State = ERequestState.rsINVALID #8;
        else:
            logerr('FirstTimeConfig: timeout before obtaining device ID')

        self.Request.CondFinish.release()

    def GetCurrentWeather(self, data, timeout):
        logdbg('GetCurrentWeather: timeout=%s' % timeout)
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('GetCurrentWeather: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('GetCurrentWeather: transceiver is not paired')
            return

        self.Request.Type = ERequestType.rtGetCurrent
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000;

        try:
            self.Request.CondFinish.acquire()
        except:
            pass

        if self.Request.CondFinish.wait(timedelta(milliseconds=timeout).seconds):
            # FIXME: implement getCurrentWeather
            #CDataStore::getCurrentWeather(thisa, Weather);
            pass
        else:
            pass
        self.Request.Type = ERequestType.rtINVALID #6;
        self.Request.State = ERequestState.rsINVALID #8;
        
        self.Request.CondFinish.release()

    def GetHistory(self, data, timeout):
        logdbg('GetHistory: timeout=%s' % timeout)
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('GetHistory: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('GetHistory: transceiver is not paired')
            return

        self.Request.Type = ERequestType.rtGetHistory
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

        try:
            self.Request.CondFinish.acquire()
        except:
            pass
        if self.Request.CondFinish.wait(timedelta(milliseconds=timeout).seconds):
            # FIXME: implement getHistory
            #CDataStore::getHistoryData(thisa, History, 1);
            pass
        else:
            pass
        self.Request.Type = ERequestType.rtINVALID #6;
        self.Request.State = ERequestState.rsINVALID #8;

        self.Request.CondFinish.release()

    def GetConfig(self):
        logdbg('GetConfig')
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('GetConfig: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('GetConfig: transceiver is not paired')
            return

        # FIXME: implement GetConfig

        self.Request.Type = ERequestType.rtGetConfig
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

    def SetConfig(self):
        logdbg('SetConfig')
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('SetConfig: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('SetConfig: transceiver is not paired')
            return

        self.Request.Type = ERequestType.rtSetConfig
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

    def SetTime(self):
        logdbg('SetTime')
        if not self.getFlag_FLAG_TRANSCEIVER_PRESENT():
            logerr('SetTime: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('SetTime: transceiver is not paired')
            return

        # FIXME: implement SetTime

        self.Request.Type = ERequestType.rtSetTime
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

    def GetDeviceConfigCS(self):
        #logdbg('GetDeviceConfigCS')
        #CWeatherStationConfig::CWeatherStationConfig((CWeatherStationConfig *)&v8, &result);
        #v4 = v1;
        #v3 = v1;
        #LOBYTE(v12) = 6;
        #v7 = CWeatherStationConfig::GetCheckSum((CWeatherStationConfig *)v1);
        #LOBYTE(v12) = 5;
        #CWeatherStationConfig::_CWeatherStationConfig((CWeatherStationConfig *)&v8);
        #LOBYTE(v12) = 4;
        #CWeatherStationConfig::_CWeatherStationConfig(&result);
        #v12 = -1;
        return self.DeviceConfig.GetCheckSum()

    def RequestTick(self):
        if self.Request.Type != ERequestType.rtINVALID:
            self.Request.TTL -= 1
            if self.Request.TTL <= 0:
                self.Request.Type = ERequestType.rtINVALID
                self.Request.State = ERequestState.rsINVALID
                logerr("RequestTick: internal timeout, request aborted")


class sHID(object):
    """USB driver abstraction"""

    def __init__(self):
        self.devh = None
        self.debug = 0
        self.timeout = 1000

    def open(self, vid=0x6666, pid=0x5555):
        device = self._find_device(vid, pid)
        if device is None:
            logcrt('Cannot find USB device with Vendor=0x%04x ProdID=0x%04x' %
                   (vid, pid))
            raise weewx.WeeWxIOError('Unable to find USB device')
        self._open_device(device)

    def close(self):
        self._close_device()

    def _find_device(self, vid, pid):
        for bus in usb.busses():
            for device in bus.devices:
                if device.idVendor == vid and device.idProduct == pid:
                    return device
        return None

    def _open_device(self, device, interface=0, configuration=1):
        self._device = device
        self._configuration = device.configurations[0]
        self._interface = self._configuration.interfaces[0][0]
        self._endpoint = self._interface.endpoints[0]
        self.devh = device.open()
        loginf('manufacturer: %s' % self.devh.getString(device.iManufacturer,30))
        loginf('product: %s' % self.devh.getString(device.iProduct,30))
        loginf('interface: %d' % self._interface.interfaceNumber)

        # detach any old claimed interfaces
        try:
            self.devh.detachKernelDriver(self._interface.interfaceNumber)
        except:
            pass

        # FIXME: this seems to be specific to ws28xx?
        usbWait = 0.05
        self.devh.getDescriptor(0x1, 0, 0x12)
        time.sleep(usbWait)
        self.devh.getDescriptor(0x2, 0, 0x9)
        time.sleep(usbWait)
        self.devh.getDescriptor(0x2, 0, 0x22)
        time.sleep(usbWait)

        # attempt to claim the interface
        try:
            if platform.system() is 'Windows':
                loginf('set USB device configuration to %d' % configuration)
                self.devh.setConfiguration(configuration)
            logdbg('claiming USB interface %d' % interface)
            self.devh.claimInterface(interface)
            self.devh.setAltInterface(interface)
        except usb.USBError, e:
            self._close_device()
            raise weewx.WeeWxIOError(e)

        # FIXME: this seems to be specific to ws28xx?
        # FIXME: check return value
        self.devh.controlMsg(
            usb.TYPE_CLASS + usb.RECIP_INTERFACE,
            0x000000a, [], 0x0000000, 0x0000000, 1000);
        time.sleep(0.05)
        self.devh.getDescriptor(0x22, 0, 0x2a9)
        time.sleep(usbWait)

    def _close_device(self):
        try:
            logdbg('release USB interface')
            self.devh.releaseInterface()
        except:
            pass
        try:
            logdbg('detach kernel driver')
            self.devh.detachKernelDriver(self._interface.interfaceNumber)
        except:
            pass

    def SetTX(self):
        buf = [0]*0x15
        buf[0] = 0xd1;
        if DEBUG_COMM > 0:
            self.dump('SetTX', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d1,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def SetRX(self):
        buf = [0]*0x15
        buf[0] = 0xD0;
        if DEBUG_COMM > 0:
            self.dump('SetRX', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d0,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def GetState(self,StateBuffer):
        try:
            buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                       usb.RECIP_INTERFACE | usb.ENDPOINT_IN,
                                       request=usb.REQ_CLEAR_FEATURE,
                                       buffer=0x0a,
                                       value=0x00003de,
                                       index=0x0000000,
                                       timeout=self.timeout)
            StateBuffer[0]=[0]*0x2
            StateBuffer[0][0]=buf[1]
            StateBuffer[0][1]=buf[2]
            result = 1
        except:
            result = 0
            if self.debug == 1:
                buf[1]=0x14
                StateBuffer[0]=[0]*0x2
                StateBuffer[0][0]=buf[1]
                StateBuffer[0][1]=buf[2]
                result =1
        if DEBUG_COMM > 0:
            self.dump('GetState', buf)
        return result

    def ReadConfigFlash(self,addr,numBytes,data):
        if numBytes <= 512:
            while ( numBytes ):
                buf=[0xcc]*0x0f #0x15
                buf[0] = 0xdd
                buf[1] = 0x0a
                buf[2] = (addr >>8)  & 0xFF;
                buf[3] = (addr >>0)  & 0xFF;
                if DEBUG_COMM > 0:
                    self.dump('ReadConfigFlash>', buf)
                try:
                    # FIXME: check return value
                    self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                         request=0x0000009,
                                         buffer=buf,
                                         value=0x00003dd,
                                         index=0x0000000,
                                         timeout=self.timeout)
                    result = 1
                except:
                    result = 0

                try:
                    buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                               usb.RECIP_INTERFACE |
                                               usb.ENDPOINT_IN,
                                               request=usb.REQ_CLEAR_FEATURE,
                                               buffer=0x15,
                                               value=0x00003dc,
                                               index=0x0000000,
                                               timeout=self.timeout)
                    result = 1
                except:
                    result = 0
                    if addr == 0x1F5 and self.debug == 1: #//fixme #debugging... without device
                        logdbg("sHID::ReadConfigFlash -emulated 0x1F5")
                        buf=[0xdc,0x0a,0x01,0xf5,0x00,0x01,0x78,0xa0,0x01,0x01,0x0c,0x0a,0x0a,0x00,0x41,0xff,0xff,0xff,0xff,0xff,0x00]

                    if addr == 0x1F9 and self.debug == 1: #//fixme #debugging... without device
                        logdbg("sHID::ReadConfigFlash -emulated 0x1F9")
                        buf=[0xdc,0x0a,0x01,0xf9,0x01,0x01,0x0c,0x0a,0x0a,0x00,0x41,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0x00]
                    if self.debug != 1:
                        return 0;

                new_data=[0]*0x15
                if ( numBytes < 16 ):
                    for i in xrange(0, numBytes):
                        new_data[i] = buf[i+4];
                    numBytes = 0;
                else:
                    for i in xrange(0, 16):
                        new_data[i] = buf[i+4];
                    numBytes -= 16;
                    addr += 16;
                if DEBUG_COMM > 0:
                    self.dump('ReadConfigFlash<', buf)

            result = 1;
        else:
            result = 0;

        data[0] = new_data
        return result

    def SetState(self,state):
        buf = [0]*0x15
        buf[0] = 0xd7;
        buf[1] = state;
        if DEBUG_COMM > 0:
            self.dump('SetState', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d7,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def SetFrame(self,data,numBytes):

#    00000000: d5 00 09 f0 f0 03 00 32 00 3f ff ff 00 00 00 00
#    00000000: d5 00 0c 00 32 c0 00 8f 45 25 15 91 31 20 01 00
#    00000000: d5 00 09 00 32 00 06 c1 00 3f ff ff 00 00 00 00
#    00000000: d5 00 09 00 32 01 06 c1 00 3f ff ff 00 00 00 00
#    00000000: d5 00 0c 00 32 c0 06 c1 47 25 15 91 31 20 01 00
#    00000000: d5 00 09 00 32 00 06 c1 00 30 01 a0 00 00 00 00
#    00000000: d5 00 09 00 32 02 06 c1 00 30 01 a0 00 00 00 00
#    00000000: d5 00 30 00 32 40 64 33 53 04 00 00 00 00 00 00
#    00000000: d5 00 09 00 32 00 06 ab 00 30 01 a0 00 00 00 00
#    00000000: d5 00 09 00 32 00 04 d0 00 30 01 a0 00 00 00 00
#    00000000: d5 00 09 00 32 02 04 d0 00 30 01 a0 00 00 00 00
#    00000000: d5 00 30 00 32 40 64 32 53 04 00 00 00 00 00 00
#    00000000: d5 00 09 00 32 00 04 cf 00 30 01 a0 00 00 00 00

        buf = [0]*0x111
        buf[0] = 0xd5;
        buf[1] = numBytes >> 8;
        buf[2] = numBytes;
        for i in xrange(0, numBytes):
            buf[i+3] = data[i]
        if DEBUG_COMM > 0:
            self.dump('SetFrame', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d5,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def GetFrame(self,data,numBytes):
        try:
            buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                       usb.RECIP_INTERFACE |
                                       usb.ENDPOINT_IN,
                                       request=usb.REQ_CLEAR_FEATURE,
                                       buffer=0x111,
                                       value=0x00003d6,
                                       index=0x0000000,
                                       timeout=self.timeout)
            new_data=[0]*0x131
            new_numBytes=(buf[1] << 8 | buf[2])& 0x1ff;
            for i in xrange(0, new_numBytes):
                new_data[i] = buf[i+3];
            if DEBUG_COMM > 0:
                self.dump('GetFrame', buf)
            data[0] = new_data
            numBytes[0] = new_numBytes
            result = 1
        except:
            result = 0
        return result

    def WriteReg(self,regAddr,data):
        buf = [0]*0x05
        buf[0] = 0xf0;
        buf[1] = regAddr & 0x7F;
        buf[2] = 0x01;
        buf[3] = data;
        buf[4] = 0x00;
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003f0,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def Execute(self,command):
        buf = [0]*0x0f #*0x15
        buf[0] = 0xd9;
        buf[1] = command;
        if DEBUG_COMM > 0:
            self.dump('Execute', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d9,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def SetPreamblePattern(self,pattern):
        buf = [0]*0x15
        buf[0] = 0xd8;
        buf[1] = pattern
        if DEBUG_COMM > 0:
            self.dump('SetPreamblePattern', buf)
        try:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003d8,
                                 index=0x0000000,
                                 timeout=self.timeout)
            result = 1
        except:
            result = 0
        return result

    def dump(self, cmd, buf):
        strbuf = ""
        for i in buf:
            strbuf += str("%.2x" % i)
        if strbuf != 'de1500000000' or DEBUG_COMM > 1:
            logdbg("%s: %s" % (cmd, strbuf))


class CCommunicationService(object):

    AX5051RegisterNames_map = dict()

    class AX5051RegisterNames:
        REVISION         = 0x0
        SCRATCH          = 0x1
        POWERMODE        = 0x2
        XTALOSC          = 0x3
        FIFOCTRL         = 0x4
        FIFODATA         = 0x5
        IRQMASK          = 0x6
        IFMODE           = 0x8
        PINCFG1          = 0x0C
        PINCFG2          = 0x0D
        MODULATION       = 0x10
        ENCODING         = 0x11
        FRAMING          = 0x12
        CRCINIT3         = 0x14
        CRCINIT2         = 0x15
        CRCINIT1         = 0x16
        CRCINIT0         = 0x17
        FREQ3            = 0x20
        FREQ2            = 0x21
        FREQ1            = 0x22
        FREQ0            = 0x23
        FSKDEV2          = 0x25
        FSKDEV1          = 0x26
        FSKDEV0          = 0x27
        IFFREQHI         = 0x28
        IFFREQLO         = 0x29
        PLLLOOP          = 0x2C
        PLLRANGING       = 0x2D
        PLLRNGCLK        = 0x2E
        TXPWR            = 0x30
        TXRATEHI         = 0x31
        TXRATEMID        = 0x32
        TXRATELO         = 0x33
        MODMISC          = 0x34
        FIFOCONTROL2     = 0x37
        ADCMISC          = 0x38
        AGCTARGET        = 0x39
        AGCATTACK        = 0x3A
        AGCDECAY         = 0x3B
        AGCCOUNTER       = 0x3C
        CICDEC           = 0x3F
        DATARATEHI       = 0x40
        DATARATELO       = 0x41
        TMGGAINHI        = 0x42
        TMGGAINLO        = 0x43
        PHASEGAIN        = 0x44
        FREQGAIN         = 0x45
        FREQGAIN2        = 0x46
        AMPLGAIN         = 0x47
        TRKFREQHI        = 0x4C
        TRKFREQLO        = 0x4D
        XTALCAP          = 0x4F
        SPAREOUT         = 0x60
        TESTOBS          = 0x68
        APEOVER          = 0x70
        TMMUX            = 0x71
        PLLVCOI          = 0x72
        PLLCPEN          = 0x73
        PLLRNGMISC       = 0x74
        AGCMANUAL        = 0x78
        ADCDCLEVEL       = 0x79
        RFMISC           = 0x7A
        TXDRIVER         = 0x7B
        REF              = 0x7C
        RXMISC           = 0x7D

    def __init__(self, cfgfn, interval=3):
        logdbg('CCommunicationService.init')
        now = datetime.now()

        self.filename = cfgfn
        self.RepeatCount = 0
        self.RepeatSize = 0
        self.RepeatInterval = None
        self.RepeatTime = now #ptime

        self.Regenerate = 0
        self.GetConfig = 0

        self.TimeSent = 0
        self.TimeUpdate = 0
        self.TimeUpdateComplete = 0

        self.DataStore = CDataStore(cfgfn)
        self.DataStore.setCommModeInterval(interval)
        self.running = False
        self.shid = sHID()

    def buildTimeFrame(self,Buffer,checkMinuteOverflow):
        logdbg("buildTimeFrame: checkMinuteOverflow=%x" % checkMinuteOverflow)

        chksum = self.DataStore.GetDeviceConfigCS()
        now = time.time()
        tm = time.localtime(now)

        new_Buffer=[0]
        new_Buffer[0]=Buffer[0]
        Second = tm[5]
        if Second > 59:
            Second = 0 # I don't know if La Crosse support leap seconds...
        if ( checkMinuteOverflow and (Second <= 5 or Second >= 55) ):
            if ( Second < 55 ):
                Second = 6 - Second
            else:
                Second = 60 - Second + 6;
            logdbg('buildTimeFrame: second=%s' % Second)
            HistoryIndex = self.DataStore.getLastHistoryIndex();
            Length = self.buildACKFrame(new_Buffer, 0, chksum, HistoryIndex, Second);
            Buffer[0]=new_Buffer[0]
        else:
            #00000000: d5 00 0c 00 32 c0 00 8f 45 25 15 91 31 20 01 00
            #00000000: d5 00 0c 00 32 c0 06 c1 47 25 15 91 31 20 01 00
            #                             3  4  5  6  7  8  9 10 11
            new_Buffer[0][2] = 0xc0
            new_Buffer[0][3] = (chksum >>8)  & 0xFF #BYTE1(chksum);
            new_Buffer[0][4] = (chksum >>0)  & 0xFF #chksum;
            new_Buffer[0][5] = (tm[5] % 10) + 0x10 * (tm[5] // 10); #sec
            new_Buffer[0][6] = (tm[4] % 10) + 0x10 * (tm[4] // 10); #min
            new_Buffer[0][7] = (tm[3] % 10) + 0x10 * (tm[3] // 10); #hour
            #DayOfWeek = tm[6] - 1; #ole from 1 - 7 - 1=Sun... 0-6 0=Sun
            DayOfWeek = tm[6];      #py  prom 0 - 6 - 0=Mon
            #if ( DayOfWeek == 1 ): # this was for OLE::Time
            #	DayOfWeek = 7;  # this was for OLE::Time
            new_Buffer[0][8] = DayOfWeek % 10 + 0x10 *  (tm[2] % 10)          #DoW + Day
            new_Buffer[0][9] =  (tm[2] // 10) + 0x10 *  (tm[1] % 10)          #day + month
            new_Buffer[0][10] = (tm[1] // 10) + 0x10 * ((tm[0] - 2000) % 10)  #month + year
            new_Buffer[0][11] = (tm[0] - 2000) // 10                          #year
            self.Regenerate = 1
            self.TimeSent = 1
            Buffer[0]=new_Buffer[0]
            Length = 0x0c
        return Length

    def buildConfigFrame(self,Buffer,Data):
        logdbg("buildConfigFrame (not yet implemented)")
        Buffer[2] = 0x40;
        Buffer[3] = 0x64;
        #CWeatherStationConfig::write(Data, &(*Buffer)[4]);
        raise Exception("buildConfigFrameCheckSumm: error... unimplemented")
        #self.Regenerate = 0;
        #self.TimeSent = 0;

#(newBuffer,3,TransceiverID,HistoryIndex,0xFFFFFFFF)
    def buildACKFrame(self,Buffer, Action, CheckSum, HistoryIndex, ComInt):
        logdbg("Action=%x CheckSum=%x HistoryIndex=%x ComInt=%x" % (Action, CheckSum, HistoryIndex, ComInt))
        newBuffer = [0]
        newBuffer[0] = [0]*9
        for i in xrange(0,2):
            newBuffer[0][i] = Buffer[0][i]
        #CDataStore::TLastStat::TLastStat(&Stat);
#	if ( !Action && ComInt == 0xFFFFFFFF ):
#	    v28 = 0;
#	    if ( !Stat.LastCurrentWeatherTime.m_status ):
#	        ATL::COleDateTime::operator_(&now, &ts, &Stat.LastCurrentWeatherTime);
#	    if ( ATL::COleDateTimeSpan::GetTotalSeconds(&ts) >= 8.0 )
#	        Action = 5;
            if datetime.now() - self.DataStore.LastStat.LastCurrentWeatherTime >= timedelta(seconds=8):
                Action = 5
#	    v28 = -1;
        newBuffer[0][2] = Action & 0xF;
#		v21 = CDataStore::GetDeviceConfigCS();
        if ( HistoryIndex >= 0x705 ):
            HistoryAddress = 0xffffff;
        else:
#			if ( !self.DataStore.getBufferCheck() ):
#				if ( !ATL::COleDateTime::GetStatus(&Stat.LastHistoryDataTime) ):
#				{
#					v9 = ATL::COleDateTime::operator_(&now, &result, &Stat.LastHistoryDataTime);
#					if ( ATL::COleDateTimeSpan::operator>(v9, &BUFFER_OVERFLOW_SPAN) )
#					{
#						val = 1;
#						self.DataStore.setBufferCheck( &val);
#					}
#				}
#			}
            if   ( self.DataStore.getBufferCheck() != 1
                   and self.DataStore.getBufferCheck() != 2 ):
                HistoryAddress = 18 * HistoryIndex + 0x1a0;
            else:
                if ( HistoryIndex != 0xffff ):
                    HistoryAddress = 18 * (HistoryIndex - 1) + 0x1a0;
                else:
                    HistoryAddress = 0x7fe8;
                self.DataStore.setBufferCheck( 2);
        newBuffer[0][3] = (CheckSum >> 8) &0xFF;
        newBuffer[0][4] = (CheckSum >> 0) &0xFF;
        if ( ComInt == 0xFFFFFFFF ):
            ComInt = self.DataStore.getCommModeInterval();
        newBuffer[0][5] = (ComInt >> 4) & 0xFF ;
        newBuffer[0][6] = (HistoryAddress >> 16) & 0x0F | 16 * (ComInt & 0xF);
        newBuffer[0][7] = (HistoryAddress >> 8 ) & 0xFF # BYTE1(HistoryAddress);
        newBuffer[0][8] = (HistoryAddress >> 0 ) & 0xFF

        #d5 00 09 f0 f0 03 00 32 00 3f ff ff
        Buffer[0]=newBuffer[0]
        self.Regenerate = 0;
        self.TimeSent = 0;
        return 9

    def handleWsAck(self,Buffer,Length):
        logdbg('handleWsAck')
        #3 = ATL::COleDateTime::GetTickCount(&result);
        self.DataStore.setLastSeen( datetime.now());
        BatteryStat = (Buffer[0][2] & 0xF);
        self.DataStore.setLastBatteryStatus( BatteryStat);
        Quality = Buffer[0][3] & 0x7F;
        self.DataStore.setLastLinkQuality( Quality);
        #ReceivedCS = (Buffer[0][4] << 8) + Buffer[0][5];
        #rt = self.DataStore.getRequestType()
        #if ( rt == ERequestType.rtSetConfig ) #rtSetConfig
        #{
        #	v11 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #	v12 = CDataStore::GetFrontEndConfigCS(v11);
        #	if ( ReceivedCS == v12 )
        #	{
        #		v13 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #		CDataStore::getFrontEndConfig(v13, &c);
        #		v33 = 5;
        #		std::bitset<23>::bitset<23>((std::bitset<23> *)&v26, 0);
        #		v14 = CWeatherStationConfig::GetResetMinMaxFlags(&c);
        #		v14->_Array[0] = v26;
        #		v15 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #		CDataStore::setDeviceConfig(v15, &c);
        #		v16 = ATL::COleDateTime::GetTickCount((ATL::COleDateTime *)&v27);
        #		v17 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #		CDataStore::setLastConfigTime(v17, v16);
        #		v18 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #		CDataStore::setRequestState(v18, rsFinished);
        #		v19 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #		CDataStore::RequestNotify(v19);
        #	        	thisa->RepeatCount = 0;
        #		v33 = -1;
        #		CWeatherStationConfig::_CWeatherStationConfig(&c);
        #	}
        #}
        #else
        #{
        #	if ( rt == ERequestType.rtSetTime ) #rtSetTime (unused)
        #	{
        #		if ( thisa->TimeSent )
        #		{
        #			v8 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #			CDataStore::setRequestState(v8, rsFinished);
        #			v9 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #			CDataStore::RequestNotify(v9);
        #			thisa->RepeatCount = 0;
        #			if ( thisa->TimeUpdate )
        #			{
        #				thisa->TimeUpdateComplete = 1;
        #				thisa->TimeUpdate = 0;
        #				ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
        #				    &FuncName,
        #				    "void __thiscall CCommunicationService::handleWsAck(unsigned char (*const )[300],unsigned int &)");
        #				v33 = 0;
        #				ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
        #				    &Name,
        #				    "DataStore->Request->Lock");
        #				LOBYTE(v33) = 1;
        #				v10 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #				CScopedLock::CScopedLock(&lock, &v10->Request->Lock, &Name, &FuncName);
        #				LOBYTE(v33) = 3;
        #				ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::_CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(&Name);
        #				LOBYTE(v33) = 4;
        #				ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::_CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(&FuncName);
        #				boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore)->Request->Type = 6;
        #				boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore)->Request->State = 8;
        #				v33 = -1;
        #				CScopedLock::_CScopedLock(&lock);
        #			}
        #			}
        #		}
        #	}
        #v73 = -1;
        #CWeatherStationConfig::_CWeatherStationConfig(&RecConfig);
        Length[0] = 0

    def handleConfig(self,Buffer,Length):
        logdbg('handleConfig')
        newBuffer=[0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        #RecConfig = None
        #diff = 0;
        t=[0]
        t[0]=[0]*300
        #j__memcpy(t, (char *)Buffer, *Length);
        for i in xrange(0,Length[0]):
            t[0][i]=newBuffer[0][i]
        #c=CWeatherStationConfig()
        #CWeatherStationConfig.CWeatherStationConfig_buf(c, t,4);
        CWeatherStationConfig.CWeatherStationConfig_buf(self.DataStore.DeviceConfig, t,4); #for the moment I need the cs here
        #v73 = 0;
        #j__memset(t, -52, *Length);
        #t[0]=[0xcc]*Length[0]
        #CWeatherStationConfig::write(&c, &t[4]);
        USBHardware.ReverseByteOrder(t, 7, 4);
        USBHardware.ReverseByteOrder(t, 11, 5);
        USBHardware.ReverseByteOrder(t, 16, 5);
        USBHardware.ReverseByteOrder(t, 21, 2);
        USBHardware.ReverseByteOrder(t, 23, 2);
        USBHardware.ReverseByteOrder(t, 25, 4);
        USBHardware.ReverseByteOrder(t, 30, 3);
        USBHardware.ReverseByteOrder(t, 33, 5);
        USBHardware.ReverseByteOrder(t, 38, 5);
        #for ( i = 4; i < 0x30; ++i )
        #{
        #	if ( t[i] != (*Buffer)[i] )
        #	{
        #		c1 = (char *)(unsigned __int8)t[i];
        #		c2 = (*Buffer)[i];
        #		v43 = c2;
        #		v42 = c1;
        #		v41.baseclass_0.m_pszData = (char *)i;
        #		v3 = CTracer::Instance();
        #		CTracer::WriteTrace(
        #				#v3,
        #				#30,
        #				#"Generated config differs from received in byte#: %02i generated = %04x rececived = %04x");
        #		diff = 1;
        #	}
        #}
        #if ( diff ):
        #v43 = *Length;
        #v42 = t;
        #v41.baseclass_0.m_pszData = (char *)v43;
        #v47 = &v41;
        #ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
        #		#&v41,
        #		#"Config_Gen");
        #v46 = v4;
        #rhs = v4;
        #LOBYTE(v73) = 1;
        #v5 = CTracer::Instance();
        #LOBYTE(v73) = 0;
        #CTracer::WriteDump(v5, 30, v41, v42, v43);
        #v43 = *Length;
        #v42 = (char *)Buffer;
        #v41.baseclass_0.m_pszData = (char *)v43;
        #v48 = &v41;
        #ATL::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>::CStringT<char_ATL::StrTraitATL<char_ATL::ChTraitsCRT<char>>>(
        #		#&v41,
        #		#"Config_Rec");
        #v46 = v6;
        #rhs = v6;
        #LOBYTE(v73) = 2;
        #v7 = CTracer::Instance();
        #LOBYTE(v73) = 0;
        #CTracer::WriteDump(v7, 30, v41, v42, v43);
        #v73 = -1;
        #CWeatherStationConfig::_CWeatherStationConfig(&c);
        RecConfig = CWeatherStationConfig(self.filename)
        confBuffer=[0]
        confBuffer[0]=[0]*0x111
        #CWeatherStationConfig.CWeatherStationConfig_buf(RecConfig, confBuffer, 4);
        #v73 = 3;
        if 1==1: #hack ident
        #if ( CWeatherStationConfig::operator bool(&RecConfig) ):
            rt = self.DataStore.getRequestType();
            #ATL::COleDateTime::GetTickCount(&now);
            #v43 = (CDataStore::ERequestState)&now;
            #v9 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
            #CDataStore::setLastSeen( (ATL::COleDateTime *)v43);
            BatteryStat = (newBuffer[0][2] & 0xF);
            self.DataStore.setLastBatteryStatus( BatteryStat);
            Quality = newBuffer[0][3] & 0x7F
            self.DataStore.setLastLinkQuality( Quality)
            #FrontCS = CDataStore::GetFrontEndConfigCS();
            HistoryIndex = self.DataStore.getLastHistoryIndex();
            #v46 = (CWeatherStationConfig *)rt;
            if 1==1: #hack ident
                if   rt == ERequestType.rtSetConfig:
                    logdbg("handleConfig rt==3 rtSetConfig")
                    #v43 = (CDataStore::ERequestState)&result;
                    #rhs = v46;
                    #LOBYTE(v73) = 4;
                    #v51 = CWeatherStationConfig::operator__(&RecConfig, CDataStore::getFrontEndConfig( (CWeatherStationConfig *)v43))
                    #LOBYTE(v73) = 3;
                    #CWeatherStationConfig::_CWeatherStationConfig(&result);
                    #if ( v51 ):
                        #*Length = CCommunicationService::buildACKFrame(thisa, Buffer, 0, &FrontCS, &HistoryIndex, 0xFFFFFFFFu);
                        #self.DataStore.setLastConfigTime( datetime.now())
                        #v43 = (CDataStore::ERequestState)&RecConfig;
                        #v16 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                        #CDataStore::setDeviceConfig(v16, (CWeatherStationConfig *)v43);
                        #self.DataStore.setRequestState( ERequestState.rsFinished); #2
                        #v18 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                        #CDataStore::RequestNotify(v18);
                    #else:
                    #    CheckSum = CWeatherStationConfig::GetCheckSum(&RecConfig);
                    #    *Length = CCommunicationService::buildACKFrame(thisa, Buffer, 2, &CheckSum, &HistoryIndex, 0xFFFFFFFFu);
                    #    self.DataStore.setRequestState( ERequestState.rsRunning); #1
                elif rt == ERequestType.rtGetConfig:
                    logdbg("handleConfig rt==2 rtGetConfig")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #v21 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                    #CDataStore::setDeviceConfig(v21, (CWeatherStationConfig *)v43);
                    #v54 = CWeatherStationConfig::GetCheckSum(&RecConfig);
                    #*Length = CCommunicationService::buildACKFrame(thisa, Buffer, 0, &v54, &HistoryIndex, 0xFFFFFFFF);
                    self.DataStore.setRequestState( ERequestState.rsFinished); #2
                    self.DataStore.RequestNotify();
                elif rt == ERequestType.rtGetCurrent:
                    logdbg("handleConfig rt==0 rtGetCurrent")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #v25 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                    #CDataStore::setDeviceConfig(v25, (CWeatherStationConfig *)v43);
                    v55 = CWeatherStationConfig.GetCheckSum(RecConfig);
                    newLength[0] = self.buildACKFrame(newBuffer, 5, v55, HistoryIndex, 0xFFFFFFFF);
                    self.DataStore.setRequestState( ERequestState.rsRunning); #1
                elif rt == ERequestType.rtGetHistory:
                    logdbg("handleConfig rt==1 rtGetHistory")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #v28 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                    #CDataStore::setDeviceConfig(v28, (CWeatherStationConfig *)v43);
                    #v56 = CWeatherStationConfig::GetCheckSum(&RecConfig);
                    #*Length = CCommunicationService::buildACKFrame(thisa, Buffer, 4, &v56, &HistoryIndex, 0xFFFFFFFFu);
                    self.DataStore.setRequestState( ERequestState.rsRunning); #1
                elif rt == ERequestType.rtSetTime:
                    logdbg("handleConfig rt==4 rtSetTime")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #v31 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
                    #CDataStore::setDeviceConfig(v31, (CWeatherStationConfig *)v43);
                    #v57 = CWeatherStationConfig::GetCheckSum(&RecConfig);
                    #*Length = CCommunicationService::buildACKFrame(thisa, Buffer, 1, &v57, &HistoryIndex, 0xFFFFFFFFu);
                    self.DataStore.setRequestState( ERequestState.rsRunning); #1
                elif rt == ERequestType.rtFirstConfig:
                    logdbg("handleConfig rt==5 rtFirstConfig")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #self.DataStore.setDeviceConfig( (CWeatherStationConfig *)v43);
                    v58 = CWeatherStationConfig.GetCheckSum(RecConfig);
                    newLength[0] = self.buildACKFrame(newBuffer, 0, v58, HistoryIndex, 0xFFFFFFFF);
                    self.DataStore.setRequestState( ERequestState.rsFinished); #2
                    self.DataStore.RequestNotify();
                elif rt == ERequestType.rtINVALID:
                    logdbg("handleConfig rt==6 rtINVALID")
                    self.DataStore.setLastConfigTime( datetime.now())
                    #v43 = (CDataStore::ERequestState)&RecConfig;
                    #self.DataStore.setDeviceConfig( (CWeatherStationConfig *)v43);
                    v59 = CWeatherStationConfig.GetCheckSum(RecConfig);
                    newLength[0] = self.buildACKFrame(newBuffer, 0, v59, HistoryIndex, 0xFFFFFFFF);
        else:
            newLength[0] = 0
        #v73 = -1;
        #CWeatherStationConfig::_CWeatherStationConfig(&RecConfig);
        Buffer[0] = newBuffer[0]
        Length[0] = newLength[0]

    def handleCurrentData(self,Buffer,Length):
        logdbg('handleCurrentData')

        now = datetime.now()
        self.DataStore.setLastSeen(now);
        self.DataStore.setLastCurrentWeatherTime(now)
        batteryStat = (Buffer[0][2] & 0xF);
        self.DataStore.setLastBatteryStatus(batteryStat);
        quality = Buffer[0][3] & 0x7F;
        self.DataStore.setLastLinkQuality(quality);
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        data = CCurrentWeatherData()
        data.read(newBuffer, 6);
        self.DataStore.setCurrentWeather(data);

        rt = self.DataStore.getRequestType();
        chksum = self.DataStore.GetDeviceConfigCS()
        idx = self.DataStore.getLastHistoryIndex();

        newLength = [0]
        if rt == ERequestType.rtGetCurrent: #0
            self.DataStore.setRequestState(ERequestState.rsFinished); #2
            self.DataStore.RequestNotify();
            newLength[0] = self.buildACKFrame(newBuffer, 0, chksum, idx, 0xFFFFFFFF);
        elif rt == ERequestType.rtGetConfig: #2
            newLength[0] = self.buildACKFrame(newBuffer, 3, chksum, idx, 0xFFFFFFFF);
            self.DataStore.setRequestState(ERequestState.rsRunning); #1
        elif rt == ERequestType.rtSetConfig: #3
            newLength[0] = self.buildACKFrame(newBuffer, 2, chksum, idx, 0xFFFFFFFF);
            self.DataStore.setRequestState(ERequestState.rsRunning); #1
        elif rt == ERequestType.rtGetHistory: #1
            newLength[0] = self.buildACKFrame(newBuffer, 4, chksum, idx, 0xFFFFFFFF);
            self.DataStore.setRequestState(ERequestState.rsRunning); #1
        elif rt == ERequestType.rtSetTime: #4
            newLength[0] = self.buildACKFrame(newBuffer, 1, chksum, idx, 0xFFFFFFFF);
            self.DataStore.setRequestState(ERequestState.rsRunning); #1
        elif rt == ERequestType.rtFirstConfig or rt == ERequestType.rtINVALID:
            newLength[0] = self.buildACKFrame(newBuffer, 0, chksum, idx, 0xFFFFFFFF);

        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def handleHistoryData(self,Buffer,Length):
        logdbg('handleHistoryData')
        now = datetime.now()
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        Data = CHistoryDataSet()
        Data.read(newBuffer, 12)
        #ATL::COleDateTime::GetTickCount(&now);
        self.DataStore.setLastSeen( now );
        BatteryStat = (Buffer[0][2] & 0xF);
        self.DataStore.setLastBatteryStatus( BatteryStat);
        Quality = Buffer[0][3] & 0x7F;
        self.DataStore.setLastLinkQuality( Quality);
        LatestHistoryAddres = ((((Buffer[0][6] & 0xF) << 8) | Buffer[0][7]) << 8) | Buffer[0][8];
        ThisHistoryAddres = ((((Buffer[0][9] & 0xF) << 8) | Buffer[0][10]) << 8) | Buffer[0][11];
        ThisHistoryIndex = (ThisHistoryAddres - 415) / 0x12;
        LatestHistoryIndex = (LatestHistoryAddres - 415) / 0x12
        #v6 = CTracer::Instance();
        #CTracer::WriteTrace(v6, 40, "ThisAddress: %X\tLatestAddress: %X");
        #v7 = CTracer::Instance();
        #CTracer::WriteTrace(v7, 40, "ThisIndex: %X\tLatestIndex: %X");
        #v38 = CDataStore::getBufferCheck();
        #    if ( self.DataStore.getBufferCheck() != 2 ):
        #      j___wassert(
        #        L"false",
        #        L"c:\\svn\\heavyweather\\trunk\\applications\\backend\\communicationservice.cpp",
        #        __LINE__Var + 85);
        #    v9 = boost::shared_ptr<CDataStore>::operator_>(&thisa->DataStore);
        #v10 = CTracer::Instance();
        #CTracer::WriteTrace(v10, 40, "getLastHistoryIndex(): %X",self.DataStore.getLastHistoryIndex());
        if ( ThisHistoryIndex == self.DataStore.getLastHistoryIndex()):
            self.DataStore.setLastHistoryDataTime( now )
        #   CDataStore::getLastHistTimeStamp( &LastHistTs);
            if 1 == 1:
        #   if ( !ATL::COleDateTime::GetStatus(&LastHistTs) )
                if 1 == 1:
        #	if ( !ATL::COleDateTime::GetStatus(CHistoryDataSet::GetTime(&Data)) ):
                    if 1 == 1:
        #	    if ( ATL::COleDateTime::operator__(CHistoryDataSet::GetTime(&Data), &LastHistTs) ):
        #		CDataStore::setOutstandingHistorySets( 0xFFFFFFFFu);
        #		self.DataStore.setLastHistoryIndex( 0xFFFFFFFF);
        #               ThisHistoryIndex = -1;
        #		ATL::COleDateTime::COleDateTime(&InvalidDateTime);
        #		ATL::COleDateTime::SetStatus(&InvalidDateTime, partial);
        #		CDataStore::setLastHistTimeStamp( &InvalidDateTime);
        #	    else:
                        self.DataStore.setLastHistoryDataTime( now )
            self.DataStore.setBufferCheck( 0)
            self.DataStore.setRequestType(ERequestType.rtINVALID)
        else:
            #CDataStore::setLastHistTimeStamp( CHistoryDataSet::GetTime(&Data));
            #CDataStore::addHistoryData( &Data);
            self.DataStore.setHistoryData(Data);
            self.DataStore.setLastHistoryIndex( ThisHistoryIndex)

        if ( LatestHistoryIndex >= ThisHistoryIndex ): #unused
            self.DifHis = LatestHistoryIndex - ThisHistoryIndex
            #self.DataStore.setOutstandingHistorySets(self.DisHis) #unused
        else:
            self.DifHis = LatestHistoryIndex + 1797 - ThisHistoryIndex
            #self.DataStore.setOutstandingHistorySets( LatestHistoryIndex + 18 - ThisHistoryIndex) #unused
        if self.DifHis > 0:
            logdbg('m_Time=%s OutstandingHistorySets=%4i' %
                   (Data.m_Time, self.DifHis))

        rt = ERequestType.rtINVALID
        if ThisHistoryIndex == LatestHistoryIndex:
            maxTimeDifference = 70 # seconds
            self.TimeDifSec = (Data.m_Time - now).seconds
            if self.TimeDifSec > 43200:
                self.TimeDifSec = self.TimeDifSec - 86400 + 1
            if abs(self.TimeDifSec) >= maxTimeDifference:
                rt = ERequestType.rtSetTime
            logdbg('handleHistoryData: timeDifSec=%4s m_Time=%s max=%s' %
                   (self.TimeDifSec, Data.m_Time, maxTimeDifference))
        else:
            logdbg('handleHistoryData: no recent history data: m_Time=%s' %
                   Data.m_Time)
        self.DataStore.setRequestType(rt)

        rt = self.DataStore.getRequestType()
        chksum = self.DataStore.GetDeviceConfigCS()
        if   rt == ERequestType.rtGetCurrent: #rtGetCurrent
            newLength[0] = self.buildACKFrame(newBuffer, 5, chksum, ThisHistoryIndex, 0xFFFFFFFF);
            self.DataStore.setRequestState( ERequestState.rsRunning);
        elif rt == ERequestType.rtGetConfig: #rtGetConfig
            newLength[0] = self.buildACKFrame(newBuffer, 3, chksum, ThisHistoryIndex, 0xFFFFFFFF);
            self.DataStore.setRequestState( ERequestState.rsRunning);
        elif rt == ERequestType.rtSetConfig: #rtSetConfig
            newLength[0] = self.buildACKFrame(newBuffer, 2, chksum, ThisHistoryIndex, 0xFFFFFFFF);
            self.DataStore.setRequestState( ERequestState.rsRunning);
        elif rt == ERequestType.rtGetHistory: #rtGetHistory
            self.DataStore.setRequestState( ERequestState.rsFinished);
            self.DataStore.RequestNotify()
            newLength[0] = self.buildACKFrame(newBuffer, 0, chksum, ThisHistoryIndex, 0xFFFFFFFF);
        elif rt == ERequestType.rtSetTime: #rtSetTime
            newLength[0] = self.buildACKFrame(newBuffer, 1, chksum, ThisHistoryIndex, 0xFFFFFFFF);
            self.DataStore.setRequestState( ERequestState.rsRunning);
        elif rt == ERequestType.rtFirstConfig or rt == ERequestType.rtINVALID: #rtFirstConfig || #rtINVALID
            newLength[0] = self.buildACKFrame(newBuffer, 0, chksum, ThisHistoryIndex, 0xFFFFFFFF);

        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def handleNextAction(self,Buffer,Length):
        logdbg('handleNextAction')
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        newLength[0] = Length[0]
        #print "handleNextAction:: Buffer[0] %x" % Buffer[0][0]
        #print "handleNextAction:: Buffer[1] %x" % Buffer[0][1]
        #print "handleNextAction:: Buffer[2] %x (CWeatherStationConfig *)" % (Buffer[0][2] & 0xF)
        rt = self.DataStore.getRequestType()
        idx = self.DataStore.getLastHistoryIndex();
        chksum = self.DataStore.GetDeviceConfigCS();
        self.DataStore.setLastSeen(datetime.now());
        quality = Buffer[0][3] & 0x7F;
        self.DataStore.setLastLinkQuality(quality);
        if (Buffer[0][2] & 0xF) == 2:
            logdbg("handleNextAction Buffer[2] == 2")
            #	v16 = CDataStore::getFrontEndConfig( &result);
            #	Data = v16;
#            newLength[0] = self.buildConfigFrame(newBuffer, v16);
            pass
        elif (Buffer[0][2] & 0xF) == 3:
            logdbg("handleNextAction Buffer[2] == 3 request time")
            newLength[0] = self.buildTimeFrame(newBuffer, 1);
        else:
            logdbg("handleNextAction Buffer[2] == %x" % (Buffer[0][2] & 0xF))
            if rt == ERequestType.rtGetCurrent: #rtGetCurrent
                newLength[0] = self.buildACKFrame(newBuffer, 5, chksum, idx, 0xFFFFFFFF);
                self.DataStore.setRequestState( ERequestState.rsRunning);
            elif rt == ERequestType.rtGetHistory: #rtGetHistory
                newLength[0] = self.buildACKFrame(newBuffer, 4, chksum, idx, 0xFFFFFFFF);
                self.DataStore.setRequestState( ERequestState.rsRunning);
            elif rt == ERequestType.rtGetConfig: #rtGetConfig
                newLength[0] = self.buildACKFrame(newBuffer, 3, chksum, idx, 0xFFFFFFFF);
                self.DataStore.setRequestState( ERequestState.rsRunning);
            elif rt == ERequestType.rtSetConfig: #rtSetConfig
                newLength[0] = self.buildACKFrame(newBuffer, 2, chksum, idx, 0xFFFFFFFF);
                self.DataStore.setRequestState( ERequestState.rsRunning);
            elif rt == ERequestType.rtSetTime: #rtSetTime
                newLength[0] = self.buildACKFrame(newBuffer, 1, chksum, idx, 0xFFFFFFFF);
                self.DataStore.setRequestState( ERequestState.rsRunning);
            else:
                if ( self.DataStore.getFlag_FLAG_FAST_CURRENT_WEATHER() ):
                    newLength[0] = self.buildACKFrame(newBuffer, 5, chksum, idx, 0xFFFFFFFF);
                else:
                    newLength[0] = self.buildACKFrame(newBuffer, 0, chksum, idx, 0xFFFFFFFF);
        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def configureRegisterNames(self):
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.IFMODE]    =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.MODULATION]=0x41 #fsk
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.ENCODING]  =0x07
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FRAMING]   =0x84 #1000:0100 ##?hdlc? |1000 010 0
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.CRCINIT3]  =0xff
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.CRCINIT2]  =0xff
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.CRCINIT1]  =0xff
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.CRCINIT0]  =0xff
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ3]     =0x38
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ2]     =0x90
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ1]     =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ0]     =0x01
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PLLLOOP]   =0x1d
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PLLRANGING]=0x08
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PLLRNGCLK] =0x03
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.MODMISC]   =0x03
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.SPAREOUT]  =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TESTOBS]   =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.APEOVER]   =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TMMUX]     =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PLLVCOI]   =0x01
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PLLCPEN]   =0x01
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.RFMISC]    =0xb0
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.REF]       =0x23
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.IFFREQHI]  =0x20
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.IFFREQLO]  =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.ADCMISC]   =0x01
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.AGCTARGET] =0x0e
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.AGCATTACK] =0x11
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.AGCDECAY]  =0x0e
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.CICDEC]    =0x3f
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.DATARATEHI]=0x19
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.DATARATELO]=0x66
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TMGGAINHI] =0x01
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TMGGAINLO] =0x96
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.PHASEGAIN] =0x03
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQGAIN]  =0x04
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQGAIN2] =0x0a
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.AMPLGAIN]  =0x06
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.AGCMANUAL] =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.ADCDCLEVEL]=0x10
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.RXMISC]    =0x35
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FSKDEV2]   =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FSKDEV1]   =0x31
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FSKDEV0]   =0x27
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TXPWR]     =0x03
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TXRATEHI]  =0x00
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TXRATEMID] =0x51
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TXRATELO]  =0xec
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.TXDRIVER]  =0x88

    def calculateFrequency(self, freq):
        logdbg('calculateFrequency')
        loginf('base frequency: %d' % freq)
        freqVal =  long(freq / 16000000.0 * 16777216.0)
        corVec = [None]
        if self.shid.ReadConfigFlash(0x1F5, 4, corVec):
            corVal = corVec[0][0] << 8
            corVal |= corVec[0][1]
            corVal <<= 8
            corVal |= corVec[0][2]
            corVal <<= 8
            corVal |= corVec[0][3]
            loginf('frequency correction: %d (%x)' % (corVal,corVal)) #0x184e8
            freqVal += corVal
        if not (freqVal % 2):
            freqVal += 1
        loginf('adjusted frequency: %d (%x)' % (freqVal,freqVal))
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ3] = (freqVal >>24) & 0xFF
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ2] = (freqVal >>16) & 0xFF
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ1] = (freqVal >>8)  & 0xFF
        self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ0] = (freqVal >>0)  & 0xFF
        logdbg('frequency registers: %x %x %x %x' % (
                self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ3],
                self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ2],
                self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ1],
                self.AX5051RegisterNames_map[self.AX5051RegisterNames.FREQ0]))

    def GenerateResponse(self, Buffer, Length):
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        newLength[0] = Length[0]
        if Length[0] != 0:
            requestType = self.DataStore.getRequestType()
            deviceID = self.DataStore.getDeviceID()
            bufferID = (Buffer[0][0] <<8) | Buffer[0][1]
            responseType = (Buffer[0][2] & 0xE0) - 0x20
            logdbg("GenerateResponse: length=%x request=%x response=%x id=%x" %
                   (Length[0], requestType, responseType, bufferID))
            self.DataStore.setRegisteredDeviceID(deviceID)
            if deviceID == bufferID:
                if responseType == 0x00:
                    #    00000000: 00 00 06 00 32 20
                    if Length[0] == 0x06:
                        loginf('weather station set time - clock set')
                        self.DataStore.setRequestType(ERequestType.rtINVALID)
                        self.handleWsAck(newBuffer, newLength);
                    else:
                        newLength[0] = 0
                elif responseType == 0x20:
                    #    00000000: 00 00 30 00 32 40
                    if Length[0] == 0x30:
                        self.handleConfig(newBuffer, newLength);
                    else:
                        newLength[0] = 0
                elif responseType == 0x40:
                    #    00000000: 00 00 d7 00 32 60
                    if Length[0] == 0xd7: #215
                        self.handleCurrentData(newBuffer, newLength);
                    else:
                        newLength[0] = 0
                elif responseType == 0x60:
                    #    00000000: 00 00 1e 00 32 80
                    if Length[0] == 0x1e:
                        self.handleHistoryData(newBuffer, newLength);
                    else:
                        newLength[0] = 0
                elif responseType == 0x80:
                    #    00000000: 00 00 06 f0 f0 a1
                    #    00000000: 00 00 06 00 32 a3
                    #    00000000: 00 00 06 00 32 a2
                    if Length[0] == 0x06:
                        self.handleNextAction(newBuffer, newLength);
                    else:
                        newLength[0] = 0
                else:
                    logcrt('unrecognized response type %x', responseType)
                    newLength[0] = 0
            elif requestType == ERequestType.rtFirstConfig:
                logdbg('GenerateResponse: ID mismatch (device=%x buffer=%x), attempting to pair' % (deviceID, bufferID))
                newLength[0] = self.buildACKFrame(newBuffer,3,deviceID,0xFFFF,0xFFFFFFFF)
                self.RepeatCount = 0
                self.DataStore.setRequestState(ERequestState.rsWaitConfig)
            else:
                logcrt('GenerateResponse: device not paired and wrong request type (%s)' % requestType)
                newLength[0] = 0
        else: #Length[0] == 0
            newBuffer[0]=[0]*0x0c
            if self.RepeatCount:
                logdbg("GenerateResponse: repeatcount=%d" %  self.RepeatCount)
                if (datetime.now() - self.RepeatTime).seconds >1:
                    if self.Regenerate:
                        logdbg('GenerateResponse: time message=0x0c')
                        newLength[0] = self.buildTimeFrame(newBuffer,1);
                    #else:
                    #	logdbg("implementami - copia data su buf")
                    #	newBuffer[0] = self.RepeatData, self.RepeatSize
                    #newLength[0] = self.RepeatSize;

        Buffer[0] = newBuffer[0]
        Length[0] = newLength[0]
        if newLength[0] == 0:
            return 0
        return 1

    def initTransceiver(self):
        logdbg('initTransceiver')

        self.configureRegisterNames()
        self.calculateFrequency(self.DataStore.TransceiverSettings.Frequency)

        errmsg = ''
        buf = [None]
        if self.shid.ReadConfigFlash(0x1F9, 7, buf):
            ID  = buf[0][5] << 8
            ID += buf[0][6]
            loginf('transceiver ID: %d (%x)' % (ID,ID))
            self.DataStore.setDeviceID(ID)

            SN  = str("%02d"%(buf[0][0]))
            SN += str("%02d"%(buf[0][1]))
            SN += str("%02d"%(buf[0][2]))
            SN += str("%02d"%(buf[0][3]))
            SN += str("%02d"%(buf[0][4]))
            SN += str("%02d"%(buf[0][5]))
            SN += str("%02d"%(buf[0][6]))
            loginf('transceiver serial: %s' % SN)
            self.DataStore.setTransceiverSerNo(SN)
            
            for r in self.AX5051RegisterNames_map:
                self.shid.WriteReg(r, self.AX5051RegisterNames_map[r])

            if self.shid.Execute(5):
                self.shid.SetPreamblePattern(0xaa)
                if self.shid.SetState(0):
                    time.sleep(1)
                    if self.shid.SetRX():
                        pass
                    else:
                        errmsg = 'SetRX failed'
                else:
                    errmsg = 'SetState failed'
            else:
                errmsg = 'Execute failed'
        else:
            errmsg = 'ReadConfigFlash failed'

        if errmsg != '':
            raise Exception('transceiver initialization failed: %s' % errmsg)

    def setup(self, frequency):
        self.DataStore.setFrequencyStandard(frequency)
        self.DataStore.setFlag_FLAG_TRANSCEIVER_SETTING_CHANGE(1)
        self.shid.open()
        self.initTransceiver()
        self.DataStore.setFlag_FLAG_TRANSCEIVER_PRESENT(1)
        self.shid.SetRX()

    def teardown(self):
        self.shid.close()

    def startRFThread(self):
        logdbg('startRFThread')
        self.running = True
        child = threading.Thread(target=self.doRF)
        child.setName('RFComm')
        child.start()

    def stopRFThread(self):
        logdbg('stopRFThread')
        self.running = False

    def isRunning(self):
        return self.running

    def doRF(self):
        try:
            logdbg('starting rf communication')
            while self.running:
                self.doRFCommunication()
            logdbg('stopping rf communication')
        except Exception, e:
            logerr('exception in doRF: %s' % e)
            self.running = False
            if weewx.debug:
                traceback.print_exc()
            raise

    def doRFCommunication(self):
        DeviceWaitEndTime = datetime.now()
        RequestType = self.DataStore.getRequestType()
        if RequestType != ERequestType.rtINVALID or DEBUG_COMM > 0:
            logdbg('RequestType=%s' % RequestType)

        if RequestType == ERequestType.rtFirstConfig:
            rs = self.DataStore.getRequestState()
            if rs == ERequestState.rsQueued:
                logdbg('RequestState=rsQueued (%s)' % rs)
                self.shid.SetPreamblePattern(0xaa)
                self.shid.SetState(0x1e)
                self.DataStore.setRequestState(ERequestState.rsPreamble)
                dur = self.DataStore.getPreambleDuration() 
                now = datetime.now()
                PreambleEndTime = now + timedelta(milliseconds=dur)
                logdbg("now=%s PreambleEndTime=%s DeviceWaitEndTime=%s" % (now, PreambleEndTime, DeviceWaitEndTime))
                while True:
                    now = datetime.now()
                    if PreambleEndTime < now:
                        logdbg("PreambleEndTime < now (%s < %s)" %
                               (PreambleEndTime, now))
                        break
                    rt = self.DataStore.getRequestType()
                    if RequestType != rt:
                        logdbg("RequestType (%s) != self.DataStore.getRequestType() (%s)" % (RequestType, rt))
                        break
                    self.DataStore.RequestTick()
                    time.sleep(0.001)
#                    self.DataStore.setFlag_FLAG_SERVICE_RUNNING(True)
                    #time.sleep(6)
                    rt = self.DataStore.getRequestType()
                    if RequestType == rt:
                        self.DataStore.setRequestState(ERequestState.rsWaitDevice)
                        RegisterWaitTime = self.DataStore.getRegisterWaitTime() 
                        DeviceWaitEndTime = datetime.now() + timedelta(milliseconds=RegisterWaitTime)
                    self.shid.SetRX() #make state from 14 to 15
            elif rs == ERequestState.rsWaitDevice: # 4
                logdbg('RequestState=rsWaitDevice (%s)' % rs)
                now = datetime.now()
                if now >= DeviceWaitEndTime :
                    logdbg("now >= DeviceWaitEndTime (%s >= %s)" %
                           (now, DeviceWaitEndTime))
                    self.DataStore.setRequestState(ERequestState.rsError)
                    self.DataStore.RequestNotify()
            else:
                logdbg('RequestState=%s' % rs)

        DataLength = [0]
        DataLength[0] = 0
        StateBuffer = [None]
        ret = self.shid.GetState(StateBuffer)
        if ret == 1:
            FrameBuffer=[0]
            FrameBuffer[0]=[0]*0x03
            ReceiverState = StateBuffer[0][0]
            if ReceiverState == 0x16:
                ret = self.shid.GetFrame(FrameBuffer, DataLength)
                if ret == 1:
                    logdbg('frame: %s' % frame2str(DataLength[0],FrameBuffer[0]))
                else:
                    logerr('GetFrame failed')

            ret = self.GenerateResponse(FrameBuffer, DataLength)
            if ret == 1:
                self.shid.SetState(0)
                # send the ackframe prepared by GenerateResponse
                ret = self.shid.SetFrame(FrameBuffer[0], DataLength[0])
                if ret == 1:
                    ret = self.shid.SetTX()
                    if ret == 1:
                        ReceiverState = 0xc8
                        while ret == 1:
                            Action = FrameBuffer[0][2]
#                            logdbg('Action=%2x' % Action)
                            ret = self.shid.GetState(StateBuffer)
                            if ret == 1:
                                #self.DataStore.RequestTick()
                                #ReceiverState = StateBuffer[0]
                                #if not ReceiverState or ReceiverState == 0x15:
                                #    self.RepeatTime = datetime.now()
                                #    time.sleep(0.2)
                                break
                            else:
                                logerr('GetState failed')
                    else:
                        logerr("SetTX failed")
                else:
                    logerr('SetFrame failed')

            if ReceiverState != 0x15:
                ret = self.shid.SetRX() #make state from 14 to 15

        # FIXME: handle bogus return value at each invocation
#        if not ret:
#            self.DataStore.setFlag_FLAG_TRANSCEIVER_PRESENT( 0)

        time.sleep(0.001)
