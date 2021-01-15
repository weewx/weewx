#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test routines for weeplot.utilities"""

from __future__ import absolute_import
import os
import time
import unittest

from weeutil.weeutil import timestamp_to_string as to_string
from weeplot.utilities import scale, scaletime, xy_seq_line, \
    pickLabelFormat, _rel_approx_equal


class WeePlotUtilTest(unittest.TestCase):
    """Test the functions in weeplot.utilities"""

    def test_scale(self):
        """Test function scale()"""
        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(1.1, 12.3, (0, 14, 2)),
                         "(0.00000, 14.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(1.1, 12.3),
                         "(0.00000, 14.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(-1.1, 12.3),
                         "(-2.00000, 14.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(-12.1, -5.3),
                         "(-13.00000, -5.00000, 1.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(10.0, 10.0),
                         "(10.00000, 10.10000, 0.01000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(10.0, 10.001),
                         "(10.00000, 10.00100, 0.00010)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(10.0, 10.0 + 1e-8),
                         "(10.00000, 10.10000, 0.01000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(0.0, 0.05, (None, None, .1), 10),
                         "(0.00000, 1.00000, 0.10000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(16.8, 21.5, (None, None, 2), 10),
                         "(16.00000, 36.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(16.8, 21.5, (None, None, 2), 4),
                         "(16.00000, 22.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(0.0, 0.21, (None, None, .02)),
                         "(0.00000, 0.22000, 0.02000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(100.0, 100.0, (None, 100, None)),
                         "(99.00000, 100.00000, 0.20000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(100.0, 100.0, (100, None, None)),
                         "(100.00000, 101.00000, 0.20000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(100.0, 100.0, (0, None, None)),
                         "(0.00000, 120.00000, 20.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(0.0, 0.2, (None, 100, None)),
                         "(0.00000, 100.00000, 20.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(0.0, 0.0, (0, None, 1), 10),
                         "(0.00000, 10.00000, 2.00000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(-17.0, -5.0,
                                                      (0, None, .1), 10),
                         "(0.00000, 1.00000, 0.20000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(5.0, 17.0,
                                                      (None, 1, .1), 10),
                         "(0.00000, 1.00000, 0.20000)")

        self.assertEqual("(%.5f, %.5f, %.5f)" % scale(5.0, 17.0,
                                                      (0, 1, None)),
                         "(0.00000, 1.00000, 0.20000)")


    def test_scaletime(self):
        """test function scaletime()"""

        os.environ['TZ'] = 'America/Los_Angeles'
        time.tzset()

        # 24 hours on an hour boundary
        time_ts = time.mktime(time.strptime("2013-05-17 08:00", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 09:00:00 PDT (1368720000), "
                         "2013-05-17 09:00:00 PDT (1368806400), 10800")

        # 24 hours on a 3-hour boundary
        time_ts = time.mktime(time.strptime("2013-05-17 09:00", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 09:00:00 PDT (1368720000), "
                         "2013-05-17 09:00:00 PDT (1368806400), 10800")

        # 24 hours on a non-hour boundary
        time_ts = time.mktime(time.strptime("2013-05-17 09:01", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 12:00:00 PDT (1368730800), "
                         "2013-05-17 12:00:00 PDT (1368817200), 10800")

        # Example 4: 27 hours
        time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 27 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 06:00:00 PDT (1368709200), "
                         "2013-05-17 09:00:00 PDT (1368806400), 10800")

        # 3 hours on a 15 minute boundary
        time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 3 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-17 05:00:00 PDT (1368792000), "
                         "2013-05-17 08:00:00 PDT (1368802800), 900")

        #  3 hours on a non-15 minute boundary
        time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 3 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-17 05:00:00 PDT (1368792000), "
                         "2013-05-17 08:00:00 PDT (1368802800), 900")

        # 12 hours
        time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 12 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 20:00:00 PDT (1368759600), "
                         "2013-05-17 08:00:00 PDT (1368802800), 3600")

        # 15 hours
        time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        xmin, xmax, xinc = scaletime(time_ts - 15 * 3600, time_ts)
        self.assertEqual("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc),
                         "2013-05-16 17:00:00 PDT (1368748800), "
                         "2013-05-17 08:00:00 PDT (1368802800), 7200")

    def test_xy_seq_line(self):
        """Test function xy_seq_line()"""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.assertEqual([xy_seq for xy_seq
                          in xy_seq_line(x, y)], [[(1, 10), (2, 20), (3, 30)]])

        x = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        y = [0, 10, None, 30, None, None, 60, 70, 80, None]
        self.assertEqual([xy_seq for xy_seq
                          in xy_seq_line(x, y)], [[(0, 0), (1, 10)],
                                                  [(3, 30)],
                                                  [(6, 60), (7, 70), (8, 80)]])

        x = [0]
        y = [None]
        self.assertEqual([xy_seq for xy_seq in xy_seq_line(x, y)], [])

        x = [0, 1, 2]
        y = [None, None, None]
        self.assertEqual([xy_seq for xy_seq in xy_seq_line(x, y)], [])

        # Using maxdx of 2:
        x = [0, 1, 2, 3, 5.1, 6, 7, 8, 9]
        y = [0, 10, 20, 30, 50, 60, 70, 80, 90]
        self.assertEqual([xy_seq for xy_seq
                          in xy_seq_line(x, y, 2)], [[(0, 0), (1, 10), (2, 20), (3, 30)],
                                                     [(5.1, 50), (6, 60), (7, 70),
                                                      (8, 80), (9, 90)]])

    def test_pickLabelFormat(self):
        """Test function pickLabelFormat"""

        self.assertEqual(pickLabelFormat(1), "%.0f")
        self.assertEqual(pickLabelFormat(20), "%.0f")
        self.assertEqual(pickLabelFormat(.2), "%.1f")
        self.assertEqual(pickLabelFormat(.01), "%.2f")

    def test__rel_approx_equal(self):
        """Test function test__rel_approx_equal"""

        self.assertFalse(_rel_approx_equal(1.23456, 1.23457))
        self.assertTrue(_rel_approx_equal(1.2345678, 1.2345679))
        self.assertTrue(_rel_approx_equal(0.0, 0.0))
        self.assertFalse(_rel_approx_equal(0.0, 0.1))
        self.assertFalse(_rel_approx_equal(0.0, 1e-9))
        self.assertTrue(_rel_approx_equal(1.0, 1.0 + 1e-9))
        self.assertTrue(_rel_approx_equal(1e8, 1e8 + 1e-3))


if __name__ == '__main__':
    unittest.main()
