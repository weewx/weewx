#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "daemon" subcommand."""
import weecfg.daemon_config
from weeutil.weeutil import bcolors

daemon_install_usage = f"""{bcolors.BOLD}weectl daemon install --type={{sysv|systemd}} 
            [--config=CONFIG-PATH] [--user=USER] 
            [--weewxd-path=WEEWXD-PATH] [-daemon-dir=DAEMON-DIR] {bcolors.ENDC}"""
daemon_uninstall_usage = f"""{bcolors.BOLD}weectl daemon uninstall  --type={{sysv|systemd}} 
            [--config=CONFIG-PATH]{bcolors.ENDC}"""

daemon_usage = "\n       ".join((daemon_install_usage, daemon_uninstall_usage))


def add_subparser(subparsers):
    daemon_parser = subparsers.add_parser("daemon",
                                          usage=daemon_usage,
                                          description='Manages the installing and uninstalling of '
                                                      'files necessary to run weewx as a daemon.',
                                          help="Install or uninstall a daemon file")

    action_parser = daemon_parser.add_subparsers(dest='action',
                                                 prog='weectl daemon',
                                                 title="Which action to take")

    # ---------- Action 'install' ----------
    daemon_install_parser = action_parser.add_parser("install",
                                                     description="Install an appropriate system "
                                                                 "file to run weewxd as a daemon. "
                                                                 "You must specify the type of file "
                                                                 "using option --type.",
                                                     usage=daemon_install_usage,
                                                     help="Install a daemon file")

    daemon_install_parser.add_argument('--type',
                                       choices=['sysv', 'systemd'],
                                       dest="daemon_type",
                                       required=True,
                                       help="Type of file to install. Required.")
    daemon_install_parser.add_argument('--config',
                                       metavar='CONFIG-PATH',
                                       help=f'Path to configuration file. '
                                            f'Default is "{weecfg.default_config_path}".')
    daemon_install_parser.add_argument('--user',
                                       help='Run as USER. If not given, "root" will be used.')
    daemon_install_parser.add_argument('--weewxd-path',
                                       help='Path to the weewxd.py file. If not given, it will '
                                            'be inferred')
    daemon_install_parser.add_argument('--daemon-dir',
                                       help='Path to the directory in which the finished daemon '
                                            'file should be put.')
    daemon_install_parser.set_defaults(func=daemon_install)

    # ---------- Action 'uninstall' ----------
    daemon_uninstall_parser = action_parser.add_parser("uninstall",
                                                       description="After uninstalling, weewxd will "
                                                                   "not run as a daemon.",
                                                       usage=daemon_uninstall_usage,
                                                       help="Uninstall a daemon file")

    daemon_uninstall_parser.add_argument('--type',
                                         choices=['sysv', 'systemd'],
                                         dest="daemon_type",
                                         required=True,
                                         help="Type of file to uninstall. Required.")

    daemon_uninstall_parser.set_defaults(func=daemon_uninstall)


def daemon_install(namespace):
    weecfg.daemon_config.daemon_install(namespace.daemon_type,
                                        config_path=namespace.config,
                                        user=namespace.user,
                                        weewxd_path=namespace.weewxd_path,
                                        daemon_dir=namespace.daemon_dir)


def daemon_uninstall(namespace):
    weecfg.daemon_config.daemon_uninstall(namespace.daemon_type)
