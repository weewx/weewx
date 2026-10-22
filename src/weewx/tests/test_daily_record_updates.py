from unittest import mock

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


DAY_SCHEMA = {'table': SCHEMA, 'day_summaries': [('rain', 'scalar'), ('outTemp', 'scalar'),
                                                ('wind', 'vector')]}


def summaries(manager):
    return {key: [tuple(row) for row in manager.genSql(
        'SELECT * FROM %s_day_%s ORDER BY dateTime' % (manager.table_name, key))]
            for key in manager.daykeys}


def test_unchanged_updates_preserve_daily_summaries(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        records = [dict(RECORD, windSpeed=2, windDir=90, windGust=4, windGustDir=180),
                   dict(RECORD, dateTime=STAMP + 300, rain=2, outTemp=30, interval=15)]
        manager.addRecord(records, log_success=False)
        before = summaries(manager)
        manager.addRecord(records, update=True, log_success=False)
        assert summaries(manager) == before
        assert manager.getSql('SELECT COUNT(*) FROM archive')[0] == 2


def test_corrected_partial_and_full_records_match_fresh_summaries(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        manager.addRecord([dict(RECORD, windSpeed=2, windDir=90, windGust=8, windGustDir=180),
                           dict(RECORD, dateTime=STAMP + 300, rain=2, outTemp=40, interval=15),
                           dict(RECORD, dateTime=STAMP + 86400, rain=3)], log_success=False)
        manager.addRecord([dict(RECORD, rain=None, outTemp=0, interval=10,
                                windSpeed=0, windDir=None, windGust=1, windGustDir=90),
                           {'dateTime': STAMP + 300, 'usUnits': weewx.METRICWX, 'interval': 15, 'outTemp': 10}],
                          update=True, log_success=False)
        actual = summaries(manager)
        archived = list(manager.genBatchRecords())
        with weewx.manager.DaySummaryManager.open_with_create(
                database, table_name='reference', schema=DAY_SCHEMA) as reference:
            reference.addRecord(archived, log_success=False)
            assert actual == summaries(reference)
        assert int(manager._read_metadata('lastUpdate')) == STAMP + 86400
        assert manager.getSql('SELECT MAX(max) FROM archive_day_outTemp')[0] == 20


def test_changed_day_is_rebuilt_once_per_chunk(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        records = [dict(RECORD, dateTime=STAMP + index * 60) for index in range(201)]
        manager.addRecord(records, log_success=False)
        with mock.patch.object(manager, '_set_day_summary', wraps=manager._set_day_summary) as write:
            manager.addRecord([dict(record, rain=2) for record in records],
                              update=True, log_success=False)
            assert write.call_count == 2
        assert tuple(manager.getSql('SELECT count, sum FROM archive_day_rain')) == (201, 402)


def test_invalidated_day_does_not_keep_old_summary_rows(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        manager.addRecord(dict(RECORD, interval=0), update=True, log_success=False)
        assert all(not rows for rows in summaries(manager).values())


def test_update_does_not_mark_unbuilt_summaries_complete(database):
    records = [dict(RECORD, dateTime=STAMP + day * 86400) for day in range(3)]
    with weewx.manager.Manager.open_with_create(database, schema=DAY_SCHEMA) as archive:
        archive.addRecord(records, log_success=False)
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        assert manager._read_metadata('lastUpdate') is None
        manager.addRecord(dict(records[-1], rain=2), update=True, log_success=False)
        assert manager._read_metadata('lastUpdate') is None
        manager.backfill_day_summary()
        assert tuple(manager.getSql('SELECT COUNT(*), SUM(sum) FROM archive_day_rain')) == (3, 4)


def test_mixed_chunk_retry_matches_clean_rebuild(database):
    with weewx.manager.DaySummaryManager.open_with_create(database, schema=DAY_SCHEMA) as manager:
        later = dict(RECORD, dateTime=STAMP + 86400)
        manager.addRecord([RECORD, later], log_success=False)
        finish = manager._finish_chunk
        attempts = []

        def fail_once(updated, cursor):
            finish(updated, cursor)
            attempts.append(True)
            if len(attempts) == 1:
                raise weedb.DatabaseLockedError('retry corrected day')

        with mock.patch.object(manager, '_finish_chunk', fail_once):
            manager.addRecord([dict(RECORD, rain=2, outTemp=10),
                               dict(RECORD, dateTime=STAMP + 300, rain=3), later,
                               dict(RECORD, dateTime=STAMP + 86700, rain=4)],
                              update=True, log_success=False)
        assert len(attempts) == 2
        with weewx.manager.DaySummaryManager.open_with_create(
                database, table_name='reference', schema=DAY_SCHEMA) as reference:
            reference.addRecord(list(manager.genBatchRecords()), log_success=False)
            assert summaries(manager) == summaries(reference)
