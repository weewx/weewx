#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 608 $
#    $Author: tkeffer $
#    $Date: 2012-08-22 21:23:11 -0700 (Wed, 22 Aug 2012) $
#
"""Abstract base class for station hardware."""

class AbstractStation(object):
    """Station drivers should inherit from this class."""    
    def genLoopPackets(self):
        raise NotImplementedError("Method genLoopPackets not implemented")
    
    def genArchiveRecords(self, lastgood_ts):
        raise NotImplementedError("Method genArchiveRecords not implemented")
        
    def getTime(self):
        raise NotImplementedError("Method getTime not implemented")
    
    def setTime(self, newtime_ts):
        raise NotImplementedError("Method setTime not implemented")
    
    def closePort(self):
        pass
