#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
import contextlib
import importlib.resources
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import configobj

import weecfg.extension
import weecfg.station_config
import weecfg.update_config
import weeutil.config
import weeutil.weeutil
import weewx
import weewxd

weewxd_path = weewxd.__file__

# For the tests, use the version of weewx.conf that comes with WeeWX.
with importlib.resources.open_text('wee_resources', 'weewx.conf', encoding='utf-8') as fd:
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
        weecfg.station_config.config_location(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")
        del self.config_dict['Station']['location']
        weecfg.station_config.config_location(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")

    def test_arg_config_location(self):
        weecfg.station_config.config_location(self.config_dict, location='foo', no_prompt=True)
        self.assertEqual(self.config_dict['Station']['location'], "foo")

    @suppress_stdout
    def test_prompt_config_location(self):
        with patch('weecfg.station_config.input', side_effect=['']):
            weecfg.station_config.config_location(self.config_dict)
            self.assertEqual(self.config_dict['Station']['location'], "WeeWX station")
        with patch('weecfg.station_config.input', side_effect=['bar']):
            weecfg.station_config.config_location(self.config_dict)
            self.assertEqual(self.config_dict['Station']['location'], "bar")


class AltitudeConfigTest(CommonConfigTest):

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
        # Try 'feet' instead of 'foot'
        with patch('weecfg.station_config.input', side_effect=['700, feet']):
            weecfg.station_config.config_altitude(self.config_dict)
            self.assertEqual(self.config_dict['Station']['altitude'], ["700", "foot"])
        # Try 'meters' instead of 'meter':
        with patch('weecfg.station_config.input', side_effect=['110, meters']):
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


class LatLonConfigTest(CommonConfigTest):

    def test_default_config_latlon(self):
        # Use the default as supplied by CONFIG_DICT
        weecfg.station_config.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 0.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 0.0)
        # Delete the values in the configuration dictionary
        del self.config_dict['Station']['latitude']
        del self.config_dict['Station']['longitude']
        # Now the defaults should be the hardwired defaults
        weecfg.station_config.config_latlon(self.config_dict, no_prompt=True)
        self.assertEqual(float(self.config_dict['Station']['latitude']), 0.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), 0.0)

    def test_arg_config_latlon(self):
        weecfg.station_config.config_latlon(self.config_dict, latitude='-20', longitude='-40')
        self.assertEqual(float(self.config_dict['Station']['latitude']), -20.0)
        self.assertEqual(float(self.config_dict['Station']['longitude']), -40.0)

    def test_badarg_config_latlon(self):
        with self.assertRaises(ValueError):
            weecfg.station_config.config_latlon(self.config_dict, latitude="-20f", longitude='-40')

    @suppress_stdout
    def test_prompt_config_latlong(self):
        with patch('weecfg.input', side_effect=['-21', '-41']):
            weecfg.station_config.config_latlon(self.config_dict)
            self.assertEqual(float(self.config_dict['Station']['latitude']), -21.0)
            self.assertEqual(float(self.config_dict['Station']['longitude']), -41.0)


class RegistryConfigTest(CommonConfigTest):

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
            with patch('weecfg.input', side_effect=['https://www.example.com', STATION_URL]):
                weecfg.station_config.config_registry(self.config_dict)
        self.assertTrue(self.config_dict['StdRESTful']['StationRegistry']['register_this_station'])
        self.assertEqual(self.config_dict['Station']['station_url'], STATION_URL)


class UnitsConfigTest(CommonConfigTest):

    def test_default_units(self):
        weecfg.station_config.config_units(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['StdReport']['Defaults']['unit_system'], 'us')

    def test_custom_units(self):
        del self.config_dict['StdReport']['Defaults']['unit_system']
        weecfg.station_config.config_units(self.config_dict, no_prompt=True)
        self.assertNotIn('unit_system', self.config_dict['StdReport']['Defaults'])

    def test_args_units(self):
        weecfg.station_config.config_units(self.config_dict, unit_system='metricwx',
                                           no_prompt=True)
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


class DriverConfigTest(CommonConfigTest):

    def test_default_config_driver(self):
        weecfg.station_config.config_driver(self.config_dict, no_prompt=True)
        self.assertEqual(self.config_dict['Station']['station_type'], 'Simulator')
        self.assertEqual(self.config_dict['Simulator']['driver'], 'weewx.drivers.simulator')

    def test_arg_config_driver(self):
        weecfg.station_config.config_driver(self.config_dict, driver='weewx.drivers.vantage',
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
        weecfg.station_config.config_driver(self.config_dict,
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
            weecfg.station_config.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS0')

        # Do it again. This time, the stanza ['Vantage'] will exist, and we'll just modify it
        with patch('weecfg.input', side_effect=['', '', '/dev/ttyS1']):
            weecfg.station_config.config_driver(self.config_dict)
            self.assertEqual(self.config_dict['Station']['station_type'], 'Vantage')
            self.assertEqual(self.config_dict['Vantage']['port'], '/dev/ttyS1')


class TestConfigRoots(CommonConfigTest):

    def test_args_config_roots(self):
        weecfg.station_config.config_roots(self.config_dict, skin_root='foo',
                                           html_root='bar', sqlite_root='baz')
        self.assertEqual(self.config_dict['StdReport']['SKIN_ROOT'], 'foo')
        self.assertEqual(self.config_dict['StdReport']['HTML_ROOT'], 'bar')
        self.assertEqual(self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'], 'baz')

        # Delete the options, then try again. They should be replaced with defaults
        del self.config_dict['StdReport']['SKIN_ROOT']
        del self.config_dict['StdReport']['HTML_ROOT']
        del self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT']
        weecfg.station_config.config_roots(self.config_dict)
        self.assertEqual(self.config_dict['StdReport']['SKIN_ROOT'], 'skins')
        self.assertEqual(self.config_dict['StdReport']['HTML_ROOT'], 'public_html')
        self.assertEqual(self.config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'],
                         'archive')


class TestCreateStation(unittest.TestCase):

    def test_create_default(self):
        "Test creating a new station"
        # Get a temporary directory to create it in
        with tempfile.TemporaryDirectory(dir='/var/tmp') as dirname:
            config_path = os.path.join(dirname, 'weewx.conf')
            # We have not run 'pip', so the only copy of weewxd.py is the one in the repository.
            # Also, 'docs' are generated by mkdocs, so they do not exist in the repository.
            with patch('weecfg.station_config.copy_docs') as mock_copy:
                # Create a station using the defaults
                weecfg.station_config.station_create(config_path, no_prompt=True)
                mock_copy.assert_called_once()

            # Retrieve the config file that was created and check it:
            config_dict = configobj.ConfigObj(config_path, encoding='utf-8')
            self.assertEqual(config_dict['WEEWX_ROOT'], dirname)
            self.assertEqual(config_dict['Station']['station_type'], 'Simulator')
            self.assertEqual(config_dict['Simulator']['driver'], 'weewx.drivers.simulator')
            self.assertEqual(config_dict['StdReport']['SKIN_ROOT'], 'skins')
            self.assertEqual(config_dict['StdReport']['HTML_ROOT'], 'public_html')
            self.assertEqual(config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'], 'archive')

            # Make sure all the skins are there
            for skin in ['Seasons', 'Smartphone', 'Mobile', 'Standard',
                         'Ftp', 'Rsync']:
                p = os.path.join(dirname, config_dict['StdReport']['SKIN_ROOT'], skin)
                self.assertTrue(os.path.isdir(p))

            # Retrieve the systemd utility file and check it
            path = os.path.join(dirname, 'util/systemd/weewx.service')
            with open(path, 'rt') as fd:
                for line in fd:
                    if line.startswith('ExecStart'):
                        self.assertEqual(line.strip(),
                                         f"ExecStart={sys.executable} {weewxd_path} {config_path}")


if __name__ == "__main__":
    unittest.main()
