#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
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


def connect(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    """Factory function, to keep things compatible with DBAPI. """
    return Connection(database_name=database_name, SQLITE_ROOT=SQLITE_ROOT, **argv)


@guard
def create(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    """Create the database specified by the db_dict. If it already exists,
    an exception of type DatabaseExistsError will be thrown."""
    file_path = _get_filepath(SQLITE_ROOT, database_name, **argv)
    # Check whether the database file exists:
    if os.path.exists(file_path):
        raise weedb.DatabaseExistsError("Database %s already exists" % (file_path,))
    else:
        if file_path != ':memory:':
            # If it doesn't exist, create the parent directories
            fileDirectory = os.path.dirname(file_path)
            if not os.path.exists(fileDirectory):
                try:
                    os.makedirs(fileDirectory)
                except OSError:
                    raise weedb.PermissionError("No permission to create %s" % fileDirectory)
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        # Open, then immediately close the database.
        connection = sqlite3.connect(file_path, timeout=timeout, isolation_level=isolation_level)
        connection.close()


def drop(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    file_path = _get_filepath(SQLITE_ROOT, database_name, **argv)
    try:
        os.remove(file_path)
    except OSError as e:
        errno = getattr(e, 'errno', 2)
        if errno == 13:
            raise weedb.PermissionError("No permission to drop database %s" % file_path)
        else:
            raise weedb.NoDatabaseError("Attempt to drop non-existent database %s" % file_path)


def _get_filepath(SQLITE_ROOT, database_name, **argv):
    """Utility function to calculate the path to the sqlite database file."""
    if database_name == ':memory:':
        return database_name
    # For backwards compatibility, allow the keyword 'root', if 'SQLITE_ROOT' is
    # not defined:
    root_dir = SQLITE_ROOT or argv.get('root', '')
    return os.path.join(root_dir, database_name)


class Connection(weedb.Connection):
    """A wrapper around a sqlite3 connection object."""

    @guard
    def __init__(self, database_name='', SQLITE_ROOT='', pragmas=None, **argv):
        """Initialize an instance of Connection.

        Args:
        
            database_name: The name of the Sqlite database. This is generally the file name
            SQLITE_ROOT: The path to the directory holding the database. Joining "SQLITE_ROOT" with
              "database_name" results in the full path to the sqlite file.
            pragmas: Any pragma statements, in the form of a dictionary.
            timeout: The amount of time, in seconds, to wait for a lock to be released.
              Optional. Default is 5.
            isolation_level(str): The type of isolation level to use. One of None,
              DEFERRED, IMMEDIATE, or EXCLUSIVE. Default is None (autocommit mode).

        Raises:
            NoDatabaseError: If the database file does not exist.
        """

        self.file_path = _get_filepath(SQLITE_ROOT, database_name, **argv)
        if self.file_path != ':memory:' and not os.path.exists(self.file_path):
            raise weedb.NoDatabaseError("Attempt to open a non-existent database %s"
                                        % self.file_path)
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        connection = sqlite3.connect(self.file_path, timeout=timeout,
                                     isolation_level=isolation_level)

        if pragmas:
            for pragma in pragmas:
                connection.execute("PRAGMA %s=%s;" % (pragma, pragmas[pragma]))
        weedb.Connection.__init__(self, connection, database_name, 'sqlite')

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


class Cursor(sqlite3.Cursor, weedb.Cursor):
    """A wrapper around the sqlite cursor object"""

    # The sqlite3 cursor object is very full-featured. We need only turn
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
