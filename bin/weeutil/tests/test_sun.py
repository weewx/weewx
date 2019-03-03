#
#    Copyright (c) 2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
from __future__ import absolute_import

import os
import time
import unittest

from weeutil import Sun


class SunTest(unittest.TestCase):

    def test_sunRiseSet(self):
        os.environ['TZ'] = 'Australia/Sydney'
        time.tzset()
        # Sydney, Australia
        result = Sun.sunRiseSet(2012, 1, 1, 151.21, -33.86)
        self.assertAlmostEqual(result[0], -5.223949864965772, 6)
        self.assertAlmostEqual(result[1], 9.152208948206106, 6)

        os.environ['TZ'] = 'America/Los_Angeles'
        time.tzset()
        # Hood River, USA
        result = Sun.sunRiseSet(2012, 1, 1, -121.566, 45.686)
        self.assertAlmostEqual(result[0], 15.781521580780003, 6)
        self.assertAlmostEqual(result[1], 24.528947667456983, 6)


unittest.main()
