#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Compute statistics, manage the statistical database

    Keeps a running tally in a database of the min, max, avg of weather data
    for each day. Also, keeps some specialized data for wind.

    General strategy is that archive data is used for min, max data and
    for averages (including wind vector averages). Fast changing LOOP
    data is also used for min, max data (where it can give higher resolution)
    and for specialized, wind rms data. It is not used for averages. 
    
    The advantage of this approach is that LOOP data is easy to miss --- neither
    the weather station nor weewx stores it. By contrast, archived data is stored, so
    it's easy to perform catchups. It's generally preferred to use it, and
    for many types it's good enough. On the other hand, LOOP has much better
    resolution, and is essential for RMS calculations.
    
    Note that a date does not include midnight --- that belongs
    to the previous day. That is because a data record archives
    the *previous* interval. So, for the date 5-Oct-2008 with
    a five minute archive interval, the statistics would include
    the following records (local time):
      5-Oct-2008 00:05:00
      5-Oct-2008 00:10:00
      5-Oct-2008 00:15:00
      .
      .
      .
      5-Oct-2008 23:55:00
      6-Oct-2008 00:00:00
"""

from __future__ import with_statement
import math
import time
import datetime
import calendar
import os
import os.path
import syslog
from pysqlite2 import dbapi2 as sqlite3

import weewx
import weewx.wxformulas
import weeutil.weeutil

#===============================================================================
# The default types for which statistical data should be kept in the
# SQL stats database. This list is used only if the user has not
# specified anything in the configuration file. Note that this default
# list includes pretty much all possible types, which can result in a
# much bigger than necessary stats database.
#
# Types 'heatdeg' and 'cooldeg' are special because they are actually calculated
# and not stored in the database.
# ===============================================================================
default_stats_types = ('barometer',
                       'inTemp',
                       'outTemp',
                       'inHumidity',
                       'outHumidity',
                       'rainRate',
                       'rain',
                       'dewpoint',
                       'windchill',
                       'heatindex',
                       'ET',
                       'radiation',
                       'UV',
                       'extraTemp1',
                       'extraTemp2',
                       'extraTemp3',
                       'soilTemp1',
                       'soilTemp2',
                       'soilTemp3',
                       'soilTemp4',
                       'leafTemp1',
                       'leafTemp2',
                       'extraHumid1',
                       'extraHumid2',
                       'soilMoist1',
                       'soilMoist2',
                       'soilMoist3',
                       'soilMoist4',
                       'leafWet1',
                       'leafWet2',
                       'rxCheckPercent',
                       'wind',
                       'heatdeg',
                       'cooldeg')

std_create_str  = """CREATE TABLE %s   ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                  """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER);"""

wind_create_str = """CREATE TABLE wind ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                  """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, """\
                  """gustdir REAL, xsum REAL, ysum REAL, squaresum REAL, squarecount INTEGER);"""

meta_create_str = """CREATE TABLE metadata (name TEXT NOT NULL UNIQUE PRIMARY KEY, value TEXT);"""
                 
std_replace_str  = """REPLACE INTO %s   VALUES(?, ?, ?, ?, ?, ?, ?)"""
wind_replace_str = """REPLACE INTO wind VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
meta_replace_str = """REPLACE into metadata VALUES(?, ?)"""  


#===============================================================================
#                    Class StdDayStats
#===============================================================================

class StdDayStats(object):
    """Holds daily statistics (min, max, avg, etc.) for a type.
    
    For a given type ('outTemp', 'wind', etc.), keeps track of the min and max
    encountered and when. It also keeps a running sum and count, so averages can
    be calculated.""" 
    def __init__(self, type, sod_ts, stats_seq = None):
        """Initialize an instance for type 'type' with default values.
        
        type: A string containing the SQL type (e.g., 'outTemp', 'rain', etc.)
        
        sod_ts: The start-of-day. Must not be None

        stats_seq: An iterable holding the initialization values in the same order
        as the stats SQL database:
            (dateTime, min, mintime, max, maxtime, sum, count)
        Note that the first value (dateTime) is not used. Instead, the value sod_ts in
        the parameter list is used. 
        [Optional. If not given, the instance will be initialized to starting values]"""
        
        if weewx.debug:
            # Make sure we have, in fact, been handed the start-of-day:
            assert(sod_ts == weeutil.weeutil.startOfDay(sod_ts))
        self.type = type
        self.dateTime = sod_ts
        self.setStats(stats_seq)

    def addToHiLow(self, rec):
        """Add a new record to the running hi/low tally for my type.
        
        rec: A dictionary holding a record. The dictionary keys are
        measurement types (eg 'outTemp') and the values the
        corresponding values. The dictionary must have value
        'dateTime'. It may or may not have my type in it. If it does,
        the value for my type is extracted and used to update my
        high/lows.  If it does not, nothing is done."""
        # Heating and cooling degree-days don't accumulate within a day:
        if self.type in ('heatdeg', 'cooldeg'):
            return
        val = rec.get(self.type)
        # NB: val could be None because either there is no data for
        # this type, or this type doesn't exist at all in the record.
        if val is None :
            return
        if self.min is None or val < self.min:
            self.min = val
            self.mintime = rec['dateTime']
        if self.max is None or val > self.max:
            self.max = val
            self.maxtime = rec['dateTime']
    
    def addToSum(self, rec):
        """Add a new record to the running sum and count for my type.
        
        rec: A dictionary holding a record. The dictionary keys are
        measurement types (eg 'outTemp') and the values the
        corresponding values. The dictionary may or may not have my
        type in it. If it does, the value for my type is extracted and
        used to update my sum and count. If it does not, nothing is
        done."""
        # Heating and cooling degree-days don't accumulate within a day:
        if self.type in ('heatdeg', 'cooldeg'):
            return
        val = rec.get(self.type)
        # NB: val could be None because either there is no data for
        # this type, or this type doesn't exist at all in the record.
        if val is None:
            return
        self.sum += val
        self.count += 1

        
    def addArchiveRecord(self, rec):
        """Add a new archive record to the hi/lo and summation data.
        
        rec: A dictionary holding an archive record. The type will be extracted
        from it. Must also have type 'dateTime'. """
        # Archive data is used for the Hi/Low data, as well as averages.
        self.addToHiLow(rec)
        self.addToSum(rec)
        
    def addLoopRecord(self, rec):
        """Add a new LOOP record to the hi/lo stats.
        
        rec: A dictionary holding an archive record. The type will be extracted
        from it. Must also have type 'dateTime'."""
        # A LOOP record is used only for Hi/Low data for standard stats.
        self.addToHiLow(rec)

    def get_avg(self):
        """Calculate average"""
        return self.sum / self.count if self.count else None
    
    # This will make avg available as an attribute:
    avg = property(get_avg)

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the
        gathered statistics.  The results are in the same order as the
        schema, making it easy to use in an SQL statement"""
        return (self.dateTime, self.min, self.mintime, self.max, self.maxtime, self.sum, self.count)
    
    def setStats(self, stats_seq):
        """Set self to the values in an iterable.
        
        stats_seq: an iterable sequence. The instance will be set to these values.
        Note that the ordering is the same as the schema, i.e., 
        (dateTime, min, mintime, max, maxtime, sum, count). The value dateTime is
        not used."""
        if not stats_seq:
            stats_seq = (None, None, None, None, None, 0.0 , 0)
        (self.min,
         self.mintime,
         self.max,
         self.maxtime,
         self.sum,
         self.count) = stats_seq[1:]
         
    
    def __str__(self):
        """Return self as a string. Useful for diagnostics & debugging."""
        time_str = weeutil.weeutil.timestamp_to_string(self.dateTime)
        min_str = "%f" % self.min if self.min is not None else "N/A"
        max_str = "%f" % self.max if self.max is not None else "N/A"
        mintime_str = weeutil.weeutil.timestamp_to_string(self.mintime)
        maxtime_str = weeutil.weeutil.timestamp_to_string(self.maxtime)
        avg_str = "%f" % self.avg if self.avg is not None else "N/A"
        sum_str = "%f" % self.sum if self.sum is not None else "N/A"
        return "time = %s; type = %s; min = %s (%s); max = %s (%s); avg = %s; sum = %s; " % \
            (time_str, self.type, min_str, mintime_str, max_str, maxtime_str, avg_str, sum_str) 


#===============================================================================
#                    Class WindDayStats
#===============================================================================

class WindDayStats(StdDayStats):
    """Specialized version of StdDayStats to be used for wind data. 
    
    It includes some extra statistics such as gust direction, rms speeds, etc."""
    def __init__(self, type, sod_ts, stats_seq = None):
        """Initialize an instance for type 'type'.
        
        type: A string containing the SQL type (must be 'wind' for this version)
        
        sod_ts: The start-of-day. Must not be None

        stats_seq: An iterable holding the initialization values in the same order
        as the stats SQL database:
            (dateTime, min, mintime, max, maxtime, sum, count,
            gustdir, xsum, ysum, squaresum, squarecount)
        Note that the first value (dateTime) is not used. Instead, the value sod_ts in
        the parameter list is used."""

        assert(stats_seq is None or len(stats_seq) == 12)
        StdDayStats.__init__(self, type, sod_ts, stats_seq)

    def addToHiLow(self, rec):
        """Specialized version for wind data. It differs from
        the standard addToHiLow in that it takes advantage of 
        wind gust data if it's available. It also keeps track
        of the *direction* of the high wind, as well as its time 
        and magnitude."""
        # Sanity check:
        assert(self.type == 'wind')
        # Get the wind speed & direction, breaking them down into vector
        # components.
        v      = rec.get('windSpeed')
        vHi    = rec.get('windGust')
        vHiDir = rec.get('windGustDir')
        if vHi is None:
            # This typically happens because a LOOP packet is being added, which
            # does not have windGust data.
            vHi    = v
            vHiDir = rec.get('windDir')

        if v is not None and (self.min is None or v < self.min):
            self.min = v
            self.mintime = rec['dateTime']
        if vHi is not None and (self.max is None or vHi > self.max):
            self.max = vHi
            self.maxtime = rec['dateTime']
            self.gustdir = vHiDir
    
    def addToSum(self, rec):
        """Specialized version for wind data. It differs from
        the standard addToSum in that it calculates a vector
        average as well."""
        # Sanity check:
        assert(self.type == 'wind')
        # Get the wind speed & direction, breaking them down into vector
        # components.
        speed = rec.get('windSpeed')
        theta = rec.get('windDir')
        if speed is not None:
            self.sum   += speed
            self.count += 1
            if theta is not None :
                self.xsum      += speed * math.cos(math.radians(90.0 - theta))
                self.ysum      += speed * math.sin(math.radians(90.0 - theta))
    
    def addToRms(self, rec):
        """Add a record to the wind-specific rms stats"""
        # Sanity check:
        assert(self.type == 'wind')
        speed = rec.get('windSpeed')
        if speed is not None:
            self.squaresum   += speed**2
            self.squarecount += 1

    def addLoopRecord(self, rec):
        """Specialized version for wind data.
        
        Same as the version for StdDayStats, except it also updates the RMS data"""
        self.addToHiLow(rec)
        self.addToRms(rec)

    def get_rms(self):
        return math.sqrt(self.squaresum / self.squarecount) if self.squarecount else None
    def get_vecavg(self):
        return math.sqrt((self.xsum**2 + self.ysum**2) / self.count**2) if self.count else None
    def get_vecdir(self):
        if self.xsum == 0.0 and self.ysum == 0.0:
            return None
        deg = 90.0 - math.degrees(math.atan2(self.ysum, self.xsum))
        return deg if deg > 0 else deg + 360.0
    
    # This will make rms, vecavg, and vecdir available as attributes:
    rms    = property(get_rms)
    vecavg = property(get_vecavg)
    vecdir = property(get_vecdir)

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics.
        The results are in the same order as the schema, making it easy
        to use in an SQL statement."""
        return (StdDayStats.getStatsTuple(self) +
                (self.gustdir, self.xsum, self.ysum, self.squaresum, self.squarecount))
        
    def setStats(self, stats_seq):
        """Set self to the values in an iterable.
        
        stats_seq: an iterable sequence. The instance will be set to
        these values.  Note that the ordering is the same as the
        schema, i.e., (dateTime, min, mintime, max, maxtime, sum, count,
        gustdir, xsum, ysum, squaresum, squarecount)"""

        if not stats_seq:
            stats_seq = (None, None, None, None, None, 0.0 , 0,
                         None, 0.0, 0.0, 0.0, 0)

        # First set the superclass,
        StdDayStats.setStats(self, stats_seq[:7])
        # Then initialize the specialized data:
        (self.gustdir,
         self.xsum,
         self.ysum,
         self.squaresum,
         self.squarecount) = stats_seq[7:]

    def __str__(self):
        """Return self as a string. Useful for diagnostics and debugging."""
        rms_str = "%f" % self.rms if self.rms is not None else "N/A"
        vecavg_str = "%f" % self.vecavg if self.vecavg is not None else "N/A"
        vecdir_str = "%f" % self.vecdir if self.vecdir is not None else "N/A"
        return super(WindDayStats, self).__str__() + "; rms = %s; vecavg = %s; vecdir = %s " % (rms_str, vecavg_str, vecdir_str)


#===============================================================================
#                    Class DayStatsDict
#===============================================================================

class DayStatsDict(dict):
    """Statistics for a day, keyed by type.

    The key of the dictionary is a type ('outTemp', 'barometer',
    etc.), the value an instance of WindDayStats for type 'wind',
    otherwise an instance of StdDayStats

    ATTRIBUTES: 
    self.timespan: The time period this instance covers.

    self.dateTime: The start of the time period this instance covers.
    (by definition, equal to self.timespan.start)"""
    
    def __init__(self, type_seq, day_span):
        """Create from a sequence of types, and from a time span.

        type_seq: An iterable sequence of types ('outTemp',
        'barometer', etc.). These will be the keys of the dictionary

        day_span: An instance of weeutil.timespan.Timespan with the
        time period this instance will cover.

        returns: An instance of DayStatsDict where the value for each
        type has been initialized to 'default' values."""

        if weewx.debug:
            # Make sure the span that has been handed to us is, in fact, a
            # day span:
            assert(day_span.start == weeutil.weeutil.startOfDay(day_span.start))
            assert(day_span == weeutil.weeutil.daySpan(day_span.start))
        self.timespan = day_span
        self.dateTime = day_span.start
        
        for type in type_seq:
            if type == 'wind':
                self[type] = WindDayStats(type, day_span.start)
            else:
                self[type] = StdDayStats(type, day_span.start)

    def __str__(self):
        outTempStats = self['outTemp']
        outTempMin_str = str(outTempStats.min) if outTempStats.min is not None else "N/A"
        outTempMax_str = str(outTempStats.max) if outTempStats.max is not None else "N/A"
        return "time span: %s; temperature (min,max) = (%s, %s)" % (str(self.timespan), outTempMin_str, outTempMax_str)

#===============================================================================
#                    Class AggregateStatsDict
#===============================================================================

class AggregateStatsDict(object):
    """Statistics for an aggregate period, such as a week, month, year, keyed by type.

    This class has a very similar interface to DayStatsDict, except it
    represents statistics for an aggregate period, rather than just a
    single day.

    ATTRIBUTES:
    self.statsTypes: A list of types that can be used as a key.

    self.days: A list of DayStatsDicts, one for each day in the aggregate period.
    
    self.timespan: The time period this instance covers.

    self.dateTime: The start time this instance covers (by definition,
    equal to self.timespan.start
    """
    
    def __init__(self, statsTypes, day_list, timespan):
        """Initialize from a list of stats
        
        statsTypes: A list of types to be used as keys (eg, 'outTemp',
        'barometer', 'heatdeg', etc.)

        day_list: A list of DayStatsDicts sufficient to cover the timespan.

        timespan: A weeutil.timespan.TimeSpan object for the length of
        time this instance covers."""

        if weewx.debug:
            _istart = datetime.date.fromtimestamp(timespan.start).toordinal()
            _iend   = datetime.date.fromtimestamp(timespan.stop).toordinal()
            _Ndays  = _iend - _istart
            if len(day_list) != _Ndays:
                raise weewx.ViolatedPrecondition, "Timespan (%d days) does not match length of day list (%d) " (_Ndays, len(day_list))
        self.statsTypes = statsTypes
        self.days       = day_list
        self.timespan   = timespan
        self.dateTime   = timespan.start

    def __getitem__(self, type):
        """Returns the helper class SummaryStats, initialized with the list 
        of children and the type."""

        # The following check is to get around a quirk in Cheetah, where it goes
        # looking for attribute 'days' in _getitem__ instead of
        # trying attributes first. We throw an exception if the
        # proferred type is not in the list of acceptable types.
        if type not in self.statsTypes:
            raise KeyError, type
        
        return SummaryStats(self.days, self.timespan, type)
    

#===============================================================================
#                    Class MonthStatsDict
#===============================================================================

class MonthStatsDict(AggregateStatsDict):
    
    def __init__(self, statsTypes, day_list, monthSpan):
        AggregateStatsDict.__init__(self, statsTypes, day_list, monthSpan)
        
#===============================================================================
#                    Class YearStatsDict
#===============================================================================

class YearStatsDict(AggregateStatsDict):
    """Statistics for a year
    
    To the methods and attributes offered by the base class AggregateStatsDict,
    this class adds an attribute self.months.

    ATTRIBUTES:
    self.statsTypes: A list of types that can be used as a key.

    self.days: A list of DayStatsDicts, one for each day in the year.
    
    self.months: A list of MonthStatsDicts, one for each month in the year.
    
    self.timespan: The time period this instance covers.

    self.dateTime: The start time this instance covers (by definition,
    equal to self.timespan.start
    """
    
    def __init__(self, statsTypes, day_list, yearSpan):
        """Initialize an instance using a list of days

        Note that the year need not be a calendar year (e.g., it could
        be a rain year). The only requirement is that the list of days
        be long enough to cover the timespan.
    
        statsTypes: A list of types to be used as keys (eg, 'outTemp',
        'barometer', 'heatdeg', etc.)

        day_list: A list of DayStatsDicts sufficient to cover the year.

        timespan: A weeutil.timespan.TimeSpan object for the year"""
        
        AggregateStatsDict.__init__(self, statsTypes, day_list, yearSpan)

        # The logic in what follows is arranged so that the year can represent
        # a rain year, as well as a calendar year. That is, the first month
        # need not be January. The only requirement is that day_list be long
        # enough to cover the time period.
        self.months = []
        _start_date = datetime.date.fromtimestamp(yearSpan.start)
        _start_ordinal = _start_date.toordinal()
        for _monthSpan in weeutil.weeutil.genMonthSpans(yearSpan.start, yearSpan.stop):
            _month_start = datetime.date.fromtimestamp(_monthSpan.start)
            _index = _month_start.toordinal() - _start_ordinal
            if weewx.debug:
                if _monthSpan.start != self.days[_index].dateTime:
                    raise weewx.LogicError, "Month start %s does not match day start %s" % (weeutil.weeutil.timestamp_to_string(_monthSpan.start),
                                                                                            weeutil.weeutil.timestamp_to_string(self.days[_index].dateTime))

            _days_in_month = calendar.monthrange(_month_start.year, _month_start.month)[1]
            self.months.append(MonthStatsDict(statsTypes, self.days[_index:_index+_days_in_month], _monthSpan))

#===============================================================================
#                    Class SummaryStats
#===============================================================================

class SummaryStats(object):
    """Helper object to return summary stats from lists of statistics.
    
    It is nearly stateless, and intended to be used as a helper class.
    That is, it is typically returned from a method or as an
    attribute, helping link the calling class with the attribute.
    
    It offers a variety of aggregate statistics, calculated dynamically."""

    def __init__(self, day_list, timespan, type):
        self.days     = day_list
        self.timespan = timespan
        self.type     = type
        self.dateTime = timespan.start
        
    #===============================================================================
    # What follows is a long list of aggregate statistics that this
    # class can offer. They are all calculated dynamically, using generator 
    # expressions
    # ===============================================================================

    def get_min(self):
        vmin_tuple = weeutil.weeutil.min_no_None( (dayStats[self.type].min,) for dayStats in self.days )
        return vmin_tuple[0] if vmin_tuple is not None else None

    def get_mintime(self):
        vmin_tuple = weeutil.weeutil.min_no_None( (dayStats[self.type].min, dayStats[self.type].mintime) for dayStats in self.days )
        return vmin_tuple[1] if vmin_tuple is not None else None

    def get_max(self):
        vmax_tuple = weeutil.weeutil.max_no_None( (dayStats[self.type].max, ) for dayStats in self.days )
        return vmax_tuple[0] if vmax_tuple is not None else None

    def get_maxtime(self):
        vmax_tuple = weeutil.weeutil.max_no_None( (dayStats[self.type].max, dayStats[self.type].maxtime) for dayStats in self.days )
        return vmax_tuple[1] if vmax_tuple is not None else None

    def get_sum(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].sum for dayStats in self.days )
    
    def get_count(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].count for dayStats in self.days )
    
    def get_avg(self):
        vcount = self.count
        return self.sum / vcount if vcount else None
    
    def get_gustdir(self):
        vmax_tuple = weeutil.weeutil.max_no_None( (dayStats[self.type].max, dayStats[self.type].gustdir) for dayStats in self.days )
        return vmax_tuple[1] if vmax_tuple is not None else None

    def get_xsum(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].xsum for dayStats in self.days )
    
    def get_ysum(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].ysum for dayStats in self.days )
    
    def get_squaresum(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].squaresum for dayStats in self.days )
    
    def get_squarecount(self):
        return weeutil.weeutil.sum_no_None( dayStats[self.type].squarecount for dayStats in self.days )

    def get_rms(self):
        return math.sqrt(self.squaresum / self.squarecount) if self.squarecount else None
    
    def get_vecavg(self):
        return math.sqrt((self.xsum**2 + self.ysum**2) / self.count**2) if self.count else None
    
    def get_vecdir(self):
        deg = 90.0 - math.degrees(math.atan2(self.ysum, self.xsum))
        return deg if deg > 0 else deg + 360.0
    
    def get_meanmax(self):
        return weeutil.weeutil.mean_no_None( dayStats[self.type].max for dayStats in self.days )

    def get_meanmin(self):
        return weeutil.weeutil.mean_no_None( dayStats[self.type].min for dayStats in self.days )
    
    def get_maxsum(self):
        vmax_tuple = weeutil.weeutil.max_no_None( (dayStats[self.type].sum, ) for dayStats in self.days )
        return vmax_tuple[0] if vmax_tuple is not None else None
    
    def get_maxsumtime(self):
        vmax_tuple = weeutil.weeutil.max_no_None( (dayStats[self.type].sum, dayStats.dateTime) for dayStats in self.days )
        return vmax_tuple[1] if vmax_tuple is not None else None
    
    # These property statements will make all these functions available as attributes:
    min          = property(get_min)
    max          = property(get_max)
    mintime      = property(get_mintime)
    maxtime      = property(get_maxtime)
    sum          = property(get_sum)
    count        = property(get_count)
    avg          = property(get_avg)
    gustdir      = property(get_gustdir)
    xsum         = property(get_xsum)
    ysum         = property(get_ysum)
    squaresum    = property(get_squaresum)
    squarecount  = property(get_squarecount)
    rms          = property(get_rms)
    vecavg       = property(get_vecavg)
    vecdir       = property(get_vecdir)
    meanmax      = property(get_meanmax)
    meanmin      = property(get_meanmin)
    maxsum       = property(get_maxsum)
    maxsumtime   = property(get_maxsumtime)
    
    def max_ge(self, val):
        return len(filter(lambda x : x is not None and x>=val, [dayStats[self.type].max for dayStats in self.days]))
    
    def max_le(self, val):
        return len(filter(lambda x : x is not None and x<=val, [dayStats[self.type].max for dayStats in self.days]))
    
    def min_ge(self, val):
        return len(filter(lambda x : x is not None and x>=val, [dayStats[self.type].min for dayStats in self.days]))
    
    def min_le(self, val):
        return len(filter(lambda x : x is not None and x<=val, [dayStats[self.type].min for dayStats in self.days]))
    
    def sum_ge(self, val):
        return len(filter(lambda x : x>=val, [dayStats[self.type].sum for dayStats in self.days]))

#===============================================================================
#                    Class StatsDb
#===============================================================================

class StatsDb(object):
    """Manage the sqlite3 statistical database. 
    
    This class acts as a wrapper around the stats database, with a set
    of methods for adding and retrieving records to and from the
    statistical compilation. It also offers methods to retrieve data
    by day, week, month year, etc.

    After initialization, the attribute self.statsTypes will contain a list
    of the types for which statistics are being gathered, or None if
    the database has not been initialized. This can be used to determine
    whether this is a virgin database.
    
    As for the SQL database itself, it consists of a separate table for each
    type. The columns of a table are things like min, max, the timestamps for
    min and max, count and sum. A count and sum are kept to make it easy to
    calculate averages for different time periods.  The wind data table also
    includes sum of squares (for calculating rms speeds) and wind gust
    direction.
    
    For example, for type 'outTemp' (outside temperature), there is 
    a table of name 'outTemp' with the following column names:
    
        dateTime, min, mintime, max, maxtime, sum, count
        
    Wind data is similar (table name 'wind'), except it adds a few extra columns:
    
        dateTime, min, mintime, max, maxtime, sum, count, 
          gustdir, xsum, ysum, squaresum, squarecount
    
    'xsum' and 'ysum' are the sums of the x- and y-components of the wind vector.
    'squaresum' is the sum of squares of the windspeed (useful for calculating rms speed).
    'squarecount' is the number of items added to 'squaresum'.
    
    In addition to all the tables for each type, there is also a separate table
    called 'metadata'. Currently, it only holds the time of last update, but more could
    be added later.
    
    ATTRIBUTES
    
    statsFilename: The path to the stats database
    
    statsTypes: The types of the statistics supported by this instance of
    StatsDb. None if the database has not been initialized.
    
    heatbase:The base temperature for calculating heating degree-days.

    coolbase: The base temperature for calculating cooling degree-days.
    """
    
    # In addition to the attributes listed above, if caching is used,
    # each instance has a private attribute self.__dayCache. This is a two-way 
    # tuple where the first member is an instance of DayStatsDict, and
    # the second member is lastUpdate. If caching is not being used, then
    # self.__dayCache equals None.
    #
    def __init__(self, statsFilename, heatbase = None, coolbase = None, cacheLoopData = True):
        """Create an instance of StatsDb to manage a database.
        
        statsFilename: Path to the stats database file.
        
        heatbase: The base degrees for calculating heating degree-days

        coolbase: The base degrees for calculating cooling degree-days
        
        cacheLoopData: True if LOOP data is to be cached and written only when
        new archive data comes in. Otherwise, it gets written with the arrival
        of every LOOP packet. [Optional. Default is True]"""
        self.statsFilename = statsFilename
        self.statsTypes    = StatsDb.__getTypes(statsFilename)
        self.heatbase      = heatbase
        self.coolbase      = coolbase
        if cacheLoopData:
            self.__dayCache  = (None, None)
        else:
            self.__dayCache  = None
        
    def addArchiveRecord(self, rec):
        """Add an archive record to the statistical database."""

        # Get the start-of-day for this archive record.
        _sod_ts = weeutil.weeutil.startOfArchiveDay(rec['dateTime'])

        _daySpan = weeutil.weeutil.daySpan(_sod_ts)
        _allStatsDict = self.day(_daySpan)

        for type in self.statsTypes:
            # ... and add this archive record to the running tally:
            _allStatsDict[type].addArchiveRecord(rec)

        # Now write the results for all types back to the database
        # in a single transaction:
        self._setDay(_allStatsDict, rec['dateTime'], writeThrough = True)
            
    def addLoopRecord(self, rec):
        """Add a LOOP record to the statistical database."""

        # Get the start-of-day for this loop record.
        _sod_ts = weeutil.weeutil.startOfArchiveDay(rec['dateTime'])

        _daySpan = weeutil.weeutil.daySpan(_sod_ts)
        _allStatsDict = self.day(_daySpan)

        for type in self.statsTypes:
            # ... and add this loop record to the running tally:
            _allStatsDict[type].addLoopRecord(rec)

        # Now write the results for all types back to the database
        # in a single transaction:
        self._setDay(_allStatsDict, rec['dateTime'], writeThrough = False)

    def getTypeStats(self, type, sod_ts, cursor = None):
        """Get the statistics for a specific type for a specific day.

        type: The type of data to retrieve ('outTemp', 'barometer', 'wind',
        'heatdeg', etc.)

        sod_ts: The timestamp of the start-of-day for the desired day.

        cursor: A database cursor to be used for the
        retrieval. [Optional. If not given, one will be created and
        destroyed for this query.]

        returns: an instance of WindDayStats for type 'wind',
        otherwise an instance of StdDayStats, initialized with the
        data from the database. If the record doesn't exist in the
        database, the returned instance will be set to 'default'
        values (generally, min==None, count=0, etc.)"""
        
        if type in ('heatdeg', 'cooldeg'):
            return self.__toHeatCool(type, self.getTypeStats('outTemp', sod_ts, cursor))

        if cursor:
            _cursor = cursor
        else:
            _connection = sqlite3.connect(self.statsFilename)
            _cursor = _connection.cursor()

        try:
            # Form a SQL select statement for the appropriate type
            _sql_str = "SELECT * FROM %s WHERE dateTime = ?" % type
            # Peform the select, against the desired timestamp
            _cursor.execute(_sql_str, (sod_ts,))
            # Get the result
            _row = _cursor.fetchone()
    
            if weewx.debug:
                if _row:
                    if type =='wind': assert(len(_row) == 12)
                    else: assert(len(_row) == 7)
    
            # The date may not exist in the database, in which case _row will
            # be 'None', causing either StdDayStats or WindDayStats
            # to initialize to default values.
            _dayStats = StdDayStats(type, sod_ts, _row) if type != 'wind' else WindDayStats(type, sod_ts, _row)

        finally:

            if not cursor:
                _cursor.close()
                _connection.close()
        
        return _dayStats

        
    def genTypeStats(self, type, span, cursor = None):
        """Generator function that returns day statistics for a specified type between two timestamps.
        
        This function can be much faster than calling getTypeStats()
        repeatedly.  It creates a connection just once, and shares it
        between all calls to the stats database. However, the
        semantics differs slightly from calling getTypeStats()
        repeatedly in that it only returns instances that exist in the
        database.
        
        type: The type of data to retrieve ('outTemp', 'barometer',
        'heatdeg', etc.)

        span: An instance of weeutil.timespan.Timespan with the time
        span over which the instances will be returned. It is
        inclusive on the left, exclusive on the right.

        cursor: A database cursor to be used for the
        retrieval. [Optional. If not given, one will be created and
        destroyed for this query.]

        yields: Instances of WindDayStats for type 'wind', otherwise
        instances of StdDayStats, initialized with the data from the
        database. Only records that exist in the database will be
        returned!"""

        if type in ('heatdeg', 'cooldeg'):
            for outTempStats in self.genTypeStats('outTemp', span, cursor):
                yield self.__toHeatCool(type, outTempStats)
            return

        if cursor:
            _cursor = cursor
        else:
            _connection = sqlite3.connect(self.statsFilename)
            _cursor = _connection.cursor()

        try:
            # Form a SQL select statement for the appropriate type
            _sql_str = "SELECT * FROM %s WHERE dateTime >= ? and dateTime < ?" % type
            # Peform the select, against the desired range of timestamp
            _cursor.execute(_sql_str, (span.start, span.stop))
            
            for _row in _cursor:
    
                if weewx.debug:
                    # In this case, the cursor row must exist (or we would not have continued in the loop)
                    assert(_row)
                    if type =='wind': assert(len(_row) == 12)
                    else: assert(len(_row) == 7)
    
                _dayStats = StdDayStats(type, _row[0], _row) if type != 'wind' else WindDayStats(type, _row[0], _row)
    
                yield _dayStats

        finally:

            if not cursor:
                _cursor.close()
                _connection.close()

    def day(self, daySpan, cursor = None):
        """Return an instance of DayStatsDict initialized to a given day's statistics.

        daySpan: An instance of weeutil.timespan.Timespan with the
        time span for the desired day.

        cursor: A database cursor to be used for the
        retrieval. [Optional. If not given, one will be created and
        destroyed for this query.]"""
        
        if self.__dayCache and self.__dayCache[0] and self.__dayCache[0].timespan == daySpan:
            return self.__dayCache[0]

        if cursor:
            _cursor = cursor
        else:
            _connection = sqlite3.connect(self.statsFilename)
            _cursor = _connection.cursor()
        
        try:

            _allStats = DayStatsDict(self.statsTypes, daySpan)
            
            for type in self.statsTypes:
                _allStats[type] = self.getTypeStats(type, daySpan.start, _cursor)
        finally:
            if not cursor:
                _cursor.close()
                _connection.close()
        
        if self.__dayCache:
            self.__dayCache = (_allStats, None)

        return _allStats
    
    def week(self, weekSpan):
        """Return a weeks worth of statistics as a AggregateStatsDict.

        weekSpan: An instance of weeutil.timespan.Timespan with the
        time span for the desired week."""
        stats_list = []
        # For each day, create a StatsDict and append it to the day list
        for daySpan in weeutil.weeutil.genDaySpans(weekSpan.start, weekSpan.stop):
            stats_list.append(DayStatsDict(self.statsTypes, daySpan)) 
        # For each type, read in the data for the whole week. Doing it in this order
        # allows us to use the function genTypeStats on a type, which is much
        # faster than getting each individual day, and then each individual type.
        for type in self.statsTypes:
            for dayStats in self.genTypeStats(type, weekSpan):
                for _dayOfWeek in range(len(stats_list)):
                    if dayStats.dateTime == stats_list[_dayOfWeek].timespan.start :
                        # Put it in the right day slot and the right type:
                        stats_list[_dayOfWeek][type] = dayStats
                        break
                
        return AggregateStatsDict(self.statsTypes, stats_list, weekSpan)
    
    def month(self, monthSpan):
        """Return a month's worth of statistics as a MonthStatsDict

        monthSpan: An instance of weeutil.timespan.Timespan with the
        time span for the desired month."""
        _day_list = []
        # For each day, create a StatsDict and append it to the day list
        for _daySpan in weeutil.weeutil.genDaySpans(monthSpan.start, monthSpan.stop):
            _day_list.append(DayStatsDict(self.statsTypes,_daySpan)) 
        # For each _type, read in the data for the whole month. Doing it in this order
        # allows us to use the function genTypeStats on a _type, which is much
        # faster than getting each individual day, and then each individual _type.
        for _type in self.statsTypes:
            for _dayStats in self.genTypeStats(_type,  monthSpan):
                # Figure out which day was just handed to us:
                _day = time.localtime(_dayStats.dateTime).tm_mday
                # Put it in the right day slot and the right _type:
                _day_list[_day-1][_type] =_dayStats
                
        return MonthStatsDict(self.statsTypes, _day_list, monthSpan)
    

    def year(self, yearSpan):
        """Returns a year's worth of statistics as a YearStatsDict.

        yearSpan: An instance of weeutil.timespan.Timespan with the
        time span for the desired year."""
        #TODO: __dayCache current year data because it gets used twice in processdata.py

        # Strategy is to fill in the whole year data structure with default values,
        # then plug in the real values from the SQL search.
        
        # Create a list of default day statistics, one year long:
        _day_list = [DayStatsDict(self.statsTypes, daySpan) for daySpan in weeutil.weeutil.genDaySpans(yearSpan.start, yearSpan.stop)]


        _yr = time.localtime(yearSpan.start)[0]
        _start_ordinal = datetime.date(_yr, 1, 1).toordinal()
        _connection = sqlite3.connect(self.statsFilename)
        _cursor = _connection.cursor()
        
        try:
            # For each type...
            for _type in self.statsTypes:
                # And for each day in the database, retrieve a StdDayStats (or WindDayStats):
                for _typeDayStats in self.genTypeStats(_type, yearSpan, _cursor):
                    # Figure out what  day was just handed to us:
                    _date_ordinal = datetime.date.fromtimestamp(_typeDayStats.dateTime).toordinal()
                    _index = _date_ordinal-_start_ordinal
                    # Put it in the right slot:
                    _day_list[_index][_type] = _typeDayStats
        finally:

            _cursor.close()
            _connection.close()

        return YearStatsDict(self.statsTypes, _day_list, yearSpan)
        
    def config(self, stats_types = None):
        """Initialize the StatsDb database
        
        Does nothing if the database has already been initialized.

        stats_types: an iterable collection with the names of the types for
        which statistics will be gathered [optional. Default is to use all
        possible types]"""
        # Check whether the database exists:
        if os.path.exists(self.statsFilename):
            syslog.syslog(syslog.LOG_INFO, "stats: statistical database %s already exists." % self.statsFilename)
        else:
            # If it doesn't exist, create the parent directories
            archiveDirectory = os.path.dirname(self.statsFilename)
            if not os.path.exists(archiveDirectory):
                syslog.syslog(syslog.LOG_NOTICE, "stats: making archive directory %s." % archiveDirectory)
                os.makedirs(archiveDirectory)
            
        # If it has no schema, initialize it:
        if not self.statsTypes:
            # No schema. Need to initialize the stats database.
            
            # If nothing has been specified, use the default stats types:
            if not stats_types:
                stats_types = default_stats_types
            
            # Now create all the necessary tables as one transaction:
            with sqlite3.connect(self.statsFilename) as _connection:
            
                for _stats_type in stats_types:
                    if _stats_type in ('heatdeg', 'cooldeg'):
                        # Heating and cooling degree days are not actually stored in the database,
                        # but instead are calculated from the daily average temperature
                        continue
                    elif _stats_type == 'wind':
                        _connection.execute(wind_create_str)
                    else:
                        _connection.execute(std_create_str % (_stats_type,))
                _connection.execute(meta_create_str)
            
            self.statsTypes = stats_types
            syslog.syslog(syslog.LOG_NOTICE, "stats: created schema for statistical database %s." % self.statsFilename)


    def _getFirstUpdate(self):
        """Returns the time of the first entry in the statistical database."""
        #=======================================================================
        # This is a bit of a hack because it actually returns the first entry
        # for the barometer, which may or may not be the earliest entry in
        # the stats database.
        #=======================================================================
        with sqlite3.connect(self.statsFilename) as _connection:
            _cursor = _connection.execute("""SELECT min(dateTime) FROM barometer;""")
            _row = _cursor.fetchone()
        return int(_row[0]) if _row else None

    def _getLastUpdate(self):
        """Returns the time of the last update to the statistical database."""

        with sqlite3.connect(self.statsFilename) as _connection:
            _cursor = _connection.execute("""SELECT value FROM metadata WHERE name = 'lastUpdate';""")
            _row = _cursor.fetchone()
        return int(_row[0]) if _row else None


    def _setDay(self, dayStatsDict, lastUpdate, writeThrough = True):
        """Write all statistics for a day to the database in a single transaction.
        
        dayStatsDict: A dictionary. Key is the type to be written, value is a
        StdDayStats or WindDayStats, as appropriate.  Class DayStatsDict
        satisfies this.
        
        lastUpdate: the time of the last update will be set to this. Normally, this
        is the timestamp of the last archive record added to the instance
        dayStatsDict."""

        assert(dayStatsDict)

        if self.__dayCache:
            if self.__dayCache[0] and self.__dayCache[0].timespan != dayStatsDict.timespan:
                # Write the old data
                self.__writeData(self.__dayCache[0], self.__dayCache[1])
        
            self.__dayCache = (dayStatsDict, lastUpdate)
            if writeThrough:
                self.__writeData(dayStatsDict, lastUpdate)
        
        else:
            self.__writeData(dayStatsDict, lastUpdate)
        
        
    def __writeData(self, dayStatsDict, lastUpdate):
        
        assert(dayStatsDict)
        assert(lastUpdate)
        
        _sod = dayStatsDict.timespan.start

        # Using the connection as a context manager means that
        # in case of an error, all tables will get rolled back.
        with sqlite3.connect(self.statsFilename) as _connection:
            for _stats_type in self.statsTypes:
                
                # Heating and cooling degree days are calculated on demand, not
                # stored in the database:
                if _stats_type in ('heatdeg', 'cooldeg'):
                    continue
                # Slightly different SQL statement for wind
                elif _stats_type == 'wind':
                    _replace_str = wind_replace_str
                else:
                    _replace_str = std_replace_str % _stats_type
                
                # Get the stats-tuple, then write the results
                _write_tuple = dayStatsDict[_stats_type].getStatsTuple()
                assert(_write_tuple[0] == _sod)
                _connection.execute(_replace_str,_write_tuple)
            # Update the time of the last stats update:
            _connection.execute(meta_replace_str, ('lastUpdate', str(int(lastUpdate))))
            
    def __toHeatCool(self, type, outTempStats):
        """Calculates heating or cooling degree-day statistics from temperature
        
        type: Either 'heatdeg' or 'cooldeg'
        
        outTempStats: An instance of StdDayStats for type 'outTemp'
        
        returns: If attribute outTempStats.avg is not None, returns an instance of
        StdDayStats where min, max, and sum are set to the heating or cooling
        degree-day value. Otherwise, returns a default instance.
        """
        assert(type in ('heatdeg', 'cooldeg'))
        assert(outTempStats.type == 'outTemp')
        _avgtemp = outTempStats.avg
        _sod_ts  = outTempStats.dateTime
        if _avgtemp is not None:
            if type == 'heatdeg':
                _degs = weewx.wxformulas.heating_degrees(_avgtemp, self.heatbase)
            else:
                _degs = weewx.wxformulas.cooling_degrees(_avgtemp, self.coolbase)
            _dayStat = StdDayStats(type, _sod_ts, (_sod_ts, _degs, _sod_ts, _degs, _sod_ts,
                                                   _degs, 1))
        else:
            _dayStat = StdDayStats(type, _sod_ts)
        return _dayStat
        
    @staticmethod
    def __getTypes(statsFilename):
        """Static method which returns the types appearing in a stats database.
        
        statsFilename: Path to the stats database.
        
        returns: A list of types or None if the database has not been initialized."""
        
        _connection = sqlite3.connect(statsFilename)
        _cursor = _connection.cursor()
        try:
            _cursor.execute('''SELECT name FROM sqlite_master WHERE type = 'table';''')
            
            stats_types = [str(_row[0]) for _row in _cursor if _row[0] != u'metadata']
            if len(stats_types) == 0 :
                stats_types = None
            else:
                stats_types += ('heatdeg', 'cooldeg')

        finally:
            _cursor.close()
            _connection.close()

        return stats_types


#===============================================================================
#                          USEFUL FUNCTIONS
#===============================================================================

def backfill(archiveDb, statsDb, start_ts = None, stop_ts = None):
    """Fill the statistical database from an archive database.
    
    Normally, the stats database if filled by LOOP packets (to get maximum time
    resolution), but if the database gets corrupted, or if a new user is
    starting up with imported wview data, it's necessary to recreate it from
    straight archive data. The Hi/Lows will all be there, but the times won't be
    any more accurate than the archive period.
    
    archiveDb: An instance of weewx.archive.Archive
    
    statsDb: An instance of weewx.stats.StatsDb
    
    start_ts: Archive data with a timestamp greater than this will be
    used. [Optional. Default is to start with the first datum in the archive.]
    
    stop_ts: Archive data with a timestamp less than or equal to this will be
    used. [Optional. Default is to end with the last datum in the archive.]"""
    
    t1 = time.time()
    nrecs = 0
    ndays = 0
    
    _allStats  = None
    _lastTime  = None
    
    # If a start time for the backfill wasn't given, then start with the time of
    # the last statistics recorded:
    if start_ts is None:
        start_ts = statsDb._getLastUpdate()
    
    # Go through all the archiveDb records in the time span, adding them to the
    # database
    for _rec in archiveDb.genBatchRecords(start_ts, stop_ts):
        _rec_time_ts = _rec['dateTime']
        _rec_sod_ts = weeutil.weeutil.startOfArchiveDay(_rec_time_ts)
        # Check whether this is the first day, or we have entered a new day:
        if _allStats is None or _allStats.dateTime != _rec_sod_ts:
                # If this is not the first day, then write it out:
                if _allStats:
                    statsDb._setDay(_allStats, _lastTime)
                    ndays += 1
                # Get the stats for the new day:
                _allStats = statsDb.day(weeutil.weeutil.daySpan(_rec_sod_ts))
        
        # Add the stats for this record to the running total for this day:
        for _type in _allStats:
            _allStats[_type].addArchiveRecord(_rec)
        nrecs += 1
        # Remember the timestamp for this record.
        _lastTime = _rec_time_ts

    # We're done. Record the stats for the last day.
    if _allStats:
        statsDb._setDay(_allStats, _lastTime)
        ndays += 1
    
    t2 = time.time()
    tdiff = t2 - t1
    if nrecs:
        syslog.syslog(syslog.LOG_NOTICE, 
                      "stats: backfilled %d days of statistics with %d records in %.2f seconds" % (ndays, nrecs, tdiff))
    else:
        syslog.syslog(syslog.LOG_INFO,
                      "stats: stats database up to date.")

if __name__ == '__main__':
    #===========================================================================
    # Strategy is to go get a day's worth of statistics from the stats
    # database and then compare them to calculating them directly from
    # the main archive database using clever SQL select statements. This
    # is a completely independent test because the data in the stats database
    # was calculated directly in Python, and not by using SQL statements.
    #===========================================================================
    import sys
    import configobj
    import weewx.archive
    
    def test(config_path):
        
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        # Open up the main archive database 
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)

        statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                     config_dict['Stats']['stats_file'])

        conn = sqlite3.connect(statsFilename)
        conn.row_factory = sqlite3.Row
        cursor=conn.cursor()

        # Start out by getting a date that exists in the database.
        # Select the 10th record to check. 
        cursor.execute("SELECT dateTime FROM barometer LIMIT 2 OFFSET 10")
        
        # This gets the start time of the test day:
        testrow = cursor.fetchone()
        if not testrow:
            print "Cannot get a test row from the typeStats database. Perhaps it is not initialized??"
            exit()
        start_ts = testrow['dateTime']

        # And this gets the end of the test day:
        testrow = cursor.fetchone()
        stop_ts = testrow['dateTime']
        
        # No need to leave these lying around:
        cursor.close()
        conn.close()

        print "start time=", weeutil.weeutil.timestamp_to_string(start_ts)
        print "stop time= ", weeutil.weeutil.timestamp_to_string(stop_ts)
        # Make sure it's a start of day:
        assert(start_ts == weeutil.weeutil.startOfDay(start_ts))

        # OK, now open up the typeStats database using the class StatsDb:
        statsDb = StatsDb(statsFilename, 65.0, 65.0)
        
        daySpan = weeutil.weeutil.daySpan(start_ts)
        allStats = statsDb.day(daySpan)

        # Test it against some types
        # Should really do a test for 'wind' as well.
        # Should also test monthly, yearly summaries
        for type in ('barometer', 'outTemp', 'inTemp', 'heatindex'):
            print "\n***************** %s ********************" % type
            # Get the StatsDict for this day and this type:
            typeStats = statsDb.getTypeStats(type, start_ts)
        
            # Now test all the aggregates:
            for aggregate in ('min', 'max', 'sum', 'count'):
                # Compare to the main archive:
                res = archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, type), start_ts, stop_ts)
                # From StatsDb:
                typeStats_res = typeStats.__getattribute__(aggregate)
                allStats_res  = allStats[type].__getattribute__(aggregate)
                print "%s: results from stats database using getTypeStats(): " % aggregate, typeStats_res
                print "%s: results from stats database using day():         " % aggregate, allStats_res
                print "%s: result from running SQL on the main archive:     " % aggregate, res[0]
                assert(typeStats_res == res[0])
                assert(allStats_res == res[0])
                
                # Check the times of min and max as well:
                if aggregate in ('min','max'):
                    res2 = archive.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (type,), res[0], start_ts, stop_ts)
                    stats_time =  typeStats.__getattribute__(aggregate+'time')
                    print aggregate+'time: from main archive:   ', weeutil.weeutil.timestamp_to_string(res2[0])
                    print aggregate+'time: from typeStats database: ', weeutil.weeutil.timestamp_to_string(stats_time)
                    assert( stats_time == res2[0])
        
        print "\nPASSES"
        
        #yearStats = statsDb.year(weeutil.weeutil.yearSpan(time.mktime((2009,6,2,1,0,0,0,0,-1))))
        #print len(yearStats._getAllDays())
        
    if len(sys.argv) < 2 :
        print "Usage: stats.py path-to-configuration-file"
        exit()
        
    test(sys.argv[1])
