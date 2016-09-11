#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions related to Quality Control of incoming data."""

# Python imports
import syslog

# weewx imports
import weeutil.weeutil
import weewx.units

#==============================================================================
#                    Class QC
#==============================================================================

class QC(object):
    """Class to apply quality checks to a record."""

    def __init__(self, config_dict, parent='engine'):

        # Save our 'parent' - for use when logging
        self.parent = parent

        # If the 'StdQC' or 'MinMax' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done.
        try:
            mm_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC information in config file.")
            return

        self.min_max_dict = {}

        target_unit_name = config_dict['StdConvert']['target_unit']
        target_unit = weewx.units.unit_constants[target_unit_name.upper()]
        converter = weewx.units.StdUnitConverters[target_unit]

        for obs_type in mm_dict.scalars:
            minval = float(mm_dict[obs_type][0])
            maxval = float(mm_dict[obs_type][1])
            if len(mm_dict[obs_type]) == 3:
                group = weewx.units._getUnitGroup(obs_type)
                vt = (minval, mm_dict[obs_type][2], group)
                minval = converter.convert(vt)[0]
                vt = (maxval, mm_dict[obs_type][2], group)
                maxval = converter.convert(vt)[0]
            self.min_max_dict[obs_type] = (minval, maxval)

    def apply_qc(self, data_dict, data_type=''):
        """Apply quality checks to the data in a record"""

        for obs_type in self.min_max_dict:
            if data_dict.has_key(obs_type) and data_dict[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= data_dict[obs_type] <= self.min_max_dict[obs_type][1]:
                    syslog.syslog(syslog.LOG_NOTICE, "%s: %s %s value '%s' %s outside limits (%s, %s)" %
                                  (self.parent,
                                   weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                   data_type, obs_type, data_dict[obs_type],
                                   self.min_max_dict[obs_type][0], self.min_max_dict[obs_type][1]))
                    data_dict[obs_type] = None

