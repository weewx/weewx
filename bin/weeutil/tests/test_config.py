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
import configobj

import weewx
import weeutil.logger
import weeutil.config

weewx.debug = 1

log = logging.getLogger(__name__)

# Set up logging using the defaults.
weeutil.logger.setup('test_config', {})


class TestConfig(unittest.TestCase):
    test_dict = {'Logging':
                     {'formatters':
                          {'simple': {'format': '%(levelname)s %(message)s'},
                           'standard': {'format': '{process_name}[%(process)d]'},
                           'verbose': {
                               'format': '{process_name}[%(process)d] %(levelname)s',
                               'datefmt': '%Y-%m-%d %H:%M:%S'}}
                      }
                 }

    def test_config_from_str(self):
        test_str = """degree_C = °C"""
        c = weeutil.config.config_from_str(test_str)
        # Make sure the values are Unicode
        self.assertEqual(type(c['degree_C']), six.text_type)

    def test_deep_copy_ConfigObj(self):
        """Test copying a full ConfigObj"""

        c_in = configobj.ConfigObj(TestConfig.test_dict, encoding='utf-8')
        c_out = weeutil.config.deep_copy(c_in)
        self.assertIsInstance(c_out, configobj.ConfigObj)
        self.assertEqual(c_out, TestConfig.test_dict)
        self.assertEqual(c_out, c_in)

        # Make sure the parentage is correct
        self.assertIs(c_out['Logging']['formatters'].parent, c_out['Logging'])
        self.assertIs(c_out['Logging']['formatters'].parent.parent, c_out)
        self.assertIs(c_out['Logging']['formatters'].main, c_out)
        self.assertIsNot(c_out['Logging']['formatters'].main, c_in)
        self.assertIs(c_out.main, c_out)
        self.assertIsNot(c_out.main, c_in)

        # Try changing something and see if it's still equal:
        c_out['Logging']['formatters']['verbose']['datefmt'] = 'foo'
        self.assertNotEqual(c_out, TestConfig.test_dict)
        # The original ConfigObj entry should still be the same
        self.assertEqual(TestConfig.test_dict['Logging']['formatters']['verbose']['datefmt'],
                         '%Y-%m-%d %H:%M:%S')
        self.assertEqual(c_in['Logging']['formatters']['verbose']['datefmt'],
                         '%Y-%m-%d %H:%M:%S')

    def test_deep_copy_Section(self):
        """Test copying just a section"""
        c_in = configobj.ConfigObj(TestConfig.test_dict, encoding='utf-8')
        c_out = weeutil.config.deep_copy(c_in['Logging']['formatters'])
        self.assertNotIsInstance(c_out, configobj.ConfigObj)
        self.assertIsInstance(c_out, configobj.Section)
        self.assertEqual(c_out, c_in['Logging']['formatters'])
        self.assertEqual(c_out, TestConfig.test_dict['Logging']['formatters'])

        # Check parentage
        self.assertIs(c_out.main, c_in)
        self.assertIs(c_out.parent, c_in['Logging'])
        self.assertIs(c_out['verbose'].parent, c_out)
        self.assertIs(c_out['verbose'].parent.parent, c_in['Logging'])


if __name__ == '__main__':
    unittest.main()
