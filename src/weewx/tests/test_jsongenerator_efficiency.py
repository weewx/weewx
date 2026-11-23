"""Check JSON output, update reuse, and memory bounds."""

import builtins
import json
import pathlib
import shutil
import tracemalloc
import types

import configobj
import pytest

import weewx.defaults
import weewx.jsongenerator
import weewx.manager
import weewx.station


def payloads(directory):
    result = {}
    for filename in sorted(directory.rglob('*.json')):
        value = json.loads(filename.read_text())
        if filename.name == 'index.json':
            value.pop('rebuilt', None)
        result[str(filename.relative_to(directory))] = value
    return result


def test_shared_boundaries_and_fresh_report_cache(tmp_path, monkeypatch):
    database = tmp_path / 'archive.sdb'
    observations = ('outTemp', 'inTemp', 'outHumidity', 'inHumidity')
    schema = {'table': [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
                        ('usUnits', 'INTEGER NOT NULL'), ('interval', 'INTEGER NOT NULL')]
                       + [(name, 'REAL') for name in observations],
              'day_summaries': [(name, 'scalar') for name in observations]}
    db_config = {'driver': 'weedb.sqlite', 'database_name': str(database)}
    first = 1761343200
    last = first + 4 * 86400
    with weewx.manager.DaySummaryManager.open_with_create(db_config, schema=schema) as manager:
        manager.addRecord([{'dateTime': stamp, 'usUnits': weewx.METRICWX, 'interval': 5,
                            'outTemp': stamp % 23, 'inTemp': 20,
                            'outHumidity': None if stamp % 11 == 0 else 50,
                            'inHumidity': 30}
                           for stamp in range(first + 300, last + 1, 300)],
                          log_success=False)
    config = configobj.ConfigObj({'WEEWX_ROOT': '/',
                                  'DataBindings': {'wx_binding': {'database': 'study',
                                      'manager': 'weewx.manager.DaySummaryManager'}},
                                  'Databases': {'study': db_config}}, interpolation=False)

    def make_generator(output, stamp):
        weewx.defaults.defaults.interpolation = False
        skin = configobj.ConfigObj(weewx.defaults.defaults.dict(), interpolation=False)
        skin.merge({'HTML_ROOT': str(output), 'REPORT_NAME': 'Sweep',
                     'data_binding': 'wx_binding', 'JSONGenerator': {
                         'include_daynight': False,
                         'JSONFiles': {'temperature': {'outTemp': {}, 'inTemp': {}},
                                       'humidity': {'outHumidity': {}, 'inHumidity': {}}},
                         'Archive': {'years': 0, 'days': 0, 'months': 1,
                                     'old_year_resolution': '4h', 'month_resolution': 900,
                                     'budget': 0, 'rebuild': 0}}})
        skin = configobj.ConfigObj(skin.dict(), interpolation=False)
        return weewx.jsongenerator.JSONGenerator(
            config, skin, stamp, True,
            weewx.station.StationInfo(latitude=52, longitude=13, altitude=[40, 'meter']))

    output = tmp_path / 'output'
    generator = make_generator(output, last - 300)
    original = weewx.jsongenerator._intervals
    calls = []

    def intervals(*args):
        calls.append(args)
        return original(*args)

    try:
        generator.start()
        backup = tmp_path / 'before-update'
        shutil.copytree(str(output), str(backup))
        monkeypatch.setattr(weewx.jsongenerator, '_intervals', intervals)
        generator.gen_ts = last
        generator.first_run = False
        generator.start()
        assert calls, 'The test did not extend any series'
        assert len(calls) == len(set(calls)), 'Series recalculated identical calendar intervals'
        updated = payloads(output)

        # Replaying the starting files simulates a retry. The same instance must
        # calculate this run's boundaries again, rather than retain its old cache.
        shutil.rmtree(str(output))
        shutil.copytree(str(backup), str(output))
        calls.clear()
        generator.start()
        assert calls, 'Calendar intervals leaked from the preceding report run'
        assert payloads(output) == updated

        fresh = make_generator(tmp_path / 'fresh', last)
        try:
            fresh.start()
            assert payloads(tmp_path / 'fresh') == updated
        finally:
            fresh.finalize()
    finally:
        generator.finalize()


def test_json_writer_avoids_per_value_writes(tmp_path, monkeypatch):
    filename = tmp_path / 'data.json'
    writes = []
    original_open = builtins.open

    class CountedFile:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, text):
            writes.append(len(text))
            return self.stream.write(text)

        def writelines(self, lines):
            return self.stream.writelines(lines)

    def counted_open(*args, **kwargs):
        return CountedFile(original_open(*args, **kwargs))

    monkeypatch.setattr(weewx.jsongenerator, 'open', counted_open, raising=False)
    data = {'unit': '°C', 'values': [None, 0, -1.5] * 1000}
    weewx.jsongenerator._write_json(str(filename), data)
    assert filename.read_text() == json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    assert len(writes) < 5, 'JSON writing still emitted thousands of separate fragments'
    assert not pathlib.Path(str(filename) + '.tmp').exists()


def test_json_writer_does_not_copy_the_whole_document(tmp_path):
    filename = tmp_path / 'large.json'
    data = {'unit': '°C', 'values': [None, 0, -1.5] * 100000}
    tracemalloc.start()
    try:
        weewx.jsongenerator._write_json(str(filename), data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert json.loads(filename.read_text()) == data
    assert peak < 512 * 1024, 'JSON writing allocated a second copy of the document'


def test_resume_cache_has_bounded_retained_memory(monkeypatch):
    generator = object.__new__(weewx.jsongenerator.JSONGenerator)
    generator.db_binder = types.SimpleNamespace(get_manager=lambda binding: None)
    generator._archive_resume = {}
    monkeypatch.setattr(generator, '_aggregate_line', lambda **options: None)
    line = {'options': {'data_binding': 'wx_binding'}, 'aggregate_interval': 300}
    tracemalloc.start()
    try:
        for day in range(1000):
            start = 1761343200 + day * 86400
            generator._archive_series(line, {}, start, start + 86400, 288, 300, None, (),
                                      None, {'newest': start + 86400})
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert retained < 64 * 1024, 'Resume cache retained calendar lists or grew without a bound'
