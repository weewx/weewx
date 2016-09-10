#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

from __future__ import with_statement

"""Module providing the base classes and API for importing observational data
into weewx.
"""

# Python imports
import datetime
import os.path
import re
import sys
import syslog
import time

from datetime import datetime as dt

# weewx imports
import weecfg
import weewx
import weewx.wxservices

from weewx.manager import open_manager_with_config
from weewx.units import unit_constants, unit_nicknames, convertStd, to_std_system, ValueTuple
from weeutil.weeutil import timestamp_to_string, option_as_list, to_int, tobool, _get_object

# List of sources we support
SUPPORTED_SOURCES = ['CSV', 'WU', 'Cumulus']

# Minimum requirements in any explicit or implicit weewx field-to-import field
# map
MINIMUM_MAP = {'dateTime': {'units': 'unix_epoch'},
               'usUnits': {'units': None},
               'interval': {'units': 'minute'}}


# ============================================================================
#                                Error Classes
# ============================================================================


class WeeImportMapError(Exception):
    """Base class of exceptions thrown when encountering an error with an
       external source-to-weewx field map.
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
        to import records into the weewx archive.

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
            dicts whose fields can be mapped to a weewx archive field
        -   defines an import data field-to-weewx archive field map (self.map)

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

        # save our weewx config dict
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
        # sensor was present. The weewx convention is to store the None value
        # when a sensor or observation does not exist. Record whether UV and/or
        # solar radiation sensor was present.
        # UV, default to True
        self.UV_sensor = tobool(import_config_dict.get('UV', True))
        # solar, default to True
        self.solar_sensor = tobool(import_config_dict.get('radiation', True))

        # get some weewx database info
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

        # get ourselves an ImportQC object to do QC on imported records
        self.import_QC = ImportQC(config_dict, log)

        # Process our command line options
        self.dry_run = options.dry_run
        self.verbose = options.verbose
        # If a --date command line option was used then we need to determine
        # the time span over which we will import any records. We will import
        # records that have dateTime > self.first_ts and <=self.last_ts.
        if options.date:
            # do we have a date range or a single date only - look for the '-'
            dates = options.date.split('-', 1)
            if len(dates) > 1:
                # we have a range
                # first try to get a date and time for each
                try:
                    _first = dt.strptime(dates[0], "%Y/%m/%d %H:%M")
                    _first_tt = _first.timetuple()
                    _last = dt.strptime(dates[1], "%Y/%m/%d %H:%M")
                    _last_tt = _last.timetuple()
                    self.first_ts = time.mktime(_first_tt)
                    self.last_ts = time.mktime(_last_tt)
                except ValueError:
                    # that did not work so try to get a date for each
                    try:
                        _first = dt.strptime(dates[0], "%Y/%m/%d")
                        _first_tt = _first.timetuple()
                        _last = (dt.strptime(dates[1], "%Y/%m/%d") +
                                 datetime.timedelta(days=1))
                        _last_tt = _last.timetuple()
                        self.first_ts = time.mktime(_first_tt)
                        self.last_ts = time.mktime(_last_tt)
                    except:
                        raise ValueError(
                            "Cannot parse --date argument '%s'." % options.date)
            else:
                # we have a date
                _first_dt = dt.strptime(dates[0], "%Y/%m/%d")
                _first_tt = _first_dt.timetuple()
                _last_dt = _first_dt + datetime.timedelta(days=1)
                _last_tt = _last_dt.timetuple()
                self.first_ts = time.mktime(_first_tt)
                self.last_ts = time.mktime(_last_tt)
        else:
            # no date on the command line so set our first/last ts to None
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

        # get some key weewx parameters
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
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)
                _raw_data = self.getRawData(period)
                _msg = 'Raw import data read successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)

                # map the raw data to a weewx archive compatible dictionary
                _msg = 'Mapping raw import data for period %d...' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)
                _mapped_data = self.mapRawData(_raw_data, weewx.US)
                _msg = 'Raw import data mapped successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)

                # save the mapped data to archive
                _msg = 'Saving mapped data to archive for period %d...' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)
                self.saveToArchive(archive, _mapped_data)
                _msg = 'Mapped data saved to archive successfully for period %d.' % self.period_no
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)

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
                    print 'Whilst %d unique records were processed those with a timestamp already in the archive' % (self.total_unique_rec, )
                    print 'will not have been imported. Confirm successful import in the weewx log file.'

    def parseMap(self, source_type, source, import_config_dict):
        """Produce a source field-to-weewx archive field data map.

        Data from an external source can be mapped to the weewx archive using a
        fixed map (WU) or through a user defined map in the import config file.
        First look for a map in the wee_import conf file, if the map is valid
        then return it. If the map is not valid or not found then return the
        default map.

        Input parameters:

            source_type: String holding name of the section in
                         import_config_dict the holds config details for the
                         source being used.

            source: Iterable holding the source data. Used if import field
                    names are included in the source data (eg CSV).

            import_config_dict: wee_import config dict.

        Returns a map as a dictionary of elements with each element structured
        as follows:

            'arch_filed_name': {'name': 'field_name', 'units': 'unit_name'}

            where:

                - arch_filed_name is an observation name in the weewx database
                  schema
                - field_name is the name of a field from the external source
                - unit_name is the weewx unit name of the units used by
                  field_name
        """

        # start with the minimum map
        _map = dict(MINIMUM_MAP)
        # look for a mapping for source in our config dict otherwise use the
        # default
        # do we have a [source_type] stanza?
        if 'Map' in import_config_dict:
            # we have a wee_import.conf map so lets get it
            for _field in import_config_dict['Map']:
                _entry = option_as_list(import_config_dict['Map'][_field])
                # expect 2 parameters for each option
                if len(_entry) == 2:
                    # we have 2 parameter so that's name and units
                    _map[_field] = {'name': _entry[0], 'units': _entry[1]}
                # if the entry is not empty then it might be valid
                elif _entry != [''] and len(_entry) == 1:
                    # we have 1 parameter so it must be just name
                    _map[_field] = {'name': _entry[0]}
                else:
                    # otherwise its invalid so ignore it
                    pass
            # do some crude error checking
            # we must have a dateTime entry
            if _map['dateTime'] is not None:
                # do we have a unit system specified (ie a 'usUnits' entry)
                if 'usUnits' not in _map:
                    # no unit system mapping do we have units specified for
                    # each individual field
                    for _field in _map:
                        if _field not in ['dateTime', 'usUnits']:
                            if 'units' in _map[_field]:
                                # we have a units field, do we know about it
                                if _map[_field]['units'] not in weewx.units.default_unit_format_dict:
                                    # we have an invalid unit string so tell
                                    # the user and exit
                                    raise weewx.UnitError(
                                        "Unknown units '%s' specified for field '%s' in %s." % (_map[_field]['units'],
                                                                                                _field,
                                                                                                self.import_config_path))
            else:
                # no dateTime map so tell the user and exit
                raise WeeImportMapError(
                    "'%s' field map found but no mapping specified for field 'dateTime'." % source_type)
            # if we got this far we have a usable map, advise the user what we
            # will use
            _msg = "The following imported field-to-weewx field map will be used:"
            if self.verbose:
                self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)
            else:
                self.wlog.logonly(syslog.LOG_INFO, _msg)
            for key, entry in _map.iteritems():
                if 'name' in entry:
                    _units_msg = ""
                    if 'units' in entry:
                        _units_msg = " in units '%s'" % entry['units']
                    _msg = "     import field '%s'%s --> weewx field '%s'" % (key,
                                                                              _units_msg,
                                                                              entry['name'])
                    if self.verbose:
                        self.wlog.verboselog(syslog.LOG_INFO, _msg, self.verbose)
                    else:
                        self.wlog.logonly(syslog.LOG_INFO, _msg)
        elif self._header_map:
            # We have a static map that maps header fields to weewx (eg WU).
            # Step through each field name in our data.
            for _key in source.fieldnames:
                # if we know about the field name add it to our map
                if _key in self._header_map:
                    _map[self._header_map[_key]['map_to']] = {'name': _key,
                                                              'units': self._header_map[_key]['units']}
        else:
            # no [[Map]] stanza and no _header_map so raise an error as we
            # don't know what to map
            _msg = "No '%s' field map found in %s." % (source_type,
                                                       self.import_config_path)
            raise WeeImportMapError(_msg)
        return _map

    def mapRawData(self, data, unit_sys=weewx.US):
        """Maps raw data to weewx archive record compatible dictionaries.

        Takes an iterable source of raw data observations, maps the fields of
        each row to a list of weewx compatible archive records and performs any
        necessary unit conversion.

        Input parameters:

            data: iterable that yields the data records to be processed.

            unit_sys: weewx unit system in which the generated records will be
                      provided. Omission will result in US customary (weewx.US)
                      being used.

        Returns a list of dicts of weewx compatible archive records.
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
            if 'name' in self.map['dateTime']:
                # we have a map for dateTime
                try:
                    _raw_dateTime = _row[self.map['dateTime']['name']]
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['dateTime']['name'])
                # now process the raw date time data
                if _raw_dateTime.isdigit():
                    # Our dateTime is a number, is it a timestamp already?
                    # Try to use it and catch the error if there is one and
                    # raise it higher.
                    try:
                        _rec_dateTime = int(_raw_dateTime)
                    except:
                        raise ValueError(
                            "Invalid '%s' field. Cannot convert '%s' to timestamp." % (self.map['dateTime']['name'],
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
                            "Invalid '%s' field. Cannot convert '%s' to timestamp." % (self.map['dateTime']['name'],
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
                raise ValueError("No mapping for weewx field 'dateTime'.")
            # usUnits
            _units = None
            if 'name' in self.map['usUnits']:
                # we have a field map for a unit system
                try:
                    # The mapped field is in _row so try to get the raw data.
                    # If its not there then raise an error.
                    _raw_units = int(_row[self.map['usUnits']['name']])
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['usUnits']['name'])
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
            if 'name' in self.map['interval']:
                # We have a map for interval so try to get the raw data. If
                # its not there then raise an error.
                try:
                    _tfield = _row[self.map['interval']['name']]
                except:
                    raise WeeImportFieldError(
                        "Field '%s' not found in source data." % self.map['interval']['name'])
                # now process the raw interval data
                if _tfield is not None and _tfield != '':
                    try:
                        interval = int(_tfield)
                    except:
                        raise ValueError(
                            "Invalid '%s' field. Cannot convert '%s' to an integer." % (self.map['interval']['name'],
                                                                                        _tfield))
                else:
                    # if it happens to be None then raise an error
                    raise ValueError(
                        "Invalid value '%s' for mapped field '%s' at timestamp '%s'." % (_tfield,
                                                                                         self.map['interval']['name'],
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
                    if self.map[_field]['name'] in _row:

                        # Yes it is. Try to get a value for the obs but if we
                        # can't catch the error
                        try:
                            _temp = float(_row[self.map[_field]['name']].strip())
                        except:
                            # perhaps we have a blank/empty entry
                            if _row[self.map[_field]['name']].strip() == '':
                                # if so we will use None
                                _temp = None
                            else:
                                # otherwise we will raise an error
                                _msg = "%s: cannot convert '%s' to float at timestamp '%s'." % (_field,
                                                                                                _row[self.map[_field]['name']],
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
                        if self.map[_field]['name'] not in _warned:
                            _msg = "Warning: Import field '%s' is mapped to weewx field '%s'" % (self.map[_field]['name'],
                                                                                                 _field)
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            _msg = "         but the import field could not be found."
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            _msg = "         weewx field '%s' will be set to 'None'." % _field
                            self.wlog.printlog(syslog.LOG_INFO, _msg)
                            # make sure we do this warning once only
                            _warned.append(self.map[_field]['name'])
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
                print "         to data integrity issues. If the raw data has a known, fixed interval value"
                print "         setting the relevant 'interval' setting in wee_import config to this value"
                print "         may give a better result."
                while self.interval_ans not in ['y', 'n']:
                    self.interval_ans = raw_input('Are you sure you want to proceed (y/n)? ')
                if self.interval_ans == 'n':
                    # the user chose to abort, but we may have already
                    # processed some records. So log it then raise a SystemExit()
                    if self.dry_run:
                        print "Dry run import aborted by user. %d records were processed." % self.total_rec_proc
                        self.wlog.logonly(syslog.LOG_INFO, 'User chose to abort import. Exiting. Nothing done.')
                        raise SystemExit('Exiting. Nothing done.')
                    else:
                        print "Whilst %d records were processed those with a timestamp already in the archive" % self.total_rec_proc
                        print "will not have been imported. Confirm successful import in syslog or weewx log file."
                        _msg = "User chose to abort import. %d records were processed. Exiting." % self.total_rec_proc
                        self.wlog.logonly(syslog.LOG_INFO, _msg)
                        if self.total_rec_proc > 0:
                            print "As the import was aborted before completion refer to the weewx log"
                            print "file to confirm which records were imported."
                            raise SystemExit('Exiting.')
                        raise SystemExit('Exiting. Nothing done.')
            self.wlog.verboselog(syslog.LOG_INFO,
                                 "Mapped %d records." % len(_records),
                                 self.verbose)
            # the user wants to continue or we have only one unique value for
            # interval so return the records
            return _records
        else:
            self.wlog.verboselog(syslog.LOG_INFO,
                                 "Mapped 0 records.",
                                 self.verbose)
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

    def qc(self, record):
        """ Apply weewx.conf QC to a record.

        If qc option is set in the import config file then apply any StdQC
        min/max checks specfied in weewx.conf.

        Input parameters:

            record: A weewx compatible archive record.

        Returns nothing. record is modified directly with obs outside of QC
        limits set to None.
        """

        if self.apply_qc:
            self.import_QC.apply_qc(record)

    def calcMissing(self, record):
        """ Add missing observations to a record.

        If calc_missing option is True in the import config file then add any
        missing derived observations (ie observation is missing or None) to the
        imported record. The weewx WxCalculate class is used to add any missing
        observations.

        Input parameters:

            record: A weewx compatible archive record.

        Returns a weewx compatible archive record that includes any derived
        observations that were previously missing/None.
        """

        if self.calc_missing:
            self.wxcalculate.do_calculations(record, 'archive')
        return record

    def saveToArchive(self, archive, records):
        """ Save records to the weewx archive.

        Supports saving one or more records to archive. Each collection of
        records is processed and saved to archive in transactions of
        self.tranche records at a time.

        if the import config file qc option was set quality checks on the
        imported record are performed using the weewx StdQC configuration from
        weewx.conf . Any missing derived observations are then added to the
        archive record using the weewx WXCalculate class if the import config
        file calc_missing option was set. weewx API addRecord() method is used
        to add archive records.

        If --dry-run was set then every aspect of the import is carried out but
        nothing is saved to archive. If --dry-run was not set then the user is
        requested to confirm the import before any records are saved to archive.

        Input parameters:

            archive: database manager object for the weewx archive.

            records: iterable that provides weewx compatible archive records
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
                print "Proceeding will save all imported records in the weewx archive."
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
                    self.qc(_conv_rec)
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
    log output otherwise log output is sent to the same log used by weewx.
    """

    def __init__(self, opt_logging, verbose, dry_run):
        """Initialise our log environment."""

        # first check if we are turning off log to file or not
        if opt_logging:
            log_bool = opt_logging.strip() == '-'
        else:
            log_bool = False
        # Flag to indicate whether we are logging to file or not. Log to file
        # every time except when logging is explicitly turned off on the
        # command line or its a dry run.
        self.log = not (dry_run or log_bool)
        # if we are logging then setup our syslog environment
        # if --verbose we log up to syslog.LOG_DEBUG
        # otherwise just log up to syslog.LOG_INFO
        if self.log:
            syslog.openlog(logoption=syslog.LOG_PID | syslog.LOG_CONS)
            if verbose:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
            else:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
        # logging by other modules (eg WxCalculate) does not use WeeImportLog
        # but we can disable most logging by raising the log priority if its a
        # dry run
        if dry_run:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_CRIT))

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

    def verboselog(self, level, message, verbose):
        """Print to screen if --verbose and log to file always."""

        if verbose:
            print message
            self.logonly(level, message)


# ============================================================================
#                              class ImportQC
# ============================================================================


class ImportQC(object):
    """Class to perform weewx like quality check on imported records."""

    def __init__(self, config_dict, log):

        # give our object some logging abilities
        self.wlog = log

        # If the 'StdQC' or 'MinMax' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done.
        try:
            mm_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            self.wlog.printlog(syslog.LOG_INFO,
                               "No QC information in weewx config file.")
            return

        self.min_max_dict = {}

        target_unit_name = config_dict['StdConvert']['target_unit']
        target_unit = unit_constants[target_unit_name.upper()]
        converter = weewx.units.StdUnitConverters[target_unit]

        for obs_type in mm_dict.scalars:
            minval = float(mm_dict[obs_type][0])
            maxval = float(mm_dict[obs_type][1])
            if len(mm_dict[obs_type]) == 3:
                group = weewx.units._getUnitGroup(obs_type)
                vt = (minval, mm_dict[obs_type][2], group)
                minval = converter.convert(vt)[0]
                vt = (maxval, mm_dict[obs_type][2], group)
                maxval = converter.convert(vt)[0]
            self.min_max_dict[obs_type] = (minval, maxval)

    def apply_qc(self, record):
        """Apply quality check to the data in a record."""

        # step through each ob type for which we have QC limits
        for obs_type in self.min_max_dict:
            # do we have that obs in our record and does it have a vallue
            if record.has_key(obs_type) and record[obs_type] is not None:
                # is our obs value outside our QC limits
                if not self.min_max_dict[obs_type][0] <= record[obs_type] <= self.min_max_dict[obs_type][1]:
                    # yes, inform the user if we applied a QC limit
                    _msg = "%s record value '%s' %s outside limits (%s, %s)" % (timestamp_to_string(record['dateTime']),
                                                                                obs_type, record[obs_type],
                                                                                self.min_max_dict[obs_type][0],
                                                                                self.min_max_dict[obs_type][1])
                    self.wlog.printlog(syslog.LOG_INFO, _msg)
                    # finally set the offending obs to None
                    record[obs_type] = None


# ============================================================================
#                             Utility functions
# ============================================================================


def get_binding(config_dict):
    """Get the binding for the weewx database."""

    # Extract our binding from the StdArchive section of the config file. If
    # it's missing, return None.
    if 'StdArchive' in config_dict:
        db_binding_wx = config_dict['StdArchive'].get('data_binding',
                                                      'wx_binding')
    else:
        db_binding_wx = None
    return db_binding_wx

