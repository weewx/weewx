#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Various handy utilities that don't belong anywhere else."""

import datetime
import time
import math
import ImageFont
import configobj


def min_no_None(seq):
    """Searches sequence of tuples, returning tuple where the first member was a minimum.
    
    seq: a sequence of tuples.
    
    returns: Tuple where the first member was a maximum. None values are ignored.
    If no non-None value was found, returns None"""
            
    v_min = None
    for v_tuple in seq:
        if v_tuple is None or v_tuple[0] is None: continue
        if v_min is None or v_tuple[0] < v_min[0]:
            v_min = v_tuple
    return v_min

def max_no_None(seq):
    """Searches sequence of tuples, returning tuple where the first member was a maximum.
    
    seq: a sequence of tuples.
    
    returns: tuple where the first member was a maximum. None values are ignored.
    If no non-None value was found, returns None."""
            
    v_max = None
    for v_tuple in seq:
        if v_tuple is None or v_tuple[0] is None: continue
        if v_max is None or v_tuple[0] > v_max[0]:
            v_max = v_tuple
    return v_max

def mean_no_None(seq):
    "Returns mean (average), ignoring None values"
    v_sum = 0.0
    count = 0
    for v in seq:
        if v is not None:
            v_sum += v
            count += 1
    return v_sum / count if count else None

def sum_no_None(seq):
    v_sum = 0.0
    for v in seq:
        if v is not None:
            v_sum += v
    return v_sum

def get_font_handle(fontpath, *args):
    
    font = None
    if fontpath is not None :
        try :
            if fontpath.endswith('.ttf'):
                font = ImageFont.truetype(fontpath, *args)
            else :
                font = ImageFont.load_path(fontpath)
        except IOError :
            pass
    
    if font is None :
        font = ImageFont.load_default()
        
    return font 

def convertToFloat(seq):
    """Convert a sequence with strings to floats, honoring 'Nones'"""
    
    if seq is None: return None
    res = [None if s in ('None', 'none') else float(s) for s in seq]
    return res

def accumulateLeaves(d):
    """Merges leaf options above a ConfigObj section with itself, accumulating the results.
    
    This routine is useful for specifying defaults near the root node, 
    then having them overridden in the leaf nodes of a ConfigObj.
    
    d: instance of a configobj.Section (i.e., a section of a ConfigObj)
    """
    
    # Use recursion. If I am the root object, then there is nothing above 
    # me to accumulate. Start with a virgin ConfigObj
    if d.parent is d :
        cum_dict = configobj.ConfigObj()
    else :
        # Otherwise, recursively accumulate scalars above me
        cum_dict = accumulateLeaves(d.parent)
        
    # Now merge my scalars into the results:
    merge_dict = {}
    for k in d.scalars :
        merge_dict[k] = d[k]
    cum_dict.merge(merge_dict)
    return cum_dict

def stampgen(startstamp, stopstamp, interval):
    """Generator function yielding a sequence of timestamps, spaced interval apart.
    
    The sequence will fall on the same local time boundary as startstamp. 
    For example, if startstamp is epoch time 1236560400 (local time 
    8-Mar-2009 18:00 PST) and interval is 10800 (3 hours), then the yielded sequence 
    will be (shown with local times):
    
    1236560400 (8-Mar-2009 18:00 PST)
    1236571200 (8-Mar-2009 21:00 PST)
    1236582000 (9-Mar-2009 00:00 PST)
    1236592800 (9-Mar-2009 03:00 PDT)
    1236603600 (9-Mar-2009 06:00 PDT), etc.
    
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
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        while dt <= stop_dt :
            yield int(time.mktime(dt.timetuple()))
            dt += delta

def intervalgen(start_ts, stop_ts, interval):
    """Generator function yielding a sequence of time intervals.
    
    Yields a sequence of intervals. First interval is (start_ts, start_ts+interval),
    second is (start_ts+interval, start_ts+2*interval), etc. The last interval
    will end at or before stop_ts. It is up to the consumer to interpret whether
    the end points of any given interval is inclusive or exclusive to the
    interval.
    
    start_ts: The start of the first interval in unix epoch time.
    
    stop_ts: The end of the last interval will be equal to or less than this.
    In unix epoch time.
    
    interval: The time length of an interval in seconds.
    
    yields: A sequence of 2-tuples. First value is start of the interval, second 
    is the end. Both the start and end will be on the same time boundary as
    start_ts
    
    """  
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
            yield (stamp1, stamp2)
            dt1 = dt2
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        while dt1 < stop_dt :
            dt2 = min(dt1 + delta, stop_dt)
            stamp1 = time.mktime(dt1.timetuple())
            stamp2 = time.mktime(dt2.timetuple())
            yield (stamp1, stamp2)
            dt1 = dt2

def _ord_to_ts(ord):
    d = datetime.date.fromordinal(ord)
    t = int(time.mktime(d.timetuple()))
    return t

#===============================================================================
# What follows is a bunch of "time span" routines. Generally, time spans
# are used when start and stop times fall on calendar boundaries
# such as days, months, years.  So, it makes sense to talk of "daySpans",
# "weekSpans", etc. They are generally not used between two random times. 
#===============================================================================

class TimeSpan(object):
    '''
    Represents a time span, exclusive on the left, inclusive on the right.
    '''

    def __init__(self, start_ts, stop_ts):
        '''
        Initialize a new instance of TimeSpan to the interval start_ts, stop_ts.
        
        start_ts: The starting time stamp of the interval.
        
        stop_ts: The stopping time stamp of the interval
        '''
        
        if start_ts >= stop_ts :
            raise ValueError, "start time must be less than stop time"
        self.start = int(start_ts)
        self.stop = int(stop_ts)
        
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

def archiveDaySpan(time_ts, grace = 30):
    """Returns a TimeSpan representing a day that includes a given time.
    
    Midnight is considered to actually belong in the previous day.
    
    Examples: (Assume grace is 30; printed times are given below, but
    the variables are actually in unix epoch timestamps)
        2007-12-3 18:12:05 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
        2007-12-3 00:00:00 returns (2007-12-2 00:00:00 to 2007-12-3 00:00:00)
        2007-12-3 00:00:25 returns (2007-12-2 00:00:00 to 2007-12-3 00:00:00)
        2007-12-3 00:00:35 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
    
    time_ts: The day will include this timestamp. 
    
    grace: This many seconds past midnight are still included in the previous day.
    [Optional. Default is 30 seconds.]
    
    returns: A TimeSpan object one day long that contains time_ts. It
    will begin and end at midnight.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_ord = _day_date.toordinal()
    return TimeSpan(_ord_to_ts(_day_ord), _ord_to_ts(_day_ord + 1))

def archiveWeekSpan(time_ts, startOfWeek = 6, grace = 30):
    """Returns a TimeSpan representing a week that includes a given time.
    
    The time at midnight at the end of the week is considered to
    actually belong in the previous week.
    
    time_ts: The week will include this timestamp. 
    
    startOfWeek: The start of the week (0=Monday, 1=Tues, ..., 6 = Sun).

    grace: This many seconds past midnight are still included in the last week.
    [Optional. Default is 30 seconds.]

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

def archiveMonthSpan(time_ts, grace = 30):
    """Returns a TimeSpan representing a month that includes a given time.
    
    Midnight of the 1st of the month is considered to actually belong
    in the previous month.
    
    time_ts: The month will include this timestamp. 
    
    grace: This many seconds past midnight of the 1st are still included
    in the previous month. [Optional. Default is 30 seconds.]

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

def archiveYearSpan(time_ts, grace = 30):
    """Returns a TimeSpan representing a year that includes a given time.
    
    Midnight of the 1st of the January is considered to actually belong
    in the previous year.
    
    time_ts: The year will include this timestamp. 
    
    grace: This many seconds past midnight of 1-Jan are still included
    in the previous year. [Optional. Default is 30 seconds.]

    returns: A TimeSpan object one year long that contains time_ts. It will
    begin and end at midnight 1-Jan.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    return TimeSpan(int(time.mktime((_day_date.year, 1, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_day_date.year + 1, 1, 1, 0, 0, 0, 0, 0, -1))))

def archiveRainYearSpan(time_ts, sory_mon = 1, grace = 30):
    """Returns a TimeSpan representing a rain year that includes a given time.
    
    Midnight of the 1st of the month starting the rain year is considered to
    actually belong in the previous rain year.
    
    time_ts: The rain year will include this timestamp. 
    
    sory_mon: The month the rain year starts. [Optional. Default is 1 (Jan)]
    
    grace: This many seconds past midnight of the 1st of the month starting
    the rain year are still included in the previous rain year.
    [Optional. Default is 30 seconds.]

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

def genDaySpans(start_ts, stop_ts):
    _start_dt = datetime.datetime.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_ord = _start_dt.toordinal()
    _stop_ord = _stop_dt.toordinal()
    if (_stop_dt.hour, _stop_dt.minute, _stop_dt.second) == (0, 0, 0):
        _stop_ord -= 1

    for ord in range(_start_ord, _stop_ord + 1):
        yield TimeSpan(_ord_to_ts(ord), _ord_to_ts(ord + 1))
 
   
def genMonthSpans(start_ts, stop_ts):
    """Generator function that generates start/stop of months in an
    inclusive range.
    
    For example, if start_ts is 1196705700 (local time 2007-12-03 10:15:00 PST)
    and stop_ts is 1206101100 (2008-03-21, 05:05:00 PST), the function
    will generate:
     
    1196496000 (2007-12-01 00:00:00 PST) 1199174400 (2008-01-01 00:00:00 PST) 
    1199174400 (2008-01-01 00:00:00 PST) 1201852800 (2008-02-01 00:00:00 PST)
    1201852800 (2008-02-01 00:00:00 PST) 1204358400 (2009-03-01 00:00:00 PST)
    1204358400 (2009-03-01 00:00:00 PST) 1207033200 (2009-04-01 00:00:00 PDT)
    
    Note that a daylight savings time change happened 8 March 2009.

    start_ts: A time stamp somewhere in the first month.
    
    stop_ts: A time stamp somewhere in the last month.
    
    yields: An instance of TimeSpan, where the start is the time stamp
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


def startOfArchiveDay(time_ts, grace = 30):
    """Given an archive time stamp, calculate its start of day.
    
    similar to startOfDay(), except that an archive stamped at midnight
    actually belongs to the *previous* day.

    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    grace: The number of seconds past midnight which is still considered
    to be in the previous day [Optional. Default is 30 seconds]
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    return startOfDay(time_ts - grace)
    
def secs_to_string(secs):
    """
    Convert seconds to a string with days, hours, minutes and seconds
    """
    str_list = []
    for (label, interval) in (('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)):
        amt = int(secs / interval)
        plural = '' if amt == 1 else 's'
        str_list.append("%d %s%s" % (amt, label, plural))
        secs %= interval
    str = ', '.join(str_list)
    return str

def timestamp_to_string(ts):
    """
    Return a string formatted from the timestamp
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)), ts)
    else:
        return "****** N/A ******** (    N/A   )"

def latlon_string(ll, hemi):
    """Decimal degrees into a string for degrees, and one for minutes."""
    labs = abs(ll)
    (frac, deg) = math.modf(labs)
    min = frac * 60.0
    return ("%d" % (deg,), "%0.2f" % (min,), hemi[0] if ll >= 0 else hemi[1])

def _get_object(module_class, *args, **kwargs):
    """Given a path to a class, instantiates an instance of the class with the given args and returns it."""
    
    # Split the path into its parts
    parts = module_class.split('.')
    # Strip off the classname:
    module = '.'.join(parts[:-1])
    # Import the top level module
    mod = __import__(module)
    # Then recursively work down from the top level module to the class name:
    for part in parts[1:]:
        mod = getattr(mod, part)
    # Instance 'mod' will now be a class. Instantiate an instance and return it:
    obj = mod(*args, **kwargs)
    return obj
        
if __name__ == '__main__':
    print "********* TimeSpans ***********"

    t = TimeSpan(1230000000, 1231000000)
    print t
    assert(t==t)
    tsub = TimeSpan(1230500000, 1230600000)
    assert(t.includes(tsub))
    assert(not tsub.includes(t))
    tleft = TimeSpan(1229000000, 1229100000)
    assert(not t.includes(tleft))
    tright = TimeSpan(1232000000, 1233000000)
    assert(not t.includes(tright))
    
    dic={}
    dic[t] = 't'
    dic[tsub] = 'tsub'
    dic[tleft] = 'tleft'
    dic[tright] = 'tright'
    
    assert(dic[t] == 't')
    print "PASSES"

    print "********* genYearSpans ***********"
    print "Should print years 2007 through 2008:"
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 03, 1, 0, 0, 0, 0, 0, -1))

    for span in genYearSpans(start_ts, stop_ts):
        print span
        
    print "********* genMonthSpans ***********"
    print "Should print months 2007-12 through 2008-02:"
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 03, 1, 0, 0, 0, 0, 0, -1))

    for span in genMonthSpans(start_ts, stop_ts):
        print span

    print "\nShould print months 2007-12 through 2008-03:"
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 03, 1, 0, 0, 1, 0, 0, -1))

    for span in genMonthSpans(start_ts, stop_ts):
        print span
    print "********** genDaySpans ************"
    
    print "Should print 2007-12-23 through 2008-1-5:"
    start_ts = time.mktime((2007, 12, 23, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 1, 5, 9, 22, 0, 0, 0, -1))
    for span in genDaySpans(start_ts, stop_ts):
        print span
    print "\nShould print the single date 2007-12-1:"
    for span in genDaySpans(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                             time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1))):
        print span

    print "******** daySpan ***************"
    assert(archiveDaySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
    assert(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 12, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))))
    assert(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 31, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
    print "PASSES"

    print "******** weekSpan ***************"
    assert(archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))
    assert(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))))
    assert(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 31, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))
    print "PASSES"

    print "******** monthSpan ***************"
    assert(archiveMonthSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 11, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 31, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
    print "PASSES"
    
    print "******** yearSpan ***************"
    assert(archiveYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))) == 
           TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 31, 0, 0, -1))) == 
           TimeSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2009, 1, 1, 0, 0, 0, 0, 0, -1))))
    print "PASSES"

    print "******** rainYearSpan ***************"
    assert(archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 10) == 
           TimeSpan(time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1))))
    assert(archiveRainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 10) == 
           TimeSpan(time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)),
                    time.mktime((2008, 10, 1, 0, 0, 0, 0, 0, -1))))
    print "PASSES"

    print "******** Start-of-days **********"

    # Test start-of-day routines around a DST boundary:
    start_ts = time.mktime((2007, 03, 11, 01, 0, 0, 0, 0, -1))
    start_of_day = startOfDay(start_ts)
    start2 = startOfArchiveDay(start_of_day)
    print timestamp_to_string(start_ts)
    print timestamp_to_string(start_of_day)
    print timestamp_to_string(start2)
    # Check that this is, in fact, a DST boundary:
    assert(start_of_day == int(time.mktime((2007, 03, 11, 0, 0, 0, 0, 0, -1))))
    assert(start2 == int(time.mktime((2007, 03, 10, 0, 0, 0, 0, 0, -1))))
    print "PASSES"
    
