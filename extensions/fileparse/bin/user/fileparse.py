#!/usr/bin/python
#
# Copyright 2014 Matthew Wall
#
# weewx driver that reads data from a file
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


# This driver will read data from a file.  Each line of the file is a 
# name=value pair, for example:
#
# temperature=50
# humidity=54
# in_temperature=75
#
# The units must be in the weewx.US unit system:
#   degree_F, inHg, inch, inch_per_hour, mile_per_hour
#
# To use this driver, put this file in the weewx user directory, then make
# the following changes to weewx.conf:
#
# [Station]
#     station_type = FileParse
# [FileParse]
#     poll_interval = 2          # number of seconds
#     path = /var/tmp/wxdata     # location of data file
#     driver = user.fileparse
#
# If the variables in the file have names different from those in the database
# schema, then create a mapping section called label_map.  This will map the
# variables in the file to variables in the database columns.  For example:
#
# [FileParse]
#     ...
#     [[label_map]]
#         temp = outTemp
#         humi = outHumidity
#         in_temp = inTemp
#         in_humid = inHumidity

from __future__ import with_statement
import syslog
import time

import weewx.drivers

DRIVER_NAME = 'FileParse'
DRIVER_VERSION = "0.6"

def logmsg(dst, msg):
    syslog.syslog(dst, 'fileparse: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def _get_as_float(d, s):
    v = None
    if s in d:
        try:
            v = float(d[s])
        except ValueError, e:
            logerr("cannot read value for '%s': %s" % (s, e))
    return v

def loader(config_dict, engine):
    return FileParseDriver(**config_dict[DRIVER_NAME])

class FileParseDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a file"""

    def __init__(self, **stn_dict):
        # where to find the data file
        self.path = stn_dict.get('path', '/var/tmp/wxdata')
        # how often to poll the weather data file, seconds
        self.poll_interval = float(stn_dict.get('poll_interval', 2.5))
        # mapping from variable names to weewx names
        self.label_map = stn_dict.get('label_map', {})

        loginf("data file is %s" % self.path)
        loginf("polling interval is %s" % self.poll_interval)
        loginf('label map is %s' % self.label_map)

    def genLoopPackets(self):
        while True:
            # read whatever values we can get from the file
            data = {}
            try:
                with open(self.path) as f:
                    for line in f:
                        eq_index = line.find('=')
                        name = line[:eq_index].strip()
                        value = line[eq_index + 1:].strip()
                        data[name] = value
            except Exception, e:
                logerr("read failed: %s" % e)

            # map the data into a weewx loop packet
            _packet = {'dateTime': int(time.time() + 0.5),
                       'usUnits': weewx.US}
            for vname in data:
                _packet[self.label_map.get(vname, vname)] = _get_as_float(data, vname)

            yield _packet
            time.sleep(self.poll_interval)

    @property
    def hardware_name(self):
        return "FileParse"

# To test this driver, run it directly as follows:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/fileparse.py
if __name__ == "__main__":
    import weeutil.weeutil
    driver = FileParseDriver()
    for packet in driver.genLoopPackets():
        print weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet
