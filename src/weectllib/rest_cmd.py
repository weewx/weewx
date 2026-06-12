#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""List RESTful services and force uploads on demand."""

import weecfg
import weectllib
import weectllib.rest_actions
from weeutil.weeutil import bcolors

rest_list_usage = f"""{bcolors.BOLD}weectl rest list
            [--config=FILENAME]{bcolors.ENDC}
"""
rest_run_usage = f"""  {bcolors.BOLD}weectl rest run [NAME ...]
            [--config=FILENAME]{bcolors.ENDC}
"""

rest_usage = '\n     '.join((rest_list_usage, rest_run_usage))

run_epilog = """In normal operation, WeeWX uploads to RESTful services only when a new archive
record arrives. This command forces an upload of the most recent archive record,
irrespective of the normal posting schedule. Use 'weectl rest list' to see the
names of the configured services."""


def add_subparser(subparsers):
    rest_parser = subparsers.add_parser('rest',
                                        usage=rest_usage,
                                        description='List RESTful services, or force an upload',
                                        help="List RESTful services, or force an upload.")
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = rest_parser.add_subparsers(dest='action',
                                               prog='weectl rest',
                                               title="Which action to take")

    # ---------- Action 'list' ----------
    list_rest_parser = action_parser.add_parser('list',
                                                description="List all configured RESTful services",
                                                usage=rest_list_usage,
                                                help='List all configured RESTful services')
    list_rest_parser.add_argument('--config',
                                  metavar='FILENAME',
                                  help=f'Path to configuration file. '
                                       f'Default is "{weecfg.default_config_path}".')
    list_rest_parser.set_defaults(func=weectllib.dispatch)
    list_rest_parser.set_defaults(action_func=list_rest)

    # ---------- Action 'run' ----------
    run_rest_parser = action_parser.add_parser('run',
                                               description="Force an upload to RESTful services",
                                               usage=rest_run_usage,
                                               help='Force an upload to RESTful services',
                                               epilog=run_epilog)
    run_rest_parser.add_argument('--config',
                                 metavar='FILENAME',
                                 help=f'Path to configuration file. '
                                      f'Default is "{weecfg.default_config_path}".')
    run_rest_parser.add_argument('services',
                                 nargs="*",
                                 metavar='NAME',
                                 help="Services to upload to, separated by spaces. "
                                      "Names are case insensitive. "
                                      "If not given, all enabled services will be run.")
    run_rest_parser.set_defaults(func=weectllib.dispatch)
    run_rest_parser.set_defaults(action_func=run_rest)


def list_rest(config_dict, _):
    weectllib.rest_actions.list_rest(config_dict)


def run_rest(config_dict, namespace):
    weectllib.rest_actions.run_rest(config_dict, services=namespace.services)
