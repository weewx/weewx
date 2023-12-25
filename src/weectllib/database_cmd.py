#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Manage a WeeWX database."""
import argparse

import weecfg
import weecfg.database
import weectllib
import weectllib.database_actions
from weeutil.weeutil import bcolors

create_usage = f"""{bcolors.BOLD}weectl database create
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
drop_daily_usage = f"""{bcolors.BOLD}weectl database drop-daily
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
rebuild_usage = f"""{bcolors.BOLD}weectl database rebuild-daily
            [[--date=YYYY-mm-dd] | [--from=YYYY-mm-dd] [--to=YYYY-mm-dd]]
            [--config=FILENAME] [--binding=BINDING-NAME] 
            [--dry-run] [-y]{bcolors.ENDC}"""
add_column_usage = f"""{bcolors.BOLD}weectl database add-column NAME
            [--type=(REAL|INTEGER)]
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
rename_column_usage = f"""{bcolors.BOLD}weectl database rename-column FROM-NAME TO-NAME
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
drop_columns_usage = f"""{bcolors.BOLD}weectl database drop-columns NAME...
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
reconfigure_usage = f"""{bcolors.BOLD}weectl database reconfigure 
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
transfer_usage = f"""{bcolors.BOLD}weectl database transfer --dest-binding=BINDING-NAME
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
calc_missing_usage = f"""{bcolors.BOLD}weectl database calc-missing
            [--date=YYYY-mm-dd | [--from=YYYY-mm-dd[THH:MM]] [--to=YYYY-mm-dd[THH:MM]]]
            [--config=FILENAME] [--binding=BINDING-NAME] [--tranche=TRANCHE-SIZE]
            [--dry-run] [-y]{bcolors.ENDC}"""
check_usage = f"""{bcolors.BOLD}weectl database check
            [--config=FILENAME] [--binding=BINDING-NAME]{bcolors.ENDC}"""
update_usage = f"""{bcolors.BOLD}weectl database update
            [--config=FILENAME] [--binding=BINDING-NAME]
            [--dry-run] [-y]{bcolors.ENDC}"""
reweight_usage = f"""{bcolors.BOLD}weectl database reweight
            [[--date=YYYY-mm-dd] | [--from=YYYY-mm-dd] [--to=YYYY-mm-dd]]
            [--config=FILENAME] [--binding=BINDING-NAME] 
            [--dry-run] [-y]{bcolors.ENDC}"""

database_usage = '\n       '.join((create_usage,
                                   drop_daily_usage,
                                   rebuild_usage,
                                   add_column_usage,
                                   rename_column_usage,
                                   drop_columns_usage,
                                   reconfigure_usage,
                                   transfer_usage,
                                   calc_missing_usage,
                                   check_usage,
                                   update_usage,
                                   reweight_usage
                                   ))

drop_columns_description = """Drop (remove) one or more columns from a WeeWX database.
This command allows you to drop more than one column at once.
For example:
    weectl database drop-columns soilTemp1 batteryStatus5 leafWet1
"""

reconfigure_description = """Create a new database using the current configuration information 
found in the configuration file. This can be used to change the unit system of a database. The new
 database will have the same name as the old database, except with a '_new' on the end."""

transfer_description = """Copy a database to a new database.
The option "--dest-binding" should hold a database binding
to the target database."""

update_description = """Update the database to the current version. This is only necessary for 
databases created before v3.7 and never updated. Before updating, this utility will check 
whether it is necessary."""

epilog = "Before taking a mutating action, make a backup!"


def add_subparser(subparsers):
    database_parser = subparsers.add_parser('database',
                                            usage=database_usage,
                                            description='Manages WeeWX databases',
                                            help="Manage WeeWX databases.",
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
                                             help='Create a new WeeWX database.',
                                             epilog=epilog)
    _add_common_args(create_parser)
    create_parser.set_defaults(func=weectllib.dispatch)
    create_parser.set_defaults(action_func=create_database)

    # ---------- Action 'drop-daily' ----------
    drop_daily_parser = action_parser.add_parser('drop-daily',
                                                 description="Drop the daily summary from a "
                                                             "WeeWX database",
                                                 usage=drop_daily_usage,
                                                 help="Drop the daily summary from a "
                                                      "WeeWX database.",
                                                 epilog=epilog)
    _add_common_args(drop_daily_parser)
    drop_daily_parser.set_defaults(func=weectllib.dispatch)
    drop_daily_parser.set_defaults(action_func=drop_daily)

    # ---------- Action 'rebuild-daily' ----------
    rebuild_parser = action_parser.add_parser('rebuild-daily',
                                              description="Rebuild the daily summary in "
                                                          "a WeeWX database",
                                              usage=rebuild_usage,
                                              help="Rebuild the daily summary in "
                                                   "a WeeWX database.",
                                              epilog=epilog)
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
    _add_common_args(rebuild_parser)
    rebuild_parser.set_defaults(func=weectllib.dispatch)
    rebuild_parser.set_defaults(action_func=rebuild_daily)

    # ---------- Action 'add-column' ----------
    add_column_parser = action_parser.add_parser('add-column',
                                                 description="Add a column to an "
                                                             "existing WeeWX database.",
                                                 usage=add_column_usage,
                                                 help="Add a column to an "
                                                      "existing WeeWX database.",
                                                 epilog=epilog)
    add_column_parser.add_argument('column_name',
                                   metavar='NAME',
                                   help="Add new column NAME to database.")
    add_column_parser.add_argument('--type',
                                   choices=['REAL', 'INTEGER', 'real', 'integer', 'int'],
                                   default='REAL',
                                   dest='column_type',
                                   help="Type of the new column. Default is 'REAL'.")
    _add_common_args(add_column_parser)
    add_column_parser.set_defaults(func=weectllib.dispatch)
    add_column_parser.set_defaults(action_func=add_column)

    # ---------- Action 'rename-column' ----------
    rename_column_parser = action_parser.add_parser('rename-column',
                                                    description="Rename a column in an "
                                                                "existing WeeWX database.",
                                                    usage=rename_column_usage,
                                                    help="Rename a column in an "
                                                         "existing WeeWX database.",
                                                    epilog=epilog)
    rename_column_parser.add_argument('from_name',
                                      metavar='FROM-NAME',
                                      help="Column to be renamed.")
    rename_column_parser.add_argument('to_name',
                                      metavar='TO-NAME',
                                      help="New name of the column.")
    _add_common_args(rename_column_parser)
    rename_column_parser.set_defaults(func=weectllib.dispatch)
    rename_column_parser.set_defaults(action_func=rename_column)

    # ---------- Action 'drop-columns' ----------
    drop_columns_parser = action_parser.add_parser('drop-columns',
                                                   description=drop_columns_description,
                                                   usage=drop_columns_usage,
                                                   help="Drop (remove) one or more columns "
                                                        "from a WeeWX database.",
                                                   formatter_class=argparse.RawDescriptionHelpFormatter,
                                                   epilog=epilog)
    drop_columns_parser.add_argument('column_names',
                                     nargs="+",
                                     metavar='NAME',
                                     help="Column(s) to be dropped. "
                                          "More than one NAME can be specified.")
    _add_common_args(drop_columns_parser)
    drop_columns_parser.set_defaults(func=weectllib.dispatch)
    drop_columns_parser.set_defaults(action_func=drop_columns)

    # ---------- Action 'reconfigure' ----------
    reconfigure_parser = action_parser.add_parser('reconfigure',
                                                  description=reconfigure_description,
                                                  usage=reconfigure_usage,
                                                  help="Reconfigure a database, using the current "
                                                       "configuration information in the config "
                                                       "file.",
                                                  epilog=epilog)
    _add_common_args(reconfigure_parser)
    reconfigure_parser.set_defaults(func=weectllib.dispatch)
    reconfigure_parser.set_defaults(action_func=reconfigure_database)

    # ---------- Action 'transfer' ----------
    transfer_parser = action_parser.add_parser('transfer',
                                               description=transfer_description,
                                               usage=transfer_usage,
                                               help="Copy a database to a new database.",
                                               epilog=epilog)
    transfer_parser.add_argument('--dest-binding',
                                 metavar='BINDING-NAME',
                                 required=True,
                                 help="A database binding pointing to the destination "
                                      "database. Required.")
    _add_common_args(transfer_parser)
    transfer_parser.set_defaults(func=weectllib.dispatch)
    transfer_parser.set_defaults(action_func=transfer_database)

    # ---------- Action 'calc-missing' ----------
    calc_missing_parser = action_parser.add_parser('calc-missing',
                                                   description="Calculate and store any missing "
                                                               "derived observations.",
                                                   usage=calc_missing_usage,
                                                   help="Calculate and store any missing "
                                                        "derived observations.",
                                                   epilog=epilog)
    calc_missing_parser.add_argument("--date",
                                     metavar="YYYY-mm-dd",
                                     help="Calculate for this date only.")
    calc_missing_parser.add_argument("--from",
                                     metavar="YYYY-mm-ddTHH:MM:SS",
                                     dest='from_date',
                                     help="Calculate starting with this datetime.")
    calc_missing_parser.add_argument("--to",
                                     metavar="YYYY-mm-ddTHH:MM:SS",
                                     dest='to_date',
                                     help="Calculate ending with this datetime.")
    calc_missing_parser.add_argument("--tranche",
                                     metavar="TRANCHE",
                                     type=int,
                                     default=10,
                                     help="Perform database transactions on TRANCHE days "
                                          "of records at a time. Default is 10.")
    _add_common_args(calc_missing_parser)
    calc_missing_parser.set_defaults(func=weectllib.dispatch)
    calc_missing_parser.set_defaults(action_func=calc_missing)

    # ---------- Action 'check' ----------
    check_parser = action_parser.add_parser('check',
                                            description="Check the database for any issues.",
                                            usage=check_usage,
                                            help="Check the database for any issues.")
    check_parser.add_argument('--config',
                              metavar='FILENAME',
                              help=f'Path to configuration file. '
                                   f'Default is "{weecfg.default_config_path}".')
    check_parser.add_argument("--binding", metavar="BINDING-NAME",
                              default='wx_binding',
                              help="The data binding to use. Default is 'wx_binding'.")
    check_parser.set_defaults(func=weectllib.dispatch)
    check_parser.set_defaults(action_func=check)

    # ---------- Action 'update' ----------
    update_parser = action_parser.add_parser('update',
                                             description=update_description,
                                             usage=update_usage,
                                             help="Update the database to the current version.",
                                             epilog=epilog)

    _add_common_args(update_parser)
    update_parser.set_defaults(func=weectllib.dispatch)
    update_parser.set_defaults(action_func=update_database)

    # ---------- Action 'reweight' ----------
    reweight_parser = action_parser.add_parser('reweight',
                                               description="Recalculate the weighted sums in "
                                                           "the daily summaries.",
                                               usage=reweight_usage,
                                               help="Recalculate the weighted sums in "
                                                    "the daily summaries.",
                                               epilog=epilog)
    reweight_parser.add_argument("--date",
                                 metavar="YYYY-mm-dd",
                                 help="Reweight for this date only.")
    reweight_parser.add_argument("--from",
                                 metavar="YYYY-mm-dd",
                                 dest='from_date',
                                 help="Reweight starting with this date.")
    reweight_parser.add_argument("--to",
                                 metavar="YYYY-mm-dd",
                                 dest='to_date',
                                 help="Reweight ending with this date.")
    _add_common_args(reweight_parser)
    reweight_parser.set_defaults(func=weectllib.dispatch)
    reweight_parser.set_defaults(action_func=reweight_daily)


# ------------------ Shims for calling database action functions ---------------- #
def create_database(config_dict, namespace):
    """Create the WeeWX database"""

    weectllib.database_actions.create_database(config_dict,
                                               db_binding=namespace.binding,
                                               dry_run=namespace.dry_run,
                                               no_confirm=namespace.yes)


def drop_daily(config_dict, namespace):
    """Drop the daily summary from a WeeWX database"""
    weectllib.database_actions.drop_daily(config_dict,
                                          db_binding=namespace.binding,
                                          dry_run=namespace.dry_run,
                                          no_confirm=namespace.yes)


def rebuild_daily(config_dict, namespace):
    """Rebuild the daily summary in a WeeWX database"""
    weectllib.database_actions.rebuild_daily(config_dict,
                                             date=namespace.date,
                                             from_date=namespace.from_date,
                                             to_date=namespace.to_date,
                                             db_binding=namespace.binding,
                                             dry_run=namespace.dry_run,
                                             no_confirm=namespace.yes)


def add_column(config_dict, namespace):
    """Add a column to a WeeWX database"""
    column_type = namespace.column_type.upper()
    if column_type == 'INT':
        column_type = "INTEGER"
    weectllib.database_actions.add_column(config_dict,
                                          column_name=namespace.column_name,
                                          column_type=column_type,
                                          db_binding=namespace.binding,
                                          dry_run=namespace.dry_run,
                                          no_confirm=namespace.yes)


def rename_column(config_dict, namespace):
    """Rename a column in a WeeWX database."""
    weectllib.database_actions.rename_column(config_dict,
                                             from_name=namespace.from_name,
                                             to_name=namespace.to_name,
                                             db_binding=namespace.binding,
                                             dry_run=namespace.dry_run,
                                             no_confirm=namespace.yes)


def drop_columns(config_dict, namespace):
    """Drop (remove) one or more columns in a WeeWX database."""
    weectllib.database_actions.drop_columns(config_dict,
                                            column_names=namespace.column_names,
                                            db_binding=namespace.binding,
                                            dry_run=namespace.dry_run,
                                            no_confirm=namespace.yes)


def reconfigure_database(config_dict, namespace):
    """Replicate a database, using current configuration settings."""
    weectllib.database_actions.reconfigure_database(config_dict,
                                                    db_binding=namespace.binding,
                                                    dry_run=namespace.dry_run,
                                                    no_confirm=namespace.yes)


def transfer_database(config_dict, namespace):
    """Copy a database to a new database."""
    weectllib.database_actions.transfer_database(config_dict,
                                                 dest_binding=namespace.dest_binding,
                                                 db_binding=namespace.binding,
                                                 dry_run=namespace.dry_run,
                                                 no_confirm=namespace.yes)


def calc_missing(config_dict, namespace):
    """Calculate derived variables in a database."""
    weectllib.database_actions.calc_missing(config_dict,
                                            date=namespace.date,
                                            from_date=namespace.from_date,
                                            to_date=namespace.to_date,
                                            db_binding=namespace.binding,
                                            tranche=namespace.tranche,
                                            dry_run=namespace.dry_run,
                                            no_confirm=namespace.yes)


def check(config_dict, namespace):
    """Check the integrity of a WeeWX database."""
    weectllib.database_actions.check(config_dict,
                                     namespace.binding)


def update_database(config_dict, namespace):
    weectllib.database_actions.update_database(config_dict,
                                               db_binding=namespace.binding,
                                               dry_run=namespace.dry_run,
                                               no_confirm=namespace.yes)


def reweight_daily(config_dict, namespace):
    """Recalculate the weights in a WeeWX database."""
    weectllib.database_actions.reweight_daily(config_dict,
                                              date=namespace.date,
                                              from_date=namespace.from_date,
                                              to_date=namespace.to_date,
                                              db_binding=namespace.binding,
                                              dry_run=namespace.dry_run,
                                              no_confirm=namespace.yes)


def _add_common_args(subparser):
    """Add options used by most of the subparsers"""
    subparser.add_argument('--config',
                           metavar='FILENAME',
                           help='Path to configuration file. '
                                f'Default is "{weecfg.default_config_path}".')
    subparser.add_argument("--binding", metavar="BINDING-NAME", default='wx_binding',
                           help="The data binding to use. Default is 'wx_binding'.")
    subparser.add_argument('--dry-run',
                           action='store_true',
                           help='Print what would happen, but do not actually do it.')
    subparser.add_argument('-y', '--yes', action='store_true',
                           help="Don't ask for confirmation. Just do it.")
