#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point to the weewx configuration program 'weectl'."""

import argparse
import importlib
import sys

import weewx

usagestr = """%(prog)s -v|--version
       %(prog)s -h|--help
       %(prog)s database --help
       %(prog)s debug --help
       %(prog)s device --help
       %(prog)s extension --help
       %(prog)s import --help
       %(prog)s report --help
       %(prog)s station --help
"""

description = """%(prog)s is the master utility used by WeeWX. It can invoke several different
subcommands, listed below. You can explore their utility by using the --help option. For example, 
to find out what the 'database' subcommand can do, use '%(prog)s database --help'."""

SUBCOMMANDS = ['database', 'debug', 'device', 'extension', 'import', 'report', 'station', ]


# ===============================================================================
#                       Main entry point
# ===============================================================================

def main():
    try:
        # The subcommand 'weectl device' uses the old optparse, so we have to intercept any
        # calls to it and call it directly.
        if sys.argv[1] == 'device':
            import weectllib.device_actions
            weectllib.device_actions.device()
            return
    except IndexError:
        pass

    # Everything else uses argparse. Proceed.
    parser = argparse.ArgumentParser(usage=usagestr, description=description)
    parser.add_argument("-v", "--version", action='version',
                        version=f"weectl {weewx.__version__}")

    # Add a subparser to handle the various subcommands.
    subparsers = parser.add_subparsers(dest='subcommand',
                                       title="Available subcommands")

    # Import the "cmd" module for each subcommand, then add its individual subparser.
    for subcommand in SUBCOMMANDS:
        module = importlib.import_module(f'weectllib.{subcommand}_cmd')
        module.add_subparser(subparsers)

    # Time to parse the whole tree
    namespace = parser.parse_args()

    if hasattr(namespace, 'func'):
        # Call the appropriate action function:
        namespace.func(namespace)
    else:
        # Shouldn't get here. Some sub-subparser failed to include a 'func' argument.
        parser.print_help()


if __name__ == "__main__":
    # Start up the program
    main()
