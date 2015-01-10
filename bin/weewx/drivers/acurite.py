#!/usr/bin/env python
# $Id$
# Copyright 2014 Matthew Wall
# See the file LICENSE.txt for your full rights.
#
# Credits:
# Thanks to dave of 'desert home'
#  http://www.desert-home.com/2014/11/acurite-weather-station-raspberry-pi.html
#
# Slow-clap thanks to Michael Walsh
#  http://forum1.valleyinfosys.com/index.php
#
# No thanks to AcuRite or Chaney instruments.  They refused to provide any
# technical details for the development of this driver.

"""Driver for AcuRite weather stations.

There are many variants of the AcuRite weather stations and sensors.  This
driver is known to work with the consoles that have a USB interface such as
models 01025 and 01035.  It should also work with the (low end?) variant
with model number 02032C.

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

The memory size is 512 KB (not expandable).

According to AcuRite specs, the update frequencies are as follows:

  wind speed: 18 second updates
  wind direction: 30 second updates
  outdoor temperature and humidity: 60 second updates
  pc connect csv data logging: 12 minute intervals
  pc connect to acurite software: 18 second updates

There is a lot of monkey business with respect to the pressure.  The pressure
sensor in the console reports a station pressure, but the firmware does some
kind of averaging to it so the console displays a pressure that is usually
nothing close to the station pressure.

According to AcuRite they use a 'patented, self-adjusting altitude pressure
compensation' algorithm.

  corrected_reading = 29.92 * current_reading / average_reading

  current_reading - absolute sensor reading
  average_reading - arithmetic mean of the absolute sensor reading

They do not specify whether the average is computed from a number of samples
or over a specific time period.

The AcuRite station has 4 USB modes:

      show data   store data   stream data
  1   x           x
  2   x           
  3   x           x            x
  4   x                        x

The console does not respond to USB requests when in mode 1 or mode 2.

The console shows up as a USB device even if it is turned off.  If the console
is powered on then communication starts, then power is removed, communication
will continue.  So the console appears to draw some power from the bus.

Apparently some stations have issues when the history buffer fills up.

Some reports say that the station stops recording data.  Some reports say that
the 02032 (and possibly other stations) should not use history mode at all
because the data are written to flash memory, which wears out, sometimes
quickly.  Some reports say this 'bricks' the station, however those appear
to be a mis-use of 'brick', because the station still works and communication
can sometimes be re-established.

The AcuRite station emits three different data strings, R1, R2 and R3.  The R1
string is 10 bytes long, contains readings from the remote sensors, and comes
in different flavors.  One contains wind speed, wind direction, and rain
counter.  Another contains wind speed, temperature, and humidity.  The R2
string is 25 bytes long and appears to contain readings from the console
sensors.  The R3 string contains historical data and (apparently) the humidity
readings from the console sensors.

Message Maps

R1 - 10 bytes
 0  1  2  3  4  5  6  7  8  9
01 CF FF FF FF FF FF FF 00 00
01 8b fa 78 00 08 48 25 03 ff
01 8b fa 71 00 06 00 02 03 ff

0: identifier, 01 for R1 messages
1: ?sensor_id
2: ?sensor_id
3: message flavor, 1 (windSpeed, windDir, rain) or 8 (windSpeed, temp, humid)
4: wind speed  (x & 0x1f) << 3
5: wind speed  (x & 0x70) >> 4
5: wind dir    (x & 0x0f)
5: temp        (x & 0x0f) << 7
6: temp        (x & 0x7f)
7: rain        (x & 0x7f)
8: ?signal strength (x & 0x0f)    observed values: 0,1,2,3
9: ?battery level   (x & 0xff)    observed values: 0x00 and 0xff

R2 - 25 bytes
 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
02 00 00 4C BE 0D EC 01 52 03 62 7E 38 18 EE 09 C4 08 22 06 07 7B A4 8A 46

R3 - 594 bytes?


Sample Messages

01 CF FF FF FF FF FF FF 00 00
no connection to sensor unit

02 00 00 4C BE 0D EC 01 52 03 62 7E 38 18 EE 09 C4 08 22 06 07 7B A4 8A 46
25.087inhg 849.5hpa 12.321psi 66.1F 19.0C -
67F 28% 30.18

02 00 00 4C BE 0D EC 01 52 03 62 7E 38 18 EE 09 C4 08 22 06 07 7B 54 8A 74
25.090inhg 849.6hpa 12.323psi 64.8F 18.2C -
66F 29% 30.18

"""

# FIXME: how to set mode via software?
# FIXME: how to download stored data?
# FIXME: can the archive interval be changed?
# FIXME: how to clear station memory?
# FIXME: how to detect console type?

# FIXME: decode console battery level
# FIXME: decode channel identifier (A,B,C)
# FIXME: heatindex, windchill, ?, rain rate, peak wind, avg wind

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers

DRIVER_NAME = 'AcuRite'
DRIVER_VERSION = '0.1'


def loader(config_dict, engine):
    return AcuRite(**config_dict[DRIVER_NAME])

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


class AcuRite(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with an AcuRite weather station.

    model: Which station model is this?
    [Optional. Default is '01035']

    max_tries - how often to retry communication before giving up
    [Optional. Default is 5]
    """
    def __init__(self, **stn_dict):
        self.model = stn_dict.get('model', '01035')
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 10))
        self.polling_interval = int(stn_dict.get('polling_interval', 18))
        self.last_rain = None
        loginf('driver version is %s' % DRIVER_VERSION)

    def genLoopPackets(self):
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                packet = {'dateTime': int(time.time() + 0.5),
                          'usUnits': weewx.US}
                with Station() as station:
                    raw = station.read_R1()
                    data = Station.decode(raw)
                    packet.update(data)
                    raw = station.read_R2()
                    data = Station.decode(raw)
                    packet.update(data)
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

    @property
    def hardware_name(self):
        return self.model

    def _augment_packet(self, packet):
        if 'rain_total' in packet:
            if self.last_rain is not None:
                packet['rain'] = packet['rain_total'] - self.last_rain
            else:
                packet['rain'] = None
            self.last_rain = packet['rain_total']


class Station(object):
    IDX_TO_DEG = {6: 0.0, 14: 22.5, 12: 45.0, 8: 67.5, 10: 90.0, 11: 112.5,
                  9: 135.0, 13: 157.5, 15: 180.0, 7: 202.5, 5: 225.0, 1: 247.5,
                  3: 270.0, 2: 292.5, 0: 315.0, 4: 337.5}
    VENDOR_ID = 0x24c0
    PRODUCT_ID = 0x0003

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
        interface = 0
        dev = self._find_dev(self.vendor_id, self.product_id, self.device_id)
        if not dev:
            logcrt("Cannot find USB device with "
                   "VendorID=0x%04x ProductID=0x%04x DeviceID=%s" %
                   (self.vendor_id, self.product_id, self.device_id))
            raise weewx.WeeWxIOError('Unable to find station on USB')

        self.handle = dev.open()
        if not self.handle:
            raise weewx.WeeWxIOError('Open USB device failed')

        loginf('mfr: %s' % self.handle.getString(dev.iManufacturer,30))
        loginf('product: %s' % self.handle.getString(dev.iProduct,30))
        loginf('interface: %d' % interface)

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

#        self.set_idle()

    def close(self):
        if self.handle is not None:
            try:
                self.handle.releaseInterface()
            except Exception, e:
                logerr("release failed: %s" % e)
            self.handle = None

    def set_idle(self):
        ret = self.handle.controlMsg(requestType=(usb.RECIP_INTERFACE +
                                                  usb.TYPE_CLASS),
                                     request=(usb.RECIP_INTERFACE +
                                              usb.REQ_CLEAR_FEATURE),
                                     buffer=0x0,
                                     value=0x0,
                                     index=0x0,
                                     timeout=self.timeout)

    def read(self, msgtype, nbytes):
        ret = self.handle.controlMsg(requestType=(usb.RECIP_INTERFACE +
                                                  usb.TYPE_CLASS +
                                                  usb.ENDPOINT_IN),
                                     request=usb.REQ_CLEAR_FEATURE,
                                     buffer=nbytes,
                                     value=0x0100 + msgtype,
                                     index=0x0,
                                     timeout=self.timeout)
        return [x for x in ret]

    def read_R1(self):
        return self.read(1, 10)

    def read_R2(self):
        return self.read(2, 25)

    def read_R3(self):
        return self.read(3, 594)

    @staticmethod
    def decode(raw):
        data = dict()
        if len(raw) == 10:
            data['signal'] = Station.decode_signal(raw)
            data['sensor_battery'] = Station.decode_sensor_battery(raw)
            if raw[3] & 0x0f == 1 or raw[3] & 0x0f == 8:
                data['windSpeed'] = Station.decode_windspeed(raw)
                if raw[3] & 0x0f == 1:
                    data['windDir'] = Station.decode_winddir(raw)
                    data['rain_total'] = Station.decode_rain(raw)
                else:
                    data['outTemp'] = Station.decode_outtemp(raw)
                    data['outHumidity'] = Station.decode_outhumid(raw)
            elif raw[3] == 0xff and raw[2] == 0xcf:
                loginf("no sensor cluster found")
            else:
                logerr("R1: unexpected byte %02x" % raw[3])
                logerr(' '.join(['%02x' % x for x in raw]))
        elif len(raw) == 25:
            data['pressure'] = Station.decode_pressure(raw)
            data['inTemp'] = Station.decode_intemp(raw)
            data['inHumidity'] = Station.decode_inhumid(raw)
        else:
            logerr("unknown data string with length %d" % len(raw))
        return data

    @staticmethod
    def decode_signal(data):
        # signal strength goes from 0 to 3, inclusive
        return data[8] & 0x0f

    @staticmethod
    def decode_sensor_battery(data):
        # battery level is 0xff or 0x00
        # return the weewx convention of 0 for ok, 1 for fail
        # FIXME: need to verify this
        return 0 if data[9] & 0xff else 1

    @staticmethod
    def decode_windspeed(data):
        # extract the wind speed from an R1 message
        # decoded value is mph, convert to kph
        lhs = (data[4] & 0x1f) << 3
        rhs = (data[5] & 0x70) >> 4
        return 0.5 * (lhs | rhs)

    @staticmethod
    def decode_winddir(data):
        # extract the wind direction from an R1 message
        # decoded value is one of 16 points, convert to degrees
        v = data[5] & 0x0f
        deg = Station.IDX_TO_DEG.get(v)
        return deg if deg is not None else None

    @staticmethod
    def decode_outtemp(data):
        # extract the temperature from an R1 message
        # decoded value is degree C
        lhs = (data[5] & 0x0f) << 7
        rhs = data[6] & 0x7f
        combined = lhs | rhs
        return (combined - 400) / 10.0

    @staticmethod
    def decode_outhumid(data):
        # extract the humidity from an R1 message
        # decoded value is percentage
        return data[7] & 0x7f

    @staticmethod
    def decode_rain(data):
        # decoded value is a count of bucket tips, each tip is 0.01 inch
        return (data[7] & 0x7f) * 0.01

    @staticmethod
    def decode_intemp(data):
        # FIXME: decode inside temperature
        return None

    @staticmethod
    def decode_inhumid(data):
        # FIXME: decode inside humidity
        return None

    @staticmethod
    def decode_pressure(data):
        # FIXME: decode pressure
        return None

    @staticmethod
    def _find_dev(vendor_id, product_id, device_id=None):
        """Find the vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    if device_id is None or dev.filename == device_id:
                        loginf('Found device at bus=%s device=%s' %
                               (bus.dirname, dev.filename))
                        return dev
        return None


class AcuRiteConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[AcuRite]
    # This section is for the AcuRite weather stations.

    # The station model, e.g., '01025', '01035', or '02032C'
    model = '01035'

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
            r1 = s.read_R1()
            r2 = s.read_R2()
#            r3 = s.read_R3()
            print tstr, ' '.join(['%02x' % x for x in r1]), Station.decode(r1)
            print tstr, ' '.join(['%02x' % x for x in r2]), Station.decode(r2)
#            print tstr, ' '.join(['%02x' % x for x in r3])
            time.sleep(18)
