#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

"""Module providing the base classes and API for importing observational data
into WeeWX.
"""

# Python imports
import datetime
import logging
import numbers
import re
import sys
import time
from datetime import datetime as dt

# WeeWX imports
import weecfg
import weecfg.database
import weewx
import weewx.accum
import weewx.qc
import weewx.wxservices
from weeutil.weeutil import timestamp_to_string, option_as_list, to_int, tobool, get_object, \
    max_with_none
from weewx.manager import open_manager_with_config
from weewx.units import unit_constants, unit_nicknames, convertStd, to_std_system, ValueTuple

log = logging.getLogger(__name__)

# List of sources we support
SUPPORTED_SOURCES = ['CSV', 'WU', 'Cumulus', 'WD', 'WeatherCat', 'Ecowitt']


# ============================================================================
#                                Error Classes
# ============================================================================

class WeeImportOptionError(Exception):
    """Base class of exceptions thrown when encountering an error with a
       command line option.
    """


class WeeImportMapError(Exception):
    """Base class of exceptions thrown when encountering an error with an
       external source-to-WeeWX field map.
    """


class WeeImportIOError(Exception):
    """Base class of exceptions thrown when encountering an I/O error with an
       external source.
    """


class WeeImportFieldError(Exception):
    """Base class of exceptions thrown when encountering an error with a field
       from an external source.
    """


class WeeImportDecodeError(Exception):
    """Base class of exceptions thrown when encountering a decode error with an
       external source.
    """

# ============================================================================
#                                class Source
# ============================================================================

class Source(object):
    """Base class used for interacting with an external data source to import
    records into the WeeWX archive.

    __init__() must define the following properties:
        dry_run             - Is this a dry run (ie do not save imported records
                              to archive). [True|False].
        calc_missing        - Calculate any missing derived observations.
                              [True|False].
        ignore_invalid_data - Ignore any invalid data found in a source field.
                              [True|False].
        tranche             - Number of records to be written to archive in a
                              single transaction. Integer.
        interval            - Method of determining interval value if interval
                              field not included in data source.
                              ['config'|'derive'|x] where x is an integer.

    Child classes are used to interact with a specific source (eg CSV file,
    WU). Any such child classes must define a get_raw_data() method which:
        -   gets the raw observation data and returns an iterable yielding data
            dicts whose fields can be mapped to a WeeWX archive field
        -   defines an import data field-to-WeeWX archive field map (self.map)

        self.raw_datetime_format - Format of date time data field from which
                                   observation timestamp is to be derived. A
                                   string in Python datetime string format such
                                   as '%Y-%m-%d %H:%M:%S'. If the date time
                                   data field cannot be interpreted as a string
                                   wee_import attempts to interpret the field
                                   as a unix timestamp. If the field is not a
                                   valid unix timestamp an error is raised.
    """

    # reg expression to match any HTML tag of the form <...>
    _tags = re.compile(r'\<.*\>')

    special_processing_fields = ('dateTime', 'usUnits', 'interval')

    def __init__(self, config_dict, import_config_dict, **kwargs):
        """A generic initialisation.

        Set some realistic default values for options read from the import
        config file. Obtain objects to handle missing derived obs (if required)
        and QC on imported data. Parse any --date command line option, so we
        know what records to import.
        """

        # save our WeeWX config dict
        self.config_dict = config_dict

        # get our import config dict settings
        # interval, default to 'derive'
        self.interval = import_config_dict.get('interval', 'derive')
        # do we ignore invalid data, default to True
        self.ignore_invalid_data = tobool(import_config_dict.get('ignore_invalid_data',
                                                                 True))
        # tranche, default to 250
        self.tranche = to_int(import_config_dict.get('tranche', 250))
        # apply QC, default to True
        self.apply_qc = tobool(import_config_dict.get('qc', True))
        # calc-missing, default to True
        self.calc_missing = tobool(import_config_dict.get('calc_missing', True))
        # decimal separator, default to period '.'
        self.decimal_sep = import_config_dict.get('decimal', '.')

        # Some sources include UV index and solar radiation values even if no
        # sensor was present. The WeeWX convention is to store the None value
        # when a sensor or observation does not exist. Record whether UV and/or
        # solar radiation sensor was present.
        # UV, default to True
        self.UV_sensor = tobool(import_config_dict.get('UV_sensor', True))
        # solar, default to True
        self.solar_sensor = tobool(import_config_dict.get('solar_sensor', True))

        # initialise ignore extreme > 255.0 values for temperature and
        # humidity fields for WD imports
        self.ignore_extr_th = False

        self.db_binding_wx = get_binding(config_dict)
        self.dbm = open_manager_with_config(config_dict, self.db_binding_wx,
                                            initialize=True,
                                            default_binding_dict={'table_name': 'archive',
                                                                  'manager': 'weewx.wxmanager.DaySummaryManager',
                                                                  'schema': 'schemas.wview_extended.schema'})
        # get the unit system used in our db
        if self.dbm.std_unit_system is None:
            # we have a fresh archive (ie no records) so cannot deduce
            # the unit system in use, so go to our config_dict
            self.archive_unit_sys = unit_constants[self.config_dict['StdConvert'].get('target_unit',
                                                                                      'US')]
        else:
            # get our unit system from the archive db
            self.archive_unit_sys = self.dbm.std_unit_system

        # initialise the accum dict with any Accumulator config in the config
        # dict
        weewx.accum.initialize(self.config_dict)

        # get ourselves a QC object to do QC on imported records
        try:
            mm_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            mm_dict = {}
        self.import_QC = weewx.qc.QC(mm_dict)

        # process our command line options
        self.dry_run = kwargs['dry_run']
        self.verbose = kwargs['verbose']
        self.no_prompt = kwargs['no_prompt']
        self.suppress_warning = kwargs['suppress_warning']

        # By processing any --date, --from and --to options we need to derive
        # self.first_ts and self.last_ts; the earliest (exclusive) and latest
        # (inclusive) timestamps of data to be imported. If we have no --date,
        # --from or --to then set both to None (we then get the default action
        # for each import type).
        # First we see if we have a valid --date, if not then we look for
        # --from and --to.
        if kwargs['date'] or kwargs['date'] == "":
            # there is a --date but is it valid
            try:
                _first_dt = dt.strptime(kwargs['date'], "%Y-%m-%d")
            except ValueError:
                # Could not convert --date. If we have a --date it must be
                # valid otherwise we can't continue so raise it.
                _msg = "Invalid --date option specified."
                raise WeeImportOptionError(_msg)
            else:
                # we have a valid date so do some date arithmetic
                _last_dt = _first_dt + datetime.timedelta(days=1)
                self.first_ts = time.mktime(_first_dt.timetuple())
                self.last_ts = time.mktime(_last_dt.timetuple())
        elif kwargs['from_datetime'] or kwargs['to_datetime'] or kwargs['from_datetime'] == '' or kwargs['to_datetime'] == '':
            # There is a --from and/or a --to, but do we have both and are
            # they valid.
            # try --from first
            try:
                if 'T' in kwargs['from_datetime']:
                    _from_dt = dt.strptime(kwargs['from_datetime'], "%Y-%m-%dT%H:%M")
                else:
                    _from_dt = dt.strptime(kwargs['from_datetime'], "%Y-%m-%d")
                _from_ts = time.mktime(_from_dt.timetuple())
            except TypeError:
                # --from not specified we can't continue so raise it
                _msg = "Missing --from option. Both --from and --to must be specified."
                raise WeeImportOptionError(_msg)
            except ValueError:
                # could not convert --from, we can't continue so raise it
                _msg = "Invalid --from option."
                raise WeeImportOptionError(_msg)
            # try --to
            try:
                if 'T' in kwargs['to_datetime']:
                    _to_dt = dt.strptime(kwargs['to_datetime'], "%Y-%m-%dT%H:%M")
                else:
                    _to_dt = dt.strptime(kwargs['to_datetime'], "%Y-%m-%d")
                    # since it is just a date we want the end of the day
                    _to_dt += datetime.timedelta(days=1)
                _to_ts = time.mktime(_to_dt.timetuple())
            except TypeError:
                # --to not specified , we can't continue so raise it
                _msg = "Missing --to option. Both --from and --to must be specified."
                raise WeeImportOptionError(_msg)
            except ValueError:
                # could not convert --to, we can't continue so raise it
                _msg = "Invalid --to option."
                raise WeeImportOptionError(_msg)
            # If we made it here we have a _from_ts and _to_ts. Do a simple
            # error check first.
            if _from_ts > _to_ts:
                # from is later than to, raise it
                _msg = "--from value is later than --to value."
                raise WeeImportOptionError(_msg)
            self.first_ts = _from_ts
            self.last_ts = _to_ts
        else:
            # no --date or --from/--to so we take the default, set all to None
            self.first_ts = None
            self.last_ts = None

        # initialise a few properties we will need during the import
        # answer flags
        self.ans = None
        self.interval_ans = None
        # properties to help with processing multi-period imports
        self.period_no = None
        # total records processed
        self.total_rec_proc = 0
        # total unique records identified
        self.total_unique_rec = 0
        # total duplicate records identified
        self.total_duplicate_rec = 0
        # time we started to first save
        self.t1 = None
        # time taken to process
        self.tdiff = None
        # earliest timestamp imported
        self.earliest_ts = None
        # latest timestamp imported
        self.latest_ts = None

        # initialise two sets to hold timestamps of records for which we
        # encountered duplicates

        # duplicates seen over all periods
        self.duplicates = set()
        # duplicates seen over the current period
        self.period_duplicates = set()

    @staticmethod
    def source_factory(config_path, config_dict, import_config, **kwargs):
        """Factory to produce a Source object.

        Returns an appropriate object depending on the source type. Raises a
        weewx.UnsupportedFeature error if an object could not be created.
        """

        # get wee_import config dict if it exists
        import_config_path, import_config_dict = weecfg.read_config(None,
                                                                    None,
                                                                    file_name=import_config)
        # we should have a source parameter at the root of out import config
        # file, try to get it but be prepared to catch the error.
        try:
            source = import_config_dict['source']
        except KeyError:
            # we have no source parameter so check if we have a single source
            # config stanza, if we do then proceed using that
            _source_keys = [s for s in SUPPORTED_SOURCES if s in import_config_dict.keys]
            if len(_source_keys) == 1:
                # we have a single source config stanza so use that
                source = _source_keys[0]
            else:
                # there is no source parameter and we do not have a single
                # source config stanza so raise an error
                _msg = "Invalid 'source' parameter or no 'source' parameter specified in %s" % import_config_path
                raise weewx.UnsupportedFeature(_msg)
        # if we made it this far we have all we need to create an object
        module_class = '.'.join(['weeimport',
                                 source.lower() + 'import',
                                 source + 'Source'])
        return get_object(module_class)(config_path,
                                        config_dict,
                                        import_config_path,
                                        import_config_dict.get(source, {}),
                                        **kwargs)

    def run(self):
        """Main entry point for importing from an external source.

        Source data may be provided as a group of records over a single period
        (eg a single CSV file) or as a number of groups of records covering
        multiple periods(eg a WU multi-day import). Step through each group of
        records, getting the raw data, mapping the data and saving the data for
        each period.
        """

        # setup a counter to count the periods of records
        self.period_no = 1
        # obtain the lastUpdate metadata value before we import anything
        last_update = to_int(self.dbm._read_metadata('lastUpdate'))
        with self.dbm as archive:
            if self.first_period:
                # collect the time for some stats reporting later
                self.t1 = time.time()
                # it's convenient to give this message now
                if self.dry_run:
                    print('Starting dry run import ...')
                else:
                    print('Starting import ...')

            if self.first_period and not self.last_period:
                # there are more periods so say so
                print("Records covering multiple periods have been identified for import.")

            # step through our periods of records until we reach the end. A
            # 'period' of records may comprise the contents of a file, a day
            # of WU obs or a month of Cumulus obs
            for period in self.period_generator():

                # if we are importing multiple periods of data then tell the
                # user what period we are up to
                if not (self.first_period and self.last_period):
                    print("Period %d ..." % self.period_no)

                # get the raw data
                _msg = 'Obtaining raw import data for period %d ...' % self.period_no
                if self.verbose:
                    print(_msg)
                log.info(_msg)
                try:
                    _raw_data = self.get_raw_data(period)
                except WeeImportIOError as e:
                    print("**** Unable to load source data for period %d." % self.period_no)
                    log.info("**** Unable to load source data for period %d." % self.period_no)
                    print("**** %s" % e)
                    log.info("**** %s" % e)
                    print("**** Period %d will be skipped. "
                          "Proceeding to next period." % self.period_no)
                    log.info("**** Period %d will be skipped. "
                             "Proceeding to next period." % self.period_no)
                    # increment our period counter
                    self.period_no += 1
                    continue
                except WeeImportDecodeError as e:
                    print("**** Unable to decode source data for period %d." % self.period_no)
                    log.info("**** Unable to decode source data for period %d." % self.period_no)
                    print("**** %s" % e)
                    log.info("**** %s" % e)
                    print("**** Period %d will be skipped. "
                          "Proceeding to next period." % self.period_no)
                    log.info("**** Period %d will be skipped. "
                             "Proceeding to next period." % self.period_no)
                    print("**** Consider specifying the source file encoding "
                          "using the 'source_encoding' config option.")
                    log.info("**** Consider specifying the source file encoding "
                             "using the 'source_encoding' config option.")
                    # increment our period counter
                    self.period_no += 1
                    continue
                _msg = 'Raw import data read successfully for period %d.' % self.period_no
                if self.verbose:
                    print(_msg)
                log.info(_msg)

                # map the raw data to a WeeWX archive compatible dictionary
                _msg = 'Mapping raw import data for period %d ...' % self.period_no
                if self.verbose:
                    print(_msg)
                log.info(_msg)
                _mapped_data = self.map_raw_data(_raw_data, self.archive_unit_sys)
                _msg = 'Raw import data mapped successfully for period %d.' % self.period_no
                if self.verbose:
                    print(_msg)
                log.info(_msg)

                # save the mapped data to archive
                # first advise the user and log, but only if it's not a dry run
                if not self.dry_run:
                    _msg = 'Saving mapped data to archive for period %d ...' % self.period_no
                    if self.verbose:
                        print(_msg)
                    log.info(_msg)
                self.save_to_archive(archive, _mapped_data)
                # advise the user and log, but only if it's not a dry run
                if not self.dry_run:
                    _msg = 'Mapped data saved to archive successfully ' \
                           'for period %d.' % self.period_no
                    if self.verbose:
                        print(_msg)
                    log.info(_msg)
                # increment our period counter
                self.period_no += 1
            # The source data has been processed and any records saved to
            # archive (except if it was a dry run).

            # calculate the time taken for the import for our summary
            self.tdiff = time.time() - self.t1

            # now update the lastUpdate metadata field, set it to the max of
            # the timestamp of the youngest record imported and the value of
            # lastUpdate from before we started
            new_last_update = max_with_none((last_update, self.latest_ts))
            if new_last_update is not None:
                self.dbm._write_metadata('lastUpdate', str(int(new_last_update)))
            # If necessary, calculate  any missing derived fields and provide
            # the user with suitable summary output.
            if self.total_rec_proc == 0:
                # nothing was imported so no need to calculate any missing
                # fields just inform the user what was done
                _msg = 'No records were identified for import. Exiting. Nothing done.'
                print(_msg)
                log.info(_msg)
            else:
                # We imported something, but was it a dry run or not?
                total_rec = self.total_rec_proc + self.total_duplicate_rec
                if self.dry_run:
                    # It was a dry run. Skip calculation of missing derived
                    # fields (since there are no archive records to process),
                    # just provide the user with a summary of what we did.
                    _msg = "Finished dry run import"
                    print(_msg)
                    log.info(_msg)
                    _msg = "%d records were processed and %d unique records would "\
                           "have been imported." % (total_rec,
                                                    self.total_rec_proc)
                    print(_msg)
                    log.info(_msg)
                    if self.total_duplicate_rec > 1:
                        _msg = "%d duplicate records were ignored." % self.total_duplicate_rec
                        print(_msg)
                        log.info(_msg)
                    elif self.total_duplicate_rec == 1:
                        _msg = "1 duplicate record was ignored."
                        print(_msg)
                        log.info(_msg)
                else:
                    # It was not a dry run so calculate any missing derived
                    # fields and provide the user with a summary of what we did.
                    if self.calc_missing:
                        # We were asked to calculate missing derived fields, so
                        # get a CalcMissing object.
                        # First construct a CalcMissing config dict
                        # (self.dry_run will never be true). Subtract 0.5
                        # seconds from the earliest timestamp as calc_missing
                        # only calculates missing derived obs for records
                        # timestamped after start_ts.
                        calc_missing_config_dict = {'name': 'Calculate Missing Derived Observations',
                                                    'binding': self.db_binding_wx,
                                                    'start_ts': self.earliest_ts-0.5,
                                                    'stop_ts': self.latest_ts,
                                                    'trans_days': 1,
                                                    'dry_run': self.dry_run is True}
                        # now obtain a CalcMissing object
                        self.calc_missing_obj = weecfg.database.CalcMissing(self.config_dict,
                                                                            calc_missing_config_dict)
                        _msg = "Calculating missing derived observations ..."
                        print(_msg)
                        log.info(_msg)
                        # do the calculations
                        self.calc_missing_obj.run()
                        _msg = "Finished calculating missing derived observations"
                        print(_msg)
                        log.info(_msg)
                    # now provide the summary report
                    _msg = "Finished import"
                    print(_msg)
                    log.info(_msg)
                    _msg = "%d records were processed and %d unique records " \
                           "imported in %.2f seconds." % (total_rec,
                                                          self.total_rec_proc,
                                                          self.tdiff)
                    print(_msg)
                    log.info(_msg)
                    if self.total_duplicate_rec > 1:
                        _msg = "%d duplicate records were ignored." % self.total_duplicate_rec
                        print(_msg)
                        log.info(_msg)
                    elif self.total_duplicate_rec == 1:
                        _msg = "1 duplicate record was ignored."
                        print(_msg)
                        log.info(_msg)
                    print("Those records with a timestamp already "
                          "in the archive will not have been")
                    print("imported. Confirm successful import in the WeeWX log file.")

    def parse_map(self, map, field_map, field_map_extensions):
        """Update a field map with a field map and/or field map extension.

        The user may alter the default field map in two ways: through use of a
        new field map (defined in the [[FieldMap]] stanza) and/or a by altering an
        existing field map with one or more field map extensions (defined in the
        [[FieldMapExtensions]] stanza). If specified, the [[FieldMap]] stanza is
        used as the base-line field map for the import (if it is not specified the
        default field map is used as the base-line field map). The base-line field
        map can be further altered using the [[FieldMapExtensions]] stanza.
        """

        # first of all get our baseline field map, it will be as defined in
        # field_map (the [[FieldMap]] stanza) or if field_map has no entries it
        # will be the default field map
        if field_map is not None and len(field_map) > 0:
            # We have a field_map, but is it a legacy CSV field map or a new common
            # source field map. A legacy field map will consist of scalars only,
            # whereas a new common source field map will be None (ie no field map)
            # or it will have one or more sections.
            if len(field_map.scalars) > 0:
                # we likely have a legacy field map
                _map = self.parse_legacy_field_map(field_map)
            else:
                # so use it
                _map = dict(field_map)
        else:
            # we have no field map so use the default field map
            _map = dict(map)
        # obtain a list of source fields that will be mapped
        _mapped_source_fields = [config['source_field'] for field, config in _map.items()]
        # we may need to modify the baseline field map so make a working copy
        _ext_map = dict(_map)
        # iterate over any field map extension entries
        for field, config in field_map_extensions.items():
            # we can only map a given source field to a single WeeWX field, if a
            # field map extension maps a source field that is already mapped then
            # we need to remove the pre-existing mapping
            if 'source_field' in config and config['source_field'] in _mapped_source_fields:
                # we have a source field that is already mapped, so look through
                # our existing field map to find it
                for w, c in dict(_ext_map).items():
                    if c['source_field'] == config['source_field']:
                        # found it, so pop the map entry from our baseline map
                        _map.pop(w)
                # add ur field map extension entry to our baseline map
                _map[field] = config
        # return the finished field map
        return _map

    def parse_legacy_field_map(self, field_map):

        _map = dict()
        for _key, _item in field_map.items():
            _entry = option_as_list(_item)
            # expect 2 parameters for each option: source field, units
            if len(_entry) == 2:
                # we have 2 parameter so that's field and units, but units
                # could be 'text' indicating a text field
                if _entry[1] != 'text':
                    _map[_key] = {'source_field': _entry[0],
                                  'unit': _entry[1]}
                else:
                    _map[_key] = {'source_field': _entry[0],
                                  'is_text': True}
            # if the entry is not empty then it might be valid ie just a
            # field name (eg if usUnits is specified)
            elif _entry != [''] and len(_entry) == 1:
                # we have 1 parameter so it must be just name
                _map[_key] = {'source_field': _entry[0]}
            else:
                # otherwise it's invalid so ignore it
                pass

        # now do some crude error checking

        # dateTime. We must have a dateTime mapping. Check for a
        # 'field_name' field under 'dateTime' and be prepared to catch the
        # error if it does not exist.
        try:
            if _map['dateTime']['source_field']:
                # we have a 'source_field' entry so continue
                pass
            else:
                # something is wrong; we have a 'source_field' entry, but it is not
                # valid so raise an error
                _msg = "Invalid legacy mapping specified in '%s' " \
                       "for field 'dateTime'." % self.import_config_path
                raise WeeImportMapError(_msg)
        except KeyError:
            _msg = "No legacy mapping specified in '%s' for " \
                   "field 'dateTime'." % self.import_config_path
            raise WeeImportMapError(_msg)

        # usUnits. We don't have to have a mapping for usUnits but if we
        # don't then we must have 'units' specified for each field mapping.
        if 'usUnits' not in _map or _map['usUnits'].get('source_field') is None:
            # no unit system mapping do we have units specified for
            # each individual field
            for _key, _val in _map.items():
                # we don't need to check dateTime and usUnits or fields that
                # are marked as text
                if _key not in ['dateTime', 'usUnits'] or not _val.get('is_text', False):
                    if 'unit' in _val:
                        # we have a unit field, do we know about it
                        if _val['unit'] not in weewx.units.conversionDict \
                                and _val['unit'] not in weewx.units.USUnits.values():
                            # we have an invalid unit string so tell the
                            # user and exit
                            _msg = "Unknown units '%s' specified for " \
                                   "field '%s' in %s." % (_val['unit'],
                                                          _key,
                                                          self.import_config_path)
                            raise weewx.UnitError(_msg)
                    else:
                        # we don't have a unit field, that's not allowed
                        # so raise an error
                        _msg = "No units specified for source field " \
                               "'%s' in %s." % (_val['source_field'],
                                                self.import_config_path)
                        raise WeeImportMapError(_msg)
        # if we got this far we have a usable map to return
        return _map

    def print_map(self):
        """Display/log the field map.

        Display and/or log the field map in use. The field map is only
        displayed on the console if --verbose was used. the field map is always
        logged.
        """

        _msg = "The following imported field-to-WeeWX field map will be used:"
        if self.verbose:
            print(_msg)
        log.info(_msg)
        # iterate over the field map entries
        for weewx_field, source_field_config in self.map.items():
            _unit_msg = ""
            if 'unit' in source_field_config:
                _unit_msg = " in units '%s'" % source_field_config['unit']
            if source_field_config.get('text', False):
                _unit_msg = " as text"
            _msg = "     source field '%s'%s --> WeeWX field '%s'" % (source_field_config['source_field'],
                                                                      _unit_msg,
                                                                      weewx_field)
            if self.verbose:
                print(_msg)
            log.info(_msg)
            # display a message if the source field is marked as cumulative
            if 'is_cumulative' in source_field_config and source_field_config['is_cumulative']:
                _msg = ("       (source field '%s' will be treated as a cumulative "
                        "value)" % source_field_config['source_field'])
                if self.verbose:
                    print(_msg)
                log.info(_msg)
            # we could have a legacy rain = cumulative option
            elif weewx_field == 'rain' and hasattr(self, 'rain') and self.rain == 'cumulative':
                _msg = ("       (WeeWX field '%s' will be calculated from "
                        "a cumulative value)" % weewx_field)
                if self.verbose:
                    print(_msg)
                log.info(_msg)

    def map_raw_data(self, data, unit_sys=weewx.US):
        """Maps raw data to WeeWX archive record compatible dictionaries.

        Takes an iterable source of raw data observations, maps the fields of
        each row to a WeeWX field based on the field map and performs any
        necessary unit conversion.

        Input parameters:

            data: iterable that yields the data records to be processed.

            unit_sys: WeeWX unit system in which the generated records will be
                      provided. Omission will result in US customary (weewx.US)
                      being used.

        Returns a list of dicts of WeeWX compatible archive records.
        """

        # initialise our list of mapped records
        _records = []
        # initialise some rain variables
        _last_ts = None
        _last_rain = None
        # list of fields we have given the user a warning over, prevents us
        # giving multiple warnings for the same field.
        _warned = []
        # step through each row in our data
        for _row in data:
            _rec = {}
            # first off process the fields that require special processing
            # dateTime
            if 'source_field' in self.map['dateTime']:
                # we have a map for dateTime
                try:
                    _raw_dateTime = _row[self.map['dateTime']['source_field']]
                except KeyError:
                    _msg = "Field '%s' not found in source "\
                           "data." % self.map['dateTime']['source_field']
                    raise WeeImportFieldError(_msg)
                # now process the raw date time data
                if isinstance(_raw_dateTime, numbers.Number) or _raw_dateTime.isdigit():
                    # Our dateTime is a number, is it a timestamp already?
                    # Try to use it and catch the error if there is one and
                    # raise it higher.
                    try:
                        _rec_dateTime = int(_raw_dateTime)
                    except ValueError:
                        _msg = "Invalid '%s' field. Cannot convert '%s' to " \
                               "timestamp." % (self.map['dateTime']['source_field'],
                                               _raw_dateTime)
                        raise ValueError(_msg)
                else:
                    # it's a non-numeric string so try to parse it and catch
                    # the error if there is one and raise it higher
                    try:
                        _datetm = time.strptime(_raw_dateTime,
                                                self.raw_datetime_format)
                        _rec_dateTime = int(time.mktime(_datetm))
                    except ValueError:
                        _msg = "Invalid '%s' field. Cannot convert '%s' to " \
                               "timestamp." % (self.map['dateTime']['source_field'],
                                               _raw_dateTime)
                        raise ValueError(_msg)
                # if we have a timeframe of concern does our record fall within
                # it
                if (self.first_ts is None and self.last_ts is None) or \
                        self.first_ts < _rec_dateTime <= self.last_ts:
                    # we have no timeframe or if we do it falls within it so
                    # save the dateTime
                    _rec['dateTime'] = _rec_dateTime
                    # update earliest and latest record timestamps
                    if self.earliest_ts is None or _rec_dateTime < self.earliest_ts:
                        self.earliest_ts = _rec_dateTime
                    if self.latest_ts is None or _rec_dateTime > self.earliest_ts:
                        self.latest_ts = _rec_dateTime
                else:
                    # it is not so skip to the next record
                    continue
            else:
                # there is no mapped field for dateTime so raise an error
                raise ValueError("No mapping for WeeWX field 'dateTime'.")
            # usUnits
            _units = None
            if 'usUnits' in self.map.keys() and 'source_field' in self.map['usUnits']:
                # we have a field map for a unit system
                try:
                    # The mapped field is in _row so try to get the raw data.
                    # If it's not there then raise an error.
                    _raw_units = int(_row[self.map['usUnits']['source_field']])
                except KeyError:
                    _msg = "Field '%s' not found in "\
                           "source data." % self.map['usUnits']['source_field']
                    raise WeeImportFieldError(_msg)
                # we have a value but is it valid
                if _raw_units in unit_nicknames:
                    # it is valid so use it
                    _units = _raw_units
                else:
                    # the units value is not valid so raise an error
                    _msg = "Invalid unit system '%s'(0x%02x) mapped from data source. " \
                           "Check data source or field mapping." % (_raw_units,
                                                                    _raw_units)
                    raise weewx.UnitError(_msg)
            # interval
            if 'interval' in self.map.keys() and 'source_field' in self.map['interval']:
                # We have a map for interval so try to get the raw data. If
                # it's not there raise an error.
                try:
                    _tfield = _row[self.map['interval']['source_field']]
                except KeyError:
                    _msg = "Field '%s' not found in "\
                           "source data." % self.map['interval']['source_field']
                    raise WeeImportFieldError(_msg)
                # now process the raw interval data
                if _tfield is not None and _tfield != '':
                    try:
                        _rec['interval'] = int(_tfield)
                    except ValueError:
                        _msg = "Invalid '%s' field. Cannot convert '%s' to " \
                               "an integer." % (self.map['interval']['source_field'],
                                                _tfield)
                        raise ValueError(_msg)
                else:
                    # if it happens to be None then raise an error
                    _msg = "Invalid value '%s' for mapped field '%s' at " \
                           "timestamp '%s'." % (_tfield,
                                                self.map['interval']['source_field'],
                                                timestamp_to_string(_rec['dateTime']))
                    raise ValueError(_msg)
            else:
                # we have no mapping so calculate it, wrap in a try..except in
                # case it cannot be calculated
                try:
                    _rec['interval'] = self.get_interval(_last_ts, _rec['dateTime'])
                except WeeImportFieldError as e:
                    # We encountered a WeeImportFieldError, which means we
                    # cannot calculate the interval value, possibly because
                    # this record is out of date-time order. We cannot use this
                    # record so skip it, advise the user (via console and log)
                    # and move to the next record.
                    _msg = "Record discarded: %s" % e
                    print(_msg)
                    log.info(_msg)
                    continue
            # now step through the rest of the fields in our map and process
            # the fields that don't require special processing
            for _field in self.map:
                # skip those that have had special processing
                if _field in self.special_processing_fields:
                    continue
                # process everything else
                else:
                    # is our mapped field in the record
                    if self.map[_field]['source_field'] in _row:
                        # yes it is
                        # first check to see if this is a text field
                        if self.map[_field].get('text', False):
                            # we have a text field, so accept the field
                            # contents as is
                            _rec[_field] = _row[self.map[_field]['source_field']]
                        else:
                            # we have a non-text field so try to get a value
                            # for the obs but if we can't, catch the error
                            try:
                                _value = float(_row[self.map[_field]['source_field']].strip())
                            except AttributeError:
                                # the data has no strip() attribute so chances
                                # are it's a number already, or it could
                                # (somehow ?) be None
                                if _row[self.map[_field]['source_field']] is None:
                                    _value = None
                                else:
                                    try:
                                        _value = float(_row[self.map[_field]['source_field']])
                                    except TypeError:
                                        # somehow we have data that is not a
                                        # number or a string
                                        _msg = "%s: cannot convert '%s' to float at " \
                                               "timestamp '%s'." % (_field,
                                                                    _row[self.map[_field]['source_field']],
                                                                    timestamp_to_string(_rec['dateTime']))
                                        raise TypeError(_msg)
                            except ValueError:
                                # A ValueError means that float() could not
                                # convert the string or number to a float, most
                                # likely because we have non-numeric, non-None
                                # data. We have some other possibilities to
                                # work through before we give up.

                                # start by setting our result to None.
                                _value = None

                                # perhaps it is numeric data but with something
                                # other that a period as decimal separator, try
                                # using float() again after replacing the
                                # decimal seperator
                                if self.decimal_sep is not None:
                                    _data = _row[self.map[_field]['source_field']].replace(self.decimal_sep,
                                                                                         '.')
                                    try:
                                        _value = float(_data)
                                    except ValueError:
                                        # still could not convert it so pass
                                        pass

                                # If this is a csv import and we are mapping to
                                # a direction field, perhaps we have a string
                                # representation of a cardinal, inter-cardinal
                                # or secondary inter-cardinal direction that we
                                # can convert to degrees

                                if _value is None and hasattr(self, 'wind_dir_map') and \
                                        self.map[_field]['unit'] == 'degree_compass':
                                    # we have a csv import and we are mapping
                                    # to a direction field, so try a cardinal
                                    # conversion

                                    # first strip any whitespace and hyphens
                                    # from the data
                                    _stripped = re.sub(r'[\s-]+', '',
                                                       _row[self.map[_field]['source_field']])
                                    # try to use the data as the key in a dict
                                    # mapping directions to degrees, if there
                                    # is no match we will have None returned
                                    try:
                                        _value = self.wind_dir_map[_stripped.upper()]
                                    except KeyError:
                                        # we did not find a match so pass
                                        pass
                                # we have exhausted all possibilities, so if we
                                # have a non-None result use it, otherwise we
                                # either ignore it or raise an error
                                if _value is None and not self.ignore_invalid_data:
                                    _msg = "%s: cannot convert '%s' to float at " \
                                           "timestamp '%s'." % (_field,
                                                                _row[self.map[_field]['source_field']],
                                                                timestamp_to_string(_rec['dateTime']))
                                    raise ValueError(_msg)

                            # some fields need some special processing

                            # data from cumulative fields needs special processing,
                            # also required for the WeeWX 'rain' field where the
                            # legacy 'rain = cumulative' option is used in the
                            # import config file
                            if ('is_cumulative' in self.map[_field] and self.map[_field]['is_cumulative']) \
                                    or (_field == "rain" and getattr(self, 'rain', 'discrete') == "cumulative"):
                                # we have a cumulative field, so process as such
                                _value = self.process_cumulative(self.map[_field]['source_field'],
                                                                 _value)

                            # wind - check any wind direction fields are within our
                            # bounds and convert to 0 to 360 range
                            elif _field == "windDir" or _field == "windGustDir":
                                if _value is not None and (self.wind_dir[0] <= _value <= self.wind_dir[1]):
                                    # normalise to 0 to 360
                                    _value %= 360
                                else:
                                    # outside our bounds so set to None
                                    _value = None
                            # UV - if there was no UV sensor used to create the
                            # imported data then we need to set the imported value
                            # to None
                            elif _field == 'UV':
                                if not self.UV_sensor:
                                    _value = None
                            # solar radiation - if there was no solar radiation
                            # sensor used to create the imported data then we need
                            # to set the imported value to None
                            elif _field == 'radiation':
                                if not self.solar_sensor:
                                    _value = None

                            # check and ignore if required temperature and humidity
                            # values of 255.0 and greater
                            if self.ignore_extr_th \
                                    and self.map[_field]['unit'] in ['degree_C', 'degree_F', 'percent'] \
                                    and _value >= 255.0:
                                _value = None
                            # if there is no mapped field for a unit system we
                            # have to do field by field unit conversions
                            if _units is None:
                                _vt = ValueTuple(_value,
                                                 self.map[_field]['unit'],
                                                 weewx.units.obs_group_dict[_field])
                                _conv_vt = convertStd(_vt, unit_sys)
                                _rec[_field] = _conv_vt.value
                            else:
                                # we do have a mapped field for a unit system so
                                # save the field in our record and continue, any
                                # unit conversion will be done in bulk later
                                _rec[_field] = _value
                    else:
                        # no it's not in our record, so set the field in our
                        # output to None
                        _rec[_field] = None
                        # now warn the user about this field if we have not
                        # already done so
                        if self.map[_field]['source_field'] not in _warned:
                            _msg = "Warning: Import field '%s' is mapped to WeeWX " \
                                   "field '%s' but the" % (self.map[_field]['source_field'],
                                                           _field)
                            if not self.suppress_warning:
                                print(_msg)
                            log.info(_msg)
                            _msg = "         import field '%s' could not be found " \
                                   "in one or more records." % self.map[_field]['source_field']
                            if not self.suppress_warning:
                                print(_msg)
                            log.info(_msg)
                            _msg = "         WeeWX field '%s' will be "\
                                   "set to 'None' in these records." % _field
                            if not self.suppress_warning:
                                print(_msg)
                            log.info(_msg)
                            # make sure we do this warning once only
                            _warned.append(self.map[_field]['source_field'])
            # if we have a mapped field for a unit system with a valid value,
            # then all we need do is set 'usUnits', bulk conversion is taken
            # care of by saveToArchive()
            if _units is not None:
                # we have a mapped field for a unit system with a valid value
                _rec['usUnits'] = _units
            else:
                # no mapped field for unit system, but we have already
                # converted any necessary fields on a field by field basis so
                # all we need do is set 'usUnits', any bulk conversion will be
                # taken care of by saveToArchive()
                _rec['usUnits'] = unit_sys
            # If interval is being derived from record timestamps our first
            # record will have an interval of None. In this case we wait until
            # we have the second record, and then we use the interval between
            # records 1 and 2 as the interval for record 1.
            if len(_records) == 1 and _records[0]['interval'] is None:
                _records[0]['interval'] = _rec['interval']
            _last_ts = _rec['dateTime']
            # this record is done, add it to our list of records to return
            _records.append(_rec)
        # If we have more than 1 unique value for interval in our records it
        # could be a sign of missing data and impact the integrity of our data,
        # so do the check and see if the user wants to continue
        if len(_records) > 0:
            # if we have any records to return do the unique interval check
            # before we return the records
            _start_interval = _records[0]['interval']
            _diff_interval = False
            for _rec in _records:
                if _rec['interval'] != _start_interval:
                    _diff_interval = True
                    break
            if _diff_interval and self.interval_ans != 'y':
                # we had more than one unique value for interval, warn the user
                _msg = "Warning: Records to be imported contain multiple " \
                       "different 'interval' values."
                print(_msg)
                log.info(_msg)
                print("         This may mean the imported data is missing "
                      "some records and it may lead")
                print("         to data integrity issues. If the raw data has "
                      "a known, fixed interval")
                print("         value setting the relevant 'interval' setting "
                      "in wee_import config to")
                print("         this value may give a better result.")
                while self.interval_ans not in ['y', 'n']:
                    if self.no_prompt:
                        self.interval_ans = 'y'
                    else:
                        self.interval_ans = input('Are you sure you want to proceed (y/n)? ')
                if self.interval_ans == 'n':
                    # the user chose to abort, but we may have already
                    # processed some records. So log it then raise a SystemExit()
                    if self.dry_run:
                        print("Dry run import aborted by user. %d records were processed." % self.total_rec_proc)
                    else:
                        if self.total_rec_proc > 0:
                            print("Those records with a timestamp already in the "
                                  "archive will not have been")
                            print("imported. As the import was aborted before completion "
                                  "refer to the WeeWX log")
                            print("file to confirm which records were imported.")
                            raise SystemExit('Exiting.')
                        else:
                            print("Import aborted by user. No records saved to archive.")
                        _msg = "User chose to abort import. %d records were processed. " \
                               "Exiting." % self.total_rec_proc
                        log.info(_msg)
                    raise SystemExit('Exiting. Nothing done.')
            _msg = "Mapped %d records." % len(_records)
            if self.verbose:
                print(_msg)
            log.info(_msg)
            # the user wants to continue, or we have only one unique value for
            # interval so return the records
            return _records
        else:
            _msg = "Mapped 0 records."
            if self.verbose:
                print(_msg)
            log.info(_msg)
            # we have no records to return so return None
            return None

    def get_interval(self, last_ts, current_ts):
        """Determine an interval value for a record.

        The interval field can be determined in one of the following ways:

        -   Derived from the raw data. The interval is calculated as the
            difference between the timestamps of consecutive records rounded to
            the nearest minute. In this case interval can change between
            records if the records are not evenly spaced in time or if there
            are missing records. This method is the default and is used when
            the interval parameter in wee_import.conf is 'derive'.

        -   Read from weewx.conf. The interval value is read from the
            archive_interval parameter in [StdArchive] in weewx.conf. In this
            case interval may or may not be the same as the difference in time
            between consecutive records. This method may be of use when the
            import source has a known interval but may be missing a number of
            records which makes deriving the interval from the imported data
            problematic. This method is used when the interval parameter in
            wee_import.conf is 'conf'.

        Input parameters:

            last_ts. timestamp of the previous record.
            current_rain. timestamp of the current record.

        Returns the interval (in minutes) for the current record.
        """

        # did we have a number specified in wee_import.conf, if so use that
        try:
            return float(self.interval)
        except ValueError:
            pass
        # how are we getting interval
        if self.interval.lower() == 'conf':
            # get interval from weewx.conf
            return to_int(float(self.config_dict['StdArchive'].get('archive_interval')) / 60.0)
        elif self.interval.lower() == 'derive':
            # get interval from the timestamps of consecutive records
            try:
                _interval = int((current_ts - last_ts) / 60.0)
                # but if _interval < 0 our records are not in date-time order
                if _interval < 0:
                    # so raise a WeeImportFieldError exception
                    _msg = "Cannot derive 'interval' for record "\
                           "timestamp: %s. " % timestamp_to_string(current_ts)
                    raise WeeImportFieldError(_msg)
            except TypeError:
                _interval = None
            return _interval
        else:
            # we don't know what to do so raise an error
            _msg = "Cannot derive 'interval'. Unknown 'interval' "\
                   "setting in %s." % self.import_config_path
            raise ValueError(_msg)

    def process_cumulative(self, source_field, current_value):
        """Determine a per-period obs value for a cumulative field.

        If the data source provides the obs value as a cumulative value then
        the per-period value is the simple difference between the two values.
        But we need to take into account some special cases:

        No last value. Will occur for very first record or maybe in an error
                       condition. Need to return 0.0.
        last value > current value. Occurs when the cumulative value was reset
                                    (maybe daily or some other period). Need to
                                    return the current value.
        current value is None. Could occur if the imported value could not be
                               converted to a numeric and config option
                               ignore_invalid_data is set.

        Input parameters:

            source_field. The source field containing the cumulative data
            current_value. Current cumulative value.

        Returns the per-period value.
        """

        if source_field in self.last_values and self.last_values[source_field] is not None:
            # we have a value for the previous period
            if current_value is not None and current_value >= self.last_values[source_field]:
                # we just want the difference
                result = current_value - self.last_values[source_field]
            else:
                # we are at a cumulative reset point or current_value is None,
                # either way we just want the current_value
                result = current_value
        else:
            # we have not seen this source field before or if we have it's last
            # value was None, so save the current value as the last value and
            # return 0.0
            result = 0.0
        # set our last value to the current value
        self.last_values[source_field] = current_value
        # return the result
        return result

    def qc(self, data_dict, data_type):
        """ Apply weewx.conf QC to a record.

        If qc option is set in the import config file then apply any StdQC
        min/max checks specified in weewx.conf.

        Input parameters:

            data_dict: A WeeWX compatible archive record.

        Returns nothing. data_dict is modified directly with obs outside of QC
        limits set to None.
        """

        if self.apply_qc:
            self.import_QC.apply_qc(data_dict, data_type=data_type)

    def save_to_archive(self, archive, records):
        """ Save records to the WeeWX archive.

        Supports saving one or more records to archive. Each collection of
        records is processed and saved to archive in transactions of
        self.tranche records at a time.

        if the import config file qc option was set quality checks on the
        imported record are performed using the WeeWX StdQC configuration from
        weewx.conf. Any missing derived observations are then added to the
        archive record using the WeeWX WXCalculate class if the import config
        file calc_missing option was set. WeeWX API addRecord() method is used
        to add archive records.

        If --dry-run was set then every aspect of the import is carried out but
        nothing is saved to archive. If --dry-run was not set then the user is
        requested to confirm the import before any records are saved to archive.

        Input parameters:

            archive: database manager object for the WeeWX archive.

            records: iterable that provides WeeWX compatible archive records
                     (in dict form) to be written to archive
        """

        # do we have any records?
        if records and len(records) > 0:
            # if this is the first period then give a little summary about what
            # records we have
            # TODO. Check that a single period shows correct and consistent console output
            if self.first_period and self.last_period:
                # there is only 1 period, so we can count them
                print("%s records identified for import." % len(records))
            # we do, confirm the user actually wants to save them
            while self.ans not in ['y', 'n'] and not self.dry_run:
                if self.no_prompt:
                    self.ans = 'y'
                else:
                    print("Proceeding will save all imported records in the WeeWX archive.")
                    self.ans = input("Are you sure you want to proceed (y/n)? ")
            if self.ans == 'y' or self.dry_run:
                # we are going to save them
                # reset record counter
                nrecs = 0
                # initialise our list of records for this tranche
                _tranche = []
                # initialise a set for use in our dry run, this lets us
                # give some better stats on records imported
                unique_set = set()
                # step through each record in this period
                for _rec in records:
                    # convert our record
                    _conv_rec = to_std_system(_rec, self.archive_unit_sys)
                    # perform any required QC checks
                    self.qc(_conv_rec, 'Archive')
                    # add the record to our tranche and increment our count
                    _tranche.append(_conv_rec)
                    nrecs += 1
                    # if we have a full tranche then save to archive and reset
                    # the tranche
                    if len(_tranche) >= self.tranche:
                        # add the record only if it is not a dry run
                        if not self.dry_run:
                            # add the record only if it is not a dry run
                            archive.addRecord(_tranche)
                        # add our the dateTime for each record in our tranche
                        # to the dry run set
                        for _trec in _tranche:
                            unique_set.add(_trec['dateTime'])
                        # tell the user what we have done
                        _msg = "Unique records processed: %d; "\
                               "Last timestamp: %s\r" % (nrecs,
                                                         timestamp_to_string(_rec['dateTime']))
                        print(_msg, end='', file=sys.stdout)
                        sys.stdout.flush()
                        _tranche = []
                # we have processed all records but do we have any records left
                # in the tranche?
                if len(_tranche) > 0:
                    # we do so process them
                    if not self.dry_run:
                        # add the record only if it is not a dry run
                        archive.addRecord(_tranche)
                    # add our the dateTime for each record in our tranche to
                    # the dry run set
                    for _trec in _tranche:
                        unique_set.add(_trec['dateTime'])
                    # tell the user what we have done
                    _msg = "Unique records processed: %d; "\
                           "Last timestamp: %s\r" % (nrecs,
                                                     timestamp_to_string(_rec['dateTime']))
                    print(_msg, end='', file=sys.stdout)
                print()
                sys.stdout.flush()
                # update our counts
                self.total_rec_proc += nrecs
                self.total_unique_rec += len(unique_set)
                # mention any duplicates we encountered
                num_duplicates = len(self.period_duplicates)
                self.total_duplicate_rec += num_duplicates
                if num_duplicates > 0:
                    if num_duplicates == 1:
                        _msg = "    1 duplicate record was identified "\
                               "in period %d:" % self.period_no
                    else:
                        _msg = "    %d duplicate records were identified "\
                               "in period %d:" % (num_duplicates,
                                                  self.period_no)
                    if not self.suppress_warning:
                        print(_msg)
                    log.info(_msg)
                    for ts in sorted(self.period_duplicates):
                        _msg = "        %s" % timestamp_to_string(ts)
                        if not self.suppress_warning:
                            print(_msg)
                        log.info(_msg)
                    # add the period duplicates to the overall duplicates
                    self.duplicates |= self.period_duplicates
                    # reset the period duplicates
                    self.period_duplicates = set()
            elif self.ans == 'n':
                # user does not want to import so display a message and then
                # ask to exit
                _msg = "User chose not to import records. Exiting. Nothing done."
                print(_msg)
                log.info(_msg)
                raise SystemExit('Exiting. Nothing done.')
        else:
            # we have no records to import, advise the user but what we say
            # will depend on if there are any more periods to import
            if self.first_period and self.last_period:
                # there was only 1 period
                _msg = 'No records identified for import.'
            else:
                # multiple periods
                _msg = 'Period %d - no records identified for import.' % self.period_no
            print(_msg)


# ============================================================================
#                             Utility functions
# ============================================================================

def get_binding(config_dict):
    """Get the binding for the WeeWX database."""

    # Extract our binding from the StdArchive section of the config file. If
    # it's missing, return None.
    if 'StdArchive' in config_dict:
        db_binding_wx = config_dict['StdArchive'].get('data_binding',
                                                      'wx_binding')
    else:
        db_binding_wx = None
    return db_binding_wx
