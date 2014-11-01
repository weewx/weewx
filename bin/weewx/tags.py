#
#    Copyright (c) 2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Classes for implementing the weewx tag 'code' codes."""

import weeutil.weeutil
from weeutil.weeutil import to_int
import weewx.units
from weewx.units import ValueTuple

#===============================================================================
#                    Class DBFactory
#===============================================================================

class DBFactory(object):
    """Binds a database cache, with a default database."""
    
    def __init__(self, db_binder, default_binding='wx_binding'):
        self.db_binder = db_binder
        self.default_binding  = default_binding
        
    def get_database(self, binding=None):
        if binding is None:
            binding = self.default_binding
        return self.db_binder.get_database(binding)

#===============================================================================
#                    Class FactoryBinder
#===============================================================================

class FactoryBinder(object):
    """Binds a DBFactory and an end time together.
    
    This class sits on the top of chain of helper classes that enable
    syntax such as $db($data_binding='wx_binding').month.rain.sum in the Cheetah templates.""" 

    def __init__(self, dbfactory, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        
        self.dbfactory   = dbfactory
        self.report_time = report_time
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
        
    def db(self, data_binding=None):
        opendb = self.dbfactory.get_database(data_binding)
        return DatabaseBinder(opendb, self.report_time, self.formatter, self.converter, **self.option_dict)
    
    def __getattr__(self, attr):
        # The following is so the Python version of Cheetah's NameMapper does not think I'm a dictionary.
        if attr == 'has_key':
            raise AttributeError(attr)
        # For syntax such as $month.outTemp.max, the funcion db() above will not
        # get called and instead, we will be queried for an attribute such as 'month'.
        # So, make the call to db() with default values, then ask it for the
        # attribute.
        return getattr(self.db(), attr)

#===============================================================================
#                    Class DatabaseBinder
#===============================================================================

class DatabaseBinder(object):
    """Binds to a specific database. Can be queried for time attributes, such as month.

    When a time period is given as an attribute to it, such as obj.month,
    the next item in the chain is returned, in this case an instance of
    TimeBinder, which binds the database with the time period.
    """

    def __init__(self, opendb, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of DatabaseBinder.
        
        opendb: A Database from which the aggregates are to be extracted.

        report_time: The time for which the report should be run.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        self.opendb      = opendb
        self.report_time = report_time
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    # What follows is the list of time period attributes:
    
    @property
    def current(self, timestamp=None):
        """Return a CurrentObj"""
        if timestamp is None:
            timestamp = self.report_time
        return CurrentObj(self.opendb, timestamp,
                          self.formatter, self.converter, **self.option_dict)
            
    def trend(self, time_delta=None, time_grace=None):
        """Returns a TrendObj that is bound to the trend parameters."""
        if time_delta is None:
            time_delta = to_int(self.option_dict['trend'].get('time_delta', 10800))
        if time_grace is None:
            time_grace = to_int(self.option_dict['trend'].get('time_grace', 300))

        return TrendObj(time_delta, time_grace, self.opendb, self.report_time, 
                 self.formatter, self.converter, **self.option_dict)

    @property
    def day(self):
        return TimeBinder(weeutil.weeutil.archiveDaySpan(self.report_time), self.opendb, 
                          'day', self.formatter, self.converter, **self.option_dict)
    @property
    def week(self):
        week_start = to_int(self.option_dict.get('week_start', 6))
        return TimeBinder(weeutil.weeutil.archiveWeekSpan(self.report_time, week_start), self.opendb,
                          'week', self.formatter, self.converter, **self.option_dict)
    @property
    def month(self):
        return TimeBinder(weeutil.weeutil.archiveMonthSpan(self.report_time), self.opendb,
                          'month', self.formatter, self.converter, **self.option_dict)
    @property
    def year(self):
        return TimeBinder(weeutil.weeutil.archiveYearSpan(self.report_time), self.opendb,
                          'year', self.formatter, self.converter, **self.option_dict)
    @property
    def rainyear(self):
        rain_year_start = to_int(self.option_dict.get('rain_year_start', 1))
        return TimeBinder(weeutil.weeutil.archiveRainYearSpan(self.report_time, rain_year_start), self.opendb,
                          'rainyear',  self.formatter, self.converter, **self.option_dict)


#===============================================================================
#                    Class TimeBinder
#===============================================================================

class TimeBinder(object):
    """Holds a binding between a database and a timespan.

    This class is the next class in the chain of helper classes.

    When an observation type is given as an attribute to it (such as 'obj.outTemp'),
    the next item in the chain is returned, in this case an instance of
    ObservationBinder, which binds the database, the time period, and
    the statistical type all together.

    It also includes a few "special attributes" that allow iteration over certain
    time periods. Example:

       # Iterate by month:
       for monthStats in yearStats.months:
           # Print maximum temperature for each month in the year:
           print monthStats.outTemp.max
    """
    def __init__(self, timespan, opendb, context='current', formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of TimeBinder.

        timespan: An instance of weeutil.Timespan with the time span
        over which the statistics are to be calculated.

        opendb: A database from which the stats are to be extracted.

        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.timespan    = timespan
        self.opendb      = opendb
        self.context     = context
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    # Iterate over days in the time period:
    @property
    def days(self):
        return TimeBinder._seqGenerator(weeutil.weeutil.genDaySpans, self.timespan, self.opendb,
                                        'day', self.formatter, self.converter, **self.option_dict)

    # Iterate over months in the time period:
    @property
    def months(self):
        return TimeBinder._seqGenerator(weeutil.weeutil.genMonthSpans, self.timespan, self.opendb,
                                        'month', self.formatter, self.converter, **self.option_dict)

    # Iterate over years in the time period:
    @property
    def years(self):
        return TimeBinder._seqGenerator(weeutil.weeutil.genYearSpans, self.timespan, self.opendb,
                                        'year', self.formatter, self.converter, **self.option_dict)

    # Static method used to implement the iteration:
    @staticmethod
    def _seqGenerator(genSpanFunc, timespan, *args, **option_dict):
        """Generator function that returns TimeBinder for the appropriate timespans"""
        for span in genSpanFunc(timespan.start, timespan.stop):
            yield TimeBinder(span, *args, **option_dict)

    # Return the start time of the time period as a ValueHelper
    @property
    def dateTime(self):
        val = weewx.units.ValueTuple(self.timespan.start, 'unix_epoch', 'group_time')
        return weewx.units.ValueHelper(val, self.context, self.formatter, self.converter)

    def __getattr__(self, obs_type):
        """Return a helper object that binds the database, a time period,
        and the given observation type.

        obs_type: An observation type, such as 'outTemp', or 'heatDeg'

        returns: An instance of class ObservationBinder."""

        # The following is so the Python version of Cheetah's NameMapper doesn't think
        # I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError

        # If we represent the "current" time, then no aggregation is possible. Just return
        # a ValueHelper.
        if self.context == 'current':
            max_delta = self.option_dict.get('max_delta')
            record_dict = self.opendb.getRecord(self.timespan.stop, max_delta)
            if record_dict is not None:
                vt = weewx.units.as_value_tuple(record_dict, obs_type)
            else:
                vt = (None, None, None)
            vh = weewx.units.ValueHelper(vt, context='current', formatter=self.formatter, converter=self.converter)
            return vh

        # For other contexts, an aggregation is possible. Return an ObservationBinder: if an attribute is
        # requested from it, an aggregation value will be returned instead.
        return ObservationBinder(obs_type, self.timespan, self.opendb, self.context,
                                 self.formatter, self.converter, **self.option_dict)

#===============================================================================
#                    Class ObservationBinder
#===============================================================================

class ObservationBinder(object):
    """This is the final class in the chain of helper classes. It binds the
    database, a time period, and an observation type all together.

    When an aggregation type (eg, 'max') is given as an attribute to it, it runs the
    query against the database, assembles the result, and returns it as a ValueHelper.
    """

    def __init__(self, obs_type, timespan, opendb, context,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """ Initialize an instance of ObservationBinder

        obs_type: A string with the stats type (e.g., 'outTemp') for which the query is
        to be done.

        timespan: An instance of TimeSpan holding the time period over which the query is
        to be run

        opendb: The database from which the stats are to be extracted.

        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.obs_type    = obs_type
        self.timespan    = timespan
        self.opendb      = opendb
        self.context     = context
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    def max_ge(self, val):
        return self._do_query('max_ge', val=val)

    def max_le(self, val):
        return self._do_query('max_le', val=val)

    def min_le(self, val):
        return self._do_query('min_le', val=val)

    def sum_ge(self, val):
        return self._do_query('sum_ge', val=val)

    def __getattr__(self, aggregateType):
        """Return statistical summary using a given aggregateType.

        aggregateType: The type of aggregation over which the summary is to be done.
        This is normally something like 'sum', 'min', 'mintime', 'count', etc.
        However, there are two special aggregation types that can be used to
        determine the existence of data:
          'exists':   Return True if the observation type exists in the database.
          'has_data': Return True if the type exists and there is a non-zero
                      number of entries over the aggregation period.

        returns: A ValueHelper containing the aggregation data."""

        return self._do_query(aggregateType)
    
    @property
    def exists(self):

        return self.opendb.exists(self.obs_type)

    @property
    def has_data(self):
 
        return self.opendb.has_data(self.obs_type, self.timespan)

    def _do_query(self, aggregateType, val=None):
        """Run a query against the databases, using the given aggregation type."""
        result = self.opendb.getAggregate(self.timespan, self.obs_type, aggregateType, val=val, **self.option_dict)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)
        
#===============================================================================
#                             Class CurrentObj
#===============================================================================

class CurrentObj(object):
    """Helper class for the "Current" record. Does the database lookup lazily.
    
    This class allows tags such as:
      $current.barometer
    """
        
    def __init__(self, opendb, timestamp, formatter, converter, **option_dict):
        self.opendb = opendb
        self.timestamp = timestamp
        self.formatter = formatter
        self.converter = converter
        
    def __getattr__(self, obs_type):
        """Return the given observation type."""
        # The following is so the Python version of Cheetah's NameMapper
        # does not think I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError

        # Get the current record:        
        record  = self.opendb.getRecord(self.timestamp)
        vt = weewx.units.as_value_tuple(record, obs_type)
        return weewx.units.ValueHelper(vt, 'current',
                                       self.formatter,
                                       self.converter)
        
#===============================================================================
#                             Class TrendObj
#===============================================================================

class TrendObj(object):
    """Helper class that calculates trends. 
    
    This class allows tags such as:
      $trend.barometer
    """

    def __init__(self, time_delta, time_grace, opendb, nowtime, formatter, converter, **option_dict):
        """Initialize a Trend object
        
        time_delta: The time difference over which the trend is to be calculated
        
        time_grace: A time within this amount is accepted.
        """
        self.time_delta_val = time_delta
        self.time_grace_val = time_grace
        self.opendb = opendb
        self.nowtime = nowtime
        self.formatter = formatter
        self.converter = converter
        self.time_delta = weewx.units.ValueHelper((time_delta, 'second', 'group_elapsed'),
                                                  'current',
                                                  self.formatter,
                                                  self.converter)
        self.time_grace = weewx.units.ValueHelper((time_grace, 'second', 'group_elapsed'),
                                                  'current',
                                                  self.formatter,
                                                  self.converter)
        
    def __getattr__(self, obs_type):
        """Return the trend for the given observation type."""
        # The following is so the Python version of Cheetah's NameMapper
        # does not think I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError

        # Get the current record, and one "time_delta" ago:        
        now_record  = self.opendb.getRecord(self.nowtime, self.time_grace_val)
        then_record = self.opendb.getRecord(self.nowtime - self.time_delta_val, self.time_grace_val)

        # Do both records exist?
        if now_record is None or then_record is None:
            # No. One is missing.
            trend = ValueTuple(None, None, None)
        else:
            # Both records exist. 
            # Check to see if the observation type is known
            if obs_type not in now_record or obs_type not in then_record:
                # obs_type is unknown. Signal it
                trend = weewx.units.UnknownType(obs_type)
            else:
                now_vt  = weewx.units.as_value_tuple(now_record, obs_type)
                then_vt = weewx.units.as_value_tuple(then_record, obs_type)
                # Do the unit conversion now, rather than lazily. This is because,
                # in the case of temperature, the difference between two converted
                # values is not the same as the conversion of the difference
                # between two values. E.g., 20C - 10C is not equal to
                # F_to_C(68F - 50F). We want the former, not the latter.
                now_vtc  = self.converter.convert(now_vt)
                then_vtc = self.converter.convert(then_vt)
                if now_vtc.value is None or then_vtc.value is None:
                    trend = ValueTuple(None, now_vtc.unit, now_vtc.group)
                else:
                    trend = now_vtc - then_vtc
            
        # Return the results as a ValueHelper. Use the formatting and labeling
        # options from the current time record. The user can always override
        # these.
        return weewx.units.ValueHelper(trend, 'current',
                                       self.formatter,
                                       self.converter)


#===============================================================================
#                             Class CurrentRecord
#===============================================================================

class CurrentRecord(object):
    """Helper class for the "Current" record.
    
    Unlike class CurrentObj above, this class holds the record internally. It does
    not do a database lookup.
    """
        
    def __init__(self, record, formatter, converter, **option_dict):
        self.record = record
        self.formatter = formatter
        self.converter = converter
        
    def __getattr__(self, obs_type):
        """Return the trend for the given observation type."""
        # The following is so the Python version of Cheetah's NameMapper
        # does not think I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError
        
        vt = weewx.units.as_value_tuple(self.record, obs_type)
        return weewx.units.ValueHelper(vt, 'current',
                                       self.formatter,
                                       self.converter)
        
