#
#    Copyright (c) 2012-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Middleware that sits above DBAPI and makes it a little more database independent."""

import sys

# The exceptions that the weedb package can raise:
class DatabaseError(StandardError):
    """Base class of all weedb exceptions."""


class OperationalError(DatabaseError):
    """Runtime database errors."""


class DatabaseExists(DatabaseError):
    """Attempt to create a database that already exists"""


class NoDatabase(DatabaseError):
    """Operation attempted on a database that does not exist."""


# In what follows, the test whether a database dictionary has function "dict" is
# to get around a bug in ConfigObj. It seems to be unable to unpack (using the
# '**' notation) a ConfigObj dictionary into a function. By calling .dict() a
# regular dictionary is returned, which can be unpacked.

def create(db_dict):
    """Create a database. If it already exists, an exception of type
    weedb.DatabaseExists will be raised."""
    __import__(db_dict['driver'])
    driver_mod = sys.modules[db_dict['driver']]
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.create(**db_dict.dict())
    else:
        return driver_mod.create(**db_dict)


def connect(db_dict):
    """Return a connection to a database. If the database does not
    exist, an exception of type weedb.OperationalError will be raised."""
    __import__(db_dict['driver'])
    driver_mod = sys.modules[db_dict['driver']]
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.connect(**db_dict.dict())
    else:
        return driver_mod.connect(**db_dict)


def drop(db_dict):
    """Drop (delete) a database. If the database does not exist,
    the exception weedb.NoDatabase will be raised."""
    __import__(db_dict['driver'])
    driver_mod = sys.modules[db_dict['driver']]
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.drop(**db_dict.dict())
    else:
        return driver_mod.drop(**db_dict)


class Connection(object):
    """Abstract base class, representing a connection to a database."""

    def __init__(self, connection, database_name, dbtype):
        """Superclass should raise exception of type weedb.OperationalError
        if the database does not exist."""
        self.connection = connection
        self.database_name = database_name
        self.dbtype = dbtype

    def cursor(self):
        """Returns an appropriate database cursor."""
        raise NotImplementedError

    def execute(self, sql_string, sql_tuple=()):
        """Execute a sql statement. This version does not return a cursor,
        so it can only be used for statements that do not return a result set."""

        cursor = self.cursor()
        try:
            cursor.execute(sql_string, sql_tuple)
        except DatabaseError:
            cursor.close()

    def tables(self):
        """Returns a list of the tables in the database.
        Returns an empty list if the database has no tables in it."""
        raise NotImplementedError

    def genSchemaOf(self, table):
        """Generator function that returns a summary of the table's schema.
        It returns a 6-way tuple:
        (number, column_name, column_type, can_be_null, default_value, is_primary)
        
        Example:
        (2, 'mintime', 'INTEGER', True, None, False)"""
        raise NotImplementedError

    def columnsOf(self, table):
        """Returns a list of the column names in the specified table.
        Raises exception of type weedb.OperationalError if the table does not exist."""
        raise NotImplementedError

    def begin(self):
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError

    def rollback(self):
        raise NotImplementedError

    def close(self):
        try:
            self.connection.close()
        except DatabaseError:
            pass


class Transaction(object):
    """Class to be used to wrap transactions in a 'with' clause."""
    def __init__(self, connection):
        self.connection = connection
        self.cursor = self.connection.cursor()

    def __enter__(self):
        self.connection.begin()
        return self.cursor

    def __exit__(self, etyp, einst, etb):
        if etyp is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        try:
            self.cursor.close()
        except DatabaseError:
            pass

