#!/usr/bin/env python
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

"""weewxd.py

Entry point to the weewx weather system.
"""

import sys
import os.path
import syslog
from optparse import OptionParser
import configobj

import daemon

import weewx.wxengine

usagestr = """
  %prog config_path [--daemon]

  Entry point to the weewx weather program. Can be run from the command
  line, or with the '--daemon' option, as a daemon.

Arguments:
    config_path: Path to the configuration file to be used.
"""


# Set defaults for the system logger:
syslog.openlog('weewx', syslog.LOG_PID|syslog.LOG_CONS)
syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

parser = OptionParser(usage=usagestr)
parser.add_option("-d", "--daemon", action="store_true", dest="daemon", help="Run as a daemon")
(options, args) = parser.parse_args()

if len(args) < 1:
    sys.stderr.write("Missing argument(s).\n")
    sys.stderr.write(parser.parse_args(["--help"]))
    exit()

if options.daemon:
    daemon.daemonize(pidfile='/var/run/weewx.pid')

# Try to open up the given configuration file. Declare an error if unable to.
try :
    config_dict = configobj.ConfigObj(args[0], file_error=True)
except IOError:
    sys.stderr.write("Unable to open configuration file %s" % args[0])
    syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % args[0])
    exit()

syslog.syslog(syslog.LOG_INFO, "main: Using configuration file %s." % os.path.abspath(args[0]))

# Prepare and enter the main loop:
weewx.wxengine.main(config_dict)
