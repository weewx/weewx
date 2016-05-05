# Copyright 2012 Matthew Wall
# See the file LICENSE.txt for your full rights.
#
# Thanks to Jim Easterbrook for pywws.  This implementation includes
# significant portions that were copied directly from pywws.
#
# pywws was derived from wwsr.c by Michael Pendec (michael.pendec@gmail.com),
# wwsrdump.c by Svend Skafte (svend@skafte.net), modified by Dave Wells,
# and other sources.
#
# Thanks also to Mark Teel for the C implementation in wview.
#
# FineOffset support in wview was inspired by the fowsr project by Arne-Jorgen
# Auberg (arne.jorgen.auberg@gmail.com) with hidapi mods by Bill Northcott.

# USB Lockups
#
# the ws2080 will frequently lock up and require a power cycle to regain
# communications.  my sample size is small (3 ws2080 consoles running
# for 1.5 years), but fairly repeatable.  one of the consoles has never
# locked up.  the other two lock up after a month or so.  the monitoring
# software will detect bad magic numbers, then the only way to clear the
# bad magic is to power cycle the console.  this was with wview and pywws.
# i am collecting a table of bad magic numbers to see if there is a pattern.
# hopefully the device is simply trying to tell us something.  on the other
# hand it could just be bad firmware.  it seems to happen when the data
# logging buffer on the console is full, but not always when the buffer
# is full.
# --mwall 30dec2012
#
# the magic numbers do not seem to be correlated with lockups.  in some cases,
# a lockup happens immediately following an unknown magic number.  in other
# cases, data collection continues with no problem.  for example, a brand new
# WS2080A console reports 44 bf as its magic number, but performs just fine.
# --mwall 02oct2013
#
# fine offset documentation indicates that set_clock should work, but so far
# it has not worked on any ambient weather WS2080 or WS1090 station i have
# tried.  it looks like the station clock is set, but at some point the fixed
# block reverts to the previous clock value.  also unclear is the behavior
# when the station attempts to sync with radio clock signal from sensor.
# -- mwall 14feb2013

"""Classes and functions for interfacing with FineOffset weather stations.

FineOffset stations are branded by many vendors, including
 * Ambient Weather
 * Watson
 * National Geographic
 * Elecsa
 * Tycon

There are many variants, for example WS1080, WS1090, WH2080, WH2081, WA2080,
WA2081, WH2081, WH1080, WH1081.  The variations include uv/luminance, solar
charging, touch screen, single instrument cluster versus separate cluster.

This implementation supports the 1080, 2080, and 3080 series devices via USB.
The 1080 and 2080 use the same data format, referred to as the 1080 data format
in this code.  The 3080 has an expanded data format, referred to as the 3080
data format, that includes ultraviolet and luminance.

It should not be necessary to specify the station type.  The default behavior
is to expect the 1080 data format, then change to 3080 format if additional
data are available.

The FineOffset station console updates every 48 seconds.  UV data update every
60 seconds.  This implementation defaults to sampling the station console via
USB for live data every 60 seconds.  Use the parameter 'polling_interval' to
adjust this.  An adaptive polling mode is also available.  This mode attempts
to read only when the console is not writing to memory or reading data from
the sensors.

This implementation maps the values decoded by pywws to the names needed
by weewx.  The pywws code is mostly untouched - it has been modified to
conform to weewx error handling and reporting, and some additional error
checks have been added.

Rainfall and Spurious Sensor Readings

The rain counter occasionally reports incorrect rainfall.  On some stations,
the counter decrements then increments.  Or the counter may increase by more
than the number of bucket tips that actually occurred.  The max_rain_rate
helps filter these bogus readings.  This filter is applied to any sample
period.  If the volume of the samples in the period divided by the sample
period interval are greater than the maximum rain rate, the samples are
ignored.

Spurious rain counter decrements often accompany what appear to be noisy
sensor readings.  So if we detect a spurious rain counter decrement, we ignore
the rest of the sensor data as well.  The suspect sensor readings appear
despite the double reading (to ensure the read is not happening mid-write)
and do not seem to correlate to unstable reads.

A single bucket tip is equivalent to 0.3 mm of rain.  The default maximum
rate is 24 cm/hr (9.44 in/hr).  For a sample period of 5 minutes this would
be 2 cm (0.78 in) or about 66 bucket tips, or one tip every 4 seconds.  For
a sample period of 30 minutes this would be 12 cm (4.72 in)

The rain counter is two bytes, so the maximum value is 0xffff or 65535.  This
translates to 19660.5 mm of rainfall (19.66 m or 64.9 ft).  The console would
have to run for two years with 2 inches of rainfall a day before the counter
wraps around.

Pressure Calculations

Pressures are calculated and reported differently by pywws and wview.  These
are the variables:

 - abs_pressure - the raw sensor reading
 - fixed_block_rel_pressure - value entered in console, then follows
     abs_pressure as it changes
 - fixed_block_abs_pressure - seems to follow abs_pressure, sometimes
     with a lag of a minute or two
 - pressure - station pressure (SP) - adjusted raw sensor reading
 - barometer - sea level pressure derived from SP using temperaure and altitude
 - altimeter - sea level pressure derived from SP using altitude

wview reports the following:

  pressure = abs_pressure * calMPressure + calCPressure
  barometer = sp2bp(pressure, altitude, temperature)
  altimeter = sp2ap(pressure, altitude)

pywws reports the following:

  pressure = abs_pressure + pressure_offset

where pressure_offset is

  pressure_offset = fixed_block_relative_pressure - fixed_block_abs_pressure

so that

  pressure = fixed_block_relative_pressure

pywws does not do barometer or altimeter calculations.

this implementation reports the abs_pressure from the hardware as 'pressure'.
altimeter and barometer are calculated by weewx.

Illuminance and Radiation

The 30xx stations include a sensor that reports illuminance (lux).  The
conversion from lux to radiation is a function of the angle of the sun and
altitude, but this driver uses a single multiplier as an approximation.

Apparently the display on fine offset stations is incorrect.  The display
reports radiation with a lux-to-W/m^2 multiplier of 0.001464.  Apparently
Cumulus and WeatherDisplay use a multiplier of 0.0079.  The multiplier for
sea level with sun directly overhead is 0.01075.

This driver uses the sea level multiplier of 0.01075.  Use an entry in
StdCalibrate to adjust this for your location and altitude.

From Jim Easterbrook:

The weather station memory has two parts: a "fixed block" of 256 bytes
and a circular buffer of 65280 bytes. As each weather reading takes 16
bytes the station can store 4080 readings, or 14 days of 5-minute
interval readings. (The 3080 type stations store 20 bytes per reading,
so store a maximum of 3264.) As data is read in 32-byte chunks, but
each weather reading is 16 or 20 bytes, a small cache is used to
reduce USB traffic. The caching behaviour can be over-ridden with the
``unbuffered`` parameter to ``get_data`` and ``get_raw_data``.

Decoding the data is controlled by the static dictionaries
``reading_format``, ``lo_fix_format`` and ``fixed_format``. The keys
are names of data items and the values can be an ``(offset, type,
multiplier)`` tuple or another dictionary. So, for example, the
reading_format dictionary entry ``'rain' : (13, 'us', 0.3)`` means
that the rain value is an unsigned short (two bytes), 13 bytes from
the start of the block, and should be multiplied by 0.3 to get a
useful value.

The use of nested dictionaries in the ``fixed_format`` dictionary
allows useful subsets of data to be decoded. For example, to decode
the entire block ``get_fixed_block`` is called with no parameters::

  print get_fixed_block()

To get the stored minimum external temperature, ``get_fixed_block`` is
called with a sequence of keys::

  print get_fixed_block(['min', 'temp_out', 'val'])

Often there is no requirement to read and decode the entire fixed
block, as its first 64 bytes contain the most useful data: the
interval between stored readings, the buffer address where the current
reading is stored, and the current date & time. The
``get_lo_fix_block`` method provides easy access to these.

From Mark Teel:

The WH1080 protocol is undocumented. The following was observed
by sniffing the USB interface:

A1 is a read command:
It is sent as A1XX XX20 A1XX XX20 where XXXX is the offset in the
memory map. The WH1080 responds with 4 8 byte blocks to make up a
32 byte read of address XXXX.

A0 is a write command:
It is sent as A0XX XX20 A0XX XX20 where XXXX is the offset in the
memory map. It is followed by 4 8 byte chunks of data to be written
at the offset. The WH1080 acknowledges the write with an 8 byte
chunk: A5A5 A5A5.

A2 is a one byte write command.
It is used as: A200 1A20 A2AA 0020 to indicate a data refresh.
The WH1080 acknowledges the write with an 8 byte chunk: A5A5 A5A5.
"""

import datetime
import sys
import syslog
import time
import usb

import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'FineOffsetUSB'
DRIVER_VERSION = '1.8'

def loader(config_dict, engine):
    return FineOffsetUSB(**config_dict[DRIVER_NAME])

def configurator_loader(config_dict):
    return FOUSBConfigurator()

def confeditor_loader():
    return FOUSBConfEditor()


# flags for enabling/disabling debug verbosity
DEBUG_SYNC = 0
DEBUG_RAIN = 0


def stash(slist, s):
    if s.find('settings') != -1:
        slist['settings'].append(s)
    elif s.find('display') != -1:
        slist['display_settings'].append(s)
    elif s.find('alarm') != -1:
        slist['alarm_settings'].append(s)
    elif s.find('min.') != -1 or s.find('max.') != -1:
        slist['minmax_values'].append(s)
    else:
        slist['values'].append(s)
    return slist

def fmtparam(label, value):
    fmt = '%s'
    if label in datum_display_formats.keys():
        fmt = datum_display_formats[label]
    fmt = '%s: ' + fmt
    return fmt % (label.rjust(30), value)

def getvalues(station, name, value):
    values = {}
    if type(value) is tuple:
        values[name] = station.get_fixed_block(name.split('.'))
    elif type(value) is dict:
        for x in value.keys():
            n = x
            if len(name) > 0:
                n = name + '.' + x
            values.update(getvalues(station, n, value[x]))
    return values

def raw_dump(date, pos, data):
    print date,
    print "%04x" % pos,
    for item in data:
        print "%02x" % item,
    print

def table_dump(date, data, showlabels=False):
    if showlabels:
        print '# date time',
        for key in data.keys():
            print key,
        print
    print date,
    for key in data.keys():
        print data[key],
    print


class FOUSBConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[FineOffsetUSB]
    # This section is for the Fine Offset series of weather stations.

    # The station model, e.g., WH1080, WS1090, WS2080, WH3081
    model = WS2080

    # How often to poll the station for data, in seconds
    polling_interval = 60

    # The driver to use:
    driver = weewx.drivers.fousb
"""

    def get_conf(self, orig_stanza=None):
        if orig_stanza is None:
            return self.default_stanza
        import configobj
        stanza = configobj.ConfigObj(orig_stanza.splitlines())
        if 'pressure_offset' in stanza[DRIVER_NAME]:
            print """
The pressure_offset is no longer supported by the FineOffsetUSB driver.  Move
the pressure calibration constant to [StdCalibrate] instead."""
        if ('polling_mode' in stanza[DRIVER_NAME] and
            stanza[DRIVER_NAME]['polling_mode'] == 'ADAPTIVE'):
            print """
Using ADAPTIVE as the polling_mode can lead to USB lockups."""
        if ('polling_interval' in stanza[DRIVER_NAME] and
            int(stanza[DRIVER_NAME]['polling_interval']) < 48):
            print """
A polling_interval of anything less than 48 seconds is not recommened."""
        return orig_stanza

    def modify_config(self, config_dict):
        print """
Setting record_generation to software."""
        config_dict['StdArchive']['record_generation'] = 'software'


class FOUSBConfigurator(weewx.drivers.AbstractConfigurator):
    def add_options(self, parser):
        super(FOUSBConfigurator, self).add_options(parser)
        parser.add_option("--info", dest="info", action="store_true",
                          help="display weather station configuration")
        parser.add_option("--current", dest="current", action="store_true",
                          help="get the current weather conditions")
        parser.add_option("--history", dest="nrecords", type=int, metavar="N",
                          help="display N records")
        parser.add_option("--history-since", dest="recmin",
                          type=int, metavar="N",
                          help="display records since N minutes ago")
        parser.add_option("--clear-memory", dest="clear", action="store_true",
                          help="clear station memory")
        parser.add_option("--set-time", dest="clock", action="store_true",
                          help="set station clock to computer time")
        parser.add_option("--set-interval", dest="interval",
                          type=int, metavar="N",
                          help="set logging interval to N minutes")
        parser.add_option("--live", dest="live", action="store_true",
                          help="display live readings from the station")
        parser.add_option("--logged", dest="logged", action="store_true",
                          help="display logged readings from the station")
        parser.add_option("--fixed-block", dest="showfb", action="store_true",
                          help="display the contents of the fixed block")
        parser.add_option("--check-usb", dest="chkusb", action="store_true",
                          help="test the quality of the USB connection")
        parser.add_option("--check-fixed-block", dest="chkfb",
                          action="store_true",
                          help="monitor the contents of the fixed block")
        parser.add_option("--format", dest="format",
                          type=str, metavar="FORMAT",
                          help="format for output, one of raw, table, or dict")

    def do_options(self, options, parser, config_dict, prompt):
        if options.format is None:
            options.format = 'table'
        elif (options.format.lower() != 'raw' and
              options.format.lower() != 'table' and
              options.format.lower() != 'dict'):
            parser.error("Unknown format '%s'.  Known formats include 'raw', 'table', and 'dict'." % options.format)

        self.station = FineOffsetUSB(**config_dict[DRIVER_NAME])
        if options.current:
            self.show_current()
        elif options.nrecords is not None:
            self.show_history(0, options.nrecords, options.format)
        elif options.recmin is not None:
            ts = int(time.time()) - options.recmin * 60
            self.show_history(ts, 0, options.format)
        elif options.live:
            self.show_readings(False)
        elif options.logged:
            self.show_readings(True)
        elif options.showfb:
            self.show_fixedblock()
        elif options.chkfb:
            self.check_fixedblock()
        elif options.chkusb:
            self.check_usb()
        elif options.clock:
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

        print "Querying the station..."
        val = getvalues(self.station, '', fixed_format)

        print 'Fine Offset station settings:'
        print '%s: %s' % ('local time'.rjust(30),
                          time.strftime('%Y.%m.%d %H:%M:%S %Z',
                                        time.localtime()))
        print '%s: %s' % ('polling mode'.rjust(30), self.station.polling_mode)

        slist = {'values':[], 'minmax_values':[], 'settings':[],
                 'display_settings':[], 'alarm_settings':[]}
        for x in sorted(val.keys()):
            if type(val[x]) is dict:
                for y in val[x].keys():
                    label = x + '.' + y
                    s = fmtparam(label, val[x][y])
                    slist = stash(slist, s)
            else:
                s = fmtparam(x, val[x])
                slist = stash(slist, s)
        for k in ('values', 'minmax_values', 'settings',
                  'display_settings', 'alarm_settings'):
            print ''
            for s in slist[k]:
                print s

    def check_usb(self):
        """Run diagnostics on the USB connection."""
        print "This will read from the station console repeatedly to see if"
        print "there are errors in the USB communications.  Leave this running"
        print "for an hour or two to see if any bad reads are encountered."
        print "Bad reads will be reported in the system log.  A few bad reads"
        print "per hour is usually acceptable."
        ptr = data_start
        total_count = 0
        bad_count = 0
        while True:
            if total_count % 1000 == 0:
                active = self.station.current_pos()
            while True:
                ptr += 0x20
                if ptr >= 0x10000:
                    ptr = data_start
                if active < ptr - 0x10 or active >= ptr + 0x20:
                    break
            result_1 = self.station._read_block(ptr, retry=False)
            result_2 = self.station._read_block(ptr, retry=False)
            if result_1 != result_2:
                syslog.syslog(syslog.LOG_INFO, 'read_block change %06x' % ptr)
                syslog.syslog(syslog.LOG_INFO, '  %s' % str(result_1))
                syslog.syslog(syslog.LOG_INFO, '  %s' % str(result_2))
                bad_count += 1
            total_count += 1
            print "\rbad/total: %d/%d " % (bad_count, total_count),
            sys.stdout.flush()

    def check_fixedblock(self):
        """Display changes to fixed block as they occur."""
        print 'This will read the fixed block then display changes as they'
        print 'occur.  Typically the most common change is the incrementing'
        print 'of the data pointer, which happens whenever readings are saved'
        print 'to the station memory.  For example, if the logging interval'
        print 'is set to 5 minutes, the fixed block should change at least'
        print 'every 5 minutes.'
        raw_fixed = self.station.get_raw_fixed_block()
        while True:
            new_fixed = self.station.get_raw_fixed_block(unbuffered=True)
            for ptr in range(len(new_fixed)):
                if new_fixed[ptr] != raw_fixed[ptr]:
                    print datetime.datetime.now().strftime('%H:%M:%S'),
                    print ' %04x (%d) %02x -> %02x' % (
                        ptr, ptr, raw_fixed[ptr], new_fixed[ptr])
                    raw_fixed = new_fixed
                    time.sleep(0.5)

    def show_fixedblock(self):
        """Display the raw fixed block contents."""
        fb = self.station.get_raw_fixed_block(unbuffered=True)
        for i, ptr in enumerate(range(len(fb))):
            print '%02x' % fb[ptr],
            if (i+1) % 16 == 0:
                print

    def show_readings(self, logged_only):
        """Display live readings from the station."""
        for data,ptr,_ in self.station.live_data(logged_only):
            print '%04x' % ptr,
            print data['idx'].strftime('%H:%M:%S'),
            del data['idx']
            print data

    def show_current(self):
        """Display latest readings from the station."""
        for packet in self.station.genLoopPackets():
            print packet
            break

    def show_history(self, ts=0, count=0, fmt='raw'):
        """Display the indicated number of records or the records since the 
        specified timestamp (local time, in seconds)"""
        records = self.station.get_records(since_ts=ts, num_rec=count)
        for i,r in enumerate(records):
            if fmt.lower() == 'raw':
                raw_dump(r['datetime'], r['ptr'], r['raw_data'])
            elif fmt.lower() == 'table':
                table_dump(r['datetime'], r['data'], i==0)
            else:
                print r['datetime'], r['data']

    def clear_history(self, prompt):
        ans = None
        while ans not in ['y', 'n']:
            v = self.station.get_fixed_block(['data_count'], True)
            print "Records in memory:", v
            if prompt:
                ans = raw_input("Clear console memory (y/n)? ")
            else:
                print 'Clearing console memory'
                ans = 'y'
            if ans == 'y' :
                self.station.clear_history()
                v = self.station.get_fixed_block(['data_count'], True)
                print "Records in memory:", v
            elif ans == 'n':
                print "Clear memory cancelled."

    def set_interval(self, interval, prompt):
        v = self.station.get_fixed_block(['read_period'], True)
        ans = None
        while ans not in ['y', 'n']:
            print "Interval is", v
            if prompt:
                ans = raw_input("Set interval to %d minutes (y/n)? " % interval)
            else:
                print "Setting interval to %d minutes" % interval
                ans = 'y'
            if ans == 'y' :
                self.station.set_read_period(interval)
                v = self.station.get_fixed_block(['read_period'], True)
                print "Interval is now", v
            elif ans == 'n':
                print "Set interval cancelled."

    def set_clock(self, prompt):
        ans = None
        while ans not in ['y', 'n']:
            v = self.station.get_fixed_block(['date_time'], True)
            print "Station clock is", v
            now = datetime.datetime.now()
            if prompt:
                ans = raw_input("Set station clock to %s (y/n)? " % now)
            else:
                print "Setting station clock to %s" % now
                ans = 'y'
            if ans == 'y' :
                self.station.set_clock()
                v = self.station.get_fixed_block(['date_time'], True)
                print "Station clock is now", v
            elif ans == 'n':
                print "Set clock cancelled."


# these are the raw data we get from the station:
# param     values     invalid description
#
# delay     [1,240]            the number of minutes since last stored reading
# hum_in    [1,99]     0xff    indoor relative humidity; %
# temp_in   [-40,60]   0xffff  indoor temp; multiply by 0.1 to get C
# hum_out   [1,99]     0xff    outdoor relative humidity; %
# temp_out  [-40,60]   0xffff  outdoor temp; multiply by 0.1 to get C
# abs_pres  [920,1080] 0xffff  pressure; multiply by 0.1 to get hPa (mbar)
# wind_ave  [0,50]     0xff    average wind speed; multiply by 0.1 to get m/s
# wind_gust [0,50]     0xff    average wind speed; multiply by 0.1 to get m/s
# wind_dir  [0,15]     bit 7   wind direction; multiply by 22.5 to get degrees
# rain                         rain; multiply by 0.33 to get mm
# status
# illuminance
# uv

# map between the pywws keys and the weewx keys
# 'weewx-key' : ( 'pywws-key', multiplier )
# rain is total measure so must split into per-period and calculate rate
# station has no separate windgustdir so use wind_dir
keymap = {
    'inHumidity'  : ('hum_in',       1.0),
    'inTemp'      : ('temp_in',      1.0), # station is C
    'outHumidity' : ('hum_out',      1.0),
    'outTemp'     : ('temp_out',     1.0), # station is C
    'pressure'    : ('abs_pressure', 1.0), # station is mbar
    'windSpeed'   : ('wind_ave',     3.6), # station is m/s, weewx wants km/h
    'windGust'    : ('wind_gust',    3.6), # station is m/s, weewx wants km/h
    'windDir'     : ('wind_dir',    22.5), # station is 0-15, weewx wants deg
    'windGustDir' : ('wind_dir',    22.5), # station is 0-15, weewx wants deg
    'rain'        : ('rain',         0.1), # station is mm, weewx wants cm
    'radiation'   : ('illuminance',  0.01075), # lux, weewx wants W/m^2
    'UV'          : ('uv',           1.0),
    'status'      : ('status',       1.0),
}

# formats for displaying fixed_format fields
datum_display_formats = {
    'magic_1' : '0x%2x',
    'magic_2' : '0x%2x',
    }

# wrap value for rain counter
rain_max = 0x10000

# values for status:
rain_overflow   = 0x80
lost_connection = 0x40
#  unknown         = 0x20
#  unknown         = 0x10
#  unknown         = 0x08
#  unknown         = 0x04
#  unknown         = 0x02
#  unknown         = 0x01

def decode_status(status):
    result = {}
    if status is None:
        return result
    for key, mask in (('rain_overflow',   0x80),
                      ('lost_connection', 0x40),
                      ('unknown',         0x3f),
                      ):
        result[key] = status & mask
    return result

def get_status(code, status):
    return 1 if status & code == code else 0

def pywws2weewx(p, ts, last_rain, last_rain_ts, max_rain_rate):
    """Map the pywws dictionary to something weewx understands.

    p: dictionary of pywws readings

    ts: timestamp in UTC

    last_rain: last rain total in cm

    last_rain_ts: timestamp of last rain total

    max_rain_rate: maximum value for rain rate in cm/hr.  rainfall readings
    resulting in a rain rate greater than this value will be ignored.
    """

    packet = {}
    # required elements
    packet['usUnits'] = weewx.METRIC
    packet['dateTime'] = ts

    # everything else...
    for k in keymap.keys():
        if keymap[k][0] in p and p[keymap[k][0]] is not None:
            packet[k] = p[keymap[k][0]] * keymap[k][1]
        else:
            packet[k] = None

    # track the pointer used to obtain the data
    packet['ptr'] = int(p['ptr']) if p.has_key('ptr') else None
    packet['delay'] = int(p['delay']) if p.has_key('delay') else None

    # station status is an integer
    if packet['status'] is not None:
        packet['status'] = int(packet['status'])
        packet['rxCheckPercent'] = 0 if get_status(lost_connection, packet['status']) else 100
        packet['outTempBatteryStatus'] = get_status(rain_overflow, packet['status'])

    # calculate the rain increment from the rain total
    # watch for spurious rain counter decrement.  if decrement is significant
    # then it is a counter wraparound.  a small decrement is either a sensor
    # glitch or a read from a previous record.  if the small decrement persists
    # across multiple samples, it was probably a firmware glitch rather than
    # a sensor glitch or old read.  a spurious increment will be filtered by
    # the bogus rain rate check.
    total = packet['rain']
    packet['rainTotal'] = packet['rain']
    if packet['rain'] is not None and last_rain is not None:
        if packet['rain'] < last_rain:
            pstr = '0x%04x' % packet['ptr'] if packet['ptr'] is not None else 'None'
            if last_rain - packet['rain'] < rain_max * 0.3 * 0.5:
                loginf('ignoring spurious rain counter decrement (%s): '
                       'new: %s old: %s' % (pstr, packet['rain'], last_rain))
            else:
                loginf('rain counter wraparound detected (%s): '
                       'new: %s old: %s' % (pstr, packet['rain'], last_rain))
                total += rain_max * 0.3
    packet['rain'] = weewx.wxformulas.calculate_rain(total, last_rain)

    # report rainfall in log to diagnose rain counter issues
    if DEBUG_RAIN and packet['rain'] is not None and packet['rain'] > 0:
        logdbg('got rainfall of %.2f cm (new: %.2f old: %.2f)' %
               (packet['rain'], packet['rainTotal'], last_rain))

    return packet

USB_RT_PORT = (usb.TYPE_CLASS | usb.RECIP_OTHER)
USB_PORT_FEAT_POWER = 8

def power_cycle_station(hub, port):
    '''Power cycle the port on the specified hub.  This works only with USB
    hubs that support per-port power switching such as the linksys USB2HUB4.'''
    loginf("Attempting to power cycle")
    busses = usb.busses()
    if not busses:
        raise weewx.WeeWxIOError("Power cycle failed: cannot find USB busses")
    device = None
    for bus in busses:
        for dev in bus.devices:
            if dev.deviceClass == usb.CLASS_HUB:
                devid = "%s:%03d" % (bus.dirname, dev.devnum)
                if devid == hub:
                    device = dev
    if device is None:
        raise weewx.WeeWxIOError("Power cycle failed: cannot find hub %s" % hub)
    handle = device.open()
    try:
        loginf("Power off port %d on hub %s" % (port, hub))
        handle.controlMsg(requestType=USB_RT_PORT,
                          request=usb.REQ_CLEAR_FEATURE,
                          value=USB_PORT_FEAT_POWER,
                          index=port, buffer=None, timeout=1000)
        loginf("Waiting 30 seconds for station to power down")
        time.sleep(30)
        loginf("Power on port %d on hub %s" % (port, hub))
        handle.controlMsg(requestType=USB_RT_PORT,
                          request=usb.REQ_SET_FEATURE,
                          value=USB_PORT_FEAT_POWER,
                          index=port, buffer=None, timeout=1000)
        loginf("Waiting 60 seconds for station to power up")
        time.sleep(60)
    finally:
        del handle
    loginf("Power cycle complete")

# decode weather station raw data formats
def _signed_byte(raw, offset):
    res = raw[offset]
    if res == 0xFF:
        return None
    sign = 1
    if res >= 128:
        sign = -1
        res = res - 128
    return sign * res
def _signed_short(raw, offset):
    lo = raw[offset]
    hi = raw[offset+1]
    if lo == 0xFF and hi == 0xFF:
        return None
    sign = 1
    if hi >= 128:
        sign = -1
        hi = hi - 128
    return sign * ((hi * 256) + lo)
def _unsigned_short(raw, offset):
    lo = raw[offset]
    hi = raw[offset+1]
    if lo == 0xFF and hi == 0xFF:
        return None
    return (hi * 256) + lo
def _unsigned_int3(raw, offset):
    lo = raw[offset]
    md = raw[offset+1]
    hi = raw[offset+2]
    if lo == 0xFF and md == 0xFF and hi == 0xFF:
        return None
    return (hi * 256 * 256) + (md * 256) + lo
def _bcd_decode(byte):
    hi = (byte // 16) & 0x0F
    lo = byte & 0x0F
    return (hi * 10) + lo
def _date_time(raw, offset):
    year = _bcd_decode(raw[offset])
    month = _bcd_decode(raw[offset+1])
    day = _bcd_decode(raw[offset+2])
    hour = _bcd_decode(raw[offset+3])
    minute = _bcd_decode(raw[offset+4])
    return '%4d-%02d-%02d %02d:%02d' % (year + 2000, month, day, hour, minute)
def _bit_field(raw, offset):
    mask = 1
    result = []
    for i in range(8):  # @UnusedVariable
        result.append(raw[offset] & mask != 0)
        mask = mask << 1
    return result
def _decode(raw, fmt):
    if not raw:
        return None
    if isinstance(fmt, dict):
        result = {}
        for key, value in fmt.items():
            result[key] = _decode(raw, value)
    else:
        pos, typ, scale = fmt
        if typ == 'ub':
            result = raw[pos]
            if result == 0xFF:
                result = None
        elif typ == 'sb':
            result = _signed_byte(raw, pos)
        elif typ == 'us':
            result = _unsigned_short(raw, pos)
        elif typ == 'u3':
            result = _unsigned_int3(raw, pos)
        elif typ == 'ss':
            result = _signed_short(raw, pos)
        elif typ == 'dt':
            result = _date_time(raw, pos)
        elif typ == 'tt':
            result = '%02d:%02d' % (_bcd_decode(raw[pos]),
                                    _bcd_decode(raw[pos+1]))
        elif typ == 'pb':
            result = raw[pos]
        elif typ == 'wa':
            # wind average - 12 bits split across a byte and a nibble
            result = raw[pos] + ((raw[pos+2] & 0x0F) << 8)
            if result == 0xFFF:
                result = None
        elif typ == 'wg':
            # wind gust - 12 bits split across a byte and a nibble
            result = raw[pos] + ((raw[pos+1] & 0xF0) << 4)
            if result == 0xFFF:
                result = None
        elif typ == 'wd':
            # wind direction - check bit 7 for invalid
            result = raw[pos]
            if result & 0x80:
                result = None
        elif typ == 'bf':
            # bit field - 'scale' is a list of bit names
            result = {}
            for k, v in zip(scale, _bit_field(raw, pos)):
                result[k] = v
            return result
        else:
            raise weewx.WeeWxIOError('decode failure: unknown type %s' % typ)
        if scale and result:
            result = float(result) * scale
    return result
def _bcd_encode(value):
    hi = value // 10
    lo = value % 10
    return (hi * 16) + lo

#def logmsg(level, msg):
#    syslog.syslog(level, 'fousb: %s: %s' %
#                  (threading.currentThread().getName(), msg))

def logmsg(level, msg):
    syslog.syslog(level, 'fousb: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

class ObservationError(Exception):
    pass

# mechanisms for polling the station
PERIODIC_POLLING = 'PERIODIC'
ADAPTIVE_POLLING = 'ADAPTIVE'

class FineOffsetUSB(weewx.drivers.AbstractDevice):
    """Driver for FineOffset USB stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        model: Which station model is this?
        [Optional. Default is 'WH1080 (USB)']

        polling_mode: The mechanism to use when polling the station.  PERIODIC
        polling queries the station console at regular intervals.  ADAPTIVE
        polling adjusts the query interval in an attempt to avoid times when
        the console is writing to memory or communicating with the sensors.
        The polling mode applies only when the weewx StdArchive is set to
        'software', otherwise weewx reads archived records from the console.
        [Optional. Default is 'PERIODIC']
        
        polling_interval: How often to sample the USB interface for data.
        [Optional. Default is 60 seconds]

        max_rain_rate: Maximum sane value for rain rate for a single polling
        interval or archive interval, measured in cm/hr.  If the rain sample
        for a single period is greater than this rate, the sample will be
        logged but not added to the loop or archive data.
        [Optional. Default is 24]

        timeout: How long to wait, in seconds, before giving up on a response
        from the USB port.
        [Optional. Default is 15 seconds]
        
        wait_before_retry: How long to wait after a failure before retrying.
        [Optional. Default is 30 seconds]

        max_tries: How many times to try before giving up.
        [Optional. Default is 3]

        device_id: The USB device ID for the station.  Specify this if there
        are multiple devices of the same type on the bus.
        [Optional. No default]
        """

        self.model             = stn_dict.get('model', 'WH1080 (USB)')
        self.polling_mode      = stn_dict.get('polling_mode', PERIODIC_POLLING)
        self.polling_interval  = int(stn_dict.get('polling_interval', 60))
        self.max_rain_rate     = int(stn_dict.get('max_rain_rate', 24))
        self.timeout           = float(stn_dict.get('timeout', 15.0))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 30.0))
        self.max_tries         = int(stn_dict.get('max_tries', 3))
        self.device_id         = stn_dict.get('device_id', None)

        # FIXME: prefer 'power_cycle_on_fail = (True|False)'
        self.pc_hub            = stn_dict.get('power_cycle_hub', None)
        self.pc_port           = stn_dict.get('power_cycle_port', None)
        if self.pc_port is not None:
            self.pc_port = int(self.pc_port)

        self.data_format   = stn_dict.get('data_format', '1080')
        self.vendor_id     = 0x1941
        self.product_id    = 0x8021
        self.usb_interface = 0
        self.usb_endpoint  = 0x81
        self.usb_read_size = 0x20

        # avoid USB activity this many seconds each side of the time when
        # console is believed to be writing to memory.
        self.avoid = 3.0
        # minimum interval between polling for data change
        self.min_pause = 0.5

        self.devh = None
        self._arcint = None
        self._last_rain_loop = None
        self._last_rain_ts_loop = None
        self._last_rain_arc = None
        self._last_rain_ts_arc = None
        self._last_status = None
        self._fixed_block = None
        self._data_block = None
        self._data_pos = None
        self._current_ptr = None
        self._station_clock = None
        self._sensor_clock = None
        # start with known magic numbers.  report any additional we encounter.
        # these are from wview: 55??, ff??, 01??, 001e, 0001
        # these are from pywws: 55aa, ffff, 5555, c400
        self._magic_numbers = ['55aa']
        self._last_magic = None

        # FIXME: get last_rain_arc and last_rain_ts_arc from database

        global DEBUG_SYNC
        DEBUG_SYNC = int(stn_dict.get('debug_sync', 0))
        global DEBUG_RAIN
        DEBUG_RAIN = int(stn_dict.get('debug_rain', 0))

        loginf('driver version is %s' % DRIVER_VERSION)
        if self.pc_hub is not None:
            loginf('power cycling enabled for port %s on hub %s' %
                   (self.pc_port, self.pc_hub))
        loginf('polling mode is %s' % self.polling_mode)
        if self.polling_mode.lower() == PERIODIC_POLLING.lower():
            loginf('polling interval is %s' % self.polling_interval)

        self.openPort()

    # Unfortunately there is no provision to obtain the model from the station
    # itself, so use what is specified from the configuration file.
    @property
    def hardware_name(self):
        return self.model

    # weewx wants the archive interval in seconds, but the database record
    # follows the wview convention of minutes and the console uses minutes.
    @property
    def archive_interval(self):
        return self._archive_interval_minutes() * 60

    # if power cycling is enabled, loop forever until we get a response from
    # the weather station.
    def _archive_interval_minutes(self):
        if self._arcint is not None:
            return self._arcint
        if self.pc_hub is not None:
            while True:
                try:
                    self.openPort()
                    self._get_arcint()
                    break
                except weewx.WeeWxIOError:
                    self.closePort()
                    power_cycle_station(self.pc_hub, self.pc_port)
        else:
            self._get_arcint()
        return self._arcint

    def _get_arcint(self):
        for i in range(self.max_tries):
            try:
                self._arcint = self.get_fixed_block(['read_period'])
                return
            except usb.USBError, e:
                logcrt("get archive interval failed attempt %d of %d: %s"
                       % (i+1, self.max_tries, e))
        else:
            raise weewx.WeeWxIOError("Unable to read archive interval after %d tries" % self.max_tries)

    def openPort(self):
        if self.devh is not None:
            return

        dev = self._find_device()
        if not dev:
            logcrt("Cannot find USB device with Vendor=0x%04x ProdID=0x%04x Device=%s" % (self.vendor_id, self.product_id, self.device_id))
            raise weewx.WeeWxIOError("Unable to find USB device")

        self.devh = dev.open()
        if not self.devh:
            raise weewx.WeeWxIOError("Open USB device failed")

        # be sure kernel does not claim the interface
        try:
            self.devh.detachKernelDriver(self.usb_interface)
        except:
            pass

        # attempt to claim the interface
        try:
            self.devh.claimInterface(self.usb_interface)
        except usb.USBError, e:
            self.closePort()
            logcrt("Unable to claim USB interface %s: %s" %
                   (self.usb_interface, e))
            raise weewx.WeeWxIOError(e)
        
    def closePort(self):
        try:
            self.devh.releaseInterface()
        except:
            pass
        self.devh = None

    def _find_device(self):
        """Find the vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.vendor_id and dev.idProduct == self.product_id:
                    if self.device_id is None or dev.filename == self.device_id:
                        loginf('found station on USB bus=%s device=%s' % (bus.dirname, dev.filename))
                        return dev
        return None

# There is no point in using the station clock since it cannot be trusted and
# since we cannot synchronize it with the computer clock.

#    def getTime(self):
#        return self.get_clock()

#    def setTime(self):
#        self.set_clock()

    def genLoopPackets(self):
        """Generator function that continuously returns decoded packets."""

        for p in self.get_observations():
            ts = int(time.time() + 0.5)
            packet = pywws2weewx(p, ts,
                                 self._last_rain_loop, self._last_rain_ts_loop,
                                 self.max_rain_rate)
            self._last_rain_loop = packet['rainTotal']
            self._last_rain_ts_loop = ts
            if packet['status'] != self._last_status:
                loginf('station status %s (%s)' % 
                       (decode_status(packet['status']), packet['status']))
                self._last_status = packet['status']
            yield packet

    def genArchiveRecords(self, since_ts):
        """Generator function that returns records from the console.

        since_ts: local timestamp in seconds.  All data since (but not
                  including) this time will be returned.  A value of None
                  results in all data.

        yields: a sequence of dictionaries containing the data, each with
                local timestamp in seconds.
        """
        records = self.get_records(since_ts)
        logdbg('found %d archive records' % len(records))
        epoch = datetime.datetime.utcfromtimestamp(0)
        for r in records:
            delta = r['datetime'] - epoch
            # FIXME: deal with daylight saving corner case
            ts = delta.days * 86400 + delta.seconds
            data = pywws2weewx(r['data'], ts,
                               self._last_rain_arc, self._last_rain_ts_arc,
                               self.max_rain_rate)
            data['interval'] = r['interval']
            data['ptr'] = r['ptr']
            self._last_rain_arc = data['rainTotal']
            self._last_rain_ts_arc = ts
            logdbg('returning archive record %s' % ts)
            yield data

    def get_observations(self):
        """Get data from the station.

        There are a few types of non-fatal failures we might encounter while
        reading.  When we encounter one, log the failure then retry.
        
        Sometimes current_pos returns None for the pointer.  This is useless to
        us, so keep querying until we get a valid pointer.

        In live_data, sometimes the delay is None.  This prevents calculation
        of the timing intervals, so bail out and retry.

        If we get USB read failures, retry until we get something valid.
        """
        nerr = 0
        old_ptr = None
        interval = self._archive_interval_minutes()
        while True:
            try:
                if self.polling_mode.lower() == ADAPTIVE_POLLING.lower():
                    for data,ptr,logged in self.live_data():  # @UnusedVariable
                        nerr = 0
                        data['ptr'] = ptr
                        yield data
                elif self.polling_mode.lower() == PERIODIC_POLLING.lower():
                    new_ptr = self.current_pos()
                    if new_ptr < data_start:
                        raise ObservationError('bad pointer: 0x%04x' % new_ptr)
                    block = self.get_raw_data(new_ptr, unbuffered=True)
                    if len(block) != reading_len[self.data_format]:
                        raise ObservationError('wrong block length: expected: %d actual: %d' % (reading_len[self.data_format], len(block)))
                    data = _decode(block, reading_format[self.data_format])
                    delay = data.get('delay', None)
                    if delay is None:
                        raise ObservationError('no delay found in observation')
                    if new_ptr != old_ptr and delay >= interval:
                        raise ObservationError('ignoring suspected bogus data from 0x%04x (delay=%s interval=%s)' % (new_ptr, delay, interval))
                    old_ptr = new_ptr
                    data['ptr'] = new_ptr
                    nerr = 0
                    yield data
                    time.sleep(self.polling_interval)
                else:
                    raise Exception("unknown polling mode '%s'" % self.polling_mode)

            except (IndexError, usb.USBError, ObservationError), e:
                logerr('get_observations failed: %s' % e)
                nerr += 1
                if nerr > self.max_tries:
                    raise weewx.WeeWxIOError("Max retries exceeded while fetching observations")
                time.sleep(self.wait_before_retry)

#==============================================================================
# methods for reading from and writing to usb
#
#            end mark: 0x20
#        read command: 0xA1
#       write command: 0xA0
#  write command word: 0xA2
#
# FIXME: to support multiple usb drivers, these should be abstracted to a class
# FIXME: refactor the _read_usb methods to pass read_size down the chain
#==============================================================================

    def _read_usb_block(self, address):
        addr1 = (address / 256) & 0xff
        addr2 = address & 0xff
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             0x0000009,
                             [0xA1,addr1,addr2,0x20,0xA1,addr1,addr2,0x20],
                             0x0000200,
                             0x0000000,
                             1000)
        data = self.devh.interruptRead(self.usb_endpoint,
                                       self.usb_read_size, # bytes to read
                                       int(self.timeout*1000))
        return list(data)

    def _read_usb_bytes(self, size):
        data = self.devh.interruptRead(self.usb_endpoint,
                                       size,
                                       int(self.timeout*1000))
        if data is None or len(data) < size:
            raise weewx.WeeWxIOError('Read from USB failed')
        return list(data)

    def _write_usb(self, address, data):
        addr1 = (address / 256) & 0xff
        addr2 = address & 0xff
        buf = [0xA2,addr1,addr2,0x20,0xA2,data,0,0x20]
        result = self.devh.controlMsg(
            usb.ENDPOINT_OUT + usb.TYPE_CLASS + usb.RECIP_INTERFACE,
            usb.REQ_SET_CONFIGURATION,  # 0x09
            buf,
            value = 0x200,
            index = 0,
            timeout = int(self.timeout*1000))
        if result != len(buf):
            return False
        buf = self._read_usb_bytes(8)
        if buf is None:
            return False
        for byte in buf:
            if byte != 0xA5:
                return False
        return True

#==============================================================================
# methods for configuring the weather station
# the following were adapted from various pywws utilities
#==============================================================================

    def decode(self, raw_data):
        return _decode(raw_data, reading_format[self.data_format])

    def clear_history(self):
        ptr = fixed_format['data_count'][0]
        data = []
        data.append((ptr,   1))
        data.append((ptr+1, 0))
        self.write_data(data)

    def set_pressure(self, pressure):
        pressure = int(float(pressure) * 10.0 + 0.5)
        ptr = fixed_format['rel_pressure'][0]
        data = []
        data.append((ptr,   pressure % 256))
        data.append((ptr+1, pressure // 256))
        self.write_data(data)

    def set_read_period(self, read_period):
        read_period = int(read_period)
        data = []
        data.append((fixed_format['read_period'][0], read_period))
        self.write_data(data)

    def set_clock(self, ts=0):
        if ts == 0:
            now = datetime.datetime.now()
            if now.second >= 55:
                time.sleep(10)
                now = datetime.datetime.now()
            now += datetime.timedelta(minutes=1)
        else:
            now = datetime.datetime.fromtimestamp(ts)
        ptr = fixed_format['date_time'][0]
        data = []
        data.append((ptr,   _bcd_encode(now.year - 2000)))
        data.append((ptr+1, _bcd_encode(now.month)))
        data.append((ptr+2, _bcd_encode(now.day)))
        data.append((ptr+3, _bcd_encode(now.hour)))
        data.append((ptr+4, _bcd_encode(now.minute)))
        time.sleep(59 - now.second)
        self.write_data(data)

    def get_clock(self):
        tstr = self.get_fixed_block(['date_time'], True)
        tt = time.strptime(tstr, '%Y-%m-%d %H:%M')
        ts = time.mktime(tt)
        return int(ts)

    def get_records(self, since_ts=0, num_rec=0):
        """Get data from station memory.

        The weather station contains a circular buffer of data, but there is
        no absolute date or time for each record, only relative offsets.  So
        the best we can do is to use the 'delay' and 'read_period' to guess
        when each record was made.

        Use the computer clock since we cannot trust the station clock.

        Return an array of dict, with each dict containing a datetimestamp
        in UTC, the pointer, the decoded data, and the raw data.  Items in the
        array go from oldest to newest.
        """
        nerr = 0
        while True:
            try:
                fixed_block = self.get_fixed_block(unbuffered=True)
                if fixed_block['read_period'] is None:
                    raise weewx.WeeWxIOError('invalid read_period in get_records')
                if fixed_block['data_count'] is None:
                    raise weewx.WeeWxIOError('invalid data_count in get_records')
                if since_ts:
                    dt = datetime.datetime.utcfromtimestamp(since_ts)
                    dt += datetime.timedelta(seconds=fixed_block['read_period']*30)
                else:
                    dt = datetime.datetime.min
                max_count = fixed_block['data_count'] - 1
                if num_rec == 0 or num_rec > max_count:
                    num_rec = max_count
                logdbg('get %d records since %s' % (num_rec, dt))
                dts, ptr = self.sync(read_period=fixed_block['read_period'])
                count = 0
                records = []
                while dts > dt and count < num_rec:
                    raw_data = self.get_raw_data(ptr)
                    data = self.decode(raw_data)
                    if data['delay'] is None or data['delay'] > 30:
                        logerr('invalid data in get_records at 0x%04x, %s' %
                               (ptr, dts.isoformat()))
                        dts -= datetime.timedelta(minutes=fixed_block['read_period'])
                    else:
                        record = dict()
                        record['ptr'] = ptr
                        record['datetime'] = dts
                        record['data'] = data
                        record['raw_data'] = raw_data
                        record['interval'] = data['delay']
                        records.insert(0, record)
                        count += 1
                        dts -= datetime.timedelta(minutes=data['delay'])
                    ptr = self.dec_ptr(ptr)
                return records
            except (IndexError, usb.USBError, ObservationError), e:
                logerr('get_records failed: %s' % e)
                nerr += 1
                if nerr > self.max_tries:
                    raise weewx.WeeWxIOError("Max retries exceeded while fetching records")
                time.sleep(self.wait_before_retry)

    def sync(self, quality=None, read_period=None):
        """Synchronise with the station to determine the date and time of the
        latest record.  Return the datetime stamp in UTC and the record
        pointer. The quality determines the accuracy of the synchronisation.

        0 - low quality, synchronisation to within 12 seconds
        1 - high quality, synchronisation to within 2 seconds

        The high quality synchronisation could take as long as a logging
        interval to complete.
        """
        if quality is None:
            if read_period is not None and read_period <= 5:
                quality = 1
            else:
                quality = 0
        loginf('synchronising to the weather station (quality=%d)' % quality)
        range_hi = datetime.datetime.max
        range_lo = datetime.datetime.min
        ptr = self.current_pos()
        data = self.get_data(ptr, unbuffered=True)
        last_delay = data['delay']
        if last_delay is None or last_delay == 0:
            prev_date = datetime.datetime.min
        else:
            prev_date = datetime.datetime.utcnow()
        maxcount = 10
        count = 0
        for data, last_ptr, logged in self.live_data(logged_only=(quality>1)):
            last_date = data['idx']
            logdbg('packet timestamp is %s' % last_date.strftime('%H:%M:%S'))
            if logged:
                break
            if data['delay'] is None:
                logerr('invalid data while synchronising at 0x%04x' % last_ptr)
                count += 1
                if count > maxcount:
                    raise weewx.WeeWxIOError('repeated invalid delay while synchronising')
                continue
            if quality < 2 and self._station_clock:
                err = last_date - datetime.datetime.fromtimestamp(self._station_clock)
                last_date -= datetime.timedelta(minutes=data['delay'],
                                                seconds=err.seconds % 60)
                logdbg('log timestamp is %s' % last_date.strftime('%H:%M:%S'))
                last_ptr = self.dec_ptr(last_ptr)
                break
            if quality < 1:
                hi = last_date - datetime.timedelta(minutes=data['delay'])
                if last_date - prev_date > datetime.timedelta(seconds=50):
                    lo = hi - datetime.timedelta(seconds=60)
                elif data['delay'] == last_delay:
                    lo = hi - datetime.timedelta(seconds=60)
                    hi = hi - datetime.timedelta(seconds=48)
                else:
                    lo = hi - datetime.timedelta(seconds=48)
                last_delay = data['delay']
                prev_date = last_date
                range_hi = min(range_hi, hi)
                range_lo = max(range_lo, lo)
                err = (range_hi - range_lo) / 2
                last_date = range_lo + err
                logdbg('estimated log time %s +/- %ds (%s..%s)' %
                       (last_date.strftime('%H:%M:%S'), err.seconds,
                        lo.strftime('%H:%M:%S'), hi.strftime('%H:%M:%S')))
                if err < datetime.timedelta(seconds=15):
                    last_ptr = self.dec_ptr(last_ptr)
                    break
        logdbg('synchronised to %s for ptr 0x%04x' % (last_date, last_ptr))
        return last_date, last_ptr

#==============================================================================
# methods for reading data from the weather station
# the following were adapted from WeatherStation.py in pywws
#
# commit 7d2e8ec700a652426c0114e7baebcf3460b1ef0f
# Author: Jim Easterbrook <jim@jim-easterbrook.me.uk>
# Date:   Thu Oct 31 13:04:29 2013 +0000
#==============================================================================

    def live_data(self, logged_only=False):
        # There are two things we want to synchronise to - the data is
        # updated every 48 seconds and the address is incremented
        # every 5 minutes (or 10, 15, ..., 30). Rather than getting
        # data every second or two, we sleep until one of the above is
        # due. (During initialisation we get data every two seconds
        # anyway.)
        read_period = self.get_fixed_block(['read_period'])
        if read_period is None:
            raise ObservationError('invalid read_period in live_data')
        log_interval = float(read_period * 60)
        live_interval = 48.0
        old_ptr = self.current_pos()
        old_data = self.get_data(old_ptr, unbuffered=True)
        if old_data['delay'] is None:
            raise ObservationError('invalid delay at 0x%04x' % old_ptr)
        now = time.time()
        if self._sensor_clock:
            next_live = now
            next_live -= (next_live - self._sensor_clock) % live_interval
            next_live += live_interval
        else:
            next_live = None
        if self._station_clock and next_live:
            # set next_log
            next_log = next_live - live_interval
            next_log -= (next_log - self._station_clock) % 60
            next_log -= old_data['delay'] * 60
            next_log += log_interval
        else:
            next_log = None
            self._station_clock = None
        ptr_time = 0
        data_time = 0
        last_log = now - (old_data['delay'] * 60)
        last_status = None
        while True:
            if not self._station_clock:
                next_log = None
            if not self._sensor_clock:
                next_live = None
            now = time.time()
            # wake up just before next reading is due
            advance = now + max(self.avoid, self.min_pause) + self.min_pause
            pause = 600.0
            if next_live:
                if not logged_only:
                    pause = min(pause, next_live - advance)
            else:
                pause = self.min_pause
            if next_log:
                pause = min(pause, next_log - advance)
            elif old_data['delay'] < read_period - 1:
                pause = min(
                    pause, ((read_period - old_data['delay']) * 60.0) - 110.0)
            else:
                pause = self.min_pause
            pause = max(pause, self.min_pause)
            if DEBUG_SYNC:
                logdbg('delay %s, pause %g' % (str(old_data['delay']), pause))
            time.sleep(pause)
            # get new data
            last_data_time = data_time
            new_data = self.get_data(old_ptr, unbuffered=True)
            if new_data['delay'] is None:
                raise ObservationError('invalid delay at 0x%04x' % old_ptr)
            data_time = time.time()
            # log any change of status
            if new_data['status'] != last_status:
                logdbg('status %s (%s)' % (str(decode_status(new_data['status'])), new_data['status']))
            last_status = new_data['status']
            # 'good' time stamp if we haven't just woken up from long
            # pause and data read wasn't delayed
            valid_time = data_time - last_data_time < (self.min_pause * 2.0) - 0.1
            # make sure changes because of logging interval aren't
            # mistaken for new live data
            if new_data['delay'] >= read_period:
                for key in ('delay', 'hum_in', 'temp_in', 'abs_pressure'):
                    old_data[key] = new_data[key]
            # ignore solar data which changes every 60 seconds
            if self.data_format == '3080':
                for key in ('illuminance', 'uv'):
                    old_data[key] = new_data[key]
            if new_data != old_data:
                logdbg('new data')
                result = dict(new_data)
                if valid_time:
                    # data has just changed, so definitely at a 48s update time
                    if self._sensor_clock:
                        diff = (data_time - self._sensor_clock) % live_interval
                        if diff > 2.0 and diff < (live_interval - 2.0):
                            logdbg('unexpected sensor clock change')
                            self._sensor_clock = None
                    if not self._sensor_clock:
                        self._sensor_clock = data_time
                        logdbg('setting sensor clock %g' %
                               (data_time % live_interval))
                    if not next_live:
                        logdbg('live synchronised')
                    next_live = data_time
                elif next_live and data_time < next_live - self.min_pause:
                    logdbg('lost sync %g' % (data_time - next_live))
                    next_live = None
                    self._sensor_clock = None
                if next_live and not logged_only:
                    while data_time > next_live + live_interval:
                        logdbg('missed interval')
                        next_live += live_interval
                    result['idx'] = datetime.datetime.utcfromtimestamp(int(next_live))
                    next_live += live_interval
                    yield result, old_ptr, False
                old_data = new_data
            # get new pointer
            if old_data['delay'] < read_period - 1:
                continue
            last_ptr_time = ptr_time
            new_ptr = self.current_pos()
            ptr_time = time.time()
            valid_time = ptr_time - last_ptr_time < (self.min_pause * 2.0) - 0.1
            if new_ptr != old_ptr:
                logdbg('new ptr: %06x (%06x)' % (new_ptr, old_ptr))
                last_log = ptr_time
                # re-read data, to be absolutely sure it's the last
                # logged data before the pointer was updated
                new_data = self.get_data(old_ptr, unbuffered=True)
                if new_data['delay'] is None:
                    raise ObservationError('invalid delay at 0x%04x' % old_ptr)
                result = dict(new_data)
                if valid_time:
                    # pointer has just changed, so definitely at a logging time
                    if self._station_clock:
                        diff = (ptr_time - self._station_clock) % 60
                        if diff > 2 and diff < 58:
                            logdbg('unexpected station clock change')
                            self._station_clock = None
                    if not self._station_clock:
                        self._station_clock = ptr_time
                        logdbg('setting station clock %g' % (ptr_time % 60.0))
                    if not next_log:
                        logdbg('log synchronised')
                    next_log = ptr_time
                elif next_log and ptr_time < next_log - self.min_pause:
                    logdbg('lost log sync %g' % (ptr_time - next_log))
                    next_log = None
                    self._station_clock = None
                if next_log:
                    result['idx'] = datetime.datetime.utcfromtimestamp(int(next_log))
                    next_log += log_interval
                    yield result, old_ptr, True
                if new_ptr != self.inc_ptr(old_ptr):
                    logerr('unexpected ptr change %06x -> %06x' %
                           (old_ptr, new_ptr))
                    old_ptr = new_ptr
                    old_data['delay'] = 0
                elif ptr_time > last_log + ((new_data['delay'] + 2) * 60):
                    # if station stops logging data, don't keep reading
                    # USB until it locks up
                    raise ObservationError('station is not logging data')
                elif valid_time and next_log and ptr_time > next_log + 6.0:
                    logdbg('log extended')
                    next_log += 60.0

    def inc_ptr(self, ptr):
        """Get next circular buffer data pointer."""
        result = ptr + reading_len[self.data_format]
        if result >= 0x10000:
            result = data_start
        return result

    def dec_ptr(self, ptr):
        """Get previous circular buffer data pointer."""
        result = ptr - reading_len[self.data_format]
        if result < data_start:
            result = 0x10000 - reading_len[self.data_format]
        return result

    def get_raw_data(self, ptr, unbuffered=False):
        """Get raw data from circular buffer.

        If unbuffered is false then a cached value that was obtained
        earlier may be returned."""
        if unbuffered:
            self._data_pos = None
        # round down ptr to a 'block boundary'
        idx = ptr - (ptr % 0x20)
        ptr -= idx
        count = reading_len[self.data_format]
        if self._data_pos == idx:
            # cache contains useful data
            result = self._data_block[ptr:ptr + count]
            if len(result) >= count:
                return result
        else:
            result = list()
        if ptr + count > 0x20:
            # need part of next block, which may be in cache
            if self._data_pos != idx + 0x20:
                self._data_pos = idx + 0x20
                self._data_block = self._read_block(self._data_pos)
            result += self._data_block[0:ptr + count - 0x20]
            if len(result) >= count:
                return result
        # read current block
        self._data_pos = idx
        self._data_block = self._read_block(self._data_pos)
        result = self._data_block[ptr:ptr + count] + result
        return result

    def get_data(self, ptr, unbuffered=False):
        """Get decoded data from circular buffer.

        If unbuffered is false then a cached value that was obtained
        earlier may be returned."""
        return _decode(self.get_raw_data(ptr, unbuffered),
                       reading_format[self.data_format])

    def current_pos(self):
        """Get circular buffer location where current data is being written."""
        new_ptr = _decode(self._read_fixed_block(0x0020),
                          lo_fix_format['current_pos'])
        if new_ptr is None:
            raise ObservationError('current_pos is None')
        if new_ptr == self._current_ptr:
            return self._current_ptr
        if self._current_ptr and new_ptr != self.inc_ptr(self._current_ptr):
            for k in reading_len:
                if (new_ptr - self._current_ptr) == reading_len[k]:
                    logerr('changing data format from %s to %s' % (self.data_format, k))
                    self.data_format = k
                    break
        self._current_ptr = new_ptr
        return self._current_ptr

    def get_raw_fixed_block(self, unbuffered=False):
        """Get the raw "fixed block" of settings and min/max data."""
        if unbuffered or not self._fixed_block:
            self._fixed_block = self._read_fixed_block()
        return self._fixed_block

    def get_fixed_block(self, keys=[], unbuffered=False):
        """Get the decoded "fixed block" of settings and min/max data.

        A subset of the entire block can be selected by keys."""
        if unbuffered or not self._fixed_block:
            self._fixed_block = self._read_fixed_block()
        fmt = fixed_format
        # navigate down list of keys to get to wanted data
        for key in keys:
            fmt = fmt[key]
        return _decode(self._fixed_block, fmt)

    def _wait_for_station(self):
        # avoid times when station is writing to memory
        while True:
            pause = 60.0
            if self._station_clock:
                phase = time.time() - self._station_clock
                if phase > 24 * 3600:
                    # station clock was last measured a day ago, so reset it
                    self._station_clock = None
                else:
                    pause = min(pause, (self.avoid - phase) % 60)
            if self._sensor_clock:
                phase = time.time() - self._sensor_clock
                if phase > 24 * 3600:
                    # sensor clock was last measured 6 hrs ago, so reset it
                    self._sensor_clock = None
                else:
                    pause = min(pause, (self.avoid - phase) % 48)
            if pause >= self.avoid * 2.0:
                return
            logdbg('avoid %s' % str(pause))
            time.sleep(pause)

    def _read_block(self, ptr, retry=True):
        # Read block repeatedly until it's stable. This avoids getting corrupt
        # data when the block is read as the station is updating it.
        old_block = None
        while True:
            self._wait_for_station()
            new_block = self._read_usb_block(ptr)
            if new_block:
                if (new_block == old_block) or not retry:
                    break
                if old_block is not None:
                    loginf('unstable read: blocks differ for ptr 0x%06x' % ptr)
                old_block = new_block
        return new_block

    def _read_fixed_block(self, hi=0x0100):
        result = []
        for mempos in range(0x0000, hi, 0x0020):
            result += self._read_block(mempos)
        # check 'magic number'.  log each new one we encounter.
        magic = '%02x%02x' % (result[0], result[1])
        if magic not in self._magic_numbers:
            logcrt('unrecognised magic number %s' % magic)
            self._magic_numbers.append(magic)
        if magic != self._last_magic:
            if self._last_magic is not None:
                logcrt('magic number changed old=%s new=%s' %
                       (self._last_magic, magic))
            self._last_magic = magic
        return result

    def _write_byte(self, ptr, value):
        self._wait_for_station()
        if not self._write_usb(ptr, value):
            raise weewx.WeeWxIOError('Write to USB failed')

    def write_data(self, data):
        """Write a set of single bytes to the weather station. Data must be an
        array of (ptr, value) pairs."""
        # send data
        for ptr, value in data:
            self._write_byte(ptr, value)
        # set 'data changed'
        self._write_byte(fixed_format['data_changed'][0], 0xAA)
        # wait for station to clear 'data changed'
        while True:
            ack = _decode(self._read_fixed_block(0x0020),
                          fixed_format['data_changed'])
            if ack == 0:
                break
            logdbg('waiting for ack')
            time.sleep(6)

# Tables of "meanings" for raw weather station data. Each key
# specifies an (offset, type, multiplier) tuple that is understood
# by _decode.
# depends on weather station type
reading_format = {}
reading_format['1080'] = {
    'delay'        : (0, 'ub', None),
    'hum_in'       : (1, 'ub', None),
    'temp_in'      : (2, 'ss', 0.1),
    'hum_out'      : (4, 'ub', None),
    'temp_out'     : (5, 'ss', 0.1),
    'abs_pressure' : (7, 'us', 0.1),
    'wind_ave'     : (9, 'wa', 0.1),
    'wind_gust'    : (10, 'wg', 0.1),
    'wind_dir'     : (12, 'wd', None),
    'rain'         : (13, 'us', 0.3),
    'status'       : (15, 'pb', None),
    }
reading_format['3080'] = {
    'illuminance' : (16, 'u3', 0.1),
    'uv'          : (19, 'ub', None),
    }
reading_format['3080'].update(reading_format['1080'])

lo_fix_format = {
    'magic_1'      : (0, 'pb', None),
    'magic_2'      : (1, 'pb', None),
    'model'        : (2, 'us', None),
    'version'      : (4, 'pb', None),
    'id'           : (5, 'us', None),
    'rain_coef'    : (7, 'us', None),
    'wind_coef'    : (9, 'us', None),
    'read_period'  : (16, 'ub', None),
    'settings_1'   : (17, 'bf', ('temp_in_F', 'temp_out_F', 'rain_in',
                                 'bit3', 'bit4', 'pressure_hPa',
                                 'pressure_inHg', 'pressure_mmHg')),
    'settings_2'   : (18, 'bf', ('wind_mps', 'wind_kmph', 'wind_knot',
                                 'wind_mph', 'wind_bft', 'bit5',
                                 'bit6', 'bit7')),
    'display_1'    : (19, 'bf', ('pressure_rel', 'wind_gust', 'clock_12hr',
                                 'date_mdy', 'time_scale_24', 'show_year',
                                 'show_day_name', 'alarm_time')),
    'display_2'    : (20, 'bf', ('temp_out_temp', 'temp_out_chill',
                                 'temp_out_dew', 'rain_hour', 'rain_day',
                                 'rain_week', 'rain_month', 'rain_total')),
    'alarm_1'      : (21, 'bf', ('bit0', 'time', 'wind_dir', 'bit3',
                                 'hum_in_lo', 'hum_in_hi',
                                 'hum_out_lo', 'hum_out_hi')),
    'alarm_2'      : (22, 'bf', ('wind_ave', 'wind_gust',
                                 'rain_hour', 'rain_day',
                                 'pressure_abs_lo', 'pressure_abs_hi',
                                 'pressure_rel_lo', 'pressure_rel_hi')),
    'alarm_3'      : (23, 'bf', ('temp_in_lo', 'temp_in_hi',
                                 'temp_out_lo', 'temp_out_hi',
                                 'wind_chill_lo', 'wind_chill_hi',
                                 'dew_point_lo', 'dew_point_hi')),
    'timezone'     : (24, 'sb', None),
    'unknown_01'   : (25, 'pb', None),
    'data_changed' : (26, 'ub', None),
    'data_count'   : (27, 'us', None),
    'display_3'    : (29, 'bf', ('illuminance_fc', 'bit1', 'bit2', 'bit3',
                                 'bit4', 'bit5', 'bit6', 'bit7')),
    'current_pos'  : (30, 'us', None),
    }

fixed_format = {
    'rel_pressure'     : (32, 'us', 0.1),
    'abs_pressure'     : (34, 'us', 0.1),
    'lux_wm2_coeff'    : (36, 'us', 0.1),
    'wind_mult'        : (38, 'us', None),
    'temp_out_offset'  : (40, 'us', None),
    'temp_in_offset'   : (42, 'us', None),
    'hum_out_offset'   : (44, 'us', None),
    'hum_in_offset'    : (46, 'us', None),
    'date_time'        : (43, 'dt', None), # conflict with temp_in_offset
    'unknown_18'       : (97, 'pb', None),
    'alarm'            : {
        'hum_in'       : {'hi': (48, 'ub', None), 'lo': (49, 'ub', None)},
        'temp_in'      : {'hi': (50, 'ss', 0.1), 'lo': (52, 'ss', 0.1)},
        'hum_out'      : {'hi': (54, 'ub', None), 'lo': (55, 'ub', None)},
        'temp_out'     : {'hi': (56, 'ss', 0.1), 'lo': (58, 'ss', 0.1)},
        'windchill'    : {'hi': (60, 'ss', 0.1), 'lo': (62, 'ss', 0.1)},
        'dewpoint'     : {'hi': (64, 'ss', 0.1), 'lo': (66, 'ss', 0.1)},
        'abs_pressure' : {'hi': (68, 'us', 0.1), 'lo': (70, 'us', 0.1)},
        'rel_pressure' : {'hi': (72, 'us', 0.1), 'lo': (74, 'us', 0.1)},
        'wind_ave'     : {'bft': (76, 'ub', None), 'ms': (77, 'ub', 0.1)},
        'wind_gust'    : {'bft': (79, 'ub', None), 'ms': (80, 'ub', 0.1)},
        'wind_dir'     : (82, 'ub', None),
        'rain'         : {'hour': (83,'us',0.3), 'day': (85,'us',0.3)},
        'time'         : (87, 'tt', None),
        'illuminance'  : (89, 'u3', 0.1),
        'uv'           : (92, 'ub', None),
        },
    'max'              : {
        'uv'           : {'val': (93, 'ub', None)},
        'illuminance'  : {'val': (94, 'u3', 0.1)},
        'hum_in'       : {'val': (98, 'ub', None), 'date' : (141, 'dt', None)},
        'hum_out'      : {'val': (100, 'ub', None), 'date': (151, 'dt', None)},
        'temp_in'      : {'val': (102, 'ss', 0.1), 'date' : (161, 'dt', None)},
        'temp_out'     : {'val': (106, 'ss', 0.1), 'date' : (171, 'dt', None)},
        'windchill'    : {'val': (110, 'ss', 0.1), 'date' : (181, 'dt', None)},
        'dewpoint'     : {'val': (114, 'ss', 0.1), 'date' : (191, 'dt', None)},
        'abs_pressure' : {'val': (118, 'us', 0.1), 'date' : (201, 'dt', None)},
        'rel_pressure' : {'val': (122, 'us', 0.1), 'date' : (211, 'dt', None)},
        'wind_ave'     : {'val': (126, 'us', 0.1), 'date' : (221, 'dt', None)},
        'wind_gust'    : {'val': (128, 'us', 0.1), 'date' : (226, 'dt', None)},
        'rain'         : {
            'hour'     : {'val': (130, 'us', 0.3), 'date' : (231, 'dt', None)},
            'day'      : {'val': (132, 'us', 0.3), 'date' : (236, 'dt', None)},
            'week'     : {'val': (134, 'us', 0.3), 'date' : (241, 'dt', None)},
            'month'    : {'val': (136, 'us', 0.3), 'date' : (246, 'dt', None)},
            'total'    : {'val': (138, 'us', 0.3), 'date' : (251, 'dt', None)},
            },
        },
    'min'              : {
        'hum_in'       : {'val': (99, 'ub', None), 'date' : (146, 'dt', None)},
        'hum_out'      : {'val': (101, 'ub', None), 'date': (156, 'dt', None)},
        'temp_in'      : {'val': (104, 'ss', 0.1), 'date' : (166, 'dt', None)},
        'temp_out'     : {'val': (108, 'ss', 0.1), 'date' : (176, 'dt', None)},
        'windchill'    : {'val': (112, 'ss', 0.1), 'date' : (186, 'dt', None)},
        'dewpoint'     : {'val': (116, 'ss', 0.1), 'date' : (196, 'dt', None)},
        'abs_pressure' : {'val': (120, 'us', 0.1), 'date' : (206, 'dt', None)},
        'rel_pressure' : {'val': (124, 'us', 0.1), 'date' : (216, 'dt', None)},
        },
    }
fixed_format.update(lo_fix_format)

# start of readings / end of fixed block
data_start = 0x0100     # 256

# bytes per reading, depends on weather station type
reading_len = {
    '1080' : 16,
    '3080' : 20,
    }
