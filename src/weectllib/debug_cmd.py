#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Generate weewx debug info"""

import weecfg
import weecfg.extension
import weectllib.debug_actions
from weeutil.weeutil import bcolors

debug_usage = f"""{bcolors.BOLD}weectl debug
            [--config=FILENAME]
            [--output=FILENAME]{bcolors.ENDC}
"""

debug_description = """
Generate a standard suite of system/weewx information to aid in remote
debugging. The debug output consists of two parts, the first part containing
a snapshot of relevant system/weewx information and the second part a parsed and
obfuscated copy of weewx.conf. This output can be redirected to a file and posted
when seeking assistance via forums or email.
"""

debug_epilog = """
weectl debug will attempt to obfuscate obvious personal/private information in
weewx.conf such as user names, passwords and API keys; however, the user
should thoroughly check the generated output for personal/private information
before posting the information publicly.
"""


def add_subparser(subparsers):
    debug_parser = subparsers.add_parser('debug',
                                         usage=debug_usage,
                                         description=debug_description,
                                         epilog=debug_epilog,
                                         help="Generate debug info.")

    debug_parser.add_argument('--config',
                              metavar='FILENAME',
                              help=f'Path to configuration file. '
                                   f'Default is "{weecfg.default_config_path}".')
    debug_parser.add_argument('--output',
                              metavar="FILENAME",
                              help="Redirect output to FILENAME. Default is "
                                   "standard output.")
    debug_parser.set_defaults(func=weectllib.dispatch)
    debug_parser.set_defaults(action_func=debug)


def debug(config_dict, namespace):
    weectllib.debug_actions.debug(config_dict, output=namespace.output)
