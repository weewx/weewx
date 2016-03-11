#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Main engine for the weewx weather system."""

# Python imports
import gc
import os.path
import platform
import signal
import socket
import sys
import syslog
import time
import thread

# 3rd party imports:
import configobj
import daemon

# weewx imports:
import weedb
import weewx.accum
import weewx.manager
import weewx.station
import weewx.reportengine
import weeutil.weeutil
from weeutil.weeutil import to_bool, to_int
from weewx import all_service_groups

class BreakLoop(Exception):
    """Exception raised when it's time to break the main loop."""

class InitializationError(weewx.WeeWxIOError):
    """Exception raised when unable to initialize the console."""

#==============================================================================
#                    Class StdEngine
#==============================================================================

class StdEngine(object):
    """The main engine responsible for the creating and dispatching of events
    from the weather station.
    
    It loads a set of services, specified by an option in the configuration
    file.
    
    When a service loads, it binds callbacks to events. When an event occurs,
    the bound callback will be called."""
    
    def __init__(self, config_dict):
        """Initialize an instance of StdEngine.
        
        config_dict: The configuration dictionary. """
        # Set a default socket time out, in case FTP or HTTP hang:
        timeout = int(config_dict.get('socket_timeout', 20))
        socket.setdefaulttimeout(timeout)
        
        # Default garbage collection is every 3 hours:
        self.gc_interval = int(config_dict.get('gc_interval', 3*3600))

        # Set up the callback dictionary:
        self.callbacks = dict()

        # Set up the weather station hardware:
        self.setupStation(config_dict)

        # Hook for performing any chores before loading the services:
        self.preLoadServices(config_dict)

        # Load the services:
        self.loadServices(config_dict)

        # Another hook for after the services load.
        self.postLoadServices(config_dict)
        
    def setupStation(self, config_dict):
        """Set up the weather station hardware."""
        # Get the hardware type from the configuration dictionary. This will be
        # a string such as "VantagePro"
        stationType = config_dict['Station']['station_type']
    
        # Find the driver name for this type of hardware
        driver = config_dict[stationType]['driver']
        
        syslog.syslog(syslog.LOG_INFO, "engine: Loading station type %s (%s)" % (stationType, driver))

        # Import the driver:
        __import__(driver)
    
        # Open up the weather station, wrapping it in a try block in case
        # of failure.
        try:
            # This is a bit of Python wizardry. First, find the driver module
            # in sys.modules.
            driver_module = sys.modules[driver]
            # Find the function 'loader' within the module:
            loader_function = getattr(driver_module, 'loader')
            # Call it with the configuration dictionary as the only argument:
            self.console = loader_function(config_dict, self)
        except Exception, ex:
            # Signal that we have an initialization error:
            raise InitializationError(ex)
        
    def preLoadServices(self, config_dict):
        
        self.stn_info = weewx.station.StationInfo(self.console, **config_dict['Station'])
        self.db_binder = weewx.manager.DBBinder(config_dict)
        
    def loadServices(self, config_dict):
        """Set up the services to be run."""
        # This will hold the list of objects, after the services has been
        # instantiated:
        self.service_obj = []

        # Wrap the instantiation of the services in a try block, so if an
        # exception occurs, any service that may have started can be shut
        # down in an orderly way.
        try:
            # Go through each of the service lists one by one:
            for service_group in all_service_groups:
                # For each service list, retrieve all the listed services.
                # Provide a default, empty list in case the service list is
                # missing completely:
                for svc in weeutil.weeutil.option_as_list(config_dict['Engine']['Services'].get(service_group, [])):
                    if svc == '':
                        syslog.syslog(syslog.LOG_DEBUG, "engine: No services in service group %s" % service_group)
                        continue
                    # For each service, instantiates an instance of the class,
                    # passing self and the configuration dictionary as the
                    # arguments:
                    syslog.syslog(syslog.LOG_DEBUG, "engine: Loading service %s" % svc)
                    self.service_obj.append(weeutil.weeutil._get_object(svc)(self, config_dict))
                    syslog.syslog(syslog.LOG_DEBUG, "engine: Finished loading service %s" % svc)
        except Exception:
            # An exception occurred. Shut down any running services, then
            # reraise the exception.
            self.shutDown()
            raise
        
    def postLoadServices(self, config_dict):
        pass

    def run(self):
        """Main execution entry point."""
        
        # Wrap the outer loop in a try block so we can do an orderly shutdown
        # should an exception occur:
        try:
            # Send out a STARTUP event:
            self.dispatchEvent(weewx.Event(weewx.STARTUP))
            
            syslog.syslog(syslog.LOG_INFO, "engine: Starting main packet loop.")

            last_gc = int(time.time())

            # This is the outer loop. 
            while True:

                # See if garbage collection is scheduled:
                if int(time.time()) - last_gc > self.gc_interval:
                    ngc = gc.collect()
                    syslog.syslog(syslog.LOG_INFO, "engine: garbage collected %d objects" % ngc)
                    last_gc = int(time.time())

                # First, let any interested services know the packet LOOP is
                # about to start
                self.dispatchEvent(weewx.Event(weewx.PRE_LOOP))
    
                # Get ready to enter the main packet loop. An exception of type
                # BreakLoop will get thrown when a service wants to break the
                # loop and interact with the console.
                try:
                
                    # And this is the main packet LOOP. It will continuously
                    # generate LOOP packets until some service breaks it by
                    # throwing an exception (usually when an archive period
                    # has passed).
                    for packet in self.console.genLoopPackets():
                        
                        # Package the packet as an event, then dispatch it.
                        self.dispatchEvent(weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet))

                        # Allow services to break the loop by throwing
                        # an exception:
                        self.dispatchEvent(weewx.Event(weewx.CHECK_LOOP, packet=packet))

                    syslog.syslog(syslog.LOG_CRIT, "engine: Internal error. Packet loop has exited.")
                    
                except BreakLoop:
                    
                    # Send out an event saying the packet LOOP is done:
                    self.dispatchEvent(weewx.Event(weewx.POST_LOOP))

        finally:
            # The main loop has exited. Shut the engine down.
            syslog.syslog(syslog.LOG_DEBUG, "engine: Main loop exiting. Shutting engine down.")
            self.shutDown()

    def bind(self, event_type, callback):
        """Binds an event to a callback function."""

        # Each event type has a list of callback functions to be called.
        # If we have not seen the event type yet, then create an empty list,
        # otherwise append to the existing list:
        self.callbacks.setdefault(event_type, []).append(callback)

    def dispatchEvent(self, event):
        """Call all registered callbacks for an event."""
        # See if any callbacks have been registered for this event type:
        if event.event_type in self.callbacks:
            # Yes, at least one has been registered. Call them in order:
            for callback in self.callbacks[event.event_type]:
                # Call the function with the event as an argument:
                callback(event)

    def shutDown(self):
        """Run when an engine shutdown is requested."""
        # If we've gotten as far as having a list of service objects, then shut
        # them all down:
        if hasattr(self, 'service_obj'):
            while len(self.service_obj):
                # Wrap each individual service shutdown, in case of a problem.
                try:
                    # Start from the end of the list and move forward
                    self.service_obj[-1].shutDown()
                except:
                    pass
                # Delete the actual service
                del self.service_obj[-1]

            del self.service_obj
            
        try:
            del self.callbacks
        except AttributeError:
            pass

        try:
            # Close the console:
            self.console.closePort()
            del self.console
        except:
            pass
        
        try:
            self.db_binder.close()
            del self.db_binder
        except:
            pass

    def _get_console_time(self):
        try:
            return self.console.getTime()
        except NotImplementedError:
            return int(time.time()+0.5)

#==============================================================================
#                    Class StdService
#==============================================================================

class StdService(object):
    """Abstract base class for all services."""
    
    def __init__(self, engine, config_dict):
        self.engine = engine
        self.config_dict = config_dict

    def bind(self, event_type, callback):
        """Bind the specified event to a callback."""
        # Just forward the request to the main engine:
        self.engine.bind(event_type, callback)
        
    def shutDown(self):
        pass

#==============================================================================
#                    Class StdConvert
#==============================================================================

class StdConvert(StdService):
    """Service for performing unit conversions.
    
    This service acts as a filter. Whatever packets and records come in are
    converted to a target unit system.
    
    This service should be run before most of the others, so observations appear
    in the correct unit."""
    
    def __init__(self, engine, config_dict):
        # Initialize my base class:
        super(StdConvert, self).__init__(engine, config_dict)

        # Get the target unit nickname (something like 'US' or 'METRIC'):
        target_unit_nickname = config_dict['StdConvert']['target_unit']
        # Get the target unit: weewx.US, weewx.METRIC, weewx.METRICWX
        self.target_unit = weewx.units.unit_constants[target_unit_nickname.upper()]
        # Bind self.converter to the appropriate standard converter
        self.converter = weewx.units.StdUnitConverters[self.target_unit]
        
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
        syslog.syslog(syslog.LOG_INFO, "engine: StdConvert target unit is 0x%x" % self.target_unit)
        
    def new_loop_packet(self, event):
        """Do unit conversions for a LOOP packet"""
        # No need to do anything if the packet is already in the target
        # unit system
        if event.packet['usUnits'] == self.target_unit: return
        # Perform the conversion
        converted_packet = self.converter.convertDict(event.packet)
        # Add the new unit system
        converted_packet['usUnits'] = self.target_unit
        # Replace the old packet with the new, converted packet:
        event.packet = converted_packet

    def new_archive_record(self, event):
        """Do unit conversions for an archive record."""
        # No need to do anything if the record is already in the target
        # unit system
        if event.record['usUnits'] == self.target_unit: return
        # Perform the conversion
        converted_record = self.converter.convertDict(event.record)
        # Add the new unit system
        converted_record['usUnits'] = self.target_unit
        # Replace the old record with the new, converted record
        event.record = converted_record
        
#==============================================================================
#                    Class StdCalibrate
#==============================================================================

class StdCalibrate(StdService):
    """Adjust data using calibration expressions.
    
    This service must be run before StdArchive, so the correction is applied
    before the data is archived."""
    
    def __init__(self, engine, config_dict):
        # Initialize my base class:
        super(StdCalibrate, self).__init__(engine, config_dict)
        
        # Get the list of calibration corrections to apply. If a section
        # is missing, a KeyError exception will get thrown:
        try:
            correction_dict = config_dict['StdCalibrate']['Corrections']
            self.corrections = {}

            # For each correction, compile it, then save in a dictionary of
            # corrections to be applied:
            for obs_type in correction_dict.scalars:
                self.corrections[obs_type] = compile(correction_dict[obs_type], 
                                                     'StdCalibrate', 'eval')
            
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE, "engine: No calibration information in config file. Ignored.")
            
    def new_loop_packet(self, event):
        """Apply a calibration correction to a LOOP packet"""
        for obs_type in self.corrections:
            try:
                event.packet[obs_type] = eval(self.corrections[obs_type], None, event.packet)
            except (TypeError, NameError):
                pass
            except ValueError, e:
                syslog.syslog(syslog.LOG_ERR, "engine: StdCalibration loop error %s" % e)

    def new_archive_record(self, event):
        """Apply a calibration correction to an archive packet"""
        # If the record was software generated, then any corrections have
        # already been applied in the LOOP packet.
        if event.origin != 'software':
            for obs_type in self.corrections:
                try:
                    event.record[obs_type] = eval(self.corrections[obs_type], None, event.record)
                except (TypeError, NameError):
                    pass
                except ValueError, e:
                    syslog.syslog(syslog.LOG_ERR, "engine: StdCalibration archive error %s" % e)

#==============================================================================
#                    Class StdQC
#==============================================================================

class StdQC(StdService):
    """Performs quality check on incoming data."""

    def __init__(self, engine, config_dict):
        super(StdQC, self).__init__(engine, config_dict)

        # If the 'StdQC' or 'MinMax' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done.
        try:
            mm_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE, "engine: No QC information in config file.")
            return

        self.min_max_dict = {}

        target_unit_name = config_dict['StdConvert']['target_unit']
        target_unit = weewx.units.unit_constants[target_unit_name.upper()]
        converter = weewx.units.StdUnitConverters[target_unit]

        for obs_type in mm_dict.scalars:
            minval = float(mm_dict[obs_type][0])
            maxval = float(mm_dict[obs_type][1])
            if len(mm_dict[obs_type]) == 3:
                group = weewx.units._getUnitGroup(obs_type)
                vt = (minval, mm_dict[obs_type][2], group)
                minval = converter.convert(vt)[0]
                vt = (maxval, mm_dict[obs_type][2], group)
                maxval = converter.convert(vt)[0]
            self.min_max_dict[obs_type] = (minval, maxval)
        
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
    def new_loop_packet(self, event):
        """Apply quality check to the data in a LOOP packet"""
        for obs_type in self.min_max_dict:
            if event.packet.has_key(obs_type) and event.packet[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= event.packet[obs_type] <= self.min_max_dict[obs_type][1]:
                    syslog.syslog(syslog.LOG_NOTICE, "engine: %s LOOP value '%s' %s outside limits (%s, %s)" % 
                                  (weeutil.weeutil.timestamp_to_string(event.packet['dateTime']), 
                                   obs_type, event.packet[obs_type], 
                                   self.min_max_dict[obs_type][0], self.min_max_dict[obs_type][1]))
                    event.packet[obs_type] = None

    def new_archive_record(self, event):
        """Apply quality check to the data in an archive packet"""
        for obs_type in self.min_max_dict:
            if event.record.has_key(obs_type) and event.record[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= event.record[obs_type] <= self.min_max_dict[obs_type][1]:
                    syslog.syslog(syslog.LOG_NOTICE, "engine: %s Archive value '%s' %s outside limits (%s, %s)" % 
                                  (weeutil.weeutil.timestamp_to_string(event.record['dateTime']),
                                   obs_type, event.record[obs_type], 
                                   self.min_max_dict[obs_type][0], self.min_max_dict[obs_type][1]))
                    event.record[obs_type] = None

#==============================================================================
#                    Class StdArchive
#==============================================================================

class StdArchive(StdService):
    """Service that archives LOOP and archive data in the SQL databases."""
    
    # This service manages an "accumulator", which records high/lows and
    # averages of LOOP packets over an archive period. At the end of the
    # archive period it then emits an archive record.
    
    def __init__(self, engine, config_dict):
        super(StdArchive, self).__init__(engine, config_dict)

        # Extract the various options from the config file. If it's missing, fill in with defaults:
        if 'StdArchive' in config_dict:
            self.data_binding      = config_dict['StdArchive'].get('data_binding', 'wx_binding')
            self.record_generation = config_dict['StdArchive'].get('record_generation', 'hardware').lower()
            self.archive_delay = to_int(config_dict['StdArchive'].get('archive_delay', 15))
            software_interval  = to_int(config_dict['StdArchive'].get('archive_interval', 300))
            self.loop_hilo     = to_bool(config_dict['StdArchive'].get('loop_hilo', True))
        else:
            self.data_binding = 'wx_binding'
            self.record_generation = 'hardware'
            self.archive_delay = 15
            software_interval = 300
            self.loop_hilo = True
            
        syslog.syslog(syslog.LOG_INFO, "engine: Archive will use data binding %s" % self.data_binding)
        
        syslog.syslog(syslog.LOG_INFO, "engine: Record generation will be attempted in '%s'" % 
                      (self.record_generation,))

        # If the station supports a hardware archive interval, use that.
        # Warn if it is different than what is in config.
        try:
            if software_interval != self.engine.console.archive_interval:
                syslog.syslog(syslog.LOG_ERR,
                              "engine: The archive interval in the"
                              " configuration file (%d) does not match the"
                              " station hardware interval (%d)." %
                              (software_interval,
                               self.engine.console.archive_interval))
            self.archive_interval = self.engine.console.archive_interval
        except NotImplementedError:
            self.archive_interval = software_interval
        syslog.syslog(syslog.LOG_INFO, "engine: Using archive interval of %d seconds" % 
                      self.archive_interval)

        if self.archive_delay <= 0:
            raise weewx.ViolatedPrecondition("Archive delay (%.1f) must be greater than zero." % 
                                             (self.archive_delay,))

        syslog.syslog(syslog.LOG_DEBUG, "engine: Use LOOP data in hi/low calculations: %d" % 
                      (self.loop_hilo,))
        
        self.setup_database(config_dict)
        
        self.bind(weewx.STARTUP,            self.startup)
        self.bind(weewx.PRE_LOOP,           self.pre_loop)
        self.bind(weewx.POST_LOOP,          self.post_loop)
        self.bind(weewx.CHECK_LOOP,         self.check_loop)
        self.bind(weewx.NEW_LOOP_PACKET,    self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
    
    def startup(self, event):  # @UnusedVariable
        """Called when the engine is starting up."""
        # The engine is starting up. The main task is to do a catch up on any
        # data still on the station, but not yet put in the database. Not
        # all consoles can do this, so be prepared to catch the exception:
        try:
            self._catchup(self.engine.console.genStartupRecords)
        except NotImplementedError:
            pass
                    
    def pre_loop(self, event):  # @UnusedVariable
        """Called before the main packet loop is entered."""
        
        # If this the the initial time through the loop, then the end of
        # the archive and delay periods need to be primed:
        if not hasattr(self, 'end_archive_period_ts'):
            self.end_archive_period_ts = \
                (int(self.engine._get_console_time() / self.archive_interval) + 1) * self.archive_interval
            self.end_archive_delay_ts  =  self.end_archive_period_ts + self.archive_delay

    def new_loop_packet(self, event):
        """Called when A new LOOP record has arrived."""
        
        the_time = event.packet['dateTime']
        
        # Do we have an accumulator at all? If not, create one:
        if not hasattr(self, "accumulator"):
            self.accumulator = self._new_accumulator(the_time)

        # Try adding the LOOP packet to the existing accumulator. If the
        # timestamp is outside the timespan of the accumulator, an exception
        # will be thrown:
        try:
            self.accumulator.addRecord(event.packet, self.loop_hilo)
        except weewx.accum.OutOfSpan:
            # Shuffle accumulators:
            (self.old_accumulator, self.accumulator) = (self.accumulator, self._new_accumulator(the_time))
            # Add the LOOP packet to the new accumulator:
            self.accumulator.addRecord(event.packet, self.loop_hilo)

    def check_loop(self, event):
        """Called after any loop packets have been processed. This is the opportunity
        to break the main loop by throwing an exception."""
        # Is this the end of the archive period? If so, dispatch an
        # END_ARCHIVE_PERIOD event
        if event.packet['dateTime'] > self.end_archive_period_ts:
            self.engine.dispatchEvent(weewx.Event(weewx.END_ARCHIVE_PERIOD, packet=event.packet))
            self.end_archive_period_ts += self.archive_interval
            
        # Has the end of the archive delay period ended? If so, break the loop.
        if event.packet['dateTime'] >= self.end_archive_delay_ts:
            raise BreakLoop

    def post_loop(self, event):  # @UnusedVariable
        """The main packet loop has ended, so process the old accumulator."""
        # If we happen to startup in the small time interval between the end of
        # the archive interval and the end of the archive delay period, then
        # there will be no old accumulator.
        dbmanager = self.engine.db_binder.get_manager(self.data_binding)
        if hasattr(self, 'old_accumulator'):
            dbmanager.updateHiLo(self.old_accumulator)
            # If the user has requested software generation, then do that:
            if self.record_generation == 'software':
                self._software_catchup()
            elif self.record_generation == 'hardware':
                # Otherwise, try to honor hardware generation. An exception
                # will be raised if the console does not support it. In that
                # case, fall back to software generation.
                try:
                    self._catchup(self.engine.console.genArchiveRecords)
                except NotImplementedError:
                    self._software_catchup()
            else:
                raise ValueError("Unknown station record generation value %s" % self.record_generation)

        # Set the time of the next break loop:
        self.end_archive_delay_ts = self.end_archive_period_ts + self.archive_delay
        
    def new_archive_record(self, event):
        """Called when a new archive record has arrived. 
        Put it in the archive database."""
        dbmanager = self.engine.db_binder.get_manager(self.data_binding)
        dbmanager.addRecord(event.record)

    def setup_database(self, config_dict):  # @UnusedVariable
        """Setup the main database archive"""

        # This will create the database if it doesn't exist, then return an
        # opened instance of the database manager. 
        dbmanager = self.engine.db_binder.get_manager(self.data_binding, initialize=True)
        syslog.syslog(syslog.LOG_INFO, "engine: Using binding '%s' to database '%s'" % (self.data_binding, dbmanager.database_name))
        
        # Back fill the daily summaries.
        _nrecs, _ndays = dbmanager.backfill_day_summary()

    def _catchup(self, generator):
        """Pull any unarchived records off the console and archive them.
        
        If the hardware does not support hardware archives, an exception of
        type NotImplementedError will be thrown.""" 

        dbmanager = self.engine.db_binder.get_manager(self.data_binding)
        # Find out when the database was last updated.
        lastgood_ts = dbmanager.lastGoodStamp()

        try:
            # Now ask the console for any new records since then.
            # (Not all consoles support this feature).
            for record in generator(lastgood_ts):
                self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                                                      record=record,
                                                      origin='hardware'))
        except weewx.HardwareError, e:
            syslog.syslog(syslog.LOG_ERR, "engine: Internal error detected. Catchup abandoned")
            syslog.syslog(syslog.LOG_ERR, "**** %s" % e)
        
    def _software_catchup(self):
        # Extract a record out of the old accumulator. 
        record = self.old_accumulator.getRecord()
        # Add the archive interval
        record['interval'] = self.archive_interval / 60
        # Send out an event with the new record:
        self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=record, origin='software'))
    
    def _new_accumulator(self, timestamp):
        start_ts = weeutil.weeutil.startOfInterval(timestamp,
                                                   self.archive_interval)
        end_ts = start_ts + self.archive_interval
        
        # Instantiate a new accumulator
        new_accumulator =  weewx.accum.Accum(weeutil.weeutil.TimeSpan(start_ts, end_ts))
        return new_accumulator
    
#==============================================================================
#                    Class StdTimeSynch
#==============================================================================

class StdTimeSynch(StdService):
    """Regularly asks the station to synch up its clock."""
    
    def __init__(self, engine, config_dict):
        super(StdTimeSynch, self).__init__(engine, config_dict)
        
        # Zero out the time of last synch, and get the time between synchs.
        self.last_synch_ts = 0
        self.clock_check = int(config_dict['StdTimeSynch'].get('clock_check', 14400))
        self.max_drift   = int(config_dict['StdTimeSynch'].get('max_drift', 5))
        
        self.bind(weewx.STARTUP,  self.startup)
        self.bind(weewx.PRE_LOOP, self.pre_loop)
    
    def startup(self, event):  # @UnusedVariable
        """Called when the engine is starting up."""
        self.do_sync()
        
    def pre_loop(self, event):  # @UnusedVariable
        """Called before the main event loop is started."""
        self.do_sync()
        
    def do_sync(self):
        """Ask the station to synch up if enough time has passed."""
        # Synch up the station's clock if it's been more than clock_check
        # seconds since the last check:
        now_ts = time.time()
        if now_ts - self.last_synch_ts >= self.clock_check:
            self.last_synch_ts = now_ts
            try:
                console_time = self.engine.console.getTime()
                if console_time is None: return
                # getTime can take a long time to run, so we use the current
                # system time
                diff = console_time - time.time()
                syslog.syslog(syslog.LOG_INFO, 
                              "engine: Clock error is %.2f seconds (positive is fast)" % diff)
                if abs(diff) > self.max_drift:
                    try:
                        self.engine.console.setTime()
                    except NotImplementedError:
                        syslog.syslog(syslog.LOG_DEBUG, "engine: Station does not support setting the time")
            except NotImplementedError:
                syslog.syslog(syslog.LOG_DEBUG, "engine: Station does not support reading the time")

#==============================================================================
#                    Class StdPrint
#==============================================================================

class StdPrint(StdService):
    """Service that prints diagnostic information when a LOOP
    or archive packet is received."""
    
    def __init__(self, engine, config_dict):
        super(StdPrint, self).__init__(engine, config_dict)

        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
    def new_loop_packet(self, event):
        """Print out the new LOOP packet"""
        print "LOOP:  ", weeutil.weeutil.timestamp_to_string(event.packet['dateTime']), StdPrint.sort(event.packet)
    
    def new_archive_record(self, event):
        """Print out the new archive record."""
        print "REC:   ", weeutil.weeutil.timestamp_to_string(event.record['dateTime']), StdPrint.sort(event.record)
       
    @staticmethod 
    def sort(rec):
        return ", ".join(["%s: %s" % (k, rec.get(k)) for k in sorted(rec, key=str.lower)])
            
        
        
#==============================================================================
#                    Class StdReport
#==============================================================================

class StdReport(StdService):
    """Launches a separate thread to do reporting."""
    
    def __init__(self, engine, config_dict):
        super(StdReport, self).__init__(engine, config_dict)
        self.max_wait    = int(config_dict['StdReport'].get('max_wait', 60))
        self.thread      = None
        self.launch_time = None
        
        self.bind(weewx.POST_LOOP, self.launch_report_thread)
        
    def launch_report_thread(self, event):  # @UnusedVariable
        """Called after the packet LOOP. Processes any new data."""
        # Do not launch the reporting thread if an old one is still alive.
        # To guard against a zombie thread (alive, but doing nothing) launch
        # anyway if enough time has passed.
        if self.thread and self.thread.isAlive() and time.time()-self.launch_time < self.max_wait:
            return
            
        try:
            self.thread = weewx.reportengine.StdReportEngine(self.config_dict,
                                                             self.engine.stn_info,
                                                             first_run= not self.launch_time) 
            self.thread.start()
            self.launch_time = time.time()
        except thread.error:
            syslog.syslog(syslog.LOG_ERR, "Unable to launch report thread.")
            self.thread = None

    def shutDown(self):
        if self.thread:
            syslog.syslog(syslog.LOG_INFO, "engine: Shutting down StdReport thread")
            self.thread.join(20.0)
            if self.thread.isAlive():
                syslog.syslog(syslog.LOG_ERR, "engine: Unable to shut down StdReport thread")
            else:
                syslog.syslog(syslog.LOG_DEBUG, "engine: StdReport thread has been terminated")
        self.thread = None
        self.launch_time = None

#==============================================================================
#                       Signal handler
#==============================================================================

class Restart(Exception):
    """Exception thrown when restarting the engine is desired."""
    
def sigHUPhandler(dummy_signum, dummy_frame):
    syslog.syslog(syslog.LOG_DEBUG, "engine: Received signal HUP. Initiating restart.")
    raise Restart

class Terminate(Exception):
    """Exception thrown when terminating the engine."""

def sigTERMhandler(dummy_signum, dummy_frame):
    syslog.syslog(syslog.LOG_DEBUG, "engine: Received signal TERM.")
    raise Terminate

#==============================================================================
#                    Function main
#==============================================================================

def main(options, args, EngineClass=StdEngine) :
    """Prepare the main loop and run it. 

    Mostly consists of a bunch of high-level preparatory calls, protected
    by try blocks in the case of an exception."""

    # Set the logging facility.
    syslog.openlog(options.log_label, syslog.LOG_PID | syslog.LOG_CONS)

    # Set up the signal handlers.
    signal.signal(signal.SIGHUP, sigHUPhandler)
    signal.signal(signal.SIGTERM, sigTERMhandler)

    syslog.syslog(syslog.LOG_INFO, "engine: Initializing weewx version %s" % weewx.__version__)
    syslog.syslog(syslog.LOG_INFO, "engine: Using Python %s" % sys.version)
    syslog.syslog(syslog.LOG_INFO, "engine: Platform %s" % platform.platform())

    # Save the current working directory. A service might
    # change it. In case of a restart, we need to change it back.
    cwd = os.getcwd()

    if options.daemon:
        syslog.syslog(syslog.LOG_INFO, "engine: pid file is %s" % options.pidfile)
        daemon.daemonize(pidfile=options.pidfile)

    # for backward compatibility, recognize loop_on_init from command-line
    loop_on_init = options.loop_on_init

    # be sure that the system has a reasonable time (at least 1 jan 2000).
    # log any problems every minute.
    ts = time.time()
    n = 0
    while ts < 946684800:
        if n % 120 == 0:
            syslog.syslog(syslog.LOG_INFO,
                          "engine: waiting for sane time.  current time is %s"
                          % weeutil.weeutil.timestamp_to_string(ts))
        n += 1
        time.sleep(0.5)
        ts = time.time()

    while True:

        os.chdir(cwd)

        config_path = os.path.abspath(args[0])
        config_dict = getConfiguration(config_path)

        # Look for the debug flag. If set, ask for extra logging
        weewx.debug = int(config_dict.get('debug', 0))
        if weewx.debug:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        else:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

        # See if there is a loop_on_init directive in the configuration, but
        # use it only if nothing was specified via command-line.
        if loop_on_init is None:
            loop_on_init = to_bool(config_dict.get('loop_on_init', False))

        try:
            syslog.syslog(syslog.LOG_DEBUG, "engine: Initializing engine")

            # Create and initialize the engine
            engine = EngineClass(config_dict)
    
            syslog.syslog(syslog.LOG_INFO, "engine: Starting up weewx version %s" % weewx.__version__)

            # Start the engine. It should run forever unless an exception
            # occurs. Log it if the function returns.
            engine.run()
            syslog.syslog(syslog.LOG_CRIT, "engine: Unexpected exit from main loop. Program exiting.")
    
        # Catch any console initialization error:
        except InitializationError, e:
            # Log it:
            syslog.syslog(syslog.LOG_CRIT, "engine: Unable to load driver: %s" % e)
            # See if we should loop, waiting for the console to be ready.
            # Otherwise, just exit.
            if loop_on_init:
                syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 60 seconds then retrying...")
                time.sleep(60)
                syslog.syslog(syslog.LOG_NOTICE, "engine: retrying...")
            else:
                syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting...")
                sys.exit(weewx.IO_ERROR)

        # Catch any recoverable weewx I/O errors:
        except weewx.WeeWxIOError, e:
            # Caught an I/O error. Log it, wait 60 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "engine: Caught WeeWxIOError: %s" % e)
            if options.exit:
                syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting...")
                sys.exit(weewx.IO_ERROR)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 60 seconds then retrying...")
            time.sleep(60)
            syslog.syslog(syslog.LOG_NOTICE, "engine: retrying...")
            
        except weedb.OperationalError, e:
            # Caught a database error. Log it, wait 120 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "engine: Caught database OperationalError: %s" % e)
            if options.exit:
                syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting...")
                sys.exit(weewx.DB_ERROR)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 2 minutes then retrying...")
            time.sleep(120)
            syslog.syslog(syslog.LOG_NOTICE, "engine: retrying...")
            
        except OSError, e:
            # Caught an OS error. Log it, wait 10 seconds, then try again
            syslog.syslog(syslog.LOG_CRIT, "engine: Caught OSError: %s" % e)
            weeutil.weeutil.log_traceback("    ****  ", syslog.LOG_DEBUG)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Waiting 10 seconds then retrying...")
            time.sleep(10)
            syslog.syslog(syslog.LOG_NOTICE,"engine: retrying...")
    
        except Restart:
            syslog.syslog(syslog.LOG_NOTICE, "engine: Received signal HUP. Restarting.")

        except Terminate:
            syslog.syslog(syslog.LOG_INFO, "engine: Terminating weewx version %s" % weewx.__version__)
            sys.exit()

        # Catch any keyboard interrupts and log them
        except KeyboardInterrupt:
            syslog.syslog(syslog.LOG_CRIT,"engine: Keyboard interrupt.")
            # Reraise the exception (this should cause the program to exit)
            raise
    
        # Catch any non-recoverable errors. Log them, exit
        except Exception, ex:
            # Caught unrecoverable error. Log it, exit
            syslog.syslog(syslog.LOG_CRIT, "engine: Caught unrecoverable exception in engine:")
            syslog.syslog(syslog.LOG_CRIT, "    ****  %s" % ex)
            # Include a stack traceback in the log:
            weeutil.weeutil.log_traceback("    ****  ", syslog.LOG_CRIT)
            syslog.syslog(syslog.LOG_CRIT, "    ****  Exiting.")
            # Reraise the exception (this should cause the program to exit)
            raise

def getConfiguration(config_path):
    """Return the configuration file at the given path."""
    # Try to open up the given configuration file. Declare an error if
    # unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        sys.stderr.write("Unable to open configuration file %s" % config_path)
        syslog.syslog(syslog.LOG_CRIT, "engine: Unable to open configuration file %s" % config_path)
        # Reraise the exception (this should cause the program to exit)
        raise
    except configobj.ConfigObjError, e:
        syslog.syslog(syslog.LOG_CRIT, "engine: Error while parsing configuration file %s" % config_path)
        syslog.syslog(syslog.LOG_CRIT, "****    Reason: '%s'" % e)
        raise

    syslog.syslog(syslog.LOG_INFO, "engine: Using configuration file %s" % config_path)

    return config_dict
