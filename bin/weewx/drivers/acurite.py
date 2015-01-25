#!/usr/bin/env python
# $Id$
# Copyright 2014 Matthew Wall
# See the file LICENSE.txt for your full rights.
#
# Credits:
# Thanks to Rich of Modern Toil (2012)
#  http://moderntoil.com/?p=794
#
# Thanks to George Nincehelser
#  http://nincehelser.com/ipwx/
#
# Thanks to Dave of 'desert home' (2014)
#  http://www.desert-home.com/2014/11/acurite-weather-station-raspberry-pi.html
#
# Thanks to Brett Warden
#  figured out a linear function for the pressure sensor in the 02032
#
# Slow-clap thanks to Michael Walsh
#  http://forum1.valleyinfosys.com/index.php
#
# No thanks to AcuRite or Chaney instruments.  They refused to provide any
# technical details for the development of this driver.

"""Driver for AcuRite weather stations.

There are many variants of the AcuRite weather stations and sensors.  This
driver is known to work with the consoles that have a USB interface such as
models 01025 and 01035.  It should also work with the 02032C.

The AcuRite stations were introduced in 2011.  The 02032 model was introduced
in 2013 or 2014.  It appears to be a low-end model - it has fewer buttons,
and a different pressure sensor.

AcuRite publishes the following specifications:

  temperature outdoor: -40F to 158F; -40C to 70C
   temperature indoor: 32F to 122F; 0C to 50C
     humidity outdoor: 1% to 99%
      humidity indoor: 16% to 98%
           wind speed: 0 to 99 mph; 0 to 159 kph
       wind direction: 16 points
             rainfall: 0 to 99.99 in; 0 to 99.99 mm
       wireless range: 330 ft; 100 m
  operating frequency: 433 MHz
        display power: 4.5V AC adapter (6 AA bateries, optional)
         sensor power: 4 AA batteries

The memory size is 512 KB and is not expandable.  The firmware cannot be
modified or upgraded.

According to AcuRite specs, the update frequencies are as follows:

  wind speed: 18 second updates
  wind direction: 30 second updates
  outdoor temperature and humidity: 60 second updates
  pc connect csv data logging: 12 minute intervals
  pc connect to acurite software: 18 second updates

The pressure sensor in the console reports a station pressure, but the
firmware does some kind of averaging to it so the console displays a pressure
that is usually nothing close to the station pressure.

According to AcuRite they use a 'patented, self-adjusting altitude pressure
compensation' algorithm.  Not helpful, and in practice not accurate.  So we
try to get the raw data.

Apparently the AcuRite bridge uses the HP03S integrated pressure sensor:

  http://www.hoperf.com/upload/sensor/HP03S.pdf

The calculation in that specification happens to work for some of the AcuRite
consoles (01035, 01036, others?).  However, some AcuRite consoles (only the
02032?) use the MS5607-02BA03 sensor:

  http://www.meas-spec.com/downloads/MS5607-02BA03.pdf

The AcuRite station has 4 USB modes:

      show data   store data   stream data
  1   x           x
  2   x           
  3   x           x            x
  4   x                        x

The console does not respond to USB requests when in mode 1 or mode 2.

The console shows up as a USB device even if it is turned off.  If the console
is powered on and communication has been established, then power is removed,
the communication will continue.  So the console appears to draw some power
from the bus.

Apparently some stations have issues when the history buffer fills up.

Some reports say that the station stops recording data.  Some reports say that
the 02032 (and possibly other stations) should not use history mode at all
because the data are written to flash memory, which wears out, sometimes
quickly.  Some reports say this 'bricks' the station, however those reports
mis-use the term 'brick', because the station still works and communication
can sometimes be re-established.

There may be firmware timing issues that affect USB communication.

The acurite stations are probably a poor choice for remote operation.  If
the power cycles on the console, communication might not be possible.  Some
consoles (but not all?) default to mode 2, which means no USB communication.

Communication Formats

The AcuRite station emits three different data strings, R1, R2 and R3.  The R1
string is 10 bytes long, contains readings from the remote sensors, and comes
in different flavors.  One contains wind speed, wind direction, and rain
counter.  Another contains wind speed, temperature, and humidity.  The R2
string is 25 bytes long and contains the temperature and pressure readings
from the console, plus a whole bunch of calibration constants required to
figure out the actual pressure and temperature.  The R3 string is 33 bytes
and contains historical data and (apparently) the humidity readings from the
console sensors.

Message Maps

R1 - 10 bytes
 0  1  2  3  4  5  6  7  8  9
01 CS SS ?1 ?W WD 00 RR ?r ??
01 CS SS ?8 ?W WT TT HH ?r ??

01 CF FF FF FF FF FF FF 00 00      no sensor unit found
01 FF FF FF FF FF FF FF FF 00      no sensor unit found
01 8b fa 71 00 06 00 0c 00 00      connection to sensor unit lost
01 8b fa 78 00 08 75 24 01 00      connection to sensor unit weak/lost
01 8b fa 78 00 08 48 25 03 ff      flavor 8
01 8b fa 71 00 06 00 02 03 ff      flavor 1
01 C0 5C 78 00 08 1F 53 03 FF      flavor 8
01 C0 5C 71 00 05 00 0C 03 FF      flavor 1

0: identifier                      01 indicates R1 messages
1: channel         x & 0xf0        observed values: 0xC=A, 0x8=B, 0x0=C
1: sensor_id hi    x & 0x0f
2: sensor_id lo
3: ?sensor type    x & 0xf0        7 is 5-in-1?
3: message flavor  x & 0x0f        type 1 is windSpeed, windDir, rain
4: wind speed     (x & 0x1f) << 3
5: wind speed     (x & 0x70) >> 4
5: wind dir       (x & 0x0f)
6: ?                               always seems to be 0
7: rain           (x & 0x7f)
8: ?battery       (x & 0xf0)       0 is normal?
8: rssi           (x & 0x0f)       observed values: 0,1,2,3
9: ?                               observed values: 0x00, 0xff

0: identifier                      01 indicates R1 messages
1: channel         x & 0xf0        observed values: 0xC=A, 0x8=B, 0x0=C
1: sensor_id hi    x & 0x0f
2: sensor_id lo
3: ?sensor type    x & 0xf0        7 is 5-in-1?
3: message flavor  x & 0x0f        type 8 is windSpeed, outTemp, outHumidity
4: wind speed     (x & 0x1f) << 3
5: wind speed     (x & 0x70) >> 4
5: temp           (x & 0x0f) << 7
6: temp           (x & 0x7f)
7: humidity       (x & 0x7f)
8: ?battery       (x & 0xf0)       0 is normal?
8: rssi           (x & 0x0f)       observed values: 0,1,2,3
9: ?                               observed values: 0x00, 0xff


R2 - 25 bytes
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
02 00 00 C1 C1 C2 C2 C3 C3 C4 C4 C5 C5 C6 C6 C7 C7 AA BB CC DD TR TR PR PR

02 00 00 4C BE 0D EC 01 52 03 62 7E 38 18 EE 09 C4 08 22 06 07 7B A4 8A 46
02 00 00 80 00 00 00 00 00 04 00 10 00 00 00 09 60 01 01 01 01 8F C7 4C D3

 0: identifier                                     02 indicates R2 messages
 1: ?                                              always seems to be 0
 2: ?                                              always seems to be 0
 3-4:   C1 sensitivity coefficient                 0x100 - 0xffff
 5-6:   C2 offset coefficient                      0x00 - 0x1fff
 7-8:   C3 temperature coefficient of sensitivity  0x00 - 0x400
 9-10:  C4 temperature coefficient of offset       0x00 - 0x1000
 11-12: C5 reference temperature                   0x1000 - 0xffff
 13-14: C6 temperature coefficient of temperature  0x00 - 0x4000
 15-16: C7 offset fine tuning                      0x960 - 0xa28
 17:    A sensor-specific parameter                0x01 - 0x3f
 18:    B sensor-specific parameter                0x01 - 0x3f
 19:    C sensor-specific parameter                0x01 - 0x0f
 20:    D sensor-specific parameter                0x01 - 0x0f
 21-22: TR measured temperature                    0x00 - 0xffff
 23-24: PR measured pressure                       0x00 - 0xffff


R3 - 33 bytes
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 ...
03 aa 55 01 00 00 00 20 20 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ...


X1 - 2 bytes
 0  2
7c e2
84 e2

0: ?
1: ?
"""

# FIXME: can we set mode via software?
# FIXME: how to detect mode via software?
# FIXME: how to download stored data?
# FIXME: can the archive interval be changed?
# FIXME: how to clear station memory?
# FIXME: how to detect console type?
# FIXME: decode console battery level
# FIXME: decode sensor type - hi byte of byte 3 in R1 message?

# FIXME: decode inside humidity
# FIXME: decode historical records

# FIXME: is it better to open device for each read, or maintain open device?

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers

DRIVER_NAME = 'AcuRite'
DRIVER_VERSION = '0.11'
DEBUG_RAW = 0


def loader(config_dict, engine):
    return AcuRiteDriver(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return AcuRiteConfEditor()


def logmsg(level, msg):
    syslog.syslog(level, 'acurite: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

def _fmt_bytes(data):
    return ' '.join(['%02x' % x for x in data])


class AcuRiteDriver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with an AcuRite weather station.

    model: Which station model is this?
    [Optional. Default is 'AcuRite']

    max_tries - How often to retry communication before giving up.
    [Optional. Default is 10]
    """
    def __init__(self, **stn_dict):
        self.model = stn_dict.get('model', 'AcuRite')
        self.max_tries = int(stn_dict.get('max_tries', 10))
        self.retry_wait = int(stn_dict.get('retry_wait', 10))
        self.polling_interval = int(stn_dict.get('polling_interval', 18))
        self.last_rain = None
        self.last_r3 = None
        self.r3_fail_count = 0
        loginf('driver version is %s' % DRIVER_VERSION)

        global DEBUG_RAW
        DEBUG_RAW = int(stn_dict.get('debug_raw', 0))

    @property
    def hardware_name(self):
        return self.model

    def genLoopPackets(self):
        last_raw2 = None
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                now = int(time.time() + 0.5)
                packet = {'dateTime': now, 'usUnits': weewx.METRIC}
                with Station() as station:
                    raw1 = station.read_R1()
                    raw2 = station.read_R2()
#                    raw3 = self.read_R3(station, now)
                if DEBUG_RAW > 0:
                    logdbg("R1: %s" % _fmt_bytes(raw1))
                    logdbg("R2: %s" % _fmt_bytes(raw2))
#                    logdbg("R3: %s" % _fmt_bytes(raw3))
                Station.check_pt_constants(last_raw2, raw2)
                last_raw2 = raw2
                packet.update(Station.decode_R1(raw1))
                packet.update(Station.decode_R2(raw2))
                self._augment_packet(packet)
                ntries = 0
                yield packet
                time.sleep(self.polling_interval)
            except (usb.USBError, weewx.WeeWxIOError), e:
                logerr("Failed attempt %d of %d to get LOOP data: %s" %
                       (ntries, self.max_tries, e))
                time.sleep(self.retry_wait)
                cnt = 0
        else:
            msg = "Max retries (%d) exceeded for LOOP data" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    def _augment_packet(self, packet):
        # calculate the rain delta from the total
        if 'rain_total' in packet:
            if self.last_rain is not None:
                packet['rain'] = packet['rain_total'] - self.last_rain
            else:
                packet['rain'] = None
            self.last_rain = packet['rain_total']

        # no wind direction when wind speed is zero
        if 'windSpeed' in packet and not packet['windSpeed']:
            packet['windDir'] = None

        # if there is no connection to sensors, clear the readings
        if 'rssi' in packet and  packet['rssi'] == 0:
            packet['outTemp'] = None
            packet['outHumidity'] = None
            packet['windSpeed'] = None
            packet['windDir'] = None
            packet['rain'] = None

        # map raw data to observations in the default database schema
        if 'sensor_battery' in packet:
            if packet['sensor_battery'] is not None:
                packet['txTempBatteryStatus'] = 1 if packet['sensor_battery'] else 0
            else:
                packet['txTempBatteryStatus'] = None
        if 'rssi' in packet and packet['rssi'] is not None:
            packet['rxCheckPercent'] = 100 * packet['rssi'] / Station.MAX_RSSI

    def read_R3(self, station, now):
        # attempt to read R3 every 12 minutes.  if the read fails multiple
        # times, make a single log message about enabling usb mode 3 then do
        # not try it again.
        r3 = []
        if self.r3_fail_count > 3:
            return r3
        if self.last_r3 is None or now - self.last_r3 > 720:
            try:
                x = statoin.read_x()
                r3 = station.read_R3()
                self.last_r3 = now
            except usb.USBError, e:
                logdbg("R3: read failed: %s" % e)
                self.r3_fail_count += 1
                if self.r3_fail_count > 3:
                    loginf("R3: put station in USB mode 3 to enable R3 data")
        return r3


class Station(object):
    # these identify the weather station on the USB
    VENDOR_ID = 0x24c0
    PRODUCT_ID = 0x0003

    # map the raw wind direction index to degrees on the compass
    IDX_TO_DEG = {6: 0.0, 14: 22.5, 12: 45.0, 8: 67.5, 10: 90.0, 11: 112.5,
                  9: 135.0, 13: 157.5, 15: 180.0, 7: 202.5, 5: 225.0, 1: 247.5,
                  3: 270.0, 2: 292.5, 0: 315.0, 4: 337.5}

    # map the raw channel value to something we prefer
    # A is 1, B is 2, C is 3
    CHANNELS = {12: 1, 8: 2, 0: 3}

    # maximum value for the rssi
    MAX_RSSI = 3.0

    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID, dev_id=None):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device_id = dev_id
        self.handle = None
        self.timeout = 1000

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):
        self.close()

    def open(self):
        dev = self._find_dev(self.vendor_id, self.product_id, self.device_id)
        if not dev:
            logcrt("Cannot find USB device with "
                   "VendorID=0x%04x ProductID=0x%04x DeviceID=%s" %
                   (self.vendor_id, self.product_id, self.device_id))
            raise weewx.WeeWxIOError('Unable to find station on USB')

        self.handle = dev.open()
        if not self.handle:
            raise weewx.WeeWxIOError('Open USB device failed')

        # These nominally report an empty string for the manufacturer and
        # 'Chaney Instruments' for the product.  However, they do not work
        # reliably, so these lines are commented for production use.
#        logdbg('mfr: %s' % self.handle.getString(dev.iManufacturer,30))
#        logdbg('product: %s' % self.handle.getString(dev.iProduct,30))

        # the station shows up as a HID with only one interface
        interface = 0

        # for linux systems, be sure kernel does not claim the interface 
        try:
            self.handle.detachKernelDriver(interface)
        except Exception:
            pass

        # attempt to claim the interface
        try:
            self.handle.claimInterface(interface)
            self.handle.setAltInterface(interface)
        except usb.USBError, e:
            self.close()
            logcrt("Unable to claim USB interface %s: %s" % (interface, e))
            raise weewx.WeeWxIOError(e)

    def close(self):
        if self.handle is not None:
            try:
                self.handle.releaseInterface()
            except Exception, e:
                logerr("release interface failed: %s" % e)
            self.handle = None

    def read(self, msgtype, nbytes):
        return self.handle.controlMsg(requestType=(usb.RECIP_INTERFACE +
                                                   usb.TYPE_CLASS +
                                                   usb.ENDPOINT_IN),
                                      request=usb.REQ_CLEAR_FEATURE,
                                      buffer=nbytes,
                                      value=0x0100 + msgtype,
                                      index=0x0,
                                      timeout=self.timeout)

    def read_R1(self):
        return self.read(1, 10)

    def read_R2(self):
        return self.read(2, 25)

    def read_R3(self):
        # FIXME: how many times can we do this read before timeout?
        # FIXME: is this a memory dump?
        # FIXME: what controls the return values?
        return self.read(3, 33)

    def read_x(self):
        # FIXME: what do the two bytes mean?
        return self.handle.controlMsg(requestType=(usb.RECIP_INTERFACE +
                                                   usb.TYPE_CLASS),
                                      request=usb.REQ_SET_CONFIGURATION,
                                      buffer=2,
                                      value=0x0201,
                                      index=0x0,
                                      timeout=self.timeout)

    @staticmethod
    def decode_R1(raw):
        data = dict()
        if len(raw) == 10 and raw[0] == 0x01:
            if raw[3] == 0xff and raw[2] == 0xcf:
                loginf("R1: no sensors found: %s" % _fmt_bytes(raw))
                data['channel'] = None
                data['sensor_id'] = None
                data['rssi'] = None
                data['sensor_battery'] = None
            elif raw[9] == 0x00:
                loginf("R1: ignoring dodgey data: %s" % _fmt_bytes(raw))
                data['channel'] = Station.decode_channel(raw)
                data['sensor_id'] = Station.decode_sensor_id(raw)
                data['rssi'] = Station.decode_rssi(raw)
                data['sensor_battery'] = None
            elif raw[3] & 0x0f == 1 or raw[3] & 0x0f == 8:
                if raw[3] & 0xf0 != 0x70:
                    loginf("R1: unexpected sensor type: %s" % _fmt_bytes(raw))
                data['channel'] = Station.decode_channel(raw)
                data['sensor_id'] = Station.decode_sensor_id(raw)
                data['rssi'] = Station.decode_rssi(raw)
                data['sensor_battery'] = Station.decode_sensor_battery(raw)
                data['windSpeed'] = Station.decode_windspeed(raw)
                if raw[3] & 0x0f == 1:
                    data['windDir'] = Station.decode_winddir(raw)
                    data['rain_total'] = Station.decode_rain(raw)
                else:
                    data['outTemp'] = Station.decode_outtemp(raw)
                    data['outHumidity'] = Station.decode_outhumid(raw)
            else:
                logerr("R1: unknown format: %s" % _fmt_bytes(raw))
        elif len(raw) == 10:
            logerr("R1: bad format: %s" % _fmt_bytes(raw))
        else:
            logerr("R1: bad length: %s" % _fmt_bytes(raw))
        return data

    @staticmethod
    def decode_R2(raw):
        data = dict()
        if len(raw) == 25 and raw[0] == 0x02:
            data['pressure'], data['inTemp'] = Station.decode_pt(raw)
        elif len(raw) == 25:
            logerr("R2: bad format: %s" % _fmt_bytes(raw))
        else:
            logerr("R2: bad length: %s" % _fmt_bytes(raw))
        return data

    @staticmethod
    def decode_channel(data):
        return Station.CHANNELS.get(data[1] & 0xf0)

    @staticmethod
    def decode_sensor_id(data):
        return ((data[1] & 0x0f) << 8) | data[2]

    @staticmethod
    def decode_rssi(data):
        # signal strength goes from 0 to 3, inclusive
        return data[8] & 0x0f

    @staticmethod
    def decode_sensor_battery(data):
        # battery level is 0xf or 0x0?
        # FIXME: need to verify this
        return data[8] & 0xf0

    @staticmethod
    def decode_windspeed(data):
        # extract the wind speed from an R1 message
        # decoded value is mph
        # return value is kph
        # FIXME: the speed decoding is not correct
        a = (data[4] & 0x1f) << 3
        b = (data[5] & 0x70) >> 4
        return 0.5 * (a | b) * 1.60934

    @staticmethod
    def decode_winddir(data):
        # extract the wind direction from an R1 message
        # decoded value is one of 16 points, convert to degrees
        v = data[5] & 0x0f
        return Station.IDX_TO_DEG.get(v)

    @staticmethod
    def decode_outtemp(data):
        # extract the temperature from an R1 message
#        t_F = 0.1 * ((((data[5] & 0x0f) << 7) | (data[6] & 0x7f)) - 400)
#        return (t_F - 32) * 5 / 9
        # return value is degree C
        a = (data[5] & 0x0f) << 7
        b = (data[6] & 0x7f)
        return (a | b) / 18.0 - 40.0

    @staticmethod
    def decode_outhumid(data):
        # extract the humidity from an R1 message
        # decoded value is percentage
        return data[7] & 0x7f

    @staticmethod
    def decode_rain(data):
        # decoded value is a count of bucket tips
        # each tip is 0.01 inch, return value is cm
        return (data[7] & 0x7f) * 0.0254

    @staticmethod
    def decode_pt(data):
        # decode pressure and temperature from the R2 message
        # decoded pressure is mbar, decoded temperature is degree C
        c1,c2,c3,c4,c5,c6,c7,a,b,c,d = Station.get_pt_constants(data)
        d2 = (data[21] << 8) + data[22]
        d1 = (data[23] << 8) + data[24]

        if (c1 == 0x8000 and c2 == c3 == 0x0 and c4 == 0x0400 and c5 == 0x1000
            and c6 == 0x0 and c7 == 0x0960 and a == b == c == d == 0x1):
            return Station.decode_pt_MS5607(d1, d2)
        elif (0x100 <= c1 <= 0xffff and
              0x0 <= c2 <= 0x1fff and
              0x0 <= c3 <= 0x400 and
              0x0 <= c4 <= 0x1000 and
              0x1000 <= c5 <= 0xffff and
              0x0 <= c6 <= 0x4000 and
              0x960 <= c7 <= 0xa28 and
              0x01 <= a <= 0x3f and 0x01 <= b <= 0x3f and
              0x01 <= c <= 0x0f and 0x01 <= d <= 0x0f):
            return Station.decode_pt_HP03S(c1,c2,c3,c4,c5,c6,c7,a,b,c,d,d1,d2)
        logerr("R2: unknown calibration constants: %s" % _fmt_bytes(data))
        return None, None

    @staticmethod
    def decode_pt_HP03S(c1,c2,c3,c4,c5,c6,c7,a,b,c,d,d1,d2):
        # for devices with the HP03S pressure sensor
        if d2 >= c5:
            dut = d2 - c5 - ((d2-c5)/128) * ((d2-c5)/128) * a / (2<<(c-1))
        else:
            dut = d2 - c5 - ((d2-c5)/128) * ((d2-c5)/128) * b / (2<<(c-1))
        off = 4 * (c2 + (c4 - 1024) * dut / 16384)
        sens = c1 + c3 * dut / 1024
        x = sens * (d1 - 7168) / 16384 - off
        p = 0.1 * (x * 10 / 32 + c7)
        t = 0.1 * (250 + dut * c6 / 65536 - dut / (2<<(d-1)))
        return p, t

    @staticmethod
    def decode_pt_MS5607(d1, d2):
        # for devices with the MS5607 sensor, do a linear scaling
        p = 0.062424282478109 * d1 - 206.48350164881
        t = 0.049538214503151 * d2 - 1801.189704931
        return p, t

    @staticmethod
    def decode_inhumid(data):
        # FIXME: decode inside humidity
        return None

    @staticmethod
    def get_pt_constants(data):
        c1 = (data[3] << 8) + data[4]
        c2 = (data[5] << 8) + data[6]
        c3 = (data[7] << 8) + data[8]
        c4 = (data[9] << 8) + data[10]
        c5 = (data[11] << 8) + data[12]
        c6 = (data[13] << 8) + data[14]
        c7 = (data[15] << 8) + data[16]
        a = data[17]
        b = data[18]
        c = data[19]
        d = data[20]
        return (c1,c2,c3,c4,c5,c6,c7,a,b,c,d)

    @staticmethod
    def check_pt_constants(a, b):
        if a is None or len(a) != 25 or len(b) != 25:
            return
        c1 = Station.get_pt_constants(a)
        c2 = Station.get_pt_constants(b)
        if c1 != c2:
            logerr("R2: constants changed: old: [%s] new: [%s]" % (
                    _fmt_bytes(a), _fmt_bytes(b)))

    @staticmethod
    def _find_dev(vendor_id, product_id, device_id=None):
        """Find the vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    if device_id is None or dev.filename == device_id:
                        logdbg('Found station at bus=%s device=%s' %
                               (bus.dirname, dev.filename))
                        return dev
        return None


class AcuRiteConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[AcuRite]
    # This section is for AcuRite weather stations.

    # The station model, e.g., 'AcuRite 01025' or 'AcuRite 02032C'
    model = 'AcuRite 01035'

    # The driver to use:
    driver = weewx.drivers.acurite
"""


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/acurite.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    syslog.openlog('acurite', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    (options, args) = parser.parse_args()

    if options.version:
        print "acurite driver version %s" % DRIVER_VERSION
        exit(0)

    with Station() as s:
        while True:
            ts = int(time.time())
            tstr = "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S %Z",
                                              time.localtime(ts)), ts)

#            try:
#                x = s.read_x()
#                print tstr, _fmt_bytes(x)
#                for i in range(0, 500):
#                    r3 = s.read_R3()
#                    print tstr, _fmt_bytes(r3)
#                    time.sleep(1)
#           except usb.USBError, e:
#                print tstr, e
#            time.sleep(12*60)

            r1 = s.read_R1()
            r2 = s.read_R2()
            print tstr, _fmt_bytes(r1), Station.decode_R1(r1)
            print tstr, _fmt_bytes(r2), Station.decode_R2(r2)
            time.sleep(18)
