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
