'''
Created on Feb 25, 2011

@author: tkeffer
'''

import random

import weewx.wxengine

class LineMonitor(weewx.wxengine.StdService):
    
    def newArchivePacket(self, archivePacket):
        archivePacket['lineVoltage'] = 120.0 + random.gauss(0.0, 2.0)
