#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Driver for sqlite"""

import os.path

# Import sqlite3. If it does not support the 'with' statement, then
# import pysqlite2, which might...
import sqlite3
if not hasattr(sqlite3.Connection, "__exit__"):
    del sqlite3
    from pysqlite2 import dbapi2 as sqlite3 #@Reimport @UnresolvedImport

import weedb

def connect(**argv):
    """Factory function, to keep things compatible with DBAPI. """
    return Connection(**argv)

def create(database='', root=''):
    """Create the database specified by the db_dict. If it already exists,
    an exception of type DatabaseExists will be thrown."""
    filename = os.path.join(root, database)
    # Check whether the database file exists:
    if os.path.exists(filename):
        raise weedb.DatabaseExists("Database %s already exists" % (filename,))
    else:
        # If it doesn't exist, create the parent directories
        fileDirectory = os.path.dirname(filename)
        if not os.path.exists(fileDirectory):
            os.makedirs(fileDirectory)

class Connection(object):
    """A database independent connection object."""
    
    def __init__(self, database='', root=''):
        """Initialize an instance of Connection.

        Parameters:
        
            file: Path to the sqlite file (required)

            fileroot: An optional path to be prefixed to parameter 'file'. If not given,
            nothing will be prefixed.
            
        If the operation fails, an exception of type weeutil.db.OperationalError will be raised.
        """
                
        file_path = os.path.join(root, database)
        try:
            self.connection = sqlite3.connect(file_path)
        except sqlite3.OperationalError:
            # The Pysqlite driver does not include the database file path.
            # Include it in case it might be useful.
            raise weedb.OperationalError("Unable to open database '%s'" % (file_path,))

    def commit(self):
        self.connection.commit()
        
    def rollback(self):
        self.connection.rollback()
        
    def close(self):
        try:
            self.connection.close()
        except:
            pass
        
    def cursor(self):
        return self.connection.cursor()
    
    def tables(self):
        """Returns a list of tables in the database."""
        
        table_list = list()
        for row in self.connection.execute("""SELECT tbl_name FROM sqlite_master WHERE type='table';"""):
            # Extract the table name. Sqlite returns unicode, so always
            # convert to a regular string:
            table_list.append(str(row[0]))
        return table_list
                
    def columnsOf(self, table):
        """Return a list of columns in the specified table. If the table does not exist,
        None is returned."""
        column_list = list()
        for row in self.connection.execute("""PRAGMA table_info(%s);""" % table):
            # Append this column to the list of columns. 
            column_list.append(str(row[1]))
        # If there are no columns (which means the table did not exist) return None
        return column_list if column_list else None
                
