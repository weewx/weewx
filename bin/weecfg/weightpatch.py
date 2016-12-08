#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
""" Classes and functions to patch the weewx daily summaries with an interval
    based weight factor.

    To apply the patch:

    1.  Create a dictionary of parameters required by the patch. The
    WeightedSumPatch uses the following parameters as indicated:

        patch:          Name of the class defining the patch, for the weighted
                        sum patch this is 'WeightedSumPatch'. String.
                        Mandatory.

        binding:        The binding of the database to be patched. Default is
                        the binding specified in [StdArchive] or weewx.conf will
                        be used. String, eg 'binding_name'. Optional.

        vacuum:         Whether to vacuum the database before patching. SQLite
                        databases only. Boolean, default is False. Optional.

        trans_days:     Number of days to be patched in each database
                        transaction. Integer, default is 50. Optional.

        verbose:        Provides additional log entries during the patch.
                        Boolean, default is False. Optional.

        dry_run:        Process the patch as if it was being applied but do not
                        write to the database. Boolean, default is True. Optional.

        log_results:    Log to the same log used by weewx. Boolean, default is
                        True. optional.

        required_weewx: Minimum weewx version required to apply this patch.
                        String, eg '3.6.0'. Mandatory.

    2.  Call the patch.Patch factory method patchFactory() passing it a weewx
    config dict, a patch config dict and a patch.PatchLog object.

    3.  Call the resulting objects run() method to apply the patch.

"""
from __future__ import with_statement

# standard python imports
import datetime
import sys
import syslog
import time

from datetime import datetime as dt

# weewx imports
import weecfg.patch
import weecfg
import weedb
import weewx

from weeutil.weeutil import archiveDaySpan, genDaySpans, timestamp_to_string, startOfDay, min_with_none


# ============================================================================
#                         WeightedSumPatch Error Classes
# ============================================================================


class WeightedSumPatchAccumError(IOError):
    """Base class of exceptions thrown when encountering an error with an
       accumulator.
    """

class WeightedSumPatchDbError(IOError):
    """Base class of exceptions thrown when encountering an error accessing the
       database.
    """


# ============================================================================
#                                 class WeightedSumPatch
# ============================================================================

class WeightedSumPatch(weecfg.patch.DatabasePatch):
    """Class to patch daily summaries with an interval based weight factor."""

    def __init__(self, config_dict, patch_config_dict, log):
        """Initialise our WeightedSumPatch object."""

        # call our parents __init__
        super(WeightedSumPatch, self).__init__(config_dict,
                                               patch_config_dict,
                                               log)
        self.plog.printlog(syslog.LOG_INFO,
                          "Preparing '%s' patch..." % self.name)

        # Get the binding for the archive we are to use. If we received an
        # explicit binding then use that otherwise use the binding that
        # StdArchive uses.
        try:
            db_binding = patch_config_dict['binding']
        except KeyError:
            if 'StdArchive' in config_dict:
                db_binding = config_dict['StdArchive'].get('data_binding',
                                                           'wx_binding')
            else:
                db_binding = 'wx_binding'
        self.binding = db_binding
        # Get a database manager object
        self.dbm = weewx.manager.open_manager_with_config(config_dict,
                                                          self.binding)
        _msg = "Using database binding '%s', which is bound to database '%s'" % (self.binding,
                                                                                 self.dbm.database_name)
        self.plog.printlog(syslog.LOG_INFO, _msg)
        # Number of days per db transaction, default to 50. Wrap in a try in 
        # case we get a None.
        try:
            self.trans_days = int(patch_config_dict.get('trans_days', 50))
        except TypeError:
            self.trans_days = 50
        _msg = "Database transactions will use %s days of data." % self.trans_days
        self.plog.logonly(syslog.LOG_DEBUG, _msg)
        # Pre-patch vacuum flag
        self.vacuum = patch_config_dict.get('vacuum', False) == True
        if self.vacuum:
            _msg = "Database '%s' will be vacuumed before patch is applied." % self.dbm.database_name
        else:
            _msg = "Database '%s' will not be vacuumed before patch is applied." % self.dbm.database_name
        self.plog.logonly(syslog.LOG_DEBUG, _msg)

    def run(self):
        """Main entry point for patching the daily summaries.

        Check archive records of unpatched days to see if each day of records
        has a unique interval value. If interval value is unique then vacuum
        the database if requested and finally apply the patch. Catch any
        exceptions and raise as necessary. If any one day has multiple interval
        value then we cannot patch the daily summaries, instead drop then
        backfill the daily summaries.
        """

        # Check metadata dailySummaryVersion value, if its 1 or greater than
        # we are already patched
        _daily_summary_version = self.read_metadata('dailySummaryVersion')
        if _daily_summary_version is None or _daily_summary_version < 1:
            # Get the ts of the (start of the) next day to patch; it's the day
            # after the ts of the last successfully patched daily summary
            _last_patched_ts = self.read_metadata('lastSummaryPatched')
            if _last_patched_ts:
                _next_day_to_patch_dt = dt.fromtimestamp(_last_patched_ts) + datetime.timedelta(days=1)
                _next_day_to_patch_ts = time.mktime(_next_day_to_patch_dt.timetuple())
            else:
                _next_day_to_patch_ts = None
            # Check to see if any days that need to be patched have multiple
            # distinct interval values
            if self.unique_day_interval(_next_day_to_patch_ts):
                # We have a homogeneous intervals for each day so we can patch
                # the daily summaries.

                # First do a vacuum if requested. If we can't vacuum that in
                # itself is not reason to abort, just log the failure and
                # continue.
                try:
                    self.do_vacuum()
                except WeightedSumPatchDbError, e:
                    self.plog.printlog(syslog.LOG_INFO, "**** %s" % e)

                # Now apply the patch but be prepared to catch any exceptions
                try:
                    self.do_patch(_next_day_to_patch_ts)
                    # If we arrive here the patch was applied, if this is not
                    # a dry run then set the dailySummaryVersion field in the
                    # daily summary meta data to indicate we have patched to
                    # version 1.
                    if not self.dry_run:
                        self.write_metadata('dailySummaryVersion', 1)
                except WeightedSumPatchAccumError, e:
                    self.plog.printlog(syslog.LOG_INFO, "**** Accumulator error.")
                    self.plog.printlog(syslog.LOG_INFO, "**** %s" % e)
                    # raise the error so our caller can deal with it if they want
                    raise
                except weewx.ViolatedPrecondition, e:
                    self.plog.printlog(syslog.LOG_INFO, "**** %s" % e)
                    self.plog.printlog(syslog.LOG_INFO, "**** '%s' patch not applied." % self.name)
                    # raise the error so our caller can deal with it if they want
                    raise
            else:
                # At least one day that needs to be patched has multiple
                # distinct interval values. We cannot apply the patch by
                # manipulating the existing daily summaries so we will patch by
                # dropping the daily summaries and then rebuilding them.
                # Drop/backfill is destructive so only do it if this is not a
                # dry run
                if not self.dry_run:
                    _msg = "Multiple distinct 'interval' values found for at least one archive day."
                    self.plog.printlog(syslog.LOG_INFO, _msg)
                    _msg = "'%s' patch will be applied by dropping and backfilling daily summaries." % self.name
                    self.plog.printlog(syslog.LOG_INFO, _msg)
                    self.dbm.drop_daily()
                    self.dbm = weewx.manager.open_manager_with_config(self.config_dict, 
                                                                      self.binding, 
                                                                      initialize=True)
                    self.dbm.backfill_day_summary()
                    print
                    # Set the dailySummaryVersion field in the daily summary
                    # meta data to indicate we have patched to version 1.
                    self.write_metadata('dailySummaryVersion', 1)
                    _msg = "Successfully applied '%s' patch." % self.name
                    self.plog.printlog(syslog.LOG_INFO, _msg)
        else:
            # daily summaries are already patched
            self.plog.printlog(syslog.LOG_INFO, "'%s' patch has already been applied." % self.name)

    def do_patch(self, np_ts):
        """Patch the daily summaries using interval as weight."""

        # do we need to patch? Only patch if next day to patch ts is None or
        # there are records in the archive from that day
        if np_ts is None or self.dbm.last_timestamp > np_ts :
            t1 = time.time()
            self.plog.printlog(syslog.LOG_INFO,
                              "Applying '%s' patch..." % self.name)
            _days = 0
            # Get the earliest daily summary ts and the obs that it came from
            first_ts, obs = self.first_summary()
            # Get the start and stop ts for our first transaction days
            _tr_start_ts = np_ts if np_ts is not None else first_ts
            _tr_stop_dt = dt.fromtimestamp(_tr_start_ts) + datetime.timedelta(days=self.trans_days)
            _tr_stop_ts = time.mktime(_tr_stop_dt.timetuple())
            _tr_stop_ts = min(startOfDay(self.dbm.last_timestamp), _tr_stop_ts)

            while True:
                with weedb.Transaction(self.dbm.connection) as _cursor:
                    for _day_span in self.genSummaryDaySpans(_tr_start_ts,
                                                             _tr_stop_ts,
                                                             obs):
                        # Get the weight to be applied for the day
                        _weight = self.get_interval(_day_span) * 60
                        # Get the current day stats in an accumulator
                        _day_accum = self.dbm._get_day_summary(_day_span.start)
                        # Set the unit system for the accumulator
                        _day_accum.unit_system = self.dbm.std_unit_system
                        # Patch the necessary accumulator stats, use a try..except
                        # in case something goes wrong
                        try:
                            for _day_key in self.dbm.daykeys:
                                _day_accum[_day_key].wsum *= _weight
                                _day_accum[_day_key].sumtime *= _weight
                                # Do we have a vecstats accumulator?
                                if hasattr(_day_accum[_day_key], 'wsquaresum'):
                                    # Yes, so update the weighted vector stats
                                    _day_accum[_day_key].wsquaresum *= _weight
                                    _day_accum[_day_key].xsum *= _weight
                                    _day_accum[_day_key].ysum *= _weight
                                    _day_accum[_day_key].dirsumtime *= _weight
                        except:
                            _msg = "'%s' daily summary for %s could not be patched." % (_day_key,
                                                                                       time.strftime("%Y-%m-%d",
                                                                                                     time.localtime(_day_span.start)))
                            raise WeightedSumPatchAccumError(_msg)
                        # Update the daily summary with the patched accumulator
                        if not self.dry_run:
                            self.dbm._set_day_summary(_day_accum,
                                                      _day_span.stop,
                                                      _cursor)
                        _days += 1
                        # Save the ts of the patched daily summary as the
                        # 'lastSummaryPatched' value in the archive_day__metadata
                        # table
                        if not self.dry_run:
                            self.write_metadata('lastSummaryPatched',
                                                _day_span.start)
                        # Give the user some information on progress
                        if _days % 50 == 0:
                            self.progress(_days, _day_span.start)

                    # Setup our next tranche
                    # Have we reached the end, if so break to finish
                    if _tr_stop_ts >= startOfDay(self.dbm.last_timestamp):
                        break
                    # More to process so set our start and stop for the next
                    # transaction
                    _tr_start_dt = dt.fromtimestamp(_tr_stop_ts) + datetime.timedelta(days=1)
                    _tr_start_ts = time.mktime(_tr_start_dt.timetuple())
                    _tr_stop_dt = dt.fromtimestamp(_tr_start_ts) + datetime.timedelta(days=self.trans_days)
                    _tr_stop_ts = time.mktime(_tr_stop_dt.timetuple())
                    _tr_stop_ts = min(self.dbm.last_timestamp, _tr_stop_ts)

            print
            # We are done so log and inform the user
            if self.dry_run:
                _msg = "%s daily summaries would have been patched in %0.1f seconds." % (_days,
                                                                         (time.time() - t1))
                _msg1 = "This was a dry run. '%s' patch was not applied." % self.name
            else:
                _msg = "%s daily summaries patched in %0.1f seconds." % (_days,
                                                                         (time.time() - t1))
                _msg1 = "Successfully applied '%s' patch." % self.name
            self.plog.printlog(syslog.LOG_INFO, _msg)
            self.plog.printlog(syslog.LOG_INFO, _msg1)
        else:
            # we didn't need to patch so inform the user
            _msg = "'%s' patch has already been applied. Patch not applied." % self.name
            self.plog.printlog(syslog.LOG_INFO, _msg)

    def genSummaryDaySpans(self, start_ts, stop_ts, obs='outTemp'):
        """Generator to generate a sequence of daily summary day TimeSpans.

        Given an observation that has a daily summary table, generate a
        sequence of TimeSpan objects for each row in the daily summary table.
        In this way the generated sequence includes only rows included in the
        daily summary rather than any 'missing' rows.

        Input parameters:
            start_ts: Include daily summary rows with a dateTime >= start_ts
            stop_ts:  Include daily summary rows with a dateTime <>= start_ts
            obs:      The weewx observation whose daily summary table is to be
                      used as the source of the TimeSpan objects

        Returns:
            A sequence of day TimeSpan objects
        """

        _sql = "SELECT dateTime FROM %s_day_%s "\
                   "WHERE dateTime >= ? AND dateTime <= ?" % (self.dbm.table_name,
                                                              obs)
        _cursor = self.dbm.connection.cursor()
        try:
            for _row in _cursor.execute(_sql, (start_ts, stop_ts)):
                yield archiveDaySpan(_row[0], grace=0)
        finally:
            _cursor.close

    def get_interval(self, span):
        """Return the interval field value used in a span.

        Gets the interval field value from a TimeSpan of records.  Raises a
        weewx.ViolatedPrecondition error if the interval field value could not
        be determined.

        Input parameters:
            span: TimesSpan object of the period from which to determine
                  the interval value.

        Returns:
            The interval field value in minutes, if no interval field values
            are found then a weewx.ViolatedPrecondition error is raised.
        """

        interpolate_dict = {'start' : span.start,
                            'stop'  : span.stop}
        _sql_stmt = "SELECT `interval` FROM archive "\
                        "WHERE dateTime > %(start)s AND dateTime <= %(stop)s;"
        _row = self.dbm.getSql(_sql_stmt % interpolate_dict)
        try:
            return _row[0]
        except:
            _msg = "'interval' field not found in archive day %s." % (span, )
            raise weewx.ViolatedPrecondition(_msg)

    def unique_day_interval(self, timestamp):
        """Check a weewx archive for homogenious interval values for each day.

        An 'archive day' of records includes all records whose dateTime value
        is greater than midnight at the start of the day and less than or equal
        to midnight at the end of the day. Each 'archive day' of records is
        checked for multiple distinct interval values.

        Input parameters:
            timestamp:  check archive days containing timestamp and later. If
                        None then all archive days are checked.

        Returns:
            True if all checked archive days have a single distinct interval
            value. Otherwise returns False (ie if more than one distinct
            interval value is found in any one archive day).
        """

        t1 = time.time()
        _msg = "Checking table '%s' for multiple 'interval' values per day..." % self.dbm.table_name
        self.plog.printlog(syslog.LOG_INFO, _msg)
        start_ts = timestamp if timestamp else self.dbm.first_timestamp
        _days = 0
        _result = True
        for _day_span in genDaySpans(start_ts, self.dbm.last_timestamp):
            interpolate_dict = {'start' : _day_span.start,
                                'stop'  : _day_span.stop}
            _sql_stmt = "SELECT MIN(`interval`),MAX(`interval`) FROM archive "\
                            "WHERE dateTime > %(start)s AND dateTime <= %(stop)s;"
            _row = self.dbm.getSql(_sql_stmt % interpolate_dict)
            try:
                # If MIN and MAX are the same then we only have 1 distinct
                # value. If the query returns nothing then that is fine too,
                # probably no archive data for that day.
                _result = _row[0] == _row[1] if _row else True
            except:
                # Something is seriously amiss, raise an error
                raise weewx.ViolatedPrecondition("Invalid 'interval' data detected in archive day %s." % (_day_span, ))
            _days += 1
            if not _result:
                break
        if _result:
            _msg = "Successfully checked %s days for multiple 'interval' values in %0.2f seconds." % (_days,
                                                                                                      (time.time() - t1))
            self.plog.printlog(syslog.LOG_INFO, _msg)
        return _result

    def first_summary(self):
        """Obtain the timestamp and observation name of the earliest daily
           summary entry.

        It is possible the earliest dateTime value in the daily summary tables
        will be different from table to table. To find the earliest dateTime
        value we loop through each daily summary table finding the earliest
        dateTime value for each table and then take the earliest value of these.

        Returns:
            A tuple of the form (timestamp, observation)

            where:

                timestamp:   The earliest timestamp across all daily summary
                             tables
                observation: The observation whose daily summary table has the
                             earliest timestamp

            (None, None) is returned if no dateTime values where found.
        """

        _res = (None, None)
        for _key in self.dbm.daykeys:
            _sql_str = "SELECT MIN(dateTime) FROM %s_day_%s" % (self.dbm.table_name,
                                                                _key)
            _row = self.dbm.getSql(_sql_str)
            if _row:
                _res = (min_with_none((_res[0], _row[0])), _key)
        return _res

    def read_metadata(self, metadata):
        """Obtain a metadata value from the archive_day__metadata table.

        Returns:
            Value of the metadata field. Returns None if no value was found.
        """

        select_patch_str = """SELECT value FROM %s_day__metadata """\
                              """WHERE name = '%s';"""
        _row = self.dbm.getSql(select_patch_str % (self.dbm.table_name,
                                                   metadata))
        return int(_row[0]) if _row else None

    def write_metadata(self, metadata, value):
        """Write a value to a metadata field in the archive_day__metadata table.

        Input parameters:
            metadata: The name of the metadata field to be written to.
            value:    The value to be written to the metadata field.
        """

        meta_replace_str = """REPLACE INTO %s_day__metadata VALUES(?, ?)"""
        _row = self.dbm.getSql(meta_replace_str % self.dbm.table_name,
                               (metadata, value))

    def do_vacuum(self):
        """Vacuum the database.

        Vacuuming an SQLite database compacts the database file and will also
        result in a speed increase for some transactions. Vacuuming also helps
        to prevent an SQLite database file from continually growing in size
        even though we prune records from the database. Vacuum will only work
        on SQLite databases. It should be OK to run this on a MySQL database,
        it will fail but we catch the error and continue.
        """

        if self.vacuum:
            t1 = time.time()
            _msg = "Performing vacuum of database '%s' (SQLite only)." % self.dbm.database_name
            self.plog.printlog(syslog.LOG_INFO, _msg)
            try:
                self.dbm.getSql('vacuum')
            except weedb.ProgrammingError:
                # Catch the error (usually) returned when we try to vacuum a non-SQLite db
                _msg = "Vacuuming database '%s' did not complete, most likely because it is not an SQLite database." % (self.dbm.database_name, )
                self.plog.printlog(syslog.LOG_INFO, _msg)
                return
            except Exception, e:
                # Raise an error should we have any other issue
                _msg = "Vacuuming database '%s' failed: %s" % (self.dbm.database_name, e)
                raise WeightedSumPatchDbError(_msg)
            # If we are here then we have successfully vacuumed, log it and return
            _msg = "Database '%s' vacuumed in %0.1f seconds." % (self.dbm.database_name,
                                                                 (time.time() - t1))
            self.plog.printlog(syslog.LOG_INFO, _msg)
        else:
            self.plog.logonly(syslog.LOG_DEBUG, "Vacuum not requested.")

    @staticmethod
    def progress(ndays, last_time):
        """Utility function to show our progress while patching."""

        print >>sys.stdout, "Days processed: %d; Timestamp: %s\r" % \
            (ndays, timestamp_to_string(last_time)),
        sys.stdout.flush()
