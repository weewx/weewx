#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the weedb exception hierarchy"""
import os.path
import sys
import pytest

import weedb

#
# For these tests to work, the database for sqdb1 must in a place where you have write permissions,
# and the database for sqdb2 must be in a place where you do NOT have write permissions
sqdb1_dict = {'database_name': '/var/tmp/weewx_test/sqdb1.sdb', 'driver': 'weedb.sqlite', 'timeout': '2'}
sqdb2_dict = {'database_name': '/usr/local/sqdb2.sdb', 'driver': 'weedb.sqlite', 'timeout': '2'}
mysql1_dict = {'database_name': 'test_weewx1', 'user': 'weewx1', 'password': 'weewx1', 'driver': 'weedb.mysql'}
mysql2_dict = {'database_name': 'test_weewx1', 'user': 'weewx2', 'password': 'weewx2', 'driver': 'weedb.mysql'}

# Double check that we have the necessary permissions (or lack thereof):
try:
    file_directory = os.path.dirname(sqdb1_dict['database_name'])
    if not os.path.exists(file_directory):
        os.makedirs(file_directory)
    fd = open(sqdb1_dict['database_name'], 'w')
    fd.close()
# Python 2 raises IOError; Python 3 raises PermissionError, a subclass of OSError:
except (IOError, OSError):
    sys.exit("For tests to work properly, you must have permission to write to '%s'.\n"
             "Change the permissions and try again." % sqdb1_dict['database_name'])

try:
    fd = open(sqdb2_dict['database_name'], 'w')
    fd.close()
# Python 2 raises IOError; Python 3 raises PermissionError, a subclass of OSError:
except (IOError, OSError):
    pass
else:
    sys.exit("For tests to work properly, you must NOT have permission to write to '%s'.\n"
             "Change the permissions and try again." % sqdb2_dict['database_name'])


class TestErrors:

    @pytest.fixture(autouse=True)
    def setup(self):
        """Drop the old databases, in preparation for running a test."""
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                pytest.skip(str(e))
        try:
            weedb.drop(mysql1_dict)
        except weedb.NoDatabase:
            pass
        try:
            weedb.drop(sqdb1_dict)
        except weedb.NoDatabase:
            pass

    def test_bad_host(self):
        mysql_dict = dict(mysql1_dict)
        mysql_dict['host'] = 'foohost'
        with pytest.raises(weedb.CannotConnectError):
            weedb.connect(mysql_dict)

    def test_bad_password(self):
        mysql_dict = dict(mysql1_dict)
        mysql_dict['password'] = 'badpw'
        with pytest.raises(weedb.BadPasswordError):
            weedb.connect(mysql_dict)

    def test_drop_nonexistent_database(self):
        with pytest.raises(weedb.NoDatabase):
            weedb.drop(mysql1_dict)
        with pytest.raises(weedb.NoDatabase):
            weedb.drop(sqdb1_dict)

    def test_drop_nopermission(self):
        weedb.create(mysql1_dict)
        with pytest.raises(weedb.PermissionError):
            weedb.drop(mysql2_dict)
        weedb.create(sqdb1_dict)
        # Can't really test this one without setting up a file where
        # we have no write permission
        with pytest.raises(weedb.NoDatabaseError):
            weedb.drop(sqdb2_dict)

    def test_create_nopermission(self):
        with pytest.raises(weedb.PermissionError):
            weedb.create(mysql2_dict)
        with pytest.raises(weedb.PermissionError):
            weedb.create(sqdb2_dict)

    def test_double_db_create(self):
        weedb.create(mysql1_dict)
        with pytest.raises(weedb.DatabaseExists):
            weedb.create(mysql1_dict)
        weedb.create(sqdb1_dict)
        with pytest.raises(weedb.DatabaseExists):
            weedb.create(sqdb1_dict)

    def test_open_nonexistent_database(self):
        with pytest.raises(weedb.OperationalError):
            connect = weedb.connect(mysql1_dict)
        with pytest.raises(weedb.OperationalError):
            connect = weedb.connect(sqdb1_dict)

    def test_select_nonexistent_database(self):
        mysql_dict = dict(mysql1_dict)
        mysql_dict.pop('database_name')
        connect = weedb.connect(mysql_dict)
        cursor = connect.cursor()
        # Earlier versions of MySQL would raise error number 1146, "Table doesn't exist".
        with pytest.raises((weedb.NoDatabaseError, weedb.NoTableError)):
            cursor.execute("SELECT foo from test_weewx1.bar")
        cursor.close()
        connect.close()

        # There's no analogous operation with sqlite. You
        # must create the database in order to open it.

    def test_select_nonexistent_table(self):
        def test(db_dict):
            weedb.create(db_dict)
            connect = weedb.connect(db_dict)
            cursor = connect.cursor()
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with pytest.raises(weedb.NoTableError):
                cursor.execute("SELECT foo from fubar")
            cursor.close()
            connect.close()

        test(mysql1_dict)
        test(sqdb1_dict)

    def test_double_table_create(self):
        def test(db_dict):
            weedb.create(db_dict)
            connect = weedb.connect(db_dict)
            cursor = connect.cursor()
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with pytest.raises(weedb.TableExistsError):
                cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            cursor.close()
            connect.close()

        test(mysql1_dict)
        test(sqdb1_dict)

    def test_select_nonexistent_column(self):
        def test(db_dict):
            weedb.create(db_dict)
            connect = weedb.connect(db_dict)
            cursor = connect.cursor()
            cursor.execute("CREATE TABLE bar (col1 int, col2 int)")
            with pytest.raises(weedb.NoColumnError):
                cursor.execute("SELECT foo from bar")
            cursor.close()
            connect.close()

        test(mysql1_dict)
        test(sqdb1_dict)

    def test_duplicate_key(self):
        def test(db_dict):
            weedb.create(db_dict)
            connect = weedb.connect(db_dict)
            cursor = connect.cursor()
            cursor.execute("CREATE TABLE test1 ( dateTime INTEGER NOT NULL PRIMARY KEY, col1 int, col2 int)")
            cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 10, 20)")
            with pytest.raises(weedb.IntegrityError):
                cursor.execute("INSERT INTO test1 (dateTime, col1, col2) VALUES (1, 30, 40)")
            cursor.close()
            connect.close()

        test(mysql1_dict)
        test(sqdb1_dict)

