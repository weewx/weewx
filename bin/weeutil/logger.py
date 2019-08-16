#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""WeeWX logging facility"""

from __future__ import absolute_import

import sys
import logging.config
from six.moves import StringIO

import configobj

import weewx
from weeutil.weeutil import to_int, to_bool

if sys.platform == "darwin":
    address = '/var/run/syslog'
    facility = 'local1'
elif sys.platform.startswith('linux'):
    address = '/dev/log'
    facility = 'user'
else:
    address = ('localhost', 514)
    facility = 'user'

LOGGING_STR = u"""
version = 1
disable_existing_loggers = False
      
[loggers]
    # Root logger
    [[root]]
      level = {log_level}
      propagate = 1
      handlers = syslog,

# Definitions of possible logging destinations
[handlers]

    # System logger
    [[syslog]]
        level = DEBUG
        formatter = standard
        class = logging.handlers.SysLogHandler
        address = {address}
        facility = {facility}

    # Log to console
    [[console]]
        level = DEBUG
        formatter = verbose
        class = logging.StreamHandler
        # Alternate choice is 'ext://sys.stderr'
        stream = ext://sys.stdout

# How to format log messages
[formatters]
    [[simple]]
        format = %(levelname)s %(message)s
    [[standard]]
        format = "{process_name}[%(process)d]/%(levelname)s %(name)s: %(message)s" 
    [[verbose]]
        format = " %(asctime)s  {process_name}[%(process)d]/%(levelname)s %(name)s: %(message)s"
        # Format to use for dates and times:
        datefmt = %Y-%m-%d %H:%M:%S
"""


def setup(process_name, user_log_dict):
    """Set up the weewx logging facility"""

    log_level = 'DEBUG' if weewx.debug else 'INFO'

    # Get a ConfigObj containing the logging defaults. Start
    # with formatting the string with values known only at runtime:
    default_logging_str = LOGGING_STR.format(log_level=log_level,
                                             address=address,
                                             facility=facility,
                                             process_name=process_name)
    # Now create a ConfigObj from the string. No interpolation (it interferes with the
    # interpolation directives embedded in the string).
    log_config = configobj.ConfigObj(StringIO(default_logging_str), interpolation=False)

    # Merge in the user additions / changes:
    log_config.merge(user_log_dict)

    # The root logger is denoted by an empty string by the logging facility. Unfortunately,
    # ConfigObj does not accept an empty string as a key. So, instead, we use this hack:
    log_dict = log_config.dict()
    try:
        log_dict['loggers'][''] = log_dict['loggers']['root']
        del log_dict['loggers']['root']
    except KeyError:
        pass

    # Make sure values are of the right type
    if 'version' in log_dict:
        log_dict['version'] = to_int(log_dict['version'])
    if 'disable_existing_loggers' in log_dict:
        log_dict['disable_existing_loggers'] = to_bool(log_dict['disable_existing_loggers'])
    for logger in log_dict['loggers']:
        if 'propagate' in log_dict['loggers'][logger]:
            log_dict['loggers'][logger]['propagate'] = to_bool(log_dict['loggers'][logger]['propagate'])

    logging.config.dictConfig(log_dict)


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
