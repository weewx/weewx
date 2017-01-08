#!/usr/bin/python
#
# Copyright 2015 Jakub Kakona
#
# weewx driver that publish the loopacket data as network broadcast.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/

import sys, json
import socket as sck
import weewx
from weewx.engine import StdService

class BroadcastService(StdService):
    """Service that broadcast meteo data information when a LOOP
    packet is received."""

    def __init__(self,engine, config_dict):
        # Pass the initialization information on to my superclass:
        super(BroadcastService, self).__init__(engine, config_dict)
        self.s = sck.socket(sck.AF_INET, sck.SOCK_DGRAM, sck.IPPROTO_UDP)
        self.s.setsockopt(sck.IPPROTO_IP, sck.IP_MULTICAST_TTL, 2)
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)

    def newLoopPacket(self, event):
        """Send the new LOOP packet to the broadcast socket"""
        data = json.dumps(event.packet)
        try:
            self.s.sendto(data, ('224.1.1.1', 50000))
        except: 
            pass

