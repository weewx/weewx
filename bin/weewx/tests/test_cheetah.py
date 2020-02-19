# -*- coding: utf-8 -*-
#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test functions in cheetahgenerator"""

import logging
import unittest

import weeutil.logger
import weeutil.weeutil
import weewx
import weewx.cheetahgenerator
from weewx.units import ValueTuple, ValueHelper

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_cheetah', {})


class TestFilter(unittest.TestCase):
    "Test the function filter() in AssureUnicode"
    def test_none(self):
        val = None
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val)
        self.assertEqual(filtered_value, u'')

    def test_str(self):
        val = "abcdé"
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val)
        self.assertEqual(filtered_value, u"abcdé")

    def test_byte_str(self):
        val = b'abcd\xc3\xa9'
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val)
        self.assertEqual(filtered_value, u"abcdé")

    def test_int(self):
        val = 27
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val)
        self.assertEqual(filtered_value, u"27")

    def test_float(self):
        val = 27.9
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val)
        self.assertEqual(filtered_value, u"27.9")

    def test_ValueHelper(self):
        val_vh = ValueHelper(ValueTuple(20.0, 'degree_C', 'group_temperature'))
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val_vh)
        self.assertEqual(filtered_value, u"68.0°F")


if __name__ == '__main__':
    unittest.main()
