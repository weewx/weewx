#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined extensions to the WeeWX type system"""

import math

import weedb
import weeutil.weeutil
import weewx
import weewx.units
import weewx.wxformulas
from weeutil.weeutil import isStartOfDay
from weewx.units import ValueTuple

# A list holding the type extensions. Each entry should be a subclass of XType, defined below.
xtypes = []


class XType(object):
    """Base class for extensions to the WeeWX type system."""

    def get_scalar(self, obs_type, record, db_manager=None):
        """Calculate a scalar. Specializing versions should raise...
        
        - an exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the
          function.
        - an exception of type `weewx.CannotCalculate` if the type is known to the function, but
          all the information necessary to calculate the type is not there.
          """
        raise weewx.UnknownType

    def get_series(self, obs_type, timespan, db_manager, aggregate_type=None,
                   aggregate_interval=None):
        """Calculate a series, possibly with aggregation. Specializing versions should raise...

        - an exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the
          function.
        - an exception of type `weewx.CannotCalculate` if the type is known to the function, but
          all the information necessary to calculate the series is not there.
          """
        raise weewx.UnknownType

    def get_aggregate(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Calculate an aggregation. Specializing versions should raise...
        
        - an exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the
          function.
        - an exception of type `weewx.UnknownAggregation` if the aggregation type `aggregate_type` 
          is unknown to the function.
        - an exception of type `weewx.CannotCalculate` if the type is known to the function, but
          all the information necessary to calculate the type is not there.
          """
        raise weewx.UnknownAggregation

    def shut_down(self):
        """Opportunity to do any clean up."""
        pass


# ##################### Retrieval functions ###########################

def get_scalar(obs_type, record, db_manager=None):
    """Return a scalar value"""
    # Search the list, looking for a get_scalar() method that does not raise an exception
    for xtype in xtypes:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype.get_scalar(obs_type, record, db_manager)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)


def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    """Return a series (aka vector) of, possibly aggregated, values."""
    # Search the list, looking for a get_series() method that does not raise an exception
    for xtype in xtypes:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype.get_series(obs_type, timespan, db_manager, aggregate_type,
                                    aggregate_interval)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)


def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
    """Calculate an aggregation over a timespan"""
    # Search the list, looking for a get_aggregate() method that does not raise an exception
    for xtype in xtypes:
        try:
            # Try this function. It will raise an exception if it doesn't know about the type of
            # aggregation.
            return xtype.get_aggregate(obs_type, timespan, aggregate_type, db_manager,
                                       **option_dict)
        except (weewx.UnknownAggregation, weewx.UnknownType):
            pass
    raise weewx.UnknownAggregation("%s('%s')" % (aggregate_type, obs_type))


#
# ######################## Class ArchiveTable ##############################
#

class ArchiveTable(XType):
    """Calculate types and aggregates directly from the archive table"""

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
        """Get a series, possibly with aggregation, from the main archive database.

        The general strategy is that if aggregation is asked for, chop the series up into separate
        chunks, calculating the aggregate for each chunk. Then assemble the results.

        If no aggregation is called for, just return the data directly out of the database.
        """

        startstamp, stopstamp = timespan
        start_vec = list()
        stop_vec = list()
        data_vec = list()

        if aggregate_type:
            # With aggregation
            unit, unit_group = None, None
            if aggregate_type == 'cumulative':
                do_aggregate = 'sum'
                total = 0
            else:
                do_aggregate = aggregate_type
            for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
                # Get the aggregate as a ValueTuple
                agg_vt = get_aggregate(obs_type, stamp, do_aggregate, db_manager)
                if unit:
                    # It's OK if the unit is unknown (=None).
                    if agg_vt[1] is not None and (unit != agg_vt[1] or unit_group != agg_vt[2]):
                        raise weewx.UnsupportedFeature("Cannot change unit groups "
                                                       "within an aggregation.")
                else:
                    unit, unit_group = agg_vt[1], agg_vt[2]
                start_vec.append(stamp.start)
                stop_vec.append(stamp.stop)
                if aggregate_type == 'cumulative':
                    if agg_vt[0] is not None:
                        total += agg_vt[0]
                    data_vec.append(total)
                else:
                    data_vec.append(agg_vt[0])

        else:

            # No aggregation
            sql_str = "SELECT dateTime, %s, usUnits, `interval` FROM %s " \
                      "WHERE dateTime >= ? AND dateTime <= ?" % (obs_type, db_manager.table_name)

            std_unit_system = None

            # Hit the database. It's possible the type is not in the database, so be prepared
            # to catch a NoColumnError:
            try:
                for record in db_manager.genSql(sql_str, (startstamp, stopstamp)):

                    # Unpack the record
                    timestamp, value, unit_system, interval = record

                    if std_unit_system:
                        if std_unit_system != unit_system:
                            raise weewx.UnsupportedFeature("Unit type cannot change "
                                                           "within an aggregation interval.")
                    else:
                        std_unit_system = unit_system
                    start_vec.append(timestamp - interval * 60)
                    stop_vec.append(timestamp)
                    data_vec.append(value)
            except weedb.NoColumnError:
                # The sql type doesn't exist. Convert to an UnknownType error
                raise weewx.UnknownType(obs_type)

            unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type,
                                                               aggregate_type)

        return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
                ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
                ValueTuple(data_vec, unit, unit_group))

    # Set of SQL statements to be used for calculating aggregates from the main archive table.
    agg_sql_dict = {
        'diff': "SELECT (b.%(obs_type)s - a.%(obs_type)s) FROM archive a, archive b "
                "WHERE b.dateTime = (SELECT MAX(dateTime) FROM archive "
                "WHERE dateTime <= %(stop)s) "
                "AND a.dateTime = (SELECT MIN(dateTime) FROM archive "
                "WHERE dateTime >= %(start)s);",
        'first': "SELECT %(obs_type)s FROM %(table_name)s "
                 "WHERE dateTime = (SELECT MIN(dateTime) FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  "
                 "AND %(obs_type)s IS NOT NULL)",
        'firsttime': "SELECT MIN(dateTime) FROM %(table_name)s "
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  "
                     "AND %(obs_type)s IS NOT NULL",
        'last': "SELECT %(obs_type)s FROM %(table_name)s "
                "WHERE dateTime = (SELECT MAX(dateTime) FROM %(table_name)s "
                "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  "
                "AND %(obs_type)s IS NOT NULL)",
        'lasttime': "SELECT MAX(dateTime) FROM %(table_name)s "
                    "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  "
                    "AND %(obs_type)s IS NOT NULL",
        'maxtime': "SELECT dateTime FROM %(table_name)s "
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "
                   "%(obs_type)s = (SELECT MAX(%(obs_type)s) FROM %(table_name)s "
                   "WHERE dateTime > %(start)s and dateTime <= %(stop)s) "
                   "AND %(obs_type)s IS NOT NULL",
        'mintime': "SELECT dateTime FROM %(table_name)s "
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "
                   "%(obs_type)s = (SELECT MIN(%(obs_type)s) FROM %(table_name)s "
                   "WHERE dateTime > %(start)s and dateTime <= %(stop)s) "
                   "AND %(obs_type)s IS NOT NULL",
        'tderiv': "SELECT (b.%(obs_type)s - a.%(obs_type)s) / (b.dateTime-a.dateTime) "
                  "FROM archive a, archive b "
                  "WHERE b.dateTime = (SELECT MAX(dateTime) FROM archive "
                  "WHERE dateTime <= %(stop)s) "
                  "AND a.dateTime = (SELECT MIN(dateTime) FROM archive "
                  "WHERE dateTime >= %(start)s);",
    }

    simple_agg_sql = "SELECT %(aggregate_type)s(%(obs_type)s) FROM %(table_name)s " \
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s " \
                     "AND %(obs_type)s IS NOT NULL"

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Returns an aggregation of an observation type over a given time period, using the
        main archive table.
    
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
    
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
    
        aggregate_type: The type of aggregation to be done.
    
        db_manager: An instance of weewx.manager.Manager or subclass.
    
        option_dict: Not used in this version.
    
        returns: A ValueTuple containing the result."""

        if aggregate_type not in ['sum', 'count', 'avg', 'max', 'min'] + list(
                ArchiveTable.agg_sql_dict.keys()):
            raise weewx.UnknownAggregation(aggregate_type)

        interpolate_dict = {
            'aggregate_type': aggregate_type,
            'obs_type': obs_type,
            'table_name': db_manager.table_name,
            'start': timespan.start,
            'stop': timespan.stop
        }

        select_stmt = ArchiveTable.agg_sql_dict.get(aggregate_type,
                                                    ArchiveTable.simple_agg_sql) % interpolate_dict

        try:
            row = db_manager.getSql(select_stmt)
        except weedb.NoColumnError:
            raise weewx.UnknownType(aggregate_type)

        value = row[0] if row else None

        # Look up the unit type and group of this combination of observation type and aggregation:
        u, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                               aggregate_type)

        # Time derivatives have special rules. For example, the time derivative of watt-hours is
        # watts, scaled by the number of seconds in an hour. The unit group also changes to
        # group_power.
        if aggregate_type == 'tderiv':
            if u == 'watt_second':
                u = 'watt'
            elif u == 'watt_hour':
                u = 'watt'
                value *= 3600
            elif u == 'kilowatt_hour':
                u = 'kilowatt'
                value *= 3600
            g = 'group_power'

        # Form the ValueTuple and return it:
        return weewx.units.ValueTuple(value, u, g)


#
# ######################## Class DailySummaries ##############################
#

class DailySummaries(XType):
    """Calculate from the daily summaries."""

    # Set of SQL statements to be used for calculating aggregates from the daily summaries.
    daily_sql_dict = {
        'avg': "SELECT SUM(wsum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'count': "SELECT SUM(count) FROM %(table_name)s_day_%(obs_key)s "
                 "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'gustdir': "SELECT max_dir FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "AND max = (SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s)",
        'max': "SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'max_ge': "SELECT SUM(max >= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'max_le': "SELECT SUM(max <= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'maxmin': "SELECT MAX(min) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'maxmintime': "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND min = (SELECT MAX(min) FROM %(table_name)s_day_%(obs_key)s "
                      "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'maxsum': "SELECT MAX(sum) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'maxsumtime': "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND sum = (SELECT MAX(sum) FROM %(table_name)s_day_%(obs_key)s "
                      "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'maxtime': "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "AND max = (SELECT MAX(max) FROM %(table_name)s_day_%(obs_key)s "
                   "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'meanmax': "SELECT AVG(max) FROM %(table_name)s_day_%(obs_key)s "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'meanmin': "SELECT AVG(min) FROM %(table_name)s_day_%(obs_key)s "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'min': "SELECT MIN(min) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'min_ge': "SELECT SUM(min >= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'min_le': "SELECT SUM(min <= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'minmax': "SELECT MIN(max) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'minmaxtime': "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND max = (SELECT MIN(max) FROM %(table_name)s_day_%(obs_key)s "
                      "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'minsum': "SELECT MIN(sum) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'minsumtime': "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND sum = (SELECT MIN(sum) FROM %(table_name)s_day_%(obs_key)s "
                      "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'mintime': "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "AND min = (SELECT MIN(min) FROM %(table_name)s_day_%(obs_key)s "
                   "WHERE dateTime >= %(start)s AND dateTime <%(stop)s)",
        'rms': "SELECT SUM(wsquaresum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'sum': "SELECT SUM(sum) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'sum_ge': "SELECT SUM(sum >= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'sum_le': "SELECT SUM(sum <= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'vecavg': "SELECT SUM(xsum),SUM(ysum),SUM(sumtime)  FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'vecdir': "SELECT SUM(xsum),SUM(ysum) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
    }

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Returns an aggregation of a statistical type for a given time period,
        by using the daily summaries.
    
        obs_type: The type over which aggregation is to be done (e.g., 'barometer',
        'outTemp', 'rain', ...)
    
        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.
    
        aggregate_type: The type of aggregation to be done.
    
        db_manager: An instance of weewx.manager.Manager or subclass.
    
        option_dict: Not used in this version.
    
        returns: A ValueTuple containing the result."""

        # Check to see if this is a valid daily summary type:
        if not hasattr(db_manager, 'daykeys') or obs_type not in db_manager.daykeys:
            raise weewx.UnknownType(obs_type)

        aggregate_type = aggregate_type.lower()

        # Raise exception if we don't know about this type of aggregation
        if aggregate_type not in DailySummaries.daily_sql_dict:
            raise weewx.UnknownAggregation(aggregate_type)

        # We cannot use the day summaries if the starting and ending times of the aggregation
        # interval are not on midnight boundaries, and are not the first or last records in the
        # database.
        if db_manager.first_timestamp is None or db_manager.last_timestamp is None:
            raise weewx.UnknownAggregation(aggregate_type)
        if not (isStartOfDay(timespan.start) or timespan.start == db_manager.first_timestamp) \
                or not (isStartOfDay(timespan.stop) or timespan.stop == db_manager.last_timestamp):
            raise weewx.UnknownAggregation(aggregate_type)

        val = option_dict.get('val')
        if val is None:
            target_val = None
        else:
            # The following is for backwards compatibility when ValueTuples had
            # just two members. This hack avoids breaking old skins.
            if len(val) == 2:
                if val[1] in ['degree_F', 'degree_C']:
                    val += ("group_temperature",)
                elif val[1] in ['inch', 'mm', 'cm']:
                    val += ("group_rain",)
            target_val = weewx.units.convertStd(val, db_manager.std_unit_system)[0]

        # Form the interpolation dictionary
        inter_dict = {
            'start': weeutil.weeutil.startOfDay(timespan.start),
            'stop': timespan.stop,
            'obs_key': obs_type,
            'aggregate_type': aggregate_type,
            'val': target_val,
            'table_name': db_manager.table_name
        }

        # Run the query against the database:
        row = db_manager.getSql(DailySummaries.daily_sql_dict[aggregate_type] % inter_dict)

        # Each aggregation type requires a slightly different calculation.
        if not row or None in row:
            # If no row was returned, or if it contains any nulls (meaning that not
            # all required data was available to calculate the requested aggregate),
            # then set the resulting value to None.
            value = None

        elif aggregate_type in ['min', 'maxmin', 'max', 'minmax', 'meanmin', 'meanmax',
                                'maxsum', 'minsum', 'sum', 'gustdir']:
            # These aggregates are passed through 'as is'.
            value = row[0]

        elif aggregate_type in ['mintime', 'maxmintime', 'maxtime', 'minmaxtime', 'maxsumtime',
                                'minsumtime', 'count', 'max_ge', 'max_le', 'min_ge', 'min_le',
                                'sum_ge', 'sum_le']:
            # These aggregates are always integers:
            value = int(row[0])

        elif aggregate_type == 'avg':
            value = row[0] / row[1] if row[1] else None

        elif aggregate_type == 'rms':
            value = math.sqrt(row[0] / row[1]) if row[1] else None

        elif aggregate_type == 'vecavg':
            value = math.sqrt((row[0] ** 2 + row[1] ** 2) / row[2] ** 2) if row[2] else None

        elif aggregate_type == 'vecdir':
            if row == (0.0, 0.0):
                value = None
            else:
                deg = 90.0 - math.degrees(math.atan2(row[1], row[0]))
                value = deg if deg >= 0 else deg + 360.0
        else:
            # Unknown aggregation. Should not have gotten this far...
            raise ValueError("Unexpected error. Aggregate type '%s'" % aggregate_type)

        # Look up the unit type and group of this combination of observation type and aggregation:
        t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                               aggregate_type)
        # Form the ValueTuple and return it:
        return weewx.units.ValueTuple(value, t, g)


#
# ######################## Class AggregateHeatCool ##############################
#

class AggregateHeatCool(XType):
    """Calculate heating and cooling degree-days."""

    # Default base temperature and unit type for heating and cooling degree days,
    # as a value tuple
    default_heatbase = (65.0, "degree_F", "group_temperature")
    default_coolbase = (65.0, "degree_F", "group_temperature")
    default_growbase = (50.0, "degree_F", "group_temperature")

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Returns heating and cooling degree days over a time period.

        obs_type: The type over which aggregation is to be done.  Must be one of 'heatdeg',
        'cooldeg', or 'growdeg'.

        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.

        aggregate_type: The type of aggregation to be done. Must be 'avg' or 'sum'.

        db_manager: An instance of weewx.manager.Manager or subclass.

        option_dict: Not used in this version.

        returns: A ValueTuple containing the result.
        """

        # Check to see whether heating or cooling degree days are being asked for:
        if obs_type not in ['heatdeg', 'cooldeg', 'growdeg']:
            raise weewx.UnknownType(obs_type)

        # Only summation (total) or average heating or cooling degree days is supported:
        if aggregate_type not in ['sum', 'avg']:
            raise weewx.UnknownAggregation(aggregate_type)

        # Get the base for heating and cooling degree-days
        units_dict = option_dict.get('skin_dict', {}).get('Units', {})
        dd_dict = units_dict.get('DegreeDays', {})
        heatbase = dd_dict.get('heating_base', AggregateHeatCool.default_heatbase)
        coolbase = dd_dict.get('cooling_base', AggregateHeatCool.default_coolbase)
        growbase = dd_dict.get('growing_base', AggregateHeatCool.default_growbase)
        # Convert to a ValueTuple in the same unit system as the database
        heatbase_t = weewx.units.convertStd((float(heatbase[0]), heatbase[1], "group_temperature"),
                                            db_manager.std_unit_system)
        coolbase_t = weewx.units.convertStd((float(coolbase[0]), coolbase[1], "group_temperature"),
                                            db_manager.std_unit_system)
        growbase_t = weewx.units.convertStd((float(growbase[0]), growbase[1], "group_temperature"),
                                            db_manager.std_unit_system)

        total = 0.0
        count = 0
        for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
            # Get the average temperature for the day as a value tuple:
            Tavg_t = DailySummaries.get_aggregate('outTemp', daySpan, 'avg', db_manager)
            # Make sure it's valid before including it in the aggregation:
            if Tavg_t is not None and Tavg_t[0] is not None:
                if obs_type == 'heatdeg':
                    total += weewx.wxformulas.heating_degrees(Tavg_t[0], heatbase_t[0])
                elif obs_type == 'cooldeg':
                    total += weewx.wxformulas.cooling_degrees(Tavg_t[0], coolbase_t[0])
                else:
                    total += weewx.wxformulas.cooling_degrees(Tavg_t[0], growbase_t[0])

                count += 1

        if aggregate_type == 'sum':
            value = total
        else:
            value = total / count if count else None

        # Look up the unit type and group of the result:
        t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                               aggregate_type)
        # Return as a value tuple
        return weewx.units.ValueTuple(value, t, g)


# ############################# WindVec extensions #########################################

class WindVec(XType):
    """Extensions for calculating special observation types 'windvec' and 'windgustvec'. It
    provides functions for calculating series, and for calculating aggregates.
    """

    windvec_types = {
        'windvec': ('windSpeed', 'windDir'),
        'windgustvec': ('windGust', 'windGustDir')
    }

    agg_sql_dict = {
        'count': "SELECT COUNT(dateTime), usUnits FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
        'first': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
                 "WHERE dateTime = (SELECT MIN(dateTime) FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
        'last': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
                "WHERE dateTime = (SELECT MAX(dateTime) FROM %(table_name)s "
                "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
        'min': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
               "ORDER BY %(mag)s ASC LIMIT 1;",
        # 'min': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
        #        "WHERE %(mag)s = (SELECT MIN(%(mag)s) FROM %(table_name)s "
        #        "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
        'max': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
               "ORDER BY %(mag)s DESC LIMIT 1;",
        # 'max': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
        #        "WHERE %(mag)s = (SELECT MAX(%(mag)s) FROM %(table_name)s "
        #        "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
    }
    # for types 'avg', 'sum'
    complex_sql_wind = 'SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s WHERE dateTime > ? ' \
                       'AND dateTime <= ?'

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
        """Get a series, possibly with aggregation, for special 'wind vector' types. These are
        typically used for the wind vector plots.
        """

        # Check to see if the requested type is not 'windvec' or 'windgustvec'
        if obs_type not in WindVec.windvec_types:
            # The type is not one of the extended wind types. We can't handle it.
            raise weewx.UnknownType(obs_type)

        # It is an extended wind type. Prepare the lists that will hold the
        # final results.
        start_vec = list()
        stop_vec = list()
        data_vec = list()

        # Is aggregation requested?
        if aggregate_type:
            # Yes. Just use the regular series function. When it comes time to do the aggregation,
            # the specialized function WindVec.get_aggregate() (defined below), will be used.
            return ArchiveTable.get_series(obs_type, timespan, db_manager, aggregate_type,
                                           aggregate_interval)

        else:
            # No aggregation desired. However, we have will have to assemble the wind vector from
            # its flattened types. This SQL select string will select the proper wind types
            sql_str = 'SELECT dateTime, %s, %s, usUnits, `interval` FROM %s ' \
                      'WHERE dateTime >= ? AND dateTime <= ?' \
                      % (WindVec.windvec_types[obs_type][0], WindVec.windvec_types[obs_type][1],
                         db_manager.table_name)
            std_unit_system = None

            for record in db_manager.genSql(sql_str, timespan):
                ts, magnitude, direction, unit_system, interval = record
                if std_unit_system:
                    if std_unit_system != unit_system:
                        raise weewx.UnsupportedFeature(
                            "Unit type cannot change within a time interval.")
                else:
                    std_unit_system = unit_system

                value = weeutil.weeutil.to_complex(magnitude, direction)

                start_vec.append(ts - interval * 60)
                stop_vec.append(ts)
                data_vec.append(value)

            unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type,
                                                               aggregate_type)

        return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
                ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
                ValueTuple(data_vec, unit, unit_group))

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Returns an aggregation of a wind vector type over a timespan by using the main archive
        table.

        obs_type: The type over which aggregation is to be done. For this function, it must be
        'windvec' or 'windgustvec'. Anything else will cause weewx.UnknownType to be raised.

        timespan: An instance of weeutil.Timespan with the time period over which aggregation is to
        be done.

        aggregate_type: The type of aggregation to be done. For this function, must be 'avg',
        'sum', 'count', 'first', 'last', 'min', or 'max'. Anything else will cause
        weewx.UnknownAggregation to be raised.

        db_manager: An instance of weewx.manager.Manager or subclass.

        option_dict: Not used in this version.

        returns: A ValueTuple containing the result. Note that the value contained in the
        ValueTuple will be a complex number.
        """
        if obs_type not in WindVec.windvec_types:
            raise weewx.UnknownType(obs_type)

        aggregate_type = aggregate_type.lower()

        # Raise exception if we don't know about this type of aggregation
        if aggregate_type not in ['avg', 'sum'] + list(WindVec.agg_sql_dict.keys()):
            raise weewx.UnknownAggregation(aggregate_type)

        # Form the interpolation dictionary
        interpolation_dict = {
            'dir': WindVec.windvec_types[obs_type][1],
            'mag': WindVec.windvec_types[obs_type][0],
            'start': weeutil.weeutil.startOfDay(timespan.start),
            'stop': timespan.stop,
            'table_name': db_manager.table_name
        }

        if aggregate_type in WindVec.agg_sql_dict:
            # For these types (e.g., first, last, etc.), we can do the aggregation in a SELECT
            # statement.
            select_stmt = WindVec.agg_sql_dict[aggregate_type] % interpolation_dict
            row = db_manager.getSql(select_stmt)
            if row:
                if aggregate_type == 'count':
                    value, std_unit_system = row
                else:
                    magnitude, direction, std_unit_system = row
                    value = weeutil.weeutil.to_complex(magnitude, direction)
            else:
                std_unit_system = db_manager.std_unit_system
                value = None
        else:
            # The result is more complex, requiring vector arithmetic. We will have to do it
            # in Python
            std_unit_system = None
            xsum = ysum = 0.0
            count = 0
            select_stmt = WindVec.complex_sql_wind % interpolation_dict

            for rec in db_manager.genSql(select_stmt, timespan):

                # Unpack the record
                mag, direction, unit_system = rec

                # Ignore rows where magnitude is NULL
                if mag is None:
                    continue

                # A good direction is necessary unless the mag is zero:
                if mag == 0.0 or direction is not None:
                    if std_unit_system:
                        if std_unit_system != unit_system:
                            raise weewx.UnsupportedFeature(
                                "Unit type cannot change within a time interval.")
                    else:
                        std_unit_system = unit_system

                    # An undefined direction is OK (and expected) if the magnitude
                    # is zero. But, in that case, it doesn't contribute to the sums either.
                    if direction is None:
                        # Sanity check
                        if weewx.debug:
                            assert (mag == 0.0)
                    else:
                        xsum += mag * math.cos(math.radians(90.0 - direction))
                        ysum += mag * math.sin(math.radians(90.0 - direction))
                    count += 1

            # We've gone through the whole interval. Were there any good data?
            if count:
                # Form the requested aggregation:
                if aggregate_type == 'sum':
                    value = complex(xsum, ysum)
                else:
                    # Must be 'avg'
                    value = complex(xsum, ysum) / count
            else:
                value = None

        # Look up the unit type and group of this combination of observation type and aggregation:
        t, g = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)
        # Form the ValueTuple and return it:
        return weewx.units.ValueTuple(value, t, g)


class WindVecDaily(XType):
    """Extension for calculating the average windvec, using the  daily summaries."""

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Optimization for calculating 'avg' aggregations for type 'windvec'. The
        timespan must be on a daily boundary."""

        # We can only do observation type 'windvec'
        if obs_type != 'windvec':
            # We can't handle it.
            raise weewx.UnknownType(obs_type)

        # We can only do 'avg''
        if aggregate_type != 'avg':
            raise weewx.UnknownAggregation(aggregate_type)

        # We cannot use the day summaries if the starting and ending times of the aggregation
        # interval are not on midnight boundaries, and are not the first or last records in the
        # database.
        if not (isStartOfDay(timespan.start) or timespan.start == db_manager.first_timestamp) \
                or not (isStartOfDay(timespan.stop) or timespan.stop == db_manager.last_timestamp):
            raise weewx.UnknownAggregation(aggregate_type)

        sql = 'SELECT SUM(xsum), SUM(ysum), SUM(dirsumtime) ' \
              'FROM %s_day_wind WHERE dateTime>=? AND dateTime<?;' % db_manager.table_name

        row = db_manager.getSql(sql, timespan)

        if not row or None in row or not row[2]:
            # If no row was returned, or if it contains any nulls (meaning that not
            # all required data was available to calculate the requested aggregate),
            # then set the resulting value to None.
            value = None
        else:
            value = complex(row[0], row[1]) / row[2]

        # Look up the unit type and group of the result:
        t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                               aggregate_type)
        # Return as a value tuple
        return weewx.units.ValueTuple(value, t, g)


# Add instantiated versions to the extension list. Order matters. We want the highly-specialized
# versions first, because they might offer optimizations.
xtypes.append(WindVecDaily())
xtypes.append(WindVec())
xtypes.append(AggregateHeatCool())
xtypes.append(DailySummaries())
xtypes.append(ArchiveTable())
