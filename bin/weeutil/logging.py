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
import validate

import weewx

if sys.platform == "darwin":
    address = '/var/run/syslog'
    facility = 'local1'
elif sys.platform == 'linux2':
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
        format = "{process_name}[%(process)d]/%(levelname)s %(module)s: %(message)s" 
    [[verbose]]
        format = " %(asctime)s  {process_name}[%(process)d]/%(levelname)s %(module)s: %(message)s"
        # Format to use for dates and times:
        datefmt = %Y-%m-%d %H:%M:%S
"""

LOGGING_VALIDATOR = """
version = integer(default=1)
disable_existing_loggers = boolean(default=False)

[loggers]
    [[__many__]]
        level = option('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL') 
        propagate = boolean(default=True)
        handlers = list()

[handlers]
    [[__many__]]
        level = option('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
        formatter = string()
        class = string()

[formatters]
    [[__many__]]
        format = string()
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
    # Now create a ConfigObj from the string. Attach the validator.
    log_config = configobj.ConfigObj(StringIO(default_logging_str),
                                     interpolation=False,
                                     configspec=StringIO(LOGGING_VALIDATOR))

    # Merge in the user additions / changes:
    log_config.merge(user_log_dict)

    # Now validate the log_dict. This has the happy side effect of getting the types
    # right.
    v = validate.Validator()
    result = log_config.validate(v, copy=True)
    if not result:
        raise ValueError("Logging not configured properly")

    # The root logger is denoted by an empty string by the logging facility. Unfortunately,
    # ConfigObj does not accept an empty string as a key. So, instead, we use this hack:
    log_dict = log_config.dict()
    try:
        log_dict['loggers'][''] = log_dict['loggers']['root']
        del log_dict['loggers']['root']
    except KeyError:
        pass

    logging.config.dictConfig(log_dict)
