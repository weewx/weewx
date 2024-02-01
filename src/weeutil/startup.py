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
    """Set debug, set up the logger, and add the user path

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
