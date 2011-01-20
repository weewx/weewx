#
#    Copyright (c) 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Data structures for unit conversions."""

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
                  "uv_index"           : "group_uv",
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
                 "group_uv"           : "uv_index",
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
                 "group_uv"           : "uv_index",
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

# Default base temperature and unit type for heating and cooling degree days
# as a value tuple
default_heatbase = (65.0, "degree_F")
default_coolbase = (65.0, "degree_F")

#===============================================================================
# If the user wants to modify the above dictionaries (for example,
# by adding a new unit type to them), then s/he can do so in a module named
# user.unitdicts. If it doesn't exist, pass on the exception.
#===============================================================================
try:
    import user.unitdicts
except:
    pass
