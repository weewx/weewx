# coding: utf-8
#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weeutil.config"""
import logging
import unittest

import six
from io import BytesIO
from six.moves import StringIO
import configobj

import weewx
import weeutil.logger
import weeutil.config

weewx.debug = 1

log = logging.getLogger(__name__)

# Set up logging using the defaults.
weeutil.logger.setup('test_config', {})


class TestConfigString(unittest.TestCase):

    def test_config_from_str(self):
        test_str = """degree_C = °C"""
        c = weeutil.config.config_from_str(test_str)
        # Make sure the values are Unicode
        self.assertEqual(type(c['degree_C']), six.text_type)


class TestConfig(unittest.TestCase):
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

    def setUp(self):
        test_dict = StringIO(TestConfig.test_dict_str)
        self.c_in = configobj.ConfigObj(test_dict, encoding='utf-8', default_encoding='utf-8')

    def test_deep_copy_ConfigObj(self):
        """Test copying a full ConfigObj"""

        c_out = weeutil.config.deep_copy(self.c_in)
        self.assertIsInstance(c_out, configobj.ConfigObj)
        self.assertEqual(c_out, self.c_in)

        # Make sure the parentage is correct
        self.assertIs(c_out['Logging']['formatters'].parent, c_out['Logging'])
        self.assertIs(c_out['Logging']['formatters'].parent.parent, c_out)
        self.assertIs(c_out['Logging']['formatters'].main, c_out)
        self.assertIsNot(c_out['Logging']['formatters'].main, self.c_in)
        self.assertIs(c_out.main, c_out)
        self.assertIsNot(c_out.main, self.c_in)

        # Try changing something and see if it's still equal:
        c_out['Logging']['formatters']['verbose']['datefmt'] = 'foo'
        self.assertNotEqual(c_out, self.c_in)
        # The original ConfigObj entry should still be the same
        self.assertEqual(self.c_in['Logging']['formatters']['verbose']['datefmt'],
                         '%Y-%m-%d %H:%M:%S')

    def test_deep_copy_Section(self):
        """Test copying just a section"""
        c_out = weeutil.config.deep_copy(self.c_in['Logging']['formatters'])
        self.assertNotIsInstance(c_out, configobj.ConfigObj)
        self.assertIsInstance(c_out, configobj.Section)
        self.assertEqual(c_out, self.c_in['Logging']['formatters'])

        # Check parentage
        self.assertIs(c_out.main, self.c_in)
        self.assertIs(c_out.parent, self.c_in['Logging'])
        self.assertIs(c_out['verbose'].parent, c_out)
        self.assertIs(c_out['verbose'].parent.parent, self.c_in['Logging'])

    def test_deep_copy_write(self):
        c_out = weeutil.config.deep_copy(self.c_in)
        bio = BytesIO()
        c_out.write(bio)
        bio.seek(0)
        out_str = bio.read().decode('utf-8')
        self.assertEqual(out_str, TestConfig.test_dict_str)


if __name__ == '__main__':
    unittest.main()
