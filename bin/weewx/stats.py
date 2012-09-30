#
#    Copyright (c) 2009, 2010, 2011, 2012 Tom Keffer <tkeffer@gmail.com>
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

    As new archive data becomes available, it can be added to the
    database with method addRecord().
    
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
import os.path
import syslog
import time

import weedb
import weeutil.weeutil
import weewx.accum
import weewx.units
import weewx.wxformulas

#===============================================================================
# The SQL statements used in the stats database
#===============================================================================

std_create_str  = """CREATE TABLE %s   ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                  """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER);"""

wind_create_str = """CREATE TABLE wind ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                  """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, """\
                  """gustdir REAL, xsum REAL, ysum REAL, squaresum REAL, squarecount INTEGER);"""

meta_create_str = """CREATE TABLE metadata (name CHAR(20) NOT NULL UNIQUE PRIMARY KEY, value TEXT);"""
                 
std_replace_str  = """REPLACE INTO %s   VALUES(?, ?, ?, ?, ?, ?, ?)"""
wind_replace_str = """REPLACE INTO wind VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
meta_replace_str = """REPLACE into metadata VALUES(?, ?)"""  

# Set of SQL statements to be used for calculating aggregate statistics. Key is the aggregation type.
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
           'rms'        : "SELECT SUM(squaresum),SUM(count) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'vecavg'     : "SELECT SUM(xsum),SUM(ysum),SUM(squarecount)  FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'vecdir'     : "SELECT SUM(xsum),SUM(ysum) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'max_ge'     : "SELECT SUM(max >= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'max_le'     : "SELECT SUM(max <= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'min_le'     : "SELECT SUM(min <= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'sum_ge'     : "SELECT SUM(sum >= %(val)s) FROM %(stats_type)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s"}

#===============================================================================
#                    Class StatsDb
#===============================================================================

class StatsDb(object):
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
    'squarecount' (perhaps not the best name, but it's there for historical reasons)
    is the number of items added to 'xsum' and 'ysum'.
    
    In addition to all the tables for each type, there is also a separate table
    called 'metadata'. Currently, it only holds the time of last update, but more could
    be added later.
    
    ATTRIBUTES
    
    statsFilename: The path to the stats database
    
    statsTypes: The types of the statistics supported by this instance of
    StatsDb. 
    
    std_unit_system: The unit system in use (weewx.US or weewx.METRIC), or
    None if no system has been specified."""
    
    def __init__(self, db_dict):
        """Create an instance of StatsDb to manage a database.
        
        If the database does not exist or it is uninitialized, an
        exception of type weedb.OperationalError will be thrown. 
        
        db_dict: A dictionary containing the database connection information"""
        
        self.connection      = weedb.connect(db_dict)
        try:
            self.statsTypes      = self.__getTypes()
        except weedb.OperationalError:
            self.close()
            raise
        self.std_unit_system = self._getStdUnitSystem()

    @staticmethod
    def fromConfigDict(config_dict):
        stats_db = config_dict['StdArchive']['stats_database']
        stats_db_dict = config_dict['Databases'][stats_db]
        return StatsDb(stats_db_dict)
        
    @property
    def database(self):
        return self.connection.database
    
    def close(self):
        self.connection.close()
        
    def updateHiLo(self, accumulator):
        """Use the contents of an accumulator to update the highs/lows of a stats database."""
        
        # Get the start-of-day for the timespan in the accumulator
        _sod_ts = weeutil.weeutil.startOfArchiveDay(accumulator.timespan.stop)
        # Retrieve the stats seen so far:
        _stats_dict = self._getDayStats(_sod_ts)
        # Update them with the contents of the accumulator:
        _stats_dict.updateHiLo(accumulator)
        # Then save the results:
        self._setDayStats(_stats_dict, accumulator.timespan.stop)
        
    def addRecord(self, record):
        """Using an archive record, update the high/lows and count of a stats database."""
        
        # Get the start-of-day for the record:
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])
        # Get the stats seen so far:
        _stats_dict = self._getDayStats(_sod_ts)
        # Update them with the contents of the record:
        _stats_dict.addRecord(record)
        # Then save the results:
        self._setDayStats(_stats_dict, record['dateTime'])
        
    def getAggregate(self, timespan, stats_type, aggregateType, val=None):
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
        type is unknown. The second element is the unit type (eg, 'degree_F').
        The third element is the unit group (eg, "group_temperature") """
        global sqlDict
        
        # This entry point won't work for heating or cooling degree days:
        if weewx.debug:
            assert(stats_type not in ('heatdeg', 'cooldeg'))
            assert(timespan is not None)

        # Check to see if this is a valid stats type:
        if stats_type not in self.statsTypes:
            raise AttributeError, "Unknown stats type %s" % (stats_type,)

        if val is not None:
            # The following is for backwards compatibility when value tuples used
            # to have just two members:
            if len(val) == 2:
                if val[1] in ('degree_F', 'degree_C'):
                    val += ("group_temperature",)
                elif val[1] in ('inch', 'mm', 'cm'):
                    val += ("group_rain",)
            target_val = weewx.units.convertStd(val, self.std_unit_system)[0]
        else:
            target_val = None
        
        # This dictionary is used for interpolating the SQL statement.
        interDict = {'start'         : timespan.start,
                     'stop'          : timespan.stop,
                     'stats_type'    : stats_type,
                     'aggregateType' : aggregateType,
                     'val'           : target_val}
        
        # Run the query against the database:
        _row = self._xeqSql(sqlDict[aggregateType], interDict)

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

        # Look up the unit type and group of this combination of stats type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, stats_type, aggregateType)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
        
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
        type is unknown. The second element is the unit type (eg, 'degree_F').
        Third element is the unit group (always "group_temperature")."""
        
        # The requested type must be heatdeg or cooldeg
        if weewx.debug:
            assert(stats_type in ('heatdeg', 'cooldeg'))

        # Only summation (total) or average heating or cooling degree days is supported:
        if aggregateType not in ('sum', 'avg'):
            raise weewx.ViolatedPrecondition, "Aggregate type %s for %s not supported." % (aggregateType, stats_type)

        _sum = 0.0
        _count = 0
        for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
            # Get the average temperature for the day as a value tuple:
            Tavg_t = self.getAggregate(daySpan, 'outTemp', 'avg')
            # Make sure it's valid before including it in the aggregation:
            if Tavg_t is not None and Tavg_t[0] is not None:
                if stats_type == 'heatdeg':
                    # Convert average temperature to the same units as heatbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, heatbase_t[1])
                    _sum += weewx.wxformulas.heating_degrees(Tavg_target_t[0], heatbase_t[0])
                else:
                    # Convert average temperature to the same units as coolbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, coolbase_t[1])
                    _sum += weewx.wxformulas.cooling_degrees(Tavg_target_t[0], coolbase_t[0])
                _count += 1

        if aggregateType == 'sum':
            _result = _sum
        else:
            _result = _sum / _count if _count else None 

        # Look up the unit type and group of the result:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, stats_type, aggregateType)
        # Return as a value tuple
        return weewx.units.ValueTuple(_result, t, g)
    
    def _getDayStats(self, sod_ts):
        """Return an instance of accum.DictAccum initialized to a given day's statistics.

        sod_ts: The timestamp of the start-of-day of the desired day."""
                
        # Get the TimeSpan for the day starting with sod_ts:
        timespan = weeutil.weeutil.archiveDaySpan(sod_ts,0)
        # Initialize an empty DictAccum
        _stats_dict = weewx.accum.DictAccum(timespan)
        
        for stats_type in self.statsTypes:
            _row = self._xeqSql("SELECT * FROM %s WHERE dateTime = %d" % (stats_type, sod_ts), {})
    
            if weewx.debug:
                if _row:
                    if stats_type =='wind': assert(len(_row) == 12)
                    else: assert(len(_row) == 7)
    
            # The date may not exist in the database, in which case _row will be 'None'
            _stats_tuple = _row[1:] if _row else None
        
            # Now initialize the observation type in the DictAccum with the
            # results seen so far, as retrieved from the database
            _stats_dict.initStats(stats_type, _stats_tuple)
        
        return _stats_dict

    def _setDayStats(self, dayStatsDict, lastUpdate):
        """Write all statistics for a day to the database in a single transaction.
        
        dayStatsDict: an instance of accum.DictAccum.
        
        lastUpdate: the time of the last update will be set to this. Normally, this
        is the timestamp of the last archive record added to the instance
        dayStatsDict."""

        _sod = dayStatsDict.timespan.start

        # Using the _connection as a context manager means that
        # in case of an error, all tables will get rolled back.
        with weedb.Transaction(self.connection) as _cursor:
            for _stats_type in self.statsTypes:
                
                # Slightly different SQL statement for wind
                if _stats_type == 'wind':
                    _replace_str = wind_replace_str
                else:
                    _replace_str = std_replace_str % _stats_type
                
                # Get the stats-tuple, then write the results
                _write_tuple = (_sod,) + dayStatsDict[_stats_type].getStatsTuple()
                _cursor.execute(_replace_str,_write_tuple)
                
            # Set the unit system if it has not been set before. 
            # To do this, first see if this file has ever been used:
            last_update = self._getLastUpdate()
            if last_update is None:
                # File has never been used. Set the unit system:
                _cursor.execute(meta_replace_str, ('unit_system', str(int(dayStatsDict.unit_system))))
            else:
                # The file has been used. If the debug flag has been set, make
                # sure the unit system of the file matches the new data.
                if weewx.debug:
                    unit_system = self._getStdUnitSystem()
                    if unit_system != dayStatsDict.unit_system:
                        raise ValueError("stats: Data uses different unit system (0x%x) than stats file (0x%x)" % (dayStatsDict.unit_system, unit_system))
            # Update the time of the last stats update:
            _cursor.execute(meta_replace_str, ('lastUpdate', str(int(lastUpdate))))
            
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
        _cursor = self.connection.cursor()
        try:
            _cursor.execute(sqlStmt)
            # Take the result set and run it through weedb.massage to convert
            # any long's or decimal.Decimals to ints
            return weedb.massage(_cursor.fetchone())
        finally:
            _cursor.close()
        
    def _getStdUnitSystem(self):
        """Returns the unit system in use in the stats database."""
        
        # If the metadata "unit_system" is missing, then it is an older style
        # stats database, which are always in the US Customary standard unit
        # system. If it exists, but is 'None', then the units have not been
        # specified yet. Otherwise, it equals the unit system used by the
        # database.

        _row = self._xeqSql("""SELECT value FROM metadata WHERE name = 'unit_system';""", {})
        
        # Check for an older database:
        if not _row:
            return weewx.US
        
        # It's a newer style database. Check for 'None' and return.
        unit_system = int(_row[0]) if str(_row[0])!='None' else None
        return unit_system

    def __getTypes(self):
        """Returns the types appearing in a stats database.
        
        Raises an exception of type weedb.OperationalError
        if the database has not been initialized.
        
        returns: A list of types"""
        
        raw_stats_types = self.connection.tables()
        
        # Some stats database have schemas for heatdeg and cooldeg (even though
        # they are not used) due to an earlier bug. Filter them out. Also,
        # filter out the metadata table:
        stats_types = filter(lambda s : s not in ['heatdeg', 'cooldeg', 'metadata'], raw_stats_types)

        return stats_types
        
            
#===============================================================================
#                    Class TaggedStats
#===============================================================================

class TaggedStats(object):
    """Allows stats references like obj.month.outTemp.max.
    
    This class sits on the top of chain of helper classes that enable
    syntax such as $month.rain.sum in the templates. 
    
    When a time period is given as an attribute to it, such as obj.month,
    the next item in the chain is returned, in this case an instance of
    TimeSpanStats, which binds the stats database with the
    time period. 
    """
    
    def __init__(self, db, endtime_ts, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of TaggedStats.
        db: The database the stats are to be extracted from.
        
        endtime_ts: The time the stats are to be current to.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]
        
        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]
        
        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        self.db          = db
        self.endtime_ts  = endtime_ts
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
        
    # What follows is the list of time period attributes:

    @property
    def day(self):
        return TimeSpanStats(weeutil.weeutil.archiveDaySpan(self.endtime_ts), self.db, 'day', 
                             self.formatter, self.converter, **self.option_dict)
    @property
    def week(self):
        return TimeSpanStats(weeutil.weeutil.archiveWeekSpan(self.endtime_ts), self.db, 'week', 
                             self.formatter, self.converter, **self.option_dict)
    @property
    def month(self):
        return TimeSpanStats(weeutil.weeutil.archiveMonthSpan(self.endtime_ts), self.db, 'month', 
                             self.formatter, self.converter, **self.option_dict)
    @property
    def year(self):
        return TimeSpanStats(weeutil.weeutil.archiveYearSpan(self.endtime_ts), self.db, 'year', 
                             self.formatter, self.converter, **self.option_dict)
    @property
    def rainyear(self):
        return TimeSpanStats(weeutil.weeutil.archiveRainYearSpan(self.endtime_ts, self.option_dict['rain_year_start']), self.db, 'rainyear', 
                             self.formatter, self.converter, **self.option_dict)
        
   
#===============================================================================
#                    Class TimeSpanStats
#===============================================================================

class TimeSpanStats(object):
    """Nearly stateless class that holds a binding to a stats database and a timespan.
    
    This class is the next class in the chain of helper classes. 

    When a statistical type is given as an attribute to it (such as 'obj.outTemp'),
    the next item in the chain is returned, in this case an instance of
    StatsTypeHelper, which binds the stats database, the time period, and
    the statistical type all together.

    It also includes a few "special attributes" that allow iteration over certain
    time periods. Example:
       
       # Iterate by month:
       for monthStats in yearStats.months:
           # Print maximum temperature for each month in the year:
           print monthStats.outTemp.max
    """
    def __init__(self, timespan, db, context='current', formatter=weewx.units.Formatter(), 
                 converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of TimeSpanStats.
        
        timespan: An instance of weeutil.Timespan with the time span
        over which the statistics are to be calculated.
        
        db: The database the stats are to be extracted from.
        
        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]
        
        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]
        
        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        
        self.timespan    = timespan
        self.db          = db
        self.context     = context
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
        
    # Iterate over days in the time period:
    @property
    def days(self):
        return TimeSpanStats._seqGenerator(weeutil.weeutil.genDaySpans, self.timespan, self.db, 'day', 
                                           self.formatter, self.converter, **self.option_dict)
        
    # Iterate over months in the time period:
    @property
    def months(self):
        return TimeSpanStats._seqGenerator(weeutil.weeutil.genMonthSpans, self.timespan, self.db, 'month', 
                                           self.formatter, self.converter, **self.option_dict)

    # Iterate over years in the time period:
    @property
    def years(self):
        return TimeSpanStats._seqGenerator(weeutil.weeutil.genYearSpans, self.timespan, self.db, 'year', 
                                           self.formatter, self.converter, **self.option_dict)

    # Static method used to implement the iteration:
    @staticmethod
    def _seqGenerator(genSpanFunc, timespan, *args, **option_dict):
        """Generator function that returns TimeSpanStats for the appropriate timespans"""
        for span in genSpanFunc(timespan.start, timespan.stop):
            yield TimeSpanStats(span, *args, **option_dict)
        
    # Return the start time of the time period as a ValueHelper
    @property
    def dateTime(self):
        val = weewx.units.ValueTuple(self.timespan.start, 'unix_epoch', 'group_time')
        return weewx.units.ValueHelper(val, self.context, self.formatter, self.converter)

    def __getattr__(self, stats_type):
        """Return a helper object that binds the stats database, a time period,
        and the given statistical type.
        
        stats_type: A statistical type, such as 'outTemp', or 'heatDeg'
        
        returns: An instance of class StatsTypeHelper."""
        
        # The following is so the Python version of Cheetah's NameMapper doesn't think
        # I'm a dictionary:
        if stats_type == 'has_key':
            raise AttributeError

        # Return the helper class, bound to the type:
        return StatsTypeHelper(stats_type, self.timespan, self.db, self.context, self.formatter, self.converter, **self.option_dict)
        
#===============================================================================
#                    Class StatsTypeHelper
#===============================================================================

class StatsTypeHelper(object):
    """This is the final class in the chain of helper classes. It binds the statistical
    database, a time period, and a statistical type all together.
    
    When an aggregation type (eg, 'max') is given as an attribute to it, it runs the
    query against the database, assembles the result, and returns it as a ValueHelper. 
    """

    def __init__(self, stats_type, timespan, db, context, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """ Initialize an instance of StatsTypeHelper
        
        stats_type: A string with the stats type (e.g., 'outTemp') for which the query is
        to be done.

        timespan: An instance of TimeSpan holding the time period over which the query is
        to be run
        
        db: The database the stats are to be extracted from.

        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]
        
        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]
        
        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        
        self.stats_type  = stats_type
        self.timespan    = timespan
        self.db          = db
        self.context     = context
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
    
    def max_ge(self, val):
        result = self.db.getAggregate(self.timespan, self.stats_type, 'max_ge', val)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)

    def max_le(self, val):
        result = self.db.getAggregate(self.timespan, self.stats_type, 'max_le', val)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
    
    def min_le(self, val):
        result = self.db.getAggregate(self.timespan, self.stats_type, 'min_le', val)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
    
    def sum_ge(self, val):
        result = self.db.getAggregate(self.timespan, self.stats_type, 'sum_ge', val)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
    
    def __getattr__(self, aggregateType):
        """Return statistical summary using a given aggregateType.
        
        aggregateType: The type of aggregation over which the summary is to be done.
        This is normally something like 'sum', 'min', 'mintime', 'count', etc.
        However, there are two special aggregation types that can be used to 
        determine the existence of data:
          'exists':   Return True if the observation type exists in the database.
          'has_data': Return True if the type exists and there is a non-zero
                      number of entries over the aggregation period.
                      
        returns: For special types 'exists' and 'has_data', returns a Boolean
        value. Otherwise, a ValueHelper containing the aggregation data."""

        if aggregateType == 'exists':
            return self.stats_type in self.db.statsTypes
        elif aggregateType == 'has_data':
            return self.stats_type in self.db.statsTypes and self.db.getAggregate(self.timespan, self.stats_type, 'count')[0] != 0
        elif self.stats_type in ('heatdeg', 'cooldeg'):
            # Heating and cooling degree days use a different entry point into Stats:
            result = self.db.getHeatCool(self.timespan, self.stats_type, aggregateType, self.option_dict['heatbase'], self.option_dict['coolbase'])
        else:
            result = self.db.getAggregate(self.timespan, self.stats_type, aggregateType)
        # Wrap the result in a ValueHelper:
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
    
#===============================================================================
#                          USEFUL FUNCTIONS
#===============================================================================

def config(db_dict, stats_types=None):
    """Initialize the StatsDb database
    
    Does nothing if the database has already been initialized.

    stats_types: an iterable collection with the names of the types for
    which statistics will be gathered [optional. Default is to use all
    possible types]"""
    # Try to create the database. If it already exists, an exception will
    # be thrown.
    try:
        weedb.create(db_dict)
    except weedb.DatabaseExists:
        pass

    # Check to see if it has already been configured. If it has,
    # there will be some tables in it. We can just return.
    _connect = weedb.connect(db_dict)
    if _connect.tables():
        return
    
    # If no schema has been specified, use the default stats types:
    if not stats_types:
        import user.schemas
        stats_types = user.schemas.defaultStatsTypes
    
    # Heating and cooling degrees are not actually stored in the database:
    final_stats_types = filter(lambda x : x not in ['heatdeg', 'cooldeg'], stats_types)

    # Now create all the necessary tables as one transaction:
    with weedb.Transaction(_connect) as _cursor:
        for _stats_type in final_stats_types:
            # Slightly different SQL statement for wind
            if _stats_type == 'wind':
                _cursor.execute(wind_create_str)
            else:
                _cursor.execute(std_create_str % (_stats_type,))
        _cursor.execute(meta_create_str)
        _cursor.execute(meta_replace_str, ('unit_system', 'None'))
    
    syslog.syslog(syslog.LOG_NOTICE, "stats: created schema for statistical database")

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
    
    syslog.syslog(syslog.LOG_DEBUG, "stats: Backfilling stats database.")
    t1 = time.time()
    nrecs = 0
    ndays = 0
    
    _statsDict = None
    _lastTime  = None
    
    # If a start time for the backfill wasn't given, then start with the time of
    # the last statistics recorded:
    if start_ts is None:
        start_ts = statsDb._getLastUpdate()
    
    # Go through all the archiveDb records in the time span, adding them to the
    # database
    for _rec in archiveDb.genBatchRecords(start_ts, stop_ts):

        # Get the start-of-day for the record:
        _sod_ts = weeutil.weeutil.startOfArchiveDay(_rec['dateTime'])
        # If this is the very first record, fetch a new accumulator
        if not _statsDict:
            _statsDict = statsDb._getDayStats(_sod_ts)
        # Try updating. If the time is out of the accumulator's time span, an
        # exception will get thrown.
        try:
            _statsDict.addRecord(_rec)
        except weewx.accum.OutOfSpan:
            # The record is out of the time span.
            # Save the old accumulator:
            statsDb._setDayStats(_statsDict, _rec['dateTime'])
            ndays += 1
            # Get a new accumulator:
            _statsDict = statsDb._getDayStats(_sod_ts)
            # try again
            _statsDict.addRecord(_rec)
         
        nrecs += 1
        # Remember the timestamp for this record.
        _lastTime = _rec['dateTime']

    # We're done. Record the stats for the last day.
    if _statsDict:
        statsDb._setDayStats(_statsDict, _lastTime)
        ndays += 1
    
    t2 = time.time()
    tdiff = t2 - t1
    if nrecs:
        syslog.syslog(syslog.LOG_NOTICE, 
                      "stats: backfilled %d days of statistics with %d records in %.2f seconds" % (ndays, nrecs, tdiff))
    else:
        syslog.syslog(syslog.LOG_INFO,
                      "stats: stats database up to date.")

    return nrecs
