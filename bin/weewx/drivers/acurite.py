#!/usr/bin/env python
# Copyright 2014 Matthew Wall
# See the file LICENSE.txt for your rights.
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
# Thanks to Weather Guy and Andrew Daviel (2015)
#  decoding of the R3 messages and R3 reports
#  decoding of the windspeed
#
# golf clap to Michael Walsh
#  http://forum1.valleyinfosys.com/index.php
#
# No thanks to AcuRite or Chaney instruments.  They refused to provide any
# technical details for the development of this driver.

"""Driver for AcuRite weather stations.

There are many variants of the AcuRite weather stations and sensors.  This
driver is known to work with the consoles that have a USB interface such as
models 01025, 01035, 02032C, and 02064C.

The AcuRite stations were introduced in 2011.  The 02032 model was introduced
in 2013 or 2014.  The 02032 appears to be a low-end model - it has fewer
buttons, and a different pressure sensor.  The 02064 model was introduced in
2015 and appears to be an attempt to fix problems in the 02032.

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

In fact, because of the message structure and the data logging design, these
are the actual update frequencies:

  wind speed: 18 seconds
  outdoor temperature, outdoor humidity: 36 seconds
  wind direction, rain total: 36 seconds
  indoor temperature, pressure: 60 seconds
  indoor humidity: 12 minutes (only when in USB mode 3)

These are the frequencies possible when reading data via USB.

There is no known way to change the archive interval of 12 minutes.

There is no known way to clear the console memory via software.

The AcuRite stations have no notion of wind gust.

The pressure sensor in the console reports a station pressure, but the
firmware does some kind of averaging to it so the console displays a pressure
that is usually nothing close to the station pressure.

According to AcuRite they use a 'patented, self-adjusting altitude pressure
compensation' algorithm.  Not helpful, and in practice not accurate.

Apparently the AcuRite bridge uses the HP03S integrated pressure sensor:

  http://www.hoperf.com/upload/sensor/HP03S.pdf

The calculation in that specification happens to work for some of the AcuRite
consoles (01035, 01036, others?).  However, some AcuRite consoles (only the
02032?) use the MS5607-02BA03 sensor:

  http://www.meas-spec.com/downloads/MS5607-02BA03.pdf

Communication

The AcuRite station has 4 modes:

      show data   store data   stream data
  1   x           x
  2   x           
  3   x           x            x
  4   x                        x

The console does not respond to USB requests when in mode 1 or mode 2.

There is no known way to change the mode via software.

The acurite stations are probably a poor choice for remote operation.  If
the power cycles on the console, communication might not be possible.  Some
consoles (but not all?) default to mode 2, which means no USB communication.

The console shows up as a USB device even if it is turned off.  If the console
is powered on and communication has been established, then power is removed,
the communication will continue.  So the console appears to draw some power
from the bus.

Apparently some stations have issues when the history buffer fills up.  Some
reports say that the station stops recording data.  Some reports say that
the 02032 (and possibly other stations) should not use history mode at all
because the data are written to flash memory, which wears out, sometimes
quickly.  Some reports say this 'bricks' the station, however those reports
mis-use the term 'brick', because the station still works and communication
can be re-established by power cycling and/or resetting the USB.

There may be firmware timing issues that affect USB communication.  Reading
R3 messages too frequently can cause the station to stop responding via USB.
Putting the station in mode 3 sometimes interferes with the collection of
data from the sensors; it can cause the station to report bad values for R1
messages (this was observed on a 01036 console, but not consistantly).

Testing with a 01036 showed no difference between opening the USB port once
during driver initialization and opening the USB port for each read.  However,
tests with a 02032 showed that opening for each read was much more robust.

Message Types

The AcuRite stations show up as USB Human Interface Device (HID).  This driver
uses the lower-level, raw USB API.  However, the communication is standard
requests for data from a HID.

The AcuRite station emits three different data strings, R1, R2 and R3.  The R1
string is 10 bytes long, contains readings from the remote sensors, and comes
in different flavors.  One contains wind speed, wind direction, and rain
counter.  Another contains wind speed, temperature, and humidity.  The R2
string is 25 bytes long and contains the temperature and pressure readings
from the console, plus a whole bunch of calibration constants required to
figure out the actual pressure and temperature.  The R3 string is 33 bytes
and contains historical data and (apparently) the humidity readings from the
console sensors.

The contents of the R2 message depends on the pressure sensor.  For stations
that use the HP03S sensor (e.g., 01035, 01036) the R2 message contains
factory-set constants for calculating temperature and pressure.  For stations
that use the MS5607-02BA03 sensor (e.g., 02032) the R2 message contents are
unknown.  In both cases, the last 4 bytes appear to contain raw temperature
and pressure readings, while the rest of the message bytes are constant.

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
01 cd ff 71 00 6c 39 71 03 ff
01 cd ff 78 00 67 3e 59 03 ff
01 cd ff 71 01 39 39 71 03 ff
01 cd ff 78 01 58 1b 4c 03 ff

0: identifier                      01 indicates R1 messages
1: channel         x & 0xf0        observed values: 0xC=A, 0x8=B, 0x0=C
1: sensor_id hi    x & 0x0f
2: sensor_id lo
3: ?status         x & 0xf0        7 is 5-in-1?  7 is battery ok?
3: message flavor  x & 0x0f        type 1 is windSpeed, windDir, rain
4: wind speed     (x & 0x1f) << 3
5: wind speed     (x & 0x70) >> 4
5: wind dir       (x & 0x0f)
6: ?                               always seems to be 0
7: rain           (x & 0x7f)
8: ?
8: rssi           (x & 0x0f)       observed values: 0,1,2,3
9: ?                               observed values: 0x00, 0xff

0: identifier                      01 indicates R1 messages
1: channel         x & 0xf0        observed values: 0xC=A, 0x8=B, 0x0=C
1: sensor_id hi    x & 0x0f
2: sensor_id lo
3: ?status         x & 0xf0        7 is 5-in-1?  7 is battery ok?
3: message flavor  x & 0x0f        type 8 is windSpeed, outTemp, outHumidity
4: wind speed     (x & 0x1f) << 3
5: wind speed     (x & 0x70) >> 4
5: temp           (x & 0x0f) << 7
6: temp           (x & 0x7f)
7: humidity       (x & 0x7f)
8: ?
8: rssi           (x & 0x0f)       observed values: 0,1,2,3
9: ?                               observed values: 0x00, 0xff


R2 - 25 bytes
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
02 00 00 C1 C1 C2 C2 C3 C3 C4 C4 C5 C5 C6 C6 C7 C7 AA BB CC DD TR TR PR PR

02 00 00 4C BE 0D EC 01 52 03 62 7E 38 18 EE 09 C4 08 22 06 07 7B A4 8A 46
02 00 00 80 00 00 00 00 00 04 00 10 00 00 00 09 60 01 01 01 01 8F C7 4C D3

for HP03S sensor:

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

for MS5607-02BA03 sensor:

 0: identifier                                     02 indicates R2 messages
 1: ?                                              always seems to be 0
 2: ?                                              always seems to be 0
 3-4:   C1 sensitivity coefficient                 0x800
 5-6:   C2 offset coefficient                      0x00
 7-8:   C3 temperature coefficient of sensitivity  0x00
 9-10:  C4 temperature coefficient of offset       0x0400
 11-12: C5 reference temperature                   0x1000
 13-14: C6 temperature coefficient of temperature  0x00
 15-16: C7 offset fine tuning                      0x0960
 17:    A sensor-specific parameter                0x01
 18:    B sensor-specific parameter                0x01
 19:    C sensor-specific parameter                0x01
 20:    D sensor-specific parameter                0x01
 21-22: TR measured temperature                    0x00 - 0xffff
 23-24: PR measured pressure                       0x00 - 0xffff


R3 - 33 bytes
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 ...
03 aa 55 01 00 00 00 20 20 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ...

An R3 report consists of multiple R3 messages.  Each R3 report contains records
that are delimited by the sequence 0xaa 0x55.  There is a separator sequence
prior to the first record, but not after the last record.

There are 6 types of records, each type identified by number:

   1,2  8-byte chunks of historical min/max data.  Each 8-byte chunk
          appears to contain two data bytes plus a 5-byte timestamp
          indicating when the event occurred.
   3    Timestamp indicating when the most recent history record was
          stored, based on the console clock.
   4    History data
   5    Timestamp indicating when the request for history data was
          received, based on the console clock.
   6    End marker indicating that no more data follows in the report.

Each record has the following header:

   0: record id            possible values are 1-6
 1,2: unknown              always seems to be 0
 3,4: size                 size of record, in 'chunks'
   5: checksum             total of bytes 0..4 minus one

  where the size of a 'chunk' depends on the record id:

   id         chunk size

   1,2,3,5    8 bytes
   4          32 bytes
   6          n/a

For all but ID6, the total record size should be equal to 6 + chunk_size * size
ID6 never contains data, but a size of 4 is always declared.

Timestamp records (ID3 and ID5):

 0-1: for ID3, the number of history records when request was received
 0-1: for ID5, unknown
   2: year
   3: month
   4: day
   5: hour
   6: minute
   7: for ID3, checksum - sum of bytes 0..6 (do not subtract 1)
   7: for ID5, unknown (always 0xff)

History Records (ID4):

Bytes 3,4 contain the number of history records that follow, say N.  After
stripping off the 6-byte record header there should be N*32 bytes of history
data.  If not, then the data are corrupt or there was an incomplete transfer.

The most recent history record is first, so the timestamp on record ID applies
to the first 32-byte chunk, and each record is 12 minutes into the past from
the previous.  Each 32-byte chunk has the following decoding:

   0-1: indoor temperature    (r[0]*256 + r[1])/18 - 100         C
   2-3: outdoor temperature   (r[2]*256 + r[3])/18 - 100         C
     4: unknown
     5: indoor humidity       r[5]                               percent
     6: unknown
     7: outdoor humidity      r[7]                               percent
   8-9: windchill             (r[8]*256 + r[9])/18 - 100         C
 10-11: heat index            (r[10]*256 + r[11])/18 - 100       C
 12-13: dewpoint              (r[12]*256 + r[13])/18 - 100       C
 14-15: barometer             ((r[14]*256 + r[15]) & 0x07ff)/10  kPa
    16: unknown
    17: unknown               0xf0
    17: wind direction        dirmap(r[17] & 0x0f)
 18-19: wind speed            (r[18]*256 + r[19])/16             kph
 20-21: wind max              (r[20]*256 + r[21])/16             kph
 22-23: wind average          (r[22]*256 + r[23])/16             kph
 24-25: rain                  (r[24]*256 + r[25]) * 0.254        mm
 26-30: rain timestamp        0xff if no rain event
    31: unknown

bytes 4 and 6 always seem to be 0
byte 16 is always zero on 02032 console, but is a copy of byte 21 on 01035.
byte 31 is always zero on 02032 console, but is a copy of byte 30 on 01035.


X1 - 2 bytes
 0  2
7c e2
84 e2

0: ?
1: ?
"""

# FIXME: how to detect mode via software?
# FIXME: what happens when memory fills up?  overwrite oldest?
# FIXME: how to detect console type?
# FIXME: how to set station time?
# FIXME: how to get station time?
# FIXME: decode console battery level
# FIXME: decode sensor type - hi byte of byte 3 in R1 message?

# FIXME: decode inside humidity
# FIXME: decode historical records
# FIXME: perhaps retry read when dodgey data or short read?

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers
import weewx.wxformulas
from weeutil.weeutil import to_bool

DRIVER_NAME = 'AcuRite'
DRIVER_VERSION = '0.24'
DEBUG_RAW = 0

# USB constants for HID
USB_HID_GET_REPORT = 0x01
USB_HID_SET_REPORT = 0x09
USB_HID_INPUT_REPORT = 0x0100
USB_HID_OUTPUT_REPORT = 0x0200

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

    use_constants - Indicates whether to use calibration constants when
    decoding pressure and temperature.  For consoles that use the HP03 sensor,
    use the constants reported  by the sensor.  Otherwise, use a linear
    approximation to derive pressure and temperature values from the sensor
    readings.
    [Optional.  Default is True]

    ignore_bounds - Indicates how to treat calibration constants from the
    pressure/temperature sensor.  Some consoles report constants that are
    outside the limits specified by the sensor manufacturer.  Typically this
    would indicate bogus data - perhaps a bad transmission or noisy USB.
    But in some cases, the apparently bogus constants actually work, and
    no amount of power cycling or resetting of the console changes the values
    that the console emits.  Use this flag to indicate that this is one of
    those quirky consoles.
    [Optional.  Default is False]
    """
    _R1_INTERVAL = 18    # 5-in-1 sensor updates every 18 seconds
    _R2_INTERVAL = 60    # console sensor updates every 60 seconds
    _R3_INTERVAL = 12*60 # historical records updated every 12 minutes

    def __init__(self, **stn_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        self.model = stn_dict.get('model', 'AcuRite')
        self.max_tries = int(stn_dict.get('max_tries', 10))
        self.retry_wait = int(stn_dict.get('retry_wait', 30))
        self.polling_interval = int(stn_dict.get('polling_interval', 6))
        self.use_constants = to_bool(stn_dict.get('use_constants', True))
        self.ignore_bounds = to_bool(stn_dict.get('ignore_bounds', False))
        if self.use_constants:
            loginf('R2 will be decoded using sensor constants')
            if self.ignore_bounds:
                loginf('R2 bounds on constants will be ignored')
        self.enable_r3 = int(stn_dict.get('enable_r3', 0))
        if self.enable_r3:
            loginf('R3 data will be attempted')
        self.last_rain = None
        self.last_r3 = None
        self.r3_fail_count = 0
        self.r3_max_fail = 3
        self.r1_next_read = 0
        self.r2_next_read = 0
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
                packet = {'dateTime': int(time.time() + 0.5),
                          'usUnits': weewx.METRIC}
                raw1 = raw2 = None
                with Station() as station:
                    if time.time() >= self.r1_next_read:
                        raw1 = station.read_R1()
                        self.r1_next_read = time.time() + self._R1_INTERVAL
                        if DEBUG_RAW > 0 and raw1:
                            logdbg("R1: %s" % _fmt_bytes(raw1))
                    if time.time() >= self.r2_next_read:
                        raw2 = station.read_R2()
                        self.r2_next_read = time.time() + self._R2_INTERVAL
                        if DEBUG_RAW > 0 and raw2:
                            logdbg("R2: %s" % _fmt_bytes(raw2))
                    if self.enable_r3:
                        raw3 = self.read_R3_block(station)
                        if DEBUG_RAW > 0 and raw3:
                            for row in raw3:
                                logdbg("R3: %s" % _fmt_bytes(row))
                if raw1:
                    packet.update(Station.decode_R1(raw1))
                if raw2:
                    Station.check_pt_constants(last_raw2, raw2)
                    last_raw2 = raw2
                    packet.update(Station.decode_R2(
                            raw2, self.use_constants, self.ignore_bounds))
                self._augment_packet(packet)
                ntries = 0
                yield packet
                next_read = min(self.r1_next_read, self.r2_next_read)
                delay = max(int(next_read - time.time() + 1),
                            self.polling_interval)
                logdbg("next read in %s seconds" % delay)
                time.sleep(delay)
            except (usb.USBError, weewx.WeeWxIOError), e:
                logerr("Failed attempt %d of %d to get LOOP data: %s" %
                       (ntries, self.max_tries, e))
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for LOOP data" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    def _augment_packet(self, packet):
        # calculate the rain delta from the total
        if 'rain_total' in packet:
            total = packet['rain_total']
            if (total is not None and self.last_rain is not None and
                total < self.last_rain):
                loginf("rain counter decrement ignored:"
                       " new: %s old: %s" % (total, self.last_rain))
            packet['rain'] = weewx.wxformulas.calculate_rain(total, self.last_rain)
            self.last_rain = total

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

    def read_R3_block(self, station):
        # attempt to read R3 every 12 minutes.  if the read fails multiple
        # times, make a single log message about enabling usb mode 3 then do
        # not try it again.
        #
        # when the station is not in mode 3, attempts to read R3 leave
        # it in an uncommunicative state.  doing a reset, close, then open
        # will sometimes, but not always, get communication started again on
        # 01036 stations.
        r3 = []
        if self.r3_fail_count >= self.r3_max_fail:
            return r3
        if (self.last_r3 is None or
            time.time() - self.last_r3 > self._R3_INTERVAL):
            try:
                x = station.read_x()
                for i in range(17):
                    r3.append(station.read_R3())
                self.last_r3 = time.time()
            except usb.USBError, e:
                self.r3_fail_count += 1
                logdbg("R3: read failed %d of %d: %s" %
                       (self.r3_fail_count, self.r3_max_fail, e))
                if self.r3_fail_count >= self.r3_max_fail:
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

    def __init__(self, vend_id=VENDOR_ID, prod_id=PRODUCT_ID, dev_id=None):
        self.vendor_id = vend_id
        self.product_id = prod_id
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

#        self.handle.reset()

        # the station shows up as a HID with only one interface
        interface = 0

        # for linux systems, be sure kernel does not claim the interface 
        try:
            self.handle.detachKernelDriver(interface)
        except (AttributeError, usb.USBError):
            pass

        # FIXME: is it necessary to set the configuration?
        try:
            self.handle.setConfiguration(dev.configurations[0])
        except (AttributeError, usb.USBError), e:
            pass

        # attempt to claim the interface
        try:
            self.handle.claimInterface(interface)
        except usb.USBError, e:
            self.close()
            logcrt("Unable to claim USB interface %s: %s" % (interface, e))
            raise weewx.WeeWxIOError(e)

        # FIXME: is it necessary to set the alt interface?
        try:
            self.handle.setAltInterface(interface)
        except (AttributeError, usb.USBError), e:
            pass

    def close(self):
        if self.handle is not None:
            try:
                self.handle.releaseInterface()
            except (ValueError, usb.USBError), e:
                logerr("release interface failed: %s" % e)
            self.handle = None

    def reset(self):
        self.handle.reset()

    def read(self, report_number, nbytes):
        return self.handle.controlMsg(
            requestType=usb.RECIP_INTERFACE + usb.TYPE_CLASS + usb.ENDPOINT_IN,
            request=USB_HID_GET_REPORT,
            buffer=nbytes,
            value=USB_HID_INPUT_REPORT + report_number,
            index=0x0,
            timeout=self.timeout)

    def read_R1(self):
        return self.read(1, 10)

    def read_R2(self):
        return self.read(2, 25)

    def read_R3(self):
        return self.read(3, 33)

    def read_x(self):
        # FIXME: what do the two bytes mean?
        return self.handle.controlMsg(
            requestType=usb.RECIP_INTERFACE + usb.TYPE_CLASS,
            request=USB_HID_SET_REPORT,
            buffer=2,
            value=USB_HID_OUTPUT_REPORT + 0x01,
            index=0x0,
            timeout=self.timeout)

    @staticmethod
    def decode_R1(raw):
        data = dict()
        if len(raw) == 10 and raw[0] == 0x01:
            if Station.check_R1(raw):
                data['channel'] = Station.decode_channel(raw)
                data['sensor_id'] = Station.decode_sensor_id(raw)
                data['rssi'] = Station.decode_rssi(raw)
                if data['rssi'] == 0:
                    data['sensor_battery'] = None
                    loginf("R1: ignoring stale data (rssi indicates no communication from sensors): %s" % _fmt_bytes(raw))
                else:
                    data['sensor_battery'] = Station.decode_sensor_battery(raw)
                    data['windSpeed'] = Station.decode_windspeed(raw)
                    if raw[3] & 0x0f == 1:
                        data['windDir'] = Station.decode_winddir(raw)
                        data['rain_total'] = Station.decode_rain(raw)
                    else:
                        data['outTemp'] = Station.decode_outtemp(raw)
                        data['outHumidity'] = Station.decode_outhumid(raw)
            else:
                data['channel'] = None
                data['sensor_id'] = None
                data['rssi'] = None
                data['sensor_battery'] = None
        elif len(raw) != 10:
            logerr("R1: bad length: %s" % _fmt_bytes(raw))
        else:
            logerr("R1: bad format: %s" % _fmt_bytes(raw))
        return data

    @staticmethod
    def check_R1(raw):
        ok = True
        if raw[1] & 0x0f == 0x0f and raw[3] == 0xff:
            loginf("R1: no sensors found: %s" % _fmt_bytes(raw))
            ok = False
        else:
            if raw[3] & 0x0f != 1 and raw[3] & 0x0f != 8:
                loginf("R1: bogus message flavor (%02x): %s" % (raw[3], _fmt_bytes(raw)))
                ok = False
            if raw[9] != 0xff and raw[9] != 0x00:
                loginf("R1: bogus final byte (%02x): %s" % (raw[9], _fmt_bytes(raw)))
                ok = False
            if raw[8] & 0x0f < 0 or raw[8] & 0x0f > 3:
                loginf("R1: bogus signal strength (%02x): %s" % (raw[8], _fmt_bytes(raw)))
                ok = False
        return ok

    @staticmethod
    def decode_R2(raw, use_constants=True, ignore_bounds=False):
        data = dict()
        if len(raw) == 25 and raw[0] == 0x02:
            data['pressure'], data['inTemp'] = Station.decode_pt(
                raw, use_constants, ignore_bounds)
        elif len(raw) != 25:
            logerr("R2: bad length: %s" % _fmt_bytes(raw))
        else:
            logerr("R2: bad format: %s" % _fmt_bytes(raw))
        return data

    @staticmethod
    def decode_R3(raw):
        data = dict()
        buf = []
        fail = False
        for i, r in enumerate(raw):
            if len(r) == 33 and r[0] == 0x03:
                try:
                    for b in r:
                        buf.append(int(b, 16))
                except ValueError, e:
                    logerr("R3: bad value in row %d: %s" % (i, _fmt_bytes(r)))
                    fail = True
            elif len(r) != 33:
                logerr("R3: bad length in row %d: %s" % (i, _fmt_bytes(r)))
                fail = True
            else:
                logerr("R3: bad format in row %d: %s" % (i, _fmt_bytes(r)))
                fail = True
        if fail:
            return data
        for i in range(2, len(buf)-2):
            if buf[i-2] == 0xff and buf[i-1] == 0xaa and buf[i] == 0x55:
                data['numrec'] = buf[i+1] + buf[i+2] * 0x100
                break
        data['raw'] = raw
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
        # according to nincehelser, this is a measure of the number of failed
        # sensor queries, not the actual RF signal strength
        return data[8] & 0x0f

    @staticmethod
    def decode_sensor_battery(data):
        # 0x7 indicates battery ok, 0xb indicates low battery?
        a = (data[3] & 0xf0) >> 4
        return 0 if a == 0x7 else 1

    @staticmethod
    def decode_windspeed(data):
        # extract the wind speed from an R1 message
        # return value is kph
        # for details see http://www.wxforum.net/index.php?topic=27244.0
        # minimum measurable speed is 1.83 kph
        n = ((data[4] & 0x1f) << 3) | ((data[5] & 0x70) >> 4)
        if n == 0:
            return 0.0
        return 0.8278 * n + 1.0

    @staticmethod
    def decode_winddir(data):
        # extract the wind direction from an R1 message
        # decoded value is one of 16 points, convert to degrees
        v = data[5] & 0x0f
        return Station.IDX_TO_DEG.get(v)

    @staticmethod
    def decode_outtemp(data):
        # extract the temperature from an R1 message
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
        return (((data[6] & 0x3f) << 7) | (data[7] & 0x7f)) * 0.0254

    @staticmethod
    def decode_pt(data, use_constants=True, ignore_bounds=False):
        # decode pressure and temperature from the R2 message
        # decoded pressure is mbar, decoded temperature is degree C
        c1,c2,c3,c4,c5,c6,c7,a,b,c,d = Station.get_pt_constants(data)

        if not use_constants:
            # use a linear approximation for pressure and temperature
            d2 = ((data[21] & 0x0f) << 8) + data[22]
            if d2 >= 0x0800:
                d2 -= 0x1000
            d1 = (data[23] << 8) + data[24]
            return Station.decode_pt_acurite(d1, d2)
        elif (c1 == 0x8000 and c2 == c3 == 0x0 and c4 == 0x0400
              and c5 == 0x1000 and c6 == 0x0 and c7 == 0x0960
              and a == b == c == d == 0x1):
            # this is a MS5607 sensor, typical in 02032 consoles
            d2 = ((data[21] & 0x0f) << 8) + data[22]
            if d2 >= 0x0800:
                d2 -= 0x1000
            d1 = (data[23] << 8) + data[24]
            return Station.decode_pt_MS5607(d1, d2)
        elif (0x100 <= c1 <= 0xffff and
              0x0 <= c2 <= 0x1fff and
              0x0 <= c3 <= 0x400 and
              0x0 <= c4 <= 0x1000 and
              0x1000 <= c5 <= 0xffff and
              0x0 <= c6 <= 0x4000 and
              0x960 <= c7 <= 0xa28 and
              (0x01 <= a <= 0x3f and 0x01 <= b <= 0x3f and
               0x01 <= c <= 0x0f and 0x01 <= d <= 0x0f) or ignore_bounds):
            # this is a HP038 sensor.  some consoles return values outside the
            # specified limits, but their data still seem to be ok.  if the
            # ignore_bounds flag is set, then permit values for A, B, C, or D
            # that are out of bounds, but enforce constraints on the other
            # constants C1-C7.
            d2 = (data[21] << 8) + data[22]
            d1 = (data[23] << 8) + data[24]
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
        return Station.decode_pt_acurite(d1, d2)

    @staticmethod
    def decode_pt_acurite(d1, d2):
        # apparently the new (2015) acurite software uses this function, which
        # is quite close to andrew daviel's reverse engineered function of:
        #    p = 0.062585727 * d1 - 209.6211
        #    t = 25.0 + 0.05 * d2
        p = d1 / 16.0 - 208
        t = 25.0 + 0.05 * d2
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

    test_r1 = True
    test_r2 = True
    test_r3 = False
    delay = 12*60
    with Station() as s:
        while True:
            ts = int(time.time())
            tstr = "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S %Z",
                                              time.localtime(ts)), ts)
            if test_r1:
                r1 = s.read_R1()
                print tstr, _fmt_bytes(r1), Station.decode_R1(r1)
                delay = min(delay, 18)
            if test_r2:
                r2 = s.read_R2()
                print tstr, _fmt_bytes(r2), Station.decode_R2(r2)
                delay = min(delay, 60)
            if test_r3:
                try:
                    x = s.read_x()
                    print tstr, _fmt_bytes(x)
                    for i in range(0, 17):
                        r3 = s.read_R3()
                        print tstr, _fmt_bytes(r3)
                except usb.USBError, e:
                    print tstr, e
                delay = min(delay, 12*60)
            time.sleep(delay)
