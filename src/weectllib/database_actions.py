#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Various high-level, interactive, database actions"""

import logging
import sys
import time

import weectllib
import weedb
import weewx
import weewx.manager
import weewx.units
from weeutil.weeutil import y_or_n, timestamp_to_string

log = logging.getLogger('weectl-database')


def create_database(config_dict,
                    db_binding='wx_binding',
                    dry_run=False,
                    no_confirm=False):
    """Create a new database."""

    # Try a simple open. If it succeeds, that means the database
    # exists and is initialized. Otherwise, an exception will be raised.
    try:
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbmanager:
            print(f"Database '{dbmanager.database_name}' already exists. Nothing done.")
    except weedb.OperationalError:
        if not dry_run:
            ans = y_or_n("Create database (y/n)? ", noprompt=no_confirm)
            if ans == 'n':
                print("Nothing done")
                return
            # Database does not exist. Try again, but allow initialization:
            with weewx.manager.open_manager_with_config(config_dict,
                                                        db_binding,
                                                        initialize=True) as dbmanager:
                print(f"Created database '{dbmanager.database_name}'.")


def drop_daily(config_dict,
               db_binding='wx_binding',
               dry_run=False,
               no_confirm=False):
    """Drop the daily summary from a WeeWX database."""

    try:
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbmanager:
            print("Proceeding will delete all your daily summaries from "
                  f"database '{dbmanager.database_name}'")
            ans = y_or_n("Are you sure you want to proceed (y/n)? ", noprompt=no_confirm)
            if ans == 'n':
                print("Nothing done")
                return
            t1 = time.time()
            try:
                if not dry_run:
                    dbmanager.drop_daily()
            except weedb.OperationalError as e:
                print("Error '%s'" % e, file=sys.stderr)
                print(f"Drop daily summary tables failed for database '{dbmanager.database_name}'")
            else:
                tdiff = time.time() - t1
                print("Daily summary tables dropped from "
                      f"database '{dbmanager.database_name}' in {tdiff:.2f} seconds")
    except weedb.OperationalError:
        # No daily summaries. Nothing to be done.
        print(f"No daily summaries found. Nothing done.")


def rebuild_daily(config_dict,
                  date=None,
                  from_date=None,
                  to_date=None,
                  db_binding='wx_binding',
                  dry_run=False,
                  no_confirm=False):
    """Rebuild the daily summaries."""

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    database_name = manager_dict['database_dict']['database_name']

    # Get any dates the user might have specified.
    from_d, to_d = weectllib.parse_dates(date, from_date, to_date)

    # Advise the user/log what we will do
    if not from_d and not to_d:
        msg = "All daily summaries will be rebuilt."
    elif from_d and not to_d:
        msg = f"Daily summaries starting with {from_d} will be rebuilt."
    elif not from_d and to_d:
        msg = f"Daily summaries through {to_d} will be rebuilt."
    elif from_d == to_d:
        msg = f"Daily summary for {from_d} will be rebuilt."
    else:
        msg = f"Daily summaries from {from_d} through {to_d}, inclusive, will be rebuilt."

    log.info(msg)
    print(msg)
    ans = y_or_n(f"Rebuild the daily summaries in the database '{database_name}'? (y/n) ",
                 noprompt=no_confirm)
    if ans == 'n':
        log.info("Nothing done.")
        print("Nothing done.")
        return

    t1 = time.time()

    log.info("Rebuilding daily summaries in database '%s' ..." % database_name)
    print("Rebuilding daily summaries in database '%s' ..." % database_name)
    if dry_run:
        return

    # Open up the database. This will create the tables necessary for the daily
    # summaries if they don't already exist:
    with weewx.manager.open_manager_with_config(config_dict,
                                                db_binding, initialize=True) as dbm:
        # Do the actual rebuild
        nrecs, ndays = dbm.backfill_day_summary(start_d=from_d,
                                                stop_d=to_d,
                                                trans_days=20)
    tdiff = time.time() - t1
    # advise the user/log what we did
    log.info("Rebuild of daily summaries in database '%s' complete." % database_name)
    if nrecs:
        sys.stdout.flush()
        # fix a bit of formatting inconsistency if less than 1000 records
        # processed
        if nrecs >= 1000:
            print()
        if ndays == 1:
            msg = f"Processed {nrecs} records to rebuild 1 daily summary in {tdiff:.2f} seconds."
        else:
            msg = f"Processed {nrecs} records to rebuild {ndays} daily summaries in " \
                  f"{tdiff:.2f} seconds."
        print(msg)
        print(f"Rebuild of daily summaries in database '{database_name}' complete.")
    else:
        print(f"Daily summaries up to date in '{database_name}'.")


def add_column(config_dict,
               column_name=None,
               column_type=None,
               db_binding='wx_binding',
               dry_run=False,
               no_confirm=False):
    """Add a single column to the database.
    column_name: The name of the new column.
    column_type: The type ("REAL"|"INTEGER") of the new column.
    """
    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    database_name = manager_dict['database_dict']['database_name']

    column_type = column_type or 'REAL'
    ans = y_or_n(
        f"Add new column '{column_name}' of type '{column_type}' "
        f"to database '{database_name}'? (y/n) ", noprompt=no_confirm)
    if ans == 'y':
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
            if not dry_run:
                dbm.add_column(column_name, column_type)
        print(f'New column {column_name} of type {column_type} added to database.')
    else:
        print("Nothing done.")


def rename_column(config_dict,
                  from_name=None,
                  to_name=None,
                  db_binding='wx_binding',
                  dry_run=False,
                  no_confirm=False):
    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    database_name = manager_dict['database_dict']['database_name']

    ans = y_or_n(f"Rename column '{from_name}' to '{to_name}' "
                 f"in database {database_name}? (y/n) ", noprompt=no_confirm)
    if ans == 'y':
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
            if not dry_run:
                dbm.rename_column(from_name, to_name)
        print(f"Column '{from_name}' renamed to '{to_name}'.")
    else:
        print("Nothing done.")


def drop_columns(config_dict,
                 column_names=None,
                 db_binding='wx_binding',
                 dry_run=False,
                 no_confirm=False):
    """Drop a set of columns from the database"""
    ans = y_or_n(f"Drop column(s) '{', '.join(column_names)}' from the database? (y/n) ",
                 noprompt=no_confirm)
    if ans == 'y':
        drop_set = set(column_names)
        # Now drop the columns. If one is missing, a NoColumnError will be raised. Be prepared
        # to catch it.
        print("This may take a while...")
        if not dry_run:
            with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
                try:
                    dbm.drop_columns(drop_set)
                except weedb.NoColumnError as e:
                    print(e, file=sys.stderr)
                    print("Nothing done.")
                else:
                    print(f"Column(s) '{', '.join(column_names)}' dropped from the database.")
    else:
        print("Nothing done.")


def reconfigure_database(config_dict,
                         db_binding='wx_binding',
                         dry_run=False,
                         no_confirm=False):
    """Create a new database, then populate it with the contents of an old database, but use
    the current configuration options. The reconfigure action will create a new database with the
     same name as the old, except with the suffix _new attached to the end."""

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    # Make a copy for the new database (we will be modifying it)
    new_database_dict = dict(manager_dict['database_dict'])

    # Now modify the database name
    new_database_dict['database_name'] = manager_dict['database_dict']['database_name'] + '_new'

    # First check and see if the new database already exists. If it does, check
    # with the user whether it's ok to delete it.
    try:
        if not dry_run:
            weedb.create(new_database_dict)
    except weedb.DatabaseExists:
        ans = y_or_n("New database '%s' already exists. "
                     "Delete it first? (y/n) " % new_database_dict['database_name'],
                     noprompt=no_confirm)
        if ans == 'y':
            weedb.drop(new_database_dict)
        else:
            print("Nothing done.")
            return

    # Get the unit system of the old archive:
    with weewx.manager.Manager.open(manager_dict['database_dict']) as old_dbmanager:
        old_unit_system = old_dbmanager.std_unit_system

    if old_unit_system is None:
        print("Old database has not been initialized. Nothing to be done.")
        return

    # Get the unit system of the new archive:
    try:
        target_unit_nickname = config_dict['StdConvert']['target_unit']
    except KeyError:
        target_unit_system = None
    else:
        target_unit_system = weewx.units.unit_constants[target_unit_nickname.upper()]

    print("Copying database '%s' to '%s'" % (manager_dict['database_dict']['database_name'],
                                             new_database_dict['database_name']))
    if target_unit_system is None or old_unit_system == target_unit_system:
        print("The new database will use the same unit system as the old ('%s')." %
              weewx.units.unit_nicknames[old_unit_system])
    else:
        print("Units will be converted from the '%s' system to the '%s' system." %
              (weewx.units.unit_nicknames[old_unit_system],
               weewx.units.unit_nicknames[target_unit_system]))

    ans = y_or_n("Are you sure you wish to proceed? (y/n) ", noprompt=no_confirm)
    if ans == 'y':
        t1 = time.time()
        weewx.manager.reconfig(manager_dict['database_dict'],
                               new_database_dict,
                               new_unit_system=target_unit_system,
                               new_schema=manager_dict['schema'],
                               dry_run=dry_run)
        tdiff = time.time() - t1
        print("Database '%s' copied to '%s' in %.2f seconds."
              % (manager_dict['database_dict']['database_name'],
                 new_database_dict['database_name'],
                 tdiff))
    else:
        print("Nothing done.")


def transfer_database(config_dict,
                      dest_binding=None,
                      db_binding='wx_binding',
                      dry_run=False,
                      no_confirm=False):
    """Transfer 'archive' data from one database to another"""

    # do we have enough to go on, must have a dest binding
    if not dest_binding:
        print("Destination binding not specified. Nothing Done. Aborting.", file=sys.stderr)
        return

    # get manager dict for our source binding
    src_manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    # get manager dict for our dest binding
    try:
        dest_manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, dest_binding)
    except weewx.UnknownBinding:
        # if we can't find the binding display a message then return
        print(f"Unknown destination binding '{dest_binding}'. "
              f"Please confirm the destination binding.")
        print("Nothing Done. Aborting.", file=sys.stderr)
        return
    except weewx.UnknownDatabase as e:
        # if we can't find the database display a message then return
        print(f"Error accessing destination database: {e}", file=sys.stderr)
        print("Nothing Done. Aborting.", file=sys.stderr)
        return
    except (ValueError, AttributeError):
        # maybe a schema issue
        print("Error accessing destination database.", file=sys.stderr)
        print("Maybe the destination schema is incorrectly specified "
              "in binding '%s' in weewx.conf?" % dest_binding, file=sys.stderr)
        print("Nothing Done. Aborting.", file=sys.stderr)
        return
    except weewx.UnknownDatabaseType:
        # maybe a [Databases] issue
        print("Error accessing destination database.", file=sys.stderr)
        print("Maybe the destination database is incorrectly defined in weewx.conf?",
              file=sys.stderr)
        print("Nothing Done. Aborting.", file=sys.stderr)
        return

    # All looks good. Get a manager for our source
    with weewx.manager.Manager.open(src_manager_dict['database_dict']) as src_manager:
        # How many source records?
        num_recs = src_manager.getSql("SELECT COUNT(dateTime) from %s;"
                                      % src_manager.table_name)[0]
        if not num_recs:
            # we have no source records to transfer so abort with a message
            print(f"No records found in source database '{src_manager.database_name}'.")
            print("Nothing done. Aborting.")
            return

        # not a dry run, actually do the transfer
        ans = y_or_n("Transfer %s records from source database '%s' "
                     "to destination database '%s'? (y/n) "
                     % (num_recs, src_manager.database_name,
                        dest_manager_dict['database_dict']['database_name']),
                     noprompt=no_confirm)
        if ans == 'n':
            print("Nothing done.")
            return

        t1 = time.time()
        nrecs = 0
        # wrap in a try..except in case we have an error
        try:
            with weewx.manager.Manager.open_with_create(
                    dest_manager_dict['database_dict'],
                    table_name=dest_manager_dict['table_name'],
                    schema=dest_manager_dict['schema']) as dest_manager:
                print("Transferring, this may take a while.... ")
                sys.stdout.flush()

                if not dry_run:
                    # This could generate a *lot* of log entries. Temporarily disable logging
                    # for events at or below INFO
                    logging.disable(logging.INFO)

                    # do the transfer, should be quick as it's done as a
                    # single transaction
                    nrecs = dest_manager.addRecord(src_manager.genBatchRecords(),
                                                   progress_fn=weewx.manager.show_progress)

                    # Remove the temporary restriction
                    logging.disable(logging.NOTSET)

                tdiff = time.time() - t1
                print("\nCompleted.")
                print("%s records transferred from source database '%s' to "
                      "destination database '%s' in %.2f seconds."
                      % (nrecs, src_manager.database_name,
                         dest_manager.database_name, tdiff))
        except ImportError as e:
            # Probably when trying to load db driver
            print("Error accessing destination database '%s'."
                  % (dest_manager_dict['database_dict']['database_name'],),
                  file=sys.stderr)
            print("Nothing done. Aborting.", file=sys.stderr)
            raise
        except (OSError, weedb.OperationalError):
            # probably a weewx.conf typo or MySQL db not created
            print("Error accessing destination database '%s'."
                  % dest_manager_dict['database_dict']['database_name'], file=sys.stderr)
            print("Maybe it does not exist (MySQL) or is incorrectly "
                  "defined in weewx.conf?", file=sys.stderr)
            print("Nothing done. Aborting.", file=sys.stderr)
            raise


def calc_missing(config_dict,
                 date=None,
                 from_date=None,
                 to_date=None,
                 db_binding='wx_binding',
                 tranche=10,
                 dry_run=False,
                 no_confirm=False):
    """Calculate any missing derived observations and save to database."""
    import weecfg.database

    log.info("Preparing to calculate missing derived observations...")

    # get a db manager dict given the config dict and binding
    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                              db_binding)
    # Get the table_name used by the binding, it could be different to the
    # default 'archive'. If for some reason it is not specified then fail hard.
    table_name = manager_dict['table_name']
    # get the first and last good timestamps from the archive, these represent
    # our overall bounds for calculating missing derived obs
    with weewx.manager.Manager.open(manager_dict['database_dict'],
                                    table_name=table_name) as dbmanager:
        first_ts = dbmanager.firstGoodStamp()
        last_ts = dbmanager.lastGoodStamp()
    # process any command line options that may limit the period over which
    # missing derived obs are calculated
    start_dt, stop_dt = weectllib.parse_dates(date,
                                              from_date=from_date, to_date=to_date,
                                              as_datetime=True)
    # we now have a start and stop date for processing, we need to obtain those
    # as epoch timestamps, if we have no start and/or stop date then use the
    # first or last good timestamp instead
    start_ts = time.mktime(start_dt.timetuple()) if start_dt is not None else first_ts - 1
    stop_ts = time.mktime(stop_dt.timetuple()) if stop_dt is not None else last_ts

    _head = "Missing derived observations will be calculated "
    # advise the user/log what we will do
    if start_dt is None and stop_dt is None:
        _tail = "for all records."
    elif start_dt and not stop_dt:
        _tail = "from %s through to the end (%s)." % (timestamp_to_string(start_ts),
                                                      timestamp_to_string(stop_ts))
    elif not start_dt and stop_dt:
        _tail = "from the beginning (%s) through to %s." % (timestamp_to_string(start_ts),
                                                            timestamp_to_string(stop_ts))
    else:
        _tail = "from %s through to %s inclusive." % (timestamp_to_string(start_ts),
                                                      timestamp_to_string(stop_ts))
    msg = "%s%s" % (_head, _tail)
    log.info(msg)
    print(msg)
    ans = y_or_n("Proceed? (y/n) ", noprompt=no_confirm)
    if ans == 'n':
        msg = "Nothing done."
        log.info(msg)
        print(msg)
        return

    t1 = time.time()

    # construct a CalcMissing config dict
    calc_missing_config_dict = {'name': 'Calculate Missing Derived Observations',
                                'binding': db_binding,
                                'start_ts': start_ts,
                                'stop_ts': stop_ts,
                                'trans_days': tranche,
                                'dry_run': dry_run}

    # obtain a CalcMissing object
    calc_missing_obj = weecfg.database.CalcMissing(config_dict,
                                                   calc_missing_config_dict)
    log.info("Calculating missing derived observations...")
    print("Calculating missing derived observations...")
    # Calculate and store any missing observations. Be prepared to
    # catch any exceptions from CalcMissing.
    try:
        calc_missing_obj.run()
    except weewx.UnknownBinding as e:
        # We have an unknown binding, this could occur if we are using a
        # non-default binding and StdWXCalculate has not been told (via
        # weewx.conf) to use the same binding. Log it and notify the user then
        # exit.
        msg = "Error: '%s'" % e
        print(msg)
        log.error(msg)
        print("Perhaps StdWXCalculate is using a different binding. Check "
              "configuration file [StdWXCalculate] stanza")
        sys.exit("Nothing done. Aborting.")
    else:
        msg = "Missing derived observations calculated in %0.2f seconds" % (time.time() - t1)
        log.info(msg)
        print(msg)


def check(config_dict, db_binding='wx_binding'):
    """Check the database for any issues."""

    print("Checking daily summary tables version...")
    with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
        daily_summary_version = dbm._read_metadata('Version')

    msg = f"Daily summary tables are at version {daily_summary_version}."
    log.info(msg)
    print(msg)

    if daily_summary_version is not None and daily_summary_version >= '2.0':
        # interval weighting fix has been applied
        msg = "Interval Weighting Fix is not required."
        log.info(msg)
        print(msg)
    else:
        print("Recommend running --update to recalculate interval weightings.")


def update_database(config_dict,
                    db_binding='wx_binding',
                    dry_run=False,
                    no_confirm=False):
    """Apply any required database fixes.

    Applies the following fixes:
    -   checks if database version is 3.0, if not interval weighting fix is
        applied
    -   recalculates windSpeed daily summary max and maxtime fields from
        archive
    """

    ans = y_or_n("The update process does not affect archive data, "
                 "but does alter the database.\nContinue (y/n)? ", noprompt=no_confirm)
    if ans == 'n':
        log.info("Update cancelled.")
        print("Update cancelled.")
        return

    log.info("Preparing interval weighting fix...")
    print("Preparing interval weighting fix...")

    # Get a database manager object
    with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
        # check the daily summary version
        msg = f"Daily summary tables are at version {dbm.version}."
        log.info(msg)
        print(msg)

        if dbm.version is not None and dbm.version >= '4.0':
            # interval weighting fix has been applied
            log.info("Interval weighting fix is not required.")
            print("Interval weighting fix is not required.")
        else:
            # apply the interval weighting
            log.info("Calculating interval weights...")
            print("Calculating interval weights. This could take awhile.")
            t1 = time.time()
            if not dry_run:
                dbm.update()
            msg = "Interval Weighting Fix completed in %0.2f seconds." % (time.time() - t1)
            print()
            print(msg)
            sys.stdout.flush()
            log.info(msg)

    # recalc the max/maxtime windSpeed values
    _fix_wind(config_dict, db_binding, dry_run)


def _fix_wind(config_dict, db_binding, dry_run):
    """Recalculate the windSpeed daily summary max and maxtime fields.

    Create a WindSpeedRecalculation object and call its run() method to
    recalculate the max and maxtime fields from archive data. This process is
    idempotent, so it can be called repeatedly with no ill effect.
    """
    import weecfg.database

    msg = "Preparing maximum windSpeed fix..."
    log.info(msg)
    print(msg)

    # notify if this is a dry run
    if dry_run:
        print("This is a dry run: maximum windSpeed will be calculated but not saved.")

    # construct a windSpeed recalculation config dict
    wind_config_dict = {'name': 'Maximum windSpeed fix',
                        'binding': db_binding,
                        'trans_days': 100,
                        'dry_run': dry_run}

    # create a windSpeedRecalculation object
    wind_obj = weecfg.database.WindSpeedRecalculation(config_dict,
                                                      wind_config_dict)
    # perform the recalculation, wrap in a try..except to catch any db errors
    t1 = time.time()

    try:
        wind_obj.run()
    except weedb.NoTableError:
        msg = "Maximum windSpeed fix applied: no windSpeed found"
        log.info(msg)
        print(msg)
    else:
        msg = "Maximum windSpeed fix completed in %0.2f seconds" % (time.time() - t1)
        log.info(msg)
        print(msg)


def reweight_daily(config_dict,
                   date=None,
                   from_date=None,
                   to_date=None,
                   db_binding='wx_binding',
                   dry_run=False,
                   no_confirm=False):
    """Recalculate the weighted sums in the daily summaries."""

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict, db_binding)
    database_name = manager_dict['database_dict']['database_name']

    # Determine the period over which we are rebuilding from any command line date parameters
    from_d, to_d = weectllib.parse_dates(date,
                                         from_date=from_date, to_date=to_date)

    # advise the user/log what we will do
    if from_d is None and to_d is None:
        msg = "The weighted sums in all the daily summaries will be recalculated."
    elif from_d and not to_d:
        msg = "The weighted sums in the daily summaries from %s through the end " \
              "will be recalculated." % from_d
    elif not from_d and to_d:
        msg = "The weighted sums in the daily summaries from the beginning through %s" \
              "will be recalculated." % to_d
    elif from_d == to_d:
        msg = "The weighted sums in the daily summary for %s will be recalculated." % from_d
    else:
        msg = "The weighted sums in the daily summaries from %s through %s, " \
              "inclusive, will be recalculated." % (from_d, to_d)

    log.info(msg)
    print(msg)
    ans = y_or_n("Proceed (y/n)? ", noprompt=no_confirm)
    if ans == 'n':
        log.info("Nothing done.")
        print("Nothing done.")
        return

    t1 = time.time()

    # Open up the database.
    with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbmanager:
        msg = f"Recalculating the weighted summaries in database '{database_name}' ..."
        log.info(msg)
        print(msg)
        if not dry_run:
            # Do the actual recalculations
            dbmanager.recalculate_weights(start_d=from_d, stop_d=to_d)

    msg = "Finished reweighting in %.1f seconds." % (time.time() - t1)
    log.info(msg)
    print()
    print(msg)
