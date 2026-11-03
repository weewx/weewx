#
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test where 'weectl debug' writes its output."""

import contextlib
import sys

import weectllib.debug_actions


def test_debug_to_stdout_leaves_it_open(monkeypatch, capsys):
    """Without an output path, the report goes to stdout, which must stay usable afterwards."""
    # Each generator would need a real station. All that matters here is the stream they get.
    monkeypatch.setattr(weectllib.debug_actions, 'generate_sys_info',
                        lambda fd: print('report', file=fd))
    for name in ['generate_weewx_info', 'generate_extension_info', 'generate_archive_info',
                 'generate_debug_conf']:
        monkeypatch.setattr(weectllib.debug_actions, name, lambda *args: None)

    # Python 3.6 does not have contextlib.nullcontext. Take it away from newer versions as well,
    # so that this test finds a use of it on all of them.
    with monkeypatch.context() as m:
        m.delattr(contextlib, 'nullcontext', raising=False)
        weectllib.debug_actions.debug({'config_path': 'unused'})

    assert not sys.stdout.closed
    assert capsys.readouterr().out == 'report\n'
