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
          ('energy', 'REAL'), ('windrun', 'REAL'), ('barometer', 'REAL'),
          ('outHumidity', 'REAL'), ('windSpeed', 'REAL'), ('windDir', 'REAL'),
          ('windGust', 'REAL'), ('windGustDir', 'REAL')]
STAMP = 1704110400
RECORD = {'dateTime': STAMP, 'usUnits': weewx.METRICWX, 'interval': 5,
          'rain': 1.0, 'outTemp': 20.0, 'energy': 1000.0}


@pytest.mark.parametrize('energy_group', ['group_energy', 'group_energy2'])
@pytest.mark.parametrize('energy_unit,output_unit', [('watt_hour', 'watt'),
                                                   ('kilowatt_hour', 'kilowatt'),
                                                   ('watt_second', 'watt')])
@pytest.mark.parametrize('values', [[], [None], [1000], [1000, None], [None, 2000],
                                   [1000, 2000], [1000, 1000], [2000, 1000]])
def test_energy_derivatives_preserve_missing_values_and_units(database, monkeypatch,
                                                             energy_group, energy_unit,
                                                             output_unit, values):
    monkeypatch.setitem(weewx.units.obs_group_dict, 'energy', energy_group)
    monkeypatch.setitem(weewx.units.MetricWXUnits, energy_group, energy_unit)
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP + 300 * index, energy=value)
                           for index, value in enumerate(values)], log_success=False)
        result = weewx.xtypes.get_aggregate('energy', (STAMP, STAMP + 300), 'tderiv', manager)
        expected = ((values[1] - values[0]) / 300
                    * (1 if energy_unit == 'watt_second' else 3600)
                    if len(values) == 2 and None not in values else None)
        if expected is None:
            assert result.value is None
        else:
            assert result.value == pytest.approx(expected)
        assert result[1:] == ((output_unit, 'group_power') if values else (None, None))


@pytest.mark.parametrize('unit_system,rain_unit,distance_unit,pressure_unit', [
    (weewx.US, 'inch_per_hour', 'mile_per_hour', 'inHg_per_hour'),
    (weewx.METRIC, 'cm_per_hour', 'km_per_hour', 'mbar_per_hour'),
    (weewx.METRICWX, 'mm_per_hour', 'km_per_hour', 'mbar_per_hour')])
@pytest.mark.parametrize('obs_type,output_group', [('rain', 'group_rainrate'),
                                                 ('windrun', 'group_speed'),
                                                 ('barometer', 'group_pressurerate')])
@pytest.mark.parametrize('values', [[], [None], [1.0], [1.0, None], [None, 6.0],
                                   [1.0, 6.0], [1.0, 1.0], [6.0, 1.0]])
def test_derivative_units_and_missing_values(database, unit_system, rain_unit,
                                             distance_unit, pressure_unit,
                                             obs_type, output_group, values):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP + 300 * index,
                                usUnits=unit_system, **{obs_type: value})
                           for index, value in enumerate(values)], log_success=False)
        result = weewx.xtypes.get_aggregate(obs_type, (STAMP, STAMP + 300), 'tderiv', manager)
        if not values:
            assert result == (None, None, None)
            return
        output_unit = {'rain': rain_unit, 'windrun': distance_unit,
                       'barometer': pressure_unit}[obs_type]
        result = weewx.units.convert(result, output_unit)
        assert result[1:] == (output_unit, output_group)
        if len(values) == 2 and None not in values:
            assert result.value == pytest.approx((values[1] - values[0]) * 12)
        else:
            assert result.value is None


@pytest.mark.parametrize('unit_system', [weewx.US, weewx.METRIC, weewx.METRICWX])
@pytest.mark.parametrize('obs_type,first,last,unit,expected,output_unit,output_group', [
    ('rain', 1.0, 6.0, 'mm', 60 / 25.4, 'inch_per_hour', 'group_rainrate'),
    ('windrun', 1.0, 2.0, 'km', 12 / 1.609344, 'mile_per_hour', 'group_speed'),
    ('barometer', 1000.0, 1003.0, 'mbar', 36 * weewx.units.INHG_PER_MBAR,
     'inHg_per_hour', 'group_pressurerate')])
def test_derivative_report_conversion(database, unit_system, obs_type, first, last,
                                      unit, expected, output_unit, output_group):
    source_group = weewx.units.getUnitGroup(obs_type)
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        for index, value in enumerate([first, last]):
            stored = weewx.units.convertStd(weewx.units.ValueTuple(value, unit, source_group),
                                           unit_system)
            manager.addRecord(dict(RECORD, dateTime=STAMP + 300 * index,
                                   usUnits=unit_system, **{obs_type: stored.value}),
                              log_success=False)
        result = weewx.xtypes.get_aggregate(obs_type, (STAMP, STAMP + 300), 'tderiv', manager)
        report = weewx.units.ValueHelper(result, converter=weewx.units.StdUnitConverters[weewx.US])
        assert report.value_t[1:] == (output_unit, output_group)
        # Distance and speed converters use slightly different rounded mile lengths.
        assert report.raw == pytest.approx(expected, rel=1e-5)


@pytest.mark.parametrize('obs_type,source_group,source_unit,first,last,expected,output_unit,output_group', [
    ('energy', 'group_energy', 'mega_joule', 0.0, 3.0, 10000.0, 'watt', 'group_power'),
    ('windrun', 'group_distance', 'meter', 0.0, 300.0, 1.0, 'meter_per_second', 'group_speed'),
    ('windrun', 'group_distance', 'astronomical_unit', 0.0, 1.0, 149597870700 / 300,
     'meter_per_second', 'group_speed'),
    ('barometer', 'group_pressure', 'hPa', 1000.0, 1003.0, 36.0,
     'mbar_per_hour', 'group_pressurerate'),
    ('barometer', 'group_pressure', 'kPa', 100.0, 100.3, 36.0,
     'mbar_per_hour', 'group_pressurerate'),
    ('barometer', 'group_pressure', 'mmHg', 750.0, 753.0, 36.0,
     'mmHg_per_hour', 'group_pressurerate')])
def test_derivative_custom_units(database, monkeypatch, obs_type, source_group,
                                 source_unit, first, last, expected, output_unit, output_group):
    monkeypatch.setitem(weewx.units.obs_group_dict, obs_type, source_group)
    monkeypatch.setitem(weewx.units.MetricWXUnits, source_group, source_unit)
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, dateTime=STAMP + 300 * index, **{obs_type: value})
                           for index, value in enumerate([first, last])], log_success=False)
        result = weewx.xtypes.get_aggregate(obs_type, (STAMP, STAMP + 300), 'tderiv', manager)
        converted = weewx.units.convert(result, output_unit)
        assert converted[1:] == (output_unit, output_group)
        assert converted.value == pytest.approx(expected)


@pytest.mark.parametrize('obs_type', ['outTemp', 'windSpeed', 'windDir', 'outHumidity', 'dateTime'])
def test_derivatives_without_rate_units_are_rejected(database, obs_type):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, windSpeed=1, windDir=10, outHumidity=40),
                           dict(RECORD, dateTime=STAMP + 300, outTemp=23,
                                windSpeed=2, windDir=20, outHumidity=50)], log_success=False)
        with pytest.raises(weewx.UnknownAggregation):
            weewx.xtypes.get_aggregate(obs_type, (STAMP, STAMP + 300), 'tderiv', manager)


@pytest.mark.parametrize('source_group,source_unit', [('group_rain', 'unknown_unit'),
                                                   ('group_altitude', 'meter')])
def test_unsupported_derivative_unit_or_group(database, monkeypatch, source_group, source_unit):
    monkeypatch.setitem(weewx.units.obs_group_dict, 'windrun', source_group)
    monkeypatch.setitem(weewx.units.MetricWXUnits, source_group, source_unit)
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([dict(RECORD, windrun=1.0),
                           dict(RECORD, dateTime=STAMP + 300, windrun=2.0)], log_success=False)
        with pytest.raises(weewx.UnknownAggregation):
            weewx.xtypes.get_aggregate('windrun', (STAMP, STAMP + 300), 'tderiv', manager)
