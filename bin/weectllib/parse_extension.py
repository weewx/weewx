#!/usr/bin/env python
#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Install and remove extensions."""
import argparse
import sys

import weewx
import weectllib
import weecfg.extension
import weeutil.logger
from weecfg import Logger
from weecfg.extension import ExtensionEngine
from weeutil.weeutil import to_int

# Redirect the import of setup:
sys.modules['setup'] = weecfg.extension

extension_list_usage = """weectllib extension list [--config=CONFIG-PATH]
"""
extension_install_usage = """  weectllib extension install {filename|directory|remote}
               [--config=CONFIG-PATH]
               [--tmpdir=DIR] [--dry-run] [--verbosity=N]
"""
extension_uninstall_usage = """  weectllib extension uninstall=EXTENSION
               [--config=CONFIG-PATH]
               [--dry-run] [--verbosity=N]
"""
extension_usage = '\n     '.join((extension_list_usage,
                                  extension_install_usage,
                                  extension_uninstall_usage))


def add_subparser(subparsers):
    extension_parser = subparsers.add_parser('extension',
                                             usage=extension_usage,
                                             description='Manages WeeWX extensions',
                                             help="Install, uninstall, or list "
                                                  "extensions")
    action_parser = extension_parser.add_subparsers(dest='action',
                                                    title="Which action to take")

    # ---------- Action 'list' ----------
    list_extension_parser = action_parser.add_parser('list',
                                                     usage=extension_list_usage,
                                                     help='List all installed extensions')
    list_extension_parser.add_argument('--config',
                                       metavar='CONFIG-PATH',
                                       help=f'Path to configuration file. '
                                            f'Default is "{weecfg.default_config_path}".')

    # ---------- Action 'install' ----------
    install_extension_parser = \
        action_parser.add_parser('install',
                                 usage=extension_install_usage,
                                 help="Install an extension contained in FILENAME "
                                      " (such as pmon.tar.gz), or from a DIRECTORY, or from "
                                      " an URL.")
    install_extension_parser.add_argument('location',
                                          metavar='FILE|DIR|URL',
                                          help="Location of the extension. It can be either a "
                                               "downloaded zipfile or tarball, an unpacked "
                                               "directory, or an URL pointing to a zipfile "
                                               "or tarball.")
    install_extension_parser.add_argument('--config',
                                          metavar='CONFIG-PATH',
                                          help=f'Path to configuration file. '
                                               f'Default is "{weecfg.default_config_path}".')
    install_extension_parser.add_argument('--tmpdir',
                                          metavar='DIR',
                                          help="Location of a temporarily directory to use if "
                                               "a zipfile or tarball needs to be unpacked. "
                                               "Optional.")
    install_extension_parser.add_argument('--dry-run',
                                          action='store_true',
                                          help='Print what would happen, but do not actually '
                                               'do it.')
    install_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                          help="How much information to display {0-3}.")
