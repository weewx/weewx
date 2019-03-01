#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""WeeWX logging facility"""

from __future__ import absolute_import

import os
import syslog
import traceback

import six
from six.moves import StringIO

log_levels = {
    'debug': syslog.LOG_DEBUG,
    'info': syslog.LOG_INFO,
    'warning': syslog.LOG_WARNING,
    'critical': syslog.LOG_CRIT,
    'error': syslog.LOG_ERR
}


def logdbg(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_DEBUG, "%s: %s" % (prefix, msg))


def loginf(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_INFO, "%s: %s" % (prefix, msg))


def logwar(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_WARNING, "%s: %s" % (prefix, msg))


def logerr(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_ERR, "%s: %s" % (prefix, msg))


def logalt(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_ALERT, "%s: %s" % (prefix, msg))


def logcrt(msg, prefix=None):
    if prefix is None:
        prefix = _get_file_root()
    syslog.syslog(syslog.LOG_CRIT, "%s: %s" % (prefix, msg))


def log_traceback(prefix='', loglevel=None):
    """Log the stack traceback into syslog.

    prefix: A string, which will be put in front of each log entry. Default is no string.

    loglevel: Either a syslog level (e.g., syslog.LOG_INFO), or a string. Valid strings
    are given by the keys of log_levels.
    """
    if loglevel is None:
        loglevel = syslog.LOG_INFO
    elif isinstance(loglevel, six.string_types):
        loglevel = log_levels.get(loglevel, syslog.LOG_INFO)
    sfd = StringIO()
    traceback.print_exc(file=sfd)
    sfd.seek(0)
    for line in sfd:
        syslog.syslog(loglevel, "%s: %s" % (prefix, line))


def _get_file_root():
    """Figure out who is the caller of the logging function"""

    # Get the stack:
    tb = traceback.extract_stack()
    # Go back 3 frames. First frame is get_file_root(), 2nd frame is the logging function, 3rd frame
    # is what we want: what called the logging function
    calling_frame = tb[-3]
    # Get the file name of what called the logging function
    calling_file = os.path.basename(calling_frame[0])
    # Get rid of any suffix (e.g., ".py"):
    file_root = calling_file.split('.')[0]
    return file_root
