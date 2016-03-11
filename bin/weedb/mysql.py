#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Driver for the MySQL database"""

import decimal

import MySQLdb
import _mysql_exceptions

from weeutil.weeutil import to_bool
import weedb

DEFAULT_ENGINE = 'INNODB'

def guard(fn):
    """Decorator function that converts MySQL exceptions into weedb exceptions."""

    def guarded_fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _mysql_exceptions.IntegrityError, e:
            raise weedb.IntegrityError(e)
        except _mysql_exceptions.ProgrammingError, e:
            raise weedb.ProgrammingError(e)
        except _mysql_exceptions.OperationalError, e:
            raise weedb.OperationalError(e)

    return guarded_fn


def connect(host='localhost', user='', password='', database_name='', 
            driver='', port=3306, engine=DEFAULT_ENGINE, **kwargs):  # @UnusedVariable
    """Connect to the specified database"""
    return Connection(host=host, user=user, password=password, 
                      database_name=database_name, port=int(port), engine=engine, **kwargs)


def create(host='localhost', user='', password='', database_name='', 
           driver='', port=3306, engine=DEFAULT_ENGINE, **kwargs):  # @UnusedVariable
    """Create the specified database. If it already exists,
    an exception of type weedb.DatabaseExists will be thrown."""
    # Open up a connection w/o specifying the database.
    try:
        connect = MySQLdb.connect(host=host,
                                  user=user,
                                  passwd=password, 
                                  port=int(port), **kwargs)
        set_engine(connect, engine)
        cursor = connect.cursor()
        # An exception will get thrown if the database already exists.
        try:
            # Now create the database.
            cursor.execute("CREATE DATABASE %s" % (database_name,))
        except _mysql_exceptions.ProgrammingError:
            # The database already exists. Change the type of exception.
            raise weedb.DatabaseExists("Database %s already exists" % (database_name,))
        finally:
            cursor.close()
    except _mysql_exceptions.OperationalError, e:
        raise weedb.OperationalError(e)


def drop(host='localhost', user='', password='', database_name='', 
         driver='', port=3306, engine=DEFAULT_ENGINE, **kwargs):  # @UnusedVariable
    """Drop (delete) the specified database."""
    # Open up a connection
    try:
        connect = MySQLdb.connect(host=host,
                                  user=user,
                                  passwd=password, 
                                  port=int(port), **kwargs)
        cursor = connect.cursor()
        try:
            cursor.execute("DROP DATABASE %s" % database_name)
        except _mysql_exceptions.OperationalError:
            raise weedb.NoDatabase("""Attempt to drop non-existent database %s""" % (database_name,))
        finally:
            cursor.close()
    except _mysql_exceptions.OperationalError, e:
        raise weedb.OperationalError(e)


class Connection(weedb.Connection):
    """A wrapper around a MySQL connection object."""

    def __init__(self, host='localhost', user='', password='', database_name='', port=3306, engine=DEFAULT_ENGINE, **kwargs):
        """Initialize an instance of Connection.

        Parameters:
        
            host: IP or hostname with the mysql database (required)
            user: User name (required)
            password: The password for the username (required)
            database_name: The database to be used. (required)
            port: Its port number (optional; default is 3306)
            engine: The MySQL database engine to use (optional; default is 'INNODB')
            kwargs:   Any extra arguments you may wish to pass on to MySQL (optional)
            
        If the operation fails, an exception of type weedb.OperationalError will be raised.
        """
        try:
            connection = MySQLdb.connect(host=host, user=user, passwd=password, db=database_name, port=int(port), **kwargs)
        except _mysql_exceptions.OperationalError, e:
            # The MySQL driver does not include the database in the
            # exception information. Tack it on, in case it might be useful.
            raise weedb.OperationalError(str(e) + " while opening database '%s'" % (database_name,))

        weedb.Connection.__init__(self, connection, database_name, 'mysql')

        # Set the storage engine to be used
        set_engine(self.connection, engine)

        # Allowing threads other than the main thread to see any transactions
        # seems to require an isolation level of READ UNCOMMITTED.
        self.connection.query("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")

    def cursor(self):
        """Return a cursor object."""
        # The implementation of the MySQLdb cursor is lame enough that we are
        # obliged to include a wrapper around it:
        return Cursor(self)

    @guard
    def tables(self):
        """Returns a list of tables in the database."""

        table_list = list()
        # Get a cursor directly from MySQL
        cursor = self.connection.cursor()
        try:
            cursor.execute("""SHOW TABLES;""")
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Extract the table name. In case it's in unicode, convert to a regular string.
                table_list.append(str(row[0]))
        finally:
            cursor.close()
        return table_list

    @guard
    def genSchemaOf(self, table):
        """Return a summary of the schema of the specified table.
        
        If the table does not exist, an exception of type weedb.OperationalError is raised."""

        # Get a cursor directly from MySQL:
        cursor = self.connection.cursor()
        try:
            # If the table does not exist, this will raise a MySQL ProgrammingError exception,
            # which gets converted to a weedb.OperationalError exception by the guard decorator
            cursor.execute("""SHOW COLUMNS IN %s;""" % table)
            irow = 0
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Append this column to the list of columns.
                colname = str(row[0])
                if row[1].upper() == 'DOUBLE':
                    coltype = 'REAL'
                elif row[1].upper().startswith('INT'):
                    coltype = 'INTEGER'
                elif row[1].upper().startswith('CHAR'):
                    coltype = 'STR'
                else:
                    coltype = str(row[1]).upper()
                is_primary = True if row[3] == 'PRI' else False
                can_be_null = False if row[2]=='' else to_bool(row[2])
                yield (irow, colname, coltype, can_be_null, row[4], is_primary)
                irow += 1
        finally:
            cursor.close()

    @guard
    def columnsOf(self, table):
        """Return a list of columns in the specified table. 
        
        If the table does not exist, an exception of type weedb.OperationalError is raised."""
        column_list = [row[1] for row in self.genSchemaOf(table)]
        return column_list

    @guard
    def get_variable(self, var_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute("SHOW VARIABLES LIKE '%s';" % var_name)
            row = cursor.fetchone()
            # This is actually a 2-way tuple (variable-name, variable-value),
            # or None, if the variable does not exist.
            return row
        finally:
            cursor.close()

    @guard
    def begin(self):
        """Begin a transaction."""
        self.connection.query("START TRANSACTION")

    @guard
    def commit(self):
        self.connection.commit()

    @guard
    def rollback(self):
        self.connection.rollback()

class Cursor(object):
    """A wrapper around the MySQLdb cursor object"""

    def __init__(self, connection):
        """Initialize a Cursor from a connection.
        
        connection: An instance of db.mysql.Connection"""

        # Get the MySQLdb cursor and store it internally:
        self.cursor = connection.connection.cursor()

    @guard
    def execute(self, sql_string, sql_tuple=()):
        """Execute a SQL statement on the MySQL server.
        
        sql_string: A SQL statement to be executed. It should use ? as
        a placeholder.
        
        sql_tuple: A tuple with the values to be used in the placeholders."""

        # MySQL uses '%s' as placeholders, so replace the ?'s with %s
        mysql_string = sql_string.replace('?', '%s')

        # Convert sql_tuple to a plain old tuple, just in case it actually
        # derives from tuple, but overrides the string conversion (as is the
        # case with a TimeSpan object):
        self.cursor.execute(mysql_string, tuple(sql_tuple))

        return self

    def fetchone(self):
        # Get a result from the MySQL cursor, then run it through the massage
        # filter below
        return massage(self.cursor.fetchone())

    def close(self):
        try:
            self.cursor.close()
            del self.cursor
        except:
            pass

    #
    # Supplying functions __iter__ and next allows the cursor to be used as an iterator.
    #
    def __iter__(self):
        return self

    def next(self):
        result = self.fetchone()
        if result is None:
            raise StopIteration
        return result


#
# This is a utility function for converting a result set that might contain
# longs or decimal.Decimals (which MySQLdb uses) to something containing just ints.
#
def massage(seq):
    # Return the massaged sequence if it exists, otherwise, return None
    if seq is not None:
        return [int(i) if isinstance(i, long) or isinstance(i, decimal.Decimal) else i for i in seq]

def set_engine(connect, engine):
    """Set the default MySQL storage engine."""
    if connect._server_version >= (5, 5):
        connect.query("SET default_storage_engine=%s" % engine)
    else:
        connect.query("SET storage_engine=%s;" % engine)
