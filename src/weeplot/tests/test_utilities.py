#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test functions in weeplot.utilities"""

import os

import pytest

from weeplot.utilities import *
from weeplot.utilities import _rel_approx_equal
from weeutil.weeutil import timestamp_to_string as to_string

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()


def test_scale():
    """Test function scale()"""
    assert scale(1.1, 12.3, (0, 14, 2), 10) == (0.0, 14.0, 2.0)
    assert scale(1.1, 12.3) == (0.0, 14.0, 2.0)
    assert scale(-1.1, 12.3) == (-2.0, 14.0, 2.0)
    assert scale(-12.1, -5.3) == (-13.00000, -5.00000, 1.00000)
    assert scale(10.0, 10.0) == (10.00000, 10.10000, 0.01000)
    assert scale(10.0, 10.001) == pytest.approx((10.00000, 10.00100, 0.00010))
    assert scale(10.0, 10.0 + 1e-8) == (10.00000, 10.10000, 0.01000)
    assert scale(0.0, 0.05, (None, None, .1), 10) == (0.00000, 1.00000, 0.10000)
    assert scale(16.8, 21.5, (None, None, 2), 10) == (16.00000, 36.00000, 2.00000)
    assert scale(16.8, 21.5, (None, None, 2), 4) == (16.00000, 22.00000, 2.00000)
    assert scale(0.0, 0.21, (None, None, .02)) == (0.00000, 0.22000, 0.02000)
    assert scale(100.0, 100.0, (None, 100, None)) == (99.00000, 100.00000, 0.20000)
    assert scale(100.0, 100.0, (100, None, None)) == (100.00000, 101.00000, 0.20000)
    assert scale(100.0, 100.0, (0, None, None)) == (0.00000, 120.00000, 20.00000)
    assert scale(0.0, 0.2, (None, 100, None)) == (0.00000, 100.00000, 20.00000)
    assert scale(0.0, 0.0, (0, None, 1), 10) == (0.00000, 10.00000, 2.00000)
    assert scale(-17.0, -5.0, (0, None, .1), 10) == (0.00000, 1.00000, 0.20000)
    assert scale(5.0, 17.0, (None, 1, .1), 10) == (0.00000, 1.00000, 0.20000)
    assert scale(5.0, 17.0, (0, 1, None)) == (0.00000, 1.00000, 0.20000)

def test_scaletime():
    """test function scaletime()"""

    # 24 hours on an hour boundary
    time_ts = time.mktime(time.strptime("2013-05-17 08:00", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 09:00:00 PDT (1368720000), "
               "2013-05-17 09:00:00 PDT (1368806400), 10800")

    # 24 hours on a 3-hour boundary
    time_ts = time.mktime(time.strptime("2013-05-17 09:00", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 09:00:00 PDT (1368720000), "
               "2013-05-17 09:00:00 PDT (1368806400), 10800")

    # 24 hours on a non-hour boundary
    time_ts = time.mktime(time.strptime("2013-05-17 09:01", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 24 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 12:00:00 PDT (1368730800), "
               "2013-05-17 12:00:00 PDT (1368817200), 10800")

    # Example 4: 27 hours
    time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 27 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 06:00:00 PDT (1368709200), "
               "2013-05-17 09:00:00 PDT (1368806400), 10800")

    # 3 hours on a 15 minute boundary
    time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 3 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-17 05:00:00 PDT (1368792000), "
               "2013-05-17 08:00:00 PDT (1368802800), 900")

    #  3 hours on a non-15 minute boundary
    time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 3 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-17 05:00:00 PDT (1368792000), "
               "2013-05-17 08:00:00 PDT (1368802800), 900")

    # 12 hours
    time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 12 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 20:00:00 PDT (1368759600), "
               "2013-05-17 08:00:00 PDT (1368802800), 3600")

    # 15 hours
    time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
    xmin, xmax, xinc = scaletime(time_ts - 15 * 3600, time_ts)
    assert ("%s, %s, %s" % (to_string(xmin), to_string(xmax), xinc)
            == "2013-05-16 17:00:00 PDT (1368748800), "
               "2013-05-17 08:00:00 PDT (1368802800), 7200")

def test_xy_seq_line():
    """Test function xy_seq_line()"""
    x = [1, 2, 3]
    y = [10, 20, 30]
    assert ([xy_seq for xy_seq
             in xy_seq_line(x, y)] == [[(1, 10), (2, 20), (3, 30)]])

    x = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    y = [0, 10, None, 30, None, None, 60, 70, 80, None]
    assert ([xy_seq for xy_seq
             in xy_seq_line(x, y)] == [[(0, 0), (1, 10)],
                                       [(3, 30)],
                                       [(6, 60), (7, 70), (8, 80)]])

    x = [0]
    y = [None]
    assert ([xy_seq for xy_seq in xy_seq_line(x, y)] == [])

    x = [0, 1, 2]
    y = [None, None, None]
    assert ([xy_seq for xy_seq in xy_seq_line(x, y)] == [])

    # Using maxdx of 2:
    x = [0, 1, 2, 3, 5.1, 6, 7, 8, 9]
    y = [0, 10, 20, 30, 50, 60, 70, 80, 90]
    assert ([xy_seq for xy_seq in xy_seq_line(x, y, 2)]
            == [[(0, 0), (1, 10), (2, 20), (3, 30)],
                [(5.1, 50), (6, 60), (7, 70),
                 (8, 80), (9, 90)]])

def test_pickLabelFormat():
    """Test function pickLabelFormat"""

    assert pickLabelFormat(1) == "%.0f"
    assert pickLabelFormat(20) == "%.0f"
    assert pickLabelFormat(.2) == "%.1f"
    assert pickLabelFormat(.01) == "%.2f"

def test__rel_approx_equal():
    """Test function test__rel_approx_equal"""

    assert not _rel_approx_equal(1.23456, 1.23457)
    assert _rel_approx_equal(1.2345678, 1.2345679)
    assert _rel_approx_equal(0.0, 0.0)
    assert not _rel_approx_equal(0.0, 0.1)
    assert not _rel_approx_equal(0.0, 1e-9)
    assert _rel_approx_equal(1.0, 1.0 + 1e-9)
    assert _rel_approx_equal(1e8, 1e8 + 1e-3)

def test_tobgr():
    """Test the function tobgr()"""
    assert tobgr("red") == 0x0000ff, "Test color name"
    assert tobgr("#f1f2f3") == 0xf3f2f1, "Test RGB string"
    assert tobgr("0xf1f2f3") == 0xf1f2f3, "Test BGR string"
    assert tobgr(0xf1f2f3) == 0xf1f2f3, "Test BGR int"
    with pytest.raises(ValueError):
        tobgr("#f1f2fk")
