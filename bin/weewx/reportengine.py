#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Engine for generating reports"""

# System imports:
import datetime
import ftplib
import glob
import os.path
import shutil
import socket
import sys
import syslog
import threading
import time
import traceback

# 3rd party imports:
import configobj

# Weewx imports:
import weeutil.weeutil
from weeutil.weeutil import to_bool
import weewx.manager

# spans of valid values for each CRON like field
MINUTES = (0, 59)
HOURS = (0, 23)
DOM = (1, 31)
MONTHS = (1, 12)
DOW = (0, 6)
# valid day names for DOW field
DAY_NAMES = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')
# valid month names for month field
MONTH_NAMES = ('jan', 'feb', 'mar', 'apr', 'may', 'jun',
               'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
# map month names to month number
MONTH_NAME_MAP = zip(('jan', 'feb', 'mar', 'apr',
                      'may', 'jun', 'jul', 'aug',
                      'sep', 'oct', 'nov', 'dec'), xrange(1, 13))
# map day names to day number
DAY_NAME_MAP = zip(('sun', 'mon', 'tue', 'wed',
                    'thu', 'fri', 'sat'), xrange(7))
# map CRON like nicknames to equivalent CRON like line
NICKNAME_MAP = {
    "@yearly": "0 0 1 1 *",
    "@anually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@hourly": "0 * * * *"
}
# list of valid spans for CRON like fields
SPANS = (MINUTES, HOURS, DOM, MONTHS, DOW)
# list of valid names for CRON lik efields
NAMES = ((), (), (), MONTH_NAMES, DAY_NAMES)
# list of name maps for CRON like fields
MAPS = ((), (), (), MONTH_NAME_MAP, DAY_NAME_MAP)

# =============================================================================
#                    Class StdReportEngine
# =============================================================================

class StdReportEngine(threading.Thread):
    """Reporting engine for weewx.

    This engine runs zero or more reports. Each report uses a skin. A skin
    has its own configuration file specifying things such as which 'generators'
    should be run, which templates are to be used, what units are to be used,
    etc..
    A 'generator' is a class inheriting from class ReportGenerator, that
    produces the parts of the report, such as image plots, HTML files.

    StdReportEngine inherits from threading.Thread, so it will be run in a
    separate thread.

    See below for examples of generators.
    """

    def __init__(self, config_dict, stn_info, record=None, gen_ts=None, first_run=True):
        """Initializer for the report engine.

        config_dict: The configuration dictionary.

        stn_info: An instance of weewx.station.StationInfo, with static
                  station information.

        record: The current archive record [Optional; default is None]

        gen_ts: The timestamp for which the output is to be current
        [Optional; default is the last time in the database]

        first_run: True if this is the first time the report engine has been
        run.  If this is the case, then any 'one time' events should be done.
        """
        threading.Thread.__init__(self, name="ReportThread")

        self.config_dict = config_dict
        self.stn_info = stn_info
        self.record = record
        self.gen_ts = gen_ts
        self.first_run = first_run

    def run(self):
        """This is where the actual work gets done.

        Runs through the list of reports. """

        if self.gen_ts:
            syslog.syslog(syslog.LOG_DEBUG,
                          "reportengine: Running reports for time %s" %
                          weeutil.weeutil.timestamp_to_string(self.gen_ts))
        else:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: "
                          "Running reports for latest time in the database.")

        # Iterate over each requested report
        for report in self.config_dict['StdReport'].sections:
            # See if this report is disabled
            enabled = to_bool(self.config_dict['StdReport'][report].get('enable', True))
            if not enabled:
                syslog.syslog(syslog.LOG_DEBUG,
                              "reportengine: Skipping report %s" % report)
                continue

            syslog.syslog(syslog.LOG_DEBUG,
                          "reportengine: Running report %s" % report)

            # Figure out where the configuration file is for the skin used for
            # this report:
            skin_config_path = os.path.join(
                self.config_dict['WEEWX_ROOT'],
                self.config_dict['StdReport']['SKIN_ROOT'],
                self.config_dict['StdReport'][report].get('skin', 'Standard'),
                'skin.conf')

            # Retrieve the configuration dictionary for the skin. Wrap it in
            # a try block in case we fail
            try:
                skin_dict = configobj.ConfigObj(skin_config_path, file_error=True)
                syslog.syslog(
                    syslog.LOG_DEBUG,
                    "reportengine: Found configuration file %s for report %s" %
                    (skin_config_path, report))
            except IOError, e:
                syslog.syslog(
                    syslog.LOG_ERR, "reportengine: "
                    "Cannot read skin configuration file %s for report %s: %s"
                    % (skin_config_path, report, e))
                syslog.syslog(syslog.LOG_ERR, "        ****  Report ignored")
                continue
            except SyntaxError, e:
                syslog.syslog(
                    syslog.LOG_ERR, "reportengine: "
                    "Failed to read skin configuration file %s for report %s: %s"
                    % (skin_config_path, report, e))
                syslog.syslog(syslog.LOG_ERR, "        ****  Report ignored")
                continue

            # Add the default database binding:
            skin_dict.setdefault('data_binding', 'wx_binding')

            # Default to logging to whatever is specified at the root level
            # of weewx.conf, or true if nothing specified:
            skin_dict.setdefault('log_success',
                                 self.config_dict.get('log_success', True))
            skin_dict.setdefault('log_failure',
                                 self.config_dict.get('log_failure', True))

            # Inject any overrides the user may have specified in the
            # weewx.conf configuration file for all reports:
            for scalar in self.config_dict['StdReport'].scalars:
                skin_dict[scalar] = self.config_dict['StdReport'][scalar]

            # Now inject any overrides for this specific report:
            skin_dict.merge(self.config_dict['StdReport'][report])

            # Finally, add the report name:
            skin_dict['REPORT_NAME'] = report

            # Default action is to run the report. Only reason to not run it is
            # if we have a valid report report_timing and it did not trigger.
            if self.record is not None:
                # StdReport called us not wee_reports so look for a report_timing
                # entry if we have one.
                timing_line = skin_dict.get('report_timing', None)
                # The report_timing entry might have one or more comma separated
                # values which ConfigObj would interpret as a list. If so then
                # reconstruct our report_timing entry.
                if hasattr(timing_line, '__iter__'):
                    timing_line = ','.join(timing_line)
                if timing_line:
                    # Get a ReportTiming object.
                    timing = ReportTiming(timing_line)
                    if timing.is_valid:
                        # Get timestamp and interval so we can check if the
                        # report timing is triggered.
                        _ts = self.record['dateTime']
                        _interval = self.record['interval'] * 60
                        # Is our report timing triggered? timing.is_triggered
                        # returns True if triggered, False if not triggered
                        # and None if an invalid report timing line.
                        if timing.is_triggered(_ts, _ts - _interval) is False:
                            # report timing was valid but not triggered so do
                            # not run the report.
                            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Report %s skipped due to report_timing setting" %
                                          (report, ))
                            continue
                    else:
                        syslog.syslog(syslog.LOG_DEBUG, "reportengine: Invalid report_timing setting for report '%s', running report anyway" % report)
                        syslog.syslog(syslog.LOG_DEBUG, "        ****  %s" % timing.validation_error)

            for generator in weeutil.weeutil.option_as_list(skin_dict['Generators'].get('generator_list')):

                try:
                    # Instantiate an instance of the class.
                    obj = weeutil.weeutil._get_object(generator)(
                        self.config_dict,
                        skin_dict,
                        self.gen_ts,
                        self.first_run,
                        self.stn_info,
                        self.record)
                except Exception, e:
                    syslog.syslog(
                        syslog.LOG_CRIT, "reportengine: "
                        "Unable to instantiate generator %s" % generator)
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % e)
                    weeutil.weeutil.log_traceback("        ****  ")
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator ignored")
                    traceback.print_exc()
                    continue

                try:
                    # Call its start() method
                    obj.start()

                except Exception, e:
                    # Caught unrecoverable error. Log it, continue on to the
                    # next generator.
                    syslog.syslog(
                        syslog.LOG_CRIT, "reportengine: "
                        "Caught unrecoverable exception in generator %s"
                        % generator)
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % str(e))
                    weeutil.weeutil.log_traceback("        ****  ")
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator terminated")
                    traceback.print_exc()
                    continue

                finally:
                    obj.finalize()

# =============================================================================
#                    Class ReportGenerator
# =============================================================================

class ReportGenerator(object):
    """Base class for all report generators."""
    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info, record):
        self.config_dict = config_dict
        self.skin_dict = skin_dict
        self.gen_ts = gen_ts
        self.first_run = first_run
        self.stn_info = stn_info
        self.record = record
        self.db_binder = weewx.manager.DBBinder(self.config_dict)

    def start(self):
        self.run()

    def run(self):
        pass

    def finalize(self):
        self.db_binder.close()


# =============================================================================
#                    Class FtpGenerator
# =============================================================================

class FtpGenerator(ReportGenerator):
    """Class for managing the "FTP generator".

    This will ftp everything in the public_html subdirectory to a webserver."""

    def run(self):
        import weeutil.ftpupload

        # determine how much logging is desired
        log_success = to_bool(self.skin_dict.get('log_success', True))

        t1 = time.time()
        if 'HTML_ROOT' in self.skin_dict:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict['HTML_ROOT'])
        else:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.config_dict['StdReport']['HTML_ROOT'])

        try:
            ftp_data = weeutil.ftpupload.FtpUpload(
                server=self.skin_dict['server'],
                user=self.skin_dict['user'],
                password=self.skin_dict['password'],
                local_root=local_root,
                remote_root=self.skin_dict['path'],
                port=int(self.skin_dict.get('port', 21)),
                name=self.skin_dict['REPORT_NAME'],
                passive=to_bool(self.skin_dict.get('passive', True)),
                max_tries=int(self.skin_dict.get('max_tries', 3)),
                secure=to_bool(self.skin_dict.get('secure_ftp', False)),
                debug=int(self.skin_dict.get('debug', 0)))
        except Exception:
            syslog.syslog(syslog.LOG_DEBUG,
                          "ftpgenerator: FTP upload not requested. Skipped.")
            return

        try:
            n = ftp_data.run()
        except (socket.timeout, socket.gaierror, ftplib.all_errors, IOError), e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "ftpgenerator: "
                          "Caught exception %s: %s" % (cl, e))
            weeutil.weeutil.log_traceback("        ****  ")
            return

        t2 = time.time()
        if log_success:
            syslog.syslog(syslog.LOG_INFO,
                          "ftpgenerator: ftp'd %d files in %0.2f seconds" %
                          (n, (t2 - t1)))


# =============================================================================
#                    Class RsynchGenerator
# =============================================================================

class RsyncGenerator(ReportGenerator):
    """Class for managing the "rsync generator".

    This will rsync everything in the public_html subdirectory to a server."""

    def run(self):
        import weeutil.rsyncupload
        # We don't try to collect performance statistics about rsync, because
        # rsync will report them for us.  Check the debug log messages.
        try:
            if 'HTML_ROOT' in self.skin_dict:
                html_root = self.skin_dict['HTML_ROOT']
            else:
                html_root = self.config_dict['StdReport']['HTML_ROOT']
            rsync_data = weeutil.rsyncupload.RsyncUpload(
                local_root=os.path.join(self.config_dict['WEEWX_ROOT'], html_root),
                remote_root=self.skin_dict['path'],
                server=self.skin_dict['server'],
                user=self.skin_dict.get('user'),
                port=self.skin_dict.get('port'),
                ssh_options=self.skin_dict.get('ssh_options'),
                compress=to_bool(self.skin_dict.get('compress', False)),
                delete=to_bool(self.skin_dict.get('delete', False)),
                log_success=to_bool(self.skin_dict.get('log_success', True)))
        except Exception:
            syslog.syslog(syslog.LOG_DEBUG,
                          "rsyncgenerator: rsync upload not requested. Skipped.")
            return

        try:
            rsync_data.run()
        except IOError, e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "rsyncgenerator: "
                          "Caught exception %s: %s" % (cl, e))


# =============================================================================
#                    Class CopyGenerator
# =============================================================================

class CopyGenerator(ReportGenerator):
    """Class for managing the 'copy generator.'

    This will copy files from the skin subdirectory to the public_html
    subdirectory."""

    def run(self):
        copy_dict = self.skin_dict['CopyGenerator']
        # determine how much logging is desired
        log_success = to_bool(copy_dict.get('log_success', True))

        copy_list = []

        if self.first_run:
            # Get the list of files to be copied only once, at the first
            # invocation of the generator. Wrap in a try block in case the
            # list does not exist.
            try:
                copy_list += weeutil.weeutil.option_as_list(copy_dict['copy_once'])
            except KeyError:
                pass

        # Get the list of files to be copied everytime. Again, wrap in a
        # try block.
        try:
            copy_list += weeutil.weeutil.option_as_list(copy_dict['copy_always'])
        except KeyError:
            pass

        # Change directory to the skin subdirectory:
        os.chdir(os.path.join(self.config_dict['WEEWX_ROOT'],
                              self.skin_dict['SKIN_ROOT'],
                              self.skin_dict['skin']))
        # Figure out the destination of the files
        html_dest_dir = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     self.skin_dict['HTML_ROOT'])

        # The copy list can contain wildcard characters. Go through the
        # list globbing any character expansions
        ncopy = 0
        for pattern in copy_list:
            # Glob this pattern; then go through each resultant filename:
            for _file in glob.glob(pattern):
                # Final destination is the join of the html destination
                # directory and any relative subdirectory on the filename:
                dest_dir = os.path.join(html_dest_dir, os.path.dirname(_file))
                # Make the destination directory, wrapping it in a try block in
                # case it already exists:
                try:
                    os.makedirs(dest_dir)
                except OSError:
                    pass
                # This version of copy does not copy over modification time,
                # so it will look like a new file, causing it to be (for
                # example) ftp'd to the server:
                shutil.copy(_file, dest_dir)
                ncopy += 1

        if log_success:
            syslog.syslog(syslog.LOG_INFO, "copygenerator: "
                          "copied %d files to %s" % (ncopy, html_dest_dir))

# ===============================================================================
#                    Class ReportTiming
# ===============================================================================

class ReportTiming(object):
    """Class for processing a CRON like line and determining whether it should
    be fired for a given time.

    The following CRON like capabilities are supported:
    - There are two ways to specify the day the line is fired, DOM and DOW. A
      match on either all other fields and either DOM or DOW will casue the
      line to be fired.
    - first-last, *. Matches all possible values for the field concerned.
    - step, /x. Matches every xth minute/hour/day etc. May be bounded by a list
      or range.
    - range, lo-hi. Matches all values from lo to hi inclusive. Ranges using
      month and day names are not supported.
    - lists, x,y,z. Matches those items in the list. List items may be a range.
      Lists using month and day names are not supported.
    - month names. Months may be specified by number 1..12 or first 3 (case
      insensitive) letters of the English month name jan..dec.
    - weekday names. Weekday names may be specified by number 0..7
      (0,7 = Sunday) or first 3 (case insensitive) letters of the English
      weekday names sun..sat.
    - nicknames. Following nicknames are supported:
        @yearly   : Run once a year,  ie "0 0 1 1 *"
        @annually : Run once a year,  ie "0 0 1 1 *"
        @monthly  : Run once a month, ie "0 0 1 * *"
        @weekly   : Run once a week,  ie "0 0 * * 0"
        @daily    : Run once a day,   ie "0 0 * * *"
        @hourly   : Run once an hour, ie "0 * * * *"

    Useful ReportTiming class attributes:

    is_valid:         Whether passed line is a valid line or not.
    validation_error: Error message if passed line is an invalid line.
    raw_line:         Raw line data passed to ReportTiming.
    line:             5 item list representing the 5 date/time fields after the
                      raw line has been processed and dom/dow named parameters
                      replaced with numeric equivalents.
    """

    def __init__(self, line):
        """Initialises a ReportTiming object.

        Processes raw line to produce 5 field line suitable for further
        processing.

        line:  The raw line to be processed.
        """

        # initialise some properties
        self.is_valid = None
        self.validation_error = None
        self.raw_line = line.strip()
        # do some basic checking of the line for unsupported characters
        for unsupported_char in ('%', '#', 'L', 'W'):
            if unsupported_char in line:
                self.is_valid = False
                self.validation_error = "Unsupported character '%s' in '%s'." % (unsupported_char,
                                                                                 line)
                return
        # six special time defintion 'nicknames' are supported which replace
        # the line elements with pre-detemined values. These nicknames start
        # with the @ character. Check for any of these nicknames and substitute
        # the corresponding line.
        for nickname, nn_line in NICKNAME_MAP.iteritems():
            if line == nickname:
                line = nn_line
                break
        fields = line.split(None, 5)
        if len(fields) < 5:
            # Not enough fields
            self.is_valid = False
            self.validation_error = "Insufficient fields found in '%s'" % line
            return
        elif len(fields) == 5:
            fields.append(None)
        # Extract individual line elements
        minutes, hours, dom, months, dow, _extra = fields
        # Save individual fields
        self.line = [minutes, hours, dom, months, dow]
        # Is DOM restricted ie is DOM not '*'
        self.dom_restrict = self.line[2] != '*'
        # Is DOW restricted ie is DOW not '*'
        self.dow_restrict = self.line[4] != '*'
        # Decode the line and generate a set of possible values for each field
        (self.is_valid, self.validation_error) = self.decode()

    def decode(self):
        """Decode each field and store the sets of valid values.

        Set of valid values is stored in self.decode. Self.decode can only be
        considered valid if self.is_valid is True. Returns a 2-way tuple
        (True|False, ERROR MESSAGE). First item is True is the line is valid
        otherwise False. ERROR MESSAGE is None if the line is valid otherwise a
        string containing a short error message.
        """

        # set a list to hold our decoded ranges
        self.decode = []
        try:
            # step through each field and its associated range, names and maps
            for field, span, names, mapp in zip(self.line, SPANS, NAMES, MAPS):
                field_set = self.parse_field(field, span, names, mapp)
                self.decode.append(field_set)
            # if we are this far then our line is valid so return True and no
            # error message
            return (True, None)
        except ValueError, e:
            # we picked up a ValueError in self.parse_field() so return False
            # and the error message
            return (False, e)

    def parse_field(self, field, span, names, mapp, is_rorl=False):
        """Return the set of valid values for a field.

        Parses and validates a field and if the field is valid returns a set
        containing all of the possible field values. Called recursively to
        parse sub-fields (eg lists of ranges). If a field is invalid a
        ValueError is raised.

        field:   String containing the raw field to be parsed.
        span:    Tuple representing the lower and upper numeric values the
                 field may take. Format is (lower, upper).
        names:   Tuple containing all valid named values for the field. For
                 numeric only fields the tuple is empty.
        mapp:    Tuple of 2 way tuples mapping named values to numeric
                 equivalents. Format is ((name1, numeric1), ..
                 (namex, numericx)). For numeric only fields the tuple is empty.
        is_rorl: Is field part of a range or list. Either True or False.
        """

        field = field.strip()
        if field == '*':  # first-last
            # simply return a set of all poss values
            return set(xrange(span[0], span[1] + 1))
        elif field.isdigit():  # just a number
            # If its a DOW then replace any 7s with 0
            _field = field.replace('7','0') if span == DOW else field
            # its valid if its within our span
            if span[0] <= int(_field) <= span[1]:
                # it's valid so return the field itself as a set
                return set((int(_field), ))
            else:
                # invalid field value so raise ValueError
                raise ValueError("Invalid field value '%s' in '%s'" % (field,
                                                                       self.raw_line))
        elif field.lower() in names:  # an abbreviated name
            # abbreviated names are only valid if not used in a range or list
            if not is_rorl:
                # replace all named values with numbers
                _field = field
                for _name, _ord in mapp:
                    _field = _field.replace(_name, str(_ord))
                # its valid if its within our span
                if span[0] <= int(_field) <= span[1]:
                    # it's valid so return the field itself as a set
                    return set((int(_field), ))
                else:
                    # invalid field value so raise ValueError
                    raise ValueError("Invalid field value '%s' in '%s'" % (field,
                                                                           self.raw_line))
            else:
                # invalid use of abbreviated name so raise ValueError
                raise ValueError("Invalid use of abbreviated name '%s' in '%s'" % (field,
                                                                                   self.raw_line))
        elif ',' in field:  # we have a list
            # get the first list item and the rest of the list
            _first, _rest = field.split(',', 1)
            # get _first as a set using a recursive call
            _first_set = self.parse_field(_first, span, names, mapp, True)
            # get _rest as a set using a recursive call
            _rest_set = self.parse_field(_rest, span, names, mapp, True)
            # return the union of the _first and _rest sets
            return _first_set | _rest_set
        elif '/' in field:  # a step
            # get the value and the step
            _val, _step = field.split('/', 1)
            # step is valid if it is numeric
            if _step.isdigit():
                # get _val as a set using a recursive call
                _val_set = self.parse_field(_val, span, names, mapp, True)
                # get the set of all possible values using _step
                _lowest = min(_val_set)
                _step_set = set([x for x in _val_set if ((x - _lowest) % int(_step) == 0)])
                # return the intersection of the _val and _step sets
                return _val_set & _step_set
            else:
                # invalid step so raise ValueError
                raise ValueError("Invalid step value '%s' in '%s'" % (field,
                                                                      self.raw_line))
        elif '-' in field:  # we have a range
            # get the lo and hi values of the range
            lo, hi = field.split('-', 1)
            # if lo is numeric and in the span range then the range is valid if
            # hi is valid
            if lo.isdigit() and span[0] <= int(lo) <= span[1]:
                # if hi is numeric and in the span range and greater than or
                # equal to lo then the range is valid
                if hi.isdigit() and int(hi) >= int(lo) and span[0] <= int(hi) <= span[1]:
                    # valid range so return a set of the range
                    return set(xrange(int(lo), int(hi) + 1))
                else:
                    # something is wrong, we have an invalid field
                    raise ValueError("Invalid range specification '%s' in '%s'" % (field,
                                                                                   self.raw_line))
            else:
                # something is wrong with lo, we have an invalid field
                raise ValueError("Invalid range specification '%s' in '%s'" % (field,
                                                                               self.raw_line))
        else:
            # we have something I don't know how to parse so raise a ValueError
            raise ValueError("Invalid field '%s' in '%s'" % (field,
                                                             self.raw_line))

    def is_triggered(self, ts_hi, ts_lo=None):
        """Determine if CRON like line is to be triggered.

        Return True if line is triggered between timestamps ts_lo and ts_hi
        (exclusivie on ts_lo inclusive on ts_hi), False if it is not
        triggered or None if the line is invalid or ts_hi is not valid.
        If ts_lo is not specified check for triggering on ts_hi only.

        ts_hi:  Timestamp of latest time to be checked for triggering.
        ts_lo:  Timestamp used for earliest time in range of times to be
                checked for triggering. May be ommitted in which case only
                ts_hi is checked.
        """

        if self.is_valid and ts_hi is not None:
            # setup ts range to iterate over
            if ts_lo is None:
                _range = [int(ts_hi)]
            else:
                # CRON like line has a 1 min resolution so step backwards every
                # 60 sec.
                _range = range(int(ts_hi), int(ts_lo), -60)
            # Iterate through each ts in our range. All we need is one ts that
            # triggers the line.
            for _ts in _range:
                # convert ts to timetuple and extract required data
                trigger_dt = datetime.datetime.fromtimestamp(_ts)
                trigger_tt = trigger_dt.timetuple()
                month, dow, day, hour, minute = (trigger_tt.tm_mon,
                                                (trigger_tt.tm_wday + 1) % 7,
                                                trigger_tt.tm_mday,
                                                trigger_tt.tm_hour,
                                                trigger_tt.tm_min)
                # construct a tuple so we can iterate over and process each
                # field
                element_tuple = zip((minute, hour, day, month, dow),
                                    self.line,
                                    SPANS,
                                    self.decode)
                # Iterate over each field and check if it will prevent
                # triggering. Remember, we only need a match on either DOM or
                # DOW but all other fields must match.
                dom_match = False
                dom_restricted_match = False
                for period, _field, field_span, decode in element_tuple:
                    if period in decode:
                        # we have a match
                        if field_span == DOM:
                            # we have a match on DOM but we need to know if it
                            # was a match on a restricted DOM field
                            dom_match = True
                            dom_restricted_match = self.dom_restrict
                        elif field_span == DOW and not(dom_restricted_match or self.dow_restrict or dom_match):
                            break
                        continue
                    elif field_span == DOW and dom_restricted_match or field_span == DOM:
                        # No match but consider it a match if this field is DOW
                        # and we already have a DOM match. Also, if we didn't
                        # match on DOM then continue as we might match on DOW.
                        continue
                    else:
                        # The field will prevent the line from triggerring for
                        # this ts so we break and move to the next ts.
                        break
                else:
                    # If we arrived here then all fields match and the line
                    # would be triggered on this ts so return True.
                    return True
            # If we are here it is becasue we broke out of all inner for loops
            # and the line was not triggered so return False.
            return False
        else:
            # Our line is not valid or we do not have a timestamp to use,
            # return None
            return None
