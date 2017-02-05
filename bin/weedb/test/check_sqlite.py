"""Test the MySQLdb interface."""

# This module does not test anything in weewx. Instead, it checks that
# the MySQLdb interface acts the way we think it should.
#
# It uses two MySQL users, weewx1 and weewx2. The companion
# script "setup_mysql" will set them up with the necessary permissions.
#
from __future__ import with_statement
import unittest
import sys
import os

import sqlite3
from sqlite3 import IntegrityError, ProgrammingError, OperationalError

# This database should be somewhere where you have write permissions:
sqdb1 = '/var/tmp/sqdb1.sdb'
# This database should be somewhere where you do NOT have write permissions:
sqdb2 = '/usr/local/sqdb2.sdb'

# Double check that we have the necessary permissions (or lack thereof):
try:
    fd = open(sqdb1, 'w')
    fd.close()
except:
    print >>sys.stderr, "For tests to work properly, you must have permission to write to '%s'." % sqdb1
    print >>sys.stderr, "Change the permissions and try again."
try:
    fd = open(sqdb2, 'w')
    fd.close()
except IOError:
    pass
else:
    print >>sys.stderr, "For tests to work properly, you must NOT have permission to write to '%s'." % sqdb2
    print >>sys.stderr, "Change the permissions and try again."

class Cursor(object):
    """Class to be used to wrap a cursor in a 'with' clause."""
    def __init__(self, file_path):
        self.connection = sqlite3.connect(file_path)
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self.cursor

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.cursor.close()
        self.connection.close()

class TestSqlite3(unittest.TestCase):
 
    def setUp(self):
        try:
            os.remove(sqdb1)
        except OSError:
            pass
        try:
            os.remove(sqdb2)
        except OSError:
            pass

    def test_create_nopermission(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(sqdb2) as cursor:
                pass
        self.assertEqual(str(e.exception), 'unable to open database file')

    def test_select_nonexistent_table(self):
        with Cursor(sqdb1) as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("SELECT foo from bar")
            self.assertEqual(str(e.exception), "no such table: bar")
        
     
    def test_double_table_create(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            self.assertEqual(str(e.exception), 'table bar already exists')
         
    def test_select_nonexistent_column(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("SELECT foo from bar")
            self.assertEqual(str(e.exception), 'no such column: foo')
         
    def test_duplicate_key(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE test1 ( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, col1 int, col2 int)")
            cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 10, 20)")
            with self.assertRaises(IntegrityError) as e:
                cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 30, 40)")
            self.assertEqual(str(e.exception), "UNIQUE constraint failed: test1.dateTime")
        
            
if __name__ == '__main__':
    unittest.main()
