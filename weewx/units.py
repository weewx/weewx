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

# This data structure maps types to a "unit class"
unitGroups = {  "barometer"          : "group_pressure",
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
                 "altitude"           : "group_altitude" }

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
                 "group_altitude"     : "meter"}

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
                 "group_volt"        : "volt",
                 "group_altitude"     : "meter"}

StdUnitSystem     = {weewx.US     : USUnits,
                     weewx.METRIC : MetricUnits}

conversionDict = {'inHg'           : {'mbar' : lambda x : 33.86 * x if x is not None else None, 
                                      'hPa'  : lambda x : 33.86 * x if x is not None else None},
                  'degree_F'       : {'degree_C' : lambda x : (5.0/9.0) * (x - 32.0) if x is not None else None},
                  'mile_per_hour'  : {'km_per_hour'       : lambda x : 1.609344 * x if x is not None else None,
                                      'knot'              : lambda x : 0.868976242 * x if x is not None else None,
                                      'meter_per_second'  : lambda x : 0.44704 * x if x is not None else None},
                  'mile_per_hour2' : {'km_per_hour2'      : lambda x : 1.609344 * x if x is not None else None,
                                      'knot2'             : lambda x : 0.868976242 * x if x is not None else None,
                                      'meter_per_second2' : lambda x : 0.44704 * x if x is not None else None},
                  'inch_per_hour'  : {'cm_per_hour' : lambda x : 2.54 * x if x is not None else None},
                  'inch'           : {'cm'          : lambda x : 2.54 * x if x is not None else None,
                                      'mm'          : lambda x : 25.4 * x if x is not None else None},
                  'foot'           : {'meter'       : lambda x : 0.3048 * x if x is not None else None} }

def convert(fromUnit, toUnit, obj):
    """ Convert a value or a sequence of values between unit systems

    fromUnit: A string with the unit system (e.g., "foot", or "inHg") from
    which the object is to be converted.
    
    toUnit: A string with the unit system (e.g., "meter", or "mbar") to
    which the object is to be converted.
    
    obj: Either a scalar value or an iterable sequence of values.
    
    returns: Either a scalar value or an iterable sequence of values (depending
    on obj converted into the desired units.
    """
    if toUnit is None or fromUnit == toUnit or obj is None:
        return obj
    
    if hasattr(obj, '__iter__'):
        return map(conversionDict[fromUnit][toUnit], obj)
    else:
        return conversionDict[fromUnit][toUnit](obj)

def convertStd(fromUnitSystem, fromType, toUnit, obj):
    """ Convert a value or a sequence of values from a standard unit system to a specified unit.
    
    fromUnitSystem: Either weewx.US or weewx.Metric, specifying the standard unit system
    from which the object is to be converted.

    fromType: The SQL type of the object (e.g., 'outTemp', or 'barometer')
    
    toUnit: A string with the unit system (e.g., "meter", or "mbar") to
    which the object is to be converted.
    
    obj: Either a scalar value or an iterable sequence of values.
    
    returns: Either a scalar value or an iterable sequence of values (depending
    on obj converted into the desired units.
    """
    fromClass = unitGroups.get(fromType)
    if not fromClass: return obj
    fromUnit = StdUnitSystem[fromUnitSystem][fromClass]
    return convert(fromUnit, toUnit, obj)
    
def getUnitType(config_dict, type):
    """Extract the type of unit (e.g., 'feet', 'miles_per_hour', etc.) as
    a string for the given type."""
    classType = unitGroups[type]
    unitType = config_dict['Units']['UnitGroups'][classType]
    return unitType

def getUnitTypeDict(config_dict):
    unitTypeDict = {}
    for type in unitGroups:
        unitTypeDict[type] = getUnitType(config_dict, type)
    return unitTypeDict

def getStringFormat(config_dict, type):
    """Extract a suitable string format (e.g., "%.0f") for a specific type"""
    return config_dict['Units']['StringFormats'][getUnitType(config_dict, type)]

def getLabel(config_dict, type):
    """Extract a generic unit label (e.g., "\xb0F", or "mph") for a specific type"""
    return config_dict['Labels']['UnitLabels'][getUnitType(config_dict, type)]
    
def getHTMLLabel(config_dict, type):
    """Extract an HTML unit label (e.g., "&deg;F") for a specific type"""
    return config_dict['HTML']['UnitLabels'][getUnitType(config_dict, type)]
    
def getStringFormatDict(config_dict):
    """Return a dictionary of suitable string formats for all types."""
    stringFormatDict = {}
    for type in unitGroups:
        stringFormatDict[type] = getStringFormat(config_dict, type)
    return stringFormatDict

def getLabelDict(config_dict):
    """Return a dictionary of suitable generic unit labels for all types."""
    labelDict = {}
    for type in unitGroups:
        labelDict[type] = getLabel(config_dict, type)
    return labelDict

def getHTMLLabelDict(config_dict):
    """Return a dictionary of suitable HTML unit labels for all types."""
    htmlLabelDict = {}
    for type in unitGroups:
        htmlLabelDict[type] = getHTMLLabel(config_dict, type)
    return htmlLabelDict
            
if __name__ == '__main__':
    
    assert(convert('degrees_F', 'degrees_C', 32.0) == 0.0)
    assert(convert('degrees_F', 'degrees_C', [32.0, 212.0, -40.0]) == [0.0, 100.0, -40.0])
    assert()
    
