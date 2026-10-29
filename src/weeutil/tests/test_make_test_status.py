import pathlib
import subprocess
import sys

import pytest


@pytest.mark.parametrize('exit_code', [0, 1, 2, 3, 4, 5, 137])
def test_make_propagates_pytest_status(tmp_path, exit_code):
    root = pathlib.Path(__file__).resolve().parents[3]
    runner = tmp_path / 'runner.py'
    runner.write_text('import sys\nsys.exit(%d)\n' % exit_code)
    command = ["make", "test", "SUITE=unused",
               "PYTHON=" + sys.executable, "PYTEST=" + sys.executable + ' ' + str(runner)]
    result = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert (result.returncode == 0) == (exit_code == 0), result.stdout.decode()

