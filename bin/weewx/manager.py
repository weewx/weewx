#
#    Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Classes and functions for interfacing with a weewx archive."""
from __future__ import with_statement
import math
import syslog
import sys

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
    
    USEFUL ATTRIBUTES
    
    database_name: The name of the database the manager is bound to.
    
    table_name: The name of the main, archive table.
    
    sqlkeys: A list of the SQL keys that the database table supports.
    
    obskeys: A list of the observation types that the database table supports.
    
    std_unit_system: The unit system used by the database table."""
    
    def __init__(self, connection, table_name='archive', schema=None):
        """Initialize an object of type Manager.
        
        connection: A weedb connection to the database to be managed.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'.
        
        schema: The schema to be used. Optional. If not supplied, then an
        exception of type weedb.OperationalError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """

        self.connection = connection
        self.table_name = table_name

        # Now get the SQL types. 
        try:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        except weedb.OperationalError:
            # Database exists, but is uninitialized. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                raise
            # Database exists, but has not been initialized. Initialize it.
            self._initialize_database(schema)
            # Try again:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        
        # Fetch the first row in the database to determine the unit system in
        # use. If the database has never been used, then the unit system is
        # still indeterminate --- set it to 'None'.
        _row = self.getSql("SELECT usUnits FROM %s LIMIT 1;" % self.table_name)
        self.std_unit_system = _row[0] if _row is not None else None

    @classmethod
    def open(cls, archive_db_dict, table_name='archive'):
        """Open and return a Manager or a subclass of Manager.  
        
        archive_db_dict: A database dictionary holding the information necessary
        to open the database.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'. """

        # This will raise a weedb.OperationalError if the database does
        # not exist. The 'open' method we are implementing never attempts an
        # initialization, so let it go by.
        connection = weedb.connect(archive_db_dict)

        # Create an instance of the right class and return it:
        dbmanager = cls(connection, table_name)
        return dbmanager
    
    @classmethod
    def open_with_create(cls, archive_db_dict, table_name='archive', schema=None):
        """Open and return a Manager or a subclass of Manager, initializing
        if necessary.  
        
        archive_db_dict: A database dictionary holding the information necessary
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
            connection = weedb.connect(archive_db_dict)
        except weedb.OperationalError:
            # Database does not exist. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                raise
            # Yes. Create the database:
            weedb.create(archive_db_dict)
            # Now I can get a connection
            connection = weedb.connect(archive_db_dict)

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

    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):
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

        with weedb.Transaction(self.connection) as cursor:

            for record in record_list:
                self._addSingleRecord(record, cursor, log_level)

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
        try:
            cursor.execute(sql_insert_stmt, value_list)
            syslog.syslog(log_level, "manager: added record %s to database '%s'" % 
                          (weeutil.weeutil.timestamp_to_string(record['dateTime']),
                           self.database_name))
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "manager: unable to add record %s to database '%s': %s" %
                          (weeutil.weeutil.timestamp_to_string(record['dateTime']), 
                           self.database_name,
                           e))

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
            
    gen_agg_sql = "SELECT %(aggregate_type)s(%(obs_type)s) FROM %(table_name)s "\
                        "WHERE dateTime > ? AND dateTime <= ?"
    lasttime_agg_sql = "SELECT MAX(dateTime) FROM %(table_name)s "\
                        "WHERE dateTime > ? AND dateTime <= ?  AND %(obs_type)s IS NOT NULL"
    last_agg_sql = "SELECT %(obs_type)s FROM %(table_name)s "\
                        "WHERE dateTime = (" + lasttime_agg_sql + ")"

    def getAggregate(self, timespan, obs_type, aggregate_type, **option_dict):
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
        
        if aggregate_type not in ['sum', 'count', 'avg', 'max', 'min', 'last', 'lasttime']:
            raise weewx.ViolatedPrecondition, "Aggregation type missing or unknown"
        
        interpolate_dict = {'aggregate_type' : aggregate_type,
                            'obs_type'       : obs_type,
                            'table_name'     : self.table_name}
        
        if aggregate_type == 'last':
            select_stmt = Manager.last_agg_sql
        elif aggregate_type == 'lasttime':
            select_stmt = Manager.lasttime_agg_sql
        else:
            select_stmt = Manager.gen_agg_sql
            
        _row = self.getSql(select_stmt % interpolate_dict, timespan)

        _result = _row[0] if _row else None
        
        # Look up the unit type and group of this combination of observation type and aggregation:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, obs_type, aggregate_type)
        # Form the value tuple and return it:
        return weewx.units.ValueTuple(_result, t, g)
    
    
    def getSqlVectors(self, ext_type, startstamp, stopstamp, 
                              aggregate_interval = None, 
                              aggregate_type = None):
        """Get time and (possibly aggregated) data vectors within a time
        interval.
        
        This function is very similar to getSqlVectors, except that for
        special types 'windvec' and 'windgustvec', it returns wind data
        broken down into its x- and y-components.
        
        sql_type: The SQL type to be retrieved (e.g., 'outTemp', or 'windvec').
        If this type is the special types 'windvec', or 'windgustvec', then
        what will be returned is a vector of complex numbers. 
        
        startstamp: If aggregation_interval is None, then data with timestamps
        greater than or equal to this value will be returned. If
        aggregation_interval is not None, then the start of the first interval
        will be greater than (exclusive of) this value. 
        
        stopstamp: Records with time stamp less than or equal to this will be
        retrieved. If interval is not None, then the last interval will
        include this value.
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Required if aggregate_type is non-None. 
        Default: None (no aggregation)
        
        aggregate_type: None if no aggregation is desired, otherwise the type
        of aggregation (e.g., 'sum', 'avg', etc.)  Default: None (no aggregation)
        
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
        if ext_type not in windvec_types:
            # The type is not one of the extended wind types. Use the regular
            # version:
            return self._getSqlVectors(ext_type, startstamp, stopstamp, 
                                      aggregate_interval, aggregate_type)

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
                    raise weewx.ViolatedPrecondition, "Aggregation type missing or unknown"
                
                # This SQL select string will select the proper wind types
                sql_str = 'SELECT dateTime, %s, usUnits FROM %s WHERE dateTime > ? AND dateTime <= ?' % \
                    (windvec_types[ext_type], self.table_name)

                # Go through each aggregation interval, calculating the aggregation.
                for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
    
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
                        (windvec_types[ext_type], self.table_name)
                
                for _rec in _cursor.execute(sql_str, (startstamp, stopstamp)):
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
        (data_type, data_group) = weewx.units.getStandardUnitType(std_unit_system, ext_type, aggregate_type)
        return (weewx.units.ValueTuple(start_vec, time_type, time_group),
                weewx.units.ValueTuple(stop_vec, time_type, time_group),
                weewx.units.ValueTuple(data_vec, data_type, data_group))

    def _check_unit_system(self, unit_system):
        """ Check to make sure a unit system is the same as what's already in use in the database."""

        if self.std_unit_system is not None:
            if unit_system != self.std_unit_system:
                raise ValueError("Unit system of incoming record (0x%x) "\
                                 "differs from the archive database (0x%x)" % 
                                 (unit_system, self.std_unit_system))
        else:
            # This is the first record. Remember the unit system to
            # check against subsequent records:
            self.std_unit_system = unit_system

    def _getSqlVectors(self, sql_type, startstamp, stopstamp,
                      aggregate_interval=None, 
                      aggregate_type=None):
        """Get time and (possibly aggregated) data vectors within a time
        interval. 
        
        The return value is a 2-way tuple. The first member is a vector of time
        values, the second member an instance of weewx.std_unit_system.Value
        with a value of a vector of data values, and a unit_type given by
        sql_type. 
        
        An example of a returned value: 
            (time_vec, Value(outTempVec, 'outTemp'))
        
        If aggregation is desired (aggregate_interval is not None), then each
        element represents a time interval exclusive on the left, inclusive on
        the right. The time elements will all fall on the same local time
        boundary as startstamp. 

        For example, if startstamp is 8-Mar-2009 18:00 and aggregate_interval
        is 10800 (3 hours), then the returned time vector will be
        (shown in local times):
        
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
        
        sql_type: The SQL type to be retrieved (e.g., 'outTemp') 
        
        startstamp: If aggregation_interval is None, then data with timestamps
        greater than or equal to this value will be returned. If
        aggregation_interval is not None, then the start of the first interval
        will be greater than (exclusive of) this value. 
        
        stopstamp: Records with time stamp less than or equal to this will be
        retrieved. If interval is not None, then the last interval will
        include this value.
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Required if aggregate_type is non-None.
        Default: None (no aggregation)
        
        aggregate_type: None if no aggregation is desired, otherwise the
        type of aggregation (e.g., 'sum', 'avg', etc.)  

        returns: a 3-way tuple of value tuples:
          (start_vec, stop_vec, data_vec)
        The first element holds a ValueTuple with the start times of the aggregation interval.
        The second element holds a ValueTuple with the stop times of the aggregation interval.
        The third element holds a ValueTuple with the data aggregation over the interval.

        See the file weewx.units for the definition of a ValueTuple.
        """

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
        
        config_dict: Typically, this is the weewx configuration dictionary.
        It should contain two keys, Bindings and Databases, each with
        a dictionary as a value, holding the bindings and databases, respectively.

        It should look something like:
          {
          'DataBindings' :     
            'wx_bindings' : {'database_name': 'archive_sqlite',
                             'manager': 'weewx.wxmanager.WXDaySummaryManager'},

          'Databases' :
            {'archive_sqlite' : {'root': '/home/weewx',
                                 'database_name': 'archive/archive.sdb',
                                 'driver': 'weedb.sqlite'}
           }"""
           
        self.config_dict = config_dict
        self.database_cache = {}
    
    def close(self):
        for data_binding in self.database_cache.keys():
            try:
                self.database_cache[data_binding].close()
                del self.database_cache[data_binding]
            except Exception:
                pass
            
    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):
        self.close()
    
    def get_database(self, data_binding='wx_binding', initialize=False):
        """Given a binding name, returns the managed object"""
        if data_binding not in self.database_cache:
            self.database_cache[data_binding] = open_database(self.config_dict,
                                                              data_binding,
                                                              initialize)
        return self.database_cache[data_binding]
    
    def bind_default(self, default_binding='wx_binding'):
        """Returns a function that holds a default database binding."""
        
        def db_lookup(data_binding=None):
            if data_binding is None:
                data_binding = default_binding
            return self.get_database(data_binding)

        return db_lookup

#===============================================================================
#                                 Utilities
#===============================================================================

def get_database_config(config_dict, data_binding,
                        default_manager='weewx.wxmanager.WXDaySummaryManager',
                        default_table='archive'):
    """Return the database dictionary associated with a binding name."""

    # Get the database name
    try:
        database = config_dict['DataBindings'][data_binding]['database']
    except KeyError, e:
        raise weewx.UnknownBinding(e)
    
    # Get the dictionary
    if database not in config_dict['Databases']:
        raise weewx.UnknownDatabase(database)
    database_dict = config_dict['Databases'][database]

    binding_dict = config_dict['DataBindings'][data_binding]
    # Get the manager if specified, otherwise use a sane default
    database_manager = binding_dict.get('manager', default_manager)
    # Get the table if specified, otherwise use a sane default
    table_name = binding_dict.get('table_name', default_table)

    return (database_manager, database_dict, table_name)

def get_schema(binding_dict, default_schema='schemas.wview.schema'):
    """Get a schema from a binding dict.  The schema may be specified as
    a string, in which case we resolve the python object to which it refers.
    Or it may be specified as a dict with field_name=sql_type pairs.  In
    the latter case, order matters, so we depend on configobj to maintain
    order.
    """
    schema_name = binding_dict.get('schema', default_schema)
    if schema_name is None:
        schema = None
    elif isinstance(schema_name, str):
        schema = weeutil.weeutil._get_object(schema_name)
    else:
        schema = []
        for k in binding_dict['schema']:
            schema.append((k, binding_dict['schema'][k]))
    return schema

def open_database(config_dict, data_binding, initialize=False):
    """Given a binding name, returns an open manager object."""
    # Get the database dictionary & manager:
    database_manager, database_dict, table_name = get_database_config(config_dict, data_binding)
    # Get the class object of the manager to be used:
    database_cls = weeutil.weeutil._get_object(database_manager)
    
    if initialize:
        schema = get_schema(config_dict['DataBindings'][data_binding])
        return database_cls.open_with_create(database_dict, table_name=table_name, schema=schema)
    else:
        return database_cls.open(database_dict, table_name=table_name)

def drop_database(config_dict, data_binding):
    """Drop (delete) the database associated with a binding name"""
    _, database_dict, _ = get_database_config(config_dict, data_binding)
    weedb.drop(database_dict)
    

#===============================================================================
#     Adds daily summaries to the database.
# 
#     This class specializes method _addSingleRecord so that it adds
#     the data to a daily summary, as well as the  =regular archive table.
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



#===============================================================================
#                        Class DaySummaryManager
#===============================================================================

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

    def _initialize_day_tables(self, archiveSchema, cursor):
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
        
    def getDayAggregate(self, timespan, obs_type, aggregate_type, **option_dict):
        """Returns an aggregation of a statistical type for a given time period.
        
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
        
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
        
        aggregate_type: The type of aggregation to be done. The keys in the dictionary
        sqlDict above are the possible aggregation types. 
        
        option_dict: Some aggregations require optional values
        
        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F').
        The third element is the unit group (eg, "group_temperature") """
        
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

        return self.exists(obs_type) and self.getDayAggregate(timespan, obs_type, 'count')[0] != 0

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
        
        returns: A 2-way tuple (nrecs, ndays) where 
          nrecs is the number of records backfilled;
          ndays is the number of days
        """
        
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
    
            # We're done. Record the daily summary for the last day.
            if _day_accum:
                self._set_day_summary(_day_accum, _lastTime, _cursor)
                ndays += 1
        
        return (nrecs, ndays)


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
                syslog.syslog(syslog.LOG_ERR, "manager: Operational error database %s; %s" % (self.manager, e))
                
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
        _all_tables = self.connection.tables()
        with weedb.Transaction(self.connection) as _cursor:
            for _table_name in _all_tables:
                if _table_name.startswith('%s_day_' % self.table_name):
                    _cursor.execute("DROP TABLE %s" % _table_name)

        del self.daykeys
