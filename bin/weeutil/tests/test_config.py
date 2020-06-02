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

    def test_config_from_str(self):
        test_str = """degree_C = °C"""
        c = weeutil.config.config_from_str(test_str)
        # Make sure the values are Unicode
        self.assertEqual(type(c['degree_C']), six.text_type)

    def test_deep_copy(self):
        test_dict = {'Logging':
                         {'formatters':
                              {'simple': {'format': '%(levelname)s %(message)s'},
                               'standard': {'format': '{process_name}[%(process)d]'},
                               'verbose': {
                                   'format': '{process_name}[%(process)d] %(levelname)s',
                                   'datefmt': '%Y-%m-%d %H:%M:%S'}}
                          }
                     }

        c_in = configobj.ConfigObj(test_dict, encoding='utf-8')
        c_out = weeutil.config.deep_copy(c_in['Logging'])
        self.assertIsInstance(c_out, configobj.Section)
        self.assertEqual(c_out, test_dict['Logging'])
        # Try changing something and see if it's still equal:
        c_out['formatters']['simple']['format'] = 'foo'
        self.assertNotEqual(c_out, test_dict['Logging'])
        # The original ConfigObj entry should still be the same
        self.assertEqual(test_dict['Logging']['formatters']['simple']['format'],
                         '%(levelname)s %(message)s')

        # Make sure the parentage is correct
        self.assertIs(c_out['formatters'].parent, c_out)
        self.assertIs(c_out['formatters']['simple'].parent.parent, c_out)


if __name__ == '__main__':
    unittest.main()
