#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "daemon" subcommand."""


def add_subparser(subparsers):
    station_parser = subparsers.add_parser("daemon", help="Install or uninstall a daemon file")

    station_parser.add_argument("--install", action='store_true', help="Install sysv or systemd file")
    station_parser.add_argument("--uninstall", action='store_true', help="Install sysv or systemd file")
    station_parser.add_argument("--config", help="Path to the CONFIG_FILE")
    station_parser.add_argument("--type",
                                choices=['sysv', 'systemd'],
                                required=True,
                                help="Type of file to install or uninstall")
