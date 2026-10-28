#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
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


@pytest.mark.parametrize('table', ['archive', 'secondary'])
@pytest.mark.parametrize('decoy', [False, True])
def test_difference_and_derivative_use_only_selected_table_and_interval(database, table, decoy):
    with weewx.manager.Manager.open_with_create(database, table_name=table, schema=SCHEMA) as manager:
        manager.addRecord([RECORD, dict(RECORD, dateTime=STAMP + 300, rain=6),
                           dict(RECORD, dateTime=STAMP + 7200, rain=8)], log_success=False)
        if decoy and table != 'archive':
            manager.connection.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY, rain REAL)')
            for stamp, rain in [(STAMP, 100), (STAMP + 300, 101)]:
                manager.connection.execute('INSERT INTO archive VALUES (?, ?)', (stamp, rain))
        for aggregate, expected in [('diff', 5), ('tderiv', 5 / 300)]:
            assert weewx.xtypes.get_aggregate('rain', (STAMP, STAMP + 300),
                                               aggregate, manager).value == pytest.approx(expected)
            assert weewx.xtypes.get_aggregate('rain', (STAMP + 600, STAMP + 3600),
                                               aggregate, manager).value is None
        assert weewx.xtypes.get_aggregate('rain', (STAMP + 200, STAMP + 400),
                                           'diff', manager).value == 0


@pytest.fixture(params=[('watt_second', 'group_energy2', 'watt', 2.0),
                       ('watt_hour', 'group_energy', 'watt', 7200.0),
                       ('kilowatt_hour', 'group_energy', 'kilowatt', 7200.0)])
def energy_parameters(request, monkeypatch):
    unit, group, power_unit, power = request.param
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energy', group)
    monkeypatch.setitem(weewx.units.MetricWXUnits, group, unit)
    return unit, group, power_unit, power


@pytest.mark.parametrize('table', ['archive', 'secondary'])
def test_difference_and_derivative_skip_null_values(database, table, energy_parameters):
    unit, group, power_unit, power = energy_parameters
    readings = [(-300, 9000.0), (0, None), (6, 0.0), (120, 1500.0),
                (300, None), (306, 600.0), (600, None), (900, 30000.0)]
    with weewx.manager.Manager.open_with_create(database, table_name=table, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP + offset, energy=value)
                           for offset, value in readings], log_success=False)
        timespan = (STAMP, STAMP + 600)
        assert weewx.xtypes.get_aggregate('energy', timespan, 'diff', manager) \
            == weewx.units.ValueTuple(600.0, unit, group)
        assert weewx.xtypes.get_aggregate('energy', timespan, 'tderiv', manager) \
            == weewx.units.ValueTuple(power, power_unit, 'group_power')


@pytest.mark.parametrize('readings, difference', [([], None),
                                                ([(0, None), (300, None)], None),
                                                ([(0, None), (6, 0.0), (300, None)], 0.0)],
                         ids=['empty', 'all_null', 'one_value'])
def test_difference_and_derivative_with_insufficient_values(database, monkeypatch,
                                                           readings, difference):
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energy', 'group_energy2')
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP - 300, energy=9000.0),
                           dict(RECORD, dateTime=STAMP + 900, energy=30000.0)]
                          + [dict(RECORD, dateTime=STAMP + offset, energy=value)
                             for offset, value in readings], log_success=False)
        timespan = (STAMP, STAMP + 600)
        assert weewx.xtypes.get_aggregate('energy', timespan, 'diff', manager) \
            == weewx.units.ValueTuple(difference, 'watt_second', 'group_energy2')
        assert weewx.xtypes.get_aggregate('energy', timespan, 'tderiv', manager) \
            == weewx.units.ValueTuple(None, 'watt', 'group_power')
