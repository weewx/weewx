#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
import contextlib
import io
import os
import unittest
from unittest.mock import patch

import configobj

import weecfg.extension
import weecfg.station_config
import weecfg.update_config
import weeutil.config
import weeutil.weeutil
import weewx

CONFIG_DICT_STR = """
# WEEWX TEST CONFIGURATION FILE

# Set to 1 for extra debug info, otherwise comment it out or set to zero
debug = 1

# Root directory of the weewx data file hierarchy for this station
WEEWX_ROOT = /home/weewx

# Whether to log successful operations. May get overridden below.
log_success = True

# Whether to log unsuccessful operations. May get overridden below.
log_failure = True

# Do not modify this. It is used when installing and updating weewx.
version = 4.10.0a1

##############################################################################

#   This section is for information about the station.

[Station]

    # Description of the station location
    location = "Test station"

    # Latitude in decimal degrees. Negative for southern hemisphere
    latitude = 5.00
    # Longitude in decimal degrees. Negative for western hemisphere.
    longitude = 10.00

    # Altitude of the station, with the unit it is in. This is used only
    # if the hardware cannot supply a value.
    altitude = 700, foot    # Choose 'foot' or 'meter' for unit

    # Set to type of station hardware. There must be a corresponding stanza
    # in this file, which includes a value for the 'driver' option.
    station_type = unspecified

    # If you have a website, you may specify an URL. This is required if you
    # intend to register your station.
    #station_url = http://www.example.com

    # The start of the rain year (1=January; 10=October, etc.). This is
    # downloaded from the station if the hardware supports it.
    rain_year_start = 1

[StdRESTful]
    [[StationRegistry]]
        register_this_station = false
        
[StdReport]
    [[Defaults]]
        lang = en
        unit_system = us
"""

CONFIG_DICT = configobj.ConfigObj(io.StringIO(CONFIG_DICT_STR))

STATION_URL = 'http://weewx.com'


def suppress_stdout(func):
    def wrapper(*args, **kwargs):
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                return func(*args, **kwargs)

    return wrapper


class AltitudeConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default_config_altitude(self):
        weecfg.station_config.config_altitude(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['altitude'], ["700", "foot"])
        # Delete the value in the configuration dictionary
        del self.config_dict['Station']['altitude']
        # Now we should get the hardwired default
        weecfg.station_config.config_altitude(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['altitude'], ["0", "foot"])

    def test_arg_config_altitude(self):
        weecfg.station_config.config_altitude(self.config_dict, altitude="500, meter")
        self.assertEqual(self.config_dict['Station']['altitude'], ["500", "meter"])

    def test_badarg_config_altitude(self):
        with self.assertRaises(ValueError):
            # Bad unit
            weecfg.station_config.config_altitude(self.config_dict, altitude="500, foo")
        with self.assertRaises(ValueError):
            # Bad value
            weecfg.station_config.config_altitude(self.config_dict, altitude="500f, foot")

    @suppress_stdout
    def test_prompt_config_altitude(self):
        with patch('weecfg.station_config.input', side_effect=['']):
            weecfg.station_config.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["700", "foot"])
        with patch('weecfg.station_config.input', side_effect=['110, meter']):
            weecfg.station_config.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])

    @suppress_stdout
    def test_badprompt_config_altitude(self):
        # Include a bad unit. It should prompt again
        with patch('weecfg.station_config.input', side_effect=['100, foo', '110, meter']):
            weecfg.station_config.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])
        # Include a bad value. It should prompt again
        with patch('weecfg.station_config.input', side_effect=['100f, foot', '110, meter']):
            weecfg.station_config.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])


class LatLonConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default_config_latlon(self):
        # Use the default as supplied by CONFIG_DICT
        weecfg.station_config.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 5.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 10.0)
        # Delete the values in the configuration dictionary
        del self.config_dict['Station']['latitude']
        del self.config_dict['Station']['longitude']
        # Now the defaults should be the hardwired defaults
        weecfg.station_config.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 0.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 0.0)

    def test_arg_config_latlon(self):
        weecfg.station_config.config_latlon(self.config_dict, latitude=-20, longitude=-40)
        self.assertEqual(float(self.config_dict['Station']['latitude']), -20.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), -40.0)

    def test_badarg_config_latlon(self):
        with self.assertRaises(ValueError):
            weecfg.station_config.config_latlon(self.config_dict, latitude="-20f", longitude=-40)

    @suppress_stdout
    def test_prompt_config_latlong(self):
        with patch('weecfg.input', side_effect=['-21', '-41']):
            weecfg.station_config.config_latlon(self.config_dict)
            self.assertEqual(float(self.config_dict['Station']['latitude']), -21.0)
            self.assertEqual(float(self.config_dict['Station']['longitude']), -41.0)


class RegistryConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default_register(self):
        weecfg.station_config.config_registry(self.config_dict, no_prompt=True)
        self.assertFalse(
            self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])

    def test_args_register(self):
        # Missing station_url:
        with self.assertRaises(weewx.ViolatedPrecondition):
            weecfg.station_config.config_registry(self.config_dict, register='True',
                                                  no_prompt=True)
        # This time we supply a station_url. Should be OK.
        weecfg.station_config.config_registry(self.config_dict, register='True',
                                              station_url=STATION_URL, no_prompt=True)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)
        # Alternatively, the config file already had a station_url:
        self.config_dict['Station']['station_url'] = STATION_URL
        weecfg.station_config.config_registry(self.config_dict, register='True', no_prompt=True)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

    @suppress_stdout
    def test_prompt_register(self):
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=[STATION_URL]):
                weecfg.station_config.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

        # Try again, but without specifying an URL. Should ask twice.
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=["", STATION_URL]):
                weecfg.station_config.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

        # Now with a bogus URL
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=['http://www.example.com', STATION_URL]):
                weecfg.station_config.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)


class UnitsConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default_units(self):
        weecfg.station_config.config_units(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'us')

    def test_custom_units(self):
        del self.config_dict['StdReport']['Defaults']['unit_system']
        weecfg.station_config.config_units(self.config_dict, no_prompt=True)
        self.assertNotIn('unit_system', self.config_dict['StdReport']['Defaults'])

    def test_args_units(self):
        weecfg.station_config.config_units(self.config_dict, unit_system='metricwx', no_prompt=True)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')

    @suppress_stdout
    def test_prompt_units(self):
        with patch('weecfg.input', side_effect=['metricwx']):
            weecfg.station_config.config_units(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')
        # Do it again, but with a wrong unit system name. It should ask again.
        with patch('weecfg.input', side_effect=['metricwz', 'metricwx']):
            weecfg.station_config.config_units(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')


class DriverConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default_config_driver(self):
        weecfg.station_config.config_driver(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Simulator')
        self.assertEqual(self.config_dict['Simulator']['driver'], 'weewx.drivers.simulator')

    def test_arg_config_driver(self):
        weecfg.station_config.config_driver(self.config_dict, driver='weewx.drivers.vantage',
                                            no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
        self.assertEqual(self.config_dict['Vantage']['driver'], 'weewx.drivers.vantage')

    @suppress_stdout
    def test_prompt_config_driver(self):
        with patch('weecfg.input', side_effect=['6', '', '/dev/ttyS0']):
            weecfg.station_config.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS0')

        # Do it again. This time, the stanza ['Vantage'] will exist, and we'll just modify it
        with patch('weecfg.input', side_effect=['', '', '/dev/ttyS1']):
            weecfg.station_config.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS1')


if __name__ == "__main__":
    unittest.main()
