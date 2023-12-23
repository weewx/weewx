#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Manage and run WeeWX reports."""
import sys
import time

import weecfg
import weectllib
import weectllib.report_actions
from weeutil.weeutil import bcolors

report_list_usage = f"""{bcolors.BOLD}weectl report list
            [--config=FILENAME]{bcolors.ENDC}"""
report_run_usage = f"""  {bcolors.BOLD}weectl report run [NAME ...]
            [--config=FILENAME]
            [--epoch=EPOCH_TIME | --date=YYYY-mm-dd --time=HH:MM]{bcolors.ENDC}"""

report_usage = '\n     '.join((report_list_usage, report_run_usage))

run_epilog = """You may specify either an epoch time (option --epoch), or a date and time combo 
(options --date and --time together), but not both."""


def add_subparser(subparsers):
    report_parser = subparsers.add_parser('report',
                                          usage=report_usage,
                                          description='Manages and runs WeeWX reports',
                                          help="List and run WeeWX reports.")
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = report_parser.add_subparsers(dest='action',
                                                 prog='weectl report',
                                                 title="Which action to take")

    # ---------- Action 'list' ----------
    list_report_parser = action_parser.add_parser('list',
                                                  description="List all installed reports",
                                                  usage=report_list_usage,
                                                  help='List all installed reports')
    list_report_parser.add_argument('--config',
                                    metavar='FILENAME',
                                    help=f'Path to configuration file. '
                                         f'Default is "{weecfg.default_config_path}".')
    list_report_parser.set_defaults(func=weectllib.dispatch)
    list_report_parser.set_defaults(action_func=list_reports)

    # ---------- Action 'run' ----------
    run_report_parser = action_parser.add_parser('run',
                                                 description="Runs reports",
                                                 usage=report_run_usage,
                                                 help='Run one or more reports',
                                                 epilog=run_epilog)
    run_report_parser.add_argument('--config',
                                   metavar='FILENAME',
                                   help=f'Path to configuration file. '
                                        f'Default is "{weecfg.default_config_path}".')
    run_report_parser.add_argument("--epoch", metavar="EPOCH_TIME",
                                   help="Time of the report in unix epoch time")
    run_report_parser.add_argument("--date", metavar="YYYY-mm-dd",
                                   type=lambda d: time.strptime(d, '%Y-%m-%d'),
                                   help="Date for the report")
    run_report_parser.add_argument("--time", metavar="HH:MM",
                                   type=lambda t: time.strptime(t, '%H:%M'),
                                   help="Time of day for the report")
    run_report_parser.add_argument('reports',
                                   nargs="*",
                                   metavar='NAME',
                                   help="Reports to be run, separated by spaces. "
                                        "Names are case sensitive. "
                                        "If not given, all enabled reports will be run.")
    run_report_parser.set_defaults(func=weectllib.dispatch)
    run_report_parser.set_defaults(action_func=run_reports)


def list_reports(config_dict, _):
    weectllib.report_actions.list_reports(config_dict)


def run_reports(config_dict, namespace):
    # Presence of --date requires --time and v.v.
    if namespace.date and not namespace.time or namespace.time and not namespace.date:
        sys.exit("Must specify both --date and --time.")
    # Can specify the time as either unix epoch time, or explicit date and time, but not both
    if namespace.epoch and namespace.date:
        sys.exit("The time of the report must be specified either as unix epoch time, "
                 "or with an explicit date and time, but not both.")

    weectllib.report_actions.run_reports(config_dict,
                                         epoch=namespace.epoch,
                                         report_date=namespace.date, report_time=namespace.time,
                                         reports=namespace.reports)
