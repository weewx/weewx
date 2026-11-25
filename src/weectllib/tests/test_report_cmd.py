#
#    Copyright (c) 2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Test the parser for 'weectl report enable' and 'weectl report disable'."""
import argparse
import contextlib
import io
import unittest

import weectllib.report_cmd as report_cmd


def make_parser():
    parser = argparse.ArgumentParser(prog='weectl')
    subparsers = parser.add_subparsers(dest='cmd')
    report_cmd.add_subparser(subparsers)
    return parser


class ReportCmdParserTest(unittest.TestCase):

    def test_enable(self):
        ns = make_parser().parse_args(['report', 'enable', 'SeasonsReport'])
        self.assertEqual(ns.report, 'SeasonsReport')
        self.assertIs(ns.action_func, report_cmd.enable_report)
        self.assertFalse(ns.dry_run)
        self.assertFalse(ns.no_backup)

    def test_disable_with_options(self):
        ns = make_parser().parse_args(['report', 'disable', 'SeasonsReport',
                                       '--config=/tmp/weewx.conf', '--dry-run', '--no-backup'])
        self.assertEqual(ns.report, 'SeasonsReport')
        self.assertEqual(ns.config, '/tmp/weewx.conf')
        self.assertIs(ns.action_func, report_cmd.disable_report)
        self.assertTrue(ns.dry_run)
        self.assertTrue(ns.no_backup)

    def test_name_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                make_parser().parse_args(['report', 'enable'])

    def test_only_one_name(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                make_parser().parse_args(['report', 'enable', 'A', 'B'])

    def test_help_lists_actions(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                make_parser().parse_args(['report', '--help'])
        self.assertIn('enable', out.getvalue())
        self.assertIn('disable', out.getvalue())


if __name__ == '__main__':
    unittest.main()
