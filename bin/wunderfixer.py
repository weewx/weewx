#!/usr/bin/env python
# ===============================================================================
# Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
# 
# This software may be used and redistributed under the
# terms of the GNU General Public License version 3.0
# or, at your option, any higher version.
# 
# See the file LICENSE.txt for your full rights.
#
# ===============================================================================
"""This utility fills in missing data on the Weather Underground.  It goes through all the records
in a weewx archive file for a given day, comparing to see whether a corresponding record exists on
the Weather Underground. If not, it will publish a new record on the Weather Underground with the
missing data.

Details of the API for downloading historical data from the WU can be found here:
https://docs.google.com/document/d/1w8jbqfAk0tfZS5P7hYnar1JiitM0gQZB-clxDfG3aD0/edit

Wunderground response codes:
- When using the "1day" API
   o Normal                    | 200
   o Non-existent station      | 204
   o Bad api key               | 401
- When using the "history" API
   o Normal                    | 200
   o Non-existent station      | 204
   o Good station, but no data | 204
   o Bad api key               | 401

Unfortunately, there is no reliable way to tell the difference between a request for a non-existing
station, and a request for a date with no data.

CHANGE HISTORY
--------------------------------
1.9.1 05/02/2020
Fixed problem under Python 3 where response was not converted to str before attempting
to parse the JSON.
Option --test now requires api_key and password, then goes ahead with querying the WU.

1.9.0 02/10/2020
With response code of 204, changed the default to assume a good station with no data
(rather than a bad station ID).

1.8.0 12/15/2019
Fixed bug where epsilon was not recognized.
Added option 'upload-only', with default of 300 seconds.

1.7.0 12/03/2019
Now uses "dual APIs." One for today, one for historical data.

1.6.0 08/17/2019
Use Python 'logging' package

1.5.1 07/19/2019
More refined error handling.

1.5.0 07/18/2019
Ported to new WU API. Now requires an API key.

1.4.1 05/14/2019
Made WunderStation class consistent with restx.AmbientThread parameters

1.4.0 05/07/2019
Ported to Python 3

1.3.0 04/30/19
Added option --timeout.

1.2.1 02/07/19
Keep going even if an observation does not satisfy [[Essentials]].

1.2.0 11/12/18
Now honors an [[[Essentials]]] section in the configuration file.

1.1.0 10/11/16
Now uses restx API to publish the requests.
Standardised option syntax.

1.0.0 8/16/15
Published version.

1.0.0a1   2/28/15
Now uses weewx API allowing use with any database supported by weewx.
Now supports weewx databases using any weewx supported unit system (eg US, 
METRIC and METRIXWX).
Database is no longer specified by file name rather path to weewx.conf and a 
binding are specified.
Now posts wind speeds with 1 decimal place and barometer with 3 decimal places.
Now has option to log to syslog.

0.5.2   11/17/12
Adds radiation and UV to the types posted on WU.

0.5.1   11/05/12
Now assumes sqlite3 will be present. If not, it falls back to pysqlite2.

0.5.0   10/31/11
Fixed bug in fuzzy compares, which were introduced in V0.3. 
Timestamps within an epsilon (default 120 seconds) of each other are
considered the same. Epsilon can be specified on the command line.

0.4.0   04/10/10
Now tries up to max_tries times to publish to the WU before giving up.
"""
from __future__ import print_function
import datetime
import gzip
import json
import logging
import optparse
import socket
import sys
import time

# Python 2/3 compatiblity shims
import six
from six.moves import urllib, input

import weecfg
import weewx.manager
import weewx.restx
import weeutil.logger
from weeutil.config import search_up
from weeutil.weeutil import timestamp_to_string

log = logging.getLogger(__name__)

usagestr = """%prog CONFIG_FILE|--config=CONFIG_FILE
                  [--binding=BINDING]
                  [--station=STATION] [--password=PASSWORD] [--api-key=API_KEY]
                  [--date=YYYY-mm-dd] [--epsilon=SECONDS] [--upload-only=SECONDS] 
                  [--verbose] [--test] [--query] [--timeout=SECONDS]
                  [--help]

This utility fills in missing data on the Weather Underground.  It goes through
all the records in a weewx archive for a given day, comparing to see whether a 
corresponding record exists on the Weather Underground. If not, it will publish
a new record on the Weather Underground with the missing data.

Be sure to use the --test switch first to see whether you like what it 
proposes!"""

epilog = """Options 'station', 'password', and 'api-key' must be supplied either
on the command line, or in the configuration file."""

__version__ = "1.9.1"

# The number of seconds difference in the timestamp between two records
# and still have them considered to be the same: 
epsilon = None


def main():
    """main program body for wunderfixer"""

    global epsilon

    parser = optparse.OptionParser(usage=usagestr, epilog=epilog)
    parser.add_option("-c", "--config", metavar="CONFIG_PATH",
                      help="Use configuration file CONFIG_PATH. "
                           "Default is /etc/weewx/weewx.conf or /home/weewx/weewx.conf.")
    parser.add_option("-b", "--binding", default='wx_binding',
                      help="The database binding to be used. Default is 'wx_binding'.")
    parser.add_option("-s", "--station",
                      help="Weather Underground station to check. Optional. "
                           "Default is to take from configuration file.")
    parser.add_option("-p", "--password",
                      help="Weather Underground station password. Optional. "
                           "Default is to take from configuration file.")
    parser.add_option("-k", "--api-key",
                      help="Weather Underground API key. Optional. "
                           "Default is to take from configuration file.")
    parser.add_option("-d", "--date", metavar="YYYY-mm-dd",
                      help="Date to check as a string of form YYYY-mm-dd. Default is today.")
    parser.add_option("-e", "--epsilon", type="int", metavar="SECONDS", default=120,
                      help="Timestamps within this value in seconds compare true. "
                           "Default is 120.")
    parser.add_option("-u", "--upload-only", type="int", metavar="SECONDS", default=300,
                      help="Upload only records every SECONDS apart or more. "
                           "Default is 300.")
    parser.add_option("-v", "--verbose", action="store_true",
                      help="Print useful extra output.")
    parser.add_option("-l", "--log", type="string", dest="logging", metavar="LOG_FACILITY",
                      help="OBSOLETE. Logging will always occur.")
    parser.add_option("-t", "--test", action="store_true", dest="simulate",
                      help="Test what would happen, but don't do anything.")
    parser.add_option("-q", "--query", action="store_true",
                      help="For each record, query the user before making a change.")
    parser.add_option("-o", "--timeout", type="int", metavar="SECONDS", default=10,
                      help="Socket timeout in seconds. Default is 10.")

    (options, args) = parser.parse_args()

    socket.setdefaulttimeout(options.timeout)

    if options.verbose:
        weewx.debug = 1
    else:
        logging.disable(logging.INFO)

    # get our config file
    config_fn, config_dict = weecfg.read_config(options.config, args)

    # Now we can set up the user-customized logging:
    weeutil.logger.setup('wunderfixer', config_dict)

    print("Using configuration file %s." % config_fn)
    log.info("Using weewx configuration file %s." % config_fn)

    # Retrieve the station ID and password from the config file
    try:
        if not options.station:
            options.station = config_dict['StdRESTful']['Wunderground']['station']
        if not options.password:
            options.password = config_dict['StdRESTful']['Wunderground']['password']
        if not options.api_key:
            options.api_key = config_dict['StdRESTful']['Wunderground']['api_key']
    except KeyError:
        log.error("Missing Wunderground station, password, and/or api_key")
        exit("Missing Wunderground station, password, and/or api_key")

    # exit if any essential arguments are not present
    if not options.station or not options.password or not options.api_key:
        print("Missing argument(s).\n")
        print(parser.parse_args(["--help"]))
        log.error("Missing argument(s). Wunderfixer exiting.")
        exit()

    # get our binding and database and say what we are using
    db_binding = options.binding
    database = config_dict['DataBindings'][db_binding]['database']
    print("Using database binding '%s', which is bound to database '%s'"
          % (db_binding, database))
    log.info("Using database binding '%s', which is bound to database '%s'"
             % (db_binding, database))

    # get the manager object for our db_binding
    dbmanager_t = weewx.manager.open_manager_with_config(config_dict, db_binding)

    _ans = 'y'
    if options.simulate:
        options.query = False
        _ans = 'n'

    if options.query:
        options.verbose = True

    if options.date:
        date_tt = time.strptime(options.date, "%Y-%m-%d")
        date_date = datetime.date(date_tt[0], date_tt[1], date_tt[2])
    else:
        # If no date option was specified on the command line, use today's date:
        date_date = datetime.date.today()

    epsilon = options.epsilon

    _essentials_dict = search_up(config_dict['StdRESTful']['Wunderground'], 'Essentials', {})
    log.debug("WU essentials: %s" % _essentials_dict)

    if options.verbose:
        print("Weather Underground Station:  ", options.station)
        print("Date to check:                ", date_date)
        log.info("Checking Weather Underground station '%s' data "
                 "for date %s" % (options.station, date_date))

    group_by = options.upload_only if options.upload_only else None

    # Get all the time stamps in the archive for the given day:
    archive_results = getArchiveDayTimeStamps(dbmanager_t, date_date, group_by)

    if options.verbose:
        print("Number of archive records:    ", len(archive_results))

    # Get a WunderStation object so we can interact with Weather Underground
    wunder = WunderStation(options.api_key,
                           q=None,  # Bogus queue. We will not be using it.
                           manager_dict=dbmanager_t,
                           station=options.station,
                           password=options.password,
                           server_url=weewx.restx.StdWunderground.pws_url,
                           protocol_name="wunderfixer",
                           essentials=_essentials_dict,
                           softwaretype="wunderfixer-%s" % __version__)

    try:
        # Get all the time stamps on the Weather Underground for the given day:
        wunder_results = wunder.get_day_timestamps(date_date)
    except Exception as e:
        print("Could not get Weather Underground data.", file=sys.stderr)
        print("Reason: %s" % e, file=sys.stderr)
        log.error("Could not get Weather Underground data. Exiting.")
        exit("Exiting.")

    if options.verbose:
        print("Number of WU records:         ", len(wunder_results))
    log.debug("Found %d archive records and %d WU records"
              % (len(archive_results), len(wunder_results)))

    # ===========================================================================
    # Unfortunately, the WU does not signal an error if you ask for a non-existent station. So,
    # there's no way to tell the difference between asking for results from a non-existent station,
    # versus a legitimate station that has no data for the given day. Warn the user, then proceed.
    # ===========================================================================
    if not wunder_results:
        sys.stdout.flush()
        print("\nNo results returned from Weather Underground "
              "(perhaps a bad station name??).", file=sys.stderr)
        print("Publishing anyway.", file=sys.stderr)
        log.error("No results returned from Weather Underground for station '%s'"
                  "(perhaps a bad station name??). Publishing anyway." % options.station)

    # Find the difference between the two lists, then sort them
    missing_records = sorted([ts for ts in archive_results if ts not in wunder_results])

    if options.verbose:
        print("Number of missing records:    ", len(missing_records))
        if missing_records:
            print("\nMissing records:")
    log.info("%d Weather Underground records missing." % len(missing_records))

    no_published = 0
    # Loop through the missing time stamps:
    for time_TS in missing_records:
        # Get the archive record for this timestamp:
        record = dbmanager_t.getRecord(time_TS.ts)
        # Print it out:
        print(print_record(record), end=' ', file=sys.stdout)
        sys.stdout.flush()

        # If this is an interactive session (option "-q") see if the
        # user wants to change it:
        if options.query:
            _ans = input("...fix? (y/n/a/q):")
            if _ans == "q":
                print("Quitting.")
                log.debug("... exiting")
                exit()
            if _ans == "a":
                _ans = "y"
                options.query = False

        if _ans == 'y':
            try:
                # Post the data to the WU:
                wunder.process_record(record, dbmanager_t)
                no_published += 1
                print(" ...published.", file=sys.stdout)
                log.debug("%s ...published" % timestamp_to_string(record['dateTime']))
            except weewx.restx.BadLogin as e:
                print("Bad login", file=sys.stderr)
                print(e, file=sys.stderr)
                exit("Bad login")
            except weewx.restx.FailedPost as e:
                print(e, file=sys.stderr)
                print("Aborted.", file=sys.stderr)
                log.error("%s ...error %s. Aborting.", timestamp_to_string(record['dateTime']), e)
                exit("Failed post")
            except weewx.restx.AbortedPost as e:
                print(" ... not published.", file=sys.stderr)
                print("Reason: ", e)
                log.error("%s ...not published. Reason '%s'",
                          timestamp_to_string(record['dateTime']), e)
            except IOError as e:
                print(" ... not published.", file=sys.stderr)
                print("Reason: ", e)
                log.error("%s ...not published. Reason '%s'",
                          timestamp_to_string(record['dateTime']), e)
                if hasattr(e, 'reason'):
                    print("Failed to reach server. Reason: %s" % e.reason, file=sys.stderr)
                    log.error("%s ...not published. Failed to reach server. Reason '%s'",
                              timestamp_to_string(record['dateTime']), e.reason)
                if hasattr(e, 'code'):
                    print("Failed to reach server. Error code: %s" % e.code, file=sys.stderr)
                    log.error("%s ...not published. Failed to reach server. Error code '%s'",
                              timestamp_to_string(record['dateTime']), e.code)

        else:
            print(" ... skipped.")
            log.debug("%s ...skipped", timestamp_to_string(record['dateTime']))
    log.info("%s out of %s missing records published to '%s' for date %s."
             " Wunderfixer exiting.",
             no_published, len(missing_records), options.station, date_date)


# ===============================================================================
#                             class WunderStation
# ===============================================================================

class WunderStation(weewx.restx.AmbientThread):
    """Class to interact with the Weather Underground."""

    def __init__(self, api_key, **kargs):
        # Get the API key, and pass the rest on to my super class
        self.api_key = api_key
        weewx.restx.AmbientThread.__init__(self, **kargs)

    def get_day_timestamps(self, day_requested):
        """Returns all time stamps for a given weather underground station for a given day.
        
        day_requested: An instance of datetime.date with the requested date
        
        return: a set containing the timestamps in epoch time
        """
        # We need to do different API calls depending on whether we are asking for today's weather,
        # or historical weather. Go figure.
        if day_requested >= datetime.date.today():
            # WU API URL format for today's weather
            url = "https://api.weather.com/v2/pws/observations/all/1day?stationId=%s" \
                  "&format=json&units=m&apiKey=%s" \
                   % (self.station, self.api_key)
        else:
            # WU API URL format for historical weather
            day_tt = day_requested.timetuple()
            url = "https://api.weather.com/v2/pws/history/all?stationId=%s&format=json" \
                  "&units=m&date=%4.4d%2.2d%2.2d&apiKey=%s" \
                   % (self.station, day_tt[0], day_tt[1], day_tt[2], self.api_key)

        request = urllib.request.Request(url)
        request.add_header('Accept-Encoding', 'gzip')
        request.add_header('User-Agent', 'Mozilla')

        try:
            response = urllib.request.urlopen(url)
        except urllib.error.URLError as e:
            print("Unable to open Weather Underground station " + self.station, " or ", e,
                  file=sys.stderr)
            log.error("Unable to open Weather Underground station %s or %s" % (self.station, e))
            raise
        except socket.timeout as e:
            print("Socket timeout for Weather Underground station " + self.station,
                  file=sys.stderr)
            log.error("Socket timeout for Weather Underground station %s", self.station)
            raise

        if hasattr(response, 'code') and response.code != 200:
            if response.code == 204:
                log.debug("Bad station (%s) or date (%s)" % (self.station, day_requested))
                return []
            elif response.code == 401:
                # This should not happen, as it should have been caught earlier as an URLError
                # exception, but just in case they change the API...
                raise weewx.restx.BadLogin("Bad login")
            else:
                raise IOError("Bad response code returned: %d" % response.code)

        # The WU API says that compression is required, yet it seems to always returns uncompressed
        # JSON. Just in case they decide to turn that requirement on, let's be ready for it:
        if response.info().get('Content-Encoding') == 'gzip':
            buf = six.StringIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()
        else:
            data = six.ensure_str(response.read())

        wu_data = json.loads(data)

        # We are only interested in the time stamps. Form a list of them
        time_stamps = [TimeStamp(record['epoch']) for record in wu_data['observations']]

        return time_stamps

    def handle_exception(self, e, count):
        """Override method that prints to the console, as well as the log"""

        # First call my superclass's method...
        super(WunderStation, self).handle_exception(e, count)
        # ... then print to the console
        print("%s: Failed upload attempt %d: %s" % (self.protocol_name, count, e))


# ===============================================================================
#                             class TimeStamp
# ===============================================================================

class TimeStamp(object):
    """This class represents a timestamp. It uses a 'fuzzy' compare.
    That is, if the times are within epsilon seconds of each other, they compare true."""

    def __init__(self, ts):
        self.ts = ts

    def __cmp__(self, other_ts):
        if self.__eq__(other_ts):
            return 0
        return 1 if self.ts > other_ts.ts else -1

    def __hash__(self):
        return hash(self.ts)

    def __eq__(self, other_ts):
        return abs(self.ts - other_ts.ts) <= epsilon

    def __lt__(self, other_ts):
        return self.ts < other_ts.ts

    def __str__(self):
        return timestamp_to_string(self.ts)


# ===============================================================================
#                             Utility functions
# ===============================================================================


# The formats to be used to print the record. For each type, there are two
# formats, the first to be used for a valid value, the second for value
# 'None'
_formats = (('barometer', ('%7.3f"', '    N/A ')),
            ('outTemp', ('%6.1fF', '   N/A ')),
            ('outHumidity', ('%4.0f%%', ' N/A ')),
            ('windSpeed', ('%4.1f mph', ' N/A mph')),
            ('windDir', ('%4.0f deg', ' N/A deg')),
            ('windGust', ('%4.1f mph gust', ' N/A mph gust')),
            ('dewpoint', ('%6.1fF', '   N/A ')),
            ('rain', ('%5.2f" rain', '  N/A  rain')))


def print_record(record):
    # Start with a formatted version of the time:
    _strlist = [timestamp_to_string(record['dateTime'])]

    # Now add the other types, in the order given by _formats:
    for (_type, _format) in _formats:
        _val = record.get(_type)
        _strlist.append(_format[0] % _val if _val is not None else _format[1])
    # _strlist is a list of strings. Convert it into one long string:
    _string_result = ';'.join(_strlist)
    return _string_result


def getArchiveDayTimeStamps(dbmanager, day_requested, group_by):
    """Returns all time stamps in a weewx archive file for a given day
    
    day_requested: An instance of datetime.date

    group_by: If present, group by this number of seconds.
    
    returns: A set containing instances of TimeStamps
    """

    # Get the ordinal number for today and tomorrow
    start_ord = day_requested.toordinal()
    end_ord = start_ord + 1

    # Convert them to instances of datetime.date
    start_date = datetime.date.fromordinal(start_ord)
    end_date = datetime.date.fromordinal(end_ord)

    # Finally, convert those to epoch time stamps. 
    # The result will be two timestamps for the two midnights
    # E.G., 2009-10-25 00:00:00 and 2009-10-26 00:00:00
    start_ts = time.mktime(start_date.timetuple())
    end_ts = time.mktime(end_date.timetuple())

    if group_by:
        sql_stmt = "SELECT MIN(dateTime) FROM archive WHERE dateTime>=? AND dateTime<? " \
               "GROUP BY ROUND(dateTime/%d);" % group_by
    else:
        sql_stmt = "SELECT dateTime FROM archive WHERE dateTime>=? AND dateTime<?"

    _gen_rows = dbmanager.genSql(sql_stmt, (start_ts, end_ts))

    # Create a list of all the time stamps
    time_stamps = [TimeStamp(record[0]) for record in _gen_rows]

    return time_stamps


# ===============================================================================
#                           Call main program body
# ===============================================================================


if __name__ == "__main__":
    main()
