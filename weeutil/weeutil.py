#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Various handy utilities that don't belong anywhere else."""

import datetime
import time
import math
import ImageFont
import configobj

import timespan

def min_no_None(seq):
    """Searches sequence of tuples, returning tuple where the first member was a minimum.
    
    seq: a sequence of tuples.
    
    returns: Tuple where the first member was a maximum. None values are ignored.
    If no non-None value was found, returns None"""
            
    v_min = None
    for v_tuple in seq:
        if v_tuple is None or v_tuple[0] is None: continue
        if v_min is None or v_tuple[0] < v_min[0]:
            v_min  = v_tuple
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
            v_max  = v_tuple
    return v_max

def mean_no_None(seq):
    "Returns mean (average), ignoring None values"
    v_sum = 0.0
    count = 0
    for v in seq:
        if v is not None:
            v_sum += v
            count += 1
    return v_sum/count if count else None

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


def accumulatescalars(d):
    """Merges scalar options above a ConfigObj section with itself, accumulating the results.
    
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
        cum_dict = accumulatescalars(d.parent)
        
    # Now merge my scalars into the results:
    merge_dict = {}
    for k in d.scalars :
        merge_dict[k] = d[k]
    cum_dict.merge(merge_dict)
    return cum_dict

def startOfNextInterval(time_ts, interval):
    """
    Calculate the unix epoch time for the start of the next interval
    in local time. This rather complicated algorithm is necessary
    because of the possibility DST might change in the middle.
    """
    time_dt = datetime.datetime.fromtimestamp(time_ts)
    delta  = datetime.timedelta(seconds=interval)
    next_dt = time_dt + delta
    return int(time.mktime(next_dt.timetuple()))
    
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
    dt      = datetime.datetime.fromtimestamp(startstamp)
    stop_dt = datetime.datetime.fromtimestamp(stopstamp)
    if interval == 365.25/12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt <= stop_dt :
            t_tuple = dt.timetuple()
            yield time.mktime(t_tuple)
            year  = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year  += 1
            dt = dt.replace(year=year, month=month)
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta  = datetime.timedelta(seconds=interval)
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
    dt1     = datetime.datetime.fromtimestamp(start_ts)
    stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    if interval == 365.25/12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt1 < stop_dt :
            t_tuple = dt1.timetuple()
            year  = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year  += 1
            dt2 = min(dt1.replace(year=year, month=month), stop_dt)
            stamp1 = time.mktime(t_tuple)
            stamp2 = time.mktime(dt2.timetuple())
            yield (stamp1, stamp2)
            dt1 = dt2
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta  = datetime.timedelta(seconds=interval)
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

def daySpan(time_ts):
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_ord  = _day_date.toordinal()
    return timespan.TimeSpan(_ord_to_ts(_day_ord), _ord_to_ts(_day_ord+1))

def weekSpan(time_ts):
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_of_week = _day_date.weekday()
    _delta = _day_of_week + 1 if _day_of_week is not 6 else 0
    _sunday_date      = _day_date    - datetime.timedelta(days = _delta)
    _next_sunday_date = _sunday_date + datetime.timedelta(days = 7)
    return timespan.TimeSpan(int(time.mktime(_sunday_date.timetuple())),
                             int(time.mktime(_next_sunday_date.timetuple())))

def monthSpan(time_ts):
    _day_date = datetime.date.fromtimestamp(time_ts)
    _month_date = _day_date.replace(day=1)
    _yr = _month_date.year
    _mo = _month_date.month + 1
    if _mo == 13:
        _mo = 1
        _yr += 1
    _next_month_date = datetime.date(_yr, _mo, 1)
    
    return timespan.TimeSpan(int(time.mktime(_month_date.timetuple())),
                             int(time.mktime(_next_month_date.timetuple())))

def yearSpan(time_ts):
    _day_date = datetime.date.fromtimestamp(time_ts)
    return timespan.TimeSpan(int(time.mktime((_day_date.year,   1, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_day_date.year+1, 1, 1, 0, 0, 0, 0, 0, -1))))

def rainYearSpan(time_ts, sory_mon = 1):
    _day_date = datetime.date.fromtimestamp(time_ts)
    _year = _day_date.year if _day_date.month >= sory_mon else _day_date.year - 1
    return timespan.TimeSpan(int(time.mktime((_year,   sory_mon, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_year+1, sory_mon, 1, 0, 0, 0, 0, 0, -1))))

def genDaySpans(start_ts, stop_ts):
    _start_dt = datetime.datetime.fromtimestamp(start_ts)
    _stop_dt  = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_ord = _start_dt.toordinal()
    _stop_ord  = _stop_dt.toordinal()
    if (_stop_dt.hour, _stop_dt.minute, _stop_dt.second) == (0, 0, 0):
        _stop_ord -= 1

    for ord in range(_start_ord, _stop_ord+1):
        yield timespan.TimeSpan( _ord_to_ts(ord), _ord_to_ts(ord+1))
 
   
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
    _start_dt = datetime.date.fromtimestamp(start_ts)
    _stop_date  = datetime.datetime.fromtimestamp(stop_ts)

    _start_month = 12 * _start_dt.year   + _start_dt.month
    _stop_month  = 12 * _stop_date.year  + _stop_date.month

    if (_stop_date.day, _stop_date.hour, _stop_date.minute, _stop_date.second) == (1,0,0,0):
        _stop_month -= 1

    for month in range(_start_month, _stop_month+1):
        _this_yr, _this_mo = divmod(month,   12)
        _next_yr, _next_mo = divmod(month+1, 12)
        yield timespan.TimeSpan(time.mktime((_this_yr, _this_mo, 1, 0, 0, 0, 0, 0, -1)),
                                time.mktime((_next_yr, _next_mo, 1, 0, 0, 0, 0, 0, -1)))

def genYearSpans(start_ts, stop_ts):
    _start_date = datetime.date.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_year = _start_date.year
    _stop_year  = _stop_dt.year
    
    if(_stop_dt.month, _stop_dt.day, _stop_dt.hour,
       _stop_dt.minute, _stop_dt.second) == (1,1,0,0,0):
        _stop_year -= 1
        
    for year in range(_start_year, _stop_year + 1):
        yield timespan.TimeSpan(time.mktime((year,   1, 1, 0, 0, 0, 0, 0, -1)),
                                time.mktime((year+1, 1, 1, 0, 0, 0, 0, 0, -1)))
        
def startOfDay(time_ts):
    """Calculate the unix epoch time for the start of a (local time) day.
    
    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_tt = time.localtime(time_ts)
    _bod_ts  = time.mktime((_time_tt.tm_year, 
                            _time_tt.tm_mon,
                            _time_tt.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return int(_bod_ts)


def startOfArchiveDay(time_ts):
    """Given an archive time stamp, calculate its start of day.
    
    similar to startOfDay(), except that an archive stamped at midnight
    actually belongs to the *previous* day.

    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_dt = datetime.datetime.fromtimestamp(time_ts)
    if (_time_dt.hour, _time_dt.minute, _time_dt.second) == (0, 0, 0):
        _time_dt -= datetime.timedelta(days=1)
    _time_tt = _time_dt.timetuple()
    _bod_ts  = time.mktime((_time_tt.tm_year, 
                            _time_tt.tm_mon,
                            _time_tt.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return int(_bod_ts)

    
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

if __name__ == '__main__':
    print "********* genYearSpans ***********"
    print "Should print years 2007 through 2008:"
    start_ts = time.mktime((2007, 12,  3, 10, 15, 0, 0, 0, -1))
    stop_ts  = time.mktime((2008, 03,  1, 0, 0, 0, 0, 0, -1))

    for span in genYearSpans(start_ts, stop_ts):
        print span
        
    print "********* genMonthSpans ***********"
    print "Should print months 2007-12 through 2008-02:"
    start_ts = time.mktime((2007, 12,  3, 10, 15, 0, 0, 0, -1))
    stop_ts  = time.mktime((2008, 03,  1, 0, 0, 0, 0, 0, -1))

    for span in genMonthSpans(start_ts, stop_ts):
        print span

    print "\nShould print months 2007-12 through 2008-03:"
    start_ts = time.mktime((2007, 12,  3, 10, 15, 0, 0, 0, -1))
    stop_ts  = time.mktime((2008, 03,  1, 0, 0, 1, 0, 0, -1))

    for span in genMonthSpans(start_ts, stop_ts):
        print span
    print "********** genDaySpans ************"
    
    print "Should print 2007-12-23 to 2008-1-6:"
    start_ts = time.mktime((2007, 12, 23, 10, 15, 0, 0, 0, -1))
    stop_ts  = time.mktime((2008,  1,  5,  9, 22, 0, 0, 0, -1))
    for span in genDaySpans(start_ts, stop_ts):
        print span
    print "\nShould print the single date 2007-12-1:"
    for span in genDaySpans( time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                             time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1))):
        print span

    print "******** daySpan ***************"
    print daySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)))

    print "******** weekSpan ***************"
    print weekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)))

    print "******** monthSpan ***************"
    print monthSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)))

    print "******** yearSpan ***************"
    print yearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)))

    print "******** rainYearSpan ***************"
    print rainYearSpan(time.mktime((2007,  2, 13, 10, 15, 0, 0, 0, -1)), 10)
    print rainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 10)

    print "******** Start-of-days **********"
    
    # Test start-of-day routines around a DST boundary:
    start_ts = time.mktime((2007, 03, 11, 01, 0, 0, 0, 0, -1))
    start_of_day = startOfDay(start_ts)
    nextDay = startOfNextInterval(start_of_day, 24*3600)
    start2 = startOfArchiveDay(start_of_day)
    print timestamp_to_string(start_ts)
    print timestamp_to_string(start_of_day)
    print timestamp_to_string(nextDay)
    print timestamp_to_string(start2)
    # Check that this is, in fact, a DST boundary:
    assert((nextDay - start_of_day) == 23*3600)
    assert(start_of_day == int(time.mktime((2007, 03, 11, 0, 0, 0, 0, 0, -1))))
    assert(nextDay      == int(time.mktime((2007, 03, 12, 0, 0, 0, 0, 0, -1))))
    assert(start2       == int(time.mktime((2007, 03, 10, 0, 0, 0, 0, 0, -1))))
    
