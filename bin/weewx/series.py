#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined extensible series.

Series (aka vector) type extensions use a function with signature
      fn(obs_type, timespan, db_manager, aggregate_type, aggregate_interval)
where

- `obs_type` is the type to be computed.
- `timespan` is an instance of `weeutil.weeutil.TimeSpan`. It defines bounding start and ending times of the series,
exclusive on the left, inclusive on the right.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.
- `aggregate_type` defines the type of aggregation. Typically, it is one of `sum`, `avg`, `min`, or `max`,
although there is nothing stopping the user-defined extension from defining new types of aggregation. If
set to `None`, then no aggregation should occur, and the full series should be returned.
- `aggregate_interval` is an aggregation interval. If set to `None`, then a single value should be returned: the
aggregate value over the entire `timespan`. Otherwise, the series should be grouped by the aggregation interval.

The function should return:

- A three-way tuple:
    ```(start_list_vt, stop_list_vt, data_list_vt)``` where

    * `start_list_vt` is a `ValueTuple`, whose first element is the list of start times;
    * `stop_list_vt` is a `ValueTuple`, whose first element is the list of stop times;
    * `data_list_vt` is a `ValueTuple`, whose first element is the list of aggregated values.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the instance.
- An exception of type `weewx.CannotCalculate` if the type is known to the function, but all the information
necessary to calculate the type is not there.
"""

import math

import weeutil.weeutil
import weewx
import weewx.aggregate
from weewx.units import ValueTuple

series_types = []


def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    """Return a vector series for a timespan, possibly aggregated. This is the
    main function to use.

    Args:
        obs_type: The observation type for which the series is to be calculated.
        timespan:  A two-way tuple with the (start, stop] times of the series.
        db_manager: An open manager.Manager object, or subclass
        aggregate_type: The type of aggregation to be performed. Default is None (no aggregation).
        aggregate_interval: The interval over which aggregation is to be done.

    Returns:
        3-way tuple: (ValueTuple holding start times,
                      ValueTuple holding stop times,
                      ValueTuple holding (possibly aggregated) values.

    Raises:
          weewx.UnknownType if no extension can be found that can calculate this type.
          weewx.UnknownAggregate: if the type of aggregation is unknown.
          weewx.CannotCalculate: if data required for the calculation is missing.
     """
    for xtype in series_types:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype(obs_type, timespan, db_manager, aggregate_type, aggregate_interval)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)


def get_series_archive(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    """Get a series, possibly with aggregation, from the main archive database."""

    startstamp, stopstamp = timespan
    start_vec = list()
    stop_vec = list()
    data_vec = list()

    if aggregate_type:
        unit, unit_group = None, None
        # With aggregation
        for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
            # Could possibly raise a weewx.UnknownType or weewx.UnknownAggregation exception, but
            # we don't care. Let it pass, so some other series extension can give it a try.
            agg_vt = weewx.aggregate.get_aggregate(obs_type, stamp, aggregate_type, db_manager)
            if unit:
                if unit != agg_vt[1] or unit_group != agg_vt[2]:
                    raise weewx.UnsupportedFeature("Cannot change unit groups within an aggregation.")
            else:
                unit, unit_group = agg_vt[1:]
            start_vec.append(stamp.start)
            stop_vec.append(stamp.stop)
            data_vec.append(agg_vt[0])

    else:
        # We only know how to get series that are in the database schema:
        if obs_type not in db_manager.sqlkeys:
            raise weewx.UnknownType(obs_type)

        # No aggregation
        sql_str = "SELECT dateTime, %s, usUnits, `interval` FROM %s " \
                  "WHERE dateTime >= ? AND dateTime <= ?" % (obs_type, db_manager.table_name)
        std_unit_system = None
        for record in db_manager.genSql(sql_str, (startstamp, stopstamp)):
            if std_unit_system:
                if std_unit_system != record[2]:
                    raise weewx.UnsupportedFeature("Unit type cannot change within an aggregation interval.")
            else:
                std_unit_system = record[2]
            start_vec.append(record[0] - record[3] * 60)
            stop_vec.append(record[0])
            data_vec.append(record[1])
        unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)

    return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
            ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
            ValueTuple(data_vec, unit, unit_group))


windvec_types = {'windvec': 'windSpeed, windDir',
                 'windgustvec': 'windGust, windGustDir'}


def get_series_windvec(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    """Get a series, possibly with aggregation, for special 'wind' types."""

    # Check to see if the requested type is not 'windvec' or 'windgustvec'
    if obs_type not in windvec_types:
        # The type is not one of the extended wind types.
        raise weewx.UnknownType(obs_type)

    # It is an extended wind type. Prepare the lists that will hold the
    # final results.
    startstamp, stopstamp = timespan
    start_vec = list()
    stop_vec = list()
    data_vec = list()

    # Is aggregation requested?
    if aggregate_type:

        unit, unit_group = None, None
        # With aggregation
        for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
            agg_vt = weewx.aggregate.get_aggregate(obs_type, stamp, aggregate_type, db_manager)
            start_vec.append(stamp.start)
            stop_vec.append(stamp.stop)
            if unit:
                # It's OK if the unit is unknown (=None).
                if agg_vt[1] is not None and (unit != agg_vt[1] or unit_group != agg_vt[2]):
                    raise weewx.UnsupportedFeature("Cannot change unit groups within an aggregation.")
            else:
                unit, unit_group = agg_vt[1:]
            data_vec.append(agg_vt[0])

    else:
        # No aggregation desired.
        # This SQL select string will select the proper wind types
        sql_str = 'SELECT dateTime, %s, usUnits, `interval` FROM %s WHERE dateTime >= ? AND dateTime <= ?' \
                  % (windvec_types[obs_type], db_manager.table_name)
        std_unit_system = None

        for record in db_manager.genSql(sql_str, timespan):
            start_vec.append(record[0] - record[4] * 60)
            stop_vec.append(record[0])
            if std_unit_system:
                if std_unit_system != record[3]:
                    raise weewx.UnsupportedFeature("Unit type cannot change within a time interval.")
            else:
                std_unit_system = record[3]
            # Break the mag and dir down into x- and y-components.
            (magnitude, direction) = record[1:3]
            if magnitude is None or direction is None:
                data_vec.append(None)
            else:
                x = magnitude * math.cos(math.radians(90.0 - direction))
                y = magnitude * math.sin(math.radians(90.0 - direction))
                if weewx.debug:
                    # There seem to be some little rounding errors that
                    # are driving my debugging crazy. Zero them out
                    if abs(x) < 1.0e-6: x = 0.0
                    if abs(y) < 1.0e-6: y = 0.0
                data_vec.append(complex(x, y))
        unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)

    return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
            ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
            ValueTuple(data_vec, unit, unit_group))


# Add the functions to the list of series types.
series_types.append(get_series_windvec)
series_types.append(get_series_archive)
