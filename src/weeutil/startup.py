#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities used when starting up a WeeWX application"""
import importlib
import logging
import os.path
import sys
import platform
import locale

import configobj

import weewx
import weecfg
import weeutil.logger
from weeutil.weeutil import bcolors

log = logging.getLogger(__name__)


def extract_roots(config_dict):
    """Get the location of the various root directories used by weewx.
    The extracted paths are *absolute* paths. That is, they are no longer relative to WEEWX_ROOT.

    Args:
        config_dict(dict): The configuration dictionary. It must contain a value for WEEWX_ROOT.
    Returns:
        dict[str, str]: Key is the type of root, value is its absolute location.
    """
    # Check if this dictionary is from a pre-V5 package install. If so, we have to patch
    # USER_ROOT to its new location.
    if 'USER_ROOT' not in config_dict and config_dict['WEEWX_ROOT'] == '/':
        user_root = '/etc/weewx/bin/user'
    else:
        user_root = config_dict.get('USER_ROOT', 'bin/user')

    root_dict = {
        'WEEWX_ROOT': config_dict['WEEWX_ROOT'],
        'USER_DIR': os.path.abspath(os.path.join(config_dict['WEEWX_ROOT'], user_root)),
        'BIN_DIR': os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
        'EXT_DIR': os.path.abspath(os.path.join(config_dict['WEEWX_ROOT'], user_root, 'installer'))
    }

    # Add SKIN_ROOT if it can be found:
    try:
        root_dict['SKIN_DIR'] = os.path.abspath(
            os.path.join(root_dict['WEEWX_ROOT'], config_dict['StdReport']['SKIN_ROOT'])
        )
    except KeyError:
        pass

    return root_dict


def initialize(config_dict):
    """Add user directory to PYTHONPATH; import user.extensions

    Args:
        config_dict(dict): The configuration dictionary

    Returns:
        tuple[str,str]: A tuple containing (WEEWX_ROOT, USER_ROOT)
    """

    root_dict = extract_roots(config_dict)

    # Add the 'user' package to PYTHONPATH
    parent_of_user_dir = os.path.abspath(os.path.join(root_dict['USER_DIR'], '..'))
    sys.path.append(parent_of_user_dir)

    # Now we can import user.extensions
    try:
        importlib.import_module('user.extensions')
    except ModuleNotFoundError as e:
        log.error("Cannot load user extensions: %s", e)

    return config_dict['WEEWX_ROOT'], root_dict['USER_DIR']

def start_app(log_label, log_name, config_option, config_arg):
    """Read the config file and log various bits of information"""

    try:
        config_path, config_dict = weecfg.read_config(config_option, [config_arg])
    except (IOError, configobj.ConfigObjError) as e:
        print(f"Error parsing config file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    print(f"Using configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC}")

    # Customize the logging with user settings.
    try:
        weeutil.logger.setup(log_label, config_dict)
    except Exception as e:
        print(f"Unable to set up logger: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    # Get a logger. This one will be customized with user settings
    logger = logging.getLogger(log_name)
    # Announce the startup
    logger.info("Initializing %s version %s", log_label, weewx.__version__)
    logger.info("Command line: %s", ' '.join(sys.argv))

    # Add USER_ROOT to PYTHONPATH, read user.extensions:
    weewx_root, user_module = initialize(config_dict)

    # Log key bits of information.
    logger.info("Using Python: %s", sys.version)
    logger.info("Located at:   %s", sys.executable)
    logger.info("Platform:     %s", platform.platform())
    logger.info("Locale:       '%s'", locale.setlocale(locale.LC_ALL))
    logger.info("Entry path:   %s", getattr(sys.modules['__main__'], '__file__', 'Unknown'))
    logger.info("WEEWX_ROOT:   %s", weewx_root)
    logger.info("Config file:  %s", config_path)
    logger.info("User module:  %s", user_module)
    logger.info("Debug:        %s", weewx.debug)

    # these try/except are because not every os will succeed here
    try:
        import pwd
        euid  = pwd.getpwuid(os.geteuid())[0]
        logger.info("User:         %s", euid)
    except Exception as ex:
        logger.info("User unavailable: %s",ex)

    try:
        import grp
        egid = grp.getgrgid(os.getegid())[0]
        logger.info("Group:        %s", egid)
        group_list = os.getgroups()
        mygroups = []
        for group in group_list:
            mygroups.append(grp.getgrgid(group)[0])
        mygrouplist = ' '.join(mygroups)
        logger.info("Groups:       %s", mygrouplist)
    except Exception as ex:
        logger.info("Groups unavailable: %s", ex)

    return config_path, config_dict, logger