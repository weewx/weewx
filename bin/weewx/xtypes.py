#
#    Copyright (c) 2019-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined extensions to the WeeWX type system"""

import datetime
import time
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

    def get_scalar(self, obs_type, record, db_manager=None, **option_dict):
        """Calculate a scalar. Specializing versions should raise...
        
        - an exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the
          function.
        - an exception of type `weewx.CannotCalculate` if the type is known to the function, but
          all the information necessary to calculate the type is not there.
          """
        raise weewx.UnknownType

    def get_series(self, obs_type, timespan, db_manager, aggregate_type=None,
                   aggregate_interval=None, **option_dict):
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

def get_scalar(obs_type, record, db_manager=None, **option_dict):
    """Return a scalar value"""

    # Search the list, looking for a get_scalar() method that does not raise an UnknownType
    # exception
    for xtype in xtypes:
        try:
            # Try this function. Be prepared to catch the TypeError exception if it is a legacy
            # style XType that does not accept kwargs.
            try:
                return xtype.get_scalar(obs_type, record, db_manager, **option_dict)
            except TypeError:
                # We likely have a legacy style XType, so try calling it again, but this time
                # without the kwargs.
                return xtype.get_scalar(obs_type, record, db_manager)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)


def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None,
               **option_dict):
    """Return a series (aka vector) of, possibly aggregated, values."""

    # Search the list, looking for a get_series() method that does not raise an UnknownType or
    # UnknownAggregation exception
    for xtype in xtypes:
        try:
            # Try this function. Be prepared to catch the TypeError exception if it is a legacy
            # style XType that does not accept kwargs.
            try:
                return xtype.get_series(obs_type, timespan, db_manager, aggregate_type,
                                        aggregate_interval, **option_dict)
            except TypeError:
                # We likely have a legacy style XType, so try calling it again, but this time
                # without the kwargs.
                return xtype.get_series(obs_type, timespan, db_manager, aggregate_type,
                                        aggregate_interval)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            # This function does not know about the type and/or aggregation.
            # Move on to the next one.
            pass
    # None of the functions worked. Raise an exception with a hopefully helpful error message.
    if aggregate_type:
        msg = "'%s' or '%s'" % (obs_type, aggregate_type)
    else:
        msg = obs_type
    raise weewx.UnknownType(msg)


def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
    """Calculate an aggregation over a timespan"""
    # Search the list, looking for a get_aggregate() method that does not raise an
    # UnknownAggregation exception
    for xtype in xtypes:
        try:
            # Try this function. It will raise an exception if it doesn't know about the type of
            # aggregation.
            return xtype.get_aggregate(obs_type, timespan, aggregate_type, db_manager,
                                       **option_dict)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            pass
    raise weewx.UnknownAggregation("%s('%s')" % (aggregate_type, obs_type))


#
# ######################## Class ArchiveTable ##############################
#

class ArchiveTable(XType):
    """Calculate types and aggregates directly from the archive table"""

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None,
                   **option_dict):
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
                if agg_vt[0] is None:
                    continue
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
                      "WHERE dateTime > ? AND dateTime <= ?" % (obs_type, db_manager.table_name)

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
        'diff': "SELECT (b.%(sql_type)s - a.%(sql_type)s) FROM archive a, archive b "
                "WHERE b.dateTime = (SELECT MAX(dateTime) FROM archive "
                "WHERE dateTime <= %(stop)s) "
                "AND a.dateTime = (SELECT MIN(dateTime) FROM archive "
                "WHERE dateTime >= %(start)s);",
        'first': "SELECT %(sql_type)s FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                 "AND %(sql_type)s IS NOT NULL ORDER BY dateTime ASC LIMIT 1",
        'firsttime': "SELECT MIN(dateTime) FROM %(table_name)s "
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                     "AND %(sql_type)s IS NOT NULL",
        'last': "SELECT %(sql_type)s FROM %(table_name)s "
                "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                "AND %(sql_type)s IS NOT NULL ORDER BY dateTime DESC LIMIT 1",
        'lasttime': "SELECT MAX(dateTime) FROM %(table_name)s "
                    "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                    "AND %(sql_type)s IS NOT NULL",
        'maxtime': "SELECT dateTime FROM %(table_name)s "
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                   "AND %(sql_type)s IS NOT NULL ORDER BY %(sql_type)s DESC LIMIT 1",
        'mintime': "SELECT dateTime FROM %(table_name)s "
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                   "AND %(sql_type)s IS NOT NULL ORDER BY %(sql_type)s ASC LIMIT 1",
        'not_null': "SELECT 1 FROM %(table_name)s "
                    "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                    "AND %(sql_type)s IS NOT NULL LIMIT 1",
        'tderiv': "SELECT (b.%(sql_type)s - a.%(sql_type)s) / (b.dateTime-a.dateTime) "
                  "FROM archive a, archive b "
                  "WHERE b.dateTime = (SELECT MAX(dateTime) FROM archive "
                  "WHERE dateTime <= %(stop)s) "
                  "AND a.dateTime = (SELECT MIN(dateTime) FROM archive "
                  "WHERE dateTime >= %(start)s);",
        'gustdir': "SELECT windGustDir FROM %(table_name)s "
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                   "ORDER BY windGust DESC limit 1",
        # Aggregations 'vecdir' and 'vecavg' require built-in math functions,
        # which were introduced in sqlite v3.35.0, 12-Mar-2021. If they don't exist, then
        # weewx will raise an exception of type "weedb.OperationalError".
        'vecdir': "SELECT SUM(`interval` * windSpeed * COS(RADIANS(90 - windDir))), "
                  "       SUM(`interval` * windSpeed * SIN(RADIANS(90 - windDir))) "
                  "FROM %(table_name)s "
                  "WHERE dateTime > %(start)s AND dateTime <= %(stop)s ",
        'vecavg': "SELECT SUM(`interval` * windSpeed * COS(RADIANS(90 - windDir))), "
                  "       SUM(`interval` * windSpeed * SIN(RADIANS(90 - windDir))), "
                  "       SUM(`interval`) "
                  "FROM %(table_name)s "
                  "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                  "AND windSpeed is not null"
    }

    valid_aggregate_types = set(['sum', 'count', 'avg', 'max', 'min']).union(agg_sql_dict.keys())

    simple_agg_sql = "SELECT %(aggregate_type)s(%(sql_type)s) FROM %(table_name)s " \
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s " \
                     "AND %(sql_type)s IS NOT NULL"

    @staticmethod
    def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """Returns an aggregation of an observation type over a given time period, using the
        main archive table.
    
        Args:
            obs_type (str): The type over which aggregation is to be done (e.g., 'barometer',
                'outTemp', 'rain', ...)
            timespan (TimeSpan): An instance of weeutil.Timespan with the time period over which
                aggregation is to be done.
            aggregate_type (str): The type of aggregation to be done.
            db_manager (weewx.manager.Manager): An instance of weewx.manager.Manager or subclass.
            option_dict (dict): Not used in this version.

        Returns:
            ValueTuple: A ValueTuple containing the result.
        """

        if aggregate_type not in ArchiveTable.valid_aggregate_types:
            raise weewx.UnknownAggregation(aggregate_type)

        # For older versions of sqlite, we need to do these calculations the hard way:
        if obs_type == 'wind' \
                and aggregate_type in ('vecdir', 'vecavg') \
                and not db_manager.connection.has_math:
            return ArchiveTable.get_wind_aggregate_long(obs_type,
                                                        timespan,
                                                        aggregate_type,
                                                        db_manager)

        if obs_type == 'wind':
            sql_type = 'windGust' if aggregate_type == 'max' else 'windSpeed'
        else:
            sql_type = obs_type

        interpolate_dict = {
            'aggregate_type': aggregate_type,
            'sql_type': sql_type,
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

        if aggregate_type == 'not_null':
            value = row is not None
        elif aggregate_type == 'vecdir':
            if None in row or row == (0.0, 0.0):
                value = None
            else:
                deg = 90.0 - math.degrees(math.atan2(row[1], row[0]))
                value = deg if deg >= 0 else deg + 360.0
        elif aggregate_type == 'vecavg':
            value = math.sqrt((row[0] ** 2 + row[1] ** 2) / row[2] ** 2) if row[2] else None
        else:
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

    @staticmethod
    def get_wind_aggregate_long(obs_type, timespan, aggregate_type, db_manager):
        """Calculate the math algorithm for vecdir and vecavg in Python. Suitable for
        versions of sqlite that do not have math functions."""

        # This should never happen:
        if aggregate_type not in ['vecdir', 'vecavg']:
            raise weewx.UnknownAggregation(aggregate_type)

        # Nor this:
        if obs_type != 'wind':
            raise weewx.UnknownType(obs_type)

        sql_stmt = "SELECT `interval`, windSpeed, windDir " \
                   "FROM %(table_name)s " \
                   "WHERE dateTime > %(start)s AND dateTime <= %(stop)s;" \
                   % {
                       'table_name': db_manager.table_name,
                       'start': timespan.start,
                       'stop': timespan.stop
                   }
        xsum = 0.0
        ysum = 0.0
        sumtime = 0.0
        for row in db_manager.genSql(sql_stmt):
            if row[1] is not None:
                sumtime += row[0]
                if row[2] is not None:
                    xsum += row[0] * row[1] * math.cos(math.radians(90.0 - row[2]))
                    ysum += row[0] * row[1] * math.sin(math.radians(90.0 - row[2]))

        if not sumtime:
            value = None
        elif aggregate_type == 'vecdir':
            deg = 90.0 - math.degrees((math.atan2(ysum, xsum)))
            value = deg if deg >= 0 else deg + 360.0
        elif aggregate_type == 'vecavg':
            value = math.sqrt((xsum ** 2 + ysum ** 2) / sumtime ** 2)

        # Look up the unit type and group of this combination of observation type and aggregation:
        u, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                               aggregate_type)

        # Form the ValueTuple and return it:
        return weewx.units.ValueTuple(value, u, g)

#
# ######################## Class DailySummaries ##############################
#

class DailySummaries(XType):
    """Calculate from the daily summaries."""

    # Set of SQL statements to be used for calculating simple aggregates from the daily summaries.
    agg_sql_dict = {
        'avg': "SELECT SUM(wsum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s "
               "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'avg_ge': "SELECT SUM((wsum/sumtime) >= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s and sumtime <> 0",
        'avg_le': "SELECT SUM((wsum/sumtime) <= %(val)s) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s and sumtime <> 0",
        'count': "SELECT SUM(count) FROM %(table_name)s_day_%(obs_key)s "
                 "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'gustdir': "SELECT max_dir FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "ORDER BY max DESC, maxtime ASC LIMIT 1",
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
                      "AND mintime IS NOT NULL "
                      "ORDER BY min DESC, mintime ASC LIMIT 1",
        'maxsum': "SELECT MAX(sum) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'maxsumtime': "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND maxtime IS NOT NULL "
                      "ORDER BY sum DESC, maxtime ASC LIMIT 1",
        'maxtime': "SELECT maxtime FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "AND maxtime IS NOT NULL "
                   "ORDER BY max DESC, maxtime ASC LIMIT 1",
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
                      "AND maxtime IS NOT NULL "
                      "ORDER BY max ASC, maxtime ASC ",
        'minsum': "SELECT MIN(sum) FROM %(table_name)s_day_%(obs_key)s "
                  "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
        'minsumtime': "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  "
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                      "AND mintime IS NOT NULL "
                      "ORDER BY sum ASC, mintime ASC LIMIT 1",
        'mintime': "SELECT mintime FROM %(table_name)s_day_%(obs_key)s  "
                   "WHERE dateTime >= %(start)s AND dateTime < %(stop)s "
                   "AND mintime IS NOT NULL "
                   "ORDER BY min ASC, mintime ASC LIMIT 1",
        'not_null': "SELECT count>0 as c FROM %(table_name)s_day_%(obs_key)s "
                 "WHERE dateTime >= %(start)s AND dateTime < %(stop)s ORDER BY c DESC LIMIT 1",
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

        # We cannot use the daily summaries if there is no aggregation
        if not aggregate_type:
            raise weewx.UnknownAggregation(aggregate_type)

        aggregate_type = aggregate_type.lower()

        # Raise exception if we don't know about this type of aggregation
        if aggregate_type not in DailySummaries.agg_sql_dict:
            raise weewx.UnknownAggregation(aggregate_type)

        # Check to see whether we can use the daily summaries:
        DailySummaries._check_eligibility(obs_type, timespan, db_manager, aggregate_type)

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
        row = db_manager.getSql(DailySummaries.agg_sql_dict[aggregate_type] % inter_dict)

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
                                'not_null', 'sum_ge', 'sum_le', 'avg_ge', 'avg_le']:
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

    # These are SQL statements used for calculating series from the daily summaries.
    # They include "group_def", which will be replaced with a database-specific GROUP BY clause
    common = {
        'min': "SELECT MIN(dateTime), MAX(dateTime), MIN(min) "
               "FROM %(day_table)s "
               "WHERE dateTime>=%(start)s AND dateTime<%(stop)s %(group_def)s",
        'max': "SELECT MIN(dateTime), MAX(dateTime), MAX(max) "
               "FROM %(day_table)s "
               "WHERE dateTime>=%(start)s AND dateTime<%(stop)s %(group_def)s",
        'avg': "SELECT MIN(dateTime), MAX(dateTime), SUM(wsum), SUM(sumtime) "
               "FROM %(day_table)s "
               "WHERE dateTime>=%(start)s AND dateTime<%(stop)s %(group_def)s",
        'sum': "SELECT MIN(dateTime), MAX(dateTime), SUM(sum) "
               "FROM %(day_table)s "
               "WHERE dateTime>=%(start)s AND dateTime<%(stop)s %(group_def)s",
        'count': "SELECT MIN(dateTime), MAX(dateTime), SUM(count) "
                 "FROM %(day_table)s "
                 "WHERE dateTime>=%(start)s AND dateTime<%(stop)s %(group_def)s",
    }
    # Database- and interval-specific "GROUP BY" clauses.
    group_defs = {
        'sqlite': {
            'day': "GROUP BY CAST("
                   "    (julianday(dateTime,'unixepoch','localtime') - 0.5 "
                   "       - CAST(julianday(%(sod)s, 'unixepoch','localtime') AS int)) "
                   "     / %(agg_days)s "
                   "AS int)",
            'month': "GROUP BY strftime('%%Y-%%m',dateTime,'unixepoch','localtime') ",
            'year': "GROUP BY strftime('%%Y',dateTime,'unixepoch','localtime') ",
        },
        'mysql': {
            'day': "GROUP BY TRUNCATE((TO_DAYS(FROM_UNIXTIME(dateTime)) "
                   "- TO_DAYS(FROM_UNIXTIME(%(sod)s)))/ %(agg_days)s, 0) ",
            'month': "GROUP BY DATE_FORMAT(FROM_UNIXTIME(dateTime), '%%%%Y-%%%%m') ",
            'year': "GROUP BY DATE_FORMAT(FROM_UNIXTIME(dateTime), '%%%%Y') ",
        },
    }

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None,
                   **option_dict):

        # We cannot use the daily summaries if there is no aggregation
        if not aggregate_type:
            raise weewx.UnknownAggregation(aggregate_type)

        aggregate_type = aggregate_type.lower()

        # Raise exception if we don't know about this type of aggregation
        if aggregate_type not in DailySummaries.common:
            raise weewx.UnknownAggregation(aggregate_type)

        # Check to see whether we can use the daily summaries:
        DailySummaries._check_eligibility(obs_type, timespan, db_manager, aggregate_type)

        # We also have to make sure the aggregation interval is either the length of a nominal
        # month or year, or some multiple of a calendar day.
        aggregate_interval = weeutil.weeutil.nominal_spans(aggregate_interval)
        if aggregate_interval != weeutil.weeutil.nominal_intervals['year'] \
                and aggregate_interval != weeutil.weeutil.nominal_intervals['month'] \
                and aggregate_interval % 86400:
            raise weewx.UnknownAggregation(aggregate_interval)

        # We're good. Proceed.
        dbtype = db_manager.connection.dbtype
        interp_dict = {
            'agg_days': aggregate_interval / 86400,
            'day_table': "%s_day_%s" % (db_manager.table_name, obs_type),
            'obs_type': obs_type,
            'sod': weeutil.weeutil.startOfDay(timespan.start),
            'start': timespan.start,
            'stop': timespan.stop,
        }
        if aggregate_interval == weeutil.weeutil.nominal_intervals['year']:
            group_by_group = 'year'
        elif aggregate_interval == weeutil.weeutil.nominal_intervals['month']:
            group_by_group = 'month'
        else:
            group_by_group = 'day'
        # Add the database-specific GROUP_BY clause to the interpolation dictionary
        interp_dict['group_def'] = DailySummaries.group_defs[dbtype][group_by_group] % interp_dict
        # This is the final SELECT statement.
        sql_stmt = DailySummaries.common[aggregate_type] % interp_dict

        start_list = list()
        stop_list = list()
        data_list = list()

        for row in db_manager.genSql(sql_stmt):
            # Find the start of this aggregation interval. That's easy: it's the minimum value.
            start_time = row[0]
            # The stop is a little trickier. It's the maximum dateTime in the interval, plus one
            # day. The extra day is needed because the timestamp marks the beginning of a day in a
            # daily summary.
            stop_date = datetime.date.fromtimestamp(row[1]) + datetime.timedelta(days=1)
            stop_time = int(time.mktime(stop_date.timetuple()))

            if aggregate_type in {'min', 'max', 'sum', 'count'}:
                data = row[2]
            elif aggregate_type == 'avg':
                data = row[2] / row[3] if row[3] else None
            else:
                # Shouldn't really have made it here. Fail hard
                raise ValueError("Unknown aggregation type %s" % aggregate_type)

            start_list.append(start_time)
            stop_list.append(stop_time)
            data_list.append(data)

        # Look up the unit type and group of this combination of observation type and aggregation:
        unit, unit_group = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type,
                                                           aggregate_type)
        return (ValueTuple(start_list, 'unix_epoch', 'group_time'),
                ValueTuple(stop_list, 'unix_epoch', 'group_time'),
                ValueTuple(data_list, unit, unit_group))

    @staticmethod
    def _check_eligibility(obs_type, timespan, db_manager, aggregate_type):

        # It has to be a type we know about
        if not hasattr(db_manager, 'daykeys') or obs_type not in db_manager.daykeys:
            raise weewx.UnknownType(obs_type)

        # We cannot use the day summaries if the starting and ending times of the aggregation
        # interval are not on midnight boundaries, and are not the first or last records in the
        # database.
        if db_manager.first_timestamp is None or db_manager.last_timestamp is None:
            raise weewx.UnknownAggregation(aggregate_type)
        if not (isStartOfDay(timespan.start) or timespan.start == db_manager.first_timestamp) \
                or not (isStartOfDay(timespan.stop) or timespan.stop == db_manager.last_timestamp):
            raise weewx.UnknownAggregation(aggregate_type)


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


class XTypeTable(XType):
    """Calculate a series for an xtype. An xtype may not necessarily be in the database, so
    this version calculates it on the fly. Note: this version only works if no aggregation has
    been requested."""

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None,
                   **option_dict):
        """Get a series of an xtype, by using the main archive table. Works only for no
        aggregation. """

        start_vec = list()
        stop_vec = list()
        data_vec = list()

        if aggregate_type:
            # This version does not know how to do aggregations, although this could be
            # added in the future.
            raise weewx.UnknownAggregation(aggregate_type)

        else:
            # No aggregation

            std_unit_system = None

            # Hit the database.
            for record in db_manager.genBatchRecords(*timespan):

                if std_unit_system:
                    if std_unit_system != record['usUnits']:
                        raise weewx.UnsupportedFeature("Unit system cannot change "
                                                       "within a series.")
                else:
                    std_unit_system = record['usUnits']

                # Given a record, use the xtypes system to calculate a value:
                try:
                    value = get_scalar(obs_type, record, db_manager)
                    data_vec.append(value[0])
                except weewx.CannotCalculate:
                    data_vec.append(None)
                start_vec.append(record['dateTime'] - record['interval'] * 60)
                stop_vec.append(record['dateTime'])

            unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type)

        return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
                ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
                ValueTuple(data_vec, unit, unit_group))


# ############################# WindVec extensions #########################################

class WindVec(XType):
    """Extensions for calculating special observation types 'windvec' and 'windgustvec' from the
    main archive table. It provides functions for calculating series, and for calculating
    aggregates.
    """

    windvec_types = {
        'windvec': ('windSpeed', 'windDir'),
        'windgustvec': ('windGust', 'windGustDir')
    }

    agg_sql_dict = {
        'count': "SELECT COUNT(dateTime), usUnits FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL",
        'first': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
                 "ORDER BY dateTime ASC LIMIT 1",
        'last': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
                "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
                "ORDER BY dateTime DESC LIMIT 1",
        'min': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
               "ORDER BY %(mag)s ASC LIMIT 1;",
        'max': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL "
               "ORDER BY %(mag)s DESC LIMIT 1;",
        'not_null' : "SELECT 1, usUnits FROM %(table_name)s "
                     "WHERE dateTime > %(start)s AND dateTime <= %(stop)s "
                     "AND %(mag)s IS NOT NULL LIMIT 1;"
    }
    # for types 'avg', 'sum'
    complex_sql_wind = 'SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s WHERE dateTime > ? ' \
                       'AND dateTime <= ?'

    @staticmethod
    def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None,
                   **option_dict):
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
                                           aggregate_interval, **option_dict)

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
            'start': timespan.start,
            'stop': timespan.stop,
            'table_name': db_manager.table_name
        }

        if aggregate_type in WindVec.agg_sql_dict:
            # For these types (e.g., first, last, etc.), we can do the aggregation in a SELECT
            # statement.
            select_stmt = WindVec.agg_sql_dict[aggregate_type] % interpolation_dict
            try:
                row = db_manager.getSql(select_stmt)
            except weedb.NoColumnError as e:
                raise weewx.UnknownType(e)

            if aggregate_type == 'not_null':
                value = row is not None
                std_unit_system = db_manager.std_unit_system
            else:
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
            # The requested aggregation must be either 'sum' or 'avg', which will require some
            # arithmetic in Python, so it cannot be done by a simple query.
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

        # We can only do 'avg' or 'not_null
        if aggregate_type not in ['avg', 'not_null']:
            raise weewx.UnknownAggregation(aggregate_type)

        # We cannot use the day summaries if the starting and ending times of the aggregation
        # interval are not on midnight boundaries, and are not the first or last records in the
        # database.
        if not (isStartOfDay(timespan.start) or timespan.start == db_manager.first_timestamp) \
                or not (isStartOfDay(timespan.stop) or timespan.stop == db_manager.last_timestamp):
            raise weewx.UnknownAggregation(aggregate_type)

        if aggregate_type == 'not_null':
            # Aggregate type 'not_null' is actually run against 'wind'.
            return DailySummaries.get_aggregate('wind', timespan, 'not_null', db_manager,
                                                **option_dict)

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
xtypes.append(XTypeTable())
