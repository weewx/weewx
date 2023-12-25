#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Import observation data"""

import weecfg
import weecfg.extension
import weectllib.import_actions
from weeutil.weeutil import bcolors

import_usage = f"""{bcolors.BOLD}weectl import --help
       weectl import --import-config=IMPORT_CONFIG_FILE
                     [--config=CONFIG_FILE]
                     [[--date=YYYY-mm-dd] | [[--from=YYYY-mm-dd[THH:MM]] [--to=YYYY-mm-dd[THH:MM]]]]
                     [--dry-run][--verbose]
                     [--no-prompt][--suppress-warnings]{bcolors.ENDC}
"""

import_description = """
Import observation data into a WeeWX archive.
"""

import_epilog = """
Import data from an external source into a WeeWX archive. Daily summaries are 
updated as each archive record is imported so there should be no need to 
separately rebuild the daily summaries.
"""


def add_subparser(subparsers):
    import_parser = subparsers.add_parser('import',
                                          usage=import_usage,
                                          description=import_description,
                                          epilog=import_epilog,
                                          help="Import observation data.")

    import_parser.add_argument('--config', 
                               metavar='FILENAME',
                               help=f'Path to configuration file. '
                                    f'Default is "{weecfg.default_config_path}".')
    import_parser.add_argument('--import-config', 
                               metavar='IMPORT_CONFIG_FILE',
                               dest='import_config',
                               help=f'Path to import configuration file.')
    import_parser.add_argument('--dry-run', 
                               action='store_true',
                               dest='dry_run',
                               help=f'Print what would happen but do not do it.')
    import_parser.add_argument('--date', 
                               metavar='YYYY-mm-dd',
                               # dest='d_date',
                               help=f'Import data for this date. Format is YYYY-mm-dd.')
    import_parser.add_argument('--from',
                               metavar='YYYY-mm-dd[THH:MM]',
                               dest='from_datetime',
                               help=f'Import data starting at this date or date-time. '
                                    f'Format is YYYY-mm-dd[THH:MM].')
    import_parser.add_argument('--to',
                               metavar='YYYY-mm-dd[THH:MM]',
                               dest='to_datetime',
                               help=f'Import data up until this date or date-time. Format '
                                    f'is YYYY-mm-dd[THH:MM].')
    import_parser.add_argument('--verbose',
                               action='store_true',
                               help=f'Print and log useful extra output.')
    import_parser.add_argument('--no-prompt',
                               action='store_true',
                               dest='no_prompt',
                               help=f'Do not prompt. Accept relevant defaults '
                                    f'and all y/n prompts.')
    import_parser.add_argument('--suppress-warnings',
                               action='store_true',
                               dest='suppress_warnings',
                               help=f'Suppress warnings to stdout. Warnings are still logged.')
    import_parser.set_defaults(func=weectllib.dispatch)
    import_parser.set_defaults(action_func=import_func)


def import_func(config_dict, namespace):
    weectllib.import_actions.obs_import(config_dict,
                                        namespace.import_config,
                                        dry_run=namespace.dry_run,
                                        date=namespace.date,
                                        from_datetime=namespace.from_datetime,
                                        to_datetime=namespace.to_datetime,
                                        verbose=namespace.verbose,
                                        no_prompt=namespace.no_prompt,
                                        suppress_warning=namespace.suppress_warnings)
