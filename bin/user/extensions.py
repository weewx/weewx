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

#===============================================================================
# As an example, extend the unit dictionaries with
# a new unit type: linevoltage.
#===============================================================================

import weewx.units

weewx.units.obs_group_dict['linevoltage'] = 'group_volt'
