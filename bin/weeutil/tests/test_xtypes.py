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


def new_type(obs_type, record):
    if obs_type == 'dewpoint':
        if record['usUnits'] == weewx.US:
            return weewx.wxformulas.dewpointF(record.get('outTemp'), record.get('outHumidity'))
        elif record['usUnits'] == weewx.METRIC or record['usUnits'] == weewx.METRICWX:
            return weewx.wxformulas.dewpointC(record.get('outTemp'), record.get('outHumidity'))
        else:
            raise ValueError("Unknown unit system %s" % record['usUnits'])
    else:
        raise ValueError(obs_type)


# These are the correct values
dewpoint = 52.81113360826872
pressure = 29.259303850622302
barometer = 29.99
altimeter = 30.001561119603156


class TestExtendedTypes(unittest.TestCase):
    """Test the Ambient RESTful protocol"""

    def setUp(self):
        self.record = {
            'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 55.7, 'inHumidity': 54.0,
            'outHumidity': 90.0, 'windSpeed': 0.0, 'windDir': None, 'windGust': 2.0, 'windGustDir': 270.0,
            'rainRate': 0.0, 'rain': 0.0, 'windchill': 55.7, 'heatindex': 55.7, 'ET': 0.0, 'radiation': 0.0, 'UV': 0.0
        }

    def test_get_temperature_12h_F(self):
        db_manager = mock.Mock()
        ps = weeutil.xtypes.PressureCooker(700, db_manager)

        # Mock a database in US units
        with mock.patch.object(db_manager, 'getRecord', return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            t = ps._get_temperature_12h_F(self.record['dateTime'])
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12*3600, max_delta=1800)
            self.assertEqual(t, 80.3)

        # Mock a database in METRICWX units
        with mock.patch.object(db_manager, 'getRecord', return_value={'usUnits': weewx.METRICWX, 'outTemp': 30.0}) as mock_mgr:
            t = ps._get_temperature_12h_F(self.record['dateTime'])
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12*3600, max_delta=1800)
            self.assertEqual(t, 86)

#
# my_types = weeutil.xtypes.ExtendedTypes(record, {'dewpoint': new_type,
#                                                  'pressure': ps.calc
#                                                  })
#
# print('dewpoint after =', my_types['dewpoint'])
# print('pressure after =', my_types['pressure'])
if __name__ == '__main__':
    unittest.main()
