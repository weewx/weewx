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


@pytest.mark.parametrize('energy_unit,output_unit', [('watt_hour', 'watt'),
                                                   ('kilowatt_hour', 'kilowatt'),
                                                   ('watt_second', 'watt')])
@pytest.mark.parametrize('values', [[None], [1000], [1000, None], [None, 2000], [1000, 2000]])
def test_energy_derivatives_preserve_missing_values_and_units(database, monkeypatch,
                                                             energy_unit, output_unit, values):
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energy', 'group_energy')
    monkeypatch.setitem(weewx.units.MetricWXUnits, 'group_energy', energy_unit)
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP + 300 * index, energy=value)
                           for index, value in enumerate(values)], log_success=False)
        result = weewx.xtypes.get_aggregate('energy', (STAMP, STAMP + 300), 'tderiv', manager)
        expected = (1000 / 300 * (1 if energy_unit == 'watt_second' else 3600)
                    if values == [1000, 2000] else None)
        if expected is None:
            assert result.value is None
        else:
            assert result.value == pytest.approx(expected)
        assert result[1:] == (output_unit, 'group_power')


def test_non_energy_derivative_does_not_claim_power_units(database):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([RECORD, dict(RECORD, dateTime=STAMP + 300, rain=6)], log_success=False)
        result = weewx.xtypes.get_aggregate('rain', (STAMP, STAMP + 300), 'tderiv', manager)
        assert result[1:] == ('mm', 'group_rain')
        assert weewx.units.StdUnitConverters[weewx.METRICWX].convert(result).value == pytest.approx(5 / 300)


def test_temperature_derivative_cannot_use_absolute_temperature_conversion(database):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, outTemp=10),
                           dict(RECORD, dateTime=STAMP + 300, outTemp=13)], log_success=False)
        with pytest.raises(weewx.UnknownAggregation):
            result = weewx.xtypes.get_aggregate('outTemp', (STAMP, STAMP + 300), 'tderiv', manager)
            weewx.units.StdUnitConverters[weewx.US].convert(result)
