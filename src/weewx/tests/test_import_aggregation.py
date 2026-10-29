# Copyright (c) 2026 Manuel Hilgert
# See the file LICENSE.txt for your full rights.
"""Aggregate actual imports with native field semantics and preserve archive structure."""

import argparse
import os
import sqlite3
import time

import configobj
import pytest

import weeimport.weeimport
import weeutil.weeutil
import weectllib.import_cmd
import weectllib.import_actions
import weewx
import weewx.accum
import weewx.manager
import weewx.schemas.wview_extended
import weewx.units


STAMP = 1704067500


@pytest.fixture(autouse=True)
def accumulator_settings(monkeypatch):
    monkeypatch.setattr(weewx.accum, 'accum_dict',
                        weeutil.weeutil.ListOfDicts(weewx.accum.defaults_dict['Accumulator'].dict()))
    previous = os.environ.get('TZ')
    os.environ['TZ'] = 'UTC'
    time.tzset()
    yield
    if previous is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = previous
    time.tzset()


@pytest.fixture
def import_configuration(tmp_path):
    config = configobj.ConfigObj({
        'WEEWX_ROOT': str(tmp_path), 'config_path': str(tmp_path / 'weewx.conf'),
        'StdArchive': {'data_binding': 'wx_binding', 'archive_interval': '300'},
        'StdConvert': {'target_unit': 'US'},
        'DataBindings': {'wx_binding': {
            'database': 'archive_sqlite', 'table_name': 'archive',
            'manager': 'weewx.manager.DaySummaryManager',
            'schema': 'weewx.schemas.wview_extended.schema'}},
        'Databases': {'archive_sqlite': {
            'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'archive.sdb')}}})
    with weewx.manager.open_manager_with_config(config, 'wx_binding', initialize=True) as manager:
        manager.addRecord([{'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5,
                            'outTemp': 60.0, 'rain': 0.25, 'barometer': 29.5},
                           {'dateTime': STAMP + 300, 'usUnits': weewx.US, 'interval': 5,
                            'outTemp': 62.0, 'rain': 0.5, 'barometer': 30.0}])
    return config


def import_source(config, tmp_path, rows, options=None, fields=None, dry_run=False, tranche=1):
    data = tmp_path / 'observations.csv'
    data.write_text(rows)
    import_path = tmp_path / 'import.conf'
    settings = configobj.ConfigObj({'source': 'CSV', 'CSV': {
        'file': str(data), 'qc': 'False', 'tranche': str(tranche),
        'FieldMap': fields or {'dateTime': ['stamp', 'unix_epoch'],
                               'outTemp': ['temperature', 'degree_F'],
                               'rain': ['amount', 'inch']},
        'UpdateAggregation': options or {}}})
    settings.filename = str(import_path)
    settings.write()
    return weeimport.weeimport.Source.source_factory(
        config['config_path'], config, str(import_path), update=False,
        update_aggregate=True, dry_run=dry_run, verbose=False, no_prompt=True,
        suppress_warning=True, date=None, from_datetime=None, to_datetime=None)


def dump(config):
    path = config['Databases']['archive_sqlite']['database_name']
    with sqlite3.connect(path) as connection:
        return list(connection.iterdump())


def test_native_mean_and_rain_sum_update_only_existing_rows(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,50,0.1\n%d,70,0.2\n%d,80,0.4\n' % (
                               STAMP - 100, STAMP, STAMP + 500))
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['outTemp'] == 60
        assert record['rain'] == pytest.approx(0.3)
        assert record['barometer'] == 29.5
        assert record['interval'] == 5
        assert manager.getRecord(STAMP + 300)['outTemp'] == 62
        assert manager.getRecord(STAMP + 500) is None
        assert manager.getSql('SELECT COUNT(*) FROM archive')[0] == 2
        assert manager.getSql('SELECT SUM(count), SUM(sum), SUM(sumtime) FROM archive_day_outTemp') == (2, 122.0, 600.0)
        assert manager.getSql('SELECT SUM(sum) FROM archive_day_rain')[0] == pytest.approx(0.8)


def test_unit_conversion_happens_before_aggregation(import_configuration, tmp_path):
    fields = {'dateTime': ['stamp', 'unix_epoch'], 'outTemp': ['temperature', 'degree_C'],
              'rain': ['amount', 'mm']}
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,0,0\n%d,20,25.4\n' % (STAMP - 100, STAMP),
                           fields=fields)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['outTemp'] == pytest.approx(50)
        assert record['rain'] == pytest.approx(1)
        assert record['usUnits'] == weewx.US


def test_dry_run_leaves_all_tables_and_metadata_unchanged(import_configuration, tmp_path, capsys):
    before = dump(import_configuration)
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n%d,30,0\n' % (STAMP - 100, STAMP),
                           dry_run=True)
    source.run()
    assert dump(import_configuration) == before
    output = capsys.readouterr().out
    assert 'outTemp: 60.0 -> 20.0' in output
    assert 'Dry run complete. No archive records changed.' in output


def test_missing_values_preserve_fields_and_zero_is_valid(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,,0\n%d,,\n' % (STAMP - 100, STAMP))
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP)['outTemp'] == 60
        assert manager.getRecord(STAMP)['rain'] == 0
        assert manager.getRecord(STAMP)['barometer'] == 29.5


def test_custom_registered_observation_requires_an_explicit_extractor(import_configuration, tmp_path, monkeypatch):
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.add_column('energyprod', 'REAL')
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energyprod', 'group_energy')
    before = dump(import_configuration)
    source = import_source(import_configuration, tmp_path,
                           'stamp,counter\n%d,100\n%d,200\n' % (STAMP - 100, STAMP),
                           fields={'dateTime': ['stamp', 'unix_epoch'], 'energyprod': ['counter', 'watt_hour']})
    with pytest.raises(weeimport.weeimport.WeeImportMapError, match='extractor explicitly'):
        source.run()
    assert dump(import_configuration) == before


def test_custom_counter_last_uses_timestamp_order_across_periods(import_configuration, tmp_path, monkeypatch):
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.add_column('energyprod', 'REAL')
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energyprod', 'group_energy')
    import_configuration['Accumulator'] = {'energyprod': {'extractor': 'last'}}
    source = import_source(import_configuration, tmp_path,
                           'stamp,counter\n%d,200\n' % STAMP,
                           fields={'dateTime': ['stamp', 'unix_epoch'], 'energyprod': ['counter', 'watt_hour']})
    periods = [[{'stamp': str(STAMP), 'counter': '200'}],
               [{'stamp': str(STAMP - 100), 'counter': '100'}]]
    source.period_generator = lambda: iter(periods)
    source.get_raw_data = lambda period: period
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP)['energyprod'] == 200
        assert manager.getRecord(STAMP)['outTemp'] == 60


def test_native_wind_vector_and_gust_semantics(import_configuration, tmp_path):
    fields = {'dateTime': ['stamp', 'unix_epoch'], 'windSpeed': ['speed', 'mile_per_hour'],
              'windDir': ['direction', 'degree_compass'], 'windGust': ['gust', 'mile_per_hour'],
              'windGustDir': ['gust_direction', 'degree_compass']}
    source = import_source(import_configuration, tmp_path,
                           'stamp,speed,direction,gust,gust_direction\n%d,10,350,20,100\n%d,10,10,30,130\n' % (STAMP - 100, STAMP),
                           fields=fields)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert min(abs(record['windDir']), abs(record['windDir'] - 360)) < 1e-9
        assert record['windSpeed'] == 10
        assert record['windGust'] == 30
        assert record['windGustDir'] == 130


def test_direction_without_speed_is_rejected_before_writes(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,direction\n%d,45\n' % STAMP,
                           fields={'dateTime': ['stamp', 'unix_epoch'], 'windDir': ['direction', 'degree_compass']})
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportMapError, match='Map windSpeed'):
        source.run()
    assert dump(import_configuration) == before


@pytest.mark.parametrize('alignment,expected', [('interval', STAMP + 300), ('nearest', STAMP),
                                               ('previous', STAMP), ('next', STAMP + 300)])
def test_explicit_alignment_rules(import_configuration, tmp_path, alignment, expected):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % (STAMP + 6),
                           options={'alignment': alignment, 'max_shift': '300'})
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(expected)['outTemp'] == 10
        assert manager.getRecord(STAMP + 6) is None


def test_ties_fail_before_any_earlier_group_is_applied(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n%d,20,0\n' % (STAMP, STAMP + 150),
                           options={'alignment': 'nearest', 'max_shift': '200'})
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportFieldError, match='Equidistant'):
        source.run()
    assert dump(import_configuration) == before


def test_overlapping_intervals_require_an_anchor(import_configuration, tmp_path):
    path = import_configuration['Databases']['archive_sqlite']['database_name']
    with sqlite3.connect(path) as connection:
        connection.execute('INSERT INTO archive (dateTime, usUnits, interval, rain) VALUES (?,1,5,0)', (STAMP + 5,))
    rows = 'stamp,temperature,amount\n%d,10,0\n%d,20,0\n' % (STAMP + 1, STAMP + 6)
    source = import_source(import_configuration, tmp_path, rows)
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportFieldError, match='overlap'):
        source.run()
    assert dump(import_configuration) == before
    source = import_source(import_configuration, tmp_path, rows, options={'anchor':'outTemp'})
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP + 300)['outTemp'] == 15
        assert manager.getRecord(STAMP + 5)['rain'] == 0


def test_selected_dates_also_bound_destination_timestamps(import_configuration, tmp_path, capsys):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % (STAMP + 6),
                           options={'alignment':'nearest', 'max_shift':'15'})
    source.first_ts = STAMP
    source.last_ts = STAMP + 300
    before = dump(import_configuration)
    source.run()
    assert dump(import_configuration) == before
    assert '1 outside date limits' in capsys.readouterr().out


def test_source_period_failure_leaves_prior_readings_unwritten(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % STAMP)
    source.period_generator = lambda: iter([1, 2])
    def get_data(period):
        if period == 2:
            raise weeimport.weeimport.WeeImportIOError('Second period unavailable')
        return [{'stamp': str(STAMP), 'temperature':'10', 'amount':'0'}]
    source.get_raw_data = get_data
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportIOError):
        source.run()
    assert dump(import_configuration) == before


def test_update_only_manager_does_not_insert_or_change_empty_archive_caches(tmp_path):
    database = {'driver':'weedb.sqlite', 'database_name':str(tmp_path / 'missing.sdb')}
    with weewx.manager.Manager.open_with_create(database, schema=weewx.schemas.wview_extended.schema) as manager:
        assert manager.addRecord({'dateTime':STAMP, 'usUnits':weewx.US, 'outTemp':10}, update_only=True) == 0
        assert manager.getSql('SELECT COUNT(*) FROM archive')[0] == 0
        assert manager.first_timestamp is None
        assert manager.last_timestamp is None
        assert manager.std_unit_system is None


@pytest.mark.parametrize('other', ['--update', '--updatedelete'])
def test_update_aggregation_flag_is_exclusive_with_update(monkeypatch, other):
    parser = argparse.ArgumentParser()
    weectllib.import_cmd.add_subparser(parser.add_subparsers())
    with pytest.raises(SystemExit) as rejected:
        parser.parse_args(['import', '--import-config', 'input.conf', other, '--updateagg'])
    assert rejected.value.code == 2
    calls = []
    monkeypatch.setattr(weectllib.import_actions, 'obs_import',
                        lambda config, path, **options: calls.append(options))
    namespace = parser.parse_args(['import', '--import-config', 'input.conf', '--updateagg'])
    weectllib.import_cmd.import_func({}, namespace)
    assert calls[0]['update_aggregate'] is True
    assert calls[0]['update'] is False


@pytest.mark.parametrize('options', [
    {'alignment':'unknown'}, {'alignment':'nearest'}, {'alignment':'previous'},
    {'alignment':'next'}, {'max_shift':'-1'}, {'max_shift':'nan'},
    {'max_shift':'inf'}, {'anchor':'missingColumn'}])
def test_invalid_alignment_configuration_is_rejected_before_writes(import_configuration, tmp_path, options):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % STAMP, options=options)
    before = dump(import_configuration)
    with pytest.raises((weeimport.weeimport.WeeImportOptionError, ValueError)):
        source.run()
    assert dump(import_configuration) == before


def test_tolerance_does_not_move_distant_readings(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n%d,90,0\n' % (STAMP + 5, STAMP + 100),
                           options={'alignment':'nearest','max_shift':'15'})
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP)['outTemp'] == 10
        assert manager.getRecord(STAMP + 300)['outTemp'] == 62
        assert manager.getSql('SELECT COUNT(*) FROM archive')[0] == 2


def test_duplicate_timestamps_across_periods_keep_the_first_reading(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0.1\n' % STAMP)
    periods = [[{'stamp':str(STAMP),'temperature':'10','amount':'0.1'}],
               [{'stamp':str(STAMP),'temperature':'90','amount':'0.9'}]]
    source.period_generator = lambda: iter(periods)
    source.get_raw_data = lambda period: period
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP)['outTemp'] == 10
        assert manager.getRecord(STAMP)['rain'] == pytest.approx(0.1)


def test_cross_midnight_periods_are_aggregated_into_the_same_archive_record(import_configuration, tmp_path):
    midnight = STAMP - 300
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.addRecord({'dateTime':midnight,'usUnits':weewx.US,'interval':5,'outTemp':60,'rain':0})
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0.1\n' % (midnight - 1))
    periods = [[{'stamp':str(midnight - 1),'temperature':'10','amount':'0.1'}],
               [{'stamp':str(midnight),'temperature':'30','amount':'0.2'}]]
    source.period_generator = lambda: iter(periods)
    source.get_raw_data = lambda period: period
    source.run()
    day = weeutil.weeutil.startOfArchiveDay(midnight)
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(midnight)['outTemp'] == 20
        assert manager.getRecord(midnight)['rain'] == pytest.approx(0.3)
        assert manager.getSql('SELECT count, sumtime FROM archive_day_outTemp WHERE dateTime = ?', (day,)) == (1, 300.0)
        assert manager.getRecord(STAMP)['outTemp'] == 60


@pytest.mark.parametrize('month,day,length,transition', [(3,31,23,7200),(10,27,25,10800)])
def test_dst_station_days_keep_native_interval_boundaries(import_configuration, tmp_path, month, day, length, transition):
    os.environ['TZ'] = 'Europe/Berlin'
    time.tzset()
    first = int(time.mktime((2024,month,day,0,0,0,0,0,-1)))
    last = int(time.mktime((2024,month,day + 1,0,0,0,0,0,-1)))
    assert last - first == length * 3600
    before_transition = first + transition - 300
    after_transition = first + transition
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.addRecord([{'dateTime':stamp,'usUnits':weewx.US,'interval':5,'outTemp':60}
                           for stamp in (before_transition, after_transition)])
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,20,0\n%d,40,0\n' % (before_transition - 1, after_transition - 1))
    source.first_ts = first
    source.last_ts = last
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(before_transition)['outTemp'] == 20
        assert manager.getRecord(after_transition)['outTemp'] == 40
        assert manager.getRecord(after_transition)['interval'] == 5
        assert manager.getSql('SELECT count, sum, sumtime FROM archive_day_outTemp WHERE dateTime = ?', (first,)) == (2,60.0,600.0)


@pytest.mark.parametrize('invalid', ['nan','inf','-inf'])
def test_non_finite_input_never_partially_updates_the_archive(import_configuration, tmp_path, invalid, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n%d,%s,0\n' % (STAMP, STAMP + 100, invalid))
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportFieldError, match='Non-finite'):
        source.run()
    assert dump(import_configuration) == before
    assert not list(tmp_path.glob('weewx-import-aggregation-*'))


def test_aggregate_overflow_is_rejected_before_writes(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,1e308\n%d,20,1e308\n' % (STAMP - 100, STAMP))
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportFieldError, match='overflow'):
        source.run()
    assert dump(import_configuration) == before


def test_cancelling_the_preview_leaves_the_archive_unchanged(import_configuration, tmp_path, monkeypatch):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % STAMP)
    source.no_prompt = False
    monkeypatch.setattr(weeutil.weeutil, 'y_or_n', lambda *args, **kwargs:'n')
    before = dump(import_configuration)
    source.run()
    assert dump(import_configuration) == before


@pytest.mark.parametrize('alignment', ['interval', 'nearest', 'previous', 'next'])
@pytest.mark.parametrize('beginning,expected', [(STAMP + 120, 0.5), (STAMP, 1.0)])
def test_date_limit_never_replaces_a_complete_interval_with_a_partial_total(
        import_configuration, tmp_path, alignment, beginning, expected):
    rows = 'stamp,temperature,amount\n' + ''.join(
        '%d,62,0.2\n' % (STAMP + offset) for offset in (60, 120, 180, 240, 300))
    if beginning == STAMP:
        rows = 'stamp,temperature,amount\n%d,62,1.0\n' % (STAMP + 300)
    source = import_source(import_configuration, tmp_path, rows,
                           options={'alignment': alignment, 'max_shift': '300'})
    source.first_ts = beginning
    source.last_ts = STAMP + 3600
    before = dump(import_configuration)
    source.run()
    if beginning != STAMP:
        assert dump(import_configuration) == before
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        assert manager.getRecord(STAMP + 300)['rain'] == pytest.approx(expected)


@pytest.mark.parametrize('speed,gust,direction,gust_direction', [
    ('', '', 90, 100), ('0', '0', 180, 180), ('', '10', 90, 180)])
def test_wind_directions_require_corresponding_measurements(
        import_configuration, tmp_path, speed, gust, direction, gust_direction):
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.addRecord({'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5,
                           'windSpeed': 5, 'windDir': 90, 'windGust': 8, 'windGustDir': 100},
                          update=True)
    fields = {'dateTime': ['stamp', 'unix_epoch'], 'windSpeed': ['speed', 'mile_per_hour'],
              'windDir': ['direction', 'degree_compass'], 'windGust': ['gust', 'mile_per_hour'],
              'windGustDir': ['gust_direction', 'degree_compass']}
    source = import_source(import_configuration, tmp_path,
                           'stamp,speed,direction,gust,gust_direction\n%d,%s,180,%s,180\n' % (
                               STAMP, speed, gust), fields=fields)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['windDir'] == direction
        assert record['windGustDir'] == gust_direction
        assert record['windSpeed'] == (5 if speed == '' else 0)
        assert record['windGust'] == (8 if gust == '' else float(gust))


def test_undecodable_source_period_aborts_cleanly_before_writing(import_configuration, tmp_path):
    source = import_source(import_configuration, tmp_path,
                           'stamp,temperature,amount\n%d,10,0\n' % STAMP)
    source.period_generator = lambda: iter([1, 2])

    def get_data(period):
        if period == 2:
            raise weeimport.weeimport.WeeImportDecodeError('Invalid encoding in second period')
        return [{'stamp': str(STAMP), 'temperature': '10', 'amount': '0'}]

    source.get_raw_data = get_data
    before = dump(import_configuration)
    with pytest.raises(weeimport.weeimport.WeeImportIOError, match='Invalid encoding'):
        source.run()
    assert dump(import_configuration) == before


def test_missing_peak_direction_preserves_the_stored_value(import_configuration, tmp_path):
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        manager.addRecord({'dateTime': STAMP, 'usUnits': weewx.US, 'interval': 5,
                           'windSpeed': 5, 'windDir': 90, 'windGust': 8, 'windGustDir': 100},
                          update=True)
    fields = {'dateTime': ['stamp', 'unix_epoch'], 'windSpeed': ['speed', 'mile_per_hour'],
              'windDir': ['direction', 'degree_compass'], 'windGust': ['gust', 'mile_per_hour'],
              'windGustDir': ['gust_direction', 'degree_compass']}
    source = import_source(import_configuration, tmp_path,
                           'stamp,speed,direction,gust,gust_direction\n%d,10,,8,180\n' % STAMP,
                           fields=fields)
    source.run()
    with weewx.manager.open_manager_with_config(import_configuration, 'wx_binding') as manager:
        record = manager.getRecord(STAMP)
        assert record['windGust'] == 10
        assert record['windGustDir'] == 100
        assert record['windDir'] == 90
