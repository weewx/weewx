#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import pytest

import weewx.uwxutils


@pytest.mark.parametrize('algorithm', ['aaASOS', 'aaASOS2', 'aaMADIS', 'aaNOAA', 'aaWOB', 'aaSMT'])
@pytest.mark.parametrize('elevation', [-100, 0, 1655, 4000])
def test_altimeter_inverse_matches_forward_algorithms(algorithm, elevation):
    metric = weewx.uwxutils.TWxUtils
    us = weewx.uwxutils.TWxUtilsUS
    setting = metric.StationToAltimeter(800, elevation, algorithm)
    assert metric.AltimeterToStationPressure(setting, elevation, algorithm) == pytest.approx(800)
    pressure = weewx.uwxutils.HPaToIn(800)
    feet = weewx.uwxutils.MToFt(elevation)
    setting_us = us.StationToAltimeter(pressure, feet, algorithm)
    assert us.AltimeterToStationPressure(setting_us, feet, algorithm) == pytest.approx(pressure)


def test_asos_published_example_and_default_units():
    assert weewx.uwxutils.TWxUtilsUS.AltimeterToStationPressure(
        30.153, 5431, 'aaASOS') == pytest.approx(24.692, abs=0.001)
    assert weewx.uwxutils.TWxUtils.AltimeterToStationPressure(1013.25, 0) == pytest.approx(1013.55)
    with pytest.raises(ValueError, match='Unknown.*algorithm'):
        weewx.uwxutils.TWxUtilsUS.AltimeterToStationPressure(30, 100, 'invalid')
