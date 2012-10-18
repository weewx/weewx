# -*- coding: utf-8 -*-
#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 670 $
#    $Author: tkeffer $
#    $Date: 2012-10-11 16:55:54 -0700 (Thu, 11 Oct 2012) $
#
"""Test archive and stats database modules"""
import unittest
import time

import weewx.archive
import weewx.stats
import weedb

archive_sqlite = {'database': '/tmp/weedb.sdb', 'driver':'weedb.sqlite'}
stats_sqlite   = {'database': '/tmp/stats.sdb', 'driver':'weedb.sqlite'}
archive_mysql  = {'database': 'test_weedb', 'user':'weewx', 'password':'weewx', 'driver':'weedb.mysql'}
stats_mysql    = {'database': 'test_stats', 'user':'weewx', 'password':'weewx', 'driver':'weedb.mysql'}

archive_schema = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                  ('usUnits',              'INTEGER NOT NULL'),
                  ('interval',             'INTEGER NOT NULL'),
                  ('barometer',            'REAL'),
                  ('inTemp',               'REAL'),
                  ('outTemp',              'REAL'),
                  ('windSpeed',            'REAL')]

drop_list = ['dateTime', 'usUnits', 'interval', 'windSpeed', 'windDir', 'windGust', 'windGustDir']
stats_types = [_tuple[0] for _tuple in archive_schema if _tuple[0] not in drop_list] + ['wind']

std_unit_system = 1
interval = 300
nrecs = 20
start_ts = int(time.mktime((2012, 07, 01, 00, 00, 0, 0, 0, -1))) # 1 July 2012
stop_ts = start_ts + interval * nrecs
last_ts = start_ts + interval * (nrecs-1)

def genRecords():
    for irec in range(nrecs):
        _record = {'dateTime': start_ts + irec*interval, 'interval': interval, 'usUnits' : 1, 
                   'outTemp': 68.0 + 0.1*irec, 'barometer': 30.0+0.01*irec, 'inTemp': 70.0 + 0.1*irec}
        yield _record

class Common(unittest.TestCase):
    
    def setUp(self):
        try:
            weedb.drop(self.archive_db_dict)
        except:
            pass
        try:
            weedb.drop(self.stats_db_dict)
        except:
            pass

    def test_no_archive(self):
        # Attempt to open a non-existent database results in an exception:
        self.assertRaises(weedb.OperationalError, weewx.archive.Archive.open, self.archive_db_dict)

    def test_no_stats(self):
        # Attempt to open a non-existent database results in an exception:
        self.assertRaises(weedb.OperationalError, weewx.stats.StatsDb.open, self.stats_db_dict)
        
    def test_create_archive(self):
        archive = weewx.archive.Archive.open_with_create(self.archive_db_dict, archive_schema)
        self.assertItemsEqual(archive.connection.tables(), ['archive'])
        self.assertEqual(archive.connection.columnsOf('archive'), ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        archive.close()
        
        # Now that the database exists, these should also succeed:
        archive = weewx.archive.Archive.open(self.archive_db_dict)
        self.assertItemsEqual(archive.connection.tables(), ['archive'])
        self.assertEqual(archive.connection.columnsOf('archive'), ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        self.assertEqual(archive.sqlkeys, ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        self.assertEqual(archive.std_unit_system, None)
        archive.close()
        
    def test_create_stats(self):
        stats = weewx.stats.StatsDb.open_with_create(self.stats_db_dict, stats_types)
        self.assertItemsEqual(stats.connection.tables(), ['barometer', 'inTemp', 'outTemp', 'wind', 'metadata'])
        self.assertEqual(stats.connection.columnsOf('barometer'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count'])
        self.assertEqual(stats.connection.columnsOf('wind'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count', 'gustdir', 'xsum', 'ysum', 'squaresum', 'squarecount'])
        stats.close()
        
        # Now that the database exists, these should also succeed:
        stats = weewx.stats.StatsDb.open(self.stats_db_dict)
        self.assertItemsEqual(stats.connection.tables(), ['barometer', 'inTemp', 'outTemp', 'wind', 'metadata'])
        self.assertEqual(stats.connection.columnsOf('barometer'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count'])
        self.assertEqual(stats.connection.columnsOf('wind'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count', 'gustdir', 'xsum', 'ysum', 'squaresum', 'squarecount'])
        stats.close()
        
    def test_empty_archive(self):
        archive = weewx.archive.Archive.open_with_create(self.archive_db_dict, archive_schema)
        self.assertEqual(archive.firstGoodStamp(), None)
        self.assertEqual(archive.lastGoodStamp(), None)
        self.assertEqual(archive.getRecord(123456789), None)
        
    def test_add_archive_records(self):
        # Test adding records using a 'with' statement:
        with weewx.archive.Archive.open_with_create(self.archive_db_dict, archive_schema) as archive:
            archive.addRecord(genRecords())

        # Now test to see what's in there:            
        with weewx.archive.Archive.open(self.archive_db_dict) as archive:
            self.assertEqual(archive.firstGoodStamp(), start_ts)
            self.assertEqual(archive.lastGoodStamp(), last_ts)
            self.assertEqual(archive.std_unit_system, std_unit_system)
            
            expected_iterator = genRecords()
            for _rec in archive.genBatchRecords():
                try:
                    _expected_rec = expected_iterator.next()
                except StopIteration:
                    break
                # Check that the missing windSpeed is None, then remove it in order to do the compare:
                self.assertEqual(_rec.pop('windSpeed'), None)
                self.assertEqual(_expected_rec, _rec)
                
            
            # Test adding an existing record. It should just quietly swallow it:
            existing_record = {'dateTime': start_ts, 'interval': interval, 'usUnits' : 1, 'outTemp': 68.0}
            archive.addRecord(existing_record)
            
            # Test changing the unit system. It should raise a ValueError exception:
            metric_record = {'dateTime': last_ts + interval, 'interval': interval, 'usUnits' : 16, 'outTemp': 20.0}
            self.assertRaises(ValueError, archive.addRecord, metric_record)

class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_sqlite
        self.stats_db_dict = stats_sqlite
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_mysql
        self.stats_db_dict = stats_mysql
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_no_archive', 'test_no_stats', 'test_create_archive', 'test_create_stats', 
             'test_empty_archive', 'test_add_archive_records']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))
            
if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
