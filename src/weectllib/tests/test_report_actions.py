#
#    Copyright (c) 2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Test enabling and disabling reports."""
import glob
import os
import shutil
import tempfile
import unittest

import configobj

import weectllib.report_actions as report_actions

CONFIG = """[StdReport]
    [[Defaults]]
        unit_system = us
    [[SeasonsReport]]
        skin = Seasons
        enable = True
    [[NoEnableReport]]
        skin = Other
"""


class ReportEnableTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, 'weewx.conf')
        with open(self.path, 'w') as fd:
            fd.write(CONFIG)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def load(self):
        config_dict = configobj.ConfigObj(self.path, encoding='utf-8')
        config_dict['config_path'] = self.path
        # As set by weeutil.startup when the configuration file is read
        config_dict['WEEWX_ROOT'] = self.tmpdir
        return config_dict

    def on_disk(self, name):
        return configobj.ConfigObj(self.path)['StdReport'][name].get('enable')

    def backups(self):
        return [f for f in glob.glob(self.path + '*') if f != self.path]

    def test_disable_then_enable(self):
        report_actions.set_report_enable(self.load(), 'SeasonsReport', False)
        self.assertEqual(self.on_disk('SeasonsReport'), 'False')
        self.assertEqual(len(self.backups()), 1)
        report_actions.set_report_enable(self.load(), 'SeasonsReport', True)
        self.assertEqual(self.on_disk('SeasonsReport'), 'True')

    def test_already_in_state(self):
        before = os.stat(self.path).st_mtime_ns
        report_actions.set_report_enable(self.load(), 'SeasonsReport', True)
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)
        self.assertEqual(self.backups(), [])

    def test_no_backup(self):
        report_actions.set_report_enable(self.load(), 'SeasonsReport', False, no_backup=True)
        self.assertEqual(self.on_disk('SeasonsReport'), 'False')
        self.assertEqual(self.backups(), [])

    def test_dry_run(self):
        report_actions.set_report_enable(self.load(), 'SeasonsReport', False, dry_run=True)
        self.assertEqual(self.on_disk('SeasonsReport'), 'True')
        self.assertEqual(self.backups(), [])

    def test_unknown_and_defaults(self):
        for name in ('Nonexistent', 'Defaults', 'seasonsreport'):
            with self.assertRaises(SystemExit):
                report_actions.set_report_enable(self.load(), name, False)
        self.assertEqual(self.on_disk('SeasonsReport'), 'True')
        self.assertEqual(self.backups(), [])

    def test_missing_enable_means_enabled(self):
        # Enabling is a no-op, as the default is enabled
        report_actions.set_report_enable(self.load(), 'NoEnableReport', True)
        self.assertIsNone(self.on_disk('NoEnableReport'))
        report_actions.set_report_enable(self.load(), 'NoEnableReport', False)
        self.assertEqual(self.on_disk('NoEnableReport'), 'False')


if __name__ == '__main__':
    unittest.main()
