#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.defaults"""
import logging
import unittest

import six
import weeutil.logger
import weewx.defaults

weewx.debug = 1

log = logging.getLogger(__name__)

# Set up logging using the defaults.
weeutil.logger.setup('test_defaults', {})

class TestDefaults(unittest.TestCase):

    def test_defaults(self):
        # Make sure the values are Unicode
        v = weewx.defaults.defaults['Units']['Labels']['degree_C']
        self.assertEqual(type(v), six.text_type)


if __name__ == '__main__':
    unittest.main()
