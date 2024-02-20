# -*- coding: utf-8 -*-
#
#    Copyright (c) 2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test functions in imagegenerator"""

import logging
import unittest

import weeutil.logger
import weeutil.weeutil
import weewx
import weewx.imagegenerator
from weewx.units import ValueTuple, ValueHelper

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('weetest_image')


class RaiseException(object):
    def __str__(self):
        raise AttributeError("Fine mess you got me in!")


class TestHelpers(unittest.TestCase):
    "Test the helper functions"

    def test_get_plot_time(self):
        """Test _get_plot_time() method."""

        options = {}
        ts = 1708423200
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 86400, ts))
        options['time_length'] = 28800
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 28800, ts))
        options['time_length'] = '2d'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400, ts))
        options['end_time'] = ''
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400 , ts))
        options['end_time'] = 'cow'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400, ts))
        options['end_time'] = 'giraffe'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400, ts))
        options['end_time'] = 'now'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400, ts))
        options['end_time'] = 'now\t\n\r'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 2 * 86400, ts))
        options['time_length'] = 10800
        options['end_time'] = 'now+2h'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts + 7200 - 10800, ts + 7200))
        options['end_time'] = 'now  +  2h'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts + 7200 - 10800, ts + 7200))
        options['end_time'] = 'now-1d'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 86400 - 10800, ts - 86400))
        options['end_time'] = 'now-3600'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 3600 - 10800, ts - 3600))
        options['end_time'] = 'now-60M'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 3600 - 10800, ts - 3600))
        options['end_time'] = 'now-2w'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 14 * 86400 - 10800, ts - 14 * 86400))
        options['end_time'] = 'now-3m'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 3 * 365.25/12 * 86400 - 10800, ts - 3 * 365.25/12 * 86400))
        options['end_time'] = 'now-1y'
        self.assertEqual(weewx.imagegenerator._get_plot_times(ts, options),
                         (ts - 365.25 * 86400 - 10800, ts - 365.25 * 86400))


if __name__ == '__main__':
    unittest.main()
