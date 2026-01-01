#
#    Copyright (c) 2018-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.wxformulas"""

import os
import time
import pytest

import weewx
import weewx.units
import weewx.wxformulas

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()


def test_dewpoint():
    """Tests dewpoint calculation across temperature and humidity ranges"""
    assert weewx.wxformulas.dewpointF(68, 50) == pytest.approx(48.7, abs=.1)
    assert weewx.wxformulas.dewpointF(32, 50) == pytest.approx(15.5, abs=.1)
    assert weewx.wxformulas.dewpointF(-10, 50) == pytest.approx(-23.5, abs=.1)
    assert weewx.wxformulas.dewpointF(-10, None) is None
    assert weewx.wxformulas.dewpointF(-10, 0) is None

def test_windchill():
    """Tests windchill calculation across temperature and windspeed ranges"""
    assert weewx.wxformulas.windchillF(55, 20) == pytest.approx(55.0, abs=0.5)
    assert weewx.wxformulas.windchillF(45, 2) == pytest.approx(45.0, abs=0.5)
    assert weewx.wxformulas.windchillF(45, 20) == pytest.approx(37.0, abs=0.5)
    assert weewx.wxformulas.windchillF(-5, 20) == pytest.approx(-29.0, abs=0.5)
    assert weewx.wxformulas.windchillF(55, None) is None

    assert weewx.wxformulas.windchillC(12, 30) == pytest.approx(12, abs=0.5)
    assert weewx.wxformulas.windchillC(5, 30) == pytest.approx(0, abs=0.5)
    assert weewx.wxformulas.windchillC(5, 3) == pytest.approx(5, abs=0.5)
    assert weewx.wxformulas.windchillC(5, None) is None

def test_heatindex():
    """Validates heat index calculation across temperature and humidity ranges"""
    assert weewx.wxformulas.heatindexF(75.0, 50.0) == pytest.approx(74.5, abs=.1)
    assert weewx.wxformulas.heatindexF(80.0, 50.0) == pytest.approx(80.8, abs=.1)
    assert weewx.wxformulas.heatindexF(80.0, 95.0) == pytest.approx(87.8, abs=.1)
    assert weewx.wxformulas.heatindexF(90.0, 50.0) == pytest.approx(94.6, abs=.1)
    assert weewx.wxformulas.heatindexF(90.0, 95.0) == pytest.approx(126.6, abs=.1)

    # Look for a smooth transition as RH crosses 40%
    assert weewx.wxformulas.heatindexF(95.0, 39.0) == pytest.approx(98.5, abs=.1)
    assert weewx.wxformulas.heatindexF(95.0, 40.0) == pytest.approx(99.0, abs=.1)
    assert weewx.wxformulas.heatindexF(95.0, 41.0) == pytest.approx(99.5, abs=.1)

    assert weewx.wxformulas.heatindexF(90, None) is None

    assert weewx.wxformulas.heatindexC(30, 80) == pytest.approx(37.7, abs=.1)
    assert weewx.wxformulas.heatindexC(30, None) is None

def test_altimeter_pressure():
    """Validates US and Metric altimeter pressure calculations"""
    assert weewx.wxformulas.altimeter_pressure_US(28.0, 0.0) == pytest.approx(28.002, abs=1e-3)
    assert weewx.wxformulas.altimeter_pressure_US(28.0, 1000.0) == pytest.approx(29.043, abs=1e-3)
    assert weewx.wxformulas.altimeter_pressure_US(28.0, None) is None
    assert weewx.wxformulas.altimeter_pressure_Metric(948.08, 0.0) == pytest.approx(948.2, abs=.1)
    assert weewx.wxformulas.altimeter_pressure_Metric(948.08, 304.8) == pytest.approx(983.4, abs=.1)
    assert weewx.wxformulas.altimeter_pressure_Metric(948.08, None) is None

def test_solar_rad():
    """Validates solar radiation calculation at different times"""
    results = [weewx.wxformulas.solar_rad_Bras(42, -72, 0, t * 3600 + 1422936471) for t in range(24)]
    expected = [0, 0, 0, 0, 0, 0, 0, 0, 1.86, 100.81, 248.71,
                374.68, 454.90, 478.76, 443.47, 353.23, 220.51, 73.71, 0, 0, 0,
                0, 0, 0]
    assert results == pytest.approx(expected, abs=1e-2)

    results = [weewx.wxformulas.solar_rad_RS(42, -72, 0, t * 3600 + 1422936471) for t in range(24)]
    expected = [0, 0, 0, 0, 0, 0, 0, 0, 0.09, 79.31, 234.77,
                369.80, 455.66, 481.15, 443.44, 346.81, 204.64, 52.63, 0, 0, 0,
                0, 0, 0]
    assert results == pytest.approx(expected, abs=1e-2)

def test_humidex():
    """Validates humidex calculation against known values"""
    assert weewx.wxformulas.humidexC(30.0, 80.0) == pytest.approx(43.66, abs=1e-2)
    assert weewx.wxformulas.humidexC(30.0, 20.0) == pytest.approx(30.00, abs=1e-2)
    assert weewx.wxformulas.humidexC(0.0, 80.0) == pytest.approx(0, abs=1e-2)
    assert weewx.wxformulas.humidexC(30.0, None) is None

def test_equation_of_time():
    # 1 October
    assert weewx.wxformulas.equation_of_time(274) == pytest.approx(0.1889, abs=1e-4)

def test_hour_angle():
    assert weewx.wxformulas.hour_angle(15.5, -16.25, 274) == pytest.approx(0.6821, abs=1e-4)
    assert weewx.wxformulas.hour_angle(0, -16.25, 274) == pytest.approx(2.9074, abs=1e-4)

def test_solar_declination():
    # 1 October
    assert weewx.wxformulas.solar_declination(274) == pytest.approx(-0.075274, abs=1e-6)

def test_sun_radiation():
    assert weewx.wxformulas.sun_radiation(doy=274,
                                          latitude_deg=16.217, longitude_deg=-16.25,
                                          tod_utc=16.0,
                                          interval=1.0) == pytest.approx(3.543, abs=1e-3)

def test_longwave_radiation():
    # In mm/day
    assert weewx.wxformulas.longwave_radiation(Tmin_C=19.1, Tmax_C=25.1,
                                               ea=2.1, Rs=14.5, Rso=18.8, rh=50) == pytest.approx(3.5, abs=.1)
    assert weewx.wxformulas.longwave_radiation(Tmin_C=28, Tmax_C=28,
                                               ea=3.402, Rs=0, Rso=0, rh=40) == pytest.approx(2.4, abs=.1)

def test_ET():
    sr_mean_wpm2 = 680.56  # == 2.45 MJ/m^2/hr
    timestamp = 1475337600  # 1-Oct-2016 at 16:00UTC
    assert weewx.wxformulas.evapotranspiration_Metric(Tmin_C=38, Tmax_C=38,
                                                      rh_min=52, rh_max=52,
                                                      sr_mean_wpm2=sr_mean_wpm2,
                                                      ws_mps=3.3,
                                                      wind_height_m=2,
                                                      latitude_deg=16.217,
                                                      longitude_deg=-16.25,
                                                      altitude_m=8, timestamp=timestamp) == pytest.approx(0.63, abs=1e-2)

    sr_mean_wpm2 = 0.0  # Night time
    timestamp = 1475294400  # 1-Oct-2016 at 04:00UTC (0300 local)
    assert weewx.wxformulas.evapotranspiration_Metric(Tmin_C=28, Tmax_C=28,
                                                      rh_min=90, rh_max=90,
                                                      sr_mean_wpm2=sr_mean_wpm2,
                                                      ws_mps=3.3,
                                                      wind_height_m=2,
                                                      latitude_deg=16.217,
                                                      longitude_deg=-16.25,
                                                      altitude_m=8, timestamp=timestamp) == pytest.approx(0.03, abs=1e-2)
    sr_mean_wpm2 = 860
    timestamp = 1469829600  # 29-July-2016 22:00 UTC (15:00 local time)
    assert weewx.wxformulas.evapotranspiration_US(Tmin_F=87.8, Tmax_F=89.1,
                                                  rh_min=34, rh_max=38,
                                                  sr_mean_wpm2=sr_mean_wpm2, ws_mph=9.58,
                                                  wind_height_ft=6,
                                                  latitude_deg=45.7, longitude_deg=-121.5,
                                                  altitude_ft=700, timestamp=timestamp) == pytest.approx(0.028, abs=1e-3)
