#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Various weather related formulas and utilities."""

from __future__ import absolute_import
from __future__ import print_function

import logging
import cmath
import math
import time

import weewx.uwxutils
import weewx.units
from weewx.units import CtoK, CtoF, FtoC, mph_to_knot, kph_to_knot, mps_to_knot
from weewx.units import INHG_PER_MBAR, METER_PER_FOOT, METER_PER_MILE, MM_PER_INCH

log = logging.getLogger(__name__)


def dewpointF(T, R):
    """Calculate dew point. 
    
    T: Temperature in Fahrenheit
    
    R: Relative humidity in percent.
    
    Returns: Dewpoint in Fahrenheit
    Examples:
    
    >>> print("%.1f" % dewpointF(68, 50))
    48.7
    >>> print("%.1f" % dewpointF(32, 50))
    15.5
    >>> print("%.1f" % dewpointF(-10, 50))
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
    http://www.nws.noaa.gov/om/cold/wind_chill.shtml
    
    T_F: Temperature in Fahrenheit
    
    V_mph: Wind speed in mph
    
    Returns Wind Chill in Fahrenheit
    """

    if T_F is None or V_mph is None:
        return None

    # only valid for temperatures below 50F and wind speeds over 3.0 mph
    if T_F >= 50.0 or V_mph <= 3.0:
        return T_F

    WcF = 35.74 + 0.6215 * T_F + (-35.75 + 0.4275 * T_F) * math.pow(V_mph, 0.16)
    return WcF


def windchillMetric(T_C, V_kph):
    """Wind chill, metric version, with wind in kph.
    
    T: Temperature in Celsius
    
    V: Wind speed in kph
    
    Returns wind chill in Celsius"""

    if T_C is None or V_kph is None:
        return None

    T_F = CtoF(T_C)
    V_mph = 0.621371192 * V_kph

    WcF = windchillF(T_F, V_mph)

    return FtoC(WcF) if WcF is not None else None


# For backwards compatibility
windchillC = windchillMetric


def windchillMetricWX(T_C, V_mps):
    """Wind chill, metric version, with wind in mps.
    
    T: Temperature in Celsius
    
    V: Wind speed in mps
    
    Returns wind chill in Celsius"""

    if T_C is None or V_mps is None:
        return None

    T_F = CtoF(T_C)
    V_mph = 2.237 * V_mps

    WcF = windchillF(T_F, V_mph)

    return FtoC(WcF) if WcF is not None else None


def heatindexF(T, R, algorithm='new'):
    """Calculate heat index.

    The 'new' algorithm uses: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml

    T: Temperature in Fahrenheit

    R: Relative humidity in percent

    Returns heat index in Fahrenheit

    Examples (Expected values obtained from https://www.wpc.ncep.noaa.gov/html/heatindex.shtml):

    >>> print("%0.0f" % heatindexF(75.0, 50.0))
    75
    >>> print("%0.0f" % heatindexF(80.0, 50.0))
    81
    >>> print("%0.0f" % heatindexF(80.0, 95.0))
    88
    >>> print("%0.0f" % heatindexF(90.0, 50.0))
    95
    >>> print("%0.0f" % heatindexF(90.0, 95.0))
    127

    """
    if T is None or R is None:
        return None

    if algorithm == 'new':
        # Formula only valid for temperatures over 40F:
        if T <= 40.0:
            return T

        # Use simplified formula
        hi_F = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (R * 0.094))

        # Apply full formula if the above, averaged with temperature, is greater than 80F:
        if (hi_F + T) / 2.0 >= 80.0:
            hi_F = -42.379 \
                   + 2.04901523 * T \
                   + 10.14333127 * R \
                   - 0.22475541 * T * R \
                   - 6.83783e-3 * T ** 2 \
                   - 5.481717e-2 * R ** 2 \
                   + 1.22874e-3 * T ** 2 * R \
                   + 8.5282e-4 * T * R ** 2 \
                   - 1.99e-6 * T ** 2 * R ** 2
            # Apply an adjustment for low humidities
            if R < 13 and 80 < T < 112:
                adjustment = ((13 - R) / 4.0) * math.sqrt((17 - abs(T - 95.)) / 17.0)
                hi_F -= adjustment
            # Apply an adjustment for high humidities
            elif R > 85 and 80 <= T < 87:
                adjustment = ((R - 85) / 10.0) * ((87 - T) / 5.0)
                hi_F += adjustment
    else:
        # Formula only valid for temperatures 80F or more, and RH 40% or more:
        if T < 80.0 or R < 40.0:
            return T

        hi_F = -42.379 \
               + 2.04901523 * T \
               + 10.14333127 * R \
               - 0.22475541 * T * R \
               - 6.83783e-3 * T ** 2 \
               - 5.481717e-2 * R ** 2 \
               + 1.22874e-3 * T ** 2 * R \
               + 8.5282e-4 * T * R ** 2 \
               - 1.99e-6 * T ** 2 * R ** 2
        if hi_F < T:
            hi_F = T

    return hi_F


def heatindexC(T_C, R, algorithm='new'):
    if T_C is None or R is None:
        return None
    T_F = CtoF(T_C)
    hi_F = heatindexF(T_F, R, algorithm)
    return FtoC(hi_F)


def heating_degrees(t, base):
    return max(base - t, 0) if t is not None else None


def cooling_degrees(t, base):
    return max(t - base, 0) if t is not None else None


def altimeter_pressure_US(SP_inHg, Z_foot, algorithm='aaASOS'):
    """Calculate the altimeter pressure, given the raw, station pressure in inHg and the altitude
    in feet.
        
    Examples:
    >>> print("%.2f" % altimeter_pressure_US(28.0, 0.0))
    28.00
    >>> print("%.2f" % altimeter_pressure_US(28.0, 1000.0))
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
    >>> print("%.1f" % altimeter_pressure_Metric(948.08, 0.0))
    948.2
    >>> print("%.1f" % altimeter_pressure_Metric(948.08, 304.8))
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
    return math.exp(-elev_meter / (t_K * 29.263))


def sealevel_pressure_Metric(sp_mbar, elev_meter, t_C):
    """Convert station pressure to sea level pressure.  This implementation was copied from wview.

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


def calculate_delta(newtotal, oldtotal, delta_key='rain'):
    """Calculate the differential given two cumulative measurements."""
    if newtotal is not None and oldtotal is not None:
        if newtotal >= oldtotal:
            delta = newtotal - oldtotal
        else:
            log.info("'%s' counter reset detected: new=%s old=%s", delta_key,
                     newtotal, oldtotal)
            delta = None
    else:
        delta = None
    return delta

# For backwards compatibility:
calculate_rain = calculate_delta

def solar_rad_Bras(lat, lon, altitude_m, ts=None, nfac=2):
    """Calculate maximum solar radiation using Bras method
    http://www.ecy.wa.gov/programs/eap/models.html

    lat, lon - latitude and longitude in decimal degrees

    altitude_m - altitude in meters

    ts - timestamp as unix epoch

    nfac - atmospheric turbidity (2=clear, 4-5=smoggy)

    Example:

    >>> for t in range(0,24):
    ...    print("%.2f" % solar_rad_Bras(42, -72, 0, t*3600+1422936471))
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
        el = alm.sun.alt  # solar elevation degrees from horizon
        R = alm.sun.earth_distance
        # NREL solar constant W/m^2
        nrel = 1367.0
        # radiation on horizontal surface at top of atmosphere (bras eqn 2.9)
        sinel = math.sin(math.radians(el))
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
    ...    print("%.2f" % solar_rad_RS(42, -72, 0, t*3600+1422936471))
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
        el = alm.sun.alt  # solar elevation degrees from horizon
        R = alm.sun.earth_distance
        z = altitude_m
        nrel = 1367.0  # NREL solar constant, W/m^2
        sinal = math.sin(math.radians(el))
        if sinal >= 0:  # sun must be above horizon
            rm = math.pow((288.0 - 0.0065 * z) / 288.0, 5.256) \
                 / (sinal + 0.15 * math.pow(el + 3.885, -1.253))
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
    >>> print("%.2f" % humidexC(30.0, 80.0))
    43.64
    >>> print("%.2f" % humidexC(30.0, 20.0))
    30.00
    >>> print("%.2f" % humidexC(0, 80.0))
    0.00
    >>> print(humidexC(30.0, None))
    None
    """
    try:
        dp_C = dewpointC(t_C, rh)
        dp_K = CtoK(dp_C)
        e = 6.11 * math.exp(5417.7530 * (1 / 273.16 - 1 / dp_K))
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
    mag_knts = abs(ws_kts)
    if mag_knts is None:
        beaufort_mag = None
    elif mag_knts < 1:
        beaufort_mag = 0
    elif mag_knts < 4:
        beaufort_mag = 1
    elif mag_knts < 7:
        beaufort_mag = 2
    elif mag_knts < 11:
        beaufort_mag = 3
    elif mag_knts < 17:
        beaufort_mag = 4
    elif mag_knts < 22:
        beaufort_mag = 5
    elif mag_knts < 28:
        beaufort_mag = 6
    elif mag_knts < 34:
        beaufort_mag = 7
    elif mag_knts < 41:
        beaufort_mag = 8
    elif mag_knts < 48:
        beaufort_mag = 9
    elif mag_knts < 56:
        beaufort_mag = 10
    elif mag_knts < 64:
        beaufort_mag = 11
    else:
        beaufort_mag = 12

    if isinstance(ws_kts, complex):
        return cmath.rect(beaufort_mag, cmath.phase(ws_kts))
    else:
        return beaufort_mag


weewx.units.conversionDict['mile_per_hour']['beaufort'] = lambda x : beaufort(mph_to_knot(x))
weewx.units.conversionDict['knot']['beaufort'] = beaufort
weewx.units.conversionDict['km_per_hour']['beaufort'] = lambda x: beaufort(kph_to_knot(x))
weewx.units.conversionDict['meter_per_second']['beaufort'] = lambda x : beaufort(mps_to_knot(x))
weewx.units.default_unit_format_dict['beaufort'] = "%d"

def equation_of_time(doy):
    """Equation of time in minutes. Plus means sun leads local time.
    
    Example (1 October):
    >>> print("%.4f" % equation_of_time(274))
    0.1889
    """
    b = 2 * math.pi * (doy - 81) / 364.0
    return 0.1645 * math.sin(2 * b) - 0.1255 * math.cos(b) - 0.025 * math.sin(b)


def hour_angle(t_utc, longitude, doy):
    """Solar hour angle at a given time in radians.
    
    t_utc: The time in UTC.
    longitude: the longitude in degrees
    doy: The day of year
    
    Returns hour angle in radians. 0 <= omega < 2*pi
    
    Example:
    >>> print("%.4f radians" % hour_angle(15.5, -16.25, 274))
    0.6821 radians
    >>> print("%.4f radians" % hour_angle(0, -16.25, 274))
    2.9074 radians
    """
    Sc = equation_of_time(doy)
    omega = (math.pi / 12.0) * (t_utc + longitude / 15.0 + Sc - 12)
    if omega < 0:
        omega += 2.0 * math.pi
    return omega


def solar_declination(doy):
    """Solar declination for the day of the year in radians
    
    Example (1 October is the 274th day of the year):
    >>> print("%.6f" % solar_declination(274))
    -0.075274
    """
    return 0.409 * math.sin(2.0 * math.pi * doy / 365 - 1.39)


def sun_radiation(doy, latitude_deg, longitude_deg, tod_utc, interval):
    """Extraterrestrial radiation. Radiation at the top of the atmosphere
    
    doy: Day-of-year

    latitude_deg, longitude_deg: Lat and lon in degrees

    tod_utc: Time-of-day (UTC) at the end of the interval in hours (0-24)

    interval: The time interval over which the radiation is to be calculated in hours

    Returns the (average?) solar radiation over the time interval in MJ/m^2/hr
    
    Example:
    >>> print("%.3f" % sun_radiation(doy=274, latitude_deg=16.217,
    ...                              longitude_deg=-16.25, tod_utc=16.0, interval=1.0))
    3.543
    """

    # Solar constant in MJ/m^2/hr
    Gsc = 4.92

    delta = solar_declination(doy)

    earth_distance = 1.0 + 0.033 * math.cos(2.0 * math.pi * doy / 365.0)  # dr

    start_utc = tod_utc - interval
    stop_utc = tod_utc
    start_omega = hour_angle(start_utc, longitude_deg, doy)
    stop_omega = hour_angle(stop_utc, longitude_deg, doy)

    latitude_radians = math.radians(latitude_deg)

    part1 = (stop_omega - start_omega) * math.sin(latitude_radians) * math.sin(delta)
    part2 = math.cos(latitude_radians) * math.cos(delta) * (math.sin(stop_omega)
                                                            - math.sin(start_omega))

    # http://www.fao.org/docrep/x0490e/x0490e00.htm Eqn 28
    Ra = (12.0 / math.pi) * Gsc * earth_distance * (part1 + part2)

    if Ra < 0:
        Ra = 0

    return Ra


def longwave_radiation(Tmin_C, Tmax_C, ea, Rs, Rso, rh):
    """Calculate the net long-wave radiation.
    Ref: http://www.fao.org/docrep/x0490e/x0490e00.htm Eqn 39
    
    Tmin_C: Minimum temperature during the calculation period
    Tmax_C: Maximum temperature during the calculation period
    ea: Actual vapor pressure in kPa
    Rs: Measured radiation. See below for units.
    Rso: Calculated clear-wky radiation. See below for units.
    rh: Relative humidity in percent
    
    Because the formula uses the ratio of Rs to Rso, their actual units do not matter,
    so long as they use the same units.
    
    Returns back radiation in MJ/m^2/day
    
    Example:
    >>> print("%.1f mm/day" % longwave_radiation(Tmin_C=19.1, Tmax_C=25.1, ea=2.1,
    ...     Rs=14.5, Rso=18.8, rh=50))
    3.5 mm/day
    
    Night time example. Set rh = 40% to reproduce the Rs/Rso ratio of 0.8 used in the paper.
    >>> print("%.1f mm/day" % longwave_radiation(Tmin_C=28, Tmax_C=28, ea=3.402,
    ...     Rs=0, Rso=0, rh=40))
    2.4 mm/day
    """
    # Calculate temperatures in Kelvin:
    Tmin_K = Tmin_C + 273.16
    Tmax_K = Tmax_C + 273.16

    # Stefan-Boltzman constant in MJ/K^4/m^2/day
    sigma = 4.903e-09

    # Use the ratio of measured to expected radiation as a measure of cloudiness, but
    # only if it's daylight
    if Rso:
        cloud_factor = Rs / Rso
    else:
        # If it's nighttime (no expected radiation), then use this totally made up formula
        if rh > 80:
            # Humid. Lots of clouds
            cloud_factor = 0.3
        elif rh > 40:
            # Somewhat humid. Modest cloud cover
            cloud_factor = 0.5
        else:
            # Low humidity. No clouds.
            cloud_factor = 0.8

    # Calculate the longwave (back) radiation (Eqn 39). Result will be in MJ/m^2/day.
    Rnl_part1 = sigma * (Tmin_K ** 4 + Tmax_K ** 4) / 2.0
    Rnl_part2 = (0.34 - 0.14 * math.sqrt(ea))
    Rnl_part3 = (1.35 * cloud_factor - 0.35)
    Rnl = Rnl_part1 * Rnl_part2 * Rnl_part3

    return Rnl


def evapotranspiration_Metric(Tmin_C, Tmax_C, rh_min, rh_max, sr_mean_wpm2,
                              ws_mps, wind_height_m, latitude_deg, longitude_deg, altitude_m,
                              timestamp, albedo=0.23, cn=37, cd=0.34):
    """Calculate the rate of evapotranspiration during a one-hour time period.
    Ref: http://www.fao.org/docrep/x0490e/x0490e00.htm.

    The document "Step by Step Calculation of the Penman-Monteith Evapotranspiration"
    https://edis.ifas.ufl.edu/pdf/AE/AE45900.pdf is also helpful. See it for values
    of cn and cd.

    Args:
 
        Tmin_C (float): Minimum temperature during the hour in degrees Celsius.
        Tmax_C (float): Maximum temperature during the hour in degrees Celsius.
        rh_min (float): Minimum relative humidity during the hour in percent.
        rh_max (float): Maximum relative humidity during the hour in percent.
        sr_mean_wpm2 (float): Mean solar radiation during the hour in watts per sq meter.
        ws_mps (float): Average wind speed during the hour in meters per second.
        wind_height_m (float): Height in meters at which windspeed is measured.
        latitude_deg (float): Latitude of the station in degrees.
        longitude_deg (float): Longitude of the station in degrees.
        altitude_m (float): Altitude of the station in meters.
        timestamp (float): The time, as unix epoch time, at the end of the hour.
        albedo (float): Albedo. Default is 0.23 (grass reference crop).
        cn (float): The numerator constant for the reference crop type and time step.
            Default is 37 (short reference crop).
        cd (float): The denominator constant for the reference crop type and time step.
            Default is 0.34 (daytime short reference crop).

    Returns:
        float: Evapotranspiration in mm/hr
    
    Example (Example 19 in the reference document):
    >>> sr_mean_wpm2 = 680.56     # == 2.45 MJ/m^2/hr
    >>> timestamp = 1475337600    # 1-Oct-2016 at 16:00UTC
    >>> print("ET0 = %.2f mm/hr" % evapotranspiration_Metric(Tmin_C=38, Tmax_C=38,
    ...                                rh_min=52, rh_max=52,
    ...                                sr_mean_wpm2=sr_mean_wpm2, ws_mps=3.3, wind_height_m=2,
    ...                                latitude_deg=16.217, longitude_deg=-16.25, altitude_m=8,
    ...                                timestamp=timestamp))
    ET0 = 0.63 mm/hr
    
    Another example, this time for night
    >>> sr_mean_wpm2 = 0.0        # night time
    >>> timestamp = 1475294400    # 1-Oct-2016 at 04:00UTC (0300 local)
    >>> print("ET0 = %.2f mm/hr" % evapotranspiration_Metric(Tmin_C=28, Tmax_C=28,
    ...                                rh_min=90, rh_max=90,
    ...                                sr_mean_wpm2=sr_mean_wpm2, ws_mps=3.3, wind_height_m=2,
    ...                                latitude_deg=16.217, longitude_deg=-16.25, altitude_m=8,
    ...                                timestamp=timestamp))
    ET0 = 0.03 mm/hr
    """
    if None in (Tmin_C, Tmax_C, rh_min, rh_max, sr_mean_wpm2, ws_mps,
                latitude_deg, longitude_deg, timestamp):
        return None

    if wind_height_m is None:
        wind_height_m = 2.0
    if altitude_m is None:
        altitude_m = 0.0

    # figure out the day of year [1-366] from the timestamp
    doy = time.localtime(timestamp)[7] - 1
    # Calculate the UTC time-of-day in hours
    time_tt_utc = time.gmtime(timestamp)
    tod_utc = time_tt_utc.tm_hour + time_tt_utc.tm_min / 60.0 + time_tt_utc.tm_sec / 3600.0

    # Calculate mean temperature
    tavg_C = (Tmax_C + Tmin_C) / 2.0

    # Mean humidity
    rh_avg = (rh_min + rh_max) / 2.0

    # Adjust windspeed for height
    u2 = 4.87 * ws_mps / math.log(67.8 * wind_height_m - 5.42)

    # Calculate the atmospheric pressure in kPa
    p = 101.3 * math.pow((293.0 - 0.0065 * altitude_m) / 293.0, 5.26)
    # Calculate the psychrometric constant in kPa/C (Eqn 8)
    gamma = 0.665e-03 * p

    # Calculate mean saturation vapor pressure, converting from hPa to kPa (Eqn 12)
    etmin = weewx.uwxutils.TWxUtils.SaturationVaporPressure(Tmin_C, 'vaTeten') / 10.0
    etmax = weewx.uwxutils.TWxUtils.SaturationVaporPressure(Tmax_C, 'vaTeten') / 10.0
    e0T = (etmin + etmax) / 2.0

    # Calculate the slope of the saturation vapor pressure curve in kPa/C (Eqn 13)
    delta = 4098.0 * (0.6108 * math.exp(17.27 * tavg_C / (tavg_C + 237.3))) / \
            ((tavg_C + 237.3) * (tavg_C + 237.3))

    # Calculate actual vapor pressure from relative humidity (Eqn 17)
    ea = (etmin * rh_max + etmax * rh_min) / 200.0

    # Convert solar radiation from W/m^2 to MJ/m^2/hr
    Rs = sr_mean_wpm2 * 3.6e-3

    # Net shortwave (measured) radiation in MJ/m^2/hr (eqn 38)
    Rns = (1.0 - albedo) * Rs

    # Extraterrestrial radiation in MJ/m^2/hr
    Ra = sun_radiation(doy, latitude_deg, longitude_deg, tod_utc, interval=1.0)
    # Clear sky solar radiation in MJ/m^2/hr (eqn 37)
    Rso = (0.75 + 2e-5 * altitude_m) * Ra

    # Longwave (back) radiation. Convert from MJ/m^2/day to MJ/m^2/hr (Eqn 39):
    Rnl = longwave_radiation(Tmin_C, Tmax_C, ea, Rs, Rso, rh_avg) / 24.0

    # Calculate net radiation at the surface in MJ/m^2/hr (Eqn. 40)
    Rn = Rns - Rnl

    # Calculate the soil heat flux. (see section "For hourly or shorter 
    # periods" in http://www.fao.org/docrep/x0490e/x0490e07.htm#radiation 
    G = 0.1 * Rn if Rs else 0.5 * Rn

    # Put it all together. Result is in mm/hr (Eqn 53)    
    ET0 = (0.408 * delta * (Rn - G) + gamma * (cn / (tavg_C + 273)) * u2 * (e0T - ea)) \
          / (delta + gamma * (1 + cd * u2))

    # We don't allow negative ET's
    if ET0 < 0:
        ET0 = 0

    return ET0


def evapotranspiration_US(Tmin_F, Tmax_F, rh_min, rh_max,
                          sr_mean_wpm2, ws_mph, wind_height_ft,
                          latitude_deg, longitude_deg, altitude_ft, timestamp,
                          albedo=0.23, cn=37, cd=0.34):
    """Calculate the rate of evapotranspiration during a one-hour time period,
    returning result in inches/hr.

    See function evapotranspiration_Metric() for references.

    Args:
 
        Tmin_F (float): Minimum temperature during the hour in degrees Fahrenheit.
        Tmax_F (float): Maximum temperature during the hour in degrees Fahrenheit.
        rh_min (float): Minimum relative humidity during the hour in percent.
        rh_max (float): Maximum relative humidity during the hour in percent.
        sr_mean_wpm2 (float): Mean solar radiation during the hour in watts per sq meter.
        ws_mph (float): Average wind speed during the hour in miles per hour.
        wind_height_ft (float): Height in feet at which windspeed is measured.
        latitude_deg (float): Latitude of the station in degrees.
        longitude_deg (float): Longitude of the station in degrees.
        altitude_ft (float): Altitude of the station in feet.
        timestamp (float): The time, as unix epoch time, at the end of the hour.
        albedo (float): Albedo. Default is 0.23 (grass reference crop).
        cn (float): The numerator constant for the reference crop type and time step.
            Default is 37 (short reference crop).
        cd (float): The denominator constant for the reference crop type and time step.
            Default is 0.34 (daytime short reference crop).

    Returns:
        float: Evapotranspiration in inches/hr
    
    Example (using data from HR station):
    >>> sr_mean_wpm2 = 860
    >>> timestamp = 1469829600  # 29-July-2016 22:00 UTC (15:00 local time)
    >>> print("ET0 = %.3f in/hr" % evapotranspiration_US(Tmin_F=87.8, Tmax_F=89.1,
    ...                                rh_min=34, rh_max=38,
    ...                                sr_mean_wpm2=sr_mean_wpm2, ws_mph=9.58, wind_height_ft=6,
    ...                                latitude_deg=45.7, longitude_deg=-121.5, altitude_ft=700,
    ...                                timestamp=timestamp))
    ET0 = 0.028 in/hr
    """
    try:
        Tmin_C = FtoC(Tmin_F)
        Tmax_C = FtoC(Tmax_F)
        ws_mps = ws_mph * METER_PER_MILE / 3600.0
        wind_height_m = wind_height_ft * METER_PER_FOOT
        altitude_m = altitude_ft * METER_PER_FOOT
    except TypeError:
        return None
    evt = evapotranspiration_Metric(Tmin_C=Tmin_C, Tmax_C=Tmax_C,
                                    rh_min=rh_min, rh_max=rh_max, sr_mean_wpm2=sr_mean_wpm2,
                                    ws_mps=ws_mps, wind_height_m=wind_height_m,
                                    latitude_deg=latitude_deg, longitude_deg=longitude_deg,
                                    altitude_m=altitude_m, timestamp=timestamp,
                                    albedo=albedo, cn=cn, cd=cd)
    return evt / MM_PER_INCH if evt is not None else None


if __name__ == "__main__":

    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
