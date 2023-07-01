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
