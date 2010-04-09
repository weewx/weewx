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
from pysqlite2 import dbapi2 as sqlite3
import math
import os
import os.path
import syslog
import time

import weewx
import weewx.units
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
                       'wind')

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

        val = rec.get(self.type)
        if val is None :
            # Either the type doesn't exist in this record, or it's bad.
            # Ignore.
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

        val = rec.get(self.type)
        if val is None :
            # Either the type doesn't exist in this record, or it's bad.
            # Ignore.
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
        super(WindDayStats, self).__init__(type, sod_ts, stats_seq)

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
            # Note that there is no separate 'count' for theta. We use the
            # 'count' for sum. This means if there are
            # a significant number of bad theta's (equal to None), then vecavg
            # could be off slightly.  
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
        return StdDayStats.__str__(self) + "; rms = %s; vecavg = %s; vecdir = %s " % (rms_str, vecavg_str, vecdir_str)


#===============================================================================
#                    Class DayStatsDict
#===============================================================================

class DayStatsDict(dict):
    """Statistics for a day, keyed by type.
    
    This is like any other dictionary except that it has an attribute startOfDay_ts,
    with the timestamp of the start of the day the dictionary represents.

    The key of the dictionary is a type ('outTemp', 'barometer',
    etc.), the value an instance of WindDayStats for type 'wind',
    otherwise an instance of StdDayStats

    ATTRIBUTES: 
    self.startOfDay_ts: The start of the day this instance covers."""
    
    def __init__(self, type_seq, startOfDay_ts):
        """Create from a sequence of types, and from a time span.

        type_seq: An iterable sequence of types ('outTemp',
        'barometer', etc.). These will be the keys of the dictionary

        startOfDay_ts: The timestamp of the beginning of the day.

        returns: An instance of DayStatsDict where the value for each
        type has been initialized to 'default' values."""

        self.startOfDay_ts = startOfDay_ts
        
        for type in type_seq:
            if type == 'wind':
                self[type] = WindDayStats(type, startOfDay_ts)
            else:
                self[type] = StdDayStats(type, startOfDay_ts)

    def __str__(self):
        """Print self out in a useful way for diagnostics."""
        outTempStats = self['outTemp']
        outTempMin_str = str(outTempStats.min) if outTempStats.min is not None else "N/A"
        outTempMax_str = str(outTempStats.max) if outTempStats.max is not None else "N/A"
        return "time span: %s; temperature (min,max) = (%s, %s)" % (str(self.timespan), outTempMin_str, outTempMax_str)

#===============================================================================
#                    Class TaggedStats
#===============================================================================

class TaggedStats(object):
    """Allows stats references like obj.month.outTemp.max.
    
    This class sits on the top of chain of helper classes that enable
    syntax such as $month.rain.sum in the template classes. 
    
    When a time period is given as an attribute to it, such as obj.month,
    the next item in the chain is returned, in this case an instance of
    TimeSpanStats, which binds the stats database with the
    time period. 
    """
    
    def __init__(self, statsDb, endtime_ts, unit_info=None):
        """Initialize an instance of TaggedStats.
        statsDb: An instance of weewx.stats.StatsReadonly
        
        endtime_ts: The time the stats are to be current to.
        
        unit_info: An instance of weewx.units.Units holding the target units. 
        [Optional. If not specified, default formatting and units will be chosen.]
        """
        self.statsDb    = statsDb
        self.endtime_ts = endtime_ts
        self.unit_info  = unit_info
        
    # What follows is the list of time period attributes:

    @property
    def day(self):
        return TimeSpanStats(self.statsDb, weeutil.weeutil.archiveDaySpan(self.endtime_ts), 'day', self.unit_info)
    @property
    def week(self):
        return TimeSpanStats(self.statsDb, weeutil.weeutil.archiveWeekSpan(self.endtime_ts), 'week', self.unit_info)
    @property
    def month(self):
        return TimeSpanStats(self.statsDb, weeutil.weeutil.archiveMonthSpan(self.endtime_ts), 'month', self.unit_info)
    @property
    def year(self):
        return TimeSpanStats(self.statsDb, weeutil.weeutil.archiveYearSpan(self.endtime_ts), 'year', self.unit_info)
    @property
    def rainyear(self):
        return TimeSpanStats(self.statsDb, weeutil.weeutil.archiveRainYearSpan(self.endtime_ts), 'rainyear', self.unit_info)
        
   
#===============================================================================
#                    Class TimeSpanStats
#===============================================================================

class TimeSpanStats(object):
    """Nearly stateless class that holds a binding to a stats database and a timespan.
    
    This class is the next class in the chain of helper classes.

    This class allows syntax such as the following:
    
       statsdb = StatsDb('somestatsfile.sdb')
       # This timespan runs from 2007-01-01 to 2008-01-01 (one year):
       yearSpan = weeutil.Timespan(1167638400, 1199174400)
       yearStats = TimeSpanStats(statsdb, yearSpan)
       
       # Print max temperature for the year:
       print yearStats.outTemp.max
       
       # You can also iterate by day, month, or year:
       for monthStats in yearStats.months:
           # Print maximum temperature for each month in the year:
           print monthStats.outTemp.max
           
       for dayStats in yearStats.days:
           # Print max temperature for each day of the year:
           print dayStats.outTemp.max
    """

    def __init__(self, statsDb, timespan, context='current', unit_info=None):
        """Initialize an instance of TimeSpanStats.
        
        statsDb: An instance of StatsReadonlyDb or a subclass.
        
        timespan: An instance of weeutil.Timespan with the time span
        over which the statistics are to be calculated.
        
        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        unit_info: An instance of weewx.units.Units holding the target units. 
        [Optional. If not specified, default formatting and units will be chosen.]
        """
        
        self.statsDb   = statsDb
        self.timespan  = timespan
        self.context   = context
        self.unit_info = unit_info
        
    @property
    def days(self):
        return _seqGenerator(self.statsDb, self.timespan, 'day', self.unit_info, weeutil.weeutil.genDaySpans)
    @property
    def months(self):
        return _seqGenerator(self.statsDb, self.timespan, 'month', self.unit_info, weeutil.weeutil.genMonthSpans)
    @property
    def years(self):
        return _seqGenerator(self.statsDb, self.timespan, 'year', self.unit_info, weeutil.weeutil.genYearSpans)
    @property
    def dateTime(self):
        return weewx.units.ValueHelper((self.timespan.start, "unix_epoch"), self.context, self.unit_info)

    def __getattr__(self, stats_type):
        """Return a helper object for the given type.
        
        stats_type: A statistical type, such as 'outTemp', or 'heatDeg'
        
        returns: The helper class StatsTypeHelper bound to the type
        and timespan.
        """
        # The attribute is probably a type such as 'barometer', or 'heatdeg'
        # Return the helper class, bound to the type:
        return StatsTypeHelper(self.statsDb, self.timespan, stats_type, self.context, self.unit_info)
        
def _seqGenerator(statsDb, timespan, context, unit_info, genSpanFunc):
    """Generator function that returns TimeSpanStats for the appropriate timespans"""
    for span in genSpanFunc(timespan.start, timespan.stop):
        yield TimeSpanStats(statsDb, span, context, unit_info)
        
#===============================================================================
#                    Class StatsTypeHelper
#===============================================================================

class StatsTypeHelper(object):
    """Nearly stateless helper class that holds the database, timespan, and type
    over which aggregation is to be done."""
    
    def __init__(self, statsDb, timespan, stats_type, context='current', unit_info=None):
        """ Initialize an instance of StatsTypeHelper
        
        statsDb: The database against which the query is to be run.
        
        timespan: An instance of TimeSpan holding the time period over which the query is
        to be run
        
        stats_type: A string with the stats type (e.g., 'outTemp') for which the query is
        to be done.
        
        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        unit_info: An instance of weewx.units.Units holding the target units. 
        [Optional. If not specified, default formatting and units will be chosen.]
        """
        
        self.statsDb    = statsDb
        self.timespan   = timespan
        self.stats_type = stats_type
        self.context    = context
        self.unit_info  = unit_info
    
    def max_ge(self, val):
        result = self.statsDb.getAggregate(self.timespan, self.stats_type, 'max_ge', val)
        return weewx.units.ValueHelper(result, self.context, self.unit_info)

    def max_le(self, val):
        result = self.statsDb.getAggregate(self.timespan, self.stats_type, 'max_le', val)
        return weewx.units.ValueHelper(result, self.context, self.unit_info)
    
    def min_le(self, val):
        result = self.statsDb.getAggregate(self.timespan, self.stats_type, 'min_le', val)
        return weewx.units.ValueHelper(result, self.context, self.unit_info)
    
    def sum_ge(self, val):
        result = self.statsDb.getAggregate(self.timespan, self.stats_type, 'sum_ge', val)
        return weewx.units.ValueHelper(result, self.context, self.unit_info)
    
    def __getattr__(self, aggregateType):
        """Attribute is an aggregation type, such as 'sum', 'max', etc."""
        if self.stats_type in ('heatdeg', 'cooldeg'):
            # Heating and cooling degree days use a different entry point into Stats:
            result = self.statsDb.getHeatCool(self.timespan, self.stats_type, aggregateType,
                                              self.unit_info.heatbase, self.unit_info.coolbase)
        else:
            result = self.statsDb.getAggregate(self.timespan, self.stats_type, aggregateType)
        # Wrap the result in a ValueHelper:
        return weewx.units.ValueHelper(result, self.context, self.unit_info)
    
        
#===============================================================================
#                    Class StatsReadonlyDb
#===============================================================================

class StatsReadonlyDb(object):
    """Manage reading from the sqlite3 statistical database. 
    
    This class acts as a wrapper around the stats database, with a set
    of methods for retrieving records from the statistical compilation. 

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
    StatsReadonlyDb. None if the database has not been initialized.
    
    std_unit_system: The unit system in use (weewx.US or weewx.METRIC). None if the
    database has not been initialized."""
    
    # In addition to the attributes listed above, if caching is used,
    # each instance has a private attribute self._dayCache. This is a two-way 
    # tuple where the first member is an instance of DayStatsDict, and
    # the second member is lastUpdate. If caching is not being used, then
    # self._dayCache equals None.
        
    def __init__(self, statsFilename, cacheDayData = True):
        """Create an instance of StatsReadonlyDb to manage a database.
        
        statsFilename: Path to the stats database file.
        
        cacheDayData: True if a days stats are to be cached after reading. 
        Otherwise, it gets read with every query.
        [Optional. Default is True]"""
        
        self._connection     = None
        self.statsFilename   = statsFilename
        self.statsTypes      = self._getTypes()
        self.std_unit_system = self._getStdUnitSystem()

        if cacheDayData:
            self._dayCache  = (None, None)
        else:
            self._dayCache  = None

    def getStatsForType(self, stats_type, sod_ts):
        """Get the statistics for a specific observation type for a specific day.

        stats_type: The type of data to retrieve ('outTemp', 'barometer', 'wind',
        'rain', etc.)

        sod_ts: The timestamp of the start-of-day for the desired day.

        returns: an instance of WindDayStats for type 'wind',
        otherwise an instance of StdDayStats, initialized with the
        data from the database. If the record doesn't exist in the
        database, the returned instance will be set to 'default'
        values (generally, min==None, count=0, etc.)"""
        
        if weewx.debug:
            assert(stats_type not in ('heatdeg', 'cooldeg'))
            
        _connection = self._getConnection()
        _cursor = _connection.cursor()

        # Form a SQL select statement for the appropriate type
        _sql_str = "SELECT * FROM %s WHERE dateTime = ?" % stats_type
        # Peform the select, against the desired timestamp
        _cursor.execute(_sql_str, (sod_ts,))
        # Get the result
        _row = _cursor.fetchone()

        if weewx.debug:
            if _row:
                if stats_type =='wind': assert(len(_row) == 12)
                else: assert(len(_row) == 7)

        # The date may not exist in the database, in which case _row will
        # be 'None', causing either StdDayStats or WindDayStats
        # to initialize to default values.
        _dayStats = StdDayStats(stats_type, sod_ts, _row) if stats_type != 'wind'\
                                                          else WindDayStats(stats_type, sod_ts, _row)

        return _dayStats

    def day(self, startOfDay_ts):
        """Return an instance of DayStatsDict initialized to a given day's statistics.

        startOfDay_ts: The timestamp of the start-of-day of the desired day.

        cursor: A database cursor to be used for the retrieval. [Optional. If not given,
        one will be created and destroyed for this query.]"""
        
        if self._dayCache and self._dayCache[0] and self._dayCache[0].startOfDay_ts == startOfDay_ts:
            return self._dayCache[0]

        _allStats = DayStatsDict(self.statsTypes, startOfDay_ts)
        
        for stats_type in self.statsTypes:
            _allStats[stats_type] = self.getStatsForType(stats_type, startOfDay_ts)
        
        if self._dayCache:
            self._dayCache = (_allStats, None)

        return _allStats

    # Set of SQL statements to be used for calculating aggregate statistics. Key is the aggregation type,
    # value is the SQL statement to be used.
    sqlDict = {'min'        : "SELECT MIN(min) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max'        : "SELECT MAX(max) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'meanmin'    : "SELECT AVG(min) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'meanmax'    : "SELECT AVG(max) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'maxsum'     : "SELECT MAX(sum) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'mintime'    : "SELECT mintime FROM %(stats_type)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "min = (SELECT MIN(min) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'maxtime'    : "SELECT maxtime FROM %(stats_type)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "max = (SELECT MAX(max) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'maxsumtime' : "SELECT maxtime FROM %(stats_type)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "sum = (SELECT MAX(sum) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'gustdir'    : "SELECT gustdir FROM %(stats_type)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "max = (SELECT MAX(max) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s)",
               'sum'        : "SELECT SUM(sum) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'count'      : "SELECT SUM(count) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'avg'        : "SELECT SUM(sum),SUM(count) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'rms'        : "SELECT SUM(squaresum),SUM(squarecount) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'vecavg'     : "SELECT SUM(xsum),SUM(ysum),SUM(count)  FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'vecdir'     : "SELECT SUM(xsum),SUM(ysum) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max_ge'     : "SELECT SUM(max >= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max_le'     : "SELECT SUM(max <= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'min_le'     : "SELECT SUM(min <= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'sum_ge'     : "SELECT SUM(sum >= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s"}

    def getAggregate(self, timespan, stats_type, aggregateType, val = None):
        """Returns an aggregation of a statistical type for a given time period.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        stats_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
        
        aggregateType: The type of aggregation to be done. The keys in the dictionary
        sqlDict above are the possible aggregation types. 
        
        val: Some aggregations require a value. Specify it here as a value tuple.
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F')
        """
        if timespan is None:
            return (None, None)

        # This entry point won't work for heating or cooling degree days:
        if weewx.debug:
            assert(stats_type not in ('heatdeg', 'cooldeg'))

        target_val = weewx.units.convertStd(val, self.std_unit_system)[0] if val else None
        
        # This dictionary is used for interpolating the SQL statement.
        interDict = {'start'         : timespan.start,
                     'stop'          : timespan.stop,
                     'stats_type'     : stats_type,
                     'aggregateType' : aggregateType,
                     'val'           : target_val}
        
        # Run the query against the database:
        _row = self._xeqSql(StatsReadonlyDb.sqlDict[aggregateType], interDict)

        #=======================================================================
        # Each aggregation type requires a slightly different calculation.
        #=======================================================================
        
        if not _row or None in _row: 
            # If no row was returned, or if it contains any nulls (meaning that not
            # all required data was available to calculate the requested aggregate),
            # then set the results to None.
            _result = None
        
        # Do the required calculation for this aggregat type
        elif aggregateType in ('min', 'max', 'meanmin', 'meanmax', 'maxsum','sum', 'gustdir'):
            # These aggregates are passed through 'as is'.
            _result = _row[0]
        
        elif aggregateType in ('mintime', 'maxtime', 'maxsumtime',
                               'count', 'max_ge', 'max_le', 'min_le', 'sum_ge'):
            # These aggregates are always integers:
            _result = int(_row[0])

        elif aggregateType in ('avg',):
            _result = _row[0]/_row[1] if _row[1] else None

        elif aggregateType in ('rms', ):
            _result = math.sqrt(_row[0]/_row[1]) if _row[1] else None
        
        elif aggregateType in ('vecavg', ):
            _result = math.sqrt((_row[0]**2 + _row[1]**2) / _row[2]**2) if _row[2] else None
        
        elif aggregateType in ('vecdir',):
            if _row[0:2] == (0.0, 0.0):
                _result = None
            deg = 90.0 - math.degrees(math.atan2(_row[1], _row[0]))
            _result = deg if deg > 0 else deg + 360.0
        else:
            # Unknown aggregation. Return None
            _result = None

        # Look up the unit type of this combination of stats type and aggregation:
        _result_unit_type = weewx.units.getStandardUnitType(self.std_unit_system, stats_type, aggregateType)
        # Form the value tuple:
        return (_result, _result_unit_type)
        
    def getHeatCool(self, timespan, stats_type, aggregateType, heatbase_t, coolbase_t):
        """Calculate heating or cooling degree days for a given timespan.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        stats_type: One of 'heatdeg' or 'cooldeg'.
        
        aggregateType: The type of aggregation to be done. Must be 'sum' or 'avg'.
        
        heatbase_t, coolbase_t: Value tuples with the heating and cooling degree
        day base, respectively.
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F')"""
        
        # The requested type must be heatdeg or cooldeg
        if weewx.debug:
            assert(stats_type in ('heatdeg', 'cooldeg'))

        # Only summation (total) or average heating or cooling degree days is supported:
        if aggregateType not in ('sum', 'avg'):
            raise weewx.ViolatedPrecondition, "Aggregate type %s for %s not supported." % (aggregateType, stats_type)

        sum = 0.0
        count = 0
        for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
            # Get the average temperature for the day as a value tuple:
            Tavg_t = self.getAggregate(daySpan, 'outTemp', 'avg')
            # Make sure it's valid before including it in the aggregation:
            if Tavg_t is not None and Tavg_t[0] is not None:
                if stats_type == 'heatdeg':
                    # Convert average temperature to the same units as heatbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, heatbase_t[1])
                    sum += weewx.wxformulas.heating_degrees(Tavg_target_t[0], heatbase_t[0])
                else:
                    # Convert average temperature to the same units as coolbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, coolbase_t[1])
                    sum += weewx.wxformulas.cooling_degrees(Tavg_target_t[0], coolbase_t[0])
                count += 1

        if aggregateType == 'sum':
            _result = sum
        else:
            _result = sum / count if count else None 

        # Look up the type of the result:
        _result_unit_type = weewx.units.getStandardUnitType(self.std_unit_system, stats_type, aggregateType)
        # Return as a value tuple
        return (_result, _result_unit_type)

    def _getFirstUpdate(self):
        """Returns the time of the first entry in the statistical database."""
        #=======================================================================
        # This is a bit of a hack because it actually returns the first entry
        # for the barometer, which may or may not be the earliest entry in
        # the stats database.
        #=======================================================================
        _row = self._xeqSql("SELECT min(dateTime) FROM barometer", {})
        return int(_row[0]) if _row else None

    def _getLastUpdate(self):
        """Returns the time of the last update to the statistical database."""

        _row = self._xeqSql("""SELECT value FROM metadata WHERE name = 'lastUpdate';""", {})
        return int(_row[0]) if _row else None

    def _xeqSql(self, rawsqlStmt, interDict):
        """Execute an arbitrary SQL statement, using an interpolation dictionary.
        
        Returns only the first row of a result set.
        
        rawsqlStmt: A SQL statement with (possible) mapping keys.
        
        interDict: The interpolation dictionary to be used on the mapping keys.
        
        returns: The first row from the result set.
        """
        
        # Do the string interpolation:
        sqlStmt = rawsqlStmt % interDict
        # Get a _connection
        _connection = self._getConnection()
        # Execute the statement:
        _cursor = _connection.execute(sqlStmt)
        # Fetch the first row and return it.
        _row = _cursor.fetchone()
        return _row 
        
    def _getConnection(self):
        """Return a sqlite _connection"""
        if not self._connection:
            self._connection = sqlite3.connect(self.statsFilename)
            
        return self._connection
    
    def _getTypes(self):
        """Returns the types appearing in a stats database.
        
        statsFilename: Path to the stats database.
        
        returns: A list of types or None if the database has not been initialized."""
        
        if not os.path.exists(self.statsFilename):
            return None
        
        with sqlite3.connect(self.statsFilename) as _connection:
            _cursor = _connection.execute('''SELECT name FROM sqlite_master WHERE type = 'table';''')
            
        stats_types = [str(_row[0]) for _row in _cursor if _row[0] != u'metadata']
        if len(stats_types) == 0 :
            return None

        # Some stats database have schemas for heatdeg and cooldeg (even though they are not
        # used) due to an earlier bug. Filter them out.
        results = filter(lambda x : x not in ('heatdeg', 'cooldeg'), stats_types)

        return results

    def _getStdUnitSystem(self):
        """Returns the unit system in use in the stats database."""
        
        if not os.path.exists(self.statsFilename):
            return None
        
        _row = self._xeqSql("""SELECT value FROM metadata WHERE name = 'unit_system';""", {})
        # If the unit system is missing, then it is an older style stats database,
        # which are always in the US Customary standard unit system:
        if not _row:
            return weewx.US
        
        # Otherwise, extract it from the row and, if debugging, test for validity
        unit_system = int(_row[0])
        if weewx.debug:
            assert(unit_system in (weewx.US, weewx.METRIC))
        return unit_system

        
#===============================================================================
#                    Class StatsDb
#===============================================================================

class StatsDb(StatsReadonlyDb):
    """Inherits from class StatsReadonlyDb, adding methods for writing to 
    the statistical database.
    """
    
    def addArchiveRecord(self, rec):
        """Add an archive record to the statistical database."""

        # Get the start-of-day for this archive record.
        _sod_ts = weeutil.weeutil.startOfArchiveDay(rec['dateTime'])

        _allStatsDict = self.day(_sod_ts)

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

        _allStatsDict = self.day(_sod_ts)

        for type in self.statsTypes:
            # ... and add this loop record to the running tally:
            _allStatsDict[type].addLoopRecord(rec)

        # Now write the results for all types back to the database
        # in a single transaction:
        self._setDay(_allStatsDict, rec['dateTime'], writeThrough = False)

        
    def config(self, stats_types = None, unit_system = weewx.US):
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
            
            # Heating and cooling degrees are not actually stored in the database:
            stats_types = filter(lambda x : x not in ('heatdeg', 'cooldeg'), stats_types)

            # Now create all the necessary tables as one transaction:
            with sqlite3.connect(self.statsFilename) as _connection:
            
                for _stats_type in stats_types:
                    # Slightly different SQL statement for wind
                    if _stats_type == 'wind':
                        _connection.execute(wind_create_str)
                    else:
                        _connection.execute(std_create_str % (_stats_type,))
                _connection.execute(meta_create_str)
                _connection.execute(meta_replace_str, ('unit_system', str(unit_system)))
            
            self.statsTypes = stats_types
            syslog.syslog(syslog.LOG_NOTICE, "stats: created schema for statistical database %s." % self.statsFilename)



    def _setDay(self, dayStatsDict, lastUpdate, writeThrough = True):
        """Write all statistics for a day to the database in a single transaction.
        
        dayStatsDict: A dictionary. Key is the type to be written, value is a
        StdDayStats or WindDayStats, as appropriate.  Class DayStatsDict
        satisfies this.
        
        lastUpdate: the time of the last update will be set to this. Normally, this
        is the timestamp of the last archive record added to the instance
        dayStatsDict."""

        assert(dayStatsDict)

        if self._dayCache:
            if self._dayCache[0] and self._dayCache[0].startOfDay_ts != dayStatsDict.startOfDay_ts:
                # Write the old data
                self.__writeData(self._dayCache[0], self._dayCache[1])
        
            self._dayCache = (dayStatsDict, lastUpdate)
            if writeThrough:
                self.__writeData(dayStatsDict, lastUpdate)
        
        else:
            self.__writeData(dayStatsDict, lastUpdate)
        
        
    def __writeData(self, dayStatsDict, lastUpdate):
        
        assert(dayStatsDict)
        assert(lastUpdate)
        
        _sod = dayStatsDict.startOfDay_ts

        # Using the _connection as a context manager means that
        # in case of an error, all tables will get rolled back.
        with sqlite3.connect(self.statsFilename) as _connection:
            for _stats_type in self.statsTypes:
                
                # Slightly different SQL statement for wind
                if _stats_type == 'wind':
                    _replace_str = wind_replace_str
                else:
                    _replace_str = std_replace_str % _stats_type
                
                # Get the stats-tuple, then write the results
                _write_tuple = dayStatsDict[_stats_type].getStatsTuple()
                assert(_write_tuple[0] == _sod)
                _connection.execute(_replace_str,_write_tuple)
            # Update the time of the last stats update:
            _connection.execute(meta_replace_str, ('lastUpdate', str(int(lastUpdate))))
            

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
        if _allStats is None or _allStats.startOfDay_ts != _rec_sod_ts:
                # If this is not the first day, then write it out:
                if _allStats:
                    statsDb._setDay(_allStats, _lastTime)
                    ndays += 1
                # Get the stats for the new day:
                _allStats = statsDb.day(_rec_sod_ts)
        
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

        # OK, now open up the typeStats database using the class StatsReadonlyDb:
        statsDb = StatsReadonlyDb(statsFilename)
        
        allStats = statsDb.day(start_ts)

        # Test it against some types
        # Should really do a test for 'wind' as well.
        # Should also test monthly, yearly summaries
        for type in ('barometer', 'outTemp', 'inTemp', 'heatindex'):
            print "\n***************** %s ********************" % type
            # Get the StatsDict for this day and this type:
            typeStats = statsDb.getStatsForType(type, start_ts)
        
            # Now test all the aggregates:
            for aggregate in ('min', 'max', 'sum', 'count'):
                # Compare to the main archive:
                res = archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, type), start_ts, stop_ts)
                # From StatsDb:
                typeStats_res = typeStats.__getattribute__(aggregate)
                allStats_res  = allStats[type].__getattribute__(aggregate)
                print "%s: results from stats database using getStatsForType(): " % aggregate, typeStats_res
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
        
        print "PASSES\n"
        
    def test2(config_path):
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                     config_dict['Stats']['stats_file'])

        statsDb = StatsReadonlyDb(statsFilename)

        start_tt = (2009, 12, 1, 0, 0, 0, 0, 0, -1)
        end_tt =   (2010,  1, 1, 0, 0, 0, 0, 0, -1)
        timespan = weeutil.weeutil.TimeSpan(time.mktime(start_tt),
                                            time.mktime(end_tt))

        tagStats = TaggedStats(statsDb, time.mktime(end_tt))

        print tagStats.month.barometer.avg
        print tagStats.month.barometer.count

        time_from_statsDb = statsDb.getAggregate(timespan, 'outTemp', 'mintime')
        time_from_tag = tagStats.month.outTemp.mintime
        assert(time_from_statsDb == time_from_tag.value_tuple)
        
        avg_from_statsDb = statsDb.getAggregate(timespan, 'outTemp', 'avg')
        avg_from_tag = tagStats.month.outTemp.avg
        assert(avg_from_statsDb == avg_from_tag.value_tuple)

        for day in tagStats.month.days:
            print day.dateTime.format("%d-%b-%Y"), day.outTemp.max, day.outTemp.maxtime
              
    if len(sys.argv) < 2 :
        print "Usage: stats.py path-to-configuration-file"
        exit()
        
    test(sys.argv[1])
    test2(sys.argv[1])
