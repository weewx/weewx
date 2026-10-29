#
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test database errors raised while reading a table schema."""

import importlib.util
import os.path
import sys
from unittest import mock

import pytest

import weedb
import weedb.sqlite
import weewx.manager


@pytest.fixture
def sqlite_connections(tmp_path):
    path = str(tmp_path / 'schema.sdb')
    weedb.sqlite.create(database_name=path)
    reader = weedb.sqlite.connect(database_name=path, timeout=0)
    writer = weedb.sqlite.connect(database_name=path, timeout=0)
    writer.execute('CREATE TABLE archive (dateTime INTEGER NOT NULL PRIMARY KEY, '
                   'usUnits INTEGER NOT NULL, interval INTEGER NOT NULL, outTemp REAL)')
    try:
        yield reader, writer
    finally:
        writer.rollback()
        writer.close()
        reader.close()


def test_sqlite_schema_query_starts_on_iteration(sqlite_connections):
    reader, writer = sqlite_connections
    schema = reader.genSchemaOf('archive')
    writer.connection.execute('BEGIN EXCLUSIVE')
    with pytest.raises(weedb.DatabaseLockedError):
        next(schema)
    writer.rollback()
    assert [row[1] for row in reader.genSchemaOf('archive')] == [
        'dateTime', 'usUnits', 'interval', 'outTemp']


@pytest.mark.parametrize('operation', ['columns', 'manager'])
def test_sqlite_schema_lock_reaches_callers_as_weedb_error(sqlite_connections, operation):
    reader, writer = sqlite_connections
    writer.connection.execute('BEGIN EXCLUSIVE')
    with pytest.raises(weedb.DatabaseLockedError):
        if operation == 'columns':
            reader.columnsOf('archive')
        else:
            weewx.manager.Manager(reader)
    writer.rollback()
    manager = weewx.manager.Manager(reader)
    assert manager.sqlkeys == ['dateTime', 'usUnits', 'interval', 'outTemp']


def test_sqlite_missing_table_has_no_schema_rows(sqlite_connections):
    reader, _ = sqlite_connections
    assert list(reader.genSchemaOf('missing_table')) == []


@pytest.fixture(params=['MySQLdb', 'pymysql'])
def mysql_driver(request, monkeypatch):
    backend = pytest.importorskip(request.param)
    # Select each real backend through its MySQLdb-compatible interface, even
    # when both are installed. Keep the normal weedb.mysql module untouched.
    monkeypatch.setitem(sys.modules, 'MySQLdb', backend)
    path = os.path.join(os.path.dirname(weedb.__file__), 'mysql.py')
    spec = importlib.util.spec_from_file_location('test_weedb_mysql_schema', path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


@pytest.mark.parametrize('errno, expected', [
    (1146, weedb.NoTableError),
    (2013, weedb.DisconnectError),
])
def test_mysql_schema_errors_are_translated_on_iteration(mysql_driver, errno, expected):
    error_class = mysql_driver.MySQLdb.ProgrammingError if errno == 1146 \
        else mysql_driver.MySQLdb.OperationalError
    original = error_class(errno, 'database error')
    native_cursor = mock.MagicMock()
    native_cursor.__enter__.return_value = native_cursor
    native_cursor.execute.side_effect = original
    connection = mysql_driver.Connection.__new__(mysql_driver.Connection)
    connection.connection = mock.Mock()
    connection.connection.cursor.return_value = native_cursor

    schema = connection.genSchemaOf('archive')
    native_cursor.execute.assert_not_called()
    with pytest.raises(expected) as error:
        next(schema)
    assert type(error.value) is expected
    assert error.value.args == (original,)
    assert error.value.__context__ is original
