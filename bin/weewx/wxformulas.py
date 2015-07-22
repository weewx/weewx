#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Various weather related formulas and utilities."""

import math
import time
import weewx.uwxutils

INHG_PER_MBAR = 0.0295333727
METER_PER_FOOT = 0.3048
METER_PER_MILE = 1609.34
MM_PER_INCH = 25.4

def CtoK(x):
    return x + 273.15

def CtoF(x):
    return x * 1.8 + 32.0

def FtoC(x):
    return (x - 32.0) * 5.0 / 9.0

def mps_to_mph(x):
    return x * 3600.0 / METER_PER_MILE

def kph_to_mph(x):
    return x * 1000.0 / METER_PER_MILE

def degtorad(x):
    return x * math.pi / 180.0

def dewpointF(T, R):
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

    if T is None or R is None:
        return None

    TdC = dewpointC(FtoC(T), R)

    return CtoF(TdC) if TdC is not None else None

def dewpointC(T, R):
    """Calculate dew point.
    http://en.wikipedia.org/wiki/Dew_point
    
    T: Temperature in Celsius
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Celsius
    """

    if T is None or R is None:
        return None
    R = R / 100.0
    try:
        _gamma = 17.27 * T / (237.7 + T) + math.log(R)
        TdC = 237.7 * _gamma / (17.27 - _gamma)
    except (ValueError, OverflowError):
        TdC = None
    return TdC

def windchillF(T_F, V_mph):
    """Calculate wind chill.
    http://www.nws.noaa.gov/om/winter/windchill.shtml
    
    T_F: Temperature in Fahrenheit
    
    V_mph: Wind speed in mph
    
    Returns Wind Chill in Fahrenheit
    """
    
    if T_F is None or V_mph is None:
        return None

    # only valid for temperatures below 50F and wind speeds over 3.0 mph
    if T_F >= 50.0 or V_mph <= 3.0: 
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
    
    T_F = CtoF(T_C)
    V_mph = 0.621371192 * V_kph
    
    WcF = windchillF(T_F, V_mph)
    
    return FtoC(WcF) if WcF is not None else None
    
def heatindexF(T, R):
    """Calculate heat index.
    http://www.crh.noaa.gov/jkl/?n=heat_index_calculator
    
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
    if T is None or R is None:
        return None
    
    # Formula only valid for temperatures over 80F:
    if T < 80.0 or R  < 40.0:
        return T

    hi_F = -42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R - 6.83783e-3 * T**2\
    -5.481717e-2 * R**2 + 1.22874e-3 * T**2 * R + 8.5282e-4 * T * R**2 - 1.99e-6 * T**2 * R**2
    if hi_F < T:
        hi_F = T
    return hi_F

def heatindexC(T_C, R):
    if T_C is None or R is None:
        return None
    T_F = CtoF(T_C)
    hi_F = heatindexF(T_F, R)
    return FtoC(hi_F)

def heating_degrees(t, base):
    return max(base - t, 0) if t is not None else None

def cooling_degrees(t, base):
    return max(t - base, 0) if t is not None else None

def altimeter_pressure_US(SP_inHg, Z_foot, algorithm='aaASOS'):
    """Calculate the altimeter pressure, given the raw, station pressure in
    inHg and the altitude in feet.
        
    Examples:
    >>> print "%.2f" % altimeter_pressure_US(28.0, 0.0)
    28.00
    >>> print "%.2f" % altimeter_pressure_US(28.0, 1000.0)
    29.04
    """
    if SP_inHg is None or Z_foot is None:
        return None
    if SP_inHg <= 0.008859:
        return None
    return weewx.uwxutils.TWxUtilsUS.StationToAltimeter(SP_inHg, Z_foot,
                                                        algorithm=algorithm)

def altimeter_pressure_Metric(SP_mbar, Z_meter, algorithm='aaASOS'):
    """Convert from (uncorrected) station pressure to altitude-corrected
    pressure.

    Examples:
    >>> print "%.1f" % altimeter_pressure_Metric(948.08, 0.0)
    948.2
    >>> print "%.1f" % altimeter_pressure_Metric(948.08, 304.8)
    983.4
    """
    if SP_mbar is None or Z_meter is None:
        return None
    if SP_mbar <= 0.3:
        return None
    return weewx.uwxutils.TWxUtils.StationToAltimeter(SP_mbar, Z_meter,
                                                      algorithm=algorithm)

def _etterm(elev_meter, t_C):
    """Calculate elevation/temperature term for sea level calculation."""
    t_K = CtoK(t_C)
    return math.exp( - elev_meter / (t_K * 29.263))

def sealevel_pressure_Metric(sp_mbar, elev_meter, t_C):
    """Convert station pressure to sea level pressure.  This implementation
    was copied from wview.

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    t_C - temperature in degrees Celsius

    bp - sea level pressure (barometer) in millibars
    """
    if sp_mbar is None or elev_meter is None or t_C is None:
        return None
    pt = _etterm(elev_meter, t_C)
    bp_mbar = sp_mbar / pt if pt != 0 else 0
    return bp_mbar

def sealevel_pressure_US(sp_inHg, elev_foot, t_F):
    if sp_inHg is None or elev_foot is None or t_F is None:
        return None
    sp_mbar = sp_inHg / INHG_PER_MBAR
    elev_meter = elev_foot * METER_PER_FOOT
    t_C = FtoC(t_F)
    slp_mbar = sealevel_pressure_Metric(sp_mbar, elev_meter, t_C)
    slp_inHg = slp_mbar * INHG_PER_MBAR
    return slp_inHg

def calculate_rain(newtotal, oldtotal):
    """Calculate the rain differential given two cumulative measurements."""
    if newtotal is not None and oldtotal is not None:
        if newtotal >= oldtotal:
            delta = newtotal - oldtotal
        else:
            delta = None
    else:
        delta = None
    return delta

def solar_rad_Bras(lat, lon, altitude_m, ts=None, nfac=2):
    """Calculate maximum solar radiation using Bras method
    http://www.ecy.wa.gov/programs/eap/models.html

    lat, lon - latitude and longitude in decimal degrees

    altitude_m - altitude in meters

    ts - timestamp as unix epoch

    nfac - atmospheric turbidity (2=clear, 4-5=smoggy)

    Example:

    >>> for t in range(0,24):
    ...    print "%.2f" % solar_rad_Bras(42, -72, 0, t*3600+1422936471) 
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    1.86
    100.81
    248.71
    374.68
    454.90
    478.76
    443.47
    353.23
    220.51
    73.71
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    """
    from weewx.almanac import Almanac
    if ts is None:
        ts = time.time()
    sr = 0.0
    try:
        alm = Almanac(ts, lat, lon, altitude_m)
        el = alm.sun.alt # solar elevation degrees from horizon
        R = alm.sun.earth_distance
        # NREL solar constant W/m^2
        nrel = 1367.0
        # radiation on horizontal surface at top of atmosphere (bras eqn 2.9)
        sinel = math.sin(degtorad(el))
        io = sinel * nrel / (R * R)
        if sinel >= 0:
            # optical air mass (bras eqn 2.22)
            m = 1.0 / (sinel + 0.15 * math.pow(el + 3.885, -1.253))
            # molecular scattering coefficient (bras eqn 2.26)
            a1 = 0.128 - 0.054 * math.log(m) / math.log(10.0)
            # clear-sky radiation at earth surface W / m^2 (bras eqn 2.25)
            sr = io * math.exp(-nfac * a1 * m)
    except (AttributeError, ValueError, OverflowError):
        sr = None
    return sr

def solar_rad_RS(lat, lon, altitude_m, ts=None, atc=0.8):
    """Calculate maximum solar radiation
    Ryan-Stolzenbach, MIT 1972
    http://www.ecy.wa.gov/programs/eap/models.html

    lat, lon - latitude and longitude in decimal degrees

    altitude_m - altitude in meters

    ts - time as unix epoch

    atc - atmospheric transmission coefficient (0.7-0.91)

    Example:

    >>> for t in range(0,24):
    ...    print "%.2f" % solar_rad_RS(42, -72, 0, t*3600+1422936471)
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    0.09
    79.31
    234.77
    369.80
    455.66
    481.15
    443.44
    346.81
    204.64
    52.63
    0.00
    0.00
    0.00
    0.00
    0.00
    0.00
    """
    from weewx.almanac import Almanac
    if atc < 0.7 or atc > 0.91:
        atc = 0.8
    if ts is None:
        ts = time.time()
    sr = 0.0
    try:
        alm = Almanac(ts, lat, lon, altitude_m)
        el = alm.sun.alt # solar elevation degrees from horizon
        R = alm.sun.earth_distance
        z = altitude_m
        nrel = 1367.0 # NREL solar constant, W/m^2
        sinal = math.sin(degtorad(el))
        if sinal >= 0: # sun must be above horizon
            rm = math.pow((288.0-0.0065*z)/288.0,5.256)/(sinal+0.15*math.pow(el+3.885,-1.253))
            toa = nrel * sinal / (R * R)
            sr = toa * math.pow(atc, rm)
    except (AttributeError, ValueError, OverflowError):
        sr = None
    return sr

def cloudbase_Metric(t_C, rh, altitude_m):
    """Calculate the cloud base in meters

    t_C - temperature in degrees Celsius

    rh - relative humidity [0-100]

    altitude_m - altitude in meters
    """
    dp_C = dewpointC(t_C, rh)
    if dp_C is None:
        return None
    cb = (t_C - dp_C) * 1000 / 2.5
    return altitude_m + cb * METER_PER_FOOT if cb is not None else None

def cloudbase_US(t_F, rh, altitude_ft):
    """Calculate the cloud base in feet

    t_F - temperature in degrees Fahrenheit

    rh - relative humidity [0-100]

    altitude_ft - altitude in feet
    """
    dp_F = dewpointF(t_F, rh)
    if dp_F is None:
        return None
    cb = altitude_ft + (t_F - dp_F) * 1000.0 / 4.4
    return cb

def humidexC(t_C, rh):
    """Calculate the humidex
    Reference (look under heading "Humidex"):
    http://climate.weather.gc.ca/climate_normals/normals_documentation_e.html?docID=1981

    t_C - temperature in degree Celsius

    rh - relative humidity [0-100]

    Examples:
    >>> print "%.2f" % humidexC(30.0, 80.0)
    43.64
    >>> print "%.2f" % humidexC(30.0, 20.0)
    30.00
    >>> print "%.2f" % humidexC(0, 80.0)
    0.00
    >>> print humidexC(30.0, None)
    None
    """
    try:
        dp_C = dewpointC(t_C, rh)
        dp_K = CtoK(dp_C)
        e = 6.11 * math.exp(5417.7530 * (1/273.16 - 1/dp_K))
        h = 0.5555 * (e - 10.0)
    except (ValueError, OverflowError, TypeError):
        return None

    return t_C + h if h > 0 else t_C

def humidexF(t_F, rh):
    """Calculate the humidex in degree Fahrenheit

    t_F - temperature in degree Fahrenheit

    rh - relative humidity [0-100]
    """
    if t_F is None:
        return None
    h_C = humidexC(FtoC(t_F), rh)
    return CtoF(h_C) if h_C is not None else None

def apptempC(t_C, rh, ws_mps):
    """Calculate the apparent temperature in degree Celsius

    t_C - temperature in degree Celsius

    rh - relative humidity [0-100]

    ws_mps - wind speed in meters per second

    http://www.bom.gov.au/info/thermal_stress/#atapproximation
      AT = Ta + 0.33*e - 0.70*ws - 4.00
    where
      AT and Ta (air temperature) are deg-C
      e is water vapor pressure
      ws is wind speed (m/s) at elevation of 10 meters
      e = rh / 100 * 6.105 * exp(17.27 * Ta / (237.7 + Ta))
      rh is relative humidity

    http://www.ncdc.noaa.gov/societal-impacts/apparent-temp/
      AT = -2.7 + 1.04*T + 2.0*e -0.65*v
    where
      AT and T (air temperature) are deg-C
      e is vapor pressure in kPa
      v is 10m wind speed in m/sec
    """
    if t_C is None:
        return None
    if rh is None or rh < 0 or rh > 100:
        return None
    if ws_mps is None or ws_mps < 0:
        return None
    try:
        e = (rh / 100.0) * 6.105 * math.exp(17.27 * t_C / (237.7 + t_C))
        at_C = t_C + 0.33 * e - 0.7 * ws_mps - 4.0
    except (ValueError, OverflowError):
        at_C = None
    return at_C

def apptempF(t_F, rh, ws_mph):
    """Calculate apparent temperature in degree Fahrenheit

    t_F - temperature in degree Fahrenheit

    rh - relative humidity [0-100]

    ws_mph - wind speed in miles per hour
    """
    if t_F is None:
        return None
    if rh is None or rh < 0 or rh > 100:
        return None
    if ws_mph is None or ws_mph < 0:
        return None
    t_C = FtoC(t_F)
    ws_mps = ws_mph * METER_PER_MILE / 3600.0
    at_C = apptempC(t_C, rh, ws_mps)
    return CtoF(at_C) if at_C is not None else None

def beaufort(ws_kts):
    """Return the beaufort number given a wind speed in knots"""
    if ws_kts is None:
        return None
    elif ws_kts < 1:
        return 0
    elif ws_kts < 4:
        return 1
    elif ws_kts < 7:
        return 2
    elif ws_kts < 11:
        return 3
    elif ws_kts < 17:
        return 4
    elif ws_kts < 22:
        return 5
    elif ws_kts < 28:
        return 6
    elif ws_kts < 34:
        return 7
    elif ws_kts < 41:
        return 8
    elif ws_kts < 48:
        return 9
    elif ws_kts < 56:
        return 10
    elif ws_kts < 64:
        return 11
    return 12

def evapotranspiration_Metric(tmax_C, tmin_C, sr_avg, ws_mps, z_m, lat, ts=None):
    """Calculate the evapotranspiration
    http://edis.ifas.ufl.edu/ae459

    tmax_C - maximum temperature in degrees Celsius

    tmin_C - minimum temperature in degrees Celsius

    sr_avg - mean daily/hourly solar radiation in watts per sq meter per day/hr

    ws_mps - average daily/hourly wind speed in meters per second

    z_m - height in meters at which windspeed is measured

    ts - current timestamp as unix epoch

    lat - latitude in degrees

    returns evapotranspiration in mm per day/hour
    """
    if tmax_C is None or tmin_C is None or sr_avg is None or ws_mps is None:
        return None
    if ts is None:
        ts = time.time()
    # figure out the day of year [1-366] from the timestamp
    doy = time.localtime(ts)[7]
    # step 1: calculate mean temperature
    tavg_C = 0.5 * (tmax_C + tmin_C)
    # step 2: convert sr from W/m^2 per day to MJ/m^2 per day
    rs = sr_avg * 0.0864
    # step 3: adjust windspeed for height
    u2 = 4.87 * ws_mps / math.log(67.8 * z_m - 5.42)
    # step 4: calculate the slope of saturation vapor pressure curve
    slope = 4098.0 * (0.6108 * math.exp(17.27 * tavg_C / (tavg_C + 273.3))) / ((tavg_C + 273.3) * (tavg_C + 273.3))
    # step 5: calculate the atmospheric pressure
    p = 101.3 * math.pow((293.0 - 0.0065 * z_m) / 293.0, 5.26)
    # step 6: calculate the psychrometric constant
    g = 0.000665 * p
    # step 7: calculate the delta term
    dt = slope / (slope + g * (1.0 + 0.34 * u2))
    # step 8: calculate the psi term
    pt = g / (slope + g * (1.0 + 0.34 * u2))
    # step 9: calculate the temperature term
    tt = 900.0 * u2 / (tavg_C + 273.0)
    # step 10: calculate mean saturation vapor pressure
    etmin = 0.6108 * math.exp(17.27 * tmin_C / (tmin_C + 273.3))
    etmax = 0.6108 * math.exp(17.27 * tmax_C / (tmax_C + 273.3))
    es = 0.5 * (etmax + etmin)
    # step 11: calculate actual vapor pressure
    # a: if rhmax and rhmin are available
#    ea = (etmin * rhmax + etmax * rhmin) / 200.0
    # b: using only rhmax
#    ea = etmin * rhmax / 100.0
    # c: using rhavg
#    ea = rhavg * (etmin + etmax) / 200.0
    # d: with no humidity data
    ea = 0.6108 * math.exp(17.27 * tmin_C / (tmin_C + 273.3))
    # step 12: earth-sun relative distance and solar declination
    dr = 1.0 + 0.033 * math.cos(doy * 2.0 * math.pi / 365.0)
    sd = 0.409 * math.sin(doy * 2.0 * math.pi / 365.0 - 1.39)
    # step 13: convert latitude to radians
    phi = lat * math.pi / 180.0
    # step 14: sunset hour angle
    w = math.acos( - math.tan(phi) * math.tan(sd))
    # step 15: extraterrestrial radiation
    gsc = 0.082
    ra = 24.0 * 60.0 / math.pi * gsc * dr * (w * math.sin(phi) * math.sin(sd) + math.cos(phi) * math.cos(sd) * math.sin(w))
    # step 16: clear sky solar radiation
    rso = (0.75 + 2e-5 * z_m) * ra
    # step 17: net solar or net shortwave radiation
    a = 0.23
    rns = (1.0 - a) * rs
    # step 18: net outgoing long wave solar radiation
    sigma = 4.903e-9
    rnl = sigma * 0.5 * (math.pow(tmax_C + 273.16, 4) + math.pow(tmin_C + 273.16, 4)) * (0.34 - 0.14 * math.sqrt(ea)) * (1.35 * rs / rso - 0.35)
    # step 19: net radiation
    rn = rns - rnl
    # step 20: overall evapotranspiration
    ev_rad = dt * rn
    ev_wind = pt * tt * (es - ea)
    evt = ev_rad + ev_wind
    return evt

def evapotranspiration_US(tmax_F, tmin_F, sr_avg, ws_mph, z_ft, lat, ts=None):
    if tmax_F is None or tmin_F is None or sr_avg is None or ws_mph is None:
        return None
    tmax_C = FtoC(tmax_F)
    tmin_C = FtoC(tmin_F)
    ws_mps = ws_mph * METER_PER_MILE / 3600.0
    z_m = z_ft * METER_PER_FOOT
    evt = evapotranspiration_Metric(tmax_C, tmin_C, sr_avg, ws_mps, z_m, lat, ts)
    return evt / MM_PER_INCH if evt is not None else None


if __name__ == "__main__":
    
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
