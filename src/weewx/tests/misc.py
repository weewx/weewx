#
#      Copyright (c) 2019-2024 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#
"""Miscellaneous classes used by the test routines."""
import math

import weewx.xtypes
from weewx.units import ValueTuple


class FakeXType(weewx.xtypes.XType):

    def get_scalar(self, obs_type, record, db_manager=None, **option_dict):
        if obs_type == 'testTemp':
            return ValueTuple(5.0, 'degree_C', 'group_temperature')
        elif obs_type == 'fooTemp':
            raise weewx.CannotCalculate('fooTemp')
        else:
            raise weewx.UnknownType(obs_type)


weewx.xtypes.xtypes.append(FakeXType())
