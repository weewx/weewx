#
#    Copyright (c) 2025 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Parameters used for database-related tests"""
import os
import time

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# The start of the 'solar year' for 2009-2010
year_start_tt = (2009, 12, 21, 9, 47, 0, 0, 0, 0)
year_start = int(time.mktime(year_start_tt))

# Roughly nine months of data:
start_tt = (2010, 1, 1, 0, 0, 0, 0, 0, -1)  # 2010-01-01 00:00
stop_tt = (2010, 9, 3, 11, 0, 0, 0, 0, -1)  # 2010-09-03 11:00
alt_start_tt = (2010, 8, 30, 0, 0, 0, 0, 0, -1)
start_ts = int(time.mktime(start_tt))
stop_ts = int(time.mktime(stop_tt))
alt_start_ts = int(time.mktime(alt_start_tt))
interval = 1800

synthetic_dict = {
    'start_ts': start_ts,
    'stop_ts': stop_ts,
    'interval': interval,
}
alt_dict = {
    'start_ts': alt_start_ts,
    'stop_ts': stop_ts,
    'interval': interval,
    'amplitude' : 0.5,
}
