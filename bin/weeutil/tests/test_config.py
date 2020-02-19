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


if __name__ == '__main__':
    unittest.main()
