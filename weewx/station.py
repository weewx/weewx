#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Defines the default station data, available for processing data."""
import time
import urlparse
import syslog

import weewx
import weeutil.weeutil
import weewx.units

class Station(object):
    """Static data about the station. Rarely changes."""
    def __init__(self, config_dict, skin_dict):
        """Extracts info from the config_dict and stores it in self."""
        self.hemispheres = skin_dict['Labels'].get('hemispheres', ('N','S','E','W'))
        self.latitude_f  = config_dict['Station'].as_float('latitude')
        self.latitude    = weeutil.weeutil.latlon_string(self.latitude_f, self.hemispheres[0:2])
        self.longitude_f = config_dict['Station'].as_float('longitude')
        self.longitude   = weeutil.weeutil.latlon_string(self.longitude_f, self.hemispheres[2:4])

        altitude_t           = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', (None, None)))
        # This test is in here to catch any old-style altitudes:
        if len(altitude_t) != 2:
            syslog.syslog(syslog.LOG_ERR,"station: Altitude must be expressed as a list with the unit as the second element.")
            altitude_t=(float(altitude_t[0]), 'foot')
            syslog.syslog(syslog.LOG_ERR,"   ****  Assuming altitude as (%f, %s)" % altitude_t)
        
        self.altitude        = weewx.units.ValueHelper((float(altitude_t[0]), altitude_t[1]), 
                                                       unit_info=weewx.units.UnitInfo.fromSkinDict(skin_dict))

        self.location        = config_dict['Station']['location']
        self.rain_year_start = int(config_dict['Station'].get('rain_year_start', 1))
        self.rain_year_str   = time.strftime("%b", (0, self.rain_year_start, 1, 0,0,0,0,0,-1))
        self.week_start      = int(config_dict['Station'].get('week_start', 6))

        self.uptime = weeutil.weeutil.secs_to_string(time.time() - weewx.launchtime_ts) if weewx.launchtime_ts else ''
        self.version = weewx.__version__
        # The following works on Linux only:
        try:
            os_uptime_secs =  float(open("/proc/uptime").read().split()[0])
            self.os_uptime = weeutil.weeutil.secs_to_string(int(os_uptime_secs + 0.5))
        except (IOError, KeyError):
            self.os_uptime = ''
    
        try:
            website = "http://" + config_dict['Reports']['FTP']['server']
            self.webpath = urlparse.urljoin(website, config_dict['Reports']['FTP']['path'])
        except KeyError:
            self.webpath = "http://www.weewx.com"
             
