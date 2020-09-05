#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Defines (mostly static) information about a station."""
from __future__ import absolute_import
import sys
import time

import weeutil.weeutil
import weewx.units

class StationInfo(object):
    """Readonly class with static station information. It has no formatting information. Just a POS.
    
    Attributes:
    
    altitude_vt:     Station altitude as a ValueTuple
    hardware:        A string holding a hardware description
    rain_year_start: The start of the rain year (1=January)
    latitude_f:      Floating point latitude
    longitude_f:     Floating point longitude
    location:        String holding a description of the station location
    week_start:      The start of the week (0=Monday)
    station_url:     An URL with an informative website (if any) about the station
    """

    def __init__(self, console=None, **stn_dict):
        """Extracts info from the console and stn_dict and stores it in self."""

        if console and hasattr(console, "altitude_vt"):
            self.altitude_vt = console.altitude_vt
        else:
            altitude_t = weeutil.weeutil.option_as_list(stn_dict.get('altitude', (None, None)))
            try:
                self.altitude_vt = weewx.units.ValueTuple(float(altitude_t[0]), altitude_t[1], "group_altitude")
            except KeyError as e:
                raise weewx.ViolatedPrecondition("Value 'altitude' needs a unit (%s)" % e)

        if console and hasattr(console, 'hardware_name'):
            self.hardware = console.hardware_name
        else:
            self.hardware = stn_dict.get('station_type', 'Unknown')

        if console and hasattr(console, 'rain_year_start'):
            self.rain_year_start = getattr(console, 'rain_year_start')
        else:
            self.rain_year_start = int(stn_dict.get('rain_year_start', 1))

        self.latitude_f      = float(stn_dict['latitude'])
        self.longitude_f     = float(stn_dict['longitude'])
        # Locations frequently have commas in them. Guard against ConfigObj turning it into a list:
        self.location        = weeutil.weeutil.list_as_string(stn_dict.get('location', 'Unknown'))
        self.week_start      = int(stn_dict.get('week_start', 6))
        self.station_url     = stn_dict.get('station_url')
        # For backwards compatibility:
        self.webpath         = self.station_url

class Station(object):
    """Formatted version of StationInfo."""

    def __init__(self, stn_info, formatter, converter, skin_dict):

        # Store away my instance of StationInfo
        self.stn_info = stn_info
        self.formatter = formatter
        self.converter = converter

        # Add a bunch of formatted attributes:
        label_dict = skin_dict.get('Labels', {})
        hemispheres    = label_dict.get('hemispheres', ('N','S','E','W'))
        latlon_formats = label_dict.get('latlon_formats')
        self.latitude  = weeutil.weeutil.latlon_string(stn_info.latitude_f,
                                                       hemispheres[0:2],
                                                       'lat', latlon_formats)
        self.longitude = weeutil.weeutil.latlon_string(stn_info.longitude_f,
                                                       hemispheres[2:4],
                                                       'lon', latlon_formats)
        self.altitude = weewx.units.ValueHelper(value_t=stn_info.altitude_vt,
                                                formatter=formatter,
                                                converter=converter)
        self.rain_year_str = time.strftime("%b", (0, self.rain_year_start, 1, 0, 0, 0, 0, 0, -1))

        self.version = weewx.__version__

        self.python_version = "%d.%d.%d" % sys.version_info[:3]

    @property
    def uptime(self):
        """Lazy evaluation of weewx uptime."""
        delta_time = time.time() - weewx.launchtime_ts if weewx.launchtime_ts else None

        return weewx.units.ValueHelper(value_t=(delta_time, "second", "group_deltatime"),
                                       formatter=self.formatter,
                                       converter=self.converter)

    @property
    def os_uptime(self):
        """Lazy evaluation of the server uptime."""
        os_uptime_secs = _os_uptime()
        return weewx.units.ValueHelper(value_t=(os_uptime_secs, "second", "group_deltatime"),
                                       formatter=self.formatter,
                                       converter=self.converter)

    def __getattr__(self, name):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if name in ['__call__', 'has_key']:
            raise AttributeError
        # For anything that is not an explicit attribute of me, try
        # my instance of StationInfo. 
        return getattr(self.stn_info, name)


def _os_uptime():
    """ Get the OS uptime. Because this is highly operating system dependent, several different
    strategies may have to be tried:"""

    try:
        # For Python 3.7 and later, most systems
        return time.clock_gettime(time.CLOCK_UPTIME)
    except AttributeError:
        pass

    try:
        # For Python 3.3 and later, most systems
        return time.clock_gettime(time.CLOCK_MONOTONIC)
    except AttributeError:
        pass

    try:
        # For Linux, Python 2 and 3:
        return float(open("/proc/uptime").read().split()[0])
    except (IOError, KeyError, OSError):
        pass

    try:
        # For MacOS, Python 2:
        from Quartz.QuartzCore import CACurrentMediaTime
        return CACurrentMediaTime()
    except ImportError:
        pass

    try:
        # for FreeBSD, Python 2
        import ctypes
        from ctypes.util import find_library

        libc = ctypes.CDLL(find_library('c'))
        size = ctypes.c_size_t()
        buf = ctypes.c_int()
        size.value = ctypes.sizeof(buf)
        libc.sysctlbyname("kern.boottime", ctypes.byref(buf), ctypes.byref(size), None, 0)
        os_uptime_secs = time.time() - float(buf.value)
        return os_uptime_secs
    except (ImportError, AttributeError, IOError, NameError):
        pass

    try:
        # For OpenBSD, Python 2. See issue #428.
        import subprocess
        from datetime import datetime
        cmd = ['sysctl', 'kern.boottime']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        o, e = proc.communicate()
        # Check for errors
        if e:
            raise IOError
        time_t = o.decode('ascii').split()
        time_as_string = time_t[1] + " " + time_t[2] + " " + time_t[4][:4] + " " + time_t[3]
        os_time = datetime.strptime(time_as_string, "%b %d %Y %H:%M:%S")
        epoch_time = (os_time - datetime(1970, 1, 1)).total_seconds()
        os_uptime_secs = time.time() - epoch_time
        return os_uptime_secs
    except (IOError, IndexError, ValueError):
        pass

    # Nothing seems to be working. Return None
    return None
