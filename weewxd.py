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
import os.path
import time
import syslog
import threading
import Queue
import socket

# Third party modules:
import configobj

# weewx modules:
import weewx
import weewx.processdata
import weewx.VantagePro
import weewx.archive
import weewx.stats
import weewx.wunderground
import weeutil.weeutil

def mainloop(config_dict):
    
    # Set a default socket time out, in case FTP or HTTP hang:
    timeout = int(config_dict.get('socket_timeout', '20'))
    socket.setdefaulttimeout(timeout)

    # This will hold the time the clock on the VP was last synchronized.
    # Setting it to zero will force a synchronization at the first opportunity.
    last_synch_ts = 0
    # How often to check the clock on the station:
    clock_check = int(config_dict['VantagePro'].get('clock_check', '14400'))
    
    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    archive = weewx.archive.Archive(archiveFilename)
    # Configure it if necessary (this will do nothing if the database has
    # already been configured):
    archive.config()

    # Prepare the stats database
    statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                 config_dict['Stats']['stats_file'])
    # statsDb is an instance of weewx.stats.StatsDb, which wraps the stats sqlite file
    statsDb = weewx.stats.StatsDb(statsFilename,
                                  int(config_dict['Station'].get('heating_base',   65)),
                                  int(config_dict['Station'].get('cooling_base',   65)),
                                  int(config_dict['Station'].get('cache_loop_data', 0)))

    # Configure it if necessary (this will do nothing if the database has
    # already been configured):
    statsDb.config(config_dict['Stats'].get('stats_types'))
    # Backfill it with data from the archive. This will do nothing if 
    # the stats database is already up-to-date.
    weewx.stats.backfill(archive, statsDb)

    # Set up the Weather Underground thread:
    setupWeatherUnderground(config_dict)
    
    # Open up the weather station:
    station = weewx.VantagePro.VantagePro(config_dict['VantagePro'])

    # Do any preloop calculations (if any) required by the weather station:
    station.preloop(archive, statsDb)

    # Now enter the main loop
    syslog.syslog(syslog.LOG_INFO, "mainloop: Starting main packet loop.")
    while True:

        # Synch up the station's clock if it's been more than 
        # clock_check seconds since the last check:
        now_ts = time.time()
        if now_ts - last_synch_ts >= clock_check:
            station.setTime()
            last_synch_ts = now_ts
            
        # Next time to ask for archive records:
        nextArchive_ts = (int(time.time() / station.archive_interval) + 1) * station.archive_interval + station.archive_delay

        # Get LOOP packets in big batches, then cancel as necessary when it's time
        # to request an archive record:
        for loopPacket in station.getLoopPackets(200):
            
            # Translate to physical units in the Imperial (US) system:
            physicalPacket = weewx.VantagePro.translateLoopToImperial(loopPacket)

            print "LOOP:  ", weeutil.weeutil.timestamp_to_string(physicalPacket['dateTime']),\
                physicalPacket['barometer'],\
                physicalPacket['outTemp'],\
                physicalPacket['windSpeed'],\
                physicalPacket['windDir']

            # Add the LOOP record to the stats database:
            statsDb.addLoopRecord(physicalPacket)
            
            # Check to see if it's time to get new archive data. If so, cancel the loop
            if time.time() >= nextArchive_ts:
                print "New archive record due. canceling loop"
                syslog.syslog(syslog.LOG_DEBUG, "mainloop: new archive record due. Canceling loop")
                station.cancelLoop()
                # Calculate/get new archive data:
                station.calcArchiveData(archive, statsDb)
                # Now process the data, using a separate thread
                processThread = threading.Thread(target = weewx.processdata.processData, args=(config_dict, ))
                processThread.start()
                break

def setupWeatherUnderground(config_dict):
    """Set up the WU thread."""
    wunder_dict = config_dict.get('Wunderground')
    if wunder_dict :
        t = weewx.wunderground.WunderThread(wunder_dict['station'], 
                                            wunder_dict['password'])

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
        
        
    while True:
        # Start the main loop, wrapping it in an exception block to catch any 
        # recoverable I/O errors
        try:
            syslog.syslog(syslog.LOG_INFO, "main: Using configuration file %s." % os.path.abspath(config_path))
            mainloop(config_dict)
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
