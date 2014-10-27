#
#    Copyright (c) 2009-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Classes and functions for interfacing with a weewx archive."""
from __future__ import with_statement
import math
import os.path
import syslog

from weewx.units import ValueTuple
import weewx.units
import weeutil.weeutil
import weedb
import user.schemas

#==============================================================================
#                         class DBManager
#==============================================================================

class DBManager(object):
    """Manages a weewx archive file. Offers a number of convenient member
    functions for managing the archive file. These functions encapsulate
    whatever sql statements are needed.
    
    ATTRIBUTES
    
    sqlkeys: A list of the SQL keys that the database supports.
    
    obskeys: A list of the observation types that the database supports.
    
    std_unit_system: The unit system used by the database."""
    
    def __init__(self, archive_db_dict, table_name='archive', schema=None):
        """Initialize an object of type weewx.DBManager.
        
        archive_db_dict: A database dictionary holding the information necessary
        to open the database.
        
        table_name: The name of the table to be used in the database. Default
        is 'archive'.
        
        schema: The schema to be used. Optional. If not supplied, then an
        exception of type weedb.OperationalError will be raised if the database
        does not exist, and of type weedb.UnitializedDatabase if it exists, but
        has not been initialized.
        """

        self.table_name = table_name
        
        try:
            self.connection = weedb.connect(archive_db_dict)
        except weedb.OperationalError:
            # Database does not exist. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                raise
            # Create the database:
            weedb.create(archive_db_dict)
            # Now I can get a connection
            self.connection = weedb.connect(archive_db_dict)

        # Now get the SQL types. 
        try:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        except weedb.OperationalError:
            # Database exists, but is uninitialized. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                raise
            # Database exists, but has not been initialized. Initialize it.
            self._initialize_archive(schema)
            # Try again:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        
        # Fetch the first row in the database to determine the unit system in
        # use. If the database has never been used, then the unit system is
        # still indeterminate --- set it to 'None'.
        _row = self.getSql("SELECT usUnits FROM %s LIMIT 1;" % self.table_name)
        self.std_unit_system = _row[0] if _row is not None else None

    def _initialize_archive(self, archiveSchema):
        """Initialize the tables needed for the archive.
        
        archiveSchema: The schema to be used
        """
    
        # List comprehension of the types, joined together with commas. Put
        # the SQL type in backquotes, because at least one of them ('interval')
        # is a MySQL reserved word
        _sqltypestr = ', '.join(["`%s` %s" % _type for _type in archiveSchema])

        try:
            with weedb.Transaction(self.connection) as _cursor:
                _cursor.execute("CREATE TABLE %s (%s);" % (self.table_name, _sqltypestr, ))
        except Exception, e:
            self.close()
            syslog.syslog(syslog.LOG_ERR, "archive: Unable to create table '%s' in database '%s': %s" % 
                          (self.table_name, self.database, e))
            raise
    
        syslog.syslog(syslog.LOG_NOTICE, "archive: Created and initialized table '%s' in database '%s'" % 
                      (self.table_name, self.database))

    @classmethod
    def open(cls, archive_db_dict):
        """Open an DBManager database.
        
        OBSOLETE. For backwards compatibility.
        Returns:
        An instance of DBManager."""
        
        return cls(archive_db_dict)
    
    @classmethod
    def open_with_create(cls, archive_db_dict, archiveSchema):
        """Open an DBManager database, initializing it if necessary.
        
        OBSOLETE. For backwards compatibility
        
        Returns: 
        An instance of DBManager""" 
    
        return cls(archive_db_dict, archiveSchema)
    
    @property
    def database(self):
        return self.connection.database
    
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
        database."""
        
        # Determine if record_obj is just a single dictionary instance
        # (in which case it will have method 'keys'). If so, wrap it in
        # something iterable (a list):
        record_list = [record_obj] if hasattr(record_obj, 'keys') else record_obj

        with weedb.Transaction(self.connection) as cursor:

            for record in record_list:
                self._addSingleRecord(record, cursor, log_level)

    def _addSingleRecord(self, record, cursor, log_level):
        
        if record['dateTime'] is None:
            syslog.syslog(syslog.LOG_ERR, "archive: archive record with null time encountered")
            raise weewx.ViolatedPrecondition("DBManager record with null time encountered.")

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
            syslog.syslog(log_level, "archive: added record %s to database '%s'" % 
                          (weeutil.weeutil.timestamp_to_string(record['dateTime']),
                           os.path.basename(self.connection.database)))
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "archive: unable to add record %s to database '%s': %s" %
                          (weeutil.weeutil.timestamp_to_string(record['dateTime']), 
                           os.path.basename(self.connection.database),
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
                if aggregate_type not in ('sum', 'count', 'avg', 'max', 'min'):
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


def reconfig(old_db_dict, new_db_dict, new_unit_system=None,
             new_schema=user.schemas.defaultArchiveSchema):
    """Copy over an old archive to a new one, using a provided schema."""
    
    with DBManager.open(old_db_dict) as old_archive:
        with DBManager.open_with_create(new_db_dict, new_schema) as new_archive:

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
          'Bindings' :     
            'wx_bindings' : {'bind_to': 'archive_sqlite',
                             'manager': 'weewx.wxstats.WXDaySummaryArchive'},

          'Databases' :
            {'archive_sqlite' : {'root': '/home/weewx',
                                 'database': 'archive/archive.sdb',
                                 'driver': 'weedb.sqlite'}
           }"""
           
        self.config_dict = config_dict
        self.archive_cache = {}
    
    def close(self):
        for binding in self.archive_cache.keys():
            try:
                self.archive_cache[binding].close()
                del self.archive_cache[binding]
            except Exception:
                pass
            
    def __enter__(self):
        return self
    
    def __exit__(self, etyp, einst, etb):
        self.close()
    
    def get_binding(self, binding='wx_binding'):
        """Given a binding name, returns the managed object"""
        if binding not in self.archive_cache:
            self.archive_cache[binding] = open_database(self.config_dict, binding)
        return self.archive_cache[binding]

#===============================================================================
#                                 Utilities
#===============================================================================

def get_database_config(config_dict, binding):
    """Return the database dictionary associated with a binding name."""
    # Get the database name
    database_name = config_dict['Bindings'][binding]['bind_to']
    # Get the dictionary
    database_dict = config_dict['Databases'][database_name]
    # Get the manager to be used
    database_manager = config_dict['Bindings'][binding].get('manager', 'weewx.wxstats.WXDaySummaryArchive')
    table_name = config_dict['Bindings'][binding].get('table_name', 'archive')

    return (database_manager, database_dict, table_name)

def open_database(config_dict, binding, initialize=False):
    # Get the database dictionary & manager:
    database_manager, database_dict, table_name = get_database_config(config_dict, binding)
    # Get the class object of the manager to be used:
    database_cls = weeutil.weeutil._get_object(database_manager)
    
    if initialize:
        schema_name = config_dict['Bindings'][binding].get('schema', 'user.schemas.defaultArchiveSchema')
        schema = weeutil.weeutil._get_object(schema_name)
    else:
        schema = None

    # Instantiate the class of the database manager:
    return database_cls(database_dict, table_name=table_name, schema=schema)
