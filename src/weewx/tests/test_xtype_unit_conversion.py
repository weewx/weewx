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


class FahrenheitTemperature(weewx.xtypes.XType):
    def get_scalar(self, obs_type, record, db_manager, **options):
        if obs_type != 'dewpoint':
            raise weewx.UnknownType(obs_type)
        value = record['outTemp']
        if value is None:
            raise weewx.CannotCalculate(obs_type)
        if record['dateTime'] == STAMP:
            return weewx.units.ValueTuple(value * 1.8 + 32, 'degree_F', 'group_temperature')
        return weewx.units.ValueTuple(value, 'degree_C', 'group_temperature')


def test_derived_series_and_aggregates_convert_each_value(database):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([RECORD, dict(RECORD, dateTime=STAMP + 300, outTemp=0),
                           dict(RECORD, dateTime=STAMP + 600, outTemp=None)], log_success=False)
        xtype = FahrenheitTemperature()
        weewx.xtypes.xtypes.insert(0, xtype)
        try:
            span = (STAMP - 300, STAMP + 600)
            series = weewx.xtypes.get_series('dewpoint', span, manager)[2]
            assert series == ([20, 0, None], 'degree_C', 'group_temperature')
            for aggregate, expected in [('sum', 20), ('avg', 10), ('min', 0), ('max', 20),
                                         ('count', 2), ('mintime', STAMP + 300), ('maxtime', STAMP)]:
                actual = weewx.xtypes.get_aggregate('dewpoint', span, aggregate, manager)
                assert actual.value == pytest.approx(expected)
            assert weewx.xtypes.get_aggregate('dewpoint', span, 'avg', manager)[1:] == (
                'degree_C', 'group_temperature')
        finally:
            weewx.xtypes.xtypes.remove(xtype)
