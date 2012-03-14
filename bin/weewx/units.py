# -*- coding: utf-8 -*-
#
#    Copyright (c) 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Data structures and functions for dealing with units."""

import time
import syslog

import weewx
import weeutil.weeutil

# This data structure maps observation types to a "unit group"
obs_group_dict = {"barometer"          : "group_pressure",
                  "pressure"           : "group_pressure",
                  "altimeter"          : "group_pressure",
                  "inTemp"             : "group_temperature",
                  "outTemp"            : "group_temperature",
                  "inHumidity"         : "group_percent",
                  "outHumidity"        : "group_percent",
                  "windSpeed"          : "group_speed",
                  "windDir"            : "group_direction",
                  "windGust"           : "group_speed",
                  "windGustDir"        : "group_direction",
                  "windvec"            : "group_speed",
                  "windgustvec"        : "group_speed",
                  "wind"               : "group_speed",
                  "vecdir"             : "group_direction",
                  "vecavg"             : "group_speed2",
                  "rms"                : "group_speed2",
                  "gustdir"            : "group_direction",
                  "rainRate"           : "group_rainrate",
                  "rain"               : "group_rain",
                  "dewpoint"           : "group_temperature",
                  "windchill"          : "group_temperature",
                  "heatindex"          : "group_temperature",
                  "ET"                 : "group_rain",
                  "radiation"          : "group_radiation",
                  "UV"                 : "group_uv",
                  "extraTemp1"         : "group_temperature",
                  "extraTemp2"         : "group_temperature",
                  "extraTemp3"         : "group_temperature",
                  "soilTemp1"          : "group_temperature",
                  "soilTemp2"          : "group_temperature",
                  "soilTemp3"          : "group_temperature",
                  "soilTemp4"          : "group_temperature",
                  "leafTemp1"          : "group_temperature",
                  "leafTemp2"          : "group_temperature",
                  "extraHumid1"        : "group_percent",
                  "extraHumid2"        : "group_percent",
                  "soilMoist1"         : "group_moisture",
                  "soilMoist2"         : "group_moisture",
                  "soilMoist3"         : "group_moisture",
                  "soilMoist4"         : "group_moisture",
                  "rxCheckPercent"     : "group_percent",
                  "consBatteryVoltage" : "group_volt",
                  "hail"               : "group_rain",
                  "hailRate"           : "group_rainrate",
                  "heatingTemp"        : "group_temperature",
                  "heatingVoltage"     : "group_volt",
                  "supplyVoltage"      : "group_volt",
                  "referenceVoltage"   : "group_volt",
                  "altitude"           : "group_altitude",
                  "heatdeg"            : "group_degree_day",
                  "cooldeg"            : "group_degree_day",
                  "dateTime"           : "group_time",
                  "interval"           : "group_interval"}

# Some aggregations when applied to a type result in a different unit
# group. This data structure maps aggregation type to the group:
agg_group = {'mintime'    : "group_time",
             'maxtime'    : "group_time",
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

# Conversion functions to go from one unit type to another.
conversionDict = {
      'inHg'             : {'mbar'             : lambda x : x * 33.86, 
                            'hPa'              : lambda x : x * 33.86},
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
      'mbar'             : {'inHg'             : lambda x : x / 33.86,
                            'hPa'              : lambda x : x * 1.0},
      'hPa'              : {'inHg'             : lambda x : x / 33.86,
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
      'unix_epoch'       : {'dublin_jd'        : lambda x : x/86400.0 + 25567.5}}


# This will extract all the target unit types in the above dictionary:
allPossibleUnitTypes = set(z for d in conversionDict.values() for z in d.keys())

# Default unit formatting to be used in the absence of a skin configuration file
default_unit_format_dict = {"centibar"           : "%.0f",
                            "cm"                 : "%.2f",
                            "cm_per_hour"        : "%.2f",
                            "degree_C"           : "%.1f",
                            "degree_C_day"       : "%.1f",
                            "degree_compass"     : "%.0f",
                            "degree_F"           : "%.1f",
                            "degree_F_day"       : "%.1f",
                            "foot"               : "%.0f",
                            "hPa"                : "%.1f",
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
                            "mm_per_hour"        : "%.1f",
                            "percent"            : "%.0f",
                            "uv_index"           : "%.1f",
                            "volt"               : "%.1f",
                            "watt_per_meter_squared" : "%.0f",
                            "NONE"              : "   N/A"}

# Default unit labels to be used in the absence of a skin configuration file
default_unit_label_dict = { "centibar"          : " cb",
                            "cm"                : " cm",
                            "cm_per_hour"       : " cm/hr",
                            "degree_C"          : "\xc2\xb0C",
                            "degree_C_day"      : "\xc2\xb0C-day",
                            "degree_compass"    : "\xc2\xb0",
                            "degree_F"          : "\xc2\xb0F",
                            "degree_F_day"      : "\xc2\xb0F-day",
                            "foot"              : " feet",
                            "hPa"               : " hPa",
                            "inHg"              : " inHg",
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
                            "mm_per_hour"       : " mm/hr",
                            "percent"           : "%",
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


#===============================================================================
#                        class ValueTuple
#===============================================================================

# A value, along with the unit it is in, can be represented by a 3-way tuple
# called a value tuple. All weewx routines can accept a simple unadorned
# 3-way tuple as a value tuple, but they return the type ValueTuple. It is
# useful because its contents can be accessed using named attributes.
#
# Item   attribute   Meaning
#    0    value      The data value (eg, 20.2)
#    1    unit       The unit it is in ("degree_C")
#    2    group      The unit group ("group_temperature")
#
# It is valid to have a data value of None.
#
# It is also valid to have a unit type of None (meaning there is no information about
# the unit the value is in). In this case, you won't be able to convert it to another
# unit.
#
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


#===============================================================================
#                        class Formatter
#===============================================================================
    
class Formatter(object):
    """Holds formatting information for the various unit types."""

    def __init__(self, unit_format_dict = default_unit_format_dict,
                       unit_label_dict  = default_unit_label_dict,
                       time_format_dict = default_time_format_dict):
        """
        unit_format_dict: Key is unit type (eg, 'inHg'), value is a string format ("%.1f")
        
        unit_label_dict: Key is unit type (eg, 'inHg'), value is a label (" inHg")
        
        time_format_dict: Key is a context (eg, 'week'), value is a strftime format ("%d-%b-%Y %H:%M")."""

        self.unit_format_dict = unit_format_dict
        self.unit_label_dict  = unit_label_dict
        self.time_format_dict = time_format_dict
        # Add new keys for backwards compatibility on old skin dictionaries:
        self.time_format_dict.setdefault('ephem_day', "%H:%M")
        self.time_format_dict.setdefault('ephem_year', "%d-%b-%Y %H:%M")
        
    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        return Formatter(skin_dict['Units']['StringFormats'],
                         skin_dict['Units']['Labels'],
                         skin_dict['Units']['TimeFormats'])

    def toString(self, val_t, context='current', addLabel=True, useThisFormat=None, NONE_string=None):
        """Format the value as a string.
        
        val_t: The value to be formatted as a value tuple. 
        
        context: A time context (eg, 'day'). 
        [Optional. If not given, context 'current' will be used.]
        
        addLabel: True to add a unit label (eg, 'mbar'), False to not.
        [Optional. If not given, a label will be added.]
        
        useThisFormat: An optional string or strftime format to be used. 
        [Optional. If not given, the format given in the initializer will be used.]
        
        NONE_string: A string to be used if the value val is None.
        [Optional. If not given, the string given unit_format_dict['NONE'] will be used.]
        """
        if val_t is None or val_t[0] is None:
            if NONE_string: 
                return NONE_string
            else:
                return self.unit_format_dict.get('NONE', 'N/A')
            
        if val_t[1] == "unix_epoch":
            # Different formatting routines are used if the value is a time.
            try:
                if useThisFormat:
                    val_str = time.strftime(useThisFormat, time.localtime(val_t[0]))
                else:
                    val_str = time.strftime(self.time_format_dict.get(context, "%d-%b-%Y %H:%M"), time.localtime(val_t[0]))
            except (KeyError, TypeError):
                # If all else fails, use this weeutil utility:
                val_str = weeutil.weeutil.timestamp_to_string(val_t[0])
        else:
            # It's not a time. It's a regular value.
            try:
                if useThisFormat:
                    val_str = useThisFormat % val_t[0]
                else:
                    val_str = self.unit_format_dict[val_t[1]] % val_t[0]
            except (KeyError, TypeError):
                # If all else fails, ask Python to convert to a string:
                val_str = str(val_t[0])

        if addLabel:
            val_str += self.unit_label_dict.get(val_t[1],'')

        return val_str

#===============================================================================
#                        class Converter
#===============================================================================

class Converter(object):
    """Holds everything necessary to do conversions to a target unit system."""
    
    def __init__(self, group_unit_dict=USUnits):
        """Initialize an instance of Converter
        
        group_unit_dict: A dictionary holding the conversion information. 
        Key is a unit_group (eg, 'group_pressure'), value is the target unit type ('mbar')"""

        self.group_unit_dict  = group_unit_dict
        
    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        return Converter(skin_dict['Units']['Groups'])

    def convert(self, val_t):
        """Convert a value from a given unit type to the target type.
        
        val_t: A value tuple with the data, a unit type, and a unit group
        
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
    
#===============================================================================
#                         Standard Converters
#===============================================================================

# This dictionary holds converters for the standard unit conversion systems. 
StdUnitConverters = {weewx.US     : Converter(USUnits),
                     weewx.METRIC : Converter(MetricUnits)}

#===============================================================================
#                        class FixedConverter
#===============================================================================

class FixedConverter(object):
    """Dirt simple converter that can only convert to a specified unit."""
    def __init__(self, target_units):
        """Initialize an instance of FixedConverter
        
        target_units: The new, target unit (eg, "degree_C")"""
        self.target_units = target_units
        
    def convert(self, val_t):
        return convert(val_t, self.target_units)
    
#===============================================================================
#                      class ValueOutputter
#===============================================================================

class ValueOutputter(object):
    """Abstract base class used to convert value tuples to a string, honoring
    unit conversion and formatting along the way. Derived classes must
    supply a method "getTuple()", which returns the value tuple to be turned
    into a string."""
    def __init__(self, context, formatter, converter):
        self.context   = context
        self.formatter = formatter
        self.converter = converter
            
    def toString(self, addLabel=True, useThisFormat=None, NONE_string=None):
        # Get the value tuple from my superclass:
        vt = self.getValueTuple()
        # Do the unit conversion:
        vtx = self.converter.convert(vt)
        # Then the format conversion:
        s = self.formatter.toString(vtx, self.context, addLabel=addLabel, useThisFormat=useThisFormat, NONE_string=NONE_string)
        return s
        
    def __str__(self):
        """Return as string"""
        return self.toString()
    
    def string(self, NONE_string=None):
        """Return as string with an optional user specified string to be used if None"""
        return self.toString(NONE_string=NONE_string)
    
    def format(self, format_string, NONE_string=None):
        """Returns a formatted version of the data, using a user-supplied format."""
        return self.toString(useThisFormat=format_string, NONE_string=NONE_string)
    
    def nolabel(self, format_string, NONE_string=None):
        """Returns a formatted version of the data, using a user-supplied format. No label."""
        return self.toString(addLabel=False, useThisFormat=format_string, NONE_string=NONE_string)
        
    @property
    def formatted(self):
        """Return a formatted version of the data. No label."""
        return self.toString(addLabel=False)
        
    @property
    def raw(self):
        """Returns the raw value without any formatting."""
        vt = self.getValueTuple()
        vtx=self.converter.convert(vt)
        return vtx[0]
    
#===============================================================================
#                        class ValueHelper
#===============================================================================
    
class ValueHelper(ValueOutputter):
    """A helper class that binds a value tuple together with everything needed to do a
    context sensitive formatting
    
    Example:
    
    >>> value_t = (68.01, "degree_F", "group_temperature")
    >>> # Use the default converter and formatter:
    >>> vh = ValueHelper(value_t)
    >>> print vh
    68.0°F
    
    Do it again, but using an explicit converter:
    
    >>> vh = ValueHelper(value_t, converter=Converter(MetricUnits))
    >>> print vh
    20.0°C
    """
    
    def __init__(self, value_t, context='current', formatter=Formatter(), converter=Converter()):
        """Initialize a ValueHelper.
        
        value_t: A value tuple holding the data.
        
        context: The time context. Something like 'current', 'day', 'week', etc.
        [Optional. If not given, context 'current' will be used.]
        
        formatter: An instance of class Formatter. [Optional. If not given, then
        the default Formatter() will be used]
        
        converter: An instance of class Converter. [Optional. If not given, then
        the default Converter() will be used, which will convert to US units]
        """
        self.value_t = value_t
        ValueOutputter.__init__(self, context, formatter, converter)

    # Supply getValueTuple:
    def getValueTuple(self):
        return self.value_t
    
    def __getattr__(self, target_unit):
        """Convert to a new unit type.
        
        target_unit: The new target unit. 
        
        returns: A ValueHelper with a FixedConverter that converts to the specified units."""
        
        # See if this is a valid unit type. If not, throw an AttributeError exception:
        if target_unit not in allPossibleUnitTypes:
            raise AttributeError, "Unit type \"%s\" unknown."%(target_unit,)
        return ValueHelper(self.value_t, self.context, self.formatter, FixedConverter(target_unit))
    
#===============================================================================
#                            class ValueDict
#===============================================================================

class ValueDict(dict):
    """A dictionary that returns contents as a DictBinder.
    
    This dictionary is like any other dictionary except, when keyed, it returns a
    DictBinder object that wraps around the returned value. It can then
    be used for context sensitive formatting. 
    
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
        # Initialize my superclass, the dictionary:
        super(ValueDict, self).__init__(d)
        self.context   = context
        self.formatter = formatter
        self.converter = converter
        
    def __getitem__(self, obs_type):
        """Look up an observation type (eg, 'outTemp') and return it as a DictBinder."""
        return DictBinder(obs_type, self, context=self.context, 
                          formatter=self.formatter, converter=self.converter)
    

class DictBinder(ValueOutputter):
    
    def __init__(self, obs_type, valuedict, context, formatter, converter):
        self.obs_type  = obs_type
        self.valuedict = valuedict
        self.context   = context
        self.formatter = formatter
        self.converter = converter
        
    def getValueTuple(self):
        # Get the value tuple from the underlying dictionary:
        vt = dict.__getitem__(self.valuedict, self.obs_type)
        return vt

    def __getattr__(self, target_unit):
        """Convert to a new unit type.
        
        target_unit: The new target unit. 
        
        returns: A DictBinder with a FixedConverter that converts to the specified units."""

        # See if this is a valid unit type. If not, throw an AttributeError exception:
        if target_unit not in allPossibleUnitTypes:
            raise AttributeError, "Unit type %s unknown."%(target_unit,)
        return DictBinder(self.obs_type, self.valuedict, self.context, self.formatter, FixedConverter(target_unit))
    
    @property
    def exists(self):
        return self.valuedict.has_key(self.obs_type)
    
    @property
    def has_data(self):
        return self.exists and self.getValueTuple()[0] is not None
    
#===============================================================================
#                             class UnitInfoHelper
#===============================================================================

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
            self.label[obs_type]  = formatter.unit_label_dict.get(u, '')
            self.format[obs_type] = formatter.unit_format_dict.get(u, '%s')
    
    # This is here for backwards compatibility:
    @property
    def unit_type_dict(self):
        return self.group_unit_dict
    
#===============================================================================
#                             Helper functions
#===============================================================================
def _getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?

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
    
        Example: convertStd((30.02, 'inHg', 'barometer'), weewx.METRIC)
        returns: (1016.5 'mbar', 'barometer')
    
    val_t: A value tuple. Example: (30.02, 'inHg', 'barometer')
    
    target_std_unit_system: A standardized unit system. 
    Example: weewx.US or weewx.METRIC.
    
    Returns: A value tuple in the given standardized unit system.
    """
    return StdUnitConverters[target_std_unit_system].convert(val_t)

def getStandardUnitType(target_std_unit_system, obs_type, agg_type=None):
    """Given a standard unit system (weewx.US or weewx.METRIC), an observation type, and
    an aggregation type, what is the unit system it uses?

    target_std_unit_system: A standardized unit system. 
    Example: weewx.US or weewx.METRIC.
    
    obs_type: An observation type. E.g., 'barometer'.
        
    agg_type: An aggregation type E.g., 'mintime', or 'avg'.
    
    returns: A 2-way tuple containing the target units, and the target group.
    """
    
    return StdUnitConverters[target_std_unit_system].getTargetUnit(obs_type, agg_type)

def dictFromStd(d):
    """Map an observation dictionary to a dictionary with values of ValueTuples.
    
    d: A dictionary containing the key-value pairs for observation types
    and their values. It must include an entry 'usUnits', giving the
    standard unit system the entries are in. An example would be:
    
        {'outTemp'   : 23.9,
         'barometer' : 1002.3,
         'usUnits'   : 2}

    In this case, the standard unit system being used is "2", or Metric.
    
    returns: a dictionary with keys of observation type, value the
    corresponding ValueTuple. Example:
        {'outTemp' : (23.9, 'degree_C', 'group_temperature'),
         'barometer' : (1002.3, 'mbar', 'group_pressure')}
    """
        
    # Find out what standard unit system (US or Metric) the dictionary is in:
    std_unit_system = d['usUnits']
    resultDict = {}
    for obs_type in d:
        # Given this standard unit system, what is the unit type of this
        # particular observation type?
        (unit_type, unit_group) = StdUnitConverters[std_unit_system].getTargetUnit(obs_type)
        # Form the value-tuple. 
        resultDict[obs_type] = ValueTuple(d[obs_type], unit_type, unit_group)
    return resultDict

    
if __name__ == "__main__":
    import doctest

    if not doctest.testmod().failed:
        print "PASSED"
