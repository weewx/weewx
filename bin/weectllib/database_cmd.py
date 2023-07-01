#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Manage a WeeWX database."""
import argparse

import weecfg
import weecfg.database
import weectllib.db_actions
from weeutil.weeutil import bcolors

create_usage = f"""{bcolors.BOLD}weectl database create \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] [--dry-run]{bcolors.ENDC}"""
drop_daily_usage = f"""{bcolors.BOLD}weectl database drop-daily \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] [--dry-run]{bcolors.ENDC}"""
rebuild_usage = f"""{bcolors.BOLD}weectl database rebuild-daily " \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME]  \\
            [[--date=YYYY-mm-dd] | [--from=YYYY-mm-dd]|[--to=YYYY-mm-dd]] \\
            [--dry-run]{bcolors.ENDC}"""
add_column_usage = f"""{bcolors.BOLD}weectl database add-column NAME " \\
            [--type=(REAL|INTEGER)] \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] \\
            [--dry-run]{bcolors.ENDC}"""
rename_column_usage = f"""{bcolors.BOLD}weectl database rename-column FROM-NAME --to-name=NEW-NAME \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] \\
            [--dry-run]{bcolors.ENDC}"""
drop_columns_usage = f"""{bcolors.BOLD}weectl database drop-columns NAME NAME ... \\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] \\
            [--dry-run]{bcolors.ENDC}"""
reconfigure_usage = f"""{bcolors.BOLD}weectl database reconfigure 
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] [--dry-run]{bcolors.ENDC}"""
transfer_usage = f"""{bcolors.BOLD}weectl database transfer --dest-binding=BINDING-NAME\\
            [--config=CONFIG-PATH] [--binding=BINDING-NAME] \\
            [--dry-run]{bcolors.ENDC}"""

database_usage = '\n       '.join((create_usage,
                                   drop_daily_usage,
                                   rebuild_usage,
                                   add_column_usage,
                                   rename_column_usage,
                                   drop_columns_usage,
                                   reconfigure_usage,
                                   transfer_usage,
                                   ))

database_schema_description = "Change the schema of an existing WeeWX database. You must also " \
                              "specify either --add-column, --rename-column, or --drop-columns."

drop_columns_description = """Drop (remove) one or more columns from a WeeWX database.
This command allows you to drop more than one column at once.
For example:
    weectl database drop-columns soilTemp1 batteryStatus5 leafWet1
"""

reconfigure_description = """Create a new database using the current configuration information 
found in the configuration file. This can be used to change the unit system of a 
database. The new database will have the same name as the old database, with a '_new' 
on the end."""

transfer_description = """Copy a database to a new database.
The option "--dest-binding" should hold a database binding
to the target database."""

epilog = "Before taking a mutating action, make a backup!"


def add_subparser(subparsers):
    database_parser = subparsers.add_parser('database',
                                            usage=database_usage,
                                            description='Manages WeeWX databases',
                                            help="Manages WeeWX databases",
                                            epilog=epilog)
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = database_parser.add_subparsers(dest='action',
                                                   prog='weectl database',
                                                   title="Which action to take")

    # ---------- Action 'create' ----------
    create_parser = action_parser.add_parser('create',
                                             description="Create a new WeeWX database",
                                             usage=create_usage,
                                             help='Create a new WeeWX database',
                                             epilog=epilog)
    create_parser.add_argument('--config',
                               metavar='CONFIG-PATH',
                               help=f'Path to configuration file. '
                                    f'Default is "{weecfg.default_config_path}".')
    create_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                               help="The data binding to use. Default is 'wx_binding'.")
    create_parser.add_argument('--dry-run',
                               action='store_true',
                               help='Print what would happen, but do not actually '
                                    'do it.')
    create_parser.set_defaults(func=create_database)

    # ---------- Action 'drop-daily' ----------
    drop_daily_parser = action_parser.add_parser('drop-daily',
                                                 description="Drop the daily summary from a "
                                                             "WeeWX database",
                                                 usage=drop_daily_usage,
                                                 help="Drop the daily summary from a "
                                                      "WeeWX database",
                                                 epilog=epilog)

    drop_daily_parser.add_argument('--config',
                                   metavar='CONFIG-PATH',
                                   help=f'Path to configuration file. '
                                        f'Default is "{weecfg.default_config_path}".')
    drop_daily_parser.add_argument("--binding", metavar="BINDING-NAME",
                                   default='wx_binding',
                                   help="The data binding to use. Default is 'wx_binding'.")
    drop_daily_parser.add_argument('--dry-run',
                                   action='store_true',
                                   help='Print what would happen, but do not actually '
                                        'do it.')
    drop_daily_parser.set_defaults(func=drop_daily)

    # ---------- Action 'rebuild-daily' ----------
    rebuild_parser = action_parser.add_parser('rebuild-daily',
                                              description="Rebuild the daily summary in "
                                                          "a WeeWX database",
                                              usage=rebuild_usage,
                                              help="Rebuild the daily summary in "
                                                   "a WeeWX database",
                                              epilog=epilog)

    rebuild_parser.add_argument('--config',
                                metavar='CONFIG-PATH',
                                help=f'Path to configuration file. '
                                     f'Default is "{weecfg.default_config_path}".')
    rebuild_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                help="The data binding to use. Default is 'wx_binding'.")
    rebuild_parser.add_argument("--date",
                                metavar="YYYY-mm-dd",
                                help="Rebuild for this date only.")
    rebuild_parser.add_argument("--from",
                                metavar="YYYY-mm-dd",
                                dest='from_date',
                                help="Rebuild starting with this date.")
    rebuild_parser.add_argument("--to",
                                metavar="YYYY-mm-dd",
                                dest='to_date',
                                help="Rebuild ending with this date.")
    rebuild_parser.add_argument('--dry-run',
                                action='store_true',
                                help='Print what would happen, but do not actually '
                                     'do it.')
    rebuild_parser.set_defaults(func=rebuild_daily)

    # ---------- Action 'add-column' ----------
    add_column_parser = action_parser.add_parser('add-column',
                                                 description="Add a column to an "
                                                             "existing WeeWX database.",
                                                 usage=add_column_usage,
                                                 help="Add a column to an "
                                                      "existing WeeWX database",
                                                 epilog=epilog)

    add_column_parser.add_argument('column_name',
                                   metavar='NAME',
                                   help="Add new column NAME to database")
    add_column_parser.add_argument('--type',
                                   choices=['REAL', 'INTEGER', 'real', 'integer', 'int'],
                                   default='REAL',
                                   dest='column_type',
                                   help="Type of the new column. Default is 'REAL'.")
    add_column_parser.add_argument('--config',
                                   metavar='CONFIG-PATH',
                                   help=f'Path to configuration file. '
                                        f'Default is "{weecfg.default_config_path}".')
    add_column_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                   help="The data binding to use. Default is 'wx_binding'.")
    add_column_parser.add_argument('--dry-run',
                                   action='store_true',
                                   help='Print what would happen, but do not actually '
                                        'do it.')
    add_column_parser.set_defaults(func=add_column)

    # ---------- Action 'rename-column' ----------
    add_column_parser = action_parser.add_parser('rename-column',
                                                 description="Rename a column in an "
                                                             "existing WeeWX database.",
                                                 usage=rename_column_usage,
                                                 help="Rename a column in an "
                                                      "existing WeeWX database",
                                                 epilog=epilog)

    add_column_parser.add_argument('column_name',
                                   metavar='FROM-NAME',
                                   help="Column to be renamed")
    add_column_parser.add_argument('--to-name',
                                   metavar='NEW-NAME',
                                   dest='new_name',
                                   required=True,
                                   help="New name of the column. Required.")
    add_column_parser.add_argument('--config',
                                   metavar='CONFIG-PATH',
                                   help=f'Path to configuration file. '
                                        f'Default is "{weecfg.default_config_path}".')
    add_column_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                   help="The data binding to use. Default is 'wx_binding'.")
    add_column_parser.add_argument('--dry-run',
                                   action='store_true',
                                   help='Print what would happen, but do not actually '
                                        'do it.')
    add_column_parser.set_defaults(func=rename_column)

    # ---------- Action 'drop-columns' ----------
    add_column_parser = action_parser.add_parser('drop-columns',
                                                 description=drop_columns_description,
                                                 usage=drop_columns_usage,
                                                 help="Drop (remove) one or more columns "
                                                      "from a WeeWX database.",
                                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                                 epilog=epilog)

    add_column_parser.add_argument('column_names',
                                   nargs="+",
                                   metavar='NAME',
                                   help="Column to be dropped. "
                                        "More than one NAME can be specified.")
    add_column_parser.add_argument('--config',
                                   metavar='CONFIG-PATH',
                                   help=f'Path to configuration file. '
                                        f'Default is "{weecfg.default_config_path}".')
    add_column_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                   help="The data binding to use. Default is 'wx_binding'.")
    add_column_parser.add_argument('--dry-run',
                                   action='store_true',
                                   help='Print what would happen, but do not actually '
                                        'do it.')
    add_column_parser.set_defaults(func=drop_columns)

    # ---------- Action 'reconfigure' ----------
    reconfigure_parser = action_parser.add_parser('reconfigure',
                                                  description=reconfigure_description,
                                                  usage=reconfigure_usage,
                                                  help="Reconfigure a database.",
                                                  epilog=epilog)
    reconfigure_parser.add_argument('--config',
                                    metavar='CONFIG-PATH',
                                    help=f'Path to configuration file. '
                                         f'Default is "{weecfg.default_config_path}".')
    reconfigure_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                    help="The data binding to use. Default is 'wx_binding'.")
    reconfigure_parser.add_argument('--dry-run',
                                    action='store_true',
                                    help='Print what would happen, but do not actually '
                                         'do it.')
    reconfigure_parser.set_defaults(func=reconfigure_database)

    # ---------- Action 'transfer' ----------
    transfer_parser = action_parser.add_parser('transfer',
                                               description=transfer_description,
                                               usage=transfer_usage,
                                               help="Copy a database to a new database",
                                               epilog=epilog)

    transfer_parser.add_argument('--dest-binding',
                                 metavar='BINDING-NAME',
                                 required=True,
                                 help="A database binding pointing to the destination "
                                      "database. Required.")
    transfer_parser.add_argument('--config',
                                 metavar='CONFIG-PATH',
                                 help=f'Path to configuration file. '
                                      f'Default is "{weecfg.default_config_path}".')
    transfer_parser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                                 help="The data binding to use. Default is 'wx_binding'.")
    transfer_parser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Print what would happen, but do not actually '
                                      'do it.')
    transfer_parser.set_defaults(func=transfer_database)


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


def add_column(namespace):
    column_type = namespace.column_type.upper()
    if column_type == 'INT':
        column_type = "INTEGER"
    weectllib.db_actions.add_column(namespace.config,
                                    db_binding=namespace.binding,
                                    column_name=namespace.column_name,
                                    column_type=column_type,
                                    dry_run=namespace.dry_run)


def rename_column(namespace):
    weectllib.db_actions.rename_column(namespace.config,
                                       db_binding=namespace.binding,
                                       column_name=namespace.column_name,
                                       new_name=namespace.new_name,
                                       dry_run=namespace.dry_run)


def drop_columns(namespace):
    weectllib.db_actions.drop_columns(namespace.config,
                                      db_binding=namespace.binding,
                                      column_names=namespace.column_names,
                                      dry_run=namespace.dry_run)


def reconfigure_database(namespace):
    weectllib.db_actions.reconfigure_database(namespace.config,
                                              db_binding=namespace.binding,
                                              dry_run=namespace.dry_run)


def transfer_database(namespace):
    weectllib.db_actions.transfer_database(namespace.config,
                                           db_binding=namespace.binding,
                                           dest_binding=namespace.dest_binding,
                                           dry_run=namespace.dry_run)
