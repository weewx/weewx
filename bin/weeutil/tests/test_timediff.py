#
#    Copyright (c) 2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test routines for weeutil.timediff."""

from __future__ import with_statement

import time
import unittest

import weewx
from weeutil.timediff import *

start = time.mktime((2013, 3, 10, 0, 0, 0, 0, 0, -1))

record1 = {
    'dateTime': start,
    'outTemp': 20.0,
}

record2 = {
    'dateTime': start + 100,
    'outTemp': 21.0,
}

record3 = {
    'dateTime': start + 400,
    'outTemp': 21.0,
}


class TimeDiffTest(unittest.TestCase):

    def test_simple(self):
        time_diff = TimeDerivative('outTemp', 300)
        self.assertIsNone(time_diff.add_record(record1))
        self.assertEqual(time_diff.add_record(record2), .01)

    def test_backwards(self):
        time_diff = TimeDerivative('outTemp', 300)
        self.assertIsNone(time_diff.add_record(record2))
        with self.assertRaises(weewx.ViolatedPrecondition):
            time_diff.add_record(record1)

    def test_no_fwd(self):
        time_diff = TimeDerivative('outTemp', 300)
        self.assertIsNone(time_diff.add_record(record1))
        self.assertIsNone(time_diff.add_record(record1))

    def test_too_old(self):
        time_diff = TimeDerivative('outTemp', 300)
        self.assertIsNone(time_diff.add_record(record1))
        self.assertIsNone(time_diff.add_record(record3))

    def test_not_there(self):
        time_diff = TimeDerivative('outTemp', 300)
        with self.assertRaises(weewx.CannotCalculate):
            time_diff.add_record({'dateTime': start})


if __name__ == '__main__':
    unittest.main()
