from unittest import mock

import weeutil.weeutil
import weewx.tags

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


class DerivedTemperature(weewx.xtypes.XType):
    def get_scalar(self, obs_type, record, db_manager, **options):
        if obs_type != 'dewpoint':
            raise weewx.UnknownType(obs_type)
        return weewx.units.ValueTuple(record['outTemp'] / 2, 'degree_C', 'group_temperature')


@pytest.mark.parametrize('binding', [None, 'wx_binding', 'alt_binding'])
def test_derived_fields_reuse_iterator_record(database, binding):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord([RECORD, dict(RECORD, dateTime=STAMP + 300, outTemp=0)], log_success=False)
        xtype = DerivedTemperature()
        weewx.xtypes.xtypes.insert(0, xtype)
        binder = weewx.tags.TimespanBinder(weeutil.weeutil.TimeSpan(STAMP - 1, STAMP + 300),
                                          lambda name: manager, data_binding=binding,
                                          converter=weewx.units.StdUnitConverters[weewx.METRICWX])
        try:
            with mock.patch.object(manager, 'getRecord', wraps=manager.getRecord) as lookup:
                assert [(row.outTemp.raw, row.dewpoint.raw) for row in binder.records()] == [
                    (20, 10), (0, 0)]
                assert lookup.call_count == 0
        finally:
            weewx.xtypes.xtypes.remove(xtype)


def test_supplied_record_does_not_cross_bindings_or_timestamps(database):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        xtype = DerivedTemperature()
        weewx.xtypes.xtypes.insert(0, xtype)
        try:
            for binding, stamp in [('other', STAMP), (None, STAMP + 300)]:
                current = weewx.tags.CurrentObj(lambda name: manager, binding, STAMP,
                                                None, weewx.units.StdUnitConverters[weewx.METRICWX],
                                                record=dict(RECORD, dateTime=stamp, outTemp=100))
                assert current.dewpoint.raw == 10
        finally:
            weewx.xtypes.xtypes.remove(xtype)


def test_partial_current_record_still_looks_up_derived_inputs(database):
    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        xtype = DerivedTemperature()
        weewx.xtypes.xtypes.insert(0, xtype)
        try:
            current = weewx.tags.CurrentObj(lambda name: manager, None, STAMP, None,
                                            weewx.units.StdUnitConverters[weewx.METRICWX],
                                            record={'dateTime': STAMP, 'usUnits': weewx.METRICWX})
            assert current.dewpoint.raw == 10
        finally:
            weewx.xtypes.xtypes.remove(xtype)


def test_extension_cannot_mutate_later_attribute_reads(database):
    class MutatingTemperature(DerivedTemperature):
        def get_scalar(self, obs_type, record, db_manager, **options):
            result = super().get_scalar(obs_type, record, db_manager, **options)
            record['outTemp'] = 999
            return result

    with weewx.manager.Manager.open_with_create(database, schema=SCHEMA) as manager:
        manager.addRecord(RECORD, log_success=False)
        xtype = MutatingTemperature()
        weewx.xtypes.xtypes.insert(0, xtype)
        binder = weewx.tags.TimespanBinder(weeutil.weeutil.TimeSpan(STAMP - 1, STAMP),
                                          lambda name: manager,
                                          converter=weewx.units.StdUnitConverters[weewx.METRICWX])
        try:
            row = next(binder.records())
            assert row.dewpoint.raw == 10
            assert row.outTemp.raw == 20
        finally:
            weewx.xtypes.xtypes.remove(xtype)
