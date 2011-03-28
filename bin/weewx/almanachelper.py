#
#    Copyright (c) 2009, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Wraps almanac ephem data, making it accessible through the units machinery"""

# If the user has installed ephem, use it. Otherwise, fall back to the weeutil algorithms:
try:
    import ephem
    import math
except:
    import weeutil.Sun

import weeutil.weeephem
import weeutil.Moon
import weewx.units

class Almanac(object):
    
    def __init__(self, time_ts, lat, lon, formatter,
                 altitude=0.0, temperature=15.0, pressure=1010.0, 
                 moon_phases=weeutil.Moon.moon_phases):

        self.ephem = weeutil.weeephem.Ephem(time_ts, lat, lon,
                                            altitude, temperature, pressure)
        self.formatter = formatter
        self.moon_phases = moon_phases
        self.moon_phase = self.moon_phases[self.ephem.moon_index] if self.moon_phases is not None else ''

    def setTime(self, time_ts):
        self.ephem.setTime(time_ts)
        self.moon_phase = self.moon_phases[self.ephem.moon_index] if self.moon_phases is not None else ''

    @property
    def sunrise(self):
        if self.ephem.hasExtras:
            time_ts = self.ephem.sun.rise
        else:
            
    def __getattr__(self, attr):
        if attr in ['next_autumnal_equinox', 'next_vernal_equinox',
                                       'next_winter_solstice', 'next_summer_solstice',
                                       'next_full_moon', 'next_new_moon']:
            time_ts = getattr(self.ephem, attr)
            vt = (time_ts, "unix_epoch", "group_time")
            vh = weewx.units.ValueHelper(vt, context='current', formatter=self.formatter)
            return vh
        else:
            body = getattr(self.ephem, attr)
            return BodyHelper(body, self.formatter)
    

class BodyHelper(object):
    
    def __init__(self, body, formatter):
        self.body = body
        self.formatter = formatter
        
    def __getattr__(self, attr):
        if attr in ['next_rising', 'next_setting', 'next_transit', 'next_antitransit',
                      'previous_rising', 'previous_setting', 'previous_transit', 'previous_antitransit',
                      'rise', 'set', 'transit']:
            time_ts = getattr(self.body, attr)
            vt = (time_ts, "unix_epoch", "group_time")
            vh = weewx.units.ValueHelper(vt, context='current', formatter=self.formatter)
            return vh
        else:
            return getattr(self.body, attr)