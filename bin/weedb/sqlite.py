#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""weedb driver for sqlite"""

import os.path

# Import sqlite3. If it does not support the 'with' statement, then
# import pysqlite2, which might...
import sqlite3

if not hasattr(sqlite3.Connection, "__exit__"):  # @UndefinedVariable
    del sqlite3
    from pysqlite2 import dbapi2 as sqlite3  # @Reimport @UnresolvedImport

# Test to see whether this version of SQLite has math functions. An explicit test is required
# (rather than just check version numbers) because the SQLite library may or may not have been
# compiled with the DSQLITE_ENABLE_MATH_FUNCTIONS option.
try:
    with sqlite3.connect(":memory:") as conn:
        conn.execute("SELECT RADIANS(0.0), SIN(0.0), COS(0.0);")
except sqlite3.OperationalError:
    has_math = False
else:
    has_math = True

import weedb
from weeutil.weeutil import to_int, to_bool


def guard(fn):
    """Decorator function that converts sqlite exceptions into weedb exceptions."""

    def guarded_fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.IntegrityError as e:
            raise weedb.IntegrityError(e)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if msg.startswith("unable to open"):
                raise weedb.PermissionError(e)
            elif msg.startswith("no such table"):
                raise weedb.NoTableError(e)
            elif msg.endswith("already exists"):
                raise weedb.TableExistsError(e)
            elif msg.startswith("no such column"):
                raise weedb.NoColumnError(e)
            else:
                raise weedb.OperationalError(e)
        except sqlite3.ProgrammingError as e:
            raise weedb.ProgrammingError(e)

    return guarded_fn


def connect(db_path='', driver='', **argv):  # @UnusedVariable
    """Factory function, to keep things compatible with DBAPI. 
    
    Args:
        db_path(str): A path to a SQLite database file
        driver(str): The weedb driver to use
        argv(dict): Any additional arguments to be passed on to the underlying Python driver
        
    Returns:
        Connection: An open weedb.sqlite.Connection connection.
    """
    return Connection(db_path=db_path, **argv)


@guard
def create(db_path='', driver='', **argv):
    """Create a SQLite database.

    Args:
        db_path(str): A path to where the SQLite database file should be created.
        driver(str): The weedb driver to use.
        argv(dict): Any additional arguments to be passed on to the underlying Python
            sqlite3 driver.

    Raises:
        DatabaseExistsError: If the SQLite database already exists.
    """

    # Check whether the database file exists:
    if os.path.exists(db_path):
        raise weedb.DatabaseExistsError(f"Database {db_path} already exists")
    else:
        if db_path != ':memory:':
            # Make any directories required, if any
            sqlite_dir = os.path.dirname(db_path)
            try:
                os.makedirs(sqlite_dir, exist_ok=True)
            except OSError:
                raise weedb.PermissionError(f"Cannot create {sqlite_dir}")
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        # Open, then immediately close the database.
        connection = sqlite3.connect(db_path, timeout=timeout, isolation_level=isolation_level)
        connection.close()


def drop(db_path, driver='', **argv):
    try:
        os.remove(db_path)
    except OSError as e:
        errno = getattr(e, 'errno', 2)
        if errno == 13:
            raise weedb.PermissionError(f"No permission to drop database {db_path}")
        else:
            raise weedb.NoDatabaseError(f"Attempt to drop non-existent database {db_path}")


class Connection(weedb.Connection):
    """A wrapper around a sqlite3 connection object."""

    @guard
    def __init__(self, db_path='', pragmas={}, **argv):
        """Initialize an instance of Connection.

        Args:
        
            db_path(str): The path to the SQLite database file.
            pragmas(dict): Any pragma statements, in the form of a dictionary.
            timeout(float): The amount of time, in seconds, to wait for a lock to be released.
              Optional. Default is 5.
            isolation_level(str): The type of isolation level to use. One of None,
              DEFERRED, IMMEDIATE, or EXCLUSIVE. Default is None (autocommit mode).

        Raises:
            NoDatabaseError: If the database file does not exist.
        """

        self.db_path = db_path
        if self.db_path != ':memory:' and not os.path.exists(db_path):
            raise weedb.NoDatabaseError(f"Attempt to open a non-existent database {db_path}")
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        connection = sqlite3.connect(db_path, timeout=timeout, isolation_level=isolation_level)

        for pragma in pragmas:
            connection.execute("PRAGMA %s=%s;" % (pragma, pragmas[pragma]))

        # Wrap the sqlite3 connection in a weedb Connection object
        weedb.Connection.__init__(self, connection, os.path.basename(db_path), 'sqlite')

    @guard
    def cursor(self):
        """Return a cursor object."""
        return self.connection.cursor(Cursor)

    @guard
    def execute(self, sql_string, sql_tuple=()):
        """Execute a sql statement. This specialized version takes advantage
        of sqlite's ability to do an execute without a cursor."""

        with self.connection:
            self.connection.execute(sql_string, sql_tuple)

    @guard
    def tables(self):
        """Returns a list of tables in the database."""

        table_list = list()
        for row in self.connection.execute("SELECT tbl_name FROM sqlite_master "
                                           "WHERE type='table';"):
            # Extract the table name. Sqlite returns unicode, so always
            # convert to a regular string:
            table_list.append(str(row[0]))
        return table_list

    @guard
    def genSchemaOf(self, table):
        """Return a summary of the schema of the specified table.
        
        If the table does not exist, an exception of type weedb.OperationalError is raised."""
        for row in self.connection.execute("""PRAGMA table_info(%s);""" % table):
            if row[2].upper().startswith('CHAR'):
                coltype = 'STR'
            else:
                coltype = str(row[2]).upper()
            yield (row[0], str(row[1]), coltype, not to_bool(row[3]), row[4], to_bool(row[5]))

    def columnsOf(self, table):
        """Return a list of columns in the specified table. If the table does not exist,
        None is returned."""

        column_list = [row[1] for row in self.genSchemaOf(table)]

        # If there are no columns (which means the table did not exist) raise an exceptional
        if not column_list:
            raise weedb.ProgrammingError("No such table %s" % table)
        return column_list

    @guard
    def get_variable(self, var_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute("PRAGMA %s;" % var_name)
            row = cursor.fetchone()
            return None if row is None else (var_name, row[0])
        finally:
            cursor.close()

    @property
    def has_math(self):
        global has_math
        return has_math

    @guard
    def begin(self):
        self.connection.execute("BEGIN TRANSACTION")

    @guard
    def commit(self):
        self.connection.commit()

    @guard
    def rollback(self):
        self.connection.rollback()

    @guard
    def close(self):
        self.connection.close()


class Cursor(sqlite3.Cursor):
    """A wrapper around the sqlite cursor object"""

    # The sqlite3 cursor object is very full featured. We need only turn
    # the sqlite exceptions into weedb exceptions.
    @guard
    def execute(self, *args, **kwargs):
        return sqlite3.Cursor.execute(self, *args, **kwargs)

    @guard
    def fetchone(self):
        return sqlite3.Cursor.fetchone(self)

    @guard
    def fetchall(self):
        return sqlite3.Cursor.fetchall(self)

    @guard
    def fetchmany(self, size=None):
        if size is None: size = self.arraysize
        return sqlite3.Cursor.fetchmany(self, size)

    def drop_columns(self, table, column_names):
        """Drop the set of 'column_names' from table 'table'.

        table: The name of the table from which the column(s) are to be dropped.

        column_names: A set (or list) of column names to be dropped. It is not an error to try to
        drop a non-existent column.
        """

        existing_column_set = set()
        create_list = []
        insert_list = []

        self.execute("""PRAGMA table_info(%s);""" % table)

        for row in self.fetchall():
            # Unpack the row
            row_no, obs_name, obs_type, no_null, default, pk = row
            existing_column_set.add(obs_name)
            # Search through the target columns.
            if obs_name in column_names:
                continue
            no_null_str = " NOT NULL" if no_null else ""
            pk_str = " UNIQUE PRIMARY KEY" if pk else ""
            default_str = " DEFAULT %s" % default if default is not None else ""
            create_list.append("`%s` %s%s%s%s" % (obs_name, obs_type, no_null_str,
                                                  pk_str, default_str))
            insert_list.append(obs_name)

        for column in column_names:
            if column not in existing_column_set:
                raise weedb.NoColumnError("Cannot DROP '%s'; column does not exist." % column)

        create_str = ", ".join(create_list)
        insert_str = ", ".join(insert_list)

        self.execute("CREATE TEMPORARY TABLE %s_temp (%s);" % (table, create_str))
        self.execute("INSERT INTO %s_temp SELECT %s FROM %s;" % (table, insert_str, table))
        self.execute("DROP TABLE %s;" % table)
        self.execute("CREATE TABLE %s (%s);" % (table, create_str))
        self.execute("INSERT INTO %s SELECT %s FROM %s_temp;" % (table, insert_str, table))
        self.execute("DROP TABLE %s_temp;" % table)

    def __enter__(self):
        return self

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        # It is not an error to close a sqlite3 cursor multiple times,
        # so there's no reason to guard it with a "try" clause:
        self.close()


def modify_config(config_dict, database_dict):
    """Modify the database dictionary returned by weedb.get_database_dict_from_config into
    something that suits our on purposes.
    """

    # Make a copy
    db_dict = dict(database_dict)

    # Very old versions of weedb used option 'root', instead of 'SQLITE_ROOT'
    sqlite_dir = db_dict.get('SQLITE_ROOT', db_dict.get('root', 'archive'))

    db_path = os.path.join(config_dict['WEEWX_ROOT'],
                           sqlite_dir,
                           db_dict['database_name'])
    db_dict['db_path'] = db_path
    # These are no longer needed:
    db_dict.pop('SQLITE_ROOT', None)
    db_dict.pop('root', None)
    del db_dict['database_name']

    return db_dict
