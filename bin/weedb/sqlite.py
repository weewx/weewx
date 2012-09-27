#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Portable database objects"""

import os.path

def connect(**argv):
    """Factory function, to keep things compatible with DBAPI. 
    
    Arguments are as in Connection object below."""
    return Connection(**argv)

def create(**db_dict):
    """Create the database specified by the db_dict. If it already exists,
    an exception of type DatabaseExists will be thrown."""
    if db_dict['type'].lower() == 'sqlite':
        filename = db_dict['file']
        # Check whether the database file exists:
        if os.path.exists(filename):
            raise DatabaseExists("Database %s already exists" % (filename,))
        else:
            # If it doesn't exist, create the parent directories
            fileDirectory = os.path.dirname(filename)
            if not os.path.exists(fileDirectory):
                os.makedirs(fileDirectory)
            
    elif db_dict['type'].lower() == 'mysql':
        import MySQLdb, _mysql_exceptions
        # Open up a connection w/o specifying the database.
        connect = MySQLdb.connect(host   = db_dict['host'],
                                  user   = db_dict['user'],
                                  passwd = db_dict['password'])
        cursor = connect.cursor()
        # An exception will get thrown if the database already exists.
        try:
            # Now create the database.
            cursor.execute("CREATE DATABASE %s" % (db_dict['database'],))
        except _mysql_exceptions.ProgrammingError:
            # The database already exists. Change the type of exception.
            raise DatabaseExists("Database %s already exists" % (db_dict['database'],))
        finally:
            cursor.close()
    
class Connection(object):
    """A database independent connection object."""
    
    def __init__(self, **db_dict):
        """Initialize an instance of Connection.

        Parameters:
        
        type: The type of database. Presently, either 'sqlite' or 'mysql' (required)
        
        The rest of the parameters depend on the database type. 
        
        if 'type' is sqlite:
        
            file: Path to the sqlite file (required)

            fileroot: An optional path to be prefixed to parameter 'file'. If not given,
            nothing will be prefixed.
            
        if 'type' is mysql:
        
            host: IP or hostname with the mysql database (required)
            user: User name (required)
            password: The password for the username (required)
            database: The database to be used. (required)
            
        If the operation fails, an exception of type weeutil.db.OperationalError will be raised.
        """
        self.dbtype = db_dict['type'].lower()
        
        if self.dbtype == 'sqlite':
            import sqlite3
            if not hasattr(sqlite3.Connection, "__exit__"):
                del sqlite3
                from pysqlite2 import dbapi2 as sqlite3 #@Reimport @UnresolvedImport
                
            file_path = os.path.join(db_dict.get('fileroot',''), db_dict['file'])
            try:
                self.connection = sqlite3.connect(file_path)
            except sqlite3.OperationalError:
                # The Pysqlite driver does not include the database file path.
                # Include it in case it might be useful.
                raise OperationalError("Unable to open database '%s'" % (file_path,))

        elif self.dbtype == 'mysql':
            import MySQLdb
            import _mysql_exceptions
            
            try:
                self.connection = MySQLdb.connect(host   = db_dict['host'],
                                                  user   = db_dict['user'],
                                                  passwd = db_dict['password'],
                                                  db     = db_dict['database'])
            except _mysql_exceptions.OperationalError, e:
                # The MySQL driver does not include the database in the
                # exception information. Tack it on, in case it might be useful.
                raise OperationalError(str(e) + " and database '%s'" % (db_dict['database'],))
        else:
            raise ValueError("Unknown database type %s" % self.dbtype)
        
    def commit(self):
        self.connection.commit()
        
    def close(self):
        try:
            self.connection.close()
            del self.connection
        except:
            pass
        
    def cursor(self):
        return Cursor(self)
    
    def tables(self):
        """Returns a list of tables in the database."""
        
        table_list = list()
        try:
            cursor = self.cursor()
            if self.dbtype == 'sqlite':
                cursor.execute("""SELECT tbl_name FROM sqlite_master WHERE type='table';""")
            elif self.dbtype == 'mysql':
                cursor.execute("""SHOW TABLES;""")
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Extract the table name. Sqlite returns unicode, so always
                # convert to a regular string:
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
            # Find an appropriate SQL statement, depending on the database type
            if self.dbtype == 'sqlite':
                cursor.execute("""PRAGMA table_info(%s);""" % table)
                type_col = 1
            elif self.dbtype == 'mysql':
                import _mysql_exceptions
                # MySQL throws an exception if you try to show the columns of a
                # non-existing table
                try:
                    cursor.execute("""SHOW COLUMNS IN %s;""" % table)
                    type_col = 0
                except _mysql_exceptions.ProgrammingError:
                    # Table does not exist. Return None
                    return None
            while True:
                row = cursor.fetchone()
                if row is None: break
                # Append this column to the list of columns. Where the result appears in the
                # result set depends on the database type.
                column_list.append(str(row[type_col]))
        finally:
            cursor.close()
        # If there are no columns (which means the table did not exist) return None
        return column_list if column_list else None
                
class Cursor(object):
    """A database independent cursor object"""
    
    def __init__(self, connection):
        """Initialize a Cursor.
        
        connection: An instance of weeutil.db.Connection"""
        self.dbtype = connection.dbtype
        self.cursor = connection.connection.cursor()
    
    def execute(self, sql_string, sql_tuple=() ):
        """Execute a SQL statement in a database-independent manner.
        
        sql_string: A SQL statement to be executed. It should use ? as
        a placeholder.
        
        sql_tuple: A tuple with the values to be used in the placeholders."""
        
        # MySQL uses '%s' as placeholders, so replace the ?'s with %s
        if self.dbtype == 'mysql':
            sql_string2 = sql_string.replace('?','%s')
        else:
            sql_string2 = sql_string
            
        self.cursor.execute(sql_string2, sql_tuple)
        
    def fetchone(self):
        return self.cursor.fetchone()

    def close(self):
        try:
            self.cursor.close()
            del self.cursor
        except:
            pass
        
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
            if self.connection.dbtype == 'sqlite':
                self.connection.rollback()
        self.cursor.close()