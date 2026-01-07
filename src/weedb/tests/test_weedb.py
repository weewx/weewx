#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the weedb package.

For this test to work, MySQL user 'weewx' must have full access to database 'test':
    mysql> grant select, update, create, delete, drop, insert on test.* to weewx@localhost;
"""

import pytest

import weedb
import weedb.sqlite
from weeutil.weeutil import version_compare

sqlite_db_dict = {'database_name': '/var/tmp/test.sdb', 'driver': 'weedb.sqlite', 'timeout': '2'}
mysql_db_dict = {'database_name': 'test_weewx1', 'user': 'weewx1', 'password': 'weewx1',
                 'driver': 'weedb.mysql'}

# Schema summary:
# (col_number, col_name, col_type, can_be_null, default_value, part_of_primary)
schema = [(0, 'dateTime', 'INTEGER', False, None, True),
          (1, 'min',      'REAL',    True,  None, False),
          (2, 'mintime',  'INTEGER', True,  None, False),
          (3, 'max',      'REAL',    True,  None, False),
          (4, 'maxtime',  'INTEGER', True,  None, False),
          (5, 'sum',      'REAL',    True,  None, False),
          (6, 'count',    'INTEGER', True,  None, False),
          (7, 'descript', 'STR',     True,  None, False)]


class Common:

    def setup_method(self):
        try:
            weedb.drop(self.db_dict)
        except Exception:
            pass

    def teardown_method(self):
        try:
            weedb.drop(self.db_dict)
        except Exception:
            pass

    def populate_db(self):
        weedb.create(self.db_dict)
        with pytest.raises(weedb.DatabaseExists):
            weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:
            with weedb.Transaction(_connect) as _cursor:
                _cursor.execute("CREATE TABLE test1 (dateTime INTEGER NOT NULL PRIMARY KEY,"
                                " min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL,"
                                " count INTEGER, descript CHAR(20));")
                _cursor.execute("CREATE TABLE test2 (dateTime INTEGER NOT NULL PRIMARY KEY,"
                                " min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, "
                                "count INTEGER, descript CHAR(20));")
                for irec in range(20):
                    _cursor.execute("INSERT INTO test1 (dateTime, min, mintime) VALUES (?, ?, ?)",
                                    (irec, 10 * irec, irec))

    def test_drop(self):
        with pytest.raises(weedb.NoDatabase):
            weedb.drop(self.db_dict)

    def test_double_create(self):
        weedb.create(self.db_dict)
        with pytest.raises(weedb.DatabaseExists):
            weedb.create(self.db_dict)

    def test_no_db(self):
        with pytest.raises(weedb.NoDatabaseError):
            weedb.connect(self.db_dict)

    def test_no_tables(self):
        weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:
            assert _connect.tables() == []
            with pytest.raises(weedb.ProgrammingError):
                _connect.columnsOf('test1')
            with pytest.raises(weedb.ProgrammingError):
                _connect.columnsOf('foo')

    def test_create(self):
        self.populate_db()
        with weedb.connect(self.db_dict) as _connect:
            assert sorted(_connect.tables()) == ['test1', 'test2']
            assert _connect.columnsOf('test1') == ['dateTime', 'min', 'mintime', 'max',
                                                   'maxtime', 'sum', 'count', 'descript']
            assert _connect.columnsOf('test2') == ['dateTime', 'min', 'mintime', 'max',
                                                   'maxtime', 'sum', 'count', 'descript']
            for icol, col in enumerate(_connect.genSchemaOf('test1')):
                assert schema[icol] == col
            for icol, col in enumerate(_connect.genSchemaOf('test2')):
                assert schema[icol] == col
            # Make sure an IntegrityError gets raised in the case of a duplicate key:
            with weedb.Transaction(_connect) as _cursor:
                with pytest.raises(weedb.IntegrityError):
                    _cursor.execute("INSERT INTO test1 (dateTime, min, mintime) VALUES (0, 10, 0)")

    def test_bad_table(self):
        self.populate_db()
        with weedb.connect(self.db_dict) as _connect:
            with pytest.raises(weedb.ProgrammingError):
                _connect.columnsOf('foo')

    def test_select(self):
        self.populate_db()
        with weedb.connect(self.db_dict) as _connect:
            with _connect.cursor() as _cursor:
                _cursor.execute("SELECT dateTime, min FROM test1")
                for i, _row in enumerate(_cursor):
                    assert _row[0] == i

                # SELECT with wild card, using a result set
                _result = _cursor.execute("SELECT * from test1")
                for i, _row in enumerate(_result):
                    assert _row[0] == i

                # Find a matching result set
                _cursor.execute("SELECT dateTime, min FROM test1 WHERE dateTime = 5")
                _row = _cursor.fetchone()
                assert _row[0] == 5
                assert _row[1] == 50

                # Now test where there is no matching result:
                _cursor.execute("SELECT dateTime, min FROM test1 WHERE dateTime = -1")
                _row = _cursor.fetchone()
                assert _row is None

                # Same, but using an aggregate:
                _cursor.execute("SELECT MAX(min) FROM test1 WHERE dateTime = -1")
                _row = _cursor.fetchone()
                assert _row is not None
                assert _row[0] is None

    def test_bad_select(self):
        self.populate_db()
        with weedb.connect(self.db_dict) as _connect:
            with _connect.cursor() as _cursor:
                # Test SELECT on a bad table name
                with pytest.raises(weedb.ProgrammingError):
                    _cursor.execute("SELECT dateTime, min FROM foo")

                # Test SELECT on a bad column name
                with pytest.raises(weedb.OperationalError):
                    _cursor.execute("SELECT dateTime, foo FROM test1")

    def test_rollback(self):
        # Create the database and schema
        weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:
            with _connect.cursor() as _cursor:
                _cursor.execute(
                    "CREATE TABLE test1 (dateTime INTEGER NOT NULL PRIMARY KEY, x REAL )")

                # Now start the transaction
                _connect.begin()
                for i in range(10):
                    _cursor.execute("INSERT INTO test1 (dateTime, x) VALUES (?, ?)", (i, i + 1))
                # Roll it back
                _connect.rollback()

        # Make sure nothing is in the database
        with weedb.connect(self.db_dict) as _connect:
            with _connect.cursor() as _cursor:
                _cursor.execute("SELECT dateTime, x from test1")
                _row = _cursor.fetchone()
        assert _row is None

    def test_transaction(self):
        # Create the database and schema
        weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:

            # With sqlite, a rollback can roll back a table creation. With MySQL, it does not. So,
            # create the table outside the transaction. We're not as concerned about a
            # transaction failing when creating a table, because it only happens the first time
            # weewx starts up.
            _connect.execute("CREATE TABLE test1 (dateTime INTEGER NOT NULL PRIMARY KEY, "
                             "x REAL );")

            # We're going to trigger the rollback by raising a bogus exception.
            # Be prepared to catch it.
            try:
                with weedb.Transaction(_connect) as _cursor:
                    for i in range(10):
                        _cursor.execute("INSERT INTO test1 (dateTime, x) VALUES (?, ?)",
                                        (i, i + 1))
                    # Raise an exception:
                    raise Exception("Bogus exception")
            except Exception:
                pass

        # Now make sure nothing is in the database
        with weedb.connect(self.db_dict) as _connect:
            with _connect.cursor() as _cursor:
                _cursor.execute("SELECT dateTime, x from test1")
                _row = _cursor.fetchone()
        assert _row is None


class TestSqlite(Common):

    def setup_method(self):
        self.db_dict = sqlite_db_dict
        super().setup_method()

    def test_variable(self):
        import sqlite3
        weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:
            # Early versions of sqlite did not support journal modes.
            # Not sure exactly when it started, but I know that v3.4.2 did not have it.
            if version_compare(sqlite3.sqlite_version, '3.4.2') > 0:
                _v = _connect.get_variable('journal_mode')
                assert _v[1].lower() == 'delete'
            _v = _connect.get_variable('foo')
            assert _v is None


class TestMySQL(Common):

    def setup_method(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                pytest.skip(str(e))
        self.db_dict = mysql_db_dict
        super().setup_method()

    def test_variable(self):
        weedb.create(self.db_dict)
        with weedb.connect(self.db_dict) as _connect:
            _v = _connect.get_variable('lower_case_table_names')
            assert _v[1] in ['0', '1', '2']
            _v = _connect.get_variable('foo')
            assert _v is None
