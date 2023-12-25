#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Various handy utilities that don't belong anywhere else.

   NB: To run the doctests, this code must be run as a module. For example:
     cd ~/git/weewx/src
     python -m weeutil.weeutil
"""

import calendar
import cmath
import datetime
import importlib
import math
import os
import re
import shutil
import time
from collections import ChainMap

# importlib.resources is 3.7 or later, importlib_resources is the backport
try:
    import importlib.resources as importlib_resources
except:
    import importlib_resources

# For backwards compatibility:
from weeutil.config import accumulateLeaves, search_up


def convertToFloat(seq):
    """Convert a sequence with strings to floats, honoring 'Nones'

    Args:
        seq(None|list[str]): A sequence of strings representing floats, possibly with a 'none'
            in there

    Returns:
        list[float]: All strings will have been converted to floats.

    Example:
        >>> print(convertToFloat(['1.2', '-2.5', 'none', '8.5']))
        [1.2, -2.5, None, 8.5]
    """

    if seq is None:
        return None
    res = [None if s in ('None', 'none') else float(s) for s in seq]
    return res


def option_as_list(option):
    if option is None:
        return None
    return [option] if not isinstance(option, list) else option


to_list = option_as_list


def list_as_string(option):
    """Returns the argument as a string.
    
    Useful for insuring that ConfigObj options are always returned
    as a string, despite the presence of a comma in the middle.
    
    Example:
        >>> print(list_as_string('a string'))
        a string
        >>> print(list_as_string(['a', 'string']))
        a, string
        >>> print(list_as_string('Reno, NV'))
        Reno, NV
    """
    # Check if it's already a string.
    if option is not None and not isinstance(option, str):
        return ', '.join(option)
    return option


def startOfInterval(time_ts, interval):
    """Find the start time of an interval.
    
    This algorithm assumes unit epoch time is divided up into
    intervals of 'interval' length. Given a timestamp, it
    figures out which interval it lies in, returning the start
    time.

    Args:

        time_ts (float): A timestamp. The start of the interval containing this
            timestamp will be returned.
        interval (int): An interval length in seconds.
    
    Returns:
        int: A timestamp with the start of the interval.

    Examples:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time.tzset()
    >>> start_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  300))
    'Thu Jul  4 01:55:00 2013'
    >>> time.ctime(startOfInterval(start_ts,  300.0))
    'Thu Jul  4 01:55:00 2013'
    >>> time.ctime(startOfInterval(start_ts,  600))
    'Thu Jul  4 01:50:00 2013'
    >>> time.ctime(startOfInterval(start_ts,  900))
    'Thu Jul  4 01:45:00 2013'
    >>> time.ctime(startOfInterval(start_ts, 3600))
    'Thu Jul  4 01:00:00 2013'
    >>> time.ctime(startOfInterval(start_ts, 7200))
    'Thu Jul  4 01:00:00 2013'
    >>> start_ts = time.mktime(time.strptime("2013-07-04 01:00:00", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  300))
    'Thu Jul  4 00:55:00 2013'
    >>> start_ts = time.mktime(time.strptime("2013-07-04 01:00:01", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  300))
    'Thu Jul  4 01:00:00 2013'
    >>> start_ts = time.mktime(time.strptime("2013-07-04 01:04:59", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  300))
    'Thu Jul  4 01:00:00 2013'
    >>> start_ts = time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  300))
    'Wed Jul  3 23:55:00 2013'
    >>> start_ts = time.mktime(time.strptime("2013-07-04 07:51:00", "%Y-%m-%d %H:%M:%S"))
    >>> time.ctime(startOfInterval(start_ts,  60))
    'Thu Jul  4 07:50:00 2013'
    >>> start_ts += 0.1
    >>> time.ctime(startOfInterval(start_ts,  60))
    'Thu Jul  4 07:51:00 2013'
    """

    start_interval_ts = int(time_ts / interval) * interval

    if time_ts == start_interval_ts:
        start_interval_ts -= interval
    return start_interval_ts


def _ord_to_ts(ord_date):
    """Convert from ordinal date to unix epoch time.

    Args:
        ord_date (int): A proleptic Gregorian ordinal.

    Returns:
        int: Unix epoch time of the start of the corresponding day.
    """
    d = datetime.date.fromordinal(ord_date)
    t = int(time.mktime(d.timetuple()))
    return t


# ===============================================================================
# What follows is a bunch of "time span" routines. Generally, time spans
# are used when start and stop times fall on calendar boundaries
# such as days, months, years.  So, it makes sense to talk of "daySpans",
# "weekSpans", etc. They are generally not used between two random times. 
# ===============================================================================

class TimeSpan(tuple):
    """Represents a time span, exclusive on the left, inclusive on the right."""

    def __new__(cls, *args):
        if args[0] > args[1]:
            raise ValueError("start time (%d) is greater than stop time (%d)" % (args[0], args[1]))
        return tuple.__new__(cls, args)

    @property
    def start(self):
        return self[0]

    @property
    def stop(self):
        return self[1]

    @property
    def length(self):
        return self[1] - self[0]

    def includesArchiveTime(self, timestamp):
        """Test whether the span includes a timestamp, exclusive on the left,
        inclusive on the right.

        Args:
            timestamp(float): The timestamp to be tested.

        Returns:
             bool: True if the span includes the time timestamp, otherwise False.
        
        """
        return self.start < timestamp <= self.stop

    def includes(self, span):
        return self.start <= span.start <= self.stop and self.start <= span.stop <= self.stop

    def __eq__(self, other):
        return self.start == other.start and self.stop == other.stop

    def __str__(self):
        return "[%s -> %s]" % (timestamp_to_string(self.start),
                               timestamp_to_string(self.stop))

    def __hash__(self):
        return hash(self.start) ^ hash(self.stop)


nominal_intervals = {
    'hour': 3600,
    'day': 86400,
    'week': 7 * 86400,
    'month': int(365.25 / 12 * 86400),
    'year': int(365.25 * 86400),
}
duration_synonyms = {
    'hour': '1h',
    'day': '1d',
    'week': '1w',
    'month': '1m',
    'year': '1y',
}


def nominal_spans(label):
    """Convert a (possible) string into a time. The string can include a duration suffix.

    Examples:
        >>> print(nominal_spans(7200))
        7200
        >>> print(nominal_spans(7200.0))
        7200.0
        >>> print(nominal_spans('2h'))
        7200
        >>> print(nominal_spans('120M'))
        7200
        >>> print(nominal_spans(None))
        None

    Args:
        label(str|float|int|None): A time, possibly with a duration suffix.

    Returns:
        int|float|None:
    """
    if label is None:
        return None

    if isinstance(label, str):
        label = duration_synonyms.get(label.lower(), label)
        if label.endswith('M'):
            # Minute
            return int(label[:-1]) * 60
        elif label.endswith('h'):
            # Hour
            return int(label[:-1]) * nominal_intervals['hour']
        elif label.endswith('d'):
            # Day
            return int(label[:-1]) * nominal_intervals['day']
        elif label.endswith('w'):
            # Week
            return int(label[:-1]) * nominal_intervals['week']
        elif label.endswith('m'):
            # Month
            return int(label[:-1]) * nominal_intervals['month']
        elif label.endswith('y'):
            # Year
            return int(label[:-1]) * nominal_intervals['year']
        else:
            return int(label)
    return label


def isStartOfDay(time_ts):
    """Is the indicated time at the start of the day, local time?

    This algorithm will work even in countries that switch to DST at midnight, such as Brazil.

    Args:
        time_ts (float): A unix epoch timestamp.

    Returns:
        bool: True if the timestamp is at midnight, False otherwise.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
        >>> print(isStartOfDay(time_ts))
        False
        >>> time_ts = time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))
        >>> print(isStartOfDay(time_ts))
        True
        >>> os.environ['TZ'] = 'America/Sao_Paulo'
        >>> time.tzset()
        >>> time_ts = 1541300400
        >>> print(isStartOfDay(time_ts))
        True
        >>> print(isStartOfDay(time_ts - 1))
        False
    """

    # Test the date of the time against the date a tenth of a second before.
    # If they do not match, the time must have been the start of the day
    dt1 = datetime.date.fromtimestamp(time_ts)
    dt2 = datetime.date.fromtimestamp(time_ts - .1)
    return not dt1 == dt2


def isMidnight(time_ts):
    """Is the indicated time on a midnight boundary, local time?
    NB: This algorithm does not work in countries that switch to DST
    at midnight, such as Brazil.

    Args:
        time_ts (float): A unix epoch timestamp.

    Returns:
        bool: True if the timestamp is at midnight, False otherwise.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
        >>> print(isMidnight(time_ts))
        False
        >>> time_ts = time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))
        >>> print(isMidnight(time_ts))
        True
    """

    time_tt = time.localtime(time_ts)
    return time_tt.tm_hour == 0 and time_tt.tm_min == 0 and time_tt.tm_sec == 0


def archiveSpanSpan(time_ts, time_delta=0, hour_delta=0, day_delta=0, week_delta=0, month_delta=0,
                    year_delta=0, boundary=None):
    """ Returns a TimeSpan for the last xxx seconds where xxx equals
        time_delta sec + hour_delta hours + day_delta days + week_delta weeks \
            + month_delta months + year_delta years

        NOTE: Use of month_delta and year_delta is deprecated.
        See issue #436 (https://github.com/weewx/weewx/issues/436)

    Example:
        >>> os.environ['TZ'] = 'Australia/Brisbane'
        >>> time.tzset()
        >>> time_ts = time.mktime(time.strptime("2015-07-21 09:05:35", "%Y-%m-%d %H:%M:%S"))
        >>> print(archiveSpanSpan(time_ts, time_delta=3600))
        [2015-07-21 08:05:35 AEST (1437429935) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, hour_delta=6))
        [2015-07-21 03:05:35 AEST (1437411935) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, day_delta=1))
        [2015-07-20 09:05:35 AEST (1437347135) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, time_delta=3600, day_delta=1))
        [2015-07-20 08:05:35 AEST (1437343535) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, week_delta=4))
        [2015-06-23 09:05:35 AEST (1435014335) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, month_delta=1))
        [2015-06-21 09:05:35 AEST (1434841535) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts, year_delta=1))
        [2014-07-21 09:05:35 AEST (1405897535) -> 2015-07-21 09:05:35 AEST (1437433535)]
        >>> print(archiveSpanSpan(time_ts))
        [2015-07-21 09:05:34 AEST (1437433534) -> 2015-07-21 09:05:35 AEST (1437433535)]

        Example over a DST boundary. Because Brisbane does not observe DST, we need to
        switch timezones.
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = 1457888400
        >>> print(timestamp_to_string(time_ts))
        2016-03-13 10:00:00 PDT (1457888400)
        >>> span = archiveSpanSpan(time_ts, day_delta=1)
        >>> print(span)
        [2016-03-12 10:00:00 PST (1457805600) -> 2016-03-13 10:00:00 PDT (1457888400)]

        Note that there is not 24 hours of time over this span:
        >>> print((span.stop - span.start) / 3600.0)
        23.0
    """

    if time_ts is None:
        return None

    # Use a datetime.timedelta so that it can take DST into account:
    time_dt = datetime.datetime.fromtimestamp(time_ts)
    time_dt -= datetime.timedelta(weeks=week_delta, days=day_delta, hours=hour_delta,
                                  seconds=time_delta)

    # Now add the deltas for months and years. Because these can be variable in length,
    # some special arithmetic is needed. Start by calculating the number of
    # months since 0 AD:
    total_months = 12 * time_dt.year + time_dt.month - 1 - 12 * year_delta - month_delta
    # Convert back from total months since 0 AD to year and month:
    year = total_months // 12
    month = total_months % 12 + 1
    # Apply the delta to our datetime object
    start_dt = time_dt.replace(year=year, month=month)

    # Finally, convert to unix epoch time
    if boundary is None:
        start_ts = int(time.mktime(start_dt.timetuple()))
        if start_ts == time_ts:
            start_ts -= 1
    elif boundary.lower() == 'midnight':
        start_ts = _ord_to_ts(start_dt.toordinal())
    else:
        raise ValueError("Unknown boundary %s" % boundary)

    return TimeSpan(start_ts, time_ts)


def archiveHoursAgoSpan(time_ts, hours_ago=0):
    """Returns a one-hour long TimeSpan for x hours ago that includes the given time.

    NB: A timestamp that falls exactly on the hour boundary is considered to belong to the
    *previous* hour.

    Args:
        time_ts (float|None): A timestamp. An hour long time span will be returned that encompasses
            this timestamp.
        hours_ago (int): Which hour we want. 0=this hour, 1=last hour, etc. Default is
            zero (this hour).

    Returns:
        TimeSpan: A TimeSpan object one hour long, that includes time_ts.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
        >>> print(archiveHoursAgoSpan(time_ts, hours_ago=0))
        [2013-07-04 01:00:00 PDT (1372924800) -> 2013-07-04 02:00:00 PDT (1372928400)]
        >>> print(archiveHoursAgoSpan(time_ts, hours_ago=2))
        [2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]
        >>> time_ts = time.mktime(datetime.date(2013, 7, 4).timetuple())
        >>> print(archiveHoursAgoSpan(time_ts, hours_ago=0))
        [2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]
        >>> print(archiveHoursAgoSpan(time_ts, hours_ago=24))
        [2013-07-02 23:00:00 PDT (1372831200) -> 2013-07-03 00:00:00 PDT (1372834800)]
    """
    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    # If we are exactly at an hour boundary, the start of the archive hour is actually
    # the *previous* hour.
    if time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        hours_ago += 1

    # Find the start of the hour
    start_of_hour_dt = time_dt.replace(minute=0, second=0, microsecond=0)

    start_span_dt = start_of_hour_dt - datetime.timedelta(hours=hours_ago)
    stop_span_dt = start_span_dt + datetime.timedelta(hours=1)

    return TimeSpan(int(time.mktime(start_span_dt.timetuple())),
                    int(time.mktime(stop_span_dt.timetuple())))


def daySpan(time_ts, days_ago=0, archive=False):
    """Returns a one-day long TimeSpan for x days ago that includes a given time.

    Args:
        time_ts (float|None): The day will include this timestamp.
        days_ago (int): Which day we want. 0=today, 1=yesterday, etc.
        archive (bool): True to calculate archive day; false otherwise.

    Returns:
        TimeSpan: A TimeSpan object one day long.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = time.mktime(time.strptime("2014-01-01 01:57:35", "%Y-%m-%d %H:%M:%S"))

        As for today:
        >>> print(daySpan(time_ts))
        [2014-01-01 00:00:00 PST (1388563200) -> 2014-01-02 00:00:00 PST (1388649600)]

        Do it again, but on the midnight boundary
        >>> time_ts = time.mktime(time.strptime("2014-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"))

        We should still get today (this differs from the function archiveDaySpan())
        >>> print(daySpan(time_ts))
        [2014-01-01 00:00:00 PST (1388563200) -> 2014-01-02 00:00:00 PST (1388649600)]
"""
    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    if archive:
        # If we are exactly at midnight, the start of the archive day is actually
        # the *previous* day
        if time_dt.hour == 0 \
                and time_dt.minute == 0 \
                and time_dt.second == 0 \
                and time_dt.microsecond == 0:
            days_ago += 1

    # Find the start of the day
    start_of_day_dt = time_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    start_span_dt = start_of_day_dt - datetime.timedelta(days=days_ago)
    stop_span_dt = start_span_dt + datetime.timedelta(days=1)

    return TimeSpan(int(time.mktime(start_span_dt.timetuple())),
                    int(time.mktime(stop_span_dt.timetuple())))


def archiveDaySpan(time_ts, days_ago=0):
    """Returns a one-day long TimeSpan for x days ago that includes a given time.

    NB: A timestamp that falls exactly on midnight is considered to belong to the *previous* day.

    Args:
        time_ts (float|None): The day will include this timestamp.
        days_ago (int): Which day we want. 0=today, 1=yesterday, etc.

    Returns:
        TimeSpan: A TimeSpan object one day long.

    Example, which spans the end-of-year boundary
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time.tzset()
    >>> time_ts = time.mktime(time.strptime("2014-01-01 01:57:35", "%Y-%m-%d %H:%M:%S"))
    
    As for today:
    >>> print(archiveDaySpan(time_ts))
    [2014-01-01 00:00:00 PST (1388563200) -> 2014-01-02 00:00:00 PST (1388649600)]

    Ask for yesterday:
    >>> print(archiveDaySpan(time_ts, days_ago=1))
    [2013-12-31 00:00:00 PST (1388476800) -> 2014-01-01 00:00:00 PST (1388563200)]

    Day before yesterday
    >>> print(archiveDaySpan(time_ts, days_ago=2))
    [2013-12-30 00:00:00 PST (1388390400) -> 2013-12-31 00:00:00 PST (1388476800)]

    Do it again, but on the midnight boundary
    >>> time_ts = time.mktime(time.strptime("2014-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"))

    This time, we should get the previous day
    >>> print(archiveDaySpan(time_ts))
    [2013-12-31 00:00:00 PST (1388476800) -> 2014-01-01 00:00:00 PST (1388563200)]
    """
    return daySpan(time_ts, days_ago, True)


# For backwards compatibility. Not sure if anyone is actually using this
archiveDaysAgoSpan = archiveDaySpan


def archiveWeekSpan(time_ts, startOfWeek=6, weeks_ago=0):
    """Returns a one-week long TimeSpan for x weeks ago that includes a given time.

    NB: The time at midnight at the end of the week is considered to
    actually belong in the previous week.

    Args:
        time_ts (float|None): The week will include this timestamp.
        startOfWeek (int): The start of the week (0=Monday, 1=Tues, ..., 6 = Sun). Default
            is 6 (Sunday).
        weeks_ago (int): Which week we want. 0=this week, 1=last week, etc. Default
            is zero (this week).
    
    Returns:
         TimeSpan: A TimeSpan object one week long that contains time_ts. It will
            start at midnight of the day considered the start of the week.
    
    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = 1483429962
        >>> print(timestamp_to_string(time_ts))
        2017-01-02 23:52:42 PST (1483429962)
        >>> print(archiveWeekSpan(time_ts))
        [2017-01-01 00:00:00 PST (1483257600) -> 2017-01-08 00:00:00 PST (1483862400)]
        >>> print(archiveWeekSpan(time_ts, weeks_ago=1))
        [2016-12-25 00:00:00 PST (1482652800) -> 2017-01-01 00:00:00 PST (1483257600)]
    """
    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    # Find the start of the day:
    start_of_day_dt = time_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    # Find the relative start of the week
    day_of_week = start_of_day_dt.weekday()
    delta = day_of_week - startOfWeek
    if delta < 0:
        delta += 7

    # If we are exactly at midnight, the start of the archive week is actually
    # the *previous* week
    if day_of_week == startOfWeek \
            and time_dt.hour == 0 \
            and time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        delta += 7

    # Finally, find the start of the requested week.
    delta += weeks_ago * 7

    start_of_week = start_of_day_dt - datetime.timedelta(days=delta)
    end_of_week = start_of_week + datetime.timedelta(days=7)

    return TimeSpan(int(time.mktime(start_of_week.timetuple())),
                    int(time.mktime(end_of_week.timetuple())))


def archiveMonthSpan(time_ts, months_ago=0):
    """Returns a one-month long TimeSpan for x months ago that includes a given time.

    The time at midnight at the end of the month is considered to actually belong in the
    previous week.

    Args:
         time_ts (float|None): The month will include this timestamp.
         months_ago (int): Which month we want. 0=this month, 1=last month, etc. Default
            is zero (this month).

    Returns:
          TimeSpan: A TimeSpan object one month long that contains time_ts.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = 1483429962
        >>> print(timestamp_to_string(time_ts))
        2017-01-02 23:52:42 PST (1483429962)
        >>> print(archiveMonthSpan(time_ts))
        [2017-01-01 00:00:00 PST (1483257600) -> 2017-02-01 00:00:00 PST (1485936000)]
        >>> print(archiveMonthSpan(time_ts, months_ago=1))
        [2016-12-01 00:00:00 PST (1480579200) -> 2017-01-01 00:00:00 PST (1483257600)]
    """
    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    # If we are exactly at midnight of the first day of the month,
    # the start of the archive month is actually the *previous* month
    if time_dt.day == 1 \
            and time_dt.hour == 0 \
            and time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        months_ago += 1

    # Find the start of the month
    start_of_month_dt = time_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total number of months since 0AD
    total_months = 12 * start_of_month_dt.year + start_of_month_dt.month - 1

    # Adjust for the requested delta:
    total_months -= months_ago

    # Now rebuild the date
    start_year = total_months // 12
    start_month = total_months % 12 + 1
    start_date = datetime.date(year=start_year, month=start_month, day=1)

    # Advance to the start of the next month. This will be the end of the time span.
    total_months += 1
    stop_year = total_months // 12
    stop_month = total_months % 12 + 1
    stop_date = datetime.date(year=stop_year, month=stop_month, day=1)

    return TimeSpan(int(time.mktime(start_date.timetuple())),
                    int(time.mktime(stop_date.timetuple())))


def archiveYearSpan(time_ts, years_ago=0):
    """Returns a TimeSpan representing a year that includes a given time.

    NB: Midnight of the 1st of the January is considered to actually belong in the previous year.

    Args:
        time_ts (float|None): The year will include this timestamp.
        years_ago (int): Which year we want. 0=this year, 1=last year, etc. Default
            is zero (this year).

    Returns:
        TimeSpan: A TimeSpan object one year long that contains time_ts. It will
            start at midnight of 1-Jan
    """

    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    # If we are exactly at midnight 1-Jan, then the start of the archive year is actually
    # the *previous* year
    if time_dt.month == 1 \
            and time_dt.day == 1 \
            and time_dt.hour == 0 \
            and time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        years_ago += 1

    return TimeSpan(int(time.mktime((time_dt.year - years_ago, 1, 1, 0, 0, 0, 0, 0, -1))),
                    int(time.mktime((time_dt.year - years_ago + 1, 1, 1, 0, 0, 0, 0, 0, -1))))


def archiveRainYearSpan(time_ts, sory_mon, years_ago=0):
    """Returns a TimeSpan representing a rain year that includes a given time.

    NB: Midnight of the 1st of the month starting the rain year is considered to
    actually belong in the previous rain year.

    Args:
        time_ts (float|None): The rain year will include this timestamp.
        sory_mon (int): The start of the rain year (1=Jan, 2=Feb, etc.)
        years_ago (int): Which rain year we want. 0=this year, 1=last year, etc. Default
            is zero (this year).

    Returns:
        TimeSpan: A one-year long TimeSpan object containing the timestamp.
    """
    if time_ts is None:
        return None

    time_dt = datetime.datetime.fromtimestamp(time_ts)

    # If we are exactly at midnight of the start of the rain year, then the start is actually
    # the *previous* year
    if time_dt.month == sory_mon \
            and time_dt.day == 1 \
            and time_dt.hour == 0 \
            and time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        years_ago += 1

    if time_dt.month < sory_mon:
        years_ago += 1

    year = time_dt.year - years_ago

    return TimeSpan(int(time.mktime((year, sory_mon, 1, 0, 0, 0, 0, 0, -1))),
                    int(time.mktime((year + 1, sory_mon, 1, 0, 0, 0, 0, 0, -1))))


def timespan_by_name(label, time_ts, **kwargs):
    """Calculate an an appropriate TimeSpan"""
    return {
        'hour': archiveHoursAgoSpan,
        'day': archiveDaySpan,
        'week': archiveWeekSpan,
        'month': archiveMonthSpan,
        'year': archiveYearSpan,
        'rainyear': archiveRainYearSpan
    }[label](time_ts, **kwargs)


def stampgen(startstamp, stopstamp, interval):
    """Generator function yielding a sequence of timestamps, spaced interval apart.

    The sequence will fall on the same local time boundary as startstamp.

    Args:
        startstamp (float): The start of the sequence in unix epoch time.
        stopstamp (float): The end of the sequence in unix epoch time.
        interval (int|float): The time length of an interval in seconds.

    Yields:
        float: yields a sequence of timestamps between startstamp and endstamp, inclusive.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> startstamp = 1236560400
        >>> print(timestamp_to_string(startstamp))
        2009-03-08 18:00:00 PDT (1236560400)
        >>> stopstamp = 1236607200
        >>> print(timestamp_to_string(stopstamp))
        2009-03-09 07:00:00 PDT (1236607200)

        >>> for stamp in stampgen(startstamp, stopstamp, 10800):
        ...     print(timestamp_to_string(stamp))
        2009-03-08 18:00:00 PDT (1236560400)
        2009-03-08 21:00:00 PDT (1236571200)
        2009-03-09 00:00:00 PDT (1236582000)
        2009-03-09 03:00:00 PDT (1236592800)
        2009-03-09 06:00:00 PDT (1236603600)

        Note that DST started in the middle of the sequence and that therefore the
        actual time deltas between stamps is not necessarily 3 hours.
    """
    dt = datetime.datetime.fromtimestamp(startstamp)
    stop_dt = datetime.datetime.fromtimestamp(stopstamp)
    if interval == 365.25 / 12 * 24 * 3600:
        # Interval is a nominal month. This algorithm is
        # necessary because not all months have the same length.
        while dt <= stop_dt:
            t_tuple = dt.timetuple()
            yield time.mktime(t_tuple)
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12:
                month -= 12
                year += 1
            dt = dt.replace(year=year, month=month)
    else:
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval.
        delta = datetime.timedelta(seconds=interval)
        ts_last = 0
        while dt <= stop_dt:
            ts = int(time.mktime(dt.timetuple()))
            # This check is necessary because time.mktime() cannot
            # disambiguate between 2am ST and 3am DST. For example,
            #   time.mktime((2013, 3, 10, 2, 0, 0, 0, 0, -1)) and
            #   time.mktime((2013, 3, 10, 3, 0, 0, 0, 0, -1))
            # both give the same value (1362909600)
            if ts > ts_last:
                yield ts
                ts_last = ts
            dt += delta


def intervalgen(start_ts, stop_ts, interval):
    """Generator function yielding a sequence of time spans whose boundaries
    are on constant local time.

    Args:
        start_ts (float): The start of the first interval in unix epoch time. In unix epoch time.
        stop_ts (float): The end of the last interval will be equal to or less than this.
            In unix epoch time.
        interval (int|float|str): The time length of an interval in seconds, or a shorthand
            description (such as 'day', or 'hour', or '3d').

    Yields:
         TimeSpan: A sequence of TimeSpans. Both the start and end of the timespan
            will be on the same time boundary as start_ts. See the example below.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> startstamp = 1236477600
        >>> print(timestamp_to_string(startstamp))
        2009-03-07 18:00:00 PST (1236477600)
        >>> stopstamp = 1236538800
        >>> print(timestamp_to_string(stopstamp))
        2009-03-08 12:00:00 PDT (1236538800)

        >>> for span in intervalgen(startstamp, stopstamp, 10800):
        ...     print(span)
        [2009-03-07 18:00:00 PST (1236477600) -> 2009-03-07 21:00:00 PST (1236488400)]
        [2009-03-07 21:00:00 PST (1236488400) -> 2009-03-08 00:00:00 PST (1236499200)]
        [2009-03-08 00:00:00 PST (1236499200) -> 2009-03-08 03:00:00 PDT (1236506400)]
        [2009-03-08 03:00:00 PDT (1236506400) -> 2009-03-08 06:00:00 PDT (1236517200)]
        [2009-03-08 06:00:00 PDT (1236517200) -> 2009-03-08 09:00:00 PDT (1236528000)]
        [2009-03-08 09:00:00 PDT (1236528000) -> 2009-03-08 12:00:00 PDT (1236538800)]

        (Note how in this example the local time boundaries are constant, despite
        DST kicking in. The interval length is not constant.)

        Another example, this one over the Fall DST boundary, and using 1-hour intervals:

        >>> startstamp = 1257051600
        >>> print(timestamp_to_string(startstamp))
        2009-10-31 22:00:00 PDT (1257051600)
        >>> stopstamp = 1257080400
        >>> print(timestamp_to_string(stopstamp))
        2009-11-01 05:00:00 PST (1257080400)
        >>> for span in intervalgen(startstamp, stopstamp, 3600):
        ...    print(span)
        [2009-10-31 22:00:00 PDT (1257051600) -> 2009-10-31 23:00:00 PDT (1257055200)]
        [2009-10-31 23:00:00 PDT (1257055200) -> 2009-11-01 00:00:00 PDT (1257058800)]
        [2009-11-01 00:00:00 PDT (1257058800) -> 2009-11-01 01:00:00 PDT (1257062400)]
        [2009-11-01 01:00:00 PDT (1257062400) -> 2009-11-01 02:00:00 PST (1257069600)]
        [2009-11-01 02:00:00 PST (1257069600) -> 2009-11-01 03:00:00 PST (1257073200)]
        [2009-11-01 03:00:00 PST (1257073200) -> 2009-11-01 04:00:00 PST (1257076800)]
        [2009-11-01 04:00:00 PST (1257076800) -> 2009-11-01 05:00:00 PST (1257080400)]
"""

    dt1 = datetime.datetime.fromtimestamp(start_ts)
    stop_dt = datetime.datetime.fromtimestamp(stop_ts)

    # If a string was passed in, convert to seconds using nominal time intervals.
    interval = nominal_spans(interval)

    if interval == 365.25 / 12 * 24 * 3600:
        # Interval is a nominal month. This algorithm is
        # necessary because not all months have the same length.
        while dt1 < stop_dt:
            t_tuple = dt1.timetuple()
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12:
                month -= 12
                year += 1
            dt2 = min(dt1.replace(year=year, month=month), stop_dt)
            stamp1 = time.mktime(t_tuple)
            stamp2 = time.mktime(dt2.timetuple())
            yield TimeSpan(stamp1, stamp2)
            dt1 = dt2
    else:
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        last_stamp1 = 0
        while dt1 < stop_dt:
            dt2 = min(dt1 + delta, stop_dt)
            stamp1 = int(time.mktime(dt1.timetuple()))
            stamp2 = int(time.mktime(dt2.timetuple()))
            if stamp2 > stamp1 > last_stamp1:
                yield TimeSpan(stamp1, stamp2)
                last_stamp1 = stamp1
            dt1 = dt2


def genHourSpans(start_ts, stop_ts):
    """Generator function that generates start/stop of hours in an inclusive range.

    Args:
        start_ts (float): A time stamp somewhere in the first day.
        stop_ts (float): A time stamp somewhere in the last day.

    Yields:
        TimeSpan: Instance of TimeSpan, where the start is the time stamp
            of the start of the day, the stop is the time stamp of the start
            of the next day.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> start_ts = 1204796460
        >>> stop_ts  = 1204818360

        >>> print(timestamp_to_string(start_ts))
        2008-03-06 01:41:00 PST (1204796460)
        >>> print(timestamp_to_string(stop_ts))
        2008-03-06 07:46:00 PST (1204818360)

        >>> for span in genHourSpans(start_ts, stop_ts):
        ...   print(span)
        [2008-03-06 01:00:00 PST (1204794000) -> 2008-03-06 02:00:00 PST (1204797600)]
        [2008-03-06 02:00:00 PST (1204797600) -> 2008-03-06 03:00:00 PST (1204801200)]
        [2008-03-06 03:00:00 PST (1204801200) -> 2008-03-06 04:00:00 PST (1204804800)]
        [2008-03-06 04:00:00 PST (1204804800) -> 2008-03-06 05:00:00 PST (1204808400)]
        [2008-03-06 05:00:00 PST (1204808400) -> 2008-03-06 06:00:00 PST (1204812000)]
        [2008-03-06 06:00:00 PST (1204812000) -> 2008-03-06 07:00:00 PST (1204815600)]
        [2008-03-06 07:00:00 PST (1204815600) -> 2008-03-06 08:00:00 PST (1204819200)]
    """
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    _start_hour = int(start_ts / 3600)
    _stop_hour = int(stop_ts / 3600)
    if (_stop_dt.minute, _stop_dt.second) == (0, 0):
        _stop_hour -= 1

    for _hour in range(_start_hour, _stop_hour + 1):
        yield TimeSpan(_hour * 3600, (_hour + 1) * 3600)


def genDaySpans(start_ts, stop_ts):
    """Generator function that generates start/stop of days in an inclusive range.

    Args:

        start_ts (float): A time stamp somewhere in the first day.
        stop_ts (float): A time stamp somewhere in the last day.

    Yields:
        TimeSpan: A sequence of TimeSpans, where the start is the time stamp
            of the start of the day, the stop is the time stamp of the start
            of the next day.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> start_ts = 1204796460
        >>> stop_ts  = 1205265720

        >>> print(timestamp_to_string(start_ts))
        2008-03-06 01:41:00 PST (1204796460)
        >>> print(timestamp_to_string(stop_ts))
        2008-03-11 13:02:00 PDT (1205265720)

        >>> for span in genDaySpans(start_ts, stop_ts):
        ...   print(span)
        [2008-03-06 00:00:00 PST (1204790400) -> 2008-03-07 00:00:00 PST (1204876800)]
        [2008-03-07 00:00:00 PST (1204876800) -> 2008-03-08 00:00:00 PST (1204963200)]
        [2008-03-08 00:00:00 PST (1204963200) -> 2008-03-09 00:00:00 PST (1205049600)]
        [2008-03-09 00:00:00 PST (1205049600) -> 2008-03-10 00:00:00 PDT (1205132400)]
        [2008-03-10 00:00:00 PDT (1205132400) -> 2008-03-11 00:00:00 PDT (1205218800)]
        [2008-03-11 00:00:00 PDT (1205218800) -> 2008-03-12 00:00:00 PDT (1205305200)]

        Note that a daylight savings time change happened 8 March 2009.
    """
    _start_dt = datetime.datetime.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)

    _start_ord = _start_dt.toordinal()
    _stop_ord = _stop_dt.toordinal()
    if (_stop_dt.hour, _stop_dt.minute, _stop_dt.second) == (0, 0, 0):
        _stop_ord -= 1

    for _ord in range(_start_ord, _stop_ord + 1):
        yield TimeSpan(_ord_to_ts(_ord), _ord_to_ts(_ord + 1))


def genMonthSpans(start_ts, stop_ts):
    """Generator function that generates start/stop of months in an
    inclusive range.
    
    Args:
        start_ts (float): A time stamp somewhere in the first month.
        stop_ts (float): A time stamp somewhere in the last month.

    Yields:
        TimeSpan: A sequence of TimeSpans, where the start is the time stamp of the start of the
            month, the stop is the time stamp of the start of the next month.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> start_ts = 1196705700
        >>> stop_ts  = 1206101100
        >>> print("start time is %s" % timestamp_to_string(start_ts))
        start time is 2007-12-03 10:15:00 PST (1196705700)
        >>> print("stop time is  %s" % timestamp_to_string(stop_ts))
        stop time is  2008-03-21 05:05:00 PDT (1206101100)

        >>> for span in genMonthSpans(start_ts, stop_ts):
        ...   print(span)
        [2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]
        [2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]
        [2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]
        [2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]

        Note that a daylight savings time change happened 8 March 2009.
    """
    if None in (start_ts, stop_ts):
        return
    _start_dt = datetime.date.fromtimestamp(start_ts)
    _stop_date = datetime.datetime.fromtimestamp(stop_ts)

    _start_month = 12 * _start_dt.year + _start_dt.month
    _stop_month = 12 * _stop_date.year + _stop_date.month

    if (_stop_date.day, _stop_date.hour, _stop_date.minute, _stop_date.second) == (1, 0, 0, 0):
        _stop_month -= 1

    for month in range(_start_month, _stop_month + 1):
        _this_yr, _this_mo = divmod(month, 12)
        _next_yr, _next_mo = divmod(month + 1, 12)
        yield TimeSpan(int(time.mktime((_this_yr, _this_mo, 1, 0, 0, 0, 0, 0, -1))),
                       int(time.mktime((_next_yr, _next_mo, 1, 0, 0, 0, 0, 0, -1))))


def genYearSpans(start_ts, stop_ts):
    if None in (start_ts, stop_ts):
        return
    _start_date = datetime.date.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)

    _start_year = _start_date.year
    _stop_year = _stop_dt.year

    if (_stop_dt.month, _stop_dt.day, _stop_dt.hour,
        _stop_dt.minute, _stop_dt.second) == (1, 1, 0, 0, 0):
        _stop_year -= 1

    for year in range(_start_year, _stop_year + 1):
        yield TimeSpan(int(time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1))),
                       int(time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1))))


def startOfDay(time_ts):
    """Calculate the unix epoch time for the start of a (local time) day.
    
    Args:
        time_ts (float): A timestamp somewhere in the day for which the start-of-day is desired.
    
    Returns:
         float: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_tt = time.localtime(time_ts)
    _bod_ts = time.mktime((_time_tt.tm_year,
                           _time_tt.tm_mon,
                           _time_tt.tm_mday,
                           0, 0, 0, 0, 0, -1))
    return int(_bod_ts)


def startOfGregorianDay(date_greg):
    """Given a Gregorian day, returns the start of the day in unix epoch time.

    Args:
        date_greg (int): A date as an ordinal Gregorian day.
    
    Returns:
         float: The local start of the day as a unix epoch time.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> date_greg = 735973  # 10-Jan-2016
        >>> print(startOfGregorianDay(date_greg))
        1452412800.0
    """
    date_dt = datetime.datetime.fromordinal(date_greg)
    date_tt = date_dt.timetuple()
    sod_ts = time.mktime(date_tt)
    return sod_ts


def toGregorianDay(time_ts):
    """Return the Gregorian day a timestamp belongs to.

    Args:
        time_ts (float): A time in unix epoch time.
    
    Returns:
         int: The ordinal Gregorian day that contains that time
    
    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = 1452412800  # Midnight, 10-Jan-2016
        >>> print(toGregorianDay(time_ts))
        735972
        >>> time_ts = 1452412801  # Just after midnight, 10-Jan-2016
        >>> print(toGregorianDay(time_ts))
        735973
    """

    date_dt = datetime.datetime.fromtimestamp(time_ts)
    date_greg = date_dt.toordinal()
    if date_dt.hour == date_dt.minute == date_dt.second == date_dt.microsecond == 0:
        # Midnight actually belongs to the previous day
        date_greg -= 1
    return date_greg


def startOfDayUTC(time_ts):
    """Calculate the unix epoch time for the start of a UTC day.

    Args:
        time_ts (float): A timestamp somewhere in the day for which the start-of-day
            is desired.
    
    Returns:
         int: The timestamp for the start-of-day (00:00) in unix epoch time.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> time_ts = 1452412800  # Midnight, 10-Jan-2016
        >>> print(startOfDayUTC(time_ts))
        1452384000
    """
    _time_tt = time.gmtime(time_ts)
    _bod_ts = calendar.timegm((_time_tt.tm_year,
                               _time_tt.tm_mon,
                               _time_tt.tm_mday,
                               0, 0, 0, 0, 0, -1))
    return _bod_ts


def startOfArchiveDay(time_ts):
    """Given an archive time stamp, calculate its start of day.
    
    Similar to startOfDay(), except that an archive stamped at midnight
    actually belongs to the *previous* day.

    Args:
        time_ts (float): A timestamp somewhere in the day for which the start-of-day
            is desired.
    
    Returns:
         float: The timestamp for the start-of-day (00:00) in unix epoch time."""

    time_dt = datetime.datetime.fromtimestamp(time_ts)
    start_of_day_dt = time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    # If we are exactly on the midnight boundary, the start of the archive day is actually
    # the *previous* day.
    if time_dt.hour == 0 \
            and time_dt.minute == 0 \
            and time_dt.second == 0 \
            and time_dt.microsecond == 0:
        start_of_day_dt -= datetime.timedelta(days=1)
    start_of_day_tt = start_of_day_dt.timetuple()
    start_of_day_ts = int(time.mktime(start_of_day_tt))
    return start_of_day_ts


def getDayNightTransitions(start_ts, end_ts, lat, lon):
    """Return the day-night transitions between the start and end times.

    Args:

        start_ts (float): A timestamp (UTC) indicating the beginning of the period
        end_ts (float): A timestamp (UTC) indicating the end of the period
        lat (float): The latitude in degrees
        lon (float): The longitude in degrees

    Returns:
        tuple[str,list[float]]: A two-way tuple, The first element is either the string 'day' 
            or 'night'.
            If 'day', the first transition is from day to night.
            If 'night', the first transition is from night to day.
            The second element is a sequence of transition times in unix epoch times.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> startstamp = 1658428400
        >>> # Stop stamp is three days later:
        >>> stopstamp = startstamp + 3 * 24 * 3600
        >>> print(timestamp_to_string(startstamp))
        2022-07-21 11:33:20 PDT (1658428400)
        >>> print(timestamp_to_string(stopstamp))
        2022-07-24 11:33:20 PDT (1658687600)
        >>> whichway, transitions = getDayNightTransitions(startstamp, stopstamp, 45, -122)
        >>> print(whichway)
        day
        >>> for x in transitions:
        ...     print(timestamp_to_string(x))
        2022-07-21 20:47:00 PDT (1658461620)
        2022-07-22 05:42:58 PDT (1658493778)
        2022-07-22 20:46:02 PDT (1658547962)
        2022-07-23 05:44:00 PDT (1658580240)
        2022-07-23 20:45:03 PDT (1658634303)
        2022-07-24 05:45:04 PDT (1658666704)
    """
    from weeutil import Sun

    start_ts = int(start_ts)
    end_ts = int(end_ts)

    first = None
    values = []
    for t in range(start_ts - 3600 * 24, end_ts + 3600 * 24 + 1, 3600 * 24):
        x = startOfDayUTC(t)
        x_tt = time.gmtime(x)
        y, m, d = x_tt[:3]
        (sunrise_utc, sunset_utc) = Sun.sunRiseSet(y, m, d, lon, lat)
        daystart_ts = calendar.timegm((y, m, d, 0, 0, 0, 0, 0, -1))
        sunrise_ts = int(daystart_ts + sunrise_utc * 3600.0 + 0.5)
        sunset_ts = int(daystart_ts + sunset_utc * 3600.0 + 0.5)

        if start_ts < sunrise_ts < end_ts:
            values.append(sunrise_ts)
            if first is None:
                first = 'night'
        if start_ts < sunset_ts < end_ts:
            values.append(sunset_ts)
            if first is None:
                first = 'day'
    return first, values


def timestamp_to_string(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    """Return a string formatted from the timestamp

    Args:
        ts (float): A unix-epoch timestamp
        format_str(str): A format string

    Returns:
        str: The time in local time as a string.
    
    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> print(timestamp_to_string(1196705700))
        2007-12-03 10:15:00 PST (1196705700)
        >>> print(timestamp_to_string(None))
        ******* N/A *******     (    N/A   )
    """
    if ts is not None:
        return "%s (%d)" % (time.strftime(format_str, time.localtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"


def timestamp_to_gmtime(ts):
    """Return a string formatted for GMT

    Args:
        ts (float): A unix-epoch timestamp

    Returns:
        str: The time in UTC as a string

    Example:
        >>> print(timestamp_to_gmtime(1196705700))
        2007-12-03 18:15:00 UTC (1196705700)
        >>> print(timestamp_to_gmtime(None))
        ******* N/A *******     (    N/A   )
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"


def utc_to_ts(y, m, d, hrs_utc):
    """Converts from a tuple-time in UTC to unix epoch time.

    Args:
        y (int): The year for which the conversion is desired.
        m (int): The month.
        d (int): The day.
        hrs_utc (float): Floating point number with the number of hours since midnight in UTC.
    
    Returns:
        float: The corresponding unix epoch time.

    Example:
        >>> print(utc_to_ts(2009, 3, 27, 14.5))
        1238164200.5
    """
    # Construct a time tuple with the time at midnight, UTC:
    daystart_utc_tt = (y, m, d, 0, 0, 0, 0, 0, -1)
    # Convert the time tuple to a time stamp and add on the number of seconds since midnight:
    time_ts = calendar.timegm(daystart_utc_tt) + hrs_utc * 3600.0 + 0.5
    return time_ts


def utc_to_local_tt(y, m, d, hrs_utc):
    """Converts from a UTC time to a local time.
    
    Args:
        y (int): The year for which the conversion is desired.
        m (int): The month.
        d (int): The day.
        hrs_utc (float): Floating point number with the number of hours since midnight in UTC.

    Returns:
         time.struct_time: A timetuple with the local time.

    Example:
        >>> os.environ['TZ'] = 'America/Los_Angeles'
        >>> time.tzset()
        >>> tt=utc_to_local_tt(2009, 3, 27, 14.5)
        >>> print(tt.tm_year, tt.tm_mon, tt.tm_mday, tt.tm_hour, tt.tm_min)
        2009 3 27 7 30
    """
    # Get the UTC time:
    time_ts = utc_to_ts(y, m, d, hrs_utc)
    # Convert to local time:
    time_local_tt = time.localtime(time_ts)
    return time_local_tt


def latlon_string(ll, hemi, which, format_list=None):
    """Decimal degrees into a string for degrees, and one for minutes.

    Args:
        ll (float): The decimal latitude or longitude
        hemi (list[str,str]|tuple[str,str]): A tuple holding strings representing positive or
            negative values. E.g.: ('N', 'S') or ('E', 'W')
        which (str): 'lat' for latitude, 'lon' for longitude
        format_list (list[str,str,str]|None): A list or tuple holding the format strings to be
            used. These are [whole degrees latitude, whole degrees longitude, minutes]

    Returns:
        tuple[str,str,str]: A 3-way tuple holding (latlon whole degrees, latlon minutes,
            hemisphere designator). Example: ('022', '08.3', 'N')

    Example:
        >>> print(latlon_string(-22.3, ('N','S'), 'lat'))
        ('22', '18.00', 'S')
        >>> print(latlon_string(-95.5, ('E','W'), 'lon'))
        ('095', '30.00', 'W')
    """
    labs = abs(ll)
    frac, deg = math.modf(labs)
    minutes = frac * 60.0
    format_list = format_list or ["%02d", "%03d", "%05.2f"]
    return ((format_list[0] if which == 'lat' else format_list[1]) % deg,
            format_list[2] % minutes,
            hemi[0] if ll >= 0 else hemi[1])


def get_object(module_class):
    """Given a string with a module class name, it imports and returns the class."""
    # Split the path into its parts
    module_name, klass_name = module_class.rsplit('.', 1)
    module = importlib.import_module(module_name)
    klass = getattr(module, klass_name)
    return klass


# For backwards compatibility:
_get_object = get_object


class GenWithPeek(object):
    """Generator object which allows a peek at the next object to be returned.
    
    Sometimes Python solves a complicated problem with such elegance! This is
    one of them.
    
    Example of usage:
    >>> # Define a generator function:
    >>> def genfunc(N):
    ...     for j in range(N):
    ...        yield j
    >>>
    >>> # Now wrap it with the GenWithPeek object:
    >>> g_with_peek = GenWithPeek(genfunc(5))
    >>> # We can iterate through the object as normal:
    >>> for i in g_with_peek:
    ...    print(i)
    ...    # Every second object, let's take a peek ahead
    ...    if i%2:
    ...        # We can get a peek at the next object without disturbing the wrapped generator:
    ...        print("peeking ahead, the next object will be: %s" % g_with_peek.peek())
    0
    1
    peeking ahead, the next object will be: 2
    2
    3
    peeking ahead, the next object will be: 4
    4
    """

    def __init__(self, generator):
        """Initialize the generator object.
        
        generator: A generator object to be wrapped
        """
        self.generator = generator
        self.have_peek = False
        self.peek_obj = None

    def __iter__(self):
        return self

    def __next__(self):
        """Advance to the next object"""
        if self.have_peek:
            self.have_peek = False
            return self.peek_obj
        else:
            return next(self.generator)

    def peek(self):
        """Take a peek at the next object"""
        if not self.have_peek:
            self.peek_obj = next(self.generator)
            self.have_peek = True
        return self.peek_obj


class GenByBatch(object):
    """Generator wrapper. Calls the wrapped generator in batches of a specified size."""

    def __init__(self, generator, batch_size=0):
        """Initialize an instance of GenWithConvert

        Args:
            generator: An iterator which will be wrapped.
            batch_size (int): The number of items to fetch in a batch.
        """
        self.generator = generator
        self.batch_size = batch_size
        self.batch_buffer = []

    def __iter__(self):
        return self

    def __next__(self):
        # If there isn't anything in the buffer, fetch new items
        if not self.batch_buffer:
            # Fetch in batches of 'batch_size'.
            count = 0
            for item in self.generator:
                self.batch_buffer.append(item)
                count += 1
                # If batch_size is zero, that means fetch everything in one big batch, so keep
                # going. Otherwise, break when we have fetched 'batch_size' items.
                if self.batch_size and count >= self.batch_size:
                    break
        # If there's still nothing in the buffer, we're done. Stop the iteration. Otherwise,
        # return the first item in the buffer.
        if self.batch_buffer:
            return self.batch_buffer.pop(0)
        else:
            raise StopIteration


def tobool(x):
    """Convert an object to boolean.
    
    Examples:
    >>> print(tobool('TRUE'))
    True
    >>> print(tobool(True))
    True
    >>> print(tobool(1))
    True
    >>> print(tobool('FALSE'))
    False
    >>> print(tobool(False))
    False
    >>> print(tobool(0))
    False
    >>> print(tobool('Foo'))
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'Foo'.
    >>> print(tobool(None))
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'None'.
    """

    try:
        if x.lower() in ('true', 'yes', 'y'):
            return True
        elif x.lower() in ('false', 'no', 'n'):
            return False
    except AttributeError:
        pass
    try:
        return bool(int(x))
    except (ValueError, TypeError):
        pass
    raise ValueError("Unknown boolean specifier: '%s'." % x)


to_bool = tobool


def to_int(x):
    """Convert an object to an integer, unless it is None
    
    Examples:
    >>> print(to_int(123))
    123
    >>> print(to_int('123'))
    123
    >>> print(to_int(-5.2))
    -5
    >>> print(to_int(None))
    None
    """
    if isinstance(x, str) and (x.lower() == 'none' or x == ''):
        x = None
    try:
        return int(x) if x is not None else None
    except ValueError:
        # Perhaps it's a string, holding a floating point number?
        return int(float(x))


def to_float(x):
    """Convert an object to a float, unless it is None
    
    Examples:
    >>> print(to_float(12.3))
    12.3
    >>> print(to_float('12.3'))
    12.3
    >>> print(to_float(None))
    None
    """
    if isinstance(x, str) and x.lower() == 'none':
        x = None
    return float(x) if x is not None else None


def to_complex(magnitude, direction):
    """Convert from magnitude and direction to a complex number."""
    if magnitude is None:
        value = None
    elif magnitude == 0:
        # If magnitude is zero, it doesn't matter what direction is. Can even be None.
        value = complex(0.0, 0.0)
    elif direction is None:
        # Magnitude must be non-zero, but we don't know the direction.
        value = None
    else:
        # Magnitude is non-zero, and we have a good direction.
        x = magnitude * math.cos(math.radians(90.0 - direction))
        y = magnitude * math.sin(math.radians(90.0 - direction))
        value = complex(x, y)
    return value


def dirN(c):
    """Given a complex number, return its phase as a compass heading"""
    if c is None:
        value = None
    else:
        value = (450 - math.degrees(cmath.phase(c))) % 360.0
    return value


class Polar(object):
    """Polar notation, except the direction is a compass heading."""

    def __init__(self, mag, direction):
        self.mag = mag
        self.dir = direction

    @classmethod
    def from_complex(cls, c):
        return cls(abs(c), dirN(c))

    def __str__(self):
        return "(%s, %s)" % (self.mag, self.dir)

    def __eq__(self, other):
        return self.mag == other.mag and self.dir == other.dir


def rounder(x, ndigits):
    """Round a number, or sequence of numbers, to a specified number of decimal digits

    Args:
        x (None, float, complex, list): The number or sequence of numbers to be rounded. If the
            argument is None, then None will be returned.
        ndigits (int|None): The number of decimal digits to retain. Set to None to retain them all

    Returns:
        None, float, complex, list: Returns the number, or sequence of numbers, with the requested
            number of decimal digits. If 'None', no rounding is done, and the function returns
            the original value.
    """
    if ndigits is None:
        return x
    elif x is None:
        return None
    elif isinstance(x, complex):
        return complex(round(x.real, ndigits), round(x.imag, ndigits))
    elif isinstance(x, Polar):
        return Polar(round(x.mag, ndigits), round(x.dir, ndigits))
    elif isinstance(x, float):
        return round(x, ndigits) if ndigits else int(x)
    elif is_iterable(x):
        return [rounder(v, ndigits) for v in x]
    return x


def min_with_none(x_seq):
    """Find the minimum in a (possibly empty) sequence, ignoring Nones"""
    xmin = None
    for x in x_seq:
        if xmin is None:
            xmin = x
        elif x is not None:
            xmin = min(x, xmin)
    return xmin


def max_with_none(x_seq):
    """Find the maximum in a (possibly empty) sequence, ignoring Nones.

    While this function is not necessary under Python 2, under Python 3 it is.
    """
    xmax = None
    for x in x_seq:
        if xmax is None:
            xmax = x
        elif x is not None:
            xmax = max(x, xmax)
    return xmax


def move_with_timestamp(path):
    """Save a file or directory to a path with a timestamp."""
    # Sometimes the target has a trailing '/'. This will take care of it:
    path = os.path.normpath(path)
    newpath = path + time.strftime(".%Y%m%d%H%M%S")
    # Check to see if this name already exists
    if os.path.exists(newpath):
        # It already exists. Stick a version number on it:
        version = 1
        while os.path.exists(newpath + '-' + str(version)):
            version += 1
        newpath = newpath + '-' + str(version)
    shutil.move(path, newpath)
    return newpath


class ListOfDicts(ChainMap):
    def extend(self, m):
        self.maps.append(m)

    def prepend(self, m):
        self.maps.insert(0, m)


class KeyDict(dict):
    """A dictionary that returns the key for an unsuccessful lookup."""

    def __missing__(self, key):
        return key


def atoi(text):
    return int(text) if text.isdigit() else text


def natural_keys(text):
    """Natural key sort.

    Allows use of key=natural_keys to sort a list in human order, eg:
        alist.sort(key=natural_keys)

    Ref: https://nedbatchelder.com/blog/200712/human_sorting.html
    """

    return [atoi(c) for c in re.split(natural_keys.compiled_re, text.lower())]


natural_keys.compiled_re = re.compile(r'(\d+)')


def natural_sort_keys(source_dict):
    """Return a naturally sorted list of keys for a dict."""

    # create a list of keys in the dict
    keys_list = list(source_dict.keys())
    # naturally sort the list of keys such that, for example, xxxxx16 appears
    # after xxxxx1
    keys_list.sort(key=natural_keys)
    # return the sorted list
    return keys_list


def to_sorted_string(rec, simple_sort=False):
    """Return a string representation of a dict sorted by key.

    Default action is to perform a 'natural' sort by key, ie 'xxx1' appears
    before 'xxx16'. If called with simple_sort=True a simple alphanumeric sort
    is performed instead which will result in 'xxx16' appearing before 'xxx1'.
    """

    if simple_sort:
        import locale
        return ", ".join(["%s: %s" % (k, rec.get(k)) for k in sorted(rec, key=locale.strxfrm)])
    else:
        # first obtain a list of key:value pairs sorted naturally by key
        sorted_dict = ["'%s': '%s'" % (k, rec[k]) for k in natural_sort_keys(rec)]
        # return as a string of comma separated key:value pairs in braces
        return ", ".join(sorted_dict)


def y_or_n(msg, noprompt=False, default=None):
    """Prompt and look for a 'y' or 'n' response

    Args:
        msg(str): A prompting message
        noprompt(bool): If truthy, don't prompt the user. Just do it.
        default(str|None): Value to be returned if no prompting has been requested
    Returns:
        str: Either 'y', or 'n'.
    """

    # If noprompt is truthy, return the default
    if noprompt:
        return 'y' if default is None else default

    while True:
        ans = input(msg).strip().lower()
        if not ans and default is not None:
            return default
        elif ans in ('y', 'n'):
            return ans


def deep_copy_path(path, dest_dir):
    """Copy a path to a destination, making any subdirectories along the way.
    The source path is relative to the current directory.

    Returns the number of files copied
    """

    ncopy = 0
    # Are we copying a directory?
    if os.path.isdir(path):
        # Yes. Walk it
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                # For each source file found, call myself recursively:
                ncopy += deep_copy_path(os.path.join(dirpath, f), dest_dir)
    else:
        # path is a file. Get the directory it's in.
        d = os.path.dirname(os.path.join(dest_dir, path))
        # Make the destination directory:
        os.makedirs(d, exist_ok=True)
        # This version of copy does not copy over modification time,
        # so it will look like a new file, causing it to be (for
        # example) ftp'd to the server:
        shutil.copy(path, d)
        ncopy += 1
    return ncopy


def is_iterable(x):
    """Test if something is iterable, but not a string"""
    return hasattr(x, '__iter__') and not isinstance(x, (bytes, str))


class bcolors:
    """Colors used for terminals"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def version_compare(v1, v2):
    """Compare two version numbers

    Args:
        v1(str): The first version number as a string. Can be something like '4.5.1a1'
        v2(str): The second version number as a string.

    Returns:
        int: Returns +1 if v1 is greater than v2, -1 if less than, 0 if they are the same.
    """

    import itertools

    mash = itertools.zip_longest(v1.split('.'), v2.split('.'), fillvalue='0')

    for x1, x2 in mash:
        if x1 > x2:
            return 1
        if x1 < x2:
            return -1
    return 0


def get_resource_path(package, resource):
    """Return a path to a resource within a package. The resource can be a directory or a file."""
    import sys

    if sys.version_info.major == 3 and sys.version_info.minor < 9:
        # For earlier Python versions, use the deprecated function path()
        return importlib_resources.path(package, resource)
    else:
        # For later versions...
        return importlib_resources.as_file(importlib_resources.files(package).joinpath(resource))


def get_resource_fd(package, resource):
    """Return a file descriptor to a resource within a package."""
    import sys

    if sys.version_info.major == 3 and sys.version_info.minor < 9:
        # For earlier Python versions, use the deprecated function open_text
        return importlib_resources.open_text(package, resource)
    else:
        # For later versions...
        return importlib_resources.files(package).joinpath(resource).open('r')


if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
