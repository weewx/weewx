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
#                    Class StdConvert
#===============================================================================

class StdConvert(StdService):
    """Service for performing unit conversions.
    
    This service acts as a filter. Whatever packets and records come in are
    converted to a target unit system.
    
    This service should be run before most of the others, so observations appear
    in the correct unit."""
    
    def __init__(self, engine, config_dict):
        # Initialize my base class:
        super(StdConvert, self).__init__(engine, config_dict)

        # Get the target unit nickname (something like 'US' or 'METRIC'):
        target_unit_nickname = config_dict['StdConvert']['target_unit']
        # Get the target unit. This will be weewx.US or weewx.METRIC
        self.target_unit = weewx.units.unit_constants[target_unit_nickname.upper()]
        # Bind self.converter to the appropriate standard converter
        self.converter = weewx.units.StdUnitConverters[self.target_unit]
        
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        
        syslog.syslog(syslog.LOG_INFO, "wxengine: StdConvert target unit is 0x%x" % self.target_unit)
        
    def new_loop_packet(self, event):
        """Do unit conversions for a LOOP packet"""
        # No need to do anything if the packet is already in the target
        # unit system
        if event.packet['usUnits'] == self.target_unit: return
        # Perform the conversion
        converted_packet = self.converter.convertDict(event.packet)
        # Add the new unit system
        converted_packet['usUnits'] = self.target_unit
        # Replace the old packet with the new, converted packet:
        event.packet = converted_packet

    def new_archive_record(self, event):
        """Do unit conversions for an archive record."""
        # No need to do anything if the record is already in the target
        # unit system
        if event.record['usUnits'] == self.target_unit: return
        # Perform the conversion
        converted_record = self.converter.convertDict(event.record)
        # Add the new unit system
        converted_record['usUnits'] = self.target_unit
        # Replace the old record with the new, converted record
        event.record = converted_record
