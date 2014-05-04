#
#    Copyright (c) 2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""Classes for implementing the weewx tag 'code' codes."""

import weeutil.weeutil
import weewx.units

#===============================================================================
#                    Class DBFactory
#===============================================================================

class DBFactory(object):
    """Binds a database cache, with a default binding."""
    
    def __init__(self, db_cache, default_binding='wx_binding'):
        self.cache = db_cache
        self.default_binding  = default_binding
        
    def get_database(self, binding=None):
        if binding is None:
            binding = self.default_binding
        return self.cache.get_database(binding)

#===============================================================================
#                    Class FactoryBinder
#===============================================================================

class FactoryBinder(object):
    """Binds a DBFactory, a timespan, and a default archive database together.
    
    This class sits on the top of chain of helper classes that enable
    syntax such as $db($binding='wx_binding').month.rain.sum in the Cheetah templates.""" 

    def __init__(self, dbfactory, endtime_ts,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        
        self.dbfactory   = dbfactory
        self.endtime_ts  = endtime_ts
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
        
    def db(self, binding=None):
        opendb = self.dbfactory.get_database(binding)
        return DatabaseBinder(opendb, self.endtime_ts, self.formatter, self.converter, **self.option_dict)
    
    def __getattr__(self, attr):
        # The following is so the Python version of Cheetah's NameMapper does not think I'm a dictionary.
        if attr == 'has_key':
            raise AttributeError(attr)
        # For syntax such as $month.outTemp.max, the funcion db() above will not
        # get called and instead, we will be queried for an attribute 'month'.
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

    def __init__(self, opendb, endtime_ts,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of DatabaseBinder.
        opendb: A Database from which the stats are to be extracted.

        endtime_ts: The time the stats are to be current to.

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
        self.endtime_ts  = endtime_ts
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    # What follows is the list of time period attributes:
    
    @property
    def current(self):
        """Return a ValueDict for the 'current" record."""
        vtd = self._get_valuetupledict(self.endtime_ts)
        vd = weewx.units.ValueDict(vtd, context='current',
                                   formatter=self.formatter,
                                   converter=self.converter)
        return vd
            
    @property
    def trend(self):
        """Return a ValueDict for the 'trend'. This is an inefficient entry point
        because it would hit the database for every observation type."""
        rb = self.get_record_binder()
        return rb.trend
        
    @property
    def day(self):
        return TimeBinder(weeutil.weeutil.archiveDaySpan(self.endtime_ts), self.opendb, 
                          'day', self.formatter, self.converter, **self.option_dict)
    @property
    def week(self):
        week_start = self.option_dict.get('week_start', 6)
        return TimeBinder(weeutil.weeutil.archiveWeekSpan(self.endtime_ts, week_start), self.opendb,
                          'week', self.formatter, self.converter, **self.option_dict)
    @property
    def month(self):
        return TimeBinder(weeutil.weeutil.archiveMonthSpan(self.endtime_ts), self.opendb,
                          'month', self.formatter, self.converter, **self.option_dict)
    @property
    def year(self):
        return TimeBinder(weeutil.weeutil.archiveYearSpan(self.endtime_ts), self.opendb,
                          'year', self.formatter, self.converter, **self.option_dict)
    @property
    def rainyear(self):
        return TimeBinder(weeutil.weeutil.archiveRainYearSpan(self.endtime_ts, self.option_dict['rain_year_start']), self.opendb,
                          'rainyear',  self.formatter, self.converter, **self.option_dict)

    def get_record_binder(self):
        time_delta = int(self.option_dict.get('time_delta', 10800))
        time_grace = int(self.option_dict.get('time_grace', 300))
        now_vtd  = self._get_valuetupledict(self.endtime_ts, time_grace)
        then_vtd = self._get_valuetupledict(self.endtime_ts - time_delta, time_grace)
        return RecordBinder(now_vtd, self.formatter, self.converter, then_vtd, time_delta)
        
    def _get_valuetupledict(self, time_ts, time_grace=None):
        # Get the record...
        record_dict = self.opendb.getRecord(time_ts, max_delta=time_grace)
        # ... convert to a dictionary with ValueTuples as values:
        record_dict_vtd = weewx.units.ValueTupleDict(record_dict) if record_dict is not None else None
        return record_dict_vtd
            
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
#                             Class RecordBinder
#===============================================================================

class RecordBinder(object):
    
    def __init__(self, now_vtd, formatter, converter, last_vtd=None, time_delta=None):
        
        self.now_vtd = now_vtd
        self.formatter = formatter
        self.converter = converter
        self.last_vtd = last_vtd
        self.time_delta = time_delta
        
    @property
    def current(self):
        return self.now_vtd
    
    @property
    def trend(self):
        return TrendObj(self.last_vtd, self.now_vtd, self.time_delta, self.formatter, self.converter)

#===============================================================================
#                             Class TrendObj
#===============================================================================

class TrendObj(object):
    """Helper class that binds together a current record and one a delta
    time in the past. Useful for trends.
    
    This class allows tags such as:
      $trend.barometer
    """
        
    def __init__(self, last_vtd, now_vtd, time_delta, formatter, converter):
        """Initialize a Trend object
        
        last_vd: A ValueTupleDict containing records from the past.
        
        now_vd: A ValueTupleDict containing current records
        
        time_delta: The time difference in seconds between them.
        """
        self.last_vtd = last_vtd
        self.now_vtd  = now_vtd
        self.formatter = formatter
        self.converter = converter
        self.time_delta = weewx.units.ValueHelper((time_delta, 'second', 'group_elapsed'),
                                                  'current',
                                                  formatter,
                                                  converter)
        
    def __getattr__(self, obs_type):
        """Return the trend for the given observation type."""
        # The following is so the Python version of Cheetah's NameMapper
        # does not think I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError
        
        # Wrap in a try block because the 'last' record might not exist,
        # or the 'now' or 'last' value might be None. 
        try:
            # Do the unit conversion now, rather than lazily. This is because,
            # in the case of temperature, the difference between two converted
            # values is not the same as the conversion of the difference
            # between two values. E.g., 20C - 10C is not equal to
            # F_to_C(68F - 50F). We want the former, not the latter.
            now_val  = self.converter.convert(self.now_vtd[obs_type])
            last_val = self.converter.convert(self.last_vtd[obs_type])
            trend = now_val - last_val
        except TypeError:
            trend = (None, None, None)

        # Return the results as a ValueHelper. Use the formatting and labeling
        # options from the current time record. The user can always override
        # these.
        return weewx.units.ValueHelper(trend, 'current',
                                       self.formatter,
                                       self.converter)
