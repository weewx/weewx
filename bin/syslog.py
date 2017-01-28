#    Copyright (c) 2017 dcapslock

"""Map syslog to the python logger for systems that have no syslog."""

# WARNING: this is a shim for syslog to get weewx to run on windows.  this
# shim is very much a work in progress.

# FIXME: make the log default to a directory 'log' in the weewx directory

import logging
from logging import handlers
import sys
import os
import time
import datetime
import socket

LOG_EMERG, LOG_ALERT, LOG_CRIT, LOG_ERR, LOG_WARNING, \
    LOG_NOTICE, LOG_INFO, LOG_DEBUG = range(8)

LOG_KERN, LOG_USER, LOG_MAIL, LOG_DAEMON, LOG_AUTH, \
    LOG_SYSLOG, LOG_LPR, LOG_NEWS, LOG_UUCP = range(0,65,8)

LOG_CRON = 120
LOG_LOCAL0 = 128
LOG_LOCAL1 = 136
LOG_LOCAL2 = 144
LOG_LOCAL3 = 152
LOG_LOCAL4 = 160
LOG_LOCAL5 = 168
LOG_LOCAL6 = 176
LOG_LOCAL7 = 184

LOG_PID = 1
LOG_CONS = 2
LOG_NDELAY = 8
LOG_NOWAIT = 16

syslog_to_logging = {
    LOG_EMERG   : logging.CRITICAL,
    LOG_ALERT   : logging.CRITICAL,
    LOG_CRIT    : logging.CRITICAL,
    LOG_ERR     : logging.ERROR,
    LOG_WARNING : logging.WARNING,
    LOG_NOTICE  : logging.INFO,
    LOG_INFO    : logging.INFO,
    LOG_DEBUG   : logging.DEBUG
}

class syslogLogger:
    def __init__(self):
        self.logger = None
        self.file_handler = None
        self.syslog_handler = None
        self.maskpri = None

    def isOpen(self):
        return not self.logger is None    

    def syslog(self, priority, message):
        if not self.logger:
            raise Exception("Logger not open")

        try:
            logging_priority = syslog_to_logging[priority]
        except KeyError:
            logging_priority = logging.NOTSET

        self.logger.log(logging_priority, message)
        self.file_handler.flush()

    def openlog(self, ident=sys.argv[0], logoptions=0, facility=LOG_USER):
        # sys.argv[0] will be empty if running from command interpreter
        if ident == '':
            ident = 'python-syslog'

        if self.logger:
            raise Exception("Logger already open")

        self.logger = logging.getLogger(ident)

        # By defafult create a local file and send to local syslog
        # TODO: Support logger config files so a .syslog file in the app folder 
        # TODO: Support logoptions correctly
        # or user folder will determine what to log

        # Local File Handler
        # FIXME: first try creating as appdir\log\<ident>.log
        # otherwise, try creating log as 'LOCALAPPDATA\<ident>\log\<ident>.log'
        # if unsuccessful, create log as 'HOME\Desktop\<ident>.log'
        maxlogsize = 10 * 1024 * 1024
        logdir = os.path.join(os.environ.get('LOCALAPPDATA'), ident + '/log')
        try:
            os.makedirs(logdir)
        except os.error:
            pass
        if not os.path.exists(logdir):
            logdir = os.path.join(os.environ.get('HOME'), 'Desktop')

        self.file_handler = handlers.RotatingFileHandler(
            os.path.join(logdir, ident + '.log'),
            maxBytes=maxlogsize, backupCount=10)
            
        syslog_format = '%(RFC3164time)s %(hostname)s {}[%(process)d]: %(message)s'.format(ident)
        syslog_formatter = SyslogFormatter(syslog_format)
        
        self.file_handler.setFormatter(syslog_formatter)
            
        self.logger.addHandler(self.file_handler)

        # local RFC3164 syslog handler

        self.syslog_handler = handlers.SysLogHandler(
            address=('localhost', 514), facility=facility)
        
        self.syslog_handler.setFormatter(syslog_formatter)

        self.logger.addHandler(self.syslog_handler)

        # Unix syslog defaults to all priority while logging defaults to
        # WARNING, so set explicitly to DEBUG
        self.maskpri = LOG_DEBUG
        self.setlogmask(self.maskpri)

    def closelog(self):
        if not self.logger:
            raise Exception("Logger not open")

        self.logger.removeHandler(self.file_handler)
        self.logger.removeHandler(self.syslog_handler)
        self.file_handler = None
        self.syslog_handler = None
        self.logger = None

    def LOG_MASK(self, maskpri):
        return maskpri

    def LOG_UPTO(self, maskpri):
        return maskpri

    def setlogmask(self, maskpri):
        if not self.logger:
            raise Exception("Logger not open")

        level = 0

        if maskpri == LOG_EMERG:
            level = logging.CRITICAL
        if maskpri == LOG_ALERT:
            level = logging.CRITICAL
        if maskpri == LOG_CRIT:
            level = logging.CRITICAL
        if maskpri == LOG_ERR:
            level = logging.ERROR
        if maskpri == LOG_WARNING:
            level = logging.WARNING
        if maskpri == LOG_NOTICE:
            level = logging.INFO
        if maskpri == LOG_INFO:
            level = logging.INFO
        if maskpri == LOG_DEBUG:
            level = logging.DEBUG

        self.logger.setLevel(level)

        old_maskpri = self.maskpri
        self.maskpri = maskpri
        return old_maskpri

_syslog = syslogLogger()

def overload(*functions):
    return lambda *args, **kwargs: functions[len(args)](*args, **kwargs)

syslog = overload(
    None,
    lambda i: syslog_no_pri(i),
    lambda i, j: syslog_with_pri(i, j)
)

def syslog_no_pri(message):
    syslog_with_pri(LOG_INFO, message)

def syslog_with_pri(priority, message):
    if not _syslog.isOpen():
        _syslog.openlog()
    _syslog.syslog(priority, message)

def openlog(ident=sys.argv[0], logoptions=0, facility=LOG_USER):
    # Handle multiple calls to openlog as happens in test suites
    if _syslog.isOpen():
        _syslog.closelog()
    _syslog.openlog(ident, logoptions, facility)

def closelog():
    _syslog.closelog()

# TODO: At the moment this syslog implementation supports LOG_UPTO 
# setlogmask expects a singular LOG_* and not a mask.
# functions are provided here for a full implementation.
def LOG_MASK(maskpri):
    return _syslog.LOG_MASK(maskpri)

def LOG_UPTO(maskpri):
    return _syslog.LOG_UPTO(maskpri)

def setlogmask(maskpri):
    return _syslog.setlogmask(maskpri)

class SyslogFormatter(logging.Formatter):

    def __init__(self, *args, **kwargs):
        super(SyslogFormatter, self).__init__(*args, **kwargs)

    def format(self, record):
        try:
            record.__dict__['hostname'] = socket.gethostname()
        except:
            #default to a localhost dotted ip address
            record.__dict__['hostname'] = '127.0.0.1'
        
        dt = datetime.datetime.fromtimestamp(record.created)
        RFC3164time = dt.strftime("%b %d %H:%M:%S")

        record.__dict__['RFC3164time'] = RFC3164time

        return super(SyslogFormatter, self).format(record)
