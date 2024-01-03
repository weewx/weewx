#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
import contextlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import configobj

import weecfg
import weectllib.station_actions
import weeutil.config
import weeutil.weeutil
import weewx
import weewxd

weewxd_path = weewxd.__file__

# For the tests, use the version of weewx.conf that comes with WeeWX.
with weeutil.weeutil.get_resource_fd('weewx_data', 'weewx.conf') as fd:
    CONFIG_DICT = configobj.ConfigObj(fd, encoding='utf-8', file_error=True)

STATION_URL = 'https://weewx.com'


def suppress_stdout(func):
    def wrapper(*args, **kwargs):
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                return func(*args, **kwargs)

    return wrapper


class CommonConfigTest(unittest.TestCase):

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)


class LocationConfigTest(CommonConfigTest):

    def test_default_config_location(self):
        weectllib.station_actions.config_location(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")
        del self.config_dict['Station']['location']
        weectllib.station_actions.config_location(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")

    def test_arg_config_location(self):
        weectllib.station_actions.config_location(self.config_dict, location='foo', no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "foo")

    @suppress_stdout
    def test_prompt_config_location(self):
        with patch('weectllib.station_actions.input', side_effect=['']):
            weectllib.station_actions.config_location(self.config_dict)
            self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")
        with patch('weectllib.station_actions.input', side_effect=['bar']):
            weectllib.station_actions.config_location(self.config_dict)
            self.assertEqual(self.config_dict['Station']['location'], "bar")


class AltitudeConfigTest(CommonConfigTest):

    def test_default_config_altitude(self):
        weectllib.station_actions.config_altitude(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['altitude'], ["0", "foot"])
        # Delete the value in the configuration dictionary
        del self.config_dict['Station']['altitude']
        # Now we should get the hardwired default
        weectllib.station_actions.config_altitude(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['altitude'], ["0", "foot"])

    def test_arg_config_altitude(self):
        weectllib.station_actions.config_altitude(self.config_dict, altitude="500, meter")
        self.assertEqual(self.config_dict['Station']['altitude'], ["500", "meter"])

    def test_badarg_config_altitude(self):
        with self.assertRaises(ValueError):
            # Bad unit
            weectllib.station_actions.config_altitude(self.config_dict, altitude="500, foo")
        with self.assertRaises(ValueError):
            # Bad value
            weectllib.station_actions.config_altitude(self.config_dict, altitude="500f, foot")

    @suppress_stdout
    def test_prompt_config_altitude(self):
        with patch('weectllib.station_actions.input', side_effect=['']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["0", "foot"])
        with patch('weectllib.station_actions.input', side_effect=['110, meter']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])
        # Try 'feet' instead of 'foot'
        with patch('weectllib.station_actions.input', side_effect=['700, feet']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["700", "foot"])
        # Try 'meters' instead of 'meter':
        with patch('weectllib.station_actions.input', side_effect=['110, meters']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])

    @suppress_stdout
    def test_badprompt_config_altitude(self):
        # Include a bad unit. It should prompt again
        with patch('weectllib.station_actions.input', side_effect=['100, foo', '110, meter']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])
        # Include a bad value. It should prompt again
        with patch('weectllib.station_actions.input', side_effect=['100f, foot', '110, meter']):
            weectllib.station_actions.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["110", "meter"])


class LatLonConfigTest(CommonConfigTest):

    def test_default_config_latlon(self):
        # Use the default as supplied by CONFIG_DICT
        weectllib.station_actions.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 0.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 0.0)
        # Delete the values in the configuration dictionary
        del self.config_dict['Station']['latitude']
        del self.config_dict['Station']['longitude']
        # Now the defaults should be the hardwired defaults
        weectllib.station_actions.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 0.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 0.0)

    def test_arg_config_latlon(self):
        weectllib.station_actions.config_latlon(self.config_dict, latitude='-20', longitude='-40')
        self.assertEqual(float(self.config_dict['Station']['latitude']), -20.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), -40.0)

    def test_badarg_config_latlon(self):
        with self.assertRaises(ValueError):
            weectllib.station_actions.config_latlon(self.config_dict, latitude="-20f",
                                                    longitude='-40')

    @suppress_stdout
    def test_prompt_config_latlong(self):
        with patch('weecfg.input', side_effect=['-21', '-41']):
            weectllib.station_actions.config_latlon(self.config_dict)
            self.assertEqual(float(self.config_dict['Station']['latitude']), -21.0)
            self.assertEqual(float(self.config_dict['Station']['longitude']), -41.0)


class RegistryConfigTest(CommonConfigTest):

    def test_default_register(self):
        weectllib.station_actions.config_registry(self.config_dict, no_prompt=True)
        self.assertFalse(
            self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])

    def test_args_register(self):
        # Missing station_url:
        with self.assertRaises(weewx.ViolatedPrecondition):
            weectllib.station_actions.config_registry(self.config_dict, register='True',
                                                      no_prompt=True)
        # This time we supply a station_url. Should be OK.
        weectllib.station_actions.config_registry(self.config_dict, register='True',
                                                  station_url=STATION_URL, no_prompt=True)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)
        # Alternatively, the config file already had a station_url:
        self.config_dict['Station']['station_url'] = STATION_URL
        weectllib.station_actions.config_registry(self.config_dict, register='True',
                                                  no_prompt=True)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

    @suppress_stdout
    def test_prompt_register(self):
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=[STATION_URL]):
                weectllib.station_actions.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

        # Try again, but without specifying an URL. Should ask twice.
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=["", STATION_URL]):
                weectllib.station_actions.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)

        # Now with a bogus URL
        with patch('weeutil.weeutil.input', side_effect=['y']):
            with patch('weecfg.input', side_effect=['https://www.example.com', STATION_URL]):
                weectllib.station_actions.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)


class UnitsConfigTest(CommonConfigTest):

    def test_default_units(self):
        weectllib.station_actions.config_units(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'us')

    def test_custom_units(self):
        del self.config_dict['StdReport']['Defaults']['unit_system']
        weectllib.station_actions.config_units(self.config_dict, no_prompt=True)
        self.assertNotIn('unit_system', self.config_dict['StdReport']['Defaults'])

    def test_args_units(self):
        weectllib.station_actions.config_units(self.config_dict, unit_system='metricwx',
                                               no_prompt=True)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')

    @suppress_stdout
    def test_prompt_units(self):
        with patch('weecfg.input', side_effect=['metricwx']):
            weectllib.station_actions.config_units(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')
        # Do it again, but with a wrong unit system name. It should ask again.
        with patch('weecfg.input', side_effect=['metricwz', 'metricwx']):
            weectllib.station_actions.config_units(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'metricwx')


class DriverConfigTest(CommonConfigTest):

    def test_default_config_driver(self):
        weectllib.station_actions.config_driver(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Simulator')
        self.assertEqual(self.config_dict['Simulator']['driver'], 'weewx.drivers.simulator')

    def test_arg_config_driver(self):
        weectllib.station_actions.config_driver(self.config_dict, driver='weewx.drivers.vantage',
                                                no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
        self.assertEqual(self.config_dict['Vantage']['driver'], 'weewx.drivers.vantage')

    def test_arg_noeditor_config_driver(self):
        # Test a driver that does not have a configurator editor. Because all WeeWX drivers do, we
        # have to disable one of them.
        import weewx.drivers.vantage
        weewx.drivers.vantage.hold = weewx.drivers.vantage.confeditor_loader
        del weewx.drivers.vantage.confeditor_loader
        # At this point, there is no configuration loader, so a minimal version of [Vantage]
        # should be supplied.
        weectllib.station_actions.config_driver(self.config_dict,
                                                driver='weewx.drivers.vantage',
                                                no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
        self.assertEqual(self.config_dict['Vantage']['driver'], 'weewx.drivers.vantage')
        # The rest of the [Vantage] stanza should be missing. Try a key.
        self.assertNotIn('port', self.config_dict['Vantage'])
        # Restore the editor:
        weewx.drivers.vantage.confeditor_loader = weewx.drivers.vantage.hold

    @suppress_stdout
    def test_prompt_config_driver(self):
        with patch('weecfg.input', side_effect=['6', '', '/dev/ttyS0']):
            weectllib.station_actions.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS0')

        # Do it again. This time, the stanza ['Vantage'] will exist, and we'll just modify it
        with patch('weecfg.input', side_effect=['', '', '/dev/ttyS1']):
            weectllib.station_actions.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS1')


class TestConfigRoots(CommonConfigTest):

    def test_args_config_roots(self):
        weectllib.station_actions.config_roots(self.config_dict, skin_root='foo',
                                               html_root='bar', sqlite_root='baz')
        self.assertEqual(self.config_dict['StdReport']['SKIN_ROOT'], 'foo')
        self.assertEqual(self.config_dict['StdReport']['HTML_ROOT'], 'bar')
        self.assertEqual(self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'], 'baz')

        # Delete the options, then try again. They should be replaced with defaults
        del self.config_dict['StdReport']['SKIN_ROOT']
        del self.config_dict['StdReport']['HTML_ROOT']
        del self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT']
        weectllib.station_actions.config_roots(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['SKIN_ROOT'], 'skins')
        self.assertEqual(self.config_dict['StdReport']['HTML_ROOT'], 'public_html')
        self.assertEqual(self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'],
                         'archive')


class TestCreateStation(unittest.TestCase):

    def test_create_default(self):
        "Test creating a new station"
        # Get a temporary directory to create it in
        with tempfile.TemporaryDirectory(dir='/var/tmp') as weewx_root:
            # We have not run 'pip', so the only copy of weewxd.py is the one in the repository.
            # Create a station using the defaults
            weectllib.station_actions.station_create(weewx_root=weewx_root, no_prompt=True)
            config_path = os.path.join(weewx_root, 'weewx.conf')

            # Retrieve the config file that was created and check it:
            config_dict = configobj.ConfigObj(config_path, encoding='utf-8')
            self.assertNotIn('WEEWX_ROOT', config_dict)
            self.assertNotIn('WEEWX_ROOT_CONFIG', config_dict)
            self.assertEqual(config_dict['Station']['station_type'], 'Simulator')
            self.assertEqual(config_dict['Simulator']['driver'], 'weewx.drivers.simulator')
            self.assertEqual(config_dict['StdReport']['SKIN_ROOT'], 'skins')
            self.assertEqual(config_dict['StdReport']['HTML_ROOT'], 'public_html')
            self.assertEqual(config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'], 'archive')

            # Make sure all the skins are there
            for skin in ['Seasons', 'Smartphone', 'Mobile', 'Standard',
                         'Ftp', 'Rsync']:
                p = os.path.join(weewx_root, config_dict['StdReport']['SKIN_ROOT'], skin)
                self.assertTrue(os.path.isdir(p))

            # Retrieve the systemd utility file and check it
            path = os.path.join(weewx_root, 'util/systemd/weewx.service')
            with open(path, 'rt') as fd:
                for line in fd:
                    if line.startswith('ExecStart'):
                        self.assertEqual(line.strip(),
                                         f"ExecStart={sys.executable} {weewxd_path} {config_path}")


class TestReconfigureStation(unittest.TestCase):

    def test_reconfigure(self):
        "Test reconfiguring a station"
        # Get a temporary directory to create a station in
        with tempfile.TemporaryDirectory(dir='/var/tmp') as weewx_root:
            # Create a station using the defaults
            weectllib.station_actions.station_create(weewx_root=weewx_root, no_prompt=True)

            # Now retrieve the config file that was created. The retrieval must use "read_config()"
            # because that's what station_reconfigure() is expecting.
            config_path = os.path.join(weewx_root, 'weewx.conf')
            config_path, config_dict = weecfg.read_config(config_path)
            # Now reconfigure it:
            weectllib.station_actions.station_reconfigure(config_dict,
                                                          weewx_root='/etc/weewx',
                                                          driver='weewx.drivers.vantage',
                                                          no_prompt=True)
            # Re-read it:
            config_dict = configobj.ConfigObj(config_path, encoding='utf-8')
            # Check it out.
            self.assertEqual(config_dict['WEEWX_ROOT'], '/etc/weewx')
            self.assertNotIn('WEEWX_ROOT_CONFIG', config_dict)
            self.assertEqual(config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(config_dict['Vantage']['driver'], 'weewx.drivers.vantage')
            self.assertEqual(config_dict['StdReport']['SKIN_ROOT'], 'skins')
            self.assertEqual(config_dict['StdReport']['HTML_ROOT'], 'public_html')
            self.assertEqual(config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'], 'archive')


if __name__ == "__main__":
    unittest.main()
