# -*- coding: iso-8859-1 -*-
""" 
SUNRISET.C - computes Sun rise/set times, start/end of twilight, and
             the length of the day at any date and latitude
			 
Written as DAYLEN.C, 1989-08-16

Modified to SUNRISET.C, 1992-12-01
			 
(c) Paul Schlyter, 1989, 1992
			 
Released to the public domain by Paul Schlyter, December 1992
			 
Direct conversion to Java 
Sean Russell <ser@germane-software.com>

Conversion to Python Class, 2002-03-21
Henrik Härkönen <radix@kortis.to>

Solar Altitude added by Miguel Tremblay 2005-01-16
Solar flux, equation of time and import of python library
  added by Miguel Tremblay 2007-11-22


2007-12-12 - v1.5 by Miguel Tremblay: bug fix to solar flux calculation

2009-03-27 - v1.6 by Tom Keffer; Got rid of the unnecessary (and stateless)
             class Sun. Cleaned up.


"""

SUN_PY_VERSION = "1.6.0"

import math
from math import pi

import calendar

# Some conversion factors between radians and degrees
RADEG= 180.0 / pi
DEGRAD = pi / 180.0
INV360 = 1.0 / 360.0

#Convenience functions for working in degrees:
# The trigonometric functions in degrees
def sind(x):
    """Returns the sin in degrees"""
    return math.sin(x * DEGRAD)

def cosd(x):
    """Returns the cos in degrees"""
    return math.cos(x * DEGRAD)

def tand(x):
    """Returns the tan in degrees"""
    return math.tan(x * DEGRAD)

def atand(x):
    """Returns the arc tan in degrees"""
    return math.atan(x) * RADEG

def asind(x):
    """Returns the arc sin in degrees"""
    return math.asin(x) * RADEG

def acosd(x):
    """Returns the arc cos in degrees"""
    return math.acos(x) * RADEG

def atan2d(y, x):
    """Returns the atan2 in degrees"""
    return math.atan2(y, x) * RADEG


def daysSince2000Jan0(y, m, d):
    """A macro to compute the number of days elapsed since 2000 Jan 0.0
    (which is equal to 1999 Dec 31, 0h UT)"""
    return (367*(y)-((7*((y)+(((m)+9)/12)))/4)+((275*(m))/9)+(d)-730530)


# Following are some macros around the "workhorse" function __daylen__ 
# They mainly fill in the desired values for the reference altitude    
# below the horizon, and also selects whether this altitude should     
# refer to the Sun's center or its upper limb.                         

def dayLength(year, month, day, lon, lat):
    """
    This macro computes the length of the day, from sunrise to sunset.
    Sunrise/set is considered to occur when the Sun's upper limb is
    35 arc minutes below the horizon (this accounts for the refraction
    of the Earth's atmosphere).
    """
    return __daylen__(year, month, day, lon, lat, -35.0/60.0, 1)


def dayCivilTwilightLength(year, month, day, lon, lat):
    """
    This macro computes the length of the day, including civil twilight.
    Civil twilight starts/ends when the Sun's center is 6 degrees below
    the horizon. 
    """
    return __daylen__(year, month, day, lon, lat, -6.0, 0)


def dayNauticalTwilightLength(year, month, day, lon, lat):
    """
    This macro computes the length of the day, incl. nautical twilight.
    Nautical twilight starts/ends when the Sun's center is 12 degrees
    below the horizon.
    """
    return __daylen__(year, month, day, lon, lat, -12.0, 0)


def dayAstronomicalTwilightLength(year, month, day, lon, lat):
    """
    This macro computes the length of the day, incl. astronomical twilight.
    Astronomical twilight starts/ends when the Sun's center is 18 degrees 
    below the horizon. 
    """
    return __daylen__(year, month, day, lon, lat, -18.0, 0)


def sunRiseSet(year, month, day, lon, lat):
    """
    This macro computes times for sunrise/sunset.
    Sunrise/set is considered to occur when the Sun's upper limb is
    35 arc minutes below the horizon (this accounts for the refraction
    of the Earth's atmosphere).
    """
    return __sunriset__(year, month, day, lon, lat, -35.0/60.0, 1)


def civilTwilight(year, month, day, lon, lat):
    """
    This macro computes the start and end times of civil twilight. 
    Civil twilight starts/ends when the Sun's center is 6 degrees below 
    the horizon.
    """
    return __sunriset__(year, month, day, lon, lat, -6.0, 0)


def nauticalTwilight(year, month, day, lon, lat):
    """
    This macro computes the start and end times of nautical twilight.
    Nautical twilight starts/ends when the Sun's center is 12 degrees
    below the horizon.
    """
    return __sunriset__(year, month, day, lon, lat, -12.0, 0)


def astronomicalTwilight(year, month, day, lon, lat):
    """
    This macro computes the start and end times of astronomical twilight.
    Astronomical twilight starts/ends when the Sun's center is 18 degrees
    below the horizon.
    """
    return __sunriset__(year, month, day, lon, lat, -18.0, 0)


# The "workhorse" function for sun rise/set times
def __sunriset__(year, month, day, lon, lat, altit, upper_limb):
    """
    Note: year,month,date = calendar date, 1801-2099 only.
          Eastern longitude positive, Western longitude negative
              Northern latitude positive, Southern latitude negative
          The longitude value IS critical in this function!
          altit = the altitude which the Sun should cross
                  Set to -35/60 degrees for rise/set, -6 degrees
    	      for civil, -12 degrees for nautical and -18
    	      degrees for astronomical twilight.
            upper_limb: non-zero -> upper limb, zero -> center
    	      Set to non-zero (e.g. 1) when computing rise/set
    	      times, and to zero when computing start/end of
    	      twilight.
          *rise = where to store the rise time 
          *set  = where to store the set  time 
                  Both times are relative to the specified altitude,
    	      and thus this function can be used to compute
    	      various twilight times, as well as rise/set times
    Return value:  0 = sun rises/sets this day, times stored at
                           *trise and *tset.
    	      +1 = sun above the specified 'horizon' 24 hours.
    	           *trise set to time when the sun is at south,
    		   minus 12 hours while *tset is set to the south
    		   time plus 12 hours. 'Day' length = 24 hours 
    	      -1 = sun is below the specified 'horizon' 24 hours
    	           'Day' length = 0 hours, *trise and *tset are
    		    both set to the time when the sun is at south.
    """
    # Compute d of 12h local mean solar time
    d = daysSince2000Jan0(year,month,day) + 0.5 - (lon/360.0)
    
    # Compute local sidereal time of this moment 
    sidtime = revolution(GMST0(d) + 180.0 + lon)
    
    # Compute Sun's RA + Decl at this moment 
    res = sunRADec(d)
    sRA = res[0]
    sdec = res[1]
    sr = res[2]
    
    # Compute time when Sun is at south - in hours UT 
    tsouth = 12.0 - rev180(sidtime - sRA)/15.0;
    
    # Compute the Sun's apparent radius, degrees 
    sradius = 0.2666 / sr;
    
    # Do correction to upper limb, if necessary 
    if upper_limb:
        altit = altit - sradius
    
    # Compute the diurnal arc that the Sun traverses to reach 
    # the specified altitude altit: 
    
    cost = (sind(altit) - sind(lat) * sind(sdec))/\
               (cosd(lat) * cosd(sdec))
    
    if cost >= 1.0:
        t = 0.0           # Sun always below altit
        
    elif cost <= -1.0:
        t = 12.0;         # Sun always above altit
    
    else:
        t = acosd(cost)/15.0   # The diurnal arc, hours
    
    
    # Store rise and set times - in hours UT 
    return (tsouth-t, tsouth+t)


def __daylen__(year, month, day, lon, lat, altit, upper_limb):
    """
    Note: year,month,date = calendar date, 1801-2099 only.             
          Eastern longitude positive, Western longitude negative       
          Northern latitude positive, Southern latitude negative       
          The longitude value is not critical. Set it to the correct   
          longitude if you're picky, otherwise set to, say, 0.0     
          The latitude however IS critical - be sure to get it correct 
          altit = the altitude which the Sun should cross              
                  Set to -35/60 degrees for rise/set, -6 degrees       
                  for civil, -12 degrees for nautical and -18          
                  degrees for astronomical twilight.                   
            upper_limb: non-zero -> upper limb, zero -> center         
                  Set to non-zero (e.g. 1) when computing day length   
                  and to zero when computing day+twilight length.      
    						
    """
    
    # Compute d of 12h local mean solar time 
    d = daysSince2000Jan0(year,month,day) + 0.5 - (lon/360.0)

    # Compute obliquity of ecliptic (inclination of Earth's axis) 
    obl_ecl = 23.4393 - 3.563E-7 * d
    
    # Compute Sun's position 
    res = sunpos(d)
    slon = res[0]
    sr = res[1]
    
    # Compute sine and cosine of Sun's declination 
    sin_sdecl = sind(obl_ecl) * sind(slon)
    cos_sdecl = math.sqrt(1.0 - sin_sdecl * sin_sdecl)
    
    # Compute the Sun's apparent radius, degrees 
    sradius = 0.2666 / sr
    
    # Do correction to upper limb, if necessary 
    if upper_limb:
        altit = altit - sradius
    
        
    cost = (sind(altit) - sind(lat) * sin_sdecl) / \
               (cosd(lat) * cos_sdecl)
    if cost >= 1.0:
        t = 0.0             # Sun always below altit
    
    elif cost <= -1.0:
        t = 24.0      # Sun always above altit
    
    else:
        t = (2.0/15.0) * acosd(cost);     # The diurnal arc, hours
        
    return t


def sunpos(d):
    """
    Computes the Sun's ecliptic longitude and distance 
    at an instant given in d, number of days since     
    2000 Jan 0.0.  The Sun's ecliptic latitude is not  
    computed, since it's always very near 0.           
    """
    
    # Compute mean elements 
    M = revolution(356.0470 + 0.9856002585 * d)
    w = 282.9404 + 4.70935E-5 * d
    e = 0.016709 - 1.151E-9 * d
    
    # Compute true longitude and radius vector 
    E = M + e * RADEG * sind(M) * (1.0 + e * cosd(M))
    x = cosd(E) - e
    y = math.sqrt(1.0 - e*e) * sind(E)
    r = math.sqrt(x*x + y*y)              #Solar distance 
    v = atan2d(y, x)                 # True anomaly 
    lon = v + w                        # True solar longitude 
    if lon >= 360.0:
        lon = lon - 360.0   # Make it 0..360 degrees
        
    return (lon,r)
    

def sunRADec(d):
    """
        Returns the angle of the Sun (RA)
        the declination (dec) and the distance of the Sun (r)
        for a given day d.
        """
    
    # Compute Sun's ecliptical coordinates 
    res = sunpos(d)
    lon = res[0]  # True solar longitude
    r = res[1]    # Solar distance
    
    # Compute ecliptic rectangular coordinates (z=0) 
    x = r * cosd(lon)
    y = r * sind(lon)
    
    # Compute obliquity of ecliptic (inclination of Earth's axis) 
    obl_ecl = 23.4393 - 3.563E-7 * d
    
    # Convert to equatorial rectangular coordinates - x is unchanged 
    z = y * sind(obl_ecl)
    y = y * cosd(obl_ecl)
    
    # Convert to spherical coordinates 
    RA = atan2d(y, x)
    dec = atan2d(z, math.sqrt(x*x + y*y))
    
    return (RA, dec, r)
    


def GMST0(d):
    """
    This function computes GMST0, the Greenwich Mean Sidereal Time  
    at 0h UT (i.e. the sidereal time at the Greenwhich meridian at  
    0h UT).  GMST is then the sidereal time at Greenwich at any     
    time of the day.  I've generalized GMST0 as well, and define it 
    as:  GMST0 = GMST - UT  --  this allows GMST0 to be computed at 
    other times than 0h UT as well.  While this sounds somewhat     
    contradictory, it is very practical:  instead of computing      
    GMST like:                                                      
                                                                    
     GMST = (GMST0) + UT * (366.2422/365.2422)                      
                                                                    
    where (GMST0) is the GMST last time UT was 0 hours, one simply  
    computes:                                                       
                                                                    
     GMST = GMST0 + UT                                              
                                                                    
    where GMST0 is the GMST "at 0h UT" but at the current moment!   
    Defined in this way, GMST0 will increase with about 4 min a     
    day.  It also happens that GMST0 (in degrees, 1 hr = 15 degr)   
    is equal to the Sun's mean longitude plus/minus 180 degrees!    
    (if we neglect aberration, which amounts to 20 seconds of arc   
    or 1.33 seconds of time)
    """
    # Sidtime at 0h UT = L (Sun's mean longitude) + 180.0 degr  
    # L = M + w, as defined in sunpos().  Since I'm too lazy to 
    # add these numbers, I'll let the C compiler do it for me.  
    # Any decent C compiler will add the constants at compile   
    # time, imposing no runtime or code overhead.               

    sidtim0 = revolution((180.0 + 356.0470 + 282.9404) +
                            (0.9856002585 + 4.70935E-5) * d)
    return sidtim0;


def solar_altitude(latitude, year, month, day):
    """
    Compute the altitude of the sun. No atmospherical refraction taken
    in account.
    Altitude of the southern hemisphere are given relative to
    true north.
    Altitude of the northern hemisphere are given relative to
    true south.
    Declination is between 23.5° North and 23.5° South depending
    on the period of the year.
    Source of formula for altitude is PhysicalGeography.net
    http://www.physicalgeography.net/fundamentals/6h.html
    """
    # Compute declination
    N = daysSince2000Jan0(year, month, day)
    res =  sunRADec(N)
    declination = res[1]

    # Compute the altitude
    altitude = 90.0 - latitude  + declination

    # In the tropical and  in extreme latitude, values over 90 may occurs.
    if altitude > 90:
        altitude = 90 - (altitude-90)

    if altitude < 0:
        altitude = 0

    return altitude


def get_max_solar_flux(latitude, year, month, day):
    """
    Compute the maximal solar flux to reach the ground for this date and
    latitude.
    Originaly comes from Environment Canada weather forecast model.
    Information was of the public domain before release by Environment Canada
    Output is in W/M^2.
    """

    (unused_fEot, fR0r, tDeclsc) = equation_of_time(year, month, day, latitude)
    fSF = (tDeclsc[0]+tDeclsc[1])*fR0r

    # In the case of a negative declinaison, solar flux is null
    if fSF < 0:
        fCoeff = 0
    else:
        fCoeff =  -1.56e-12*fSF**4 + 5.972e-9*fSF**3 -\
                 8.364e-6*fSF**2  + 5.183e-3*fSF - 0.435
   
    fSFT = fSF * fCoeff 

    if fSFT < 0:
        fSFT=0

    return fSFT


def equation_of_time(year, month, day, latitude):
    """
    Description: Subroutine computing the part of the equation of time
                 needed in the computing of the theoritical solar flux
                 Correction originating of the CMC GEM model.
                 
    Parameters:  int nTime : cTime for the correction of the time.

    Returns: tuple (double fEot, double fR0r, tuple tDeclsc)
             dEot: Correction for the equation of time 
             dR0r: Corrected solar constant for the equation of time
             tDeclsc: Declinaison
    """
    # Julian date 
    nJulianDate = Julian(year, month, day)
    # Check if it is a leap year
    if(calendar.isleap(year)):
        fDivide = 366.0
    else:
        fDivide = 365.0
    # Correction for "equation of time"
    fA = nJulianDate/fDivide*2*pi
    fR0r = __Solcons(fA)*0.1367e4
    fRdecl = 0.412*math.cos((nJulianDate+10.0)*2.0*pi/fDivide-pi)
    fDeclsc1 = sind(latitude)*math.sin(fRdecl)
    fDeclsc2 = cosd(latitude)*math.cos(fRdecl)
    tDeclsc = (fDeclsc1, fDeclsc2)
    # in minutes
    fEot = 0.002733 -7.343*math.sin(fA)+ .5519*math.cos(fA) \
           - 9.47*math.sin(2.0*fA) - 3.02*math.cos(2.0*fA) \
           - 0.3289*math.sin(3.*fA) -0.07581*math.cos(3.0*fA) \
           -0.1935*math.sin(4.0*fA) -0.1245*math.cos(4.0*fA)
    # Express in fraction of hour
    fEot = fEot/60.0
    # Express in radians
    fEot = fEot*15*pi/180.0

    return (fEot, fR0r, tDeclsc)


def __Solcons(dAlf):
    """
    Name: __Solcons
    
    Parameters: [I] double dAlf : Solar constant to correct the excentricity
    
    Returns: double dVar : Variation of the solar constant

    Functions Called: cos, sin
     
    Description:  Statement function that calculates the variation of the
      solar constant as a function of the julian day. (dAlf, in radians)
     
    Notes: Comes from the 
     
    Revision History:
    Author		Date		Reason
    Miguel Tremblay      June 30th 2004
    """
    
    dVar = 1.0/(1.0-9.464e-4*math.sin(dAlf)-0.01671*math.cos(dAlf)- \
                + 1.489e-4*math.cos(2.0*dAlf)-2.917e-5*math.sin(3.0*dAlf)- \
                + 3.438e-4*math.cos(4.0*dAlf))**2
    return dVar


def Julian(year, month, day):
    """
    Return julian day.
    """
    if calendar.isleap(year): # Bissextil year, 366 days
        lMonth = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]
    else: # Normal year, 365 days
        lMonth = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

    nJulian = lMonth[month-1] + day
    return nJulian

def revolution(x):
    """
    This function reduces any angle to within the first revolution 
    by subtracting or adding even multiples of 360.0 until the     
    result is >= 0.0 and < 360.0
    
    Reduce angle to within 0..360 degrees
    """
    return (x - 360.0 * math.floor(x * INV360))


def rev180(x):
    """
    Reduce angle to within +180..+180 degrees
    """ 
    return (x - 360.0 * math.floor(x * INV360 + 0.5))



if __name__ == "__main__":
    (sunrise_utc, sunset_utc) = sunRiseSet(2009, 3, 27, -122.65, 45.517)
    print sunrise_utc, sunset_utc
    
    #Assert that the results are within 1 minute of NOAA's 
    # calculator (see http://www.srrb.noaa.gov/highlights/sunrise/sunrise.html)
    assert((sunrise_utc - 14.00) < 1.0/60.0)
    assert((sunset_utc  - 26.55) < 1.0/60.0)
