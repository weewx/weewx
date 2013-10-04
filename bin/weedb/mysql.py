#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Driver for the MySQL database"""

import decimal

import MySQLdb
import _mysql_exceptions

import weedb

def connect(host='localhost', user='', password='', database='', driver='', **kwargs):
    """Connect to the specified database"""
    return Connection(host=host, user=user, password=password, database=database, **kwargs)

def create(host='localhost', user='', password='', database='', driver='', **kwargs):
    """Create the specified database. If it already exists,
    an exception of type weedb.DatabaseExists will be thrown."""
    # Open up a connection w/o specifying the database.
    try:
        connect = MySQLdb.connect(host   = host,
                                  user   = user,
                                  passwd = password, **kwargs)
        cursor = connect.cursor()
        # An exception will get thrown if the database already exists.
        try:
            # Now create the database.
            cursor.execute("CREATE DATABASE %s" % (database,))
        except _mysql_exceptions.ProgrammingError:
            # The database already exists. Change the type of exception.
            raise weedb.DatabaseExists("Database %s already exists" % (database,))
        finally:
            cursor.close()
    except _mysql_exceptions.OperationalError, e:
        raise weedb.OperationalError(e)
    
def drop(host='localhost', user='', password='', database='', driver='', **kwargs):
    """Drop (delete) the specified database."""
    # Open up a connection
    try:
        connect = MySQLdb.connect(host   = host,
                                  user   = user,
                                  passwd = password, **kwargs)
        cursor = connect.cursor()
        try:
            cursor.execute("DROP DATABASE %s" % database)
        except _mysql_exceptions.OperationalError:
            raise weedb.NoDatabase("""Attempt to drop non-existent database %s""" % (database,))
        finally:
            cursor.close()
    except _mysql_exceptions.OperationalError, e:
        raise weedb.OperationalError(e)
    
class Connection(weedb.Connection):
    """A wrapper around a MySQL connection object."""
    
    def __init__(self, host='localhost', user='', password='', database='', **kwargs):
        """Initialize an instance of Connection.

        Parameters:
        
            host: IP or hostname with the mysql database (required)
            user: User name (required)
            password: The password for the username (required)
            database: The database to be used. (required)
            kwargs:   Any extra arguments you may wish to pass on to MySQL (optional)
            
        If the operation fails, an exception of type weedb.OperationalError will be raised.
        """
        try:
            connection = MySQLdb.connect(host=host, user=user, passwd=password, db=database, **kwargs)
        except _mysql_exceptions.OperationalError, e:
            # The MySQL driver does not include the database in the
            # exception information. Tack it on, in case it might be useful.
            raise weedb.OperationalError(str(e) + " while opening database '%s'" % (database,))

        weedb.Connection.__init__(self, connection, database, 'mysql')
        
        # Allowing threads other than the main thread to see any transactions
        # seems to require an isolation level of READ UNCOMMITTED.
        self.connection.query("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED") 
        
    def cursor(self):
        """Return a cursor object."""
        # The implementation of the MySQLdb cursor is lame enough that we are
        # obliged to include a wrapper around it:
        return Cursor(self)
    
    def tables(self):
        """Returns a list of tables in the database."""
        
        table_list = list()
        try:
            # Get a cursor directly from MySQL
            cursor = self.connection.cursor()
            cursor.execute("""SHOW TABLES;""")
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Extract the table name. In case it's in unicode, convert to a regular string.
                table_list.append(str(row[0]))
        finally:
            cursor.close()
        return table_list
                
    def columnsOf(self, table):
        """Return a list of columns in the specified table. 
        
        If the table does not exist, an exception of type weedb.OperationalError is raised."""
        column_list = list()
        try:
            # Get a cursor directly from MySQL:
            cursor = self.connection.cursor()
            # MySQL throws an exception if you try to show the columns of a
            # non-existing table
            try:
                cursor.execute("""SHOW COLUMNS IN %s;""" % table)
            except _mysql_exceptions.ProgrammingError, e:
                # Table does not exist. Change the exception type:
                raise weedb.OperationalError(e)
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Append this column to the list of columns.
                column_list.append(str(row[0]))
        finally:
            cursor.close()

        return column_list
    
    def begin(self):
        """Begin a transaction."""
        self.connection.query("START TRANSACTION")
    
class Cursor(object):
    """A wrapper around the MySQLdb cursor object"""
    
    def __init__(self, connection):
        """Initialize a Cursor from a connection.
        
        connection: An instance of db.mysql.Connection"""
        
        # Get the MySQLdb cursor and store it internally:
        self.cursor = connection.connection.cursor()
    
    def execute(self, sql_string, sql_tuple=() ):
        """Execute a SQL statement on the MySQL server.
        
        sql_string: A SQL statement to be executed. It should use ? as
        a placeholder.
        
        sql_tuple: A tuple with the values to be used in the placeholders."""
        
        # MySQL uses '%s' as placeholders, so replace the ?'s with %s
        mysql_string = sql_string.replace('?','%s')
            
        try:
            # Convert sql_tuple to a plain old tuple, just in case it actually
            # derives from tuple, but overrides the string conversion (as is the
            # case with a TimeSpan object):
            self.cursor.execute(mysql_string, tuple(sql_tuple))
        except (_mysql_exceptions.OperationalError, _mysql_exceptions.ProgrammingError), e:
            raise weedb.OperationalError(e)
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
        return [int(i) if isinstance(i, long) or isinstance(i,decimal.Decimal) else i for i in seq]
