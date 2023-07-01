#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Various high-level, interactive, database actions"""

import logging
import sys
import time

import weecfg
import weectllib
import weedb
import weewx.manager
from weeutil.weeutil import bcolors, y_or_n

log = logging.getLogger(__name__)


def create_database(config_path, db_binding='wx_binding', dry_run=False):
    """Create a new database."""
    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    # Try a simple open. If it succeeds, that means the database
    # exists and is initialized. Otherwise, an exception will be raised.
    try:
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbmanager:
            print(f"Database '{dbmanager.database_name}' already exists. Nothing done.")
    except weedb.OperationalError:
        if not dry_run:
            # Database does not exist. Try again, but allow initialization:
            with weewx.manager.open_manager_with_config(config_dict,
                                                        db_binding,
                                                        initialize=True) as dbmanager:
                print(f"Created database '{dbmanager.database_name}'.")


def drop_daily(config_path, db_binding='wx_binding', dry_run=False):
    """Drop the daily summary from a WeeWX database."""

    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

    print(f"Proceeding will delete all your daily summaries from database '{database_name}'")
    ans = y_or_n("Are you sure you want to proceed (y/n)? ")
    if ans == 'y':
        t1 = time.time()
        print(f"Dropping daily summary tables from '{database_name}' ... ")
        try:
            with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbmanager:
                try:
                    if not dry_run:
                        dbmanager.drop_daily()
                except weedb.OperationalError as e:
                    print("Error '%s'" % e, file=sys.stderr)
                    print(f"Drop daily summary tables failed for database '{database_name}'")
                else:
                    tdiff = time.time() - t1
                    print("Daily summary tables dropped from "
                          f"database '{database_name}' in {tdiff:.2f} seconds")
        except weedb.OperationalError:
            # No daily summaries. Nothing to be done.
            print(f"No daily summaries found in database '{database_name}'. Nothing done.")
    else:
        print("Nothing done.")

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


def rebuild_daily(config_path,
                  db_binding='wx_binding',
                  date=None,
                  from_date=None,
                  to_date=None,
                  dry_run=False):
    """Rebuild the daily summaries."""

    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

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
    ans = y_or_n(f"Rebuild the daily summaries in the database '{database_name}'? (y/n) ")
    if ans == 'n':
        log.info("Nothing done.")
        print("Nothing done.")
        return

    t1 = time.time()

    log.info("Rebuilding daily summaries in database '%s' ..." % database_name)
    print("Rebuilding daily summaries in database '%s' ..." % database_name)
    if dry_run:
        print("This was a dry run. Nothing was actually done.")
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


def add_column(config_path,
               db_binding='wx_binding',
               column_name=None,
               column_type=None,
               dry_run=False):
    """Add a single column to the database.
    column_name: The name of the new column.
    column_type: The type ("REAL"|"INTEGER") of the new column.
    """
    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

    column_type = column_type or 'REAL'
    ans = y_or_n(
        f"Add new column '{column_name}' of type '{column_type}' "
        f"to database '{database_name}'? (y/n) ")
    if ans == 'y':
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
            if not dry_run:
                dbm.add_column(column_name, column_type)
        print(f'New column {column_name} of type {column_type} added to database.')
    else:
        print("Nothing done.")

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


def rename_column(config_path,
                  db_binding='wx_binding',
                  column_name=None,
                  new_name=None,
                  dry_run=False):
    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

    ans = y_or_n(f"Rename column '{column_name}' to '{new_name}' "
                 f"in database {database_name}? (y/n) ")
    if ans == 'y':
        with weewx.manager.open_manager_with_config(config_dict, db_binding) as dbm:
            if not dry_run:
                dbm.rename_column(column_name, new_name)
        print(f"Column '{column_name}' renamed to '{new_name}'.")
    else:
        print("Nothing done.")

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


def drop_columns(config_path,
                 db_binding='wx_binding',
                 column_names=None,
                 dry_run=False):
    """Drop a set of columns from the database"""
    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

    ans = y_or_n(f"Drop column(s) '{', '.join(column_names)}' from the database? (y/n) ")
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

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


def reconfigure_database(config_path,
                         db_binding='wx_binding',
                         dry_run=False):
    """Create a new database, then populate it with the contents of an old database, but use
    the current configuration options."""

    config_path, config_dict, database_name = _prepare(config_path, db_binding, dry_run)

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                              db_binding)
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
                     "Delete it first? (y/n) " % new_database_dict['database_name'])
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

    ans = y_or_n("Are you sure you wish to proceed? (y/n) ")
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

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


def transfer_database(config_path, db_binding='wx_binding', dest_binding=None, dry_run=False):
    """Transfer 'archive' data from one database to another"""

    # do we have enough to go on, must have a dest binding
    if not dest_binding:
        print("Destination binding not specified. Nothing Done. Aborting.", file=sys.stderr)
        return

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    # get manager dict for our source binding
    src_manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                                  db_binding)
    # get manager dict for our dest binding
    try:
        dest_manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                                       dest_binding)
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
                        dest_manager_dict['database_dict']['database_name']))
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

    if dry_run:
        print("This was a dry run. Nothing was actually done.")


# --------------------- UTILITIES -------------------- #
def _prepare(config_path, db_binding, dry_run):
    """Common preamble, used by most of the action functions."""

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                              db_binding)
    database_name = manager_dict['database_dict']['database_name']

    return config_path, config_dict, database_name
