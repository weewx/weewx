#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Functions for computing aggregates."""
import math

import weeutil.weeutil
import weewx
import weewx.units
import weewx.wxformulas
from weeutil.weeutil import isStartOfDay

# -------------- get_aggregate() --------------

# Set of SQL statements to be used for calculating aggregates from the main archive table.
sql_dict = {
    'first': "SELECT %(obs_type)s FROM %(table_name)s "
             "WHERE dateTime = (SELECT MIN(dateTime) FROM %(table_name)s "
             "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL)",
    'firsttime': "SELECT MIN(dateTime) FROM %(table_name)s "
                 "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL",
    'last': "SELECT %(obs_type)s FROM %(table_name)s "
            "WHERE dateTime = (SELECT MAX(dateTime) FROM %(table_name)s "
            "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL)",
    'lasttime': "SELECT MAX(dateTime) FROM %(table_name)s "
                "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(obs_type)s IS NOT NULL",
    'maxtime': "SELECT dateTime FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "
               "%(obs_type)s = (SELECT MAX(%(obs_type)s) FROM %(table_name)s "
               "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND %(obs_type)s IS NOT NULL",
    'mintime': "SELECT dateTime FROM %(table_name)s "
               "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND "
               "%(obs_type)s = (SELECT MIN(%(obs_type)s) FROM %(table_name)s "
               "WHERE dateTime > %(start)s and dateTime <= %(stop)s) AND %(obs_type)s IS NOT NULL",
}

simple_sql = "SELECT %(aggregate_type)s(%(obs_type)s) FROM %(table_name)s " \
             "WHERE dateTime > %(start)s AND dateTime <= %(stop)s AND %(obs_type)s IS NOT NULL"


def get_aggregate_archive(obs_type, timespan, aggregate_type, db_manager, **option_dict):
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

    if obs_type not in db_manager.sqlkeys:
        raise weewx.UnknownType(obs_type)

    aggregate_type = aggregate_type.lower()

    if aggregate_type not in ['sum', 'count', 'avg', 'max', 'min'] + list(sql_dict.keys()):
        raise weewx.UnknownAggregation(aggregate_type)

    interpolate_dict = {
        'aggregate_type': aggregate_type,
        'obs_type': obs_type,
        'table_name': db_manager.table_name,
        'start': timespan.start,
        'stop': timespan.stop
    }

    select_stmt = sql_dict.get(aggregate_type, simple_sql) % interpolate_dict
    row = db_manager.getSql(select_stmt)

    value = row[0] if row else None

    # Look up the unit type and group of this combination of observation type and aggregation:
    t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type, aggregate_type)
    # Form the ValueTuple and return it:
    return weewx.units.ValueTuple(value, t, g)


# -------------- get_aggregate_daily() --------------

# Set of SQL statements to be used for calculating aggregates from the daily summaries.
daily_sql_dict = {
    'avg': "SELECT SUM(wsum),SUM(sumtime) FROM %(table_name)s_day_%(obs_key)s "
           "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
    'count': "SELECT SUM(count) FROM %(table_name)s_day_%(obs_key)s "
             "WHERE dateTime >= %(start)s AND dateTime < %(stop)s",
    'cumulative': "SELECT SUM(sum) FROM %(table_name)s_day_%(obs_key)s "
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


def get_aggregate_daily(obs_type, timespan, aggregate_type, db_manager, **option_dict):
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

    if aggregate_type == 'cumulative':
        aggregate_type = 'sum'

    # Raise exception if we don't know about this type of aggregation
    if aggregate_type not in daily_sql_dict:
        raise weewx.UnknownAggregation(aggregate_type)

    # We cannot use the day summaries if the starting and ending times of the aggregation interval are not on midnight
    # boundaries, and are not the first or last records in the database.
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
    interDict = {
        'start': weeutil.weeutil.startOfDay(timespan.start),
        'stop': timespan.stop,
        'obs_key': obs_type,
        'aggregate_type': aggregate_type,
        'val': target_val,
        'table_name': db_manager.table_name
    }

    # Run the query against the database:
    row = db_manager.getSql(daily_sql_dict[aggregate_type] % interDict)

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
        deg = 90.0 - math.degrees(math.atan2(row[1], row[0]))
        value = deg if deg >= 0 else deg + 360.0
    else:
        # Unknown aggregation. Should not have gotten this far...
        raise ValueError("Unexpected error. Aggregate type '%s'" % aggregate_type)

    # Look up the unit type and group of this combination of observation type and aggregation:
    t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type, aggregate_type)
    # Form the ValueTuple and return it:
    return weewx.units.ValueTuple(value, t, g)


windvec_types = {
    'windvec': ('windSpeed', 'windDir'),
    'windgustvec': ('windGust', 'windGustDir')
}

sql_dict_wind = {
    'count': "SELECT COUNT(dateTime), usUnits FROM %(table_name)s "
             "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
    'first': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
             "WHERE dateTime = (SELECT MIN(dateTime) FROM %(table_name)s "
             "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
    'last': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
            "WHERE dateTime = (SELECT MAX(dateTime) FROM %(table_name)s "
            "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
    'min': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
           "WHERE %(mag)s = (SELECT MIN(%(mag)s) FROM %(table_name)s "
           "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
    'max': "SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s "
           "WHERE %(mag)s = (SELECT MAX(%(mag)s) FROM %(table_name)s "
           "WHERE dateTime > %(start)s AND dateTime <= %(stop)s  AND %(mag)s IS NOT NULL)",
}
# for types 'avg', 'sum'
complex_sql_wind = 'SELECT %(mag)s, %(dir)s, usUnits FROM %(table_name)s WHERE dateTime > ? AND dateTime <= ?'


def get_aggregate_wind(obs_type, timespan, aggregate_type, db_manager, **option_dict):
    """Returns an aggregation of a wind type over a timespan by using the main archive table.

    obs_type: The type over which aggregation is to be done (e.g., 'barometer',
    'outTemp', 'rain', ...)

    timespan: An instance of weeutil.Timespan with the time period over which
    aggregation is to be done.

    aggregate_type: The type of aggregation to be done.

    db_manager: An instance of weewx.manager.Manager or subclass.

    option_dict: Not used in this version.

    returns: A ValueTuple containing the result. Note that the value contained in the ValueTuple
    will be a complex number for aggregation_types of 'avg', 'sum', 'first', 'last', 'min', and 'max'.
    """
    if obs_type not in windvec_types:
        raise weewx.UnknownType(obs_type)

    aggregate_type = aggregate_type.lower()

    # Raise exception if we don't know about this type of aggregation
    if aggregate_type not in ['avg', 'sum'] + list(sql_dict_wind.keys()):
        raise weewx.UnknownAggregation(aggregate_type)

    # Form the interpolation dictionary
    interpolation_dict = {
        'dir': windvec_types[obs_type][1],
        'mag': windvec_types[obs_type][0],
        'start': weeutil.weeutil.startOfDay(timespan.start),
        'stop': timespan.stop,
        'table_name': db_manager.table_name
    }

    if aggregate_type in sql_dict_wind:
        # For these types, we can do the aggregation in a SELECT statement
        select_stmt = sql_dict_wind[aggregate_type] % interpolation_dict
        row = db_manager.getSql(select_stmt)
        if row:
            std_unit_system = row[-1]
            if aggregate_type == 'count':
                value = row[0]
            else:
                value = complex(row[0], row[1])
        else:
            std_unit_system = db_manager.std_unit_system
            value = None
    else:
        # The result is more complex, requiring vector arithmetic. We will have to do it
        # in Python
        std_unit_system = None
        xsum = ysum = 0.0
        count = 0
        select_stmt = complex_sql_wind % interpolation_dict

        for rec in db_manager.genSql(select_stmt, timespan):

            # Unpack the magnitude and direction
            mag, direction = rec[0:2]

            # Ignore rows where magnitude is NULL
            if mag is None:
                continue

            # A good direction is necessary unless the mag is zero:
            if mag == 0.0 or direction is not None:
                if std_unit_system:
                    if std_unit_system != rec[2]:
                        raise weewx.UnsupportedFeature("Unit type cannot change within a time interval.")
                else:
                    std_unit_system = rec[2]

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
                value = complex(xsum / count, ysum / count)
        else:
            value = None

    # Look up the unit type and group of this combination of observation type and aggregation:
    t, g = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)
    # Form the ValueTuple and return it:
    return weewx.units.ValueTuple(value, t, g)


def get_aggregate_heatcool(obs_type, timespan, aggregate_type, db_manager, **option_dict):
    """Returns an aggregation of a wind type over a timespan by using the main archive table.

    obs_type: The type over which aggregation is to be done (e.g., 'barometer',
    'outTemp', 'rain', ...)

    timespan: An instance of weeutil.Timespan with the time period over which
    aggregation is to be done.

    aggregate_type: The type of aggregation to be done.

    db_manager: An instance of weewx.manager.Manager or subclass.

    option_dict: Not used in this version.

    returns: A ValueTuple containing the result. Note that the value contained in the ValueTuple
    will be a complex number for aggregation_types of 'avg', 'sum', 'first', 'last', 'min', and 'max'.
    """
    # Default base temperature and unit type for heating and cooling degree days,
    # as a value tuple
    default_heatbase = (65.0, "degree_F", "group_temperature")
    default_coolbase = (65.0, "degree_F", "group_temperature")
    default_growbase = (50.0, "degree_F", "group_temperature")

    # Check to see whether heating or cooling degree days are being asked for:
    if obs_type not in ['heatdeg', 'cooldeg', 'growdeg']:
        raise weewx.UnknownType(obs_type)

    # Only summation (total) or average heating or cooling degree days is supported:
    if aggregate_type not in ['sum', 'avg']:
        raise weewx.UnknownAggregation(aggregate_type)

    # Get the base for heating and cooling degree-days
    units_dict = option_dict.get('skin_dict', {}).get('Units', {})
    dd_dict = units_dict.get('DegreeDays', {})
    heatbase = dd_dict.get('heating_base', default_heatbase)
    coolbase = dd_dict.get('cooling_base', default_coolbase)
    growbase = dd_dict.get('growing_base', default_growbase)
    heatbase_t = (float(heatbase[0]), heatbase[1], "group_temperature")
    coolbase_t = (float(coolbase[0]), coolbase[1], "group_temperature")
    growbase_t = (float(growbase[0]), growbase[1], "group_temperature")

    total = 0.0
    count = 0
    for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
        # Get the average temperature for the day as a value tuple:
        Tavg_t = get_aggregate_daily('outTemp', daySpan, 'avg', db_manager)
        # Make sure it's valid before including it in the aggregation:
        if Tavg_t is not None and Tavg_t[0] is not None:
            if obs_type == 'heatdeg':
                # Convert average temperature to the same units as heatbase:
                Tavg_target_t = weewx.units.convert(Tavg_t, heatbase_t[1])
                total += weewx.wxformulas.heating_degrees(Tavg_target_t[0], heatbase_t[0])
            elif obs_type == 'cooldeg':
                # Convert average temperature to the same units as coolbase:
                Tavg_target_t = weewx.units.convert(Tavg_t, coolbase_t[1])
                total += weewx.wxformulas.cooling_degrees(Tavg_target_t[0], coolbase_t[0])
            else:
                # Must be 'growdeg'. Convert average temperature to the same units as growbase:
                Tavg_target_t = weewx.units.convert(Tavg_t, growbase_t[1])
                total += weewx.wxformulas.cooling_degrees(Tavg_target_t[0], growbase_t[0])

            count += 1

    if aggregate_type == 'sum':
        result = total
    else:
        result = total / count if count else None

    # Look up the unit type and group of the result:
    (t, g) = weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type, aggregate_type)
    # Return as a value tuple
    return weewx.units.ValueTuple(result, t, g)


aggregate_fns = [get_aggregate_heatcool,
                 get_aggregate_wind,
                 get_aggregate_daily,
                 get_aggregate_archive]


def get_aggregate(obs_type, timespan, aggregate_type, db_manager, **option_dict):
    for agg_fn in aggregate_fns:
        try:
            return agg_fn(obs_type, timespan, aggregate_type, db_manager, **option_dict)
        except (weewx.UnknownAggregation, weewx.UnknownType):
            pass
    raise weewx.UnknownAggregation(aggregate_type)
