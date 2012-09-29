#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

import sys

class OperationalError(StandardError):
    """Unable to open a database."""
    
class DatabaseExists(StandardError):
    """Attempt to create a database that already exists"""

def create(driver='', **db_dict):
    __import__(driver)
    driver_mod = sys.modules[driver]
    driver_mod.create(**db_dict)

def connect(driver='', **db_dict):
    __import__(driver)
    driver_mod = sys.modules[driver]
    return driver_mod.connect(**db_dict)

def drop(driver='', **db_dict):
    __import__(driver)
    driver_mod = sys.modules[driver]
    driver_mod.drop(**db_dict)

class Connection(object):

    def __init__(self, connection):
        self.connection = connection
        
    def cursor(self):
        """Returns an appropriate database cursor."""
        raise NotImplementedError
        
    def tables(self):
        """Returns a list of the tables in the database.
        
        Should raise exception weedb.OperationalError if the database does not exist.
        Returns an empty list if the database exists, but there is nothing in it."""
        raise NotImplementedError
    
    def columnsOf(self, table):
        """Returns a list of the column names in the specified table."""
        raise NotImplementedError
            
    def commit(self):
        self.connection.commit()
        
    def rollback(self):
        self.connection.rollback()
        
    def close(self):
        try:
            self.connection.close()
        except:
            pass

    def execute(self, sql_string, sql_tuple=() ):
        """Execute a sql statement. This version does not return a cursor,
        so it can only be used for statements that do not return a result set."""
        
        try:
            cursor = self.cursor()
            cursor.execute(sql_string, sql_tuple)
        except:
            cursor.close()

class Transaction(object):
    
    def __init__(self, connection):
        self.connection = connection
        self.cursor = self.connection.cursor()
        
    def __enter__(self):
        return self.cursor
    
    def __exit__(self, etyp, einst, etb):
        if etyp is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        try:
            self.cursor.close()
        except:
            pass
        