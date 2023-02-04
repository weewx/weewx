# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Data structures and functions for dealing with units."""

#
# The doctest examples work only under Python 3!!
#

from __future__ import absolute_import
from __future__ import print_function
import json
import locale
import logging
import time

import six

import weewx
import weeutil.weeutil
from weeutil.weeutil import ListOfDicts, Polar, is_iterable

log = logging.getLogger(__name__)

# Handy conversion constants and functions:
INHG_PER_MBAR  = 0.0295299875
MM_PER_INCH    = 25.4
CM_PER_INCH    = MM_PER_INCH / 10.0
METER_PER_MILE = 1609.34
METER_PER_FOOT = METER_PER_MILE / 5280.0
MILE_PER_KM    = 1000.0 / METER_PER_MILE
SECS_PER_DAY   = 86400

def CtoK(x):
    return x + 273.15

def KtoC(x):
    return x - 273.15

def KtoF(x):
    return CtoF(KtoC(x))

def FtoK(x):
    return CtoK(FtoC(x))

def CtoF(x):
    return x * 1.8 + 32.0

def FtoC(x):
    return (x - 32.0) / 1.8

# Conversions to and from Felsius.
# For the definition of Felsius, see https://xkcd.com/1923/
def FtoE(x):
    return (7.0 * x - 80.0) / 9.0

def EtoF(x):
    return (9.0 * x + 80.0) / 7.0

def CtoE(x):
    return (7.0 / 5.0) * x + 16.0

def EtoC(x):
    return (x - 16.0) * 5.0 / 7.0

def mps_to_mph(x):
    return x * 3600.0 / METER_PER_MILE

def kph_to_mph(x):
    return x * 1000.0 / METER_PER_MILE

def mph_to_knot(x):
    return x * 0.868976242

def kph_to_knot(x):
    return x * 0.539956803

def mps_to_knot(x):
    return x * 1.94384449

class UnknownType(object):
    """Indicates that the observation type is unknown."""
    def __init__(self, obs_type):
        self.obs_type = obs_type

unit_constants = {
    'US'       : weewx.US,
    'METRIC'   : weewx.METRIC,
    'METRICWX' : weewx.METRICWX
}

unit_nicknames = {
    weewx.US       : 'US',
    weewx.METRIC   : 'METRIC',
    weewx.METRICWX : 'METRICWX'
}

# This data structure maps observation types to a "unit group"
# We start with a standard object group dictionary, but users are
# free to extend it:
obs_group_dict = ListOfDicts({
    "altimeter"                 : "group_pressure",
    "altimeterRate"             : "group_pressurerate",
    "altitude"                  : "group_altitude",
    "appTemp"                   : "group_temperature",
    "appTemp1"                  : "group_temperature",
    "barometer"                 : "group_pressure",
    "barometerRate"             : "group_pressurerate",
    "beaufort"                  : "group_count",           # DEPRECATED
    "cloudbase"                 : "group_altitude",
    "cloudcover"                : "group_percent",
    "co"                        : "group_fraction",
    "co2"                       : "group_fraction",
    "consBatteryVoltage"        : "group_volt",
    "cooldeg"                   : "group_degree_day",
    "dateTime"                  : "group_time",
    "dayRain"                   : "group_rain",
    "daySunshineDur"            : "group_deltatime",
    "dewpoint"                  : "group_temperature",
    "dewpoint1"                 : "group_temperature",
    "ET"                        : "group_rain",
    "extraHumid1"               : "group_percent",
    "extraHumid2"               : "group_percent",
    "extraHumid3"               : "group_percent",
    "extraHumid4"               : "group_percent",
    "extraHumid5"               : "group_percent",
    "extraHumid6"               : "group_percent",
    "extraHumid7"               : "group_percent",
    "extraHumid8"               : "group_percent",
    "extraTemp1"                : "group_temperature",
    "extraTemp2"                : "group_temperature",
    "extraTemp3"                : "group_temperature",
    "extraTemp4"                : "group_temperature",
    "extraTemp5"                : "group_temperature",
    "extraTemp6"                : "group_temperature",
    "extraTemp7"                : "group_temperature",
    "extraTemp8"                : "group_temperature",
    "growdeg"                   : "group_degree_day",
    "gustdir"                   : "group_direction",
    "hail"                      : "group_rain",
    "hailRate"                  : "group_rainrate",
    "heatdeg"                   : "group_degree_day",
    "heatindex"                 : "group_temperature",
    "heatindex1"                : "group_temperature",
    "heatingTemp"               : "group_temperature",
    "heatingVoltage"            : "group_volt",
    "highOutTemp"               : "group_temperature",
    "hourRain"                  : "group_rain",
    "humidex"                   : "group_temperature",
    "humidex1"                  : "group_temperature",
    "illuminance"               : "group_illuminance",
    "inDewpoint"                : "group_temperature",
    "inHumidity"                : "group_percent",
    "inTemp"                    : "group_temperature",
    "interval"                  : "group_interval",
    "leafTemp1"                 : "group_temperature",
    "leafTemp2"                 : "group_temperature",
    "leafTemp3"                 : "group_temperature",
    "leafTemp4"                 : "group_temperature",
    "leafWet1"                  : "group_count",
    "leafWet2"                  : "group_count",
    "lightning_distance"        : "group_distance",
    "lightning_disturber_count" : "group_count",
    "lightning_noise_count"     : "group_count",
    "lightning_strike_count"    : "group_count",
    "lowOutTemp"                : "group_temperature",
    "maxSolarRad"               : "group_radiation",
    "monthRain"                 : "group_rain",
    "nh3"                       : "group_fraction",
    "no2"                       : "group_concentration",
    "noise"                     : "group_db",
    "o3"                        : "group_fraction",
    "outHumidity"               : "group_percent",
    "outTemp"                   : "group_temperature",
    "outWetbulb"                : "group_temperature",
    "pb"                        : "group_fraction",
    "pm1_0"                     : "group_concentration",
    "pm2_5"                     : "group_concentration",
    "pm10_0"                    : "group_concentration",
    "pop"                       : "group_percent",
    "pressure"                  : "group_pressure",
    "pressureRate"              : "group_pressurerate",
    "radiation"                 : "group_radiation",
    "rain"                      : "group_rain",
    "rain24"                    : "group_rain",
    "rainDur"                   : "group_deltatime",
    "rainRate"                  : "group_rainrate",
    "referenceVoltage"          : "group_volt",
    "rms"                       : "group_speed2",
    "rxCheckPercent"            : "group_percent",
    "snow"                      : "group_rain",
    "snowDepth"                 : "group_rain",
    "snowMoisture"              : "group_percent",
    "snowRate"                  : "group_rainrate",
    "so2"                       : "group_fraction",
    "soilMoist1"                : "group_moisture",
    "soilMoist2"                : "group_moisture",
    "soilMoist3"                : "group_moisture",
    "soilMoist4"                : "group_moisture",
    "soilTemp1"                 : "group_temperature",
    "soilTemp2"                 : "group_temperature",
    "soilTemp3"                 : "group_temperature",
    "soilTemp4"                 : "group_temperature",
    "stormRain"                 : "group_rain",
    "stormStart"                : "group_time",
    "sunshineDur"               : "group_deltatime",
    "supplyVoltage"             : "group_volt",
    "THSW"                      : "group_temperature",
    "totalRain"                 : "group_rain",
    "UV"                        : "group_uv",
    "vecavg"                    : "group_speed2",
    "vecdir"                    : "group_direction",
    "wind"                      : "group_speed",
    "windchill"                 : "group_temperature",
    "windDir"                   : "group_direction",
    "windDir10"                 : "group_direction",
    "windGust"                  : "group_speed",
    "windGustDir"               : "group_direction",
    "windgustvec"               : "group_speed",
    "windrun"                   : "group_distance",
    "windSpeed"                 : "group_speed",
    "windSpeed10"               : "group_speed",
    "windvec"                   : "group_speed",
    "yearRain"                  : "group_rain",
})

# Some aggregations when applied to a type result in a different unit
# group. This data structure maps aggregation type to the group:
agg_group = {
    "firsttime"  : "group_time",
    "lasttime"   : "group_time",
    "maxsumtime" : "group_time",
    "minsumtime" : "group_time",
    'count'      : "group_count",
    'gustdir'    : "group_direction",
    'max_ge'     : "group_count",
    'max_le'     : "group_count",
    'maxmintime' : "group_time",
    'maxtime'    : "group_time",
    'min_ge'     : "group_count",
    'min_le'     : "group_count",
    'minmaxtime' : "group_time",
    'mintime'    : "group_time",
    'not_null'   : "group_boolean",
    'sum_ge'     : "group_count",
    'sum_le'     : "group_count",
    'vecdir'     : "group_direction",
    'avg_ge'     : "group_count",
    'avg_le'     : "group_count",
}

# This dictionary maps unit groups to a standard unit type in the 
# US customary unit system:
USUnits = ListOfDicts({
    "group_altitude"    : "foot",
    "group_amp"         : "amp",
    "group_boolean"     : "boolean",
    "group_concentration": "microgram_per_meter_cubed",
    "group_count"       : "count",
    "group_data"        : "byte",
    "group_db"          : "dB",
    "group_degree_day"  : "degree_F_day",
    "group_deltatime"   : "second",
    "group_direction"   : "degree_compass",
    "group_distance"    : "mile",
    "group_elapsed"     : "second",
    "group_energy"      : "watt_hour",
    "group_energy2"     : "watt_second",
    "group_fraction"    : "ppm",
    "group_frequency"   : "hertz",
    "group_illuminance" : "lux",
    "group_interval"    : "minute",
    "group_length"      : "inch",
    "group_moisture"    : "centibar",
    "group_percent"     : "percent",
    "group_power"       : "watt",
    "group_pressure"    : "inHg",
    "group_pressurerate": "inHg_per_hour",
    "group_radiation"   : "watt_per_meter_squared",
    "group_rain"        : "inch",
    "group_rainrate"    : "inch_per_hour",
    "group_speed"       : "mile_per_hour",
    "group_speed2"      : "mile_per_hour2",
    "group_temperature" : "degree_F",
    "group_time"        : "unix_epoch",
    "group_uv"          : "uv_index",
    "group_volt"        : "volt",
    "group_volume"      : "gallon"
})

# This dictionary maps unit groups to a standard unit type in the 
# metric unit system:
MetricUnits = ListOfDicts({
    "group_altitude"    : "meter",
    "group_amp"         : "amp",
    "group_boolean"     : "boolean",
    "group_concentration": "microgram_per_meter_cubed",
    "group_count"       : "count",
    "group_data"        : "byte",
    "group_db"          : "dB",
    "group_degree_day"  : "degree_C_day",
    "group_deltatime"   : "second",
    "group_direction"   : "degree_compass",
    "group_distance"    : "km",
    "group_elapsed"     : "second",
    "group_energy"      : "watt_hour",
    "group_energy2"     : "watt_second",
    "group_fraction"    : "ppm",
    "group_frequency"   : "hertz",
    "group_illuminance" : "lux",
    "group_interval"    : "minute",
    "group_length"      : "cm",
    "group_moisture"    : "centibar",
    "group_percent"     : "percent",
    "group_power"       : "watt",
    "group_pressure"    : "mbar",
    "group_pressurerate": "mbar_per_hour",
    "group_radiation"   : "watt_per_meter_squared",
    "group_rain"        : "cm",
    "group_rainrate"    : "cm_per_hour",
    "group_speed"       : "km_per_hour",
    "group_speed2"      : "km_per_hour2",
    "group_temperature" : "degree_C",
    "group_time"        : "unix_epoch",
    "group_uv"          : "uv_index",
    "group_volt"        : "volt",
    "group_volume"      : "liter"
})

# This dictionary maps unit groups to a standard unit type in the 
# "Metric WX" unit system. It's the same as the "Metric" system,
# except for rain and speed:
MetricWXUnits = ListOfDicts(*MetricUnits.maps)
MetricWXUnits.prepend({
    'group_rain': 'mm',
    'group_rainrate' : 'mm_per_hour',
    'group_speed': 'meter_per_second',
    'group_speed2': 'meter_per_second2',
})

std_groups = {
    weewx.US: USUnits,
    weewx.METRIC: MetricUnits,
    weewx.METRICWX: MetricWXUnits
}

# Conversion functions to go from one unit type to another.
conversionDict = {
    'bit'              : {'byte'             : lambda x : x / 8},
    'byte'             : {'bit'              : lambda x : x * 8},
    'cm'               : {'inch'             : lambda x : x / CM_PER_INCH,
                          'mm'               : lambda x : x * 10.0},
    'cm_per_hour'      : {'inch_per_hour'    : lambda x : x * 0.393700787,
                          'mm_per_hour'      : lambda x : x * 10.0},
    'cubic_foot'       : {'gallon'           : lambda x : x * 7.48052,
                          'litre'            : lambda x : x * 28.3168,
                          'liter'            : lambda x : x * 28.3168},
    'day'              : {'second'           : lambda x : x * SECS_PER_DAY,
                          'minute'           : lambda x : x*1440.0,
                          'hour'             : lambda x : x*24.0},
    'degree_C'         : {'degree_F'         : CtoF,
                          'degree_E'         : CtoE,
                          'degree_K'         : CtoK},
    'degree_C_day'     : {'degree_F_day'     : lambda x : x * (9.0/5.0)},
    'degree_E'         : {'degree_C'         : EtoC,
                          'degree_F'         : EtoF},
    'degree_F'         : {'degree_C'         : FtoC,
                          'degree_E'         : FtoE,
                          'degree_K'         : FtoK},
    'degree_F_day'     : {'degree_C_day'     : lambda x : x * (5.0/9.0)},
    'degree_K'         : {'degree_C'         : KtoC,
                          'degreeF'          : KtoF},
    'dublin_jd'        : {'unix_epoch'       : lambda x : (x-25567.5) * SECS_PER_DAY,
                          'unix_epoch_ms'    : lambda x : (x-25567.5) * SECS_PER_DAY * 1000,
                          'unix_epoch_ns'    : lambda x : (x-25567.5) * SECS_PER_DAY * 1e06},
    'foot'             : {'meter'            : lambda x : x * METER_PER_FOOT},
    'gallon'           : {'liter'            : lambda x : x * 3.78541,
                          'litre'            : lambda x : x * 3.78541,
                          'cubic_foot'       : lambda x : x * 0.133681},
    'hour'             : {'second'           : lambda x : x*3600.0,
                          'minute'           : lambda x : x*60.0,
                          'day'              : lambda x : x/24.0},
    'hPa'              : {'inHg'             : lambda x : x * INHG_PER_MBAR,
                          'mmHg'             : lambda x : x * 0.75006168,
                          'mbar'             : lambda x : x,
                          'kPa'              : lambda x : x / 10.0},
    'hPa_per_hour'     : {'inHg_per_hour'    : lambda x : x * INHG_PER_MBAR,
                          'mmHg_per_hour'    : lambda x : x * 0.75006168,
                          'mbar_per_hour'    : lambda x : x,
                          'kPa_per_hour'     : lambda x : x / 10.0},
    'inch'             : {'cm'               : lambda x : x * CM_PER_INCH,
                          'mm'               : lambda x : x * MM_PER_INCH},
    'inch_per_hour'    : {'cm_per_hour'      : lambda x : x * 2.54,
                          'mm_per_hour'      : lambda x : x * 25.4},
    'inHg'             : {'mbar'             : lambda x : x / INHG_PER_MBAR,
                          'hPa'              : lambda x : x / INHG_PER_MBAR,
                          'kPa'              : lambda x : x / INHG_PER_MBAR / 10.0,
                          'mmHg'             : lambda x : x * 25.4},
    'inHg_per_hour'    : {'mbar_per_hour'    : lambda x : x / INHG_PER_MBAR,
                          'hPa_per_hour'     : lambda x : x / INHG_PER_MBAR,
                          'kPa_per_hour'     : lambda x : x / INHG_PER_MBAR / 10.0,
                          'mmHg_per_hour'    : lambda x : x * 25.4},
    'kilowatt'         : {'watt'             : lambda x : x * 1000.0},
    'kilowatt_hour'    : {'mega_joule'       : lambda x : x * 3.6,
                          'watt_second'      : lambda x : x * 3.6e6,
                          'watt_hour'        : lambda x : x * 1000.0},
    'km'               : {'meter'            : lambda x : x * 1000.0,
                          'mile'             : lambda x : x * 0.621371192},
    'km_per_hour'      : {'mile_per_hour'    : kph_to_mph,
                          'knot'             : kph_to_knot,
                          'meter_per_second' : lambda x : x * 0.277777778},
    'knot'             : {'mile_per_hour'    : lambda x : x * 1.15077945,
                          'km_per_hour'      : lambda x : x * 1.85200,
                          'meter_per_second' : lambda x : x * 0.514444444},
    'knot2'             : {'mile_per_hour2'  : lambda x : x * 1.15077945,
                           'km_per_hour2'     : lambda x : x * 1.85200,
                           'meter_per_second2': lambda x : x * 0.514444444},
    'kPa'              : {'inHg'             : lambda x: x * INHG_PER_MBAR * 10.0,
                          'mmHg'             : lambda x: x * 7.5006168,
                          'mbar'             : lambda x: x * 10.0,
                          'hPa'              : lambda x: x * 10.0},
    'kPa_per_hour'     : {'inHg_per_hour'    : lambda x: x * INHG_PER_MBAR * 10.0,
                          'mmHg_per_hour'    : lambda x: x * 7.5006168,
                          'mbar_per_hour'    : lambda x: x * 10.0,
                          'hPa_per_hour'     : lambda x: x * 10.0},
    'liter'            : {'gallon'           : lambda x : x * 0.264172,
                          'cubic_foot'       : lambda x : x * 0.0353147},
    'mbar'             : {'inHg'             : lambda x : x * INHG_PER_MBAR,
                          'mmHg'             : lambda x : x * 0.75006168,
                          'hPa'              : lambda x : x,
                          'kPa'              : lambda x : x / 10.0},
    'mbar_per_hour'    : {'inHg_per_hour'    : lambda x : x * INHG_PER_MBAR,
                          'mmHg_per_hour'    : lambda x : x * 0.75006168,
                          'hPa_per_hour'     : lambda x : x,
                          'kPa_per_hour'     : lambda x : x / 10.0},
    'mega_joule'       : {'kilowatt_hour'    : lambda x : x / 3.6,
                          'watt_hour'        : lambda x : x * 1000000 / 3600,
                          'watt_second'      : lambda x : x * 1000000},
    'meter'            : {'foot'             : lambda x : x / METER_PER_FOOT,
                          'km'               : lambda x : x / 1000.0},
    'meter_per_second' : {'mile_per_hour'    : mps_to_mph,
                          'knot'             : mps_to_knot,
                          'km_per_hour'      : lambda x : x * 3.6},
    'meter_per_second2': {'mile_per_hour2'   : lambda x : x * 2.23693629,
                          'knot2'            : lambda x : x * 1.94384449,
                          'km_per_hour2'     : lambda x : x * 3.6},
    'mile'             : {'km'               : lambda x : x * 1.609344},
    'mile_per_hour'    : {'km_per_hour'      : lambda x : x * 1.609344,
                          'knot'             : mph_to_knot,
                          'meter_per_second' : lambda x : x * 0.44704},
    'mile_per_hour2'   : {'km_per_hour2'     : lambda x : x * 1.609344,
                          'knot2'            : lambda x : x * 0.868976242,
                          'meter_per_second2': lambda x : x * 0.44704},
    'minute'           : {'second'           : lambda x : x * 60.0,
                          'hour'             : lambda x : x / 60.0,
                          'day'              : lambda x : x / 1440.0},
    'mm'               : {'inch'             : lambda x : x / MM_PER_INCH,
                          'cm'               : lambda x : x * 0.10},
    'mm_per_hour'      : {'inch_per_hour'    : lambda x : x * .0393700787,
                          'cm_per_hour'      : lambda x : x * 0.10},
    'mmHg'             : {'inHg'             : lambda x : x / MM_PER_INCH,
                          'mbar'             : lambda x : x / 0.75006168,
                          'hPa'              : lambda x : x / 0.75006168,
                          'kPa'              : lambda x : x / 7.5006168},
    'mmHg_per_hour'    : {'inHg_per_hour'    : lambda x : x / MM_PER_INCH,
                          'mbar_per_hour'    : lambda x : x / 0.75006168,
                          'hPa_per_hour'     : lambda x : x / 0.75006168,
                          'kPa_per_hour'     : lambda x : x / 7.5006168},
    'second'           : {'hour'             : lambda x : x/3600.0,
                          'minute'           : lambda x : x/60.0,
                          'day'              : lambda x : x / SECS_PER_DAY},
    'unix_epoch'       : {'dublin_jd'        : lambda x: x / SECS_PER_DAY + 25567.5,
                          'unix_epoch_ms'    : lambda x : x * 1000,
                          'unix_epoch_ns'    : lambda x : x * 1000000},
    'unix_epoch_ms'    : {'dublin_jd'        : lambda x: x / (SECS_PER_DAY * 1000) + 25567.5,
                          'unix_epoch'       : lambda x : x / 1000,
                          'unix_epoch_ns'    : lambda x : x * 1000},
    'unix_epoch_ns'    : {'dublin_jd'        : lambda x: x / (SECS_PER_DAY * 1e06) + 25567.5,
                          'unix_epoch'       : lambda x : x / 1e06,
                          'unix_epoch_ms'    : lambda x : x / 1000},
    'watt'             : {'kilowatt'         : lambda x : x / 1000.0},
    'watt_hour'        : {'kilowatt_hour'    : lambda x : x / 1000.0,
                          'mega_joule'       : lambda x : x * 0.0036,
                          'watt_second'      : lambda x : x * 3600.0},
    'watt_second'      : {'kilowatt_hour'    : lambda x : x / 3.6e6,
                          'mega_joule'       : lambda x : x / 1000000,
                          'watt_hour'        : lambda x : x / 3600.0},
}


# These used to hold default values for formats and labels, but that has since been moved
# to units.defaults. However, they are still used by modules that extend the unit system
# programmatically.
default_unit_format_dict = {}
default_unit_label_dict = {}

DEFAULT_DELTATIME_FORMAT = "%(day)d%(day_label)s, " \
                           "%(hour)d%(hour_label)s, " \
                           "%(minute)d%(minute_label)s"

# Default mapping from compass degrees to ordinals
DEFAULT_ORDINATE_NAMES = [
    'N', 'NNE','NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
    'S', 'SSW','SW', 'WSW', 'W', 'WNW', 'NW', 'NNW',
    'N/A'
]

complex_conversions = {
    'x': lambda c: c.real if c is not None else None,
    'y': lambda c: c.imag if c is not None else None,
    'magnitude': lambda c: abs(c) if c is not None else None,
    'direction': weeutil.weeutil.dirN,
    'polar': lambda c: weeutil.weeutil.Polar.from_complex(c) if c is not None else None,
}

class ValueTuple(tuple):
    """
    A value, along with the unit it is in, can be represented by a 3-way tuple called a value
    tuple. All weewx routines can accept a simple unadorned 3-way tuple as a value tuple, but they
    return the type ValueTuple. It is useful because its contents can be accessed using named
    attributes.

    Item   attribute   Meaning
       0    value      The data value(s). Can be a series (eg, [20.2, 23.2, ...])
                       or a scalar (eg, 20.2).
       1    unit       The unit it is in ("degree_C")
       2    group      The unit group ("group_temperature")

    It is valid to have a datum value of None.

    It is also valid to have a unit type of None (meaning there is no information about the unit
    the value is in). In this case, you won't be able to convert it to another unit.
    """
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
            raise TypeError("Unsupported operand error for subtraction: %s and %s"
                            % (self[1], other[1]))
        return ValueTuple(self[0] - other[0], self[1], self[2])

    def __add__(self, other):
        if self[1] != other[1] or self[2] != other[2]:
            raise TypeError("Unsupported operand error for addition: %s and %s"
                            % (self[1], other[1]))
        return ValueTuple(self[0] + other[0], self[1], self[2])


#==============================================================================
#                        class Formatter
#==============================================================================

class Formatter(object):
    """Holds formatting information for the various unit types. """

    def __init__(self, unit_format_dict = None,
                 unit_label_dict  = None,
                 time_format_dict = None,
                 ordinate_names   = None,
                 deltatime_format_dict = None):
        """

        Args:
            unit_format_dict (dict):  Key is unit type (e.g., 'inHg'), value is a
                string format (e.g., "%.1f")
            unit_label_dict (dict): Key is unit type (e.g., 'inHg'), value is a
                label (e.g., " inHg")
            time_format_dict (dict): Key is a context (e.g., 'week'), value is a
                strftime format (e.g., "%d-%b-%Y %H:%M").
            ordinate_names(list): A list containing ordinal compass names (e.g., ['N', 'NNE', etc.]
            deltatime_format_dict (dict): Key is a context (e.g., 'week'), value is a deltatime
                format string (e.g., "%(minute)d%(minute_label)s, %(second)d%(second_label)s")
        """

        self.unit_format_dict = unit_format_dict or {}
        self.unit_label_dict  = unit_label_dict or {}
        self.time_format_dict = time_format_dict or {}
        self.ordinate_names    = ordinate_names or DEFAULT_ORDINATE_NAMES
        self.deltatime_format_dict = deltatime_format_dict or {}

    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        try:
            unit_format_dict = skin_dict['Units']['StringFormats']
        except KeyError:
            unit_format_dict = {}

        try:
            unit_label_dict = skin_dict['Units']['Labels']
        except KeyError:
            unit_label_dict = {}

        try:
            time_format_dict = skin_dict['Units']['TimeFormats']
        except KeyError:
            time_format_dict = {}

        try:
            ordinate_names = weeutil.weeutil.option_as_list(
                skin_dict['Units']['Ordinates']['directions'])
        except KeyError:
            ordinate_names = {}

        try:
            deltatime_format_dict = skin_dict['Units']['DeltaTimeFormats']
        except KeyError:
            deltatime_format_dict = {}

        return Formatter(unit_format_dict,
                         unit_label_dict,
                         time_format_dict,
                         ordinate_names,
                         deltatime_format_dict)

    def get_format_string(self, unit):
        """Return a suitable format string."""

        # First, try the (misnamed) custom unit format dictionary
        if unit in default_unit_format_dict:
            return default_unit_format_dict[unit]
        # If that didn't work, try my internal format dictionary
        elif unit in self.unit_format_dict:
            return self.unit_format_dict[unit]
        else:
            # Can't find one. Return a generic formatter:
            return '%f'

    def get_label_string(self, unit, plural=True):
        """Return a suitable label.
        
        This function looks up a suitable label in the unit_label_dict. If the
        associated value is a string, it returns it. If it is a tuple or a list,
        then it is assumed the first value is a singular version of the label
        (e.g., "foot"), the second a plural version ("feet"). If the parameter
        plural=False, then the singular version is returned. Otherwise, the
        plural version.
        """

        # First, try the (misnamed) custom dictionary
        if unit in default_unit_label_dict:
            label = default_unit_label_dict[unit]
        # Then try my internal label dictionary:
        elif unit in self.unit_label_dict:
            label = self.unit_label_dict[unit]
        else:
            # Can't find a label. Just return an empty string:
            return u''

        # Is the label a tuple or list?
        if isinstance(label, (tuple, list)):
            # Yes. Return the singular or plural version as requested
            return label[1] if plural and len(label) > 1 else label[0]
        else:
            # No singular/plural version. It's just a string. Return it.
            return label

    def toString(self, val_t, context='current', addLabel=True,
                 useThisFormat=None, None_string=None,
                 localize=True):
        """Format the value as a unicode string.

        Args:
            val_t (ValueTuple): A ValueTuple holding the value to be formatted. The value can be an iterable.
            context (str): A time context (eg, 'day').
                [Optional. If not given, context 'current' will be used.]
            addLabel (bool):  True to add a unit label (eg, 'mbar'), False to not.
                [Optional. If not given, a label will be added.]
            useThisFormat (str): An optional string or strftime format to be used.
                [Optional. If not given, the format given in the initializer will be used.]
            None_string (str): A string to be used if the value val is None.
                [Optional. If not given, the string given by unit_format_dict['NONE']
                will be used.]
            localize (bool): True to localize the results. False otherwise.

        Returns:
            str. The localized, formatted, and labeled value.
        """

        # Check to see if the ValueTuple holds an iterable:
        if is_iterable(val_t[0]):
            # Yes. Format each element individually, then stick them all together.
            s_list = [self._to_string((v, val_t[1], val_t[2]),
                                      context, addLabel, useThisFormat, None_string, localize)
                      for v in val_t[0]]
            s = ", ".join(s_list)
        else:
            # The value is a simple scalar.
            s = self._to_string(val_t, context, addLabel, useThisFormat, None_string, localize)

        return s

    def _to_string(self, val_t, context='current', addLabel=True,
                   useThisFormat=None, None_string=None,
                   localize=True):
        """Similar to the function toString(), except that the value in val_t must be a
        simple scalar."""

        if val_t is None or val_t[0] is None:
            if None_string is None:
                val_str = self.unit_format_dict.get('NONE', u'N/A')
            else:
                # Make sure the "None_string" is, in fact, a string
                if isinstance(None_string, six.string_types):
                    val_str = None_string
                else:
                    # Coerce to a string.
                    val_str = str(None_string)
            addLabel = False
        elif type(val_t[0]) is complex:
            # The type is complex. Break it up into real and imaginary, then format
            # them separately. No label --- it will get added later
            r = ValueTuple(val_t[0].real, val_t[1], val_t[2])
            i = ValueTuple(val_t[0].imag, val_t[1], val_t[2])
            val_str = "(%s, %s)" % (self._to_string(r, context, False,
                                                    useThisFormat, None_string, localize),
                                    self._to_string(i, context, False,
                                                    useThisFormat, None_string, localize))
        elif type(val_t[0]) is Polar:
            # The type is a Polar number. Break it up into magnitude and direction, then format
            # them separately.
            mag = ValueTuple(val_t[0].mag, val_t[1], val_t[2])
            dir = ValueTuple(val_t[0].dir, "degree_compass", "group_direction")
            val_str = "(%s, %s)" % (self._to_string(mag, context, addLabel,
                                                    useThisFormat, None_string, localize),
                                    self._to_string(dir, context, addLabel,
                                                    None, None_string, localize))
            addLabel = False
        elif val_t[1] in {"unix_epoch", "unix_epoch_ms", "unix_epoch_ns"}:
            # Different formatting routines are used if the value is a time.
            t = val_t[0]
            if val_t[1] == "unix_epoch_ms":
                t /= 1000.0
            elif val_t[1] == "unix_epoch_ns":
                t /= 1000000.0
            if useThisFormat is None:
                val_str = time.strftime(self.time_format_dict.get(context, "%d-%b-%Y %H:%M"),
                                        time.localtime(t))
            else:
                val_str = time.strftime(useThisFormat, time.localtime(t))
            addLabel = False
        else:
            # It's not a time. It's a regular value. Get a suitable format string:
            if useThisFormat is None:
                # No user-specified format string. Go get one:
                format_string = self.get_format_string(val_t[1])
            else:
                # User has specified a string. Use it.
                format_string = useThisFormat
            if localize:
                # Localization requested. Use locale with the supplied format:
                val_str = locale.format_string(format_string, val_t[0])
            else:
                # No localization. Just format the string.
                val_str = format_string % val_t[0]

        # Make sure the results are in unicode:
        val_ustr = six.ensure_text(val_str)

        # Add a label, if requested:
        if addLabel:
            # Make sure the label is in unicode before tacking it on to the end
            label = self.get_label_string(val_t[1], plural=(not val_t[0]==1))
            val_ustr += six.ensure_text(label)

        return val_ustr

    def to_ordinal_compass(self, val_t):
        if val_t[0] is None:
            return self.ordinate_names[-1]
        _sector_size = 360.0 / (len(self.ordinate_names)-1)
        _degree = (val_t[0] + _sector_size/2.0) % 360.0
        _sector = int(_degree / _sector_size)
        return self.ordinate_names[_sector]

    def long_form(self, val_t, context, format_string=None, None_string=None):
        """Format a delta time using the long-form.

        Args:
            val_t (ValueTuple): a ValueTuple holding the delta time.
            context (str): The time context. Something like 'day', 'current', etc.
            format_string (str|None): An optional custom format string. Otherwise, an appropriate
                string will be looked up in deltatime_format_dict.
        Returns
            str: The results formatted in a "long-form" time. This is something like
                "2 hours, 14 minutes, 21 seconds".
        """
        # Get a delta-time format string. Use a default if the user did not supply one:
        if not format_string:
            format_string = self.deltatime_format_dict.get(context, DEFAULT_DELTATIME_FORMAT)
        # Now format the delta time, using the function delta_time_to_string:
        val_str = self.delta_time_to_string(val_t, format_string, None_string)
        return val_str

    def delta_time_to_string(self, val_t, label_format, None_string=None):
        """Format elapsed time as a string

        Args:
            val_t (ValueTuple): A ValueTuple containing the elapsed time.
            label_format (str): The formatting string.

        Returns:
            str: The formatted time as a string.
        """
        if val_t is None or val_t[0] is None:
            if None_string is None:
                val_str = self.unit_format_dict.get('NONE', u'N/A')
            else:
                # Make sure the "None_string" is, in fact, a string
                if isinstance(None_string, six.string_types):
                    val_str = None_string
                else:
                    # Coerce to a string.
                    val_str = str(None_string)
            return val_str
        secs = convert(val_t, 'second')[0]
        etime_dict = {}
        secs = abs(secs)
        for (label, interval) in (('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)):
            amt = int(secs // interval)
            etime_dict[label] = amt
            etime_dict[label + '_label'] = self.get_label_string(label, not amt == 1)
            secs %= interval
        if 'day' not in label_format:
            # If 'day' does not appear in the formatting string, add its time to hours
            etime_dict['hour'] += 24 * etime_dict['day']
        ans = locale.format_string(label_format, etime_dict)
        return ans

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
        >>> print("%.3f %s %s" % c.convert(p_m))
        30.017 inHg group_pressure
        
        Try an unspecified unit type:
        >>> p2 = (1016.5, None, None)
        >>> print(c.convert(p2))
        (1016.5, None, None)
        
        Try a bad unit type:
        >>> p3 = (1016.5, 'foo', 'group_pressure')
        >>> try:
        ...     print(c.convert(p3))
        ... except KeyError:
        ...     print("Exception thrown")
        Exception thrown
        
        Try a bad group type:
        >>> p4 = (1016.5, 'mbar', 'group_foo')
        >>> try:
        ...     print(c.convert(p4))
        ... except KeyError:
        ...     print("Exception thrown")
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
            'usUnits': weewx.METRIC, 'barometer':1015.9166, 'interval':15}
        >>> target_dict = c.convertDict(source_dict)
        >>> print("dateTime: %d, interval: %d, barometer: %.3f, outTemp: %.3f" %\
        (target_dict['dateTime'], target_dict['interval'], \
         target_dict['barometer'], target_dict['outTemp']))
        dateTime: 194758100, interval: 15, barometer: 30.000, outTemp: 68.000
        """
        target_dict = {}
        for obs_type in obs_dict:
            if obs_type == 'usUnits': continue
            # Do the conversion, but keep only the first value in
            # the ValueTuple:
            target_dict[obs_type] = self.convert(as_value_tuple(obs_dict, obs_type))[0]
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
        if unit_group in self.group_unit_dict:
            unit_type = self.group_unit_dict[unit_group]
        else:
            unit_type = USUnits.get(unit_group)
        return (unit_type, unit_group)

#==============================================================================
#                         Standard Converters
#==============================================================================

# This dictionary holds converters for the standard unit conversion systems. 
StdUnitConverters = {weewx.US       : Converter(USUnits),
                     weewx.METRIC   : Converter(MetricUnits),
                     weewx.METRICWX : Converter(MetricWXUnits)}


#==============================================================================
#                      class ValueHelper
#==============================================================================

class ValueHelper(object):
    """A helper class that binds a value tuple together with everything needed to do a
    context sensitive formatting """
    def __init__(self, value_t, context='current', formatter=Formatter(), converter=None):
        """Initialize a ValueHelper

        Args:
            value_t (ValueTuple or UnknownType): This parameter can be either a ValueTuple,
                or an instance of UnknownType. If a ValueTuple, the "value" part can be either a
                scalar, or a series. If a converter is given, it will be used to convert the
                ValueTuple before storing. If the parameter is 'UnknownType', it is an error ot
                perform any operation on the resultant ValueHelper, except ask it to be formatted
                as a string. In this case, the name of the unknown type will be included in the
                resultant string.
            context (str): The time context. Something like 'current', 'day', 'week'.
                [Optional. If not given, context 'current' will be used.]
            formatter (Formatter): An instance of class Formatter.
                [Optional. If not given, then the default Formatter() will be used]
            converter (Converter):  An instance of class Converter.
                [Optional.]
        """
        # If there's a converter, then perform the conversion:
        if converter and not isinstance(value_t, UnknownType):
            self.value_t = converter.convert(value_t)
        else:
            self.value_t = value_t
        self.context   = context
        self.formatter = formatter

    def toString(self,
                 addLabel=True,
                 useThisFormat=None,
                 None_string=None,
                 localize=True,
                 NONE_string=None):
        """Convert my internally held ValueTuple to a unicode string, using the supplied
        converter and formatter.

        Args:
            addLabel (bool):  If True, add a unit label
            useThisFormat (str):  String with a format to be used when formatting the value.
                If None, then a format will be supplied. Default is None.
            None_string (str): A string to be used if the value is None. If None, then a default
                string from skin.conf will be used. Default is None.
            localize (bool):  If True, localize the results. Default is True
            NONE_string (str): Supplied for backwards compatibility. Identical semantics to
                None_string.

        Returns:
            str. The formatted and labeled string
        """
        # If the type is unknown, then just return an error string:
        if isinstance(self.value_t, UnknownType):
            return u"?'%s'?" % self.value_t.obs_type
        # Check NONE_string for backwards compatibility:
        if None_string is None and NONE_string is not None:
            None_string = NONE_string
        # Then do the format conversion:
        s = self.formatter.toString(self.value_t, self.context, addLabel=addLabel,
                                    useThisFormat=useThisFormat, None_string=None_string,
                                    localize=localize)
        return s

    def __str__(self):
        """Return as the native string type for the version of Python being run."""
        s = self.toString()
        return six.ensure_str(s)

    def __unicode__(self):
        """Return as unicode. This function is called only under Python 2."""
        return self.toString()

    def format(self, format_string=None, None_string=None, add_label=True, localize=True):
        """Returns a formatted version of the datum, using user-supplied customizations."""
        return self.toString(useThisFormat=format_string, None_string=None_string,
                             addLabel=add_label, localize=localize)

    def ordinal_compass(self):
        """Returns an ordinal compass direction (eg, 'NNW')"""
        # Get the raw value tuple, then ask the formatter to look up an
        # appropriate ordinate:
        return self.formatter.to_ordinal_compass(self.value_t)

    def long_form(self, format_string=None, None_string=None):
        """Format a delta time"""
        return self.formatter.long_form(self.value_t,
                                        context=self.context,
                                        format_string=format_string,
                                        None_string=None_string)

    def json(self, **kwargs):
        return json.dumps(self.raw, cls=ComplexEncoder, **kwargs)

    def round(self, ndigits=None):
        """Round the data part to ndigits decimal digits."""
        # Create a new ValueTuple with the rounded data
        vt = ValueTuple(weeutil.weeutil.rounder(self.value_t[0], ndigits),
                        self.value_t[1],
                        self.value_t[2])
        # Use it to create a new ValueHelper
        return ValueHelper(vt, self.context, self.formatter)

    @property
    def raw(self):
        """Returns just the data part, without any formatting."""
        return self.value_t[0]

    def convert(self, target_unit):
        """Return a ValueHelper in a new target unit.

        Args:
            target_unit (str): The unit (eg, 'degree_C') to which the data will be converted

        Returns:
            ValueHelper.
        """
        value_t = convert(self.value_t, target_unit)
        return ValueHelper(value_t, self.context, self.formatter)

    def __getattr__(self, target_unit):
        """Convert to a new unit type.

        Args:
            target_unit (str): The new target unit

        Returns:
            ValueHelper. The data in the new ValueHelper will be in the desired units.
        """

        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if target_unit in ['__call__', 'has_key']:
            raise AttributeError

        # Convert any illegal conversions to an AttributeError:
        try:
            converted = self.convert(target_unit)
        except KeyError:
            raise AttributeError("Illegal conversion from '%s' to '%s'"
                                 % (self.value_t[1], target_unit))
        return converted

    def __iter__(self):
        """Return an iterator that can iterate over the elements of self.value_t."""
        for row in self.value_t[0]:
            # Form a ValueTuple using the value, plus the unit and unit group
            vt = ValueTuple(row, self.value_t[1], self.value_t[2])
            # Form a ValueHelper out of that
            vh = ValueHelper(vt, self.context, self.formatter)
            yield vh

    def exists(self):
        return not isinstance(self.value_t, UnknownType)

    def has_data(self):
        return self.exists() and self.value_t[0] is not None

    # Backwards compatibility
    def string(self, None_string=None):
        """Return as string with an optional user specified string to be used if None.
        DEPRECATED."""
        return self.toString(None_string=None_string)

    # Backwards compatibility
    def nolabel(self, format_string, None_string=None):
        """Returns a formatted version of the datum, using a user-supplied format. No label.
        DEPRECATED."""
        return self.toString(addLabel=False, useThisFormat=format_string, None_string=None_string)

    # Backwards compatibility
    @property
    def formatted(self):
        """Return a formatted version of the datum. No label.
        DEPRECATED."""
        return self.toString(addLabel=False)


#==============================================================================
#                        SeriesHelper
#==============================================================================

class SeriesHelper(object):
    """Convenience class that binds the series data, along with start and stop times."""

    def __init__(self, start, stop, data):
        """Initializer

        Args:
            start (ValueHelper): A ValueHelper holding the start times of the data. None if
                there is no start series.
            stop (ValueHelper): A ValueHelper holding the stop times of the data. None if
                there is no stop series
            data (ValueHelper): A ValueHelper holding the data.
        """
        self.start = start
        self.stop = stop
        self.data = data

    def json(self, order_by='row', **kwargs):
        """Return the data in this series as JSON.

        Args:
            order_by (str): A string that determines whether the generated string is ordered by
                row or column. Either 'row' or 'column'.
            **kwargs (Any): Any extra arguments are passed on to json.loads()

        Returns:
            str. A string with the encoded JSON.
        """

        if order_by == 'row':
            if self.start and self.stop:
                json_data = list(zip(self.start.raw, self.stop.raw, self.data.raw))
            elif self.start and not self.stop:
                json_data = list(zip(self.start.raw, self.data.raw))
            else:
                json_data = list(zip(self.stop.raw, self.data.raw))
        elif order_by == 'column':
            if self.start and self.stop:
                json_data = [self.start.raw, self.stop.raw, self.data.raw]
            elif self.start and not self.stop:
                json_data = [self.start.raw, self.data.raw]
            else:
                json_data = [self.stop.raw, self.data.raw]
        else:
            raise ValueError("Unknown option '%s' for parameter 'order_by'" % order_by)

        return json.dumps(json_data, cls=ComplexEncoder, **kwargs)

    def round(self, ndigits=None):
        """
        Round the data part to ndigits number of decimal digits.

        Args:
            ndigits (int): The number of decimal digits to include in the data. Default is None,
                which means keep all digits.

        Returns:
            SeriesHelper: A new SeriesHelper, with the data part rounded to the requested number of
                decimal digits.
        """
        return SeriesHelper(self.start, self.stop, self.data.round(ndigits))

    def __str__(self):
        """Return as the native string type for the version of Python being run."""
        s = self.format()
        return six.ensure_str(s)

    def __unicode__(self):
        """Return as unicode. This function is called only under Python 2."""
        return self.format()

    def __len__(self):
        return len(self.start)

    def format(self, format_string=None, None_string=None, add_label=True,
               localize=True, order_by='row'):
        """Format a series as a string.

        Args:
            format_string (str):  String with a format to be used when formatting the values.
                If None, then a format will be supplied. Default is None.
            None_string (str): A string to be used if a value is None. If None,
                then a default string from skin.conf will be used. Default is None.
            add_label (bool):  If True, add a unit label to each value.
            localize (bool):  If True, localize the results. Default is True
            order_by (str): A string that determines whether the generated string is ordered by
                row or column. Either 'row' or 'column'.

        Returns:
            str. The formatted and labeled string
        """

        if order_by == 'row':
            rows = []
            if self.start and self.stop:
                for start_, stop_, data_ in self:
                    rows += ["%s, %s, %s"
                             % (str(start_),
                                str(stop_),
                                data_.format(format_string, None_string, add_label, localize))
                    ]
            elif self.start and not self.stop:
                for start_, data_ in zip(self.start, self.data):
                    rows += ["%s, %s"
                             % (str(start_),
                                data_.format(format_string, None_string, add_label, localize))
                    ]
            else:
                for stop_, data_ in zip(self.stop, self.data):
                    rows += ["%s, %s"
                             % (str(stop_),
                                data_.format(format_string, None_string, add_label, localize))
                    ]
            return "\n".join(rows)

        elif order_by == 'column':
            if self.start and self.stop:
                return "%s\n%s\n%s" \
                       % (str(self.start),
                          str(self.stop),
                          self.data.format(format_string, None_string, add_label, localize))
            elif self.start and not self.stop:
                return "%s\n%s" \
                       % (str(self.start),
                          self.data.format(format_string, None_string, add_label, localize))
            else:
                return "%s\n%s" \
                       % (str(self.stop),
                          self.data.format(format_string, None_string, add_label, localize))
        else:
            raise ValueError("Unknown option '%s' for parameter 'order_by'" % order_by)

    def __getattr__(self, target_unit):
        """Return a new SeriesHelper, with the data part converted to a new unit

        Args:
            target_unit (str): The data part of the returned SeriesHelper will be in this unit.

        Returns:
            SeriesHelper. The data in the new SeriesHelper will be in the target unit.
        """

        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if target_unit in ['__call__', 'has_key']:
            raise AttributeError

        # This will be a ValueHelper.
        converted_data = self.data.convert(target_unit)

        return SeriesHelper(self.start, self.stop, converted_data)

    def __iter__(self):
        """Iterate over myself by row."""
        for start, stop, data in zip(self.start, self.stop, self.data):
            yield start, stop, data

#==============================================================================
#                       class UnitInfoHelper and friends
#==============================================================================

class UnitHelper(object):
    def __init__(self, converter):
        self.converter = converter
    def __getattr__(self, obs_type):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError
        return self.converter.getTargetUnit(obs_type)[0]

class FormatHelper(object):
    def __init__(self, formatter, converter):
        self.formatter = formatter
        self.converter = converter
    def __getattr__(self, obs_type):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError
        return get_format_string(self.formatter, self.converter, obs_type)

class LabelHelper(object):
    def __init__(self, formatter, converter):
        self.formatter = formatter
        self.converter = converter
    def __getattr__(self, obs_type):
        # This is to get around bugs in the Python version of Cheetah's namemapper:
        if obs_type in ['__call__', 'has_key']:
            raise AttributeError
        return get_label_string(self.formatter, self.converter, obs_type)

class UnitInfoHelper(object):
    """Helper class used for for the $unit template tag."""
    def __init__(self, formatter, converter):
        """
        formatter: an instance of Formatter
        converter: an instance of Converter
        """
        self.unit_type = UnitHelper(converter)
        self.format    = FormatHelper(formatter, converter)
        self.label     = LabelHelper(formatter, converter)
        self.group_unit_dict = converter.group_unit_dict

    # This is here for backwards compatibility:
    @property
    def unit_type_dict(self):
        return self.group_unit_dict


class ObsInfoHelper(object):
    """Helper class to implement the $obs template tag."""
    def __init__(self, skin_dict):
        try:
            d = skin_dict['Labels']['Generic']
        except KeyError:
            d = {}
        self.label = weeutil.weeutil.KeyDict(d)


#==============================================================================
#                             Helper functions
#==============================================================================
def getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group
    does it belong to?

    Examples:
        +-------------+-----------+---------------------+
        | obs_type    | agg_type  | Returns             |
        +=============+===========+=====================+
        | 'outTemp'   | None      | 'group_temperature' |
        +-------------+-----------+---------------------+
        | 'outTemp'   | 'min'     | 'group_temperature' |
        +-------------+-----------+---------------------+
        | 'outTemp'   | 'mintime' | 'group_time'        |
        +-------------+-----------+---------------------+
        | 'wind'      | 'avg'     | 'group_speed'       |
        +-------------+-----------+---------------------+
        | 'wind'      | 'vecdir'  | 'group_direction'   |
        +-------------+-----------+---------------------+

    Args:
        obs_type (str): An observation type (eg, 'barometer')
        agg_type (str): An aggregation (eg, 'mintime', or 'avg'.)

    Returns:
        str or None. The unit group or None if it cannot be determined.
    """
    if agg_type and agg_type in agg_group:
        return agg_group[agg_type]
    else:
        return obs_group_dict.get(obs_type)


# For backwards compatibility:
_getUnitGroup = getUnitGroup


def convert(val_t, target_unit):
    """Convert a ValueTuple to a new unit

    Args:
        val_t (ValueTuple): A ValueTuple containing the value to be converted. The first element
            can be either a scalar or an iterable.
        target_unit (str): The unit type (e.g., "meter", or "mbar") to which the value is to be
         converted. If the ValueTuple holds a complex number, target_unit can be a complex
         conversion nickname, such as 'polar'.

    Returns:
        ValueTuple. An instance of ValueTuple, where the desired conversion has been performed.
    """

    # Is the "target_unit" really a conversion for complex numbers?
    if target_unit in complex_conversions:
        # Yes. Get the conversion function. Also, note that these operations do not change the
        # unit the ValueTuple is in.
        conversion_func = complex_conversions[target_unit]
        target_unit = val_t[1]
    else:
        # We are converting between units. If the value is already in the target unit type, then
        # just return it:
        if val_t[1] == target_unit:
            return val_t

        # Retrieve the conversion function. An exception of type KeyError
        # will occur if the target or source units are invalid
        try:
            conversion_func = conversionDict[val_t[1]][target_unit]
        except KeyError:
            log.debug("Unable to convert from %s to %s", val_t[1], target_unit)
            raise
    # Are we converting a list, or a simple scalar?
    if isinstance(val_t[0], (list, tuple)):
        # A list
        new_val = [conversion_func(x) if x is not None else None for x in val_t[0]]
    else:
        # A scalar
        new_val = conversion_func(val_t[0]) if val_t[0] is not None else None

    # Add on the unit type and the group type and return the results:
    return ValueTuple(new_val, target_unit, val_t[2])


def convertStd(val_t, target_std_unit_system):
    """Convert a value tuple to an appropriate unit in a target standardized
    unit system
    
    Example:
        >>> value_t = (30.02, 'inHg', 'group_pressure')
        >>> print("(%.2f, %s, %s)" % convertStd(value_t, weewx.METRIC))
        (1016.59, mbar, group_pressure)
        >>> value_t = (1.2, 'inch', 'group_rain')
        >>> print("(%.2f, %s, %s)" % convertStd(value_t, weewx.METRICWX))
        (30.48, mm, group_rain)
    Args:
        val_t (ValueTuple): The ValueTuple to be converted.
        target_std_unit_system (int):  A standardized WeeWX unit system (weewx.US, weewx.METRIC,
            or weewx.METRICWX)

    Returns:
        ValueTuple. A value tuple in the given standardized unit system.
    """
    return StdUnitConverters[target_std_unit_system].convert(val_t)

def convertStdName(val_t, target_nickname):
    """Convert to a target standard unit system, using the unit system's nickname"""
    return convertStd(val_t, unit_constants[target_nickname.upper()])

def getStandardUnitType(target_std_unit_system, obs_type, agg_type=None):
    """Given a standard unit system (weewx.US, weewx.METRIC, weewx.METRICWX),
    an observation type, and an aggregation type, what units would it be in?

    Examples:
        >>> print(getStandardUnitType(weewx.US,     'barometer'))
        ('inHg', 'group_pressure')
        >>> print(getStandardUnitType(weewx.METRIC, 'barometer'))
        ('mbar', 'group_pressure')
        >>> print(getStandardUnitType(weewx.US, 'barometer', 'mintime'))
        ('unix_epoch', 'group_time')
        >>> print(getStandardUnitType(weewx.METRIC, 'barometer', 'avg'))
        ('mbar', 'group_pressure')
        >>> print(getStandardUnitType(weewx.METRIC, 'wind', 'rms'))
        ('km_per_hour', 'group_speed')
        >>> print(getStandardUnitType(None, 'barometer', 'avg'))
        (None, None)

    Args:
        target_std_unit_system (int): A standardized unit system. If None, then
            the the output units are indeterminate, so (None, None) is returned.

        obs_type (str): An observation type, e.g., 'outTemp'

        agg_type (str): An aggregation type, e.g., 'mintime', or 'avg'.
    
    Returns:
         tuple. A 2-way tuple containing the target units, and the target group.
    """

    if target_std_unit_system is not None:
        return StdUnitConverters[target_std_unit_system].getTargetUnit(obs_type, agg_type)
    else:
        return None, None


def get_format_string(formatter, converter, obs_type):
    # First convert to the target unit type:
    u = converter.getTargetUnit(obs_type)[0]
    # Then look up the format string for that unit type:
    return formatter.get_format_string(u)


def get_label_string(formatter, converter, obs_type, plural=True):
    # First convert to the target unit type:    
    u = converter.getTargetUnit(obs_type)[0]
    # Then look up the label for that unit type:
    return formatter.get_label_string(u, plural)


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
    >>> # First, try the raw generator function. Output should be in US
    >>> for _out in genfunc():
    ...    print("Timestamp: %d; Temperature: %.2f; Unit system: %d"
    ...        % (_out['dateTime'], _out['outTemp'], _out['usUnits']))
    Timestamp: 194758100; Temperature: 68.00; Unit system: 1
    Timestamp: 194758400; Temperature: 69.80; Unit system: 1
    Timestamp: 194758700; Temperature: 71.60; Unit system: 1
    >>> # Now do it again, but with the generator function wrapped by GenWithConvert:
    >>> for _out in GenWithConvert(genfunc(), weewx.METRIC):
    ...    print("Timestamp: %d; Temperature: %.2f; Unit system: %d"
    ...        % (_out['dateTime'], _out['outTemp'], _out['usUnits']))
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

    def __next__(self):
        _record = next(self.input_generator)
        if self.target_unit_system is None:
            return _record
        else:
            return to_std_system(_record, self.target_unit_system)

    # For Python 2:
    next = __next__


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


def as_value_tuple(record_dict, obs_type):
    """Look up an observation type in a record, returning the result as a ValueTuple.

    Args:
        record_dict (dict): A record. May be None. If it is not None, then it must contain an
            entry for `usUnits`.
        obs_type (str): The observation type to be returned

    Returns:
        ValueTuple.

    Raises:
        KeyIndex, If the observation type cannot be found in the record, a KeyIndex error is
            raised.
    """

    # Is the record None?
    if record_dict is None:
        # Yes. Signal a value of None and, arbitrarily, pick the US unit system:
        val = None
        std_unit_system = weewx.US
    else:
        # There is a record. Get the value, and the unit system.
        val = record_dict[obs_type]
        std_unit_system = record_dict['usUnits']

    # Given this standard unit system, what is the unit type of this
    # particular observation type? If the observation type is not recognized,
    # a unit_type of None will be returned
    (unit_type, unit_group) = StdUnitConverters[std_unit_system].getTargetUnit(obs_type)

    # Form the value-tuple and return it:
    return ValueTuple(val, unit_type, unit_group)


class ComplexEncoder(json.JSONEncoder):
    """Custom encoder that knows how to encode complex and polar objects"""
    def default(self, obj):
        if isinstance(obj, complex):
            # Return as tuple
            return obj.real, obj.imag
        elif isinstance(obj, Polar):
            # Return as tuple:
            return obj.mag, obj.dir
        # Otherwise, let the base class handle it
        return json.JSONEncoder.default(self, obj)


def get_default_formatter():
    """Get a default formatter. Useful for the test suites."""
    import weewx.defaults
    weewx.defaults.defaults.interpolation = False
    formatter = Formatter(
        unit_format_dict=weewx.defaults.defaults['Units']['StringFormats'],
        unit_label_dict=weewx.defaults.defaults['Units']['Labels'],
        time_format_dict=weewx.defaults.defaults['Units']['TimeFormats'],
        ordinate_names=weewx.defaults.defaults['Units']['Ordinates']['directions'],
        deltatime_format_dict=weewx.defaults.defaults['Units']['DeltaTimeFormats']
    )
    return formatter


if __name__ == "__main__":
    if not six.PY3:
        exit("units.py doctest must be run under Python 3")
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
