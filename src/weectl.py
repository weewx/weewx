#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point to the weewx configuration program 'weectl'."""

import argparse
import importlib
import inspect
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
subcommands, listed below. You can explore what each subcommand does by using the --help option.
For example, to find out what the 'database' subcommand can do, use '%(prog)s database --help'."""

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
                        help="show the WeeWX version, then exit",
                        version=f"weectl {weewx.__version__}")

    # Add a subparser to handle the various subcommands.
    subparsers = parser.add_subparsers(dest='subcommand',
                                       title="Available subcommands")

    # Import the "cmd" module for each subcommand, then add its individual subparser.
    for subcommand in SUBCOMMANDS:
        module = importlib.import_module(f'weectllib.{subcommand}_cmd')
        module.add_subparser(subparsers)

    # Parse what we can. This gives us access to the namespace.
    namespace, extra_args = parser.parse_known_args()
    # Guard against there being no subcommand at all. In this case, display the help message.
    if namespace.subcommand is None:
        namespace = parser.parse_args(['-h'])
    # Now take a look at the signature of the dispatch function and see how many arguments it has.
    sig = inspect.signature(namespace.func)
    if len(sig.parameters) == 1:
        # No optional arguments. Reparse everything, this time using the more restrictive
        # parse_args() method. This will raise an error if there are any unrecognized arguments.
        namespace = parser.parse_args()
        namespace.func(namespace)
    elif len(sig.parameters) == 2:
        # Optional arguments are possible. Pass them on to the dispatch function.
        namespace.func(namespace, extra_args)
    else:
        # Shouldn't be here. Some weird dispatch function.
        raise TypeError(f"Unexpected dispatch function signature: {sig}")


if __name__ == "__main__":
    # Start up the program
    main()
