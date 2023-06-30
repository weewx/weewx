#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Manage a WeeWX database."""
import weecfg
import weecfg.database
import weectllib.db_actions
from weeutil.weeutil import bcolors

database_create_usage = f"""{bcolors.BOLD}weectl database create \\
            [--config=CONFIG-PATH] [--binding=BINDING_NAME] [--dry-run]{bcolors.ENDC}"""
database_drop_daily_usage = f"""{bcolors.BOLD}weectl database drop-daily \\
            [--config=CONFIG-PATH] [--binding=BINDING_NAME] [--dry-run]{bcolors.ENDC}"""
database_rebuild_usage = f"""{bcolors.BOLD}weectl database rebuild-daily " \\
            [--config=CONFIG-PATH] [--binding=BINDING_NAME]  \\
            [[--date=YYYY-mm-dd] | [--from=YYYY-mm-dd]|[--to=YYYY-mm-dd]] \\
            [--dry-run]{bcolors.ENDC}"""

database_usage = '\n       '.join((database_create_usage,
                                   database_drop_daily_usage,
                                   database_rebuild_usage
                                   ))


def add_subparser(subparsers):
    database_parser = subparsers.add_parser('database',
                                            usage=database_usage,
                                            description='Manages WeeWX databases',
                                            help="Manages WeeWX databases")
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = database_parser.add_subparsers(dest='action',
                                                   prog='weectl database',
                                                   title="Which action to take")

    # ---------- Action 'create' ----------
    database_create_parser = action_parser.add_parser('create',
                                                      description="Create a new WeeWX database",
                                                      usage=database_create_usage,
                                                      help='Create a new WeeWX database')
    database_create_parser.add_argument('--config',
                                        metavar='CONFIG-PATH',
                                        help=f'Path to configuration file. '
                                             f'Default is "{weecfg.default_config_path}".')
    database_create_parser.add_argument("--binding", metavar="BINDING_NAME", default='wx_binding',
                                        help="The data binding to use. Default is 'wx_binding'.")
    database_create_parser.add_argument('--dry-run',
                                        action='store_true',
                                        help='Print what would happen, but do not actually '
                                             'do it.')
    database_create_parser.set_defaults(func=create_database)

    # ---------- Action 'drop-daily' ----------
    database_drop_daily_parser = action_parser.add_parser('drop-daily',
                                                          description="Drop the daily summary from a "
                                                                      "WeeWX database",
                                                          usage=database_drop_daily_usage,
                                                          help="Drop the daily summary from a "
                                                               "WeeWX database")

    database_drop_daily_parser.add_argument('--config',
                                            metavar='CONFIG-PATH',
                                            help=f'Path to configuration file. '
                                                 f'Default is "{weecfg.default_config_path}".')
    database_drop_daily_parser.add_argument("--binding", metavar="BINDING_NAME",
                                            default='wx_binding',
                                            help="The data binding to use. Default is 'wx_binding'.")
    database_drop_daily_parser.add_argument('--dry-run',
                                            action='store_true',
                                            help='Print what would happen, but do not actually '
                                                 'do it.')
    database_drop_daily_parser.set_defaults(func=drop_daily)

    # ---------- Action 'rebuild-daily' ----------
    database_rebuild_parser = action_parser.add_parser('rebuild-daily',
                                                       description="Rebuild the daily summary in "
                                                                   "a WeeWX database",
                                                       usage=database_rebuild_usage,
                                                       help="Rebuild the daily summary in "
                                                            "a WeeWX database")

    database_rebuild_parser.add_argument('--config',
                                         metavar='CONFIG-PATH',
                                         help=f'Path to configuration file. '
                                              f'Default is "{weecfg.default_config_path}".')
    database_rebuild_parser.add_argument("--binding", metavar="BINDING_NAME", default='wx_binding',
                                         help="The data binding to use. Default is 'wx_binding'.")
    database_rebuild_parser.add_argument("--date",
                                         metavar="YYYY-mm-dd",
                                         help="Rebuild for this date only.")
    database_rebuild_parser.add_argument("--from",
                                         metavar="YYYY-mm-dd",
                                         dest='from_date',
                                         help="Rebuild starting with this date.")
    database_rebuild_parser.add_argument("--to",
                                         metavar="YYYY-mm-dd",
                                         dest='to_date',
                                         help="Rebuild ending with this date.")
    database_rebuild_parser.add_argument('--dry-run',
                                         action='store_true',
                                         help='Print what would happen, but do not actually '
                                              'do it.')
    database_rebuild_parser.set_defaults(func=rebuild_daily)


def create_database(namespace):
    """Create the WeeWX database"""

    weectllib.db_actions.create_database(namespace.config,
                                         db_binding=namespace.binding,
                                         dry_run=namespace.dry_run)


def drop_daily(namespace):
    """Drop the daily summary from a WeeWX database"""
    weectllib.db_actions.drop_daily(namespace.config,
                                    db_binding=namespace.binding,
                                    dry_run=namespace.dry_run)


def rebuild_daily(namespace):
    """Rebuild the daily summary in a WeeWX database"""
    weectllib.db_actions.rebuild_daily(namespace.config,
                                       db_binding=namespace.binding,
                                       date=namespace.date,
                                       from_date=namespace.from_date,
                                       to_date=namespace.to_date,
                                       dry_run=namespace.dry_run)
