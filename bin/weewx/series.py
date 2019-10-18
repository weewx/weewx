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

import weeutil.weeutil
import weewx
import weewx.aggregate
from weewx.units import ValueTuple

series_types = []


def get_series_archive(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    """Get a series, possibly with aggregation, from the main archive database."""

    # We only know how to get series that are in the database schema:
    if obs_type not in db_manager.sqlkeys:
        raise weewx.UnknownType(obs_type)

    startstamp, stopstamp = timespan
    start_vec = list()
    stop_vec = list()
    data_vec = list()

    if aggregate_type:
        unit, unit_group = None, None
        # With aggregation
        for stamp in weeutil.weeutil.intervalgen(startstamp, stopstamp, aggregate_interval):
            agg_vt = weewx.aggregate.get_aggregate(obs_type, stamp, aggregate_type, db_manager)
            start_vec.append(stamp.start)
            stop_vec.append(stamp.stop)
            if unit:
                if unit != agg_vt[1] or unit_group != agg_vt[2]:
                    raise weewx.UnsupportedFeature("Cannot change unit groups within an aggregation.")
            else:
                unit, unit_group = agg_vt[1:]
            data_vec.append(agg_vt[0])

    else:
        # No aggregation
        sql_str = "SELECT dateTime, %s, usUnits, `interval` FROM %s " \
                  "WHERE dateTime >= ? AND dateTime <= ?" % (obs_type, db_manager.table_name)
        std_unit_system = None
        for record in db_manager.genSql(sql_str, (startstamp, stopstamp)):
            start_vec.append(record[0] - record[3] * 60)
            stop_vec.append(record[0])
            if std_unit_system:
                if std_unit_system != record[2]:
                    raise weewx.UnsupportedFeature("Unit type cannot change within an aggregation interval.")
            else:
                std_unit_system = record[2]
            data_vec.append(record[1])
        unit, unit_group = weewx.units.getStandardUnitType(std_unit_system, obs_type, aggregate_type)

    return (ValueTuple(start_vec, 'unix_epoch', 'group_time'),
            ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
            ValueTuple(data_vec, unit, unit_group))


# Add the function to the list of series types.
series_types.append(get_series_archive)


def get_series(obs_type, timespan, db_manager, aggregate_type=None, aggregate_interval=None):
    for xtype in series_types:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype(obs_type, timespan, db_manager, aggregate_type, aggregate_interval)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)
