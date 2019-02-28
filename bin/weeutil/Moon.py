#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Given a date, determine the phase of the moon."""

from __future__ import absolute_import
import time
import math

moon_phases = ["new (totally dark)",
               "waxing crescent (increasing to full)",
               "in its first quarter (increasing to full)",
               "waxing gibbous (increasing to full)",
               "full (full light)",
               "waning gibbous (decreasing from full)",
               "in its last quarter (decreasing from full)",
               "waning crescent (decreasing from full)"]

# First new moon of 2018: 17-Jan-2018 at 02:17 UTC
new_moon_2018 = 1516155420


def moon_phase(year, month, day, hour=12):
    """Calculates the phase of the moon, given a year, month, day.

    returns: a tuple. First value is an index into an array
    of moon phases, such as Moon.moon_phases above. Second
    value is the percent fullness of the moon.
    """

    # Convert to UTC
    time_ts = time.mktime((year, month, day, hour, 0, 0, 0, 0, -1))

    return moon_phase_ts(time_ts)


def moon_phase_ts(time_ts):
    # How many days since the first moon of 2018
    delta_days = (time_ts - new_moon_2018) / 86400.0
    # Number of lunations
    lunations = delta_days / 29.530588

    # The fraction of the lunar cycle
    position = float(lunations) % 1.0
    # The percent illumination, rounded to the nearest integer
    fullness = int(100.0 * (1.0 - math.cos(2.0 * math.pi * position)) / 2.0 + 0.5)
    index = int((position * 8) + 0.5) & 7

    return index, fullness
