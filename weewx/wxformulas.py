#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Various weather related formulas and utilities."""
import math

def dewpointF(T, R) :
    """Calculate dew point. 
    
    T: Temperature in Fahrenheit
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Fahrenheit
    """

    if T is None or R is None :
        return None

    TdC = dewpointC((T - 32.0)*5.0/9.0, R)

    return TdC * 9.0/5.0 + 32.0

def dewpointC(T, R):
    """Calculate dew point. From http://en.wikipedia.org/wiki/Dew_point
    
    T: Temperature in Celsius
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Celsius
    """

    if T is None or R is None :
        return None
    R = R / 100.0
    _gamma = 17.27 * T / (237.7 + T) + math.log(R)
    TdC = 237.7 * _gamma / (17.27 - _gamma)
    return TdC

def windchillF(T, V) :
    """Calculate wind chill. From http://www.nws.noaa.gov/om/windchill
    
    T: Temperature in Fahrenheit
    
    V: Wind speed in mph
    
    Returns Wind Chill in Fahrenheit
    """
    
    if T is None or V is None:
        return None

    # Formula only valid for temperatures below 50F and wind speeds over 3.0 mph
    if T >= 50.0 or V <= 3.0 : 
        return T
    WcF = 35.74 + 0.6215 * T + (-35.75  + 0.4275 * T) * math.pow(V, 0.16) 
    return WcF

def heatindexF(T, R) :
    """Calculate heat index. From http://www.crh.noaa.gov/jkl/?n=heat_index_calculator
    
    T: Temperature in Fahrenheit
    
    R: Relative humidity in percent
    
    Returns heat index in Fahrenheit
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

def heating_degrees(t, base):
    return max(base - t, 0) if t is not None else None

def cooling_degrees(t, base):
    return max(t - base, 0) if t is not None else None

if __name__ == '__main__':
    print heatindexF(75.0, 50.0)
    print heatindexF(80.0, 50.0)
    print heatindexF(80.0, 95.0)
    print heatindexF(90.0, 50.0)
    print heatindexF(90.0, 95.0)
