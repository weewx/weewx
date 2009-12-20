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
import threading
from optparse import OptionParser
import configobj

import daemon

import weewx
import weewx.archive
import weewx.stats
import weewx.processdata
import weeutil.weeutil

usagestr = """
  %prog config_path [--daemon]

  Entry point to the weewx weather program. Can be run from the command
  line or, by specifying the '--daemon' option, as a daemon.

Arguments:
    config_path: Path to the configuration file to be used.
"""


#===============================================================================
#                    Class StdEngine
#===============================================================================

class StdEngine(object):
    
    def __init__(self, service_list):
        """Initialize an instance of StdEngine.
        
        For each listed service in service_list, instantiates an instance of the class,
        passing self as the only argument."""

        self.service_obj = [_get_object(svc, self) for svc in service_list]
        
    def setup(self):
        """Run before anything else."""
        
        self.parseArgs()

        # Set up the main archive database:
        self.setupArchiveDatabase()

        # Set up the statistical database:
        self.setupStatsDatabase()

        # Set up the weather station hardware:
        self.setupStation()

        # Set a default socket time out, in case FTP or HTTP hang:
        timeout = int(self.config_dict.get('socket_timeout', '20'))
        socket.setdefaulttimeout(timeout)
        
        # Allow each service to run its setup:
        for obj in self.service_obj:
            obj.setup()

    def parseArgs(self):
        """Parse any command line options."""

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
            self.config_dict = configobj.ConfigObj(args[0], file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % args[0])
            syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % args[0])
            exit()
        
        syslog.syslog(syslog.LOG_INFO, "main: Using configuration file %s." % os.path.abspath(args[0]))
    
        if int(self.config_dict.get('debug', '0')):
            # Get extra debug info. Set the logging mask for full debug info
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
            # Set the global debug flag:
            weewx.debug = True

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
                                                  int(self.config_dict['Station'].get('heating_base',   '65')),
                                                  int(self.config_dict['Station'].get('cooling_base',   '65')),
                                                  int(self.config_dict['Station'].get('cache_loop_data', '1')))
        # Configure it if necessary (this will do nothing if the database has
        # already been configured):
        self.statsDb.config(self.config_dict['Stats'].get('stats_types'))

        # Backfill it with data from the archive. This will do nothing if 
        # the stats database is already up-to-date.
        weewx.stats.backfill(self.archive, self.statsDb)
        
    def setupStation(self):
        """Set up the weather station hardware."""
        # Get the hardware type from the configuration dictionary.
        # This will be a string such as "VantagePro"
        stationType = self.config_dict['Station']['station_type']
    
        # Look for and load the module that handles this hardware type:
        _moduleName = "weewx." + stationType
        __import__(_moduleName)
        hardware_module = sys.modules[_moduleName]
    
        try:
    
            # Now open up the weather station:
            self.station = hardware_module.WxStation(self.config_dict[stationType])
    
        except Exception, ex:
            # Caught unrecoverable error. Log it, exit
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Unable to open WX station hardware: %s" % ex)
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Exiting.")
            # Reraise the exception (this will eventually cause the program to exit)
            raise
            
        
    def preloop(self):
        """Run every time before asking for LOOP packets"""

        for obj in self.service_obj:
            obj.preloop()

            
    def processLoopPacket(self, physicalPacket):
        """Run whenever a LOOP packet needs to be processed."""
        
        for obj in self.service_obj:
            obj.processLoopPacket(physicalPacket)
            
    def getArchiveData(self):
        """This function gets or calculates new archive data"""
        
        lastgood_ts = self.archive.lastGoodStamp()
        
        nrec = 0
        # Add all missed archive records since the last good record in the database
        for rec in self.station.genArchivePackets(lastgood_ts) :
            self.postArchiveData(rec)
            nrec += 1
    
        if nrec != 0:
            syslog.syslog(syslog.LOG_INFO, "wxengine: %d new archive packets added to database" % nrec)
    
    def postArchiveData(self, rec):
        """Run whenever any new archive data appears."""

        # Add the new record to the archive database and stats database:
        self.archive.addRecord(rec)
        self.statsDb.addArchiveRecord(rec)

        # Give each service a chance to take a look at it:
        for obj in self.service_obj:
            obj.postArchiveData(rec)
        
    def processArchiveData(self):
        """Run after any archive data has been retrieved and put in the database."""
        
        for obj in self.service_obj:
            obj.processArchiveData()
            
    def start(self):
        """Start up the engine. Runs member function run()"""
        
        self.run()
        
    def run(self):
        """This is where the work gets done."""
        self.setup()
        
        syslog.syslog(syslog.LOG_INFO, "wxengine: Starting main packet loop.")

        while True:
    
            self.preloop()

            # Next time to ask for archive records:
            nextArchive_ts = (int(time.time() / self.station.archive_interval) + 1) * self.station.archive_interval + self.station.archive_delay
    
            for physicalPacket in self.station.genLoopPacketsUntil(nextArchive_ts):
                
                # Process the physical LOOP packet:
                self.processLoopPacket(physicalPacket)
                
            # Calculate/get new archive data:
            self.getArchiveData()
            
            # Now process it. Typically, this means generating reports, etc.
            self.processArchiveData()

#===============================================================================
#                    Class StdService
#===============================================================================

class StdService(object):
    
    def __init__(self, engine):
        self.engine = engine
    
    def setup(self):
        pass
    
    def preloop(self):
        pass
    
    def processLoopPacket(self, physicalPacket):
        pass
    
    def postArchiveData(self, rec):
        pass
    
    def processArchiveData(self):
        pass
     
#===============================================================================
#                    Class StdCatchUp
#===============================================================================

class StdCatchUp(StdService):        

    def __init__(self, engine):
        StdService.__init__(self, engine)
    
    def setup(self):
        self.engine.getArchiveData()

#===============================================================================
#                    Class StdTimeSynch
#===============================================================================

class StdTimeSynch(StdService):
    
    def __init__(self, engine):
        StdService.__init__(self, engine)
        self.last_synch_ts = 0
        
    def preloop(self):
        # Synch up the station's clock if it's been more than 
        # clock_check seconds since the last check:
        now_ts = time.time()
        if now_ts - self.last_synch_ts >= self.engine.station.clock_check:
            self.engine.station.setTime()
            self.last_synch_ts = now_ts
            
class StdPrint(StdService):
    """Service that prints diagnostic information when a LOOP
    or archive packet is received."""
    
    def __init__(self, engine):
        StdService.__init__(self, engine)
        
    def processLoopPacket(self, physicalPacket):
        print "LOOP:  ", weeutil.weeutil.timestamp_to_string(physicalPacket['dateTime']),\
            physicalPacket['barometer'],\
            physicalPacket['outTemp'],\
            physicalPacket['windSpeed'],\
            physicalPacket['windDir']

    def postArchiveData(self, rec):
        print"REC:-> ", weeutil.weeutil.timestamp_to_string(rec['dateTime']), rec['barometer'],\
                                                            rec['outTemp'],   rec['windSpeed'],\
                                                            rec['windDir'], " <-"

#===============================================================================
#                    Class StdWunderground
#===============================================================================

class StdWunderground(StdService):
    import weewx.wunderground

    def __init__(self, engine):
        StdService.__init__(self, engine)
        
    def setup(self):
        wunder_dict = self.engine.config_dict.get('Wunderground')
        
        # Make sure we have a section [Wunderground] and that the station name
        # and password exist before committing:
        if wunder_dict and (wunder_dict.has_key('station') and 
                            wunder_dict.has_key('password')):
            self.queue = Queue.Queue()
            archiveFilename = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'], 
                                           self.engine.config_dict['Archive']['archive_file'])
            t = weewx.wunderground.WunderThread(archiveFilename = archiveFilename,
                                                queue = self.queue, 
                                                **wunder_dict)
        else:
            self.queue = None
        
    def postArchiveData(self, rec):
        if self.queue:
            self.queue.put(rec['dateTime'])

#===============================================================================
#                    Class StdProcess
#===============================================================================

class StdProcess(StdService):
    
    def __init__(self, engine):
        StdService.__init__(self, engine)
        
    def processArchiveData(self):
        """This function processes any new archive data"""
        # Now process the data, using a separate thread
        processThread = threading.Thread(target = weewx.processdata.processData,
                                         args   =(self.engine.config_dict, ))
        processThread.start()


#===============================================================================
#                    Function main
#===============================================================================

def main(EngineClass = StdEngine,
         service_list = ['weewx.wxengine.StdWunderground',
                         'weewx.wxengine.StdCatchUp',
                         'weewx.wxengine.StdTimeSynch',
                         'weewx.wxengine.StdPrint',
                         'example.alarm.MyAlarm',
                         'weewx.wxengine.StdProcess']) :
    """Prepare the main loop and run it. 

    Mostly consists of a bunch of high-level prepatory calls, protected
    by try blocks in the case of an exception."""

    try:

        # Create and initialize the MainLoop object
        engine = EngineClass(service_list)

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
        
