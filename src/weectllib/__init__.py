#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""The 'weectllib' package."""

import datetime

import weecfg
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


def prepare(config_path, db_binding, dry_run):
    """Common preamble, used by most of the action functions."""

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                              db_binding)
    database_name = manager_dict['database_dict']['database_name']

    return config_path, config_dict, database_name
