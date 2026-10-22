#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import contextlib
import pathlib
import threading

import weewx.reportengine


def test_overlapping_report_engines_wait_before_changing_directory(tmp_path, monkeypatch):
    initial = pathlib.Path.cwd()
    for skin in ('first', 'second'):
        (tmp_path / skin).mkdir()
    first_ready = threading.Event()
    second_attempt = threading.Event()
    observed = []
    errors = []
    original_locale = weewx.reportengine.set_locale

    @contextlib.contextmanager
    def set_locale(name):
        if threading.current_thread().name == 'second':
            second_attempt.set()
        with original_locale(name) as current:
            yield current

    class Generator:
        def __init__(self, config, skin, *args):
            self.skin = skin['skin']

        def start(self):
            if self.skin == 'first':
                first_ready.set()
                if not second_attempt.wait(5):
                    errors.append('second report never attempted locale lock')
            observed.append((self.skin, pathlib.Path.cwd()))

        def finalize(self):
            pass

    def skin_dict(config, report):
        return {'SKIN_ROOT': '.', 'skin': report, 'lang': 'C',
                'Generators': {'generator_list': ['test.Generator']}}

    monkeypatch.setattr(weewx.reportengine, 'set_locale', set_locale)
    monkeypatch.setattr(weewx.reportengine, 'build_skin_dict', skin_dict)
    monkeypatch.setattr(weewx.reportengine.weeutil.weeutil, 'get_object', lambda name: Generator)
    config = {'WEEWX_ROOT': str(tmp_path), 'StdReport': {}}

    def run(report):
        try:
            engine = weewx.reportengine.StdReportEngine(config, None, gen_ts=1704110400)
            engine.run(reports=[report])
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=run, args=('first',), name='first')
    second = threading.Thread(target=run, args=('second',), name='second')
    first.start()
    try:
        assert first_ready.wait(5)
        second.start()
    finally:
        first.join(10)
        if second.ident is not None:
            second.join(10)
    assert not first.is_alive() and not second.is_alive()
    assert not errors
    assert observed == [('first', tmp_path / 'first'), ('second', tmp_path / 'second')]
    assert pathlib.Path.cwd() == initial
