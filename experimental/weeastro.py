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

These calculations were taken from the NOAA spreadsheet explained at

  http://www.srrb.noaa.gov/highlights/sunrise/calcdetails.html

and available as an Excel spreadsheet at:

  http://www.srrb.noaa.gov/highlights/sunrise/NOAA_Solar_Calculations_year.xls
  
Most of the test calculations are done for the date 17-Jan-2011, local time 12
Noon, in the Pacific Standard Time Zone (UTC-8). For something like sunrise,
which will actually happen a few hours earlier than noon, that means these
calculations are necessarily an approximation.

"""

from math import cos, sin, tan, acos, asin, atan2, radians, degrees, pow

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

def jd_from_j2000(jc2000):
    """Convert from the number of centuries since J2000.0 to the Julian day."""
    
    return jc2000 * 36525.0 + 2451545.0

class WeeSolar(object):
    
    """
    Object that holds astronomical data for a specific time, lat/long, and timezone.
    The data is then available as attributes.
    
    Attributes:
    
        geom_mean_long_sun: Geometric mean longitude of the sun (degrees)
        geom_mean_anom_sun: Geometric mean anomaly of the sun (degrees)
        earth_eccentricity: The eccentricity of the earth's orbit (unitless number)
        sun_eq_of_center: Equation of center of the sun
        sun_true_long: The sun's true longitude (degrees)
        sun_true_anom: The sun's true anomaly (degrees)
        sun_rad_vector: The sun's radius vector in AUs
        sun_apparent_long: The sun's apparent longitude (degrees)
        mean_obliquity_ecliptic: The mean obliquity of the ecliptic (degrees)
        obliquity_correction: Obliquity correction (degrees)
        sun_right_ascension: The sun's right ascension (degrees)
        sun_declination: The sun's declination (degrees)
        equation_of_time: The equation of time (minutes)
        solar_noon: Solar noon (LST in fraction of a day since midnight)
        ha_sunrise: Hour angle of sunrise (degrees). 'None' if the sun does not rise
        sunrise: Time of sunrise (LST in fraction of a day since midnight). 
            'None' if the sun does not rise
        sunset: Time of sunset (LST in fraction of a day since midnight). 
            'None' if the sun does not set
        total_sunlight: Sunlight duration (minutes)
        true_solar_time: True time by the sun (minutes past midnight)
        hour_angle: Hour angle of the sun (degrees)
        solar_zenith_angle: Angle of the sun from the zenith (degrees)
        solar_elevation_angle: Elevation of the sun above the horizon (degrees)
        atmospheric_refraction: Correction due to atmospheric refraction (degrees)
        solar_elevation_angle_corrected: Elevation of the sun above the horizon, 
            corrected for atmospheric refraction (degrees)
        solar_azimuth: Azimuth angle of the sun (degrees clockwise from North)


    Example:
    
    Construct different WeeSolar objects for different lat/lons, but all for
    1/17/2011 2000 UTC:
    
    >>> utc_tt = (2011,1,17,20,0,0,0,0,-1)
    >>> time_ts = time.mktime(utc_tt) - time.timezone
    >>> print time.asctime(time.gmtime(time_ts))
    Mon Jan 17 20:00:00 2011
    >>> jc2000 = j2000_from_timestamp(time_ts)
    >>> wa45 = WeeSolar(0.5, jc2000, 45.0, -122.0, -8.0)
    >>> wa65 = WeeSolar(0.5, jc2000, 65.0, -122.0, -8.0)
    >>> wa75 = WeeSolar(0.5, jc2000, 75.0, -122.0, -8.0)

    Now exercise the various attributes:
    
    >>> print "Mean longitude of the sun: %.4f" % wa45.geom_mean_long_sun
    Mean longitude of the sun: 296.8965

    >>> print "Mean anomaly of the sun: %.3f" % wa45.geom_mean_anom_sun
    Mean anomaly of the sun: 4333.769

    >>> print "Eccentricity of the earth's orbit: %.6f" % wa45.earth_eccentricity
    Eccentricity of the earth's orbit: 0.016702

    >>> print "Equation of center: %.6f" % wa45.sun_eq_of_center
    Equation of center: 0.464999

    >>> print "The Sun's true longitude: %.4f" % wa45.sun_true_long
    The Sun's true longitude: 297.3615

    >>> print "The Sun's true longitude: %.3f" % wa45.sun_true_anom
    The Sun's true longitude: 4334.234

    >>> print "The Sun's radius vector: %.6f" % wa45.sun_rad_vector
    The Sun's radius vector: 0.983795

    >>> print "The Sun's apparent longitude: %.4f" % wa45.sun_apparent_long
    The Sun's apparent longitude: 297.3606

    >>> print "The obliquity of the ecliptic: %.5f" % wa45.mean_obliquity_ecliptic
    The obliquity of the ecliptic: 23.43785

    >>> print "The obliquity correction: %.5f" % wa45.obliquity_correction
    The obliquity correction: 23.43792

    >>> print "The Sun's right ascension: %.4f" % wa45.sun_right_ascension
    The Sun's right ascension: 150.5764

    >>> print "The Sun's declination: %.4f" % wa45.sun_declination
    The Sun's declination: -20.6868

    >>> print "The equation of time is: %.5f" % wa45.equation_of_time
    The equation of time is: -10.11117

    >>> # Solar noon.
    >>> print "Solar noon is at %.5f (%s)" %(wa45.solar_noon, time_from_fday(wa45.solar_noon))
    Solar noon is at 0.51258 (12:18:07)
    
    >>> # Hour angle of sunrise. If we are far enough north, there is no sunrise
    >>> print "The hour angle of sunrise at 45N (sun above horizon) is: %.5f" % wa45.ha_sunrise
    The hour angle of sunrise at 45N (sun above horizon) is: 69.16806
    >>> print "The hour angle of sunrise at 75N (sun below horizon) is", wa75.ha_sunrise
    The hour angle of sunrise at 75N (sun below horizon) is None
    
    >>> # Sunrise. If we are far enough north, there is no sunrise
    >>> print "Sunrise at 45N is at %.5f (%s)" %(wa45.sunrise, time_from_fday(wa45.sunrise))
    Sunrise at 45N is at 0.32044 (07:41:26)
    >>> print "Sunrise at 75N (no sunrise):", wa75.sunrise
    Sunrise at 75N (no sunrise): None

    >>> # Sunset. If we are far enough north, there is no sunset
    >>> print "Sunset at 45N is at %.5f (%s)" %(wa45.sunset, time_from_fday(wa45.sunset))
    Sunset at 45N is at 0.70471 (16:54:47)
    >>> print "Sunset at 75N (no sunset):", wa75.sunset
    Sunset at 75N (no sunset): None

    >>> # Total sunlight If we are far enough north, there is no sunlight
    >>> print "Total sunlight at 45N is %.3f minutes" % wa45.total_sunlight
    Total sunlight at 45N is 553.344 minutes
    >>> print "Total sunlight at 75N is %.3f minutes" % wa75.total_sunlight
    Total sunlight at 75N is 0.000 minutes
    
    >>> # True solar time
    >>> print "True time is %.4f (%s)" %(wa45.true_solar_time, time_from_fday(wa45.true_solar_time/1440.0))
    True time is 701.8888 (11:41:53)
    
    >>> print "Hour angle= %.5f" % wa45.hour_angle
    Hour angle= -4.52779

    >>> print "Solar zenith angle at 45N = %.5f" % wa45.solar_zenith_angle
    Solar zenith angle at 45N = 65.81652
    >>> print "Solar zenith angle at 65N = %.5f" % wa65.solar_zenith_angle
    Solar zenith angle at 65N = 85.75768

    >>> print "Solar elevation angle at 45N = %.5f" % wa45.solar_elevation_angle
    Solar elevation angle at 45N = 24.18348
    >>> print "Solar elevation angle at 65N = %.5f" % wa65.solar_elevation_angle
    Solar elevation angle at 65N = 4.24232

    >>> # Do 3 different refraction angles, exercising all branches in the algorithm:
    >>> print "Atmospheric refraction at 45N = %.6f" % wa45.atmospheric_refraction
    Atmospheric refraction at 45N = 0.035725
    >>> print "Atmospheric refraction at 65N = %.6f" % wa65.atmospheric_refraction
    Atmospheric refraction at 65N = 0.180923
    >>> print "Atmospheric refraction at 75N = %.4f" % wa75.atmospheric_refraction
    Atmospheric refraction at 75N = 0.0575

    >>> print "Corrected solar elevation angle at 45N = %.5f" % wa45.solar_elevation_angle_corrected
    Corrected solar elevation angle at 45N = 24.21921
    >>> print "Corrected solar elevation angle at 65N = %.5f" % wa65.solar_elevation_angle_corrected
    Corrected solar elevation angle at 65N = 4.42324

    >>> print "Solar azimuth angle at 45N, 122W = %.4f" % wa45.solar_azimuth
    Solar azimuth angle at 45N, 122W = 175.3564
    >>> # Do it again, but for a longitude where the sun is to the west
    >>> wa45117 = WeeSolar(0.5, jc2000, 45.0, -117.0, -8.0)
    >>> print "Solar azimuth angle at 45N, 117W = %.4f" % wa45117.solar_azimuth
    Solar azimuth angle at 45N, 117W = 180.4848
    

    """
    def __init__(self, tod, jc2000, latitude, longitude, timezone):

        self.tod = tod
        self.jc2000 = jc2000
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.recalc()
        
    @staticmethod
    def fromtimestamp(time_ts, latitude, longitude, timezone):
        pass
    
    def recalc(self):
        
        self.geom_mean_long_sun = (280.46646 + self.jc2000*(36000.76983 + self.jc2000*0.0003032)) % 360.0

        self.geom_mean_anom_sun = 357.52911 + self.jc2000*(35999.05029 - 0.0001536*self.jc2000)

        self.earth_eccentricity = 0.016708634 - self.jc2000*(0.000042037+0.0001537*self.jc2000)

        self.sun_eq_of_center = sin(radians(self.geom_mean_anom_sun))*(1.914602-self.jc2000*(0.004817+0.000014*self.jc2000))+sin(radians(2*self.geom_mean_anom_sun))*(0.019993-0.000101*self.jc2000)+sin(radians(3*self.geom_mean_anom_sun))*0.000289

        self.sun_true_long = self.geom_mean_long_sun + self.sun_eq_of_center

        self.sun_true_anom = self.geom_mean_anom_sun + self.sun_eq_of_center

        self.sun_rad_vector = (1.000001018 * (1.0 - self.earth_eccentricity*self.earth_eccentricity)) / (1.0 + self.earth_eccentricity * cos(radians(self.sun_true_anom)))

        self.sun_apparent_long = self.sun_true_long - 0.00569 - 0.00478 * sin(radians(125.04-1934.136*self.jc2000))

        self.mean_obliquity_ecliptic = 23.0 + (26.0 + ((21.448 - self.jc2000*(46.815+self.jc2000*(0.00059-self.jc2000*0.001813))))/60.0)/60.0

        self.obliquity_correction = self.mean_obliquity_ecliptic + 0.00256 * cos(radians(125.04 - 1934.136*self.jc2000))

        self.sun_right_ascension = degrees(atan2(cos(radians(self.sun_apparent_long)), cos(radians(self.obliquity_correction))*sin(radians(self.sun_apparent_long))))

        self.sun_declination = degrees(asin(sin(radians(self.obliquity_correction)) * sin(radians(self.sun_apparent_long))))

        x = tan(radians(self.obliquity_correction/2.0))
        u_vy =  x**2
        self.equation_of_time = 4.0*degrees(u_vy*sin(2.0*radians(self.geom_mean_long_sun))-2.0*self.earth_eccentricity*sin(radians(self.geom_mean_anom_sun))\
                                            + 4.0 *  self.earth_eccentricity*u_vy*sin(radians(self.geom_mean_anom_sun)) * cos(2.0*radians(self.geom_mean_long_sun))\
                                            - 0.5 *  u_vy*u_vy*sin(4.0*radians(self.geom_mean_long_sun))\
                                            - 1.25 * self.earth_eccentricity*self.earth_eccentricity*sin(2.0*radians(self.geom_mean_anom_sun)))

        self.solar_noon = (720.0 - 4.0*self.longitude - self.equation_of_time + self.timezone * 60) / 1440.0

        # A ValueError exception will get thrown if the sun never appears above the horizon:
        try:
            self.ha_sunrise = degrees(acos(cos(radians(90.833))/(cos(radians(self.latitude)) * cos(radians(self.sun_declination)))\
                                           - tan(radians(self.latitude))*tan(radians(self.sun_declination))))
            self.sunrise    = self.solar_noon - self.ha_sunrise/360.0
            self.sunset     = self.solar_noon + self.ha_sunrise/360.0
            self.total_sunlight = 8 * self.ha_sunrise
        except ValueError:
            self.ha_sunrise = None
            self.sunrise    = None
            self.sunset     = None
            self.total_sunlight = 0.0

        self.true_solar_time = (self.tod *1440.0 + self.equation_of_time + 4.0*self.longitude - 60.0*self.timezone) % 1440

        ha = self.true_solar_time / 4.0
        self.hour_angle = ha + 180.0 if ha < 0 else ha - 180.0

        self.solar_zenith_angle = degrees(acos(sin(radians(self.latitude)) * sin(radians(self.sun_declination)) + cos(radians(self.latitude))*cos(radians(self.sun_declination))*cos(radians(self.hour_angle))))
    
        self.solar_elevation_angle = 90.0 - self.solar_zenith_angle

        # To calculate the atmospheric refraction effect, select which
        # formula to use based on the elevation of the sun:
        if self.solar_elevation_angle > 85.0:
            # Sun very high in the sky. There is no effect.
            ar = 0.0
        elif    5.0 < self.solar_elevation_angle <= 85.0:
            ar = 58.1 / tan(radians(self.solar_elevation_angle))-0.07/pow(tan(radians(self.solar_elevation_angle)),3) + 0.000086/pow(tan(radians(self.solar_elevation_angle)),5)
        elif -0.575 < self.solar_elevation_angle <=  5.0:
            # Sun near the horizon    
            ar = 1735 + self.solar_elevation_angle*(-518.2+self.solar_elevation_angle*(103.4+self.solar_elevation_angle*(-12.79+self.solar_elevation_angle*0.711)))
        else:
            # Sun well below the horizon.
            ar = -20.772/tan(radians(self.solar_elevation_angle))
        self.atmospheric_refraction = ar/3600.0

        self.solar_elevation_angle_corrected = self.solar_elevation_angle + self.atmospheric_refraction

        if self.hour_angle>0:
            self.solar_azimuth = (degrees(acos(((sin(radians(self.latitude))*cos(radians(self.solar_zenith_angle)))-sin(radians(self.sun_declination)))/(cos(radians(self.latitude))*sin(radians(self.solar_zenith_angle)))))+180 ) % 360
        else:
            self.solar_azimuth = (540-degrees(acos(((sin(radians(self.latitude))*cos(radians(self.solar_zenith_angle)))-sin(radians(self.sun_declination)))/(cos(radians(self.latitude))*sin(radians(self.solar_zenith_angle)))))) % 360

if __name__ == "__main__":
    
    import time
    import datetime
    import doctest

    # Used in the doctest examples:
    def time_from_fday(fday):
        # Convert a fractional day into a time object
        secs = fday * 86400
        h = int(secs/3600.0)
        secs %= 3600.0
        m = int(secs/60.0)
        secs = int(round(secs % 60))
        return datetime.time(h,m,secs)
            
    doctest.testmod()

    # Try some exercises near the vernal equinox
    utc_tt = (2011,3,21,20,0,0,0,0,0)
    time_ts = time.mktime(utc_tt) - time.timezone
    print time.asctime(time.gmtime(time_ts))
    jc2000 = j2000_from_timestamp(time_ts)
    wa45 = WeeSolar(0.5, jc2000, 45.0, -122.0, -8.0)
    print "Sunrise at 45N is at %.5f (%s)" %(wa45.sunrise, time_from_fday(wa45.sunrise))
    print "Sunset  at 45N is at %.5f (%s)" %(wa45.sunset, time_from_fday(wa45.sunset))
    print "Solar noon at 45N is at %.5f (%s)" %(wa45.solar_noon, time_from_fday(wa45.solar_noon))
