#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Driver for mysql"""

import MySQLdb
import _mysql_exceptions

import weedb

def connect(**argv):
    """Factory function, to keep things compatible with DBAPI. """
    return Connection(**argv)

def create(database='', host='localhost', **db_dict):
    """Create the database specified by the db_dict. If it already exists,
    an exception of type DatabaseExists will be thrown."""
    # Open up a connection w/o specifying the database.
    connect = MySQLdb.connect(host   = host,
                              user   = db_dict['user'],
                              passwd = db_dict['password'])
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
    
class Connection(weedb.Connection):
    """A database independent connection object."""
    
    def __init__(self, **db_dict):
        """Initialize an instance of Connection.

        Parameters:
        
            host: IP or hostname with the mysql database (required)
            user: User name (required)
            password: The password for the username (required)
            database: The database to be used. (required)
            
        If the operation fails, an exception of type weeutil.db.OperationalError will be raised.
        """
        try:
            connection = MySQLdb.connect(host   = db_dict['host'],
                                              user   = db_dict['user'],
                                              passwd = db_dict['password'],
                                              db     = db_dict['database'])
        except _mysql_exceptions.OperationalError, e:
            # The MySQL driver does not include the database in the
            # exception information. Tack it on, in case it might be useful.
            raise weedb.OperationalError(str(e) + " and database '%s'" % (db_dict['database'],))

        weedb.Connection.__init__(self, connection)
        
    def cursor(self):
        return Cursor(self)
    
    def tables(self):
        """Returns a list of tables in the database."""
        
        table_list = list()
        try:
            cursor = self.cursor()
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
        """Return a list of columns in the specified table. If the table does not exist,
        None is returned."""
        column_list = list()
        try:
            cursor = self.cursor()
            # MySQL throws an exception if you try to show the columns of a
            # non-existing table
            try:
                cursor.execute("""SHOW COLUMNS IN %s;""" % table)
            except _mysql_exceptions.ProgrammingError:
                # Table does not exist. Return None
                return None
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Append this column to the list of columns.
                column_list.append(str(row[0]))
        finally:
            cursor.close()
        # If there are no columns (which means the table did not exist) return None
        return column_list if column_list else None
    
class Cursor(object):
    """A database independent cursor object"""
    
    def __init__(self, connection):
        """Initialize a Cursor.
        
        connection: An instance of weeutil.db.Connection"""
        self.cursor = connection.connection.cursor()
    
    def execute(self, sql_string, sql_tuple=() ):
        """Execute a SQL statement in a database-independent manner.
        
        sql_string: A SQL statement to be executed. It should use ? as
        a placeholder.
        
        sql_tuple: A tuple with the values to be used in the placeholders."""
        
        # MySQL uses '%s' as placeholders, so replace the ?'s with %s
        mysql_string = sql_string.replace('?','%s')
            
        self.cursor.execute(mysql_string, sql_tuple)
        return self
        
    def fetchone(self):
        return self.cursor.fetchone()

    def close(self):
        try:
            self.cursor.close()
            del self.cursor
        except:
            pass
        
    def __iter__(self):
        return self
    
    def next(self):
        result = self.fetchone()
        if result is None:
            raise StopIteration
        return result

