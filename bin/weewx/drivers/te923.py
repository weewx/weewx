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
# Thanks to Sebastian John for the te923tool written in C:
#   http://te923.fukz.org/
# Thanks to Mark Teel for the te923 implementation in wview:
#   http://www.wviewweather.com/

"""Classes and functions for interfacing with te923 weather stations.

These stations were made by Hideki and branded as Honeywell, Meade, IROX Pro X,
Mebus TE923, and TFA Nexus.

A single bucket tip is between 0.02 and 0.03 in (0.508 to 0.762 mm).

The station has altitude, latitude, longitude, and time.  Read these during
initialization and indicate any difference with values from weewx.conf.  If
conflicts, use the values from weewx.conf.

Notes from Other Implementations

It is not clear whether te923tool copied from wview or vice versa.  te923tool
provides more detail about the reason for invalid values, for example, values
out of range versus no link with sensors.

There are some disagreements between the wview and te923tool implementations.

There are a few oddities in the te923tool:
- reading from usb in 8 byte chunks instead of all at once
- length of buffer is 35, but reads are 32-byte blocks
- windspeed and windgust state can never be -1
- index 29 in rain count, also in wind dir

wview does the 8-byte reads using interruptRead as well.

wview ignores the windchill value from the station.

Random Notes

Here are some tidbits for usb putzing.  The documentation for reading/writing
USB in python is scarce.  Apparently there are (at least) two ways of reading
from USB - one using interruptRead, the other doing bulk reads.  Which you use
may depend on the device itself.

There are at least two Python interfaces, e.g. claim_interface vs
claimInterface.

  usb_control_msg(0x21,    # request type
                  0x09,    # request
                  0x0200,  # value
                  0x0000,  # index
                  buf,     # buffer
                  0x08,    # size
                  timeout) # timeout
"""

# FIXME: add option to calculate windchill instead of using station value
# FIXME: verify pressure/altimeter

from __future__ import with_statement
import optparse
import syslog
import time
import usb

import weeutil
import weewx.abstractstation
import weewx.wxformulas

DRIVER_VERSION = '0.1'
DEBUG_READ = 1
DEBUG_DECODE = 1

def logmsg(dst, msg):
    syslog.syslog(dst, 'te923: %s' % msg)

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
    station = TE923(altitude=altitude_m, **config_dict['TE923'])
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

# FIXME: this goes in weeutil.weeutil
def calculate_rain_rate(delta, curr_ts, last_ts):
    """Calculate the rain rate based on the time between two rain readings.

    delta_cm: rainfall since last reading, in cm

    curr_ts: timestamp of current reading, in seconds

    last_ts: timestamp of last reading, in seconds

    return: rain rate in X per hour

    If the period between readings is zero, ignore the rainfall since there
    is no way to calculate a rate with no period."""

    if curr_ts is None:
        return None
    if last_ts is None:
        last_ts = curr_ts
    if delta is not None:
        period = curr_ts - last_ts
        if period != 0:
            rate = 3600 * delta / period
        else:
            rate = None
            if delta != 0:
                loginf('rain rate period is zero, ignoring rainfall of %f' % delta)
    else:
        rate = None
    return rate

class TE923(weewx.abstractstation.AbstractStation):
    """Driver for Hideki TE923 stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        altitude: Altitude of the station
        [Required. No default]

        polling_interval: How often to poll the station, in seconds.
        [Optional. Default is 60]

        pressure_offset: Calibration offset in millibars for the station
        pressure sensor.  This offset is added to the station sensor output
        before barometer and altimeter pressures are calculated.
        [Optional. No Default]

        model: Which station model is this?
        [Optional. Default is 'TE923']

        out_sensor: Which sensor is the outside sensor?  The station supports
        up to 5 sensors.  This indicates which should be considered the
        outside temperature and humidity.
        [Optional. Default is 1]
        """
        self._last_rain        = None
        self._last_rain_ts     = None

        global DEBUG_READ
        DEBUG_READ             = int(stn_dict.get('debug_read', 0))
        global DEBUG_DECODE
        DEBUG_DECODE           = int(stn_dict.get('debug_decode', 0))

        self.altitude          = stn_dict['altitude']
        self.polling_interval  = stn_dict.get('polling_interval', 60)
        self.model             = stn_dict.get('model', 'TE923')
        self.pressure_offset   = stn_dict.get('pressure_offset', None)
        if self.pressure_offset is not None:
            self.pressure_offset = float(self.pressure_offset)

        self.out_sensor        = stn_dict.get('out_sensor', '1')

        vendor_id              = int(stn_dict.get('vendor_id',  '0x1130'), 0)
        product_id             = int(stn_dict.get('product_id', '0x6801'), 0)
        device_id              = stn_dict.get('device_id', None)
        self.station = Station(vendor_id, product_id, device_id)
        self.station.open()

    @property
    def hardware_name(self):
        return self.model

    def closePort(self):
        self.station.close()
        self.station = None

    def genLoopPackets(self):
        while True:
            data = self.station.get_readings()
            packet = self.data_to_packet(data,
                                         altitude=self.altitude,
                                         pressure_offset=self.pressure_offset,
                                         last_rain=self._last_rain,
                                         last_rain_ts=self._last_rain_ts)
            self._last_rain = packet['rainTotal']
            self._last_rain_ts = packet['dateTime']
            yield packet
            time.sleep(self.polling_interval)

    def data_to_packet(self, data, altitude=0, pressure_offset=None,
                       last_rain=None, last_rain_ts=None):
        """convert raw data to format and units required by weewx"""
        packet = {}
        packet['usUnits'] = weewx.METRIC
        packet['dateTime'] = int(time.time() + 0.5)

        packet['inTemp'] = data['t_in'] # T is degree C
        packet['inHumidity'] = data['h_in'] # H is percent
        packet['outTemp'] = data['t_%s' % self.out_sensor]
        packet['outHumidity'] = data['h_%s' % self.out_sensor]
        packet['pressure'] = data['pressure']
        packet['UV'] = data['uv']
        packet['windSpeed'] = data['windspeed']
        if packet['windSpeed'] is not None:
            packet['windSpeed'] *= 3.6 # weewx wants km/h
        packet['windGust'] = data['windgust']
        if packet['windGust'] is not None:
            packet['windGust'] *= 3.6 # weewx wants km/h

        if packet['windSpeed'] is not None and packet['windSpeed'] > 0:
            packet['windDir'] = data['winddir']
            if packet['windDir'] is not None:
                packet['windDir'] *= 22.5 # weewx wants degrees
        else:
            packet['windDir'] = None

        if packet['windGust'] is not None and packet['windGust'] > 0:
            packet['windGustDir'] = data['winddir']
            if packet['windGustDir'] is not None:
                packet['windGustDir'] *= 22.5 # weewx wants degrees
        else:
            packet['windGustDir'] = None

        packet['rainTotal'] = data['rain']
        if packet['rainTotal'] is not None:
            packet['rainTotal'] *= 0.0635 # weewx wants cm
        packet['rain'] = calculate_rain(packet['rainTotal'], last_rain)

        packet['rainRate'] = calculate_rain_rate(packet['rain'],
                                                 packet['dateTime'],
                                                 last_rain_ts)

        packet['heatindex'] = weewx.wxformulas.heatindexC(
            packet['outTemp'], packet['outHumidity'])
        packet['dewpoint'] = weewx.wxformulas.dewpointC(
            packet['outTemp'], packet['outHumidity'])
        packet['windchill'] = data['windchill']

        # FIXME: station knows altitude, so 'pressure' might be 'altimeter'
        adjp = packet['pressure']
        if pressure_offset is not None and adjp is not None:
            adjp += pressure_offset
        packet['barometer'] = sp2bp(adjp, altitude, packet['outTemp'])
        packet['altimeter'] = sp2ap(adjp, altitude)

#        packet['txBatteryStatus'] = data['batteryUV']
#        packet['windBatteryStatus'] = data['batteryWind']
#        packet['rainBatteryStatus'] = data['batteryRain']
#        packet['outTempBatteryStatus'] = data['battery%s' % self.out_sensor]

        # battery5, battery4, battery3, battery2, battery1

        return packet


STATE_OK = 'ok'
STATE_INVALID = 'inv'
STATE_OUT_OF_RANGE = 'out_of_range'
STATE_MISSING_LINK = 'no_link'
STATE_ERROR = 'error'
BUFLEN = 35
ENDPOINT_IN = 0x01
READ_LENGTH = 0x8

def bcd2int(bcd):
    return int(((bcd & 0xf0) >> 4) * 10) + int(bcd & 0x0f)

def decode(buf, ts=int(time.time())):
    data = {}
    data['timestamp'] = ts
    for i in range(6):  # 5 channels plus indoor
        data.update(decode_th(buf, i))
    data.update(decode_uv(buf))
    data.update(decode_pressure(buf))
    data.update(decode_wind(buf))
    data.update(decode_rain(buf))
    data.update(decode_windchill(buf))
    data.update(decode_status(buf))
    return data

def decode_th(buf, i):
    """decode temperature and humidity from the indicated sensor."""

    if i == 0:
        tlabel = 't_in'
        tstate = 't_in_state'
        hlabel = 'h_in'
        hstate = 'h_in_state'
    else:
        tlabel = 't_%d' % i
        tstate = 't_%d_state' % i
        hlabel = 'h_%d' % i
        hstate = 'h_%d_state' % i

    offset = i*3
    data = {}
    data[tstate] = STATE_OK
    if DEBUG_DECODE:
        logdbg("TMP%d BUF[%02d]=%02x BUF[%02d]=%02x BUF[%02d]=%02x" %
               (i, 0+offset, buf[0+offset], 1+offset, buf[1+offset],
                2+offset, buf[2+offset]))
    if bcd2int(buf[0+offset] & 0x0f) > 9:
        if DEBUG_DECODE > 1:
            logdbg("TMP%d buffer 0 & 0x0f > 9" % i)
        # FIXME: wview uses 0x0c || 0x0b instead of 0x06 || 0x0b
        if buf[0+offset] & 0x0f == 0x06 or buf[0+offset] & 0x0f == 0x0b:
            if DEBUG_DECODE > 1:
                logdbg("TMP%d buffer 0 & 0x0f = 0x0c or 0x0b" % i)
            data[tstate] = STATE_OUT_OF_RANGE
        else:
            if DEBUG_DECODE > 1:
                logdbg("TMP%d other error in buffer 0" % i)
            data[tstate] = STATE_INVALID
    if buf[1+offset] & 0x40 != 0x40 and i > 0:
        if DEBUG_DECODE > 1:
            logdbg("TMP%d buffer 1 bit 6 set" % i)
        data[tstate] = STATE_OUT_OF_RANGE
    # FIXME: what about missing link for temperature?

    if data[tstate] == STATE_OK:
        data[tlabel] = bcd2int(buf[0+offset]) / 10.0 \
            + bcd2int(buf[1+offset] & 0x0f) * 10.0
        if DEBUG_DECODE > 1:
            logdbg("TMP%d before is %0.2f" % (i, data[tlabel]))
        if buf[1+offset] & 0x20 == 0x20:
            data[tlabel] += 0.05
        if buf[1+offset] & 0x80 != 0x80:
            data[tlabel] *= -1
        if DEBUG_DECODE > 1:
            logdbg("TMP%d after is %0.2f" % (i, data[tlabel]))
    else:
        data[tlabel] = None

    # FIXME: the following is suspect...
    if data[tstate] == STATE_OUT_OF_RANGE or data[tstate] == STATE_ERROR:
        data[hstate] = data[tstate]
        data[hlabel] = None
    elif bcd2int(buf[2+offset] & 0x0f) > 9:
        data[hstate] = STATE_MISSING_LINK # FIXME: should be oor or invalid?
        data[hlabel] = None
    else:
        data[hstate] = STATE_OK
        data[hlabel] = bcd2int(buf[2+offset])

    if DEBUG_DECODE:
        logdbg("TMP%d %s %s %s %s" % (i, data[tlabel], data[tstate],
                                      data[hlabel], data[hstate]))
    return data

# FIXME: wview and te923tool disagree about uv calculation.  wview does a
# rightshift of 4: (bcd2int(buf[18] & 0xf0) >> 4)
def decode_uv(buf):
    """decode data from uv sensor"""
    data = {}
    if DEBUG_DECODE:
        logdbg("UVX  BUF[18]=%02x BUF[19]=%02x" % (buf[18],buf[19]))
    if buf[18] == 0xaa and buf[19] == 0x0a:
        data['uv_state'] = STATE_MISSING_LINK
        data['uv'] = None
    elif bcd2int(buf[18]) > 99 or bcd2int(buf[19]) > 99:
        data['uv_state'] = STATE_INVALID
        data['uv'] = None
    else:
        data['uv_state'] = STATE_OK
        data['uv'] = bcd2int(buf[18] & 0x0f) / 10.0 \
            + bcd2int(buf[18] & 0xf0) \
            + bcd2int(buf[19] & 0x0f) * 10.0
    if DEBUG_DECODE:
        logdbg("UVX  %s %s" % (data['uv'], data['uv_state']))
    return data

def decode_pressure(buf):
    """decode pressure data"""
    data = {}
    if DEBUG_DECODE:
        logdbg("PRS  BUF[20]=%02x BUF[21]=%02x" % (buf[20], buf[21]))
    if buf[21] & 0xf0 == 0xf0:
        data['pressure_state'] = STATE_INVALID
        data['pressure'] = None
    else:
        data['pressure_state'] = STATE_OK
        data['pressure'] = int(buf[21] * 0x100 + buf[20]) * 0.0625
    if DEBUG_DECODE:
        logdbg("PRS  %s %s" % (data['pressure'], data['pressure_state']))
    return data

# NB: te923tool divides by 2.23694, wview does not
#   1 meter/sec = 2.23694 miles/hour
# NB: wview multiplies winddir by 22.5, te923tool does not
def decode_wind(buf):
    data = {}
    if DEBUG_DECODE:
        logdbg("WGS  BUF[25]=%02x BUF[26]=%02x" % (buf[25], buf[26]))
    if bcd2int(buf[25] & 0xf0) > 90 or bcd2int(buf[25] & 0x0f) > 9:
        if buf[25] == 0xbb and buf[26] == 0x8b:
            data['windgust_state'] = STATE_OUT_OF_RANGE
        elif buf[25] == 0xee and buf[26] == 0x8e:
            data['windgust_state'] = STATE_MISSING_LINK
        else:
            data['windgust_state'] = STATE_ERROR
        data['windgust'] = None
    else:
        data['windgust_state'] = STATE_OK
        offset = 100 if buf[26] & 0x10 == 0x10 else 0
        data['windgust'] = bcd2int(buf[25]) / 10.0 \
            + bcd2int(buf[26] & 0x0f) * 10.0 \
            + offset
    if DEBUG_DECODE:
        logdbg("WGS  %s %s" % (data['windgust'], data['windgust_state']))

    if DEBUG_DECODE:
        logdbg("WSP  BUF[27]=%02x BUF[28]=%02x" % (buf[27], buf[28]))
    if bcd2int(buf[27] & 0xf0) > 90 or bcd2int(buf[27] & 0x0f) > 9:
        if buf[27] == 0xbb and buf[28] == 0x8b:
            data['windspeed_state'] = STATE_OUT_OF_RANGE
        elif buf[27] == 0xee and buf[28] == 0x8e:
            data['windspeed_state'] = STATE_MISSING_LINK
        else:
            data['windspeed_state'] = STATE_ERROR
        data['windspeed'] = None
    else:
        data['windspeed_state'] = STATE_OK
        offset = 100 if buf[28] & 0x10 == 0x10 else 0
        data['windspeed'] = bcd2int(buf[27]) / 10.0 \
            + bcd2int(buf[28] & 0x0f) * 10.0 \
            + offset
    if DEBUG_DECODE:
        logdbg("WSP  %s %s" % (data['windspeed'], data['windspeed_state']))

    if DEBUG_DECODE:
        logdbg("WDR  BUF[29]=%02x" % buf[29])
    if data['windspeed_state'] == STATE_MISSING_LINK:
        data['winddir_state'] = data['windspeed_state']
        data['winddir'] = None
    else:
        data['winddir_state'] = STATE_OK
        data['winddir'] = int(buf[29] & 0x0f)
    if DEBUG_DECODE:
        logdbg("WDR  %s %s" % (data['winddir'], data['winddir_state']))
    
    return data

# FIXME: figure out how to detect link status between station and rain bucket
# FIXME: according to sebastian, the counter is in the station, not the rain
# bucket.  so if the link between rain bucket and station is lost, the station
# will miss rainfall and there is no way to know about it.

# NB: wview treats the raw rain count as millimeters
def decode_rain(buf):
    data = {}
    if DEBUG_DECODE:
        logdbg("RAIN BUF[30]=%02x BUF[31]=%02x" % (buf[30], buf[31]))
    data['rain_state'] = STATE_OK
    data['rain'] = int(buf[31] * 0x100 + buf[30])
    if DEBUG_DECODE:
        logdbg("RAIN %s %s" % (data['rain'], data['rain_state']))
    return data

def decode_windchill(buf):
    data = {}
    if DEBUG_DECODE:
        logdbg("WCL  BUF[23]=%02x BUF[24]=%02x" % (buf[23], buf[24]))
    if bcd2int(buf[23] & 0xf0) > 90 or bcd2int(buf[23] & 0x0f) > 9:
        if buf[23] == 0xaa and buf[24] == 0x8a:
            data['windchill_state'] = STATE_INVALID
        elif buf[23] == 0xbb and buf[24] == 0x8b:
            data['windchill_state'] = STATE_OUT_OF_RANGE
        elif buf[23] == 0xee and buf[24] == 0x8e:
            data['windchill_state'] = STATE_MISSING_LINK
        else:
            data['windchill_state'] = STATE_ERROR
        data['windchill'] = None
    elif buf[24] & 0x40 != 0x40:
        data['windchill_state'] = STATE_OUT_OF_RANGE
        data['windchill'] = None
    else:
        data['windchill_state'] = STATE_OK
        data['windchill'] = bcd2int(buf[23]) / 10.0 + bcd2int(buf[24] & 0x0f) * 10.0
        if buf[24] & 0x20 == 0x20:
            data['windchill'] += 0.05
        if buf[24] & 0x80 != 0x80:
            data['windchill'] *= -1;
    if DEBUG_DECODE:
        logdbg("WCL  %s %s" % (data['windchill'], data['windchill_state']))
    return data

def decode_status(buf):
    data = {}
    if DEBUG_DECODE:
        logdbg("STT  BUFF[22]=%02x" % buf[22])
    if buf[22] & 0x0f == 0x0f:
        data['storm'] = None
        data['forecast'] = None
    else:
        data['storm'] = True if buf[22] & 0x08 == 0x08 else False
        data['forecast'] = int(buf[22] & 0x07)
    if DEBUG_DECODE:
        logdbg("STT  %s %s" % (data['storm'], data['forecast']))
    return data

class DataRequestFailed(Exception):
    """USB control message returned unexpected value"""

class BadLength(Exception):
    """Bogus data length"""

class BadCRC(Exception):
    """Bogus CRC value while reading from USB"""

class BadLeadingByte(Exception):
    """Bogus checksum while reading from USB"""

class BadRead(Exception):
    """No valid response from station"""

class Station(object):
    def __init__(self, vendor_id=0x1130, product_id=0x6801,
                 dev_id=None, ifc=None, cfg=None):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device_id = dev_id
        self.interface = ifc
        self.configuration = cfg
        self.handle = None

        self.elevation = None
        self.latitude = None
        self.longitude = None
        self.archive_interval = None

    def _find(self, vendor_id, product_id, device_id):
        """Find the vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    if device_id is None or dev.filename == device_id:
                        loginf('Found device on USB bus=%s device=%s' % (bus.dirname, dev.filename))
                        return dev
        return None

    def open(self):
        dev = self._find(self.vendor_id, self.product_id, self.device_id)
        if not dev:
            logcrt("Cannot find USB device with VendorID=0x%04x ProductID=0x%04x DeviceID=%s" % (self.vendor_id, self.product_id, self.device_id))
            raise weewx.WeeWxIOError("Unable to find station on USB")

        if self.configuration is None:
            self.configuration = dev.configurations[0]
        if self.interface is None:
            self.interface = self.configuration.interfaces[0][0]
        self.handle = dev.open()

        try:
            self.handle.detachKernelDriver(self.interface)
        except Exception:
            pass

        try:
            self.handle.setConfiguration(self.configuration)
            self.handle.claimInterface(self.interface)
            self.handle.setAltInterface(self.interface)
        except usb.USBError, e:
            self.close()
            logcrt("Unable to claim USB interface %s of configuration %s: %s" %
                   (self.interface, self.configuration, e))
            raise weewx.WeeWxIOError(e)

    def close(self):
        try:
            self.handle.releaseInterface()
        except Exception:
            pass
        try:
            self.handle.detachKernelDriver(iface)
        except Exception:
            pass
        self.handle = None

    # The te923tool does reads in chunks with pause between.  According to
    # the wview implementation, after sending the read command the device will
    # send back 32 bytes of data within 100 ms.  If not, the command was not
    # properly received.
    def _raw_read(self, addr, timeout=50):
        reqbuf = [0x05, 0x0AF, 0x00, 0x00, 0x00, 0x00, 0xAF, 0xFE]
        reqbuf[4] = addr / 0x10000
        reqbuf[3] = (addr - (reqbuf[4] * 0x10000)) / 0x100
        reqbuf[2] = addr - (reqbuf[4] * 0x10000) - (reqbuf[3] * 0x100)
        reqbuf[5] = (reqbuf[1] ^ reqbuf[2] ^ reqbuf[3] ^ reqbuf[4])
        ret = self.handle.controlMsg(requestType=0x21,
                                     request=usb.REQ_SET_CONFIGURATION,
                                     value=0x0200,
                                     index=0x0000,
                                     buffer=reqbuf,
                                     timeout=timeout)
        if ret != 8:
            msg = 'Unexpected response to data request: %s != 8' % ret
            logerr(msg)
            raise DataRequestFailed(msg)

        rbuf = []
        time.sleep(0.3)
        try:
            buf = self.handle.interruptRead(ENDPOINT_IN, READ_LENGTH, timeout)
            while buf:
                nbytes = buf[0]
                if DEBUG_READ:
                    msg = 'raw: '
                    msg += ' '.join(["%02x" % buf[x] for x in range(8)])
                    logdbg(msg)
                if nbytes > 7 or nbytes > len(buf)-1:
                    raise BadLength("bogus length during read: %d" % nbytes)
                rbuf.extend(buf[1:1+nbytes])
                time.sleep(0.15)
                buf = self.handle.interruptRead(ENDPOINT_IN, READ_LENGTH, timeout)
        except usb.USBError, e:
            logdbg(e)

        if len(rbuf) < 34:
            raise BadLength("not enough bytes: %d < 34" % len(rbuf))
        if rbuf[0] != 0x5a:
            raise BadLeadingByte("bad byte: %02x != %02x" % (rbuf[0], 0x5a))

        crc = 0x00
        for x in rbuf[:33]:
            crc = crc ^ x
        if crc != rbuf[33]:
            raise BadCRC("bad crc: %02x != %02x" % (crc, rbuf[33]))
        return rbuf

    def _read(self, addr, max_tries=100):
        if DEBUG_READ:
            logdbg("reading station at address 0x%06x" % addr)
        cnt = 0
        while cnt < max_tries:
            cnt += 1
            try:
                buf = self._raw_read(addr)
                if DEBUG_READ:
                    logdbg("BUF  " + ' '.join(["%02x" % x for x in buf]))
                return buf
            except (BadLength, BadLeadingByte, BadCRC), e:
                logdbg(e)
        else:
            raise BadRead("No read after %d attempts" % cnt)

    def get_status(self):
        """get station status"""
        status = {}

        buf = self._read(0x000098)
        status['barVer']  = buf[1]
        status['uvVer']   = buf[2]
        status['rccVer']  = buf[3]
        status['windVer'] = buf[4]
        status['sysVer']  = buf[5]

        buf = self._read(0x00004c)
        status['batteryRain'] = True if buf[1] & 0x80 == 0x80 else False
        status['batteryWind'] = True if buf[1] & 0x40 == 0x40 else False
        status['batteryUV']   = True if buf[1] & 0x20 == 0x20 else False
        status['battery5']    = True if buf[1] & 0x10 == 0x10 else False
        status['battery4']    = True if buf[1] & 0x08 == 0x08 else False
        status['battery3']    = True if buf[1] & 0x04 == 0x04 else False
        status['battery2']    = True if buf[1] & 0x02 == 0x02 else False
        status['battery1']    = True if buf[1] & 0x01 == 0x01 else False
        
        return status

    def get_readings(self):
        """get sensor readings from the station, return as dictionary"""
        buf = self._read(0x020001)
        data = decode(buf[1:])
        return data

    def get_memory(self, count=208, bigmem=False):
        if bigmem:
            count = 3442
        addr = None
        records = []
        for i in range(count):
            logdbg("reading record %d of %d" % (i+1, count))
            record,addr = self.get_record(addr,bigmem)
            records.append(record)
        return records

    def get_record(self, addr=None, bigmem=False):
        """return memory dump from station"""
        radr = 0x001FBB
        if bigmem:
            radr = 0x01ffec

        if addr is None:
            buf = self._read(0x0000fb)
            addr = (buf[3] * 0x100 + buf[5]) * 0x26 + 0x101

        buf = self._read(addr)
        now = int(time.time())
        tt = time.localtime(now)
        year = tt.tm_year
        month = buf[1] & 0x0f
        day = bcd2int(buf[2])
        if month > tt.tm_mon + 1:
            year -= 1
        hour = bcd2int(buf[3])
        minute = bcd2int(buf[4])

        ts = time.mktime((year, month-1, day, hour, minute, 0, 0, 0, -1))

        tmpbuf = BUFLEN*[0]
        for i,x in enumerate(buf[5:16]):
            tmpbuf[i] = x
        addr += 0x10
        buf = self._read(addr)
        for i,x in enumerate(buf[1:21]):
            tmpbuf[11+i] = x
        data = decode(tmpbuf)
        addr += 0x16
        if addr > radr:
            addr = 0x000101

        data['timestamp'] = int(ts)

        return data, addr



# define a main entry point for basic testing of the station without weewx
# engine and service overhead.

usage = """%prog [options] [--debug] [--help]"""

def main():
    syslog.openlog('wee_te923', syslog.LOG_PID | syslog.LOG_CONS)
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display diagnostic information while running')
    parser.add_option('--status', dest='status', action='store_true',
                      help='display station status')
    parser.add_option('--readings', dest='readings', action='store_true',
                      help='display sensor readings')
    parser.add_option('--memory', dest='memory', action='store_true',
                      help='dump station memory')
    (options, args) = parser.parse_args()

    if options.debug is not None:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    else:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

    station = None
    try:
        station = Station()
        station.open()
        if options.status:
            data = station.get_status()
            for key in sorted(data):
                print "%s: %s" % (key.rjust(16), data[key])
        if options.readings:
            data = station.get_readings()
            for key in sorted(data):
                print "%s: %s" % (key.rjust(16), data[key])
        if options.memory:
            data = station.get_memory(count=10)
            for x in data:
                print x
    finally:
        if station is not None:
            station.close()

if __name__ == '__main__':
    main()
