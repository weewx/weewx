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
#                    Class StdCalibrate
#===============================================================================

class StdCalibrate(StdService):
    """Adjust data using calibration expressions.
    
    This service must be run before StdArchive, so the correction is applied
    before the data is archived."""
    
    def __init__(self, engine, config_dict):
        # Initialize my base class:
        super(StdCalibrate, self).__init__(engine, config_dict)
        
        # Get the list of calibration corrections to apply. If a section
        # is missing, a KeyError exception will get thrown:
        try:
            correction_dict = config_dict['StdCalibrate']['Corrections']
            self.corrections = {}

            # For each correction, compile it, then save in a dictionary of
            # corrections to be applied:
            for obs_type in correction_dict.scalars:
                self.corrections[obs_type] = compile(correction_dict[obs_type], 
                                                     'StdCalibrate', 'eval')
            
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        except KeyError:
            syslog.syslog(syslog.LOG_NOTICE, "wxengine: No calibration information in config file. Ignored.")
            
    def new_loop_packet(self, event):
        """Apply a calibration correction to a LOOP packet"""
        for obs_type in self.corrections:
            if event.packet.has_key(obs_type) and event.packet[obs_type] is not None:
                event.packet[obs_type] = eval(self.corrections[obs_type], None, event.packet)

    def new_archive_record(self, event):
        """Apply a calibration correction to an archive packet"""
        # If the record was software generated, then any corrections have already been applied
        # in the LOOP packet.
        if event.origin != 'software':
            for obs_type in self.corrections:
                if event.record.has_key(obs_type) and event.record[obs_type] is not None:
                    event.record[obs_type] = eval(self.corrections[obs_type], None, event.record)

