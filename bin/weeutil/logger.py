#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""WeeWX logging facility"""

from __future__ import absolute_import

import sys
import logging.config
import six
from six.moves import StringIO

import configobj

import weewx

# The logging defaults. Note that two kinds of placeholders are used:
#
#  {value}: these are plugged in by the function setup().
#  %(value)s: these are plugged in by the Python logging module.
#
LOGGING_STR = """[Logging]
    version = 1
    disable_existing_loggers = False

    # Root logger
    [[root]]
      level = {log_level}
      handlers = syslog,

    # Additional loggers would go in the following section. This is useful for tailoring logging
    # for individual modules.
    [[loggers]]

    # Definitions of possible logging destinations
    [[handlers]]

        # System logger
        [[[syslog]]]
            level = DEBUG
            formatter = standard
            class = logging.handlers.SysLogHandler
            address = {address}
            facility = {facility}

        # Log to console
        [[[console]]]
            level = DEBUG
            formatter = verbose
            class = logging.StreamHandler
            # Alternate choice is 'ext://sys.stderr'
            stream = ext://sys.stdout

    # How to format log messages
    [[formatters]]
        [[[simple]]]
            format = "%(levelname)s %(message)s"
        [[[standard]]]
            format = "{process_name}[%(process)d] %(levelname)s %(name)s: %(message)s" 
        [[[verbose]]]
            format = "%(asctime)s  {process_name}[%(process)d] %(levelname)s %(name)s: %(message)s"
            # Format to use for dates and times:
            datefmt = %Y-%m-%d %H:%M:%S
"""

# These values are known only at runtime
if sys.platform == "darwin":
    address = '/var/run/syslog'
    facility = 'local1'

    # Mac uses slightly different logging setup
    LOGGING_STR = """[Logging]
        version = 1
        disable_existing_loggers = False

        # Root logger
        [[root]]
          level = {log_level}
          handlers = rotate,
    
        # Additional loggers would go in the following section. This is useful for tailoring logging
        # for individual modules.
        [[loggers]]

        # Definitions of possible logging destinations
        [[handlers]]

            # Log to a set of rotating files    
            [[[rotate]]]
                level = DEBUG
                formatter = standard
                class = logging.handlers.RotatingFileHandler
                # Writing to this file will require root privileges:
                filename = /var/log/weewx.log
                maxBytes = 10000000
                backupCount = 4

            # Log to console
            [[[console]]]
                level = DEBUG
                formatter = verbose
                class = logging.StreamHandler
                # Alternate choice is 'ext://sys.stderr'
                stream = ext://sys.stdout

        # How to format log messages
        [[formatters]]
            [[[simple]]]
                format = "%(levelname)s %(message)s"
            [[[standard]]]
                format = "{process_name}[%(process)d] %(levelname)s %(name)s: %(message)s" 
            [[[verbose]]]
                format = "%(asctime)s  {process_name}[%(process)d] %(levelname)s %(name)s: %(message)s"
                # Format to use for dates and times:
                datefmt = %Y-%m-%d %H:%M:%S
    """
elif sys.platform.startswith('linux'):
    address = '/dev/log'
    facility = 'user'
elif sys.platform.startswith('freebsd'):
    address = '/var/run/log'
    facility = 'user'
elif sys.platform.startswith('netbsd'):
    address = '/var/run/log'
    facility = 'user'
elif sys.platform.startswith('openbsd'):
    address = '/dev/log'
    facility = 'user'
else:
    address = ('localhost', 514)
    facility = 'user'


def setup(process_name, user_log_dict):
    """Set up the weewx logging facility"""

    # Create a ConfigObj from the default string. No interpolation (it interferes with the
    # interpolation directives embedded in the string).
    log_config = configobj.ConfigObj(StringIO(LOGGING_STR), interpolation=False, encoding='utf-8')

    # Turn off interpolation in the incoming dictionary. First save the old
    # value, then restore later. However, the incoming dictionary may be a simple
    # Python dictionary and not have interpolation. Hence the try block.
    try:
        old_interpolation = user_log_dict.interpolation
        user_log_dict.interpolation = False
    except AttributeError:
        old_interpolation = None

    # Merge in the user additions / changes:
    log_config.merge(user_log_dict)

    # Adjust the logging level in accordance with whether or not the 'debug' flag is on
    log_level = 'DEBUG' if weewx.debug else 'INFO'

    # Now we need to walk the structure, plugging in the values we know.
    # First, we need a function to do this:
    def _fix(section, key):
        if isinstance(section[key], (list, tuple)):
            # The value is a list or tuple
            section[key] = [item.format(log_level=log_level,
                                        address=address,
                                        facility=facility,
                                        process_name=process_name) for item in section[key]]
        else:
            # The value is a string
            section[key] = section[key].format(log_level=log_level,
                                               address=address,
                                               facility=facility,
                                               process_name=process_name)

    # Using the function, walk the 'Logging' part of the structure
    log_config['Logging'].walk(_fix)

    # Now walk the structure again, this time converting any strings to an appropriate type:
    log_config['Logging'].walk(_convert_from_string)

    # Extract just the part used by Python's logging facility
    log_dict = log_config.dict().get('Logging', {})

    # Finally! The dictionary is ready. Set the defaults.
    logging.config.dictConfig(log_dict)

    # Restore the old interpolation value
    if old_interpolation is not None:
        user_log_dict.interpolation = old_interpolation


def log_traceback(log_fn, prefix=''):
    """Log the stack traceback into a logger.

    log_fn: One of the logging.Logger logging functions, such as logging.Logger.warning.

    prefix: A string, which will be put in front of each log entry. Default is no string.
    """
    import traceback
    sfd = StringIO()
    traceback.print_exc(file=sfd)
    sfd.seek(0)
    for line in sfd:
        log_fn("%s%s", prefix, line)


def _convert_from_string(section, key):
    """If possible, convert any strings to an appropriate type."""
    # Check to make sure it is a string
    if isinstance(section[key], six.string_types):
        if section[key].lower() == 'false':
            # It's boolean False
            section[key] = False
        elif section[key].lower() == 'true':
            # It's boolean True
            section[key] = True
        elif section[key].count('.') == 1:
            # Contains a decimal point. Could be float
            try:
                section[key] = float(section[key])
            except ValueError:
                pass
        else:
            # Try integer?
            try:
                section[key] = int(section[key])
            except ValueError:
                pass
