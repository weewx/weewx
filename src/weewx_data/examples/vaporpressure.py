#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""This example shows how to extend the XTypes system with a new type, vapor_p, the vapor
pressure of water.

REQUIRES WeeWX V4.2 OR LATER!

To use:
    1. Stop weewxd
    2. Put this file in your user subdirectory.
    3. In weewx.conf, subsection [Engine][[Services]], add VaporPressureService to the list
    "xtype_services". For example, this means changing this

        [Engine]
            [[Services]]
                xtype_services = weewx.wxxtypes.StdWXXTypes, weewx.wxxtypes.StdPressureCooker, weewx.wxxtypes.StdRainRater

    to this:

        [Engine]
            [[Services]]
                xtype_services = weewx.wxxtypes.StdWXXTypes, weewx.wxxtypes.StdPressureCooker, weewx.wxxtypes.StdRainRater, user.vaporpressure.VaporPressureService

    4. Optionally, add the following section to weewx.conf:
        [VaporPressure]
            algorithm = simple   # Or tetens

    5. Restart weewxd

"""
import math

import weewx
import weewx.units
import weewx.xtypes
from weewx.engine import StdService
from weewx.units import ValueTuple


class VaporPressure(weewx.xtypes.XType):

    def __init__(self, algorithm='simple'):
        # Save the algorithm to be used.
        self.algorithm = algorithm.lower()

    def get_scalar(self, obs_type, record, db_manager):
        # We only know how to calculate 'vapor_p'.
        # For everything else, raise an exception UnknownType
        if obs_type != 'vapor_p':
            raise weewx.UnknownType(obs_type)

        # We need outTemp in order to do the calculation.
        if 'outTemp' not in record or record['outTemp'] is None:
            raise weewx.CannotCalculate(obs_type)

        # We have everything we need. Start by forming a ValueTuple for the outside temperature.
        outTemp_vt = weewx.units.as_value_tuple(record, 'outTemp')

        # Both algorithms need temperature in Celsius, so let's make sure our incoming temperature
        # is in that unit. Use function convert(). The results will be in the form of a ValueTuple
        outTemp_C_vt = weewx.units.convert(outTemp_vt, 'degree_C')

        # The attribute ".value" will give us just the value part of the ValueTuple
        result = calc_vapor_pressure(outTemp_C_vt.value, self.algorithm)

        # Convert to the unit system that we are using and return
        return weewx.units.convertStd(result, record['usUnits'])


def calc_vapor_pressure(outTemp_C, algorithm='simple'):
    """Given a temperature in Celsius, calculate the vapor pressure"""
    if outTemp_C is None:
        return ValueTuple(None, 'mmHg', 'group_pressure')
    if algorithm == 'simple':
        # Use the "Simple" algorithm.
        # We need temperature in Kelvin.
        outTemp_K = weewx.units.CtoK(outTemp_C)
        # Now we can use the formula. Results will be in mmHg. Create a ValueTuple out of it:
        p_vt = ValueTuple(math.exp(20.386 - 5132.0 / outTemp_K), 'mmHg', 'group_pressure')
    elif algorithm == 'teters':
        # Use Teter's algorithm.
        # Use the formula. Results will be in kPa:
        p_kPa = 0.61078 * math.exp(17.27 * outTemp_C / (outTemp_C + 237.3))
        # Form a ValueTuple
        p_vt = ValueTuple(p_kPa, 'kPa', 'group_pressure')
    else:
        # Don't recognize the algorithm. Fail hard:
        raise ValueError(algorithm)
    return p_vt


class VaporPressureService(StdService):
    def __init__(self, engine, config_dict):
        super(VaporPressureService, self).__init__(engine, config_dict)

        # Get the desired algorithm. Default to "simple".
        try:
            algorithm = config_dict['VaporPressure']['algorithm']
        except KeyError:
            algorithm = 'simple'

        # Instantiate an instance of VaporPressure:
        self.vp = VaporPressure(algorithm)
        # Register it with the XTypes system:
        weewx.xtypes.xtypes.insert(0, self.vp)

    def shutDown(self):
        # Remove the registered instance:
        weewx.xtypes.xtypes.remove(self.vp)


# Tell the unit system what group our new observation type, 'vapor_p', belongs to:
weewx.units.obs_group_dict['vapor_p'] = "group_pressure"
