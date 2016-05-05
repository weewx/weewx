#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with a weewx archive."""
from __future__ import with_statement
import math
import syslog
import sys
import time

import weewx.accum
from weewx.units import ValueTuple
import weewx.units
import weeutil.weeutil
import weedb

#==============================================================================
#                         class Manager
#==============================================================================

class Manager(object):
    """Manages a database table. Offers a number of convenient member
    functions for querying and inserting data into the table. 
    These functions encapsulate whatever sql statements are needed.
    
    A limitation of this implementation is that it caches the timestamps of the 
    first and last record in the table. Normally, the caches get updated as data comes
    in. However, if one manager is updating the table, wile another is doing
    aggregate queries, the latter manager will be unaware of later records in
    the database, and may choose the wrong query strategy. In this might be the case,
    call member function _sync() before starting the query. 
    
    USEFUL ATTRIBUTES
    
    database_name: The name of the database the manager is bound to.
    
    table_name: The name of the main, archive table.
    
    sqlkeys: A list of the SQL keys that the database table supports.
    
    obskeys: A list of the observation types that the database table supports.
    
    std_unit_system: The unit system used by the database table.
    
    first_timestamp: The timestamp of the earliest record in the table.
    
    last_timestamp: The timestamp of the last record in the table."""
    
    def __init__(self, connection, table_name='archive', schema=None):
        """Initialize an object of type Manager.
        
        connection: A weedb connection to the database to be managed.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'.
        
        schema: The schema to be used. Optional. If not supplied, then an
        exception of type weedb.ProgrammingError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """

        self.connection = connection
        self.table_name = table_name

        # Now get the SQL types. 
        try:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        except weedb.ProgrammingError:
            # Database exists, but is uninitialized. Did the caller supply
            # a schema?
            if schema is None:
                # No. Nothing to be done.
                syslog.syslog(syslog.LOG_ERR, "manager: cannot get columns of table %s, and no schema specified" % self.table_name)
                raise
            # Database exists, but has not been initialized. Initialize it.
            self._initialize_database(schema)
            # Try again:
            self.sqlkeys = self.connection.columnsOf(self.table_name)

        # Set up cached data:
        self._sync()
        
    @classmethod
    def open(cls, database_dict, table_name='archive'):
        """Open and return a Manager or a subclass of Manager.  
        
        database_dict: A database dictionary holding the information necessary
        to open the database.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'. """

        # This will raise a weedb.OperationalError if the database does
        # not exist. The 'open' method we are implementing never attempts an
        # initialization, so let it go by.
        connection = weedb.connect(database_dict)

        # Create an instance of the right class and return it:
        dbmanager = cls(connection, table_name)
        return dbmanager
    
    @classmethod
    def open_with_create(cls, database_dict, table_name='archive', schema=None):
        """Open and return a Manager or a subclass of Manager, initializing
        if necessary.  
        
        database_dict: A database dictionary holding the information necessary
        to open the database.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'.
        
        schema: The schema to be used. If not supplied, then an
        exception of type weedb.OperationalError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """
    
        # This will raise a weedb.OperationalError if the database does
        # not exist. 
        try:
            connection = weedb.connect(database_dict)
        except weedb.OperationalError:
            # Database does not exist. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                syslog.syslog(syslog.LOG_ERR, "manager: cannot open database, and no schema specified")
                raise
            # Yes. Create the database:
            weedb.create(database_dict)
            # Now I can get a connection
            connection = weedb.connect(database_dict)

        # Create an instance of the right class and return it:
        dbmanager = cls(connection, table_name=table_name, schema=schema)
        return dbmanager
    
    @property
    def database_name(self):
        return self.connection.database_name
    
    @property
    def obskeys(self):
        """The list of observation types"""
        return [obs_type for obs_type in self.sqlkeys if obs_type not in ['dateTime', 'usUnits', 'interval']]
    
    def close(self):
        self.connection.close()
        del self.sqlkeys
        del self.first_timestamp
        del self.last_timestamp
        del self.std_unit_system

    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.close()    
    
    def _initialize_database(self, schema):
        """Initialize the tables needed for the archive.
        
        schema: The schema to be used
        """
    
        # List comprehension of the types, joined together with commas. Put
        # the SQL type in backquotes, because at least one of them ('interval')
        # is a MySQL reserved word
        _sqltypestr = ', '.join(["`%s` %s" % _type for _type in schema])

        try:
            with weedb.Transaction(self.connection) as _cursor:
                _cursor.execute("CREATE TABLE %s (%s);" % (self.table_name, _sqltypestr, ))
        except weedb.DatabaseError, e:
            syslog.syslog(syslog.LOG_ERR, "manager: Unable to create table '%s' in database '%s': %s" % 
                          (self.table_name, self.database_name, e))
            raise
    
        syslog.syslog(syslog.LOG_NOTICE, "manager: Created and initialized table '%s' in database '%s'" % 
                      (self.table_name, self.database_name))

    def _sync(self):
        """Resynch the internal caches."""
        # Fetch the first row in the database to determine the unit system in
        # use. If the database has never been used, then the unit system is
        # still indeterminate --- set it to 'None'.
        _row = self.getSql("SELECT usUnits FROM %s LIMIT 1;" % self.table_name)
        self.std_unit_system = _row[0] if _row is not None else None
        
        # Cache the first and last timestamps
        self.first_timestamp = self.firstGoodStamp()
        self.last_timestamp  = self.lastGoodStamp()

    def lastGoodStamp(self):
        """Retrieves the epoch time of the last good archive record.
        
        returns: Time of the last good archive record as an epoch time, or
        None if there are no records."""
        _row = self.getSql("SELECT MAX(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None
    
    def firstGoodStamp(self):
        """Retrieves earliest timestamp in the archive.
        
        returns: Time of the first good archive record as an epoch time, or
        None if there are no records."""
        _row = self.getSql("SELECT MIN(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None

    def addRecord(self, record_obj, log_level=syslog.LOG_NOTICE):
        """Commit a single record or a collection of records to the archive.
        
        record_obj: Either a data record, or an iterable that can return data
        records. Each data record must look like a dictionary, where the keys
        are the SQL types and the values are the values to be stored in the
        database.
        
        log_level: What syslog level to use for any logging. Default is syslog.LOG_NOTICE.
        """
        
        # Determine if record_obj is just a single dictionary instance
        # (in which case it will have method 'keys'). If so, wrap it in
        # something iterable (a list):
        record_list = [record_obj] if hasattr(record_obj, 'keys') else record_obj
        
        min_ts = None
        max_ts = 0
        with weedb.Transaction(self.connection) as cursor:

            for record in record_list:
                try:
                    self._addSingleRecord(record, cursor, log_level)
                    min_ts = min(min_ts, record['dateTime']) if min_ts is not None else record['dateTime']
                    max_ts = max(max_ts, record['dateTime'])
                except (weedb.IntegrityError, weedb.OperationalError), e:
                    syslog.syslog(syslog.LOG_ERR, "manager: unable to add record %s to database '%s': %s" %
                                  (weeutil.weeutil.timestamp_to_string(record['dateTime']), 
                                   self.database_name,
                                   e))

        # Update the cached timestamps. This has to sit outside the
        # transaction context, in case an exception occurs.
        self.first_timestamp = min(min_ts, self.first_timestamp)
        self.last_timestamp  = max(max_ts, self.last_timestamp)
        
    def _addSingleRecord(self, record, cursor, log_level):
        """Internal function for adding a single record to the database."""
        
        if record['dateTime'] is None:
            syslog.syslog(syslog.LOG_ERR, "manager: archive record with null time encountered")
            raise weewx.ViolatedPrecondition("Manager record with null time encountered.")

        # Check to make sure the incoming record is in the same unit
        # system as the records already in the database:
        self._check_unit_system(record['usUnits'])

        # Only data types that appear in the database schema can be
        # inserted. To find them, form the intersection between the
        # set of all record keys and the set of all sql keys
        record_key_set = set(record.keys())
        insert_key_set = record_key_set.intersection(self.sqlkeys)
        # Convert to an ordered list:
        key_list = list(insert_key_set)
        # Get the values in the same order:
        value_list = [record[k] for k in key_list]
        
        # This will a string of sql types, separated by commas. Because
        # some of the weewx sql keys (notably 'interval') are reserved
        # words in MySQL, put them in backquotes.
        k_str = ','.join(["`%s`" % k for k in key_list])
        # This will be a string with the correct number of placeholder
        # question marks:
        q_str = ','.join('?' * len(key_list))
        # Form the SQL insert statement:
        sql_insert_stmt = "INSERT INTO %s (%s) VALUES (%s)" % (self.table_name, k_str, q_str) 
        cursor.execute(sql_insert_stmt, value_list)
        syslog.syslog(log_level, "manager: added record %s to database '%s'" % 
                      (weeutil.weeutil.timestamp_to_string(record['dateTime']),
                       self.database_name))

    def genBatchRows(self, startstamp=None, stopstamp=None):
        """Generator function that yields raw rows from the archive database
        with timestamps within an interval.
        
        startstamp: Exclusive start of the interval in epoch time. If 'None',
        then start at earliest archive record.
        
        stopstamp: Inclusive end of the interval in epoch time. If 'None', then
        end at last archive record.
        
        yields: A list with the data records"""

        _cursor = self.connection.cursor()
        try:
            if startstamp is None:
                if stopstamp is None:
                    _gen = _cursor.execute("SELECT * FROM %s ORDER BY dateTime ASC" % self.table_name)
                else:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE dateTime <= ? ORDER BY dateTime ASC" % self.table_name, (stopstamp,))
            else:
                if stopstamp is None:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE dateTime > ? ORDER BY dateTime ASC" % self.table_name, (startstamp,))
                else:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE dateTime > ? AND dateTime <= ? ORDER BY dateTime ASC" % self.table_name,
                                            (startstamp, stopstamp))
               
            _last_time = 0
            for _row in _gen:
                # The following is to get around a bug in sqlite when all the
                # tables are in one file:
                if _row[0] <= _last_time:
                    continue
                _last_time = _row[0]
                yield _row
        finally:
            _cursor.close()

    def genBatchRecords(self, startstamp=None, stopstamp=None):
        """Generator function that yields records with timestamps within an
        interval.
        
        startstamp: Exclusive start of the interval in epoch time. If 'None',
        then start at earliest archive record.
        
        stopstamp: Inclusive end of the interval in epoch time. If 'None', then
        end at last archive record.
        
        yields: A dictionary where key is the observation type (eg, 'outTemp')
        and the value is the observation value"""
        
        for _row in self.genBatchRows(startstamp, stopstamp):
            yield dict(zip(self.sqlkeys, _row)) if _row else None
        
    def getRecord(self, timestamp, max_delta=None):
        """Get a single archive record with a given epoch time stamp.
        
        timestamp: The epoch time of the desired record.
        
        max_delta: The largest difference in time that is acceptable. 
        [Optional. The default is no difference]
        
        returns: a record dictionary or None if the record does not exist."""

        _cursor = self.connection.cursor()
        try:
            if max_delta:
                time_start_ts = timestamp - max_delta
                time_stop_ts  = timestamp + max_delta
                _cursor.execute("SELECT * FROM %s WHERE dateTime>=? AND dateTime<=? "\
                                "ORDER BY ABS(dateTime-?) ASC LIMIT 1" % self.table_name,
                                (time_start_ts, time_stop_ts, timestamp))
            else:
                _cursor.execute("SELECT * FROM %s WHERE dateTime=?" % self.table_name, (timestamp,))
            _row = _cursor.fetchone()
            return dict(zip(self.sqlkeys, _row)) if _row else None
        finally:
            _cursor.close()

    def updateValue(self, timestamp, obs_type, new_value):
        """Update (replace) a single value in the database."""
        
        self.connection.execute("UPDATE %s SET %s=? WHERE dateTime=?" % 
                                (self.table_name, obs_type), (new_value, timestamp))

    def getSql(self, sql, sqlargs=()):
        """Executes an arbitrary SQL statement on the database.
        
        sql: The SQL statement
        
        sqlargs: A tuple containing the arguments for the SQL statement
        
        returns: a tuple containing the results
        """
        _cursor = self.connection.cursor()
        try:
            _cursor.execute(sql, sqlargs)
            return _cursor.fetchone()
        finally:
            _cursor.close()

    def genSql(self, sql, sqlargs=()):
        """Generator function that executes an arbitrary SQL statement on
        the database."""
        
        _cursor = self.connection.cursor()
        try:
            for _row in _cursor.execute(sql, sqlargs):
                yield _row
        finally:
            _cursor.close()
            
    sql_dict = {'mintime' : "SELECT dateTime FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "\
                              "%(obs_type)s = (SELECT MIN(%(obs_type)s) FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND %(obs_type)s IS NOT NULL",
                'maxtime' : "SELECT dateTime FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "\
                              "%(obs_type)s = (SELECT MAX(%(obs_type)s) FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND %(obs_type)s IS NOT NULL",
                'last'    : "SELECT %(obs_type)s FROM %(table_name)s "\
                              "WHERE dateTime = (SELECT MAX(dateTime) FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL)",
                'lasttime': "SELECT MAX(dateTime) FROM %(table_name)s "\
                              "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL"}
                            
    simple_sql = "SELECT %(aggregate_type)s(%(obs_type)s) FROM %(table_name)s "\
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND %(obs_type)s IS NOT NULL"
                   
    def getAggregate(self, timespan, obs_type,
                     aggregate_type, **option_dict):  # @UnusedVariable
        """Returns an aggregation of a statistical type for a given time period.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
        
        aggregate_type: The type of aggregation to be done. 
        
        option_dict: Not used in this version.
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F').
        The third element is the unit group (eg, "group_temperature") """
        
        if aggregate_type not in ['sum', 'count', 'avg', 'max', 'min', 
                                  'mintime', 'maxtime', 'last', 'lasttime']:
            raise weewx.ViolatedPrecondition("Invalid aggregation type '%s'" % aggregate_type)
        
        interpolate_dict = {'aggregate_type' : aggregate_type,
                            'obs_type'       : obs_type,
                            'table_name'     : self.table_name,
                            'start'          : timespan.start,
                            'stop'           : timespan.stop}
        
        select_stmt = Manager.sql_dict.get(aggregate_type, Manager.simple_sql)
        _row = self.getSql(select_stmt % interpolate_dict)

        _result = _row[0] if _row else None
        
        # Look up the unit type and group of this combination of observation type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, obs_type, aggregate_type)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
    
    def getSqlVectors(self, timespan, obs_type, 
                      aggregate_type=None,
                      aggregate_interval=None): 
        """Get time and (possibly aggregated) data vectors within a time
        interval.
        
        This function is very similar to _getSqlVectors, except that for
        special types 'windvec' and 'windgustvec', it returns wind data
        broken down into its x- and y-components.
        
        timespan: The timespan over which the aggregation is to be done.
        
        obs_type: The observation type to be retrieved (e.g., 'outTemp', or 'windvec').
        If this type is the special types 'windvec', or 'windgustvec', then
        what will be returned is a vector of complex numbers. 
        
        aggregate_type: None if no aggregation is desired, otherwise the type
        of aggregation (e.g., 'sum', 'avg', etc.)  Default: None (no aggregation)
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Required if aggregate_type is non-None. 
        Default: None (no aggregation)
        
        returns: a 3-way tuple of value tuples:
          (start_vec, stop_vec, data_vec)
        The first element holds a ValueTuple with the start times of the aggregation interval.
        The second element holds a ValueTuple with the stop times of the aggregation interval.
        The third element holds a ValueTuple with the data aggregation over the interval.

        If sql_type is 'windvec' or 'windgustvec', the data vector will
        be a vector of types complex. The real part is the x-component of the
        wind, the imaginary part the y-component. 

        See the file weewx.units for the definition of a ValueTuple.
        """

        windvec_types = {'windvec'     : ('windSpeed, windDir'),
                         'windgustvec' : ('windGust,  windGustDir')}
        
        # Check to see if the requested type is not 'windvec' or 'windgustvec'
        if obs_type not in windvec_types:
            # The type is not one of the extended wind types. Use the regular
            # version:
            return self._getSqlVectors(timespan, obs_type, 
                                      aggregate_type, aggregate_interval)

        # It is an extended wind type. Prepare the lists that will hold the
        # final results.
        start_vec = list()
        stop_vec  = list()
        data_vec  = list()
        std_unit_system = None
        
        _cursor=self.connection.cursor()
        try:
    
            # Is aggregation requested?
            if aggregate_type:
                
                # Check to make sure we have everything:
                if not aggregate_interval:
                    raise weewx.ViolatedPrecondition("Aggregation interval missing")

                # Aggregation is requested.
                # The aggregation should happen over the x- and y-components.
                # Because they do not appear in the database (only the
                # magnitude and direction do) we cannot do the aggregation
                # in the SQL statement. We'll have to do it in Python.
                # Do we know how to do it?
                if aggregate_type not in ['sum', 'count', 'avg', 'max', 'min']:
                    raise weewx.ViolatedPrecondition("Invalid aggregation type" % aggregate_type)
                
                # This SQL select string will select the proper wind types
                sql_str = 'SELECT dateTime, %s, usUnits FROM %s WHERE dateTime > ? AND dateTime <= ?' % \
                    (windvec_types[obs_type], self.table_name)

                # Go through each aggregation interval, calculating the aggregation.
                for stamp in weeutil.weeutil.intervalgen(timespan[0], timespan[1], aggregate_interval):
    
                    _mag_extreme = _dir_at_extreme = None
                    _xsum = _ysum = 0.0
                    _count = 0
                    _last_time = None
    
                    for _rec in _cursor.execute(sql_str, stamp):
                        (_mag, _dir) = _rec[1:3]
    
                        if _mag is None:
                            continue
    
                        # A good direction is necessary unless the mag is zero:
                        if _mag == 0.0  or _dir is not None:
                            _count += 1
                            _last_time  = _rec[0]
                            if std_unit_system:
                                if std_unit_system != _rec[3]:
                                    raise weewx.UnsupportedFeature("Unit type cannot change "\
                                                                   "within a time interval.")
                            else:
                                std_unit_system = _rec[3]
                            
                            # Pick the kind of aggregation:
                            if aggregate_type == 'min':
                                if _mag_extreme is None or _mag < _mag_extreme:
                                    _mag_extreme = _mag
                                    _dir_at_extreme = _dir
                            elif aggregate_type == 'max':
                                if _mag_extreme is None or _mag > _mag_extreme:
                                    _mag_extreme = _mag
                                    _dir_at_extreme = _dir
                            else:
                                # No need to do the arithmetic if mag is zero.
                                # We also need a good direction
                                if _mag > 0.0 and _dir is not None:
                                    _xsum += _mag * math.cos(math.radians(90.0 - _dir))
                                    _ysum += _mag * math.sin(math.radians(90.0 - _dir))
                    # We've gone through the whole interval. Were there any
                    # good data?
                    if _count:
                        # Record the time of the last good data point:
                        start_vec.append(stamp.start)
                        stop_vec.append(stamp.stop)
                        # Form the requested aggregation:
                        if aggregate_type in ('min', 'max'):
                            if _dir_at_extreme is None:
                                # The only way direction can be zero with a
                                # non-zero count is if all wind velocities
                                # were zero
                                if weewx.debug:
                                    assert(_mag_extreme <= 1.0e-6)
                                x_extreme = y_extreme = 0.0
                            else:
                                x_extreme = _mag_extreme * math.cos(math.radians(90.0 - _dir_at_extreme))
                                y_extreme = _mag_extreme * math.sin(math.radians(90.0 - _dir_at_extreme))
                            data_vec.append(complex(x_extreme, y_extreme))
                        elif aggregate_type == 'sum':
                            data_vec.append(complex(_xsum, _ysum))
                        elif aggregate_type == 'count':
                            data_vec.append(_count)
                        else:
                            # Must be 'avg'
                            data_vec.append(complex(_xsum/_count, _ysum/_count))
            else:
                # No aggregation desired. It's a lot simpler. Go get the
                # data in the requested time period
                # This SQL select string will select the proper wind types
                sql_str = 'SELECT dateTime, %s, usUnits, `interval` FROM %s WHERE dateTime >= ? AND dateTime <= ?' % \
                        (windvec_types[obs_type], self.table_name)
                
                for _rec in _cursor.execute(sql_str, timespan):
                    start_vec.append(_rec[0] - _rec[4])
                    stop_vec.append(_rec[0])
                    if std_unit_system:
                        if std_unit_system != _rec[3]:
                            raise weewx.UnsupportedFeature("Unit type cannot change "\
                                                           "within a time interval.")
                    else:
                        std_unit_system = _rec[3]
                    # Break the mag and dir down into x- and y-components.
                    (_mag, _dir) = _rec[1:3]
                    if _mag is None or _dir is None:
                        data_vec.append(None)
                    else:
                        x = _mag * math.cos(math.radians(90.0 - _dir))
                        y = _mag * math.sin(math.radians(90.0 - _dir))
                        if weewx.debug:
                            # There seem to be some little rounding errors that
                            # are driving my debugging crazy. Zero them out
                            if abs(x) < 1.0e-6 : x = 0.0
                            if abs(y) < 1.0e-6 : y = 0.0
                        data_vec.append(complex(x,y))
        finally:
            _cursor.close()

        (time_type, time_group) = weewx.units.getStandardUnitType(std_unit_system, 'dateTime')
        (data_type, data_group) = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)
        return (weewx.units.ValueTuple(start_vec, time_type, time_group),
                weewx.units.ValueTuple(stop_vec, time_type, time_group),
                weewx.units.ValueTuple(data_vec, data_type, data_group))

    def _check_unit_system(self, unit_system):
        """ Check to make sure a unit system is the same as what's already in use in the database."""

        if self.std_unit_system is not None:
            if unit_system != self.std_unit_system:
                raise weewx.UnitError("Unit system of incoming record (0x%02x) "\
                                      "differs from '%s' table in '%s' database (0x%02x)" % 
                                      (unit_system, self.table_name, self.database_name,
                                       self.std_unit_system))
        else:
            # This is the first record. Remember the unit system to
            # check against subsequent records:
            self.std_unit_system = unit_system

    def _getSqlVectors(self, timespan, sql_type, 
                      aggregate_type=None,
                      aggregate_interval=None): 
        """Get time and (possibly aggregated) data vectors within a time
        interval. 
        
        timespan: The timespan over which the aggregation is to be done.
        
        sql_type: The observation type to be retrieved. The type should be one
        of the columns in the archive database.
        
        aggregate_type: None if no aggregation is desired, otherwise the type
        of aggregation (e.g., 'sum', 'avg', etc.)  Default: None (no aggregation)
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Required if aggregate_type is non-None. 
        Default: None (no aggregation)

        returns: a 3-way tuple of value tuples:
          (start_vec, stop_vec, data_vec)
        The first element holds a ValueTuple with the start times of the aggregation interval.
        The second element holds a ValueTuple with the stop times of the aggregation interval.
        The third element holds a ValueTuple with the data aggregation over the interval.

        If aggregation is desired (aggregate_interval is not None), then each
        element represents a time interval exclusive on the left, inclusive on
        the right. The time elements will all fall on the same local time
        boundary as startstamp. 

        For example, if the starting time in the timespan is 8-Mar-2009 18:00
        and aggregate_interval is 10800 (3 hours), then the returned time vector
        will be (shown in local times):
        
        8-Mar-2009 21:00
        9-Mar-2009 00:00
        9-Mar-2009 03:00
        9-Mar-2009 06:00 etc.
        
        Note that DST happens at 02:00 on 9-Mar, so the actual time deltas
        between the elements is 3 hours between times #1 and #2, but only 2
        hours between #2 and #3.
        
        NB: there is an algorithmic assumption here that the archive time
        interval is a constant.
        
        There is another assumption that the unit type does not change within
        a time interval.

        See the file weewx.units for the definition of a ValueTuple.
        """

        startstamp, stopstamp = timespan
        start_vec = list()
        stop_vec  = list()
        data_vec  = list()
        std_unit_system = None

        _cursor=self.connection.cursor()
        try:
    
            if aggregate_type :
                
                # Check to make sure we have everything:
                if not aggregate_interval:
                    raise weewx.ViolatedPrecondition("Aggregation interval missing")

                if aggregate_type.lower() == 'last':
                    sql_str = "SELECT %s, MIN(usUnits), MAX(usUnits) FROM %s WHERE dateTime = "\
                        "(SELECT MAX(dateTime) FROM %s WHERE "\
                        "dateTime > ? AND dateTime <= ? AND %s IS NOT NULL)" % (sql_type, self.table_name, 
                                                                                self.table_name, sql_type)
                else:
                    sql_str = "SELECT %s(%s), MIN(usUnits), MAX(usUnits) FROM %s "\
                        "WHERE dateTime > ? AND dateTime <= ?" % (aggregate_type, sql_type, self.table_name)

                for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
                    _cursor.execute(sql_str, stamp)
                    _rec = _cursor.fetchone()
                    # Don't accumulate any results where there wasn't a record
                    # (signified by a null result)
                    if _rec and _rec[0] is not None:
                        if std_unit_system:
                            if not (std_unit_system == _rec[1] == _rec[2]):
                                raise weewx.UnsupportedFeature("Unit type cannot change "\
                                                               "within a time interval (%s vs %s vs %s)." %
                                                               (std_unit_system, _rec[1], _rec[2]))
                        else:
                            std_unit_system = _rec[1]
                        start_vec.append(stamp.start)
                        stop_vec.append(stamp.stop)
                        data_vec.append(_rec[0])
            else:
                # No aggregation
                sql_str = "SELECT dateTime, %s, usUnits, `interval` FROM %s "\
                            "WHERE dateTime >= ? AND dateTime <= ?" % (sql_type, self.table_name)
                for _rec in _cursor.execute(sql_str, (startstamp, stopstamp)):
                    start_vec.append(_rec[0] - _rec[3])
                    stop_vec.append(_rec[0])
                    if std_unit_system:
                        if std_unit_system != _rec[2]:
                            raise weewx.UnsupportedFeature("Unit type cannot change "\
                                                           "within a time interval.")
                    else:
                        std_unit_system = _rec[2]
                    data_vec.append(_rec[1])
        finally:
            _cursor.close()

        (time_type, time_group) = weewx.units.getStandardUnitType(std_unit_system, 'dateTime')
        (data_type, data_group) = weewx.units.getStandardUnitType(std_unit_system, sql_type, aggregate_type)
        return (ValueTuple(start_vec, time_type, time_group),
                ValueTuple(stop_vec, time_type, time_group), 
                ValueTuple(data_vec, data_type, data_group))


def reconfig(old_db_dict, new_db_dict, new_unit_system=None, new_schema=None):
    """Copy over an old archive to a new one, using a provided schema."""
    
    with Manager.open(old_db_dict) as old_archive:
        if new_schema is None:
            import schemas.wview
            new_schema = schemas.wview.schema
        with Manager.open_with_create(new_db_dict, schema=new_schema) as new_archive:

            # Wrap the input generator in a unit converter.
            record_generator = weewx.units.GenWithConvert(old_archive.genBatchRecords(), new_unit_system)
        
            # This is very fast because it is done in a single transaction
            # context:
            new_archive.addRecord(record_generator)

#===============================================================================
#                    Class DBBinder
#===============================================================================

class DBBinder(object):
    """Given a binding name, it returns the matching database as a managed object. Caches
    results."""

    def __init__(self, config_dict):
        """ Initialize a DBBinder object.

        config_dict: The configuration dictionary. """

        self.config_dict = config_dict           
        self.default_binding_dict = {}
        self.manager_cache = {}
    
    def close(self):
        for data_binding in self.manager_cache.keys():
            try:
                self.manager_cache[data_binding].close()
                del self.manager_cache[data_binding]
            except Exception:
                pass
            
    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.close()
    
    def set_binding_defaults(self, binding_name, default_binding_dict):
        """Set the defaults for the binding binding_name."""
        self.default_binding_dict[binding_name] = default_binding_dict
        
    def get_manager(self, data_binding='wx_binding', initialize=False):
        """Given a binding name, returns the managed object"""
        global default_binding_dict

        if data_binding not in self.manager_cache:
            # If this binding has a set of defaults, use them. Otherwise, use the generic
            # defaults
            defaults = self.default_binding_dict.get(data_binding, default_binding_dict)
            manager_dict = get_manager_dict_from_config(self.config_dict,
                                                        data_binding, 
                                                        default_binding_dict=defaults)
            self.manager_cache[data_binding] = open_manager(manager_dict, initialize)

        return self.manager_cache[data_binding]
    
    # For backwards compatibility with early V3.1 alphas:
    get_database = get_manager
    
    def bind_default(self, default_binding='wx_binding'):
        """Returns a function that holds a default database binding."""
        
        def db_lookup(data_binding=None):
            if data_binding is None:
                data_binding = default_binding
            return self.get_manager(data_binding)

        return db_lookup

#===============================================================================
#                                 Utilities
#===============================================================================

# If the [DataBindings] section is missing or incomplete, this is the set
# of defaults that will be used.
default_binding_dict = {'database'   : 'archive_sqlite',
                        'table_name' : 'archive',
                        'manager'    : 'weewx.wxmanager.WXDaySummaryManager',
                        'schema'     : 'schemas.wview.schema'}

def get_database_dict_from_config(config_dict, database):
    """Return a database dictionary holding the information necessary
    to open a database. Searches top-level stanzas for any missing
    information about a database.
    
    config_dict: The configuration dictionary.
                               
    database: The database whose database dict is to be
    retrieved (example: 'archive_sqlite')

    Returns: a database dictionary, with everything needed to pass on to
    a Manager or weedb in order to open a database.
    
    Example. Given a configuration file snippet that looks like:
    
    >>> import configobj, StringIO
    >>> config_snippet = '''
    ... WEEWX_ROOT = /home/weewx
    ... [DatabaseTypes]
    ...   [[SQLite]]
    ...     driver = weedb.sqlite
    ...     SQLITE_ROOT = %(WEEWX_ROOT)s/archive
    ... [Databases]
    ...     [[archive_sqlite]]
    ...        database_name = weewx.sdb
    ...        database_type = SQLite'''
    >>> config_dict = configobj.ConfigObj(StringIO.StringIO(config_snippet))
    >>> database_dict = get_database_dict_from_config(config_dict, 'archive_sqlite')
    >>> keys = sorted(database_dict.keys())
    >>> for k in keys:
    ...     print "%15s: %12s" % (k, database_dict[k])
        SQLITE_ROOT: /home/weewx/archive
      database_name:    weewx.sdb
             driver: weedb.sqlite
    """
    try:
        database_dict = dict(config_dict['Databases'][database])
    except KeyError, e:
        raise weewx.UnknownDatabase("Unknown database '%s'" % e)
    
    # See if a 'database_type' is specified. This is something
    # like 'SQLite' or 'MySQL'. If it is, use it to augment any
    # missing information in the database_dict:
    if 'database_type' in database_dict:
        database_type = database_dict.pop('database_type')
    
        # Augment any missing information in the database dictionary with
        # the top-level stanza
        if database_type in config_dict['DatabaseTypes']:
            weeutil.weeutil.conditional_merge(database_dict, config_dict['DatabaseTypes'][database_type])
        else:
            raise weewx.UnknownDatabaseType('database_type')
    
    return database_dict

#
# A "manager dict" is everything needed to open up a manager. It is basically
# the same as a binding dictionary, except that the database has been replaced
# with a database dictionary.
#
# As such, it includes keys:
#
#  manager: The manager class
#  table_name: The name of the internal table
#  schema: The schema to be used in case of initialization
#  database_dict: The database dictionary. This will be passed
#      on to weedb.
#
def get_manager_dict_from_config(config_dict, data_binding,
                                 default_binding_dict=default_binding_dict):
    
    # Start with a copy of the bindings in the config dictionary (we
    # will be adding to it):
    try:
        manager_dict = dict(config_dict['DataBindings'][data_binding])
    except KeyError, e:
        raise weewx.UnknownBinding("Unknown data binding '%s'" % e)

    # If anything is missing, substitute from the default dictionary:
    weeutil.weeutil.conditional_merge(manager_dict, default_binding_dict)
    
    # Now get the database dictionary if it's missing:
    if 'database_dict' not in manager_dict:
        try:
            database = manager_dict.pop('database')
            manager_dict['database_dict'] = get_database_dict_from_config(config_dict,
                                                                          database)
        except KeyError, e:
            raise weewx.UnknownDatabase("Unknown database '%s'" % e)
        
    # The schema may be specified as a string, in which case we resolve the
    # python object to which it refers. Or it may be specified as a dict with
    # field_name=sql_type pairs.
    schema_name = manager_dict.get('schema')
    if schema_name is None:
        manager_dict['schema'] = None
    elif isinstance(schema_name, dict):
        # Schema is a ConfigObj section (that is, a dictionary). Retrieve the
        # elements of the schema in order:
        manager_dict['schema'] = [(col_name, manager_dict['schema'][col_name]) for col_name in manager_dict['schema']]
    else:
        # Schema is a string, with the name of the schema object
        manager_dict['schema'] = weeutil.weeutil._get_object(schema_name)
    
    return manager_dict

# The following is for backwards compatibility:        
def get_manager_dict(bindings_dict, databases_dict, data_binding,
                     default_binding_dict=default_binding_dict):
    if bindings_dict.parent != databases_dict.parent:
        raise weewx.UnsupportedFeature("Database and binding dictionaries"
                                       " require common parent")
    return get_manager_dict_from_config(bindings_dict.parent, data_binding, 
                                        default_binding_dict)
    
def open_manager(manager_dict, initialize=False):
    
    manager_cls = weeutil.weeutil._get_object(manager_dict['manager'])
    if initialize:
        return manager_cls.open_with_create(manager_dict['database_dict'],
                                            manager_dict['table_name'],
                                            manager_dict['schema'])
    else:
        return manager_cls.open(manager_dict['database_dict'],
                                manager_dict['table_name'])
    
def open_manager_with_config(config_dict, data_binding,
                             initialize=False, default_binding_dict=default_binding_dict):
    """Given a binding name, returns an open manager object."""
    manager_dict = get_manager_dict_from_config(config_dict, 
                                                data_binding=data_binding,
                                                default_binding_dict=default_binding_dict)
    return open_manager(manager_dict, initialize)

def drop_database(manager_dict):
    """Drop (delete) a database, given a manager dict"""
    
    weedb.drop(manager_dict['database_dict'])

def drop_database_with_config(config_dict, data_binding,
                              default_binding_dict=default_binding_dict):
    """Drop (delete) the database associated with a binding name"""

    manager_dict = get_manager_dict_from_config(config_dict,
                                    data_binding=data_binding, 
                                    default_binding_dict=default_binding_dict)
    drop_database(manager_dict)    


#===============================================================================
#                        Class DaySummaryManager
#
#     Adds daily summaries to the database.
# 
#     This class specializes method _addSingleRecord so that it adds
#     the data to a daily summary, as well as the regular archive table.
#     
#     Note that a date does not include midnight --- that belongs
#     to the previous day. That is because a data record archives
#     the *previous* interval. So, for the date 5-Oct-2008 with
#     a five minute archive interval, the statistics would include
#     the following records (local time):
#       5-Oct-2008 00:05:00
#       5-Oct-2008 00:10:00
#       5-Oct-2008 00:15:00
#       .
#       .
#       .
#       5-Oct-2008 23:55:00
#       6-Oct-2008 00:00:00
#
#===============================================================================

def show_progress(nrec, last_time):
    """Utility function to show our progress while backfilling"""
    print >>sys.stdout, "Records processed: %d; Last date: %s\r" % \
        (nrec, weeutil.weeutil.timestamp_to_string(last_time)),
    sys.stdout.flush()
        
class DaySummaryManager(Manager):
    """Manage a daily statistical summary. 
    
    The daily summary consists of a separate table for each type. The columns 
    of each table are things like min, max, the timestamps for min and max, 
    sum and sumtime. The values sum and sumtime are kept to make it easy to
    calculate averages for different time periods.
    
    For example, for type 'outTemp' (outside temperature), there is 
    a table of name 'archive_day_outTemp' with the following column names:
    
        dateTime, min, mintime, max, maxtime, sum, count, wsum, sumtime
    
    wsum is the "Weighted sum," that is, the sum weighted by the archive interval.
    sumtime is the sum of the archive intervals.
        
    In addition to all the tables for each type, there is one additional table called
    'archive_day__metadata', which currently holds the time of the last update. """
    
    version = "1.0"

    # The SQL statements used in the daily summary parts of the database
    
    sql_create_str = "CREATE TABLE %s_day_%s (dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, "\
      "min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, "\
      "wsum REAL, sumtime INTEGER);"
                                 
    meta_create_str   = """CREATE TABLE %s_day__metadata (name CHAR(20) NOT NULL UNIQUE PRIMARY KEY, value TEXT);"""
    meta_replace_str  = """REPLACE INTO %s_day__metadata VALUES(?, ?)"""  
    
    select_update_str = """SELECT value FROM %s_day__metadata WHERE name = 'lastUpdate';"""
    
    # Set of SQL statements to be used for calculating aggregate statistics. Key is the aggregation type.
    sqlDict = {'min'        : "SELECT MIN(min) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'minmax'     : "SELECT MIN(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max'        : "SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'maxmin'     : "SELECT MAX(min) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'meanmin'    : "SELECT AVG(min) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'meanmax'    : "SELECT AVG(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'maxsum'     : "SELECT MAX(sum) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'mintime'    : "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "min = (SELECT MIN(min) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'maxmintime' : "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "min = (SELECT MAX(min) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'maxtime'    : "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "max = (SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'minmaxtime' : "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "max = (SELECT MIN(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'maxsumtime' : "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "sum = (SELECT MAX(sum) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
               'gustdir'    : "SELECT max_dir FROM %(table_name)s_day_%(obs_key)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s AND " \
                              "max = (SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s)",
               'sum'        : "SELECT SUM(sum) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'count'      : "SELECT SUM(count) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'avg'        : "SELECT SUM(wsum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'rms'        : "SELECT SUM(wsquaresum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'vecavg'     : "SELECT SUM(xsum),SUM(ysum),SUM(dirsumtime)  FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'vecdir'     : "SELECT SUM(xsum),SUM(ysum) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max_ge'     : "SELECT SUM(max >= %(val)s) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'max_le'     : "SELECT SUM(max <= %(val)s) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'min_ge'     : "SELECT SUM(min >= %(val)s) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'min_le'     : "SELECT SUM(min <= %(val)s) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
               'sum_ge'     : "SELECT SUM(sum >= %(val)s) FROM %(table_name)s_day_%(obs_key)s WHERE dateTime >= %(start)s AND dateTime < %(stop)s"}
    
    def __init__(self, connection, table_name='archive', schema=None):
        """Initialize an instance of DaySummaryManager
        
        connection: A weedb connection to the database to be managed.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'.
        
        schema: The schema to be used. Optional. If not supplied, then an
        exception of type weedb.OperationalError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """
        # Initialize my superclass:
        super(DaySummaryManager, self).__init__(connection, table_name, schema)
        
        # If the database has not been initialized with the daily summaries, then create the
        # necessary tables, but only if a schema has been given.
        if '%s_day__metadata' % self.table_name not in self.connection.tables():
            # Database has not been initialized with the summaries. Is there a schema?
            if schema is None:
                # Uninitialized, but no schema was supplied. Raise an exception
                raise weedb.OperationalError("No day summary schema for table '%s' in database '%s'" % (self.table_name, connection.database_name))
            # There is a schema. Create all the daily summary tables as one transaction:
            with weedb.Transaction(self.connection) as _cursor:
                self._initialize_day_tables(schema, _cursor)
            syslog.syslog(syslog.LOG_NOTICE, "manager: Created daily summary tables")
        
        # Get a list of all the observation types which have daily summaries
        all_tables = self.connection.tables()
        prefix = "%s_day_" % self.table_name
        Nprefix = len(prefix)
        meta_name = '%s_day__metadata' % self.table_name
        self.daykeys = [x[Nprefix:] for x in all_tables if (x.startswith(prefix) and x != meta_name)]
        row = self.connection.execute("""SELECT value FROM %s_day__metadata WHERE name = 'Version';""" % self.table_name)
        self.version = row[0] if row is not None else "1.0"

    def _initialize_day_tables(self, archiveSchema, cursor):  # @UnusedVariable
        """Initialize the tables needed for the daily summary."""
        # Create the tables needed for the daily summaries.
        for _obs_type in self.obskeys:
            cursor.execute(DaySummaryManager.sql_create_str % (self.table_name, _obs_type))
        # Create the meta table:
        cursor.execute(DaySummaryManager.meta_create_str % self.table_name)
        # Put the version number in it:
        cursor.execute(DaySummaryManager.meta_replace_str % self.table_name, ("Version", DaySummaryManager.version))

    def _addSingleRecord(self, record, cursor, log_level):
        """Specialized version that updates the daily summaries, as well as the 
        main archive table."""
        
        # First let my superclass handle adding the record to the main archive table:
        super(DaySummaryManager, self)._addSingleRecord(record, cursor, log_level=log_level)

        # Get the start of day for the record:        
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])

        # Now add to the daily summary for the appropriate day:
        _day_summary = self._get_day_summary(_sod_ts, cursor)
        _day_summary.addRecord(record)
        self._set_day_summary(_day_summary, record['dateTime'], cursor)
        syslog.syslog(log_level, "manager: added record %s to daily summary in '%s'" % 
                      (weeutil.weeutil.timestamp_to_string(record['dateTime']), 
                       self.database_name))
        
    def updateHiLo(self, accumulator):
        """Use the contents of an accumulator to update the daily hi/lows."""
        
        # Get the start-of-day for the timespan in the accumulator
        _sod_ts = weeutil.weeutil.startOfArchiveDay(accumulator.timespan.stop)

        with weedb.Transaction(self.connection) as _cursor:
            # Retrieve the daily summaries seen so far:
            _stats_dict = self._get_day_summary(_sod_ts, _cursor)
            # Update them with the contents of the accumulator:
            _stats_dict.updateHiLo(accumulator)
            # Then save the results:
            self._set_day_summary(_stats_dict, accumulator.timespan.stop, _cursor)
        
    def getAggregate(self, timespan, obs_type, aggregate_type, **option_dict):
        """Returns an aggregation of a statistical type for a given time period.
        It will use the daily summaries if possible, otherwise the archive table.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
        
        aggregate_type: The type of aggregation to be done.
        
        option_dict: Some aggregations require optional values
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F').
        The third element is the unit group (eg, "group_temperature") """
        
        # We can use the day summary optimizations if the starting and ending times of
        # the aggregation interval sit on midnight boundaries, or are the first or last
        # records in the database.
        if aggregate_type in ['last', 'lasttime'] or not (weeutil.weeutil.isMidnight(timespan.start) or \
                                                          timespan.start == self.first_timestamp) \
                                                  or not (weeutil.weeutil.isMidnight(timespan.stop)  or \
                                                          timespan.stop  == self.last_timestamp):
            
            # Cannot use the day summaries. We'll have to calculate the aggregate
            # using the regular archive table:
            return Manager.getAggregate(self, timespan, obs_type, aggregate_type, 
                                          **option_dict)

        # We can use the daily summaries. Proceed.
                
        # This entry point won't work for heating or cooling degree days:
        if weewx.debug:
            assert(obs_type not in ['heatdeg', 'cooldeg'])
            assert(timespan is not None)

        # Check to see if this is a valid daily summary type:
        if obs_type not in self.daykeys:
            raise AttributeError, "Unknown daily summary type %s" % (obs_type,)

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

        # convert to lower-case:
        aggregate_type = aggregate_type.lower()

        # Form the interpolation dictionary        
        interDict = {'start'         : weeutil.weeutil.startOfDay(timespan.start),
                     'stop'          : timespan.stop,
                     'obs_key'       : obs_type,
                     'aggregate_type': aggregate_type,
                     'val'           : target_val,
                     'table_name'    : self.table_name}
            
        # Run the query against the database:
        _row = self.getSql(DaySummaryManager.sqlDict[aggregate_type] % interDict)

        #=======================================================================
        # Each aggregation type requires a slightly different calculation.
        #=======================================================================
        
        if not _row or None in _row: 
            # If no row was returned, or if it contains any nulls (meaning that not
            # all required data was available to calculate the requested aggregate),
            # then set the results to None.
            _result = None
        
        # Do the required calculation for this aggregat type
        elif aggregate_type in ['min', 'maxmin', 'max', 'minmax', 'meanmin', 'meanmax', 
                               'maxsum', 'sum', 'gustdir']:
            # These aggregates are passed through 'as is'.
            _result = _row[0]
        
        elif aggregate_type in ['mintime', 'maxmintime', 'maxtime', 'minmaxtime', 'maxsumtime',
                               'count', 'max_ge', 'max_le', 'min_le', 'sum_ge']:
            # These aggregates are always integers:
            _result = int(_row[0])

        elif aggregate_type == 'avg':
            _result = _row[0]/_row[1] if _row[1] else None

        elif aggregate_type == 'rms':
            _result = math.sqrt(_row[0]/_row[1]) if _row[1] else None
        
        elif aggregate_type == 'vecavg':
            _result = math.sqrt((_row[0]**2 + _row[1]**2) / _row[2]**2) if _row[2] else None
        
        elif aggregate_type == 'vecdir':
            if _row == (0.0, 0.0):
                _result = None
            deg = 90.0 - math.degrees(math.atan2(_row[1], _row[0]))
            _result = deg if deg >= 0 else deg + 360.0
        else:
            # Unknown aggregation. Return None
            _result = None

        # Look up the unit type and group of this combination of stats type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, obs_type, aggregate_type)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
        
    def exists(self, obs_type):
        """Checks whether the observation type exists in the database."""

        # Check to see if this is a valid daily summary type:
        return obs_type in self.daykeys

    def has_data(self, obs_type, timespan):
        """Checks whether the observation type exists in the database and whether it has any data."""

        return self.exists(obs_type) and self.getAggregate(timespan, obs_type, 'count')[0] != 0

    def backfill_day_summary(self, start_ts=None, stop_ts=None, 
                             progress_fn=show_progress, trans_days=5):
        """Fill the statistical database from an archive database.
        
        Normally, the daily summaries get filled by LOOP packets (to get maximum time
        resolution), but if the database gets corrupted, or if a new user is
        starting up with imported wview data, it's necessary to recreate it from
        straight archive data. The Hi/Lows will all be there, but the times won't be
        any more accurate than the archive period.
        
        To help prevent database errors for large archives database transactions 
        are limited to trans_days days of archive data. This is a trade-off between 
        speed and memory usage.
        
        start_ts: Archive data with a timestamp greater than this will be
        used. [Optional. Default is to start with the first datum in the archive.]
        
        stop_ts: Archive data with a timestamp less than or equal to this will be
        used. [Optional. Default is to end with the last datum in the archive.]
        
        progress_fn: This function will be called after processing every 1000 records.
        
        trans_day: Number of days of archive data to be used for each daily summaries database transaction. [Optional. Default is 5.] 
        
        returns: A 2-way tuple (nrecs, ndays) where 
          nrecs is the number of records backfilled;
          ndays is the number of days
        """
        
        syslog.syslog(syslog.LOG_INFO, "manager: Starting backfill of daily summaries")
        t1 = time.time()
        
        nrecs = 0
        ndays = 0
        
        _day_accum = None
        _lastTime  = None
        
        # If a start time for the backfill wasn't given, then start with the time of
        # the last statistics recorded:
        tranche_start_ts = start_ts if start_ts else self._getLastUpdate()
        # Calculate the stop time for our first tranche of data
        if tranche_start_ts:
            # have a start ts so we stop trans_days after the start of archive 
            # day containing our start ts
            tranche_stop_ts = weeutil.weeutil.startOfArchiveDay(tranche_start_ts) + \
                trans_days * 86400
        else:
            # don't have a start ts; could be because there are no archive 
            # records or there are no daily summaries
            if self.firstGoodStamp():
                # we have archive records but don't know how many so set a stop ts
                tranche_stop_ts = weeutil.weeutil.startOfArchiveDay(self.firstGoodStamp()) + \
                    trans_days * 86400
            else:
                # we have no archive records so set our stop ts to None and let 
                # weewx take its course
                tranche_stop_ts = None
        # If we have a stop time then make sure our tranche does not go past it
        if stop_ts:
            tranche_stop_ts = min(stop_ts, tranche_stop_ts)
        while True:
            with weedb.Transaction(self.connection) as _cursor:
                # Go through all the archive records in the tranche, adding 
                # them to the accumulator and then the daily summary tables
                start = tranche_start_ts + 1 if tranche_start_ts else None
                for _rec in self.genBatchRecords(start, tranche_stop_ts):
                    # Get the start-of-day for the record:
                    _sod_ts = weeutil.weeutil.startOfArchiveDay(_rec['dateTime'])
                    # If this is the very first record, fetch a new accumulator
                    if not _day_accum:
                        _day_accum = self._get_day_summary(_sod_ts)
                    # Try updating. If the time is out of the accumulator's time 
                    # span, an exception will get raised.
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
                    if progress_fn and nrecs%1000 == 0:
                        progress_fn(nrecs, _lastTime)
        
                # Tranche complete; but are we done?
                if tranche_stop_ts:
                    if tranche_stop_ts >= max(stop_ts, self.lastGoodStamp()):
                        # We had a stop time and we have reached it so we are done
                        # First record the daily summary for the last day then break
                        if _day_accum:
                            self._set_day_summary(_day_accum, _lastTime, _cursor)
                            ndays += 1
                        break
                else:
                    # we had no stop time so we are done, break out of the loop
                    break
            # Still have more tranches to do so get the start and stop times of 
            # our next tranche
            tranche_start_ts = tranche_stop_ts
            tranche_stop_ts = weeutil.weeutil.startOfArchiveDay(tranche_start_ts + 1) + \
                trans_days * 86400
            # If we have a stop time then make sure the next tranche does not go
            # past it
            if stop_ts:
                tranche_stop_ts = min(stop_ts, tranche_stop_ts)
        tdiff = time.time() - t1
        if nrecs:
            syslog.syslog(syslog.LOG_INFO, 
                          "manager: Processed %d records to backfill %d day summaries in %.2f seconds" % (nrecs, ndays, tdiff))
        else:
            syslog.syslog(syslog.LOG_INFO,
                          "manager: Daily summaries up to date")
        
        return (nrecs, ndays)


    #--------------------------- UTILITY FUNCTIONS -----------------------------------

    def _get_day_summary(self, sod_ts, cursor=None):
        """Return an instance of an appropriate accumulator, initialized to a given day's statistics.

        sod_ts: The timestamp of the start-of-day of the desired day."""
                
        # Get the TimeSpan for the day starting with sod_ts:
        _timespan = weeutil.weeutil.archiveDaySpan(sod_ts,0)

        # Get an empty day accumulator:
        _day_accum = weewx.accum.Accum(_timespan)
        
        _cursor = cursor or self.connection.cursor()

        try:
            # For each observation type, execute the SQL query and hand the results on
            # to the accumulator.
            for _day_key in self.daykeys:
                _cursor.execute("SELECT * FROM %s_day_%s WHERE dateTime = ?" % (self.table_name, _day_key), (_day_accum.timespan.start,))
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

        # For each daily summary type...
        for _summary_type in day_accum:
            # Don't try an update for types not in the database:
            if _summary_type not in self.daykeys:
                continue
            # ... get the stats tuple to be written to the database...
            _write_tuple = (_sod,) + day_accum[_summary_type].getStatsTuple()
            # ... and an appropriate SQL command with the correct number of question marks ...
            _qmarks = ','.join(len(_write_tuple)*'?')
            _sql_replace_str = "REPLACE INTO %s_day_%s VALUES(%s)" % (self.table_name, _summary_type, _qmarks)
            # ... and write to the database. In case the type doesn't appear in the database,
            # be prepared to catch an exception:
            try:
                cursor.execute(_sql_replace_str, _write_tuple)
            except weedb.OperationalError, e:
                syslog.syslog(syslog.LOG_ERR, "manager: Operational error database %s; %s" % (self.database_name, e))
                
        # Update the time of the last daily summary update:
        cursor.execute(DaySummaryManager.meta_replace_str % self.table_name, ('lastUpdate', str(int(lastUpdate))))
            
    def _getLastUpdate(self, cursor=None):
        """Returns the time of the last update to the statistical database."""

        if cursor:
            cursor.execute(DaySummaryManager.select_update_str % self.table_name)
            _row = cursor.fetchone()
        else:
            _row = self.getSql(DaySummaryManager.select_update_str % self.table_name)
        return int(_row[0]) if _row else None
    
    def drop_daily(self):
        """Drop the daily summaries."""
        
        syslog.syslog(syslog.LOG_INFO, 
                      "manager: Dropping daily summary tables from '%s' ..." % self.connection.database_name)
        try:
            _all_tables = self.connection.tables()
            with weedb.Transaction(self.connection) as _cursor:
                for _table_name in _all_tables:
                    if _table_name.startswith('%s_day_' % self.table_name):
                        _cursor.execute("DROP TABLE %s" % _table_name)

            del self.daykeys
        except weedb.OperationalError, e:
            syslog.syslog(syslog.LOG_ERR, 
                          "manager: Operational error database '%s'; %s" % (self.connection.database_name, e))
        else:
            syslog.syslog(syslog.LOG_INFO,
                          "manager: Dropped daily summary tables from database '%s'" % (self.connection.database_name,))

if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
