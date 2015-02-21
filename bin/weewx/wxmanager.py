#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Weather-specific database manager."""

import weeutil.weeutil
import weewx.wxformulas
import weewx.manager

#===============================================================================
#                        Class WXDaySummaryManager
#===============================================================================

class WXDaySummaryManager(weewx.manager.DaySummaryManager):
    """Daily summaries, suitable for WX applications.

    Like a regular daily summary database, except it understands wind, and heating- and cooling-degree days."""

    # Default base temperature and unit type for heating and cooling degree days,
    # as a value tuple
    default_heatbase = (65.0, "degree_F", "group_temperature")
    default_coolbase = (65.0, "degree_F", "group_temperature")

    # Sql statement to be used to create the wind daily summaries:
    wx_sql_create_str = "CREATE TABLE %s_day_wind (dateTime INTEGER NOT NULL UNIQUE PRIMARY KEY, "\
      "min REAL, mintime INTEGER, max REAL, maxtime INTEGER, sum REAL, count INTEGER, "\
      "wsum REAL, sumtime INTEGER, "\
      "max_dir REAL, xsum REAL, ysum REAL, dirsumtime INTEGER, squaresum REAL, wsquaresum REAL);"
                             
    def _initialize_day_tables(self, archiveSchema, cursor):
        """Specializing version that adds schema for wind data."""
        # First initialize my superclass:
        weewx.manager.DaySummaryManager._initialize_day_tables(self, archiveSchema, cursor)
        
        # Now initialize the WX specific tables
        cursor.execute(WXDaySummaryManager.wx_sql_create_str % self.table_name)
        
    def getAggregate(self, timespan, obs_type, aggregateType, **option_dict):
        """Specialized version of getDayAggregate that can calculate heating or cooling degree days.

        timespan: An instance of weeutil.Timespan with the time period over which
        aggregation is to be done.

        obs_type: The observation type. For anything other than 'heatdeg' or 'cooldeg',
        the superclass is used.

        aggregateType: The type of aggregation to be done. For 'heatdeg' or 'cooldeg',
        it must be 'sum' or 'avg'.

        returns: A value tuple. First element is the aggregation value,
        or None if not enough data was available to calculate it, or if the aggregation
        type is unknown. The second element is the unit type (eg, 'degree_F').
        Third element is the unit group (eg. 'group_temperature')."""

        # Check to see whether heating or cooling degree days are being asked for:
        if obs_type not in ['heatdeg', 'cooldeg']:
            # No. Use my superclass's version:
            return weewx.manager.DaySummaryManager.getAggregate(self, timespan, obs_type, aggregateType, **option_dict)

        # Only summation (total) or average heating or cooling degree days is supported:
        if aggregateType not in ['sum', 'avg']:
            raise weewx.ViolatedPrecondition, "Aggregate type %s for %s not supported." % (aggregateType, obs_type)

        # Get the base for heating and cooling degree-days
        units_dict = option_dict['skin_dict'].get('Units', {})
        dd_dict = units_dict.get('DegreeDays', {})
        heatbase = dd_dict.get('heating_base')
        coolbase = dd_dict.get('cooling_base')
        heatbase_t = (float(heatbase[0]), heatbase[1], "group_temperature") if heatbase else WXDaySummaryManager.default_heatbase
        coolbase_t = (float(coolbase[0]), coolbase[1], "group_temperature") if coolbase else WXDaySummaryManager.default_coolbase

        _sum = 0.0
        _count = 0
        for daySpan in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
            # Get the average temperature for the day as a value tuple:
            Tavg_t = weewx.manager.DaySummaryManager.getAggregate(self, daySpan, 'outTemp', 'avg')
            # Make sure it's valid before including it in the aggregation:
            if Tavg_t is not None and Tavg_t[0] is not None:
                if obs_type == 'heatdeg':
                    # Convert average temperature to the same units as heatbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, heatbase_t[1])
                    _sum += weewx.wxformulas.heating_degrees(Tavg_target_t[0], heatbase_t[0])
                else:
                    # Convert average temperature to the same units as coolbase:
                    Tavg_target_t = weewx.units.convert(Tavg_t, coolbase_t[1])
                    _sum += weewx.wxformulas.cooling_degrees(Tavg_target_t[0], coolbase_t[0])
                _count += 1

        if aggregateType == 'sum':
            _result = _sum
        else:
            _result = _sum / _count if _count else None

        # Look up the unit type and group of the result:
        (t, g) = weewx.units.getStandardUnitType(self.std_unit_system, obs_type, aggregateType)
        # Return as a value tuple
        return weewx.units.ValueTuple(_result, t, g)
