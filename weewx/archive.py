#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Classes and functions for interfacing with a weewx sqlite3 archive.

Note that this archive uses a schema that is compatible with a wview V5.X.X 
(see http://www.wviewweather.com) sqlite3 database.

"""
from __future__ import with_statement
import time
import datetime
import syslog
import os
import os.path
import math
from pysqlite2 import dbapi2 as sqlite3
    
import weewx
import weeutil.weeutil

# This is a tuple containing the schema of the archive database. 
# Although a type may be listed here, it may not necessarily be supported by a weather station
sqltypes = (('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
            ('usUnits',              'INTEGER NOT NULL'),
            ('interval',             'INTEGER NOT NULL'),
            ('barometer',            'REAL'),
            ('pressure',             'REAL'),
            ('altimeter',            'REAL'),
            ('inTemp',               'REAL'),
            ('outTemp',              'REAL'),
            ('inHumidity',           'REAL'),
            ('outHumidity',          'REAL'),
            ('windSpeed',            'REAL'),
            ('windDir',              'REAL'),
            ('windGust',             'REAL'),
            ('windGustDir',          'REAL'),
            ('rainRate',             'REAL'),
            ('rain',                 'REAL'),
            ('dewpoint',             'REAL'),
            ('windchill',            'REAL'),
            ('heatindex',            'REAL'),
            ('ET',                   'REAL'),
            ('radiation',            'REAL'),
            ('UV',                   'REAL'),
            ('extraTemp1',           'REAL'),
            ('extraTemp2',           'REAL'),
            ('extraTemp3',           'REAL'),
            ('soilTemp1',            'REAL'),
            ('soilTemp2',            'REAL'),
            ('soilTemp3',            'REAL'),
            ('soilTemp4',            'REAL'),
            ('leafTemp1',            'REAL'),
            ('leafTemp2',            'REAL'),
            ('extraHumid1',          'REAL'),
            ('extraHumid2',          'REAL'),
            ('soilMoist1',           'REAL'),
            ('soilMoist2',           'REAL'),
            ('soilMoist3',           'REAL'),
            ('soilMoist4',           'REAL'),
            ('leafWet1',             'REAL'),
            ('leafWet2',             'REAL'),
            ('rxCheckPercent',       'REAL'),
            ('txBatteryStatus',      'REAL'),
            ('consBatteryVoltage',   'REAL'),
            ('hail',                 'REAL'),
            ('hailRate',             'REAL'),
            ('heatingTemp',          'REAL'),
            ('heatingVoltage',       'REAL'),
            ('supplyVoltage',        'REAL'),
            ('referenceVoltage',     'REAL'),
            ('windBatteryStatus',    'REAL'),
            ('rainBatteryStatus',    'REAL'),
            ('outTempBatteryStatus', 'REAL'),
            ('inTempBatteryStatus',  'REAL'))

# This is just a list of the first value in each tuple above (i.e., the SQL keys):
sqlkeys = [_tuple[0] for _tuple in sqltypes]

# This is a SQL insert statement to be used to add a record. It will have the correct
# number of placeholder question marks, separated by commas:
sql_insert_stmt = "INSERT INTO archive VALUES ( %s );" % ','.join('?'*len(sqlkeys))



        
class Archive(object):
    """Manages a sqlite archive file. Offers a number of convenient member functions
    for managing the archive file. These functions encapsulate whatever sql statements
    are needed.
    
    """
    
    def __init__(self, archiveFile):
        """Initialize an object of type weewx.Archive. 
        
        archiveFile: The path name to the sqlite3 archive file.
        
        """
        self.archiveFile = archiveFile

    def lastGoodStamp(self):
        """Retrieves the epoch time of the last good archive record.
        
        returns: Time of the last good archive record as an epoch time, or
        None if there are no records."""
        with sqlite3.connect(self.archiveFile) as _connection:
            _row = _connection.execute("SELECT MAX(dateTime) FROM archive").fetchone()
            _ts = _row[0]
        return _ts
    
    def firstGoodStamp(self):
        """Retrieves earliest timestamp in the archive.
        
        returns: Time of the first good archive record as an epoch time, or
        None if there are no records."""
        with sqlite3.connect(self.archiveFile) as _connection:
            _row = _connection.execute("SELECT MIN(dateTime) FROM archive").fetchone()
            _ts = _row[0]
        return _ts

    def addRecord(self, record):
        """Commit an archive record to the sqlite3 database.
        
        This function commits the record after adding it to the DB. 
        
        record: A data record. It must look like a dictionary, where the keys
        are the SQL types and the values are the values to be stored in the
        database. 
        
        """
        global sql_insert_stmt
        global sqlkeys
 
        # This will be a list of the values, in the order of the sqlkeys.
        # A value will be replaced with None if it did not exist in the record
        _vallist = [record.get(_key) for _key in sqlkeys]

        with sqlite3.connect(self.archiveFile) as _connection:
            _connection.execute(sql_insert_stmt, _vallist)
        
        syslog.syslog(syslog.LOG_NOTICE, "Archive: added archive record %s" % weeutil.weeutil.timestamp_to_string(_vallist[0]))


    def genBatchRecords(self, startstamp, stopstamp):
        """Generator function that yields ArchiveRecords within a time interval.
        
        startstamp: Exclusive start of the interval in epoch time. If 'None', then
        start at earliest archive record.
        
        stopstamp: Inclusive end of the interval in epoch time. If 'None', then
        end at last archive record.
        
        yields: instances of ArchiveRecord between the two times. """
        _connection = sqlite3.connect(self.archiveFile)
        _connection.row_factory = sqlite3.Row
        _cursor=_connection.cursor()
        try:
            if startstamp is None:
                if stopstamp is None:
                    _cursor.execute("SELECT * FROM archive")
                else:
                    _cursor.execute("SELECT * from archive where dateTime <= ?", (stopstamp,))
            else:
                if stopstamp is None:
                    _cursor.execute("SELECT * from archive where dateTime > ?", (startstamp,))
                else:
                    _cursor.execute("SELECT * FROM archive WHERE dateTime > ? AND dateTime <= ?", (startstamp, stopstamp))
            
            for _row in _cursor :
                yield ArchiveRecord(_row)
        finally:
            _cursor.close()
            _connection.close()

    def getRecord(self, timestamp):
        """Get a single instance of ArchiveRecord with a given epoch time stamp.
        
        timestamp: The epoch time of the desired record.
        
        returns: an instance of weewx.archive.ArchiveRecord"""
        with sqlite3.connect(self.archiveFile) as _connection:
            _connection.row_factory = sqlite3.Row
            _cursor = _connection.execute("SELECT * FROM archive WHERE dateTime=?;", (timestamp,))
            _row = _cursor.fetchone()
            return ArchiveRecord(_row)
    
    def getSql(self, sql, *sqlargs):
        """Executes an arbitrary SQL statement on the database.
        
        sql: The SQL statement
        
        sqlargs: The arguments for the SQL statement
        
        returns: an instance of sqlite3.Row
        """
        with sqlite3.connect(self.archiveFile) as _connection:
            _connection.row_factory = sqlite3.Row
            _cursor = _connection.execute(sql, sqlargs)
            _row = _cursor.fetchone()
            return _row

    def genSql(self, sql, *sqlargs):
        """Generator function that executes an arbitrary SQL statement on the database."""
        _connection = sqlite3.connect(self.archiveFile)
        _connection.row_factory = sqlite3.Row
        _cursor=_connection.cursor()
        try:
            _cursor.execute(sql, sqlargs)
            for _row in _cursor:
                yield _row
        finally:
            _cursor.close()
            _connection.close()

    def getSqlVectors(self, sql_type, startstamp, stopstamp, aggregate_interval = None, aggregate_type = None):
        """Get time and (possibly aggregated) data vectors within a time interval. 
        
        The return value is a 2-way tuple. The first member is a vector of time
        values, the second member a vector of data values for sql type sql_type. 
        
        An example of a returned value is: (time_vec, outTempVec). 
        
        If aggregation is desired (archive_interval is not None), then each element represents
        a time interval exclusive on the left, inclusive on the right. The time
        elements will all fall on the same local time boundary as startstamp. 
        For example, if startstamp is 8-Mar-2009 18:00
        and archive_interval is 10800 (3 hours), then the returned time vector will be
        (shown in local times):
        
        8-Mar-2009 21:00
        9-Mar-2009 00:00
        9-Mar-2009 03:00
        9-Mar-2009 06:00 etc.
        
        Note that DST happens at 02:00 on 9-Mar, so the actual time deltas between the
        elements is 3 hours between times #1 and #2, but only 2 hours between #2 and #3.
        
        NB: there is an algorithmic assumption here that all archived
        time intervals are the same length. That is, the archive interval cannot change.
        
        sql_type: The SQL type to be retrieved (e.g., 'outTemp') 
        
        startstamp: If aggregation_interval is None, then data with timestamps greater
        than or equal to this value will be returned. If aggregation_interval is not
        None, then the start of the first interval will be greater than (exclusive of) this
        value. 
        
        stopstamp: Records with time stamp less than or equal to this will be retrieved.
        If interval is not None, then the last interval will include this value.
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Default: None (no aggregation)
        
        aggregate_type: None if no aggregation is desired, otherwise the type of
        aggregation (e.g., 'sum', 'avg', etc.)  Required if aggregate_interval
        is non-None. Default: None (no aggregation)

        returns: a 2-way tuple. First element is the time vector, second element
        is the data vector
        """

        _connection = sqlite3.connect(self.archiveFile)
        _cursor=_connection.cursor()
        time_vec = list()
        data_vec = list()

        if aggregate_interval :
            if not aggregate_type:
                raise weewx.ViolatedPrecondition, "Aggregation type missing"
            sql_str = 'SELECT dateTime, %s(%s) FROM archive WHERE dateTime > ? AND dateTime <= ?' % (aggregate_type, sql_type)
            for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
                _cursor.execute(sql_str, stamp)
                _rec = _cursor.fetchone()
                # Don't accumulate any results where there wasn't a record
                # (signified by sqlite3 by a null key)
                if _rec:
                    if _rec[0] is not None:
                        time_vec.append(_rec[0])
                        data_vec.append(_rec[1])
        else:
            sql_str = 'SELECT dateTime, %s FROM archive WHERE dateTime >= ? AND dateTime <= ?' % sql_type
            _cursor.execute(sql_str, (startstamp, stopstamp))
            for _rec in _cursor:
                assert(_rec[0])
                time_vec.append(_rec[0])
                data_vec.append(_rec[1])

        _cursor.close()
        _connection.close()

        return (time_vec, data_vec)

    def getSqlVectorsExtended(self, ext_type, startstamp, stopstamp, aggregate_interval = None, aggregate_type = None):
        """Get time and (possibly aggregated) data vectors within a time interval.
        
        This function is very similar to getSqlVectors, except that for special types
        'windvec' and 'windgustvec' it returns wind data broken down into 
        its x- and y-components.
        
        sql_type: The SQL type to be retrieved (e.g., 'outTemp', or 'windvec'). 
        If this type is the special types 'windvec', or 'windgustvec', then what
        will be returned is a vector of complex numbers. 
        
        startstamp: If aggregation_interval is None, then data with timestamps greater
        than or equal to this value will be returned. If aggregation_interval is not
        None, then the start of the first interval will be greater than (exclusive of) this
        value. 
        
        stopstamp: Records with time stamp less than or equal to this will be retrieved.
        If interval is not None, then the last interval will include this value.
        
        aggregate_interval: None if no aggregation is desired, otherwise
        this is the time interval over which a result will be aggregated.
        Default: None (no aggregation)
        
        aggregate_type: None if no aggregation is desired, otherwise the type of
        aggregation (e.g., 'sum', 'avg', etc.)  Required if aggregate_interval
        is non-None. Default: None (no aggregation)

        returns: a 2-way tuple. First element is the time vector, second element
        is the data vector. If sql_type is 'windvec' or 'windgustvec', the data
        vector will be a vector of types complex. The real part is the x-component
        of the wind, the imaginary part the y-component.
        """

        windvec_types = {'windvec'     : ('windSpeed, windDir'),
                         'windgustvec' : ('windGust,  windGustDir')}
        
        # Check to see if the requested type is 'windvec' or 'windgustvec'
        if ext_type in windvec_types:
            # It is. Prepare the lists that will hold the final results.
            time_vec = list()
            data_vec = list()
            # This SQL select string will select the proper wind types
            sql_str = 'SELECT dateTime, %s FROM archive WHERE dateTime > ? AND dateTime <= ?' % windvec_types[ext_type]
            _connection = sqlite3.connect(self.archiveFile)
            _cursor=_connection.cursor()
    
            # Is aggregation requested?
            if aggregate_interval :
                # Aggregation is requested.
                # The aggregation should happen over the x- and y-components. Because they do
                # not appear in the database (only the magnitude and direction do) we cannot
                # do the aggregation in the SQL statement. We'll have to do it in Python.
                # Do we know how to do it?
                if aggregate_type not in ('sum', 'count', 'avg'):
                    raise weewx.ViolatedPrecondition, "Aggregation type missing or unknown"
                
                # Go through each aggregation interval, calculating the aggregation.
                for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
                    xsum = ysum = 0.0
                    count = 0
                    last_time = None
                    _cursor.execute(sql_str, stamp)
                    for _rec in _cursor:
                        (mag, dir) = _rec[1:3]
                        # We need both magnitude and direction to break it down into
                        # x and y components
                        if mag is not None and dir is not None:
                            xsum += mag * math.cos(math.radians(90.0 - dir))
                            ysum += mag * math.sin(math.radians(90.0 - dir))
                            count += 1
                            last_time = _rec[0]
                    # We've gone through the whole interval. Was their any good data?
                    if count:
                        # Record the time of the last good data point:
                        time_vec.append(last_time)
                        # Form the requested aggregation:
                        if aggregate_type == 'sum':
                            data_vec.append(complex(xsum, ysum))
                        elif aggregate_type == 'count':
                            data_vec.append(count)
                        else:
                            # Must be 'avg'
                            data_vec.append(complex(xsum/count, ysum/count))
            else:
                # No aggregation desired. It's a lot simpler. Go get the
                # data in the requested time period
                _cursor.execute(sql_str, (startstamp, stopstamp))
                for _rec in _cursor:
                    # Record the time:
                    time_vec.append(_rec[0])
                    # Break the mag and dir down into x- and y-components.
                    (mag, dir) = _rec[1:3]
                    if mag is None or dir is None:
                        data_vec.append(None)
                    else:
                        x = mag * math.cos(math.radians(90.0 - dir))
                        y = mag * math.sin(math.radians(90.0 - dir))
                        if weewx.debug:
                            # There seem to be some little rounding errors that are driving
                            # my debugging crazy. Zero them out
                            if abs(x) < 1.0e-6 : x = 0.0
                            if abs(y) < 1.0e-6 : y = 0.0
                        data_vec.append(complex(x,y))
            _cursor.close()
            _connection.close()
            return (time_vec, data_vec)

        else:
            # The type is other than the extended wind types. Use the regular version:
            return self.getSqlVectors(ext_type, startstamp, stopstamp, aggregate_interval, aggregate_type)


    def config(self):
        """Configure a database for use with weewx. This will create the initial schema
        if necessary.
        
        """
    
        # Check whether the database exists:
        if os.path.exists(self.archiveFile):
            syslog.syslog(syslog.LOG_INFO, "archive: archive database %s already exists." % self.archiveFile)
        else:
            # If it doesn't exist, create the parent directories
            archiveDirectory = os.path.dirname(self.archiveFile)
            if not os.path.exists(archiveDirectory):
                syslog.syslog(syslog.LOG_NOTICE, "archive: making archive directory %s." % archiveDirectory)
                os.makedirs(archiveDirectory)
            
        # If it has no schema, initialize it:
        if not self._getCreate():
       
            # List comprehension of the types, joined together with commas:
            _sqltypestr = ', '.join([' '.join(type) for type in sqltypes])
            
            _createstr ="CREATE TABLE archive (%s);" % _sqltypestr
        
            with sqlite3.connect(self.archiveFile) as _connection:
                _connection.execute(_createstr)
            
            syslog.syslog(syslog.LOG_NOTICE, "archive: created schema for archive file %s." % self.archiveFile)

    def _getCreate(self):
        """Returns the CREATE statement that created the archive.
        
        Useful for determining if the archive has been initialized.
        
        returns: the string used to CREATE the archive, or None if the archive
        has not been initialized.
        """
        _connection = sqlite3.connect(self.archiveFile)
        _cursor=_connection.cursor()
        try:
            _cursor.execute("""SELECT sql FROM sqlite_master where type='table';""")
            _row = _cursor.fetchone()
            res = str(_row[0]) if _row is not None else None
        finally:
            _cursor.close()
            _connection.close() 
        
        return res

class ArchiveRecord(dict) :
    """A dictionary which represents a single archive record in the sqlite3 archive file
    
    It is no different from any other dictionary, except it has a special method of __str__ to
    print out the most important contents nicely.
    """
    
    # A dictionary. The key is the type, the value is a tuple containing the two formats
    # to be used to print something out. The first format is for normal printing, the
    # second if a 'None' value is encountered.
    _format_dict = {'str_dateTime' : ('%s',              'YYYY-MM-DD HH:MM:SS'),
                    'dateTime'     : ('(%10u);',         '(   N/A    );'),
                    'barometer'    : ('%7.3f";',         '    N/A ;'),
                    'outTemp'      : ('%6.1fF;',         '   N/A ;'),
                    'outHumidity'  : ('%4.0f%%;',        ' N/A ;'),
                    'windSpeed'    : ('%4.0f mph;',      ' N/A mph;'),
                    'windDir'      : ('%4.0f deg;',      ' N/A deg;'),
                    'windGust'     : ('%4.0f mph gust;', ' N/A mph gust;'),
                    'rain'         : ('%5.2f" rain;',    '  N/A  rain;'),
                    'dewpoint'     : ('%4.0fF dewpt;',   ' N/A  dewpt;')}
    

    def __init__(self, start_dict=None) :
        """Initialize an instance of ArchiveRecord. It must at the least contain a valid
        key for 'dateTime' """
        if start_dict is not None :
            super(ArchiveRecord, self).__init__(start_dict)
    
    def __str__(self):
        _strlist = []
        for _data_type in ArchiveRecord._format_dict.keys():
            _val = self.get(_data_type)
            if _val is None:
                _strlist.append(ArchiveRecord._format_dict[_data_type][1])
            else:
                _strlist.append(ArchiveRecord._format_dict[_data_type][0] % _val)
        # _strlist is a list of strings. Convert it into one long string:
        _string_result = ''.join(_strlist)
        return _string_result
    
    def __getitem__(self, key):
        # Add formatted strings for local and UTC time:
        if key == 'str_dateTime' :
            return datetime.datetime.fromtimestamp(self['dateTime']).isoformat(' ')
        elif key == 'str_dateTimeUTC' :
            return datetime.datetime.utcfromtimestamp(self['dateTime']).isoformat('+')
        return super(ArchiveRecord, self).__getitem__(key)
