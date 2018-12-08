#
#    Copyright (c) 2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.almanac"""
import os
import time
import unittest
from weewx.almanac import *


class AlmanacTest(unittest.TestCase):

    def setUp(self):
        os.environ['TZ'] = 'America/Los_Angeles'
        time.tzset()
        # Unix epoch time
        self.ts_ue = 1238180400  # 2009-03-27 12:00:00 PDT (1238180400)
        self.almanac = Almanac(self.ts_ue, 46.0, -122.0)

    def test_Dublin(self):
        # Dublin julian days
        t_djd = timestamp_to_djd(self.ts_ue)
        # Test forward conversion
        self.assertAlmostEqual(t_djd, 39898.29167, 5)
        # Test back conversion
        self.assertAlmostEqual(djd_to_timestamp(t_djd), self.ts_ue, 5)

    def test_moon(self):
        # Test backwards compatiblity with the attribute _moon_fullness
        self.assertAlmostEqual(self.almanac._moon_fullness, 5, 2)
        self.assertEqual(self.almanac.moon_phase, 'waxing crescent (increasing to full)')

        # Now test a more precise result for fullness of the moon:
        self.assertAlmostEqual(self.almanac.moon.moon_fullness, 1.70, 2)
        self.assertEqual(str(self.almanac.moon.rise), "06:59")
        self.assertEqual(str(self.almanac.moon.transit), "14:01")
        self.assertEqual(str(self.almanac.moon.set), "21:20")

        self.assertEqual(str(self.almanac.next_full_moon), "09-Apr-2009 07:55")
        self.assertEqual(str(self.almanac.next_new_moon), "24-Apr-2009 20:22")
        self.assertEqual(str(self.almanac.next_first_quarter_moon), "02-Apr-2009 07:33")

        # Location of the moon
        self.assertAlmostEqual(self.almanac.moon.az, 133.55, 2)
        self.assertAlmostEqual(self.almanac.moon.alt, 47.89, 2)

    def test_sun(self):
        # Test backwards compatibility
        self.assertEqual(str(self.almanac.sunrise), "06:56")
        self.assertEqual(str(self.almanac.sunset), "19:30")

        # Use pyephem
        self.assertEqual(str(self.almanac.sun.rise), "06:56")
        self.assertEqual(str(self.almanac.sun.transit), "13:13")
        self.assertEqual(str(self.almanac.sun.set), "19:30")

        # Equinox / solstice
        self.assertEqual(str(self.almanac.next_vernal_equinox), "20-Mar-2010 10:32")
        self.assertEqual(str(self.almanac.next_autumnal_equinox), "22-Sep-2009 14:18")
        self.assertEqual(str(self.almanac.next_summer_solstice), "20-Jun-2009 22:45")
        self.assertEqual(str(self.almanac.previous_winter_solstice), "21-Dec-2008 04:03")
        self.assertEqual(str(self.almanac.next_winter_solstice), "21-Dec-2009 09:46")

        # Location of the sun
        self.assertAlmostEqual(self.almanac.sun.az, 154.14, 2)
        self.assertAlmostEqual(self.almanac.sun.alt, 44.02, 2)

    def test_mars(self):
        self.assertEqual(str(self.almanac.mars.rise), "06:08")
        self.assertEqual(str(self.almanac.mars.transit), "11:34")
        self.assertEqual(str(self.almanac.mars.set), "17:00")
        self.assertAlmostEqual(self.almanac.mars.sun_distance, 1.3857, 4)

    def test_jupiter(self):
        # Specialized attribute for Jupiter:
        self.assertEqual(str(self.almanac.jupiter.cmlI), "310:55:32.7")
        # Should fail if applied to a different body
        with self.assertRaises(AttributeError):
            self.almanac.venus.cmlI

    def test_star(self):
        self.assertEqual(str(self.almanac.rigel.rise), "12:32")
        self.assertEqual(str(self.almanac.rigel.transit), "18:00")
        self.assertEqual(str(self.almanac.rigel.set), "23:28")

    def test_sidereal(self):
        self.assertAlmostEqual(self.almanac.sidereal_time, 348.3400, 4)

    def test_always_up(self):
        # Time and location where the sun is always up
        t = 1371044003  # 2013-06-12 06:33:23 PDT (1371044003)
        almanac = Almanac(t, 64.0, 0.0)
        self.assertIsNone(almanac(horizon=-6).sun(use_center=1).rise.raw)

    def test_naval_observatory(self):
        #
        # pyephem "Naval Observatory" example.
        t = 1252256400  # 2009-09-06 17:00:00 UTC (1252256400)
        atlanta = Almanac(t, 33.8, -84.4, pressure=0, horizon=-34.0 / 60.0)
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


unittest.main()
