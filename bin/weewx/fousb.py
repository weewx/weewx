# FineOffset module for weewx
# $Id: fousb.py 449 2013-02-07 17:15:41Z mwall $
#
# Copyright 2012 Matthew Wall
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
# is full.  --mwall 30dec2012

# FIXME: occasionally the inside temperature reading spikes
# FIXME: maximum sane rain may need adjustment still

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
USB for live data every 30 seconds.  Use the parameter 'sampling_period' to
adjust this.

The following functions from pywws are used by the weewx module:

  current_pos  - determine the pointer to the current data block
  get_raw_data - returns raw bytes from the station console

This function has been useful during development:

  get_data     - returns a dictionary with values decoded from raw bytes

This implementation maps the values decoded by pywws to the names needed
by weewx.  The pywws code is mostly untouched - it has been modified to
conform to weewx error handling and reporting, and some additional error
checks have been added.

The rain counter frequently flip-flops.  The value decrements, so it looks
like a counter wrap around, then it increments, looking like some rain.  A
typical bogus increment shows up as 6.6 mm (22 raw), so we use a maximum
sane value of 2 mm to avoid the spurious readings.  So if the real rainfall
is more than 2 mm per sample period it will be ignored.  With a sample period
of 30 seconds that is a rain rate of 9.4 in/hr.  The highest recorded rain
rate is 43 inches in 24 hours, or 1.79 in/hr.

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

import math
import time
import syslog

import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.wxformulas

def loader(config_dict):

    # The driver needs the altitude in meters in order to calculate relative
    # pressure. Get it from the Station data and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', (None, None)))
    # Form a value-tuple:
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    # Now convert to meters, using only the first element of the value-tuple:
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    
    station = FineOffsetUSB(altitude=altitude_m,**config_dict['FineOffsetUSB'])
    return station

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

# map between the pywws keys and the weewx (and wview) keys
# 'weewx-key' : ( 'pywws-key', multiplier )
# rain needs special treatment
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
    'radiation'   : ('illuminance',  1.0),
    'UV'          : ('uv',           1.0),
    'dewpoint'    : ('dewpoint',     1.0),
    'heatindex'   : ('heatindex',    1.0),
    'windchill'   : ('windchill',    1.0),
}

# formats for displaying fixed_format fields
datum_display_formats = {
    'magic_1' : '0x%2x',
    'magic_2' : '0x%2x',
    }

# wrap value for rain counter
rain_max = 0x10000

# values for status:
status_rain_overflow   = 0x80
status_lost_connection = 0x40
#  unknown         = 0x20
#  unknown         = 0x10
#  unknown         = 0x08
#  unknown         = 0x04
#  unknown         = 0x02
#  unknown         = 0x01

# decode weather station raw data formats
def _decode(raw, fmt):
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
        hi = (byte / 16) & 0x0F
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

def logdbg(msg):
    syslog.syslog(syslog.LOG_DEBUG, 'fousb: %s' % msg)

def loginf(msg):
    syslog.syslog(syslog.LOG_INFO, 'fousb: %s' % msg)

def logcrt(msg):
    syslog.syslog(syslog.LOG_CRIT, 'fousb: %s' % msg)

def logerr(msg):
    syslog.syslog(syslog.LOG_ERR, 'fousb: %s' % msg)

# implementation copied from wview
def sp2ap(sp_mbar, elev_meter):
    """Convert station pressure to sea level pressure.

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

class CurrentPositionError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return repr(self.msg)
    def __str__(self):
        return self.msg

class BlockLengthError(Exception):
    def __init__(self, actual_len, expected_len):
        self.act_len = actual_len
        self.exp_len = expected_len
        self.msg = 'actual:%d expected:%d' % (self.act_len, self.exp_len)
    def __repr__(self):
        return repr(self.msg)
    def __str__(self):
        return self.msg

class FineOffsetUSB(weewx.abstractstation.AbstractStation):
    """Driver for FineOffset USB stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        altitude: Altitude of the station
        [Required. Obtained from weewx configuration.]

        model: Which station model is this?
        [Optional. Default is 'WH1080 (USB)']

        rain_max_sane: Maximum sane value for rain in a single sampling
        period, measured in mm
        [Optional. Default is 2]

        timeout: How long to wait, in seconds, before giving up on a response
        from the USB port.
        [Optional. Default is 15 seconds]
        
        wait_before_retry: How long to wait after a failure before retrying.
        [Optional. Default is 5 seconds]

        max_tries: How many times to try before giving up.
        [Optional. Default is 3]
        
        sample_period: How often to sample the USB interface for data.
        [Optional. Default is 30 seconds]

        interface: The USB interface.
        [Optional. Default is 0]
        
        vendor_id: The USB vendor ID for the station.
        [Optional. Default is 1941]
        
        product_id: The USB product ID for the station.
        [Optional. Default is 8021]

        usb_endpoint: The IN_endpoint for reading from USB.
        [Optional. Default is 0x81]
        
        usb_read_size: Number of bytes to read from USB.
        [Optional. Default is 32 and is the same for all FineOffset devices]

        data_format: Format for data from the station
        [Optional. Default is 1080, automatically changes to 3080 as needed]
        """

        self.altitude          = stn_dict['altitude']
        self.record_generation = stn_dict.get('record_generation', 'software')
        self.model             = stn_dict.get('model', 'WH1080 (USB)')
        self.rain_max_sane     = int(stn_dict.get('rain_max_sane', 2))
        self.timeout           = float(stn_dict.get('timeout', 15.0))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 5.0))
        self.max_tries         = int(stn_dict.get('max_tries', 3))
        self.sample_period     = int(stn_dict.get('sample_period', 30))
        self.interface         = int(stn_dict.get('interface', 0))
        self.vendor_id         = int(stn_dict.get('vendor_id',  '0x1941'), 0)
        self.product_id        = int(stn_dict.get('product_id', '0x8021'), 0)
        self.usb_endpoint      = int(stn_dict.get('usb_endpoint', '0x81'), 0)
        self.usb_read_size     = int(stn_dict.get('usb_read_size', '0x20'), 0)
        self.data_format       = stn_dict.get('data_format', '1080')

        self._rain_period_ts = None
        self._last_rain = None
        self._fixed_block = None
        self._data_block = None
        self._data_pos = None
        self._current_ptr = None

        self.openPort()

    # Unfortunately there is no provision to obtain the model number.
    @property
    def hardware_name(self):
        return self.model

    def openPort(self):
        dev = self._findDevice()
        if not dev:
            logerr("Cannot find USB device with Vendor=0x%04x ProdID=0x%04x" % (self.vendor_id, self.product_id))
            raise weewx.WeeWxIOError("Unable to find USB device")
        self.devh = dev.open()
        # Detach any old claimed interfaces
        try:
            self.devh.detachKernelDriver(self.interface)
        except:
            pass
        try:
            self.devh.claimInterface(self.interface)
        except usb.USBError, e:
            self.closePort()
            logcrt("Unable to claim USB interface: %s" % e)
            raise weewx.WeeWxIOError(e)
        
    def closePort(self):
        try:
            self.devh.releaseInterface()
        except:
            pass
        try:
            self.devh.detachKernelDriver(self.interface)
        except:
            pass
        
    def genLoopPackets(self):
        """Generator function that continuously returns decoded packets"""
        
        genBytes = self._genBytes_raw()

        for ibyte in genBytes:
            packet = {}
            # required elements
            packet['usUnits'] = weewx.METRIC
            packet['dateTime'] = int(time.time() + 0.5)

            # decode the bytes into a pywws dictionary
            p = _decode(ibyte, reading_format[self.data_format])

            # map the pywws dictionary to something weewx understands
            for k in keymap.keys():
                if keymap[k][0] in p and p[keymap[k][0]] is not None:
                    packet[k] = p[keymap[k][0]] * keymap[k][1]
                else:
                    packet[k] = None

            # calculate the rain increment from the rain total
            if 'rain' in p and p['rain'] is not None:
                if self._last_rain is not None:
                    r = p['rain']
                    if r < self._last_rain:
                        loginf('rain counter wraparound detected: curr: %f last: %f (mm)' % (r, self._last_rain))
                        r = r + float(rain_max) * 0.3 # r is in mm
                    r = r - self._last_rain
                    if r < self.rain_max_sane:
                        packet['rain'] = r / 10 # weewx expects cm
                    else:
                        logerr('ignoring bogus rain value: rain: %f curr: %f last: %f (mm)' % (r, p['rain'], self._last_rain))
                        packet['rain'] = None
                else:
                    packet['rain'] = None
                self._last_rain = p['rain']

            # calculate the rain rate (weewx wants cm/hr)
            # if the period is zero we must ignore the rainfall, so overall
            # rain rate may be under-reported.
            if self._rain_period_ts is None:
                self._rain_period_ts = packet['dateTime']
            if packet['rain'] is not None:
                period = packet['dateTime'] - self._rain_period_ts
                if period != 0:
                    packet['rainRate'] = 3600 * packet['rain'] / period
                else:
                    if packet['rain'] != 0:
                        loginf('rain rate period is zero, ignoring rainfall of %f cm' % packet['rain'])
                    packet['rainRate'] = 0
            else:
                packet['rainRate'] = 0
            self._rain_period_ts = packet['dateTime']

            # calculated elements not directly reported by station
            if 'temp_out' in p and p['temp_out'] is not None and \
                    'hum_out' in p and p['hum_out'] is not None:
                packet['heatindex'] = weewx.wxformulas.heatindexC(p['temp_out'], p['hum_out'])
                packet['dewpoint'] = weewx.wxformulas.dewpointC(p['temp_out'], p['hum_out'])

            if 'temp_out' in p and p['temp_out'] is not None and \
                    'wind_ave' in p and p['wind_ave'] is not None:
                packet['windchill'] = weewx.wxformulas.windchillC(p['temp_out'], p['wind_ave'])

            # station reports gauge pressure, must calculate other pressures
            packet['barometer'] = sp2bp(packet['pressure'], self.altitude, packet['outTemp'])
            packet['altimeter'] = sp2ap(packet['pressure'], self.altitude)

            # report rainfall in log until we sort counter issues
            if weewx.debug and packet['rain'] is not None and packet['rain'] > 0:
                logdbg('got rainfall of %f cm' % packet['rain'])

            yield packet
                               
    def _findDevice(self):
        """Find the vendor and product ID on the USB bus."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.vendor_id and dev.idProduct == self.product_id:
                    return dev

    # there are a few types of non-fatal failures we might encounter while
    # reading.  when we encounter one, report the failure to log then retry.
    #
    # sometimes current_pos returns None for the pointer.  this is useless to
    # us, so keep querying until we get a valid pointer.
    #
    # if we get USB read failures, retry until we get something valid.
    def _genBytes_raw(self):
        """Get a sequence of bytes from the USB interface."""

        nusberr = 0
        nptrerr = 0
        old_ptr = None
        while True:
            try:
                new_ptr = self.current_pos()
                if new_ptr is None:
                    raise CurrentPositionError('current_pos returned None')
                if weewx.debug and old_ptr is not None and old_ptr != new_ptr:
                    logdbg('ptr changed: old=0x%06x new=0x%06x' % (old_ptr, new_ptr))
                nptrerr = 0
                old_ptr = new_ptr

                block = self.get_raw_data(new_ptr, unbuffered=True)
                if not len(block) == reading_len[self.data_format]:
                    raise BlockLengthError(len(block), reading_len[self.data_format])

                nusberr = 0
                yield block
                time.sleep(self.sample_period)

            except (IndexError, usb.USBError), e:
                logdbg('read data from USB failed: %s' % e)
                nusberr += 1
                if nusberr > self.max_tries:
                    msg = "Max retries exceeded while fetching data via USB"
                    logerr(msg)
                    raise weewx.WeeWxIOError(msg)
                time.sleep(self.wait_before_retry)

            except CurrentPositionError, e:
                logdbg('bogus block address: %s' % e)
                nptrerr += 1
                if nptrerr > self.max_tries:
                    msg = "Max tries exceeded while fetching current pointer"
                    logerr(msg)
                    raise weewx.WeeWxIOError(msg)
                time.sleep(self.wait_before_retry)

            except BlockLengthError, e:
                logdbg('wrong block length: %s' % e)
                time.sleep(self.wait_before_retry)

#==============================================================================
# methods for reading from and writing to usb
# FIXME: these should be abstracted to a class to support multiple usb drivers
#==============================================================================

    def _read_usb(self, address):
        buf1 = (address / 256) & 0xff
        buf2 = address & 0xff
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             0x0000009,
                             [0xA1,buf1,buf2,0x20,0xA1,buf1,buf2,0x20],
                             0x0000200,
                             0x0000000,
                             1000)
        data = self.devh.interruptRead(self.usb_endpoint,
                                       self.usb_read_size, # bytes to read
                                       int(self.timeout*1000))
        return list(data)

    def _write_usb(self, address, value):
        # FIXME: write to usb is not implemented
        return False

#==============================================================================
# methods for reading data from the weather station
# the following were adapted from pywws 12.10_r547
#==============================================================================

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
            return new_ptr
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

    def _read_block(self, ptr, retry=True):
        # Read block repeatedly until it's stable. This avoids getting corrupt
        # data when the block is read as the station is updating it.
        old_block = None
        while True:
            new_block = self._read_usb(ptr)
            if new_block:
                if (new_block == old_block) or not retry:
                    break
                if old_block != None:
                    loginf('unstable read: blocks differ for ptr 0x%06x' % ptr)
                old_block = new_block
        return new_block

    def _read_fixed_block(self, hi=0x0100):
        result = []
        for mempos in range(0x0000, hi, 0x0020):
            result += self._read_block(mempos)
        # check 'magic number'
        if result[:2] not in ([0x55, 0xAA], [0xFF, 0xFF],
                              [0x55, 0x55], [0xC4, 0x00]):
            logerr('unrecognised magic number %02x %02x' % (result[0], result[1]))
        return result

    def _write_byte(self, ptr, value):
        if not self._write_usb(ptr, value):
            raise weewx.WeeWxIOError('Write to USB failed')

    def write_data(self, data):
        """Write a set of single bytes to the weather station. Data must be an
        array of (ptr, value) pairs."""
        # send data
        for ptr, value in data:
            self._write_byte(ptr, value)
        # set 'data changed'
        self._write_byte(self.fixed_format['data_changed'][0], 0xAA)
        # wait for station to clear 'data changed'
        while True:
            ack = _decode(self._read_fixed_block(0x0020),
                          self.fixed_format['data_changed'])
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
    'wind_dir'     : (12, 'ub', None),
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
