#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
import os
import os.path
import syslog
import time
import threading

import weewx.archive
import weewx.stats
import weeutil.weeutil

class MainLoop(object):
    
    def __init__(self, config_dict, station):

        self.config_dict = config_dict
        
        # Binds to the particular weather hardware in use:
        self.station = station
        
        # This will hold the time the clock on weather station was last synchronized.
        # Setting it to zero will force a synchronization at the first opportunity.
        self.last_synch_ts = 0
        
        # Open up the main database archive
        archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                       config_dict['Archive']['archive_file'])
        self.archive = weewx.archive.Archive(archiveFilename)
        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.archive.config()
    
        # Prepare the stats database
        statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                     config_dict['Stats']['stats_file'])
        # statsDb is an instance of weewx.stats.StatsDb, which wraps the stats sqlite file
        self.statsDb = weewx.stats.StatsDb(statsFilename,
                                      int(config_dict['Station'].get('heating_base',   65)),
                                      int(config_dict['Station'].get('cooling_base',   65)),
                                      int(config_dict['Station'].get('cache_loop_data', 0)))

        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.statsDb.config(config_dict['Stats'].get('stats_types'))
        # Backfill it with data from the archive. This will do nothing if 
        # the stats database is already up-to-date.
        weewx.stats.backfill(self.archive, self.statsDb)
    
        # Set up the Weather Underground thread:
        self.setupWeatherUnderground(config_dict)

        # Do any preloop calculations (if any) required by the weather station:
        self.station.preloop(self.archive, self.statsDb)

    def run(self):
    
        # Now enter the main loop
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
            for loopPacket in self.station.getLoopPackets(200):
                
                # Translate to physical units in the Imperial (US) system:
                physicalPacket = weewx.VantagePro.translateLoopToImperial(loopPacket)
    
                print "LOOP:  ", weeutil.weeutil.timestamp_to_string(physicalPacket['dateTime']),\
                    physicalPacket['barometer'],\
                    physicalPacket['outTemp'],\
                    physicalPacket['windSpeed'],\
                    physicalPacket['windDir']
    
                # Add the LOOP record to the stats database:
                self.statsDb.addLoopRecord(physicalPacket)
                
                # Check to see if it's time to get new archive data. If so, cancel the loop
                if time.time() >= nextArchive_ts:
                    print "New archive record due. canceling loop"
                    syslog.syslog(syslog.LOG_DEBUG, "mainloop: new archive record due. Canceling loop")
                    self.station.cancelLoop()
                    # Calculate/get new archive data:
                    self.station.calcArchiveData(self.archive, self.statsDb)
                    # Now process the data, using a separate thread
                    processThread = threading.Thread(target = weewx.processdata.processData, args=(self.config_dict, ))
                    processThread.start()
                    break

    def setupWeatherUnderground(self, config_dict):
        """Set up the WU thread."""
        wunder_dict = config_dict.get('Wunderground')
        if wunder_dict :
            t = weewx.wunderground.WunderThread(wunder_dict['station'], 
                                                wunder_dict['password'])

