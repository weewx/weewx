#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with a weewx database archive."""

from __future__ import absolute_import
from __future__ import print_function

import datetime
import logging
import sys
import time

from six.moves import zip

import weedb
import weeutil.config
import weeutil.weeutil
import weewx.accum
import weewx.units
import weewx.xtypes
from weeutil.weeutil import timestamp_to_string, to_int

log = logging.getLogger(__name__)


class IntervalError(ValueError):
    """Raised when a bad value of 'interval' is encountered."""


# ==============================================================================
#                         class Manager
# ==============================================================================

class Manager(object):
    """Manages a database table. Offers a number of convenient member functions for querying and
    inserting data into the table. These functions encapsulate whatever sql statements are needed.

    A limitation of this implementation is that it caches the timestamps of the first and last
    record in the table. Normally, the caches get updated as data comes in. However, if one manager
    is updating the table, while another is doing aggregate queries, the latter manager will be
    unaware of later records in the database, and may choose the wrong query strategy. If this
    might be the case, call member function _sync() before starting the query.
    
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
        
        table_name: The name of the table to be used in the database. Default is 'archive'.
        
        schema: The schema to be used. Optional. If not supplied, then an exception of type
        weedb.ProgrammingError will be raised if the database does not exist, and of type
        weedb.UnitializedDatabase if it exists, but has not been initialized.
        """

        self.connection = connection
        self.table_name = table_name
        self.first_timestamp = None
        self.last_timestamp = None
        self.std_unit_system = None

        # Now get the SQL types. 
        try:
            self.sqlkeys = self.connection.columnsOf(self.table_name)
        except weedb.ProgrammingError:
            # Database exists, but is uninitialized. Did the caller supply
            # a schema?
            if schema is None:
                # No. Nothing to be done.
                log.error("Cannot get columns of table %s, and no schema specified",
                          self.table_name)
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
        
        database_dict: A database dictionary holding the information necessary to open the
        database.

          For example, for sqlite, it looks something like:
            {
               'SQLITE_ROOT' : '/home/weewx/archive',
               'database_name' : 'weewx.sdb',
               'driver' : 'weedb.sqlite'
            }

          For MySQL:
            {
              'host': 'localhost',
              'user': 'weewx',
              'password': 'weewx-password',
              'database_name' : 'weeewx',
              'driver' : 'weedb.mysql'
            }

        table_name: The name of the table to be used in the database. Default is 'archive'.
        """

        # This will raise a weedb.OperationalError if the database does not exist. The 'open'
        # method we are implementing never attempts an initialization, so let it go by.
        connection = weedb.connect(database_dict)

        # Create an instance of the right class and return it:
        dbmanager = cls(connection, table_name)
        return dbmanager

    @classmethod
    def open_with_create(cls, database_dict, table_name='archive', schema=None):
        """Open and return a Manager or a subclass of Manager, initializing if necessary.

        database_dict: A database dictionary holding the information necessary to open the
        database. See the classmethod above for details.

        table_name: The name of the table to be used in the database. Default is 'archive'.

        schema: The schema to be used. If not supplied, then an exception of type
        weedb.OperationalError will be raised if the database does not exist, and of type
        weedb.UnitializedDatabase if it exists, but has not been initialized.
        """

        # This will raise a weedb.OperationalError if the database does not exist.
        try:
            connection = weedb.connect(database_dict)
        except weedb.OperationalError:
            # Database does not exist. Did the caller supply a schema?
            if schema is None:
                # No. Nothing to be done.
                log.error("Cannot open database, and no schema specified")
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
        return [obs_type for obs_type in self.sqlkeys
                if obs_type not in ['dateTime', 'usUnits', 'interval']]

    def close(self):
        self.connection.close()
        self.sqlkeys = None
        self.first_timestamp = None
        self.last_timestamp = None
        self.std_unit_system = None

    def __enter__(self):
        return self

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.close()

    def _initialize_database(self, schema):
        """Initialize the tables needed for the archive.
        
        schema: The schema to be used
        """
        # If this is an old-style schema, this will raise an exception. Be prepared to catch it.
        try:
            table_schema = schema['table']
        except TypeError:
            # Old style schema:
            table_schema = schema

        # List comprehension of the types, joined together with commas. Put the SQL type in
        # backquotes, because at least one of them ('interval') is a MySQL reserved word
        sqltypestr = ', '.join(["`%s` %s" % _type for _type in table_schema])

        try:
            with weedb.Transaction(self.connection) as cursor:
                cursor.execute("CREATE TABLE %s (%s);" % (self.table_name, sqltypestr))
        except weedb.DatabaseError as e:
            log.error("Unable to create table '%s' in database '%s': %s",
                      self.table_name, self.database_name, e)
            raise

        log.info("Created and initialized table '%s' in database '%s'",
                 self.table_name, self.database_name)

    def _sync(self):
        """Resynch the internal caches."""

        # Fetch the first row in the database to determine the unit system in use. If the database
        # has never been used, then the unit system is still indeterminate --- set it to 'None'.
        _row = self.getSql("SELECT usUnits FROM %s LIMIT 1;" % self.table_name)
        self.std_unit_system = _row[0] if _row is not None else None

        # Cache the first and last timestamps
        self.first_timestamp = self.firstGoodStamp()
        self.last_timestamp = self.lastGoodStamp()

    def lastGoodStamp(self):
        """Retrieves the epoch time of the last good archive record.
        
        returns: Time of the last good archive record as an epoch time, or None if there are no
        records.
        """
        _row = self.getSql("SELECT MAX(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None

    def firstGoodStamp(self):
        """Retrieves earliest timestamp in the archive.
        
        returns: Time of the first good archive record as an epoch time, or None if there are no
        records.
        """
        _row = self.getSql("SELECT MIN(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None

    def addRecord(self, record_obj, accumulator=None):
        """Commit a single record or a collection of records to the archive.
        
        record_obj: Either a data record, or an iterable that can return data records. Each data
        record must look like a dictionary, where the keys are the SQL types and the values are the
        values to be stored in the database.
        """

        # Determine if record_obj is just a single dictionary instance (in which case it will have
        # method 'keys'). If so, wrap it in something iterable (a list):
        record_list = [record_obj] if hasattr(record_obj, 'keys') else record_obj

        min_ts = float('inf')  # A "big number"
        max_ts = 0
        with weedb.Transaction(self.connection) as cursor:

            for record in record_list:
                try:
                    # If the accumulator time matches the record we are working with,
                    # use it to update the highs and lows.
                    if accumulator and record_obj['dateTime'] == accumulator.timespan.stop:
                        self._updateHiLo(accumulator, cursor)

                    # Then add the record to the archives:
                    self._addSingleRecord(record, cursor)

                    min_ts = min(min_ts, record['dateTime'])
                    max_ts = max(max_ts, record['dateTime'])
                except (weedb.IntegrityError, weedb.OperationalError) as e:
                    log.error("Unable to add record %s to database '%s': %s",
                              weeutil.weeutil.timestamp_to_string(record['dateTime']),
                              self.database_name, e)

        # Update the cached timestamps. This has to sit outside the transaction context,
        # in case an exception occurs.
        if self.first_timestamp is not None:
            self.first_timestamp = min(min_ts, self.first_timestamp)
        if self.last_timestamp is not None:
            self.last_timestamp = max(max_ts, self.last_timestamp)

    def _addSingleRecord(self, record, cursor):
        """Internal function for adding a single record to the database."""

        if record['dateTime'] is None:
            log.error("Archive record with null time encountered")
            raise weewx.ViolatedPrecondition("Manager record with null time encountered.")

        # Check to make sure the incoming record is in the same unit system as the records already
        # in the database:
        self._check_unit_system(record['usUnits'])

        # Only data types that appear in the database schema can be inserted. To find them, form
        # the intersection between the set of all record keys and the set of all sql keys
        record_key_set = set(record.keys())
        insert_key_set = record_key_set.intersection(self.sqlkeys)
        # Convert to an ordered list:
        key_list = list(insert_key_set)
        # Get the values in the same order:
        value_list = [record[k] for k in key_list]

        # This will a string of sql types, separated by commas. Because some of the weewx sql keys
        # (notably 'interval') are reserved words in MySQL, put them in backquotes.
        k_str = ','.join(["`%s`" % k for k in key_list])
        # This will be a string with the correct number of placeholder
        # question marks:
        q_str = ','.join('?' * len(key_list))
        # Form the SQL insert statement:
        sql_insert_stmt = "INSERT INTO %s (%s) VALUES (%s)" % (self.table_name, k_str, q_str)
        cursor.execute(sql_insert_stmt, value_list)
        log.info("Added record %s to database '%s'",
                 weeutil.weeutil.timestamp_to_string(record['dateTime']),
                 self.database_name)

    def _updateHiLo(self, accumulator, cursor):
        pass

    def genBatchRows(self, startstamp=None, stopstamp=None):
        """Generator function that yields raw rows from the archive database with timestamps within
        an interval.

        startstamp: Exclusive start of the interval in epoch time. If 'None', then start at
        earliest archive record.

        stopstamp: Inclusive end of the interval in epoch time. If 'None', then end at last archive
        record.

        yields: A list with the data records. """

        with self.connection.cursor() as _cursor:

            if startstamp is None:
                if stopstamp is None:
                    _gen = _cursor.execute(
                        "SELECT * FROM %s ORDER BY dateTime ASC" % self.table_name)
                else:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE "
                                           "dateTime <= ? ORDER BY dateTime ASC" % self.table_name,
                                           (stopstamp,))
            else:
                if stopstamp is None:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE "
                                           "dateTime > ? ORDER BY dateTime ASC" % self.table_name,
                                           (startstamp,))
                else:
                    _gen = _cursor.execute("SELECT * FROM %s WHERE "
                                           "dateTime > ? AND dateTime <= ? ORDER BY dateTime ASC"
                                           % self.table_name, (startstamp, stopstamp))

            _last_time = 0
            for _row in _gen:
                # The following is to get around a bug in sqlite when all the
                # tables are in one file:
                if _row[0] <= _last_time:
                    continue
                _last_time = _row[0]
                yield _row

    def genBatchRecords(self, startstamp=None, stopstamp=None):
        """Generator function that yields records with timestamps within an interval.

        startstamp: Exclusive start of the interval in epoch time. If 'None', then start at
        earliest archive record.

        stopstamp: Inclusive end of the interval in epoch time. If 'None', then end at last archive
        record.

        yields: A dictionary where key is the observation type (eg, 'outTemp') and the value is the
        observation value. """

        for _row in self.genBatchRows(startstamp, stopstamp):
            yield dict(list(zip(self.sqlkeys, _row))) if _row else None

    def getRecord(self, timestamp, max_delta=None):
        """Get a single archive record with a given epoch time stamp.
        
        timestamp: The epoch time of the desired record.
        
        max_delta: The largest difference in time that is acceptable. 
        [Optional. The default is no difference]
        
        returns: a record dictionary or None if the record does not exist."""

        with self.connection.cursor() as _cursor:

            if max_delta:
                time_start_ts = timestamp - max_delta
                time_stop_ts = timestamp + max_delta
                _cursor.execute("SELECT * FROM %s WHERE dateTime>=? AND dateTime<=? "
                                "ORDER BY ABS(dateTime-?) ASC LIMIT 1" % self.table_name,
                                (time_start_ts, time_stop_ts, timestamp))
            else:
                _cursor.execute("SELECT * FROM %s WHERE dateTime=?"
                                % self.table_name, (timestamp,))
            _row = _cursor.fetchone()
            return dict(list(zip(self.sqlkeys, _row))) if _row else None

    def updateValue(self, timestamp, obs_type, new_value):
        """Update (replace) a single value in the database."""

        self.connection.execute("UPDATE %s SET %s=? WHERE dateTime=?" %
                                (self.table_name, obs_type), (new_value, timestamp))

    def getSql(self, sql, sqlargs=(), cursor=None):
        """Executes an arbitrary SQL statement on the database.
        
        sql: The SQL statement
        
        sqlargs: A tuple containing the arguments for the SQL statement
        
        returns: a tuple containing the results
        """
        _cursor = cursor or self.connection.cursor()
        try:
            _cursor.execute(sql, sqlargs)
            return _cursor.fetchone()
        finally:
            if cursor is None:
                _cursor.close()

    def genSql(self, sql, sqlargs=()):
        """Generator function that executes an arbitrary SQL statement on
        the database."""

        with self.connection.cursor() as _cursor:
            for _row in _cursor.execute(sql, sqlargs):
                yield _row

    def getAggregate(self, timespan, obs_type,
                     aggregate_type, **option_dict):
        """ OBSOLETE. Use weewx.xtypes.get_aggregate() instead. """

        return weewx.xtypes.get_aggregate(obs_type, timespan, aggregate_type, self, **option_dict)

    def getSqlVectors(self, timespan, obs_type,
                      aggregate_type=None,
                      aggregate_interval=None):
        """ OBSOLETE. Use weewx.xtypes.get_series() instead """

        return weewx.xtypes.get_series(obs_type, timespan, self,
                                       aggregate_type, aggregate_interval)

    def _check_unit_system(self, unit_system):
        """Check to make sure a unit system is the same as what's already in use in the database.
        """

        if self.std_unit_system is not None:
            if unit_system != self.std_unit_system:
                raise weewx.UnitError("Unit system of incoming record (0x%02x) "
                                      "differs from '%s' table in '%s' database (0x%02x)" %
                                      (unit_system, self.table_name, self.database_name,
                                       self.std_unit_system))
        else:
            # This is the first record. Remember the unit system to check against subsequent
            # records:
            self.std_unit_system = unit_system


def reconfig(old_db_dict, new_db_dict, new_unit_system=None, new_schema=None):
    """Copy over an old archive to a new one, using a provided schema."""

    with Manager.open(old_db_dict) as old_archive:
        if new_schema is None:
            import schemas.wview_extended
            new_schema = schemas.wview_extended.schema
        with Manager.open_with_create(new_db_dict, schema=new_schema) as new_archive:
            # Wrap the input generator in a unit converter.
            record_generator = weewx.units.GenWithConvert(old_archive.genBatchRecords(),
                                                          new_unit_system)

            # This is very fast because it is done in a single transaction context:
            new_archive.addRecord(record_generator)


# ===============================================================================
#                    Class DBBinder
# ===============================================================================

class DBBinder(object):
    """Given a binding name, it returns the matching database as a managed object. Caches
    results.
    """

    def __init__(self, config_dict):
        """ Initialize a DBBinder object.

        config_dict: The configuration dictionary. """

        self.config_dict = config_dict
        self.default_binding_dict = {}
        self.manager_cache = {}

    def close(self):
        for data_binding in list(self.manager_cache.keys()):
            self.manager_cache[data_binding].close()
            del self.manager_cache[data_binding]

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


# ===============================================================================
#                                 Utilities
# ===============================================================================

# If the [DataBindings] section is missing or incomplete, this is the set
# of defaults that will be used.
default_binding_dict = {'database': 'archive_sqlite',
                        'table_name': 'archive',
                        'manager': 'weewx.manager.DaySummaryManager',
                        'schema': 'schemas.wview_extended.schema'}


def get_database_dict_from_config(config_dict, database):
    """Return a database dictionary holding the information necessary to open a database. Searches
    top-level stanzas for any missing information about a database.

    config_dict: The configuration dictionary.

    database: The database whose database dict is to be retrieved (example: 'archive_sqlite')

    Returns: a database dictionary, with everything needed to pass on to a Manager or weedb in
    order to open a database.
    
    Example. Given a configuration file snippet that looks like:
    
    >>> import configobj
    >>> from six.moves import StringIO
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
    >>> config_dict = configobj.ConfigObj(StringIO(config_snippet))
    >>> database_dict = get_database_dict_from_config(config_dict, 'archive_sqlite')
    >>> keys = sorted(database_dict.keys())
    >>> for k in keys:
    ...     print("%15s: %12s" % (k, database_dict[k]))
        SQLITE_ROOT: /home/weewx/archive
      database_name:    weewx.sdb
             driver: weedb.sqlite
    """
    try:
        database_dict = dict(config_dict['Databases'][database])
    except KeyError as e:
        raise weewx.UnknownDatabase("Unknown database '%s'" % e)

    # See if a 'database_type' is specified. This is something
    # like 'SQLite' or 'MySQL'. If it is, use it to augment any
    # missing information in the database_dict:
    if 'database_type' in database_dict:
        database_type = database_dict.pop('database_type')

        # Augment any missing information in the database dictionary with
        # the top-level stanza
        if database_type in config_dict['DatabaseTypes']:
            weeutil.config.conditional_merge(database_dict,
                                             config_dict['DatabaseTypes'][database_type])
        else:
            raise weewx.UnknownDatabaseType('database_type')

    return database_dict


#
# A "manager dict" is everything needed to open up a manager. It is basically the same as a binding
# dictionary, except that the database has been replaced with a database dictionary.
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
    # Start with a copy of the bindings in the config dictionary (we will be adding to it):
    try:
        manager_dict = dict(config_dict['DataBindings'][data_binding])
    except KeyError as e:
        raise weewx.UnknownBinding("Unknown data binding '%s'" % e)

    # If anything is missing, substitute from the default dictionary:
    weeutil.config.conditional_merge(manager_dict, default_binding_dict)

    # Now get the database dictionary if it's missing:
    if 'database_dict' not in manager_dict:
        try:
            database = manager_dict.pop('database')
            manager_dict['database_dict'] = get_database_dict_from_config(config_dict,
                                                                          database)
        except KeyError as e:
            raise weewx.UnknownDatabase("Unknown database '%s'" % e)

    # The schema may be specified as a string, in which case we resolve the python object to which
    # it refers. Or it may be specified as a dict with field_name=sql_type pairs.
    schema_name = manager_dict.get('schema')
    if schema_name is None:
        manager_dict['schema'] = None
    elif isinstance(schema_name, dict):
        # Schema is a ConfigObj section (that is, a dictionary). Retrieve the
        # elements of the schema in order:
        manager_dict['schema'] = [(col_name, manager_dict['schema'][col_name]) for col_name in
                                  manager_dict['schema']]
    else:
        # Schema is a string, with the name of the schema object
        manager_dict['schema'] = weeutil.weeutil.get_object(schema_name)

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
    manager_cls = weeutil.weeutil.get_object(manager_dict['manager'])
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


def show_progress(nrec, last_time):
    """Utility function to show our progress while backfilling"""
    print("Records processed: %d; Last date: %s\r"
          % (nrec, weeutil.weeutil.timestamp_to_string(last_time)), end='', file=sys.stdout)
    sys.stdout.flush()


# ===============================================================================
#                        Class DaySummaryManager
#
#     Adds daily summaries to the database.
# 
#     This class specializes method _addSingleRecord so that it adds the data to a daily summary,
#     as well as the regular archive table.
#
#     Note that a date does not include midnight --- that belongs to the previous day. That is
#     because a data record archives the *previous* interval. So, for the date 5-Oct-2008 with a
#     five minute archive interval, the statistics would include the following records (local
#     time):
#       5-Oct-2008 00:05:00
#       5-Oct-2008 00:10:00
#       5-Oct-2008 00:15:00
#       .
#       .
#       .
#       5-Oct-2008 23:55:00
#       6-Oct-2008 00:00:00
#
# ===============================================================================

class DaySummaryManager(Manager):
    """Manage a daily statistical summary. 
    
    The daily summary consists of a separate table for each type. The columns of each table are
    things like min, max, the timestamps for min and max, sum and sumtime. The values sum and
    sumtime are kept to make it easy to calculate averages for different time periods.

    For example, for type 'outTemp' (outside temperature), there is a table of name
    'archive_day_outTemp' with the following column names:

        dateTime, min, mintime, max, maxtime, sum, count, wsum, sumtime

    wsum is the "Weighted sum," that is, the sum weighted by the archive interval. sumtime is the
    sum of the archive intervals.
        
    In addition to all the tables for each type, there is one additional table called
    'archive_day__metadata', which currently holds the version number and the time of the last
    update.
    """

    version = "2.0"

    # Schemas used by the daily summaries:
    day_schemas = {
        'scalar': [
            ('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
            ('min', 'REAL'),
            ('mintime', 'INTEGER'),
            ('max', 'REAL'),
            ('maxtime', 'INTEGER'),
            ('sum', 'REAL'),
            ('count', 'INTEGER'),
            ('wsum', 'REAL'),
            ('sumtime', 'INTEGER')
        ],
        'vector': [
            ('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
            ('min', 'REAL'),
            ('mintime', 'INTEGER'),
            ('max', 'REAL'),
            ('maxtime', 'INTEGER'),
            ('sum', 'REAL'),
            ('count', 'INTEGER'),
            ('wsum', 'REAL'),
            ('sumtime', 'INTEGER'),
            ('max_dir', 'REAL'),
            ('xsum', 'REAL'),
            ('ysum', 'REAL'),
            ('dirsumtime', 'INTEGER'),
            ('squaresum', 'REAL'),
            ('wsquaresum', 'REAL'),
        ]
    }

    # SQL statements used by the meta data in the daily summaries.
    meta_create_str = "CREATE TABLE %s_day__metadata (name CHAR(20) NOT NULL " \
                      "UNIQUE PRIMARY KEY, value TEXT);"
    meta_replace_str = "REPLACE INTO %s_day__metadata VALUES(?, ?)"
    meta_select_str = "SELECT value FROM %s_day__metadata WHERE name=?"

    def __init__(self, connection, table_name='archive', schema=None):
        """Initialize an instance of DaySummaryManager
        
        connection: A weedb connection to the database to be managed.
        
        table_name: The name of the table to be used in the database. Default is 'archive'.

        schema: The schema to be used. Optional. If not supplied, then an exception of type
        weedb.OperationalError will be raised if the database does not exist, and of type
        weedb.Uninitialized if it exists, but has not been initialized.
        """
        # Initialize my superclass:
        super(DaySummaryManager, self).__init__(connection, table_name, schema)

        # Has the database been initialized with the daily summaries?
        if '%s_day__metadata' % self.table_name not in self.connection.tables():
            # Database has not been initialized. Initialize it:
            self._initialize_day_tables(schema)

        # Get a list of all the observation types which have daily summaries
        all_tables = self.connection.tables()
        prefix = "%s_day_" % self.table_name
        n_prefix = len(prefix)
        meta_name = '%s_day__metadata' % self.table_name
        self.daykeys = [x[n_prefix:] for x in all_tables
                        if (x.startswith(prefix) and x != meta_name)]
        self.version = self._read_metadata('Version')
        log.debug('Daily summary version is %s', self.version)

    def close(self):
        self.version = None
        self.daykeys = None
        super(DaySummaryManager, self).close()

    def _initialize_day_tables(self, schema):
        """Initialize the tables needed for the daily summary."""

        if schema is None:
            # Uninitialized, but no schema was supplied. Raise an exception
            raise weedb.OperationalError("No day summary schema for table '%s' in database '%s'"
                                         % (self.table_name, self.connection.database_name))
        # See if we have new-style daily summaries, or old-style. Old-style will raise an
        # exception. Be prepared to catch it.
        try:
            day_summaries_schemas = schema['day_summaries']
        except TypeError:
            # Old-style schema. Include a daily summary for each observation type in the archive
            # table.
            day_summaries_schemas = [(e, 'scalar') for e in self.sqlkeys if
                                     e not in ('dateTime', 'usUnits', 'interval')]
            import weewx.wxmanager
            if type(self) == weewx.wxmanager.WXDaySummaryManager:
                # For backwards compatibility, include 'wind'
                day_summaries_schemas += [('wind', 'vector')]

        # Create the tables needed for the daily summaries in one transaction:
        with weedb.Transaction(self.connection) as cursor:
            for obs in day_summaries_schemas:
                obs_schema = (obs[0], obs[1].lower())
                # 'obs_schema' is a two-way tuple (obs_name, 'scalar'|'vector')
                # 'column_type' is a two-way tuple (column_name, 'REAL'|'INTEGER')
                s = ', '.join(
                    ["%s %s" % column_type
                     for column_type in DaySummaryManager.day_schemas[obs_schema[1]]])
                sql_create_str = "CREATE TABLE %s_day_%s (%s);" \
                                 % (self.table_name, obs_schema[0], s)
                cursor.execute(sql_create_str)
            # Create the meta table:
            cursor.execute(DaySummaryManager.meta_create_str % self.table_name)
            # Put the version number in it:
            self._write_metadata('Version', DaySummaryManager.version, cursor)
            log.info("Created daily summary tables")

    def _addSingleRecord(self, record, cursor):
        """Specialized version that updates the daily summaries, as well as the main archive
        table.
        """

        # First let my superclass handle adding the record to the main archive table:
        super(DaySummaryManager, self)._addSingleRecord(record, cursor)

        # Get the start of day for the record:        
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])

        # Get the weight. If the value for 'interval' is bad, an exception will be raised.
        try:
            _weight = self._calc_weight(record)
        except IntervalError as e:
            # Bad value for interval. Ignore this record
            log.error(e)
            log.error('*** record ignored')
            return

        # Now add to the daily summary for the appropriate day:
        _day_summary = self._get_day_summary(_sod_ts, cursor)
        _day_summary.addRecord(record, weight=_weight)
        self._set_day_summary(_day_summary, record['dateTime'], cursor)
        log.info("Added record %s to daily summary in '%s'",
                 weeutil.weeutil.timestamp_to_string(record['dateTime']),
                 self.database_name)

    def _updateHiLo(self, accumulator, cursor):
        """Use the contents of an accumulator to update the daily hi/lows."""

        # Get the start-of-day for the timespan in the accumulator
        _sod_ts = weeutil.weeutil.startOfArchiveDay(accumulator.timespan.stop)

        # Retrieve the daily summaries seen so far:
        _stats_dict = self._get_day_summary(_sod_ts, cursor)
        # Update them with the contents of the accumulator:
        _stats_dict.updateHiLo(accumulator)
        # Then save the results:
        self._set_day_summary(_stats_dict, accumulator.timespan.stop, cursor)

    def exists(self, obs_type):
        """Checks whether the observation type exists in the database."""

        # Check to see if this is a valid daily summary type:
        return obs_type in self.daykeys

    def has_data(self, obs_type, timespan):
        """Checks whether the observation type exists in the database and whether it has any
        data.
        """

        return self.exists(obs_type) and self.getAggregate(timespan, obs_type, 'count')[0] != 0

    def backfill_day_summary(self, start_d=None, stop_d=None,
                             progress_fn=show_progress, trans_days=5):

        """Fill the daily summaries from an archive database.
          
        Normally, the daily summaries get filled by LOOP packets (to get maximum time resolution),
        but if the database gets corrupted, or if a new user is starting up with imported wview
        data, it's necessary to recreate it from straight archive data. The Hi/Lows will all be
        there, but the times won't be any more accurate than the archive period.

        To help prevent database errors for large archives database transactions are limited to
        trans_days days of archive data. This is a trade-off between speed and memory usage.

        start_d: The first day to be included, specified as a datetime.date object [Optional.
        Default is to start with the first datum in the archive.]

        stop_d: The last day to be included, specified as a datetime.date object [Optional. Default
        is to include the date of the last archive record.]
          
        progress_fn: This function will be called after processing every 1000 records.
          
        trans_day: Number of days of archive data to be used for each daily summaries database
        transaction. [Optional. Default is 5.]
          
        returns: A 2-way tuple (nrecs, ndays) where 
          nrecs is the number of records backfilled;
          ndays is the number of days
        """
        # Table of actions.
        #
        # State                  start_ts    stop_ts     Action
        # -----                  --------    -------     ------
        # lastUpdate==None       any         any         No summary. Rebuild all
        # lastUpdate <lastRecord any         any         Aborted rebuild. lastUpdate should 
        #                                                be on day boundary. Restart from there.
        # lastUpdate==lastRecord None        None        No action.
        #          ""            X           None        Rebuild from X to end
        #          ""            None        Y           Rebuild from beginning through Y,
        #                                                inclusively
        #          ""            X           Y           Rebuild from X through Y, inclusively
        #
        # Definitions:
        #   lastUpdate: last update to the daily summary
        #   lastRecord: last update to the archive table
        #   X:          A start time that falls on a day boundary
        #   Y:          A stop  time that falls on a day boundary
        #

        log.info("Starting backfill of daily summaries")

        first_record = self.firstGoodStamp()
        if first_record is None:
            # Nothing in the archive database, so there's nothing to do.
            return 0, 0

        t1 = time.time()

        lastUpdate = to_int(self._read_metadata('lastUpdate'))
        lastRecord = self.last_timestamp

        if lastUpdate is None or lastUpdate < lastRecord:
            # We are either building the daily summary from scratch, or restarting from
            # an aborted build. Must finish the rebuild first.
            if start_d or stop_d:
                raise weewx.ViolatedPrecondition(
                    "Daily summaries not complete. Try again without from/to dates.")

            start_ts = lastUpdate or first_record
            start_d = datetime.date.fromtimestamp(start_ts)
            stop_d = datetime.date.fromtimestamp(lastRecord)

        elif lastUpdate == lastRecord:
            # This is the normal state of affairs. If a value for start_d or stop_d
            # has been passed in, a rebuild has been requested.
            if start_d is None and stop_d is None:
                # Nothing to do
                return 0, 0
            if start_d is None:
                start_d = datetime.date.fromtimestamp(first_record)
            if stop_d is None:
                stop_d = datetime.date.fromtimestamp(lastRecord)
        else:
            raise weewx.ViolatedPrecondition("lastUpdate(%s) > lastRecord(%s)" %
                                             (timestamp_to_string(lastUpdate),
                                              timestamp_to_string(lastRecord)))

        nrecs = 0
        ndays = 0

        while start_d <= stop_d:
            # Calculate the last date included in this transaction
            stop_transaction = min(stop_d, start_d + datetime.timedelta(days=(trans_days - 1)))
            day_accum = None

            with weedb.Transaction(self.connection) as cursor:
                # Go through all the archive records in the time span, adding them to the
                # daily summaries
                start_batch = time.mktime(start_d.timetuple())
                stop_batch = time.mktime(
                    (stop_transaction + datetime.timedelta(days=1)).timetuple())
                for rec in self.genBatchRecords(start_batch, stop_batch):
                    # If this is the very first record, fetch a new accumulator
                    if not day_accum:
                        # Get a TimeSpan that include's the record's timestamp:
                        timespan = weeutil.weeutil.archiveDaySpan(rec['dateTime'])
                        # Get an empty day accumulator:
                        day_accum = weewx.accum.Accum(timespan)
                    try:
                        weight = self._calc_weight(rec)
                    except IntervalError as e:
                        # Ignore records with bad values for 'interval'
                        log.error(e)
                        log.error('***  ignored.')
                        continue
                    # Try updating. If the time is out of the accumulator's time span, an
                    # exception will get raised.
                    try:
                        day_accum.addRecord(rec, weight=weight)
                    except weewx.accum.OutOfSpan:
                        # The record is out of the time span.
                        # Save the old accumulator:
                        self._set_day_summary(day_accum, None, cursor)
                        ndays += 1
                        # Get a new accumulator:
                        timespan = weeutil.weeutil.archiveDaySpan(rec['dateTime'])
                        day_accum = weewx.accum.Accum(timespan)
                        # try again
                        day_accum.addRecord(rec, weight=weight)

                    lastUpdate = max(lastUpdate, rec['dateTime']) \
                        if lastUpdate else rec['dateTime']
                    nrecs += 1
                    if progress_fn and nrecs % 1000 == 0:
                        progress_fn(nrecs, rec['dateTime'])

                # We're done with this transaction. Record the daily summary for the last day
                # unless it is empty
                if day_accum and not day_accum.isEmpty:
                    self._set_day_summary(day_accum, None, cursor)
                    ndays += 1
                # Patch lastUpdate:
                if lastUpdate:
                    self._write_metadata('lastUpdate', str(int(lastUpdate)), cursor)

            # Advance
            start_d += datetime.timedelta(days=trans_days)

        tdiff = time.time() - t1
        if nrecs:
            log.info("Processed %d records to backfill %d day summaries in %.2f seconds", nrecs,
                     ndays, tdiff)
        else:
            log.info("Daily summaries up to date")

        return nrecs, ndays

    # --------------------------- UTILITY FUNCTIONS -----------------------------------

    def _get_day_summary(self, sod_ts, cursor=None):
        """Return an instance of an appropriate accumulator, initialized to a given day's
        statistics.

        sod_ts: The timestamp of the start-of-day of the desired day.
        """

        # Get the TimeSpan for the day starting with sod_ts:
        _timespan = weeutil.weeutil.archiveDaySpan(sod_ts, 0)

        # Get an empty day accumulator:
        _day_accum = weewx.accum.Accum(_timespan, self.std_unit_system)

        _cursor = cursor or self.connection.cursor()

        try:
            # For each observation type, execute the SQL query and hand the results on to the
            # accumulator.
            for _day_key in self.daykeys:
                _cursor.execute(
                    "SELECT * FROM %s_day_%s WHERE dateTime = ?" % (self.table_name, _day_key),
                    (_day_accum.timespan.start,))
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
        
        lastUpdate: the time of the last update will be set to this unless it is None. 
        Normally, this is the timestamp of the last archive record added to the instance
        day_accum. """

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
            _qmarks = ','.join(len(_write_tuple) * '?')
            _sql_replace_str = "REPLACE INTO %s_day_%s VALUES(%s)" % (
                self.table_name, _summary_type, _qmarks)
            # ... and write to the database. In case the type doesn't appear in the database,
            # be prepared to catch an exception:
            try:
                cursor.execute(_sql_replace_str, _write_tuple)
            except weedb.OperationalError as e:
                log.error("Replace failed for database %s: %s", self.database_name, e)

        # If requested, update the time of the last daily summary update:
        if lastUpdate is not None:
            self._write_metadata('lastUpdate', str(int(lastUpdate)), cursor)

    def _calc_weight(self, record):
        if 'interval' not in record:
            raise ValueError("Missing value for record field 'interval'")
        elif record['interval'] <= 0:
            raise IntervalError(
                "Non-positive value for record field 'interval': %s" % (record['interval'],))
        weight = 60.0 * record['interval'] if self.version >= '2.0' else 1.0
        return weight

    def _read_metadata(self, key, cursor=None):
        """Obtain a value from the daily summary metadata table.

        Returns:
            Value of the metadata field. Returns None if no value was found.
        """
        _row = self.getSql(DaySummaryManager.meta_select_str % self.table_name, (key,), cursor)
        return _row[0] if _row else None

    def _write_metadata(self, key, value, cursor=None):
        """Write a value to the daily summary metadata table.

        Input parameters:
            key:    The name of the metadata field to be written to.
            value:  The value to be written to the metadata field.
        """
        _cursor = cursor or self.connection.cursor()

        try:
            _cursor.execute(DaySummaryManager.meta_replace_str % self.table_name,
                            (key, value))
        finally:
            if cursor is None:
                _cursor.close()

    def drop_daily(self):
        """Drop the daily summaries."""

        log.info("Dropping daily summary tables from '%s' ...", self.connection.database_name)
        try:
            _all_tables = self.connection.tables()
            with weedb.Transaction(self.connection) as _cursor:
                for _table_name in _all_tables:
                    if _table_name.startswith('%s_day_' % self.table_name):
                        _cursor.execute("DROP TABLE %s" % _table_name)

            self.daykeys = None
        except weedb.OperationalError as e:
            log.error("Drop daily summary tables failed for database '%s': %s",
                      self.connection.database_name, e)
            raise
        else:
            log.info("Dropped daily summary tables from database '%s'",
                     self.connection.database_name)


if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
