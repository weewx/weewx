#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#

from __future__ import with_statement

"""Module providing the base classes and API for importing observational data
into weeWX.
"""

# Python imports
import datetime
import os.path
import re
import sys
import syslog
import time

from datetime import datetime as dt

# weeWX imports
import weecfg
import weewx
import weewx.qc
import weewx.wxservices

from weewx.manager import open_manager_with_config
from weewx.units import unit_constants, unit_nicknames, convertStd, to_std_system, ValueTuple
from weeutil.weeutil import timestamp_to_string, option_as_list, to_int, tobool, _get_object

# List of sources we support
SUPPORTED_SOURCES = ['CSV', 'WU', 'Cumulus']

# Minimum requirements in any explicit or implicit weeWX field-to-import field
# map
MINIMUM_MAP = {'dateTime': {'units': 'unix_epoch'},
               'usUnits': {'units': None},
               'interval': {'units': 'minute'}}


# ============================================================================
#                                Error Classes
# ============================================================================


class WeeImportOptionError(Exception):
    """Base class of exceptions thrown when encountering an error with a
       command line option.
    """

class WeeImportMapError(Exception):
    """Base class of exceptions thrown when encountering an error with an
       external source-to-weeWX field map.
    """


class WeeImportIOError(Exception):
    """Base class of exceptions thrown when encountering an I/O error with an
       external source.
    """


class WeeImportFieldError(Exception):
    """Base class of exceptions thrown when encountering an error with a field
       from an external source.
    """


# ============================================================================
#                                class Source
# ============================================================================


class Source(object):
    """ Abstract base class used for interacting with an external data source
        to import records into the weeWX archive.

    __init__() must define the following properties:
        self.dry_run      - Is this a dry run (ie do not save imported records
                            to archive). [True|False].
        self.calc_missing - Calculate any missing derived observations.
                            [True|False].
        self.tranche      - Number of records to be written to archive in a
                            single transaction. Integer.
        self.interval     - Method of determining interval value if interval
                            field not included in data source.
                            ['config'|'derive'|x] where x is an integer.

    Child classes are used to interract with a specific source (eg CSV file,
    WU). Any such child classes must define a getRawData() method which:
        -   gets the raw observation data and returns an iterable yielding data
            dicts whose fields can be mapped to a weeWX archive field
        -   defines an import data field-to-weeWX archive field map (self.map)

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

    def __init__(self, config_dict, import_config_dict, options, log):
        """A generic initialisation.

        Set some realistic default values for options read from the import
        config file. Obtain objects to handle missing derived obs (if required)
        and QC on imported data. Parse any --date command line option so we
        know what records to import.
        """

        # give our source object some logging abilities
        self.wlog = log

        # save our weeWX config dict
        self.config_dict = config_dict

        # get our import config dict settings
        # interval, default to 'derive'
        self.interval = import_config_dict.get('interval', 'derive')
        # tranche, default to 250
        self.tranche = to_int(import_config_dict.get('tranche', 250))
        # apply QC, default to True
        self.apply_qc = tobool(import_config_dict.get('qc', True))
        # calc-missing, default to True
        self.calc_missing = tobool(import_config_dict.get('calc_missing', True))
        # Some sources include UV index and solar radiation values even if no
        # sensor was present. The weeWX convention is to store the None value
        # when a sensor or observation does not exist. Record whether UV and/or
        # solar radiation sensor was present.
        # UV, default to True
        self.UV_sensor = tobool(import_config_dict.get('UV_sensor', True))
        # solar, default to True
        self.solar_sensor = tobool(import_config_dict.get('solar_sensor', True))

        # get some weeWX database info
        self.db_binding_wx = get_binding(config_dict)
        self.dbm = open_manager_with_config(config_dict, self.db_binding_wx,
                                            initialize=True,
                                            default_binding_dict={'table_name': 'archive',
                                                                  'manager': 'weewx.wxmanager.WXDaySummaryManager',
                                                                  'schema': 'schemas.wview.schema'})
        # get the unit system used in our db
        if self.dbm.std_unit_system is None:
            # we have a fresh archive (ie no records) so cannot deduce
            # the unit system in use, so go to our config_dict
            self.archive_unit_sys = unit_constants[self.config_dict['StdConvert'].get('target_unit','US')]
        else:
            # get our unit system from the archive db
            self.archive_unit_sys = self.dbm.std_unit_system

        # do we need a WXCalculate object, if so get one
        if self.calc_missing:
            # parameters required to obtain a WXCalculate object
            stn_dict = config_dict['Station']
            altitude_t = option_as_list(stn_dict.get('altitude', (None, None)))
            try:
                altitude_vt = weewx.units.ValueTuple(float(altitude_t[0]),
                                                     altitude_t[1],
                                                     "group_altitude")
            except KeyError, e:
                raise weewx.ViolatedPrecondition(
                    "Value 'altitude' needs a unit (%s)" % e)
            latitude_f = float(stn_dict['latitude'])
            longitude_f = float(stn_dict['longitude'])
            # get a WXCalculate object
            self.wxcalculate = weewx.wxservices.WXCalculate(config_dict,
                                                            altitude_vt,
                                                            latitude_f,
                                                            longitude_f)
        else:
            self.wxcalculate = None

        # get ourselves a QC object to do QC on imported records
        self.import_QC = weewx.qc.QC(config_dict, parent='weeimport')

        # Process our command line options
        self.dry_run = options.dry_run
        self.verbose = options.verbose

        # By processing any --date, --from and --to options we need to derive
        # self.first_ts and self.last_ts; the earliest and latest (inclusive)
        # timestamps of data to be imported. If we have no --date, --from or
        # --to then set both to None (we then get the default action for each
        # import type).
        # First we see if we have a valid --date, if not then we look for
        # --from and --to.
        if options.date or options.date == "":
            # there is a --date but is it valid
            try:
                _first_dt = dt.strptime(options.date, "%Y-%m-%d")
            except ValueError:
                # Could not convert --date. If we have a --date it must be
                # valid otherwise we can't continue so raise it.
                _msg = "Invalid --date option specified."
                raise WeeImportOptionError(_msg)
            else:
                # we have a valid date so do soem date arithmetic
                _last_dt = _first_dt + datetime.timedelta(days=1)
                self.first_ts = time.mktime(_first_dt.timetuple())
                self.last_ts = time.mktime(_last_dt.timetuple())
        elif options.date_from or options.date_to or options.date_from == '' or options.date_to == '':
            # There is a --from and/or a --to, but do we have both and are
            # they valid.
            # try --from first
            try:
                if 'T' in options.date_from:
                    _from_dt = dt.strptime(options.date_from, "%Y-%m-%dT%H:%M")
                else:
                    _from_dt = dt.strptime(options.date_from, "%Y-%m-%d")
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
                if 'T' in options.date_to:
                    _to_dt = dt.strptime(options.date_to, "%Y-%m-%dT%H:%M")
                else:
                    _to_dt = dt.strptime(options.date_to, "%Y-%m-%d")
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
        self.first_period = True
        self.last_period = False
        self.period_no = 1
        # total records processed
        self.total_rec_proc = 0
        # total unique records identified
        self.total_unique_rec = 0
        # time we started to first save
        self.t1 = None

    @staticmethod
    def sourceFactory(options, args, log):
        """Factory to produce a Source object.

        Returns an appropriate object depending on the source type. Raises a
        weewx.UnsupportedFeature error if an object could not be created.
        """

        # get some key weeWX parameters
        # first the config dict to use
        config_path, config_dict = weecfg.read_config(None,
                                                      args,
                                                      file_name=options.config_path)
        # get wee_import config dict if it exists
        import_config_path, import_config_dict = weecfg.read_config(None,
                                                                    args,
                                                                    file_name=options.import_config_path)
        # we should have a source parameter at the root of out import config
        # file, try to get it but be prepared to catch the error.
        try:
            source = import_config_dict['source']
        except KeyError:
            # we have no source parameter so check if we have a single source
            # config stanza, if we do then proceed using that
            _source_keys = [s for s in SUPPORTED_SOURCES if s in import_config_dict.keys()]
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
        return _get_object(module_class)(config_dict,
                                         config_path,
                                         import_config_dict.get(source, {}),
                                         import_config_path,
                                         options,
                                         log)

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
        with self.dbm as archive:
            # step through our periods of records until we reach the end. A
            # 'period' of records may comprise the contents of a file, a day
            # of WU obs or a month of Cumulus obs
            for period in self.period_generator():

                # get the raw data
                _msg = 'Obtaining raw import data for period %d...' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)
                _raw_data = self.getRawData(period)
                _msg = 'Raw import data read successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)

                # map the raw data to a weeWX archive compatible dictionary
                _msg = 'Mapping raw import data for period %d...' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)
                _mapped_data = self.mapRawData(_raw_data, self.archive_unit_sys)
                _msg = 'Raw import data mapped successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)

                # save the mapped data to archive
                _msg = 'Saving mapped data to archive for period %d...' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)
                self.saveToArchive(archive, _mapped_data)
                _msg = 'Mapped data saved to archive successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg)

                # increment our period counter
                self.period_no += 1
            # Provide some summary info now that we have finished the import.
            # What we say depends on whether it was a dry run or not and
            # whether we imported and records or not.
            if self.total_rec_proc == 0:
                # nothing imported so say so
                _msg = 'No records were identified for import. Exiting. Nothing done.'
                self.wlog.printlog(syslog.LOG_INFO, _msg)
            else:
                # we imported something
                if self.dry_run:
                    # but it was a dry run
                    _msg = "Finished dry run import. %d records were processed and %d unique records would have been imported." % (self.total_rec_proc,
                                                                                                                                   self.total_unique_rec)
                    self.wlog.printlog(syslog.LOG_INFO, _msg)
                else:
                    # something should have been saved to database
                    _msg = "Finished import. %d raw records resulted in %d unique records being processed in %.2f seconds." % (self.total_rec_proc,
                                                                                                                               self.total_unique_rec,
                                                                                                                               self.tdiff)
                    self.wlog.printlog(syslog.LOG_INFO, _msg)
                    print "Those records with a timestamp already in the archive will not have been"
                    print "imported. Confirm successful import in the weeWX log file."

    def parseMap(self, source_type, source, import_config_dict):
        """Produce a source field-to-weeWX archive field map.

        Data from an external source can be mapped to the weeWX archive using:
        - a fixed field map (WU),
        - a fixed field map with user specified source units (Cumulus), or
        - a user defined field/units map.

        All user defined mapping is specified in the import config file.

        To generate the field map first look to see if we have a fixed map, if
        we do validate it and return the resulting map. Otherwise look for user
        specified mapping in the import config file, construct the field map
        and return it. If there is neither a fixed map or user specified
        mapping then raise an error.

        Input parameters:

            source_type: String holding name of the section in
                         import_config_dict the holds config details for the
                         source being used.

            source: Iterable holding the source data. Used if import field
                    names are included in the source data (eg CSV).

            import_config_dict: config dict from import config file.

        Returns a map as a dictionary of elements with each element structured
        as follows:

            'archive_field_name': {'field_name': 'source_field_name',
                                   'units': 'unit_name'}

            where:

                - archive_field_name is an observation name in the weeWX
                  database schema
                - source_field_name is the name of a field from the external
                  source
                - unit_name is the weeWX unit name of the units used by
                  source_field_name
        """

        # start with the minimum map
        _map = dict(MINIMUM_MAP)

        # Do the easy one first, do we have a fixed mapping, if so validate it
        if self._header_map:
            # We have a static map that maps header fields to weeWX (eg WU).
            # Our static map may have entries for fields that don't exist in our
            # source data so step through each field name in our source data and
            # only add those that exist to our resulting map.
            for _key in source.fieldnames:
                # if we know about the field name add it to our map
                if _key in self._header_map:
                    _map[self._header_map[_key]['map_to']] = {'field_name': _key,
                                                              'units': self._header_map[_key]['units']}
        # Do we have a user specified map, if so construct our field map
        elif 'FieldMap' in import_config_dict:
            # we have a user specified map so construct our map dict
            for _key, _item in import_config_dict['FieldMap'].iteritems():
                _entry = option_as_list(_item)
                # expect 2 parameters for each option: source field, units
                if len(_entry) == 2:
                    # we have 2 parameter so that's field and units
                    _map[_key] = {'field_name': _entry[0],
                                  'units': _entry[1]}
                # if the entry is not empty then it might be valid ie just a
                # field name (eg if usUnits is specified)
                elif _entry != [''] and len(_entry) == 1:
                    # we have 1 parameter so it must be just name
                    _map[_key] = {'field_name': _entry[0]}
                else:
                    # otherwise its invalid so ignore it
                    pass

            # now do some crude error checking

            # dateTime. We must have a dateTime mapping. Check for a 'field_name'
            # field under 'dateTime' and be prepared to catch the error if it
            # does not exist.
            try:
                if _map['dateTime']['field_name']:
                    # we have a 'field_name' entry so continue
                    pass
                else:
                    # something is wrong, we have a 'field_name' entry but it
                    # is not valid so raise an error
                    raise WeeImportMapError(
                        "Invalid mapping specified in '%s' for field 'dateTime'." % self.import_config_path)
            except KeyError:
                raise WeeImportMapError(
                    "No mapping specified in '%s' for field 'dateTime'." % self.import_config_path)

            # usUnits. We don't have to have a mapping for usUnits but if we
            # don't then we must have 'units' specified for each field mapping.
            if 'usUnits' not in _map:
                # no unit system mapping do we have units specified for
                # each individual field
                for _key,_val in _map.iteritems():
                    # we don't need to check dateTime and usUnits
                    if _key not in ['dateTime', 'usUnits']:
                        if 'units' in _val:
                            # we have a units field, do we know about it
                            if _val['units'] not in weewx.units.default_unit_format_dict:
                                # we have an invalid unit string so tell the
                                # user and exit
                                raise weewx.UnitError(
                                    "Unknown units '%s' specified for field '%s' in %s." % (_map[_field]['units'],
                                                                                            _field,
                                                                                            self.import_config_path))
                        else:
                            # we don't have a units field, that's not allowed
                            # so raise an error
                            raise WeeImportMapError(
                                "No units specified for source field '%s' in %s." % (_key,
                                                                                     self.import_config_path))

            # if we got this far we have a usable map, advise the user what we
            # will use
            _msg = "The following imported field-to-weeWX field map will be used:"
            if self.verbose:
                self.wlog.verboselog(syslog.LOG_INFO, _msg)
            else:
                self.wlog.logonly(syslog.LOG_INFO, _msg)
            for _key, _val in _map.iteritems():
                if 'field_name' in _val:
                    _units_msg = ""
                    if 'units' in _val:
                        _units_msg = " in units '%s'" % _val['units']
                    _msg = "     source field '%s'%s --> weeWX field '%s'" % (_val['field_name'],
                                                                              _units_msg,
                                                                              _key)
                    if self.verbose:
                        self.wlog.verboselog(syslog.LOG_INFO, _msg)
                    else:
                        self.wlog.logonly(syslog.LOG_INFO, _msg)
        else:
            # no [[FieldMap]] stanza and no _header_map so raise an error as we
            # don't know what to map
            _msg = "No '%s' field map found in %s." % (source_type,
                                                       self.import_config_path)
            raise WeeImportMapError(_msg)
        return _map

    def mapRawData(self, data, unit_sys=weewx.US):
        """Maps raw data to weeWX archive record compatible dictionaries.

        Takes an iterable source of raw data observations, maps the fields of
        each row to a list of weeWX compatible archive records and performs any
        necessary unit conversion.

        Input parameters:

            data: iterable that yields the data records to be processed.

            unit_sys: weeWX unit system in which the generated records will be
                      provided. Omission will result in US customary (weewx.US)
                      being used.

        Returns a list of dicts of weeWX compatible archive records.
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
            if 'field_name' in self.map['dateTime']:
                # we have a map for dateTime
                try:
                    _raw_dateTime = _row[self.map['dateTime']['field_name']]
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['dateTime']['field_name'])
                # now process the raw date time data
                if _raw_dateTime.isdigit():
                    # Our dateTime is a number, is it a timestamp already?
                    # Try to use it and catch the error if there is one and
                    # raise it higher.
                    try:
                        _rec_dateTime = int(_raw_dateTime)
                    except:
                        raise ValueError(
                            "Invalid '%s' field. Cannot convert '%s' to timestamp." % (self.map['dateTime']['field_name'],
                                                                                       _raw_dateTime))
                else:
                    # it's a string so try to parse it and catch the error if
                    # there is one and raise it higher
                    try:
                        _datetm = time.strptime(_raw_dateTime,
                                                self.raw_datetime_format)
                        _rec_dateTime = int(time.mktime(_datetm))
                    except:
                        raise ValueError(
                            "Invalid '%s' field. Cannot convert '%s' to timestamp." % (self.map['dateTime']['field_name'],
                                                                                       _raw_dateTime))
                # if we have a timeframe of concern does our record fall within
                # it
                if (self.first_ts is None and self.last_ts is None) or self.first_ts <= _rec_dateTime <= self.last_ts:
                    # we have no timeframe or if we do it falls within it so
                    # save the dateTime
                    _rec['dateTime'] = _rec_dateTime
                else:
                    # it is not so skip to the next record
                    continue
            else:
                # there is no mapped field for dateTime so raise an error
                raise ValueError("No mapping for weeWX field 'dateTime'.")
            # usUnits
            _units = None
            if 'field_name' in self.map['usUnits']:
                # we have a field map for a unit system
                try:
                    # The mapped field is in _row so try to get the raw data.
                    # If its not there then raise an error.
                    _raw_units = int(_row[self.map['usUnits']['field_name']])
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['usUnits']['field_name'])
                # we have a value but is it valid
                if _raw_units in unit_nicknames:
                    # it is valid so use it
                    _units = _raw_units
                else:
                    # the units value is not valid so raise an error
                    _msg = "Invalid unit system '%s'(0x%02x) mapped from data source. Check data source or field mapping." % (_raw_units,
                                                                                                                              _raw_units)
                    raise weewx.UnitError(_msg)
            # interval
            if 'field_name' in self.map['interval']:
                # We have a map for interval so try to get the raw data. If
                # its not there then raise an error.
                try:
                    _tfield = _row[self.map['interval']['field_name']]
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['interval']['field_name'])
                # now process the raw interval data
                if _tfield is not None and _tfield != '':
                    try:
                        interval = int(_tfield)
                    except:
                        raise ValueError(
                            "Invalid '%s' field. Cannot convert '%s' to an integer." % (self.map['interval']['field_name'],
                                                                                        _tfield))
                else:
                    # if it happens to be None then raise an error
                    raise ValueError(
                        "Invalid value '%s' for mapped field '%s' at timestamp '%s'." % (_tfield,
                                                                                         self.map['interval']['field_name'],
                                                                                         timestamp_to_string(_rec['dateTime'])))
            else:
                # we have no mapping so try to calculate it
                interval = self.getInterval(_last_ts, _rec['dateTime'])
            _rec['interval'] = interval
            # now step through the rest of the fields in our map and process
            # the fields that don't require special processing
            for _field in self.map:
                # skip those that have had special processing
                if _field in MINIMUM_MAP:
                    continue
                # process everything else
                else:
                    # is our mapped field in the record
                    if self.map[_field]['field_name'] in _row:

                        # Yes it is. Try to get a value for the obs but if we
                        # can't catch the error
                        try:
                            _temp = float(_row[self.map[_field]['field_name']].strip())
                        except:
                            # perhaps we have a None or a blank/empty entry
                            if _row[self.map[_field]['field_name']] is None or _row[self.map[_field]['field_name']].strip() == '':
                                # if so we will use None
                                _temp = None
                            else:
                                # otherwise we will raise an error
                                _msg = "%s: cannot convert '%s' to float at timestamp '%s'." % (_field,
                                                                                                _row[self.map[_field]['field_name']],
                                                                                                timestamp_to_string(_rec['dateTime']))
                                raise ValueError(_msg)
                        # some fields need some special processing

                        # rain - if our imported 'rain' field is cumulative
                        # (self.rain == 'cumulative') then we need to calculate
                        # the discrete rainfall for this archive period
                        if _field == "rain" and self.rain == "cumulative":
                            _rain = self.getRain(_last_rain, _temp)
                            _last_rain = _temp
                            _temp = _rain

                        # wind - check any wind direction fields are within our
                        # bounds and convert to 0 to 360 range
                        if _field == "windDir" or _field == "windGustDir":
                            if self.wind_dir[0] <= _temp <= self.wind_dir[1]:
                                # normalise to 0 to 360
                                _temp %= 360
                            else:
                                # outside our bounds so set to None
                                _temp = None

                        # UV - if there was no UV sensor used to create the
                        # imported data then we need to set the imported value
                        # to None
                        if _field == 'UV' and not self.UV_sensor:
                            _temp = None

                        # solar radiation - if there was no solar radiation
                        # sensor used to create the imported data then we need
                        # to set the imported value to None
                        if _field == 'radiation' and not self.solar_sensor:
                            _temp = None

                        # if no mapped field for a unit system we have to do
                        # field by field unit conversions
                        if _units is None:
                            _temp_vt = ValueTuple(_temp,
                                                  self.map[_field]['units'],
                                                  weewx.units.obs_group_dict[_field])
                            _conv_vt = convertStd(_temp_vt, unit_sys)
                            _rec[_field] = _conv_vt.value
                        else:
                            # we do have a mapped field for a unit system so
                            # save the field in our record and continue, any
                            # unit conversion will be done in bulk later
                            _rec[_field] = _temp
                    else:
                        # No it's not. Set the field in our output to None
                        _rec[_field] = None
                        # now warn the user about this field if we have not
                        # already done so
                        if self.map[_field]['field_name'] not in _warned:
                            _msg = "Warning: Import field '%s' is mapped to weeWX field '%s'" % (self.map[_field]['field_name'],
                                                                                                 _field)
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            _msg = "         but the import field could not be found."
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            _msg = "         weeWX field '%s' will be set to 'None'." % _field
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            # make sure we do this warning once only
                            _warned.append(self.map[_field]['field_name'])
            # if we have a mapped field for a unit system with a valid value,
            # then all we need do is set 'usUnits', bulk conversion is taken
            # care of by saveToArchive()
            if _units is not None:
                # we have a mapped field for a unit system with a valid value
                _rec['usUnits'] = _units
            else:
                # no mapped field for unit system but we have already converted
                # any necessary fields on a field by field basis so all we need
                # do is set 'usUnits', any bulk conversion will be taken care of
                # by saveToArchive()
                _rec['usUnits'] = unit_sys
            # If interval is being derived from record timestamps our first
            # record will have an interval of None. In this case we wait until
            # we have the second record and then we use the interval between
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
                self.wlog.printlog(syslog.LOG_INFO, "Warning: Records to be imported contain multiple different 'interval' values.")
                print "         This may mean the imported data is missing some records and it may lead"
                print "         to data integrity issues. If the raw data has a known, fixed interval"
                print "         value setting the relevant 'interval' setting in wee_import config to"
                print "         this value may give a better result."
                while self.interval_ans not in ['y', 'n']:
                    self.interval_ans = raw_input('Are you sure you want to proceed (y/n)? ')
                if self.interval_ans == 'n':
                    # the user chose to abort, but we may have already
                    # processed some records. So log it then raise a SystemExit()
                    if self.dry_run:
                        print "Dry run import aborted by user. %d records were processed." % self.total_rec_proc
                    else:
                        if self.total_rec_proc > 0:
                            print "Those records with a timestamp already in the archive will not have been"
                            print "imported. As the import was aborted before completion refer to the weeWX log"
                            print "file to confirm which records were imported."
                            raise SystemExit('Exiting.')
                        else:
                            print "Import aborted by user. No records saved to archive."
                        _msg = "User chose to abort import. %d records were processed. Exiting." % self.total_rec_proc
                        self.wlog.logonly(syslog.LOG_INFO, _msg)
                        raise SystemExit('Exiting. Nothing done.')
            self.wlog.verboselog(syslog.LOG_INFO,
                                 "Mapped %d records." % len(_records))
            # the user wants to continue or we have only one unique value for
            # interval so return the records
            return _records
        else:
            self.wlog.verboselog(syslog.LOG_INFO, "Mapped 0 records.")
            # we have no records to return so return None
            return None

    def getInterval(self, last_ts, current_ts):
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
        except:
            pass
        # how are we getting interval
        if self.interval.lower() == 'conf':
            # get interval from weewx.conf
            return to_int(float(self.config_dict['StdArchive'].get('archive_interval')) / 60.0)
        elif self.interval.lower() == 'derive':
            # get interval from the timestamps of consecutive records
            try:
                _interval = int((current_ts - last_ts) / 60.0)
                # but if _interval < 0 our records are not in date time order
                if _interval < 0:
                    # so raise an error
                    _msg = "Cannot derive 'interval' for record timestamp: %s." % timestamp_to_string(current_ts)
                    self.wlog.printlog(syslog.LOG_INFO, _msg)
                    raise ValueError(
                        "Raw data is not in ascending date time order.")
            except TypeError:
                _interval = None
            return _interval
        else:
            # we don't know what to do so raise an error
            raise ValueError(
                "Cannot derive 'interval'. Unknown 'interval' setting in %s." % self.import_config_path)

    @staticmethod
    def getRain(last_rain, current_rain):
        """Determine the rainfall in a period from two cumulative rainfall
            values.

        If the data source provides rainfall as a cumulative value then the
        rainfall in a period is the simple difference between the two values.
        But we need to take into account some special cases:

        No last_rain value. Will occur for very first record or maybe in an
                            error condition. Need to return 0.0.
        last_rain > current_rain. Occurs when rain counter was reset (maybe
                                  daily or some other period). Need to return
                                  current_rain.

        Input parameters:

            last_rain. Previous rainfall total.
            current_rain. Current rainfall total.

        Returns the rainfall in the period.
        """

        if last_rain is not None:
            # we have a value for the previous period
            if current_rain >= last_rain:
                # just return the difference
                return current_rain - last_rain
            else:
                # we are at at a cumulative reset point so we just want
                # current_rain
                return current_rain
        else:
            # we have no previous rain value so return zero
            return 0.0

    def qc(self, data_dict, data_type):
        """ Apply weewx.conf QC to a record.

        If qc option is set in the import config file then apply any StdQC
        min/max checks specfied in weewx.conf.

        Input parameters:

            data_dict: A weeWX compatible archive record.

        Returns nothing. data_dict is modified directly with obs outside of QC
        limits set to None.
        """

        if self.apply_qc:
            self.import_QC.apply_qc(data_dict, data_type=data_type)

    def calcMissing(self, record):
        """ Add missing observations to a record.

        If calc_missing option is True in the import config file then add any
        missing derived observations (ie observation is missing or None) to the
        imported record. The weeWX WxCalculate class is used to add any missing
        observations.

        Input parameters:

            record: A weeWX compatible archive record.

        Returns a weeWX compatible archive record that includes any derived
        observations that were previously missing/None.
        """

        if self.calc_missing:
            self.wxcalculate.do_calculations(record, 'archive')
        return record

    def saveToArchive(self, archive, records):
        """ Save records to the weeWX archive.

        Supports saving one or more records to archive. Each collection of
        records is processed and saved to archive in transactions of
        self.tranche records at a time.

        if the import config file qc option was set quality checks on the
        imported record are performed using the weeWX StdQC configuration from
        weewx.conf . Any missing derived observations are then added to the
        archive record using the weeWX WXCalculate class if the import config
        file calc_missing option was set. weeWX API addRecord() method is used
        to add archive records.

        If --dry-run was set then every aspect of the import is carried out but
        nothing is saved to archive. If --dry-run was not set then the user is
        requested to confirm the import before any records are saved to archive.

        Input parameters:

            archive: database manager object for the weeWX archive.

            records: iterable that provides weeWX compatible archive records
                     (in dict form) to be written to archive
        """

        if self.first_period:
            # collect the time for some stats reporting later
            self.t1 = time.time()
            # it's convenient to give this message now
            if self.dry_run:
                print 'Starting dry run import ...'
            else:
                print 'Starting import ...'
        # do we have any records?
        if records and len(records) > 0:
            # if this is the first period then give a little summary about what
            # records we have
            if self.first_period:
                if self.last_period:
                    # there is only 1 period, so we can count them
                    print "%s records identified for import." % len(records)
                else:
                    # there are more periods so say so
                    print "Records covering multiple periods have been identified for import."
            # we do, confirm the user actually wants to save them
            while self.ans not in ['y', 'n'] and not self.dry_run:
                print "Proceeding will save all imported records in the weeWX archive."
                self.ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if self.ans == 'y' or self.dry_run:
                # we are going to save them
                # reset record counter
                nrecs = 0
                # initialise our list of records for this tranche
                _tranche = []
                # initialise a set for use in our dry run, this lets us
                # give some better stats on records imported
                unique_set = set()
                # if we are importing multiple periods of data then tell the
                # user what period we are up to
                if not (self.first_period and self.last_period):
                    print "Period %d ..." % self.period_no
                # step through each record in this period
                for _rec in records:
                    # convert our record
                    _conv_rec = to_std_system(_rec, self.archive_unit_sys)
                    # perform any any required QC checks
                    self.qc(_conv_rec, 'Archive')
                    # now add any derived obs that we can to our record
                    _final_rec = self.calcMissing(_rec)
                    # add the record to our tranche and increment our count
                    _tranche.append(_final_rec)
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
                        _msg = "Records processed: %d; Unique records: %d; Last timestamp: %s\r" % (nrecs,
                                                                                                    len(unique_set),
                                                                                                    timestamp_to_string(_final_rec['dateTime']))
                        print >> sys.stdout, _msg,
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
                    _msg = "Records processed: %d; Unique records: %d; Last timestamp: %s\r" % (nrecs,
                                                                                                len(unique_set),
                                                                                                timestamp_to_string(_final_rec['dateTime']))
                    print >> sys.stdout, _msg,
                print
                sys.stdout.flush()
                # update our counts
                self.total_rec_proc += nrecs
                self.total_unique_rec += len(unique_set)
            elif self.ans == 'n':
                # user does not want to import so display a message and then
                # ask to exit
                self.wlog.logonly(syslog.LOG_INFO,
                                  'User chose not to import records. Exiting. Nothing done.')
                raise SystemExit('Exiting. Nothing done.')
        else:
            # we have no records to import, advise the user but what we say
            # will depend if there are any more periods to import
            if self.first_period and self.last_period:
                # there was only 1 period
                _msg = 'No records identified for import.'
            else:
                # multiple periods
                _msg = 'Period %d - no records identified for import.' % self.period_no
            print _msg
        # if we have finished record the time taken for our summary
        if self.last_period:
            self.tdiff = time.time() - self.t1


# ============================================================================
#                              class WeeImportLog
# ============================================================================


class WeeImportLog(object):
    """Class to handle wee_import logging.

    This class provides a wrapper around the python syslog module to handle
    wee_import logging requirements. The --log=- command line option disables
    log output otherwise log output is sent to the same log used by weeWX.
    """

    def __init__(self, opt_logging, opt_verbose, opt_dry_run):
        """Initialise our log environment."""

        # first check if we are turning off log to file or not
        if opt_logging:
            log_bool = opt_logging.strip() == '-'
        else:
            log_bool = False
        # Flag to indicate whether we are logging to file or not. Log to file
        # every time except when logging is explicitly turned off on the
        # command line or its a dry run.
        self.log = not (opt_dry_run or log_bool)
        # if we are logging then setup our syslog environment
        # if --verbose we log up to syslog.LOG_DEBUG
        # otherwise just log up to syslog.LOG_INFO
        if self.log:
            syslog.openlog(logoption=syslog.LOG_PID | syslog.LOG_CONS)
            if opt_verbose:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
            else:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
        # logging by other modules (eg WxCalculate) does not use WeeImportLog
        # but we can disable most logging by raising the log priority if its a
        # dry run
        if opt_dry_run:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_CRIT))
        # keep opt_verbose for later
        self.verbose = opt_verbose

    def logonly(self, level, message):
        """Log to file only."""

        # are we logging ?
        if self.log:
             # add a little preamble to say this is wee_import
            _message = 'wee_import: ' + message
            syslog.syslog(level, _message)

    def printlog(self, level, message):
        """Print to screen and log to file."""

        print message
        self.logonly(level, message)

    def verboselog(self, level, message):
        """Print to screen if --verbose and log to file always."""

        if self.verbose:
            print message
            self.logonly(level, message)


# ============================================================================
#                             Utility functions
# ============================================================================


def get_binding(config_dict):
    """Get the binding for the weeWX database."""

    # Extract our binding from the StdArchive section of the config file. If
    # it's missing, return None.
    if 'StdArchive' in config_dict:
        db_binding_wx = config_dict['StdArchive'].get('data_binding',
                                                      'wx_binding')
    else:
        db_binding_wx = None
    return db_binding_wx

