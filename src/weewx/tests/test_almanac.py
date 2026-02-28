#
#    Copyright (c) 2021-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.almanac"""
import locale
import os

import pytest

import weeutil.Moon
from weewx.almanac import *

locale.setlocale(locale.LC_ALL, 'C')
os.environ['LANG'] = 'C'

LATITUDE = 46.0
LONGITUDE = -122.0
SPRING_TIMESTAMP = 1238180400  # 2009-03-27 12:00:00 PDT
FALL_TIMESTAMP   = 1254078000  # 2009-09-27 12:00:00 PDT

default_formatter = weewx.units.get_default_formatter()

@pytest.fixture(scope="module", autouse=True)
def set_tz():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    yield
    # No need to reset TZ as it's a test environment

class TestAlmanac:

    @pytest.fixture(autouse=True)
    def setup(self):
        # Unix epoch time
        self.ts_ue = SPRING_TIMESTAMP
        self.almanac = Almanac(self.ts_ue, LATITUDE, LONGITUDE, formatter=default_formatter)

    def test_Dublin(self):
        # Dublin julian days
        t_djd = timestamp_to_djd(self.ts_ue)
        # Test forward conversion
        assert t_djd == pytest.approx(39898.29167, abs=1e-5)
        # Test back conversion
        assert djd_to_timestamp(t_djd) == pytest.approx(self.ts_ue, abs=1e-5)

    def test_moon_extended(self):
        # Now test a more precise result for fullness of the moon:
        assert self.almanac.moon.moon_fullness == pytest.approx(1.70, abs=1e-2)
        assert str(self.almanac.moon.rise) == "06:59:14"
        assert str(self.almanac.moon.transit) == "14:01:57"
        assert str(self.almanac.moon.set) == "21:20:06"

        # Location of the moon
        assert self.almanac.moon.az == pytest.approx(133.55, abs=1e-2)
        assert self.almanac.moon.alt == pytest.approx(47.89, abs=1e-2)

        assert str(self.almanac.next_full_moon) == "04/09/09 07:55:49"
        assert str(self.almanac.next_new_moon) == "04/24/09 20:22:33"
        assert str(self.almanac.next_first_quarter_moon) == "04/02/09 07:33:42"

    def test_sun_extended(self):
        # Test backwards compatibility
        assert str(self.almanac.sunrise) == "06:56:36"
        assert str(self.almanac.sunset) == "19:30:41"

        # Use pyephem
        assert str(self.almanac.sun.rise) == "06:56:36"
        assert str(self.almanac.sun.transit) == "13:13:13"
        assert str(self.almanac.sun.set) == "19:30:41"

        # Equinox / solstice
        assert str(self.almanac.next_vernal_equinox) == "03/20/10 10:32:11"
        assert str(self.almanac.next_autumnal_equinox) == "09/22/09 14:18:39"
        assert str(self.almanac.next_summer_solstice) == "06/20/09 22:45:40"
        assert str(self.almanac.previous_winter_solstice) == "12/21/08 04:03:36"
        assert str(self.almanac.next_winter_solstice) == "12/21/09 09:46:38"

        # Location of the sun
        assert self.almanac.sun.az == pytest.approx(154.14, abs=1e-2)
        assert self.almanac.sun.alt == pytest.approx(44.02, abs=1e-2)

        # Visible time
        assert self.almanac.sun.visible.long_form() == "12 hours, 34 minutes, 4 seconds"
        # Change in visible time:
        assert str(self.almanac.sun.visible_change().long_form()) == "3 minutes, 15 seconds"
        # Do it again, but in the fall when daylight is decreasing:
        almanac = Almanac(FALL_TIMESTAMP, LATITUDE, LONGITUDE, formatter=default_formatter)
        assert str(almanac.sun.visible_change().long_form()) == "3 minutes, 13 seconds"

    def test_mars(self):
        assert str(self.almanac.mars.rise) == "06:08:57"
        assert str(self.almanac.mars.transit) == "11:34:13"
        assert str(self.almanac.mars.set) == "17:00:04"
        assert self.almanac.mars.sun_distance == pytest.approx(1.3857, abs=1e-4)

    def test_jupiter(self):
        # Specialized attribute for Jupiter:
        assert str(self.almanac.jupiter.cmlI) == "310:55:32.7"
        # Should fail if applied to a different body
        with pytest.raises(AttributeError):
            self.almanac.venus.cmlI

    def test_star(self):
        assert self.almanac.castor.rise.raw == pytest.approx(1238178997, abs=0.5)
        assert self.almanac.castor.transit.raw == pytest.approx(1238210429, abs=0.5)
        assert self.almanac.castor.set.raw == pytest.approx(1238155697, abs=0.5)

    def test_sidereal(self):
        assert self.almanac.sidereal_time == pytest.approx(348.3400, abs=1e-4)

    def test_exceptions_pyephem(self):
        # Try a nonsense body
        with pytest.raises(AttributeError):
            self.almanac.bar.rise
        # Try a nonsense tag
        with pytest.raises(AttributeError):
            self.almanac.sun.foo

def test_always_up():
    # Time and location where the sun is always up
    t = 1371044003  # 2013-06-12 06:33:23 PDT (1371044003)
    almanac = Almanac(t, 74.0, 0.0, formatter=default_formatter)
    assert almanac(horizon=-6).sun(use_center=1).rise.raw is None
    assert almanac(horizon=-6).sun(use_center=1).set.raw is None
    assert almanac(horizon=-6).sun(use_center=1).visible.raw == 86400
    assert almanac(horizon=-6).sun(use_center=1).visible.long_form() == \
                     "24 hours, 0 minutes, 0 seconds"

    # Now where the sun is always down:
    almanac = Almanac(t, -74.0, 0.0, formatter=default_formatter)
    assert almanac(horizon=-6).sun(use_center=1).rise.raw is None
    assert almanac(horizon=-6).sun(use_center=1).set.raw is None
    assert almanac(horizon=-6).sun(use_center=1).visible.raw == 0
    assert almanac(horizon=-6).sun(use_center=1).visible.long_form() == \
                     "0 hours, 0 minutes, 0 seconds"

def test_naval_observatory():
    #
    # pyephem "Naval Observatory" example.
    t = 1252256400  # 2009-09-06 17:00:00 UTC (1252256400)
    atlanta = Almanac(t, 33.8, -84.4, pressure=0, horizon=-34.0 / 60.0,
                      formatter=default_formatter)
    assert atlanta.sun.previous_rising.raw == pytest.approx(1252235697, abs=0.5)
    assert atlanta.moon.next_setting.raw == pytest.approx(1252332329, abs=0.5)

    # Civil twilight examples:
    assert atlanta(horizon=-6).sun(use_center=1).previous_rising.raw == pytest.approx(1252234180, abs=0.5)
    assert atlanta(horizon=-6).sun(use_center=1).next_setting.raw == pytest.approx(1252282883, abs=0.5)

    # Try sun rise again, to make sure the horizon value cleared:
    assert atlanta.sun.previous_rising.raw == pytest.approx(1252235697, abs=0.5)


def test_moon_phases():
    """Regression test for PR #1069"""
    # First, test the defaults:
    test_default = Almanac(SPRING_TIMESTAMP, LATITUDE, LONGITUDE,
                           formatter=default_formatter)
    assert test_default.moon_phase == 'new (totally dark)'

    # Now override the moon phase descriptions:
    test_override = Almanac(SPRING_TIMESTAMP, LATITUDE, LONGITUDE,
                           moon_phases = ['pitch black'] + weeutil.Moon.moon_phases[1:],
                           formatter=default_formatter)
    assert test_override.moon_phase == 'pitch black'
