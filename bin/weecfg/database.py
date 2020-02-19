#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick <gjroderick@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes to support fixes or other bulk corrections of weewx data."""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

# standard python imports
import datetime
import logging
import sys
import time

# weewx imports
import weedb
import weeutil.weeutil
import weewx.manager
import weewx.units
import weewx.wxservices
from weeutil.weeutil import timestamp_to_string, startOfDay, to_bool, option_as_list

log = logging.getLogger(__name__)

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
        self.dry_run = to_bool(fix_config_dict.get('dry_run', True))
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

        _sql = "SELECT dateTime FROM %s_day_%s " \
               " WHERE dateTime >= ? AND dateTime <= ?" % (self.dbm.table_name, obs)

        _cursor = self.dbm.connection.cursor()
        try:
            for _row in _cursor.execute(_sql, (start_ts, stop_ts)):
                yield weeutil.weeutil.archiveDaySpan(_row[0], grace=0)
        finally:
            _cursor.close()

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

    @staticmethod
    def _progress(record, ts):
        """Utility function to show our progress while processing the fix.

            Override in derived class to provide a different progress display.
            To do nothing override with a pass statement.
        """

        _msg = "Fixing database record: %d; Timestamp: %s\r" % (record, timestamp_to_string(ts))
        print(_msg, end='', file=sys.stdout)
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
            log.info("maxwindspeed: This is a dry run. "
                     "Maximum windSpeed will be recalculated but not saved.")

        log.debug("maxwindspeed: Using database binding '%s', "
                  "which is bound to database '%s'." %
                  (self.binding, self.dbm.database_name))
        # number of days per db transaction, default to 50.
        self.trans_days = int(fix_config_dict.get('trans_days', 50))
        log.debug("maxwindspeed: Database transactions will use %s days of data." % self.trans_days)

    def run(self):
        """Main entry point for applying the windSpeed Calculation fix.

        Recalculating the windSpeed daily summary max field from archive data
        is idempotent so there is no need to check whether the fix has already
        been applied. Just go ahead and do it catching any exceptions we know
        may be raised.
        """

        # apply the fix but be prepared to catch any exceptions
        try:
            self.do_fix()
        except weedb.NoTableError:
            raise
        except weewx.ViolatedPrecondition as e:
            log.error("maxwindspeed: %s not applied: %s" % (self.name, e))
            # raise the error so caller can deal with it if they want
            raise

    def do_fix(self):
        """Recalculate windSpeed daily summary max field from archive data.

        Step through each row in the windSpeed daily summary table and replace
        the max field with the max value for that day based on archive data.
        Database transactions are done in self.trans_days days at a time.
        """

        t1 = time.time()
        log.info("maxwindspeed: Applying %s..." % self.name)
        # get the start and stop Gregorian day number
        start_ts = self.first_summary_ts('windSpeed')
        start_greg = weeutil.weeutil.toGregorianDay(start_ts)
        stop_greg = weeutil.weeutil.toGregorianDay(self.dbm.last_timestamp)
        # initialise a few things
        day = start_greg
        n_days = 0
        last_start = None
        while day <= stop_greg:
            # get the start and stop timestamps for this tranche
            tr_start_ts = weeutil.weeutil.startOfGregorianDay(day)
            tr_stop_ts = weeutil.weeutil.startOfGregorianDay(day + self.trans_days - 1)
            # start the transaction
            with weedb.Transaction(self.dbm.connection) as _cursor:
                # iterate over the rows in the windSpeed daily summary table
                for day_span in self.genSummaryDaySpans(tr_start_ts, tr_stop_ts, 'windSpeed'):
                    # get the days max windSpeed and the time it occurred from
                    # the archive
                    (day_max_ts, day_max) = self.get_archive_span_max(day_span, 'windSpeed')
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
                    last_start = day_span.start
            # advance to the next tranche
            day += self.trans_days

        # we have finished, give the user some final information on progress,
        # mainly so the total tallies with the log
        self._progress(n_days, last_start)
        print(file=sys.stdout)
        tdiff = time.time() - t1
        # We are done so log and inform the user
        log.info("maxwindspeed: Maximum windSpeed calculated "
                 "for %s days in %0.2f seconds." % (n_days, tdiff))
        if self.dry_run:
            log.info("maxwindspeed: This was a dry run. %s was not applied." % self.name)

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

        select_str = "SELECT dateTime, %(obs_type)s FROM %(table_name)s " \
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND " \
                     "%(obs_type)s = (SELECT MAX(%(obs_type)s) FROM %(table_name)s " \
                     "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND " \
                     "%(obs_type)s IS NOT NULL"
        interpolate_dict = {'obs_type': obs,
                            'table_name': self.dbm.table_name,
                            'start': span.start,
                            'stop': span.stop}

        _row = self.dbm.getSql(select_str % interpolate_dict)
        if _row:
            try:
                return _row[0], _row[1]
            except IndexError:
                _msg = "'%s' field not found in archive day %s." % (obs, span)
                raise weewx.ViolatedPrecondition(_msg)
        else:
            return None, None

    def write_max(self, obs, row_ts, value, when_ts, cursor=None):
        """Update the max and maxtime fields in an existing daily summary row.

        Updates the max and maxtime fields in a row in a daily summary table.

        Input parameters:
            obs:     The observation to be used. the daily summary updated will
                     be xxx_day_obs where xxx is the database archive table name.
            row_ts:  Timestamp of the row to be updated.
            value:   The value to be saved in field max
            when_ts: The timestamp to be saved in field maxtime
            cursor:  Cursor object for the database connection being used.

        Returns:
            Nothing.
        """

        _cursor = cursor or self.dbm.connection.cursor()

        max_update_str = "UPDATE %s_day_%s SET %s=?,%s=? " \
                         "WHERE datetime=?" % (self.dbm.table_name, obs, 'max', 'maxtime')
        _cursor.execute(max_update_str, (value, when_ts, row_ts))
        if cursor is None:
            _cursor.close()

    @staticmethod
    def _progress(ndays, last_time):
        """Utility function to show our progress while processing the fix."""

        _msg = "Updating 'windSpeed' daily summary: %d; " \
               "Timestamp: %s\r" % (ndays, timestamp_to_string(last_time, format_str="%Y-%m-%d"))
        print(_msg, end='', file=sys.stdout)
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

        # Number of days per db transaction, default to 50.
        self.trans_days = int(fix_config_dict.get('trans_days', 50))

    def run(self):
        """Main entry point for applying the interval weighting fix.

        Check archive records of unweighted days to see if each day of records
        has a unique interval value. If interval value is unique then apply the
        weighting. Catch any exceptions and raise as necessary. If any one day
        has multiple interval value then we cannot weight the daily summaries,
        instead rebuild the daily summaries.
        """

        # first do some logging about what we will do
        if self.dry_run:
            log.info("intervalweighting: This is a dry run. "
                     "Interval weighting will be applied but not saved.")

        log.info("intervalweighting: Using database binding '%s', "
                 "which is bound to database '%s'." %
                 (self.binding, self.dbm.database_name))
        log.debug("intervalweighting: Database transactions "
                  "will use %s days of data." % self.trans_days)
        # Check metadata 'Version' value, if its greater than 1.0 we are
        # already weighted
        _daily_summary_version = self.dbm._read_metadata('Version')
        if _daily_summary_version is None or _daily_summary_version < '2.0':
            # Get the ts of the (start of the) next day to weight; it's the day
            # after the ts of the last successfully weighted daily summary
            _last_patched_ts = self.dbm._read_metadata('lastWeightPatch')
            if _last_patched_ts:
                _next_day_to_patch_dt = datetime.datetime.fromtimestamp(int(_last_patched_ts)) \
                                        + datetime.timedelta(days=1)
                _next_day_to_patch_ts = time.mktime(_next_day_to_patch_dt.timetuple())
            else:
                _next_day_to_patch_ts = None
            # Check to see if any days that need to be weighted have multiple
            # distinct interval values
            if self.unique_day_interval(_next_day_to_patch_ts):
                # We have a homogeneous intervals for each day so we can weight
                # the daily summaries.

                # Now apply the weighting but be prepared to catch any
                # exceptions
                try:
                    self.do_fix(_next_day_to_patch_ts)
                    # If we arrive here the fix was applied, if this is not
                    # a dry run then set the 'Version' metadata field to
                    # indicate we have updated to version 2.0.
                    if not self.dry_run:
                        with weedb.Transaction(self.dbm.connection) as _cursor:
                            self.dbm._write_metadata('Version', '2.0', _cursor)
                except weewx.ViolatedPrecondition as e:
                    log.info("intervalweighting: %s not applied: %s"
                             % (self.name, e))
                    # raise the error so caller can deal with it if they want
                    raise
            else:
                # At least one day that needs to be weighted has multiple
                # distinct interval values. We cannot apply the weighting by
                # manipulating the existing daily summaries so we will weight
                # by rebuilding the daily summaries. Rebuild is destructive so
                # only do it if this is not a dry run
                if not self.dry_run:
                    log.debug("intervalweighting: Multiple distinct 'interval' "
                              "values found for at least one archive day.")
                    log.info("intervalweighting: %s will be applied by dropping "
                             "and rebuilding daily summaries." % self.name)
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
            log.info("intervalweighting: %s has already been applied." % self.name)

    def do_fix(self, np_ts):
        """Apply the interval weighting fix to the daily summaries."""

        # do we need to weight? Only weight if next day to weight ts is None or
        # there are records in the archive from that day
        if np_ts is None or self.dbm.last_timestamp > np_ts:
            t1 = time.time()
            log.info("intervalweighting: Applying %s..." % self.name)
            _days = 0
            # Get the earliest daily summary ts and the obs that it came from
            first_ts, obs = self.first_summary()
            # Get the start and stop ts for our first transaction days
            _tr_start_ts = np_ts if np_ts is not None else first_ts
            _tr_stop_dt = datetime.datetime.fromtimestamp(_tr_start_ts) \
                + datetime.timedelta(days=self.trans_days)
            _tr_stop_ts = time.mktime(_tr_stop_dt.timetuple())
            _tr_stop_ts = min(startOfDay(self.dbm.last_timestamp), _tr_stop_ts)
            last_start = None
            while True:
                with weedb.Transaction(self.dbm.connection) as _cursor:
                    for _day_span in self.genSummaryDaySpans(_tr_start_ts, _tr_stop_ts, obs):
                        # Get the weight to be applied for the day
                        _weight = self.get_interval(_day_span) * 60
                        # Get the current day stats in an accumulator
                        _day_accum = self.dbm._get_day_summary(_day_span.start)
                        # Set the unit system for the accumulator
                        _day_accum.unit_system = self.dbm.std_unit_system
                        # Weight the necessary accumulator stats, use a
                        # try..except in case something goes wrong
                        last_key = None
                        try:
                            for _day_key in self.dbm.daykeys:
                                last_key = _day_key
                                _day_accum[_day_key].wsum *= _weight
                                _day_accum[_day_key].sumtime *= _weight
                                # Do we have a vecstats accumulator?
                                if hasattr(_day_accum[_day_key], 'wsquaresum'):
                                    # Yes, so update the weighted vector stats
                                    _day_accum[_day_key].wsquaresum *= _weight
                                    _day_accum[_day_key].xsum *= _weight
                                    _day_accum[_day_key].ysum *= _weight
                                    _day_accum[_day_key].dirsumtime *= _weight
                        except Exception as e:
                            # log the exception and re-raise it
                            log.info("intervalweighting: Interval weighting of '%s' daily summary "
                                     "for %s failed: %s"
                                     % (last_key, timestamp_to_string(_day_span.start,
                                                                      format_str="%Y-%m-%d"), e))
                            raise
                        # Update the daily summary with the weighted accumulator
                        if not self.dry_run:
                            self.dbm._set_day_summary(_day_accum, None, _cursor)
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
                        last_start = _day_span.start

                    # Setup our next tranche
                    # Have we reached the end, if so break to finish
                    if _tr_stop_ts >= startOfDay(self.dbm.last_timestamp):
                        break
                    # More to process so set our start and stop for the next
                    # transaction
                    _tr_start_dt = datetime.datetime.fromtimestamp(_tr_stop_ts) \
                        + datetime.timedelta(days=1)
                    _tr_start_ts = time.mktime(_tr_start_dt.timetuple())
                    _tr_stop_dt = datetime.datetime.fromtimestamp(_tr_start_ts) \
                        + datetime.timedelta(days=self.trans_days)
                    _tr_stop_ts = time.mktime(_tr_stop_dt.timetuple())
                    _tr_stop_ts = min(self.dbm.last_timestamp, _tr_stop_ts)

            # We have finished. Get rid of the no longer needed lastWeightPatch
            with weedb.Transaction(self.dbm.connection) as _cursor:
                _cursor.execute("DELETE FROM %s_day__metadata WHERE name=?"
                                % self.dbm.table_name, ('lastWeightPatch',))

            # Give the user some final information on progress,
            # mainly so the total tallies with the log
            self._progress(_days, last_start)
            print(file=sys.stdout)
            tdiff = time.time() - t1
            # We are done so log and inform the user
            log.info("intervalweighting: Calculated weighting "
                     "for %s days in %0.2f seconds." % (_days, tdiff))
            if self.dry_run:
                log.info("intervalweighting: "
                         "This was a dry run. %s was not applied." % self.name)
        else:
            # we didn't need to weight so inform the user
            log.info("intervalweighting: %s has already been applied." % self.name)

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

        _row = self.dbm.getSql(
            "SELECT `interval` FROM %s WHERE dateTime > ? AND dateTime <= ?;"
            % self.dbm.table_name, span)
        try:
            return _row[0]
        except IndexError:
            _msg = "'interval' field not found in archive day %s." % span
            raise weewx.ViolatedPrecondition(_msg)

    def unique_day_interval(self, timestamp):
        """Check a weewx archive for homogeneous interval values for each day.

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
        log.debug("intervalweighting: Checking table '%s' for multiple "
                  "'interval' values per day..." % self.dbm.table_name)
        start_ts = timestamp if timestamp else self.dbm.first_timestamp
        _days = 0
        _result = True
        for _day_span in weeutil.weeutil.genDaySpans(start_ts,
                                                     self.dbm.last_timestamp):
            _row = self.dbm.getSql("SELECT MIN(`interval`),MAX(`interval`) FROM %s "
                                   "WHERE dateTime > ? AND dateTime <= ?;"
                                   % self.dbm.table_name, _day_span)
            try:
                # If MIN and MAX are the same then we only have 1 distinct
                # value. If the query returns nothing then that is fine too,
                # probably no archive data for that day.
                _result = _row[0] == _row[1] if _row else True
            except IndexError:
                # Something is seriously amiss, raise an error
                raise weewx.ViolatedPrecondition("Invalid 'interval' data "
                                                 "detected in archive day %s." % _day_span)
            _days += 1
            if not _result:
                break
        if _result:
            log.debug("intervalweighting: Successfully checked %s days "
                      "for multiple 'interval' values in %0.2f seconds."
                      % (_days, (time.time() - t1)))
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

        print("Weighting daily summary: %d; Timestamp: %s\r"
              % (ndays, timestamp_to_string(last_time, format_str="%Y-%m-%d")),
              end='', file=sys.stdout)
        sys.stdout.flush()


# ============================================================================
#                             class CalcMissing
# ============================================================================


class CalcMissing(DatabaseFix):
    """Class to calculate and store missing derived observations.

    The following algorithm is used to calculate and store missing derived
     observations:

    1.  Obtain a wxservices.WXCalculate() object to calculate the derived obs
        fields for each record
    2.  Iterate over each day and record in the period concerned augmenting
        each record with derived fields. Any derived fields that are missing
        or == None are calculated. Days are processed in tranches and each
        updated derived fields for each tranche are processed as a single db
        transaction.
    4.  Once all days/records have been processed the daily summaries for the
        period concerned are recalculated.
    """

    def __init__(self, config_dict, calc_missing_config_dict):
        """Initialise a CalcMissing object.

        config_dict: WeeWX config file as a dict
        calc_missing_config_dict: A config dict with the following structure:
            name:       A descriptive name for the class
            binding:    data binding to use
            start_ts:   start ts of timespan over which missing derived fields
                        will be calculated
            stop_ts:    stop ts of timespan over which missing derived fields
                        will be calculated
            trans_days: number of days of records per db transaction
            dry_run:    is this a dry run (boolean)
        """

        # call our parents __init__
        super(CalcMissing, self).__init__(config_dict, calc_missing_config_dict)

        # the start timestamp of the period to calc missing
        self.start_ts = int(calc_missing_config_dict.get('start_ts'))
        # the stop timestamp of the period to calc missing
        self.stop_ts = int(calc_missing_config_dict.get('stop_ts'))
        # number of days per db transaction, default to 50.
        self.trans_days = int(calc_missing_config_dict.get('trans_days', 10))
        # is this a dry run, default to true
        self.dry_run = to_bool(calc_missing_config_dict.get('dry_run', True))

    def run(self):
        """Main entry point for calculating missing derived fields.

        Calculate the missing derived fields for the timespan concerned, save
        the calculated data to archive and recalculate the daily summaries.
        """

        # record the current time
        t1 = time.time()
        # obtain a wxservices.WXCalculate object to calculate the missing fields
        # first we need station altitude, latitude and longitude
        stn_dict = self.config_dict['Station']
        altitude_t = option_as_list(stn_dict.get('altitude', (None, None)))
        try:
            altitude_vt = weewx.units.ValueTuple(float(altitude_t[0]),
                                                 altitude_t[1],
                                                 "group_altitude")
        except KeyError as e:
            raise weewx.ViolatedPrecondition(
                "Value 'altitude' needs a unit (%s)" % e)
        latitude_f = float(stn_dict['latitude'])
        longitude_f = float(stn_dict['longitude'])

        # now we can create a WXCalculate object
        wxcalculate = weewx.wxservices.WXCalculate(self.config_dict,
                                                   altitude_vt,
                                                   latitude_f,
                                                   longitude_f)

        # initialise some counters so we know what we have processed
        days_updated = 0
        days_processed = 0
        total_records_processed = 0
        total_records_updated = 0

        # obtain gregorian days for our start and stop timestamps
        start_greg = weeutil.weeutil.toGregorianDay(self.start_ts)
        stop_greg = weeutil.weeutil.toGregorianDay(self.stop_ts)
        # start at the first day
        day = start_greg
        while day <= stop_greg:
            # get the start and stop timestamps for this tranche
            tr_start_ts = weeutil.weeutil.startOfGregorianDay(day)
            tr_stop_ts = min(weeutil.weeutil.startOfGregorianDay(stop_greg + 1),
                             weeutil.weeutil.startOfGregorianDay(day + self.trans_days))
            # start the transaction
            with weedb.Transaction(self.dbm.connection) as _cursor:
                # iterate over each day in the tranche we are to work in
                for tranche_day in weeutil.weeutil.genDaySpans(tr_start_ts, tr_stop_ts):
                    # initialise a counter for records processed on this day
                    records_updated = 0
                    # iterate over each record in this day
                    for record in self.dbm.genBatchRecords(startstamp=tranche_day.start,
                                                           stopstamp=tranche_day.stop):
                        # but we are only concerned with records after the
                        # start and before or equal to the stop timestamps
                        if self.start_ts < record['dateTime'] <= self.stop_ts:
                            # first obtain a list of the fields that may be calculated
                            extras_list = []
                            for obs in wxcalculate.svc_dict['Calculations']:
                                directive = wxcalculate.svc_dict['Calculations'][obs]
                                if directive == 'software' \
                                        or directive == 'prefer_hardware' and (
                                        obs not in record or record[obs] is None):
                                    extras_list.append(obs)

                            # calculate the missing derived fields for the record
                            wxcalculate.do_calculations(data_dict=record,
                                                        data_type='archive')
                            # Obtain a dict containing only those fields that
                            # WXCalculate calculated. We could do this as a
                            # dictionary comprehension but python2.6 does not
                            # support dictionary comprehensions.
                            extras_dict = {}
                            for k in extras_list:
                                if k in record.keys():
                                    extras_dict[k] = record[k]
                            # update the archive with the calculated data
                            records_updated += self.update_record_fields(record['dateTime'],
                                                                         extras_dict)
                            # update the total records processed
                            total_records_processed += 1
                        # Give the user some information on progress
                        if total_records_processed % 1000 == 0:
                            p_msg = "Processing record: %d; Last record: %s" % (total_records_processed,
                                                                                timestamp_to_string(record['dateTime']))
                            self._progress(p_msg)
                    # update the total records updated
                    total_records_updated += records_updated
                    # if we updated any records on this day increment the count
                    # of days updated
                    days_updated += 1 if records_updated > 0 else 0
                    days_processed += 1
            # advance to the next tranche
            day += self.trans_days
        # finished, so give the user some final information on progress, mainly
        # so the total tallies with the log
        p_msg = "Processing record: %d; Last record: %s" % (total_records_processed,
                                                            timestamp_to_string(tr_stop_ts))
        self._progress(p_msg, overprint=False)
        # now update the daily summaries, but only if this is not a dry run
        if not self.dry_run:
            print("Recalculating daily summaries...")
            # first we need a start and stop date object
            start_d = datetime.date.fromtimestamp(self.start_ts)
            # Since each daily summary is identified by the midnight timestamp
            # for that day we need to make sure we our stop timestamp is not on
            # a midnight boundary or we will rebuild the following days sumamry
            # as well. if it is on a midnight boundary just subtract 1 second
            # and use that.
            summary_stop_ts = self.stop_ts
            if weeutil.weeutil.isMidnight(self.stop_ts):
                summary_stop_ts -= 1
            stop_d = datetime.date.fromtimestamp(summary_stop_ts)
            # do the update
            self.dbm.backfill_day_summary(start_d=start_d, stop_d=stop_d)
            print(file=sys.stdout)
            print("Finished recalculating daily summaries")
        else:
            # it's a dry run so say the rebuild was skipped
            print("This is a dry run, recalculation of daily summaries was skipped")
        tdiff = time.time() - t1
        # we are done so log and inform the user
        _day_processed_str = "day" if days_processed == 1 else "days"
        _day_updated_str = "day" if days_updated == 1 else "days"
        if not self.dry_run:
            log.info("Processed %d %s consisting of %d records. "
                     "%d %s consisting of %d records were updated "
                     "in %0.2f seconds." % (days_processed,
                                            _day_processed_str,
                                            total_records_processed,
                                            days_updated,
                                            _day_updated_str,
                                            total_records_updated,
                                            tdiff))
        else:
            # this was a dry run
            log.info("Processed %d %s consisting of %d records. "
                     "%d %s consisting of %d records would have been updated "
                     "in %0.2f seconds." % (days_processed,
                                            _day_processed_str,
                                            total_records_processed,
                                            days_updated,
                                            _day_updated_str,
                                            total_records_updated,
                                            tdiff))

    def update_record_fields(self, ts, record, cursor=None):
        """Update multiple fields in a given archive record.

        Updates multiple fields in an archive record via an update query.

        Inputs:
            ts:     epoch timestamp of the record to be updated
            record: dict containing the updated data in field name-value pairs
            cursor: sqlite cursor
        """

        # Only data types that appear in the database schema can be
        # updated. To find them, form the intersection between the set of
        # all record keys and the set of all sql keys
        record_key_set = set(record.keys())
        update_key_set = record_key_set.intersection(self.dbm.sqlkeys)
        # only update if we have data for at least one field that is in the schema
        if len(update_key_set) > 0:
            # convert to an ordered list
            key_list = list(update_key_set)
            # get the values in the same order
            value_list = [record[k] for k in key_list]

            # Construct the SQL update statement. First construct the 'SET'
            # argument, we want a string of comma separated `field_name`=?
            # entries. Each ? will be replaced by a value from update value list
            # when the SQL statement is executed. We should not see any field
            # names that are SQLite/MySQL reserved words (eg interval) but just
            # in case enclose field names in backquotes.
            set_str = ','.join(["`%s`=?" % k for k in key_list])
            # form the SQL update statement
            sql_update_stmt = "UPDATE %s SET %s WHERE dateTime=%s" % (self.dbm.table_name,
                                                                      set_str,
                                                                      ts)
            # obtain a cursor if we don't have one
            _cursor = cursor or self.dbm.connection.cursor()
            # execute the update statement but only if its not a dry run
            if not self.dry_run:
                _cursor.execute(sql_update_stmt, value_list)
            # close the cursor is we opened one
            if cursor is None:
                _cursor.close()
            # if we made it here the record was updated so return the number of
            # records updated which will always be 1
            return 1
        # there were no fields to update so return 0
        return 0

    @staticmethod
    def _progress(message, overprint=True):
        """Utility function to show our progress."""

        if overprint:
            print(message + "\r", end='')
        else:
            print(message)
        sys.stdout.flush()
