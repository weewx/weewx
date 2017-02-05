"""Test the MySQLdb interface."""

# This module does not test anything in weewx. Instead, it checks that
# the MySQLdb interface acts the way we think it should.
#
# It uses two MySQL users, weewx1 and weewx2. The companion
# script "setup_mysql" will set them up with the necessary permissions.
#
from __future__ import with_statement
import unittest

import MySQLdb
from _mysql_exceptions import IntegrityError, ProgrammingError, OperationalError

class Cursor(object):
    """Class to be used to wrap a cursor in a 'with' clause."""
    def __init__(self, host='localhost', user='', passwd='', db=''):
        self.connection = MySQLdb.connect(host=host, user=user, passwd=passwd, db=db)
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self.cursor

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.cursor.close()
        try:
            self.connection.close()
        except ProgrammingError:
            pass

class TestMySQL(unittest.TestCase):
 
    def setUp(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            try:
                cursor.execute("DROP DATABASE test_weewx1")
            except OperationalError:
                pass
            try:
                cursor.execute("DROP DATABASE test_weewx2")
            except OperationalError:
                pass

    def test_bad_host(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(host='foohost', user='weewx1', passwd='weewx1') as e:
                pass
        self.assertEqual(e.exception[0], 2005)
        
    def test_bad_password(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(user='weewx1', passwd='badpw') as e:
                pass
        self.assertEqual(e.exception[0], 1045)

    def test_drop_nonexistent_database(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("DROP DATABASE test_weewx1")
            self.assertEqual(e.exception[0], 1008)
    
    def test_drop_nopermission(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor1:
            cursor1.execute("CREATE DATABASE test_weewx1")
            with Cursor(user='weewx2', passwd='weewx2') as cursor2:
                with self.assertRaises(OperationalError) as e:
                    cursor2.execute("DROP DATABASE test_weewx1")
                self.assertEqual(e.exception[0], 1044)

    def test_create_nopermission(self):
        with Cursor(user='weewx2', passwd='weewx2') as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("CREATE DATABASE test_weewx1")
            self.assertEqual(e.exception[0], 1044)
            
    def test_double_db_create(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            with self.assertRaises(ProgrammingError) as e:
                cursor.execute("CREATE DATABASE test_weewx1")
            self.assertEqual(e.exception[0], 1007)        
        
    def test_open_nonexistent_database(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(user='weewx1', passwd='weewx1', db='test_weewx1') as cursor:
                pass
        self.assertEqual(e.exception[0], 1049)
        
    def test_select_nonexistent_database(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            with self.assertRaises(ProgrammingError) as e:
                cursor.execute("SELECT foo from test_weewx1.bar")
            self.assertEqual(e.exception[0], 1146)
    
    def test_select_nonexistent_table(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(ProgrammingError) as e:
                cursor.execute("SELECT foo from test_weewx1.fubar")
            self.assertEqual(e.exception[0], 1146)

    def test_double_table_create(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            self.assertEqual(e.exception[0], 1050)
        
    def test_select_nonexistent_column(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("SELECT foo from test_weewx1.bar")
            self.assertEqual(e.exception[0], 1054)
        
    def test_duplicate_key(self):
        with Cursor(user='weewx1', passwd='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.test1 ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, col1 int, col2 int)")
            cursor.execute("INSERT INTO test_weewx1.test1 (dateTime, col1, col2) VALUES (1, 10, 20)")
            with self.assertRaises(IntegrityError) as e:
                cursor.execute("INSERT INTO test_weewx1.test1 (dateTime, col1, col2) VALUES (1, 30, 40)")
            self.assertEqual(e.exception[0], 1062)

        
            
if __name__ == '__main__':
    unittest.main()
