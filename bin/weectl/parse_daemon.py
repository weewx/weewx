#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "daemon" subcommand."""

daemon_install_usage = "weectl daemon install --type={sysv|systemd} [--config=CONFIG-PATH]"
daemon_uninstall_usage = "weectl daemon uninstall  --type={sysv|systemd} [--config=CONFIG-PATH]"

daemon_usage = "\n       ".join((daemon_install_usage, daemon_uninstall_usage))


def add_subparser(subparsers):
    daemon_parser = subparsers.add_parser("daemon",
                                          usage=daemon_usage,
                                          help="Install or uninstall a daemon file")

    action_parser = daemon_parser.add_subparsers(dest='action',
                                                 title="Which action to take")

    # Action "install':
    action_install_parser = action_parser.add_parser("install",
                                                     description="Install an appropriate system "
                                                                 "file to run weewxd as a daemon. "
                                                                 "You must specify the type of file "
                                                                 "using option --type.",
                                                     usage=daemon_install_usage,
                                                     help="Install a daemon file")

    action_install_parser.add_argument('--type',
                                       choices=['sysv', 'systemd'],
                                       required=True,
                                       help="Type of file to install. Required.")

    # Action "uninstall":
    action_uninstall_parser = action_parser.add_parser("uninstall",
                                                       description="After uninstalling, weewxd will "
                                                                   "not run as a daemon.",
                                                       usage=daemon_uninstall_usage,
                                                       help="Uninstall a daemon file")

    action_uninstall_parser.add_argument('--type',
                                         choices=['sysv', 'systemd'],
                                         required=True,
                                         help="Type of file to uninstall. Required.")
