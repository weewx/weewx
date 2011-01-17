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

import weewx.reportengine

def gen_all(config_path, gen_ts = None):
    
    syslog.openlog('reports', syslog.LOG_PID|syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

    socket.setdefaulttimeout(10)
    
    t = weewx.reportengine.StdReportEngine(config_path, gen_ts)
    t.start()
    t.join()

    
if len(sys.argv) < 2 :
    print "Usage: reports.py path-to-configuration-file [timestamp-to-be-generated]"
    exit()
gen_ts = int(sys.argv[2]) if len(sys.argv)>=3 else None
    
gen_all(sys.argv[1], gen_ts)
