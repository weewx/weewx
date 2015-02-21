#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Determine the phase of the moon phase given a date.
    CF: http://en.wikipedia.org/wiki/Lunar_phase
"""

import datetime
import math
import decimal

dec = decimal.Decimal

moon_phases = ["new (totally dark)", 
               "waxing crescent (increasing to full)", 
               "in its first quarter (increasing to full)", 
               "waxing gibbous (increasing to full)", 
               "full (full light)", 
               "waning gibbous (decreasing from full)", 
               "in its last quarter (decreasing from full)", 
               "waning crescent (decreasing from full)"]


def moon_phase(year, month, day):
    """Calculates the phase of the moon, given a year, month, day.
    
    returns: a tuple. First value is an index into an array
    of moon phases, such as Moon.moon_phases above. Second
    value is the percent fullness of the moon.
    """
    time_dt = datetime.datetime(year, month, day)
    diff = time_dt - datetime.datetime(2001, 1, 1)
    
    days = dec(diff.days) + (dec(diff.seconds) / dec(86400))
    lunations = dec('0.20439731') + (days / dec('29.530589'))
    position = float(lunations) % 1.0
    fullness = int(100.0*(1.0 - math.cos(2.0 * math.pi * position))/2.0 + 0.5)
    index = int((position * 8) + 0.5) & 7

    return (index, fullness)
