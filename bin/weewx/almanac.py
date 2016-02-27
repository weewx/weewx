#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Almanac data

This module can optionally use PyEphem, which offers high quality
astronomical calculations. See http://rhodesmill.org/pyephem. """

import time
import sys
import math
import copy

import weeutil.Moon
import weewx.units

# If the user has installed ephem, use it. Otherwise, fall back to the weeutil algorithms:
try:
    import ephem
except ImportError:
    import weeutil.Sun

# NB: Have Almanac inherit from 'object'. However, this will cause 
# an 'autocall' bug in Cheetah versions before 2.1.
class Almanac(object):
    """Almanac data.
    
    ATTRIBUTES.
    
    As a minimum, the following attributes are available:
    
        sunrise: Time (local) upper limb of the sun rises above the horizon, formatted using the format 'timeformat'.
        sunset: Time (local) upper limb of the sun sinks below the horizon, formatted using the format 'timeformat'.
        moon_phase: A description of the moon phase(eg. "new moon", Waxing crescent", etc.)
        moon_fullness: Percent fullness of the moon (0=new moon, 100=full moon)

    If the module 'ephem' is used, them many other attributes are available.
    Here are a few examples:
    
        sun.rise: Time upper limb of sun will rise above the horizon today in unix epoch time
        sun.transit: Time of transit today (sun over meridian) in unix epoch time
        sun.previous_sunrise: Time of last sunrise in unix epoch time
        sun.az: Azimuth (in degrees) of sun
        sun.alt: Altitude (in degrees) of sun
        mars.rise: Time when upper limb of mars will rise above horizon today in unix epoch time
        mars.ra: Right ascension of mars
        etc.
    
    EXAMPLES:
    
    These examples are designed to work in the Pacific timezone
    >>> import os
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> t = 1238180400
    >>> print timestamp_to_string(t)
    2009-03-27 12:00:00 PDT (1238180400)
    
    Test conversions to Dublin Julian Days
    >>> t_djd = timestamp_to_djd(t)
    >>> print "%.5f" % t_djd
    39898.29167
    
    Test the conversion back
    >>> print "%.0f" % djd_to_timestamp(t_djd)
    1238180400
    
    >>> almanac = Almanac(t, 46.0, -122.0)
    
    Test backwards compatibility with attribute 'moon_fullness':
    >>> print "Fullness of the moon (rounded) is %.2f%% [%s]" % (almanac.moon_fullness, almanac.moon_phase)
    Fullness of the moon (rounded) is 2.00% [new (totally dark)]
    
    Now get a more precise result for fullness of the moon:
    >>> print "Fullness of the moon (more precise) is %.2f%%" % almanac.moon.moon_fullness
    Fullness of the moon (more precise) is 1.70%

    Test backwards compatibility with attributes 'sunrise' and 'sunset'
    >>> print "Sunrise, sunset:", almanac.sunrise, almanac.sunset
    Sunrise, sunset: 06:56 19:30

    Get sunrise, sun transit, and sunset using the new 'ephem' syntax:
    >>> print "Sunrise, sun transit, sunset:", almanac.sun.rise, almanac.sun.transit, almanac.sun.set
    Sunrise, sun transit, sunset: 06:56 13:13 19:30
    
    Do the same with the moon:
    >>> print "Moon rise, transit, set:", almanac.moon.rise, almanac.moon.transit, almanac.moon.set
    Moon rise, transit, set: 06:59 14:01 21:20
    
    And Mars
    >>> print "Mars rise, transit, set:", almanac.mars.rise, almanac.mars.transit, almanac.moon.set
    Mars rise, transit, set: 06:08 11:34 21:20
    
    Finally, try a star
    >>> print "Rigel rise, transit, set:", almanac.rigel.rise, almanac.rigel.transit, almanac.rigel.set 
    Rigel rise, transit, set: 12:32 18:00 23:28

    Exercise equinox, solstice routines
    >>> print almanac.next_vernal_equinox
    20-Mar-2010 10:32
    >>> print almanac.next_autumnal_equinox
    22-Sep-2009 14:18
    >>> print almanac.next_summer_solstice
    20-Jun-2009 22:45
    >>> print almanac.previous_winter_solstice
    21-Dec-2008 04:03
    >>> print almanac.next_winter_solstice
    21-Dec-2009 09:46
    
    Exercise moon state routines
    >>> print almanac.next_full_moon
    09-Apr-2009 07:55
    >>> print almanac.next_new_moon
    24-Apr-2009 20:22
    >>> print almanac.next_first_quarter_moon
    02-Apr-2009 07:33
    
    Now location of the sun and moon
    >>> print "Solar azimuth, altitude = (%.2f, %.2f)" % (almanac.sun.az, almanac.sun.alt)
    Solar azimuth, altitude = (154.14, 44.02)
    >>> print "Moon azimuth, altitude = (%.2f, %.2f)" % (almanac.moon.az, almanac.moon.alt)
    Moon azimuth, altitude = (133.55, 47.89)
    
    Try a time and location where the sun is always up
    >>> t = 1371044003
    >>> print timestamp_to_string(t)
    2013-06-12 06:33:23 PDT (1371044003)
    >>> almanac = Almanac(t, 64.0, 0.0)
    >>> print almanac(horizon=-6).sun(use_center=1).rise
       N/A

    Try the pyephem "Naval Observatory" example.
    >>> t = 1252256400
    >>> print timestamp_to_gmtime(t)
    2009-09-06 17:00:00 UTC (1252256400)
    >>> atlanta = Almanac(t, 33.8, -84.4, pressure=0, horizon=-34.0/60.0)
    >>> # Print it in GMT, so it can easily be compared to the example:
    >>> print timestamp_to_gmtime(atlanta.sun.previous_rising.raw) 
    2009-09-06 11:14:56 UTC (1252235696)
    >>> print timestamp_to_gmtime(atlanta.moon.next_setting.raw)
    2009-09-07 14:05:29 UTC (1252332329)
    
    Now try the civil twilight examples:
    >>> print timestamp_to_gmtime(atlanta(horizon=-6).sun(use_center=1).previous_rising.raw)
    2009-09-06 10:49:40 UTC (1252234180)
    >>> print timestamp_to_gmtime(atlanta(horizon=-6).sun(use_center=1).next_setting.raw)
    2009-09-07 00:21:22 UTC (1252282882)

    Try sun rise again, to make sure the horizon value cleared:
    >>> print timestamp_to_gmtime(atlanta.sun.previous_rising.raw) 
    2009-09-06 11:14:56 UTC (1252235696)

    Try an attribute that does not explicitly appear in the class Almanac
    >>> print "%.3f" % almanac.mars.sun_distance
    1.494

    Try a specialized attribute for Jupiter
    >>> print almanac.jupiter.cmlI
    191:16:58.0

    Should fail if applied to a different body
    >>> print almanac.venus.cmlI
    Traceback (most recent call last):
        ...
    AttributeError: 'Venus' object has no attribute 'cmlI'
    
    Try a nonsense body:
    >>> x = almanac.bar.rise
    Traceback (most recent call last):
        ...
    KeyError: 'Bar'
    
    Try a nonsense tag:
    >>> x = almanac.sun.foo
    Traceback (most recent call last):
        ...
    AttributeError: 'Sun' object has no attribute 'foo'
    """
    
    def __init__(self, time_ts, lat, lon,
                 altitude=None,
                 temperature=None,
                 pressure=None,
                 horizon=None,
                 moon_phases=weeutil.Moon.moon_phases,
                 formatter=weewx.units.Formatter()):
        """Initialize an instance of Almanac

        time_ts: A unix epoch timestamp with the time of the almanac. If None, the
        present time will be used.
        
        lat, lon: Observer's location in degrees.
        
        altitude: Observer's elevation in **meters**. [Optional. Default is 0 (sea level)]
        
        temperature: Observer's temperature in **degrees Celsius**. [Optional. Default is 15.0]
        
        pressure: Observer's atmospheric pressure in **mBars**. [Optional. Default is 1010]
        
        horizon: Angle of the horizon in degrees [Optional. Default is zero]
        
        moon_phases: An array of 8 strings with descriptions of the moon 
        phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]
        
        formatter: An instance of weewx.units.Formatter() with the formatting information
        to be used.
        """
        self.time_ts      = time_ts if time_ts else time.time()
        self.time_djd     = timestamp_to_djd(self.time_ts)
        self.lat          = lat
        self.lon          = lon
        self.altitude     = altitude if altitude is not None else 0.0
        self.temperature  = temperature if temperature is not None else 15.0
        self.pressure     = pressure if pressure is not None else 1010.0
        self.horizon      = horizon if horizon is not None else 0.0
        self.moon_phases  = moon_phases
        self.formatter    = formatter

        (y,m,d) = time.localtime(self.time_ts)[0:3]
        (self.moon_index, self._moon_fullness) = weeutil.Moon.moon_phase(y, m, d)
        self.moon_phase = self.moon_phases[self.moon_index]
            
        # Check to see whether the user has module 'ephem'. 
        if 'ephem' in sys.modules:
            
            self.hasExtras = True

        else:
            
            # No ephem package. Use the weeutil algorithms, which supply a minimum of functionality
            (sunrise_utc_h, sunset_utc_h) = weeutil.Sun.sunRiseSet(y, m, d, self.lon, self.lat)
            sunrise_ts = weeutil.weeutil.utc_to_ts(y, m, d, sunrise_utc_h)
            sunset_ts  = weeutil.weeutil.utc_to_ts(y, m, d, sunset_utc_h)
            self._sunrise = weewx.units.ValueHelper((sunrise_ts, "unix_epoch", "group_time"), 
                                                    context="ephem_day", formatter=self.formatter)
            self._sunset  = weewx.units.ValueHelper((sunset_ts,  "unix_epoch", "group_time"), 
                                                    context="ephem_day", formatter=self.formatter)
            self.hasExtras = False            

    # Shortcuts, used for backwards compatibility
    @property
    def sunrise(self):
        return self.sun.rise if self.hasExtras else self._sunrise
    @property
    def sunset(self):
        return self.sun.set if self.hasExtras else self._sunset
    @property
    def moon_fullness(self):
        return int(self.moon.moon_fullness+0.5) if self.hasExtras else self._moon_fullness
    
    def __call__(self, **kwargs):
        """Call an almanac object as a functor. This allows overriding the values
        used when the Almanac instance was initialized.
        
        Named arguments:
        
            almanac_time: The observer's time in unix epoch time.
            lat: The observer's latitude in degrees
            lon: The observer's longitude in degrees
            altitude: The observer's altitude in meters
            horizon: The horizon angle in degrees
            temperature: The observer's temperature (used to calculate refraction)
            pressure: The observer's pressure (used to calculate refraction) 
        """
        # Make a copy of myself.       
        almanac = copy.copy(self)
        # Now set a new value for any named arguments.
        for key in kwargs:
            if 'almanac_time' in kwargs:
                almanac.time_ts = kwargs['almanac_time']
                almanac.time_djd = timestamp_to_djd(self.time_ts)
            else:
                setattr(almanac, key, kwargs[key])

        return almanac
        
    def __getattr__(self, attr):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if attr.startswith('__') or attr == 'has_key':
            raise AttributeError(attr)
        
        if not self.hasExtras:
            # If the Almanac does not have extended capabilities, we can't
            # do any of the following. Raise an exception.
            raise AttributeError("Unknown attribute %s" % attr)

        # We do have extended capability. Check to see if the attribute is a calendar event:
        elif attr in ['previous_equinox', 'next_equinox', 
                      'previous_solstice', 'next_solstice',
                      'previous_autumnal_equinox', 'next_autumnal_equinox', 
                      'previous_vernal_equinox', 'next_vernal_equinox', 
                      'previous_winter_solstice', 'next_winter_solstice', 
                      'previous_summer_solstice', 'next_summer_solstice',
                      'previous_new_moon', 'next_new_moon',
                      'previous_first_quarter_moon', 'next_first_quarter_moon',
                      'previous_full_moon', 'next_full_moon',
                      'previous_last_quarter_moon', 'next_last_quarter_moon']:
            # This is how you call a function on an instance when all you have
            # is the function's name as a string
            djd = getattr(ephem, attr)(self.time_djd)
            return weewx.units.ValueHelper((djd, "dublin_jd", "group_time"), 
                                           context="ephem_year", formatter=self.formatter)
        else:
            # It's not a calendar event. The attribute must be a heavenly body
            # (such as 'sun', or 'jupiter'). Bind the almanac and the heavenly body
            # together and return as an AlmanacBinder
            return AlmanacBinder(self, attr)

fn_map = {'rise'    : 'next_rising',
          'set'     : 'next_setting',
          'transit' : 'next_transit'}

class AlmanacBinder(object):
    """This class binds the observer properties held in Almanac, with the heavenly
    body to be observed."""
    
    def __init__(self, almanac, heavenly_body):
        # Transfer all values over
        self.time_ts      = almanac.time_ts
        self.time_djd     = almanac.time_djd
        self.lat          = almanac.lat
        self.lon          = almanac.lon
        self.altitude     = almanac.altitude
        self.temperature  = almanac.temperature
        self.pressure     = almanac.pressure
        self.horizon      = almanac.horizon
        self.moon_phases  = almanac.moon_phases
        self.moon_phase   = almanac.moon_phase
        self.formatter    = almanac.formatter

        # Calculate and store the start-of-day in Dublin Julian Days. 
#        self.sod_djd = timestamp_to_djd(weeutil.weeutil.startOfDay(self.time_ts))
        (y,m,d) = time.localtime(self.time_ts)[0:3]
        self.sod_djd = timestamp_to_djd(time.mktime((y,m,d,0,0,0,0,0,-1)))

        self.heavenly_body= heavenly_body
        self.use_center   = False
        
    def __call__(self, use_center=False):
        self.use_center = use_center
        return self
    
    def __getattr__(self, attr):
        """Get the requested observation, such as when the body will rise."""

        if attr.startswith('__'):
            raise AttributeError(attr)
        
        # Many of these functions have the unfortunate side effect of changing the state of the body
        # being examined. So, create a temporary body and then throw it away
        ephem_body = _get_ephem_body(self.heavenly_body)
        
        if attr in ['rise', 'set', 'transit']:
            # These verbs refer to the time the event occurs anytime in the day, which
            # is not necessarily the *next* sunrise.
            attr = fn_map[attr]
            # These functions require the time at the start of day
            observer = self._get_observer(self.sod_djd)
            # Call the function. Be prepared to catch an exception if the body is always up.
            try:
                if attr in ['next_rising', 'next_setting']:
                    time_djd = getattr(observer, attr)(ephem_body, use_center=self.use_center)
                else:
                    time_djd = getattr(observer, attr)(ephem_body)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                time_djd = None
            return weewx.units.ValueHelper((time_djd, "dublin_jd", "group_time"), context="ephem_day", formatter=self.formatter)
        
        elif attr in ['next_rising', 'next_setting', 'next_transit', 'next_antitransit',
                      'previous_rising', 'previous_setting', 'previous_transit', 'previous_antitransit']:
            # These functions require the time of the observation
            observer = self._get_observer(self.time_djd)
            # Call the function. Be prepared to catch an exception if the body is always up.
            try:
                if attr in ['next_rising', 'next_setting', 'previous_rising', 'previous_setting']:
                    time_djd = getattr(observer, attr)(ephem_body, use_center=self.use_center)
                else:
                    time_djd = getattr(observer, attr)(ephem_body)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                time_djd = None
            return weewx.units.ValueHelper((time_djd, "dublin_jd", "group_time"), context="ephem_day", formatter=self.formatter)
        else:
            # These functions need the current time in Dublin Julian Days
            observer = self._get_observer(self.time_djd)
            ephem_body.compute(observer)
            if attr in ['az', 'alt', 'a_ra', 'a_dec', 'g_ra', 'ra', 'g_dec', 'dec', 
                        'elong', 'radius', 'hlong', 'hlat', 'sublat', 'sublong']:
                # Return the results in degrees rather than radians
                return math.degrees(getattr(ephem_body, attr))
            elif attr=='moon_fullness':
                # The attribute "moon_fullness" is the percentage of the moon surface that is illuminated.
                # Unfortunately, phephem calls it "moon_phase", so call ephem with that name.
                # Return the result in percent.
                return 100.0 * ephem_body.moon_phase
            else:
                # Just return the result unchanged. This will raise an AttributeError exception
                # if the attribute does not exist.
                return getattr(ephem_body, attr)
        
    def _get_observer(self, time_ts):
        # Build an ephem Observer object
        observer           = ephem.Observer()
        observer.lat       = math.radians(self.lat)
        observer.long      = math.radians(self.lon)
        observer.elevation = self.altitude
        observer.horizon   = math.radians(self.horizon)
        observer.temp      = self.temperature
        observer.pressure  = self.pressure
        observer.date      = time_ts
        return observer
        
def _get_ephem_body(heavenly_body):
    # The library 'ephem' refers to heavenly bodies using a capitalized
    # name. For example, the module used for 'mars' is 'ephem.Mars'.
    cap_name = heavenly_body.capitalize() 
    
    # If the heavenly body is a star, or if the body does not exist, then an
    # exception will be raised. Be prepared to catch it.
    try:
        ephem_body = getattr(ephem, cap_name)()
    except AttributeError:
        # That didn't work. Try a star. If this doesn't work either,
        # then a KeyError exception will be raised.
        ephem_body = ephem.star(cap_name)

    return ephem_body

def timestamp_to_djd(time_ts):
    """Convert from a unix time stamp to the number of days since 12/31/1899 12:00 UTC
    (aka "Dublin Julian Days")"""
    # The number 25567.5 is the start of the Unix epoch (1/1/1970). Just add on the
    # number of days since then
    return 25567.5 + time_ts/86400.0
    
def djd_to_timestamp(djd):
    """Convert from number of days since 12/31/1899 12:00 UTC ("Dublin Julian Days") to unix time stamp"""
    return (djd-25567.5) * 86400.0

if __name__ == '__main__':
    
    def dummy_no_ephem():
        """Final test that does not use ephem.
        
        First, get rid of 'ephem':
        >>> p = sys.modules.pop('ephem')
        
        Now do the rest as before:
        >>> import os
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> t = 1238180400
        >>> print timestamp_to_string(t)
        2009-03-27 12:00:00 PDT (1238180400)
        >>> almanac = Almanac(t, 46.0, -122.0)
        
        Use "_sunrise" to make sure we're getting the results from weeutil (not ephem):
        >>> print "Sunrise, sunset:", almanac._sunrise, almanac._sunset
        Sunrise, sunset: 06:56 19:30"""
    
    import doctest
    from weeutil.weeutil import timestamp_to_string, timestamp_to_gmtime  #@UnusedImport

    if not doctest.testmod().failed:
        print("PASSED")
