#
#    Copyright (c) 2009, 2010, 2011, 2012, 2013 Tom Keffer <tkeffer@gmail.com>
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
import sys
import syslog
import time

import weedb
import weeutil.weeutil
import weewx.accum
import weewx.units
import weewx.wxformulas

#===============================================================================
# The SQL statements used in the stats database
#
# In what follows, a "schema-tuple" is a 2-way tuple (obs_name, obs_type), where
# obs_name is something like 'barometer', or 'wind'. The obs_type is either
# 'REAL' or 'VECTOR'.
#
#===============================================================================

sql_create_strs = {'REAL'  : """CREATE TABLE %s ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                             """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER);""", 
                   'VECTOR': """CREATE TABLE %s ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                             """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, """\
                             """gustdir REAL, xsum REAL, ysum REAL, squaresum REAL, squarecount INTEGER);"""}

sql_replace_strs = {'REAL'   : """REPLACE INTO %s VALUES(?, ?, ?, ?, ?, ?, ?)""",
                    'VECTOR' : """REPLACE INTO %s VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""}

def _sql_create_string_factory(schema_tuple):
    """Returns whatever SQL string is required to create the desired observation type"""
    sql_str = sql_create_strs[schema_tuple[1].upper()]
    return sql_str % schema_tuple[0]

def _sql_replace_string_factory(schema_dict, obs_type):
    """Returns whatever SQL string is required to update the desired observation type"""
    sql_str = sql_replace_strs[schema_dict[obs_type]]
    return sql_str % obs_type
        
meta_create_str   = """CREATE TABLE metadata (name CHAR(20) NOT NULL UNIQUE PRIMARY KEY, value TEXT);"""
schema_create_str = """CREATE TABLE _stats_schema (obs_name CHAR(20) NOT NULL UNIQUE, obs_type CHAR(12), reserve1 CHAR(20), reserve2 CHAR(20))""" 
                 
meta_replace_str = """REPLACE into metadata VALUES(?, ?)"""  

select_update_str = """SELECT value FROM metadata WHERE name = 'lastUpdate';"""
select_unit_str   = """SELECT value FROM metadata WHERE name = 'unit_system';"""

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
#                        Class StatsDb
#===============================================================================

class StatsDb(object):
    """Manage reading from the sqlite3 statistical database. 
    
    This class acts as a wrapper around the stats database, with a set
    of methods for retrieving records from the statistical compilation. 

    An attempt to open an uninitialized or nonexistent database will result
    in an exception of type weedb.OperationalError being thrown.
    
    After initialization, the attribute self.statsTypes will contain a list
    of the observation types in the statistical database.
    
    The SQL database consists of a separate table for each type. The columns 
    of a table are things like min, max, the timestamps for min and max, 
    count and sum. A count and sum are kept to make it easy to
    calculate averages for different time periods.  The wind data table also
    includes sum of squares (for calculating rms speeds) and wind gust
    direction.
    
    For example, for type 'outTemp' (outside temperature), there is 
    a table of name 'outTemp' with the following column names:
    
        dateTime, min, mintime, max, maxtime, sum, count
        
    Vector data (example, 'wind') is similar, except it adds a few extra columns:
    
        dateTime, min, mintime, max, maxtime, sum, count, 
          gustdir, xsum, ysum, squaresum, squarecount
    
    'xsum' and 'ysum' are the sums of the x- and y-components of the wind vector.
    'squaresum' is the sum of squares of the windspeed (useful for calculating rms speed).
    'squarecount' (perhaps not the best name, but it's there for historical reasons)
    is the number of items added to 'xsum' and 'ysum'.
    
    In addition to all the tables for each type, there are two other tables:
    
     o The first is called 'metadata'. It currently holds the time of the last update, and the
       unit system in use in the database. If the unit system is missing, then it is assumed
       to be 'US'.
    
     o The second is called _stats_schema. Each row in the table is a 2-way 
       schema-tuple (obs_type, obs_type). See comments above about schema-tuples.
    
    ATTRIBUTES
    
    schema: A dictionary with key obs_name, and value of 'REAL' or 'VECTOR'.
    
    statsTypes: A list of all the obs_name supported by this database.
    
    std_unit_system: The unit system in use (weewx.US or weewx.METRIC), or
    None if the system has been specified yet.
    
    accumClass: The class to be used as an accumulator. Default is weewx.accum.WXAccum.
    This can be changed for specialized, non-weather, applications.
    """
    
    def __init__(self, connection):
        """Create an instance of StatsDb to manage a database.
        
        If the database is uninitialized, an exception of type weewx.UninitializedDatabase
        will be raised. 
        
        connection: A weedb connection to the stats database. """
        
        self.connection = connection
        try:
            self.schema = self._getSchema()
        except weedb.OperationalError, e:
            self.close()
            raise weewx.UninitializedDatabase(e)
        # The class to be used as an accumulator. This can be changed by the
        # calling program.
        self.AccumClass = weewx.accum.WXAccum
        self.statsTypes = self.schema.keys()
        self.std_unit_system = self._getStdUnitSystem()
        
    #--------------------------- STATIC METHODS -----------------------------------
    
    @staticmethod
    def open(stats_db_dict):
        """Helper function to return an opened StatsDb object.
        
        stats_db_dict: A dictionary passed on to weedb. It should hold
        the keywords necessary to open the database."""
        connection = weedb.connect(stats_db_dict)
        return StatsDb(connection)

    @staticmethod
    def open_with_create(stats_db_dict, stats_schema):
        """Open a StatsDb database, creating and initializing it if necessary.
        
        stats_db_dict: A dictionary passed on to weedb. It should hold
        the keywords necessary to open the database.

        stats_schema: an iterable collection of schema-tuples. The first member of the
        tuple is the observation type, the second is either the string 'REAL' (scalar value), 
        or 'VECTOR' (vector value). The database will be initialized to collect stats
        for only the given types.
        
        Returns:
        An instance of StatsDb"""

        # If the database exists and has been initialized, then
        # this will be successful. If not, an exception will be thrown.
        try:
            stats = StatsDb.open(stats_db_dict)
            # The database exists and has been initialized. Return it.
            return stats
        except (weedb.OperationalError, weewx.UninitializedDatabase):
            pass
        
        # The database does not exist. Initialize and return it.
        _connect = StatsDb._init_db(stats_db_dict, stats_schema)
        
        return StatsDb(_connect)

    @staticmethod
    def _init_db(stats_db_dict, stats_schema):
        """Create and initialize a database."""
        
        # First, create the database if necessary. If it already exists, an
        # exception will be thrown.
        try:
            weedb.create(stats_db_dict)
        except weedb.DatabaseExists:
            pass

        # Get a connection
        _connect = weedb.connect(stats_db_dict)
        
        try:
            # Now create all the necessary tables as one transaction:
            with weedb.Transaction(_connect) as _cursor:
                for _stats_tuple in stats_schema:
                    # Get the SQL string necessary to create the type:
                    _sql_create_str = _sql_create_string_factory(_stats_tuple)
                    _cursor.execute(_sql_create_str)
                # Now create the meta table:
                _cursor.execute(meta_create_str)
                # Set the unit system to 'None' (Unknown) for now
                _cursor.execute(meta_replace_str, ('unit_system', 'None'))
                # Finally, save the stats schema:
                StatsDb._save_schema(_cursor, stats_schema)
        except Exception, e:
            _connect.close()
            syslog.syslog(syslog.LOG_ERR, "archive: Unable to create stats database.")
            syslog.syslog(syslog.LOG_ERR, "****     %s" % (e,))
            raise
    
        syslog.syslog(syslog.LOG_NOTICE, "stats: created schema for statistical database")

        return _connect
    
    @staticmethod
    def _save_schema(cursor, stats_schema):
        cursor.execute(schema_create_str)
        for stats_tuple in stats_schema:
            cursor.execute("INSERT INTO _stats_schema (obs_name, obs_type) VALUES(?, ?)", stats_tuple)

    #--------------------------- REGULAR METHODS -----------------------------------

    @property
    def database(self):
        return self.connection.database
    
    def close(self):
        self.connection.close()
        
    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):
        self.close()    
    
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
            # The following is for backwards compatibility when ValueTuples had
            # just two members. This hack avoids breaking old skins.
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
        _row = self.xeqSql(sqlDict[aggregateType], interDict)

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
            if _row == (0.0, 0.0):
                _result = None
            deg = 90.0 - math.degrees(math.atan2(_row[1], _row[0]))
            _result = deg if deg >= 0 else deg + 360.0
        else:
            # Unknown aggregation. Return None
            _result = None

        # Look up the unit type and group of this combination of stats type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, stats_type, aggregateType)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
        
    def backfillFrom(self, archiveDb, start_ts = None, stop_ts = None):
        """Fill the statistical database from an archive database.
        
        Normally, the stats database if filled by LOOP packets (to get maximum time
        resolution), but if the database gets corrupted, or if a new user is
        starting up with imported wview data, it's necessary to recreate it from
        straight archive data. The Hi/Lows will all be there, but the times won't be
        any more accurate than the archive period.
        
        archiveDb: An instance of weewx.archive.Archive
        
        start_ts: Archive data with a timestamp greater than this will be
        used. [Optional. Default is to start with the first datum in the archive.]
        
        stop_ts: Archive data with a timestamp less than or equal to this will be
        used. [Optional. Default is to end with the last datum in the archive.]
        
        returns: The number of records backfilled."""
        
        syslog.syslog(syslog.LOG_DEBUG, "stats: Backfilling stats database.")
        t1 = time.time()
        nrecs = 0
        ndays = 0
        
        _statsDict = None
        _lastTime  = None
        
        # If a start time for the backfill wasn't given, then start with the time of
        # the last statistics recorded:
        if start_ts is None:
            start_ts = self._getLastUpdate()
        
        # Go through all the archiveDb records in the time span, adding them to the
        # database
        for _rec in archiveDb.genBatchRecords(start_ts, stop_ts):
    
            # Get the start-of-day for the record:
            _sod_ts = weeutil.weeutil.startOfArchiveDay(_rec['dateTime'])
            # If this is the very first record, fetch a new accumulator
            if not _statsDict:
                _statsDict = self._getDayStats(_sod_ts)
            # Try updating. If the time is out of the accumulator's time span, an
            # exception will get thrown.
            try:
                _statsDict.addRecord(_rec)
            except weewx.accum.OutOfSpan:
                # The record is out of the time span.
                # Save the old accumulator:
                self._setDayStats(_statsDict, _rec['dateTime'])
                ndays += 1
                # Get a new accumulator:
                _statsDict = self._getDayStats(_sod_ts)
                # try again
                _statsDict.addRecord(_rec)
             
            # Remember the timestamp for this record.
            _lastTime = _rec['dateTime']
            nrecs += 1
            if nrecs%1000 == 0:
                print >>sys.stdout, "Records processed: %d; Last date: %s\r" % (nrecs, weeutil.weeutil.timestamp_to_string(_lastTime)),
                sys.stdout.flush()
    
        # We're done. Record the stats for the last day.
        if _statsDict:
            self._setDayStats(_statsDict, _lastTime)
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

    def xeqSql(self, rawsqlStmt, interDict):
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
            return _cursor.fetchone()
        finally:
            _cursor.close()
        
    #--------------------------- UTILITY FUNCTIONS -----------------------------------

    def _getDayStats(self, sod_ts):
        """Return an instance an appropriate accumulator, initialized to a given day's statistics.

        sod_ts: The timestamp of the start-of-day of the desired day."""
                
        # Get the TimeSpan for the day starting with sod_ts:
        timespan = weeutil.weeutil.archiveDaySpan(sod_ts,0)

        # Get an empty accumulator
        _stats_dict = self.AccumClass(timespan)

        # For each kind of stats, execute the SQL query and hand the results on
        # to the accumulator.
        for stats_type in self.statsTypes:
            _row = self.xeqSql("SELECT * FROM %s WHERE dateTime = %d" % (stats_type, sod_ts), {})

            # If the date does not exist in the database yet then _row will be None.
            _stats_tuple = _row[1:] if _row is not None else None
            # Pick the right kind of Stats object
            if self.schema[stats_type] == 'REAL':
                _stats_dict[stats_type] = weewx.accum.ScalarStats(_stats_tuple)
            elif self.schema[stats_type] == 'VECTOR':
                _stats_dict[stats_type] = weewx.accum.VecStats(_stats_tuple)
        
        return _stats_dict

    def _setDayStats(self, dayStatsDict, lastUpdate):
        """Write all statistics for a day to the database in a single transaction.
        
        dayStatsDict: an accumulator. See weewx.accum
        
        lastUpdate: the time of the last update will be set to this. Normally, this
        is the timestamp of the last archive record added to the instance
        dayStatsDict."""

        _sod = dayStatsDict.timespan.start

        # Using the _connection as a context manager means that
        # in case of an error, all tables will get rolled back.
        with weedb.Transaction(self.connection) as _cursor:

            # For each stats type...
            for _stats_type in self.statsTypes:
                # ... get the stats tuple to be written to the database...
                _write_tuple = (_sod,) + dayStatsDict[_stats_type].getStatsTuple()
                # ... and an appropriate SQL command ...
                _sql_replace_str = _sql_replace_string_factory(self.schema, _stats_type)
                # ... and write to the database.
                _cursor.execute(_sql_replace_str,_write_tuple)
                
            # Set the unit system if it has not been set before. 
            # To do this, first see if this file has ever been used:
            last_update = self._getLastUpdate(_cursor)
            if last_update is None:
                # File has never been used. Set the unit system:
                _cursor.execute(meta_replace_str, ('unit_system', str(int(dayStatsDict.unit_system))))
            else:
                # The file has been used. Make sure the new data uses
                # the same unit system as the database.
                unit_system = self._getStdUnitSystem(_cursor)
                if unit_system != dayStatsDict.unit_system:
                    raise ValueError("stats: Data uses different unit system (0x%x) than stats file (0x%x)" % (dayStatsDict.unit_system, unit_system))
            # Update the time of the last stats update:
            _cursor.execute(meta_replace_str, ('lastUpdate', str(int(lastUpdate))))
            
    def _getLastUpdate(self, cursor=None):
        """Returns the time of the last update to the statistical database."""

        if cursor:
            cursor.execute(select_update_str)
            _row = cursor.fetchone()
        else:
            _row = self.xeqSql(select_update_str, {})
        return int(_row[0]) if _row else None

    def _getStdUnitSystem(self, cursor=None):
        """Returns the unit system in use in the stats database."""
        
        # If the metadata "unit_system" is missing, then it is an older style
        # stats database, which are always in the US Customary standard unit
        # system. If it exists, but is 'None', then the units have not been
        # specified yet. Otherwise, it equals the unit system used by the
        # database.

        if cursor:
            cursor.execute(select_unit_str)
            _row = cursor.fetchone()
        else:
            _row = self.xeqSql(select_unit_str, {})
        
        # Check for an older database:
        if not _row:
            return weewx.US
        
        # It's a newer style database. Check for 'None' and return.
        unit_system = int(_row[0]) if str(_row[0])!='None' else None
        return unit_system

    def _getSchema(self):
        """Get the weewx stats schema used to initialize the stats database."""
        
        # Early versions of the stats database did not have an explicit
        # schema. In this case, an exception will be raised. Be prepared to
        # catch it, then back calculate the schema.
        _cursor = self.connection.cursor()
        try:
            _cursor.execute("SELECT obs_name, obs_type from _stats_schema")
            _stats_schema_dict = dict((str(_row[0]), str(_row[1])) for _row in _cursor)
        except weedb.OperationalError:
            # The stats schema does not exist. Compute it, then save it.
            _stats_schema = self._backcompute_schema(_cursor)
            StatsDb._save_schema(_cursor, _stats_schema)
            _stats_schema_dict = dict(_stats_schema)
        finally:
            _cursor.close()

        return _stats_schema_dict
        
    def _backcompute_schema(self, cursor):
        """Used to extract the schema out of older databases that do
        not have the schema metadata table _stats_schema."""
        raw_stats_types = self.connection.tables()
        if not raw_stats_types:
            raise weedb.OperationalError("Unitialized stats database")
        # Some stats database have schemas for heatdeg and cooldeg (even though
        # they are not used) due to an earlier bug. Filter them out. Also,
        # filter out the metadata table. In case the same database is being used
        # for the archive data, filter out the 'archive' database.
        stats_types = [s for s in raw_stats_types if s not in ['heatdeg','cooldeg','metadata', 'archive']]
        stats_schema = []
        for stat_type in stats_types:
            ncol = len(self.connection.columnsOf(stat_type))
            stats_schema.append((stat_type, 'REAL' if ncol==7 else 'VECTOR'))
        return stats_schema

#===============================================================================
#                        function get_heat_cool
#===============================================================================

def get_heat_cool(statsdb, timespan, stats_type, aggregateType, heatbase_t, coolbase_t):
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
        assert(stats_type in ['heatdeg', 'cooldeg'])

    # Only summation (total) or average heating or cooling degree days is supported:
    if aggregateType not in ['sum', 'avg']:
        raise weewx.ViolatedPrecondition, "Aggregate type %s for %s not supported." % (aggregateType, stats_type)

    _sum = 0.0
    _count = 0
    for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
        # Get the average temperature for the day as a value tuple:
        Tavg_t = statsdb.getAggregate(daySpan, 'outTemp', 'avg')
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
    (t, g) = weewx.units.getStandardUnitType(statsdb.std_unit_system, stats_type, aggregateType)
    # Return as a value tuple
    return weewx.units.ValueTuple(_result, t, g)
    
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
            result = get_heat_cool(self.db, self.timespan, self.stats_type, aggregateType, self.option_dict['heatbase'], self.option_dict['coolbase'])
        else:
            result = self.db.getAggregate(self.timespan, self.stats_type, aggregateType)
        # Wrap the result in a ValueHelper:
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
