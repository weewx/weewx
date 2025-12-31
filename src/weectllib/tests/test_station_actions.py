#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
import os
import sys
import tempfile

import configobj
import pytest

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


@pytest.fixture
def config_dict():
    """Return a copy of the configuration dictionary."""
    return weeutil.config.deep_copy(CONFIG_DICT)


class TestLocationConfig:

    def test_default_config_location(self, config_dict):
        weectllib.station_actions.config_location(config_dict, no_prompt=True)
        assert config_dict['Station']['location'] == "WeeWX station"
        del config_dict['Station']['location']
        weectllib.station_actions.config_location(config_dict, no_prompt=True)
        assert config_dict['Station']['location'] == "WeeWX station"

    def test_arg_config_location(self, config_dict):
        weectllib.station_actions.config_location(config_dict, location='foo', no_prompt=True)
        assert config_dict['Station']['location'] == "foo"

    def test_prompt_config_location(self, config_dict, capsys, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda _: '')
        weectllib.station_actions.config_location(config_dict)
        assert config_dict['Station']['location'] == "WeeWX station"
        monkeypatch.setattr('builtins.input', lambda _: 'bar')
        weectllib.station_actions.config_location(config_dict)
        assert config_dict['Station']['location'] == "bar"


class TestAltitudeConfig:

    def test_default_config_altitude(self, config_dict):
        weectllib.station_actions.config_altitude(config_dict, no_prompt=True)
        assert config_dict['Station']['altitude'] == ["0", "foot"]
        # Delete the value in the configuration dictionary
        del config_dict['Station']['altitude']
        # Now we should get the hardwired default
        weectllib.station_actions.config_altitude(config_dict, no_prompt=True)
        assert config_dict['Station']['altitude'] == ["0", "foot"]

    def test_arg_config_altitude(self, config_dict):
        weectllib.station_actions.config_altitude(config_dict, altitude="500, meter")
        assert config_dict['Station']['altitude'] == ["500", "meter"]

    def test_badarg_config_altitude(self, config_dict):
        with pytest.raises(ValueError):
            # Bad unit
            weectllib.station_actions.config_altitude(config_dict, altitude="500, foo")
        with pytest.raises(ValueError):
            # Bad value
            weectllib.station_actions.config_altitude(config_dict, altitude="500f, foot")

    def test_prompt_config_altitude(self, config_dict, capsys, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda _: '')
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["0", "foot"]
        monkeypatch.setattr('builtins.input', lambda _: '110, meter')
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["110", "meter"]
        # Try 'feet' instead of 'foot'
        monkeypatch.setattr('builtins.input', lambda _: '700, feet')
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["700", "foot"]
        # Try 'meters' instead of 'meter':
        monkeypatch.setattr('builtins.input', lambda _: '110, meters')
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["110", "meter"]

    def test_badprompt_config_altitude(self, config_dict, capsys, monkeypatch):
        # Include a bad unit. It should prompt again
        responses = iter(['100, foo', '110, meter'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["110", "meter"]
        # Include a bad value. It should prompt again
        responses = iter(['100f, foot', '110, meter'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_altitude(config_dict)
        assert config_dict['Station']['altitude'] == ["110", "meter"]


class TestLatLonConfig:

    def test_default_config_latlon(self, config_dict):
        # Use the default as supplied by CONFIG_DICT
        weectllib.station_actions.config_latlon(config_dict, no_prompt=True)
        assert float(config_dict['Station']['latitude']) == 0.0
        assert float(config_dict['Station']['longitude']) == 0.0
        # Delete the values in the configuration dictionary
        del config_dict['Station']['latitude']
        del config_dict['Station']['longitude']
        # Now the defaults should be the hardwired defaults
        weectllib.station_actions.config_latlon(config_dict, no_prompt=True)
        assert float(config_dict['Station']['latitude']) == 0.0
        assert float(config_dict['Station']['longitude']) == 0.0

    def test_arg_config_latlon(self, config_dict):
        weectllib.station_actions.config_latlon(config_dict, latitude='-20', longitude='-40')
        assert float(config_dict['Station']['latitude']) == -20.0
        assert float(config_dict['Station']['longitude']) == -40.0

    def test_badarg_config_latlon(self, config_dict):
        with pytest.raises(ValueError):
            weectllib.station_actions.config_latlon(config_dict, latitude="-20f",
                                                   longitude='-40')

    def test_prompt_config_latlong(self, config_dict, capsys, monkeypatch):
        responses = iter(['-21', '-41'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_latlon(config_dict)
        assert float(config_dict['Station']['latitude']) == -21.0
        assert float(config_dict['Station']['longitude']) == -41.0


class TestRegistryConfig:

    def test_default_register(self, config_dict):
        weectllib.station_actions.config_registry(config_dict, no_prompt=True)
        assert not config_dict['StdRESTful']['StationRegistry']['register_this_station']

    def test_args_register(self, config_dict):
        # Missing station_url:
        with pytest.raises(weewx.ViolatedPrecondition):
            weectllib.station_actions.config_registry(config_dict, register='True',
                                                      no_prompt=True)
        # This time we supply a station_url. Should be OK.
        weectllib.station_actions.config_registry(config_dict, register='True',
                                                  station_url=STATION_URL, no_prompt=True)
        assert config_dict['StdRESTful']['StationRegistry']['register_this_station']
        assert config_dict['Station']['station_url'] == STATION_URL
        # Alternatively, the config file already had a station_url:
        config_dict['Station']['station_url'] = STATION_URL
        weectllib.station_actions.config_registry(config_dict, register='True',
                                                  no_prompt=True)
        assert config_dict['StdRESTful']['StationRegistry']['register_this_station']
        assert config_dict['Station']['station_url'] == STATION_URL

    def test_prompt_register(self, config_dict, capsys, monkeypatch):
        responses = iter(['y', STATION_URL])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_registry(config_dict)
        assert config_dict['StdRESTful']['StationRegistry']['register_this_station']
        assert config_dict['Station']['station_url'] == STATION_URL

        # Try again, but without specifying an URL. Should ask twice.
        responses = iter(['y', '', STATION_URL])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_registry(config_dict)
        assert config_dict['StdRESTful']['StationRegistry']['register_this_station']
        assert config_dict['Station']['station_url'] == STATION_URL

        # Now with a bogus URL
        responses = iter(['y', 'https://www.example.com', STATION_URL])
        weectllib.station_actions.config_registry(config_dict)
        assert config_dict['StdRESTful']['StationRegistry']['register_this_station']
        assert config_dict['Station']['station_url'] == STATION_URL


class TestUnitsConfig:

    def test_default_units(self, config_dict):
        weectllib.station_actions.config_units(config_dict, no_prompt=True)
        assert config_dict['StdReport']['Defaults']['unit_system'] == 'us'

    def test_custom_units(self, config_dict):
        del config_dict['StdReport']['Defaults']['unit_system']
        weectllib.station_actions.config_units(config_dict, no_prompt=True)
        assert 'unit_system' not in config_dict['StdReport']['Defaults']

    def test_args_units(self, config_dict):
        weectllib.station_actions.config_units(config_dict, unit_system='metricwx',
                                               no_prompt=True)
        assert config_dict['StdReport']['Defaults']['unit_system'] == 'metricwx'

    def test_prompt_units(self, config_dict, capsys, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda _: 'metricwx')
        weectllib.station_actions.config_units(config_dict)
        assert config_dict['StdReport']['Defaults']['unit_system'] == 'metricwx'
        # Do it again, but with a wrong unit system name. It should ask again.
        responses = iter(['metricwz', 'metricwx'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_units(config_dict)
        assert config_dict['StdReport']['Defaults']['unit_system'] == 'metricwx'


class TestDriverConfig:

    def test_default_config_driver(self, config_dict):
        weectllib.station_actions.config_driver(config_dict, no_prompt=True)
        assert config_dict['Station']['station_type'] == 'Simulator'
        assert config_dict['Simulator']['driver'] == 'weewx.drivers.simulator'

    def test_arg_config_driver(self, config_dict):
        weectllib.station_actions.config_driver(config_dict, driver='weewx.drivers.vantage',
                                                no_prompt=True)
        assert config_dict['Station']['station_type'] == 'Vantage'
        assert config_dict['Vantage']['driver'] == 'weewx.drivers.vantage'

    def test_arg_noeditor_config_driver(self, config_dict):
        # Test a driver that does not have a configurator editor. Because all WeeWX drivers do, we
        # have to disable one of them.
        import weewx.drivers.vantage
        weewx.drivers.vantage.hold = weewx.drivers.vantage.confeditor_loader
        del weewx.drivers.vantage.confeditor_loader
        # At this point, there is no configuration loader, so a minimal version of [Vantage]
        # should be supplied.
        weectllib.station_actions.config_driver(config_dict,
                                                driver='weewx.drivers.vantage',
                                                no_prompt=True)
        assert config_dict['Station']['station_type'] == 'Vantage'
        assert config_dict['Vantage']['driver'] == 'weewx.drivers.vantage'
        # The rest of the [Vantage] stanza should be missing. Try a key.
        assert 'port' not in config_dict['Vantage']
        # Restore the editor:
        weewx.drivers.vantage.confeditor_loader = weewx.drivers.vantage.hold

    def test_prompt_config_driver(self, config_dict, capsys, monkeypatch):
        responses = iter(['6', '', '/dev/ttyS0'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_driver(config_dict)
        assert config_dict['Station']['station_type'] == 'Vantage'
        assert config_dict['Vantage']['port'] == '/dev/ttyS0'

        # Do it again. This time, the stanza ['Vantage'] will exist, and we'll just modify it
        responses = iter(['', '', '/dev/ttyS1'])
        monkeypatch.setattr('builtins.input', lambda _: next(responses))
        weectllib.station_actions.config_driver(config_dict)
        assert config_dict['Station']['station_type'] == 'Vantage'
        assert config_dict['Vantage']['port'] == '/dev/ttyS1'


class TestConfigRoots:

    def test_args_config_roots(self, config_dict):
        weectllib.station_actions.config_roots(config_dict, skin_root='foo',
                                               html_root='bar', sqlite_root='baz')
        assert config_dict['StdReport']['SKIN_ROOT'] == 'foo'
        assert config_dict['StdReport']['HTML_ROOT'] == 'bar'
        assert config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] == 'baz'

        # Delete the options, then try again. They should be replaced with defaults
        del config_dict['StdReport']['SKIN_ROOT']
        del config_dict['StdReport']['HTML_ROOT']
        del config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT']
        weectllib.station_actions.config_roots(config_dict)
        assert config_dict['StdReport']['SKIN_ROOT'] == 'skins'
        assert config_dict['StdReport']['HTML_ROOT'] == 'public_html'
        assert config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] == 'archive'


class TestCreateStation:

    def test_create_default(self):
        """Test creating a new station"""
        # Get a temporary directory to create it in
        with tempfile.TemporaryDirectory(dir='/var/tmp') as weewx_root:
            # We have not run 'pip', so the only copy of weewxd.py is the one in the repository.
            # Create a station using the defaults
            weectllib.station_actions.station_create(weewx_root=weewx_root, no_prompt=True)
            config_path = os.path.join(weewx_root, 'weewx.conf')

            # Retrieve the config file that was created and check it:
            config_dict = configobj.ConfigObj(config_path, encoding='utf-8')
            assert 'WEEWX_ROOT' not in config_dict
            assert 'WEEWX_ROOT_CONFIG' not in config_dict
            assert config_dict['Station']['station_type'] == 'Simulator'
            assert config_dict['Simulator']['driver'] == 'weewx.drivers.simulator'
            assert config_dict['StdReport']['SKIN_ROOT'] == 'skins'
            assert config_dict['StdReport']['HTML_ROOT'] == 'public_html'
            assert config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] == 'archive'

            # Make sure all the skins are there
            for skin in ['Seasons', 'Smartphone', 'Mobile', 'Standard',
                         'Ftp', 'Rsync']:
                p = os.path.join(weewx_root, config_dict['StdReport']['SKIN_ROOT'], skin)
                assert os.path.isdir(p)

            # Retrieve the systemd utility file and check it
            path = os.path.join(weewx_root, 'util/systemd/weewx.service')
            with open(path, 'rt') as fd:
                for line in fd:
                    if line.startswith('ExecStart'):
                        assert line.strip() == f"ExecStart={sys.executable} {weewxd_path} {config_path}"


class TestReconfigureStation:

    def test_reconfigure(self):
        """Test reconfiguring a station"""
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
            assert config_dict['WEEWX_ROOT'] == '/etc/weewx'
            assert 'WEEWX_ROOT_CONFIG' not in config_dict
            assert config_dict['Station']['station_type'] == 'Vantage'
            assert config_dict['Vantage']['driver'] == 'weewx.drivers.vantage'
            assert config_dict['StdReport']['SKIN_ROOT'] == 'skins'
            assert config_dict['StdReport']['HTML_ROOT'] == 'public_html'
            assert config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] == 'archive'
