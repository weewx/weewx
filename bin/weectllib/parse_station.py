#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "station" subcommand."""
import sys

import weecfg.station_config
import weewx
from weeutil.weeutil import bcolors

station_create_usage = f"""{bcolors.BOLD}weectl station create [--config=CONFIG-PATH] \\
                             [--driver=DRIVER] \\
                             [--location=LOCATION] \\
                             [--altitude=ALTITUDE,{{foot|meter}}] \\
                             [--latitude=LATITUDE] [--longitude=LONGITUDE] \\
                             [--register={{y,n}} [--station-url=STATION_URL]] \\
                             [--units={{us,metricwx,metric}}] \\
                             [--skin-root=SKIN_ROOT] \\
                             [--sqlite-root=SQLITE_ROOT] \\
                             [--html-root=HTML_ROOT] \\
                             [--user-root=USER_ROOT] \\
                             [--docs-root=DOCS_ROOT] \\
                             [--examples-root=EXAMPLES_ROOT] \\
                             [--no-prompt]{bcolors.ENDC}
"""
station_reconfigure_usage = f"""{bcolors.BOLD}weectl station reconfigure [--config=CONFIG-PATH] \\ 
                                  [--driver=DRIVER] \\
                                  [--location=LOCATION] \\
                                  [--altitude=ALTITUDE,{{foot|meter}}] \\
                                  [--latitude=LATITUDE] [--longitude=LONGITUDE] \\
                                  [--register={{y,n}} [--station-url=STATION_URL]] \\
                                  [--units={{us,metricwx,metric}}] \\
                                  [--skin-root=SKIN_ROOT] \\
                                  [--sqlite-root=SQLITE_ROOT] \\
                                  [--html-root=HTML_ROOT] \\
                                  [--no-prompt]{bcolors.ENDC}
"""
station_upgrade_usage = f'{bcolors.BOLD}weectl station upgrade [--config=CONFIG-PATH]{bcolors.ENDC}'
station_upgrade_skins_usage = f'{bcolors.BOLD}weectl station upgrade-skins ' \
                              f'[--config=CONFIG-PATH]{bcolors.ENDC}'

station_usage = '\n       '.join((station_create_usage, station_reconfigure_usage,
                                  station_upgrade_usage, station_upgrade_skins_usage))

CREATE_DESCRIPTION = f"""In what follows, {bcolors.BOLD}WEEWX_ROOT{bcolors.ENDC} is the directory 
that contains the configuration file. For example, if "--config={weecfg.default_config_path}", 
then WEEWX_ROOT will be "{weecfg.default_weewx_root}"."""


def add_subparser(subparsers):
    """Add the parsers used to implement the 'station' command. """
    station_parser = subparsers.add_parser('station',
                                           usage=station_usage,
                                           description='Manages the configuration file and skins',
                                           help='Create, modify, or upgrade a config file')
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = station_parser.add_subparsers(dest='action',
                                                  prog='weectl station',
                                                  title='Which action to take')

    # ---------- Action 'create' ----------
    station_create_parser = action_parser.add_parser('create',
                                                     description=CREATE_DESCRIPTION,
                                                     usage=station_create_usage,
                                                     help='Create a station config file')
    station_create_parser.add_argument('--config',
                                       metavar='CONFIG-PATH',
                                       help=f'Path to configuration file. It must not already '
                                            f'exist. Default is "{weecfg.default_config_path}".')
    _add_common_args(station_create_parser)
    station_create_parser.add_argument('--user-root',
                                       help='Where to put the "user" directory, relative to '
                                       '$WEEWX_ROOT. Default is "lib/user"')
    station_create_parser.add_argument('--docs-root',
                                       help='Where to put the documentation, relative to '
                                       '$WEEWX_ROOT. Default is "docs".')
    station_create_parser.add_argument('--examples-root',
                                       help='Where to put the examples, relative to '
                                       '$WEEWX_ROOT. Default is "examples".')
    station_create_parser.add_argument('--no-prompt', action='store_true',
                                       help='If set, do not prompt. Use default values.')
    station_create_parser.set_defaults(func=create_station)

    # ---------- Action 'reconfigure' ----------
    station_reconfigure_parser = action_parser.add_parser('reconfigure',
                                                          usage=station_reconfigure_usage,
                                                          help='Reconfigure a station config file')

    station_reconfigure_parser.add_argument('--config',
                                            metavar='CONFIG-PATH',
                                            help=f'Path to configuration file. '
                                                 f'Default is "{weecfg.default_config_path}"')
    _add_common_args(station_reconfigure_parser)
    station_reconfigure_parser.add_argument('--no-prompt', action='store_true',
                                            help='If set, do not prompt. Use default values.')
    station_reconfigure_parser.set_defaults(func=reconfigure_station)

    # Action 'upgrade'
    station_upgrade_parser = \
        action_parser.add_parser('upgrade',
                                 usage=station_upgrade_usage,
                                 description='Upgrade the configuration file, docs, and examples',
                                 help='Upgrade the configuration file, docs, and examples')

    # Action 'upgrade-skins'
    station_upgrade_skins_parser = action_parser.add_parser('upgrade-skins',
                                                            usage=station_upgrade_skins_usage,
                                                            help='Upgrade the skins')


def create_station(namespace):
    try:
        weecfg.station_config.station_create(config_path=namespace.config,
                                             driver=namespace.driver,
                                             location=namespace.location,
                                             altitude=namespace.altitude,
                                             latitude=namespace.latitude,
                                             longitude=namespace.longitude,
                                             register=namespace.register,
                                             unit_system=namespace.unit_system,
                                             skin_root=namespace.skin_root,
                                             sqlite_root=namespace.sqlite_root,
                                             html_root=namespace.html_root,
                                             docs_root=namespace.docs_root,
                                             examples_root=namespace.examples_root,
                                             no_prompt=namespace.no_prompt)
    except weewx.ViolatedPrecondition as e:
        sys.exit(e)


def reconfigure_station(namespace):
    try:
        weecfg.station_config.station_reconfigure(config_path=namespace.config,
                                                  driver=namespace.driver,
                                                  location=namespace.location,
                                                  altitude=namespace.altitude,
                                                  latitude=namespace.latitude,
                                                  longitude=namespace.longitude,
                                                  register=namespace.register,
                                                  unit_system=namespace.unit_system,
                                                  skin_root=namespace.skin_root,
                                                  sqlite_root=namespace.sqlite_root,
                                                  html_root=namespace.html_root,
                                                  no_prompt=namespace.no_prompt)
    except weewx.ViolatedPrecondition as e:
        sys.exit(e)


def _add_common_args(parser):
    """Add common arguments"""
    parser.add_argument('--driver',
                        help='Driver to use. Default is "weewx.drivers.simulator".')
    parser.add_argument('--location',
                        help='A description of the station. This will be used '
                             'for report titles. Default is "WeeWX".')
    parser.add_argument('--altitude', metavar='ALTITUDE,{foot|meter}',
                        help='The station altitude in either feet or meters. '
                             'For example, "750,foot" or "320,meter". '
                             'Default is "0, foot".')
    parser.add_argument('--latitude',
                        help='The station latitude in decimal degrees. '
                             'Default is 0.00.')
    parser.add_argument('--longitude',
                        help='The station longitude in decimal degrees. '
                             'Default is 0.00.')
    parser.add_argument('--register', choices=['y', 'n'],
                        help='Register this station in the weewx registry? '
                             'Default is "n" (do not register).')
    parser.add_argument('--station-url',
                        help='Unique URL to be used if registering the station. '
                             'Required if the station is to be registered.')
    parser.add_argument('--units', choices=['us', 'metricwx', 'metric'],
                        dest='unit_system',
                        help='Set display units to us, metricwx, or metric. '
                             'Default is "us".')
    parser.add_argument('--skin-root',
                        help='Where to put the skins, relatve to $WEEWX_ROOT. Default is "skins".')
    parser.add_argument('--sqlite-root',
                        help='Where to put the SQLite database, relative to $WEEWX_ROOT. '
                             'Default is "archive".')
    parser.add_argument('--html-root',
                        help='Where to put the generated HTML and images, relative to WEEWX_ROOT. '
                             'Default is "public_html".')