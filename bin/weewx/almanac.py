#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Almanac data

This module can optionally use PyEphem, which offers high quality
astronomical calculations. See http://rhodesmill.org/pyephem. """

from __future__ import absolute_import
from __future__ import print_function
import time
import sys
import math
import copy

import weeutil.Moon
import weewx.units
from weewx.units import ValueTuple

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
    
    These examples require pyephem to be installed.
    >>> if "ephem" not in sys.modules:
    ...   raise KeyboardInterrupt("Almanac examples require 'pyephem'")

    These examples are designed to work in the Pacific timezone
    >>> import os
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time.tzset()
    >>> from weeutil.weeutil import timestamp_to_string, timestamp_to_gmtime
    >>> t = 1238180400
    >>> print(timestamp_to_string(t))
    2009-03-27 12:00:00 PDT (1238180400)
    
    Test conversions to Dublin Julian Days
    >>> t_djd = timestamp_to_djd(t)
    >>> print("%.5f" % t_djd)
    39898.29167
    
    Test the conversion back
    >>> print("%.0f" % djd_to_timestamp(t_djd))
    1238180400
    
    >>> almanac = Almanac(t, 46.0, -122.0, formatter=weewx.units.get_default_formatter())
    
    Test backwards compatibility with attribute 'moon_fullness':
    >>> print("Fullness of the moon (rounded) is %.2f%% [%s]" % (almanac._moon_fullness, almanac.moon_phase))
    Fullness of the moon (rounded) is 3.00% [new (totally dark)]

    Now get a more precise result for fullness of the moon:
    >>> print("Fullness of the moon (more precise) is %.2f%%" % almanac.moon.moon_fullness)
    Fullness of the moon (more precise) is 1.70%

    Test backwards compatibility with attributes 'sunrise' and 'sunset'
    >>> print("Sunrise, sunset: %s, %s" % (almanac.sunrise, almanac.sunset))
    Sunrise, sunset: 06:56:36, 19:30:41

    Get sunrise, sun transit, and sunset using the new 'ephem' syntax:
    >>> print("Sunrise, sun transit, sunset: %s, %s, %s" % (almanac.sun.rise, almanac.sun.transit, almanac.sun.set))
    Sunrise, sun transit, sunset: 06:56:36, 13:13:13, 19:30:41
    
    Do the same with the moon:
    >>> print("Moon rise, transit, set: %s, %s, %s" % (almanac.moon.rise, almanac.moon.transit, almanac.moon.set))
    Moon rise, transit, set: 06:59:14, 14:01:57, 21:20:06
    
    And Mars
    >>> print("Mars rise, transit, set: %s, %s, %s" % (almanac.mars.rise, almanac.mars.transit, almanac.mars.set))
    Mars rise, transit, set: 06:08:57, 11:34:13, 17:00:04
    
    Finally, try a star
    >>> print("Rigel rise, transit, set: %s, %s, %s" % (almanac.rigel.rise, almanac.rigel.transit, almanac.rigel.set))
    Rigel rise, transit, set: 12:32:33, 18:00:38, 23:28:43

    Exercise sidereal time
    >>> print("%.4f" % almanac.sidereal_time)
    348.3400

    Exercise equinox, solstice routines
    >>> print(almanac.next_vernal_equinox)
    03/20/10 10:32:11
    >>> print(almanac.next_autumnal_equinox)
    09/22/09 14:18:39
    >>> print(almanac.next_summer_solstice)
    06/20/09 22:45:40
    >>> print(almanac.previous_winter_solstice)
    12/21/08 04:03:36
    >>> print(almanac.next_winter_solstice)
    12/21/09 09:46:38
    
    Exercise moon state routines
    >>> print(almanac.next_full_moon)
    04/09/09 07:55:49
    >>> print(almanac.next_new_moon)
    04/24/09 20:22:33
    >>> print(almanac.next_first_quarter_moon)
    04/02/09 07:33:42
    
    Now location of the sun and moon
    >>> print("Solar azimuth, altitude = (%.2f, %.2f)" % (almanac.sun.az, almanac.sun.alt))
    Solar azimuth, altitude = (154.14, 44.02)
    >>> print("Moon azimuth, altitude = (%.2f, %.2f)" % (almanac.moon.az, almanac.moon.alt))
    Moon azimuth, altitude = (133.55, 47.89)
    
    Try a time and location where the sun is always up
    >>> t = 1371044003
    >>> print(timestamp_to_string(t))
    2013-06-12 06:33:23 PDT (1371044003)
    >>> almanac = Almanac(t, 64.0, 0.0)
    >>> print(almanac(horizon=-6).sun(use_center=1).rise)
    N/A

    Try the pyephem "Naval Observatory" example.
    >>> t = 1252256400
    >>> print(timestamp_to_gmtime(t))
    2009-09-06 17:00:00 UTC (1252256400)
    >>> atlanta = Almanac(t, 33.8, -84.4, pressure=0, horizon=-34.0/60.0)
    >>> # Print it in GMT, so it can easily be compared to the example:
    >>> print(timestamp_to_gmtime(atlanta.sun.previous_rising.raw))
    2009-09-06 11:14:56 UTC (1252235696)
    >>> print(timestamp_to_gmtime(atlanta.moon.next_setting.raw))
    2009-09-07 14:05:29 UTC (1252332329)
    
    Now try the civil twilight examples:
    >>> print(timestamp_to_gmtime(atlanta(horizon=-6).sun(use_center=1).previous_rising.raw))
    2009-09-06 10:49:40 UTC (1252234180)
    >>> print(timestamp_to_gmtime(atlanta(horizon=-6).sun(use_center=1).next_setting.raw))
    2009-09-07 00:21:22 UTC (1252282882)

    Try sun rise again, to make sure the horizon value cleared:
    >>> print(timestamp_to_gmtime(atlanta.sun.previous_rising.raw))
    2009-09-06 11:14:56 UTC (1252235696)

    Try an attribute that does not explicitly appear in the class Almanac
    >>> print("%.3f" % almanac.mars.sun_distance)
    1.494

    Try a specialized attribute for Jupiter
    >>> print(almanac.jupiter.cmlI)
    191:16:58.0

    Should fail if applied to a different body
    >>> print(almanac.venus.cmlI)
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
                 formatter=None,
                 converter=None):
        """Initialize an instance of Almanac

        Args:

            time_ts (int): A unix epoch timestamp with the time of the almanac. If None, the
            present time will be used.

            lat (float): Observer's latitude in degrees.

            lon (float): Observer's longitude in degrees.

            altitude: (float) Observer's elevation in **meters**. [Optional. Default is 0 (sea level)]

            temperature (float): Observer's temperature in **degrees Celsius**. [Optional. Default is 15.0]

            pressure (float): Observer's atmospheric pressure in **mBars**. [Optional. Default is 1010]

            horizon (float): Angle of the horizon in degrees [Optional. Default is zero]

            moon_phases (list): An array of 8 strings with descriptions of the moon
            phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]

            formatter (weewx.units.Formatter): An instance of weewx.units.Formatter() with the formatting information
            to be used.

            converter (weewx.units.Converter): An instance of weewx.units.Converter with the conversion information to be used.
        """
        self.time_ts = time_ts if time_ts else time.time()
        self.lat = lat
        self.lon = lon
        self.altitude = altitude if altitude is not None else 0.0
        self.temperature = temperature if temperature is not None else 15.0
        self.pressure = pressure if pressure is not None else 1010.0
        self.horizon = horizon if horizon is not None else 0.0
        self.moon_phases = moon_phases
        self.formatter = formatter or weewx.units.Formatter()
        self.converter = converter or weewx.units.Converter()
        self._precalc()

    def _precalc(self):
        """Precalculate local variables."""
        self.moon_index, self._moon_fullness = weeutil.Moon.moon_phase_ts(self.time_ts)
        self.moon_phase = self.moon_phases[self.moon_index]
        self.time_djd = timestamp_to_djd(self.time_ts)

        # Check to see whether the user has module 'ephem'. 
        if 'ephem' in sys.modules:

            self.hasExtras = True

        else:

            # No ephem package. Use the weeutil algorithms, which supply a minimum of functionality
            (y, m, d) = time.localtime(self.time_ts)[0:3]
            (sunrise_utc_h, sunset_utc_h) = weeutil.Sun.sunRiseSet(y, m, d, self.lon, self.lat)
            sunrise_ts = weeutil.weeutil.utc_to_ts(y, m, d, sunrise_utc_h)
            sunset_ts = weeutil.weeutil.utc_to_ts(y, m, d, sunset_utc_h)
            self._sunrise = weewx.units.ValueHelper(
                ValueTuple(sunrise_ts, "unix_epoch", "group_time"),
                context="ephem_day",
                formatter=self.formatter,
                converter=self.converter)
            self._sunset = weewx.units.ValueHelper(
                ValueTuple(sunset_ts, "unix_epoch", "group_time"),
                context="ephem_day",
                formatter=self.formatter,
                converter=self.converter)
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
        return int(self.moon.moon_fullness + 0.5) if self.hasExtras else self._moon_fullness

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
            if key == 'almanac_time':
                almanac.time_ts = kwargs['almanac_time']
            else:
                setattr(almanac, key, kwargs[key])
        almanac._precalc()

        return almanac

    def separation(self, body1, body2):
        return ephem.separation(body1, body2)

    def __getattr__(self, attr):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if attr.startswith('__') or attr == 'has_key':
            raise AttributeError(attr)

        if not self.hasExtras:
            # If the Almanac does not have extended capabilities, we can't
            # do any of the following. Raise an exception.
            raise AttributeError("Unknown attribute %s" % attr)

        # We do have extended capability. Check to see if the attribute is a calendar event:
        elif attr in {'previous_equinox', 'next_equinox',
                      'previous_solstice', 'next_solstice',
                      'previous_autumnal_equinox', 'next_autumnal_equinox',
                      'previous_vernal_equinox', 'next_vernal_equinox',
                      'previous_winter_solstice', 'next_winter_solstice',
                      'previous_summer_solstice', 'next_summer_solstice',
                      'previous_new_moon', 'next_new_moon',
                      'previous_first_quarter_moon', 'next_first_quarter_moon',
                      'previous_full_moon', 'next_full_moon',
                      'previous_last_quarter_moon', 'next_last_quarter_moon'}:
            # This is how you call a function on an instance when all you have
            # is the function's name as a string
            djd = getattr(ephem, attr)(self.time_djd)
            return weewx.units.ValueHelper(ValueTuple(djd, "dublin_jd", "group_time"),
                                           context="ephem_year",
                                           formatter=self.formatter,
                                           converter=self.converter)
        # Check to see if the attribute is sidereal time
        elif attr == 'sidereal_time':
            # sidereal time is obtained from an ephem Observer method, first get
            # an Observer object
            observer = _get_observer(self, self.time_djd)
            # Then call the method returning the result in degrees
            return math.degrees(getattr(observer, attr)())
        else:
            # The attribute must be a heavenly body (such as 'sun', or 'jupiter').
            # Bind the almanac and the heavenly body together and return as an
            # AlmanacBinder
            return AlmanacBinder(self, attr)


fn_map = {'rise': 'next_rising',
          'set': 'next_setting',
          'transit': 'next_transit'}


class AlmanacBinder(object):
    """This class binds the observer properties held in Almanac, with the heavenly
    body to be observed."""

    def __init__(self, almanac, heavenly_body):
        self.almanac = almanac

        # Calculate and store the start-of-day in Dublin Julian Days. 
        y, m, d = time.localtime(self.almanac.time_ts)[0:3]
        self.sod_djd = timestamp_to_djd(time.mktime((y, m, d, 0, 0, 0, 0, 0, -1)))

        self.heavenly_body = heavenly_body
        self.use_center = False

    def __call__(self, use_center=False):
        self.use_center = use_center
        return self

    @property
    def visible(self):
        """Calculate how long the body has been visible today"""
        ephem_body = _get_ephem_body(self.heavenly_body)
        observer = _get_observer(self.almanac, self.sod_djd)
        try:
            time_rising_djd = observer.next_rising(ephem_body, use_center=self.use_center)
            time_setting_djd = observer.next_setting(ephem_body, use_center=self.use_center)
        except ephem.AlwaysUpError:
            visible = 86400
        except ephem.NeverUpError:
            visible = 0
        else:
            visible = (time_setting_djd - time_rising_djd) * weewx.units.SECS_PER_DAY

        return weewx.units.ValueHelper(ValueTuple(visible, "second", "group_deltatime"),
                                       context="short_delta",
                                       formatter=self.almanac.formatter,
                                       converter=self.almanac.converter)

    def visible_change(self, days_ago=1):
        """Change in visibility of the heavenly body compared to 'days_ago'."""
        # Visibility for today:
        today_visible = self.visible
        # The time to compare to
        then_time = self.almanac.time_ts - days_ago * 86400
        # Get a new almanac, set up for the time back then
        then_almanac = self.almanac(almanac_time=then_time)
        # Find the visibility back then
        then_visible = getattr(then_almanac, self.heavenly_body).visible
        # Take the difference
        diff = today_visible.raw - then_visible.raw
        return weewx.units.ValueHelper(ValueTuple(diff, "second", "group_deltatime"),
                                       context="brief_delta",
                                       formatter=self.almanac.formatter,
                                       converter=self.almanac.converter)

    def __getattr__(self, attr):
        """Get the requested observation, such as when the body will rise."""

        # Don't try any attributes that start with a double underscore, or any of these
        # special names: they are used by the Python language:
        if attr.startswith('__') or attr in ['mro', 'im_func', 'func_code']:
            raise AttributeError(attr)

        # Many of these functions have the unfortunate side effect of changing the state of the body
        # being examined. So, create a temporary body and then throw it away
        ephem_body = _get_ephem_body(self.heavenly_body)

        if attr in ['rise', 'set', 'transit']:
            # These verbs refer to the time the event occurs anytime in the day, which
            # is not necessarily the *next* sunrise.
            attr = fn_map[attr]
            # These functions require the time at the start of day
            observer = _get_observer(self.almanac, self.sod_djd)
            # Call the function. Be prepared to catch an exception if the body is always up.
            try:
                if attr in ['next_rising', 'next_setting']:
                    time_djd = getattr(observer, attr)(ephem_body, use_center=self.use_center)
                else:
                    time_djd = getattr(observer, attr)(ephem_body)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                time_djd = None
            return weewx.units.ValueHelper(ValueTuple(time_djd, "dublin_jd", "group_time"),
                                           context="ephem_day",
                                           formatter=self.almanac.formatter,
                                           converter=self.almanac.converter)

        elif attr in {'next_rising', 'next_setting', 'next_transit', 'next_antitransit',
                      'previous_rising', 'previous_setting', 'previous_transit',
                      'previous_antitransit'}:
            # These functions require the time of the observation
            observer = _get_observer(self.almanac, self.almanac.time_djd)
            # Call the function. Be prepared to catch an exception if the body is always up.
            try:
                if attr in ['next_rising', 'next_setting', 'previous_rising', 'previous_setting']:
                    time_djd = getattr(observer, attr)(ephem_body, use_center=self.use_center)
                else:
                    time_djd = getattr(observer, attr)(ephem_body)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                time_djd = None
            return weewx.units.ValueHelper(ValueTuple(time_djd, "dublin_jd", "group_time"),
                                           context="ephem_day",
                                           formatter=self.almanac.formatter,
                                           converter=self.almanac.converter)

        else:
            # These functions need the current time in Dublin Julian Days
            observer = _get_observer(self.almanac, self.almanac.time_djd)
            ephem_body.compute(observer)
            if attr in {'az', 'alt', 'a_ra', 'a_dec', 'g_ra', 'ra', 'g_dec', 'dec',
                        'elong', 'radius', 'hlong', 'hlat', 'sublat', 'sublong'}:
                # Return the results in degrees rather than radians
                return math.degrees(getattr(ephem_body, attr))
            elif attr == 'moon_fullness':
                # The attribute "moon_fullness" is the percentage of the moon surface that is illuminated.
                # Unfortunately, phephem calls it "moon_phase", so call ephem with that name.
                # Return the result in percent.
                return 100.0 * ephem_body.moon_phase
            else:
                # Just return the result unchanged. This will raise an AttributeError exception
                # if the attribute does not exist.
                return getattr(ephem_body, attr)


def _get_observer(almanac_obj, time_ts):
    # Build an ephem Observer object
    observer = ephem.Observer()
    observer.lat = math.radians(almanac_obj.lat)
    observer.long = math.radians(almanac_obj.lon)
    observer.elevation = almanac_obj.altitude
    observer.horizon = math.radians(almanac_obj.horizon)
    observer.temp = almanac_obj.temperature
    observer.pressure = almanac_obj.pressure
    observer.date = time_ts
    return observer


def _get_ephem_body(heavenly_body):
    # The library 'ephem' refers to heavenly bodies using a capitalized
    # name. For example, the module used for 'mars' is 'ephem.Mars'.
    cap_name = heavenly_body.title()

    # If the heavenly body is a star, or if the body does not exist, then an
    # exception will be raised. Be prepared to catch it.
    try:
        ephem_body = getattr(ephem, cap_name)()
    except AttributeError:
        # That didn't work. Try a star. If this doesn't work either,
        # then a KeyError exception will be raised.
        ephem_body = ephem.star(cap_name)
    except TypeError:
        # Heavenly bodies added by a ephem.readdb() statement are not functions.
        # So, just return the attribute, without calling it:
        ephem_body = getattr(ephem, cap_name)

    return ephem_body


def timestamp_to_djd(time_ts):
    """Convert from a unix time stamp to the number of days since 12/31/1899 12:00 UTC
    (aka "Dublin Julian Days")"""
    # The number 25567.5 is the start of the Unix epoch (1/1/1970). Just add on the
    # number of days since then
    return 25567.5 + time_ts / 86400.0


def djd_to_timestamp(djd):
    """Convert from number of days since 12/31/1899 12:00 UTC ("Dublin Julian Days") to
    unix time stamp"""
    return (djd - 25567.5) * 86400.0


if __name__ == '__main__':

    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
