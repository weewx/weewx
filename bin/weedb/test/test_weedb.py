#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 689 $
#    $Author: tkeffer $
#    $Date: 2012-10-16 15:54:56 -0700 (Tue, 16 Oct 2012) $
#
"""Test the weedb package"""

from __future__ import with_statement
import unittest

import weedb

sqlite_db_dict = {'database': '/tmp/test.sdb', 'driver':'weedb.sqlite'}
mysql_db_dict  = {'database': 'test', 'user':'weewx', 'password':'weewx', 'driver':'weedb.mysql'}

class Common(unittest.TestCase):
    
    def setUp(self):
        try:
            weedb.drop(self.db_dict)
        except:
            pass

    def tearDown(self):
        try:
            weedb.drop(self.db_dict)
        except:
            pass

    def populate_db(self):
        weedb.create(self.db_dict)
        self.assertRaises(weedb.DatabaseExists, weedb.create, self.db_dict)
        _connect = weedb.connect(self.db_dict)
        with weedb.Transaction(_connect) as _cursor:
            _cursor.execute("""CREATE TABLE test1 ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                      """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER);""")
            _cursor.execute("""CREATE TABLE test2 ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, """\
                      """min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER);""")
            for irec in range(20):
                _cursor.execute("INSERT INTO test1 (dateTime, min, mintime) VALUES (?, ?, ?)", (irec, 10*irec, irec))
        _connect.close()

    def test_drop(self):
        self.assertRaises(weedb.NoDatabase, weedb.drop, self.db_dict)
        weedb.create(self.db_dict)

    def test_double_create(self):
        weedb.create(self.db_dict)
        self.assertRaises(weedb.DatabaseExists, weedb.create, self.db_dict)
        
    def test_no_db(self):        
        self.assertRaises(weedb.OperationalError, weedb.connect, self.db_dict)
        
    def test_no_tables(self):
        weedb.create(self.db_dict)
        _connect = weedb.connect(self.db_dict)
        self.assertEqual(_connect.tables(), [])
        self.assertRaises(weedb.OperationalError, _connect.columnsOf, 'test1')
        _connect.close()
        
    def test_create(self):
        self.populate_db()
        _connect = weedb.connect(self.db_dict)
        self.assertItemsEqual(_connect.tables(), ['test1', 'test2'])
        self.assertEqual(_connect.columnsOf('test1'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count'])
        self.assertEqual(_connect.columnsOf('test2'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count'])
        _connect.close()
        
    def test_bad_table(self):
        self.populate_db()
        _connect = weedb.connect(self.db_dict)
        self.assertRaises(weedb.OperationalError, _connect.columnsOf, 'foo')
        _connect.close()
        
    def test_select(self):
        self.populate_db()
        _connect = weedb.connect(self.db_dict)
        _cursor = _connect.cursor()
        _cursor.execute("SELECT dateTime, min FROM test1")
        for i, _row in enumerate(_cursor):
            self.assertEqual(_row[0], i)
        _cursor.close()
        _connect.close()
        
    def test_bad_select(self):
        self.populate_db()
        _connect = weedb.connect(self.db_dict)
        _cursor = _connect.cursor()
        with self.assertRaises(weedb.OperationalError):
            _cursor.execute("SELECT dateTime, min FROM foo")
        _cursor.close()
        _connect.close()
        
class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.db_dict = sqlite_db_dict
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.db_dict = mysql_db_dict
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_drop', 'test_double_create', 'test_no_db', 'test_no_tables', 
             'test_create', 'test_bad_table', 'test_select', 'test_bad_select']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))
    
if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())