#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""The 'weectllib' package."""

import datetime

import weewx


def parse_dates(date=None, from_date=None, to_date=None):
    """Parse --date, --from and --to command line options.

        Parses --date or --from and --to.

        Args:
            date(str|None): In the form YYYY-mm-dd
            from_date(str|None): In the form YYYY-mm-dd
            to_date(str|None) In the form YYYY-mm-dd

        Returns:
            tuple: A two-way tuple (from_d, to_d) representing the from and to dates
                as datetime.date objects.
    """

    # default is None, unless user has specified an option
    from_d = to_d = None

    # first look for --date
    if date:
        # we have a --date option, make sure we are not over specified
        if from_date or to_date:
            raise ValueError("Specify either --date or a --from and --to combination; not both")

        # there is a --date but is it valid
        try:
            from_d = to_d = datetime.date.fromisoformat(date)
        except ValueError:
            raise ValueError("Invalid --date option specified.")

    else:
        # we don't have --date. Look for --from and/or --to
        if from_date:
            try:
                from_d = datetime.date.fromisoformat(from_date)
            except ValueError:
                raise ValueError("Invalid --from option specified.")

        if to_date:
            try:
                to_d = datetime.date.fromisoformat(to_date)
            except ValueError:
                raise ValueError("Invalid --to option specified.")

            if from_date and from_d > to_d:
                raise weewx.ViolatedPrecondition("--from value is later than --to value.")

    return from_d, to_d
