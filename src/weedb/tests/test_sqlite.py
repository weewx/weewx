#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the sqlite3 interface."""

#
# This module does not test anything in weewx. Instead, it checks that
# the sqlite interface acts the way we think it should.
#

import os
import sqlite3
import pytest
from sqlite3 import IntegrityError, OperationalError

# This database should be somewhere where you have write permissions:
sqdb1 = '/var/tmp/sqdb1.sdb'
# This database should be somewhere where you do NOT have write permissions:
sqdb2 = '/usr/local/sqdb2.sdb'


class Cursor:
    """Class to be used to wrap a cursor in a 'with' clause."""

    def __init__(self, file_path):
        self.connection = sqlite3.connect(file_path)
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self.cursor

    def __exit__(self, etyp, einst, etb):  # @UnusedVariable
        self.cursor.close()
        self.connection.close()


class TestSqlite3:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Remove any databases we created."""
        self.tear_down()
        yield
        self.tear_down()

    def tear_down(self):
        try:
            os.remove(sqdb1)
        except OSError:
            pass
        try:
            os.remove(sqdb2)
        except OSError:
            pass

    def test_create_nopermission(self):
        with pytest.raises(OperationalError) as e:
            with Cursor(sqdb2):
                pass
        assert str(e.value) == 'unable to open database file'

    def test_select_nonexistent_table(self):
        with Cursor(sqdb1) as cursor:
            with pytest.raises(OperationalError) as e:
                cursor.execute("SELECT foo from bar")
            assert str(e.value) == "no such table: bar"

    def test_double_table_create(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with pytest.raises(OperationalError) as e:
                cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            assert str(e.value) == 'table bar already exists'

    def test_select_nonexistent_column(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with pytest.raises(OperationalError) as e:
                cursor.execute("SELECT foo from bar")
            assert str(e.value) == 'no such column: foo'

    def test_duplicate_key(self):
        with Cursor(sqdb1) as cursor:
            cursor.execute("CREATE TABLE test1 ( dateTime INTEGER NOT NULL PRIMARY KEY, col1 int, col2 int)")
            cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 10, 20)")
            with pytest.raises(IntegrityError) as e:
                cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 30, 40)")
            assert str(e.value) == "UNIQUE constraint failed: test1.dateTime"
