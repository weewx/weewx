#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "station" subcommand."""
import os.path
import sys

import weecfg
import weectllib
import weectllib.station_actions
import weewx
from weeutil.weeutil import bcolors

station_create_usage = f"""{bcolors.BOLD}weectl station create [WEEWX-ROOT]
            [--driver=DRIVER]
            [--location=LOCATION]
            [--altitude=ALTITUDE,(foot|meter)]
            [--latitude=LATITUDE] [--longitude=LONGITUDE]
            [--register=(y,n) [--station-url=URL]]
            [--units=(us|metricwx|metric)]
            [--skin-root=DIRECTORY]
            [--sqlite-root=DIRECTORY]
            [--html-root=DIRECTORY]
            [--user-root=DIRECTORY]
            [--examples-root=DIRECTORY]
            [--no-prompt]
            [--config=FILENAME]
            [--dist-config=FILENAME]
            [--dry-run]{bcolors.ENDC}
"""
station_reconfigure_usage = f"""{bcolors.BOLD}weectl station reconfigure
            [--driver=DRIVER]
            [--location=LOCATION]
            [--altitude=ALTITUDE,(foot|meter)]
            [--latitude=LATITUDE] [--longitude=LONGITUDE]
            [--register=(y,n) [--station-url=URL]]
            [--units=(us|metricwx|metric)]
            [--skin-root=DIRECTORY]
            [--sqlite-root=DIRECTORY]
            [--html-root=DIRECTORY]
            [--user-root=DIRECTORY]
            [--weewx-root=DIRECTORY]
            [--no-backup]
            [--no-prompt]
            [--config=FILENAME] 
            [--dry-run]{bcolors.ENDC}
"""
station_upgrade_usage = f"""{bcolors.BOLD}weectl station upgrade
            [--examples-root=DIRECTORY]
            [--skin-root=DIRECTORY]
            [--what ITEM [ITEM ...]
            [--no-backup]
            [--yes]
            [--config=FILENAME]
            [--dist-config=FILENAME]]
            [--dry-run]{bcolors.ENDC}
"""

station_usage = '\n       '.join((station_create_usage, station_reconfigure_usage,
                                  station_upgrade_usage))

CREATE_DESCRIPTION = f"""Create a new station data area at the location WEEWX-ROOT. If WEEWX-ROOT 
is not provided, the location {weecfg.default_weewx_root} will be used."""

RECONFIGURE_DESCRIPTION = f"""Reconfigure an existing configuration file at the location given
by the --config option. If the option is not provided, the location {weecfg.default_config_path}
will be used. Unless the --no-prompt option has been specified, the user will be prompted for
new values."""

UPGRADE_DESCRIPTION = f"""Upgrade an existing station data area managed by the configuration file
given by the --config option. If the option is not provided, the location 
{weecfg.default_config_path} will be used. Any combination of the examples, utility files, 
configuration file, and skins can be upgraded, """


def add_subparser(subparsers):
    """Add the parsers used to implement the 'station' command. """
    station_parser = subparsers.add_parser('station',
                                           usage=station_usage,
                                           description='Manages the station data area, including '
                                                       'the configuration file and skins.',
                                           help='Create, modify, or upgrade a station data area.')
    # In the following, the 'prog' argument is necessary to get a proper error message.
    # See Python issue https://bugs.python.org/issue42297
    action_parser = station_parser.add_subparsers(dest='action',
                                                  prog='weectl station',
                                                  title='Which action to take')

    # ---------- Action 'create' ----------
    create_parser = action_parser.add_parser('create',
                                             description=CREATE_DESCRIPTION,
                                             usage=station_create_usage,
                                             help='Create a new station data area, including a '
                                                  'configuration file.')
    create_parser.add_argument('--driver',
                               help='Driver to use. Default is "weewx.drivers.simulator".')
    create_parser.add_argument('--location',
                               help='A description of the station. This will be used for report '
                                    'titles. Default is "WeeWX".')
    create_parser.add_argument('--altitude', metavar='ALTITUDE,{foot|meter}',
                               help='The station altitude in either feet or meters. For example, '
                                    '"750,foot" or "320,meter". Default is "0, foot".')
    create_parser.add_argument('--latitude',
                               help='The station latitude in decimal degrees. Default is "0.00".')
    create_parser.add_argument('--longitude',
                               help='The station longitude in decimal degrees. Default is "0.00".')
    create_parser.add_argument('--register', choices=['y', 'n'],
                               help='Register this station in the weewx registry? Default is "n" '
                                    '(do not register).')
    create_parser.add_argument('--station-url',
                               metavar='URL',
                               help='Unique URL to be used if registering the station. Required '
                                    'if the station is to be registered.')
    create_parser.add_argument('--units', choices=['us', 'metricwx', 'metric'],
                               dest='unit_system',
                               help='Set display units to us, metricwx, or metric. '
                                    'Default is "us".')
    create_parser.add_argument('--skin-root',
                               metavar='DIRECTORY',
                               help='Where to put the skins, relatve to WEEWX_ROOT. '
                                    'Default is "skins".')
    create_parser.add_argument('--sqlite-root',
                               metavar='DIRECTORY',
                               help='Where to put the SQLite database, relative to WEEWX_ROOT. '
                                    'Default is "archive".')
    create_parser.add_argument('--html-root',
                               metavar='DIRECTORY',
                               help='Where to put the generated HTML and images, relative to '
                                    'WEEWX_ROOT. Default is "public_html".')
    create_parser.add_argument('--user-root',
                               metavar='DIRECTORY',
                               help='Where to put the user extensions, relative to WEEWX_ROOT. '
                                    'Default is "bin/user".')
    create_parser.add_argument('--examples-root',
                               metavar='DIRECTORY',
                               help='Where to put the examples, relative to WEEWX_ROOT. '
                                    'Default is "examples".')
    create_parser.add_argument('--no-prompt', action='store_true',
                               help='Do not prompt. Use default values.')
    create_parser.add_argument('--config',
                               metavar='FILENAME',
                               help='Where to put the configuration file, relative to WEEWX-ROOT. '
                                    'It must not already exist. Default is "./weewx.conf".')
    create_parser.add_argument('--dist-config',
                               metavar='FILENAME',
                               help='Use configuration file DIST-CONFIG-PATH as the new '
                                    'configuration file. Default is to retrieve it from package '
                                    'resources. The average user is unlikely to need this option.')
    create_parser.add_argument('--dry-run',
                               action='store_true',
                               help='Print what would happen, but do not actually do it.')
    create_parser.add_argument('weewx_root',
                               nargs='?',
                               metavar='WEEWX_ROOT',
                               help='Path to the WeeWX station data area to be created. '
                                    f'Default is {weecfg.default_weewx_root}.')
    create_parser.set_defaults(func=create_station)

    # ---------- Action 'reconfigure' ----------
    reconfigure_parser = \
        action_parser.add_parser('reconfigure',
                                 description=RECONFIGURE_DESCRIPTION,
                                 usage=station_reconfigure_usage,
                                 help='Reconfigure an existing station configuration file.')

    reconfigure_parser.add_argument('--driver',
                                    help='New driver to use. Default is the old driver.')
    reconfigure_parser.add_argument('--location',
                                    help='A new description for the station. This will be used '
                                         'for report titles. Default is the old description.')
    reconfigure_parser.add_argument('--altitude', metavar='ALTITUDE,{foot|meter}',
                                    help='The new station altitude in either feet or meters. '
                                         'For example, "750,foot" or "320,meter". '
                                         'Default is the old altitude.')
    reconfigure_parser.add_argument('--latitude',
                                    help='The new station latitude in decimal degrees. '
                                         'Default is the old latitude.')
    reconfigure_parser.add_argument('--longitude',
                                    help='The new station longitude in decimal degrees. '
                                         'Default is the old longitude.')
    reconfigure_parser.add_argument('--register', choices=['y', 'n'],
                                    help='Register this station in the weewx registry? '
                                         'Default is the old value.')
    reconfigure_parser.add_argument('--station-url',
                                    metavar='URL',
                                    help='A new unique URL to be used if registering the . '
                                         'station. Default is the old URL.')
    reconfigure_parser.add_argument('--units', choices=['us', 'metricwx', 'metric'],
                                    dest='unit_system',
                                    help='New display units. Set to to us, metricwx, or metric. '
                                         'Default is the old unit system.')
    reconfigure_parser.add_argument('--skin-root',
                                    metavar='DIRECTORY',
                                    help='New location where to find the skins, relatve '
                                         'to WEEWX_ROOT. Default is the old location.')
    reconfigure_parser.add_argument('--sqlite-root',
                                    metavar='DIRECTORY',
                                    help='New location where to find the SQLite database, '
                                         'relative to WEEWX_ROOT. Default is the old location.')
    reconfigure_parser.add_argument('--html-root',
                                    metavar='DIRECTORY',
                                    help='New location where to put the generated HTML and '
                                         'images, relative to WEEWX_ROOT. '
                                         'Default is the old location.')
    reconfigure_parser.add_argument('--user-root',
                                    metavar='DIRECTORY',
                                    help='New location where to find the user extensions, '
                                         'relative to WEEWX_ROOT. Default is the old location.')
    reconfigure_parser.add_argument('--weewx-root',
                                    metavar='WEEWX_ROOT',
                                    help='New path to the WeeWX station data area. '
                                         'Default is the old path.')
    reconfigure_parser.add_argument('--no-backup', action='store_true',
                                    help='Do not backup the old configuration file.')
    reconfigure_parser.add_argument('--no-prompt', action='store_true',
                                    help='Do not prompt. Use default values.')
    reconfigure_parser.add_argument('--config',
                                    metavar='FILENAME',
                                    help=f'Path to configuration file. '
                                         f'Default is "{weecfg.default_config_path}"')
    reconfigure_parser.add_argument('--dry-run',
                                    action='store_true',
                                    help='Print what would happen, but do not actually '
                                         'do it.')
    reconfigure_parser.set_defaults(func=weectllib.dispatch)
    reconfigure_parser.set_defaults(action_func=reconfigure_station)

    # ---------- Action 'upgrade' ----------
    station_upgrade_parser = \
        action_parser.add_parser('upgrade',
                                 usage=station_upgrade_usage,
                                 description=UPGRADE_DESCRIPTION,
                                 help='Upgrade any combination of the examples, utility '
                                      'files, configuration file, and skins.')

    station_upgrade_parser.add_argument('--examples-root',
                                        metavar='DIRECTORY',
                                        help='Where to put the new examples, relative to '
                                             'WEEWX_ROOT. Default is "examples".')
    station_upgrade_parser.add_argument('--skin-root',
                                        metavar='DIRECTORY',
                                        help='Where to put the skins, relative to '
                                             'WEEWX_ROOT. Default is "skins".')
    station_upgrade_parser.add_argument('--what',
                                        choices=['examples', 'util', 'config', 'skins'],
                                        default=['examples', 'util'],
                                        nargs='+',
                                        metavar='ITEM',
                                        help="What to upgrade. Choose from 'examples', 'util', "
                                             "'skins', 'config', or some combination, "
                                             "separated by spaces. Default is to upgrade the "
                                             "examples, and utility files.")
    station_upgrade_parser.add_argument('--no-backup', action='store_true',
                                        help='Do not backup the old configuration file.')
    station_upgrade_parser.add_argument('-y', '--yes', action='store_true',
                                          help="Don't ask for confirmation. Just do it.")
    station_upgrade_parser.add_argument('--config',
                                        metavar='FILENAME',
                                        help=f'Path to configuration file. '
                                             f'Default is "{weecfg.default_config_path}"')
    station_upgrade_parser.add_argument('--dist-config',
                                        metavar='FILENAME',
                                        help='Use configuration file FILENAME as the '
                                             'new configuration file. Default is to retrieve it '
                                             'from package resources. The average user is '
                                             'unlikely to need this option.')
    station_upgrade_parser.add_argument('--dry-run',
                                        action='store_true',
                                        help='Print what would happen, but do not actually '
                                             'do it.')
    station_upgrade_parser.set_defaults(func=weectllib.dispatch)
    station_upgrade_parser.set_defaults(action_func=upgrade_station)


# ==============================================================================
#                        Action invocations
# ==============================================================================


def create_station(namespace):
    """Map 'namespace' to a call to station_create()"""
    try:
        config_dict = weectllib.station_actions.station_create(
            weewx_root=namespace.weewx_root,
            rel_config_path=namespace.config,
            driver=namespace.driver,
            location=namespace.location,
            altitude=namespace.altitude,
            latitude=namespace.latitude,
            longitude=namespace.longitude,
            register=namespace.register,
            station_url=namespace.station_url,
            unit_system=namespace.unit_system,
            skin_root=namespace.skin_root,
            sqlite_root=namespace.sqlite_root,
            html_root=namespace.html_root,
            examples_root=namespace.examples_root,
            user_root=namespace.user_root,
            dist_config_path=namespace.dist_config,
            no_prompt=namespace.no_prompt,
            dry_run=namespace.dry_run)
    except weewx.ViolatedPrecondition as e:
        sys.exit(str(e))


def reconfigure_station(config_dict, namespace):
    """Map namespace to a call to station_reconfigure()"""
    try:
        weectllib.station_actions.station_reconfigure(config_dict=config_dict,
                                                      driver=namespace.driver,
                                                      location=namespace.location,
                                                      altitude=namespace.altitude,
                                                      latitude=namespace.latitude,
                                                      longitude=namespace.longitude,
                                                      register=namespace.register,
                                                      station_url=namespace.station_url,
                                                      unit_system=namespace.unit_system,
                                                      weewx_root=namespace.weewx_root,
                                                      skin_root=namespace.skin_root,
                                                      sqlite_root=namespace.sqlite_root,
                                                      html_root=namespace.html_root,
                                                      user_root=namespace.user_root,
                                                      no_prompt=namespace.no_prompt,
                                                      no_backup=namespace.no_backup,
                                                      dry_run=namespace.dry_run)
    except weewx.ViolatedPrecondition as e:
        sys.exit(str(e))


def upgrade_station(config_dict, namespace):
    weectllib.station_actions.station_upgrade(config_dict=config_dict,
                                              dist_config_path=namespace.dist_config,
                                              examples_root=namespace.examples_root,
                                              skin_root=namespace.skin_root,
                                              what=namespace.what,
                                              no_confirm=namespace.yes,
                                              no_backup=namespace.no_backup,
                                              dry_run=namespace.dry_run)
