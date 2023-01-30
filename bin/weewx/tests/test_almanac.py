#
#    Copyright (c) 2021-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.almanac"""
import os
import unittest

import weewx.units
from weewx.almanac import *

LATITUDE = 46.0
LONGITUDE = -122.0
SPRING_TIMESTAMP = 1238180400  # 2009-03-27 12:00:00 PDT
FALL_TIMESTAMP   = 1254078000  # 2009-09-27 12:00:00 PDT

default_formatter = weewx.units.get_default_formatter()

class AlmanacTest(unittest.TestCase):

    def setUp(self):
        os.environ['TZ'] = 'America/Los_Angeles'
        time.tzset()
        # Unix epoch time
        self.ts_ue = SPRING_TIMESTAMP
        self.almanac = Almanac(self.ts_ue, LATITUDE, LONGITUDE, formatter=default_formatter)

    def test_Dublin(self):
        # Dublin julian days
        t_djd = timestamp_to_djd(self.ts_ue)
        # Test forward conversion
        self.assertAlmostEqual(t_djd, 39898.29167, 5)
        # Test back conversion
        self.assertAlmostEqual(djd_to_timestamp(t_djd), self.ts_ue, 5)

    def test_moon(self):
        # Test backwards compatiblity with the attribute _moon_fullness
        self.assertAlmostEqual(self.almanac._moon_fullness, 3, 2)
        self.assertEqual(self.almanac.moon_phase, 'new (totally dark)')

        # Now test a more precise result for fullness of the moon:
        self.assertAlmostEqual(self.almanac.moon.moon_fullness, 1.70, 2)
        self.assertEqual(str(self.almanac.moon.rise), "06:59:14")
        self.assertEqual(str(self.almanac.moon.transit), "14:01:57")
        self.assertEqual(str(self.almanac.moon.set), "21:20:06")

        self.assertEqual(str(self.almanac.next_full_moon), "04/09/09 07:55:49")
        self.assertEqual(str(self.almanac.next_new_moon), "04/24/09 20:22:33")
        self.assertEqual(str(self.almanac.next_first_quarter_moon), "04/02/09 07:33:42")

        # Location of the moon
        self.assertAlmostEqual(self.almanac.moon.az, 133.55, 2)
        self.assertAlmostEqual(self.almanac.moon.alt, 47.89, 2)

    def test_sun(self):
        # Test backwards compatibility
        self.assertEqual(str(self.almanac.sunrise), "06:56:36")
        self.assertEqual(str(self.almanac.sunset), "19:30:41")

        # Use pyephem
        self.assertEqual(str(self.almanac.sun.rise), "06:56:36")
        self.assertEqual(str(self.almanac.sun.transit), "13:13:13")
        self.assertEqual(str(self.almanac.sun.set), "19:30:41")

        # Equinox / solstice
        self.assertEqual(str(self.almanac.next_vernal_equinox), "03/20/10 10:32:11")
        self.assertEqual(str(self.almanac.next_autumnal_equinox), "09/22/09 14:18:39")
        self.assertEqual(str(self.almanac.next_summer_solstice), "06/20/09 22:45:40")
        self.assertEqual(str(self.almanac.previous_winter_solstice), "12/21/08 04:03:36")
        self.assertEqual(str(self.almanac.next_winter_solstice), "12/21/09 09:46:38")

        # Location of the sun
        self.assertAlmostEqual(self.almanac.sun.az, 154.14, 2)
        self.assertAlmostEqual(self.almanac.sun.alt, 44.02, 2)

        # Visible time
        self.assertEqual(self.almanac.sun.visible.long_form(), "12 hours, 34 minutes, 4 seconds")
        # Change in visible time:
        self.assertEqual(str(self.almanac.sun.visible_change().long_form()), "3 minutes, 15 seconds")
        # Do it again, but in the fall when daylight is decreasing:
        almanac = Almanac(FALL_TIMESTAMP, LATITUDE, LONGITUDE, formatter=default_formatter)
        self.assertEqual(str(almanac.sun.visible_change().long_form()), "3 minutes, 13 seconds")

    def test_mars(self):
        self.assertEqual(str(self.almanac.mars.rise), "06:08:57")
        self.assertEqual(str(self.almanac.mars.transit), "11:34:13")
        self.assertEqual(str(self.almanac.mars.set), "17:00:04")
        self.assertAlmostEqual(self.almanac.mars.sun_distance, 1.3857, 4)

    def test_jupiter(self):
        # Specialized attribute for Jupiter:
        self.assertEqual(str(self.almanac.jupiter.cmlI), "310:55:32.7")
        # Should fail if applied to a different body
        with self.assertRaises(AttributeError):
            self.almanac.venus.cmlI

    def test_star(self):
        self.assertAlmostEqual(self.almanac.castor.rise.raw, 1238178997, 0)
        self.assertAlmostEqual(self.almanac.castor.transit.raw, 1238210429, 0)
        self.assertAlmostEqual(self.almanac.castor.set.raw, 1238155697, 0)

    def test_sidereal(self):
        self.assertAlmostEqual(self.almanac.sidereal_time, 348.3400, 4)

    def test_always_up(self):
        # Time and location where the sun is always up
        t = 1371044003  # 2013-06-12 06:33:23 PDT (1371044003)
        almanac = Almanac(t, 74.0, 0.0, formatter=default_formatter)
        self.assertIsNone(almanac(horizon=-6).sun(use_center=1).rise.raw)
        self.assertIsNone(almanac(horizon=-6).sun(use_center=1).set.raw)
        self.assertEqual(almanac(horizon=-6).sun(use_center=1).visible.raw, 86400)
        self.assertEqual(almanac(horizon=-6).sun(use_center=1).visible.long_form(),
                         "24 hours, 0 minutes, 0 seconds")

        # Now where the sun is always down:
        almanac = Almanac(t, -74.0, 0.0, formatter=default_formatter)
        self.assertIsNone(almanac(horizon=-6).sun(use_center=1).rise.raw)
        self.assertIsNone(almanac(horizon=-6).sun(use_center=1).set.raw)
        self.assertEqual(almanac(horizon=-6).sun(use_center=1).visible.raw, 0)
        self.assertEqual(almanac(horizon=-6).sun(use_center=1).visible.long_form(),
                         "0 hours, 0 minutes, 0 seconds")

    def test_naval_observatory(self):
        #
        # pyephem "Naval Observatory" example.
        t = 1252256400  # 2009-09-06 17:00:00 UTC (1252256400)
        atlanta = Almanac(t, 33.8, -84.4, pressure=0, horizon=-34.0 / 60.0,
                          formatter=default_formatter)
        self.assertAlmostEqual(atlanta.sun.previous_rising.raw, 1252235697, 0)
        self.assertAlmostEqual(atlanta.moon.next_setting.raw, 1252332329, 0)

        # Civil twilight examples:
        self.assertAlmostEqual(atlanta(horizon=-6).sun(use_center=1).previous_rising.raw, 1252234180, 0)
        self.assertAlmostEqual(atlanta(horizon=-6).sun(use_center=1).next_setting.raw, 1252282883, 0)

        # Try sun rise again, to make sure the horizon value cleared:
        self.assertAlmostEqual(atlanta.sun.previous_rising.raw, 1252235697, 0)

    def test_exceptions(self):
        # Try a nonsense body
        with self.assertRaises(KeyError):
            self.almanac.bar.rise

        # Try a nonsense tag
        with self.assertRaises(AttributeError):
            self.almanac.sun.foo


if __name__ == '__main__':
    unittest.main()
