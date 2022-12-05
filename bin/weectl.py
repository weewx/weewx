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
import sys

import weewx

log = logging.getLogger(__name__)

usagestr = """weectl -v|--version
       weectl -h|--help
       weectl station --help
       weectl daemon --help
"""

SUBCOMMANDS = ['station', 'daemon']


# ===============================================================================
#                       Main entry point
# ===============================================================================

def main():
    parser = argparse.ArgumentParser(usage=usagestr)
    parser.add_argument("-v", "--version", action='version',
                        version=f"weectl v{weewx.__version__}")

    subparsers = parser.add_subparsers(dest='subcommand', help='subcommand to run')

    for subcommand in SUBCOMMANDS:
        module = importlib.import_module(f'weectl.{subcommand}')
        module.add_subparser(subparsers)

    namespace = parser.parse_args()
    print(namespace)

if __name__ == "__main__":
    # Start up the program
    main()
