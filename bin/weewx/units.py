#
#    Copyright (c) 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Data structures and functions for dealing with units"""
import time

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
                  "UV"                 : "group_radiation",
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

# Key is a unit type, value is which unit group it belongs to.  There is an
# assumption here that there is a one-to-one mapping from a unit type to a unit
# group, but that doesn't have to be so.  For example, supposed someone wanted
# to measure rain in meters.  Would a meter be in group_rain, or group_altitude?
# A workaround would be to create a new unit type of "rain_meter".
unit_type_dict = {"centibar"           : "group_moisture",
                  "cm"                 : "group_rain",
                  "cm_per_hour"        : "group_rainrate",
                  "count"              : "group_count",
                  "degree_C"           : "group_temperature",
                  "degree_C_day"       : "group_degree_day",
                  "degree_compass"     : "group_direction",
                  "degree_F"           : "group_temperature",
                  "degree_F_day"       : "group_degree_day",
                  "foot"               : "group_altitude",
                  "hPa"                : "group_pressure",
                  "inHg"               : "group_pressure",
                  "inch"               : "group_rain",
                  "inch_per_hour"      : "group_rainrate",
                  "km_per_hour"        : "group_speed",
                  "km_per_hour2"       : "group_speed2",
                  "knot"               : "group_speed",
                  "knot2"              : "group_speed2",
                  "mbar"               : "group_pressure",
                  "meter"              : "group_altitude",
                  "meter_per_second"   : "group_speed",
                  "meter_per_second2"  : "group_speed2",
                  "mile_per_hour"      : "group_speed",
                  "mile_per_hour2"     : "group_speed2",
                  "minute"             : "group_interval",
                  "mm"                 : "group_rain",
                  "mm_per_hour"        : "group_rainrate",
                  "percent"            : "group_percent",
                  "unix_epoch"         : "group_time",
                  "volt"               : "group_volt",
                  "watt_per_meter_squared" : "group_radiation"}

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

# This structure maps unit groups to the unit type in the 
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
                 "group_volt"         : "volt"}

# This structure maps unit groups to the unit type in the 
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
                 "group_volt"         : "volt"}

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
      'inch_per_hour'    : {'cm_per_hour' : lambda x : 2.54   * x if x is not None else None,
                            'mm_per_hour' : lambda x : 25.4   * x if x is not None else None},
      'inch'             : {'cm'          : lambda x : 2.54   * x if x is not None else None,
                            'mm'          : lambda x : 25.4   * x if x is not None else None},
      'foot'             : {'meter'       : lambda x : 0.3048 * x if x is not None else None},
      
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
                            "percent"           :  "%",
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

# Default base temperature and unit type for heating and cooling degree days
# as a value tuple
default_heatbase = (65.0, "degree_F")
default_coolbase = (65.0, "degree_F")

#===============================================================================
#                        class ValueHelper
#===============================================================================
    
class ValueHelper(object):
    """A helper class that binds together everything needed to do a
    context sensitive formatting"""
    
    def __init__(self, value_t, context='current', unit_info=None):
        """Initialize a ValueHelper.
        
        value_t: The value tuple with the data. First element is the value,
        second element the unit type (or None if not known).
        
        context: The time context. Something like 'current', 'day', 'week', etc.
        [Optional. If not given, context 'current' will be used.]
        
        unit_info: An instance of UnitInfo. This will be used to determine what
        unit the value is to be displayed in, as well as any formatting and labeling
        information. [Optional. If not given, the default UnitInfo will be used]
        """
        self.value_t   = value_t
        self.context   = context
        self.unit_info = unit_info if unit_info else UnitInfo()
        
    def __str__(self):
        """Return as string"""
        return self.unit_info.toString(self.value_t, self.context)
    
    def string(self, NONE_string=None):
        """Return as string with an optional user specified string to be used if None"""
        return self.unit_info.toString(self.value_t, self.context, NONE_string=NONE_string)
    
    def format(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format."""
        return self.unit_info.toString(self.value_t, self.context, useThisFormat=format_string, NONE_string=NONE_string)
    
    def nolabel(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format. No label."""
        return self.unit_info.toString(self.value_t, self.context, addLabel=False, useThisFormat=format_string, NONE_string=NONE_string)

    @property
    def formatted(self):
        """Return a formatted version of the data. No label."""
        return self.unit_info.toString(self.value_t, self.context, addLabel=False)
        
    @property
    def raw(self):
        """Return the value in the target unit type.
        
        'Raw' does unit conversion, but does not apply any formatting.
        
        Returns: The value in the target unit type"""
        return self.value_tuple[0]
    
    @property
    def value_tuple(self):
        """Returns a value tuple with the value in the targeted unit type.
        
        Returns: A value tuple. First element is the value, second element the unit type"""
        
        return self.unit_info.convert(self.value_t)
        
#===============================================================================
#                            class ValueDict
#===============================================================================

class ValueDict(dict):
    """A dictionary that returns contents as a ValueHelper.
    
    This dictionary, when keyed, returns a ValueHelper object, which can then
    be used for context sensitive formatting.
    """
    
    def __init__(self, d, unit_info=None):
        dict.__init__(self, d)
        self.unit_info = unit_info if unit_info else UnitInfo()
        
    def __getitem__(self, obs_type):
        std_unit_system = dict.__getitem__(self, 'usUnits')
        unit_type = getStandardUnitType(std_unit_system, obs_type)
        val_t = (dict.__getitem__(self, obs_type), unit_type)
        vh = ValueHelper(val_t, unit_info=self.unit_info)
        return vh
        
#===============================================================================
#                            class UnitInfo
#===============================================================================

class UnitInfo(object):
    """Holds formatting, labels, and target types for units."""

    def __init__(self, 
                 unit_type_dict   = USUnits, 
                 unit_format_dict = default_unit_format_dict,  
                 unit_label_dict  = default_unit_label_dict,
                 time_format_dict = default_time_format_dict,
                 heatbase=None, coolbase=None):
        """
        unit_type_dict: Key is a unit_group (eg, 'group_pressure'), 
        value is the target unit type ('mbar')
        
        unit_format_dict: Key is unit type (eg, 'inHg'), 
        value is a string format ("%.1f")
        
        unit_label_dict: Key is unit type (eg, 'inHg'), 
        value is a label (" inHg")
        
        time_format_dict: Key is a context (eg, 'week'),
        value is a strftime format ("%d-%b-%Y %H:%M").
        
        heatbase: A value tuple. First element is the base temperature
        for heating degree days, second element the unit it is in.
        [Optional. If not given, (65.0, 'default_F') will be used.]
        
        coolbase: A value tuple. First element is the base temperature
        for cooling degree days, second element the unit it is in.
        [Optional. If not given, (65.0, 'default_F') will be used.]
        """
        self.unit_type_dict  = unit_type_dict
        self.unit_format_dict = unit_format_dict
        self.unit_label_dict  = unit_label_dict
        self.time_format_dict = time_format_dict
        self.heatbase = heatbase if heatbase is not None else default_heatbase
        self.coolbase = coolbase if coolbase is not None else default_coolbase
        
        # These are mostly used as template tags:
        self.format    = self.getObsFormatDict()
        self.label     = self.getObsLabelDict()
        self.unit_type = self.getObsUnitDict()

    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        heatbase = skin_dict['Units']['DegreeDays'].get('heating_base')
        coolbase = skin_dict['Units']['DegreeDays'].get('heating_base')
        heatbase_t = (float(heatbase[0]), heatbase[1]) if heatbase else None
        coolbase_t = (float(coolbase[0]), coolbase[1]) if coolbase else None

        return UnitInfo(skin_dict['Units']['Groups'],
                        skin_dict['Units']['StringFormats'],
                        skin_dict['Units']['Labels'],
                        skin_dict['Units']['TimeFormats'],
                        heatbase_t,
                        coolbase_t)
    
    def toString(self, val_t, context='current', addLabel=True, 
                 useThisFormat=None, NONE_string=None):
        """Format the value as a string.
        
        val_t: The value to be formatted as a value tuple. First element
        is the value, the second element the unit type (eg, 'degree_F') it is in.
        
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
            
        # It's not a None value. Perform the type conversion to the internally
        # held target type:
        (target_val, target_unit_type) = self.convert(val_t)

        if target_unit_type == "unix_epoch":
            # Different formatting routines are used if the value is a time.
            try:
                if useThisFormat:
                    val_str = time.strftime(useThisFormat, time.localtime(target_val))
                else:
                    val_str = time.strftime(self.time_format_dict[context], time.localtime(target_val))
            except (KeyError, TypeError):
                # If all else fails, use this weeutil utility:
                val_str = weeutil.weeutil.timestamp_to_string(target_val)
        else:
            # It's not a time. It's a regular value.
            try:
                if useThisFormat:
                    val_str = useThisFormat % target_val
                else:
                    val_str = self.unit_format_dict[target_unit_type] % target_val
            except (KeyError, TypeError):
                # If all else fails, ask Python to convert to a string:
                val_str = str(target_val)

        if addLabel:
            val_str += self.unit_label_dict.get(target_unit_type,'')

        return val_str

    def getUnitType(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return the target unit type.
        
        Examples:
             obs_type  agg_type              Returns
             ________  ________              _______
            'outTemp',  None     returns --> 'degree_C'
            'outTemp', 'mintime' returns --> 'unix_epoch'
            'wind',    'avg'     returns --> 'meter_per_second'
            'wind',    'vecdir'  returns --> 'degree_compass'
        
        obs_type: An observation type. E.g., 'barometer'.
        
        agg_type: An aggregation type E.g., 'mintime', or 'avg'.
        
        Returns: the target unit type
        """
        unit_group = getUnitGroup(obs_type, agg_type)
        unit_type = self._getUnitTypeFromGroup(unit_group)
        return unit_type
        
    def getTargetType(self, old_unit_type):
        """Given an old unit type, return the target unit type.
        
        old_unit_type: A unit type such as 'inHg'.
        
        Returns: the target unit type, such as 'mbar'.
        """
        unit_group= unit_type_dict[old_unit_type]
        unit_type = self._getUnitTypeFromGroup(unit_group)
        return unit_type
    
    def convert(self, val_t):
        """Convert a value from a given unit type to the target type.
        
        val_t: A value tuple with the data and a unit type. 
        Example: (30.02, 'inHg')
        
        returns: A value tuple in the new, target unit type 
        Example: (1016.5, 'mbar')"""
        new_unit_type = self.getTargetType(val_t[1])
        new_val_t = convert(val_t, new_unit_type)
        return new_val_t
        
    def getObsFormatDict(self):
        """Returns a dictionary with key an observation type, value a string or time format."""
        obs_format_dict = {}
        for obs_type in obs_group_dict:
            obs_format_dict[obs_type] = self.unit_format_dict.get(self.getUnitType(obs_type),'')
        return obs_format_dict
    
    def getObsLabelDict(self):
        """Returns a dictionary with key an observation type, value a label."""
        obs_label_dict = {}
        for obs_type in obs_group_dict:
            obs_label_dict[obs_type] = self.unit_label_dict.get(self.getUnitType(obs_type),'')
        return obs_label_dict
    
    def getObsUnitDict(self):
        """Returns a dictionary with key an observation type, value the target unit type."""
        obs_unit_dict = {}
        for obs_type in obs_group_dict:
            obs_unit_dict[obs_type] = self.getUnitType(obs_type)
        return obs_unit_dict
    
    def _getUnitTypeFromGroup(self, unit_group):
        unit_type = self.unit_type_dict.get(unit_group, USUnits[unit_group])
        return unit_type
        
    
def getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?
    
    Returns None if it cannot be determined."""
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
        unit_group = getUnitGroup(obs_type, agg_type)
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
    which the value is to be converted.
    
    returns: A value tuple converted into the desired units.
    """
    if target_unit_type is None or val_t[1] == target_unit_type or val_t[0] is None:
        return val_t

    try:
        return (map(conversionDict[val_t[1]][target_unit_type], val_t[0]), target_unit_type)
    except TypeError:
        return (conversionDict[val_t[1]][target_unit_type](val_t[0]), target_unit_type)

def convertStd(val_t, target_std_unit_system):
    """Convert a value tuple to an appropriate unit in a target standardized
    unit system
    
        Example: convertStd((30.02, 'inHg'), weewx.METRIC)
        returns: (1016.5 'mbar')
    
    val_t: A value tuple. Example: (30.02, 'inHg')
    
    target_std_unit_system: A standardized unit system. 
    Example: weewx.US or weewx.METRIC.
    
    Returns: A value tuple in the given standardized unit system.
    """
    unit_group = unit_type_dict[val_t[1]]
    target_unit_type = StdUnitSystem[target_std_unit_system][unit_group]
    return convert(val_t, target_unit_type)
