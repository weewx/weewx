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

#===============================================================================
#                 Architectural notes
#
# Unfortunately, sunrise and sunset have to be calculated dynamically when
# using ephem because of its unfortunate design decision to change the
# state of the body when calling next_rising() or next_setting(). This leads
# to some complications in the class BodyWrapper 
#===============================================================================
    
import calendar
import time
import sys

import Moon

# If the user has installed ephem, use it. Otherwise, fall back to the weeutil algorithms:
try:
    import ephem
    import math
except:
    import Sun

class Almanac(object):
    """Almanac data.
    
    time_ts: A timestamp within the date for which sunrise/sunset is desired.
    
    lat, lon: Location for which sunrise/sunset is desired.
    
    altitude: Elevation in **meters**. [Optional. Default is 0 (sea level)]
    
    temperature: The temperature in **degrees Celsius**. [Optional. Default is 15.0]
    
    pressure: The atmospheric pressure in **mBars**. [Optional. Default is 1010]
    
    moon_phases: An array of 8 strings with descriptions of the moon 
    phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]
    
    timeformat: A strftime style format to be used to format sunrise and sunset.
    [optional. If not given, then "%H:%M" will be used.
    
    ATTRIBUTES.
    
    As a minimum, the following attributes are available:
    
        sunrise: Time (local) upper limb of the sun rises above the horizon, formatted using the format 'timeformat'.
        sunset: Time (local) upper limb of the sun sinks below the horizon, formatted using the format 'timeformat'.
        moon_phase: A description of the moon phase(eg. "new moon", Waxing crescent", etc.)
        moon_fullness: Percent fullness of the moon (0=new moon, 100=full moon)

    If the module 'ephem' is used, many other attributes are available.
    
        sun.transit: Time of transit (sun over meridian)
        sun.previous_sunrise: Time of last sunrise
        sun.az: Azimuth (in degrees) of sun
        sun.alt: Altitude (in degrees) of sun
        mars.rise: Time of mars rising
        mars.ra: Right ascension of mars
        etc.
    
    EXAMPLES:
    
    >>> t = time.mktime((2009, 3, 27, 12, 0, 0, 0, 0, -1))
    >>> print weeutil.timestamp_to_string(t)
    2009-03-27 12:00:00 PDT (1238180400)
    >>> almanac = Almanac(t, 46.0, -122.0)
    
    Test backwards compatiblity with attributes 'sunrise' and 'sunset'
    >>> print "Sunrise, sunset:", almanac.sunrise, almanac.sunset
    Sunrise, sunset: 06:56 19:30

    Test backwards compatiblity with attribute 'moon_fullness':
    >>> print "Fullness of the moon (rounded) is %.2f%% [%s]" % (almanac.moon_fullness, almanac.moon_phase)
    Fullness of the moon (rounded) is 2.00% [new (totally dark)]
    
    Now get a more precise result for fullness of the moon:
    >>> print "Fullness of the moon (more precise) is %.2f" % almanac.moon.moon_phase
    Fullness of the moon (more precise) is 1.70

    Get sunrise, sun transit, and sunset using the new 'ephem' syntax:
    >>> print "Sunrise, sun transit, sunset:", almanac.sun.rise, almanac.sun.transit, almanac.sun.set
    Sunrise, sun transit, sunset: 06:56 13:13 19:30
    
    Do the same with the moon:
    >>> print "Moon rise, moon transit, moon set:", almanac.moon.rise, almanac.moon.transit, almanac.moon.set
    Moon rise, moon transit, moon set: 06:59 14:01 21:20

    Exercise equinox, solstice routines
    >>> print weeutil.timestamp_to_string(almanac.next_vernal_equinox)
    2010-03-20 10:32:10 PDT (1269106330)
    >>> print weeutil.timestamp_to_string(almanac.next_autumnal_equinox)
    2009-09-22 14:18:38 PDT (1253654318)
    >>> print weeutil.timestamp_to_string(almanac.next_summer_solstice)
    2009-06-20 22:45:40 PDT (1245563140)
    >>> print weeutil.timestamp_to_string(almanac.next_winter_solstice)
    2009-12-21 09:46:38 PST (1261417598)
    
    Exercise moon state routines
    >>> print weeutil.timestamp_to_string(almanac.next_full_moon)
    2009-04-09 07:55:49 PDT (1239288949)
    >>> print weeutil.timestamp_to_string(almanac.next_new_moon)
    2009-04-24 20:22:33 PDT (1240629753)
    
    Now location of the sun and moon
    >>> print "Solar azimuth, altitude = (%.2f, %.2f)" % (almanac.sun.az, almanac.sun.alt)
    Solar azimuth, altitude = (154.14, 44.02)
    >>> print "Moon azimuth, altitude = (%.2f, %.2f)" % (almanac.moon.az, almanac.moon.alt)
    Moon azimuth, altitude = (133.55, 47.89)
    """
    
    def __init__(self, time_ts, lat, lon, 
                 altitude=0, temperature=15.0, pressure=1010.0, 
                 moon_phases=Moon.moon_phases, timeformat="%H:%M"):
        self.lat = lat
        self.lon = lon
        self.altitude = altitude
        self.temperature = temperature
        self.pressure = pressure
        self.timeformat = timeformat
        self.date_tt = (0, 0, 0, 0, 0, 0)

        self.moon_phases = moon_phases
        self.moon_phase = ''
        self.moon_fullness = None
        
        self.hasExtras = False
                
        self.setTime(time_ts)
        
    def setTime(self, time_ts):
        """Reset the observer's time for the almanac. 
        
        If the time differs from the previous time, then it will
        recalculate the astronomical data."""
        _newdate_tt = time.localtime(time_ts)
        if _newdate_tt[0:6] != self.date_tt[0:6] :

            (y,m,d) = _newdate_tt[0:3]
            (moon_index, _moon_fullness) = Moon.moon_phase(y, m, d)
            self.moon_phase = self.moon_phases[moon_index] if self.moon_phases is not None else ''
            
            # Check to see whether the user has module 'ephem'. If so, use it.
            if sys.modules.has_key('ephem'):
                
                # Set up an observer object holding the location and time:
                stn = ephem.Observer()
                stn.long = math.radians(self.lon)
                stn.lat  = math.radians(self.lat)
                stn.elev = self.altitude
                stn.temp = self.temperature
                stn.pressure = self.pressure
                stn.date = self.time_j1899 = timestamp_to_j1899(time_ts)
                
                # Sun calculations:
                self.sun = BodyWrapper(ephem.Sun, stn, self.timeformat)    #@UndefinedVariable
                
                # Moon calculations:
                self.moon = BodyWrapper(ephem.Moon, stn, self.timeformat)
                
                # Venus calculations:
                self.venus = BodyWrapper(ephem.Venus, stn, self.timeformat) #@UndefinedVariable
                
                # Mars calculations:
                self.mars = BodyWrapper(ephem.Mars, stn, self.timeformat)   #@UndefinedVariable
                
                # Jupiter calculations:
                self.jupiter = BodyWrapper(ephem.Jupiter, stn, self.timeformat)
                
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
                
                self.hasExtras = False
                
            self.date_tt = _newdate_tt
    
    # Short cuts, used for backwards compatibility
    @property
    def sunrise(self):
        return self.sun.rise if self.hasExtras else self._sunrise
    @property
    def sunset(self):
        return self.sun.set if self.hasExtras else self._sunset

    def __getattr__(self, attr):
        if self.hasExtras and attr in ['next_autumnal_equinox', 'next_vernal_equinox', 
                                       'next_winter_solstice', 'next_summer_solstice',
                                       'next_full_moon', 'next_new_moon']:
            # This is how you call a function on an instance when all you have is its name:
            j1899 = ephem.__dict__[attr](self.time_j1899)   #@UndefinedVariable
            t = j1899_to_timestamp(j1899)
            return t
        else:
            raise AttributeError, "Unknown attribute "+attr
            
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

fn_map = {'rise'    : 'next_rising',
          'set'     : 'next_setting',
          'transit' : 'next_transit'}

class BodyWrapper(object):
    """This class wraps a celestial body. It returns results in degrees (instead of radians)
    and percent (instead of fractions). It also deals with the unfortunately side-effect
    of changing the state of the body with certain functions."""
    
    def __init__(self, body_factory, observer, timeformat="%H:%M"):
        """Initialize a wrapper
        
        body_factory: A function that returns an instance of the body
        to be wrapped. Example would be ephem.Sun
        
        observer: An instance of ephem.Observer, containing the observer's lat, lon, time, etc.
        
        timeformat: A strftime style format to be used to format sunrise and sunset.
        [optional. If not given, then "%H:%M" will be used.
        """
        self.body_factory = body_factory
        self.observer     = observer
        self.timeformat   = timeformat
        self.body = body_factory(observer)
        (y,m,d) = time.localtime(j1899_to_timestamp(observer.date))[0:3]
        self.sod_j1899 = timestamp_to_j1899(time.mktime((y,m,d,0,0,0,0,0,-1)))

    def __getattr__(self, attr):
        if attr in ['az', 'alt', 'a_ra', 'a_dec', 'g_ra', 'ra', 'g_dec', 'dec', 
                     'elong', 'radius', 'hlong', 'hlat', 'sublat', 'sublong']:
            # Return the results in degrees rather than radians
            v = getattr(self.body, attr)
            return math.degrees(v)
        elif attr=='moon_phase':
            # Return the result in percent
            v = getattr(self.body, attr)
            return 100.0 * v
        elif attr in ['next_rising', 'next_setting', 'next_transit', 'next_antitransit',
                      'previous_rising', 'previous_setting', 'previous_transit', 'previous_antitransit']:
            # These functions have the unfortunate side effect of changing the state of the body
            # being examined. So, create a temporary body and then throw it away
            temp_body = self.body_factory()
            time_j1899 = getattr(self.observer, attr)(temp_body)
            return j1899_to_string(time_j1899, self.timeformat)
        elif attr in ['rise', 'set', 'transit']:
            # These functions have the unfortunate side effect of changing the state of the body
            # being examined. So, create a temporary body and then throw it away
            temp_body = self.body_factory(self.observer)
            # Look up the function to be called for this attribute (eg, call 'next_rising' for 'rise')
            fn = fn_map[attr]
            time_j1899 = getattr(self.observer, fn)(temp_body, self.sod_j1899)
            return j1899_to_string(time_j1899, self.timeformat)
        else:
            return getattr(self.body, attr)

def timestamp_to_j1899(time_ts):
    """Convert from a unix time stamp to the number of days since 12/31/1899 12:00 UTC"""
    # The number 25567.5 is the start of the Unix epoch (1/1/1970). Just add on the
    # number of days since then
    return 25567.5 + time_ts/86400.0
    
def j1899_to_timestamp(j1899):
    """Convert from number of days since 12/31/1899 12:00 UTC to unix time stamp"""
    return (j1899-25567.5) * 86400.0
    
def j1899_to_string(j1899, timeformat="%H:%M"):
    time_tt = time.localtime(j1899_to_timestamp(j1899))
    return time.strftime(timeformat, time_tt)
    
if __name__ == '__main__':
    
    import doctest
    import weeutil   #@UnusedImport
            
    doctest.testmod()

