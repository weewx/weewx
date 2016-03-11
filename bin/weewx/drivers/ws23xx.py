#!usr/bin/env python
#
# Copyright 2013 Matthew Wall
# See the file LICENSE.txt for your full rights.
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

The stations were also sold as the TFA Matrix and TechnoLine 2350.

The WWVB receiver is located in the console.

To synchronize the console and sensors, press and hold the PLUS key for 2
seconds.  When console is not synchronized no data will be received.

To do a factory reset, press and hold PRESSURE and WIND for 5 seconds.

A single bucket tip is 0.0204 in (0.518 mm).

The station has 175 history records.  That is just over 7 days of data with
the default history recording interval of 60 minutes.

The station supports both wireless and wired communication between the
sensors and a station console.  Wired connection updates data every 8 seconds.
Wireless connection updates data in 16 to 128 second intervals, depending on
wind speed and rain activity.

The connection type can be one of 0=cable, 3=lost, 15=wireless

sensor update frequency:

   32 seconds when wind speed > 22.36 mph (wireless)
  128 seconds when wind speed < 22.36 mph (wireless)
   10 minutes (wireless after 5 failed attempts)
    8 seconds (wired)

console update frequency:

  15 seconds (pressure/temperature)
  20 seconds (humidity)

It is possible to increase the rate of wireless updates:

  http://www.wxforum.net/index.php?topic=2196.0

Sensors are connected by unshielded phone cables.  RF interference can cause
random spikes in data, with one symptom being values of 25.5 m/s or 91.8 km/h
for the wind speed.  Unfortunately those values are within the sensor limits
of 0-113 mph (50.52 m/s or 181.9 km/h).  To reduce the number of spikes in
data, replace with shielded cables:

  http://www.lavrsen.dk/sources/weather/windmod.htm

The station records wind speed and direction, but has no notion of gust.

The station calculates windchill and dewpoint.

The station has a serial connection to the computer.

This driver does not keep the serial port open for long periods.  Instead, the
driver opens the serial port, reads data, then closes the port.

This driver polls the station.  Use the polling_interval parameter to specify
how often to poll for data.  If not specified, the polling interval will adapt
based on connection type and status.

USB-Serial Converters

With a USB-serial converter one can connect the station to a computer with
only USB ports, but not every converter will work properly.  Perhaps the two
most common converters are based on the Prolific and FTDI chipsets.  Many
people report better luck with the FTDI-based converters.  Some converters
that use the Prolific chipset (PL2303) will work, but not all of them.

Known to work: ATEN UC-232A

Bounds checking

 wind speed: 0-113 mph
 wind direction: 0-360
 humidity: 0-100
 temperature: ok if not -22F and humidity is valid
 dewpoint: ok if not -22F and humidity is valid
 barometer: 25-35 inHg
 rain rate: 0-10 in/hr

Discrepancies Between Implementations

As of December 2013, there are significant differences between the open2300,
wview, and ws2300 implementations.  Current version numbers are as follows:

  open2300 1.11
  ws2300 1.8
  wview 5.20.2

History Interval

The factory default is 60 minutes.  The value stored in the console is one
less than the actual value (in minutes).  So for the factory default of 60,
the console stores 59.  The minimum interval is 1.

ws2300.py reports the actual value from the console, e.g., 59 when the
interval is 60.  open2300 reports the interval, e.g., 60 when the interval
is 60.  wview ignores the interval.

Detecting Bogus Sensor Values

wview queries the station 3 times for each sensor then accepts the value only
if the three values were close to each other.

open2300 sleeps 10 seconds if a wind measurement indicates invalid or overflow.

The ws2300.py implementation includes overflow and validity flags for values
from the wind sensors.  It does not retry based on invalid or overflow.

Wind Speed

There is disagreement about how to calculate wind speed and how to determine
whether the wind speed is valid.

This driver introduces a WindConversion object that uses open2300/wview
decoding so that wind speeds match that of open2300/wview.  ws2300 1.8
incorrectly uses bcd2num instead of bin2num.  This bug is fixed in this driver.

The memory map indicates the following:

addr  smpl description
0x527 0    Wind overflow flag: 0 = normal
0x528 0    Wind minimum code: 0=min, 1=--.-, 2=OFL
0x529 0    Windspeed: binary nibble 0 [m/s * 10]
0x52A 0    Windspeed: binary nibble 1 [m/s * 10]
0x52B 0    Windspeed: binary nibble 2 [m/s * 10]
0x52C 8    Wind Direction = nibble * 22.5 degrees
0x52D 8    Wind Direction 1 measurement ago
0x52E 9    Wind Direction 2 measurement ago
0x52F 8    Wind Direction 3 measurement ago
0x530 7    Wind Direction 4 measurement ago
0x531 7    Wind Direction 5 measurement ago
0x532 0

wview 5.20.2 implementation (wview apparently copied from open2300):

read 3 bytes starting at 0x527

0x527 x[0]
0x528 x[1]
0x529 x[2]

if ((x[0] != 0x00) ||
    ((x[1] == 0xff) && (((x[2] & 0xf) == 0) || ((x[2] & 0xf) == 1)))) {
  fail
} else {
  dir = (x[2] >> 4) * 22.5
  speed = ((((x[2] & 0xf) << 8) + (x[1])) / 10.0 * 2.23693629)
  maxdir = dir
  maxspeed = speed
}

open2300 1.10 implementation:

read 6 bytes starting at 0x527

0x527 x[0]
0x528 x[1]
0x529 x[2]
0x52a x[3]
0x52b x[4]
0x52c x[5]

if ((x[0] != 0x00) ||
    ((x[1] == 0xff) && (((x[2] & 0xf) == 0) || ((x[2] & 0xf) == 1)))) {
  sleep 10
} else {
  dir = x[2] >> 4
  speed = ((((x[2] & 0xf) << 8) + (x[1])) / 10.0)
  dir0 = (x[2] >> 4) * 22.5
  dir1 = (x[3] & 0xf) * 22.5
  dir2 = (x[3] >> 4) * 22.5
  dir3 = (x[4] & 0xf) * 22.5
  dir4 = (x[4] >> 4) * 22.5
  dir5 = (x[5] & 0xf) * 22.5
}

ws2300.py 1.8 implementation:

read 1 nibble starting at 0x527
read 1 nibble starting at 0x528
read 4 nibble starting at 0x529
read 3 nibble starting at 0x529
read 1 nibble starting at 0x52c
read 1 nibble starting at 0x52d
read 1 nibble starting at 0x52e
read 1 nibble starting at 0x52f
read 1 nibble starting at 0x530
read 1 nibble starting at 0x531

0x527 overflow
0x528 validity
0x529 speed[0]
0x52a speed[1]
0x52b speed[2]
0x52c dir[0]

speed:    ((x[2] * 100 + x[1] * 10 + x[0]) % 1000) / 10
velocity:  (x[2] * 100 + x[1] * 10 + x[0]) / 10

dir = data[0] * 22.5
speed = (bcd2num(data) % 10**3 + 0) / 10**1
velocity = (bcd2num(data[:3])/10.0, bin2num(data[3:4]) * 22.5)

bcd2num([a,b,c]) -> c*100+b*10+a

"""

# TODO: use pyserial instead of LinuxSerialPort
# TODO: put the __enter__ and __exit__ scaffolding on serial port, not Station
# FIXME: unless we can get setTime to work, just ignore the console clock
# FIXME: detect bogus wind speed/direction
# i see these when the wind instrument is disconnected:
# ws 26.399999
# wsh 21
# w0 135

from __future__ import with_statement
import syslog
import time
import string

import fcntl
import os
import select
import struct
import termios
import tty

import weeutil.weeutil
import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'WS23xx'
DRIVER_VERSION = '0.24'


def loader(config_dict, _):
    return WS23xxDriver(config_dict=config_dict, **config_dict[DRIVER_NAME])

def configurator_loader(_):
    return WS23xxConfigurator()

def confeditor_loader():
    return WS23xxConfEditor()


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


class WS23xxConfigurator(weewx.drivers.AbstractConfigurator):
    def add_options(self, parser):
        super(WS23xxConfigurator, self).add_options(parser)
        parser.add_option("--info", dest="info", action="store_true",
                          help="display weather station configuration")
        parser.add_option("--current", dest="current", action="store_true",
                          help="get the current weather conditions")
        parser.add_option("--history", dest="nrecords", type=int, metavar="N",
                          help="display N history records")
        parser.add_option("--history-since", dest="recmin",
                          type=int, metavar="N",
                          help="display history records since N minutes ago")
        parser.add_option("--clear-memory", dest="clear", action="store_true",
                          help="clear station memory")
        parser.add_option("--set-time", dest="settime", action="store_true",
                          help="set the station clock to the current time")
        parser.add_option("--set-interval", dest="interval",
                          type=int, metavar="N",
                          help="set the station archive interval to N minutes")

    def do_options(self, options, parser, config_dict, prompt):
        self.station = WS23xxDriver(**config_dict[DRIVER_NAME])
        if options.current:
            self.show_current()
        elif options.nrecords is not None:
            self.show_history(count=options.nrecords)
        elif options.recmin is not None:
            ts = int(time.time()) - options.recmin * 60
            self.show_history(ts=ts)
        elif options.settime:
            self.set_clock(prompt)
        elif options.interval is not None:
            self.set_interval(options.interval, prompt)
        elif options.clear:
            self.clear_history(prompt)
        else:
            self.show_info()
        self.station.closePort()

    def show_info(self):
        """Query the station then display the settings."""
        print 'Querying the station for the configuration...'
        config = self.station.getConfig()
        for key in sorted(config):
            print '%s: %s' % (key, config[key])

    def show_current(self):
        """Get current weather observation."""
        print 'Querying the station for current weather data...'
        for packet in self.station.genLoopPackets():
            print packet
            break

    def show_history(self, ts=None, count=0):
        """Show the indicated number of records or records since timestamp"""
        print "Querying the station for historical records..."
        for i, r in enumerate(self.station.genStartupRecords(since_ts=ts,
                                                             count=count)):
            print r
            if count and i > count:
                break

    def set_clock(self, prompt):
        """Set station clock to current time."""
        ans = None
        while ans not in ['y', 'n']:
            v = self.station.getTime()
            vstr = weeutil.weeutil.timestamp_to_string(v)
            print "Station clock is", vstr
            if prompt:
                ans = raw_input("Set station clock (y/n)? ")
            else:
                print "Setting station clock"
                ans = 'y'
            if ans == 'y':
                self.station.setTime()
                v = self.station.getTime()
                vstr = weeutil.weeutil.timestamp_to_string(v)
                print "Station clock is now", vstr
            elif ans == 'n':
                print "Set clock cancelled."

    def set_interval(self, interval, prompt):
        print "Changing the interval will clear the station memory."
        v = self.station.getArchiveInterval()
        ans = None
        while ans not in ['y', 'n']:
            print "Interval is", v
            if prompt:
                ans = raw_input("Set interval to %d minutes (y/n)? " % interval)
            else:
                print "Setting interval to %d minutes" % interval
                ans = 'y'
            if ans == 'y':
                self.station.setArchiveInterval(interval)
                v = self.station.getArchiveInterval()
                print "Interval is now", v
            elif ans == 'n':
                print "Set interval cancelled."

    def clear_history(self, prompt):
        ans = None
        while ans not in ['y', 'n']:
            v = self.station.getRecordCount()
            print "Records in memory:", v
            if prompt:
                ans = raw_input("Clear console memory (y/n)? ")
            else:
                print 'Clearing console memory'
                ans = 'y'
            if ans == 'y':
                self.station.clearHistory()
                v = self.station.getRecordCount()
                print "Records in memory:", v
            elif ans == 'n':
                print "Clear memory cancelled."


class WS23xxDriver(weewx.drivers.AbstractDevice):
    """Driver for LaCrosse WS23xx stations."""
    
    def __init__(self, **stn_dict):
        """Initialize the station object.

        port: The serial port, e.g., /dev/ttyS0 or /dev/ttyUSB0
        [Required. Default is /dev/ttyS0]

        polling_interval: How often to poll the station, in seconds.
        [Optional. Default is 8 (wired) or 30 (wireless)]

        model: Which station model is this?
        [Optional. Default is 'LaCrosse WS23xx']
        """
        self._last_rain = None
        self._last_cn = None
        self._poll_wait = 60

        self.model = stn_dict.get('model', 'LaCrosse WS23xx')
        self.port = stn_dict.get('port', DEFAULT_PORT)
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 30))
        self.polling_interval = stn_dict.get('polling_interval', None)
        if self.polling_interval is not None:
            self.polling_interval = int(self.polling_interval)
        self.enable_startup_records = stn_dict.get('enable_startup_records',
                                                   True)
        self.enable_archive_records = stn_dict.get('enable_archive_records',
                                                   True)
        self.mode = stn_dict.get('mode', 'single_open')

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('serial port is %s' % self.port)
        loginf('polling interval is %s' % self.polling_interval)

        if self.mode == 'single_open':
            self.station = WS23xx(self.port)
        else:
            self.station = None

    def closePort(self):
        if self.station is not None:
            self.station.close()
            self.station = None

    @property
    def hardware_name(self):
        return self.model

    # weewx wants the archive interval in seconds, but the console uses minutes
    @property
    def archive_interval(self):
        if not self.enable_startup_records and not self.enable_archive_records:
            raise NotImplementedError            
        return self.getArchiveInterval() * 60

    def genLoopPackets(self):
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                if self.station:
                    data = self.station.get_raw_data(SENSOR_IDS)
                else:
                    with WS23xx(self.port) as s:
                        data = s.get_raw_data(SENSOR_IDS)
                packet = data_to_packet(data, int(time.time() + 0.5),
                                        last_rain=self._last_rain)
                self._last_rain = packet['rainTotal']
                ntries = 0
                yield packet

                if self.polling_interval is not None:
                    self._poll_wait = self.polling_interval
                if data['cn'] != self._last_cn:
                    conn_info = get_conn_info(data['cn'])
                    loginf("connection changed from %s to %s" %
                           (get_conn_info(self._last_cn)[0], conn_info[0]))
                    self._last_cn = data['cn']
                    if self.polling_interval is None:
                        loginf("using %s second polling interval"
                               " for %s connection" % 
                               (conn_info[1], conn_info[0]))
                        self._poll_wait = conn_info[1]
                time.sleep(self._poll_wait)
            except Ws2300.Ws2300Exception, e:
                logerr("Failed attempt %d of %d to get LOOP data: %s" %
                       (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for LOOP data" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    def genStartupRecords(self, since_ts):
        if not self.enable_startup_records:
            raise NotImplementedError
        if self.station:
            return self.genRecords(self.station, since_ts)
        else:
            with WS23xx(self.port) as s:
                return self.genRecords(s, since_ts)

    def genArchiveRecords(self, since_ts, count=0):
        if not self.enable_archive_records:
            raise NotImplementedError
        if self.station:
            return self.genRecords(self.station, since_ts, count)
        else:
            with WS23xx(self.port) as s:
                return self.genRecords(s, since_ts, count)

    def genRecords(self, s, since_ts, count=0):
        last_rain = None
        for ts, data in s.gen_records(since_ts=since_ts, count=count):
            record = data_to_packet(data, ts, last_rain=last_rain)
            record['interval'] = data['interval']
            last_rain = record['rainTotal']
            yield record

#    def getTime(self) :
#        with WS23xx(self.port) as s:
#            return s.get_time()

#    def setTime(self):
#        with WS23xx(self.port) as s:
#            s.set_time()

    def getArchiveInterval(self):
        if self.station:
            return self.station.get_archive_interval()
        else:
            with WS23xx(self.port) as s:
                return s.get_archive_interval()

    def setArchiveInterval(self, interval):
        if self.station:
            self.station.set_archive_interval(interval)
        else:
            with WS23xx(self.port) as s:
                s.set_archive_interval(interval)

    def getConfig(self):
        fdata = dict()
        if self.station:
            data = self.station.get_raw_data(Measure.IDS.keys())
        else:
            with WS23xx(self.port) as s:
                data = s.get_raw_data(Measure.IDS.keys())
        for key in data:
            fdata[Measure.IDS[key].name] = data[key]
        return fdata

    def getRecordCount(self):
        if self.station:
            return self.station.get_record_count()
        else:
            with WS23xx(self.port) as s:
                return s.get_record_count()

    def clearHistory(self):
        if self.station:
            self.station.clear_memory()
        else:
            with WS23xx(self.port) as s:
                s.clear_memory()


# ids for current weather conditions and connection type
SENSOR_IDS = ['it','ih','ot','oh','pa','wind','rh','rt','dp','wc','cn']
# polling interval, in seconds, for various connection types
POLLING_INTERVAL = {0: ("cable", 8), 3: ("lost", 60), 15: ("wireless", 30)}

def get_conn_info(conn_type):
    return POLLING_INTERVAL.get(conn_type, ("unknown", 60))

def data_to_packet(data, ts, last_rain=None):
    """Convert raw data to format and units required by weewx.

                    station      weewx (metric)
    temperature     degree C     degree C
    humidity        percent      percent
    uv index        unitless     unitless
    pressure        mbar         mbar
    wind speed      m/s          km/h
    wind dir        degree       degree
    wind gust       None
    wind gust dir   None
    rain            mm           cm
    rain rate                    cm/h
    """

    packet = dict()
    packet['usUnits'] = weewx.METRIC
    packet['dateTime'] = ts
    packet['inTemp'] = data['it']
    packet['inHumidity'] = data['ih']
    packet['outTemp'] = data['ot']
    packet['outHumidity'] = data['oh']
    packet['pressure'] = data['pa']

    ws, wd, wso, wsv = data['wind']
    if wso == 0 and wsv == 0:
        packet['windSpeed'] = ws
        if packet['windSpeed'] is not None:
            packet['windSpeed'] *= 3.6 # weewx wants km/h
        packet['windDir'] = wd if packet['windSpeed'] else None
    else:
        loginf('invalid wind reading: speed=%s dir=%s overflow=%s invalid=%s' %
               (ws, wd, wso, wsv))
        packet['windSpeed'] = None
        packet['windDir'] = None

    packet['windGust'] = None
    packet['windGustDir'] = None

    packet['rainTotal'] = data['rt']
    if packet['rainTotal'] is not None:
        packet['rainTotal'] /= 10 # weewx wants cm
    packet['rain'] = weewx.wxformulas.calculate_rain(
        packet['rainTotal'], last_rain)

    # station provides some derived variables
    packet['rainRate'] = data['rh']
    if packet['rainRate'] is not None:
        packet['rainRate'] /= 10 # weewx wants cm/hr
    packet['dewpoint'] = data['dp']
    packet['windchill'] = data['wc']

    return packet


class WS23xx(object):
    """Wrap the Ws2300 object so we can easily open serial port, read/write,
    close serial port without all of the try/except/finally scaffolding."""

    def __init__(self, port):
        logdbg('create LinuxSerialPort')
        self.serial_port = LinuxSerialPort(port)
        logdbg('create Ws2300')
        self.ws = Ws2300(self.serial_port)

    def __enter__(self):
        logdbg('station enter')
        return self

    def __exit__(self, type_, value, traceback):
        logdbg('station exit')
        self.ws = None
        self.close()

    def close(self):
        logdbg('close LinuxSerialPort')
        self.serial_port.close()
        self.serial_port = None

    def set_time(self, ts):
        """Set station time to indicated unix epoch."""
        logdbg('setting station clock to %s' % 
               weeutil.weeutil.timestamp_to_string(ts))
        for m in [Measure.IDS['sd'], Measure.IDS['st']]:
            data = m.conv.value2binary(ts)
            cmd = m.conv.write(data, None)
            self.ws.write_safe(m.address, *cmd[1:])

    def get_time(self):
        """Return station time as unix epoch."""
        data = self.get_raw_data(['sw'])
        ts = int(data['sw'])
        logdbg('station clock is %s' % weeutil.weeutil.timestamp_to_string(ts))
        return ts

    def set_archive_interval(self, interval):
        """Set the archive interval in minutes."""
        if int(interval) < 1:
            raise ValueError('archive interval must be greater than zero')
        logdbg('setting hardware archive interval to %s minutes' % interval)
        interval -= 1
        for m,v in [(Measure.IDS['hi'],interval), # archive interval in minutes
                    (Measure.IDS['hc'],1), # time till next sample in minutes
                    (Measure.IDS['hn'],0)]: # number of valid records
            data = m.conv.value2binary(v)
            cmd = m.conv.write(data, None)
            self.ws.write_safe(m.address, *cmd[1:])

    def get_archive_interval(self):
        """Return archive interval in minutes."""
        data = self.get_raw_data(['hi'])
        x = 1 + int(data['hi'])
        logdbg('station archive interval is %s minutes' % x)
        return x

    def clear_memory(self):
        """Clear station memory."""
        logdbg('clearing console memory')
        for m,v in [(Measure.IDS['hn'],0)]: # number of valid records
            data = m.conv.value2binary(v)
            cmd = m.conv.write(data, None)
            self.ws.write_safe(m.address, *cmd[1:])    

    def get_record_count(self):
        data = self.get_raw_data(['hn'])
        x = int(data['hn'])
        logdbg('record count is %s' % x)
        return x

    def gen_records(self, since_ts=None, count=None, use_computer_clock=True):
        """Get latest count records from the station from oldest to newest.  If
        count is 0 or None, return all records.

        The station has a history interval, and it records when the last
        history sample was saved.  So as long as the interval does not change
        between the first and last records, we are safe to infer timestamps
        for each record.  This assumes that if the station loses power then
        the memory will be cleared.

        There is no timestamp associated with each record - we have to guess.
        The station tells us the time until the next record and the epoch of
        the latest record, based on the station's clock.  So we can use that
        or use the computer clock to guess the timestamp for each record.

        To ensure accurate data, the first record must be read within one
        minute of the initial read and the remaining records must be read
        within numrec * interval minutes.
        """

        logdbg("gen_records: since_ts=%s count=%s clock=%s" % 
               (since_ts, count, use_computer_clock))
        measures = [Measure.IDS['hi'], Measure.IDS['hw'],
                    Measure.IDS['hc'], Measure.IDS['hn']]
        raw_data = read_measurements(self.ws, measures)
        interval = 1 + int(measures[0].conv.binary2value(raw_data[0])) # minute
        latest_ts = int(measures[1].conv.binary2value(raw_data[1])) # epoch
        time_to_next = int(measures[2].conv.binary2value(raw_data[2])) # minute
        numrec = int(measures[3].conv.binary2value(raw_data[3]))

        now = int(time.time())
        cstr = 'station'
        if use_computer_clock:
            latest_ts = now - (interval - time_to_next) * 60
            cstr = 'computer'
        logdbg("using %s clock with latest_ts of %s" %
               (cstr, weeutil.weeutil.timestamp_to_string(latest_ts)))

        if not count:
            count = HistoryMeasure.MAX_HISTORY_RECORDS
        if since_ts is not None:
            count = int((now - since_ts) / (interval * 60))
            logdbg("count is %d to satisfy timestamp of %s" %
                   (count, weeutil.weeutil.timestamp_to_string(since_ts)))
        if count == 0:
            return
        if count > numrec:
            count = numrec
        if count > HistoryMeasure.MAX_HISTORY_RECORDS:
            count = HistoryMeasure.MAX_HISTORY_RECORDS

        # station is about to overwrite first record, so skip it
        if time_to_next <= 1 and count == HistoryMeasure.MAX_HISTORY_RECORDS:
            count -= 1

        logdbg("downloading %d records from station" % count)
        HistoryMeasure.set_constants(self.ws)
        measures = [HistoryMeasure(n) for n in range(count-1, -1, -1)]
        raw_data = read_measurements(self.ws, measures)
        last_ts = latest_ts - (count-1) * interval * 60
        for measure, nybbles in zip(measures, raw_data):
            value = measure.conv.binary2value(nybbles)
            data_dict = {
                'interval': interval,
                'it': value.temp_indoor,
                'ih': value.humidity_indoor,
                'ot': value.temp_outdoor,
                'oh': value.humidity_outdoor,
                'pa': value.pressure_absolute,
                'rt': value.rain,
                'wind': (value.wind_speed/10, value.wind_direction, 0, 0),
                'rh': None,  # no rain rate in history
                'dp': None,  # no dewpoint in history
                'wc': None,  # no windchill in history
                }
            yield last_ts, data_dict
            last_ts += interval * 60

    def get_raw_data(self, labels):
        """Get raw data from the station, return as dictionary."""
        measures = [Measure.IDS[m] for m in labels]
        raw_data = read_measurements(self.ws, measures)
        data_dict = dict(zip(labels, [m.conv.binary2value(d) for m, d in zip(measures, raw_data)]))
        return data_dict


# =============================================================================
# The following code was adapted from ws2300.py by Russell Stuart
# =============================================================================

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
    class Ws2300Exception(weewx.WeeWxIOError):
        def __init__(self, *args):
            weewx.WeeWxIOError.__init__(self, *args)
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
            for _ in range(self.__class__.MAX_RESETS):
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
            for _ in range(self.MAXRETRIES):
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
                StandardError("Too many nybbles requested")
            bytes_ = (nybble_count + 1) // 2
            if not self.write_address(nybble_address):
                return None
            #
            # Write the number bytes we want to read.
            #
            encoded_data = chr(0xC2 + bytes_*4)
            self.write_byte(encoded_data)
            answer = self.read_byte()
            check = chr(0x30 + bytes_)
            if answer != check:
                self.log("??")
                return None
            #
            # Read the response.
            #
            self.log(", :")
            response = ""
            for _ in range(bytes_):
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
                    for _ in range(self.MAXRETRIES):
                        bytes_ = min(self.MAXBLOCK, batch[1]-start_pos)
                        response = self.read_data(address + start_pos, bytes_)
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
    def log(self, s):
        if not DEBUG_SERIAL:
            return
        self.log_buffer[-1] = self.log_buffer[-1] + s
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
    for _ in range(nybble_count):
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
    for _ in range(nybble_count):
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
    def parse(self, s): raise NotImplementedError()
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
    def parse(self, s):
        return float(s)

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
    def parse(self, s):
        return float(s)

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
    def __init__(self, nybble_count, format_):
        description =  format_
        for xlate in "%Y:yyyy,%m:mm,%d:dd,%H:hh,%M:mm,%S:ss".split(","):
            description = description.replace(*xlate.split(":"))
        Conversion.__init__(self, "", nybble_count, description)
        self.format = format_
    def str(self, value):
        return time.strftime(self.format, time.localtime(value))
    def parse(self, s):
        return time.mktime(time.strptime(s, self.format))

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
    def parse(self, s):
        return time.mktime((0,0,0) + time.strptime(s, self.format)[3:]) + time.timezone

class WindDirectionConversion(Conversion):
    def __init__(self):
        Conversion.__init__(self, "deg", 1, "North=0 clockwise")
    def binary2value(self, data):
        return data[0] * 22.5
    def value2binary(self, value):
        return (int((value + 11.25) / 22.5),)
    def str(self, value):
        return "%g" % value
    def parse(self, s):
        return float(s)

class WindVelocityConversion(Conversion):
    def __init__(self):
        Conversion.__init__(self, "ms,d", 4, "wind speed and direction")
    def binary2value(self, data):
        return (bin2num(data[:3])/10.0, bin2num(data[3:4]) * 22.5)
    def value2binary(self, value):
        return num2bin(value[0]*10, 3) + num2bin((value[1] + 11.5) / 22.5, 1)
    def str(self, value):
        return "%.1f,%g" % value
    def parse(self, s):
        return tuple([float(x) for x in s.split(",")])

# The ws2300 1.8 implementation does not calculate wind speed correctly -
# it uses bcd2num instead of bin2num.  This conversion object uses bin2num
# decoding and it reads all wind data in a single transcation so that we do
# not suffer coherency problems.
class WindConversion(Conversion):
    def __init__(self):
        Conversion.__init__(self, "ms,d,o,v", 12, "wind speed, dir, validity")
    def binary2value(self, data):
        overflow = data[0]
        validity = data[1]
        speed = bin2num(data[2:5]) / 10.0
        direction = data[5] * 22.5
        return (speed, direction, overflow, validity)
    def str(self, value):
        return "%.1f,%g,%s,%s" % value
    def parse(self, s):
        return tuple([float(x) for x in s.split(",")])

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
    def parse(self, s):
        result = [c[0] for c in self.constants.items() if c[1] == s]
        if result:
            return result[0]
        return None

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
    def parse(self, s):
        return [c[0] for c in self.desc.items() if c[1] == s][0]

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
        def parse(cls, s):
            rec = cls()
            toks = [tok.rstrip(string.ascii_letters + "%/") for tok in s.split()]
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
    def parse(self, s):
        return self.__class__.HistoryRecord.parse(s)

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
conv_wspd = BinConversion("m/s", 3, 1, "speed")
conv_wind = WindConversion()

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
    def __init__(self, address, id_, conv, name, reset=None):
        self.address = address
        self.conv = conv
        self.reset = reset
        if id_ != None:
            self.id = id_
            assert not id_ in self.__class__.IDS
            self.__class__.IDS[id_] = self
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
    def parse(self, s):
        toks = s.replace(","," ").split()
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
    def __init__(self, address, id_, conv, name):
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
# get all of the wind info in a single invocation
Measure(0x527, "wind", conv_wind, "wind")

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


class WS23xxConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WS23xx]
    # This section is for the La Crosse WS-2300 series of weather stations.

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The station model, e.g., 'LaCrosse WS2317' or 'TFA Primus'
    model = LaCrosse WS23xx

    # The driver to use:
    driver = weewx.drivers.ws23xx
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}

    def modify_config(self, config_dict):
        print """
Setting record_generation to software."""
        config_dict['StdArchive']['record_generation'] = 'software'


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/ws23xx.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--debug] [--help]"""

    syslog.openlog('ws23xx', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
    port = DEFAULT_PORT
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display diagnostic information while running')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='serial port to which the station is connected')
    parser.add_option('--readings', dest='readings', action='store_true',
                      help='display sensor readings')
    parser.add_option("--records", dest="records", type=int, metavar="N",
                      help="display N station records, oldest to newest")
    parser.add_option('--help-measures', dest='hm', action='store_true',
                      help='display measure names')
    parser.add_option('--measure', dest='measure', type=str,
                      metavar="MEASURE", help='display single measure')

    (options, args) = parser.parse_args()

    if options.version:
        print "ws23xx driver version %s" % DRIVER_VERSION
        exit(1)

    if options.debug is not None:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    if options.port:
        port = options.port

    with WS23xx(port) as s:
        if options.readings:
            data = s.get_raw_data(SENSOR_IDS)
            print data
        if options.records is not None:
            for ts,record in s.gen_records(count=options.records):
                print ts,record
        if options.measure:
            data = s.get_raw_data([options.measure])
            print data
        if options.hm:
            for m in Measure.IDS:
                print "%s\t%s" % (m, Measure.IDS[m].name)
