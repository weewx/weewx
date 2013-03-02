#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Various weather related formulas and utilities."""
import math

def dewpointF(T, R) :
    """Calculate dew point. 
    
    T: Temperature in Fahrenheit
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Fahrenheit
    Examples:
    
    >>> print "%.1f" % dewpointF(68, 50)
    48.7
    >>> print "%.1f" % dewpointF(32, 50)
    15.5
    >>> print "%.1f" % dewpointF(-10, 50)
    -23.5
    """

    if T is None or R is None :
        return None

    TdC = dewpointC((T - 32.0)*5.0/9.0, R)

    return TdC * 9.0/5.0 + 32.0 if TdC is not None else None

def dewpointC(T, R):
    """Calculate dew point. From http://en.wikipedia.org/wiki/Dew_point
    
    T: Temperature in Celsius
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Celsius
    """

    if T is None or R is None :
        return None
    R = R / 100.0
    try:
        _gamma = 17.27 * T / (237.7 + T) + math.log(R)
        TdC = 237.7 * _gamma / (17.27 - _gamma)
    except (ValueError, OverflowError):
        TdC = None
    return TdC

def windchillF(T_F, V_mph) :
    """Calculate wind chill. From http://www.nws.noaa.gov/om/windchill
    
    T_F: Temperature in Fahrenheit
    
    V_mph: Wind speed in mph
    
    Returns Wind Chill in Fahrenheit
    """
    
    if T_F is None or V_mph is None:
        return None

    # Formula only valid for temperatures below 50F and wind speeds over 3.0 mph
    if T_F >= 50.0 or V_mph <= 3.0 : 
        return T_F
    WcF = 35.74 + 0.6215 * T_F + (-35.75  + 0.4275 * T_F) * math.pow(V_mph, 0.16) 
    return WcF

def windchillC(T_C, V_kph):
    """Wind chill, metric version.
    
    T: Temperature in Celsius
    
    V: Wind speed in kph
    
    Returns wind chill in Celsius"""
    
    if T_C is None or V_kph is None:
        return None
    
    T_F = T_C * (9.0/5.0) + 32.0
    V_mph = 0.621371192 * V_kph
    
    WcF = windchillF(T_F, V_mph)
    
    return (WcF - 32.0) * (5.0 / 9.0) if WcF is not None else None
    
def heatindexF(T, R) :
    """Calculate heat index. From http://www.crh.noaa.gov/jkl/?n=heat_index_calculator
    
    T: Temperature in Fahrenheit
    
    R: Relative humidity in percent
    
    Returns heat index in Fahrenheit
    
    Examples:
    
    >>> print heatindexF(75.0, 50.0)
    75.0
    >>> print heatindexF(80.0, 50.0)
    80.8029049
    >>> print heatindexF(80.0, 95.0)
    86.3980618
    >>> print heatindexF(90.0, 50.0)
    94.5969412
    >>> print heatindexF(90.0, 95.0)
    126.6232036

    """
    if T is None or R is None :
        return None
    
    # Formula only valid for temperatures over 80F:
    if T < 80.0 or R  < 40.0:
        return T

    hiF = -42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R - 6.83783e-3 * T**2\
    -5.481717e-2 * R**2 + 1.22874e-3 * T**2 * R + 8.5282e-4 * T * R**2 - 1.99e-6 * T**2 * R**2
    if hiF < T :
        hiF = T
    return hiF

def heatindexC(T_C, R):
    if T_C is None or R is None :
        return None
    T_F = T_C * (9.0/5.0) + 32.0
    hiF = heatindexF(T_F, R)
    return (hiF - 32.0) * (5.0/9.0)

def heating_degrees(t, base):
    return max(base - t, 0) if t is not None else None

def cooling_degrees(t, base):
    return max(t - base, 0) if t is not None else None

def altimeter_pressure_US(SP_inHg, Z_feet):
    """Calculate the altimeter pressure, given the raw, station pressure in inHg and the
    altitude in feet.
    
    Formula from:
        http://davisnet.com/product_documents/weather/app_notes/AN_28-derived-weather-variables.pdf
        
    Examples:
    >>> print "%.2f" % altimeter_pressure_US(28.0, 0.0)
    28.00
    >>> print "%.2f" % altimeter_pressure_US(28.0, 1000.0)
    29.04
    """
    if SP_inHg is None or Z_feet is None:
        return None
    N = 0.1903
    K = 1.313e-5
    return (SP_inHg**N + K*Z_feet)**(1/N)

def altimeter_pressure_Metric(SP_mbars, Z_meters):
    """Convert from (uncorrected) station pressure, altitude-corrected pressure.
    Example:
    >>> print "%.1f" % altimeter_pressure_Metric(948.08, 0.0)
    948.1
    >>> print "%.1f" % altimeter_pressure_Metric(948.08, 304.8)
    983.3
    """
    if SP_mbars is None or Z_meters is None:
        return None
    SP_inHg = 0.0295333727*SP_mbars
    Z_feet  = 3.28084*Z_meters
    return altimeter_pressure_US(SP_inHg, Z_feet) / 0.0295333727

if __name__ == '__main__':
    import doctest

    doctest.testmod()
