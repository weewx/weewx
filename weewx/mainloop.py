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
import os
import os.path
import socket
import sys
import syslog
import threading
import Queue
import time

# weewx modules:
import weewx
import weewx.archive
import weewx.stats
import weeutil.weeutil
import weewx.wunderground
import weewx.processdata

def main(config_dict):
    """Prepare the main loop and run it. 

    Mostly consists of a bunch of high-level prepatory calls, protected
    by try blocks in the case of an exception."""

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

    try:

        # Now open up the weather station:
        station = hardware_module.WxStation(config_dict[stationType])

    except Exception, ex:
        # Caught unrecoverable error. Log it, exit
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to open WX station hardware: %s" % ex)
        syslog.syslog(syslog.LOG_CRIT, "main: Exiting.")
        # Reraise the exception (this will eventually cause the program to exit)
        raise

    try:

        # Create and initialize the MainLoop object, using the dictionary
        # and the hardware station:
        mainloop = weewx.mainloop.MainLoop(config_dict, station)

    except Exception, ex:
        # Caught unrecoverable error. Log it, exit
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to initialize main loop:")
        syslog.syslog(syslog.LOG_CRIT, "main: %s" % ex)
        syslog.syslog(syslog.LOG_CRIT, "main: Exiting.")
        # Reraise the exception (this will eventually cause the program to exit)
        raise


    while True:
        # Start the main loop, wrapping it in an exception block.
        try:

            mainloop.run()

        # Catch any recoverable weewx I/O errors:
        except weewx.WeeWxIOError, e:
            # Caught an I/O error. Log it, wait 60 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "main: Caught WeeWxIOError: %s" % e)
            syslog.syslog(syslog.LOG_CRIT, "main: Waiting 60 seconds then retrying...")
            time.sleep(60)
            syslog.syslog(syslog.LOG_NOTICE, "main: retrying...")

        # If run from the command line, catch any keyboard interrupts and log them:
        except KeyboardInterrupt:
            syslog.syslog(syslog.LOG_CRIT,"main: Keyboard interrupt.")
            raise SystemExit, "keyboard interrupt"

        # Catch any non-recoverable errors. Log them, exit
        except Exception, ex:
            # Caught unrecoverable error. Log it, exit
            syslog.syslog(syslog.LOG_CRIT, "main: Caught unrecoverable exception in main loop:")
            syslog.syslog(syslog.LOG_CRIT, "main: %s" % ex)
            syslog.syslog(syslog.LOG_CRIT, "main: Exiting.")
            # Reraise the exception (this will eventually cause the program to exit)
            raise

class MainLoop(object):
    """Main loop of weewx.

    If you wish to customize something here, subclass MainLoop, then override
    the relevant member function."""

    def __init__(self, config_dict, station):
        """Create an instance using the configuration dictionary and station object."""

        self.config_dict = config_dict
        
        # Binds to the particular weather hardware in use:
        self.station = station
        
        # This will hold the time the clock on weather station was last synchronized.
        # Setting it to zero will force a synchronization at the first opportunity.
        self.last_synch_ts = 0
        
        # Set up the main archive database:
        self.setupArchiveDatabase()

        # Set up the statistical database:
        self.setupStatsDatabase()

        # Set up the Weather Underground thread:
        self.setupWeatherUnderground(config_dict)

        # Catch up if possible
        self.getArchiveData()

    def setupArchiveDatabase(self):
        """Setup the main database archive"""
        archiveFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                       self.config_dict['Archive']['archive_file'])
        self.archive = weewx.archive.Archive(archiveFilename)
        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.archive.config()
    

    def setupStatsDatabase(self):
        """Prepare the stats database"""
        statsFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                     self.config_dict['Stats']['stats_file'])
        # statsDb is an instance of weewx.stats.StatsDb, which wraps the stats sqlite file
        self.statsDb = weewx.stats.StatsDb(statsFilename,
                                      int(self.config_dict['Station'].get('heating_base',   65)),
                                      int(self.config_dict['Station'].get('cooling_base',   65)),
                                      int(self.config_dict['Station'].get('cache_loop_data', 0)))

        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.statsDb.config(self.config_dict['Stats'].get('stats_types'))
        # Backfill it with data from the archive. This will do nothing if 
        # the stats database is already up-to-date.
        weewx.stats.backfill(self.archive, self.statsDb)

    def setupWeatherUnderground(self, config_dict):
        """Set up the WU thread."""
        wunder_dict = config_dict.get('Wunderground')
        if wunder_dict :
            weewx.wunderground.wunderQueue = Queue.Queue()
            t = weewx.wunderground.WunderThread(wunder_dict['station'], 
                                                wunder_dict['password'])

    
    def processLoopPacket(self, physicalPacket):
        """Given a LOOP packet with physical units, this function processes it."""
        print "LOOP:  ", weeutil.weeutil.timestamp_to_string(physicalPacket['dateTime']),\
            physicalPacket['barometer'],\
            physicalPacket['outTemp'],\
            physicalPacket['windSpeed'],\
            physicalPacket['windDir']
    
        # Add the LOOP record to the stats database:
        self.statsDb.addLoopRecord(physicalPacket)

    def getArchiveData(self):
        """This function gets or calculates new archive data"""
        lastgood_ts = self.archive.lastGoodStamp()
        
        nrec = 0
        # Add all missed archive records since the last good record in the database
        for rec in self.station.genArchivePackets(lastgood_ts) :
            print"REC:-> ", weeutil.weeutil.timestamp_to_string(rec['dateTime']), rec['barometer'],\
                                                                rec['outTemp'],   rec['windSpeed'], 
                                                                rec['windDir'], " <-"
            self.archive.addRecord(rec)
            self.statsDb.addArchiveRecord(rec)
            if weewx.wunderground.wunderQueue:
                weewx.wunderground.wunderQueue.put((self.archive, rec['dateTime']))
            nrec += 1
    
        if nrec != 0:
            syslog.syslog(syslog.LOG_INFO, "mainloop: %d new archive packets added to database" % nrec)

    def processArchiveData(self):
        """This function processes any new archive data"""
        # Now process the data, using a separate thread
        processThread = threading.Thread(target = weewx.processdata.processData,
                                         args   =(self.config_dict, ))
        processThread.start()

    def run(self):
        """Run the main loop of the program."""

        syslog.syslog(syslog.LOG_INFO, "mainloop: Starting main packet loop.")

        while True:
    
            # Synch up the station's clock if it's been more than 
            # clock_check seconds since the last check:
            now_ts = time.time()
            if now_ts - self.last_synch_ts >= self.station.clock_check:
                self.station.setTime()
                self.last_synch_ts = now_ts
                
            # Next time to ask for archive records:
            nextArchive_ts = (int(time.time() / self.station.archive_interval) + 1) * self.station.archive_interval + self.station.archive_delay
    
            # Get LOOP packets in big batches, then cancel as necessary when it's time
            # to request an archive record:
            for physicalPacket in self.station.genLoopPackets(200):
                
                # Process the physical LOOP packet:
                self.processLoopPacket(physicalPacket)
                
                # Check to see if it's time to get new archive data. If so, cancel the loop
                if time.time() >= nextArchive_ts:
                    print "New archive record due. canceling loop"
                    syslog.syslog(syslog.LOG_DEBUG, "mainloop: new archive record due. Canceling loop")
                    self.station.cancelLoop()
                    
                    # Calculate/get new archive data:
                    self.getArchiveData()

                    # Now process it. Typically, this means generating reports, etc.
                    self.processArchiveData()
                    
                    # Start all over again from the top.
                    break

