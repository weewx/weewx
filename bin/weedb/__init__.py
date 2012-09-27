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

class OperationalError(StandardError):
    """Unable to open a database."""
    
class DatabaseExists(StandardError):
    """Attempt to create a database that already exists"""


class Database(object):
    
    def __init__(self, driver, **db_dict):
        __import__(driver)