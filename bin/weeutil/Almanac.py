# -*- coding: iso-8859-1 -*-
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Almanac data

This module can optionally use PyEphem, which offers high quality
astronomical calculations. See http://rhodesmill.org/pyephem. """

import datetime
import calendar
import time
import sys
import Moon

try:
    import ephem
    import math
except:
    import Sun

class Almanac(object):
    """Almanac data.
    
    time_ts: A timestamp within the date for which sunrise/sunset is desired.
    
    lat, lon: Location for which sunrise/sunset is desired.
    
    altitude: Elevation in **meters**.
    
    moon_phases: An array of 8 strings with descriptions of the moon 
    phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]
    
    timeformat: A strftime style format to be used to format sunrise and sunset.
    [optional. If not given, then "%H:%M" will be used.
    
    ATTRIBUTES.
    
    As a minimum, the following attributes are available:
    
        sunrise: A string version of the above, formatted using the format 'timeformat'.
        sunset: A string version of the above, formatted using the format 'timeformat'.
        moon_phase: A description of the moon phase(eg. "new moon", Waxing crescent", etc.)
        moon_fullness: Percent fullness of the moon (0=new moon, 100=full moon)

    If the module 'ephem' is used, there are many others

    EXAMPLES:
    
    >>> t = time.mktime((2009, 3, 27, 12, 0, 0, 0, 0, -1))
    >>> print weeutil.timestamp_to_string(t)
    2009-03-27 12:00:00 PDT (1238180400)
    >>> almanac = Almanac(t, 46.0, -122.0)
    >>> print "Sunrise, sunset:", almanac.sunrise, almanac.sunset
    Sunrise, sunset: 06:54 19:30
    >>> print "Fullness of the moon (rounded) is %.0f%%" % almanac.moon_fullness
    Fullness of the moon (rounded) is 2%
    >>> print "Fullness of the moon (more precise) is %.2f" % almanac.moon.moon_phase
    Fullness of the moon (more precise) is 1.70
    >>> print weeutil.timestamp_to_string(almanac.next_vernal_equinox)
    2010-03-20 10:32:10 PDT (1269106330)
    >>> print weeutil.timestamp_to_string(almanac.next_autumnal_equinox)
    2009-09-22 14:18:38 PDT (1253654318)
    >>> print weeutil.timestamp_to_string(almanac.next_summer_solstice)
    2009-06-20 22:45:40 PDT (1245563140)
    >>> print weeutil.timestamp_to_string(almanac.next_winter_solstice)
    2009-12-21 09:46:38 PST (1261417598)
    >>> print weeutil.timestamp_to_string(almanac.next_full_moon)
    2009-04-09 07:55:49 PDT (1239288949)
    >>> print weeutil.timestamp_to_string(almanac.next_new_moon)
    2009-04-24 20:22:33 PDT (1240629753)
    >>> print "Solar azimuth, altitude = (%.2f°, %.2f°)" % (almanac.sun.az, almanac.sun.alt)
    Solar azimuth, altitude = (154.14°, 44.02°)
    >>> print "Moon azimuth, altitude = (%.2f°, %.2f°)" % (almanac.moon.az, almanac.moon.alt)
    Moon azimuth, altitude = (133.55°, 47.89°)
    """
    def __init__(self, time_ts, lat, lon, altitude=0, moon_phases=Moon.moon_phases, timeformat="%H:%M"):
        self.lat = lat
        self.lon = lon
        self.altitude = altitude
        self.timeformat = timeformat
        self.date_tt = (0, 0, 0)

        self.moon_phases = moon_phases
        self.moon_phase = ''
        self.moon_fullness = None
        
        self.hasExtras = False
                
        self.setTime(time_ts)
        
    def setTime(self, time_ts):
        """Reset the observer's time for the almanac. 
        
        If the date differs from the previous date, then it will
        recalculate the astronomical data.
        
        """
        _newdate_tt = time.localtime(time_ts)
        if _newdate_tt[0:3] != self.date_tt[0:3] :

            (y,m,d) = _newdate_tt[0:3]
            (moon_index, _moon_fullness) = Moon.moon_phase(y, m, d)
            self.moon_phase = self.moon_phases[moon_index] if self.moon_phases is not None else ''
            
            # Check to see whether the user has module 'ephem'. If so, use it.
            if sys.modules.has_key('ephem'):
                
                # Set up the Observer object for our location:
                self.stn = ephem.Observer()
                self.stn.long = math.radians(self.lon)
                self.stn.lat  = math.radians(self.lat)
                self.stn.elev = self.altitude
                self.stn.date = self.time_j1899 = timestamp_to_j1899(time_ts)
                
                # Sun calculations:
                _sun = ephem.Sun()
                _sun.compute(self.stn)
                self.sun = BodyWrapper(_sun)
                
                # Moon calculations:
                _moon = ephem.Moon()
                _moon.compute(self.stn)
                self.moon = BodyWrapper(_moon)
                # This attribute is here for backwards compatiblity.
                # For full precision, use attribute moon.moon_phase
                self.moon_fullness = int(self.moon.moon_phase+0.5)
                
                self.hasExtras = True

            else:
                
                # No ephem package. Use the weeutil algorithms. Less accurate, but they get the
                # job done.
                (sunrise_utc, sunset_utc) = Sun.sunRiseSet(y, m, d, self.lon, self.lat)
                # The above function returns its results in UTC hours. Convert
                # to a local time tuple
                sunrise_tt = Almanac._adjustTime(y, m, d, sunrise_utc)
                sunset_tt  = Almanac._adjustTime(y, m, d, sunset_utc)
                self._sunrise = time.strftime(self.timeformat, sunrise_tt)
                self._sunset  = time.strftime(self.timeformat, sunset_tt)

                self.moon_fullness = _moon_fullness
            self.date_tt = _newdate_tt

    def __getattr__(self, attr):
        if attr in ['next_autumnal_equinox', 'next_vernal_equinox', 
                     'next_winter_solstice', 'next_summer_solstice',
                     'next_full_moon', 'next_new_moon']:
            j1899 = ephem.__dict__[attr](self.time_j1899)
            t = j1899_to_timestamp(j1899)
            return t
        elif attr in ['sunrise', 'sunset']:
            if self.hasExtras:
                # Unfortunately, sunrise and sunset have to be calculated dynamically when
                # using ephem because of its unfortunate design decision to change the
                # state of _sun. Hence, _sun has to be built and torn down every time.
                _sun = ephem.Sun()
                _sun.compute(self.stn)
                if attr == 'sunrise':
                    time_ephem = self.stn.next_rising(_sun)  # This stmt changes the state of _sun
                else:
                    time_ephem = self.stn.next_setting(_sun) # This one too
                time_tt = time.localtime(j1899_to_timestamp(time_ephem))
                return time.strftime(self.timeformat, time_tt)
            else:
                return self._sunrise if attr=='sunrise' else self._sunset
            
        
    @staticmethod
    def _adjustTime(y, m, d,  hrs_utc):
        """Converts from a UTC time to a local time.
        
        y,m,d: The year, month, day for which the conversion is desired.
        
        hrs_tc: Floating point number with the number of hours since midnight in UTC.
        
        Returns: A timetuple with the local time."""
        # Construct a time tuple with the time at midnight, UTC:
        daystart_utc_tt = (y,m,d,0,0,0,0,0,-1)
        # Convert the time tuple to a time stamp and add on the number of seconds since midnight:
        time_ts = int(calendar.timegm(daystart_utc_tt) + hrs_utc * 3600.0 + 0.5)
        # Convert to local time:
        time_local_tt = time.localtime(time_ts)
        return time_local_tt

class BodyWrapper(object):
    
    def __init__(self, body):
        self.body = body
        
    def __getattr__(self, attr):
        v = getattr(self.body, attr)
        if attr in ['az', 'alt', 'a_ra', 'a_dec', 'g_ra', 'ra', 'g_dec', 'dec', 
                     'elong', 'radius', 'hlong', 'hlat', 'sublat', 'sublong']:
            return math.degrees(v)
        elif attr=='moon_phase':
            return 100.0 * v
        else:
            return v

def timestamp_to_j1899(time_ts):
    """Convert from a unix time stamp to the number of days since 12/31/1899 12:00 UTC"""
    # The number 25567.5 is the start of the Unix epoch (1/1/1970). Just add on the
    # number of days since then
    return 25567.5 + time_ts/86400.0
    
def j1899_to_timestamp(j1899):
    """Convert from number of days since 12/31/1899 12:00 UTC to unix time stamp"""
    return (j1899-25567.5) * 86400.0
    
if __name__ == '__main__':
    
    import doctest
    import weeutil
            
    doctest.testmod()

