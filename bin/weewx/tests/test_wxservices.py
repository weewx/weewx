#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test StdWXService"""

import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

import weewx.wxservices

altitude_vt = (700, 'foot', 'group_altitude')
svc_dict = {
    'Algorithms': {},
    'Calculations': {
        'appTemp': 'software',
        'beaufort': 'software',
        'dewpoint': 'software',
        'heatindex': 'software',
        'humidex': 'software',
        'inDewpoint': 'software',
        'windchill': 'software',
        'windrun': 'software',
    }
}

# Test values:
record = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 88.7, 'inHumidity': 54.0,
    'outHumidity': 90.0, 'windSpeed': 12.0, 'windDir': None, 'windGust': 15.0, 'windGustDir': 270.0,
    'rain': 0.02,
}

# These are the correct values
correct = {
    'dewpoint': 85.37502296294483,
    'inDewpoint': 55.3580124202402,
    'windchill': 88.7,
    'heatindex': 116.1964007023,
    'humidex': 121.28308732603907,
    'appTemp': 99.36405806590201,
    'beaufort': 3,
    'windrun': 1.0
}


class TestSimpleFunctions(unittest.TestCase):

    def setUp(self):
        # Make a copy. We may be modifying it.
        self.record = dict(record)
        self.wx_calc = weewx.wxservices.WXXTypes(svc_dict, altitude_vt, 45, -122)

    def test_appTemp(self):
        self.calc('appTemp', 'outTemp', 'outHumidity', 'windSpeed')

    def test_beaufort(self):
        self.calc('beaufort', 'windSpeed')

    def test_dewpoint(self):
        self.calc('dewpoint', 'outTemp', 'outHumidity')

    def test_heatindex(self):
        self.calc('heatindex', 'outTemp', 'outHumidity')

    def test_humidex(self):
        self.calc('humidex', 'outTemp', 'outHumidity')

    def test_inDewpoint(self):
        self.calc('inDewpoint', 'inTemp', 'inHumidity')

    def test_windchill(self):
        self.calc('windchill', 'outTemp', 'windSpeed')

    def test_windrun(self):
        self.calc('windrun', 'windSpeed')

    def calc(self, key, *crits):
        """Calculate derived type 'key'. Parameters in "crits" are required to perform the calculation. Their
        presence will be tested."""
        result = self.wx_calc.get_scalar(key, self.record, None)
        self.assertAlmostEqual(result[0], correct[key], 3)
        # Now try it, but with a critical key missing
        for crit in crits:
            # Restore the record
            self.setUp()
            # Set the critical key to None
            self.record[crit] = None
            result = self.wx_calc.get_scalar(key, self.record, None)
            # Result should be None
            self.assertEqual(result[0], None)
            # Try again, but delete the key completely. Should raise an exception.
            with self.assertRaises(weewx.CannotCalculate):
                del self.record[crit]
                self.wx_calc.get_scalar(key, self.record, None)
        # Finally, make sure it raises weewx.UnknownType when presented with an unknown key
        with self.assertRaises(weewx.UnknownType):
            self.wx_calc.get_scalar('foo', self.record, None)



# Test values for the PressureCooker test:
record = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 55.7, 'inHumidity': 54.0,
    'outHumidity': 90.0, 'windSpeed': 0.0, 'windDir': None, 'windGust': 2.0, 'windGustDir': 270.0,
    'rain': 0.0, 'windchill': 55.7, 'heatindex': 55.7,
    'pressure': 29.259303850622302, 'barometer': 29.99, 'altimeter': 30.001561119603156,
}

altitude_vt = weewx.units.ValueTuple(700, "foot", "group_altitude")

# These are the correct values
pressure = 29.259303850622302
barometer = 30.01396476909608
altimeter = 30.001561119603156


class TestPressureCooker(unittest.TestCase):
    """Test the class PressureCooker"""

    def setUp(self):
        # Make a copy. We will be modifying it.
        self.record = dict(record)

    def test_get_temperature_12h(self):
        pc = weewx.wxservices.PressureCooker(altitude_vt)

        # Mock a database in US units
        db_manager = mock.Mock()
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            # Make sure the mocked database manager got called with a time 12h ago
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, (80.3, 'degree_F', 'group_temperature'))

        # Mock a database in METRICWX units
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX, 'outTemp': 30.0}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, (30.0, 'degree_C', 'group_temperature'))

        # Mock a database missing a record from 12h ago
        with mock.patch.object(db_manager, 'getRecord',
                               return_value=None) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, None)

        # Mock a database that has a record from 12h ago, but it's missing outTemp
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, None)

    def test_pressure(self):
        """Test interface pressure()"""

        # Create a pressure cooker
        pc = weewx.wxservices.PressureCooker(altitude_vt)

        # Mock up a database manager in US units
        db_manager = mock.Mock()
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}):
            p = pc.pressure(self.record, db_manager)
            self.assertEqual(p, pressure)

            # Remove 'outHumidity' and try again. Should now raise exception.
            del self.record['outHumidity']
            with self.assertRaises(weewx.CannotCalculate):
                p = pc.pressure(self.record, db_manager)

        # Mock a database missing a record from 12h ago
        with mock.patch.object(db_manager, 'getRecord',
                               return_value=None):
            with self.assertRaises(weewx.CannotCalculate):
                p = pc.pressure(self.record, db_manager)

        # Mock a database that has a record from 12h ago, but it's missing outTemp
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX}) as mock_mgr:
            with self.assertRaises(weewx.CannotCalculate):
                p = pc.pressure(self.record, db_manager)

    def test_altimeter(self):
        """Test interface altimeter()"""

        # Create a pressure cooker
        pc = weewx.wxservices.PressureCooker(altitude_vt)

        a = pc.altimeter(self.record)
        self.assertEqual(a, altimeter)

        # Remove 'pressure' from the record and check for exception
        del self.record['pressure']
        with self.assertRaises(weewx.CannotCalculate):
            a = pc.altimeter(self.record)

    def test_barometer(self):
        """Test interface barometer()"""

        # Create a pressure cooker
        pc = weewx.wxservices.PressureCooker(altitude_vt)

        b = pc.barometer(self.record)
        self.assertEqual(b, barometer)

        # Remove 'outTemp' from the record and check for exception
        del self.record['outTemp']
        with self.assertRaises(weewx.CannotCalculate):
            b = pc.barometer(self.record)


class TestRainRater(unittest.TestCase):
    now = 1571083200  # 14-Oct-2019 1300 PDT
    rain_period = 900
    retain_period = 915

    def setUp(self):
        self.rr = weewx.wxservices.RainRater(TestRainRater.rain_period, TestRainRater.retain_period)
        self.db_manager = mock.Mock()
        with mock.patch.object(self.db_manager, 'genSql', return_value=[
            (TestRainRater.now - 600, weewx.US, 0.01),
            (TestRainRater.now - 300, weewx.US, 0.02),
        ]):
            self.rr.add_loop_packet({'dateTime': TestRainRater.now + 5, 'usUnits': weewx.US, 'rain': 0.0},
                                    self.db_manager)

    def test_setup(self):
        self.assertEqual(self.rr.rain_events, [(TestRainRater.now - 600, 0.01), (TestRainRater.now - 300, 0.02)])

    def test_add_US(self):
        record = {'dateTime': TestRainRater.now + 60, 'usUnits': weewx.US, 'rain': 0.01}
        self.rr.add_loop_packet(record, self.db_manager)
        rate = self.rr.rain_rate('rainRate', record, None)
        self.assertEqual(rate, 3600 * .04 / TestRainRater.rain_period)

    def test_add_METRICWX(self):
        record = {'dateTime': TestRainRater.now + 60, 'usUnits': weewx.METRICWX, 'rain': 0.254}
        self.rr.add_loop_packet(record, self.db_manager)
        rate = self.rr.rain_rate('rainRate', record, None)
        self.assertEqual(rate, 3600 * .04 / TestRainRater.rain_period)

    def test_window(self):
        """Rain event falls outside rain window, but inside retain window"""
        record = {'dateTime': TestRainRater.now + 305, 'usUnits': weewx.US, 'rain': 0.0}
        self.rr.add_loop_packet(record, self.db_manager)
        rate = self.rr.rain_rate('rainRate', record, None)
        self.assertEqual(rate, 3600 * .02 / TestRainRater.rain_period)

        record = {'dateTime': TestRainRater.now + 310, 'usUnits': weewx.US, 'rain': 0.03}
        self.rr.add_loop_packet(record, self.db_manager)
        rate = self.rr.rain_rate('rainRate', record, None)
        self.assertEqual(rate, 3600 * .05 / TestRainRater.rain_period)

    def test_trim(self):
        """"Test trimming old events"""
        record = {'dateTime': TestRainRater.now + 320, 'usUnits': weewx.US, 'rain': 0.03}
        self.rr.add_loop_packet(record, self.db_manager)
        rate = self.rr.rain_rate('rainRate', record, None)
        self.assertEqual(rate, 3600 * .05 / TestRainRater.rain_period)
        self.assertEqual(self.rr.rain_events, [(TestRainRater.now - 300, 0.02), (1571083520, 0.03)])

if __name__ == '__main__':
    unittest.main()
