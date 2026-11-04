#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import pytest

import weewx
import weewx.manager
import weewx.units
import weewx.xtypes


SCHEMA = [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'), ('usUnits', 'INTEGER NOT NULL'),
          ('interval', 'INTEGER NOT NULL'), ('rain', 'REAL'), ('outTemp', 'REAL'),
          ('energy', 'REAL'), ('windSpeed', 'REAL'), ('windDir', 'REAL'),
          ('windGust', 'REAL'), ('windGustDir', 'REAL')]
STAMP = 1704110400
RECORD = {'dateTime': STAMP, 'usUnits': weewx.METRICWX, 'interval': 5,
          'rain': 1.0, 'outTemp': 20.0, 'energy': 1000.0}


@pytest.mark.parametrize('observation', ['windvec', 'windgustvec'])
def test_vector_counts_accept_strict_mysql_and_empty_intervals(database, observation):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        if manager.connection.dbtype == 'mysql':
            mode = manager.getSql('SELECT @@SESSION.sql_mode')[0]
            if 'ONLY_FULL_GROUP_BY' not in mode:
                manager.connection.execute("SET SESSION sql_mode = ?", (mode + ',ONLY_FULL_GROUP_BY',))
        manager.addRecord([dict(RECORD, dateTime=STAMP + 300 * index,
                                windSpeed=speed, windGust=speed, windDir=direction,
                                windGustDir=direction)
                           for index, (speed, direction) in enumerate([(3, 90), (0, None), (None, 90)])],
                          log_success=False)
        assert weewx.xtypes.get_aggregate(observation, (STAMP - 1, STAMP + 600),
                                           'count', manager) == (2, 'count', 'group_count')
        assert weewx.xtypes.get_aggregate(observation, (STAMP + 600, STAMP + 1200),
                                           'count', manager) == (0, 'count', 'group_count')
