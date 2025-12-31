#
#    Copyright (c) 2018-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import os
import time
import pytest

from weeutil import Sun


def test_sun_rise_set():
    os.environ['TZ'] = 'Australia/Sydney'
    time.tzset()
    # Sydney, Australia
    result = Sun.sunRiseSet(2012, 1, 1, 151.21, -33.86)
    assert result[0] == pytest.approx(-5.223949864965772, abs=1e-6)
    assert result[1] == pytest.approx(9.152208948206106, abs=1e-6)

    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    # Hood River, USA
    result = Sun.sunRiseSet(2012, 1, 1, -121.566, 45.686)
    assert result[0] == pytest.approx(15.781521580780003, abs=1e-6)
    assert result[1] == pytest.approx(24.528947667456983, abs=1e-6)
