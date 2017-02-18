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
        # Last record cache
        self.last_records = {'LOOP': {},'Archive': {}}

        # If the 'StdQC', 'MinMax', 'Spike' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done for those sections.
        try:
            mm_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC MinMax information in config file.")
            mm_dict = None

        try:
            spike_dict = config_dict['StdQC']['Spike']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC Spike information in config file.")
            spike_dict = None

        self.min_max_dict = {}
        self.spike_dict = {}

        target_unit_name = config_dict['StdConvert']['target_unit']
        target_unit = weewx.units.unit_constants[target_unit_name.upper()]
        converter = weewx.units.StdUnitConverters[target_unit]

        if mm_dict is not None:
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

        if spike_dict is not None:
            for obs_type in spike_dict.scalars:
                spikeval = float(spike_dict[obs_type][0])
                spiketime = float(spike_dict[obs_type][1])
                if len(spike_dict[obs_type]) == 3:
                    group = weewx.units._getUnitGroup(obs_type)
                    vt = (spikeval, spike_dict[obs_type][2], group)
                    spikeval = converter.convert(vt)[0]
                # Quantise spike to 1 second
                try:
                    spikeval = spikeval / spiketime
                except ZeroDivisionError:
                    continue
                self.spike_dict[obs_type] = spikeval

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
        
        # If no data_type we will not do spike detection
        # On first time for each data_type last_record will be an empty dict
        if data_type is not '':
            last_record = self.last_records[data_type]
            # Build cache record based on the last record
            cache_record = last_record
            cache_record['dateTime'] = data_dict['dateTime']
            for obs_type in self.spike_dict:
                # Observation may not be in record or MinMax QC may have set to None
                if data_dict.has_key(obs_type) and data_dict[obs_type] is not None:
                    # build cache. Will be updated with last value if spike detected
                    cache_record[obs_type] = data_dict[obs_type]
                    # Observation may not be in the cached last record
                    if last_record.has_key(obs_type) and last_record[obs_type] is not None:
                        spikecheck = data_dict[obs_type] - last_record[obs_type]
                        try:
                            spikecheck = abs(spikecheck / (data_dict['dateTime'] - last_record['dateTime']))
                        except ZeroDivisionError:
                            continue
                        # If spike detected then report and set observation value to None
                        if spikecheck > self.spike_dict[obs_type]:
                            syslog.syslog(syslog.LOG_NOTICE, "%s: %s %s value '%s' %s (last: %s) outside spike limit (%s)" %
                                            (self.parent,
                                            weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                            data_type, obs_type, data_dict[obs_type],
                                            last_record[obs_type], self.spike_dict[obs_type]))
                            # Save the last record for observation as our cache for spike checking
                            cache_record[obs_type] = last_record[obs_type]
                            # Set the spike value for observation to None
                            data_dict[obs_type] = None
            # Save the cache record
            self.last_records[data_type] = cache_record




