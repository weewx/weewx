#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Routines for astronomical calculations.

These calculations were taken from the NASA spreadsheet explained at

  http://www.srrb.noaa.gov/highlights/sunrise/calcdetails.html

and available as an Excel spreadsheet at:

  http://www.srrb.noaa.gov/highlights/sunrise/NOAA_Solar_Calculations_year.xls
  
Most of the test calculations are done for the date 17-Jan-2011, local time 12
Noon, in the Pacific Standard Time Zone (UTC-8). For something like sunrise,
which will actually happen a few hours earlier than noon, that means these
calculations are necessarily an approximation.

"""

import math

def jd_from_timestamp(time_ts):
    """Julian day from a unix time epoch.
    
    Example, find the Julian Day of 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Julian Day: %.4f" % jd_from_timestamp(time_ts)
    Julian Day: 2455579.3333
    """
    return 2440587.5 + time_ts / 86400.0

def j2000_from_timestamp(time_ts):
    """Convert unix epoch timestamp to the number of centuries since J2000.0
    
    Example, find the J2000 Julian century of 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "J2000: %.8f" % j2000_from_timestamp(time_ts)
    J2000: 0.11045403
    """
    return (jd_from_timestamp(time_ts)-2451545.0)/36525.0
    
def j2000_from_jd(jd):
    """Convert from the Julian Day to the number of centuries since J2000.0"""
    
    return (jd-2451545.0)/36525.0

def jd_from_j2000(jc):
    """Convert from the number of centuries since J2000.0 to the Julian day."""
    
    return jc * 36525.0 + 2451545.0
    
def geom_mean_long_sun(jc):
    """Given the julian century, find the mean longitude of the sun in degrees
    
    jc: Julian century
    
    Returns: Geometric mean longitude of the Sun in degrees
    
    Example, find the mean longitude of the sun at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Mean longitude of the sun: %.4f" % geom_mean_long_sun(j2000_from_timestamp(time_ts))
    Mean longitude of the sun: 296.8965
    """
    return (280.46646 + jc*(36000.76983 + jc*0.0003032)) % 360.0

def geom_mean_anom_sun(jc):
    """Given the julian century, find the mean longitude of the sun in degrees
    
    jc: Julian century
    
    Returns: Geometric mean anomaly of the Sun in degrees
    
    Example, find mean anomaly of the sun at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Mean anomaly of the sun: %.3f" % geom_mean_anom_sun(j2000_from_timestamp(time_ts))
    Mean anomaly of the sun: 4333.769
    """
    return 357.52911 + jc*(35999.05029 - 0.0001536*jc)

def earth_eccentricity(jc):
    """Given the julian century, find the unitless eccentricity of the Earth's orbit
    
    jc: Julian century
    
    Returns: the Earth's eccentricity
    
    Example, find the Earth's eccentricity at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Eccentricity of the earth's orbit: %.6f" % earth_eccentricity(j2000_from_timestamp(time_ts))
    Eccentricity of the earth's orbit: 0.016702
    """
    return 0.016708634 - jc*(0.000042037+0.0001537*jc)

def sun_eq_of_center(jc):
    """Given the Julian Century, find the equation of the center of the sun
    
    jc: Julian century
    
    Returns: The equation of the center of the sun
    
    Example, find the Sun's Eqn of Center at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Equation of center: %.6f" % sun_eq_of_center(j2000_from_timestamp(time_ts))
    Equation of center: 0.464999
    """
    gmas = geom_mean_anom_sun(jc)    
    return math.sin(math.radians(gmas))*(1.914602-jc*(0.004817+0.000014*jc))+math.sin(math.radians(2*gmas))*(0.019993-0.000101*jc)+math.sin(math.radians(3*gmas))*0.000289

def sun_true_long(jc):
    """Given the Julian Century, find the Sun's true longitude.
    
    Example, find the Sun's true longitude at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's true longitude: %.4f" % sun_true_long(j2000_from_timestamp(time_ts))
    The Sun's true longitude: 297.3615
    """
    return geom_mean_long_sun(jc) + sun_eq_of_center(jc)

def sun_true_anom(jc):
    """Given the Julian Century, find the Sun's true anomaly.
    
    Example, find the Sun's true anomaly at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's true longitude: %.3f" % sun_true_anom(j2000_from_timestamp(time_ts))
    The Sun's true longitude: 4334.234
    """
    return geom_mean_anom_sun(jc) + sun_eq_of_center(jc)

def sun_rad_vector(jc):
    """Given the Julian Century, find the Sun's radius vector in AUs.
    
    Example, find the Sun's radius vector at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's radius vector: %.6f" % sun_rad_vector(j2000_from_timestamp(time_ts))
    The Sun's radius vector: 0.983795
    """
    ec = earth_eccentricity(jc)
    return (1.000001018 * (1.0 - ec*ec)) / (1.0 + ec * math.cos(math.radians(sun_true_anom(jc))))

def sun_apparent_long(jc):
    """Given the Julian Century, find the Sun's apparent longitude
    
    Example, find the Sun's apparent longiutde at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's apparent longitude: %.4f" % sun_apparent_long(j2000_from_timestamp(time_ts))
    The Sun's apparent longitude: 297.3606
    """
    return sun_true_long(jc) - 0.00569 - 0.00478 * math.sin(math.radians(125.04-1934.136*jc))

def mean_obliquity_ecliptic(jc):
    """Given the Julian Century, find the mean obliquity of the ecliptic.
    
    Example, find the mean obliquity of the ecliptic at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The obliquity of the ecliptic: %.5f" % mean_obliquity_ecliptic(j2000_from_timestamp(time_ts))
    The obliquity of the ecliptic: 23.43785
    """
    return 23.0 + (26.0 + ((21.448 - jc*(46.815+jc*(0.00059-jc*0.001813))))/60.0)/60.0

def obliquity_correction(jc):
    """Given the Julian Century, find the obliquity correction in degrees
    
    Example, find the obliquity correction at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The obliquity correction: %.5f" % obliquity_correction(j2000_from_timestamp(time_ts))
    The obliquity correction: 23.43792
    """
    return mean_obliquity_ecliptic(jc) + 0.00256 * math.cos(math.radians(125.04 - 1934.136*jc))

def sun_right_ascension(jc):
    """Given the Julian Century, find the right ascension of the Sun in degrees.
    
    Example, find the Sun's right ascension at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's right ascension: %.4f" % sun_right_ascension(j2000_from_timestamp(time_ts))
    The Sun's right ascension: 150.5764
    """
    oc = obliquity_correction(jc)
    sal = sun_apparent_long(jc)
    return math.degrees(math.atan2(math.cos(math.radians(sal)), 
                                   math.cos(math.radians(oc))*math.sin(math.radians(sal))))

def sun_declination(jc):
    """Given the Julian Century, find the declination of the Sun in degrees.
    
    Example, find the Sun's declination at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The Sun's declination: %.4f" % sun_declination(j2000_from_timestamp(time_ts))
    The Sun's declination: -20.6868
    """
    oc = obliquity_correction(jc)
    sal = sun_apparent_long(jc)
    return math.degrees(math.asin(math.sin(math.radians(oc)) * math.sin(math.radians(sal))))


def equation_of_time(jc):
    """Given the Julian Century, find the equation of time in minutes
    
    Example, find the Equation of Time at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The equation of time is: %.5f" % equation_of_time(j2000_from_timestamp(time_ts))
    The equation of time is: -10.11117
    """
    # To keep the transcription from the spreadsheet straight, the letter before the underscore
    # is the column number in the original spreadsheet: 
    r_oc = obliquity_correction(jc)
    x = math.tan(math.radians(r_oc/2.0))
    u_vy =  x**2
    i_gmls = geom_mean_long_sun(jc)
    k_ec = earth_eccentricity(jc)
    j_gmas = geom_mean_anom_sun(jc)
    eot = 4.0*math.degrees(u_vy*math.sin(2.0*math.radians(i_gmls))-2.0*k_ec*math.sin(math.radians(j_gmas))\
                           + 4.0 *  k_ec*u_vy*math.sin(    math.radians(j_gmas)) * math.cos(2.0*math.radians(i_gmls))\
                           - 0.5 *  u_vy*u_vy*math.sin(4.0*math.radians(i_gmls))\
                           - 1.25 * k_ec*k_ec*math.sin(2.0*math.radians(j_gmas)))
    return eot

def ha_sunrise(jc, latitude):
    """Given the Julian Century and the latitude, find the hour angle of sunrise in degrees
    
    Example, find the hour angle of sunrise at 45.0 latitude at 1/17/2011 2000 UTC.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "The hour angle of sunrise is: %.5f" % ha_sunrise(j2000_from_timestamp(time_ts), 45.0)
    The hour angle of sunrise is: 69.16806
    """
    t_sd = sun_declination(jc)
    return math.degrees(math.acos(math.cos(math.radians(90.833))/(math.cos(math.radians(latitude)) * math.cos(math.radians(t_sd)))\
                                  - math.tan(math.radians(latitude))*math.tan(math.radians(t_sd))))

def solar_noon(jc, longitude, timezone):
    """
    Given a J2000 time, longitude, and timezone, find the solar noon/
    
    jc: The time in Julian centuries since J2000.0
    
    longitude: The longitude (west longitude is negative)
    
    timezone: Timezone relative to GMT (eg, PST is -8)
    
    Returns: Time of solar noon in days
    
    Example: Find solar noon for the longitude 122W on 1/17/2011
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> sn_days = solar_noon(j2000_from_timestamp(time_ts), -122.0, -8.0)
    >>> secs = sn_days * 86400
    >>> h = int(secs/3600.0)
    >>> secs %= 3600.0
    >>> m = int(secs/60.0)
    >>> secs = int(round(secs % 60))
    >>> print "Solar noon is at %.5f (%s)" %(sn_days, datetime.time(h,m,secs))
    Solar noon is at 0.51258 (12:18:07)
    """

    return (720.0 - 4.0*longitude - equation_of_time(jc) + timezone * 60) / 1440.0

def sunrise(jc, latitude, longitude, timezone):
    """
    Given a J2000 time, latitude, longitude, and timezone, find the sunrise.
    
    jc: The time in Julian centuries since J2000.0
    
    latitude: The latitude
    
    longitude: The longitude (west longitude is negative)
    
    timezone: Timezone relative to GMT (eg, PST is -8)
    
    Returns: Time of sunrise in days
    
    Example: Find sunrise for the longitude 122W on 1/17/2011
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> sn_days = sunrise(j2000_from_timestamp(time_ts), 45.0, -122.0, -8.0)
    >>> secs = sn_days * 86400
    >>> h = int(secs/3600.0)
    >>> secs %= 3600.0
    >>> m = int(secs/60.0)
    >>> secs = int(round(secs % 60))
    >>> print "Sunrise is at %.5f (%s)" %(sn_days, datetime.time(h,m,secs))
    Sunrise is at 0.32044 (07:41:26)
    """
    return solar_noon(jc, longitude, timezone) - ha_sunrise(jc, latitude)/360.0
    
def sunset(jc, latitude, longitude, timezone):
    """
    Given a J2000 time, latitude, longitude, and timezone, find the sunset.
    
    jc: The time in Julian centuries since J2000.0
    
    latitude: The latitude
    
    longitude: The longitude (west longitude is negative)
    
    timezone: Timezone relative to GMT (eg, PST is -8)
    
    Returns: Time of sunset in days
    
    Example: Find sunset for the longitude 122W on 1/17/2011
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> sn_days = sunset(j2000_from_timestamp(time_ts), 45.0, -122.0, -8.0)
    >>> secs = sn_days * 86400
    >>> h = int(secs/3600.0)
    >>> secs %= 3600.0
    >>> m = int(secs/60.0)
    >>> secs = int(round(secs % 60))
    >>> print "Sunset is at %.5f (%s)" %(sn_days, datetime.time(h,m,secs))
    Sunset is at 0.70471 (16:54:47)
    """
    return solar_noon(jc, longitude, timezone) + ha_sunrise(jc, latitude)/360.0
    
def total_sunlight(jc, latitude):
    """
    Given a J2000 time and latitude, find the total sunlight in minutes
    
    jc: The time in Julian centuries since J2000.0
    
    latitude: The latitude
    
    Returns: Amount of sunlight in minutes
    
    Example: Find the amount of sunlight at 45N on 1/17/2011
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> print "Total sunlight is %.3f minutes" % total_sunlight(j2000_from_timestamp(time_ts), 45.0)
    Total sunlight is 553.344 minutes
    """
    return 8 * ha_sunrise(jc, latitude)

def true_solar_time(t, jc, longitude, timezone):
    """
    Return the local, true solar time in minutes
    
    Comment: There is no reason why parameters t and jc could not be collapsed
    into one parameter (indeed, they can be at odds), but this mimics what the
    spreadsheet does.
    
    t: Time in fractions of a day (eg, 6am would be 0.25)
    
    jc: The time in Julian centuries since J2000.0
    
    longitude: The longitude (west longitude is negative)
    
    timezone: Timezone relative to GMT (eg, PST is -8)
    
    Returns: True time in minutes
    
    Example: Find the true time for the longitude 122W on 1/17/2011 at noon.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> sn_mins = true_solar_time(0.5, j2000_from_timestamp(time_ts), -122.0, -8.0)
    >>> secs = sn_mins*60.0
    >>> h = int(secs/3600.0)
    >>> secs %= 3600.0
    >>> m = int(secs/60.0)
    >>> secs = int(round(secs % 60))
    >>> print "True time is %.4f (%s)" %(sn_mins, datetime.time(h,m,secs))
    True time is 701.8888 (11:41:53)
    """
    
    return (t *1440.0 + equation_of_time(jc) + 4.0*longitude - 60.0*timezone) % 1440

def hour_angle(t, jc, longitude, timezone):
    """
    Return the local hour angle of the sun in degrees.
    
    Comment: There is no reason why parameters t and jc could not be collapsed
    into one parameter (indeed, they can be at odds), but this mimics what the
    spreadsheet does.
    
    t: Time in fractions of a day (eg, 6am would be 0.25)
    
    jc: The time in Julian centuries since J2000.0
    
    longitude: The longitude (west longitude is negative)
    
    timezone: Timezone relative to GMT (eg, PST is -8)
    
    Returns: Hour angle of the sun in degrees.
    
    Example: Find hour angle of the sun for the longitude 122W on 1/17/2011 at noon.
    
    >>> time_ts = 1295294400.0
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> ha = hour_angle(0.5, j2000_from_timestamp(time_ts), -122.0, -8.0)
    >>> print "Hour angle= %.5f" % ha
    Hour angle= -4.52779
    """
    
    ha = true_solar_time(t, jc, longitude, timezone) / 4.0

    return ha + 180.0 if ha < 0 else ha - 180.0

if __name__ == "__main__":
    
    import time
    import datetime
    
    import doctest
    doctest.testmod()
    
