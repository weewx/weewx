#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Driver for sqlite"""

from __future__ import with_statement
import os.path

# Import sqlite3. If it does not support the 'with' statement, then
# import pysqlite2, which might...
import sqlite3

if not hasattr(sqlite3.Connection, "__exit__"):  # @UndefinedVariable
    del sqlite3
    from pysqlite2 import dbapi2 as sqlite3  #@Reimport @UnresolvedImport

sqlite_version = sqlite3.sqlite_version

import weedb
from weeutil.weeutil import to_int, to_bool

def guard(fn):
    """Decorator function that converts sqlite exceptions into weedb exceptions."""

    def guarded_fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.IntegrityError, e:
            raise weedb.IntegrityError(e)
        except sqlite3.OperationalError, e:
            # Change no such table errors into a ProgrammingError
            # (this is what MySQL does).
            if e.message.lower().startswith("no such table"):
                raise weedb.ProgrammingError(e)
            raise weedb.OperationalError(e)

    return guarded_fn


def connect(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    """Factory function, to keep things compatible with DBAPI. """
    return Connection(database_name=database_name, SQLITE_ROOT=SQLITE_ROOT, **argv)


def create(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    """Create the database specified by the db_dict. If it already exists,
    an exception of type DatabaseExists will be thrown."""
    file_path = get_filepath(SQLITE_ROOT, database_name, **argv)
    # Check whether the database file exists:
    if os.path.exists(file_path):
        raise weedb.DatabaseExists("Database %s already exists" % (file_path,))
    else:
        # If it doesn't exist, create the parent directories
        fileDirectory = os.path.dirname(file_path)
        if not os.path.exists(fileDirectory):
            os.makedirs(fileDirectory)
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        connection = sqlite3.connect(file_path, timeout=timeout, isolation_level=isolation_level)
        connection.close()

def get_filepath(SQLITE_ROOT, database_name, **argv):
    # For backwards compatibility, allow the keyword 'root', if 'SQLITE_ROOT' is
    # not defined:
    root_dir = SQLITE_ROOT or argv.get('root', '')
    return os.path.join(root_dir, database_name)
    
def drop(database_name='', SQLITE_ROOT='', driver='', **argv):  # @UnusedVariable
    file_path = get_filepath(SQLITE_ROOT, database_name, **argv)
    try:
        os.remove(file_path)
    except OSError:
        raise weedb.NoDatabase("""Attempt to drop non-existent database %s""" % (file_path,))


class Connection(weedb.Connection):
    """A wrapper around a sqlite3 connection object."""

    def __init__(self, database_name='', SQLITE_ROOT='', pragmas=None, **argv):
        """Initialize an instance of Connection.

        Parameters:
        
            database_name: The name of the Sqlite database. This is generally the file name
            SQLITE_ROOT: The path to the directory holding the database. Joining "SQLITE_ROOT" with
              "database_name" results in the full path to the sqlite file.
            pragmas: Any pragma statements, in the form of a dictionary.
            timeout: The amount of time, in seconds, to wait for a lock to be released. 
              Optional. Default is 5.
            isolation_level: The type of isolation level to use. One of None, 
              DEFERRED, IMMEDIATE, or EXCLUSIVE. Default is None (autocommit mode).
            
        If the operation fails, an exception of type weedb.OperationalError will be raised.
        """

        self.file_path = get_filepath(SQLITE_ROOT, database_name, **argv)
        if not os.path.exists(self.file_path):
            raise weedb.OperationalError("Attempt to open a non-existent database %s" % self.file_path)
        timeout = to_int(argv.get('timeout', 5))
        isolation_level = argv.get('isolation_level')
        try:
            connection = sqlite3.connect(self.file_path, timeout=timeout, isolation_level=isolation_level)
        except sqlite3.OperationalError:
            # The Pysqlite driver does not include the database file path.
            # Include it in case it might be useful.
            raise weedb.OperationalError("Unable to open database '%s'" % (self.file_path,))

        if pragmas is not None:
            for pragma in pragmas:
                connection.execute("PRAGMA %s=%s;" % (pragma, pragmas[pragma]))
        weedb.Connection.__init__(self, connection, database_name, 'sqlite')

    @guard
    def cursor(self):
        """Return a cursor object."""
        return Cursor(self.connection)

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
        for row in self.connection.execute("""SELECT tbl_name FROM sqlite_master WHERE type='table';"""):
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
    def __init__(self, *args, **kwargs):
        sqlite3.Cursor.__init__(self, *args, **kwargs)

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
