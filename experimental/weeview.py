#!/usr/bin/env python
# Simple client app for PyMeteostation

# Receive UDP packets transmitted by a broadcasting service

MYPORT = 50000

import sys, json
from socket import *

s = socket(AF_INET, SOCK_DGRAM)
s.bind(('', MYPORT))

while True:
    packet, wherefrom = s.recvfrom(4096)
    print wherefrom
#    print data
    data = json.loads(packet)
    print data['UV']
    print data['windDir'], data['windSpeed']
