#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

import sys
import syslog
import time
import socket
import os.path
import Queue

import weewx
import weewx.archive
import weewx.stats
import weewx.wunderground
import weeutil.weeutil

def main(config_dict):
    """Prepare the main loop and run it. 

    Mostly consists of a bunch of high-level preparatory calls, protected
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

        # Create and initialize the WxEngine object, using the dictionary
        # and the hardware station:
        engine = WxEngine(config_dict, station)

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

            engine.start()

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

def _get_object(module_class, *args, **kwargs):
    """Given a path to a class, instantiates an instance of the class with the given args and returns it."""
    
    # Split the path into its parts
    parts = module_class.split('.')
    # Strip off the classname:
    module = '.'.join(parts[:-1])
    # Import the top level module
    mod =  __import__(module)
    # Then recursively work down from the top level module to the class name:
    for part in parts[1:]:
        mod = getattr(mod, part)
    # Instance 'mod' will now be a class. Instantiate an instance and return it:
    obj = mod(*args, **kwargs)
    return obj
        
class WxEngine(object):
    
    def __init__(self, config_dict, station,
                 setup_list   = [('weewx.wxengine.StdSetup')],
                 preloop_list = [('weewx.wxengine.StdPreLoop')], 
                 loop_list    = [], 
                 archive_list = [], 
                 process_list = []):
        
        self.config_dict = config_dict
        
        self.station = station

        self.setup_list   = setup_list
        self.preloop_list = preloop_list
        self.loop_list    = loop_list
        self.archive_list = archive_list
        self.process_list = process_list
        
    def setup(self):
        print "In setup()"
        for module_class in self.setup_list:
            obj = _get_object(module_class, self)
            obj.start()
            
    def preloop(self):
        print "In preloop()"
        for module_class in self.preloop_list:
            obj = _get_object(module_class, self)
            obj.start()
            
    def processLoopPacket(self, physicalPacket):
        print "In processLoopPacket()"
        for module_class in self.loop_list:
            obj = _get_object(module_class, self, physicalPacket)
            obj.start()
            
    def getArchiveData(self):
        print "In getArchiveData()"
        for module_class in self.archive_list:
            obj = _get_object(module_class, self)
            obj.start()
            
    def processArchiveData(self):
        print "In processArchiveData()"
        for module_class in self.process_list:
            obj = _get_object(module_class, self)
            obj.start()
            
    def start(self):
        
        self.run()
        
    def run(self):
        
        self.setup()
        
        syslog.syslog(syslog.LOG_INFO, "wxengine: Starting main packet loop.")

        while True:
    
            self.preloop()

            # Next time to ask for archive records:
            nextArchive_ts = (int(time.time() / self.station.archive_interval) + 1) * self.station.archive_interval + self.station.archive_delay
    
            # Get LOOP packets in big batches, then cancel as necessary when it's time
            # to request an archive record:
            for physicalPacket in self.station.genLoopPacketsUntil(nextArchive_ts):
                
                # Process the physical LOOP packet:
                self.processLoopPacket(physicalPacket)
                
            # Calculate/get new archive data:
            self.getArchiveData()

            # Now process it. Typically, this means generating reports, etc.
            self.processArchiveData()


class StdSetup(object):
    
    def __init__(self, engine):
        self.engine = engine
        self.config_dict = engine.config_dict

    def start(self):
        self.run()
        
    def run(self):
        
        archiveFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                       self.config_dict['Archive']['archive_file'])
        self.engine.archive = weewx.archive.Archive(archiveFilename)
    
        statsFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                     self.config_dict['Stats']['stats_file'])
        # statsDb is an instance of weewx.stats.StatsDb, which wraps the stats sqlite file
        self.engine.statsDb = weewx.stats.StatsDb(statsFilename,
                                                  int(self.config_dict['Station'].get('heating_base',   '65')),
                                                  int(self.config_dict['Station'].get('cooling_base',   '65')),
                                                  int(self.config_dict['Station'].get('cache_loop_data', '1')))
        self.engine.last_synch_ts = 0

        # Set up the main archive database:
        self.setupArchiveDatabase()

        # Set up the statistical database:
        self.setupStatsDatabase()

        # Set up the Weather Underground thread:
        self.setupWeatherUnderground()

        # Catch up if possible
        self.catchUpArchiveData()

    def setupArchiveDatabase(self):
        """Setup the main database archive"""
        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.engine.archive.config()
    

    def setupStatsDatabase(self):
        """Prepare the stats database"""
        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.engine.statsDb.config(self.config_dict['Stats'].get('stats_types'))

        # Backfill it with data from the archive. This will do nothing if 
        # the stats database is already up-to-date.
        weewx.stats.backfill(self.engine.archive, self.engine.statsDb)
        
    def catchUpArchiveData(self):
        getArchiveData(self.engine.station, self.engine.archive, self.engine.statsDb)

    def setupWeatherUnderground(self):
        """Set up the WU thread."""
        wunder_dict = self.config_dict.get('Wunderground')
        
        # Make sure we have a section [Wunderground] and that the station name
        # and password exist before committing:
        if wunder_dict and (wunder_dict.has_key('station') and 
                            wunder_dict.has_key('password')):
            weewx.wunderground.wunderQueue = Queue.Queue()
            t = weewx.wunderground.WunderThread(**wunder_dict)


class StdPreLoop(object):
    
    def __init__(self, engine):
        self.engine = engine
        
    def start(self):
        self.run()
        
    def run(self):
        print "In StdPreLoop.run()"
        # Synch up the station's clock if it's been more than 
        # clock_check seconds since the last check:
        now_ts = time.time()
        if now_ts - self.engine.last_synch_ts >= self.engine.station.clock_check:
            self.engine.station.setTime()
            self.engine.last_synch_ts = now_ts
                
def getArchiveData(station, archive, statsDb):
    """This function gets or calculates new archive data"""
    lastgood_ts = archive.lastGoodStamp()
    
    nrec = 0
    # Add all missed archive records since the last good record in the database
    for rec in station.genArchivePackets(lastgood_ts) :
        print"REC:-> ", weeutil.weeutil.timestamp_to_string(rec['dateTime']), rec['barometer'],\
                                                            rec['outTemp'],   rec['windSpeed'],\
                                                            rec['windDir'], " <-"
        archive.addRecord(rec)
        statsDb.addArchiveRecord(rec)
        if weewx.wunderground.wunderQueue:
            weewx.wunderground.wunderQueue.put((archive, rec['dateTime']))
        nrec += 1

    if nrec != 0:
        syslog.syslog(syslog.LOG_INFO, "wxengine: %d new archive packets added to database" % nrec)

#class StdProcessLoopPacket(object):
#    
#    def __init__(self, engine):
#        self.engine = engine
#        
#    def start(self):
#        self.run()
#        
#    def run(self):
