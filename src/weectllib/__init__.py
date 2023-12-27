#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""The 'weectllib' package."""

import datetime
import logging
import sys

import configobj

import weecfg
import weeutil.logger
import weeutil.startup
import weewx
from weeutil.weeutil import bcolors


def parse_dates(date=None, from_date=None, to_date=None, as_datetime=False):
    """Parse --date, --from and --to command line options.

        Parses --date or --from and --to.

        Args:
            date(str|None): In the form YYYY-mm-dd
            from_date(str|None): Any ISO 8601 acceptable date or datetime.
            to_date(str|None): Any ISO 8601 acceptable date or datetime.
            as_datetime(bool): True, return a datetime.datetime object. Otherwise, return
                a datetime.date object.

        Returns:
            tuple: A two-way tuple (from_val, to_d) representing the from and to dates
                as datetime.datetime objects (as_datetime==True), or datetime.date (False).
    """

    # default is None, unless user has specified an option
    from_val = to_val = None

    # first look for --date
    if date:
        # we have a --date option, make sure we are not over specified
        if from_date or to_date:
            raise ValueError("Specify either --date or a --from and --to combination; not both")

        # there is a --date but is it valid
        try:
            if as_datetime:
                from_val = to_val = datetime.datetime.fromisoformat(date)
            else:
                from_val = to_val = datetime.date.fromisoformat(date)
        except ValueError:
            raise ValueError("Invalid --date option specified.")

    else:
        # we don't have --date. Look for --from and/or --to
        if from_date:
            try:
                if as_datetime:
                    from_val = datetime.datetime.fromisoformat(from_date)
                else:
                    from_val = datetime.date.fromisoformat(from_date)
            except ValueError:
                raise ValueError("Invalid --from option specified.")

        if to_date:
            try:
                if as_datetime:
                    to_val = datetime.datetime.fromisoformat(to_date)
                else:
                    to_val = datetime.date.fromisoformat(to_date)
            except ValueError:
                raise ValueError("Invalid --to option specified.")

            if from_date and from_val > to_val:
                raise weewx.ViolatedPrecondition("--from value is later than --to value.")

    return from_val, to_val


def dispatch(namespace):
    """All weectl commands come here. This function reads the configuration file, sets up logging,
    then dispatches to the actual action.
    """
    # Read the configuration file
    try:
        config_path, config_dict = weecfg.read_config(namespace.config)
    except (IOError, configobj.ConfigObjError) as e:
        print(f"Error parsing config file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    print(f"Using configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC}")

    try:
        # Customize the logging with user settings.
        weeutil.logger.setup('weectl', config_dict)
    except Exception as e:
        print(f"Unable to set up logger: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    # Get a logger. This one will have the requested configuration.
    log = logging.getLogger(__name__)
    # Announce the startup
    log.info("Initializing weectl version %s", weewx.__version__)
    log.info("Command line: %s", ' '.join(sys.argv))

    # Set up debug, add USER_ROOT to PYTHONPATH, read user.extensions:
    weeutil.startup.initialize(config_dict)

    # Note a dry-run, if applicable:
    if hasattr(namespace, 'dry_run') and namespace.dry_run:
        print("This is a dry run. Nothing will actually be done.")
        log.info("This is a dry run. Nothing will actually be done.")

    # Call the specified action:
    namespace.action_func(config_dict, namespace)

    if hasattr(namespace, 'dry_run') and namespace.dry_run:
        print("This was a dry run. Nothing was actually done.")
        log.info("This was a dry run. Nothing was actually done.")
