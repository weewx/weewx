#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions related to Quality Control of incoming data."""

# Python imports
import syslog
from copy import deepcopy

# weewx imports
import weeutil.weeutil
import weewx.units

#==============================================================================
#                    Class QC
#==============================================================================

class QC(object):
    """Class to apply quality checks to a record."""

    def __init__(self, config_dict, parent='engine', db_binder=None):

        # Save our 'parent' - for use when logging
        self.parent = parent
        # our config
        svc_dict = config_dict['StdQC']
        # database binding for any hitting database on startup
        if db_binder is None:
            db_binder = weewx.manager.DBBinder(config_dict)
        self.db_binder = db_binder
        self.binding = svc_dict.get('data_binding', 'wx_binding')
        # max_delta for hitting database on startup
        self.max_delta = int(svc_dict.get('max_delta', 300))
        # Last record cache
        self.last_records = {'LOOP': {}, 'Archive': {}}

        # If the 'StdQC', 'MinMax', 'Spike' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done for those sections.
        try:
            mm_dict = svc_dict['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC MinMax information in config file.")
            mm_dict = None

        try:
            spike_dict = svc_dict['Spike']
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
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: MinMax %s < %s < %s" % (self.parent, minval, obs_type, maxval))

        if spike_dict is not None:
            # Get database record to build cache
            manager = self.db_binder.get_manager(self.binding)
            timestamp = manager.lastGoodStamp()
            db_record = manager.getRecord(timestamp, max_delta=self.max_delta)
            # Empty cache record
            cache_record = {}

            for obs_type in spike_dict.scalars:
                spikeval = float(spike_dict[obs_type][0])
                spiketime = float(spike_dict[obs_type][1])
                if len(spike_dict[obs_type]) == 3:
                    group = weewx.units._getUnitGroup(obs_type)
                    vt = (spikeval, spike_dict[obs_type][2], group)
                    spikeval = converter.convert(vt)[0]
                # Quantise spike to 1 second
                try:
                    spikeval /= spiketime
                except ZeroDivisionError:
                    continue
                self.spike_dict[obs_type] = spikeval
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: Spike limit for %s = %s / sec" % (self.parent, obs_type, spikeval))
                if db_record is not None and db_record.has_key(obs_type) and db_record[obs_type] is not None:
                    rec_data = db_record[obs_type]
                    rec_dateTime = db_record['dateTime']
                else:
                    rec_data = None
                    rec_dateTime = None

                cache_record[obs_type] = {}
                cache_record[obs_type]['data'] = rec_data
                cache_record[obs_type]['dateTime'] = rec_dateTime
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: Spike initial cache for %s = %s at %s" %
                  (self.parent,
                   obs_type,
                   cache_record[obs_type]['data'],
                   weeutil.weeutil.timestamp_to_string(cache_record[obs_type]['dateTime'])))

            self.last_records['LOOP'] = cache_record
            self.last_records['Archive'] = cache_record

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
        if data_type is not '':
            last_record = self.last_records[data_type]
            # Build cache record based on the last record
            # We will keep values which may not be in this packet
            # It is a dict of dicts so need to deep copy
            cache_record = deepcopy(last_record)
            if weewx.debug >= 2:
                spike_debug = []
            for obs_type in self.spike_dict:
                # Observation may not be in record or MinMax QC may have set to None
                if data_dict.has_key(obs_type) and data_dict[obs_type] is not None:
                    # build cache. Will be updated with last value if spike detected
                    cache_record[obs_type]['data'] = data_dict[obs_type]
                    cache_record[obs_type]['dateTime'] = data_dict['dateTime']
                    # Observation may not be in the cached last record
                    if last_record.has_key(obs_type) and last_record[obs_type]['data'] is not None:
                        spikecheck = data_dict[obs_type] - last_record[obs_type]['data']
                        try:
                            spikecheck = abs(spikecheck / (data_dict['dateTime'] - last_record[obs_type]['dateTime']))
                        except ZeroDivisionError:
                            continue
                        # If spike detected then report and set observation value to None
                        if weewx.debug >= 2:
                            spike_debug.append("%s: %s" % (obs_type, spikecheck))
                        if spikecheck > self.spike_dict[obs_type]:
                            syslog.syslog(syslog.LOG_NOTICE, "%s: %s %s value '%s' %s (last: %s) outside spike limit (%s)" %
                                            (self.parent,
                                            weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                            data_type, obs_type, data_dict[obs_type],
                                            last_record[obs_type]['data'], self.spike_dict[obs_type]))
                            # Save the last record for observation as our cache for spike checking
                            cache_record[obs_type]['data'] = last_record[obs_type]['data']
                            cache_record[obs_type]['dateTime'] = last_record[obs_type]['dateTime']
                            # Set the spike value for observation to None
                            data_dict[obs_type] = None

            if weewx.debug >= 2:
                syslog.syslog(syslog.LOG_DEBUG, "%s: StqQC: spike check: %s: %s" % (self.parent, data_type, ", ".join(spike_debug)))
            # Save the cache record
            self.last_records[data_type] = cache_record




