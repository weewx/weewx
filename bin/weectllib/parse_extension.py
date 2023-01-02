#!/usr/bin/env python
#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Install and remove extensions."""
import sys
import os.path

import weewx
import weecfg
import weecfg.extension
import weeutil.logger
import weecfg.extension
from weeutil.weeutil import bcolors, to_int

# Redirect the import of setup:
sys.modules['setup'] = weecfg.extension

if sys.platform == 'darwin':
    OLD_WEEWX_DIR = '/Users/Shared/weewx'
else:
    OLD_WEEWX_DIR = '/home/weewx'
OLD_USER_DIR = os.path.abspath(os.path.join(OLD_WEEWX_DIR, 'bin', 'user'))

extension_list_usage = f"""{bcolors.BOLD}weectl extension list [--config=CONFIG-PATH]{bcolors.ENDC}
"""
extension_install_usage = f"""  {bcolors.BOLD}weectl extension install {{FILE|DIR|URL}} \\
           [--config=CONFIG-PATH] \\
           [--dry-run] [--verbosity=N]{bcolors.ENDC}
"""
extension_uninstall_usage = f"""  {bcolors.BOLD}weectl extension uninstall NAME \\
           [--config=CONFIG-PATH] \\
           [--dry-run] [--verbosity=N]{bcolors.ENDC}
"""
extension_transfer_usage = f"""  {bcolors.BOLD}weectl extension transfer \\
           [--config=CONFIG-PATH] \\
           [--old=OLD-USERDIR] \\
           [--dry-run] [--verbosity=N]{bcolors.ENDC}
"""
extension_usage = '\n     '.join((extension_list_usage,
                                  extension_install_usage,
                                  extension_uninstall_usage,
                                  extension_transfer_usage))


def add_subparser(subparsers):
    extension_parser = subparsers.add_parser('extension',
                                             usage=extension_usage,
                                             description='Manages WeeWX extensions',
                                             help="Install, uninstall, or list "
                                                  "extensions")
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = extension_parser.add_subparsers(dest='action',
                                                    prog='weectl extension',
                                                    title="Which action to take")

    # ---------- Action 'list' ----------
    list_extension_parser = action_parser.add_parser('list',
                                                     usage=extension_list_usage,
                                                     help='List all installed extensions')
    list_extension_parser.add_argument('--config',
                                       metavar='CONFIG-PATH',
                                       help=f'Path to configuration file. '
                                            f'Default is "{weecfg.default_config_path}".')
    list_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                       help="How much information to display {0-3}.")
    list_extension_parser.set_defaults(func=list_extensions)

    # ---------- Action 'install' ----------
    install_extension_parser = \
        action_parser.add_parser('install',
                                 usage=extension_install_usage,
                                 help="Install an extension contained in FILENAME "
                                      " (such as pmon.tar.gz), or from a DIRECTORY, or from "
                                      " an URL.")
    install_extension_parser.add_argument('source',
                                          help="Location of the extension. It can be a path to a "
                                               "zipfile or tarball, a path to an unpacked "
                                               "directory, or an URL pointing to a zipfile "
                                               "or tarball.")
    install_extension_parser.add_argument('--config',
                                          metavar='CONFIG-PATH',
                                          help=f'Path to configuration file. '
                                               f'Default is "{weecfg.default_config_path}".')
    install_extension_parser.add_argument('--dry-run',
                                          action='store_true',
                                          help='Print what would happen, but do not actually '
                                               'do it.')
    install_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                          help="How much information to display {0-3}.")
    install_extension_parser.set_defaults(func=install_extension)

    # ---------- Action uninstall' ----------
    uninstall_extension_parser = \
        action_parser.add_parser('uninstall',
                                 usage=extension_uninstall_usage,
                                 help="Uninstall an extension")
    uninstall_extension_parser.add_argument('name',
                                            help="Name of the extension to uninstall.")
    uninstall_extension_parser.add_argument('--config',
                                            metavar='CONFIG-PATH',
                                            help=f'Path to configuration file. '
                                                 f'Default is "{weecfg.default_config_path}".')
    uninstall_extension_parser.add_argument('--dry-run',
                                            action='store_true',
                                            help='Print what would happen, but do not actually '
                                                 'do it.')
    uninstall_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                            help="How much information to display {0-3}.")
    uninstall_extension_parser.set_defaults(func=uninstall_extension)

    # ---------- Action 'transfer' ----------
    transfer_extension_parser = action_parser.add_parser('transfer',
                                                         usage=extension_transfer_usage,
                                                         help='Migrate old extensions to this '
                                                              'installation.')
    transfer_extension_parser.add_argument('--config',
                                           metavar='CONFIG-PATH',
                                           help=f'Path to configuration file. '
                                                f'Default is "{weecfg.default_config_path}".')
    transfer_extension_parser.add_argument('--old',
                                           metavar='OLD-USERDIR',
                                           default= OLD_USER_DIR,
                                           help=f'Path to the old user directory. Default '
                                                f'is {OLD_USER_DIR}.')
    transfer_extension_parser.add_argument('--dry-run',
                                           action='store_true',
                                           help='Print what would happen, but do not actually '
                                                'do it.')
    transfer_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                           help="How much information to display {0-3}.")
    transfer_extension_parser.set_defaults(func=transfer_extensions)


def list_extensions(namespace):
    ext = _get_extension_engine(namespace.config)
    ext.enumerate_extensions()


def install_extension(namespace):
    ext = _get_extension_engine(namespace.config, namespace.dry_run, namespace.verbosity)
    ext.install_extension(namespace.source)


def uninstall_extension(namespace):
    ext = _get_extension_engine(namespace.config, namespace.dry_run, namespace.verbosity)
    ext.uninstall_extension(namespace.name)


def transfer_extensions(namespace):
    ext = _get_extension_engine(namespace.config, namespace.dry_run, namespace.verbosity)
    ext.transfer(namespace.old)


def _get_extension_engine(config_path, dry_run=False, verbosity=1):
    config_path, config_dict = weecfg.read_config(config_path)

    # Set weewx.debug as necessary:
    weewx.debug = to_int(config_dict.get('debug', 0))

    # Customize the logging with user settings.
    weeutil.logger.setup('weectl', config_dict)

    ext = weecfg.extension.ExtensionEngine(config_path=config_path,
                                           config_dict=config_dict,
                                           dry_run=dry_run,
                                           logger=weecfg.Logger(verbosity=verbosity))

    return ext
