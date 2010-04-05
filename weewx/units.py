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
                  "cooldeg"            : "group_temperature"}

# Some aggregations when applied to a type result in a
# different unit group. This data structure maps aggregation
# type to the group:
agg_group = {'mintime'  : "group_time",
             'maxtime'  : "group_time",
             'count'    : "group_count",
             'max_ge'   : "group_count",
             'max_le'   : "group_count",
             'min_le'   : "group_count",
             'sum_ge'   : "group_count",
             'vec_dir'  : "group_direction",
             'gust_dir' : "group_direction"}

# This structure maps unit classes to actual units using the
# US customary unit system.
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
                 "group_NONE"         : "NONE"}

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
                 "group_NONE"         : "NONE"}

StdUnitSystem     = {weewx.US     : USUnits,
                     weewx.METRIC : MetricUnits}

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



class Units(object):
    
    def __init__(self, skin_dict):
        
        # Key is a unit_group (eg, 'pressure'), value is the desired unit type ('mbar'):
        self.unit_group_dict = skin_dict['Units']['Groups']
        # Key is unit type, value is a string format:
        self.unit_type_format_dict = skin_dict['Units']['StringFormats']
        # Key is unit type, value is a label:
        self.unit_type_label_dict = skin_dict['Units']['Labels']
        
    def convertFromStd(self, std_unit_system, obj, obs_type, agg_type=None):

        from_unit_type = getStandardUnitType(std_unit_system, obs_type, agg_type)
        to_unit_type = self.getUnitType(obs_type, agg_type)
        val = convert(from_unit_type, to_unit_type, obj)
        return val
        
    def getUnitType(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return the target unit type."""
        unit_group = getUnitGroup(obs_type, agg_type)
        unit_type  = self.unit_group_dict[unit_group]
        return unit_type

    def getUnitFormat(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return a suitable string format (e.g., "%.0f")"""
        unit_type = self.getUnitType(obs_type, agg_type)
        return self.unit_type_format_dict[unit_type]

    def getUnitLabel(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return a suitable unit label (e.g., "\xb0F", or "mph")"""
        unit_type = self.getUnitType(obs_type, agg_type)
        return self.unit_type_label_dict[unit_type]
        
def getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?"""
    if agg_type and agg_type in agg_group:
        unit_group = agg_group[agg_type]
    else:
        unit_group = obs_group_dict[obs_type]
    return unit_group
    
def getStandardUnitType(std_unit_system, obs_type, agg_type=None):
    """Given an observation type and an aggregation type, return the unit type within a standardized unit system.
    
    std_unit_system: Either weewx.US or weewx.METRIC
    
    obs_type: An observation type ('outTemp', 'rain', etc.)
    
    agg_type: Type of aggregation ('mintime', 'count', etc.)
    [Optional. default is no aggregation)
    """
    unit_group = getUnitGroup(obs_type, agg_type)
    unit_type  = StdUnitSystem[std_unit_system][unit_group]
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


#def convertStd(from_unit_system, obs_type, to_unit_type, obj):
#    """ Convert a value or a sequence of values from a standard unit system to a specified unit.
#    
#    from_unit_system: Either weewx.US or weewx.Metric, specifying the standard unit system
#    from which the object is to be converted.
#
#    obs_type: The SQL type of the object (e.g., 'outTemp', or 'barometer')
#    
#    to_unit_type: A string with the unit system (e.g., "meter", or "mbar") to
#    which the object is to be converted.
#    
#    obj: Either a scalar value or an iterable sequence of values.
#    
#    returns: Either a scalar value or an iterable sequence of values (depending
#    on obj converted into the desired units.
#    """
#    from_group = obs_group_dict.get(obs_type)
#    if None in (from_unit_system, from_group): 
#        return obj
#    fromUnit = StdUnitSystem[from_unit_system][from_group]
#    return convert(fromUnit, to_unit_type, obj)
#    
#def getUnitType(skin_dict, obs_type):
#    """Extract the type of unit (e.g., 'feet', 'miles_per_hour', etc.) as
#    a string for the given observation type."""
#    unit_group = obs_group_dict[obs_type]
#    unitType = skin_dict['Units']['Groups'][unit_group]
#    return unitType
#
#def getUnitTypeDict(skin_dict):
#    """Returns a dictionary where the key is an observation type (eg, 'outTemp'),
#    and the value is the type of unit for that type (eg, 'degree_F')"""
#    unitTypeDict = {}
#    for obs_type in obs_group_dict:
#        unitTypeDict[obs_type] = getUnitType(skin_dict, obs_type)
#    return unitTypeDict
#
#def getStringFormat(skin_dict, obs_type):
#    """Extract a suitable string format (e.g., "%.0f") for a specific observation type"""
#    return skin_dict['Units']['StringFormats'][getUnitType(skin_dict, obs_type)]
#
#def getUnitLabel(skin_dict, obs_type):
#    """Extract a generic unit label (e.g., "\xb0F", or "mph") for a specific observation type"""
#    label = skin_dict['Units']['Labels'][getUnitType(skin_dict, obs_type)]
#    return label
#    
#def getUnitStringFormatDict(skin_dict):
#    """Return a dictionary of suitable string formats for all observation types."""
#    stringFormatDict = {}
#    for obs_type in obs_group_dict:
#        stringFormatDict[obs_type] = getStringFormat(skin_dict, obs_type)
#    return stringFormatDict
#
#def getUnitLabelDict(skin_dict):
#    """Return a dictionary of suitable generic unit labels for all observation types."""
#    labelDict = {}
#    for obs_type in obs_group_dict:
#        labelDict[obs_type] = getUnitLabel(skin_dict, obs_type)
#    return labelDict

if __name__ == '__main__':
    
    assert(convert('degrees_F', 'degrees_C', 32.0) == 0.0)
    assert(convert('degrees_F', 'degrees_C', [32.0, 212.0, -40.0]) == [0.0, 100.0, -40.0])
    
