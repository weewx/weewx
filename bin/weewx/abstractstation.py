#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Abstract base class for station hardware."""

import weewx

class AbstractStation(object):
    """Station drivers should inherit from this class."""    
    def genLoopPackets(self):
        raise weewx.NotImplemented("Method genLoopPackets not implemented")
    
    def genArchiveRecords(self, lastgood_ts):
        raise weewx.NotImplemented("Method genArchiveRecords not implemented")
        
    def getTime(self):
        raise weewx.NotImplemented("Method getTime not implemented")
    
    def setTime(self, newtime_ts):
        raise weewx.NotImplemented("Method setTime not implemented")
