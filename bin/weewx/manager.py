#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with a weewx database archive.

This module includes two classes for managing database connections:

   Manager: For managing a WeeWX database without a daily summary.
   DaySummaryManager: For managing a WeeWX database with a daily summary. It inherits from Manager.

While one could instantiate these classes directly, it's easier with these two class methods:

    cls.open(): For opening an existing database.
    cls.open_with_create(): For opening a database that may or may not have been created.

where:
    cls is the class to be opened, either weewx.manager.Manager or weewx.manager.DaySummaryManager.

Which manager to choose depends on whether or not a daily summary is desired for performance
reasons. Generally, it's a good idea to use one. The database binding section in weewx.conf
is responsible for choosing the type of manager. Here's a typical entry in the configuration file.
Note the entry 'manager':

[DataBindings]

    [[wx_binding]]
        # The database must match one of the sections in [Databases].
        # This is likely to be the only option you would want to change.
        database = archive_sqlite
        # The name of the table within the database
        table_name = archive
        # The manager handles aggregation of data for historical summaries
        manager = weewx.manager.DaySummaryManager
        # The schema defines the structure of the database.
        # It is *only* used when the database is created.
        schema = schemas.wview_extended.schema

To avoid making the user dig into the configuration dictionary to figure out which type of
database manager to open, there is a convenience function for doing so:

    open_manager_with_config(config_dict, data_binding, initialize, default_binding_dict)

This will return a database manager of the proper type for the specified data binding.

Because opening a database and creating a manager can be expensive, the module also provides
a caching utility, DBBinder.

Example:

    db_binder = DBBinder(config_dict)
    db_manager = db_binder.get_manager(data_binding='wx_binding')
    for row in db_manager.genBatchRows(1664389800, 1664391600):
        print(row)

"""
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
from weeutil.weeutil import timestamp_to_string, to_int, TimeSpan

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

    Attributes:
        connection (weedb.Connection): The underlying database connection.
        table_name (str): The name of the main, archive table.
        first_timestamp (int): The timestamp of the earliest record in the table.
        last_timestamp (int): The timestamp of the last record in the table.
        std_unit_system (int): The unit system used by the database table.
        sqlkeys (list[str]): A list of the SQL keys that the database table supports.
    """

    def __init__(self, connection, table_name='archive', schema=None):
        """Initialize an object of type Manager.

        Args:
            connection (weedb.Connection): A weedb connection to the database to be managed.
            table_name (str): The name of the table to be used in the database.
                Default is 'archive'.
            schema (dict): The schema to be used. Optional.

        Raises:
            weedb.NoDatabaseError: If the database does not exist and no schema has been
                supplied.
            weedb.ProgrammingError: If the database exists, but has not been initialized and no
                schema has been supplied.
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

        # Set up cached data. Make sure to call my version, not any subclass's version. This is
        # because the subclass has not been initialized yet.
        Manager._sync(self)

    @classmethod
    def open(cls, database_dict, table_name='archive'):
        """Open and return a Manager or a subclass of Manager. The database must exist.

        Args:
            cls: The class object to be created. Typically, something
                like weewx.manager.DaySummaryManager.
            database_dict (dict): A database dictionary holding the information necessary to open
                the database.

                For example, for sqlite, it looks something like this:

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

            table_name (str): The name of the table to be used in the database. Default
                is 'archive'.

        Returns:
            cls: An instantiated instance of class "cls".

        Raises:
            weedb.NoDatabaseError: If the database does not exist.
            weedb.ProgrammingError: If the database exists, but has not been initialized.
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

        Args:
            cls: The class object to be created. Typically, something
                like weewx.manager.DaySummaryManager.
            database_dict (dict): A database dictionary holding the information necessary to open
                the database.

                For example, for sqlite, it looks something like this:

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

            table_name (str): The name of the table to be used in the database. Default
                is 'archive'.
            schema: The schema to be used.
        Returns:
            cls: An instantiated instance of class "cls".
        Raises:
            weedb.NoDatabaseError: Raised if the database does not exist and a schema has
                not been supplied.
            weedb.ProgrammingError: Raised if the database exists, but has not been initialized
                and no schema has been supplied.
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
        """str: The name of the database the manager is bound to."""
        return self.connection.database_name

    @property
    def obskeys(self):
        """list[str]: The list of observation types"""
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

    def _create_sync(self):
        """Create the internal caches."""

        # Fetch the first row in the database to determine the unit system in use. If the database
        # has never been used, then the unit system is still indeterminate --- set it to 'None'.
        _row = self.getSql("SELECT usUnits FROM %s LIMIT 1;" % self.table_name)
        self.std_unit_system = _row[0] if _row is not None else None

        # Cache the first and last timestamps
        self.first_timestamp = self.firstGoodStamp()
        self.last_timestamp = self.lastGoodStamp()

    def _sync(self):
        Manager._create_sync(self)

    def lastGoodStamp(self):
        """Retrieves the epoch time of the last good archive record.

        Returns:
            int|None: Time of the last good archive record as an epoch time,
                or None if there are no records.
        """
        _row = self.getSql("SELECT MAX(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None

    def firstGoodStamp(self):
        """Retrieves the earliest timestamp in the archive.

        Returns:
            int|None: Time of the first good archive record as an epoch time,
                or None if there are no records.
        """
        _row = self.getSql("SELECT MIN(dateTime) FROM %s" % self.table_name)
        return _row[0] if _row else None

    def exists(self, obs_type):
        """Checks whether the observation type exists in the database.

        Args:
            obs_type(str): The observation type to check for existence.

        Returns:
            bool: True if the observation type is in the database schema. False otherwise.
        """

        # Check to see if this is a valid observation type:
        return obs_type in self.obskeys

    def has_data(self, obs_type, timespan):
        """Checks whether the observation type exists in the database and whether it has any
        data.

        Args:
            obs_type(str): The observation type to check for existence.
            timespan (tuple): A 2-way tuple with the start and stop time to be checked for data.

        Returns:
            bool: True if the type is in the schema, and has some data within the given timespan.
                Otherwise, return False.
        """
        return self.exists(obs_type) \
               and bool(weewx.xtypes.get_aggregate(obs_type, timespan, 'not_null', self)[0])

    def addRecord(self, record_obj,
                  accumulator=None,
                  progress_fn=None,
                  log_success=True,
                  log_failure=True):
        """
        Commit a single record or a collection of records to the archive.

        Args:
            record_obj (iterable|dict): Either a data record, or an iterable that can return
                data records. Each data record must look like a dictionary, where the keys are the
                SQL types and the values are the values to be stored in the database.
            accumulator (weewx.accum.Accum): An optional accumulator. If given, the record
                will be added to the accumulator.
            progress_fn (function): This function will be called every 1000 insertions. It should
                have the signature fn(time, N) where time is the unix epoch time, and N is the
                insertion count.
            log_success (bool): Set to True to have successful insertions logged.
            log_failure (bool): Set to True to have unsuccessful insertions logged

        Returns:
            int: The number of successful insertions.
        """

        # Determine if record_obj is just a single dictionary instance (in which case it will have
        # method 'keys'). If so, wrap it in something iterable (a list):
        record_list = [record_obj] if hasattr(record_obj, 'keys') else record_obj

        min_ts = float('inf')  # A "big number"
        max_ts = 0
        N = 0
        with weedb.Transaction(self.connection) as cursor:

            for record in record_list:
                try:
                    # If the accumulator time matches the record we are working with,
                    # use it to update the highs and lows.
                    if accumulator and record_obj['dateTime'] == accumulator.timespan.stop:
                        self._updateHiLo(accumulator, cursor)

                    # Then add the record to the archives:
                    self._addSingleRecord(record, cursor, log_success, log_failure)

                    N += 1
                    if progress_fn and N % 1000 == 0:
                        progress_fn(record['dateTime'], N)

                    min_ts = min(min_ts, record['dateTime'])
                    max_ts = max(max_ts, record['dateTime'])
                except (weedb.IntegrityError, weedb.OperationalError) as e:
                    if log_failure:
                        log.error("Unable to add record %s to database '%s': %s",
                                  timestamp_to_string(record['dateTime']),
                                  self.database_name, e)

        # Update the cached timestamps. This has to sit outside the transaction context,
        # in case an exception occurs.
        if self.first_timestamp is not None:
            self.first_timestamp = min(min_ts, self.first_timestamp)
        if self.last_timestamp is not None:
            self.last_timestamp = max(max_ts, self.last_timestamp)

        return N

    def _addSingleRecord(self, record, cursor, log_success=True, log_failure=True):
        """Internal function for adding a single record to the main archive table."""

        if record['dateTime'] is None:
            if log_failure:
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
        if log_success:
            log.info("Added record %s to database '%s'",
                     timestamp_to_string(record['dateTime']),
                     self.database_name)

    def _updateHiLo(self, accumulator, cursor):
        pass

    def genBatchRows(self, startstamp=None, stopstamp=None):
        """Generator function that yields raw rows from the archive database with timestamps within
        an interval.

        Args:
            startstamp (int|None): Exclusive start of the interval in epoch time. If 'None',
                then start at earliest archive record.
            stopstamp (int|None): Inclusive end of the interval in epoch time. If 'None',
                then end at last archive record.

        Yields:
            list: Each iteration yields a single data row.
        """

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

        Args:
            startstamp (int|None): Exclusive start of the interval in epoch time. If 'None',
                then start at earliest archive record.
            stopstamp (int|None): Inclusive end of the interval in epoch time. If 'None',
                then end at last archive record.

        Yields:
             dict|None: A dictionary where key is the observation type (eg, 'outTemp') and the
                value is the observation value, or None if there are no rows in the time range.
        """

        for _row in self.genBatchRows(startstamp, stopstamp):
            yield dict(list(zip(self.sqlkeys, _row))) if _row else None

    def getRecord(self, timestamp, max_delta=None):
        """Get a single archive record with a given epoch time stamp.

        Args:
            timestamp (int): The epoch time of the desired record.
            max_delta (int|None): The largest difference in time that is acceptable.
                [Optional. The default is no difference]

        Returns:
            dict|None: a record dictionary or None if the record does not exist.
        """

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
        """Update (replace) a single value in the database.

        Args:
            timestamp (int): The timestamp of the record to be updated.
            obs_type (str): The observation type to be updated.
            new_value (float | str): The updated value
        """

        self.connection.execute("UPDATE %s SET %s=? WHERE dateTime=?" %
                                (self.table_name, obs_type), (new_value, timestamp))

    def getSql(self, sql, sqlargs=(), cursor=None):
        """Executes an arbitrary SQL statement on the database. The result will be a single row.

        Args:
            sql (str): The SQL statement
            sqlargs (tuple): A tuple containing the arguments for the SQL statement
            cursor (cursor| None): An optional cursor to be used. If not given, then one will be
                created and closed when finished.

        Returns:
             tuple: a tuple containing a single result set.
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
        the database, returning a result set.

        Args:
            sql (str): The SQL statement
            sqlargs (tuple): A tuple containing the arguments for the SQL statement.

        Yields:
            list: A row in the result set.
        """

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

    def add_column(self, column_name, column_type="REAL"):
        """Add a single new column to the database.

        Args:
            column_name (str): The name of the new column.
            column_type (str): The type ("REAL"|"INTEGER|) of the new column. Default is "REAL".
        """
        with weedb.Transaction(self.connection) as cursor:
            self._add_column(column_name, column_type, cursor)

    def _add_column(self, column_name, column_type, cursor):
        """Add a column to the main archive table"""
        cursor.execute("ALTER TABLE %s ADD COLUMN `%s` %s"
                       % (self.table_name, column_name, column_type))

    def rename_column(self, old_column_name, new_column_name):
        """Rename an existing column

        Args:
            old_column_name (str): Tne old name of the column to be renamed.
            new_column_name (str): Its new name
        """
        with weedb.Transaction(self.connection) as cursor:
            self._rename_column(old_column_name, new_column_name, cursor)

    def _rename_column(self, old_column_name, new_column_name, cursor):
        """Rename a column in the main archive table."""
        cursor.execute("ALTER TABLE %s RENAME COLUMN %s TO %s"
                       % (self.table_name, old_column_name, new_column_name))

    def drop_columns(self, column_names):
        """Drop a list of columns from the database

        Args:
            column_names (list[str]): A list containing the observation types to be dropped.
        """
        with weedb.Transaction(self.connection) as cursor:
            self._drop_columns(column_names, cursor)

    def _drop_columns(self, column_names, cursor):
        """Drop a column in the main archive table"""
        cursor.drop_columns(self.table_name, column_names)

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
    """Copy over an old archive to a new one, using an optionally new unit system and schema.

    Args:
        old_db_dict (dict): The database dictionary for the old database. See
            method Manager.open() for the definition of a database dictionary.
        new_db_dict (dict): THe database dictionary for the new database.  See
            method Manager.open() for the definition of a database dictionary.
        new_unit_system (int|None): The new unit system to be used, or None to keep the old one.
        new_schema (dict): The new schema to use, or None to use the old one.

    """

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

        Args:
            config_dict (dict): The configuration dictionary.
        """

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
        """Given a binding name, returns the managed object

        Args:
            data_binding (str): The returned Manager object will be bound to this binding.
            initialize (bool): True to initialize the database first.

        Returns:
            weewx.manager.Manager: Or its subclass, weewx.manager.DaySummaryManager, depending
                on the settings under the [DataBindings] section.
        """
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
    """Convenience function that given a configuration dictionary and a database name,
     returns a database dictionary that can be used to open the database using Manager.open().

    Args:

        config_dict (dict): The configuration dictionary.
        database (str): The database whose database dict is to be retrieved
            (example: 'archive_sqlite')

    Returns:
        dict: Adatabase dictionary, with everything needed to pass on to a Manager or weedb in
            order to open a database.

    Example:
        Given a configuration file snippet that looks like:

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
# A "manager dict" includes keys:
#
#  manager: The manager class
#  table_name: The name of the internal table
#  schema: The schema to be used in case of initialization
#  database_dict: The database dictionary. This will be passed on to weedb.
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


def show_progress(last_time, nrec=None):
    """Utility function to show our progress"""
    if nrec:
        msg = "Records processed: %d; time: %s\r" \
              % (nrec, timestamp_to_string(last_time))
    else:
        msg = "Processed through: %s\r" % timestamp_to_string(last_time)
    print(msg, end='', file=sys.stdout)
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

    version = "4.0"

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

        self.version = None
        self.daykeys = None
        DaySummaryManager._create_sync(self)
        self.patch_sums()

    def exists(self, obs_type):
        """Checks whether the observation type exists in the database."""

        # Check both with the superclass, and my own set of daily summaries
        return super(DaySummaryManager, self).exists(obs_type) or obs_type in self.daykeys

    def close(self):
        self.version = None
        self.daykeys = None
        super(DaySummaryManager, self).close()

    def _create_sync(self):
        # Get a list of all the observation types which have daily summaries
        all_tables = self.connection.tables()
        prefix = "%s_day_" % self.table_name
        n_prefix = len(prefix)
        meta_name = '%s_day__metadata' % self.table_name
        # Create a set of types that are in the daily summaries:
        self.daykeys = {x[n_prefix:] for x in all_tables
                        if (x.startswith(prefix) and x != meta_name)}

        self.version = self._read_metadata('Version')
        if self.version is None:
            self.version = '1.0'
        log.debug('Daily summary version is %s', self.version)

    def _sync(self):
        super(DaySummaryManager, self)._sync()
        self._create_sync()

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
            if type(self) == weewx.wxmanager.WXDaySummaryManager or 'windSpeed' in self.sqlkeys:
                # For backwards compatibility, include 'wind'
                day_summaries_schemas += [('wind', 'vector')]

        # Create the tables needed for the daily summaries in one transaction:
        with weedb.Transaction(self.connection) as cursor:
            # obs will be a 2-way tuple (obs_type, ('scalar'|'vector'))
            for obs in day_summaries_schemas:
                self._initialize_day_table(obs[0], obs[1].lower(), cursor)

            # Now create the meta table...
            cursor.execute(DaySummaryManager.meta_create_str % self.table_name)
            # ... then put the version number in it:
            self._write_metadata('Version', DaySummaryManager.version, cursor)

            log.info("Created daily summary tables")

    def _initialize_day_table(self, obs_type, day_schema_type, cursor):
        """Initialize a single daily summary.

        obs_type: An observation type, such as 'outTemp'
        day_schema: The schema to be used. Either 'scalar', or 'vector'
        cursor: An open cursor
        """
        s = ', '.join(
            ["%s %s" % column_type
             for column_type in DaySummaryManager.day_schemas[day_schema_type]])

        sql_create_str = "CREATE TABLE %s_day_%s (%s);" % (self.table_name, obs_type, s)
        cursor.execute(sql_create_str)

    def _add_column(self, column_name, column_type, cursor):
        # First call my superclass's version...
        Manager._add_column(self, column_name, column_type, cursor)
        # ... then do mine
        self._initialize_day_table(column_name, 'scalar', cursor)

    def _rename_column(self, old_column_name, new_column_name, cursor):
        # First call my superclass's version...
        Manager._rename_column(self, old_column_name, new_column_name, cursor)
        # ... then do mine
        cursor.execute("ALTER TABLE %s_day_%s RENAME TO %s_day_%s;"
                       % (self.table_name, old_column_name, self.table_name, new_column_name))

    def _drop_columns(self, column_names, cursor):
        # First call my superclass's version...
        Manager._drop_columns(self, column_names, cursor)
        # ... then do mine
        for column_name in column_names:
            cursor.execute("DROP TABLE IF EXISTS %s_day_%s;" % (self.table_name, column_name))

    def _addSingleRecord(self, record, cursor, log_success=True, log_failure=True):
        """Specialized version that updates the daily summaries, as well as the main archive
        table.
        """

        # First let my superclass handle adding the record to the main archive table:
        super(DaySummaryManager, self)._addSingleRecord(record, cursor, log_success, log_failure)

        # Get the start of day for the record:
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])

        # Get the weight. If the value for 'interval' is bad, an exception will be raised.
        try:
            _weight = self._calc_weight(record)
        except IntervalError as e:
            # Bad value for interval. Ignore this record
            if log_failure:
                log.info(e)
                log.info('*** record ignored')
            return

        # Now add to the daily summary for the appropriate day:
        _day_summary = self._get_day_summary(_sod_ts, cursor)
        _day_summary.addRecord(record, weight=_weight)
        self._set_day_summary(_day_summary, record['dateTime'], cursor)
        if log_success:
            log.info("Added record %s to daily summary in '%s'",
                     timestamp_to_string(record['dateTime']),
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

    def backfill_day_summary(self, start_d=None, stop_d=None,
                             progress_fn=show_progress, trans_days=5):

        """Fill the daily summaries from an archive database.

        Normally, the daily summaries get filled by LOOP packets (to get maximum time resolution),
        but if the database gets corrupted, or if a new user is starting up with imported wview
        data, it's necessary to recreate it from straight archive data. The Hi/Lows will all be
        there, but the times won't be any more accurate than the archive period.

        To help prevent database errors for large archives, database transactions are limited to
        trans_days days of archive data. This is a trade-off between speed and memory usage.

        Args:

            start_d (datetime.date|None): The first day to be included, specified as a datetime.date
                object [Optional. Default is to start with the first datum in the archive.]
            stop_d (datetime.date|None): The last day to be included, specified as a datetime.date
                object [Optional. Default is to include the date of the last archive record.]
            progress_fn (function): This function will be called after processing every 1000 records.
            trans_day (int): Number of days of archive data to be used for each daily summaries database
                transaction. [Optional. Default is 5.]

        Returns:
             tuple[int,int]: A 2-way tuple (nrecs, ndays) where
                  nrecs is the number of records backfilled;
                  ndays is the number of days
        """
        # Definition:
        #   last_daily_ts: Timestamp of the last record that was incorporated into the
        #                  daily summary. Usually it is equal to last_record, but it can be less
        #                  if a backfill was aborted.

        log.info("Starting backfill of daily summaries")

        if self.first_timestamp is None:
            # Nothing in the archive database, so there's nothing to do.
            log.info("Empty database")
            return 0, 0

        # Convert tranch size to a timedelta object, so we can perform arithmetic with it.
        tranche_days = datetime.timedelta(days=trans_days)

        t1 = time.time()

        last_daily_ts = to_int(self._read_metadata('lastUpdate'))

        # The goal here is to figure out:
        #  first_d:   A datetime.date object, representing the first date to be rebuilt.
        #  last_d:    A datetime.date object, representing the date after the last date
        #             to be rebuilt.

        # Check preconditions. Cannot specify start_d or stop_d unless the summaries are complete.
        if last_daily_ts != self.last_timestamp and (start_d or stop_d):
            raise weewx.ViolatedPrecondition("Daily summaries are not complete. "
                                             "Try again without from/to dates.")

        # If we were doing a complete rebuild, these would be the first and
        # last dates to be processed:
        first_d = datetime.date.fromtimestamp(weeutil.weeutil.startOfArchiveDay(
            self.first_timestamp))
        last_d = datetime.date.fromtimestamp(weeutil.weeutil.startOfArchiveDay(
            self.last_timestamp))

        # Are there existing daily summaries?
        if last_daily_ts:
            # Yes. Is it an aborted rebuild?
            if last_daily_ts < self.last_timestamp:
                # We are restarting from an aborted build. Pick up from where we left off.
                # Because last_daily_ts always sits on the boundary of a day, this will include the
                # following day to be included, but not the actual record with
                # timestamp last_daily_ts.
                first_d = datetime.date.fromtimestamp(last_daily_ts)
            else:
                # Daily summaries exist, and they are complete.
                if not start_d and not stop_d:
                    # The daily summaries are complete, yet the user has not specified anything.
                    # Guess we're done.
                    log.info("Daily summaries up to date")
                    return 0, 0
                # Trim what we rebuild to what the user has specified
                if start_d:
                    first_d = max(first_d, start_d)
                if stop_d:
                    last_d = min(last_d, stop_d)

        # For what follows, last_d needs to point to the day *after* the last desired day
        last_d += datetime.timedelta(days=1)

        nrecs = 0
        ndays = 0

        mark_d = first_d

        while mark_d < last_d:
            # Calculate the last date included in this transaction
            stop_transaction = min(mark_d + tranche_days, last_d)
            day_accum = None

            with weedb.Transaction(self.connection) as cursor:
                # Go through all the archive records in the time span, adding them to the
                # daily summaries
                start_batch_ts = time.mktime(mark_d.timetuple())
                stop_batch_ts = time.mktime(stop_transaction.timetuple())
                for rec in self.genBatchRecords(start_batch_ts, stop_batch_ts):
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
                        log.info(e)
                        log.info('***  ignored.')
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

                    if last_daily_ts is None:
                        last_daily_ts = rec['dateTime']
                    else:
                        last_daily_ts = max(last_daily_ts, rec['dateTime'])
                    nrecs += 1
                    if progress_fn and nrecs % 1000 == 0:
                        progress_fn(rec['dateTime'], nrecs)

                # We're done with this transaction. Unless it is empty, save the daily summary for
                # the last day
                if day_accum and not day_accum.isEmpty:
                    self._set_day_summary(day_accum, None, cursor)
                    ndays += 1
                # Patch lastUpdate:
                if last_daily_ts:
                    self._write_metadata('lastUpdate', str(int(last_daily_ts)), cursor)

            # Advance to the next tranche
            mark_d += tranche_days

        tdiff = time.time() - t1
        log.info("Processed %d records to backfill %d day summaries in %.2f seconds",
                 nrecs, ndays, tdiff)

        return nrecs, ndays

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

    def recalculate_weights(self, start_d=None, stop_d=None,
                            tranche_size=100, weight_fn=None, progress_fn=show_progress):
        """Recalculate just the daily summary weights.

        Rather than backfill all the daily summaries, this function simply recalculates the
        weighted sums.

        start_d: The first day to be included, specified as a datetime.date object [Optional.
        Default is to start with the first record in the daily summaries.]

        stop_d: The last day to be included, specified as a datetime.date object [Optional.
        Default is to end with the last record in the daily summaries.]

        tranche_size: How many days to do in a single transaction.

        weight_fn: A function used to calculate the weights for a record. Default
        is _calc_weight().

        progress_fn: This function will be called after every tranche with the timestamp of the
        last record processed.
        """

        log.info("recalculate_weights: Using database '%s'" % self.database_name)
        log.debug("recalculate_weights: Tranche size %d" % tranche_size)

        # Convert tranch size to a timedelta object, so we can perform arithmetic with it.
        tranche_days = datetime.timedelta(days=tranche_size)

        # Get the first and last timestamps for all the tables in the daily summaries.
        first_ts, last_ts = self.get_first_last()
        if first_ts is None or last_ts is None:
            log.info("recalculate_weights: Empty daily summaries. Nothing done.")
            return

        # Convert to date objects
        first_d = datetime.date.fromtimestamp(first_ts)
        last_d = datetime.date.fromtimestamp(last_ts)

        # Trim according to the requested dates
        if start_d:
            first_d = max(first_d, start_d)
        if stop_d:
            last_d = min(last_d, stop_d)

        # For what follows, last_date needs to point to the day *after* the last desired day.
        last_d += datetime.timedelta(days=1)

        mark_d = first_d

        # March forward, tranche by tranche
        while mark_d < last_d:
            end_of_tranche_d = min(mark_d + tranche_days, last_d)
            self._do_tranche(mark_d, end_of_tranche_d, weight_fn, progress_fn)
            mark_d = end_of_tranche_d

    def _do_tranche(self, start_d, last_d, weight_fn=None, progress_fn=None):
        """Reweight a tranche of daily summaries.

        start_d: A datetime.date object with the first date in the tranche to be reweighted.

        last_d: A datetime.date object with the day after the last date in the
        tranche to be reweighted.

        weight_fn: A function used to calculate the weights for a record. Default is
        _calc_weight().

        progress_fn: A function to call to show progress. It will be called after every update.
        """

        if weight_fn is None:
            weight_fn = DaySummaryManager._calc_weight

        # Do all the dates in the tranche as a single transaction
        with weedb.Transaction(self.connection) as cursor:

            # March down the tranche, day by day
            mark_d = start_d
            while mark_d < last_d:
                next_d = mark_d + datetime.timedelta(days=1)
                day_span = TimeSpan(time.mktime(mark_d.timetuple()),
                                    time.mktime(next_d.timetuple()))
                # Get an accumulator for the day
                day_accum = weewx.accum.Accum(day_span)
                # Now populate it with a day's worth of records
                for rec in self.genBatchRecords(day_span.start, day_span.stop):
                    try:
                        weight = weight_fn(self, rec)
                    except IntervalError as e:
                        log.info("%s: %s", timestamp_to_string(rec['dateTime']), e)
                        log.info('***  ignored.')
                    else:
                        day_accum.addRecord(rec, weight=weight)
                # Write out the results of the accumulator
                self._set_day_sums(day_accum, cursor)
                if progress_fn:
                    # Update our progress
                    progress_fn(day_accum.timespan.stop)
                # On to the next day
                mark_d += datetime.timedelta(days=1)

    def _set_day_sums(self, day_accum, cursor):
        """Replace the weighted sums for all types for a day. Don't touch the mins and maxes."""
        for obs_type in day_accum:
            # Skip any types that are not in the daily summary schema
            if obs_type not in self.daykeys:
                continue
            # This will be list that looks like ['sum=2345.65', 'count=123', ... etc]
            # It will only include attributes that are in the accumulator for this type.
            set_list = ['%s=%s' % (k, getattr(day_accum[obs_type], k))
                        for k in ['sum', 'count', 'wsum', 'sumtime',
                                  'xsum', 'ysum', 'dirsumtime',
                                  'squaresum', 'wsquaresum']
                        if hasattr(day_accum[obs_type], k)]
            update_sql = "UPDATE {archive_table}_day_{obs_type} SET {set_stmt} " \
                         "WHERE dateTime = ?;".format(archive_table=self.table_name,
                                                      obs_type=obs_type,
                                                      set_stmt=', '.join(set_list))
            # Update this observation type's weighted sums:
            cursor.execute(update_sql, (day_accum.timespan.start,))

    def patch_sums(self):
        """Version 4.2.0 accidentally interpreted V2.0 daily sums as V1.0, so the weighted sums
        were all given a weight of 1.0, instead of the interval length. Version 4.3.0 attempted
        to fix this bug but introduced its own bug by failing to weight 'dirsumtime'. This fixes
        both bugs."""
        if '1.0' < self.version < '4.0':
            msg = "Daily summaries at V%s. Patching to V%s" \
                  % (self.version, DaySummaryManager.version)
            print(msg)
            log.info(msg)
            # We need to upgrade from V2.0 or V3.0 to V4.0. The only difference is
            # that the patch has been supplied to V4.0 daily summaries. The patch
            # need only be done from a date well before the V4.2 release.
            # We pick 1-Jun-2020.
            self.recalculate_weights(start_d=datetime.date(2020, 6, 1))
            self._write_metadata('Version', DaySummaryManager.version)
            self.version = DaySummaryManager.version
            log.info("Patch finished.")

    def update(self):
        """Update the database to V4.0.

        - all V1.0 daily sums need to be upgraded
        - V2.0 daily sums need to be upgraded but only those after a date well before the
          V4.2.0 release (we pick 1 June 2020)
        - V3.0 daily sums need to be upgraded due to a bug in the V4.2.0 and V4.3.0 releases
          but only those after 1 June 2020
        """
        if self.version == '1.0':
            self.recalculate_weights(weight_fn=DaySummaryManager._get_weight)
            self._write_metadata('Version', DaySummaryManager.version)
            self.version = DaySummaryManager.version
        elif self.version == '2.0' or self.version == '3.0':
            self.patch_sums()

    # --------------------------- UTILITY FUNCTIONS -----------------------------------

    def get_first_last(self):
        """Obtain the first and last timestamp of all the daily summaries.

        Returns:
            tuple[int,int]|None: A two-way tuple (first_ts, last_ts) with the first timestamp and
                the last timestamp. Returns None if there is nothing in the daily summaries.
        """

        big_select = ["SELECT MIN(dateTime) AS mtime FROM %s_day_%s"
                      % (self.table_name, key) for key in self.daykeys]
        big_sql = " UNION ".join(big_select) + " ORDER BY mtime ASC LIMIT 1"
        first_ts = self.getSql(big_sql)

        big_select = ["SELECT MAX(dateTime) AS mtime FROM %s_day_%s"
                      % (self.table_name, key) for key in self.daykeys]
        big_sql = " UNION ".join(big_select) + " ORDER BY mtime DESC LIMIT 1"
        last_ts = self.getSql(big_sql)

        return first_ts[0], last_ts[0]

    def _get_day_summary(self, sod_ts, cursor=None):
        """Return an instance of an appropriate accumulator, initialized to a given day's
        statistics.

        sod_ts: The timestamp of the start-of-day of the desired day.
        """

        # Get the TimeSpan for the day starting with sod_ts:
        _timespan = weeutil.weeutil.daySpan(sod_ts)

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
        """Returns the weighting to be used, depending on the version of the daily summaries."""
        if 'interval' not in record:
            raise ValueError("Missing value for record field 'interval'")
        elif record['interval'] <= 0:
            raise IntervalError(
                "Non-positive value for record field 'interval': %s" % (record['interval'],))
        weight = 60.0 * record['interval'] if self.version >= '2.0' else 1.0
        return weight

    def _get_weight(self, record):
        """Always returns a weight based on the field 'interval'."""
        if 'interval' not in record:
            raise ValueError("Missing value for record field 'interval'")
        elif record['interval'] <= 0:
            raise IntervalError(
                "Non-positive value for record field 'interval': %s" % (record['interval'],))
        return 60.0 * record['interval']

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


if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
