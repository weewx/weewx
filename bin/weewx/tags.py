#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes for implementing the weewx tag 'code' codes."""

from __future__ import absolute_import

import weeutil.weeutil
import weewx.units
import weewx.xtypes
from weeutil.weeutil import to_int
from weewx.units import ValueTuple


# ===============================================================================
#                    Class TimeBinder
# ===============================================================================

class TimeBinder(object):
    """Binds to a specific time. Can be queried for time attributes, such as month.

    When a time period is given as an attribute to it, such as obj.month, the next item in the
    chain is returned, in this case an instance of TimespanBinder, which binds things to a
    timespan.
    """

    def __init__(self, db_lookup, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(),
                 **option_dict):
        """Initialize an instance of DatabaseBinder.
        
        db_lookup: A function with call signature db_lookup(data_binding), which returns a database
        manager and where data_binding is an optional binding name. If not given, then a default
        binding will be used.

        report_time: The time for which the report should be run.

        formatter: An instance of weewx.units.Formatter() holding the formatting information to be
        used. [Optional. If not given, the default Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit information to be
        used. [Optional. If not given, the default Converter will be used.]

        option_dict: Other options which can be used to customize calculations. [Optional.]
        """
        self.db_lookup = db_lookup
        self.report_time = report_time
        self.formatter = formatter
        self.converter = converter
        self.option_dict = option_dict

    # What follows is the list of time period attributes:

    def trend(self, time_delta=None, time_grace=None, data_binding=None):
        """Returns a TrendObj that is bound to the trend parameters."""
        if time_delta is None:
            time_delta = to_int(self.option_dict['trend'].get('time_delta', 10800))
        if time_grace is None:
            time_grace = to_int(self.option_dict['trend'].get('time_grace', 300))
        return TrendObj(time_delta, time_grace, self.db_lookup, data_binding, self.report_time,
                        self.formatter, self.converter, **self.option_dict)

    def hour(self, data_binding=None, hours_ago=0):
        return TimespanBinder(
            weeutil.weeutil.archiveHoursAgoSpan(self.report_time, hours_ago=hours_ago),
            self.db_lookup, data_binding=data_binding,
            context='day', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    def day(self, data_binding=None, days_ago=0):
        return TimespanBinder(weeutil.weeutil.archiveDaySpan(self.report_time, days_ago=days_ago),
                              self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              **self.option_dict)

    def yesterday(self, data_binding=None):
        return self.day(data_binding, days_ago=1)

    def week(self, data_binding=None, weeks_ago=0):
        week_start = to_int(self.option_dict.get('week_start', 6))
        return TimespanBinder(
            weeutil.weeutil.archiveWeekSpan(self.report_time, week_start, weeks_ago=weeks_ago),
            self.db_lookup, data_binding=data_binding,
            context='week', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    def month(self, data_binding=None, months_ago=0):
        return TimespanBinder(
            weeutil.weeutil.archiveMonthSpan(self.report_time, months_ago=months_ago),
            self.db_lookup, data_binding=data_binding,
            context='month', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    def year(self, data_binding=None, years_ago=0):
        return TimespanBinder(
            weeutil.weeutil.archiveYearSpan(self.report_time, years_ago=years_ago),
            self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    def rainyear(self, data_binding=None):
        rain_year_start = to_int(self.option_dict.get('rain_year_start', 1))
        return TimespanBinder(
            weeutil.weeutil.archiveRainYearSpan(self.report_time, rain_year_start),
            self.db_lookup, data_binding=data_binding,
            context='rainyear', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    def span(self, data_binding=None, time_delta=0, hour_delta=0, day_delta=0, week_delta=0,
             month_delta=0, year_delta=0):
        return TimespanBinder(
            weeutil.weeutil.archiveSpanSpan(self.report_time, time_delta=time_delta,
                                            hour_delta=hour_delta, day_delta=day_delta,
                                            week_delta=week_delta, month_delta=month_delta,
                                            year_delta=year_delta),
            self.db_lookup, data_binding=data_binding,
            context='day', formatter=self.formatter, converter=self.converter,
            **self.option_dict)

    # For backwards compatiblity
    hours_ago = hour
    days_ago = day


# ===============================================================================
#                    Class TimespanBinder
# ===============================================================================

class TimespanBinder(object):
    """Holds a binding between a database and a timespan.

    This class is the next class in the chain of helper classes.

    When an observation type is given as an attribute to it (such as 'obj.outTemp'), the next item
    in the chain is returned, in this case an instance of ObservationBinder, which binds the
    database, the time period, and the statistical type all together.

    It also includes a few "special attributes" that allow iteration over certain time periods.
    Example:

       # Iterate by month:
       for monthStats in yearStats.months:
           # Print maximum temperature for each month in the year:
           print monthStats.outTemp.max
    """

    def __init__(self, timespan, db_lookup, data_binding=None, context='current',
                 formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of TimespanBinder.

        timespan: An instance of weeutil.Timespan with the time span over which the statistics are
        to be calculated.

        db_lookup: A function with call signature db_lookup(data_binding), which returns a database
        manager and where data_binding is an optional binding name. If not given, then a default
        binding will be used.

        data_binding: If non-None, then use this data binding.

        context: A tag name for the timespan. This is something like 'current', 'day', 'week', etc.
        This is used to figure out how to do aggregations, and for picking an appropriate label.

        formatter: An instance of weewx.units.Formatter() holding the formatting information to be
        used. [Optional. If not given, the default Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit information to be
        used. [Optional. If not given, the default Converter will be used.]

        option_dict: Other options which can be used to customize calculations. [Optional.]
        """

        self.timespan = timespan
        self.db_lookup = db_lookup
        self.data_binding = data_binding
        self.context = context
        self.formatter = formatter
        self.converter = converter
        self.option_dict = option_dict

    # Iterate over all records in the time period:
    def records(self):
        manager = self.db_lookup(self.data_binding)
        for record in manager.genBatchRecords(self.timespan.start, self.timespan.stop):
            yield CurrentObj(self.db_lookup, self.data_binding, record['dateTime'], self.formatter,
                             self.converter, record=record)

    # Iterate over custom span
    def spans(self, context='day', interval=10800):
        for span in weeutil.weeutil.intervalgen(self.timespan.start, self.timespan.stop, interval):
            yield TimespanBinder(span, self.db_lookup, self.data_binding,
                                 context, self.formatter, self.converter, **self.option_dict)

    # Iterate over hours in the time period:
    def hours(self):
        return TimespanBinder._seqGenerator(weeutil.weeutil.genHourSpans, self.timespan,
                                            self.db_lookup, self.data_binding,
                                            'hour', self.formatter, self.converter,
                                            **self.option_dict)

    # Iterate over days in the time period:
    def days(self):
        return TimespanBinder._seqGenerator(weeutil.weeutil.genDaySpans, self.timespan,
                                            self.db_lookup, self.data_binding,
                                            'day', self.formatter, self.converter,
                                            **self.option_dict)

    # Iterate over months in the time period:
    def months(self):
        return TimespanBinder._seqGenerator(weeutil.weeutil.genMonthSpans, self.timespan,
                                            self.db_lookup, self.data_binding,
                                            'month', self.formatter, self.converter,
                                            **self.option_dict)

    # Iterate over years in the time period:
    def years(self):
        return TimespanBinder._seqGenerator(weeutil.weeutil.genYearSpans, self.timespan,
                                            self.db_lookup, self.data_binding,
                                            'year', self.formatter, self.converter,
                                            **self.option_dict)

    # Static method used to implement the iteration:
    @staticmethod
    def _seqGenerator(genSpanFunc, timespan, *args, **option_dict):
        """Generator function that returns TimespanBinder for the appropriate timespans"""
        for span in genSpanFunc(timespan.start, timespan.stop):
            yield TimespanBinder(span, *args, **option_dict)

    # Return the start time of the time period as a ValueHelper
    @property
    def start(self):
        val = weewx.units.ValueTuple(self.timespan.start, 'unix_epoch', 'group_time')
        return weewx.units.ValueHelper(val, self.context, self.formatter, self.converter)

    # Return the ending time:
    @property
    def end(self):
        val = weewx.units.ValueTuple(self.timespan.stop, 'unix_epoch', 'group_time')
        return weewx.units.ValueHelper(val, self.context, self.formatter, self.converter)

    # Alias for the start time:
    dateTime = start

    def __getattr__(self, obs_type):
        """Return a helper object that binds the database, a time period, and the given observation
        type.

        obs_type: An observation type, such as 'outTemp', or 'heatDeg'

        returns: An instance of class ObservationBinder."""

        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError

        # Return an ObservationBinder: if an attribute is
        # requested from it, an aggregation value will be returned.
        return ObservationBinder(obs_type, self.timespan, self.db_lookup, self.data_binding,
                                 self.context,
                                 self.formatter, self.converter, **self.option_dict)


# ===============================================================================
#                    Class ObservationBinder
# ===============================================================================

class ObservationBinder(object):
    """This is the final class in the chain of helper classes. It binds the
    database, a time period, and an observation type all together.

    When an aggregation type (eg, 'max') is given as an attribute to it, it runs the
    query against the database, assembles the result, and returns it as a ValueHelper.
    """

    def __init__(self, obs_type, timespan, db_lookup, data_binding, context,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(),
                 **option_dict):
        """ Initialize an instance of ObservationBinder

        obs_type: A string with the stats type (e.g., 'outTemp') for which the query is to be done.

        timespan: An instance of TimeSpan holding the time period over which the query is to be run

        db_lookup: A function with call signature db_lookup(data_binding), which returns a database
        manager and where data_binding is an optional binding name. If not given, then a default
        binding will be used.

        data_binding: If non-None, then use this data binding.

        context: A tag name for the timespan. This is something like 'current', 'day', 'week', etc.
        This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting information to be
        used. [Optional. If not given, the default Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit information to be
        used. [Optional. If not given, the default Converter will be used.]

        option_dict: Other options which can be used to customize calculations. [Optional.]
        """

        self.obs_type = obs_type
        self.timespan = timespan
        self.db_lookup = db_lookup
        self.data_binding = data_binding
        self.context = context
        self.formatter = formatter
        self.converter = converter
        self.option_dict = option_dict

    def max_ge(self, val):
        return self._do_query('max_ge', val=val)

    def max_le(self, val):
        return self._do_query('max_le', val=val)

    def min_ge(self, val):
        return self._do_query('min_ge', val=val)

    def min_le(self, val):
        return self._do_query('min_le', val=val)

    def sum_ge(self, val):
        return self._do_query('sum_ge', val=val)

    def sum_le(self, val):
        return self._do_query('sum_le', val=val)

    def __getattr__(self, aggregate_type):
        """Return statistical summary using a given aggregate type.

        aggregate_type: The type of aggregation over which the summary is to be done. This is
        normally something like 'sum', 'min', 'mintime', 'count', etc. However, there are two
        special aggregation types that can be used to determine the existence of data:
          'exists':   Return True if the observation type exists in the database.
          'has_data': Return True if the type exists and there is a non-zero number of entries over
                      the aggregation period.

        returns: A ValueHelper containing the aggregation data.
        """

        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if aggregate_type in ['__call__', 'has_key']:
            raise AttributeError
        return self._do_query(aggregate_type)

    @property
    def exists(self):
        return self.db_lookup(self.data_binding).exists(self.obs_type)

    @property
    def has_data(self):
        return self.db_lookup(self.data_binding).has_data(self.obs_type, self.timespan)

    def _do_query(self, aggregate_type, val=None):
        """Run a query against the databases, using the given aggregation type."""
        db_manager = self.db_lookup(self.data_binding)
        try:
            # If we cannot perform the aggregation, we will get an UnknownType or
            # UnknownAggregation error. Be prepared to catch it.
            result = weewx.xtypes.get_aggregate(self.obs_type, self.timespan, aggregate_type,
                                                db_manager, val=val, **self.option_dict)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            # Signal Cheetah that we don't know how to do this by raiing an AttributeError.
            raise AttributeError(self.obs_type)
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)


# ===============================================================================
#                             Class RecordBinder
# ===============================================================================

class RecordBinder(object):

    def __init__(self, db_lookup, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(),
                 record=None):
        self.db_lookup = db_lookup
        self.report_time = report_time
        self.formatter = formatter
        self.converter = converter
        self.record = record

    def current(self, timestamp=None, max_delta=None, data_binding=None):
        """Return a CurrentObj"""
        if timestamp is None:
            timestamp = self.report_time
        return CurrentObj(self.db_lookup, data_binding, current_time=timestamp,
                          max_delta=max_delta,
                          formatter=self.formatter, converter=self.converter, record=self.record)

    def latest(self, data_binding=None):
        """Return a CurrentObj, using the last available timestamp."""
        manager = self.db_lookup(data_binding)
        timestamp = manager.lastGoodStamp()
        return self.current(timestamp, data_binding=data_binding)


# ===============================================================================
#                             Class CurrentObj
# ===============================================================================

class CurrentObj(object):
    """Helper class for the "Current" record. Hits the database lazily.
    
    This class allows tags such as:
      $current.barometer
    """

    def __init__(self, db_lookup, data_binding, current_time,
                 formatter, converter, max_delta=None, record=None):
        self.db_lookup = db_lookup
        self.data_binding = data_binding
        self.current_time = current_time
        self.formatter = formatter
        self.converter = converter
        self.max_delta = max_delta
        self.record = record

    def __getattr__(self, obs_type):
        """Return the given observation type."""
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError

        # TODO: Refactor the following to be a separate function.

        # If no data binding has been specified, and we have a current record with the right
        # timestamp at hand, we don't have to hit the database.
        if not self.data_binding and self.record and obs_type in self.record \
                and self.record['dateTime'] == self.current_time:
            # Use the record given to us to form a ValueTuple
            vt = weewx.units.as_value_tuple(self.record, obs_type)
        else:
            # A binding has been specified, or we don't have a record, or the observation type
            # is not in the record, or the timestamp is wrong.
            try:
                # Get the appropriate database manager
                db_manager = self.db_lookup(self.data_binding)
            except weewx.UnknownBinding:
                # Don't recognize the binding.
                vt = weewx.units.UnknownType(self.data_binding)
            else:
                # Get the record for this timestamp from the database
                record = db_manager.getRecord(self.current_time, max_delta=self.max_delta)
                # If there was no record at that timestamp, it will be None. If there was a record,
                # check to see if the type is in it.
                if not record or obs_type in record:
                    # If there was no record, then the value of the ValueTuple will be None.
                    # Otherwise, it will be value stored in the database.
                    vt = weewx.units.as_value_tuple(record, obs_type)
                else:
                    # Couldn't get the value out of the record. Try the XTypes system.
                    try:
                        vt = weewx.xtypes.get_scalar(obs_type, self.record, db_manager)
                    except (weewx.UnknownType, weewx.CannotCalculate):
                        # Nothing seems to be working. It's an unknown type.
                        vt = weewx.units.UnknownType(obs_type)

        # Finally, return a ValueHelper
        return weewx.units.ValueHelper(vt, 'current', self.formatter, self.converter)


# ===============================================================================
#                             Class TrendObj
# ===============================================================================

class TrendObj(object):
    """Helper class that calculates trends. 
    
    This class allows tags such as:
      $trend.barometer
    """

    def __init__(self, time_delta, time_grace, db_lookup, data_binding,
                 nowtime, formatter, converter, **option_dict):  # @UnusedVariable
        """Initialize a Trend object
        
        time_delta: The time difference over which the trend is to be calculated
        
        time_grace: A time within this amount is accepted.
        """
        self.time_delta_val = time_delta
        self.time_grace_val = time_grace
        self.db_lookup = db_lookup
        self.data_binding = data_binding
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
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError

        db_manager = self.db_lookup(self.data_binding)
        # Get the current record, and one "time_delta" ago:        
        now_record = db_manager.getRecord(self.nowtime, self.time_grace_val)
        then_record = db_manager.getRecord(self.nowtime - self.time_delta_val, self.time_grace_val)

        # Do both records exist?
        if now_record is None or then_record is None:
            # No. One is missing.
            trend = ValueTuple(None, None, None)
        else:
            # Both records exist. Check to see if the observation type is known
            if obs_type not in now_record or obs_type not in then_record:
                # obs_type is unknown. Signal it
                trend = weewx.units.UnknownType(obs_type)
            else:
                # Both records exist, both types are known. We can proceed.
                now_vt = weewx.units.as_value_tuple(now_record, obs_type)
                then_vt = weewx.units.as_value_tuple(then_record, obs_type)
                # Do the unit conversion now, rather than lazily. This is because the temperature
                # conversion functions are not distributive. That is,
                #     F_to_C(68F - 50F)
                # is not equal to
                #     F_to_C(68F) - F_to_C(50F)
                # We want the latter, not the former, so we perform the conversion immediately.
                now_vtc = self.converter.convert(now_vt)
                then_vtc = self.converter.convert(then_vt)
                if now_vtc.value is None or then_vtc.value is None:
                    # One of the values is None, so the trend will be None.
                    trend = ValueTuple(None, now_vtc.unit, now_vtc.group)
                else:
                    # All good. Calculate the trend.
                    trend = now_vtc - then_vtc

        # Return the results as a ValueHelper. Use the formatting and labeling options from the
        # current time record. The user can always override these.
        return weewx.units.ValueHelper(trend, 'current', self.formatter, self.converter)
