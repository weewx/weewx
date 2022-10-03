# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test archive and stats database modules"""
from __future__ import with_statement
from __future__ import absolute_import

import unittest
import time

from six.moves import StringIO
from six.moves import map
from six.moves import range

import configobj

import weewx.manager
import weedb
import weeutil.weeutil
import weeutil.logger

weeutil.logger.setup('test_database',{})

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
start_ts = int(time.mktime((2012, 7, 1, 00, 00, 0, 0, 0, -1))) # 1 July 2012
stop_ts = start_ts + interval * (nrecs-1)
timevec = [start_ts+i*interval for i in range(nrecs)]

def timefunc(i):
    return start_ts + i*interval
def barfunc(i):
    return 30.0 + 0.01*i
def temperfunc(i):
    return 68.0 + 0.1*i

def expected_record(irec):
    _record = {'dateTime': timefunc(irec), 'interval': int(interval/60), 'usUnits' : 1,
               'outTemp': temperfunc(irec), 'barometer': barfunc(irec), 'inTemp': 70.0 + 0.1*irec}
    return _record

def gen_included_recs(timevec, start_ts, stop_ts, agg_interval):
    """Generator function that marches down a set of aggregation intervals. Each yield returns
     the set of records included in that interval."""
    for span in weeutil.weeutil.intervalgen(start_ts, stop_ts, agg_interval):
        included = set()
        for (irec, ts) in enumerate(timevec):
            if span[0] < ts <= span[1]:
                included.add(irec)
        yield included
    
def genRecords():
    for irec in range(nrecs):
        _record = expected_record(irec)
        yield _record


class TestDatabaseDict(unittest.TestCase):

    def test_get_database_dict(self):
        config_snippet = '''
        WEEWX_ROOT = /home/weewx
        [DatabaseTypes]
          [[SQLite]]
            driver = weedb.sqlite
            SQLITE_ROOT = %(WEEWX_ROOT)s/archive
        [Databases]
            [[archive_sqlite]]
               database_name = weewx.sdb
               database_type = SQLite'''
        config_dict = configobj.ConfigObj(StringIO(config_snippet))
        database_dict = weewx.manager.get_database_dict_from_config(config_dict, 'archive_sqlite')
        self.assertEqual(database_dict, {'SQLITE_ROOT': '/home/weewx/archive',
                                         'database_name': 'weewx.sdb',
                                         'driver': 'weedb.sqlite'})


class Common(object):
    
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

    def test_open_no_archive(self):
        # Attempt to open a non-existent database results in an exception:
        with self.assertRaises(weedb.NoDatabaseError):
            db_manager = weewx.manager.Manager.open(self.archive_db_dict)

    def test_open_unitialized_archive(self):
        """Test creating the database, but not initializing it. Then try to open it."""
        weedb.create(self.archive_db_dict)
        with self.assertRaises(weedb.ProgrammingError):
            db_manager = weewx.manager.Manager.open(self.archive_db_dict)

    def test_open_with_create_no_archive(self):
        """Test open_with_create of a non-existent database and without supplying a schema."""
        with self.assertRaises(weedb.NoDatabaseError):
            db_manager = weewx.manager.Manager.open_with_create(self.archive_db_dict)

    def test_open_with_create_uninitialized(self):
        """Test open_with_create with a database that exists, but has not been initialized and
        no schema has been supplied."""
        weedb.create(self.archive_db_dict)
        with self.assertRaises(weedb.ProgrammingError):
            db_manager = weewx.manager.Manager.open_with_create(self.archive_db_dict)

    def test_create_archive(self):
        """Test open_with_create with a database that does not exist, while supplying a schema"""
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
                    _expected_rec = next(expected_iterator)
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
                
            itest = int(nrecs/2)
            # Try getRecord():
            target_ts = timevec[itest]
            _rec = archive.getRecord(target_ts)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(itest), _rec)
            
            # Try finding the nearest neighbor below
            target_ts = timevec[itest] + interval/100
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(itest), _rec)

            # Try finding the nearest neighbor above
            target_ts = timevec[itest] - interval/100
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            # Check that the missing windSpeed is None, then remove it in order to do the compare:
            self.assertEqual(_rec.pop('windSpeed'), None)
            self.assertEqual(expected_record(itest), _rec)
            
            # Try finding a neighbor too far away:
            target_ts = timevec[itest] - interval/2
            _rec = archive.getRecord(target_ts, max_delta=interval/50)
            self.assertEqual(_rec, None)

            # Try finding a non-existent record:
            target_ts = timevec[itest] + 1
            _rec = archive.getRecord(target_ts)
            self.assertEqual(_rec, None)
            
        # Now try fetching them as vectors:
        with weewx.manager.Manager.open(self.archive_db_dict) as archive:
            # Return the values between start_ts and stop_ts, exclusive on the left,
            # inclusive on the right.
            # Recall that barvec returns a 3-way tuple of VectorTuples.
            start_vt, stop_vt, data_vt = archive.getSqlVectors((start_ts, stop_ts), 'barometer')
            # Build the expected series of stop times and data values. Note that the very first
            # value in the database (at timestamp start_ts) is not included, so it should not be
            # included in the expected results either.
            expected_stop = [timefunc(irec) for irec in range(1, nrecs)]
            expected_data = [barfunc(irec) for irec in range(1, nrecs)]
            self.assertEqual(stop_vt, (expected_stop, "unix_epoch", "group_time"))
            self.assertEqual(data_vt, (expected_data, "inHg",       "group_pressure"))

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
                recs = next(gen)
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


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_sqlite
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):
    
    def __init__(self, *args, **kwargs):
        self.archive_db_dict = archive_mysql
        super(TestMySQL, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super(TestMySQL, self).setUp()

    
def suite():
    tests = ['test_open_no_archive', 'test_open_unitialized_archive',
             'test_open_with_create_no_archive', 'test_open_with_create_uninitialized',
             'test_empty_archive', 'test_add_archive_records', 'test_get_records', 'test_update']
    suite = unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))
    suite.addTest(TestDatabaseDict('test_get_database_dict'))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
