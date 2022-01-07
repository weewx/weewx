#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions related to Quality Control of incoming data."""

# Python imports
from __future__ import absolute_import
import logging

# weewx imports
import weeutil.weeutil
import weewx.units
from weeutil.weeutil import to_float

log = logging.getLogger(__name__)


# ==============================================================================
#                    Class QC
# ==============================================================================

class QC(object):
    """Class to apply quality checks to a record."""

    def __init__(self, mm_dict, log_failure=True):
        """
        Initialize
        Args:
            mm_dict: A dictionary containing the limits. The key is an observation type, the value
            is a 2- or 3-way tuple. If a 2-way tuple, then the values are (min, max) acceptable
            value in a record for that observation type. If a 3-way tuple, then the values are
            (min, max, unit), where min and max are as before, but the value 'unit' is the unit the
            min and max values are in. If 'unit' is not specified, then the values must be in the
            same unit as the incoming record (a risky supposition!).

            log_failure: True to log values outside of their limits. False otherwise.
        """

        self.mm_dict = {}
        for obs_type in mm_dict:
            self.mm_dict[obs_type] = list(mm_dict[obs_type])
            # The incoming min, max values may be from a ConfigObj, which are typically strings.
            # Convert to floats.
            self.mm_dict[obs_type][0] = to_float(self.mm_dict[obs_type][0])
            self.mm_dict[obs_type][1] = to_float(self.mm_dict[obs_type][1])

        self.log_failure = log_failure

    def apply_qc(self, data_dict, data_type=''):
        """Apply quality checks to the data in a record"""

        converter = weewx.units.StdUnitConverters[data_dict['usUnits']]

        for obs_type in self.mm_dict:
            if obs_type in data_dict and data_dict[obs_type] is not None:
                # Extract the minimum and maximum acceptable values
                min_v, max_v = self.mm_dict[obs_type][0:2]
                # If a unit has been specified, convert the min, max acceptable value to the same
                # unit system as the incoming record:
                if len(self.mm_dict[obs_type]) == 3:
                    min_max_unit = self.mm_dict[obs_type][2]
                    group = weewx.units.getUnitGroup(obs_type)
                    min_v = converter.convert((min_v, min_max_unit, group))[0]
                    max_v = converter.convert((max_v, min_max_unit, group))[0]

                if not min_v <= data_dict[obs_type] <= max_v:
                    if self.log_failure:
                        log.warning("%s %s value '%s' %s outside limits (%s, %s)",
                                    weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                    data_type, obs_type, data_dict[obs_type], min_v, max_v)
                    data_dict[obs_type] = None
