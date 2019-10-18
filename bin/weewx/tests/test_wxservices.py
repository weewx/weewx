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

    def test_dewpoint(self):
        self.calc('dewpoint', 'outTemp', 'outHumidity')

    def test_inDewpoint(self):
        self.calc('inDewpoint', 'inTemp', 'inHumidity')

    def test_windchill(self):
        self.calc('windchill', 'outTemp', 'windSpeed')

    def test_heatindex(self):
        self.calc('heatindex', 'outTemp', 'outHumidity')

    def test_humidex(self):
        self.calc('humidex', 'outTemp', 'outHumidity')

    def test_appTemp(self):
        self.calc('appTemp', 'outTemp', 'outHumidity', 'windSpeed')

    def test_beaufort(self):
        self.calc('beaufort', 'windSpeed')

    def test_windrun(self):
        self.calc('windrun', 'windSpeed')

    def calc(self, key, *crits):
        """Calculate derived type 'key'. Parameters in "crits" are required to perform the calculation. Their
        presence will be tested."""
        # Figure out what function to call
        function = getattr(weewx.wxservices, 'calc_' + key)
        # Call it and get the results
        result = function(key, self.record)
        self.assertAlmostEqual(result, correct[key], 3)
        # Now try it, but with a critical key missing
        for crit in crits:
            # Restore the record
            self.setUp()
            # Set the critical key to None
            self.record[crit] = None
            result = function(key, self.record)
            # Result should be None
            self.assertEqual(result, None)
            # Try again, but delete the key completely. Should raise an exception.
            with self.assertRaises(weewx.CannotCalculate):
                del self.record[crit]
                function(key, self.record)
        # Finally, make sure it raises weewx.UnknownType when presented with an unknown key
        with self.assertRaises(weewx.UnknownType):
            function('foo', self.record)

# class TestWXCalculate(unittest.TestCase):
#
#     altitude_vt = (700, 'foot', 'group_altitude')
#
#     def setUp(self):
#         get a dbmanager
#         # Use default config dictionary:
#         self.calc = TestWXCalculate({}, TestWXCalculate.altitude_vt, 45, -123, )

if __name__ == '__main__':
    unittest.main()
