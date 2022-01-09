# -*- coding: utf-8 -*-
#
#    Copyright (c) 2021 Tom Keffer <tkeffer@gmail.com>
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


class RaiseException(object):
    def __str__(self):
        raise AttributeError("Fine mess you got me in!")


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
        val_vh = ValueHelper(ValueTuple(20.0, 'degree_C', 'group_temperature'),
                             formatter=weewx.units.get_default_formatter())
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(val_vh)
        self.assertEqual(filtered_value, u"20.0°C")

    def test_RaiseException(self):
        r = RaiseException()
        au = weewx.cheetahgenerator.AssureUnicode()
        filtered_value = au.filter(r)
        self.assertEqual(filtered_value, u'Fine mess you got me in!?')


class TestHelpers(unittest.TestCase):
    "Test the helper functions"

    def test_jsonize(self):
        full = zip([0, None, 4], [1, 3, 5])
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.jsonize(full),
                         '[[0, 1], [null, 3], [4, 5]]')
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.jsonize([complex(1,2), complex(3,4)]),
                         '[[1.0, 2.0], [3.0, 4.0]]')

    def test_rnd(self):
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.rnd(1.2345, 2), 1.23)
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.rnd(-1.2345, 2), -1.23)
        self.assertIsNone(weewx.cheetahgenerator.JSONHelpers.rnd(None, 2))

    def test_to_int(self):
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.to_int(1.2345), 1)
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.to_int('1.2345'), 1)
        self.assertEqual(weewx.cheetahgenerator.JSONHelpers.to_int(-1.2345), -1)
        self.assertIsNone(weewx.cheetahgenerator.JSONHelpers.to_int(None))


if __name__ == '__main__':
    unittest.main()
