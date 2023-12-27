#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point for the "station" subcommand."""
import os.path
import sys

import weecfg.station_config
import weectllib
import weewx
from weeutil.weeutil import bcolors

station_create_usage = f"""{bcolors.BOLD}weectl station create
            [--driver=DRIVER]
            [--location=LOCATION]
            [--altitude=ALTITUDE,(foot|meter)]
            [--latitude=LATITUDE] [--longitude=LONGITUDE]
            [--register=(y,n) [--station-url=URL]]
            [--units=(us|metricwx|metric)]
            [--weewx-root=DIRECTORY]
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
            [--weewx-root=DIRECTORY]
            [--skin-root=DIRECTORY]
            [--sqlite-root=DIRECTORY]
            [--html-root=DIRECTORY]
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
            [--no-prompt]
            [--config=FILENAME]
            [--dist-config=FILENAME]]
            [--dry-run]{bcolors.ENDC}
"""

station_usage = '\n       '.join((station_create_usage, station_reconfigure_usage,
                                  station_upgrade_usage))

WEEWX_ROOT_DESCRIPTION = f"""In what follows, {bcolors.BOLD}WEEWX_ROOT{bcolors.ENDC} is the
directory that contains the configuration file. For example, if 
"--config={weecfg.default_config_path}", then WEEWX_ROOT will be "{weecfg.default_weewx_root}"."""

CREATE_DESCRIPTION = """Create a new station data area, including a configuration file. """ \
                     + WEEWX_ROOT_DESCRIPTION

UPGRADE_DESCRIPTION = """Upgrade an existing station data area, including any combination of the 
examples, utility files, configuration file, and skins. """ + WEEWX_ROOT_DESCRIPTION


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
    station_create_parser = action_parser.add_parser('create',
                                                     description=CREATE_DESCRIPTION,
                                                     usage=station_create_usage,
                                                     help='Create a new station data area, '
                                                          'including a configuration file.')
    _add_common_args(station_create_parser)
    station_create_parser.add_argument('--user-root',
                                       metavar='DIRECTORY',
                                       help='Where to put the "user" directory, relative to '
                                            'WEEWX_ROOT. Default is "bin/user"')
    station_create_parser.add_argument('--examples-root',
                                       metavar='DIRECTORY',
                                       help='Where to put the examples, relative to '
                                            'WEEWX_ROOT. Default is "examples".')
    station_create_parser.add_argument('--no-prompt', action='store_true',
                                       help='Do not prompt. Use default values.')
    station_create_parser.add_argument('--config',
                                       metavar='FILENAME',
                                       help=f'Path to configuration file. It must not already '
                                            f'exist. Default is "{weecfg.default_config_path}".')
    station_create_parser.add_argument('--dist-config',
                                       metavar='FILENAME',
                                       help='Use configuration file DIST-CONFIG-PATH as the '
                                            'new configuration file. Default is to retrieve it '
                                            'from package resources. The average user is '
                                            'unlikely to need this option.')
    station_create_parser.add_argument('--dry-run',
                                       action='store_true',
                                       help='Print what would happen, but do not actually '
                                            'do it.')
    station_create_parser.set_defaults(func=create_station)

    # ---------- Action 'reconfigure' ----------
    station_reconfigure_parser = \
        action_parser.add_parser('reconfigure',
                                 usage=station_reconfigure_usage,
                                 help='Reconfigure a station configuration file.')

    _add_common_args(station_reconfigure_parser)
    station_reconfigure_parser.add_argument('--no-backup', action='store_true',
                                            help='Do not backup the old configuration file.')
    station_reconfigure_parser.add_argument('--no-prompt', action='store_true',
                                            help='Do not prompt. Use default values.')
    station_reconfigure_parser.add_argument('--config',
                                            metavar='FILENAME',
                                            help=f'Path to configuration file. '
                                                 f'Default is "{weecfg.default_config_path}"')
    station_reconfigure_parser.add_argument('--dry-run',
                                            action='store_true',
                                            help='Print what would happen, but do not actually '
                                                 'do it.')
    station_reconfigure_parser.set_defaults(func=weectllib.dispatch)
    station_reconfigure_parser.set_defaults(action_func=reconfigure_station)

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
    station_upgrade_parser.add_argument('--no-prompt', action='store_true',
                                        help='Do not prompt. Use default values.')
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
        config_dict = weecfg.station_config.station_create(config_path=namespace.config,
                                                           dist_config_path=namespace.dist_config,
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
                                                           examples_root=namespace.examples_root,
                                                           no_prompt=namespace.no_prompt,
                                                           dry_run=namespace.dry_run)
    except weewx.ViolatedPrecondition as e:
        sys.exit(e)
    script_dir = os.path.join(config_dict["WEEWX_ROOT"], "scripts")
    script_name = None
    if os.path.isdir('/etc/systemd'):
        script_name = 'setup-daemon.systemd'
    elif os.path.isdir('/etc/init.d'):
        script_name = 'setup-daemon.sysv'
    elif os.path.isdir('/Library/LaunchDaemons'):
        script_name = 'setup-daemon.macos'
    if script_name:
        print("\nYou can set up a daemon by running a script in the directory")
        print(f"  {script_dir}")
        path = os.path.join(script_dir, script_name)
        print(f"For example:")
        print(f"  {bcolors.BOLD}sudo {path}{bcolors.ENDC}")


def reconfigure_station(config_dict, namespace):
    """Map namespace to a call to station_reconfigure()"""
    try:
        weecfg.station_config.station_reconfigure(config_dict=config_dict,
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
                                                  no_prompt=namespace.no_prompt,
                                                  no_backup=namespace.no_backup,
                                                  dry_run=namespace.dry_run)
    except weewx.ViolatedPrecondition as e:
        sys.exit(e)


def upgrade_station(config_dict, namespace):
    weecfg.station_config.station_upgrade(config_dict=config_dict,
                                          dist_config_path=namespace.dist_config,
                                          examples_root=namespace.examples_root,
                                          skin_root=namespace.skin_root,
                                          what=namespace.what,
                                          no_prompt=namespace.no_prompt,
                                          no_backup=namespace.no_backup,
                                          dry_run=namespace.dry_run)


# ==============================================================================
#                            Utilities
# ==============================================================================

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
                             'Default is "0.00".')
    parser.add_argument('--longitude',
                        help='The station longitude in decimal degrees. '
                             'Default is "0.00".')
    parser.add_argument('--register', choices=['y', 'n'],
                        help='Register this station in the weewx registry? '
                             'Default is "n" (do not register).')
    parser.add_argument('--station-url',
                        metavar='URL',
                        help='Unique URL to be used if registering the station. '
                             'Required if the station is to be registered.')
    parser.add_argument('--units', choices=['us', 'metricwx', 'metric'],
                        dest='unit_system',
                        help='Set display units to us, metricwx, or metric. '
                             'Default is "us".')
    parser.add_argument('--weewx-root',
                        metavar='DIRECTORY',
                        help="Location of WEEWX_ROOT.")
    parser.add_argument('--skin-root',
                        metavar='DIRECTORY',
                        help='Where to put the skins, relatve to WEEWX_ROOT. Default is "skins".')
    parser.add_argument('--sqlite-root',
                        metavar='DIRECTORY',
                        help='Where to put the SQLite database, relative to WEEWX_ROOT. '
                             'Default is "archive".')
    parser.add_argument('--html-root',
                        metavar='DIRECTORY',
                        help='Where to put the generated HTML and images, relative to WEEWX_ROOT. '
                             'Default is "public_html".')
