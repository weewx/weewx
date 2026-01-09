#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Middleware that sits above DBAPI and makes it a little more database independent.

Weedb generally follows the MySQL exception model. Specifically:
  - Operations on a non-existent database result in a weedb.OperationalError exception
    being raised.
  - Operations on a non-existent table result in a weedb.ProgrammingError exception
    being raised.
  - Select statements requesting non-existing columns result in a weedb.OperationalError
    exception being raised.
  - Attempt to add a duplicate key results in a weedb.IntegrityError exception
    being raised.
"""

import importlib


# The exceptions that the weedb package can raise:
class DatabaseError(Exception):
    """Base class of all weedb exceptions."""


class IntegrityError(DatabaseError):
    """Operation attempted involving the relational integrity of the database."""


class ProgrammingError(DatabaseError):
    """SQL or other programming error."""


class DatabaseExistsError(ProgrammingError):
    """Attempt to create a database that already exists"""


class TableExistsError(ProgrammingError):
    """Attempt to create a table that already exists."""


class NoTableError(ProgrammingError):
    """Attempt to operate on a non-existing table."""


class OperationalError(DatabaseError):
    """Runtime database errors."""


class NoDatabaseError(OperationalError):
    """Operation attempted on a database that does not exist."""


class CannotConnectError(OperationalError):
    """Unable to connect to the database server."""


class DisconnectError(OperationalError):
    """Database went away."""


class NoColumnError(OperationalError):
    """Attempt to operate on a column that does not exist."""


class BadPasswordError(OperationalError):
    """Bad or missing password."""


class PermissionError(OperationalError):
    """Lacking necessary permissions."""


# For backwards compatibility:
DatabaseExists = DatabaseExistsError
NoDatabase = NoDatabaseError
CannotConnect = CannotConnectError


# In what follows, the test whether a database dictionary has function "dict" is
# to get around a bug in ConfigObj. It seems to be unable to unpack (using the
# '**' notation) a ConfigObj dictionary into a function. By calling .dict() a
# regular dictionary is returned, which can be unpacked.

def create(db_dict):
    """Create a database. If it already exists, an exception of type
    weedb.DatabaseExistsError will be raised."""
    driver_mod = importlib.import_module(db_dict['driver'])
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.create(**db_dict.dict())
    else:
        return driver_mod.create(**db_dict)


def connect(db_dict):
    """Return a connection to a database. If the database does not
    exist, an exception of type weedb.NoDatabaseError will be raised."""
    driver_mod = importlib.import_module(db_dict['driver'])
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.connect(**db_dict.dict())
    else:
        return driver_mod.connect(**db_dict)


def drop(db_dict):
    """Drop (delete) a database. If the database does not exist,
    the exception weedb.NoDatabaseError will be raised."""
    driver_mod = importlib.import_module(db_dict['driver'])
    # See note above
    if hasattr(db_dict, "dict"):
        return driver_mod.drop(**db_dict.dict())
    else:
        return driver_mod.drop(**db_dict)


class Connection:
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
        finally:
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
        """Returns a list of the column names in the specified table. Implementers
        should raise an exception of type weedb.ProgrammingError if the table does not exist."""
        raise NotImplementedError

    def get_variable(self, var_name):
        """Return a database specific operational variable. Generally, things like 
        pragmas, or optimization-related variables.
        
        It returns a 2-way tuple:
        (variable-name, variable-value)
        If the variable does not exist, it returns None.
        """
        raise NotImplementedError

    @property
    def has_math(self):
        """Returns True if the database supports math functions such as cos() and sin().
        False otherwise."""
        return True

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

    def __enter__(self):
        return self

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        try:
            self.close()
        except DatabaseError:
            pass


class Cursor:

    def execute(self, sql_string, sql_tuple=()):
        raise NotImplementedError

    def create_table(self, table_name, table_schema):
        """Create a table with the given name and columns.
        table_name (str): The name of the table to be created.
        table_schema (List[Tuple]): List of tuples, each tuple containing 
            the column name and type.
        """
        # List comprehension of the types, joined together with commas.
        sqltypestr = ', '.join(["%s %s" % _type for _type in table_schema])
        self.execute(f"CREATE TABLE {table_name} ({sqltypestr});")

    def drop_table(self, table_name):
        """Drop an existing table."""
        self.execute(f"DROP TABLE IF EXISTS {table_name}")

    def add_column(self, table_name, column_name, column_type):
        """Add a single new column to an existing table."""
        self.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def rename_column(self, table_name, old_column_name, new_column_name):
        """Rename a column in the main archive table."""
        self.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_column_name} TO {new_column_name}")

    def drop_columns(self, table, column_names):
        """Drop one or more columns from an existing table."""
        raise NotImplementedError

    def rename_table(self, old_table_name, new_table_name):
        """Rename an existing table."""
        self.execute(f"ALTER TABLE {old_table_name} RENAME TO {new_table_name}")

class Transaction:
    """Class to be used to wrap transactions in a 'with' clause."""

    def __init__(self, connection):
        self.connection = connection
        self.cursor = self.connection.cursor()

    def __enter__(self):
        self.connection.begin()
        return self.cursor

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        if etyp is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        try:
            self.cursor.close()
        except DatabaseError:
            pass

