#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import threading
from unittest import mock

import weedb.mysql

import pytest

import weedb
import weewx
import weewx.manager
import weewx.units
import weewx.xtypes


@pytest.fixture(params=['sqlite', 'mysql'])
def database(request, tmp_path):
    if request.param == 'sqlite':
        yield {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'archive.sdb')}
    else:
        config = {'driver': 'weedb.mysql', 'database_name': 'test_scratch',
                  'host': 'localhost', 'user': 'weewx', 'password': 'weewx'}
        try:
            weedb.drop(config)
        except weedb.NoDatabaseError:
            pass
        try:
            yield config
        finally:
            try:
                weedb.drop(config)
            except weedb.NoDatabaseError:
                pass


SCHEMA = [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'), ('usUnits', 'INTEGER NOT NULL'),
          ('interval', 'INTEGER NOT NULL'), ('rain', 'REAL'), ('outTemp', 'REAL'),
          ('energy', 'REAL'), ('windSpeed', 'REAL'), ('windDir', 'REAL'),
          ('windGust', 'REAL'), ('windGustDir', 'REAL')]
STAMP = 1704110400
RECORD = {'dateTime': STAMP, 'usUnits': weewx.METRICWX, 'interval': 5,
          'rain': 1.0, 'outTemp': 20.0, 'energy': 1000.0}


DAY_SCHEMA = {'table': SCHEMA, 'day_summaries': [('rain', 'scalar'), ('outTemp', 'scalar')]}


def test_permanent_summary_failure_rolls_back_archive_and_metadata(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        original = type(manager.connection.cursor()).execute

        def fail(cursor, sql, *args, **kwargs):
            if sql.startswith('INSERT INTO archive_day_rain VALUES'):
                raise weedb.OperationalError('summary write failed')
            return original(cursor, sql, *args, **kwargs)

        with mock.patch.object(type(manager.connection.cursor()), 'execute', fail):
            with pytest.raises(weedb.OperationalError, match='summary write failed'):
                manager.addRecord(dict(RECORD, dateTime=STAMP + 300), log_success=False)
        assert manager.getSql('SELECT COUNT(*) FROM archive')[0] == 1
        assert manager.getSql('SELECT sum FROM archive_day_rain')[0] == 1
        assert int(manager._read_metadata('lastUpdate')) == STAMP
        assert manager.last_timestamp == STAMP


def test_mysql_deadlock_retries_entire_archive_transaction(database):
    if database['driver'] != 'weedb.mysql':
        pytest.skip('Requires InnoDB deadlock detection')
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        manager.connection.execute('SET SESSION innodb_lock_wait_timeout=5')
        other = weedb.connect(database)
        reached_second = threading.Event()
        first_key, second_key = manager.daykeys
        outcome = {}
        original = weedb.mysql.Cursor.execute
        second_delete = 'DELETE FROM archive_day_%s WHERE' % second_key

        def execute(cursor, sql, *args, **kwargs):
            if threading.current_thread().name == 'archive-writer' and sql.startswith(second_delete):
                reached_second.set()
            return original(cursor, sql, *args, **kwargs)

        def add():
            try:
                outcome['added'] = manager.addRecord(dict(RECORD, dateTime=STAMP + 300, rain=2),
                                                       log_success=False)
            except Exception as error:
                outcome['error'] = error

        try:
            other.execute('SET SESSION innodb_lock_wait_timeout=5')
            other.execute('CREATE TABLE scratch (id INTEGER PRIMARY KEY)')
            other.begin()
            for number in range(200):
                other.execute('INSERT INTO scratch VALUES (?)', (number,))
            other.execute('SELECT * FROM archive_day_%s FOR UPDATE' % second_key)
            with mock.patch.object(weedb.mysql.Cursor, 'execute', execute):
                writer = threading.Thread(target=add, name='archive-writer')
                writer.start()
                try:
                    assert reached_second.wait(5)
                    other.execute('SELECT * FROM archive_day_%s FOR UPDATE' % first_key)
                finally:
                    other.rollback()
                    writer.join(15)
            assert not writer.is_alive()
            assert outcome == {'added': 1}
            assert tuple(manager.getSql('SELECT COUNT(*), SUM(rain) FROM archive')) == (2, 3)
            assert tuple(manager.getSql('SELECT count, sum FROM archive_day_rain')) == (2, 3)
            assert int(manager._read_metadata('lastUpdate')) == STAMP + 300
            assert manager.last_timestamp == STAMP + 300
        finally:
            other.rollback()
            other.close()


def test_mysql_lock_timeout_retries_archive_and_summary_together(database):
    if database['driver'] != 'weedb.mysql':
        pytest.skip('Requires InnoDB row lock timeouts')
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        manager.connection.execute('SET SESSION innodb_lock_wait_timeout=1')
        other = weedb.connect(database)
        original = weedb.mysql.Cursor.execute
        timeouts = []

        def execute(cursor, sql, *args, **kwargs):
            try:
                return original(cursor, sql, *args, **kwargs)
            except weedb.DatabaseLockedError as error:
                if sql.startswith('DELETE FROM archive_day_rain WHERE'):
                    timeouts.append(error)
                    other.rollback()
                raise

        try:
            other.begin()
            other.execute('SELECT * FROM archive_day_rain FOR UPDATE')
            with mock.patch.object(weedb.mysql.Cursor, 'execute', execute):
                assert manager.addRecord(dict(RECORD, dateTime=STAMP + 300, rain=2),
                                          log_success=False) == 1
            assert len(timeouts) == 1 and '1205' in str(timeouts[0])
            assert tuple(manager.getSql('SELECT COUNT(*), SUM(rain) FROM archive')) == (2, 3)
            assert tuple(manager.getSql('SELECT count, sum FROM archive_day_rain')) == (2, 3)
        finally:
            other.rollback()
            other.close()
