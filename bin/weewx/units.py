# -*- coding: utf-8 -*-
#
#    Copyright (c) 2010-2014 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
# $Id$
#
"""Data structures and functions for dealing with units."""

import locale
import time
import syslog

import weewx
import weeutil.weeutil

class UnknownType(object):
    """Indicates that the observation type is unknown."""
    def __init__(self, obs_type):
        self.obs_type = obs_type

unit_constants = {'US'       : weewx.US,
                  'METRIC'   : weewx.METRIC,
                  'METRICWX' : weewx.METRICWX}

unit_nicknames = {weewx.US       : 'US',
                  weewx.METRIC   : 'METRIC',
                  weewx.METRICWX : 'METRICWX'}

# This data structure maps observation types to a "unit group"
obs_group_dict = {"altitude"           : "group_altitude",
                  "cooldeg"            : "group_degree_day",
                  "heatdeg"            : "group_degree_day",
                  "gustdir"            : "group_direction",
                  "vecdir"             : "group_direction",
                  "windDir"            : "group_direction",
                  "windGustDir"        : "group_direction",
                  "interval"           : "group_interval",
                  "soilMoist1"         : "group_moisture",
                  "soilMoist2"         : "group_moisture",
                  "soilMoist3"         : "group_moisture",
                  "soilMoist4"         : "group_moisture",
                  "extraHumid1"        : "group_percent",
                  "extraHumid2"        : "group_percent",
                  "inHumidity"         : "group_percent",
                  "outHumidity"        : "group_percent",
                  "rxCheckPercent"     : "group_percent",
                  "altimeter"          : "group_pressure",
                  "barometer"          : "group_pressure",
                  "pressure"           : "group_pressure",
                  "radiation"          : "group_radiation",
                  "ET"                 : "group_rain",
                  "dayRain"            : "group_rain",
                  "hail"               : "group_rain",
                  "hourRain"           : "group_rain",
                  "monthRain"          : "group_rain",
                  "rain"               : "group_rain",
                  "rain24"             : "group_rain",
                  "totalRain"          : "group_rain",
                  "stormRain"          : "group_rain",
                  "yearRain"           : "group_rain",
                  "hailRate"           : "group_rainrate",
                  "rainRate"           : "group_rainrate",
                  "wind"               : "group_speed",
                  "windGust"           : "group_speed",
                  "windSpeed"          : "group_speed",
                  "windSpeed10"        : "group_speed",
                  "windgustvec"        : "group_speed",
                  "windvec"            : "group_speed",
                  "rms"                : "group_speed2",
                  "vecavg"             : "group_speed2",
                  "dewpoint"           : "group_temperature",
                  "extraTemp1"         : "group_temperature",
                  "extraTemp2"         : "group_temperature",
                  "extraTemp3"         : "group_temperature",
                  "heatindex"          : "group_temperature",
                  "heatingTemp"        : "group_temperature",
                  "inTemp"             : "group_temperature",
                  "leafTemp1"          : "group_temperature",
                  "leafTemp2"          : "group_temperature",
                  "outTemp"            : "group_temperature",
                  "soilTemp1"          : "group_temperature",
                  "soilTemp2"          : "group_temperature",
                  "soilTemp3"          : "group_temperature",
                  "soilTemp4"          : "group_temperature",
                  "windchill"          : "group_temperature",
                  "dateTime"           : "group_time",
                  "UV"                 : "group_uv",
                  "consBatteryVoltage" : "group_volt",
                  "heatingVoltage"     : "group_volt",
                  "referenceVoltage"   : "group_volt",
                  "supplyVoltage"      : "group_volt"}

# Some aggregations when applied to a type result in a different unit
# group. This data structure maps aggregation type to the group:
agg_group = {'mintime'    : "group_time",
             'maxmintime' : "group_time",
             'maxtime'    : "group_time",
             'minmaxtime' : "group_time",
             "maxsumtime" : "group_time",
             'count'      : "group_count",
             'max_ge'     : "group_count",
             'max_le'     : "group_count",
             'min_le'     : "group_count",
             'sum_ge'     : "group_count",
             'vecdir'     : "group_direction",
             'gustdir'    : "group_direction"}

# This dictionary maps unit groups to a standard unit type in the 
# US customary unit system:
USUnits     = {"group_altitude"    : "foot",
               "group_count"       : "count",
               "group_degree_day"  : "degree_F_day",
               "group_direction"   : "degree_compass",
               "group_elapsed"     : "second",
               "group_interval"    : "minute",
               "group_moisture"    : "centibar",
               "group_percent"     : "percent",
               "group_pressure"    : "inHg",
               "group_radiation"   : "watt_per_meter_squared",
               "group_rain"        : "inch",
               "group_rainrate"    : "inch_per_hour",
               "group_speed"       : "mile_per_hour",
               "group_speed2"      : "mile_per_hour2",
               "group_temperature" : "degree_F",
               "group_time"        : "unix_epoch",
               "group_uv"          : "uv_index",
               "group_volt"        : "volt"}

# This dictionary maps unit groups to a standard unit type in the 
# metric unit system:
MetricUnits = {"group_altitude"    : "meter",
               "group_count"       : "count",
               "group_degree_day"  : "degree_C_day",
               "group_direction"   : "degree_compass",
               "group_elapsed"     : "second",
               "group_interval"    : "minute",
               "group_moisture"    : "centibar",
               "group_percent"     : "percent",
               "group_pressure"    : "mbar",
               "group_radiation"   : "watt_per_meter_squared",
               "group_rain"        : "cm",
               "group_rainrate"    : "cm_per_hour",
               "group_speed"       : "km_per_hour",
               "group_speed2"      : "km_per_hour2",
               "group_temperature" : "degree_C",
               "group_time"        : "unix_epoch",
               "group_uv"          : "uv_index",
               "group_volt"        : "volt"}

# This dictionary maps unit groups to a standard unit type in the 
# "Metric WX" unit system. It's the same as the "Metric" system,
# except for rain and speed:
MetricWXUnits = dict(MetricUnits)
MetricWXUnits['group_rain']     = "mm"
MetricWXUnits['group_rainrate'] = "mm_per_hour"
MetricWXUnits['group_speed']    = "meter_per_second"
MetricWXUnits['group_speed2']   = "meter_per_second2"


# Conversion functions to go from one unit type to another.
conversionDict = {
      'inHg'             : {'mbar'             : lambda x : x * 33.86, 
                            'hPa'              : lambda x : x * 33.86,
                            'mmHg'             : lambda x : x * 25.4},
      'degree_F'         : {'degree_C'         : lambda x : (x-32.0) * (5.0/9.0)},
      'degree_F_day'     : {'degree_C_day'     : lambda x : x * (5.0/9.0)},
      'mile_per_hour'    : {'km_per_hour'      : lambda x : x * 1.609344,
                            'knot'             : lambda x : x * 0.868976242,
                            'meter_per_second' : lambda x : x * 0.44704},
      'mile_per_hour2'   : {'km_per_hour2'     : lambda x : x * 1.609344,
                            'knot2'            : lambda x : x * 0.868976242,
                            'meter_per_second2': lambda x : x * 0.44704},
      'knot'             : {'mile_per_hour'    : lambda x : x * 1.15077945,
                            'km_per_hour'      : lambda x : x * 1.85200,
                            'meter_per_second' : lambda x : x * 0.514444444},
      'knot2'             : {'mile_per_hour2'  : lambda x : x * 1.15077945,
                            'km_per_hour2'     : lambda x : x * 1.85200,
                            'meter_per_second2': lambda x : x * 0.514444444},
      'inch_per_hour'    : {'cm_per_hour'      : lambda x : x * 2.54,
                            'mm_per_hour'      : lambda x : x * 25.4},
      'inch'             : {'cm'               : lambda x : x * 2.54,
                            'mm'               : lambda x : x * 25.4},
      'foot'             : {'meter'            : lambda x : x * 0.3048},
      'mmHg'             : {'inHg'             : lambda x : x / 25.4,
                            'mbar'             : lambda x : x / 0.75006168,
                            'hPa'              : lambda x : x / 0.75006168},
      'mbar'             : {'inHg'             : lambda x : x / 33.86,
                            'mmHg'             : lambda x : x * 0.75006168,
                            'hPa'              : lambda x : x * 1.0},
      'hPa'              : {'inHg'             : lambda x : x / 33.86,
                            'mmHg'             : lambda x : x * 0.75006168,
                            'mbar'             : lambda x : x * 1.0},
      'degree_C'         : {'degree_F'         : lambda x : x * (9.0/5.0) + 32.0},
      'degree_C_day'     : {'degree_F_day'     : lambda x : x * (9.0/5.0)},
      'km_per_hour'      : {'mile_per_hour'    : lambda x : x * 0.621371192,
                            'knot'             : lambda x : x * 0.539956803,
                            'meter_per_second' : lambda x : x * 0.277777778},
      'meter_per_second' : {'mile_per_hour'    : lambda x : x * 2.23693629,
                            'knot'             : lambda x : x * 1.94384449,
                            'km_per_hour'      : lambda x : x * 3.6},
      'meter_per_second2': {'mile_per_hour2'   : lambda x : x * 2.23693629,
                            'knot2'            : lambda x : x * 1.94384449,
                            'km_per_hour2'     : lambda x : x * 3.6},
      'cm_per_hour'      : {'inch_per_hour'    : lambda x : x * 0.393700787,
                            'mm_per_hour'      : lambda x : x * 10.0},
      'mm_per_hour'      : {'inch_per_hour'    : lambda x : x * .0393700787,
                            'cm_per_hour'      : lambda x : x * 0.10},
      'cm'               : {'inch'             : lambda x : x * 0.393700787,
                            'mm'               : lambda x : x * 10.0},
      'mm'               : {'inch'             : lambda x : x * .0393700787,
                            'cm'               : lambda x : x * 0.10},
      'meter'            : {'foot'             : lambda x : x * 3.2808399 },
      'dublin_jd'        : {'unix_epoch'       : lambda x : (x-25567.5) * 86400.0},
      'unix_epoch'       : {'dublin_jd'        : lambda x : x/86400.0 + 25567.5},
      'second'           : {'hour'             : lambda x : x/3600.0,
                            'day'              : lambda x : x/86400.0},
      'hour'             : {'second'           : lambda x : x*3600.0,
                            'day'              : lambda x : x/24.0},
      'day'              : {'second'           : lambda x : x*86400.0,
                            'hour'             : lambda x : x*24.0}}

# This will extract all the target unit types in the above dictionary:
allPossibleUnitTypes = set(z for d in conversionDict.values() for z in d.keys())

# Default unit formatting to be used in the absence of a skin configuration file
default_unit_format_dict = {"centibar"           : "%.0f",
                            "cm"                 : "%.2f",
                            "cm_per_hour"        : "%.2f",
                            "day"                : "%.1f",
                            "degree_C"           : "%.1f",
                            "degree_C_day"       : "%.1f",
                            "degree_F"           : "%.1f",
                            "degree_F_day"       : "%.1f",
                            "degree_compass"     : "%.0f",
                            "foot"               : "%.0f",
                            "hPa"                : "%.1f",
                            "hour"               : "%.1f",
                            "inHg"               : "%.3f",
                            "inch"               : "%.2f",
                            "inch_per_hour"      : "%.2f",
                            "km_per_hour"        : "%.0f",
                            "km_per_hour2"       : "%.1f",
                            "knot"               : "%.0f",
                            "knot2"              : "%.1f",
                            "mbar"               : "%.1f",
                            "meter"              : "%.0f",
                            "meter_per_second"   : "%.0f",
                            "meter_per_second2"  : "%.1f",
                            "mile_per_hour"      : "%.0f",
                            "mile_per_hour2"     : "%.1f",
                            "mm"                 : "%.1f",
                            "mmHg"               : "%.1f",
                            "mm_per_hour"        : "%.1f",
                            "percent"            : "%.0f",
                            "second"             : "%.0f",
                            "uv_index"           : "%.1f",
                            "volt"               : "%.1f",
                            "watt_per_meter_squared" : "%.0f",
                            "NONE"              : "   N/A"}

# Default unit labels to be used in the absence of a skin configuration file
default_unit_label_dict = { "centibar"          : " cb",
                            "cm"                : " cm",
                            "cm_per_hour"       : " cm/hr",
                            "day"               : " days",
                            "degree_C"          : "\xc2\xb0C",
                            "degree_C_day"      : "\xc2\xb0C-day",
                            "degree_F"          : "\xc2\xb0F",
                            "degree_F_day"      : "\xc2\xb0F-day",
                            "degree_compass"    : "\xc2\xb0",
                            "foot"              : " feet",
                            "hPa"               : " hPa",
                            "inHg"              : " inHg",
                            "hour"              : " hrs",
                            "inch"              : " in",
                            "inch_per_hour"     : " in/hr",
                            "km_per_hour"       : " kph",
                            "km_per_hour2"      : " kph",
                            "knot"              : " knots",
                            "knot2"             : " knots",
                            "mbar"              : " mbar",
                            "meter"             : " meters",
                            "meter_per_second"  : " m/s",
                            "meter_per_second2" : " m/s",
                            "mile_per_hour"     : " mph",
                            "mile_per_hour2"    : " mph",
                            "mm"                : " mm",
                            "mmHg"              : " mmHg",
                            "mm_per_hour"       : " mm/hr",
                            "percent"           : "%",
                            "second"            : " secs",
                            "uv_index"          : "",
                            "volt"              : " V",
                            "watt_per_meter_squared" : " W/m\xc2\xb2",
                            "NONE"              : "" }

# Default strftime formatting to be used in the absence of a skin
# configuration file:
default_time_format_dict = {"day"        : "%H:%M",
                            "week"       : "%H:%M on %A",
                            "month"      : "%d-%b-%Y %H:%M",
                            "year"       : "%d-%b-%Y %H:%M",
                            "rainyear"   : "%d-%b-%Y %H:%M",
                            "current"    : "%d-%b-%Y %H:%M",
                            "ephem_day"  : "%H:%M",
                            "ephem_year" : "%d-%b-%Y %H:%M"}

# Default mapping from compass degrees to ordinals
default_ordinate_names = ['N', 'NNE','NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                          'S', 'SSW','SW', 'WSW', 'W', 'WNW', 'NW', 'NNW',
                          'N/A']

#==============================================================================
#                        class ValueTuple
#==============================================================================

# A value, along with the unit it is in, can be represented by a 3-way tuple
# called a value tuple. All weewx routines can accept a simple unadorned
# 3-way tuple as a value tuple, but they return the type ValueTuple. It is
# useful because its contents can be accessed using named attributes.
#
# Item   attribute   Meaning
#    0    value      The datum value (eg, 20.2)
#    1    unit       The unit it is in ("degree_C")
#    2    group      The unit group ("group_temperature")
#
# It is valid to have a datum value of None.
#
# It is also valid to have a unit type of None (meaning there is no information
# about the unit the value is in). In this case, you won't be able to convert
# it to another unit.

class ValueTuple(tuple):
    def __new__(cls, *args):
        return tuple.__new__(cls, args)
    @property
    def value(self):
        return self[0]
    @property
    def unit(self):
        return self[1]
    @property
    def group(self):
        return self[2]
    # ValueTuples have some modest math abilities: subtraction and addition.
    def __sub__(self, other):
        if self[1] != other[1] or self[2] != other[2]:
            raise TypeError("unsupported operand error for subtraction: %s and %s" % (self[1], other[1]))
        return ValueTuple(self[0] - other[0], self[1], self[2])
    def __add__(self, other):
        if self[1] != other[1] or self[2] != other[2]:
            raise TypeError("unsupported operand error for addition: %s and %s" % (self[1], other[1]))
        return ValueTuple(self[0] + other[0], self[1], self[2])

#==============================================================================
#                        class Formatter
#==============================================================================

class Formatter(object):
    """Holds formatting information for the various unit types.
    
    Examples (using the default formatters):
    >>> f = Formatter()
    >>> print f.toString((20.0, "degree_C", "group_temperature"))
    20.0°C
    >>> print f.toString((83.2, "degree_F", "group_temperature"))
    83.2°F
    >>> print f.toString((123456789,  "unix_epoch", "group_time"))
    29-Nov-1973 13:33
    >>> print f.to_ordinal_compass((5.0, "degree_compass", "group_direction"))
    N
    >>> print f.to_ordinal_compass((0.0, "degree_compass", "group_direction"))
    N
    >>> print f.to_ordinal_compass((12.5, "degree_compass", "group_direction"))
    NNE
    >>> print f.to_ordinal_compass((360.0, "degree_compass", "group_direction"))
    N
    >>> print f.to_ordinal_compass((None, "degree_compass", "group_direction"))
    N/A
    """

    def __init__(self, unit_format_dict = default_unit_format_dict,
                       unit_label_dict  = default_unit_label_dict,
                       time_format_dict = default_time_format_dict,
                       ordinate_names   = default_ordinate_names):
        """
        unit_format_dict: Key is unit type (eg, 'inHg'), value is a
        string format ("%.1f")
        
        unit_label_dict: Key is unit type (eg, 'inHg'), value is a
        label (" inHg")
        
        time_format_dict: Key is a context (eg, 'week'), value is a
        strftime format ("%d-%b-%Y %H:%M")."""

        self.unit_format_dict = unit_format_dict
        self.unit_label_dict  = unit_label_dict
        self.time_format_dict = time_format_dict
        self.ordinate_names    = ordinate_names
        # Add new keys for backwards compatibility on old skin dictionaries:
        self.time_format_dict.setdefault('ephem_day', "%H:%M")
        self.time_format_dict.setdefault('ephem_year', "%d-%b-%Y %H:%M")
        
    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        try:
            unit_format_dict = skin_dict['Units']['StringFormats']
        except KeyError:
            unit_format_dict = default_unit_format_dict

        try:
            unit_label_dict = skin_dict['Units']['Labels']
        except KeyError:
            unit_label_dict = default_unit_label_dict

        try:
            time_format_dict = skin_dict['Units']['TimeFormats']
        except KeyError:
            time_format_dict = default_time_format_dict

        try:
            ordinate_names = weeutil.weeutil.option_as_list(skin_dict['Units']['Ordinates']['directions'])
        except KeyError:
            ordinate_names = default_ordinate_names

        return Formatter(unit_format_dict,
                         unit_label_dict,
                         time_format_dict,
                         ordinate_names)

    def get_format_string(self, unit):
        """Return a suitable format string."""

        # First, try my internal format dict
        if self.unit_format_dict.has_key(unit):
            return self.unit_format_dict[unit]
        # If that didn't work, try the default dict:
        elif default_unit_format_dict.has_key(unit):
            return default_unit_format_dict[unit]
        else:
            # Can't find one. Return a generic formatter:
            return '%f'

    def get_label_string(self, unit):
        """Return a suitable label."""

        # First, try my internal label dictionary:
        if self.unit_label_dict.has_key(unit):
            return self.unit_label_dict[unit]
        # If that didn't work, try the default label dictionary:
        elif default_unit_label_dict.has_key(unit):
            return default_unit_label_dict[unit]
        else:
            # Can't find a label. Just return an empty string:
            return ''

    def toString(self, val_t, context='current', addLabel=True, useThisFormat=None, NONE_string=None):
        """Format the value as a string.
        
        val_t: The value to be formatted as a value tuple. 
        
        context: A time context (eg, 'day'). 
        [Optional. If not given, context 'current' will be used.]
        
        addLabel: True to add a unit label (eg, 'mbar'), False to not.
        [Optional. If not given, a label will be added.]
        
        useThisFormat: An optional string or strftime format to be used. 
        [Optional. If not given, the format given in the initializer will
        be used.]
        
        NONE_string: A string to be used if the value val is None.
        [Optional. If not given, the string given unit_format_dict['NONE']
        will be used.]
        """
        if val_t is None or val_t[0] is None:
            if NONE_string is not None: 
                return NONE_string
            else:
                return self.unit_format_dict.get('NONE', 'N/A')
            
        if val_t[1] == "unix_epoch":
            # Different formatting routines are used if the value is a time.
            try:
                if useThisFormat is not None:
                    val_str = time.strftime(useThisFormat, time.localtime(val_t[0]))
                else:
                    val_str = time.strftime(self.time_format_dict.get(context, "%d-%b-%Y %H:%M"), time.localtime(val_t[0]))
            except (KeyError, TypeError):
                # If all else fails, use this weeutil utility:
                val_str = weeutil.weeutil.timestamp_to_string(val_t[0])
        else:
            # It's not a time. It's a regular value. Get a suitable
            # format string:
            if useThisFormat is None:
                # No user-specified format string. Go get one:
                format_string = self.get_format_string(val_t[1])
            else:
                # User has specified a string. Use it.
                format_string = useThisFormat
            # Now use the format string to format the value:
            val_str = locale.format_string(format_string, val_t[0])

        # Add a label, if requested:
        if addLabel:
            val_str += self.get_label_string(val_t[1])

        return val_str

    def to_ordinal_compass(self, val_t):
        if val_t[0] is None:
            return self.ordinate_names[-1]
        _sector_size = 360.0 / (len(self.ordinate_names)-1)
        _degree = (val_t[0] + _sector_size/2.0) % 360.0
        _sector = int(_degree / _sector_size)
        return self.ordinate_names[_sector]
    
#==============================================================================
#                        class Converter
#==============================================================================

class Converter(object):
    """Holds everything necessary to do conversions to a target unit system."""
    
    def __init__(self, group_unit_dict=USUnits):
        """Initialize an instance of Converter
        
        group_unit_dict: A dictionary holding the conversion information. 
        Key is a unit_group (eg, 'group_pressure'), value is the target
        unit type ('mbar')"""

        self.group_unit_dict  = group_unit_dict
        
    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        try:
            group_unit_dict = skin_dict['Units']['Groups']
        except KeyError:
            group_unit_dict = USUnits
        return Converter(group_unit_dict)

    def convert(self, val_t):
        """Convert a value from a given unit type to the target type.
        
        val_t: A value tuple with the datum, a unit type, and a unit group
        
        returns: A value tuple in the new, target unit type. If the input
        value tuple contains an unknown unit type an exception of type KeyError
        will be thrown. If the input value tuple has either a unit
        type of None, or a group type of None (but not both), then an
        exception of type KeyError will be thrown. If both the
        unit and group are None, then the original val_t will be
        returned (i.e., no conversion is done).
        
        Examples:
        >>> p_m = (1016.5, 'mbar', 'group_pressure')
        >>> c = Converter()
        >>> print c.convert(p_m)
        (30.020673360897813, 'inHg', 'group_pressure')
        
        Try an unspecified unit type:
        >>> p2 = (1016.5, None, None)
        >>> print c.convert(p2)
        (1016.5, None, None)
        
        Try a bad unit type:
        >>> p3 = (1016.5, 'foo', 'group_pressure')
        >>> try:
        ...     print c.convert(p3)
        ... except KeyError:
        ...     print "Exception thrown"
        Exception thrown
        
        Try a bad group type:
        >>> p4 = (1016.5, 'mbar', 'group_foo')
        >>> try:
        ...     print c.convert(p4)
        ... except KeyError:
        ...     print "Exception thrown"
        Exception thrown
        """
        if val_t[1] is None and val_t[2] is None:
            return val_t
        # Determine which units (eg, "mbar") this group should be in.
        # If the user has not specified anything, then fall back to US Units.
        new_unit_type = self.group_unit_dict.get(val_t[2], USUnits[val_t[2]])
        # Now convert to this new unit type: 
        new_val_t = convert(val_t, new_unit_type)
        return new_val_t

    def convertDict(self, obs_dict):
        """Convert an observation dictionary into the target unit system.
        
        The source dictionary must include the key 'usUnits' in order for the
        converter to figure out what unit system it is in.
        
        The output dictionary will contain no information about the unit
        system (that is, it will not contain a 'usUnits' entry). This is
        because the conversion is general: it may not result in a standard
        unit system.
        
        Example: convert a dictionary which is in the metric unit system
        into US units
        
        >>> # Construct a default converter, which will be to US units
        >>> c = Converter()
        >>> # Source dictionary is in metric units
        >>> source_dict = {'dateTime': 194758100, 'outTemp': 20.0,\
            'usUnits': weewx.METRIC, 'barometer':1015.8, 'interval':15}
        >>> target_dict = c.convertDict(source_dict)
        >>> print target_dict
        {'outTemp': 68.0, 'interval': 15, 'barometer': 30.0, 'dateTime': 194758100}
        """
        # Wrap the source dictionary in a ValueTupleDict. This will cause
        # keyed values to be returned as ValueTuples:
        obs_vdt = ValueTupleDict(obs_dict)
        
        target_dict = {}
        for obs_type in obs_vdt:
            if obs_type == 'usUnits': continue
            # Do the conversion, but keep only the first value in
            # the ValueTuple:
            target_dict[obs_type] = self.convert(obs_vdt[obs_type])[0]
        return target_dict
            
    def getTargetUnit(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type, return the 
        target unit type and group, or (None, None) if they cannot be determined.
        
        obs_type: An observation type ('outTemp', 'rain', etc.)
        
        agg_type: Type of aggregation ('mintime', 'count', etc.)
        [Optional. default is no aggregation)
        
        returns: A 2-way tuple holding the unit type and the unit group
        or (None, None) if they cannot be determined.
        """        
        unit_group = _getUnitGroup(obs_type, agg_type)
        unit_type  = self.group_unit_dict.get(unit_group)
        return (unit_type, unit_group)

#==============================================================================
#                         Standard Converters
#==============================================================================

# This dictionary holds converters for the standard unit conversion systems. 
StdUnitConverters = {weewx.US       : Converter(USUnits),
                     weewx.METRIC   : Converter(MetricUnits),
                     weewx.METRICWX : Converter(MetricWXUnits)}

#==============================================================================
#                        class FixedConverter
#==============================================================================

class FixedConverter(object):
    """Dirt simple converter that can only convert to a specified unit."""
    def __init__(self, target_units):
        """Initialize an instance of FixedConverter
        
        target_units: The new, target unit (eg, "degree_C")"""
        self.target_units = target_units
        
    def convert(self, val_t):
        return convert(val_t, self.target_units)
    
#==============================================================================
#                      class ValueHelper
#==============================================================================

class ValueHelper(object):
    """A helper class that binds a value tuple together with everything needed to do a
    context sensitive formatting
    
    Example:
    
    >>> value_t = (68.01, "degree_F", "group_temperature")
    >>> # Use the default converter and formatter:
    >>> vh = ValueHelper(value_t)
    >>> print vh
    68.0°F
    
    Try explicit unit conversion:
    >>> print vh.degree_C
    20.0°C
    
    Do it again, but using a converter:
    >>> vh = ValueHelper(value_t, converter=Converter(MetricUnits))
    >>> print vh
    20.0°C
    
    Extract just the raw value:
    >>> print "%.1f" % vh.raw
    20.0
    """
    def __init__(self, value_t, context='current', formatter=Formatter(), converter=Converter()):
        """Initialize a ValueHelper.
        
        value_t: A value tuple holding the datum.
        
        context: The time context. Something like 'current', 'day', 'week'.
        [Optional. If not given, context 'current' will be used.]
        
        formatter: An instance of class Formatter.
        [Optional. If not given, then the default Formatter() will be used]
        
        converter: An instance of class Converter.
        [Optional. If not given, then the default Converter() will be used,
        which will convert to US units]
        """
        self.value_t   = value_t
        self.context   = context
        self.formatter = formatter
        self.converter = converter
            
    def toString(self, addLabel=True, useThisFormat=None, NONE_string=None):
        """Convert my internally held ValueTuple to a string, using the supplied
        converter and formatter."""
        # If the type is unknown, then just return an error string: 
        if isinstance(self.value_t, UnknownType):
            return "?'%s'?" % self.value_t.obs_type 
        # Get the value tuple in the target units:
        vtx = self._raw_value_tuple
        # Then do the format conversion:
        s = self.formatter.toString(vtx, self.context, addLabel=addLabel, useThisFormat=useThisFormat, NONE_string=NONE_string)
        return s
        
    def __str__(self):
        """Return as string"""
        return self.toString()
    
    def string(self, NONE_string=None):
        """Return as string with an optional user specified string to be
        used if None"""
        return self.toString(NONE_string=NONE_string)
    
    def format(self, format_string, NONE_string=None):
        """Returns a formatted version of the datum, using a user-supplied
        format."""
        return self.toString(useThisFormat=format_string, NONE_string=NONE_string)
    
    def nolabel(self, format_string, NONE_string=None):
        """Returns a formatted version of the datum, using a user-supplied
        format. No label."""
        return self.toString(addLabel=False, useThisFormat=format_string, NONE_string=NONE_string)
    
    def ordinal_compass(self):
        """Returns an ordinal compass direction (eg, 'NNW')"""
        # Get the raw value tuple, then ask the formatter to look up an
        # appropriate ordinate:
        return self.formatter.to_ordinal_compass(self._raw_value_tuple)
        
    @property
    def formatted(self):
        """Return a formatted version of the datum. No label."""
        return self.toString(addLabel=False)
        
    @property
    def raw(self):
        """Returns the raw value without any formatting."""
        return self._raw_value_tuple[0]

    @property    
    def _raw_value_tuple(self):
        """Return a value tuple in the target units."""
        # ... Do the unit conversion ...
        vtx = self.converter.convert(self.value_t)
        # ... and then return it
        return vtx

    def __getattr__(self, target_unit):
        """Convert to a new unit type.
        
        target_unit: The new target unit. 
        
        returns: A ValueHelper with a FixedConverter that converts to the
        specified units."""

        # If we are being asked to perform a conversion, make sure it's a
        # legal one:
        if self.value_t[1] != target_unit:        
            try:
                conversionDict[self.value_t[1]][target_unit]
            except KeyError:
                raise AttributeError, "Illegal conversion from '%s' to '%s'"%(self.value_t[1], target_unit)
        return ValueHelper(self.value_t, self.context, self.formatter, FixedConverter(target_unit))
    
    def exists(self):
        return not isinstance(self.value_t, UnknownType)
    
    def has_data(self):
        return self.exists() and self.value_t[0] is not None
    
#==============================================================================
#                            class ValueDict
#==============================================================================

class ValueDict(object):
    """A dictionary that returns values as ValueHelper.
    
    This dictionary holds a dictionary that returns ValueTuples.
    Then, when it is keyed, it wraps the returned ValueTuples in a 
    ValueHelper, which can then be used for context sensitive formatting. 
    
    Example:
    >>> vd = ValueDict({'outTemp'   : (20.3, 'degree_C', 'group_temperature'),\
                        'barometer' : (30.02 , 'inHg', 'group_pressure') })
    >>> print vd['outTemp']
    68.5°F
    
    Print barometric pressure, overriding the units to millibars:
    >>> print vd['barometer'].mbar
    1016.5 mbar
    """
    
    def __init__(self, d, context='current', formatter=Formatter(), converter=Converter()):
        """Initialize the ValueDict from a dictionary with keys of observation
        types, values of value tuples.
        
        d: A dictionary with keys of observation types, values a ValueTuple
        
        context: The time context of the dictionary. This will be passed on to
        the returned instance of ValueHelper. [Optional. If not given,
        'current' will be used]

        formatter: A unit formatter. This will be passed on to the returned
        DictBinder. [Optional. If not given, the default Formatter() will
        be passed on.]
        
        converter: A unit converter. This will be passed on to the returned
        DictBinder. [Optional. If not given, the default Converter() will
        be passed on.] 
        """
        self.dictionary= d
        self.context   = context
        self.formatter = formatter
        self.converter = converter
        
    def __getitem__(self, obs_type):
        """Look up an observation type (eg, 'outTemp') and return it as a ValueHelper.
        
        obs_type: The key.
        
        Returns: A ValueHelper, or an object of type UnknownType if the key does
        not appear in the dictionary.
        """
        vt = self.dictionary.get(obs_type, UnknownType(obs_type))
        return ValueHelper(vt, context=self.context, formatter=self.formatter,
                           converter=self.converter)

    def __getattr__(self, obs_type):
        """Look up an observation type (eg, 'outTemp') and return it as a ValueHelper.
        
        obs_type: An attribute
        
        Returns: A ValueHelper, or an object of type UnknownType if the key does
        not appear in the dictionary.
        """
        # The following is so the Python version of Cheetah's NameMapper does not
        # think I'm a functor or real dictionary.
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError(obs_type)
        vt = self.dictionary.get(obs_type, UnknownType(obs_type))
        return ValueHelper(vt, context=self.context, formatter=self.formatter,
                           converter=self.converter)
    
#==============================================================================
#                             class ValueTupleDict
#==============================================================================

class ValueTupleDict(dict):
    """A dictionary like any other dictionary, except that when keyed, it
    returns its results as a ValueTuple. It is useful to be fed into
    ValudDict above.
    
    Example:
    >>> vtd = ValueTupleDict({'usUnits' : 1, 'outTemp' : 68.0})
    >>> print vtd['outTemp']
    (68.0, 'degree_F', 'group_temperature')
    >>> print vtd.get('outTemp')
    (68.0, 'degree_F', 'group_temperature')
    >>> print vtd.get('foo', 100.0)
    100.0
    """
    def __getitem__(self, key):

        # Get the standard unit system from the underlying dictionary:
        std_unit_system = dict.__getitem__(self, 'usUnits')
        # Get the unadorned value from the underlying dictionary:
        val = dict.__getitem__(self, key)
        
        # Given this standard unit system, what is the unit type of this
        # particular observation type?
        (unit_type, unit_group) = StdUnitConverters[std_unit_system].getTargetUnit(key)
        # Form the value-tuple and return it 
        return ValueTuple(val, unit_type, unit_group)
    
    def get(self, key, default=None):
        if self.has_key(key):
            return self[key]
        else:
            return default
    
#==============================================================================
#                             class UnitInfoHelper
#==============================================================================

class UnitInfoHelper(object):
    """Helper class used for for the $unit template tag."""
    def __init__(self, formatter, converter):
        """
        formatter: an instance of Formatter
        converter: an instance of Converter
        """
        self.group_unit_dict = converter.group_unit_dict
        self.unit_type = {}
        self.label     = {}
        self.format    = {}
        for obs_type in obs_group_dict:
            self.unit_type[obs_type] = u = converter.getTargetUnit(obs_type)[0]
            self.format[obs_type] = formatter.get_format_string(u)
            self.label[obs_type]  = formatter.get_label_string(u)
    
    # This is here for backwards compatibility:
    @property
    def unit_type_dict(self):
        return self.group_unit_dict
    
#==============================================================================
#                             Helper functions
#==============================================================================
def _getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group
    does it belong to?

        Examples:
             obs_type  agg_type          Returns
             ________  ________         _________
            'outTemp',  None      -->  'group_temperature'
            'outTemp', 'min'      -->  'group_temperature'
            'outTemp', 'mintime'  -->  'group_time'
            'wind',    'avg'      -->  'group_speed'
            'wind',    'vecdir'   -->  'group_direction'
        
        obs_type: An observation type. E.g., 'barometer'.
        
        agg_type: An aggregation type E.g., 'mintime', or 'avg'.
        
        Returns: the unit group or None if it cannot be determined."""
    if agg_type and agg_type in agg_group:
        return agg_group[agg_type]
    else:
        return obs_group_dict.get(obs_type)
    
def convert(val_t, target_unit_type):
    """ Convert a value or a sequence of values between unit systems

    val_t: A value-tuple with the value to be converted. The first
    element is the value (either a scalar or iterable), the second element 
    the unit type (e.g., "foot", or "inHg") it is in.
    
    target_unit_type: The unit type (e.g., "meter", or "mbar") to
    which the value is to be converted. 
    
    returns: An instance of weewx.ValueTuple, converted into the desired units.
    """
    # If the value is already in the target unit type, then just return it:
    if val_t[1] == target_unit_type:
        return val_t

    # Retrieve the conversion function. An exception of type KeyError
    # will occur if the target or source units are invalid
    try:
        conversion_func = conversionDict[val_t[1]][target_unit_type]
    except KeyError:
        if weewx.debug:
            syslog.syslog(syslog.LOG_DEBUG, "units: Unable to convert from %s to %s" %(val_t[1], target_unit_type))
        raise
    # Try converting a sequence first. A TypeError exception will occur if
    # the value is actually a scalar:
    try:
        new_val = map(lambda x : conversion_func(x) if x is not None else None, val_t[0])
    except TypeError:
        new_val = conversion_func(val_t[0]) if val_t[0] is not None else None
    # Add on the unit type and the group type and return the results:
    return ValueTuple(new_val, target_unit_type, val_t[2])

def convertStd(val_t, target_std_unit_system):
    """Convert a value tuple to an appropriate unit in a target standardized
    unit system
    
    val_t: A value tuple.
    
    target_std_unit_system: A standardized unit system
                            (weewx.US, weewx.METRIC, or weewx.METRICWX)
    
    Returns: A value tuple in the given standardized unit system.
    
    Example:
    >>> value_t = (30.02, 'inHg', 'group_pressure')
    >>> print "(%.2f, %s, %s)" % convertStd(value_t, weewx.METRIC)
    (1016.48, mbar, group_pressure)
    >>> value_t = (1.2, 'inch', 'group_rain')
    >>> print "(%.2f, %s, %s)" % convertStd(value_t, weewx.METRICWX)
    (30.48, mm, group_rain)
    """
    return StdUnitConverters[target_std_unit_system].convert(val_t)

def getStandardUnitType(target_std_unit_system, obs_type, agg_type=None):
    """Given a standard unit system (weewx.US, weewx.METRIC, weewx.METRICWX),
    an observation type, and an aggregation type, what units would it be in?
    
    target_std_unit_system: A standardized unit system. If None, then
    the the output units are indeterminate, so (None, None) is returned. 
    
    obs_type: An observation type.
        
    agg_type: An aggregation type E.g., 'mintime', or 'avg'.
    
    returns: A 2-way tuple containing the target units, and the target group.

    Examples:
    >>> print getStandardUnitType(weewx.US,     'barometer')
    ('inHg', 'group_pressure')
    >>> print getStandardUnitType(weewx.METRIC, 'barometer')
    ('mbar', 'group_pressure')
    >>> print getStandardUnitType(weewx.US, 'barometer', 'mintime')
    ('unix_epoch', 'group_time')
    >>> print getStandardUnitType(weewx.METRIC, 'barometer', 'avg')
    ('mbar', 'group_pressure')
    >>> print getStandardUnitType(weewx.METRIC, 'wind', 'rms')
    ('km_per_hour', 'group_speed')
    >>> print getStandardUnitType(None, 'barometer', 'avg')
    (None, None)
    """
    
    if target_std_unit_system is not None:
        return StdUnitConverters[target_std_unit_system].getTargetUnit(obs_type, agg_type)
    else:
        return (None, None)

class GenWithConvert(object):
    """Generator wrapper. Converts the output of the wrapped generator to a
    target unit system.
    
    Example:
    >>> def genfunc():
    ...    for i in range(3):
    ...        _rec = {'dateTime' : 194758100 + i*300,
    ...            'outTemp' : 68.0 + i * 9.0/5.0,
    ...            'usUnits' : weewx.US}
    ...        yield _rec
    >>> for _out in GenWithConvert(genfunc(), weewx.METRIC):
    ...    print "Timestamp: %d; Temperature: %.2f; Unit system: %d" % (_out['dateTime'], _out['outTemp'], _out['usUnits'])
    Timestamp: 194758100; Temperature: 20.00; Unit system: 16
    Timestamp: 194758400; Temperature: 21.00; Unit system: 16
    Timestamp: 194758700; Temperature: 22.00; Unit system: 16
    """
    
    def __init__(self, input_generator, target_unit_system=weewx.METRIC):
        """Initialize an instance of GenWithConvert
        
        input_generator: An iterator which will return dictionary records.
        
        target_unit_system: The unit system the output of the generator should
        use, or 'None' if it should leave the output unchanged."""
        self.input_generator = input_generator
        self.target_unit_system = target_unit_system
        
    def __iter__(self):
        return self
    
    def next(self): 
        _record = self.input_generator.next()
        if self.target_unit_system is None or _record['usUnits'] == self.target_unit_system:
            return _record
        _record_c = StdUnitConverters[self.target_unit_system].convertDict(_record)
        _record_c['usUnits'] = self.target_unit_system
        return _record_c


def getAltitude(config_dict, units):
    """Get altitude, in specified units, from the Station section of dict."""
    altitude_t = weeutil.weeutil.option_as_list(
        config_dict['Station'].get('altitude', (None, None)))
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    altitude = convert(altitude_vt, units)[0]
    return altitude

def getAltitudeM(config_dict):
    return getAltitude(config_dict, 'meter')

def getAltitudeFt(config_dict):
    return getAltitude(config_dict, 'foot')

def to_US(datadict):
    """Convert the units used in a dictionary to US Customary."""
    return to_std_system(datadict, weewx.US)

def to_METRIC(datadict):
    """Convert the units used in a dictionary to Metric."""
    return to_std_system(datadict, weewx.METRIC)

def to_METRICWX(datadict):
    """Convert the units used in a dictionary to MetricWX."""
    return to_std_system(datadict, weewx.METRICWX)

def to_std_system(datadict, unit_system):
    """Convert the units used in a dictionary to a target unit system."""
    if datadict['usUnits'] == unit_system:
        # It's already in the unit system.
        return datadict
    else:
        # It's in something else. Perform the conversion
        _datadict_target = StdUnitConverters[unit_system].convertDict(datadict)
        # Add the new unit system
        _datadict_target['usUnits'] = unit_system
        return _datadict_target

    
if __name__ == "__main__":
    
    import doctest

    if not doctest.testmod().failed:
        print "PASSED"
