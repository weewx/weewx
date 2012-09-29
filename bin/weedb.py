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
    
class NoDatabase(StandardError):
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

########################################################
#          TESTING
########################################################

if __name__=="__main__" :
    import argparse
    import configobj
    import sys
    
    import weedb
    import weewx.archive
    import weewx.stats
    
    # Create a command line parser:
    parser = argparse.ArgumentParser()
    
    # Add the various options:
    parser.add_argument("config_path",
                        help="Path to the configuration file (Required)")
    
    # Now we are ready to parse the command line:
    args = parser.parse_args()

    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(args.config_path, file_error=True)
    except IOError:
        print >>sys.stderr, "Unable to open configuration file ", args.config_path
        exit(1)
    except configobj.ConfigObjError:
        print >>sys.stderr, "Error wile parsing configuration file %s" % args.config_path
        exit(1)

    archive_db_dict = config_dict['Databases']['archive_mysql']
    stats_db_dict   = config_dict['Databases']['stats_mysql']
    
    archive = weewx.archive.Archive(archive_db_dict)
    exit()
    # First the archive database:
    try:
        weedb.drop(archive_db_dict)
    except weedb.NoDatabase:
        pass
    archive = weewx.archive.Archive(archive_db_dict)
    exit()
    weewx.archive.config(archive_db_dict)
    archive = weewx.archive.Archive(archive_db_dict)

    # Now the stats database:
    try:
        weedb.drop(stats_db_dict)
    except weedb.NoDatabase:
        pass
    weewx.stats.config(stats_db_dict)
    stats = weewx.stats.StatsDb(stats_db_dict)


    
    for i in range(0,10):
        ts = 1348779300 + i*300
        record = {'dateTime': ts, 'interval':300, 'usUnits':1, 'outTemp': 74.0, 'barometer':29.35}
        archive.addRecord(record)
        
    rec = archive.getRecord(1348779300)
    print rec

    for rec in archive.genBatchRecords(1348779300):
        print rec
        
    print "now nonexistent dates"
    for rec in archive.genBatchRecords(100,200):
        print rec
        
