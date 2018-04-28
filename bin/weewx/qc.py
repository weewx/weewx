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
#                    Class Qc
#==============================================================================


class Qc(object):
    """Abstract Class to apply quality checks to a record.
    
    QC objects derive from this class
    """

    def __init__(self, config_dict, parent='engine', db_record=None):

        # Save our 'parent' - for use when logging
        self.parent = parent
        # our config
        self.config_dict = config_dict['StdQC']
        # Our starting db_record
        self.db_record = db_record

        try:
            target_unit_name = config_dict['StdConvert']['target_unit']
        except KeyError:
            target_unit_name = 'US'

        target_unit = weewx.units.unit_constants[target_unit_name.upper()]
        self.converter = weewx.units.StdUnitConverters[target_unit]

    def apply_qc(self, data_dict, data_type=''):
        pass

#==============================================================================
#                    Class QcMixMax
#==============================================================================


class QcMinMax(Qc):
    """MinMax QC Class. Applies MinMax QC to packets"""

    def __init__(self, config_dict, parent='engine', db_record=None):
        super(QcMinMax, self).__init__(config_dict, parent, db_record)

        # If the 'MinMax' sections do not exist in the configuration
        # dictionary then an exception will be thrown and nothing will be done for these sections
        try:
            mm_dict = self.config_dict['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC MinMax information in config file.")
            mm_dict = None

        self.min_max_dict = dict()

        if mm_dict is not None:
            for obs_type in mm_dict.scalars:
                minval = float(mm_dict[obs_type][0])
                maxval = float(mm_dict[obs_type][1])
                if len(mm_dict[obs_type]) == 3:
                    group = weewx.units._getUnitGroup(obs_type)
                    vt = (minval, mm_dict[obs_type][2], group)
                    minval = self.converter.convert(vt)[0]
                    vt = (maxval, mm_dict[obs_type][2], group)
                    maxval = self.converter.convert(vt)[0]
                self.min_max_dict[obs_type] = (minval, maxval)
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: MinMax %s < %s < %s" % (self.parent, minval, obs_type, maxval))

    def apply_qc(self, data_dict, data_type=''):
        """Apply MinMax quality checks to the data in a record"""

        for obs_type in self.min_max_dict:
            if data_dict.has_key(obs_type) and data_dict[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= data_dict[obs_type] <= self.min_max_dict[obs_type][1]:
                    syslog.syslog(syslog.LOG_NOTICE, "%s: %s %s value '%s' %s outside limits (%s, %s)" %
                                  (self.parent,
                                   weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                   data_type, obs_type, data_dict[obs_type],
                                   self.min_max_dict[obs_type][0], self.min_max_dict[obs_type][1]))
                    data_dict[obs_type] = None

#==============================================================================
#                    Class QcSpike
#==============================================================================


class QcSpike(Qc):
    """Spike QC Class. Applies Spike QC to packets
    
    Spike detection will handle a jump up and back. All obs outside the spike limit
    will be set to None until the jump back or until the configured timeband has expired
    """

    def __init__(self, config_dict, parent='engine', db_record=None):
        super(QcSpike, self).__init__(config_dict, parent, db_record)

        # Last record cache
        self.last_values = {'LOOP': {}, 'Archive': {}}

        # If the 'Spike' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done for those sections.

        try:
            spike_dict = self.config_dict['Spike']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE,
                          self.parent + ": No QC Spike information in config file.")
            spike_dict = None

        self.spike_dict = dict()

        if spike_dict is not None:
            # Empty cache record
            cache_record = dict()

            for obs_type in spike_dict.scalars:
                spikeval = float(spike_dict[obs_type][0])
                spiketime = float(spike_dict[obs_type][1])
                if len(spike_dict[obs_type]) == 3:
                    group = weewx.units._getUnitGroup(obs_type)
                    vt = (spikeval, spike_dict[obs_type][2], group)
                    spikeval = self.converter.convert(vt)[0]
                # Quantise spike to 1 second
                try:
                    spikeval /= spiketime
                except ZeroDivisionError:
                    continue
                self.spike_dict[obs_type] = spikeval
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: Spike limit for %s = %s / sec" % (self.parent, obs_type, spikeval))
                cache_record[obs_type] = dict()
                if db_record is not None and db_record.has_key(obs_type) and db_record[obs_type] is not None:
                    self.last_values['LOOP']['data'] = db_record[obs_type]
                    self.last_values['LOOP']['dateTime'] = db_record['dateTime']
                    self.last_values['Archive']['data'] = db_record[obs_type]
                    self.last_values['Archive']['dateTime'] = db_record['dateTime']
                else:
                    self.last_values['LOOP']['data'] = None
                    self.last_values['LOOP']['dateTime'] = None
                    self.last_values['Archive']['data'] = None
                    self.last_values['Archive']['dateTime'] = None
                syslog.syslog(syslog.LOG_DEBUG, "%s: StdQC: Spike initial cache for %s = %s at %s" %
                  (self.parent,
                   obs_type,
                   cache_record[obs_type]['data'],
                   weeutil.weeutil.timestamp_to_string(cache_record[obs_type]['dateTime'])))

    def apply_qc(self, data_dict, data_type=''):
        """Apply Spike quality checks to the data in a record"""

        # If no data_type we will not do spike detection
        if data_type is not '':
            spike_debug = []
            for obs_type in self.spike_dict:
                # Observation may not be in record or Previous QC may have set to None
                if data_dict.has_key(obs_type) and data_dict[obs_type] is not None:
                    # Observation may not be in the last values cache
                    if self.last_values[data_type].has_key(obs_type) and self.last_values[data_type][obs_type]['data'] is not None:
                        try:
                            spikecheck = abs((data_dict[obs_type] - self.last_values[data_type][obs_type]['data']) /
                                             (data_dict['dateTime'] - self.last_values[data_type][obs_type]['dateTime']))
                        except ZeroDivisionError:
                            continue
                        # If spike detected then report and set observation value to None
                        if weewx.debug >= 2:
                            spike_debug.append("%s: %s" % (obs_type, spikecheck))
                        if spikecheck > self.spike_dict[obs_type]:
                            # Spike!
                            syslog.syslog(syslog.LOG_NOTICE, "%s: %s %s value '%s' %s (last: %s) outside spike limit (%s)" %
                                            (self.parent,
                                            weeutil.weeutil.timestamp_to_string(data_dict['dateTime']),
                                            data_type, obs_type, data_dict[obs_type],
                                             self.last_values[data_type][obs_type]['data'], self.spike_dict[obs_type]))
                            # Set the spike value for observation to None
                            data_dict[obs_type] = None

                    # Save current value in last values cache if it is good
                    if data_dict[obs_type] is not None:
                        self.last_values[data_type][obs_type]['data'] = data_dict[obs_type]
                        self.last_values[data_type][obs_type]['dateTime'] = data_dict['dateTime']

            if weewx.debug >= 2:
                syslog.syslog(syslog.LOG_DEBUG, "%s: StqQC: spike check: %s: %s" % (self.parent, data_type, ", ".join(spike_debug)))