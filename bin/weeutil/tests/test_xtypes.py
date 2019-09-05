#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test ExtendedTypes"""

import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

import weewx.manager
import weeutil.xtypes


# A simple extension function. It can only do dewpoint.
def calc_dewpoint(obs_type, record):
    if obs_type == 'dewpoint':
        if record['usUnits'] == weewx.US:
            return weewx.wxformulas.dewpointF(record.get('outTemp'), record.get('outHumidity'))
        elif record['usUnits'] == weewx.METRIC or record['usUnits'] == weewx.METRICWX:
            return weewx.wxformulas.dewpointC(record.get('outTemp'), record.get('outHumidity'))
        else:
            raise ValueError("Unknown unit system %s" % record['usUnits'])
    else:
        raise ValueError(obs_type)


# Test values:
record = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 55.7, 'inHumidity': 54.0,
    'outHumidity': 90.0, 'windSpeed': 0.0, 'windDir': None, 'windGust': 2.0, 'windGustDir': 270.0,
    'rain': 0.0, 'windchill': 55.7, 'heatindex': 55.7
}
# These are the correct values
dewpoint = 52.81113360826872
pressure = 29.259303850622302
barometer = 29.99
altimeter = 30.001561119603156


class TestExtendedTypes(unittest.TestCase):
    """Test the Ambient RESTful protocol"""

    def setUp(self):
        # Make a copy. We will be modifying it.
        self.record = dict(record)

    def test_get_item(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        self.assertEqual(xt['outTemp'], 55.7)

    def test_get_item_bad_type(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        with self.assertRaises(KeyError):
            xt['foo']

    def test_calculated_get_item(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        # This will set the value in the record, but the calculated dewpoint should take precedence
        xt['dewpoint'] = 50
        self.assertEqual(xt['dewpoint'], dewpoint)
        # Delete the calculated dewpoint. Now it should get the value in the record
        del xt.new_types['dewpoint']
        self.assertEqual(xt['dewpoint'], 50)

    def test_get(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        self.assertEqual(xt.get('outTemp'), 55.7)
        self.assertEqual(xt.get('foo', 0), 0)

    def test_calculated_get(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        self.assertEqual(xt.get('dewpoint', 0), dewpoint)

    def test_keys(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        # The ExtendedType should include not only the keys in the record, but also
        # the keys of the types that can be calculated:
        self.assertEqual(set(xt.keys()), set(self.record.keys()).union(set(['dewpoint'])))

    def test_contains(self):
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'dewpoint': calc_dewpoint})
        self.assertTrue('outTemp' in xt)
        self.assertTrue('dewpoint' in xt)
        self.assertFalse('foo' in xt)


class TestPressureCooker(unittest.TestCase):

    def setUp(self):
        # Make a copy. We will be modifying it.
        self.record = dict(record)

    def test_get_temperature_12h_F(self):
        db_manager = mock.Mock()
        pc = weeutil.xtypes.PressureCooker(700, db_manager)

        # Mock a database in US units
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            t = pc._get_temperature_12h_F(self.record['dateTime'])
            # Make sure the mocked database manager got called with a time 12h ago
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, 80.3)

        # Mock a database in METRICWX units
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX, 'outTemp': 30.0}) as mock_mgr:
            t = pc._get_temperature_12h_F(self.record['dateTime'])
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            self.assertEqual(t, 86)

    def test_calc_pressure(self):
        # To calculate station pressure, we need barometric pressure. Add it
        self.record['barometer'] = barometer
        # Mock up a database manager
        db_manager = mock.Mock()
        # Create a pressure cooker with our mocked manager
        pc = weeutil.xtypes.PressureCooker(700, db_manager)

        # Mock a result set in US units
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            p = pc.calc_pressure(self.record)
            self.assertEqual(p, pressure)

        # Try it using the "calc()" entry point:
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            p = pc.calc('pressure', self.record)
            self.assertEqual(p, pressure)

    def test_bound_method(self):
        """Do a test, this time using a bound method (instead of a simple function)"""
        # To calculate station pressure, we need barometric pressure. Add it
        self.record['barometer'] = barometer
        # Mock up a database manager
        db_manager = mock.Mock()
        # Create a pressure cooker with our mocked manager
        pc = weeutil.xtypes.PressureCooker(700, db_manager)
        xt = weeutil.xtypes.ExtendedTypes(self.record, {'pressure': pc.calc})

        # Mock a result set in US units
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            p = xt['pressure']
            self.assertEqual(p, pressure)

if __name__ == '__main__':
    unittest.main()
