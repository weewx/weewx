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
import weedb

archive_sqlite = {'database': '/tmp/weedb.sdb', 'driver':'weedb.sqlite'}
archive_mysql  = {'database': 'test_weedb', 'user':'weewx', 'password':'weewx', 'driver':'weedb.mysql'}

archive_schema = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                  ('usUnits',              'INTEGER NOT NULL'),
                  ('interval',             'INTEGER NOT NULL'),
                  ('barometer',            'REAL'),
                  ('inTemp',               'REAL'),
                  ('outTemp',              'REAL'),
                  ('windSpeed',            'REAL')]

std_unit_system = 1
interval = 3600     # One hour
nrecs = 12
start_ts = int(time.mktime((2012, 07, 01, 00, 00, 0, 0, 0, -1))) # 1 July 2012
stop_ts = start_ts + interval * nrecs
last_ts = start_ts + interval * (nrecs-1)

def timefunc(i):
    return start_ts + i*interval
def barfunc(i):
    return 30.0 + 0.01*i
def temperfunc(i):
    return 68.0 + 0.1*i

def genRecords():
    for irec in range(nrecs):
        _record = {'dateTime': timefunc(irec), 'interval': interval, 'usUnits' : 1, 
                   'outTemp': temperfunc(irec), 'barometer': barfunc(irec), 'inTemp': 70.0 + 0.1*irec}
        yield _record

class Common(unittest.TestCase):
    
    def setUp(self):
        try:
            weedb.drop(self.archive_db_dict)
        except:
            pass

    def test_no_archive(self):
        # Attempt to open a non-existent database results in an exception:
        self.assertRaises(weedb.OperationalError, weewx.archive.Archive.open, self.archive_db_dict)

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

    def test_get_records(self):
        # Add a bunch of records:
        with weewx.archive.Archive.open_with_create(self.archive_db_dict, archive_schema) as archive:
            archive.addRecord(genRecords())

        # Now fetch them:
        with weewx.archive.Archive.open_with_create(self.archive_db_dict, archive_schema) as archive:
            # Test getSql:
            bar0 = archive.getSql("SELECT barometer FROM archive WHERE dateTime=?", (start_ts,))
            self.assertEqual(bar0[0], barfunc(0))
            
            # Test genSql:
            for (irec,_row) in enumerate(archive.genSql("SELECT barometer FROM archive;")):
                self.assertEqual(_row[0], barfunc(irec))
                
            # Test getSqlVectors:

            barvec = archive.getSqlVectors('barometer', start_ts, last_ts)
            self.assertEqual(barvec[1], ([barfunc(irec) for irec in range(nrecs)], "inHg", "group_pressure"))
            self.assertEqual(barvec[0], ([timefunc(irec) for irec in range(nrecs)], "unix_epoch", "group_time"))

class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_sqlite
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_mysql
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_no_archive', 'test_create_archive', 
             'test_empty_archive', 'test_add_archive_records', 'test_get_records']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))
            
if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
