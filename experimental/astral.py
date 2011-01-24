# Copyright 2009-2010, Simon Kennedy, python@sffjunkie.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Heavily modified from the original by Simon Kennedy to distill it
down to just the astronomical calculations.

All of the city data has been deleted.

-Tom Keffer 1/17/2011
"""

import datetime
import time
from math import cos, sin, tan, acos, asin, atan2, floor, radians, degrees

__version__ = "0.3+"
__author__ = "Simon Kennedy <python@sffjunkie.co.uk>"

class AstralError(Exception):
    """Thrown for astronomical exceptions."""
    
solar_depression = {'civil': 6.0, 'nautical': 12.0, 'astronomical': 18.0}

#===============================================================================
#                          Public functions
#===============================================================================

def dawn(date, latitude, longitude, depression, tzinfo=None):
    """Calculate dawn time for a specific date at a particular position.
    
    Returns datetime.datetime object
    """
    
    julianday = _julianday(date.day, date.month, date.year)

    if latitude > 89.8:
        latitude = 89.8
        
    if latitude < -89.8:
        latitude = -89.8
    
    t = _jday_to_jcentury(julianday)
    eqtime = _eq_of_time(t)
    solarDec = _sun_declination(t)
    
    try:
        hourangle = _hour_angle_sunrise(latitude, solarDec)
    except:
        raise AstralError('Sun remains below horizon on this day, at this location.')

    delta = longitude - degrees(hourangle)
    timeDiff = 4.0 * delta
    timeUTC = 720.0 + timeDiff - eqtime

    newt = _jday_to_jcentury(_jcentury_to_jday(t) + timeUTC / 1440.0)
    eqtime = _eq_of_time(newt)
    solarDec = _sun_declination(newt)
    hourangle = _hour_angle_dawn(latitude, solarDec, depression)
    delta = longitude - degrees(hourangle)
    timeDiff = 4 * delta
    timeUTC = 720 + timeDiff - eqtime
    
    timeUTC = timeUTC/60.0
    hour = int(timeUTC)
    minute = int((timeUTC - hour) * 60)
    second = int((((timeUTC - hour) * 60) - minute) * 60)

    if hour > 23:
        hour -= 24
        date += datetime.timedelta(days=1)

    dawn = datetime.datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=tzinfo)

    return dawn

def sunrise(date, latitude, longitude, tzinfo=None):
    """Calculate sunrise time for a specific date at a particular position.
    
    Returns datetime.datetime object
    """
    
    julianday = _julianday(date.day, date.month, date.year)

    t = _jday_to_jcentury(julianday)
    eqtime = _eq_of_time(t)
    solarDec = _sun_declination(t)

    try:
        hourangle = _hour_angle_sunrise(latitude, solarDec)
    except:
        raise AstralError('Sun remains below horizon on this day, at this location.')

    delta = longitude - degrees(hourangle)
    timeDiff = 4.0 * delta
    timeUTC = 720.0 + timeDiff - eqtime

    newt = _jday_to_jcentury(_jcentury_to_jday(t) + timeUTC / 1440.0)
    eqtime = _eq_of_time(newt)
    solarDec = _sun_declination(newt)
    hourangle = _hour_angle_sunrise(latitude, solarDec)
    delta = longitude - degrees(hourangle)
    timeDiff = 4 * delta
    timeUTC = 720 + timeDiff - eqtime
    
    timeUTC = timeUTC/60.0
    hour = int(timeUTC)
    minute = int((timeUTC - hour) * 60)
    second = int((((timeUTC - hour) * 60) - minute) * 60)

    if hour > 23:
        hour -= 24
        date += datetime.timedelta(days=1)

    sunrise = datetime.datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=tzinfo)

    return sunrise

def solar_noon(date, longitude, tzinfo=None):
    """Calculate solar noon time for a specific date at a particular position.
    
    Returns datetime.datetime
    """
    
    julianday = _julianday(date.day, date.month, date.year)

    newt = _jday_to_jcentury(julianday + 0.5 + longitude / 360.0)

    eqtime = _eq_of_time(newt)
    solarNoonDec = _sun_declination(newt)
    timeUTC = 720.0 + (longitude * 4.0) - eqtime

    timeUTC = timeUTC/60.0
    hour = int(timeUTC)
    minute = int((timeUTC - hour) * 60)
    second = int((((timeUTC - hour) * 60) - minute) * 60)

    if hour > 23:
        hour -= 24
        date += datetime.timedelta(days=1)

    noon = datetime.datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=tzinfo)

    return noon

def sunset(date, latitude, longitude, tzinfo=None):
    """Calculate sunset time for a specific date at a particular position.
    
    Returns datetime.datetime
    """
    
    julianday = _julianday(date.day, date.month, date.year)

    t = _jday_to_jcentury(julianday)
    eqtime = _eq_of_time(t)
    solarDec = _sun_declination(t)

    try:
        hourangle = _hour_angle_sunset(latitude, solarDec)
    except:
        raise AstralError('Sun remains below horizon on this day, at this location.')

    delta = longitude - degrees(hourangle)
    timeDiff = 4.0 * delta
    timeUTC = 720.0 + timeDiff - eqtime

    newt = _jday_to_jcentury(_jcentury_to_jday(t) + timeUTC / 1440.0)
    eqtime = _eq_of_time(newt)
    solarDec = _sun_declination(newt)
    hourangle = _hour_angle_sunset(latitude, solarDec)
    delta = longitude - degrees(hourangle)
    timeDiff = 4 * delta
    timeUTC = 720 + timeDiff - eqtime
    
    timeUTC = timeUTC/60.0
    hour = int(timeUTC)
    minute = int((timeUTC - hour) * 60)
    second = int((((timeUTC - hour) * 60) - minute) * 60)

    if hour > 23:
        hour -= 24
        date += datetime.timedelta(days=1)

    sunset = datetime.datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=tzinfo)

    return sunset

def dusk(date, latitude, longitude, depression, tzinfo=None):
    """Calculate dusk time for a specific date at a particular position.
    
    Returns datetime.datetime
    """
    
    julianday = _julianday(date.day, date.month, date.year)

    if latitude > 89.8:
        latitude = 89.8
        
    if latitude < -89.8:
        latitude = -89.8
    
    t = _jday_to_jcentury(julianday)
    eqtime = _eq_of_time(t)
    solarDec = _sun_declination(t)

    try:
        hourangle = _hour_angle_sunset(latitude, solarDec)
    except:
        raise AstralError('Sun remains below horizon on this day, at this location.')

    delta = longitude - degrees(hourangle)
    timeDiff = 4.0 * delta
    timeUTC = 720.0 + timeDiff - eqtime

    newt = _jday_to_jcentury(_jcentury_to_jday(t) + timeUTC / 1440.0)
    eqtime = _eq_of_time(newt)
    solarDec = _sun_declination(newt)
    hourangle = _hour_angle_dusk(latitude, solarDec, depression)
    delta = longitude - degrees(hourangle)
    timeDiff = 4 * delta
    timeUTC = 720 + timeDiff - eqtime
    
    timeUTC = timeUTC/60.0
    hour = int(timeUTC)
    minute = int((timeUTC - hour) * 60)
    second = int((((timeUTC - hour) * 60) - minute) * 60)

    if hour > 23:
        hour -= 24
        date += datetime.timedelta(days=1)

    dusk = datetime.datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=tzinfo)

    return dusk

def rahukaalam(date, latitude, longitude, tzinfo=None):
    """Calculate ruhakaalam times at a particular location.
    """
    
    if date is None:
        date = datetime.date.today()

    sunrise = sunrise(date, latitude, longitude, tzinfo)
    sunset  = sunset(date, latitude, longitude, tzinfo)
    
    octant_duration = (sunset - sunrise) / 8

    # Mo,Sa,Fr,We,Th,Tu,Su
    octant_index = [1,6,4,5,3,2,7]
    
    weekday = date.weekday()
    octant = octant_index[weekday]
    
    start = sunrise + (octant_duration * octant)
    end = start + octant_duration
    
    return (start, end)


def solar_position(ts, latitude, longitude):
    """Calculate the azimuth and elevation of the sun at a specific time and location.
    
    ts:           Timestamp in unix epoch time for which the sun's position is desired
    latitude:     Latitude
    longitude:    Longitude
    
    returns:    A 2-way tuple (azimuth, elevation)
    
    Example:
    
    >>> ts = time.mktime((2011,1,17,12,0,0,0,0,-1))
        
    >>> print "Azimuth = %.2f; Elevation = %.2f" % solar_position(ts,  45.0, -122.0)
    Azimuth = 175.36; Elevation = 24.22
    >>> print "Azimuth = %.2f; Elevation = %.2f" % solar_position(ts,  45.0,  122.0)
    >>> print "Azimuth = %.2f; Elevation = %.2f" % solar_position(ts, -45.0,  122.0)
    >>> print "Azimuth = %.2f; Elevation = %.2f" % solar_position(ts, -45.0, -122.0)

    """

    if latitude > 89.8:
        latitude = 89.8
        
    if latitude < -89.8:
        latitude = -89.8
    
#    # Convert from Unix epoch time to Julian Date
    JD = ts / 86400 + 2440587.5
    t = _jday_to_jcentury(JD)
    solarDec = _sun_declination(t)
    eqtime   = _eq_of_time(t)
    
    #print "Eqn of time=", eqtime
    
    gm_time = time.gmtime(ts)
    
    gm_hour = gm_time.tm_hour + gm_time.tm_min/60 + gm_time.tm_sec
    ha = 15*(gm_hour-12.0) + longitude

    hourangle = ha + eqtime/4.0

    #print "hour angle = ", hourangle
    harad = radians(hourangle)

    csz = sin(radians(latitude)) * sin(radians(solarDec)) + \
          cos(radians(latitude)) * cos(radians(solarDec)) * cos(harad)

    if csz > 1.0:
        csz = 1.0
    elif csz < -1.0:
        csz = -1.0
    
    zenith = degrees(acos(csz))

    azDenom = (cos(radians(latitude)) * sin(radians(zenith)))
    
    if (abs(azDenom) > 0.001):
        azRad = ((sin(radians(latitude)) *  cos(radians(zenith))) - sin(radians(solarDec))) / azDenom
        
        if abs(azRad) > 1.0:
            if azRad < 0:
                azRad = -1.0
            else:
                azRad = 1.0

        azimuth = 180.0 - degrees(acos(azRad))

        if hourangle > 0.0:
            azimuth = -azimuth
    else:
        if latitude > 0.0:
            azimuth = 180.0
        else:
            azimuth = 0#

    if azimuth < 0.0:
        azimuth = azimuth + 360.0
             
    exoatmElevation = 90.0 - zenith

    if exoatmElevation > 85.0:
        refractionCorrection = 0.0
    else:
        te = tan(radians(exoatmElevation))
        if exoatmElevation > 5.0:
            refractionCorrection = 58.1 / te - 0.07 / (te * te * te) + 0.000086 / (te * te * te * te * te)
        elif exoatmElevation > -0.575:
            step1 = (-12.79 + exoatmElevation * 0.711)
            step2 = (103.4 + exoatmElevation * (step1))
            step3 = (-518.2 + exoatmElevation * (step2))
            refractionCorrection = 1735.0 + exoatmElevation * (step3)
        else:
            refractionCorrection = -20.774 / te

        refractionCorrection = refractionCorrection / 3600.0
        
    solarzen = zenith - refractionCorrection
                 
    solarelevation = 90.0 - solarzen
    
    return (azimuth, solarelevation)

#===============================================================================
#                       (Private) helper functions
#===============================================================================

def _julianday(day, month, year):
    if month <= 2:
        year = year - 1
        month = month + 12
    
    A = floor(year / 100.0)
    B = 2 - A + floor(A / 4.0)

    return floor(365.25 * (year + 4716)) + floor(30.6001 * (month + 1)) + day + B - 1524.5
    
def _jday_to_jcentury(julianday):
    return (julianday - 2451545.0) / 36525.0

def _jcentury_to_jday(juliancentury):
    return (juliancentury * 36525.0) + 2451545.0

def _mean_obliquity_of_ecliptic(juliancentury):
    seconds = 21.448 - juliancentury * (46.815 + juliancentury * (0.00059 - juliancentury * (0.001813)))
    return 23.0 + (26.0 + (seconds / 60.0)) / 60.0

def _obliquity_correction(juliancentury):
    e0 = _mean_obliquity_of_ecliptic(juliancentury)

    omega = 125.04 - 1934.136 * juliancentury
    return e0 + 0.00256 * cos(radians(omega))

def _geom_mean_long_sun(juliancentury):
    l0 = 280.46646 + juliancentury * (36000.76983 + 0.0003032 * juliancentury)
    return l0 % 360.0
    
def _eccentricity_earth_orbit(juliancentury):
    return 0.016708634 - juliancentury * (0.000042037 + 0.0000001267 * juliancentury)
    
def _geom_mean_anomaly_sun(juliancentury):
    return 357.52911 + juliancentury * (35999.05029 - 0.0001537 * juliancentury)

def _eq_of_time(juliancentury):
    epsilon = _obliquity_correction(juliancentury)
    l0 = _geom_mean_long_sun(juliancentury)
    e  = _eccentricity_earth_orbit(juliancentury)
    m  = _geom_mean_anomaly_sun(juliancentury)

    y = tan(radians(epsilon) / 2.0)
    y = y * y

    sin2l0 = sin(2.0 * radians(l0))
    sinm = sin(radians(m))
    cos2l0 = cos(2.0 * radians(l0))
    sin4l0 = sin(4.0 * radians(l0))
    sin2m = sin(2.0 * radians(m))

    Etime = y * sin2l0 - 2.0 * e * sinm + 4.0 * e * y * sinm * cos2l0 - \
            0.5 * y * y * sin4l0 - 1.25 * e * e * sin2m

    return degrees(Etime) * 4.0

def _sun_eq_of_center(juliancentury):
    m = _geom_mean_anomaly_sun(juliancentury)

    mrad = radians(m)
    sinm = sin(mrad)
    sin2m = sin(mrad + mrad)
    sin3m = sin(mrad + mrad + mrad)

    c = sinm * (1.914602 - juliancentury * (0.004817 + 0.000014 * juliancentury)) + \
        sin2m * (0.019993 - 0.000101 * juliancentury) + sin3m * 0.000289
        
    return c

def _sun_true_long(juliancentury):
    l0 = _geom_mean_long_sun(juliancentury)
    c = _sun_eq_of_center(juliancentury)

    return l0 + c

def _sun_apparent_long(juliancentury):
    O = _sun_true_long(juliancentury)

    omega = 125.04 - 1934.136 * juliancentury
    return O - 0.00569 - 0.00478 * sin(radians(omega))

def _sun_declination(juliancentury):
    e = _obliquity_correction(juliancentury)
    lambd = _sun_apparent_long(juliancentury)

    sint = sin(radians(e)) * sin(radians(lambd))
    return degrees(asin(sint))

def _hour_angle(latitude, solar_dec, solar_depression):
    latRad = radians(latitude)
    sdRad = radians(solar_dec)

    HA = (acos(cos(radians(90 + solar_depression)) / (cos(latRad) * cos(sdRad)) - tan(latRad) * tan(sdRad)))
    
    return HA

def _hour_angle_sunrise(latitude, solar_dec):
    return _hour_angle(latitude, solar_dec, 0.833)
    
def _hour_angle_sunset(latitude, solar_dec):
    return -_hour_angle(latitude, solar_dec, 0.833)

def _hour_angle_dawn(latitude, solar_dec, solar_depression):
    return _hour_angle(latitude, solar_dec, solar_depression)

def _hour_angle_dusk(latitude, solar_dec, solar_depression):
    return -_hour_angle(latitude, solar_dec, solar_depression)

def _sun_true_anomoly(juliancentury):
    m = _geom_mean_anomaly_sun(juliancentury)
    c = _sun_eq_of_center(juliancentury)

    return m + c

def _sun_rad_vector(juliancentury):
    v = _sun_true_anomoly(juliancentury)
    e = _eccentricity_earth_orbit(juliancentury)

    return (1.000001018 * (1 - e * e)) / (1 + e * cos(radians(v)))

def _sun_rt_ascension(juliancentury):
    e = _obliquity_correction(juliancentury)
    lambd = _sun_apparent_long(juliancentury)

    tananum = (cos(radians(e)) * sin(radians(lambd)))
    tanadenom = (cos(radians(lambd)))

    return degrees(atan2(tananum, tanadenom))

if __name__ == "__main__":

#    ts = time.mktime((2011,1,17,12,0,0,0,0,-1))
#    print "Time stamp = ", ts, time.localtime(ts)
#    
#    (az_alt, elv_alt) = solar_position(ts, 45.0, -122.0)
#    print "Azimuth using simple method  =", az_alt
#    print "Elevation using simple method=", elv_alt
#    # Elevation should be 24.21

    import doctest
    doctest.testmod()
    
