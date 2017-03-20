# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test archive and stats database modules"""
from __future__ import with_statement
import unittest
import time

import weewx.manager
import weedb
import weeutil.weeutil

archive_sqlite = {'database_name': '/var/tmp/weewx_test/weedb.sdb', 'driver':'weedb.sqlite'}
archive_mysql  = {'database_name': 'test_weedb', 'user':'weewx1', 'password':'weewx1', 'driver':'weedb.mysql'}

archive_schema = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                  ('usUnits',              'INTEGER NOT NULL'),
                  ('interval',             'INTEGER NOT NULL'),
                  ('barometer',            'REAL'),
                  ('inTemp',               'REAL'),
                  ('outTemp',              'REAL'),
                  ('windSpeed',            'REAL')]

std_unit_system = 1
interval = 3600     # One hour
nrecs = 48          # Two days
start_ts = int(time.mktime((2012, 07, 01, 00, 00, 0, 0, 0, -1))) # 1 July 2012
stop_ts = start_ts + interval * (nrecs-1)
timevec = [start_ts+i*interval for i in range(nrecs)]

def timefunc(i):
    return start_ts + i*interval
def barfunc(i):
    return 30.0 + 0.01*i
def temperfunc(i):
    return 68.0 + 0.1*i

def expected_record(irec):
    _record = {'dateTime': timefunc(irec), 'interval': interval, 'usUnits' : 1, 
               'outTemp': temperfunc(irec), 'barometer': barfunc(irec), 'inTemp': 70.0 + 0.1*irec}
    return _record

def gen_included_recs(timevec, start_ts, stop_ts, agg_interval):
    for stamp in weeutil.weeutil.intervalgen(start_ts, stop_ts, agg_interval):
        included = []
        for (irec, ts) in enumerate(timevec):
            if stamp[0] < ts <= stamp[1]:
                included.append(irec)
        yield included
    
def genRecords():
    for irec in range(nrecs):
        _record = expected_record(irec)
        yield _record

#for rec in genRecords():
#    print weeutil.weeutil.timestamp_to_string(rec['dateTime']), rec
#time.sleep(0.5)

class Common(unittest.TestCase):
    
    def setUp(self):
        try:
            weedb.drop(self.archive_db_dict)
        except:
            pass

    def tearDown(self):
        try:
            weedb.drop(self.archive_db_dict)
        except:
            pass
        
    def populate_database(self):
        # Use a 'with' statement:
        with weewx.manager.Manager.open_with_create(self.archive_db_dict, schema=archive_schema) as archive:
            archive.addRecord(genRecords())

    def test_no_archive(self):
        # Attempt to open a non-existent database results in an exception:
        self.assertRaises(weedb.OperationalError, weewx.manager.Manager.open, self.archive_db_dict)

    def test_unitialized_archive(self):
        _connect = weedb.create(self.archive_db_dict)
        self.assertRaises(weewx.UninitializedDatabase, weewx.manager.Manager(_connect))
        
    def test_create_archive(self):
        archive = weewx.manager.Manager.open_with_create(self.archive_db_dict, schema=archive_schema)
        self.assertEqual(archive.connection.tables(), ['archive'])
        self.assertEqual(archive.connection.columnsOf('archive'), ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        archive.close()
        
        # Now that the database exists, these should also succeed:
        archive = weewx.manager.Manager.open(self.archive_db_dict)
        self.assertEqual(archive.connection.tables(), ['archive'])
        self.assertEqual(archive.connection.columnsOf('archive'), ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        self.assertEqual(archive.sqlkeys, ['dateTime', 'usUnits', 'interval', 'barometer', 'inTemp', 'outTemp', 'windSpeed'])
        self.assertEqual(archive.std_unit_system, None)
        archive.close()
        
    def test_empty_archive(self):
        archive = weewx.manager.Manager.open_with_create(self.archive_db_dict, schema=archive_schema)
        self.assertEqual(archive.firstGoodStamp(), None)
        self.assertEqual(archive.lastGoodStamp(), None)
        self.assertEqual(archive.getRecord(123456789), None)
        self.assertEqual(archive.getRecord(123456789, max_delta=1800), None)
        archive.close()
        
    def test_add_archive_records(self):
        # Add a bunch of records
        self.populate_database()

        # Now test to see what's in there:            
        with weewx.manager.Manager.open(self.archive_db_dict) as archive:
            self.assertEqual(archive.firstGoodStamp(), start_ts)
            self.assertEqual(archive.lastGoodStamp(), stop_ts)
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
            
            # Test changing the unit system. It should raise a UnitError exception:
            metric_record = {'dateTime': stop_ts + interval, 'interval': interval, 'usUnits' : 16, 'outTemp': 20.0}
            self.assertRaises(weewx.UnitError, archive.addRecord, metric_record)

    def test_get_records(self):
        # Add a bunch of records
        self.populate_database()

        # Now fetch them:
        with weewx.manager.Manager.open(self.archive_db_dict) as archive:
            # Test getSql on existing type:
            bar0 = archive.getSql("SELECT barometer FROM archive WHERE dateTime=?", (start_ts,))
            self.assertEqual(bar0[0], barfunc(0))

            # Test getSql on existing type, no record:
            bar0 = archive.getSql("SELECT barometer FROM archive WHERE dateTime=?", (start_ts + 1,))
            self.assertEqual(bar0, None)

            # Try getSql on non-existing types
            self.assertRaises(weedb.OperationalError, archive.getSql, "SELECT foo FROM archive WHERE dateTime=?",
                              (start_ts,))
            self.assertRaises(weedb.ProgrammingError, archive.getSql, "SELECT barometer FROM foo WHERE dateTime=?",
                              (start_ts,))

            # Test genSql:
            for (irec,_row) in enumerate(archive.genSql("SELECT barometer FROM archive;")):
                self.assertEqual(_row[0], barfunc(irec))
                
            # Try getRecord():
            target_ts = timevec[nrecs/2]
            _rec = archive.getRecord(target_ts)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(nrecs/2), _rec)
            
            # Try finding the nearest neighbor below
            target_ts = timevec[nrecs/2] + interval/100
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(nrecs/2), _rec)

            # Try finding the nearest neighbor above
            target_ts = timevec[nrecs/2] - interval/100
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(nrecs/2), _rec)
            
            # Try finding a neighbor too far away:
            target_ts = timevec[nrecs/2] - interval/2
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            self.assertEqual(_rec, None)

            # Try finding a non-existent record:
            target_ts = timevec[nrecs/2] + 1
            _rec = archive.getRecord(target_ts)
            self.assertEqual(_rec, None)
            
        # Now try fetching them as vectors:
        with weewx.manager.Manager.open(self.archive_db_dict) as archive:
            barvec = archive.getSqlVectors((start_ts, stop_ts), 'barometer')
            # Recall that barvec will be a 3-way tuple. The first element is the vector of starting
            # times, the second the vector of ending times, and the third the data vector.
            self.assertEqual(barvec[1], ([timefunc(irec) for irec in range(nrecs)], "unix_epoch", "group_time"))
            self.assertEqual(barvec[2], ([barfunc(irec)  for irec in range(nrecs)], "inHg",       "group_pressure"))

        # Now try fetching the vectora gain, but using aggregation.
        # Start by setting up a generator function that will return the records to be
        # included in each aggregation
        gen = gen_included_recs(timevec, start_ts, stop_ts, 6*interval)
        with weewx.manager.Manager.open(self.archive_db_dict) as archive:
            barvec = archive.getSqlVectors((start_ts, stop_ts), 'barometer', aggregate_type='avg', aggregate_interval=6*interval)
            n_expected = int(nrecs / 6)
            self.assertEqual(n_expected, len(barvec[0][0]))
            for irec in range(n_expected):
                # Get the set of records to be included in this aggregation:
                recs = gen.next()
                # Make sure the timestamp of the aggregation interval is the same as the last
                # record to be included in the aggregation:
                self.assertEqual(timevec[max(recs)], barvec[1][0][irec])
                # Calculate the expected average of the records included in the aggregation.
                expected_avg = sum((barfunc(i) for i in recs)) / len(recs)
                # Compare them.
                self.assertAlmostEqual(expected_avg, barvec[2][0][irec])

    def test_update(self):
        # Add a bunch of records
        self.populate_database()
        expected_rec = expected_record(3)
        with weewx.manager.Manager.open_with_create(self.archive_db_dict, schema=archive_schema) as archive:
            archive.updateValue(expected_rec['dateTime'], 'outTemp', -1.0)
        with weewx.manager.Manager.open_with_create(self.archive_db_dict, schema=archive_schema) as archive:
            rec = archive.getRecord(expected_rec['dateTime'])
        self.assertEqual(rec['outTemp'], -1.0)


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
             'test_empty_archive', 'test_add_archive_records', 'test_get_records', 'test_update']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))
            
if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
