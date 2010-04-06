#
#    Copyright (c) 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Data structures and functions for dealing with units

"""

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
                  "heatdeg"            : "group_temperature",
                  "cooldeg"            : "group_temperature",
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
                  "degree_compass"     : "group_direction",
                  "degree_F"           : "group_temperature",
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
                  "mm"                 : "group_rain",
                  "mm_per_hour"        : "group_rainrate",
                  "percent"            : "group_percent",
                  "volt"               : "group_volt",
                  "watt_per_meter_squared" : "group_radiation"}

# Some aggregations when applied to a type result in a different unit
# group. This data structure maps aggregation type to the group:
agg_group = {'mintime'  : "group_time",
             'maxtime'  : "group_time",
             'count'    : "group_count",
             'max_ge'   : "group_count",
             'max_le'   : "group_count",
             'min_le'   : "group_count",
             'sum_ge'   : "group_count",
             'vec_dir'  : "group_direction",
             'gust_dir' : "group_direction"}

# This structure maps unit classes to actual units using the US customary unit
# system.
USUnits       = {"group_pressure"     : "inHg",
                 "group_temperature"  : "degree_F",
                 "group_percent"      : "percent",
                 "group_speed"        : "mile_per_hour",
                 "group_direction"    : "degree_compass",
                 "group_speed2"       : "mile_per_hour2",
                 "group_rainrate"     : "inch_per_hour",
                 "group_rain"         : "inch",
                 "group_radiation"    : "watt_per_meter_squared",
                 "group_moisture"     : "centibar",
                 "group_volt"         : "volt",
                 "group_altitude"     : "meter",
                 "group_time"         : "unix_epoch",
                 "group_interval"     : "minute",
                 "group_count"        : "count"}

MetricUnits   = {"group_pressure"     : "mbar",
                 "group_temperature"  : "degree_C",
                 "group_percent"      : "percent",
                 "group_speed"        : "km_per_hour",
                 "group_direction"    : "degree_compass",
                 "group_speed2"       : "km_per_hour2",
                 "group_rainrate"     : "cm_per_hour",
                 "group_rain"         : "cm",
                 "group_radiation"    : "watt_per_meter_squared",
                 "group_moisture"     : "centibar",
                 "group_volt"         : "volt",
                 "group_altitude"     : "meter",
                 "group_time"         : "unix_epoch",
                 "group_interval"     : "minute",
                 "group_count"        : "count"}

StdUnitSystem     = {weewx.US     : USUnits,
                     weewx.METRIC : MetricUnits}

# Conversion functions to go from one unit type to another.  Right now, it only
# maps US Customary to Metric. It should be extended to go the other way.
conversionDict = {'inHg'           : {'mbar' : lambda x : 33.86 * x if x is not None else None, 
                                      'hPa'  : lambda x : 33.86 * x if x is not None else None},
                  'degree_F'       : {'degree_C' : lambda x : (5.0/9.0) * (x - 32.0) if x is not None else None},
                  'mile_per_hour'  : {'km_per_hour'       : lambda x : 1.609344    * x if x is not None else None,
                                      'knot'              : lambda x : 0.868976242 * x if x is not None else None,
                                      'meter_per_second'  : lambda x : 0.44704     * x if x is not None else None},
                  'mile_per_hour2' : {'km_per_hour2'      : lambda x : 1.609344    * x if x is not None else None,
                                      'knot2'             : lambda x : 0.868976242 * x if x is not None else None,
                                      'meter_per_second2' : lambda x : 0.44704     * x if x is not None else None},
                  'inch_per_hour'  : {'cm_per_hour' : lambda x : 2.54   * x if x is not None else None,
                                      'mm_per_hour' : lambda x : 25.4   * x if x is not None else None},
                  'inch'           : {'cm'          : lambda x : 2.54   * x if x is not None else None,
                                      'mm'          : lambda x : 25.4   * x if x is not None else None},
                  'foot'           : {'meter'       : lambda x : 0.3048 * x if x is not None else None} }


# Default unit formatting to be used in the absence of a skin configuration file
default_unit_format_dict = {"centibar"           : "%.0f",
                            "cm"                 : "%.2f",
                            "cm_per_hour"        : "%.2f",
                            "degree_C"           : "%.1f",
                            "degree_compass"     : "%.0f",
                            "degree_F"           : "%.1f",
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

# Default unit formatting to be used in the absence of a skin configuration file
default_unit_label_dict = { "centibar"          : " cb",
                            "cm"                : " cm",
                            "cm_per_hour"       : " cm/hr",
                            "degree_C"          : "\xc2\xb0C",
                            "degree_compass"    : "\xc2\xb0",
                            "degree_F"          : "\xc2\xb0F",
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

#===============================================================================
#                                class Value
#===============================================================================

class Value(object):
    """Represents an arbitrary value and a unit type (eg, 'mbar')"""
    
    def __init__(self, val, unit_type):
        """Initialize with a value and a unit type.
        
        val: A scalar .
        
        unit_type: The units val is in ('mbar', 'foot', 'degree_F'), etc.
        Set to None if unknown
        """
        self.val = val
        self.unit_type = unit_type
        
    @staticmethod
    def convertFrom(old_value, to_unit_type):
        """Convert an instance of Value to a new unit type.
        
        old_value: an instance of weewx.units.Value
        
        to_unit_type: The type of desired unit ('mbar', 'cm', etc.).
        
        Returns: A Value with attribute val equal to the converted values, 
        attribute unit_type equal to the new unit_type."""
        
        if old_value.unit_type is None or to_unit_type is None:
            return Value(old_value.val, None)
        if  old_value.unit_type == to_unit_type:
            return Value(old_value.val, old_value.unit_type)
    
        return Value(conversionDict[old_value.unit_type][to_unit_type](old_value.val), to_unit_type)
    
    @staticmethod
    def convertUsing(old_value, units):
        """Convert an instance of Value to a new unit given by an instance of weewx.units.Units.
        
        old_value: an instance of weewx.units.Value
        
        units: an instance of weewx.units.Units.
        
        Returns: A Value with attribute val equal to the converted values, 
        attribute unit_type equal to the new unit_type."""
        to_unit_type = units.getTargetType(old_value.unit_type)
        return Value.convertFrom(old_value, to_unit_type)

    def __str__(self):
        return ValueFormatter().toString(self)
    
    def __cmp__(self, other):
        return cmp(self.val, other.val) and cmp(self.unit_type, other.unit_type)
    
    def toString(self, valueFormatter = None):
        if not valueFormatter: 
            valueFormatter = ValueFormatter()
        return valueFormatter.toString(self)
    
#===============================================================================
#                        ValueList
#===============================================================================

class ValueList(list):
    """Represents a list with a unit type."""

    def __init__(self, seq, unit_type):
        """Initialize with a seq and a unit type.
        
        seq: A sequence.
        
        unit_type: The units val is in ('mbar', 'foot', 'degree_F'), etc.  Set
        to None if unknown
        """
        super(ValueList, self).__init__(self, seq)
        self.unit_type = unit_type
        
    def toUnit(self, to_unit_type):
        if self.unit_type is None or to_unit_type is None:
            return ValueList(self, None)
        if  self.unit_type == to_unit_type:
            return ValueList(self, self.unit_type)
    
        return ValueList(map(conversionDict[self.unit_type][to_unit_type], self), to_unit_type)

        
#===============================================================================
#                            class ValueDict
#===============================================================================

class ValueDict(dict) :
    """A dictionary like object which retains unit type information."""
    
    def __init__(self, d):
        unit_system = d['usUnits']
        
        for obs_type in d.keys():
            if obs_type == 'usUnits': continue
            self[obs_type] = Value(d[obs_type], getStandardUnitType(unit_system, obs_type))
    
    @staticmethod
    def fromSeq(type_seq, row_seq):

        d = dict(zip(type_seq, row_seq))
        return ValueDict(d)
        
    def __str__(self):
        return '{' + ', '.join(str(self[obs_type]) for obs_type in self.keys()) + '}'
    
    def summary(self):
        str_list = []
        for obs_type in ('dateTime', 'outTemp', 'barometer', 'windSpeed', 'windDir'):
            try:
                str_list.append(str(self[obs_type]))
            except KeyError:
                pass
        return ', '.join(str_list)    

#===============================================================================
#                            class ValueFormatter
#===============================================================================

class ValueFormatter(object):

    def __init__(self,
                 unit_format_dict = default_unit_format_dict, 
                 unit_label_dict  = default_unit_label_dict):
        # Key is unit type, value is a string format:
        self.unit_format_dict = unit_format_dict
        # Key is unit type, value is a label:
        self.unit_label_dict = unit_label_dict

    @staticmethod
    def fromSkinDict(skin_dict):
        return ValueFormatter(skin_dict['Units']['StringFormats'],
                              skin_dict['Units']['Labels'])
    
    def toString(self, val):
        if val.val is None:
            return self.unit_format_dict.get('NONE', 'N/A')
        elif val.unit_type == "unix_epoch":
            return weeutil.weeutil.timestamp_to_string(val.val)
        else:
            try:
                val_str = self.unit_format_dict[val.unit_type] % val.val
            except (KeyError, TypeError):
                val_str = str(val.val)
            
        label  = self.unit_label_dict.get(val.unit_type,'')
        return val_str + label

#===============================================================================
#                                class Units
#===============================================================================

class Units(object):
    """Retains information about desired unit types"""
    
    def __init__(self, unit_group_dict):
        """Initialize an instance of Units
        
        unit_group_dict: Key is a unit_group (eg, 'pressure'), 
        value is the desired unit type ('mbar')"""
        self.unit_group_dict = unit_group_dict

    @staticmethod
    def fromSkinDict(skin_dict):
        return Units(skin_dict['Units']['Groups'])

    def getUnitType(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return the target unit type."""
        unit_group = getUnitGroup(obs_type, agg_type)
        unit_type  = self.unit_group_dict[unit_group]
        return unit_type
        
    def getTargetType(self, old_unit_type):
        unit_group= unit_type_dict[old_unit_type]
        unit_type = self.unit_group_dict[unit_group]
        return unit_type
        
#    def convertFromStd(self, std_unit_system, obj, obs_type, agg_type=None):
#
#        from_unit_type = getStandardUnitType(std_unit_system, obs_type, agg_type)
#        to_unit_type = self.getUnitType(obs_type, agg_type)
#        val = convert(from_unit_type, to_unit_type, obj)
#        return val
        
def getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?"""
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
    """
    unit_group = getUnitGroup(obs_type, agg_type)
    unit_type  = StdUnitSystem[std_unit_system][unit_group] if unit_group else None
    return unit_type
    
def convert(from_unit_type, to_unit_type, obj):
    """ Convert a value or a sequence of values between unit systems

    from_unit_type: A string with the unit type (e.g., "foot", or "inHg") from
    which the object is to be converted.
    
    to_unit_type: A string with the unit type (e.g., "meter", or "mbar") to
    which the object is to be converted.
    
    obj: Either a scalar value or an iterable sequence of values.
    
    returns: Either a scalar value or an iterable sequence of values (depending
    on obj), converted into the desired units.
    """
    if to_unit_type is None or from_unit_type == to_unit_type or obj is None:
        return obj

    try:
        return map(conversionDict[from_unit_type][to_unit_type], obj)
    except TypeError:
        return conversionDict[from_unit_type][to_unit_type](obj)


if __name__ == '__main__':
    
    assert(convert('degree_F', 'degree_C', 32.0) == 0.0)
    assert(convert('degree_F', 'degree_C', [32.0, 212.0, -40.0]) == [0.0, 100.0, -40.0])
    
    d = {'usUnits' : 1,
         'dateTime' : 1234567890,
         'barometer': 30.02,
         'outTemp'  : 45.2}
    
    vd = ValueDict(d)
    print vd['barometer']
    
    print vd
    print vd.summary()
    
