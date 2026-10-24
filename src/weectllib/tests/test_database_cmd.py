#
#    See the file LICENSE.txt for your rights.
#
"""Tests for selecting an alternate SQLite file with weectl database."""

import argparse
import copy
import logging
import sqlite3
import subprocess
import sys

import configobj
import pytest

import weectl
import weectllib.database_cmd
import weedb
import weewx.manager


@pytest.fixture
def config_dict(tmp_path):
    binding = {
        'database': 'archive_sqlite',
        'manager': 'weewx.manager.Manager',
        'table_name': 'archive',
        'schema': {
            'dateTime': 'INTEGER NOT NULL PRIMARY KEY',
            'usUnits': 'INTEGER NOT NULL',
            'interval': 'INTEGER NOT NULL',
            'outTemp': 'REAL',
            'extraTemp1': 'REAL',
        },
    }
    return configobj.ConfigObj({
        'WEEWX_ROOT': str(tmp_path),
        'DataBindings': {'wx_binding': binding, 'other_binding': copy.deepcopy(binding)},
        'Databases': {
            'archive_sqlite': {'database_name': 'weewx.sdb', 'database_type': 'SQLite'},
        },
        'DatabaseTypes': {
            'SQLite': {'driver': 'weedb.sqlite', 'SQLITE_ROOT': '%(WEEWX_ROOT)s/archive'},
        },
        'StdConvert': {'target_unit': 'METRIC'},
    })


@pytest.fixture
def parser():
    parser = argparse.ArgumentParser()
    weectllib.database_cmd.add_subparser(parser.add_subparsers())
    return parser


@pytest.fixture
def run_command(config_dict, parser, monkeypatch):
    monkeypatch.setattr(weectllib.weeutil.startup, 'start_app',
                        lambda *args: (None, config_dict, logging.getLogger(__name__)))

    def run(args):
        namespace = parser.parse_args(['database'] + args)
        namespace.func(namespace)

    return run


@pytest.mark.parametrize('args', [
    ['create'], ['drop-daily'], ['rebuild-daily'], ['add-column', 'soilTemp1'],
    ['rename-column', 'outTemp', 'soilTemp1'], ['drop-columns', 'soilTemp1'],
    ['reconfigure'], ['calc-missing'],
    ['check'], ['update'], ['reweight'],
])
def test_override_all_actions(config_dict, parser, run_command, args):
    original = copy.deepcopy(config_dict.dict())
    namespace = parser.parse_args(['database'] + args
                                 + ['--binding=other_binding', '--db-filename=old.sdb'])
    calls = []

    def inspect_config(action_config, action_namespace):
        manager_dict = weewx.manager.get_manager_dict_from_config(action_config,
                                                                 action_namespace.binding)
        assert manager_dict['database_dict']['database_name'] == 'old.sdb'
        assert manager_dict['database_dict']['SQLITE_ROOT'] == config_dict['WEEWX_ROOT'] + '/archive'
        assert manager_dict['table_name'] == 'archive'
        assert 'extraTemp1' in dict(manager_dict['schema'])
        destination = weewx.manager.get_manager_dict_from_config(action_config, 'wx_binding')
        assert destination['database_dict']['database_name'] == 'weewx.sdb'
        calls.append(action_namespace.action)

    namespace.database_action = inspect_config
    namespace.func(namespace)
    assert calls == [args[0]]
    assert config_dict.dict() == original


@pytest.mark.parametrize('driver', ['weedb.sqlite', 'weedb.mysql'])
def test_no_override(config_dict, parser, run_command, driver):
    config_dict['DatabaseTypes']['SQLite']['driver'] = driver
    calls = []

    def inspect_config(action_config, namespace):
        assert action_config.dict() == config_dict.dict()
        calls.append(namespace.action)

    namespace = parser.parse_args(['database', 'check'])
    namespace.database_action = inspect_config
    namespace.func(namespace)
    assert calls == ['check']


@pytest.mark.parametrize('filename,driver,message', [
    ('old.sdb', 'weedb.mysql', 'only available for SQLite'),
    ('', 'weedb.sqlite', 'must not be empty'),
])
def test_invalid_override(config_dict, parser, run_command, filename, driver, message):
    config_dict['DatabaseTypes']['SQLite']['driver'] = driver

    def unexpected_action(*args):
        pytest.fail('Invalid filename override reached the database action')

    namespace = parser.parse_args(['database', 'create', '--db-filename=' + filename, '-y'])
    namespace.database_action = unexpected_action
    with pytest.raises(SystemExit, match=message):
        namespace.func(namespace)


@pytest.mark.parametrize('absolute', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('dry_run', [False, True])
def test_reconfigure_file(config_dict, run_command, tmp_path, absolute, legacy, dry_run):
    if legacy:
        config_dict['Databases']['archive_sqlite'] = {
            'database_name': 'weewx.sdb', 'driver': 'weedb.sqlite',
            'root': str(tmp_path / 'archive'),
        }
    directory = tmp_path / ('backup' if absolute else 'archive')
    directory.mkdir()
    source_path = directory / 'old.sdb'
    with sqlite3.connect(str(source_path)) as connection:
        connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, '
                           'usUnits INTEGER, interval INTEGER, outTemp REAL)')
        connection.execute('INSERT INTO archive VALUES (1470000000, 1, 5, 68.0)')
    source_bytes = source_path.read_bytes()
    filename = str(source_path) if absolute else 'old.sdb'
    args = ['reconfigure', '--db-filename=' + filename, '-y']
    if dry_run:
        args.append('--dry-run')
    run_command(args)
    assert source_path.read_bytes() == source_bytes
    assert not (tmp_path / 'archive' / 'weewx.sdb').exists()
    destination_path = directory / 'old.sdb_new'
    if dry_run:
        assert not destination_path.exists()
    else:
        with sqlite3.connect(str(destination_path)) as connection:
            assert connection.execute('SELECT dateTime, usUnits, interval, outTemp, extraTemp1 '
                                      'FROM archive').fetchall() == [(1470000000, 16, 5, 20.0, None)]


@pytest.mark.parametrize('binding', ['wx_binding', 'other_binding'])
@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('destination_exists', [False, True])
def test_transfer_preserves_destination(config_dict, run_command, tmp_path, binding,
                                         dry_run, destination_exists):
    directory = tmp_path / 'archive'
    directory.mkdir()
    source_path = directory / 'old.sdb'
    with sqlite3.connect(str(source_path)) as connection:
        connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, '
                           'usUnits INTEGER, interval INTEGER, outTemp REAL)')
        connection.execute('INSERT INTO archive VALUES (1470000000, 1, 5, 68.0)')
    source_bytes = source_path.read_bytes()
    destination_path = directory / 'weewx.sdb'
    if destination_exists:
        with sqlite3.connect(str(destination_path)) as connection:
            connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, '
                               'usUnits INTEGER, interval INTEGER, outTemp REAL)')
            connection.execute('INSERT INTO archive VALUES (1470000300, 1, 5, 70.0)')
        destination_bytes = destination_path.read_bytes()
    args = ['transfer', '--binding=' + binding, '--dest-binding=wx_binding',
            '--db-filename=old.sdb', '-y']
    if dry_run:
        args.append('--dry-run')
    run_command(args)
    assert source_path.read_bytes() == source_bytes
    if dry_run:
        if destination_exists:
            assert destination_path.read_bytes() == destination_bytes
        else:
            assert not destination_path.exists()
    else:
        with sqlite3.connect(str(destination_path)) as connection:
            expected = [(68.0,), (70.0,)] if destination_exists else [(68.0,)]
            assert connection.execute('SELECT outTemp FROM archive ORDER BY dateTime').fetchall() \
                   == expected


@pytest.mark.parametrize('source_exists', [False, True])
@pytest.mark.parametrize('destination_exists', [False, True])
def test_reconfigure_invalid_source(run_command, tmp_path, source_exists, destination_exists):
    directory = tmp_path / 'archive'
    directory.mkdir()
    if source_exists:
        with sqlite3.connect(str(directory / 'old.sdb')) as connection:
            connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, '
                               'usUnits INTEGER, interval INTEGER, outTemp REAL)')
    destination_path = directory / 'old.sdb_new'
    if destination_exists:
        destination_path.write_bytes(b'existing destination must not be deleted')
    if source_exists:
        run_command(['reconfigure', '--db-filename=old.sdb', '-y'])
    else:
        with pytest.raises(weedb.NoDatabaseError):
            run_command(['reconfigure', '--db-filename=old.sdb', '-y'])
    if destination_exists:
        assert destination_path.read_bytes() == b'existing destination must not be deleted'
    else:
        assert not destination_path.exists()


def test_cli_reconfigure(config_dict, tmp_path):
    directory = tmp_path / 'archive'
    directory.mkdir()
    source_path = directory / 'old.sdb'
    with sqlite3.connect(str(source_path)) as connection:
        connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, '
                           'usUnits INTEGER, interval INTEGER, outTemp REAL)')
        connection.execute('INSERT INTO archive VALUES (1470000000, 1, 5, 68.0)')
    source_bytes = source_path.read_bytes()
    config_path = tmp_path / 'weewx.conf'
    config_dict.filename = str(config_path)
    config_dict['Logging'] = {'root': {'handlers': ['console'], 'level': 'CRITICAL'}}
    config_dict.write()
    config_bytes = config_path.read_bytes()
    command = [sys.executable, weectl.__file__, 'database', 'reconfigure',
               '--config=' + str(config_path), '--db-filename=old.sdb', '-y']
    destination_path = directory / 'old.sdb_new'
    for extra_args in [['--dry-run'], []]:
        result = subprocess.run(command + extra_args, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert config_path.read_bytes() == config_bytes
        assert source_path.read_bytes() == source_bytes
        assert not (directory / 'weewx.sdb').exists()
        if extra_args:
            assert not destination_path.exists()
        else:
            with sqlite3.connect(str(destination_path)) as connection:
                assert connection.execute('SELECT outTemp, extraTemp1 FROM archive').fetchall() \
                       == [(20.0, None)]
