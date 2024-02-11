#
#      Copyright (c) 2019-2024 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#
"""Miscellaneous classes used by the test routines."""
import math

import weewx.xtypes
from weewx.units import ValueTuple


class VaporPressure(weewx.xtypes.XType):
    """Calculate VaporPressure."""

    def get_scalar(self, obs_type, record, db_manager):
        # We only know how to calculate 'vapor_p'. For everything else, raise an exception
        if obs_type != 'vapor_p':
            raise weewx.UnknownType(obs_type)

        # We need outTemp in order to do the calculation.
        if 'outTemp' not in record or record['outTemp'] is None:
            raise weewx.CannotCalculate(obs_type)

        # We have everything we need. Start by forming a ValueTuple for the outside temperature.
        # To do this, figure out what unit and group the record is in ...
        unit_and_group = weewx.units.getStandardUnitType(record['usUnits'], 'outTemp')
        # ... then form the ValueTuple.
        outTemp_vt = weewx.units.ValueTuple(record['outTemp'], *unit_and_group)

        # We need the temperature in Kelvin
        outTemp_K_vt = weewx.units.convert(outTemp_vt, 'degree_K')

        # Now we can use the formula. Results will be in mmHg. Create a ValueTuple out of it:
        p_vt = weewx.units.ValueTuple(math.exp(20.386 - 5132.0 / outTemp_K_vt[0]),
                                      'mmHg',
                                      'group_pressure')

        # We have the vapor pressure as a ValueTuple. Convert it back to the units used by
        # the incoming record and return it
        return weewx.units.convertStd(p_vt, record['usUnits'])


# Register vapor pressure
weewx.units.obs_group_dict['vapor_p'] = "group_pressure"
# Instantiate and register an instance of VaporPressure:
weewx.xtypes.xtypes.append(VaporPressure())


class FakeXType(weewx.xtypes.XType):

    def get_scalar(self, obs_type, record, db_manager=None, **option_dict):
        if obs_type == 'testTemp':
            return ValueTuple(5.0, 'degree_C', 'group_temperature')
        elif obs_type == 'fooTemp':
            raise weewx.CannotCalculate('fooTemp')
        else:
            raise weewx.UnknownType(obs_type)


weewx.xtypes.xtypes.append(FakeXType())
