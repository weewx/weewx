#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and
#                            Gary Roderick
#
#    See the file LICENSE.txt for your full rights.
#
"""Module for use with weeimport to import observational data from Weather 
Display monthly log files.
"""

# Python imports
import collections
import csv
import datetime
import glob
import io
import logging
import operator
import os
import time

# WeeWX imports
from . import weeimport
import weeutil.weeutil
import weewx

from weeutil.weeutil import timestamp_to_string
from weewx.units import unit_nicknames

log = logging.getLogger(__name__)

# ============================================================================
#                             class WDSource
# ============================================================================


class WDSource(weeimport.Source):
    """Class to interact with a Weather Display generated monthly log files.

    Handles the import of data from WD monthly log files. WD stores observation
    data across a number of monthly log files. Each log file contains one month
    of minute separated data in structured text or csv format.

    Data is imported from all monthly log files found in the source directory
    one set of monthly log files at a time. Units of measure are not specified
    in the monthly log files so the units of measure must be specified in the
    wee_import config file. Whilst the WD monthly log file formats are well
    defined, some pre-processing of the data is required to provide data in a
    format suitable for use in the wee_import mapping methods.

    WD log file units are set to either Metric or US in WD via the 'Log File'
    setting under 'Units' on the 'Units/Wind Chill' tab of the universal setup.
    The units used in each log file in each case are:

    Log File                            Field               Metric      US
                                                            Units       Units
    MMYYYYlg.txt                        day
    MMYYYYlg.txt                        month
    MMYYYYlg.txt                        year
    MMYYYYlg.txt                        hour
    MMYYYYlg.txt                        minute
    MMYYYYlg.txt                        temperature         C           F
    MMYYYYlg.txt                        humidity            %           %
    MMYYYYlg.txt                        dewpoint            C           F
    MMYYYYlg.txt                        barometer           hPa         inHg
    MMYYYYlg.txt                        windspeed           knots       mph
    MMYYYYlg.txt                        gustspeed           knots       mph
    MMYYYYlg.txt                        direction           degrees     degrees
    MMYYYYlg.txt                        rainlastmin         mm          inch
    MMYYYYlg.txt                        dailyrain           mm          inch
    MMYYYYlg.txt                        monthlyrain         mm          inch
    MMYYYYlg.txt                        yearlyrain          mm          inch
    MMYYYYlg.txt                        heatindex           C           F
    MMYYYYvantagelog.txt                Solar radiation     W/sqm       W/sqm
    MMYYYYvantagelog.txt                UV                  index       index
    MMYYYYvantagelog.txt                Daily ET            mm          inch
    MMYYYYvantagelog.txt                soil moist          cb          cb
    MMYYYYvantagelog.txt                soil temp           C           F
    MMYYYYvantageextrasensrslog.txt     temp1-temp7         C           F
    MMYYYYvantageextrasensrslog.txt     hum1-hum7           %           %
    """

    # Dict of log files and field names that we know how to process. Field
    # names would normally be derived from the first line of log file but
    # inconsistencies in field naming in the log files make this overly
    # complicated and difficult. 'fields' entry can be overridden from import
    # config if required.
    logs = {'lg.txt': {'fields': ['day', 'month', 'year', 'hour', 'minute',
                                  'temperature', 'humidity', 'dewpoint',
                                  'barometer', 'windspeed', 'gustspeed',
                                  'direction', 'rainlastmin', 'dailyrain',
                                  'monthlyrain', 'yearlyrain', 'heatindex']
                       },
            'lgcsv.csv': {'fields': ['day', 'month', 'year', 'hour', 'minute',
                                     'temperature', 'humidity', 'dewpoint',
                                     'barometer', 'windspeed', 'gustspeed',
                                     'direction', 'rainlastmin', 'dailyrain',
                                     'monthlyrain', 'yearlyrain', 'heatindex']
                          },
            'vantageextrasensorslog.csv': {'fields': ['day', 'month', 'year',
                                                      'hour', 'minute', 'temp1',
                                                      'temp2', 'temp3', 'temp4',
                                                      'temp5', 'temp6', 'temp7',
                                                      'hum1', 'hum2', 'hum3',
                                                      'hum4', 'hum5', 'hum6',
                                                      'hum7']
                                           },
            'vantagelog.txt': {'fields': ['day', 'month', 'year', 'hour',
                                          'minute', 'radiation', 'UV',
                                          'dailyet', 'soilmoist',
                                          'soiltemp']
                               },
            'vantagelogcsv.csv': {'fields': ['day', 'month', 'year', 'hour',
                                             'minute', 'radiation', 'UV',
                                             'dailyet', 'soilmoist',
                                             'soiltemp']
                                  }
            }

    # dict to lookup WD log field units based on the WD logging Metric or US
    # unit system
    wd_unit_sys = {'temperature': {'METRIC': 'degree_C', 'US': 'degree_F'},
                   'pressure': {'METRIC': 'hPa', 'US': 'inHg'},
                   'rain': {'METRIC': 'mm', 'US': 'inch'},
                   'speed': {'METRIC': 'knot', 'US': 'mile_per_hour'}
                   }

    # tuple of fields using 'temperature' units
    _temperature_fields = ('temperature', 'dewpoint', 'heatindex', 'soiltemp',
                           'temp1', 'temp2', 'temp3', 'temp4', 'temp5',
                           'temp6', 'temp7')
    # tuple of fields using 'pressure' units
    _pressure_fields = ('barometer', )
    # tuple of fields using 'rain' units
    _rain_fields = ('rainlastmin', 'daily_rain', 'monthlyrain', 'yearlyrain', 'dailyet')
    # tuple of fields using 'speed' units
    _speed_fields = ('windspeed', 'gustspeed')

    # dict to map all possible WD field names (refer _field_list) to WeeWX
    # archive field names and units
    default_map = {
        'dateTime': {
            'source_field': 'datetime',
            'unit': 'unix_epoch'},
        'outTemp': {
            'source_field': 'temperature'},
        'outHumidity': {
            'source_field': 'humidity',
            'unit': 'percent'},
        'dewpoint': {
            'source_field': 'dewpoint'},
        'heatindex': {
            'source_field': 'heatindex'},
        'barometer': {
            'source_field': 'barometer'},
        'rain': {
            'source_field': 'rainlastmin'},
        'windSpeed': {
            'source_field': 'windspeed'},
        'windDir': {
            'source_field': 'direction',
            'unit': 'degree_compass'},
        'windGust': {
            'source_field': 'gustspeed'},
        'radiation': {
            'source_field': 'radiation',
            'unit': 'watt_per_meter_squared'},
        'UV': {
            'source_field': 'uv',
            'unit': 'uv_index'},
        'ET': {
            'source_field': 'dailyet',
            'is_cumulative': True},
        'soilMoist1': {
            'source_field': 'soilmoist',
            'unit': 'centibar'},
        'soilTemp1': {
            'source_field': 'soiltemp'},
        'extraTemp1': {
            'source_field': 'temp1'},
        'extraHumid1': {
            'source_field': 'humid1'},
        'extraTemp2': {
            'source_field': 'temp2'},
        'extraHumid2': {
            'source_field': 'humid2'},
        'extraTemp3': {
            'source_field': 'temp3'},
        'extraHumid3': {
            'source_field': 'humid3'},
        'extraTemp4': {
            'source_field': 'temp4'},
        'extraHumid4': {
            'source_field': 'humid4'},
        'extraTemp5': {
            'source_field': 'temp5'},
        'extraHumid5': {
            'source_field': 'humid5'},
        'extraTemp6': {
            'source_field': 'temp6'},
        'extraHumid6': {
            'source_field': 'humid6'},
        'extraTemp7': {
            'source_field': 'temp7'},
        'extraHumid7': {
            'source_field': 'humid7'}
    }

    def __init__(self, config_path, config_dict, import_config_path,
                 wd_config_dict, **kwargs):

        # call our parents __init__
        super().__init__(config_dict, wd_config_dict, **kwargs)

        # save the import config path
        self.import_config_path = import_config_path
        # save the import config dict
        self.wd_config_dict = wd_config_dict

        # our parent uses 'derive' as the default interval setting, for WD the
        # default should be 1 (minute) so redo the interval setting with our
        # default
        self.interval = wd_config_dict.get('interval', 1)

        # wind dir bounds
        self.wind_dir = [0, 360]

        # field delimiter used in text format monthly log files, default to
        # space
        self.txt_delimiter = str(wd_config_dict.get('txt_delimiter', ' '))
        # field delimiter used in csv format monthly log files, default to
        # comma
        self.csv_delimiter = str(wd_config_dict.get('csv_delimiter', ','))

        # ignore extreme > 255.0 values for temperature and humidity fields
        self.ignore_extr_th = weeutil.weeutil.tobool(wd_config_dict.get('ignore_extreme_temp_hum',
                                                                        True))

        # initialise the import field-to-WeeWX archive field map
        _map = dict(WDSource.default_map)
        # create the final field map based on the default field map and any
        # field map options provided by the user
        self.map = self.parse_map(_map,
                                  self.wd_config_dict.get('FieldMap', {}),
                                  self.wd_config_dict.get('FieldMapExtensions', {}))

        # property holding the current log file name being processed
        self.file_name = None

        # obtain a list of logs files to be processed
        _to_process = wd_config_dict.get('logs_to_process', list(self.logs.keys()))
        self.logs_to_process = weeutil.weeutil.option_as_list(_to_process)

        # can missing log files be ignored
        self.ignore_missing_log = weeutil.weeutil.to_bool(wd_config_dict.get('ignore_missing_log',
                                                                             True))

        # get our source file path
        try:
            self.source = wd_config_dict['directory']
        except KeyError:
            _msg = "Weather Display monthly logs directory not " \
                   "specified in '%s'." % import_config_path
            raise weewx.ViolatedPrecondition(_msg)

        # get the source file encoding, default to utf-8-sig
        self.source_encoding = self.wd_config_dict.get('source_encoding',
                                                       'utf-8-sig')

        # Now get a list on monthly log files sorted from oldest to newest.
        # This is complicated by the log file naming convention used by WD.
        # first the 1 digit months
        _lg_5_list = glob.glob(self.source + '/' + '[0-9]' * 5 + 'lg.txt')
        # and the 2 digit months
        _lg_6_list = glob.glob(self.source + '/' + '[0-9]' * 6 + 'lg.txt')
        # concatenate the two lists to get the complete list
        month_lg_list = _lg_5_list + _lg_6_list
        # create a list of log files in chronological order (month, year)
        _temp = []
        # create a list of log files, adding year and month fields for sorting
        for p in month_lg_list:
            # obtain the file name
            fn = os.path.split(p)[1]
            # obtain the numeric part of the file name
            _digits = ''.join(c for c in fn if c.isdigit())
            # append a list of format [path+file name, month, year]
            _temp.append([p, int(_digits[:-4]), int(_digits[-4:])])
        # now sort the list keeping just the log file path and name
        self.log_list = [a[0] for a in sorted(_temp, key=lambda el: (el[2], el[1]))]
        # if there are no log files then there is nothing to be done
        if len(self.log_list) == 0:
            raise weeimport.WeeImportIOError("No Weather Display monthly logs "
                                             "found in directory '%s'." % self.source)
        # Some log files have entries that belong in a different month.
        # Initialise a list to hold these extra records for processing during
        # the appropriate month
        self.extras = {}
        for log_to_process in self.logs_to_process:
            self.extras[log_to_process] = []

        # property holding dict of last seen values for cumulative observations
        self.last_values = {}

        # tell the user/log what we intend to do
        _msg = "Weather Display monthly log files in the '%s' " \
               "directory will be imported" % self.source
        print(_msg)
        log.info(_msg)
        _msg = "The following options will be used:"
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     config=%s, import-config=%s" % (config_path,
                                                     self.import_config_path)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        if kwargs['date']:
            _msg = "     date=%s" % kwargs['date']
        else:
            # we must have --from and --to
            _msg = "     from=%s, to=%s" % (kwargs['from_datetime'], kwargs['to_datetime'])
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     dry-run=%s, calc_missing=%s, " \
               "ignore_invalid_data=%s" % (self.dry_run,
                                           self.calc_missing,
                                           self.ignore_invalid_data)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     tranche=%s, interval=%s" % (self.tranche,
                                                 self.interval)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "     UV=%s, radiation=%s ignore extreme temperature " \
               "and humidity=%s" % (self.UV_sensor,
                                    self.solar_sensor,
                                    self.ignore_extr_th)
        if self.verbose:
            print(_msg)
        log.debug(_msg)
        _msg = "Using database binding '%s', which is bound to " \
               "database '%s'" % (self.db_binding_wx,
                                  self.dbm.database_name)
        print(_msg)
        log.info(_msg)
        _msg = "Destination table '%s' unit system " \
               "is '%#04x' (%s)." % (self.dbm.table_name,
                                     self.archive_unit_sys,
                                     unit_nicknames[self.archive_unit_sys])
        print(_msg)
        log.info(_msg)
        self.print_map()
        if self.calc_missing:
            print("Missing derived observations will be calculated.")
        if not self.UV_sensor:
            print("All WeeWX UV fields will be set to None.")
        if not self.solar_sensor:
            print("All WeeWX radiation fields will be set to None.")
        if kwargs['date'] or kwargs['from_datetime']:
            print("Observations timestamped after %s and "
                  "up to and" % timestamp_to_string(self.first_ts))
            print("including %s will be imported." % timestamp_to_string(self.last_ts))
        if self.dry_run:
            print("This is a dry run, imported data will not be saved to archive.")

    def get_raw_data(self, period):
        """ Obtain raw observation data from a log file.

        The getRawData() method must return a single iterable containing the
        raw observational data for the period. Since Weather Display uses more
        than one log file per month the data from all relevant log files needs
        to be combined into a single dict. A date-time field must be generated
        for each row and the resulting raw data dict returned.

        Input parameters:

            period: the file name, including path, of the Weather Display monthly
                    log file from which raw obs data will be read.
        """

        # since we may have multiple log files to parse for a given period
        # strip out the month-year portion of the log file
        _path, _file = os.path.split(period)
        _prefix = _file[:-6]
        _month = _prefix[:-4]
        _year = _prefix[-4:]

        # initialise a list to hold the list of dicts read from each log file
        _data_list = []
        # iterate over the log files to processed
        for lg in self.logs_to_process:
            # obtain the path and file name of the log we are to process
            _fn = '%s%s' % (_prefix, lg)
            _path_file_name = os.path.join(_path, _fn)

            # check that the log file exists
            if os.path.isfile(_path_file_name):
                # It exists.  The source file may use some encoding, if we can't
                # decode it raise a WeeImportDecodeError.
                try:
                    with io.open(_path_file_name, mode='r', encoding=self.source_encoding) as f:
                        _raw_data = f.readlines()
                except UnicodeDecodeError as e:
                    # not a utf-8 based encoding, so raise a WeeImportDecodeError
                    raise weeimport.WeeImportDecodeError(e)
            else:
                # log file does not exist ignore it if we are allowed else
                # raise it
                if self.ignore_missing_log:
                    continue
                else:
                    _msg = "Weather Display monthly log file '%s' could " \
                           "not be found." % _path_file_name
                    raise weeimport.WeeImportIOError(_msg)

            # Determine delimiter to use. This is a simple check, if 'csv'
            # exists anywhere in the file name then assume a csv and use the
            # csv delimiter otherwise use the txt delimiter
            _del = self.csv_delimiter if 'csv' in lg.lower() else self.txt_delimiter

            # the raw data needs a bit of cleaning up before we can parse/map it
            _clean_data = []
            for i, _row in enumerate(_raw_data):
                # do a crude check of the expected v actual number of columns
                # since we are not aware whether the WD log files structure may
                # have changed over time

                # ignore the first line, it will likely be header info
                if i == 2 and \
                        len(" ".join(_row.split()).split(_del)) != len(self.logs[lg]['fields']):
                    _msg = "Unexpected number of columns found in '%s': " \
                           "%s v %s" % (_fn,
                                        len(_row.split(_del)),
                                        len(self.logs[lg]['fields']))
                    print(_msg)
                    log.info(_msg)
                # check for and remove any null bytes
                clean_row = _row
                if "\x00" in _row:
                    clean_row = clean_row.replace("\x00", "")
                    _msg = "One or more null bytes found in and removed " \
                           "from row %d in file '%s'" % (i, _fn)
                    print(_msg)
                    log.info(_msg)
                # make sure we have full stops as decimal points
                _clean_data.append(clean_row.replace(self.decimal_sep, '.'))

            # initialise a list to hold our processed data for this log file
            _data = []
            # obtain the field names to be used for this log file
            _field_names = self.logs[lg].get('fields')
            # create a CSV dictionary reader, use skipinitialspace=True to skip
            # any extra whitespace between columns and fieldnames to specify
            # the field names to be used
            _reader = csv.DictReader(_clean_data,
                                     delimiter=_del,
                                     skipinitialspace=True,
                                     fieldnames=_field_names)
            # skip the header line since we are using our own field names
            next(_reader)
            # iterate over the records and calculate a unix timestamp for each
            # record
            for rec in _reader:
                # first get a datetime object from the individual date-time
                # fields
                _dt = datetime.datetime(int(rec['year']), int(rec['month']),
                                        int(rec['day']), int(rec['hour']),
                                        int(rec['minute']))
                # now as a timetuple
                _tt = _dt.timetuple()
                # and finally a timestamp but as a string like the rest of our
                # data
                _ts = "%s" % int(time.mktime(_tt))
                # add the timestamp to our record
                _ts_rec = dict(rec, **{'datetime': _ts})
                # some WD log files contain records from another month so check
                # year and month and if the record belongs to another month
                # store it for use later otherwise add it to this month's data
                if _ts_rec['year'] == _year and _ts_rec['month'] == _month:
                    # add the timestamped record to our data list
                    _data.append(_ts_rec)
                else:
                    # add the record to the list for later processing
                    self.extras[lg].append(_ts_rec)
                # now add any extras that may belong in this month
                for e_rec in self.extras[lg]:
                    if e_rec['year'] == _year and e_rec['month'] == _month:
                        # add the record
                        _data.append(e_rec)
                # now update our extras and remove any records we added
                self.extras[lg][:] = [x for x in self.extras[lg] if
                                      not (x['year'] == _year and x['month'] == _month)]

            # There may be duplicate timestamped records in the data. We will
            # keep the first encountered duplicate and discard the latter ones,
            # but we also need to keep track of the duplicate timestamps for
            # later reporting.

            # initialise a set to hold the timestamps we have seen
            _timestamps = set()
            # initialise a list to hold the unique timestamped records
            unique_data = []
            # iterate over each record in the list of records
            for item in _data:
                # has this timestamp been seen before
                if item['datetime'] not in _timestamps:
                    # no it hasn't, so keep the record and add the timestamp
                    # to the list of timestamps seen
                    unique_data.append(item)
                    _timestamps.add(item['datetime'])
                else:
                    # yes it has been seen, so add the timestamp to the list of
                    # duplicates for later reporting
                    self.period_duplicates.add(int(item['datetime']))

            # add the data (list of dicts) to the list of processed log file
            # data
            _data_list.append(unique_data)

        # we have all our data so now combine the data for each timestamp into
        # a common record, this gives us a single list of dicts
        d = collections.defaultdict(dict)
        for _list in _data_list:
            for elm in _list:
                d[elm['datetime']].update(elm)

        # The combined data will likely not be in dateTime order, WD logs can
        # be imported in a dateTime unordered state but the user will be
        # presented with a more legible display as the import progresses if
        # the data is in ascending dateTime order.
        _sorted = sorted(list(d.values()), key=operator.itemgetter('datetime'))
        # return our sorted data
        return _sorted

    def period_generator(self):
        """Generator function yielding a sequence of monthly log file names.

        This generator controls the FOR statement in the parents run() method
        that loops over the monthly log files to be imported. The generator
        yields a monthly log file name from the list of monthly log files to
        be imported until the list is exhausted.
        """

        # Step through each of our file names
        for self.file_name in self.log_list:
            # yield the file name
            yield self.file_name

    @property
    def first_period(self):
        """True if current period is the first period otherwise False.

         Return True if the current file name being processed is the first in
         the list, or if it is None (the initialisation value).
         """

        return self.file_name == self.log_list[0] if self.file_name is not None else True

    @property
    def last_period(self):
        """True if current period is the last period otherwise False.

         Return True if the current file name being processed is the last in
         the list.
         """

        return self.file_name == self.log_list[-1]
