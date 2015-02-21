#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
import os
import resource

import weewx
from weewx.wxengine import StdService

class Memory(StdService):
    
    def __init__(self, engine, config_dict):
        # Pass the initialization information on to my superclass:
        super(Memory, self).__init__(engine, config_dict)

        self.page_size = resource.getpagesize()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.newArchiveRecord)

    def newArchiveRecord(self, event):
        
        pid = os.getpid()
        procfile = "/proc/%s/statm" % pid
        try:
            mem_tuple = open(procfile).read().split()
        except (IOError, ):
            return
         
        # Unpack the tuple:
        (size, resident, share, text, lib, data, dt) = mem_tuple

        mb = 1024 * 1024
        event.record['soilMoist1'] = float(size)     * self.page_size / mb 
        event.record['soilMoist2'] = float(resident) * self.page_size / mb
        event.record['soilMoist3'] = float(share)    * self.page_size / mb
        