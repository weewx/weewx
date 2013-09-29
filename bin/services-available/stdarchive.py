#
#    Copyright (c) 2009, 2010, 2012, 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

import syslog

import weewx
from weewx.wxengine import StdService

#===============================================================================
#                    Class StdArchive
#===============================================================================

class StdArchive(StdService):
    """Service that archives LOOP and archive data in the SQL databases."""
    
    # This service manages an "accumulator", which records high/lows and averages
    # of LOOP packets over an archive period. At the end of the archive period
    # it then emits an archive record.
    
    def __init__(self, engine, config_dict):
        super(StdArchive, self).__init__(engine, config_dict)

        # Get the archive interval from the configuration file
        software_archive_interval = config_dict['StdArchive'].as_int('archive_interval')

        # If the station supports a hardware archive interval use that instead, but
        # warn if they mismatch:
        try:
            if software_archive_interval != self.engine.console.archive_interval:
                syslog.syslog(syslog.LOG_ERR, "wxengine: The archive interval in the configuration file (%d)"\
                              " does not match the station hardware interval (%d)." % \
                              (software_archive_interval, self.engine.console.archive_interval))
            self.archive_interval = self.engine.console.archive_interval
            syslog.syslog(syslog.LOG_INFO, "wxengine: Using station hardware archive interval of %d" % self.archive_interval)
        except NotImplementedError:
            self.archive_interval = software_archive_interval
            syslog.syslog(syslog.LOG_INFO, "wxengine: Using config file archive interval of %d" % self.archive_interval)

        self.archive_delay    = config_dict['StdArchive'].as_int('archive_delay')
        if self.archive_delay <= 0:
            raise weewx.ViolatedPrecondition("Archive delay (%.1f) must be greater than zero." % (self.archive_delay,))
        
        self.record_generation = config_dict['StdArchive'].get('record_generation', 'hardware').lower()
        syslog.syslog(syslog.LOG_INFO, "wxengine: Record generation will be attempted in '%s'" % (self.record_generation,))

        self.setupArchiveDatabase(config_dict)
        self.setupStatsDatabase(config_dict)
        
        self.bind(weewx.STARTUP,            self.startup)
        self.bind(weewx.PRE_LOOP,           self.pre_loop)
        self.bind(weewx.POST_LOOP,          self.post_loop)
        self.bind(weewx.CHECK_LOOP,         self.check_loop)
        self.bind(weewx.NEW_LOOP_PACKET,    self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
    
    def startup(self, event):
        """Called when the engine is starting up."""
        # The engine is starting up. The main task is to do a catch up on any
        # data still on the station, but not yet put in the database. Not
        # all consoles can do this, so be prepared to catch the exception:
        try:
            self._catchup()
        except NotImplementedError:
            pass
                    
    def pre_loop(self, event):
        """Called before the main packet loop is entered."""
        
        # The only thing that needs to be done is to calculate the end of the
        # archive period, and the end of the archive delay period.
        self.end_archive_period_ts = (int(self.engine._get_console_time() / self.archive_interval) + 1) * self.archive_interval
        self.end_archive_delay_ts  =  self.end_archive_period_ts + self.archive_delay

    def new_loop_packet(self, event):
        """Called when A new LOOP record has arrived."""
        
        the_time = event.packet['dateTime']
        
        # Do we have an accumulator at all? If not, create one:
        if not hasattr(self, "accumulator"):
            self.accumulator = self._new_accumulator(the_time)

        # Try adding the LOOP packet to the existing accumulator. If the timestamp is
        # outside the timespan of the accumulator, an exception will be thrown:
        try:
            self.accumulator.addRecord(event.packet)
        except weewx.accum.OutOfSpan:
            # Shuffle accumulators:
            (self.old_accumulator, self.accumulator) = (self.accumulator, self._new_accumulator(the_time))
            # Add the LOOP packet to the new accumulator:
            self.accumulator.addRecord(event.packet)

    def check_loop(self, event):
        """Called after any loop packets have been processed. This is the opportunity
        to break the main loop by throwing an exception."""
        # Is this the end of the archive period? If so, dispatch an END_ARCHIVE_PERIOD event
        if event.packet['dateTime'] > self.end_archive_period_ts:
            self.engine.dispatchEvent(weewx.Event(weewx.END_ARCHIVE_PERIOD, packet=event))
            self.end_archive_period_ts += self.archive_interval
            
        # Has the end of the archive delay period ended? If so, break the loop.
        if event.packet['dateTime'] >= self.end_archive_delay_ts:
            raise BreakLoop

    def post_loop(self, event):
        """The main packet loop has ended. Time to process the old accumulator."""
        # If we happen to startup in the small time interval between the end of
        # the archive interval and the end of the archive delay period, then
        # there will be no old accumulator and an exception will be thrown. Be
        # prepared to catch it.
        try:
            self.statsDb.updateHiLo(self.old_accumulator)
        except AttributeError:
            return
        
        # If the user has requested software generation, then do that:
        if self.record_generation == 'software':
            self._software_catchup()
        elif self.record_generation == 'hardware':
            # Otherwise, try to honor hardware generation. An exception will
            # be raised if the console does not support it. In that case, fall
            # back to software generation.
            try:
                self._catchup()
            except NotImplementedError:
                self._software_catchup()
        else:
            raise ValueError("Unknown station record generation value %s" % self.record_generation)

    def new_archive_record(self, event):
        """Called when a new archive record has arrived. 
        Put it in the archive database."""
        self.archive.addRecord(event.record)
        self.statsDb.addRecord(event.record)

    def setupArchiveDatabase(self, config_dict):
        """Setup the main database archive"""

        archive_schema_str = config_dict['StdArchive'].get('archive_schema', 'user.schemas.defaultArchiveSchema')
        archive_schema = weeutil.weeutil._get_object(archive_schema_str)
        archive_db = config_dict['StdArchive']['archive_database']
        # This will create the database if it doesn't exist, the return an
        # opened instance of Archive:
        self.archive = weewx.archive.Archive.open_with_create(config_dict['Databases'][archive_db], archive_schema)
        syslog.syslog(syslog.LOG_INFO, "wxengine: Using archive database: %s" % (archive_db,))

    def setupStatsDatabase(self, config_dict):
        """Setup the stats database"""
        
        stats_schema_str = config_dict['StdArchive'].get('stats_schema', 'user.schemas.defaultStatsSchema')
        stats_schema = weeutil.weeutil._get_object(stats_schema_str)
        stats_db = config_dict['StdArchive']['stats_database']
        # This will create the database if it doesn't exist, then return an
        # opened stats database object:
        self.statsDb = weewx.stats.StatsDb.open_with_create(config_dict['Databases'][stats_db], stats_schema)
        # Backfill it with data from the archive. This will do nothing if the
        # stats database is already up-to-date.
        self.statsDb.backfillFrom(self.archive)

        syslog.syslog(syslog.LOG_INFO, "wxengine: Using stats database: %s" % (config_dict['StdArchive']['stats_database'],))
        
    def shutDown(self):
        self.archive.close()
        self.statsDb.close()
        
    def _catchup(self):
        """Pull any unarchived records off the console and archive them.
        
        If the hardware does not support hardware archives, an exception of type
        NotImplementedError will be thrown.""" 

        # Find out when the archive was last updated.
        lastgood_ts = self.archive.lastGoodStamp()

        try:
            # Now ask the console for any new records since then. (Not all consoles
            # support this feature).
            for record in self.engine.console.genArchiveRecords(lastgood_ts):
                self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=record, origin='hardware'))
        except weewx.HardwareError, e:
            syslog.syslog(syslog.LOG_ERR, "wxengine: Internal error detected. Catchup abandoned")
            syslog.syslog(syslog.LOG_ERR, "****      %s" % e)
        
    def _software_catchup(self):
        # Extract a record out of the old accumulator. 
        record = self.old_accumulator.getRecord()
        # Add the archive interval
        record['interval'] = self.archive_interval / 60
        # Send out an event with the new record:
        self.engine.dispatchEvent(weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=record, origin='software'))
    
    def _new_accumulator(self, timestamp):
        start_archive_ts = weeutil.weeutil.startOfInterval(timestamp,
                                                           self.archive_interval)
        end_archive_ts = start_archive_ts + self.archive_interval
        
        new_accumulator =  weewx.accum.WXAccum(weeutil.weeutil.TimeSpan(start_archive_ts, end_archive_ts))
        return new_accumulator
