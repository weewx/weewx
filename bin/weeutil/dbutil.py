#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"Functions for querying sqlite databases about schema attributes"

from __future__ import with_statement

import re

from pysqlite2 import dbapi2 as sqlite3

# Regular expression that matches everything within the set
# of parenthesis which marks the column definition:
column_def_re = re.compile(r"\(.*\)",re.DOTALL)

def schema(database):
    """Returns a dictionary with the schema definition.
    
    database: The sqlite3 database to be queried.
    
    returns: A dictionary. Keys will be the table names in the database,
             values a list of column definitions. A column definition will
             be something like "barometer INTEGER" or 
             "dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY".
    """
    result = {}
    with sqlite3.connect(database) as _connection:

        for _row in _connection.execute("""SELECT tbl_name, sql FROM sqlite_master where type='table';"""):
    
            if None in _row:
                continue
            # Separate out the column definitions (which are enclosed
            # by parenthesis):
            column_def = column_def_re.search(_row[1]).group()
            
            # Now split the definitions by their separating columns:
            column_list = column_def[1:-1].split(',')
            # Clean up the results by getting rid of whitespace:
            column_list_clean = [s.strip() for s in column_list]
            # Add the results to the dictionary:
            result[_row[0]] = column_list_clean
    return result
            

def column_dict(schema_dict):
    """Extracts the column names out of a schema dictionary
    
    schema_dict: A schema dictionary as returned by 
    function schema() above.
    
    returns: A dictionary. Keys will be the table name, values a list
    of strings with the column names. """
    
    results = {}
    for table_name in schema_dict:
        results[table_name] = [s.split(' ')[0] for s in schema_dict[table_name]]
        
    return results

                   
        
if __name__ == '__main__':
    archiveFile = '/home/weewx/archive/stats.sdb'
    
    schema_dict = schema(archiveFile)
    print schema_dict

    columns = column_dict(schema_dict)
    
    print columns
    