#!/usr/bin/env python
#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Module can be called as a main program to generate reports, etc.,
that are current as of the last archive record in the archive database."""

import socket
import sys
import syslog
import configobj

import user.extensions
import weewx.reportengine

def gen_all(config_path, gen_ts = None):
    
    syslog.openlog('runreports', syslog.LOG_PID|syslog.LOG_CONS)
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        sys.stderr.write("Unable to open configuration file %s" % config_path)
        syslog.syslog(syslog.LOG_CRIT, "runreports: Unable to open configuration file %s" % config_path)
        # Reraise the exception (this will eventually cause the program to exit)
        raise
    except configobj.ConfigObjError:
        syslog.syslog(syslog.LOG_CRIT, "runreports: Error while parsing configuration file %s" % config_path)
        raise
    # Look for the debug flag. If set, ask for extra logging
    weewx.debug = int(config_dict.get('debug', 0))
    if weewx.debug:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    else:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

    socket.setdefaulttimeout(10)
    
    t = weewx.reportengine.StdReportEngine(config_path, gen_ts)

    # Although the report engine inherits from Thread, we can just run it in the main thread:
    t.run()
    
if len(sys.argv) < 2 :
    print "Usage: reports.py path-to-configuration-file [timestamp-to-be-generated]"
    exit()
gen_ts = int(sys.argv[2]) if len(sys.argv)>=3 else None
    
gen_all(sys.argv[1], gen_ts)
