#
#    Copyright (c) 2009-2017 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick <gjroderick@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes to support fixes or other bulk corrections of weewx data."""

from __future__ import with_statement

# standard python imports
import datetime
import sys
import syslog
import time

# weewx imports
import weedb
import weeutil.weeutil
import weewx.manager

from weeutil.weeutil import timestamp_to_string, startOfDay, tobool


# ============================================================================
#                             class DatabaseFix
# ============================================================================


class DatabaseFix(object):
    """Base class for fixing bulk data in the weewx database.

    Classes for applying different fixes the weewx database data should be
    derived from this class. Derived classes require:

        run() method:       The entry point to apply the fix.
        fix config dict:    Dictionary containing config data specific to
                            the fix. Minimum fields required are:

                            name.           The name of the fix. String.
    """

    def __init__(self, config_dict, fix_config_dict):
        """A generic initialisation."""

        # save our weewx config dict
        self.config_dict = config_dict
        # save our fix config dict
        self.fix_config_dict = fix_config_dict
        # get our name
        self.name = fix_config_dict['name']
        # is this a dry run
        self.dry_run = tobool(fix_config_dict.get('dry_run', True)) == True

    def run(self):
        raise NotImplementedError("Method 'run' not implemented")

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
                yield weeutil.weeutil.archiveDaySpan(_row[0], grace=0)
        finally:
            _cursor.close

    def first_summary_ts(self, obs_type):
        """Obtain the timestamp of the earliest daily summary entry for an
        observation type.

        Imput:
            obs_type: The observation type whose daily summary is to be checked.

        Returns:
            The timestamp of the earliest daily summary entry for obs_tpye
            observation. None is returned if no record culd be found.
        """

        _sql_str = "SELECT MIN(dateTime) FROM %s_day_%s" % (self.dbm.table_name,
                                                            obs_type)
        _row = self.dbm.getSql(_sql_str)
        if _row:
            return _row[0]
        return None

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
            syslog.syslog(syslog.LOG_DEBUG,
                          "databasefix: Performing vacuum of database '%s' (SQLite only)." % self.dbm.database_name)
            try:
                self.dbm.getSql('vacuum')
            except weedb.ProgrammingError:
                # Catch the error (usually) returned when we try to vacuum a
                # non-SQLite db
                syslog.syslog(syslog.LOG_DEBUG,
                              "databasefix: Vacuuming database '%s' did not complete, most likely because it is not an SQLite database." % (self.dbm.database_name, ))
                return
            except Exception, e:
                # log the error and re-raise it
                syslog.syslog(syslog.LOG_INFO,
                              "databasefix: Vacuuming database '%s' failed: %s" % (self.dbm.database_name,
                                                                                   e))
                raise
            # If we are here then we have successfully vacuumed, log it and return
            syslog.syslog(syslog.LOG_DEBUG,
                          "databasefix: Database '%s' vacuumed in %0.1f seconds." % (self.dbm.database_name,
                                                                                     (time.time() - t1)))

    @staticmethod
    def _progress(record, ts):
        """Utility function to show our progress while processing the fix.

            Override in derived class to provide a different progress display.
            To do nothing override with a pass statement.
        """

        print >>sys.stdout, "Fixing database record: %d; Timestamp: %s\r" % \
            (record, timestamp_to_string(ts)),
        sys.stdout.flush()


# ============================================================================
#                        class WindSpeedRecalculation
# ============================================================================


class WindSpeedRecalculation(DatabaseFix):
    """Class to recalculate windSpeed daily maximum value. To recalculate the
    windSpeed daily maximum values:

    1.  Create a dictionary of parameters required by the fix. The
    WindSpeedRecalculation class uses the following parameters as indicated:

        name:           Name of the fix, for the windSpeed recalculation fix
                        this is 'windSpeed Recalculation'. String. Mandatory.

        binding:        The binding of the database to be fixed. Default is
                        the binding specified in weewx.conf [StdArchive].
                        String, eg 'binding_name'. Optional.

        vacuum:         Whether to vacuum the database before applying the fix.
                        SQLite databases only. Boolean, default is False.
                        Optional.

        trans_days:     Number of days of data used in each database
                        transaction. Integer, default is 50. Optional.

        dry_run:        Process the fix as if it was being applied but do not
                        write to the database. Boolean, default is True.
                        Optional.

    2.  Create an WindSpeedRecalculation object passing it a weewx config dict
    and a fix config dict.

    3.  Call the resulting object's run() method to apply the fix.
    """

    def __init__(self, config_dict, fix_config_dict):
        """Initialise our WindSpeedRecalculation object."""

        # call our parents __init__
        super(WindSpeedRecalculation, self).__init__(config_dict, fix_config_dict)
        
        # log if a dry run
        if self.dry_run:
            syslog.syslog(syslog.LOG_INFO, "maxwindspeed: This is a dry run. Maximum windSpeed will be recalculated but not saved.")


        # Get the binding for the archive we are to use. If we received an
        # explicit binding then use that otherwise use the binding that
        # StdArchive uses.
        try:
            db_binding = fix_config_dict['binding']
        except KeyError:
            if 'StdArchive' in config_dict:
                db_binding = config_dict['StdArchive'].get('data_binding',
                                                           'wx_binding')
            else:
                db_binding = 'wx_binding'
        self.binding = db_binding
        # get a database manager object
        self.dbm = weewx.manager.open_manager_with_config(config_dict,
                                                          self.binding)
        syslog.syslog(syslog.LOG_DEBUG,
                      "maxwindspeed: Using database binding '%s', which is bound to database '%s'." % (self.binding,
                                                                                                          self.dbm.database_name))
        # number of days per db transaction, default to 50.
        self.trans_days = int(fix_config_dict.get('trans_days', 50))
        syslog.syslog(syslog.LOG_DEBUG,
                      "maxwindspeed: Database transactions will use %s days of data." % self.trans_days)
        # pre-fix vacuum flag
        self.vacuum = fix_config_dict.get('vacuum', False) == True
        if self.vacuum:
            syslog.syslog(syslog.LOG_DEBUG,
                          "maxwindspeed: Database '%s' will be vacuumed before fix is applied." % self.dbm.database_name)
        else:
            syslog.syslog(syslog.LOG_DEBUG,
                          "maxwindspeed: Database '%s' will not be vacuumed before fix is applied." % self.dbm.database_name)

    def run(self):
        """Main entry point for applying the windSpeed Calculation fix.

        Recalculating the windSpeed daily sumamry max field from archive data
        is idempotent so there is no need to check wheteher the fix has already
        been applied. Just go ahead and do it catching any exceptions we know
        may be raised.
        """

        # First do a vacuum if requested.
        self.do_vacuum()
        # apply the fix but be prepared to catch any exceptions
        try:
            self.do_fix()
        except weewx.ViolatedPrecondition, e:
            syslog.syslog(syslog.LOG_ERR,
                          "maxwindspeed: **** %s" % e)
            syslog.syslog(syslog.LOG_ERR,
                          "maxwindspeed: **** '%s' fix not applied." % self.name)
            # raise the error so our caller can deal with it if they want
            raise

    def do_fix(self):
        """Recalculate windSpeed daily sumamry max field from archive data.

        Step through each row in the windSpeed daily summary table and replace
        the max field with the max value for that day based on archive data.
        Database transactions are done in self.trans_days days at a time.
        """

        t1 = time.time()
        syslog.syslog(syslog.LOG_INFO, "maxwindspeed: Applying '%s' fix..." % self.name)
        # get the start and stop Gregorian day number
        start_ts = self.first_summary_ts('windSpeed')
        start_greg = weeutil.weeutil.toGregorianDay(start_ts)
        stop_greg = weeutil.weeutil.toGregorianDay(self.dbm.last_timestamp)
        # initialise a few things
        day = start_greg
        n_days = 0
        while day <= stop_greg:
            # get the start and stop timestamps for this tranche
            tr_start_ts = weeutil.weeutil.startOfGregorianDay(day)
            tr_stop_ts = weeutil.weeutil.startOfGregorianDay(day + self.trans_days - 1)
            # start the transaction
            with weedb.Transaction(self.dbm.connection) as _cursor:
                # iterate over the rows in the windSpeed daily summary table
                for day_span in self.genSummaryDaySpans(tr_start_ts,
                                                        tr_stop_ts,
                                                        'windSpeed'):
                    # get the days max windSpeed and the time it occurred from
                    # the archive
                    (day_max_ts, day_max) = self.get_archive_span_max(day_span,
                                                                      'windSpeed')
                    # now save the value and time in the applicable row in the
                    # windSpeed daily summary, but only if its not a dry run
                    if not self.dry_run:
                        self.write_max('windSpeed', day_span.start,
                                       day_max, day_max_ts)
                    # increment our days done counter
                    n_days += 1
                    # give the user some information on progress
                    if n_days % 50 == 0:
                        self._progress(n_days, day_span.start)
            # advance to the next tranche
            day += self.trans_days

        # we have finished, give the user some final information on progress,
        # mainly so the total tallies with the log
        self._progress(n_days, day_span.start)
        print
        tdiff = time.time() - t1
        # We are done so log and inform the user
        if self.dry_run:
            syslog.syslog(syslog.LOG_INFO,
                          "maxwindspeed: Maximum windSpeed would have been calculated for %s days in %0.2f seconds." % (n_days,
                                                                                                                        tdiff))
            syslog.syslog(syslog.LOG_INFO,
                          "maxwindspeed: This was a dry run. '%s' fix was not applied." % self.name)
        else:
            syslog.syslog(syslog.LOG_INFO,
                          "maxwindspeed: Successfully applied '%s' fix to %s days in %0.2f seconds." % (self.name,
                                                                                                        n_days,
                                                                                                        tdiff))

    def get_archive_span_max(self, span, obs):
        """Find the max value of an obs and its timestamp in a span based on
           archive data.

        Gets the max value of an observation and the timestamp at which it
        occurred from a TimeSpan of archive records. Raises a
        weewx.ViolatedPrecondition error if the max value of the observation
        field could not be determined.

        Input parameters:
            span: TimesSpan object of the period from which to determine
                  the interval value.
            obs:  The observation to be used.

        Returns:
            A tuple of the format:

                (timestamp, value)

            where:
                timestamp is the epoch timestamp when the max value occurred
                value is the max value of the observation over the time span

            If no observation field values are found then a
            weewx.ViolatedPrecondition error is raised.
        """

        select_str = "SELECT dateTime, %(obs_type)s FROM %(table_name)s "\
                        "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "\
                        "%(obs_type)s = (SELECT MAX(%(obs_type)s) FROM %(table_name)s "\
                        "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND "\
                        "%(obs_type)s IS NOT NULL"
        interpolate_dict = {'obs_type'       : obs,
                            'table_name'     : self.dbm.table_name,
                            'start'          : span.start,
                            'stop'           : span.stop}

        _row = self.dbm.getSql(select_str % interpolate_dict)
        if _row:
            try:
                return (_row[0], _row[1])
            except IndexError:
                _msg = "'%s' field not found in archive day %s." % (obs, span)
                raise weewx.ViolatedPrecondition(_msg)
        else:
            return (None, None)

    def write_max(self, obs, row_ts, value, when_ts, cursor=None):
        """Update the max and maxtime fields in an existing daily summary row.

        Updates the max and maxtime fields in a row in a daily summary table.

        Input parameters:
            obs:     The observation to be used. the daily sumamry updated will
                     be xxx_day_obs where xxx is the database archive table name.
            row_ts:  Timestamp of the row to be uodated.
            value:   The value to be saved in field max
            when_ts: The timestamp to be saved in field maxtime
            cursor:  Cursor object for the database connection being used.

        Returns:
            Nothing.
        """

        _cursor = cursor or self.dbm.connection.cursor()

        max_update_str = "UPDATE %s_day_%s SET %s=?,%s=? WHERE datetime=?" % (self.dbm.table_name,
                                                                              obs,
                                                                              'max',
                                                                              'maxtime')
        _cursor.execute(max_update_str, (value, when_ts, row_ts))
        if cursor is None:
            _cursor.close()

    @staticmethod
    def _progress(ndays, last_time):
        """Utility function to show our progress while processing the fix."""

        print >>sys.stdout, "Updating 'windSpeed' daily summary: %d; Timestamp: %s\r" % \
            (ndays, timestamp_to_string(last_time, format_str="%Y-%m-%d")),
        sys.stdout.flush()


# ============================================================================
#                          class IntervalWeighting
# ============================================================================


class IntervalWeighting(DatabaseFix):
    """Class to apply an interval based weight factor to the daily summaries.
    To apply the interval weight factor:

    1.  Create a dictionary of parameters required by the fix. The
    IntervalWeighting class uses the following parameters as indicated:

        name:           Name of the class defining the fix, for the interval
                        weighting fix this is 'Interval Weighting'. String.
                        Mandatory.

        binding:        The binding of the database to be fixed. Default is
                        the binding specified in weewx.conf [StdArchive].
                        String, eg 'binding_name'. Optional.

        vacuum:         Whether to vacuum the database before applying the fix.
                        SQLite databases only. Boolean, default is False.
                        Optional.

        trans_days:     Number of days to be fixed in each database
                        transaction. Integer, default is 50. Optional.

        dry_run:        Process the fix as if it was being applied but do not
                        write to the database. Boolean, default is True.
                        Optional.

    2.  Create an IntervalWeighting object passing it a weewx config dict and a
    fix config dict.

    3.  Call the resulting object's run() method to apply the fix.
    """

    def __init__(self, config_dict, fix_config_dict):
        """Initialise our IntervalWeighting object."""

        # call our parents __init__
        super(IntervalWeighting, self).__init__(config_dict, fix_config_dict)

        # Get the binding for the archive we are to use. If we received an
        # explicit binding then use that otherwise use the binding that
        # StdArchive uses.
        try:
            db_binding = fix_config_dict['binding']
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
        # Number of days per db transaction, default to 50.
        self.trans_days = int(fix_config_dict.get('trans_days', 50))
        # Pre-fix vacuum flag
        self.vacuum = fix_config_dict.get('vacuum', False) == True

    def run(self):
        """Main entry point for applying the interval weighting fix.

        Check archive records of unweighted days to see if each day of records
        has a unique interval value. If interval value is unique then vacuum
        the database if requested and finally apply the weighting. Catch any
        exceptions and raise as necessary. If any one day has multiple interval
        value then we cannot weight the daily summaries, instead rebuild the
        daily summaries.
        """

        # first do some logging about what we will do
        if self.dry_run:
            syslog.syslog(syslog.LOG_INFO, "intervalweighting: This is a dry run. Interval weighting will be applied but not saved.")

        syslog.syslog(syslog.LOG_INFO,
                      "intervalweighting: Using database binding '%s', which is bound to database '%s'." % (self.binding,
                                                                                                           self.dbm.database_name))
        syslog.syslog(syslog.LOG_DEBUG,
                      "intervalweighting: Database transactions will use %s days of data." % self.trans_days)
        if self.vacuum:
            syslog.syslog(syslog.LOG_DEBUG,
                          "intervalweighting: Database '%s' will be vacuumed before fix is applied." % self.dbm.database_name)
        # Check metadata 'Version' value, if its greater than 1.0 we are
        # already weighted
        _daily_summary_version = self.dbm._read_metadata('Version')
        if _daily_summary_version is None or _daily_summary_version < '2.0':
            # Get the ts of the (start of the) next day to weight; it's the day
            # after the ts of the last successfully weighted daily summary
            _last_patched_ts = self.dbm._read_metadata('lastWeightPatch')
            if _last_patched_ts:
                _next_day_to_patch_dt = datetime.datetime.fromtimestamp(int(_last_patched_ts)) + datetime.timedelta(days=1)
                _next_day_to_patch_ts = time.mktime(_next_day_to_patch_dt.timetuple())
            else:
                _next_day_to_patch_ts = None
            # Check to see if any days that need to be weighted have multiple
            # distinct interval values
            if self.unique_day_interval(_next_day_to_patch_ts):
                # We have a homogeneous intervals for each day so we can weight
                # the daily summaries.

                # First do a vacuum if requested.
                self.do_vacuum()

                # Now apply the weighting but be prepared to catch any
                # exceptions
                try:
                    self.do_fix(_next_day_to_patch_ts)
                    # If we arrive here the fix was applied, if this is not
                    # a dry run then set the 'Version' metadata field to
                    # indicate we have updated to version 2.0.
                    if not self.dry_run:
                        self.dbm._write_metadata('Version', '2.0')
                except weewx.ViolatedPrecondition, e:
                    syslog.syslog(syslog.LOG_INFO,
                                  "intervalweighting: **** %s" % e)
                    syslog.syslog(syslog.LOG_INFO,
                                  "intervalweighting: **** '%s' fix not applied." % self.name)
                    # raise the error so our caller can deal with it if they want
                    raise
            else:
                # At least one day that needs to be weighted has multiple
                # distinct interval values. We cannot apply the weighting by
                # manipulating the existing daily summaries so we will weight
                # by rebuilding the daily summaries. Rebuild is destructive so
                # only do it if this is not a dry run
                if not self.dry_run:
                    syslog.syslog(syslog.LOG_DEBUG,
                                  "intervalweighting: Multiple distinct 'interval' values found for at least one archive day.")
                    syslog.syslog(syslog.LOG_INFO,
                                  "intervalweighting: '%s' fix will be applied by dropping and backfilling daily summaries." % self.name)
                    self.dbm.drop_daily()
                    self.dbm.close()
                    # Reopen to force rebuilding of the schema
                    self.dbm = weewx.manager.open_manager_with_config(self.config_dict,
                                                                      self.binding,
                                                                      initialize=True)
                    # This will rebuild to a V2 daily summary
                    self.dbm.backfill_day_summary()
        else:
            # daily summaries are already weighted
            syslog.syslog(syslog.LOG_INFO,
                          "intervalweighting: '%s' fix has already been applied." % self.name)

    def do_fix(self, np_ts):
        """Apply the interval weighting fix to the daily summaries."""

        # do we need to weight? Only weight if next day to weight ts is None or
        # there are records in the archive from that day
        if np_ts is None or self.dbm.last_timestamp > np_ts :
            t1 = time.time()
            syslog.syslog(syslog.LOG_INFO, "intervalweighting: Applying '%s' fix..." % self.name)
            _days = 0
            # Get the earliest daily summary ts and the obs that it came from
            first_ts, obs = self.first_summary()
            # Get the start and stop ts for our first transaction days
            _tr_start_ts = np_ts if np_ts is not None else first_ts
            _tr_stop_dt = datetime.datetime.fromtimestamp(_tr_start_ts) + datetime.timedelta(days=self.trans_days)
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
                        # Weight the necessary accumulator stats, use a
                        # try..except in case something goes wrong
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
                        except Exception, e:
                            # log the exception and re-raise it
                            syslog.syslog(syslog.LOG_INFO,
                                          "intervalweighting: Interval weighting of '%s' daily summary "
                                          "for %s failed: %s" % (_day_key,
                                                                 timestamp_to_string(_day_span.start, format="%Y-%m-%d"),
                                                                 e))
                            raise
                        # Update the daily summary with the weighted accumulator
                        if not self.dry_run:
                            self.dbm._set_day_summary(_day_accum,
                                                      None,
                                                      _cursor)
                        _days += 1
                        # Save the ts of the weighted daily summary as the
                        # 'lastWeightPatch' value in the archive_day__metadata
                        # table
                        if not self.dry_run:
                            self.dbm._write_metadata('lastWeightPatch',
                                                     _day_span.start,
                                                     _cursor)
                        # Give the user some information on progress
                        if _days % 50 == 0:
                            self._progress(_days, _day_span.start)

                    # Setup our next tranche
                    # Have we reached the end, if so break to finish
                    if _tr_stop_ts >= startOfDay(self.dbm.last_timestamp):
                        break
                    # More to process so set our start and stop for the next
                    # transaction
                    _tr_start_dt = datetime.datetime.fromtimestamp(_tr_stop_ts) + datetime.timedelta(days=1)
                    _tr_start_ts = time.mktime(_tr_start_dt.timetuple())
                    _tr_stop_dt = datetime.datetime.fromtimestamp(_tr_start_ts) + datetime.timedelta(days=self.trans_days)
                    _tr_stop_ts = time.mktime(_tr_stop_dt.timetuple())
                    _tr_stop_ts = min(self.dbm.last_timestamp, _tr_stop_ts)

            # We have finished. Get rid of the no longer needed lastWeightPatch
            self.dbm.getSql("DELETE FROM %s_day__metadata WHERE name=?" % self.dbm.table_name, ('lastWeightPatch',))
             
            # Give the user some final information on progress,
            # mainly so the total tallies with the log
            self._progress(_days, _day_span.start)
            print
            tdiff = time.time() - t1
            # We are done so log and inform the user
            if self.dry_run:
                syslog.syslog(syslog.LOG_INFO, 
                              "intervalweighting: %s days would have been weighted in %0.2f seconds." % (_days,
                                                                                                         tdiff))
                syslog.syslog(syslog.LOG_INFO, "intervalweighting: This was a dry run. '%s' fix was not applied." % self.name)
            else:
                syslog.syslog(syslog.LOG_INFO, 
                              "intervalweighting: Successfully applied '%s' fix to %s days in %0.2f seconds." % (self.name, 
                                                                                                                 _days, 
                                                                                                                 tdiff))
        else:
            # we didn't need to weight so inform the user
            syslog.syslog(syslog.LOG_INFO, 
                                 "intervalweighting: '%s' fix has already been applied. Fix not applied." % self.name)

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

        _row = self.dbm.getSql("SELECT `interval` FROM %s "
                        "WHERE dateTime > ? AND dateTime <= ?;" % self.dbm.table_name, span)
        try:
            return _row[0]
        except IndexError:
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
        syslog.syslog(syslog.LOG_DEBUG,
                      "intervalweighting: Checking table '%s' for multiple "
                      "'interval' values per day..." % self.dbm.table_name)
        start_ts = timestamp if timestamp else self.dbm.first_timestamp
        _days = 0
        _result = True
        for _day_span in weeutil.weeutil.genDaySpans(start_ts,
                                                     self.dbm.last_timestamp):
            _row = self.dbm.getSql("SELECT MIN(`interval`),MAX(`interval`) FROM %s "
                                   "WHERE dateTime > ? AND dateTime <= ?;" % self.dbm.table_name, _day_span)
            try:
                # If MIN and MAX are the same then we only have 1 distinct
                # value. If the query returns nothing then that is fine too,
                # probably no archive data for that day.
                _result = _row[0] == _row[1] if _row else True
            except IndexError:
                # Something is seriously amiss, raise an error
                raise weewx.ViolatedPrecondition("Invalid 'interval' data detected in archive day %s." % (_day_span, ))
            _days += 1
            if not _result:
                break
        if _result:
            syslog.syslog(syslog.LOG_DEBUG,
                          "intervalweighting: Successfully checked %s days "
                          "for multiple 'interval' values in %0.2f seconds." % (_days, (time.time() - t1)))
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

            (None, None) is returned if no dateTime values were found.
        """

        _res = (None, None)
        for _key in self.dbm.daykeys:
            _ts = self.first_summary_ts(_key)
            if _ts:
                _res = (weeutil.weeutil.min_with_none((_res[0], _ts)), _key)
        return _res

    @staticmethod
    def _progress(ndays, last_time):
        """Utility function to show our progress while processing the fix."""

        print >>sys.stdout, "Weighting daily summary: %d; Timestamp: %s\r" % \
            (ndays, timestamp_to_string(last_time, format_str="%Y-%m-%d")),
        sys.stdout.flush()
