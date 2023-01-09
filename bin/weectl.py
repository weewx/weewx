#!/usr/bin/env python
#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point to the weewx configuration program 'weectl'."""

import argparse
import importlib
import logging
import os.path
import sys

# In case we are invoked from the git repository, include my parent directory in the Python path
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import weewx

log = logging.getLogger(__name__)

usagestr = """weectl -v|--version
       weectl -h|--help
       weectl station --help
       weectl daemon --help
       weectl extension --help
"""

SUBCOMMANDS = ['station', 'daemon', 'extension']


# ===============================================================================
#                       Main entry point
# ===============================================================================

def main():
    parser = argparse.ArgumentParser(usage=usagestr)
    parser.add_argument("-v", "--version", action='version',
                        version=f"weectl v{weewx.__version__}")

    subparsers = parser.add_subparsers(dest='subcommand',
                                       title="Available subcommands")

    for subcommand in SUBCOMMANDS:
        module = importlib.import_module(f'weectllib.parse_{subcommand}')
        module.add_subparser(subparsers)

    namespace = parser.parse_args()

    if hasattr(namespace, 'func'):
        # Call the appropriate action function:
        namespace.func(namespace)
    else:
        # Now subcommand was invoked. Print a help message
        parser.print_help()


if __name__ == "__main__":
    # Start up the program
    main()
