#
#    Copyright (c) 2009, 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Defines (mostly static) information about a station."""
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
        self.station_url     = stn_dict.get('station_url', None)
        # For backwards compatibility:
        self.webpath         = self.station_url

class Station(object):
    """Formatted version of StationInfo."""
    
    def __init__(self, stn_info, formatter, converter, skin_dict):
        
        # Store away my instance of StationInfo
        self.stn_info = stn_info
        
        # Add a bunch of formatted attributes:
        hemispheres    = skin_dict['Labels'].get('hemispheres', ('N','S','E','W'))
        latlon_formats = skin_dict['Labels'].get('latlon_formats')
        self.latitude  = weeutil.weeutil.latlon_string(stn_info.latitude_f,  
                                                         hemispheres[0:2], 'lat', latlon_formats)
        self.longitude = weeutil.weeutil.latlon_string(stn_info.longitude_f, 
                                                         hemispheres[2:4], 'lon', latlon_formats)
        self.altitude  = weewx.units.ValueHelper(value_t=stn_info.altitude_vt,
                                                   formatter=formatter,
                                                   converter=converter)
        self.rain_year_str   = time.strftime("%b", (0, self.rain_year_start, 1, 0,0,0,0,0,-1))
        self.uptime = weeutil.weeutil.secs_to_string(time.time() - weewx.launchtime_ts) if weewx.launchtime_ts else ''
        self.version = weewx.__version__
        # The following works on Linux only:
        try:
            os_uptime_secs = float(open("/proc/uptime").read().split()[0])
            self.os_uptime = weeutil.weeutil.secs_to_string(int(os_uptime_secs + 0.5))
        except (IOError, KeyError):
            self.os_uptime = ''

    def __getattr__(self, name):
        # For anything that is not an explicit attribute of me, try
        # my instance of StationInfo. 
        return getattr(self.stn_info, name)
