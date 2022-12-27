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


class Transaction(object):
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


def get_database_dict_from_config(config_dict, database):
    """Convenience function that given a configuration dictionary and a database name,
     returns a database dictionary that can be used to open the database using Manager.open().

    Args:

        config_dict (dict): The configuration dictionary.
        database (str): The database whose database dict is to be retrieved
            (example: 'archive_sqlite')

    Returns:
        dict: A database dictionary, with everything needed to pass on to a Manager or weedb in
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
    ...     SQLITE_ROOT = archive
    ... [Databases]
    ...     [[archive_sqlite]]
    ...        database_name = weewx.sdb
    ...        database_type = SQLite'''
    >>> config_dict = configobj.ConfigObj(StringIO(config_snippet))
    >>> database_dict = get_database_dict_from_config(config_dict, 'archive_sqlite')
    >>> keys = sorted(database_dict.keys())
    >>> for k in keys:
    ...     print("%15s: %12s" % (k, database_dict[k]))
      database_name:    weewx.sdb
            db_path: /home/weewx/archive/weewx.sdb
             driver: weedb.sqlite
    """
    import weewx
    import weeutil.config
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

    # Import the driver and see if it wants to modify the database dictionary
    db_mod = importlib.import_module(database_dict['driver'])
    if hasattr(db_mod, 'modify_config'):
        database_dict = getattr(db_mod, 'modify_config')(config_dict, database_dict)

    return database_dict


if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
