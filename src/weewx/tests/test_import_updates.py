# Copyright (c) 2026 Manuel Hilgert
# See the file LICENSE.txt for your full rights.
"""Import missing values without losing existing observations or SQL insert semantics."""

import argparse
import sqlite3

import configobj
import pytest

import weectllib.import_actions
import weectllib.import_cmd
import weeimport.weeimport
import weewx
import weewx.manager


STAMP = 1704067500


@pytest.fixture
def import_configuration(tmp_path):
    config = configobj.ConfigObj({
        'WEEWX_ROOT': str(tmp_path),
        'config_path': str(tmp_path / 'weewx.conf'),
        'StdArchive': {'data_binding': 'wx_binding', 'archive_interval': '300'},
        'StdConvert': {'target_unit': 'US'},
        'DataBindings': {'wx_binding': {
            'database': 'archive_sqlite', 'table_name': 'archive',
            'manager': 'weewx.manager.DaySummaryManager',
            'schema': 'weewx.schemas.wview_small.schema'}},
        'Databases': {'archive_sqlite': {
            'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'archive.sdb')}}})
    with weewx.manager.open_manager_with_config(config, 'wx_binding', initialize=True) as manager:
        manager.addRecord({'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5,
                           'outTemp': 60.0, 'rain': 0.25, 'barometer': 29.5})
    return config


def import_source(config, tmp_path, rows, update=False, update_delete=False, dry_run=False,
                  fields=None, tranche=1):
    data = tmp_path / 'observations.csv'
    data.write_text(rows)
    import_path = tmp_path / 'import.conf'
    settings = configobj.ConfigObj({
        'source': 'CSV', 'CSV': {
            'file': str(data), 'interval': 'conf', 'qc': 'False',
            'calc_missing': 'False', 'tranche': str(tranche),
            'FieldMap': fields or {'dateTime': ['stamp', 'unix_epoch'],
                                   'outTemp': ['temperature', 'degree_F'],
                                   'rain': ['amount', 'inch']}}})
    settings.filename = str(import_path)
    settings.write()
    return weeimport.weeimport.Source.source_factory(
        config['config_path'], config, str(import_path),
        update=update, update_delete=update_delete, dry_run=dry_run,
        verbose=False, no_prompt=True, suppress_warning=True,
        date=None, from_datetime=None, to_datetime=None)


@pytest.mark.parametrize('update,delete,temperature,rain', [
    (False, False, 60.0, 0.25), (True, False, 60.0, 0.0), (False, True, None, 0.0)])
def test_csv_missing_values_and_zero_update_existing_rows(
        import_configuration, tmp_path, update, delete, temperature, rain):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,,0\n%d,,0\n' % (STAMP, STAMP + 300),
                           update=update, update_delete=delete)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        existing = manager.getRecord(STAMP)
        assert existing['outTemp'] == temperature
        assert existing['rain'] == rain
        assert existing['barometer'] == 29.5
        assert manager.getRecord(STAMP + 300)['outTemp'] is None
        assert manager.getSql('SELECT COALESCE(SUM(count), 0) FROM archive_day_outTemp')[0] == (0 if delete else 1)


def test_delete_does_not_clear_a_column_absent_from_the_source(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature\n%d,\n' % STAMP, update_delete=True)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['outTemp'] is None
        assert record['rain'] == 0.25
        assert record['barometer'] == 29.5


def test_dry_run_leaves_archive_summaries_and_metadata_unchanged(import_configuration, tmp_path):
    path = import_configuration['Databases']['archive_sqlite']['database_name']
    with sqlite3.connect(path) as connection:
        before = list(connection.iterdump())
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,,0\n' % (STAMP + 300),
                           update_delete=True, dry_run=True)
    source.run()
    with sqlite3.connect(path) as connection:
        assert list(connection.iterdump()) == before


def test_manager_null_policy_preserves_insert_defaults_and_default_update_behavior(tmp_path):
    schema = [('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'), ('usUnits', 'INTEGER'),
              ('interval', 'INTEGER'), ('outTemp', 'REAL DEFAULT 99'),
              ('note', "TEXT DEFAULT 'fallback'")]
    database = {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'defaults.sdb')}
    with weewx.manager.Manager.open_with_create(database, schema=schema) as manager:
        original = {'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5,
                    'outTemp': 60.0, 'note': 'kept'}
        manager.addRecord(original)
        missing = dict(original, outTemp=None, note=None)
        manager.addRecord(missing, update=True, update_nulls=False)
        assert manager.getRecord(STAMP)['outTemp'] == 60.0
        assert manager.getRecord(STAMP)['note'] == 'kept'
        manager.addRecord(dict(missing, dateTime=STAMP + 300), update=True, update_nulls=False)
        assert manager.getRecord(STAMP + 300)['outTemp'] is None
        assert manager.getRecord(STAMP + 300)['note'] is None
        manager.addRecord(missing, update=True)
        assert manager.getRecord(STAMP)['outTemp'] is None
        assert manager.getRecord(STAMP)['note'] is None


@pytest.mark.parametrize('delete,expected', [(False, 'kept'), (True, None)])
def test_import_empty_text_uses_the_same_null_policy(import_configuration, tmp_path, delete, expected):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,60,0\n' % STAMP,
                           update=not delete, update_delete=delete)
    schema = [('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'), ('usUnits', 'INTEGER'),
              ('interval', 'INTEGER'), ('note', 'TEXT')]
    database = {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'text.sdb')}
    try:
        with weewx.manager.Manager.open_with_create(database, schema=schema) as manager:
            manager.addRecord({'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5, 'note': 'kept'})
            source.save_to_archive(manager, [{'dateTime': STAMP, 'usUnits': weewx.US,
                                              'interval': 5, 'note': ''}])
            assert manager.getRecord(STAMP)['note'] == expected
    finally:
        source.dbm.close()


def test_import_update_flags_are_mutually_exclusive_and_dispatched(monkeypatch):
    parser = argparse.ArgumentParser()
    weectllib.import_cmd.add_subparser(parser.add_subparsers())
    arguments = ['import', '--import-config', 'input.conf']
    with pytest.raises(SystemExit) as rejected:
        parser.parse_args(arguments + ['--update', '--updatedelete'])
    assert rejected.value.code == 2
    calls = []
    monkeypatch.setattr(weectllib.import_actions, 'obs_import',
                        lambda config, path, **options: calls.append(options))
    namespace = parser.parse_args(arguments + ['--updatedelete'])
    weectllib.import_cmd.import_func({}, namespace)
    assert calls[0]['update_delete'] is True
    assert calls[0]['update'] is False


def test_delete_preserves_missing_trailing_csv_cells(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,61\n' % STAMP, update_delete=True)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['outTemp'] == 61
        assert record['rain'] == 0.25


@pytest.mark.parametrize('method', ['_add_with_retry', '_add_chunk', '_addSingleRecord'])
def test_default_add_record_accepts_legacy_manager_overrides(tmp_path, method):
    def add_single(self, record, cursor, log_success=True, log_failure=True, update=False):
        return weewx.manager.Manager._addSingleRecord(
            self, record, cursor, log_success, log_failure, update)

    def add_chunk(self, chunk, accumulator=None, progress_fn=None,
                  log_success=True, log_failure=True, update=False, count=0):
        return weewx.manager.Manager._add_chunk(
            self, chunk, accumulator, progress_fn, log_success, log_failure, update, count)

    def add_with_retry(self, chunk, accumulator=None, progress_fn=None,
                       log_success=True, log_failure=True, update=False, count=0):
        return weewx.manager.Manager._add_with_retry(
            self, chunk, accumulator, progress_fn, log_success, log_failure, update, count)

    overrides = {'_add_with_retry': add_with_retry, '_add_chunk': add_chunk,
                 '_addSingleRecord': add_single}
    legacy = type('LegacyManager', (weewx.manager.Manager,), {method: overrides[method]})
    database = {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'legacy.sdb')}
    schema = [('dateTime', 'INTEGER PRIMARY KEY'), ('usUnits', 'INTEGER'), ('outTemp', 'REAL')]
    with legacy.open_with_create(database, schema=schema) as manager:
        assert manager.addRecord({'dateTime': STAMP, 'usUnits': weewx.US, 'outTemp': 60}) == 1


@pytest.mark.parametrize('tranche', [1, 10])
def test_normal_csv_import_accepts_a_legacy_manager(import_configuration, tmp_path, monkeypatch, tranche):
    class LegacyManager(weewx.manager.DaySummaryManager):
        def _addSingleRecord(self, record, cursor, log_success=True, log_failure=True, update=False):
            return super()._addSingleRecord(record, cursor, log_success, log_failure, update)

    monkeypatch.setattr(weewx.manager, 'LegacyImportManager', LegacyManager, raising=False)
    import_configuration['DataBindings']['wx_binding']['manager'] = 'weewx.manager.LegacyImportManager'
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,61,0\n' % (STAMP + 300), tranche=tranche)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP + 300)['outTemp'] == 61
