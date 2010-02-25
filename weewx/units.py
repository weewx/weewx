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
unitClasses = {  "barometer"          : "class_pressure",
                 "pressure"           : "class_pressure",
                 "altimeter"          : "class_pressure",
                 "inTemp"             : "class_temperature",
                 "outTemp"            : "class_temperature",
                 "inHumidity"         : "class_percent",
                 "outHumidity"        : "class_percent",
                 "windSpeed"          : "class_speed",
                 "windDir"            : "class_direction",
                 "windGust"           : "class_speed",
                 "windGustDir"        : "class_direction",
                 "windvec"            : "class_speed",
                 "windgustvec"        : "class_speed",
                 "wind"               : "class_speed",
                 "vecdir"             : "class_direction",
                 "vecavg"             : "class_speed2",
                 "rms"                : "class_speed2",
                 "gustdir"            : "class_direction",
                 "rainRate"           : "class_rainrate",
                 "rain"               : "class_rain",
                 "dewpoint"           : "class_temperature",
                 "windchill"          : "class_temperature",
                 "heatindex"          : "class_temperature",
                 "ET"                 : "class_rain",
                 "radiation"          : "class_radiation",
                 "UV"                 : "class_radiation",
                 "extraTemp1"         : "class_temperature",
                 "extraTemp2"         : "class_temperature",
                 "extraTemp3"         : "class_temperature",
                 "soilTemp1"          : "class_temperature",
                 "soilTemp2"          : "class_temperature",
                 "soilTemp3"          : "class_temperature",
                 "soilTemp4"          : "class_temperature",
                 "leafTemp1"          : "class_temperature",
                 "leafTemp2"          : "class_temperature",
                 "extraHumid1"        : "class_percent",
                 "extraHumid2"        : "class_percent",
                 "soilMoist1"         : "class_moisture",
                 "soilMoist2"         : "class_moisture",
                 "soilMoist3"         : "class_moisture",
                 "soilMoist4"         : "class_moisture",
                 "rxCheckPercent"     : "class_percent",
                 "consBatteryVoltage" : "class_volt",
                 "hail"               : "class_rain",
                 "hailRate"           : "class_rainrate",
                 "heatingTemp"        : "class_temperature",
                 "heatingVoltage"     : "class_volt",
                 "supplyVoltage"      : "class_volt",
                 "referenceVoltage"   : "class_volt",
                 "altitude"           : "class_altitude" }

# This structure maps unit classes to actual units using the
# US customary unit system.
USUnits       = {"class_pressure"     : "inHg",
                 "class_temperature"  : "degree_F",
                 "class_percent"      : "percent",
                 "class_speed"        : "mile_per_hour",
                 "class_direction"    : "degree_compass",
                 "class_speed2"       : "mile_per_hour2",
                 "class_rainrate"     : "inch_per_hour",
                 "class_rain"         : "inch",
                 "class_radiation"    : "watt_per_meter_squared",
                 "class_moisture"     : "centibar",
                 "class_volt"         : "volt",
                 "class_altitude"     : "meter"}

MetricUnits   = {"class_pressure"     : "mbar",
                 "class_temperature"  : "degree_C",
                 "class_percent"      : "percent",
                 "class_speed"        : "km_per_hour",
                 "class_direction"    : "degree_compass",
                 "class_speed2"       : "km_per_hour2",
                 "class_rainrate"     : "cm_per_hour",
                 "class_rain"         : "cm",
                 "class_radiation"    : "watt_per_meter_squared",
                 "class_moisture"     : "centibar",
                 "class_volt"        : "volt",
                 "class_altitude"     : "meter"}

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
    fromClass = unitClasses.get(fromType)
    if not fromClass: return obj
    fromUnit = StdUnitSystem[fromUnitSystem][fromClass]
    return convert(fromUnit, toUnit, obj)
    
def getUnitType(config_dict, type):
    """Extract the type of unit (e.g., 'feet', 'miles_per_hour', etc.) as
    a string for the given type."""
    classType = unitClasses[type]
    unitType = config_dict['Units']['UnitClasses'][classType]
    return unitType

def getUnitTypeDict(config_dict):
    unitTypeDict = {}
    for type in unitClasses:
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
    for type in unitClasses:
        stringFormatDict[type] = getStringFormat(config_dict, type)
    return stringFormatDict

def getLabelDict(config_dict):
    """Return a dictionary of suitable generic unit labels for all types."""
    labelDict = {}
    for type in unitClasses:
        labelDict[type] = getLabel(config_dict, type)
    return labelDict

def getHTMLLabelDict(config_dict):
    """Return a dictionary of suitable HTML unit labels for all types."""
    htmlLabelDict = {}
    for type in unitClasses:
        htmlLabelDict[type] = getHTMLLabel(config_dict, type)
    return htmlLabelDict
            
if __name__ == '__main__':
    
    assert(convert('degrees_F', 'degrees_C', 32.0) == 0.0)
    assert(convert('degrees_F', 'degrees_C', [32.0, 212.0, -40.0]) == [0.0, 100.0, -40.0])
    assert()
    
