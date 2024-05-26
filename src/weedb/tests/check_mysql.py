#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the MySQLdb interface."""

# This module does not test anything in weewx. Instead, it checks that
# the MySQLdb interface acts the way we think it should.
#
# It uses two MySQL users, weewx1 and weewx2. The companion
# script "setup_mysql.sh" will set them up with the necessary permissions.
#
import unittest

try:
    import MySQLdb
    has_MySQLdb = True
except ImportError:
    # Some installs use 'pymysql' instead of 'MySQLdb'
    import pymysql as MySQLdb
    from pymysql import IntegrityError, ProgrammingError, OperationalError
    has_MySQLdb = False
else:
    try:
        from MySQLdb import IntegrityError, ProgrammingError, OperationalError
    except ImportError:
        from _mysql_exceptions import IntegrityError, ProgrammingError, OperationalError


def get_error(e):
    return e.exception.args[0]


class Cursor:
    """Class to be used to wrap a cursor in a 'with' clause."""

    def __init__(self, host='localhost', user='', password='', database=''):
        self.connection = MySQLdb.connect(host=host, user=user,
                                          password=password, database=database)
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self.cursor

    def __exit__(self, etyp, einst, etb):
        self.cursor.close()
        try:
            self.connection.close()
        except ProgrammingError:
            pass


class TestMySQL(unittest.TestCase):

    def setUp(self):
        self.tearDown()

    def tearDown(self):
        """Remove any databases we created."""
        with Cursor(user='weewx1', password='weewx1') as cursor:
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
            with Cursor(host='foohost', user='weewx1', password='weewx1') as e:
                pass
        if has_MySQLdb:
            self.assertEqual(get_error(e), 2005)
        else:
            self.assertEqual(get_error(e), 2003)

    def test_bad_password(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(user='weewx1', password='badpw') as e:
                pass
        self.assertEqual(get_error(e), 1045)

    def test_drop_nonexistent_database(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("DROP DATABASE test_weewx1")
            self.assertEqual(get_error(e), 1008)

    def test_drop_nopermission(self):
        with Cursor(user='weewx1', password='weewx1') as cursor1:
            cursor1.execute("CREATE DATABASE test_weewx1")
            with Cursor(user='weewx2', password='weewx2') as cursor2:
                with self.assertRaises(OperationalError) as e:
                    cursor2.execute("DROP DATABASE test_weewx1")
                self.assertEqual(get_error(e), 1044)

    def test_create_nopermission(self):
        with Cursor(user='weewx2', password='weewx2') as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("CREATE DATABASE test_weewx1")
            self.assertEqual(get_error(e), 1044)

    def test_double_db_create(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            with self.assertRaises(ProgrammingError) as e:
                cursor.execute("CREATE DATABASE test_weewx1")
            self.assertEqual(get_error(e), 1007)

    def test_open_nonexistent_database(self):
        with self.assertRaises(OperationalError) as e:
            with Cursor(user='weewx1', password='weewx1', database='test_weewx1') as cursor:
                pass
        self.assertEqual(get_error(e), 1049)

    def test_select_nonexistent_database(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            with self.assertRaises(OperationalError) as e:
                cursor.execute("SELECT foo from test_weewx1.bar")
            self.assertEqual(get_error(e), 1049)

    def test_select_nonexistent_table(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(ProgrammingError) as e:
                cursor.execute("SELECT foo from test_weewx1.fubar")
            self.assertEqual(get_error(e), 1146)

    def test_double_table_create(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            self.assertEqual(get_error(e), 1050)

    def test_select_nonexistent_column(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.bar (col1 int, col2 int)")
            with self.assertRaises(OperationalError) as e:
                cursor.execute("SELECT foo from test_weewx1.bar")
            self.assertEqual(get_error(e), 1054)

    def test_duplicate_key(self):
        with Cursor(user='weewx1', password='weewx1') as cursor:
            cursor.execute("CREATE DATABASE test_weewx1")
            cursor.execute("CREATE TABLE test_weewx1.test1 "
                           "( dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, col1 int, col2 int)")
            cursor.execute("INSERT INTO test_weewx1.test1 "
                           "(dateTime, col1, col2) VALUES (1, 10, 20)")
            with self.assertRaises(IntegrityError) as e:
                cursor.execute("INSERT INTO test_weewx1.test1 (dateTime, col1, col2) "
                               "VALUES (1, 30, 40)")
            self.assertEqual(get_error(e), 1062)


if __name__ == '__main__':
    unittest.main()
