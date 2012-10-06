#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 648 $
#    $Author: tkeffer $
#    $Date: 2012-10-01 10:33:11 -0700 (Mon, 01 Oct 2012) $
#
"""Defines the default station data, available for processing data."""
import time

import weeutil.weeutil
import weewx.units

class StationInfo(object):
    """Readonly class with static station information."""
    
    def __init__(self, console=None, **stn_dict):
        """Extracts info from the console and stn_dict and stores it in self."""
        
        if console and hasattr(console, "altitude_vt"):
            self.altitude_vt = console.altitude_vt
        else:
            altitude_t       = weeutil.weeutil.option_as_list(stn_dict.get('altitude', (None, None)))
            self.altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")

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
        self.location        = stn_dict.get('location', 'Unknown')
        self.week_start      = int(stn_dict.get('week_start', 6))

class Station(object):
    """Formatted data about the station. Rarely changes."""
    def __init__(self, stn_info,  webpath, formatter, converter, skin_dict):
        """Extracts info from the config_dict and stores it in self."""
        self.hemispheres = skin_dict['Labels'].get('hemispheres', ('N','S','E','W'))
        self.latitude_f  = stn_info.latitude_f
        self.longitude_f = stn_info.longitude_f
        self.latitude    = weeutil.weeutil.latlon_string(stn_info.latitude_f,  self.hemispheres[0:2], 'lat')
        self.longitude   = weeutil.weeutil.latlon_string(stn_info.longitude_f, self.hemispheres[2:4], 'lon')
        self.location    = stn_info.location
        self.hardware    = stn_info.hardware
        self.altitude_vt = stn_info.altitude_vt
        self.altitude    = weewx.units.ValueHelper(value_t=stn_info.altitude_vt,
                                                   formatter=formatter,
                                                   converter=converter)
        self.rain_year_start = stn_info.rain_year_start
        self.rain_year_str   = time.strftime("%b", (0, self.rain_year_start, 1, 0,0,0,0,0,-1))
        self.week_start      = stn_info.week_start
        self.uptime = weeutil.weeutil.secs_to_string(time.time() - weewx.launchtime_ts) if weewx.launchtime_ts else ''
        self.version = weewx.__version__
        # The following works on Linux only:
        try:
            os_uptime_secs =  float(open("/proc/uptime").read().split()[0])
            self.os_uptime = weeutil.weeutil.secs_to_string(int(os_uptime_secs + 0.5))
        except (IOError, KeyError):
            self.os_uptime = ''
    
        self.webpath = webpath
