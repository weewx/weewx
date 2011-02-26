#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

"""User extensions module

This module is imported from the main executable, so
any user extensions put here will be executed before
anything else happens. This makes it a good place
to put any user extensions.
"""

from weewx.units import obs_group_dict, USUnits, MetricUnits, allPossibleUnitTypes

# Add a new observation type and a new group type:
obs_group_dict['lineVoltage'] = "group_bigvolts"

# Add the standard unit type in the US customary system:
USUnits["group_bigvolts"] = "voltAC"

# Add the standard unit type in the Metric system:
MetricUnits["group_bigvolts"] = "voltAC"

# Update the set of all possible unit types to reflect the
# above additions:
allPossibleUnitTypes = set(USUnits.values()+MetricUnits.values())
