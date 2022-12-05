#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""The 'weectl' package."""

import argparse

# This is a common parser used as a parent for the other parsers.
common_parser = argparse.ArgumentParser(description="Common parser", add_help=False)
common_parser.add_argument('--config',
                           metavar="CONFIG-PATH",
                           help="path to configuration file")
