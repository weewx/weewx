#
#    Copyright (c) 2009, 2011, 2012 Tom Keffer <tkeffer@gmail.com>
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

import calendar
import time
import sys
import math

import weeutil.Moon
import weewx.units

# If the user has installed ephem, use it. Otherwise, fall back to the weeutil algorithms:
try:
    import ephem
except ImportError:
    import weeutil.Sun

# NB: In order to avoid an 'autocall' bug in Cheetah versions before 2.1,
# this class must not be a "new-style" class.
class Almanac():
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
    
    EXAMPLES (note that these will only work in the Pacific Time Zone)
    
    >>> t = 1238180400
    >>> print timestamp_to_string(t)
    2009-03-27 12:00:00 PDT (1238180400)
    >>> almanac = Almanac(t, 46.0, -122.0)
    
    Test backwards compatibility with attribute 'moon_fullness':
    >>> print "Fullness of the moon (rounded) is %.2f%% [%s]" % (almanac.moon_fullness, almanac.moon_phase)
    Fullness of the moon (rounded) is 2.00% [new (totally dark)]
    
    Now get a more precise result for fullness of the moon:
    >>> print "Fullness of the moon (more precise) is %.2f%%" % almanac.moon.moon_phase
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
    
    Try the pyephem "Naval Observatory" example.
    >>> t = 1252252800
    >>> print timestamp_to_gmtime(t)
    2009-09-06 16:00:00 UTC (1252252800)
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
    """
    
    def __init__(self, time_ts, lat, lon,
                 altitude=None,     # Use 'None' in case a bad value is passed in
                 temperature=None,  #  "
                 pressure=None,     #  "
                 horizon=None,      #  "
                 moon_phases=weeutil.Moon.moon_phases,
                 formatter=weewx.units.Formatter()):
        """Initialize an instance of Almanac

        time_ts: A unix epoch timestamp for which the almanac will be current.
        
        lat, lon: Observer's location
        
        altitude: Observer's elevation in **meters**. [Optional. Default is 0 (sea level)]
        
        temperature: Observer's temperature in **degrees Celsius**. [Optional. Default is 15.0]
        
        pressure: Observer's atmospheric pressure in **mBars**. [Optional. Default is 1010]
        
        horizon: Angle of the horizon in degrees [Optional. Default is zero]
        
        moon_phases: An array of 8 strings with descriptions of the moon 
        phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]
        
        formatter: An instance of weewx.units.Formatter() with the formatting information
        to be used.
        """
        self.time_ts      = time_ts
        self.time_djd     = timestamp_to_djd(time_ts)
        self.lat          = lat
        self.lon          = lon
        self.altitude     = altitude if altitude is not None else 0.0
        self.temperature  = temperature if temperature is not None else 15.0
        self.pressure     = pressure if pressure is not None else 1010.0
        self.horizon      = horizon if horizon is not None else 0.0
        self.moon_phases  = moon_phases
        self.formatter    = formatter

        (y,m,d) = time.localtime(time_ts)[0:3]
        (self.moon_index, self._moon_fullness) = weeutil.Moon.moon_phase(y, m, d)
        self.moon_phase = self.moon_phases[self.moon_index]
            
        # Check to see whether the user has module 'ephem'. 
        if 'ephem' in sys.modules:
            
            self.hasExtras = True

        else:
            
            # No ephem package. Use the weeutil algorithms, which supply a minimum of functionality
            (sunrise_utc, sunset_utc) = weeutil.Sun.sunRiseSet(y, m, d, self.lon, self.lat)
            # The above function returns its results in UTC hours. Convert
            # to a local time tuple
            sunrise_tt = weeutil.weeutil.utc_to_local_tt(y, m, d, sunrise_utc)
            sunset_tt  = weeutil.weeutil.utc_to_local_tt(y, m, d, sunset_utc)
            self._sunrise = time.strftime("%H:%M", sunrise_tt)
            self._sunset  = time.strftime("%H:%M", sunset_tt)

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
        return int(self.moon.moon_phase+0.5) if self.hasExtras else self._moon_fullness

    # What follows is a bit of Python wizardry to allow syntax such as:
    #   almanac(horizon=-0.5).sun.rise
    def __call__(self, **kwargs):
        """Call an almanac object as a functor. This allows overriding the values
        used when the Almanac instance was initialized.
        
        Named arguments:

        Any named arguments will be passed on to the initializer of the ObserverBinder,
        overriding any default values. These are all optional:
        
            almanac_time: The observer's time in unix epoch time.
            lat: The observer's latitude in degrees
            lon: The observer's longitude in degrees
            altitude: The observer's altitude in meters
            horizon: The horizon angle in degrees
            temperature: The observer's temperature (used to calculate refraction)
            pressure: The observer's pressure (used to calculate refraction) 
        """
        
        # Using an encapsulated class allows easy access to the default values
        class ObserverBinder(object):
            
            # Use the default values provided by the outer class (Almanac):
            def __init__(self, almanac_time=self.time_ts, lat=self.lat, lon=self.lon, 
                         altitude=self.altitude, horizon=self.horizon, temperature=self.temperature, 
                         pressure=self.pressure, formatter=self.formatter):
                # Build an ephem Observer object
                self.observer         = ephem.Observer()
                self.observer.date    = timestamp_to_djd(almanac_time)
                self.observer.lat     = math.radians(lat)
                self.observer.long    = math.radians(lon)
                self.observer.elev    = altitude
                self.observer.horizon = math.radians(horizon)
                self.observer.temp    = temperature
                self.observer.pressure= pressure
                
                self.formatter = formatter

            def __getattr__(self, body):
                """Return a BodyWrapper that binds the observer to a heavenly body.
                
                If there is no such body an exception of type AttributeError will
                be raised.
                
                body: A heavenly body. Examples, 'sun', 'moon', 'jupiter'
                
                Returns:
                An instance of a BodyWrapper. It will bind together the heavenly
                body (an instance of something like ephem.Jupiter) and the observer
                (an instance of ephem.Observer)
                """
                # Find the module used by pyephem. For example, the module used for
                # 'mars' is 'ephem.Mars'. If there is no such module, an exception
                # of type AttributeError will get thrown.
                ephem_module = getattr(ephem, body.capitalize())
                # Now, together with the observer object, return an
                # appropriate BodyWrapper
                return BodyWrapper(ephem_module, self.observer, self.formatter)

        # This will override the default values with any explicit parameters in kwargs:
        return ObserverBinder(**kwargs)
                
    def __getattr__(self, attr):
        
        if not self.hasExtras:
            # If the Almanac does not have extended capabilities, we can't
            # do any of the following. Raise an exception.
            raise AttributeError, "Unknown attribute %s" % attr

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
            # (such as 'sun', or 'jupiter'). Create an instance of
            # ObserverBinder by calling the __call__ function in Almanac, but
            # with no parameters
            binder = self()
            # Now try getting the body as an attribute. If successful, an
            # instance of BodyWrapper will be returned. If not, an exception of
            # type AttributeError will be raised.
            return getattr(binder, attr)
            
fn_map = {'rise'    : 'next_rising',
          'set'     : 'next_setting',
          'transit' : 'next_transit'}

class BodyWrapper(object):
    """This class wraps a celestial body. It returns results in degrees (instead of radians)
    and percent (instead of fractions). For times, it returns the results as a ValueHelper.
    It also deals with the unfortunate design decision in pyephem to change
    the state of the celestial body when using it as an argument in certain functions."""
    
    def __init__(self, body_factory, observer, formatter):
        """Initialize a wrapper
        
        body_factory: A function that returns an instance of the body
        to be wrapped. Example would be ephem.Sun
        
        observer: An instance of ephem.Observer, containing the observer's lat, lon, time, etc.
        
        formatter: An instance of weewx.units.Formatter(), containing the formatting
        to be used for times.
        """
        self.body_factory = body_factory
        self.observer     = observer
        self.formatter    = formatter
        self.body = body_factory(observer)
        self.use_center = False
        
        # Calculate and store the start-of-day in Dublin Julian Days:
        (y,m,d) = time.localtime(djd_to_timestamp(observer.date))[0:3]
        self.sod_djd = timestamp_to_djd(time.mktime((y,m,d,0,0,0,0,0,-1)))

    def __call__(self, use_center=False):
        self.use_center = use_center
        return self
    
    def __getattr__(self, attr):
        if attr in ['az', 'alt', 'a_ra', 'a_dec', 'g_ra', 'ra', 'g_dec', 'dec', 
                     'elong', 'radius', 'hlong', 'hlat', 'sublat', 'sublong']:
            # Return the results in degrees rather than radians
            return math.degrees(getattr(self.body, attr))
        elif attr=='moon_phase':
            # Return the result in percent
            return 100.0 * self.body.moon_phase
        elif attr in ['next_rising', 'next_setting', 'next_transit', 'next_antitransit',
                      'previous_rising', 'previous_setting', 'previous_transit', 'previous_antitransit']:
            # These functions have the unfortunate side effect of changing the state of the body
            # being examined. So, create a temporary body and then throw it away
            temp_body = self.body_factory()
            time_djd = getattr(self.observer, attr)(temp_body, use_center=self.use_center)
            return weewx.units.ValueHelper((time_djd, "dublin_jd", "group_time"), context="ephem_day", formatter=self.formatter)
        elif attr in fn_map:
            # These attribute names have to be mapped to a different function name. Like the
            # attributes above, they also have the side effect of changing the state of the body.
            # Finally, they return the time of the event anywhere in the day (not just the next
            # event), so they take a second argument in the function call.
            temp_body = self.body_factory(self.observer)
            # Look up the function to be called for this attribute (eg, call 'next_rising' for 'rise')
            fn = fn_map[attr]
            # Call the function, with a second argument giving the start-of-day
            time_djd = getattr(self.observer, fn)(temp_body, self.sod_djd)
            return weewx.units.ValueHelper((time_djd, "dublin_jd", "group_time"), context="ephem_day", formatter=self.formatter)
        else:
            # Just return the result unchanged.
            return getattr(self.body, attr)

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
    import doctest
    from weeutil.weeutil import timestamp_to_string, timestamp_to_gmtime  #@UnusedImport
            
    doctest.testmod()
