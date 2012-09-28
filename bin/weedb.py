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

class Database(object):
    
    def __init__(self, driver='', **db_dict):
        __import__(driver)
        self.db = sys.modules[driver]
        self.db_dict = db_dict
        
    def create(self):
        self.db.create(**self.db_dict)
        
    def connect(self):
        return self.db.connect(**self.db_dict)
        
class Connection(object):

    def __init__(self, connection):
        self.connection = connection
        
    def cursor(self):
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
        