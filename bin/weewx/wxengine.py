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
import signal
import socket
import os.path
import Queue
from optparse import OptionParser
import configobj

import daemon

import weewx
import weewx.archive
import weewx.stats
import weewx.restful
import weewx.reportengine
import weeutil.weeutil

usagestr = """
  %prog config_path [--daemon] [--version]

  Entry point to the weewx weather program. Can be run from the command
  line or, by specifying the '--daemon' option, as a daemon.

Arguments:
    config_path: Path to the weewx configuration file to be used.
"""


#===============================================================================
#                    Class StdEngine
#===============================================================================

class StdEngine(object):
    """Engine that drives weewx.
    
    This engine manages a list of 'services.' At key events, each service
    is given a chance to participate.
    """
    
    def __init__(self):
        """Initialize an instance of StdEngine."""
        

    def setup(self):
        """Gets run before anything else."""
        
        syslog.openlog('weewx', syslog.LOG_PID|syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
        
        self.parseArgs()

        service_list = weeutil.weeutil.option_as_list(self.config_dict['Engines']['WxEngine'].get('service_list'))
        
        syslog.syslog(syslog.LOG_DEBUG, "wxengine: List of services to be run:")
        for svc in service_list:
            syslog.syslog(syslog.LOG_DEBUG, "    ****  %s" % svc)
        
        #For each listed service in service_list, instantiates an instance of the class,
        # passing self as the only argument."""
        self.service_obj = [weeutil.weeutil._get_object(svc, self) for svc in service_list]
        
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
        parser.add_option("-d", "--daemon",  action="store_true", dest="daemon",  help="Run as a daemon")
        parser.add_option("-v", "--version", action="store_true", dest="version", help="Give version number then exit")
        (options, args) = parser.parse_args()
        
        if options.version:
            print weewx.__version__
            exit()
            
        if len(args) < 1:
            sys.stderr.write("Missing argument(s).\n")
            sys.stderr.write(parser.parse_args(["--help"]))
            exit()
        
        if options.daemon:
            daemon.daemonize(pidfile='/var/run/weewx.pid')
            
        self.config_path = os.path.abspath(args[0])
            
        # Try to open up the given configuration file. Declare an error if unable to.
        try :
            self.config_dict = configobj.ConfigObj(self.config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % args[0])
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Unable to open configuration file %s" % args[0])
            # Reraise the exception (this will eventually cause the program to exit)
            raise

        # Look for the debug flag. If set, ask for extra logging
        weewx.debug = int(self.config_dict.get('debug', 0))
        if weewx.debug:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        syslog.syslog(syslog.LOG_INFO, "wxengine: Using configuration file %s." % self.config_path)

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
        
        #Add the LOOP record to the stats database:
        self.statsDb.addLoopRecord(physicalPacket)

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

    def shutDown(self):
        """Run when an engine shutdown is requested."""
        for obj in self.service_obj:
            obj.shutDown()
            
#===============================================================================
#                    Class StdService
#===============================================================================

class StdService(object):
    """Abstract base class for all services."""
    
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

    def shutDown(self):
        pass
    
#===============================================================================
#                    Class StdCatchUp
#===============================================================================

class StdCatchUp(StdService):        
    """Looks for data that is on the weather station but not in the database.
    
    If any data is found, it arranges to have it put in the database."""
    
    def setup(self):
        self.engine.getArchiveData()

#===============================================================================
#                    Class StdTimeSynch
#===============================================================================

class StdTimeSynch(StdService):
    """Regularly asks the station to synch up its clock."""

    def setup(self):
        """Zero out the time of last synch, and get the time between synchs."""
        self.last_synch_ts = 0
        self.clock_check = int(self.engine.config_dict['Station'].get('clock_check','14400'))
        
    def preloop(self):
        """Ask the station to synch up if enough time has passed."""
        # Synch up the station's clock if it's been more than 
        # clock_check seconds since the last check:
        now_ts = time.time()
        if now_ts - self.last_synch_ts >= self.clock_check:
            self.engine.station.setTime()
            self.last_synch_ts = now_ts
            
#===============================================================================
#                    Class StdPrint
#===============================================================================

class StdPrint(StdService):
    """Service that prints diagnostic information when a LOOP
    or archive packet is received."""
    
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
#                    Class StdRESTful
#===============================================================================

class StdRESTful(StdService):

    def __init__(self, engine):
        StdService.__init__(self, engine)
        self.queue  = None
        self.thread = None
        
    def setup(self):
        
        station_list = []

        # Each subsection in section [RESTful] represents a different upload site:
        for site in self.engine.config_dict['RESTful'].sections:

            # Get the dictionary for this site:
            site_dict = self.engine.config_dict['RESTful'][site]
            # Some protocols require extra entries:
            site_dict['latitude']  = self.engine.config_dict['Station']['latitude']
            site_dict['longitude'] = self.engine.config_dict['Station']['longitude']
            site_dict['hardware']  = self.engine.config_dict['Station']['station_type']
            try:
                # Instantiate an instance of the class that implements the
                # protocol used by this site. It will throw an exception if
                # not enough information is available to instantiate.
                obj_class = 'weewx.restful.' + site_dict['protocol']
                new_station = weeutil.weeutil._get_object(obj_class, site, site_dict)
            except KeyError:
                syslog.syslog(syslog.LOG_DEBUG, "wxengine: Data will not be posted to %s" % (site,))
            else:
                station_list.append(new_station)
                syslog.syslog(syslog.LOG_DEBUG, "wxengine: Data will be posted to %s" % (site,))
        
        # Were there any valid upload sites?
        if len(station_list) > 0 :
            # Yes. Proceed by setting up the queue and thread.
            
            # Create an instance of weewx.archive.Archive
            archiveFilename = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'], 
                                           self.engine.config_dict['Archive']['archive_file'])
            archive = weewx.archive.Archive(archiveFilename)
            # Create the queue into which we'll put the timestamps of new data
            self.queue = Queue.Queue()
            # Start up the thread:
            self.thread = weewx.restful.RESTThread(archive, self.queue, station_list)
            self.thread.start()
            syslog.syslog(syslog.LOG_DEBUG, "wxengine: Started thread for RESTful upload sites.")
        
        else:
            self.queue  = None
            self.thread = None
            syslog.syslog(syslog.LOG_DEBUG, "wxengine: No RESTful upload sites. Thread not started.")
        
    def postArchiveData(self, rec):
        """Post the new archive data to the WU queue"""
        if self.queue:
            self.queue.put(rec['dateTime'])

    def shutDown(self):
        """Shut down the RESTful thread"""
        # Make sure we have initialized:
        if self.queue:
            # Put a None in the queue. This will signal to the thread to shutdown
            self.queue.put(None)
            # Wait for the thread to exit:
            self.thread.join(20.0)
            syslog.syslog(syslog.LOG_DEBUG, "Shut down RESTful thread.")

#===============================================================================
#                    Class StdReportService
#===============================================================================

class StdReportService(StdService):
    
    def __init__(self, engine):
        StdService.__init__(self, engine)
        self.thread = None
        self.first_run = True
        
    def processArchiveData(self):
        """This function processes any new archive data"""
        # Now process the data, using a separate thread
        self.thread = weewx.reportengine.StdReportEngine(self.engine.config_path,
                                                         first_run = self.first_run) 
        self.thread.start()
        self.first_run = False

    def shutDown(self):
        if self.thread:
            self.thread.join(20.0)
            syslog.syslog(syslog.LOG_DEBUG, "Shut down StdReportService thread.")
        self.first_run = True

#===============================================================================
#                       Signal handler
#===============================================================================

class Restart(Exception):
    """Exception thrown when restarting the engine is desired."""
    
def sigHUPhandler(signum, frame):
    syslog.syslog(syslog.LOG_DEBUG, "wxengine: Received signal HUP. Throwing Restart exception.")
    raise Restart

#===============================================================================
#                    Function main
#===============================================================================

def main(EngineClass = StdEngine) :
    """Prepare the main loop and run it. 

    Mostly consists of a bunch of high-level preparatory calls, protected
    by try blocks in the case of an exception."""

    try:

        # Create and initialize the engine
        engine = EngineClass()
        signal.signal(signal.SIGHUP, sigHUPhandler)
        
    except Exception, ex:
        # Caught unrecoverable error. Log it, exit
        syslog.syslog(syslog.LOG_CRIT, "wxengine: Unable to initialize main loop:")
        syslog.syslog(syslog.LOG_CRIT, "    ****  %s" % ex)
        syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting.")
        # Reraise the exception (this will eventually cause the program to exit)
        raise


    while True:
        # Start the main loop, wrapping it in an exception block.
        try:

            engine.start()

        # Catch any recoverable weewx I/O errors:
        except weewx.WeeWxIOError, e:
            # Caught an I/O error. Log it, wait 60 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Caught WeeWxIOError: %s" % e)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 60 seconds then retrying...")
            time.sleep(60)
            syslog.syslog(syslog.LOG_NOTICE, "wxengine: retrying...")
            
        except OSError, e:
            # Caught an OS error. Log it, wait 10 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Caught OSError: %s" % e)
            syslog.syslog(syslog.LOG_CRIT, "    ****  This is typically caused by another program trying to access the weather station")
            syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 10 seconds then retrying...")
            time.sleep(10)
            syslog.syslog(syslog.LOG_NOTICE,"wxengine: retrying...")

        except Restart:
            syslog.syslog(syslog.LOG_NOTICE, "wxengine: Received signal HUP. Restarting.")
            
        # If run from the command line, catch any keyboard interrupts and log them:
        except KeyboardInterrupt:
            syslog.syslog(syslog.LOG_CRIT,"wxengine: Keyboard interrupt.")
            raise SystemExit, "keyboard interrupt"

        # Catch any non-recoverable errors. Log them, exit
        except Exception, ex:
            # Caught unrecoverable error. Log it, exit
            syslog.syslog(syslog.LOG_CRIT, "wxengine: Caught unrecoverable exception in wxengine:")
            syslog.syslog(syslog.LOG_CRIT, "    ****  %s" % ex)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting.")
            # Reraise the exception (this will eventually cause the program to exit)
            raise

        # Shut down the engine first, before retrying.
        engine.shutDown()
