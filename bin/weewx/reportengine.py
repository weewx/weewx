#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Engine for generating reports"""

from __future__ import absolute_import

# System imports:
import datetime
import ftplib
import glob
import logging
import os.path
import threading
import time
import traceback

# 3rd party imports
import configobj
from six.moves import zip

# WeeWX imports:
import weeutil.config
import weeutil.logger
import weeutil.weeutil
import weewx.defaults
import weewx.manager
import weewx.units
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)

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
MONTH_NAME_MAP = list(zip(('jan', 'feb', 'mar', 'apr',
                           'may', 'jun', 'jul', 'aug',
                           'sep', 'oct', 'nov', 'dec'), list(range(1, 13))))
# map day names to day number
DAY_NAME_MAP = list(zip(('sun', 'mon', 'tue', 'wed',
                         'thu', 'fri', 'sat'), list(range(7))))
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
            log.debug("Running reports for time %s",
                      weeutil.weeutil.timestamp_to_string(self.gen_ts))
        else:
            log.debug("Running reports for latest time in the database.")

        # Iterate over each requested report
        for report in self.config_dict['StdReport'].sections:

            # Ignore the [[Defaults]] section
            if report == 'Defaults':
                continue

            # See if this report is disabled
            enabled = to_bool(self.config_dict['StdReport'][report].get('enable', True))
            if not enabled:
                log.debug("Report '%s' not enabled. Skipping.", report)
                continue

            log.debug("Running report '%s'", report)

            # Fetch and build the skin_dict:
            try:
                skin_dict = _build_skin_dict(self.config_dict, report)
            except SyntaxError as e:
                log.error("Syntax error: %s", e)
                log.error("   ****       Report ignored")
                continue

            # Default action is to run the report. Only reason to not run it is
            # if we have a valid report report_timing and it did not trigger.
            if self.record:
                # StdReport called us not wee_reports so look for a report_timing
                # entry if we have one.
                timing_line = skin_dict.get('report_timing')
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
                            log.debug("Report '%s' skipped due to report_timing setting", report)
                            continue
                    else:
                        log.debug("Invalid report_timing setting for report '%s', "
                                  "running report anyway", report)
                        log.debug("       ****  %s", timing.validation_error)

            if 'Generators' in skin_dict and 'generator_list' in skin_dict['Generators']:
                for generator in weeutil.weeutil.option_as_list(skin_dict['Generators']['generator_list']):

                    try:
                        # Instantiate an instance of the class.
                        obj = weeutil.weeutil.get_object(generator)(
                            self.config_dict,
                            skin_dict,
                            self.gen_ts,
                            self.first_run,
                            self.stn_info,
                            self.record)
                    except Exception as e:
                        log.error("Unable to instantiate generator '%s'", generator)
                        log.error("        ****  %s", e)
                        weeutil.logger.log_traceback(log.error, "        ****  ")
                        log.error("        ****  Generator ignored")
                        traceback.print_exc()
                        continue

                    try:
                        # Call its start() method
                        obj.start()

                    except Exception as e:
                        # Caught unrecoverable error. Log it, continue on to the
                        # next generator.
                        log.error("Caught unrecoverable exception in generator '%s'", generator)
                        log.error("        ****  %s", e)
                        weeutil.logger.log_traceback(log.error, "        ****  ")
                        log.error("        ****  Generator terminated")
                        traceback.print_exc()
                        continue

                    finally:
                        obj.finalize()
            else:
                log.debug("No generators specified for report '%s'", report)


def _build_skin_dict(config_dict, report):
    """Find and build the skin_dict for the given report"""

    #######################################################################
    # Start with the defaults in the defaults module. Because we will be modifying it, we need
    # to make a deep copy.
    skin_dict = weeutil.config.deep_copy(weewx.defaults.defaults)

    # Turn off interpolation for the copy. It will interfere with interpretation of delta
    # time fields
    skin_dict.interpolation = False
    # Add the report name:
    skin_dict['REPORT_NAME'] = report

    #######################################################################
    # Add in the global values for log_success and log_failure:
    if 'log_success' in config_dict:
        skin_dict['log_success'] = to_bool(config_dict['log_success'])
    if 'log_failure' in config_dict:
        skin_dict['log_failure'] = to_bool(config_dict['log_failure'])

    #######################################################################
    # Now add the options in the report's skin.conf file.
    # Start by figuring out where it is located.
    skin_config_path = os.path.join(
        config_dict['WEEWX_ROOT'],
        config_dict['StdReport']['SKIN_ROOT'],
        config_dict['StdReport'][report].get('skin', ''),
        'skin.conf')

    # Retrieve the configuration dictionary for the skin. Wrap it in a try block in case we
    # fail.  It is ok if there is no file - everything for a skin might be defined in the weewx
    # configuration.
    try:
        merge_dict = configobj.ConfigObj(skin_config_path,
                                         encoding='utf-8',
                                         interpolation=False,
                                         file_error=True)
    except IOError as e:
        log.debug("Cannot read skin configuration file %s for report '%s': %s",
                  skin_config_path, report, e)
    except SyntaxError as e:
        log.error("Failed to read skin configuration file %s for report '%s': %s",
                  skin_config_path, report, e)
        raise
    else:
        log.debug("Found configuration file %s for report '%s'", skin_config_path, report)
        # If a language is specified, honor it.
        if 'lang' in merge_dict:
            merge_lang(merge_dict['lang'], config_dict, report, skin_dict)
        # If the file has a unit_system specified, honor it.
        if 'unit_system' in merge_dict:
            merge_unit_system(merge_dict['unit_system'], skin_dict)
        # Merge the rest of the config file in:
        weeutil.config.merge_config(skin_dict, merge_dict)

    #######################################################################
    # Merge in the [[Defaults]] section
    if 'Defaults' in config_dict['StdReport']:
        # Because we will be modifying the results, make a deep copy of the section.
        merge_dict = weeutil.config.deep_copy(config_dict)['StdReport']['Defaults']
        # If a language is specified, honor it
        if 'lang' in merge_dict:
            merge_lang(merge_dict['lang'], config_dict, report, skin_dict)
        # If a unit_system is specified, honor it
        if 'unit_system' in merge_dict:
            merge_unit_system(merge_dict['unit_system'], skin_dict)
        weeutil.config.merge_config(skin_dict, merge_dict)

    # Any scalar overrides have lower-precedence than report-specific options, so do them now.
    for scalar in config_dict['StdReport'].scalars:
        skin_dict[scalar] = config_dict['StdReport'][scalar]

    # Finally the report-specific section.
    if report in config_dict['StdReport']:
        # Because we will be modifying the results, make a deep copy of the section.
        merge_dict = weeutil.config.deep_copy(config_dict)['StdReport'][report]
        # If a language is specified, honor it
        if 'lang' in merge_dict:
            merge_lang(merge_dict['lang'], config_dict, report, skin_dict)
        # If a unit_system is specified, honor it
        if 'unit_system' in merge_dict:
            merge_unit_system(merge_dict['unit_system'], skin_dict)
        weeutil.config.merge_config(skin_dict, merge_dict)

    return skin_dict


def merge_unit_system(report_units_base, skin_dict):
    """
    Given a unit system, merge its unit groups into a configuration dictionary
    Args:
        report_units_base (str): A unit base (such as 'us', or 'metricwx')
        skin_dict (dict): A configuration dictionary

    Returns:
        None
    """
    report_units_base = report_units_base.upper()
    # Get the chosen unit system out of units.py, then merge it into skin_dict.
    units_dict = weewx.units.std_groups[
        weewx.units.unit_constants[report_units_base]]
    skin_dict['Units']['Groups'].update(units_dict)


def get_lang_dict(lang_spec, config_dict, report):
    """Given a language specification, return its corresponding locale dictionary. """

    # The language's corresponding locale file will be found in subdirectory 'lang', with
    # a suffix '.conf'. Find the path to it:.
    lang_config_path = os.path.join(
        config_dict['WEEWX_ROOT'],
        config_dict['StdReport']['SKIN_ROOT'],
        config_dict['StdReport'][report].get('skin', ''),
        'lang',
        lang_spec+'.conf')

    # Retrieve the language dictionary for the skin and requested language. Wrap it in a
    # try block in case we fail.  It is ok if there is no file - everything for a skin
    # might be defined in the weewx configuration.
    try:
        lang_dict = configobj.ConfigObj(lang_config_path,
                                        encoding='utf-8',
                                        interpolation=False,
                                        file_error=True)
    except IOError as e:
        log.debug("Cannot read localization file %s for report '%s': %s",
                  lang_config_path, report, e)
        log.debug("**** Using defaults instead.")
        lang_dict = configobj.ConfigObj({},
                                        encoding='utf-8',
                                        interpolation=False)
    except SyntaxError as e:
        log.error("Syntax error while reading localization file %s for report '%s': %s",
                  lang_config_path, report, e)
        raise

    if 'Texts' not in lang_dict:
        lang_dict['Texts'] = {}

    return lang_dict


def merge_lang(lang_spec, config_dict, report, skin_dict):

    lang_dict = get_lang_dict(lang_spec, config_dict, report)
    # There may or may not be a unit system specified. If so, honor it.
    if 'unit_system' in lang_dict:
        merge_unit_system(lang_dict['unit_system'], skin_dict)
    weeutil.config.merge_config(skin_dict, lang_dict)
    return skin_dict


# =============================================================================
#                    Class ReportGenerator
# =============================================================================

class ReportGenerator(object):
    """Base class for all report generators."""

    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info, record=None):
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
        log_success = to_bool(weeutil.config.search_up(self.skin_dict, 'log_success', True))
        log_failure = to_bool(weeutil.config.search_up(self.skin_dict, 'log_failure', True))

        t1 = time.time()
        try:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict.get('HTML_ROOT', self.config_dict['StdReport']['HTML_ROOT']))
            ftp_data = weeutil.ftpupload.FtpUpload(
                server=self.skin_dict['server'],
                user=self.skin_dict['user'],
                password=self.skin_dict['password'],
                local_root=local_root,
                remote_root=self.skin_dict['path'],
                port=int(self.skin_dict.get('port', 21)),
                name=self.skin_dict['REPORT_NAME'],
                passive=to_bool(self.skin_dict.get('passive', True)),
                secure=to_bool(self.skin_dict.get('secure_ftp', False)),
                debug=weewx.debug,
                secure_data=to_bool(self.skin_dict.get('secure_data', True)),
                reuse_ssl=to_bool(self.skin_dict.get('reuse_ssl', False)),
                encoding=self.skin_dict.get('ftp_encoding', 'utf-8')
            )
        except KeyError:
            log.debug("ftpgenerator: FTP upload not requested. Skipped.")
            return

        max_tries = int(self.skin_dict.get('max_tries', 3))
        for count in range(max_tries):
            try:
                n = ftp_data.run()
            except ftplib.all_errors as e:
                log.error("ftpgenerator: (%d): caught exception '%s': %s", count, type(e), e)
                weeutil.logger.log_traceback(log.error, "        ****  ")
            else:
                if log_success:
                    t2 = time.time()
                    log.info("ftpgenerator: Ftp'd %d files in %0.2f seconds", n, (t2 - t1))
                break
        else:
            # The loop completed normally, meaning the upload failed.
            if log_failure:
                log.error("ftpgenerator: Upload failed")


# =============================================================================
#                    Class RsyncGenerator
# =============================================================================

class RsyncGenerator(ReportGenerator):
    """Class for managing the "rsync generator".

    This will rsync everything in the public_html subdirectory to a server."""

    def run(self):
        import weeutil.rsyncupload
        log_success = to_bool(weeutil.config.search_up(self.skin_dict, 'log_success', True))
        log_failure = to_bool(weeutil.config.search_up(self.skin_dict, 'log_failure', True))

        # We don't try to collect performance statistics about rsync, because
        # rsync will report them for us.  Check the debug log messages.
        try:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict.get('HTML_ROOT', self.config_dict['StdReport']['HTML_ROOT']))
            rsync_data = weeutil.rsyncupload.RsyncUpload(
                local_root=local_root,
                remote_root=self.skin_dict['path'],
                server=self.skin_dict['server'],
                user=self.skin_dict.get('user'),
                port=to_int(self.skin_dict.get('port')),
                ssh_options=self.skin_dict.get('ssh_options'),
                compress=to_bool(self.skin_dict.get('compress', False)),
                delete=to_bool(self.skin_dict.get('delete', False)),
                log_success=log_success,
                log_failure=log_failure
            )
        except KeyError:
            log.debug("rsyncgenerator: Rsync upload not requested. Skipped.")
            return

        try:
            rsync_data.run()
        except IOError as e:
            log.error("rsyncgenerator: Caught exception '%s': %s", type(e), e)


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
        log_success = to_bool(weeutil.config.search_up(copy_dict, 'log_success', True))

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
            # Glob this pattern; then go through each resultant path:
            for path in glob.glob(pattern):
                ncopy += weeutil.weeutil.deep_copy_path(path, html_dest_dir)
        if log_success:
            log.info("Copied %d files to %s", ncopy, html_dest_dir)


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

    def __init__(self, raw_line):
        """Initialises a ReportTiming object.

        Processes raw line to produce 5 field line suitable for further
        processing.

        raw_line: The raw line to be processed.
        """

        # initialise some properties
        self.is_valid = None
        self.validation_error = None
        # To simplify error reporting keep a copy of the raw line passed to us
        # as a string. The raw line could be a list if it included any commas.
        # Assume a string but catch the error if it is a list and join the list
        # elements to make a string
        try:
            line_str = raw_line.strip()
        except AttributeError:
            line_str = ','.join(raw_line).strip()
        self.raw_line = line_str
        # do some basic checking of the line for unsupported characters
        for unsupported_char in ('%', '#', 'L', 'W'):
            if unsupported_char in line_str:
                self.is_valid = False
                self.validation_error = "Unsupported character '%s' in '%s'." % (unsupported_char,
                                                                                 self.raw_line)
                return
        # Six special time definition 'nicknames' are supported which replace
        # the line elements with pre-determined values. These nicknames start
        # with the @ character. Check for any of these nicknames and substitute
        # the corresponding line.
        for nickname, nn_line in NICKNAME_MAP.items():
            if line_str == nickname:
                line_str = nn_line
                break
        fields = line_str.split(None, 5)
        if len(fields) < 5:
            # Not enough fields
            self.is_valid = False
            self.validation_error = "Insufficient fields found in '%s'" % self.raw_line
            return
        elif len(fields) == 5:
            fields.append(None)
        # extract individual line elements
        minutes, hours, dom, months, dow, _extra = fields
        # save individual fields
        self.line = [minutes, hours, dom, months, dow]
        # is DOM restricted ie is DOM not '*'
        self.dom_restrict = self.line[2] != '*'
        # is DOW restricted ie is DOW not '*'
        self.dow_restrict = self.line[4] != '*'
        # decode the line and generate a set of possible values for each field
        (self.is_valid, self.validation_error) = self.decode_fields()

    def decode_fields(self):
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
        except ValueError as e:
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
            return set(range(span[0], span[1] + 1))
        elif field.isdigit():  # just a number
            # If its a DOW then replace any 7s with 0
            _field = field.replace('7', '0') if span == DOW else field
            # its valid if its within our span
            if span[0] <= int(_field) <= span[1]:
                # it's valid so return the field itself as a set
                return set((int(_field),))
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
                    return set((int(_field),))
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
                    return set(range(int(lo), int(hi) + 1))
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
        (exclusive on ts_lo inclusive on ts_hi), False if it is not
        triggered or None if the line is invalid or ts_hi is not valid.
        If ts_lo is not specified check for triggering on ts_hi only.

        ts_hi:  Timestamp of latest time to be checked for triggering.
        ts_lo:  Timestamp used for earliest time in range of times to be
                checked for triggering. May be omitted in which case only
                ts_hi is checked.
        """

        if self.is_valid and ts_hi is not None:
            # setup ts range to iterate over
            if ts_lo is None:
                _range = [int(ts_hi)]
            else:
                # CRON like line has a 1 min resolution so step backwards every
                # 60 sec.
                _range = list(range(int(ts_hi), int(ts_lo), -60))
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
                element_tuple = list(zip((minute, hour, day, month, dow),
                                         self.line,
                                         SPANS,
                                         self.decode))
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
                        elif field_span == DOW and not (dom_restricted_match or self.dow_restrict or dom_match):
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
            # If we are here it is because we broke out of all inner for loops
            # and the line was not triggered so return False.
            return False
        else:
            # Our line is not valid or we do not have a timestamp to use,
            # return None
            return None
