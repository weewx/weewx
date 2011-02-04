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
USUnits       = {"group_altitude"     : "foot",
                 "group_count"        : "count",
                 "group_degree_day"   : "degree_F_day",
                 "group_direction"    : "degree_compass",
                 "group_interval"     : "minute",
                 "group_moisture"     : "centibar",
                 "group_percent"      : "percent",
                 "group_pressure"     : "inHg",
                 "group_radiation"    : "watt_per_meter_squared",
                 "group_rain"         : "inch",
                 "group_rainrate"     : "inch_per_hour",
                 "group_speed"        : "mile_per_hour",
                 "group_speed2"       : "mile_per_hour2",
                 "group_temperature"  : "degree_F",
                 "group_time"         : "unix_epoch",
                 "group_uv"           : "uv_index",
                 "group_volt"         : "volt"}

# This dictionary maps unit groups to a standard unit type in the 
# metric unit system:
MetricUnits   = {"group_altitude"     : "meter",
                 "group_count"        : "count",
                 "group_degree_day"   : "degree_C_day",
                 "group_direction"    : "degree_compass",
                 "group_interval"     : "minute",
                 "group_moisture"     : "centibar",
                 "group_percent"      : "percent",
                 "group_pressure"     : "mbar",
                 "group_radiation"    : "watt_per_meter_squared",
                 "group_rain"         : "cm",
                 "group_rainrate"     : "cm_per_hour",
                 "group_speed"        : "km_per_hour",
                 "group_speed2"       : "km_per_hour2",
                 "group_temperature"  : "degree_C",
                 "group_time"         : "unix_epoch",
                 "group_uv"           : "uv_index",
                 "group_volt"         : "volt"}

# This dictionary maps the integer codes used in the databases to the
# appropriate unit system dictionary:
StdUnitSystem     = {weewx.US     : USUnits,
                     weewx.METRIC : MetricUnits}

# Conversion functions to go from one unit type to another.
conversionDict = {
      'inHg'             : {'mbar' : lambda x : 33.86 * x if x is not None else None, 
                            'hPa'  : lambda x : 33.86 * x if x is not None else None},
      'degree_F'         : {'degree_C'   : lambda x : (5.0/9.0) * (x - 32.0) if x is not None else None},
      'degree_F_day'     : {'degree_C_day'      : lambda x : (5.0/9.0)   * x if x is not None else None},
      'mile_per_hour'    : {'km_per_hour'       : lambda x : 1.609344    * x if x is not None else None,
                            'knot'              : lambda x : 0.868976242 * x if x is not None else None,
                            'meter_per_second'  : lambda x : 0.44704     * x if x is not None else None},
      'mile_per_hour2'   : {'km_per_hour2'      : lambda x : 1.609344    * x if x is not None else None,
                            'knot2'             : lambda x : 0.868976242 * x if x is not None else None,
                            'meter_per_second2' : lambda x : 0.44704     * x if x is not None else None},
      'inch_per_hour'    : {'cm_per_hour'       : lambda x : 2.54   * x if x is not None else None,
                            'mm_per_hour'       : lambda x : 25.4   * x if x is not None else None},
      'inch'             : {'cm'                : lambda x : 2.54   * x if x is not None else None,
                            'mm'                : lambda x : 25.4   * x if x is not None else None},
      'foot'             : {'meter'             : lambda x : 0.3048 * x if x is not None else None},
      
      'mbar'             : {'inHg'            : lambda x : 0.0295333727 * x if x is not None else None,
                            'hPa'             : lambda x : 1.0 * x          if x is not None else None},
      'hPa'              : {'inHg'            : lambda x : 0.0295333727 * x if x is not None else None,
                            'mbar'            : lambda x : 1.0 * x          if x is not None else None},
      'degree_C'         : {'degree_F'        : lambda x : (9.0/5.0 * x + 32.0) if x is not None else None},
      'degree_C_day'     : {'degree_F_day'    : lambda x : (9.0/5.0 * x)   if x is not None else None},
      'km_per_hour'      : {'mile_per_hour'   : lambda x : 0.621371192* x if x is not None else None,
                            'knot'            : lambda x : 0.539956803* x if x is not None else None,
                            'meter_per_second': lambda x : 0.277777778* x if x is not None else None},
      'meter_per_second' : {'mile_per_hour'   : lambda x : 2.23693629 * x if x is not None else None,
                            'knot'            : lambda x : 1.94384449 * x if x is not None else None,
                            'km_per_hour'     : lambda x : 3.6        * x if x is not None else None},
      'meter_per_second2': {'mile_per_hour2'  : lambda x : 2.23693629 * x if x is not None else None,
                            'knot2'           : lambda x : 1.94384449 * x if x is not None else None,
                            'km_per_hour2'    : lambda x : 3.6        * x if x is not None else None},
      'cm_per_hour'      : {'inch_per_hour'   : lambda x : 0.393700787* x if x is not None else None,
                            'mm_per_hour'     : lambda x : 10.0       * x if x is not None else None},
      'mm_per_hour'      : {'inch_per_hour'   : lambda x : .0393700787* x if x is not None else None,
                            'cm_per_hour'     : lambda x : 0.10       * x if x is not None else None},
      'cm'               : {'inch'            : lambda x : 0.393700787* x if x is not None else None,
                            'mm'              : lambda x : 10.0       * x if x is not None else None},
      'mm'               : {'inch'            : lambda x : .0393700787* x if x is not None else None,
                            'cm'              : lambda x : 0.10       * x if x is not None else None},
      'meter'            : {'foot'            : lambda x : 3.2808399  * x if x is not None else None} }


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
default_time_format_dict = {"day"      : "%H:%M",
                            "week"     : "%H:%M on %A",
                            "month"    : "%d-%b-%Y %H:%M",
                            "year"     : "%d-%b-%Y %H:%M",
                            "rainyear" : "%d-%b-%Y %H:%M",
                            "current"  : "%d-%b-%Y %H:%M"}


#===============================================================================
#                            class UnitConversion
#===============================================================================

class UnitConversion(object):
    """Converts units to a target unit."""

    def __init__(self, group_unit_dict=USUnits):
        """Initialize an instance of UnitConversion.
        
        group_unit_dict: Key is a unit_group (eg, 'group_pressure'), value is the target unit type ('mbar')
        """
        self.group_unit_dict  = group_unit_dict
        
    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""

        return UnitConversion(skin_dict['Units']['Groups'])

    def convert(self, val_t):
        """Convert a value from a given unit type to the target type.
        
        val_t: A value tuple with the data, a unit type, and an observation type 
        Example: (30.02, 'inHg', 'barometer')
        
        returns: A value tuple in the new, target unit type 
        Example: (1016.5, 'mbar', 'barometer') or None if the conversion cannot be performed."""
        if weewx.debug:
            if val_t[1] is None or val_t[2] is None:
                syslog.syslog(syslog.LOG_DEBUG, "units: None encountered in value tuple "+str(val_t))
        # Get which group (eg, "group_pressure") this observation type is in:
        unit_group= obs_group_dict[val_t[2]]
        # Determine which units (eg, "mbar") this group should be in:
        new_unit_type = self.group_unit_dict[unit_group]
        # Now convert to this new unit type: 
        new_val_t = convert(val_t, new_unit_type)
        return new_val_t
        

#===============================================================================
#                            class Formatter
#===============================================================================

class Formatter(object):
    """Holds unit formatting and label information."""

    def __init__(self, unit_format_dict = default_unit_format_dict,  
                       unit_label_dict  = default_unit_label_dict,
                       time_format_dict = default_time_format_dict):
        """
        unit_format_dict: Key is unit type (eg, 'inHg'), value is a string format ("%.1f")
        
        unit_label_dict: Key is unit type (eg, 'inHg'), value is a label (" inHg")
        
        time_format_dict: Key is a context (eg, 'week'), value is a strftime format ("%d-%b-%Y %H:%M").
        """
        self.unit_format_dict = unit_format_dict
        self.unit_label_dict  = unit_label_dict
        self.time_format_dict = time_format_dict

    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        return Formatter(skin_dict['Units']['StringFormats'],
                         skin_dict['Units']['Labels'],
                         skin_dict['Units']['TimeFormats'])
    
    def toString(self, val_t, context='current', addLabel=True, 
                 useThisFormat=None, NONE_string=None):
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
                    val_str = time.strftime(self.time_format_dict[context], time.localtime(val_t[0]))
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
#                        class ValueHelper
#===============================================================================
    
class ValueHelper(object):
    """A helper class that binds together everything needed to do a
    context sensitive formatting"""
    
    def __init__(self, value_t, context='current', formatter=Formatter()):
        """Initialize a ValueHelper.
        
        value_t: An instance of weewx.ValueTuple holding the data.
        
        context: The time context. Something like 'current', 'day', 'week', etc.
        [Optional. If not given, context 'current' will be used.]
        
        formatter: An instance of class Formatter() to be used to format the value
        as a string. [Optional. If not given, the default Formatter will be used]
        """
        self.value_t   = value_t
        self.context   = context
        self.formatter = formatter
        
    def __str__(self):
        """Return as string"""
        return self.formatter.toString(self.value_t, self.context)
    
    def string(self, NONE_string=None):
        """Return as string with an optional user specified string to be used if None"""
        return self.formatter.toString(self.value_t, self.context, NONE_string=NONE_string)
    
    def format(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format."""
        return self.formatter.toString(self.value_t, self.context, useThisFormat=format_string, NONE_string=NONE_string)
    
    def nolabel(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format. No label."""
        return self.formatter.toString(self.value_t, self.context, addLabel=False, useThisFormat=format_string, NONE_string=NONE_string)
        
    @property
    def formatted(self):
        """Return a formatted version of the data. No label."""
        return self.formatter.toString(self.value_t, self.context, addLabel=False)
        
    @property
    def raw(self):
        """Return the raw value without any formatting."""
        return self.value_t[0]
        
#===============================================================================
#                            class ValueDict
#===============================================================================

class ValueDict(dict):
    """A dictionary that returns contents as a ValueHelper.
    
    This dictionary, when keyed, returns a ValueHelper object, which can then
    be used for context sensitive formatting. 
    """
    
    def __init__(self, d, formatter=Formatter(), context='current'):
        """Initialize the ValueDict from another dictionary.
        
        d: A dictionary containing the key-value pairs for observation types
        and their values. It must include an entry 'usUnits', giving the
        standard unit system the entries are in. An example would be:
        
            {'outTemp'   : 23.9,
             'barometer' : 1002.3,
             'usUnits'   : 2}

        In this case, the standard unit system being used is "2", or Metric.
        
        formatter: An instance of the class Formatter. This will be passed on to
        the returned instance of ValueHelper. [Optional. If not given,
        the default Formatter will be used]
        
        context: The time context of the dictionary. This will be passed on to
        the returned instance of ValueHelper. [Optional. If not given,
        'current' will be used]
        """
        # Initialize my superclass, the dictionary:
        super(ValueDict, self).__init__(d)
        self.formatter = formatter
        self.context   = context
        
    def __getitem__(self, obs_type):
        """Look up an observation type (eg, 'outTemp') and return it as a 
        value-tuple in the target unit system."""
        # Find out what standard unit system (US or Metric) I am in:
        std_unit_system = dict.__getitem__(self, 'usUnits')
        # Given this standard unit system, what is the unit type of this
        # particular observation type?
        unit_type = getStandardUnitType(std_unit_system, obs_type)
        # Form the value-tuple. 
        val_t = weewx.ValueTuple(dict.__getitem__(self, obs_type), unit_type, obs_type)
        # Return the results as a ValueHelper
        vh = ValueHelper(val_t, context=self.context, formatter=self.formatter)
        return vh

#===============================================================================
#                             Helper functions
#===============================================================================
def _getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?

        Examples:
             obs_type  agg_type          Returns
             ________  ________         _________
            'outTemp',  None      -->  'group_temperature'
            'outTemp', 'mintime'  -->  'group_time'
            'wind',    'avg'      -->  'group_speed'
            'wind',    'vecdir'   -->  'group_direction'
        
        obs_type: An observation type. E.g., 'barometer'.
        
        agg_type: An aggregation type E.g., 'mintime', or 'avg'.
        
        Returns: the unit group or None if it cannot be determined."""
    if agg_type and agg_type in agg_group:
        unit_group = agg_group[agg_type]
    else:
        unit_group = obs_group_dict.get(obs_type)
    return unit_group
    
def getStandardUnitType(std_unit_system, obs_type, agg_type=None):
    """Given an observation type and an aggregation type, return the unit type
    within a standardized unit system.
    
    std_unit_system: Either weewx.US or weewx.METRIC
    
    obs_type: An observation type ('outTemp', 'rain', etc.)
    
    agg_type: Type of aggregation ('mintime', 'count', etc.)
    [Optional. default is no aggregation)
    
    returns the unit type of the given observation and aggregation type, 
    or None if it cannot be determined.
    """
    try:
        unit_group = _getUnitGroup(obs_type, agg_type)
        unit_type  = StdUnitSystem[std_unit_system][unit_group]
    except KeyError:
        unit_type = None
    return unit_type
    
def convert(val_t, target_unit_type):
    """ Convert a value or a sequence of values between unit systems

    val_t: A value-tuple with the value to be converted. The first
    element is the value (either a scalar or iterable), the second element 
    the unit type (e.g., "foot", or "inHg") it is in.
    
    target_unit_type: The unit type (e.g., "meter", or "mbar") to
    which the value is to be converted. If None, it will not be converted.
    
    returns: An instance of weewx.ValueTuple, converted into the desired units.
    """
    if target_unit_type is None or val_t[1] == target_unit_type or val_t[0] is None:
        return val_t

    # Try converting a sequence first. A TypeError exception will occur if
    # the value is actually a scalar:
    try:
        new_val = map(conversionDict[val_t[1]][target_unit_type], val_t[0])
    except TypeError:
        new_val = conversionDict[val_t[1]][target_unit_type](val_t[0])
    # Add on the unit type and the observation type and return the results:
    return weewx.ValueTuple((new_val, target_unit_type, val_t[2]))

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
    unit_group = obs_group_dict[val_t[2]]
    target_unit_type = StdUnitSystem[target_std_unit_system][unit_group]
    return convert(val_t, target_unit_type)
