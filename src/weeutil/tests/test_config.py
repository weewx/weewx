#
#    Copyright (c) 2020-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weeutil.config"""
import logging
from io import BytesIO, StringIO

import configobj
import pytest

import weeutil.config
import weeutil.logger
import weewx

weewx.debug = 1

log = logging.getLogger(__name__)

# Set up logging using the defaults.
weeutil.logger.setup('weetest_config')


def test_config_from_str():
    test_str = """degree_C = °C"""
    c = weeutil.config.config_from_str(test_str)
    # Make sure the values are Unicode
    assert type(c['degree_C']) is str


class TestConfig:
    test_dict_str = u"""[Logging]
    [[formatters]]
        [[[simple]]]
            # -1.33 à 1.72?? -2.3 à 990mb (mes 1068)
            format = %(levelname)s %(message)s    # Inline comment æ ø å
        [[[standard]]]
            format = {process_name}[%(process)d]
        [[[verbose]]]
            format = {process_name}[%(process)d] %(levelname)s
            datefmt = %Y-%m-%d %H:%M:%S
"""

    @pytest.fixture
    def c_in(self):
        test_dict = StringIO(TestConfig.test_dict_str)
        return configobj.ConfigObj(test_dict, encoding='utf-8', default_encoding='utf-8')

    def test_deep_copy_ConfigObj(self, c_in):
        """Test copying a full ConfigObj"""

        c_out = weeutil.config.deep_copy(c_in)
        assert isinstance(c_out, configobj.ConfigObj)
        assert c_out == c_in

        # Make sure the parentage is correct
        assert c_out['Logging']['formatters'].parent is c_out['Logging']
        assert c_out['Logging']['formatters'].parent.parent is c_out
        assert c_out['Logging']['formatters'].main is c_out
        assert c_out['Logging']['formatters'].main is not c_in
        assert c_out.main is c_out
        assert c_out.main is not c_in

        # Try changing something and see if it's still equal:
        c_out['Logging']['formatters']['verbose']['datefmt'] = 'foo'
        assert c_out != c_in
        # The original ConfigObj entry should still be the same
        assert c_in['Logging']['formatters']['verbose']['datefmt'] == '%Y-%m-%d %H:%M:%S'

    def test_deep_copy_Section(self, c_in):
        """Test copying just a section"""
        c_out = weeutil.config.deep_copy(c_in['Logging']['formatters'])
        assert not isinstance(c_out, configobj.ConfigObj)
        assert isinstance(c_out, configobj.Section)
        assert c_out == c_in['Logging']['formatters']

        # Check parentage
        assert c_out.main is c_in
        assert c_out.parent is c_in['Logging']
        assert c_out['verbose'].parent is c_out
        assert c_out['verbose'].parent.parent is c_in['Logging']

    def test_deep_copy_write(self, c_in):
        c_out = weeutil.config.deep_copy(c_in)
        bio = BytesIO()
        c_out.write(bio)
        bio.seek(0)
        out_str = bio.read().decode('utf-8')
        assert out_str == TestConfig.test_dict_str
