#
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test MySQL error translation and failed-query diagnostics."""

import importlib.util
import logging
import os.path
import sys
import time
from unittest import mock

import pytest

import weedb
import weewxd


@pytest.fixture(params=['MySQLdb', 'pymysql'])
def mysql_driver(request, monkeypatch):
    backend = pytest.importorskip(request.param)
    # Select each real backend through its MySQLdb-compatible interface, even
    # when both are installed. Keep the normal weedb.mysql module untouched.
    monkeypatch.setitem(sys.modules, 'MySQLdb', backend)
    path = os.path.join(os.path.dirname(weedb.__file__), 'mysql.py')
    spec = importlib.util.spec_from_file_location('test_weedb_mysql_recovery', path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


@pytest.mark.parametrize('errno, expected', [
    (1040, weedb.CannotConnectError),
    (1203, weedb.CannotConnectError),
    (4031, weedb.DisconnectError),
    (2006, weedb.DisconnectError),
    (2013, weedb.DisconnectError),
    (1067, weedb.DatabaseError),
    (9999, weedb.DatabaseError),
])
def test_error_translation_preserves_original(mysql_driver, errno, expected):
    original = mysql_driver.MySQLdb.OperationalError(errno, 'database error')

    @mysql_driver.guard
    def fail():
        raise original

    with pytest.raises(expected) as error:
        fail()
    assert type(error.value) is expected
    assert error.value.args == (original,)
    assert error.value.__context__ is original


@pytest.mark.parametrize('errno', [1040, 1203, 4031])
def test_database_errors_reach_daemon_retry(mysql_driver, monkeypatch, errno):
    original = mysql_driver.MySQLdb.OperationalError(errno, 'database error')
    cursor = mysql_driver.Cursor(mock.Mock())
    cursor.cursor.execute.side_effect = original
    connect = mock.Mock(side_effect=original)
    monkeypatch.setattr(mysql_driver.MySQLdb, 'connect', connect)

    def create_engine(config):
        if errno != 4031:
            return mysql_driver.Connection()
        engine = mock.Mock()
        engine.run.side_effect = lambda: cursor.execute('SELECT 1')
        return engine

    class RetryObserved(Exception):
        pass

    waits = []

    def wait(seconds):
        waits.append(seconds)
        raise RetryObserved()

    monkeypatch.setattr(sys, 'argv', ['weewxd'])
    monkeypatch.setattr(weewxd.weeutil.startup, 'start_app',
                        lambda *args: ('', {}, mock.Mock()))
    monkeypatch.setattr(weewxd.weewx.engine, 'StdEngine', create_engine)
    monkeypatch.setattr(weewxd.weewx, 'launchtime_ts', time.time() + 100)
    monkeypatch.setattr(weewxd.signal, 'signal', mock.Mock())
    monkeypatch.setattr(weewxd.time, 'sleep', wait)

    with pytest.raises(RetryObserved):
        weewxd.main()
    assert waits == [60]
    if errno == 4031:
        cursor.cursor.execute.assert_called_once()
    else:
        connect.assert_called_once()


@pytest.mark.parametrize('error_name, errno, expected', [
    ('OperationalError', 2006, weedb.DisconnectError),
    ('InterfaceError', 0, weedb.DisconnectError),
    ('ProgrammingError', 1064, weedb.DatabaseError),
])
def test_failed_query_logs_sql_without_replacing_error(mysql_driver, caplog,
                                                      error_name, errno, expected):
    original = getattr(mysql_driver.MySQLdb, error_name)(errno, 'database error')
    cursor = mysql_driver.Cursor(mock.Mock())
    cursor.cursor.execute.side_effect = original
    sql = 'SELECT * FROM archive WHERE dateTime > ?'
    parameters = (1704110400,)

    with caplog.at_level(logging.DEBUG, logger=mysql_driver.__name__):
        with pytest.raises(expected) as error:
            cursor.execute(sql, parameters)

    assert type(error.value) is expected
    assert error.value.args == (original,)
    assert error.value.__context__ is original
    cursor.cursor.execute.assert_called_once()
    records = [record for record in caplog.records if record.name == mysql_driver.__name__]
    assert len(records) == 1
    assert sql in records[0].getMessage()
    assert repr(parameters) in records[0].getMessage()
    assert records[0].exc_info[1] is original


def test_query_diagnostics_require_debug_logging(mysql_driver, caplog):
    cursor = mysql_driver.Cursor(mock.Mock())
    cursor.cursor.execute.side_effect = mysql_driver.MySQLdb.OperationalError(2006, 'gone')
    with caplog.at_level(logging.INFO, logger=mysql_driver.__name__):
        with pytest.raises(weedb.DisconnectError):
            cursor.execute('SELECT 1')
    assert not caplog.records


def test_successful_query_has_no_diagnostic(mysql_driver, caplog):
    cursor = mysql_driver.Cursor(mock.Mock())
    with caplog.at_level(logging.DEBUG, logger=mysql_driver.__name__):
        cursor.execute('SELECT 1')
    assert not caplog.records
