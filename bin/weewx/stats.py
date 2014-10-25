#
#    Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Adds daily summaries to the archive database.

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
import os
import sys
import syslog
import time

import weedb
import weeutil.weeutil
import weewx.accum
import weewx.units
import weewx.archive

#===============================================================================
# The SQL statements used in the stats database
#===============================================================================

sql_create_str = "CREATE TABLE day_%s (dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, "\
  "min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, "\
  "wsum REAL, sumtime INTEGER);"
                             
meta_create_str   = """CREATE TABLE day__metadata (name CHAR(20) NOT NULL UNIQUE PRIMARY KEY, value TEXT);"""
meta_replace_str  = """REPLACE INTO day__metadata VALUES(?, ?)"""  

select_update_str = """SELECT value FROM day__metadata WHERE name = 'lastUpdate';"""

# Set of SQL statements to be used for calculating aggregate statistics. Key is the aggregation type.
sqlDict = {'min'        : "SELECT MIN(min) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'minmax'     : "SELECT MIN(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'max'        : "SELECT MAX(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'maxmin'     : "SELECT MAX(min) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'meanmin'    : "SELECT AVG(min) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'meanmax'    : "SELECT AVG(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'maxsum'     : "SELECT MAX(sum) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'mintime'    : "SELECT mintime FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "min = (SELECT MIN(min) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
           'maxmintime' : "SELECT mintime FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "min = (SELECT MAX(min) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
           'maxtime'    : "SELECT maxtime FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "max = (SELECT MAX(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
           'minmaxtime' : "SELECT maxtime FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "max = (SELECT MIN(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
           'maxsumtime' : "SELECT maxtime FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "sum = (SELECT MAX(sum) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
           'gustdir'    : "SELECT max_dir FROM day_%(day_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                          "max = (SELECT MAX(max) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s)",
           'sum'        : "SELECT SUM(sum) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'count'      : "SELECT SUM(count) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'avg'        : "SELECT SUM(wsum),SUM(sumtime) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'rms'        : "SELECT SUM(wsquaresum),SUM(sumtime) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'vecavg'     : "SELECT SUM(xsum),SUM(ysum),SUM(dirsumtime)  FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'vecdir'     : "SELECT SUM(xsum),SUM(ysum) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'max_ge'     : "SELECT SUM(max >= %(val)s) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'max_le'     : "SELECT SUM(max <= %(val)s) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'min_le'     : "SELECT SUM(min <= %(val)s) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
           'sum_ge'     : "SELECT SUM(sum >= %(val)s) FROM day_%(day_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s"}

#===============================================================================
#                        Class DaySummaryArchive
#===============================================================================

class DaySummaryArchive(weewx.archive.Archive):
    """Manage reading from the sqlite3 statistical database. 
    
    The daily summary consists of a separate table for each type. The columns 
    of each table are things like min, max, the timestamps for min and max, 
    sum and sumtime. The values sum and sumtime are kept to make it easy to
    calculate averages for different time periods.
    
    For example, for type 'outTemp' (outside temperature), there is 
    a table of name 'day_outTemp' with the following column names:
    
        dateTime, min, mintime, max, maxtime, sum, count, wsum, sumtime
    
    wsum is the "Weighted sum," that is, the sum weighted by the archive interval.
    sumtime is the sum of the archive intervals.
        
    In addition to all the tables for each type, there is one additional table called
    'day__metadata', which currently holds the time of the last update. """

    def __init__(self, archive_db_dict, archiveSchema=None):
        """Initialize an instance of DaySummarArchive
        
        archive_db_dict: A database dictionary containing items necessary to open up the
        database.
        
        archiveSchema: The schema to be used. Optional. If not supplied, then an
        exception of type weedb.OperationalError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """
        # Initialize my superclass:
        super(DaySummaryArchive, self).__init__(archive_db_dict, archiveSchema)
        
        # If the database has not been initialized with the daily summaries, then create the
        # necessary tables, but only if a schema has been given.
        if 'day__metadata' not in self.connection.tables():
            # Daily summary tables have not been created yet.
            if archiveSchema is None:
                # The user has not indicated he wants initialization. Raise an exception
                raise weedb.OperationalError("Uninitialized day summaries")
            # Create all the daily summary tables as one transaction:
            with weedb.Transaction(self.connection) as _cursor:
                self._initialize_day_tables(archiveSchema, _cursor)
            syslog.syslog(syslog.LOG_NOTICE, "stats: Created daily summary tables")
        
        # Get a list of all the observation types which have daily summaries
        all_tables = self.connection.tables()
        self.daykeys = [x[4:] for x in all_tables if (x.startswith('day_') and x!='day__metadata')]

    def _initialize_day_tables(self, archiveSchema, cursor):
        """Initialize the tables needed for the daily summary."""
        # Create the tables needed for the daily summaries.
        for _obs_type in self.obskeys:
            cursor.execute(sql_create_str % _obs_type)
        # Then create the meta table:
        cursor.execute(meta_create_str)

    def _addSingleRecord(self, record, cursor, log_level):
        """Specialized version that updates the daily summaries, as well as the 
        main archive table."""
        
        # First let my superclass handle adding the record to the main archive table:
        super(DaySummaryArchive, self)._addSingleRecord(record, cursor, log_level=syslog.LOG_DEBUG)

        # Get the start of day for the record:        
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])

        # Now add to the daily summary for the appropriate day:
        _day_summary = self._get_day_summary(_sod_ts, cursor)
        _day_summary.addRecord(record)
        self._set_day_summary(_day_summary, record['dateTime'], cursor)
        syslog.syslog(log_level, "stats:   added %s to daily summary in '%s'" % 
                      (weeutil.weeutil.timestamp_to_string(record['dateTime']), 
                       os.path.basename(self.connection.database)))
        
    def updateHiLo(self, accumulator):
        """Use the contents of an accumulator to update the daily hi/lows."""
        
        # Get the start-of-day for the timespan in the accumulator
        _sod_ts = weeutil.weeutil.startOfArchiveDay(accumulator.timespan.stop)

        with weedb.Transaction(self.connection) as _cursor:
            # Retrieve the stats seen so far:
            _stats_dict = self._get_day_summary(_sod_ts, _cursor)
            # Update them with the contents of the accumulator:
            _stats_dict.updateHiLo(accumulator)
            # Then save the results:
            self._set_day_summary(_stats_dict, accumulator.timespan.stop, _cursor)
        
    def getAggregate(self, timespan, obs_type, aggregateType, **option_dict):
        """Returns an aggregation of a statistical type for a given time period.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
        
        aggregateType: The type of aggregation to be done. The keys in the dictionary
        sqlDict above are the possible aggregation types. 
        
        option_dict: Some aggregations require optional values
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F').
        The third element is the unit group (eg, "group_temperature") """
        global sqlDict
        
        # This entry point won't work for heating or cooling degree days:
        if weewx.debug:
            assert(obs_type not in ['heatdeg', 'cooldeg'])
            assert(timespan is not None)

        # Check to see if this is a valid stats type:
        if obs_type not in self.daykeys:
            raise AttributeError, "Unknown stats type %s" % (obs_type,)

        val = option_dict.get('val')
        if val is None:
            target_val = None
        else:
            # The following is for backwards compatibility when ValueTuples had
            # just two members. This hack avoids breaking old skins.
            if len(val) == 2:
                if val[1] in ['degree_F', 'degree_C']:
                    val += ("group_temperature",)
                elif val[1] in ['inch', 'mm', 'cm']:
                    val += ("group_rain",)
            target_val = weewx.units.convertStd(val, self.std_unit_system)[0]

        # This dictionary is used for interpolating the SQL statement.
        interDict = {'start'         : weeutil.weeutil.startOfDay(timespan.start),
                     'stop'          : timespan.stop,
                     'day_key'       : obs_type,
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
        elif aggregateType in ['min', 'maxmin', 'max', 'minmax', 'meanmin', 'meanmax', 'maxsum', 'sum', 'gustdir']:
            # These aggregates are passed through 'as is'.
            _result = _row[0]
        
        elif aggregateType in ['mintime', 'maxmintime', 'maxtime', 'minmaxtime', 'maxsumtime',
                               'count', 'max_ge', 'max_le', 'min_le', 'sum_ge']:
            # These aggregates are always integers:
            _result = int(_row[0])

        elif aggregateType == 'avg':
            _result = _row[0]/_row[1] if _row[1] else None

        elif aggregateType == 'rms':
            _result = math.sqrt(_row[0]/_row[1]) if _row[1] else None
        
        elif aggregateType == 'vecavg':
            _result = math.sqrt((_row[0]**2 + _row[1]**2) / _row[2]**2) if _row[2] else None
        
        elif aggregateType == 'vecdir':
            if _row == (0.0, 0.0):
                _result = None
            deg = 90.0 - math.degrees(math.atan2(_row[1], _row[0]))
            _result = deg if deg >= 0 else deg + 360.0
        else:
            # Unknown aggregation. Return None
            _result = None

        # Look up the unit type and group of this combination of stats type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, obs_type, aggregateType)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
        
    def exists(self, obs_type):
        """Checks whether the observation type exists in the database."""

        # Check to see if this is a valid stats type:
        return obs_type in self.daykeys

    def has_data(self, obs_type, timespan):
        """Checks whether the observation type exists in the database and whether it has any data."""

        return self.exists(obs_type) and self.getAggregate(timespan, obs_type, 'count')[0] != 0

    def backfill_day_summary(self, start_ts=None, stop_ts=None):
        """Fill the statistical database from an archive database.
        
        Normally, the daily summaries get filled by LOOP packets (to get maximum time
        resolution), but if the database gets corrupted, or if a new user is
        starting up with imported wview data, it's necessary to recreate it from
        straight archive data. The Hi/Lows will all be there, but the times won't be
        any more accurate than the archive period.
        
        start_ts: Archive data with a timestamp greater than this will be
        used. [Optional. Default is to start with the first datum in the archive.]
        
        stop_ts: Archive data with a timestamp less than or equal to this will be
        used. [Optional. Default is to end with the last datum in the archive.]
        
        returns: The number of records backfilled."""
        
        syslog.syslog(syslog.LOG_DEBUG, "stats: Backfilling daily summaries.")
        t1 = time.time()
        nrecs = 0
        ndays = 0
        
        _day_accum = None
        _lastTime  = None
        
        # If a start time for the backfill wasn't given, then start with the time of
        # the last statistics recorded:
        if start_ts is None:
            start_ts = self._getLastUpdate()

        with weedb.Transaction(self.connection) as _cursor:
            # Go through all the archiveDb records in the time span, adding them to the
            # database
            start = start_ts + 1 if start_ts else None
            for _rec in self.genBatchRecords(start, stop_ts):
                # Get the start-of-day for the record:
                _sod_ts = weeutil.weeutil.startOfArchiveDay(_rec['dateTime'])
                # If this is the very first record, fetch a new accumulator
                if not _day_accum:
                    _day_accum = self._get_day_summary(_sod_ts)
                # Try updating. If the time is out of the accumulator's time span, an
                # exception will get raised.
                try:
                    _day_accum.addRecord(_rec)
                except weewx.accum.OutOfSpan:
                    # The record is out of the time span.
                    # Save the old accumulator:
                    self._set_day_summary(_day_accum, _rec['dateTime'], _cursor)
                    ndays += 1
                    # Get a new accumulator:
                    _day_accum = self._get_day_summary(_sod_ts)
                    # try again
                    _day_accum.addRecord(_rec)
                 
                # Remember the timestamp for this record.
                _lastTime = _rec['dateTime']
                nrecs += 1
                if nrecs%1000 == 0:
                    print >>sys.stdout, "Records processed: %d; Last date: %s\r" % (nrecs, weeutil.weeutil.timestamp_to_string(_lastTime)),
                    sys.stdout.flush()
    
            # We're done. Record the stats for the last day.
            if _day_accum:
                self._set_day_summary(_day_accum, _lastTime, _cursor)
                ndays += 1
        
        t2 = time.time()
        tdiff = t2 - t1
        if nrecs:
            syslog.syslog(syslog.LOG_NOTICE, 
                          "stats: Processed %d records to backfill %d day summaries in %.2f seconds" % (nrecs, ndays, tdiff))
        else:
            syslog.syslog(syslog.LOG_INFO,
                          "stats: Daily summary up to date.")
    
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

    def _get_day_summary(self, sod_ts, cursor=None):
        """Return an instance of an appropriate accumulator, initialized to a given day's statistics.

        sod_ts: The timestamp of the start-of-day of the desired day."""
                
        # Get the TimeSpan for the day starting with sod_ts:
        _timespan = weeutil.weeutil.archiveDaySpan(sod_ts,0)

        # Get an empty day accumulator:
        _day_accum = weewx.accum.Accum(_timespan)
        
        _cursor = cursor if cursor else self.connection.cursor()

        try:
            # For each observation type, execute the SQL query and hand the results on
            # to the accumulator.
            for _day_key in self.daykeys:
                _cursor.execute("SELECT * FROM day_%s WHERE dateTime = ?" % _day_key, (_day_accum.timespan.start,))
                _row = _cursor.fetchone()
                # If the date does not exist in the database yet then _row will be None.
                _stats_tuple = _row[1:] if _row is not None else None
                _day_accum.set_stats(_day_key, _stats_tuple)
            
            return _day_accum
        finally:
            if not cursor:
                _cursor.close()

    def _set_day_summary(self, day_accum, lastUpdate, cursor):
        """Write all statistics for a day to the database in a single transaction.
        
        day_accum: an accumulator with the daily summary. See weewx.accum
        
        lastUpdate: the time of the last update will be set to this. Normally, this
        is the timestamp of the last archive record added to the instance
        day_accum."""

        # Make sure the new data uses the same unit system as the database.
        self._check_unit_system(day_accum.unit_system)

        _sod = day_accum.timespan.start

        # For each stats type...
        for _summary_type in day_accum:
            # Don't try an update for types not in the database:
            if _summary_type not in self.daykeys:
                continue
            # ... get the stats tuple to be written to the database...
            _write_tuple = (_sod,) + day_accum[_summary_type].getStatsTuple()
            # ... and an appropriate SQL command with the correct number of question marks ...
            _qmarks = ','.join(len(_write_tuple)*'?')
            _sql_replace_str = "REPLACE INTO day_%s VALUES(%s)" % (_summary_type, _qmarks)
            # ... and write to the database. In case the type doesn't appear in the database,
            # be prepared to catch an exception:
            try:
                cursor.execute(_sql_replace_str, _write_tuple)
            except weedb.OperationalError, e:
                syslog.syslog(syslog.LOG_ERR, "stats: Operational error database %s; %s" % (self.database, e))
                
        # Update the time of the last stats update:
        cursor.execute(meta_replace_str, ('lastUpdate', str(int(lastUpdate))))
            
    def _getLastUpdate(self, cursor=None):
        """Returns the time of the last update to the statistical database."""

        if cursor:
            cursor.execute(select_update_str)
            _row = cursor.fetchone()
        else:
            _row = self.xeqSql(select_update_str, {})
        return int(_row[0]) if _row else None
    
    def drop_daily(self):
        """Drop the daily summaries."""
        _all_tables = self.connection.tables()
        with weedb.Transaction(self.connection) as _cursor:
            for _table_name in _all_tables:
                if _table_name.startswith('day_'):
                    _cursor.execute("DROP TABLE %s" % _table_name)

        del self.daykeys
