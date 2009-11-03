#!/usr/bin/env python
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Main loop of the weewx weather system.

There are three main threads in this program.

The main thread collects LOOP data off the weather station every 
2 seconds, using it to update the stats database. At the end of
an archive interval, the thread gets any new archive records off the station, 
and puts them in the main database. It optionally adds the new records
to a queue to be sent to the Weather Underground.
It then spawns a separate "processing" thread to generate any products
asynchronously. It then goes back to collecting LOOP data.

The "processing" thread is responsible for generating products from the
database, such as HTML generation, NOAA monthly report generation, image
generation. It also optionally FTPs data to a remote web server.

The third thread is optional and responsible for watching the queue
holding new Weather Underground records. If any show up, it arranges to
have them sent to the WU asynchronously.

The overall effect is that the main loop thread manages the weather instrument
and puts data into the databases. It does very little processing. All processing
is done asynchronously in separate threads so that the main loop thread can
get back to monitoring the instrument as quickly as possible.

"""
# Standard Python modules:
import sys
import os.path
import time
import syslog
import threading
import socket

# Third party modules:
import configobj

# weewx modules:
import weewx
import weewx.mainloop

def main(config_path):        

    # Set defaults for the system logger:
    syslog.openlog('weewx', syslog.LOG_PID|syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
    
    # Try to open up the given configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print "Unable to open configuration file ", config_path
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % config_path)
        exit()

    if int(config_dict.get('debug', '0')):
        # Get extra debug info. Set the logging mask for full debug info
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        # Set the global debug flag:
        weewx.debug = True

    # Set a default socket time out, in case FTP or HTTP hang:
    timeout = int(config_dict.get('socket_timeout', '20'))
    socket.setdefaulttimeout(timeout)
    
    # Get the hardware type from the configuration dictionary.
    # This will be a string such as "VantagePro"
    stationType = config_dict['Station']['station_type']
    
    # Look for and load the module that handles this hardware type:
    _moduleName = "weewx." + stationType
    __import__(_moduleName)
    hardware_module = sys.modules[_moduleName]
    
    # Now open up the weather station:
    station = hardware_module.WxStation(config_dict[stationType])
    
    mainloop = weewx.mainloop.MainLoop(config_dict, station)
        
    while True:
        # Start the main loop, wrapping it in an exception block to catch any 
        # recoverable I/O errors
        try:
            syslog.syslog(syslog.LOG_INFO, "main: Using configuration file %s." % os.path.abspath(config_path))

            mainloop.run()
        except weewx.WeeWxIOError, e:
            # Caught an I/O error. Log it, wait 60 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, 
                          "main: Caught WeeWxIOError (%s). Waiting 60 seconds then retrying." % str(e))
            time.sleep(60)
            syslog.syslog(syslog.LOG_NOTICE, "main: retrying...")

if __name__ == '__main__' :
    from optparse import OptionParser
    import daemon
    
    usagestr = """%prog: config_path

    Main loop of the WeeWx weather program.

    Arguments:
        config_path: Path to the configuration file to be used."""
    parser = OptionParser(usage=usagestr)
    parser.add_option("--daemon", action="store_true", dest="daemon", help="Run as a daemon")
    (options, args) = parser.parse_args()

    if len(args) < 1:
        print "Missing argument(s)."
        print parser.parse_args(["--help"])
        exit()
    
    if options.daemon:
        daemon.daemonize(pidfile='/var/run/weewx.pid')
        
    main(args[0])
