#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Install and remove extensions."""
import weecfg
import weecfg.extension
import weectllib
from weeutil.printer import Printer
from weeutil.weeutil import bcolors

extension_list_usage = f"""{bcolors.BOLD}weectl extension list
            [--config=FILENAME]{bcolors.ENDC}
"""
extension_install_usage = f"""  {bcolors.BOLD}weectl extension install (FILE|DIR|URL)
            [--config=FILENAME]
            [--dry-run] [--yes] [--verbosity=N]{bcolors.ENDC}
"""
extension_uninstall_usage = f"""  {bcolors.BOLD}weectl extension uninstall NAME
            [--config=FILENAME]
            [--dry-run] [--yes] [--verbosity=N]{bcolors.ENDC}
"""
extension_usage = '\n     '.join((extension_list_usage,
                                  extension_install_usage,
                                  extension_uninstall_usage))


def add_subparser(subparsers):
    extension_parser = subparsers.add_parser('extension',
                                             usage=extension_usage,
                                             description='Manages WeeWX extensions',
                                             help="List, install, or uninstall extensions.")
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = extension_parser.add_subparsers(dest='action',
                                                    prog='weectl extension',
                                                    title="Which action to take")

    # ---------- Action 'list' ----------
    list_extension_parser = action_parser.add_parser('list',
                                                     description="List all installed extensions",
                                                     usage=extension_list_usage,
                                                     help='List all installed extensions')
    list_extension_parser.add_argument('--config',
                                       metavar='FILENAME',
                                       help=f'Path to configuration file. '
                                            f'Default is "{weecfg.default_config_path}".')
    list_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                       help="How much information to display (0|1|2|3).")
    list_extension_parser.set_defaults(func=weectllib.dispatch)
    list_extension_parser.set_defaults(action_func=list_extensions)

    # ---------- Action 'install' ----------
    install_extension_parser = \
        action_parser.add_parser('install',
                                 description="Install an extension contained in FILE "
                                             " (such as pmon.tar.gz), directory (DIR), or from "
                                             " an URL.",
                                 usage=extension_install_usage,
                                 help="Install an extension contained in FILE "
                                      " (such as pmon.tar.gz), directory (DIR), or from "
                                      " an URL.")
    install_extension_parser.add_argument('source',
                                          help="Location of the extension. It can be a path to a "
                                               "zipfile or tarball, a path to an unpacked "
                                               "directory, or an URL pointing to a zipfile "
                                               "or tarball.")
    install_extension_parser.add_argument('--config',
                                          metavar='FILENAME',
                                          help=f'Path to configuration file. '
                                               f'Default is "{weecfg.default_config_path}".')
    install_extension_parser.add_argument('--dry-run',
                                          action='store_true',
                                          help='Print what would happen, but do not actually '
                                               'do it.')
    install_extension_parser.add_argument('-y', '--yes', action='store_true',
                                          help="Don't ask for confirmation. Just do it.")
    install_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                          help="How much information to display (0|1|2|3).")
    install_extension_parser.set_defaults(func=weectllib.dispatch)
    install_extension_parser.set_defaults(action_func=install_extension)

    # ---------- Action uninstall' ----------
    uninstall_extension_parser = \
        action_parser.add_parser('uninstall',
                                 description="Uninstall an extension",
                                 usage=extension_uninstall_usage,
                                 help="Uninstall an extension")
    uninstall_extension_parser.add_argument('name',
                                            metavar='NAME',
                                            help="Name of the extension to uninstall.")
    uninstall_extension_parser.add_argument('--config',
                                            metavar='FILENAME',
                                            help=f'Path to configuration file. '
                                                 f'Default is "{weecfg.default_config_path}".')
    uninstall_extension_parser.add_argument('--dry-run',
                                            action='store_true',
                                            help='Print what would happen, but do not actually '
                                                 'do it.')
    uninstall_extension_parser.add_argument('-y', '--yes', action='store_true',
                                            help="Don't ask for confirmation. Just do it.")
    uninstall_extension_parser.add_argument('--verbosity', type=int, default=1, metavar='N',
                                            help="How much information to display (0|1|2|3).")
    uninstall_extension_parser.set_defaults(func=weectllib.dispatch)
    uninstall_extension_parser.set_defaults(action_func=uninstall_extension)


def list_extensions(config_dict, _):
    ext = _get_extension_engine(config_dict)
    ext.enumerate_extensions()


def install_extension(config_dict, namespace):
    ext = _get_extension_engine(config_dict, namespace.dry_run, namespace.verbosity)
    ext.install_extension(namespace.source, no_confirm=namespace.yes)


def uninstall_extension(config_dict, namespace):
    ext = _get_extension_engine(config_dict, namespace.dry_run, namespace.verbosity)
    ext.uninstall_extension(namespace.name, no_confirm=namespace.yes)


def _get_extension_engine(config_dict, dry_run=False, verbosity=1):
    ext = weecfg.extension.ExtensionEngine(config_path=config_dict['config_path'],
                                           config_dict=config_dict,
                                           dry_run=dry_run,
                                           printer=Printer(verbosity=verbosity))

    return ext
