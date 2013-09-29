#
#    Copyright (c) 2009, 2010, 2012, 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

import syslog

import weewx
from weewx.wxengine import StdService
#===============================================================================
#                    Class StdQC
#===============================================================================

class StdQC(StdService):
    """Performs quality check on incoming data."""

    def __init__(self, engine, config_dict):
        super(StdQC, self).__init__(engine, config_dict)

        # If the 'StdQC' or 'MinMax' sections do not exist in the configuration
        # dictionary, then an exception will get thrown and nothing will be
        # done.
        try:
            min_max_dict = config_dict['StdQC']['MinMax']
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE, "wxengine: No QC information in config file. Ignored.")
            return

        self.min_max_dict = {}

        for obs_type in min_max_dict.scalars:
            self.min_max_dict[obs_type] = (float(min_max_dict[obs_type][0]),
                                           float(min_max_dict[obs_type][1]))
        
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
    def new_loop_packet(self, event):
        """Apply quality check to the data in a LOOP packet"""
        for obs_type in self.min_max_dict:
            if event.packet.has_key(obs_type) and event.packet[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= event.packet[obs_type] <= self.min_max_dict[obs_type][1]:
                    event.packet[obs_type] = None

    def new_archive_record(self, event):
        """Apply quality check to the data in an archive packet"""
        for obs_type in self.min_max_dict:
            if event.record.has_key(obs_type) and event.record[obs_type] is not None:
                if not self.min_max_dict[obs_type][0] <= event.record[obs_type] <= self.min_max_dict[obs_type][1]:
                    event.record[obs_type] = None

