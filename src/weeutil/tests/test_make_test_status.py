import pathlib
import subprocess
import sys

import pytest


@pytest.mark.parametrize('exit_code', [0, 1, 2, 3, 4, 5, 137])
def test_make_propagates_pytest_status_without_log_markers(tmp_path, exit_code):
    root = pathlib.Path(__file__).resolve().parents[3]
    runner = tmp_path / 'runner.py'
    runner.write_text('import sys\nprint("finished")\nsys.exit(%d)\n' % exit_code)
    command = ["make", "test", "SUITE=unused", "BLDDIR=" + str(tmp_path / 'build'),
               "PYTHON=" + sys.executable, "PYTEST=" + sys.executable + ' ' + str(runner)]
    result = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert (result.returncode == 0) == (exit_code == 0), result.stdout.decode()
    assert (tmp_path / 'build' / 'test-results').read_text().count('finished') == 1
    if exit_code:
        assert b'no failures' not in result.stdout


@pytest.mark.parametrize('marker', ['FAILURES', 'ERRORS'])
def test_make_accepts_passing_pytest_with_error_words_in_filename(tmp_path, marker):
    root = pathlib.Path(__file__).resolve().parents[3]
    suite = tmp_path / ('test_%s.py' % marker)
    suite.write_text('def test_success():\n    assert True\n')
    result = subprocess.run(['make', 'test', 'SUITE=' + str(suite),
                             'BLDDIR=' + str(tmp_path / 'build'), 'PYTHON=' + sys.executable,
                             'PYTEST=' + sys.executable + ' -m pytest -q'], cwd=str(root),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout.decode()
    assert b'no failures' in result.stdout
    assert '1 passed' in (tmp_path / 'build' / 'test-results').read_text()


def test_make_keeps_running_remaining_suites_after_failure(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[3]
    runner = tmp_path / 'runner.py'
    runner.write_text('import sys\nprint(sys.argv[1])\nsys.exit(sys.argv[1] == "first")\n')
    result = subprocess.run(['make', 'test', 'SUITE=first second',
                             'BLDDIR=' + str(tmp_path / 'build'), 'PYTHON=' + sys.executable,
                             'PYTEST=' + sys.executable + ' ' + str(runner)], cwd=str(root),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode != 0
    assert b'running second' in result.stdout
    assert '\nsecond\n' in (tmp_path / 'build' / 'test-results').read_text()


def test_make_prints_failure_summary_before_exiting(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[3]
    runner = tmp_path / 'runner.py'
    runner.write_text('import sys\nprint("FAIL: weather regression")\nsys.exit(1)\n')
    result = subprocess.run(['make', 'test', 'SUITE=unused',
                             'BLDDIR=' + str(tmp_path / 'build'), 'PYTHON=' + sys.executable,
                             'PYTEST=' + sys.executable + ' ' + str(runner)], cwd=str(root),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode != 0
    assert b'FAIL: weather regression' in result.stdout
