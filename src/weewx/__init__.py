#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Package weewx, containing modules specific to the weewx runtime engine."""
import importlib
import os.path
import sys
import time

import weeutil.logger
from weeutil.weeutil import to_int

__version__ = "5.0.0b16"

# Holds the program launch time in unix epoch seconds:
# Useful for calculating 'uptime.'
launchtime_ts = time.time()

# Set to true for extra debug information:
debug = False

# Exit return codes
CMD_ERROR = 2
CONFIG_ERROR = 3
IO_ERROR = 4
DB_ERROR = 5

# Constants used to indicate a unit system:
METRIC = 0x10
METRICWX = 0x11
US = 0x01


# =============================================================================
#           Define possible exceptions that could get thrown.
# =============================================================================

class WeeWxIOError(IOError):
    """Base class of exceptions thrown when encountering an input/output error
    with the hardware."""


class WakeupError(WeeWxIOError):
    """Exception thrown when unable to wake up or initially connect with the
    hardware."""


class CRCError(WeeWxIOError):
    """Exception thrown when unable to pass a CRC check."""


class RetriesExceeded(WeeWxIOError):
    """Exception thrown when max retries exceeded."""


class HardwareError(Exception):
    """Exception thrown when an error is detected in the hardware."""


class UnknownArchiveType(HardwareError):
    """Exception thrown after reading an unrecognized archive type."""


class UnsupportedFeature(Exception):
    """Exception thrown when attempting to access a feature that is not
    supported (yet)."""


class ViolatedPrecondition(Exception):
    """Exception thrown when a function is called with violated
    preconditions."""


class StopNow(Exception):
    """Exception thrown to stop the engine."""


class UnknownDatabase(Exception):
    """Exception thrown when attempting to use an unknown database."""


class UnknownDatabaseType(Exception):
    """Exception thrown when attempting to use an unknown database type."""


class UnknownBinding(Exception):
    """Exception thrown when attempting to use an unknown data binding."""


class UnitError(ValueError):
    """Exception thrown when there is a mismatch in unit systems."""


class UnknownType(ValueError):
    """Exception thrown for an unknown observation type"""


class UnknownAggregation(ValueError):
    """Exception thrown for an unknown aggregation type"""


class CannotCalculate(ValueError):
    """Exception raised when a type cannot be calculated."""


class NoCalculate(Exception):
    """Exception raised when a type does not need to be calculated."""


# =============================================================================
#                       Possible event types.
# =============================================================================

class STARTUP(object):
    """Event issued when the engine first starts up. Services have been
    loaded."""


class PRE_LOOP(object):
    """Event issued just before the main packet loop is entered. Services
    have been loaded."""


class NEW_LOOP_PACKET(object):
    """Event issued when a new LOOP packet is available. The event contains
    attribute 'packet', which is the new LOOP packet."""


class CHECK_LOOP(object):
    """Event issued in the main loop, right after a new LOOP packet has been
    processed. Generally, it is used to throw an exception, breaking the main
    loop, so the console can be used for other things."""


class END_ARCHIVE_PERIOD(object):
    """Event issued at the end of an archive period."""


class NEW_ARCHIVE_RECORD(object):
    """Event issued when a new archive record is available. The event contains
    attribute 'record', which is the new archive record."""


class POST_LOOP(object):
    """Event issued right after the main loop has been broken. Services hook
    into this to access the console for things other than generating LOOP
    packet."""


# =============================================================================
#                       Service groups.
# =============================================================================

# All existent service groups and the order in which they should be run:
all_service_groups = ['prep_services', 'data_services', 'process_services', 'xtype_services',
                      'archive_services', 'restful_services', 'report_services']


# =============================================================================
#                       Class Event
# =============================================================================
class Event(object):
    """Represents an event."""

    def __init__(self, event_type, **argv):
        self.event_type = event_type

        for key in argv:
            setattr(self, key, argv[key])

    def __str__(self):
        """Return a string with a reasonable representation of the event."""
        et = "Event type: %s | " % self.event_type
        s = "; ".join("%s: %s" % (k, self.__dict__[k]) for k in self.__dict__ if k != "event_type")
        return et + s


# =============================================================================
#                           Utilities
# =============================================================================


def require_weewx_version(module, required_version):
    """utility to check for version compatibility"""
    from weeutil.weeutil import version_compare
    if version_compare(__version__, required_version) < 0:
        raise UnsupportedFeature("%s requires weewx %s or greater, found %s"
                                 % (module, required_version, __version__))


def add_user_path(config_dict):
    """add the path to the parent of the user directory to PYTHONPATH."""
    root_dict = extract_roots(config_dict)
    lib_dir = os.path.abspath(os.path.join(root_dict['USER_DIR'], '..'))
    sys.path.append(lib_dir)


def extract_roots(config_dict):
    """Get the location of the various root directories used by weewx.
    The extracted paths are *absolute* paths. That is, they are no longer relative to WEEWX_ROOT.

    Args:
        config_dict(dict): The configuration dictionary
    Returns:
        dict[str, str]: Key is the type of root, value is its location.
    """
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


def initialize(config_dict, log_label):
    """Set debug, set up the logger, and add the user path"""
    global debug

    # Set weewx.debug as necessary:
    debug = to_int(config_dict.get('debug', 0))

    # Customize the logging with user settings.
    weeutil.logger.setup(log_label, config_dict)

    # Add the 'user' package to PYTHONPATH
    add_user_path(config_dict)
    # Now we can import user.extensions
    importlib.import_module('user.extensions')
