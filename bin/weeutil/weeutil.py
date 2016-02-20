# This Python file uses the following encoding: utf-8
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Various handy utilities that don't belong anywhere else."""

from __future__ import with_statement

import StringIO
import calendar
import datetime
import math
import os
import shutil
import syslog
import time
import traceback

import Sun

def convertToFloat(seq):
    """Convert a sequence with strings to floats, honoring 'Nones'"""
    
    if seq is None: return None
    res = [None if s in ('None', 'none') else float(s) for s in seq]
    return res

def search_up(d, k, *default):
    """Search a ConfigObj dictionary for a key. If it's not found, try my parent, and so on
    to the root.
    
    d: An instance of configobj.Section
    
    k: A key to be searched for. If not found in d, it's parent will be searched
    
    default: If the key is not found, then the default is returned. If no default is given,
    then an AttributeError exception is raised.
    
    Example: 
    
    >>> import configobj
    >>> c = configobj.ConfigObj({"color":"blue", "size":10, "dayimage":{"color":"red"}});
    >>> print search_up(c['dayimage'], 'size')
    10
    >>> print search_up(c, 'color')
    blue
    >>> print search_up(c['dayimage'], 'color')
    red
    >>> print search_up(c['dayimage'], 'flavor', 'salty')
    salty
    >>> print search_up(c['dayimage'], 'flavor')
    Traceback (most recent call last):
    AttributeError: flavor
    """
    if k in d:
        return d[k]
    if d.parent is d:
        if len(default):
            return default[0]
        else:
            raise AttributeError(k)
    else:
        return search_up(d.parent, k, *default)
    
def accumulateLeaves(d, max_level=99):
    """Merges leaf options above a ConfigObj section with itself, accumulating the results.
    
    This routine is useful for specifying defaults near the root node, 
    then having them overridden in the leaf nodes of a ConfigObj.
    
    d: instance of a configobj.Section (i.e., a section of a ConfigObj)
    
    Returns: a dictionary with all the accumulated scalars, up to max_level deep, 
    going upwards
    
    Example: Supply a default color=blue, size=10. The section "dayimage" overrides the former:
    
    >>> import configobj
    >>> c = configobj.ConfigObj({"color":"blue", "size":10, "dayimage":{"color":"red", "position":{"x":20, "y":30}}});
    >>> print accumulateLeaves(c["dayimage"])
    {'color': 'red', 'size': 10}
    >>> print accumulateLeaves(c["dayimage"], max_level=0)
    {'color': 'red'}
    >>> print accumulateLeaves(c["dayimage"]["position"])
    {'color': 'red', 'size': 10, 'y': 30, 'x': 20}
    >>> print accumulateLeaves(c["dayimage"]["position"], max_level=1)
    {'color': 'red', 'y': 30, 'x': 20}
    """
    
    import configobj

    # Use recursion. If I am the root object, then there is nothing above 
    # me to accumulate. Start with a virgin ConfigObj
    if d.parent is d :
        cum_dict = configobj.ConfigObj()
    else:
        if max_level:
            # Otherwise, recursively accumulate scalars above me
            cum_dict = accumulateLeaves(d.parent, max_level-1)
        else:
            cum_dict = configobj.ConfigObj()
        
    # Now merge my scalars into the results:
    merge_dict = {}
    for k in d.scalars :
        merge_dict[k] = d[k]
    cum_dict.merge(merge_dict)
    return cum_dict

def conditional_merge(a_dict, b_dict):
    """Merge fields from b_dict into a_dict, but only if they do not yet
    exist in a_dict"""
    # Go through each key in b_dict
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if not k in a_dict:
                # It's a new section. Initialize it...
                a_dict[k] = {}
                # ... and transfer over the section comments, if available
                try:
                    a_dict.comments[k] = b_dict.comments[k]
                except AttributeError:
                    pass
            conditional_merge(a_dict[k], b_dict[k])
        elif not k in a_dict:
            # It's a scalar. Transfer over the value...
            a_dict[k] = b_dict[k]
            # ... then its comments, if available:
            try:
                a_dict.comments[k] = b_dict.comments[k]
            except AttributeError:
                pass

def option_as_list(option):
    if option is None: return None
    if hasattr(option, '__iter__'):
        return option
    return [option]

def list_as_string(option):
    """Returns the argument as a string.
    
    Useful for insuring that ConfigObj options are always returned
    as a string, despite the presence of a comma in the middle.
    
    Example:
    >>> print list_as_string('a string')
    a string
    >>> print list_as_string(['a', 'string'])
    a, string
    >>> print list_as_string('Reno, NV')
    Reno, NV
    """
    if option is not None and hasattr(option, '__iter__'):
        return ', '.join(option)
    return option

def stampgen(startstamp, stopstamp, interval):
    """Generator function yielding a sequence of timestamps, spaced interval apart.
    
    The sequence will fall on the same local time boundary as startstamp. 

    Example:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> startstamp = 1236560400
    >>> print timestamp_to_string(startstamp)
    2009-03-08 18:00:00 PDT (1236560400)
    >>> stopstamp = 1236607200
    >>> print timestamp_to_string(stopstamp)
    2009-03-09 07:00:00 PDT (1236607200)
    
    >>> for stamp in stampgen(startstamp, stopstamp, 10800):
    ...     print timestamp_to_string(stamp)
    2009-03-08 18:00:00 PDT (1236560400)
    2009-03-08 21:00:00 PDT (1236571200)
    2009-03-09 00:00:00 PDT (1236582000)
    2009-03-09 03:00:00 PDT (1236592800)
    2009-03-09 06:00:00 PDT (1236603600)

    Note that DST started in the middle of the sequence and that therefore the
    actual time deltas between stamps is not necessarily 3 hours.
    
    startstamp: The start of the sequence in unix epoch time.
    
    stopstamp: The end of the sequence in unix epoch time. 
    
    interval: The time length of an interval in seconds.
    
    yields a sequence of timestamps between startstamp and endstamp, inclusive.
    """
    dt = datetime.datetime.fromtimestamp(startstamp)
    stop_dt = datetime.datetime.fromtimestamp(stopstamp)
    if interval == 365.25 / 12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt <= stop_dt :
            t_tuple = dt.timetuple()
            yield time.mktime(t_tuple)
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year += 1
            dt = dt.replace(year=year, month=month)
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval.
        delta = datetime.timedelta(seconds=interval)
        ts_last = 0
        while dt <= stop_dt :
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

def startOfInterval(time_ts, interval):
    """Find the start time of an interval.
    
    This algorithm assumes the day is divided up into
    intervals of 'interval' length. Given a timestamp, it
    figures out which interval it lies in, returning the start
    time.
    
    time_ts: A timestamp. The start of the interval containing this
    timestamp will be returned.
    
    interval: An interval length in seconds.
    
    Returns: A timestamp with the start of the interval.

    Examples:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
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
    'Thu Jul  4 00:00:00 2013'
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

    interval_m = int(interval // 60)
    interval_h = int(interval // 3600)
    time_tt = time.localtime(time_ts)
    m = int(time_tt.tm_min  // interval_m * interval_m)
    h = int(time_tt.tm_hour // interval_h * interval_h) if interval_h > 1 else time_tt.tm_hour

    # Replace the hour, minute, and seconds with the start of the interval.
    # Everything else gets retained:
    start_interval_ts = time.mktime((time_tt.tm_year,
                                     time_tt.tm_mon,
                                     time_tt.tm_mday,
                                     h, m, 0,
                                     0, 0, time_tt.tm_isdst))
    # Weewx uses the convention that the interval is exclusive on left, inclusive
    # on the right. So, if the timestamp is at the beginning of the interval,
    # it actually belongs to the previous interval.
    if time_ts == start_interval_ts:
        start_interval_ts -= interval
    return start_interval_ts

def _ord_to_ts(_ord):
    d = datetime.date.fromordinal(_ord)
    t = int(time.mktime(d.timetuple()))
    return t

#===============================================================================
# What follows is a bunch of "time span" routines. Generally, time spans
# are used when start and stop times fall on calendar boundaries
# such as days, months, years.  So, it makes sense to talk of "daySpans",
# "weekSpans", etc. They are generally not used between two random times. 
#===============================================================================

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
        """
        Returns True if the span includes the time timestamp, otherwise False.
        
        timestamp: The timestamp to be tested.
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
    
    def __cmp__(self, other):
        if self.start < other.start :
            return - 1
        return 0 if self.start == other.start else 1

def intervalgen(start_ts, stop_ts, interval):
    """Generator function yielding a sequence of time spans whose boundaries
    are on constant local time.
    
    Yields a sequence of TimeSpans. The start times of the timespans will
    be on the same local time boundary as the start of the sequence. See the
    example below.
    
    Example:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> startstamp = 1236477600
    >>> print timestamp_to_string(startstamp)
    2009-03-07 18:00:00 PST (1236477600)
    >>> stopstamp = 1236538800
    >>> print timestamp_to_string(stopstamp)
    2009-03-08 12:00:00 PDT (1236538800)
    
    >>> for span in intervalgen(startstamp, stopstamp, 10800):
    ...     print span
    [2009-03-07 18:00:00 PST (1236477600) -> 2009-03-07 21:00:00 PST (1236488400)]
    [2009-03-07 21:00:00 PST (1236488400) -> 2009-03-08 00:00:00 PST (1236499200)]
    [2009-03-08 00:00:00 PST (1236499200) -> 2009-03-08 03:00:00 PDT (1236506400)]
    [2009-03-08 03:00:00 PDT (1236506400) -> 2009-03-08 06:00:00 PDT (1236517200)]
    [2009-03-08 06:00:00 PDT (1236517200) -> 2009-03-08 09:00:00 PDT (1236528000)]
    [2009-03-08 09:00:00 PDT (1236528000) -> 2009-03-08 12:00:00 PDT (1236538800)]

    (Note how in this example the local time boundaries are constant, despite
    DST kicking in. The interval length is not constant.)
    
    Another example, this one over the Fall DST boundary, and using 1 hour intervals:

    >>> startstamp = 1257051600
    >>> print timestamp_to_string(startstamp)
    2009-10-31 22:00:00 PDT (1257051600)
    >>> stopstamp = 1257080400
    >>> print timestamp_to_string(stopstamp)
    2009-11-01 05:00:00 PST (1257080400)
    >>> for span in intervalgen(startstamp, stopstamp, 3600):
    ...    print span
    [2009-10-31 22:00:00 PDT (1257051600) -> 2009-10-31 23:00:00 PDT (1257055200)]
    [2009-10-31 23:00:00 PDT (1257055200) -> 2009-11-01 00:00:00 PDT (1257058800)]
    [2009-11-01 00:00:00 PDT (1257058800) -> 2009-11-01 01:00:00 PDT (1257062400)]
    [2009-11-01 01:00:00 PDT (1257062400) -> 2009-11-01 02:00:00 PST (1257069600)]
    [2009-11-01 02:00:00 PST (1257069600) -> 2009-11-01 03:00:00 PST (1257073200)]
    [2009-11-01 03:00:00 PST (1257073200) -> 2009-11-01 04:00:00 PST (1257076800)]
    [2009-11-01 04:00:00 PST (1257076800) -> 2009-11-01 05:00:00 PST (1257080400)]
    
    start_ts: The start of the first interval in unix epoch time. In unix epoch time.
    
    stop_ts: The end of the last interval will be equal to or less than this.
    In unix epoch time.
    
    interval: The time length of an interval in seconds.
    
    yields: A sequence of TimeSpans. Both the start and end of the timespan
    will be on the same time boundary as start_ts"""  

    dt1 = datetime.datetime.fromtimestamp(start_ts)
    stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    if interval == 365.25 / 12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt1 < stop_dt :
            t_tuple = dt1.timetuple()
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year += 1
            dt2 = min(dt1.replace(year=year, month=month), stop_dt)
            stamp1 = time.mktime(t_tuple)
            stamp2 = time.mktime(dt2.timetuple())
            yield TimeSpan(stamp1, stamp2)
            dt1 = dt2
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        last_stamp1 = 0
        while dt1 < stop_dt :
            dt2 = min(dt1 + delta, stop_dt)
            stamp1 = int(time.mktime(dt1.timetuple()))
            stamp2 = int(time.mktime(dt2.timetuple()))
            if stamp2 > stamp1 and stamp1 > last_stamp1:
                yield TimeSpan(stamp1, stamp2)
                last_stamp1 = stamp1
            dt1 = dt2

def archiveHoursAgoSpan(time_ts, hours_ago=0, grace=1):
    """Returns a TimeSpan for x hours ago
    
    Example:
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
    >>> print archiveHoursAgoSpan(time_ts, hours_ago=0)
    [2013-07-04 01:00:00 PDT (1372924800) -> 2013-07-04 02:00:00 PDT (1372928400)]
    >>> print archiveHoursAgoSpan(time_ts, hours_ago=2)
    [2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]
    >>> time_ts = time.mktime(datetime.date(2013,07,04).timetuple())
    >>> print archiveHoursAgoSpan(time_ts, hours_ago=0)
    [2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]
    >>> print archiveHoursAgoSpan(time_ts, hours_ago=24)
    [2013-07-02 23:00:00 PDT (1372831200) -> 2013-07-03 00:00:00 PDT (1372834800)]
    """
    if time_ts is None:
        return None
    time_ts -= grace
    dt = datetime.datetime.fromtimestamp(time_ts)
    hour_start_dt = dt.replace(minute=0, second=0, microsecond=0)
    start_span_dt = hour_start_dt - datetime.timedelta(hours=hours_ago)
    stop_span_dt = start_span_dt + datetime.timedelta(hours=1)

    return TimeSpan(time.mktime(start_span_dt.timetuple()), 
                    time.mktime(stop_span_dt.timetuple()))
    
def archiveSpanSpan(time_ts, time_delta=0, hour_delta=0, day_delta=0, week_delta=0):
    """ Returns a TimeSpan for the last xxx seconds where xxx equals
        time_delta sec + hour_delta hours + day_delta days + week_delta weeks
    
    Example:
    >>> os.environ['TZ'] = 'Australia/Brisbane'
    >>> time_ts = time.mktime(time.strptime("2015-07-21 09:05:35", "%Y-%m-%d %H:%M:%S"))
    >>> print archiveSpanSpan(time_ts, time_delta=3600)
    [2015-07-21 08:05:35 AEST (1437429935) -> 2015-07-21 09:05:35 AEST (1437433535)]
    >>> print archiveSpanSpan(time_ts, hour_delta=6)
    [2015-07-21 03:05:35 AEST (1437411935) -> 2015-07-21 09:05:35 AEST (1437433535)]
    >>> print archiveSpanSpan(time_ts, day_delta=1)
    [2015-07-20 09:05:35 AEST (1437347135) -> 2015-07-21 09:05:35 AEST (1437433535)]
    >>> print archiveSpanSpan(time_ts, time_delta=3600, day_delta=1)
    [2015-07-20 08:05:35 AEST (1437343535) -> 2015-07-21 09:05:35 AEST (1437433535)]
    >>> print archiveSpanSpan(time_ts, week_delta=4)
    [2015-06-23 09:05:35 AEST (1435014335) -> 2015-07-21 09:05:35 AEST (1437433535)]
    >>> print archiveSpanSpan(time_ts)
    [2015-07-21 09:05:34 AEST (1437433534) -> 2015-07-21 09:05:35 AEST (1437433535)]
    """
    
    if time_ts is None:
        return None
    start_ts = time_ts - time_delta - hour_delta * 3600 - day_delta * 86400 - \
               week_delta * 604800
    if start_ts == time_ts:
        start_ts -= 1
    return TimeSpan(start_ts, time_ts)
    
def isMidnight(time_ts):
    """Is the indicated time on a midnight boundary, local time?
    
    Example:
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
    >>> print isMidnight(time_ts)
    False
    >>> time_ts = time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))
    >>> print isMidnight(time_ts)
    True
    """
    
    time_tt = time.localtime(time_ts)
    return time_tt.tm_hour==0 and time_tt.tm_min==0 and time_tt.tm_sec==0
    
def archiveDaysAgoSpan(time_ts, days_ago=0, grace=1):
    """Returns a TimeSpan for x days ago
    
    Example:
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
    >>> print archiveDaysAgoSpan(time_ts, days_ago=2)
    [2013-07-02 00:00:00 PDT (1372748400) -> 2013-07-03 00:00:00 PDT (1372834800)]
    >>> time_ts = time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))
    >>> print archiveDaysAgoSpan(time_ts, days_ago=2)
    [2013-07-01 00:00:00 PDT (1372662000) -> 2013-07-02 00:00:00 PDT (1372748400)]
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_ord = _day_date.toordinal()
    return TimeSpan(_ord_to_ts(_day_ord - days_ago), _ord_to_ts(_day_ord - days_ago + 1))

def archiveDaySpan(time_ts, grace=1):
    """Returns a TimeSpan representing a day that includes a given time.
    
    Midnight is considered to actually belong in the previous day if
    grace is greater than zero.
    
    Examples: (Assume grace is 1; printed times are given below, but
    the variables are actually in unix epoch timestamps)
        2007-12-3 18:12:05 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
        2007-12-3 00:00:00 returns (2007-12-2 00:00:00 to 2007-12-3 00:00:00)
        2007-12-3 00:00:01 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
    
    time_ts: The day will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    day. Set to zero to have midnight be included in the
    following day.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one day long that contains time_ts. It
    will begin and end at midnight.
    """
    return archiveDaysAgoSpan(time_ts, days_ago=0, grace=grace)

def archiveWeekSpan(time_ts, startOfWeek=6, grace=1):
    """Returns a TimeSpan representing a week that includes a given time.
    
    The time at midnight at the end of the week is considered to
    actually belong in the previous week.
    
    time_ts: The week will include this timestamp. 
    
    startOfWeek: The start of the week (0=Monday, 1=Tues, ..., 6 = Sun).

    grace: This many seconds past midnight marks the start of the next
    week. Set to zero to have midnight be included in the
    following week.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one week long that contains time_ts. It will
    start at midnight of the day considered the start of the week, and be
    one week long.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_of_week = _day_date.weekday()
    _delta = _day_of_week - startOfWeek
    if _delta < 0: _delta += 7
    _sunday_date = _day_date - datetime.timedelta(days=_delta)
    _next_sunday_date = _sunday_date + datetime.timedelta(days=7)
    return TimeSpan(int(time.mktime(_sunday_date.timetuple())),
                             int(time.mktime(_next_sunday_date.timetuple())))

def archiveMonthSpan(time_ts, grace=1):
    """Returns a TimeSpan representing a month that includes a given time.
    
    Midnight of the 1st of the month is considered to actually belong
    in the previous month.
    
    time_ts: The month will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    month. Set to zero to have midnight be included in the
    following month.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one month long that contains time_ts.
    It will start at midnight of the start of the month, and end at midnight
    of the start of the next month.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _month_date = _day_date.replace(day=1)
    _yr = _month_date.year
    _mo = _month_date.month + 1
    if _mo == 13:
        _mo = 1
        _yr += 1
    _next_month_date = datetime.date(_yr, _mo, 1)
    
    return TimeSpan(int(time.mktime(_month_date.timetuple())),
                             int(time.mktime(_next_month_date.timetuple())))

def archiveYearSpan(time_ts, grace=1):
    """Returns a TimeSpan representing a year that includes a given time.
    
    Midnight of the 1st of the January is considered to actually belong
    in the previous year.
    
    time_ts: The year will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    year. Set to zero to have midnight be included in the
    following year.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one year long that contains time_ts. It will
    begin and end at midnight 1-Jan.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    return TimeSpan(int(time.mktime((_day_date.year, 1, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_day_date.year + 1, 1, 1, 0, 0, 0, 0, 0, -1))))

def archiveRainYearSpan(time_ts, sory_mon, grace=1):
    """Returns a TimeSpan representing a rain year that includes a given time.
    
    Midnight of the 1st of the month starting the rain year is considered to
    actually belong in the previous rain year.
    
    time_ts: The rain year will include this timestamp. 
    
    sory_mon: The month the rain year starts.
    
    grace: This many seconds past midnight marks the start of the next
    rain year. Set to zero to have midnight be included in the
    following rain year.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one year long that contains time_ts. It will
    begin on the 1st of the month that starts the rain year.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _year = _day_date.year if _day_date.month >= sory_mon else _day_date.year - 1
    return TimeSpan(int(time.mktime((_year, sory_mon, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_year + 1, sory_mon, 1, 0, 0, 0, 0, 0, -1))))

def genHourSpans(start_ts, stop_ts):
    """Generator function that generates start/stop of hours in an inclusive range.

    Example:

    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> start_ts = 1204796460
    >>> stop_ts  = 1204818360

    >>> print timestamp_to_string(start_ts)
    2008-03-06 01:41:00 PST (1204796460)
    >>> print timestamp_to_string(stop_ts)
    2008-03-06 07:46:00 PST (1204818360)

    >>> for span in genHourSpans(start_ts, stop_ts):
    ...   print span
    [2008-03-06 01:00:00 PST (1204794000) -> 2008-03-06 02:00:00 PST (1204797600)]
    [2008-03-06 02:00:00 PST (1204797600) -> 2008-03-06 03:00:00 PST (1204801200)]
    [2008-03-06 03:00:00 PST (1204801200) -> 2008-03-06 04:00:00 PST (1204804800)]
    [2008-03-06 04:00:00 PST (1204804800) -> 2008-03-06 05:00:00 PST (1204808400)]
    [2008-03-06 05:00:00 PST (1204808400) -> 2008-03-06 06:00:00 PST (1204812000)]
    [2008-03-06 06:00:00 PST (1204812000) -> 2008-03-06 07:00:00 PST (1204815600)]
    [2008-03-06 07:00:00 PST (1204815600) -> 2008-03-06 08:00:00 PST (1204819200)]

    start_ts: A time stamp somewhere in the first day.

    stop_ts: A time stamp somewhere in the last day.

    yields: Instance of TimeSpan, where the start is the time stamp
    of the start of the day, the stop is the time stamp of the start
    of the next day.

    """
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    _start_hour = int(start_ts / 3600)
    _stop_hour = int(stop_ts / 3600)
    if (_stop_dt.minute, _stop_dt.second) == (0, 0):
        _stop_hour -= 1

    for _hour in range(_start_hour, _stop_hour+1):
        yield TimeSpan(_hour*3600, (_hour+1)*3600)

def genDaySpans(start_ts, stop_ts):
    """Generator function that generates start/stop of days in an inclusive range.
    
    Example:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> start_ts = 1204796460
    >>> stop_ts  = 1205265720
    
    >>> print timestamp_to_string(start_ts)
    2008-03-06 01:41:00 PST (1204796460)
    >>> print timestamp_to_string(stop_ts)
    2008-03-11 13:02:00 PDT (1205265720)
    
    >>> for span in genDaySpans(start_ts, stop_ts):
    ...   print span
    [2008-03-06 00:00:00 PST (1204790400) -> 2008-03-07 00:00:00 PST (1204876800)]
    [2008-03-07 00:00:00 PST (1204876800) -> 2008-03-08 00:00:00 PST (1204963200)]
    [2008-03-08 00:00:00 PST (1204963200) -> 2008-03-09 00:00:00 PST (1205049600)]
    [2008-03-09 00:00:00 PST (1205049600) -> 2008-03-10 00:00:00 PDT (1205132400)]
    [2008-03-10 00:00:00 PDT (1205132400) -> 2008-03-11 00:00:00 PDT (1205218800)]
    [2008-03-11 00:00:00 PDT (1205218800) -> 2008-03-12 00:00:00 PDT (1205305200)]
    
    Note that a daylight savings time change happened 8 March 2009.

    start_ts: A time stamp somewhere in the first day.
    
    stop_ts: A time stamp somewhere in the last day.
    
    yields: Instance of TimeSpan, where the start is the time stamp
    of the start of the day, the stop is the time stamp of the start
    of the next day.
    
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
    
    Example:
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> start_ts = 1196705700
    >>> stop_ts  = 1206101100
    >>> print "start time is", timestamp_to_string(start_ts)
    start time is 2007-12-03 10:15:00 PST (1196705700)
    >>> print "stop time is ", timestamp_to_string(stop_ts)
    stop time is  2008-03-21 05:05:00 PDT (1206101100)
    
    >>> for span in genMonthSpans(start_ts, stop_ts):
    ...   print span
    [2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]
    [2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]
    [2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]
    [2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]
    
    Note that a daylight savings time change happened 8 March 2009.

    start_ts: A time stamp somewhere in the first month.
    
    stop_ts: A time stamp somewhere in the last month.
    
    yields: Instance of TimeSpan, where the start is the time stamp
    of the start of the month, the stop is the time stamp of the start
    of the next month.
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
        yield TimeSpan(time.mktime((_this_yr, _this_mo, 1, 0, 0, 0, 0, 0, -1)),
                       time.mktime((_next_yr, _next_mo, 1, 0, 0, 0, 0, 0, -1)))

def genYearSpans(start_ts, stop_ts):
    if None in (start_ts, stop_ts):
        return
    _start_date = datetime.date.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_year = _start_date.year
    _stop_year = _stop_dt.year
    
    if(_stop_dt.month, _stop_dt.day, _stop_dt.hour,
       _stop_dt.minute, _stop_dt.second) == (1, 1, 0, 0, 0):
        _stop_year -= 1
        
    for year in range(_start_year, _stop_year + 1):
        yield TimeSpan(time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1)),
                       time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1)))
        
def startOfDay(time_ts):
    """Calculate the unix epoch time for the start of a (local time) day.
    
    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_tt = time.localtime(time_ts)
    _bod_ts = time.mktime((_time_tt.tm_year,
                            _time_tt.tm_mon,
                            _time_tt.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return int(_bod_ts)
        
def startOfDayUTC(time_ts):
    """Calculate the unix epoch time for the start of a UTC day.
    
    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_tt = time.gmtime(time_ts)
    _bod_ts = calendar.timegm((_time_tt.tm_year,
                               _time_tt.tm_mon,
                               _time_tt.tm_mday,
                               0, 0, 0, 0, 0, -1))
    return int(_bod_ts)

def startOfArchiveDay(time_ts, grace=1):
    """Given an archive time stamp, calculate its start of day.
    
    similar to startOfDay(), except that an archive stamped at midnight
    actually belongs to the *previous* day.

    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    grace: The number of seconds past midnight when the following
    day is considered to start [Optional. Default is 1 second]
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time."""
    
    return startOfDay(time_ts - grace)

def getDayNightTransitions(start_ts, end_ts, lat, lon):
    """Return the day-night transitions between the start and end times.

    start_ts: A timestamp (UTC) indicating the beginning of the period

    end_ts: A timestamp (UTC) indicating the end of the period

    returns: indication of whether the period from start to first transition
    is day or night, plus array of transitions (UTC).
    """
    first = None
    values = []
    for t in range(start_ts-3600*24, end_ts+3600*24+1, 3600*24):
        x = startOfDayUTC(t)
        x_tt = time.gmtime(x)
        y, m, d = x_tt[:3]
        (sunrise_utc, sunset_utc) = Sun.sunRiseSet(y, m, d, lon, lat)
        daystart_ts = calendar.timegm((y,m,d,0,0,0,0,0,-1))
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
    
def secs_to_string(secs):
    """Convert seconds to a string with days, hours, and minutes"""
    str_list = []
    for (label, interval) in (('day', 86400), ('hour', 3600), ('minute', 60)):
        amt = int(secs / interval)
        plural = '' if amt == 1 else 's'
        str_list.append("%d %s%s" % (amt, label, plural))
        secs %= interval
    ans = ', '.join(str_list)
    return ans

def timestamp_to_string(ts):
    """Return a string formatted from the timestamp
    
    Example:

    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> print timestamp_to_string(1196705700)
    2007-12-03 10:15:00 PST (1196705700)
    >>> print timestamp_to_string(None)
    ******* N/A *******     (    N/A   )
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"

def timestamp_to_gmtime(ts):
    """Return a string formatted for GMT
    
    >>> print timestamp_to_gmtime(1196705700)
    2007-12-03 18:15:00 UTC (1196705700)
    >>> print timestamp_to_gmtime(None)
    ******* N/A *******     (    N/A   )
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"
        
def utc_to_ts(y, m, d, hrs_utc):
    """Converts from a UTC tuple-time to unix epoch time.
    
    y,m,d: The year, month, day for which the conversion is desired.
    
    hrs_tc: Floating point number with the number of hours since midnight in UTC.
    
    Returns: The unix epoch time.
    
    >>> print utc_to_ts(2009, 3, 27, 14.5)
    1238164200
    """
    # Construct a time tuple with the time at midnight, UTC:
    daystart_utc_tt = (y,m,d,0,0,0,0,0,-1)
    # Convert the time tuple to a time stamp and add on the number of seconds since midnight:
    time_ts = int(calendar.timegm(daystart_utc_tt) + hrs_utc * 3600.0 + 0.5)
    return time_ts

def utc_to_local_tt(y, m, d,  hrs_utc):
    """Converts from a UTC time to a local time.
    
    y,m,d: The year, month, day for which the conversion is desired.
    
    hrs_tc: Floating point number with the number of hours since midnight in UTC.
    
    Returns: A timetuple with the local time.
    
    >>> os.environ['TZ'] = 'America/Los_Angeles'
    >>> tt=utc_to_local_tt(2009, 3, 27, 14.5)
    >>> print tt.tm_year, tt.tm_mon, tt.tm_mday, tt.tm_hour, tt.tm_min
    2009 3 27 7 30
    """
    # Get the UTC time:
    time_ts = utc_to_ts(y, m, d, hrs_utc)
    # Convert to local time:
    time_local_tt = time.localtime(time_ts)
    return time_local_tt

def latlon_string(ll, hemi, which, format_list=None):
    """Decimal degrees into a string for degrees, and one for minutes.
    ll: The decimal latitude or longitude
    hemi: A tuple holding strings representing positive or negative values. E.g.: ('N', 'S')
    which: 'lat' for latitude, 'long' for longitude
    format_list: A list or tuple holding the format strings to be used. These are [whole degrees latitude, 
                 whole degrees longitude, minutes]
                 
    Returns:
    A 3-way tuple holding (latlon whole degrees, latlon minutes, hemisphere designator). 
    Example: (022, 08.3, 'N') """
    labs = abs(ll)
    (frac, deg) = math.modf(labs)
    minutes = frac * 60.0
    if format_list is None:
        format_list = ["%02d", "%03d", "%05.2f"]
    return ((format_list[0] if which == 'lat' else format_list[1]) % (deg,), format_list[2] % (minutes,), hemi[0] if ll >= 0 else hemi[1])

def log_traceback(prefix='', loglevel=syslog.LOG_INFO):
    """Log the stack traceback into syslog."""
    sfd = StringIO.StringIO()
    traceback.print_exc(file=sfd)
    sfd.seek(0)
    for line in sfd:
        syslog.syslog(loglevel, prefix + line)
    del sfd
    
def _get_object(module_class):
    """Given a string with a module class name, it imports and returns the class."""
    # Split the path into its parts
    parts = module_class.split('.')
    # Strip off the classname:
    module = '.'.join(parts[:-1])
    # Import the top level module
    mod = __import__(module)
    # Recursively work down from the top level module to the class name.
    # Be prepared to catch an exception if something cannot be found.
    try:
        for part in parts[1:]:
            mod = getattr(mod, part)
    except AttributeError:
        # Can't find something. Give a more informative error message:
        raise AttributeError("Module '%s' has no attribute '%s' when searching for '%s'" % (mod.__name__, part, module_class))
    return mod

class GenWithPeek(object):
    """Generator object which allows a peek at the next object to be returned.
    
    Sometimes Python solves a complicated problem with such elegance! This is
    one of them.
    
    Example of usage:
    >>> # Define a generator function:
    >>> def genfunc(N):
    ...     for i in range(N):
    ...        yield i
    >>>
    >>> # Now wrap it with the GenWithPeek object:
    >>> g_with_peek = GenWithPeek(genfunc(5))
    >>> # We can iterate through the object as normal:
    >>> for i in g_with_peek:
    ...    print i
    ...    # Every second object, let's take a peek ahead
    ...    if i%2:
    ...        # We can get a peek at the next object without disturbing the wrapped generator:
    ...        print "peeking ahead, the next object will be: ", g_with_peek.peek()
    0
    1
    peeking ahead, the next object will be:  2
    2
    3
    peeking ahead, the next object will be:  4
    4
    """
    
    def __init__(self, generator):
        """Initialize the generator object.
        
        generator: A generator object to be wrapped
        """
        self.generator = generator
        self.have_peek = False
        
    def __iter__(self):
        return self
    
    def next(self):  #@ReservedAssignment
        """Advance to the next object"""
        if self.have_peek:
            self.have_peek = False
            return self.peek_obj
        else:
            return self.generator.next()
        
    def peek(self):
        """Take a peek at the next object"""
        if not self.have_peek:
            self.peek_obj = self.generator.next()
            self.have_peek = True
        return self.peek_obj

def tobool(x):
    """Convert an object to boolean.
    
    Examples:
    >>> print tobool('TRUE')
    True
    >>> print tobool(True)
    True
    >>> print tobool(1)
    True
    >>> print tobool('FALSE')
    False
    >>> print tobool(False)
    False
    >>> print tobool(0)
    False
    >>> print tobool('Foo')
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'Foo'.
    >>> print tobool(None)
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'None'.
    """

    try:
        if x.lower() in ['true', 'yes']:
            return True
        elif x.lower() in ['false', 'no']:
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
    >>> print to_int(123)
    123
    >>> print to_int('123')
    123
    >>> print to_int(-5.2)
    -5
    >>> print to_int(None)
    None
    """
    if isinstance(x, basestring) and x.lower() == 'none':
        x = None
    return int(x) if x is not None else None

def to_float(x):
    """Convert an object to a float, unless it is None
    
    Examples:
    >>> print to_float(12.3)
    12.3
    >>> print to_float('12.3')
    12.3
    >>> print to_float(None)
    None
    """
    if isinstance(x, basestring) and x.lower() == 'none':
        x = None
    return float(x) if x is not None else None

def to_unicode(string, encoding='utf8'):
    """Convert to Unicode, unless string is None
    
    Example:
    >>> print to_unicode("degree sign from UTF8: \xc2\xb0")
    degree sign from UTF8: °
    >>> print to_unicode(u"degree sign from Unicode: \u00b0")
    degree sign from Unicode: °
    >>> print to_unicode(None)
    None
    """
    try:
        return unicode(string, encoding) if string is not None else None
    except TypeError:
        # The string is already in Unicode. Just return it.
        return string

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
    """Find the maximum in a (possibly empty) sequence, ignoring Nones"""
    xmax = None
    for x in x_seq:
        if xmax is None:
            xmax = x
        elif x is not None:
            xmax = max(x, xmax)
    return xmax

def print_dict(d, margin=0, increment=4):
    """Pretty print a dictionary.
    
    Example:
    >>> print_dict({'sec1' : {'a':1, 'b':2, 'sec2': {'f':9}}, 'e':3})
     sec1
         a = 1
         b = 2
         sec2
             f = 9
     e = 3
    """
    for k in d:
        if type(d[k]) is dict:
            print margin * ' ', k
            print_dict(d[k], margin + increment, increment)
        else:
            print margin * ' ', k, '=', d[k]

def move_with_timestamp(filepath):
    """Save a file to a path with a timestamp."""
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    # Check to see if this name already exists
    if os.path.exists(newpath):
        # It already exists. Stick a version number on it:
        version = 1
        while os.path.exists(newpath + '-' + str(version)):
            version += 1
        newpath = newpath + '-' + str(version)
    shutil.move(filepath, newpath)
    return newpath

class ListOfDicts(dict):
    """A list of dictionaries, that are searched in order.
    
    It assumes only that any inserted dictionaries support a keyed
    lookup using the syntax obj[key].
    
    Example:

    # Try an empty dictionary:
    >>> lod = ListOfDicts()
    >>> print lod['b']
    Traceback (most recent call last):
    KeyError: 'b'
    >>> # Now initialize it with a starting dictionary:
    >>> lod = ListOfDicts({'a':1, 'b':2, 'c':3})
    >>> print lod['b']
    2
    >>> # Look for a non-existent key
    >>> print lod['d']
    Traceback (most recent call last):
    KeyError: 'd'
    >>> # Now extend the dictionary:
    >>> lod.extend({'d':4, 'e':5})
    >>> # And try the lookup:
    >>> print lod['d']
    4
    >>> # Explicitly add a new key to the dictionary:
    >>> lod['f'] = 6
    >>> # Try it:
    >>> print lod['f']
    6
    """
    def __init__(self, starting_dict=None):
        if starting_dict:
            super(ListOfDicts,self).__init__(starting_dict)
        self.dict_list = []

    def __getitem__(self, key):
        for this_dict in self.dict_list:
            try:
                return this_dict[key]
            except KeyError:
                pass
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def extend(self, new_dict):
        self.dict_list.append(new_dict)

# Supply an implementation of os.path.relpath, but it was not introduced
# until Python v2.5
try:
    os.path.relpath
    # We can use the Python library version.
    relpath = os.path.relpath
except AttributeError:
    # No Python library version.
    # Substitute a version from James Gardner's BareNecessities
    # https://jimmyg.org/work/code/barenecessities/index.html
    import posixpath
    from posixpath import curdir, sep, pardir, join
    
    def relpath(path, start=curdir):
        """Return a relative version of a path"""
        if not path:
            raise ValueError("no path specified")
        start_list = posixpath.abspath(start).split(sep)
        path_list = posixpath.abspath(path).split(sep)
        # Work out how much of the filepath is shared by start and path.
        i = len(posixpath.commonprefix([start_list, path_list]))
        rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
        if not rel_list:
            return curdir
        return join(*rel_list)

if __name__ == '__main__':
    import sys
    reload(sys)
    sys.setdefaultencoding("UTF-8")  # @UndefinedVariable
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
