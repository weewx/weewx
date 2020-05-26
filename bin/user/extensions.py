#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""User extensions module

This module is imported from the main executable, so anything put here will be
executed before anything else happens. This makes it a good place to put user
extensions.
"""

import locale
import os
# This will use the locale specified by the environment variable 'LANG'
# Other options are possible. See:
# http://docs.python.org/2/library/locale.html#locale.setlocale
if 'LANG' not in os.environ:
    os.environ['LANG'] = 'en_AU'
locale.setlocale(locale.LC_ALL, 'en_AU')

import weewx.units

# fix the misspelt metric "metre" ("litre" already fixed in 4.0.0)
#
# conversionDict
weewx.units.conversionDict['metre'] = weewx.units.conversionDict['meter']
weewx.units.conversionDict['metre']['meter'] = lambda x: x
weewx.units.conversionDict['meter']['metre'] = lambda x: x
weewx.units.conversionDict['km']['metre'] = weewx.units.conversionDict['km']['meter']
weewx.units.conversionDict['foot']['metre'] = weewx.units.conversionDict['foot']['meter']
weewx.units.conversionDict['metre_per_second'] = \
    weewx.units.conversionDict['meter_per_second']
weewx.units.conversionDict['metre_per_second']['meter_per_second'] = lambda x: x
weewx.units.conversionDict['meter_per_second']['metre_per_second'] = lambda x: x
weewx.units.conversionDict['metre_per_second2'] = \
    weewx.units.conversionDict['meter_per_second2']
weewx.units.conversionDict['metre_per_second2']['meter_per_second2'] = lambda x: x
weewx.units.conversionDict['meter_per_second2']['metre_per_second2'] = lambda x: x
weewx.units.conversionDict['km_per_hour']['metre_per_second'] = \
    weewx.units.conversionDict['km_per_hour']['meter_per_second']
weewx.units.conversionDict['mile_per_hour']['metre_per_second'] = \
    weewx.units.conversionDict['mile_per_hour']['meter_per_second']
weewx.units.conversionDict['mile_per_hour2']['metre_per_second2'] = \
    weewx.units.conversionDict['mile_per_hour2']['meter_per_second2']
weewx.units.conversionDict['knot']['metre_per_second'] = \
    weewx.units.conversionDict['knot']['meter_per_second']
weewx.units.conversionDict['knot2']['metre_per_second2'] = \
    weewx.units.conversionDict['knot2']['meter_per_second2']
#
# default_unit_format_dict
weewx.units.default_unit_format_dict['metre'] = \
    weewx.units.default_unit_format_dict['meter']
weewx.units.default_unit_format_dict['metre_per_second'] = \
    weewx.units.default_unit_format_dict['meter_per_second']
weewx.units.default_unit_format_dict['metre_per_second2'] = \
    weewx.units.default_unit_format_dict['meter_per_second2']
weewx.units.default_unit_format_dict['microgram_per_metre_cubed'] = \
    weewx.units.default_unit_format_dict['microgram_per_meter_cubed']
weewx.units.default_unit_format_dict['watt_per_metre_squared'] = \
    weewx.units.default_unit_format_dict['watt_per_meter_squared']
#
# default_unit_label_dict
weewx.units.default_unit_label_dict['metre'] = \
    weewx.units.default_unit_label_dict['meter']
weewx.units.default_unit_label_dict['metre_per_second'] = \
    weewx.units.default_unit_label_dict['meter_per_second']
weewx.units.default_unit_label_dict['metre_per_second2'] = \
    weewx.units.default_unit_label_dict['meter_per_second2']
weewx.units.default_unit_label_dict['microgram_per_metre_cubed'] = \
    weewx.units.default_unit_label_dict['microgram_per_meter_cubed']
weewx.units.default_unit_label_dict['watt_per_metre_squared'] = \
    weewx.units.default_unit_label_dict['watt_per_meter_squared']

## add the "metre" fixes to MetricUnits
#weewx.units.MetricUnits.prepend({
#    'group_altitude'    : 'metre',
#    'group_concentration' : 'microgram_per_metre_cubed',
#    'group_radiation'   : 'watt_per_metre_squared',
#
#    # throw in the "litre" fix too
#    'group_volume'      : 'litre',
#})

## add my preferences as well as "metre" fixes to MetricWXUnits
#weewx.units.MetricWXUnits.prepend({
#    'group_altitude'    : 'metre',
#    'group_concentration' : 'microgram_per_metre_cubed',
#    'group_radiation'   : 'watt_per_metre_squared',
#
#    # throw in the "litre" fix too
#    'group_volume'      : 'litre',
#
#    # my preferences
#    'group_speed'       : 'km_per_hour',
#    'group_pressure'    : 'hPa',
#    'group_pressurerate' : 'hPa_per_hour',
#    'group_energy'      : 'kilowatt_hour',
#})

weewx.units.obs_group_dict['riverLevel'] = 'group_length'
#weewx.units.obs_group_dict['leafWet1'] = 'group_length' # (was) jam riverLevel
weewx.units.obs_group_dict['leafWet2'] = 'group_count' # jam forecastRule
weewx.units.obs_group_dict['leafTemp1'] = 'group_rain' # jam stormRain
weewx.units.obs_group_dict['leafTemp2'] = 'group_time' # jam stormStart
weewx.units.obs_group_dict['soilMoist3'] = 'group_energy' # jam solar energy

import schemas.wview_extended
schema = {
    'table' :
        schemas.wview_extended.table + [('riverLevel', 'REAL' )],
    'day_summaries' :
        schemas.wview_extended.day_summaries + [('riverLevel', 'SCALAR' )]
}
