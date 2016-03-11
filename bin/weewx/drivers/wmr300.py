#!/usr/bin/env python
# Copyright 2015 Matthew Wall
# See the file LICENSE.txt for your rights.
#
# Credits:
# Thanks to Benji for the identification and decoding of 7 packet types
#
# Thanks to Eric G for posting USB captures and providing hardware for testing
#   https://groups.google.com/forum/#!topic/weewx-development/5R1ahy2NFsk
#
# Thanks to Zahlii
#   https://bsweather.myworkbook.de/category/weather-software/
#
# No thanks to oregon scientific - repeated requests for hardware and/or
# specifications resulted in no response at all.

# TODO: battery level for each sensor
# TODO: signal strength for each sensor
# TODO: altitude
# TODO: archive interval

"""Driver for Oregon Scientific WMR300 weather stations.

Sensor data transmission frequencies:
  wind: 2.5 to 3 seconds
    TH: 10 to 12 seconds
  rain: 20 to 24 seconds

The station supports 1 wind, 1 rain, 1 UV, and up to 8 temperature/humidity
sensors.

Sniffing USB traffic shows all communication is interrupt.  The endpoint
descriptors for the device show this as well.  Response timing is 1.

The station ships with "Weather OS PRO" software for windows.  This was used
for the USB sniffing.

Internal observation names use the convention name_with_specifier.  These are
mapped to the wview or other schema as needed with a configuration setting.
For example, for the wview schema, wind_speed maps to windSpeed, temperature_0
maps to inTemp, and humidity_1 maps to outHumidity.

Message types -----------------------------------------------------------------

packet types from station:
57 - station type/model; history count
41 - ACK
D2 - history; 128 bytes
D3 - temperature/humidity/dewpoint; 61 bytes
D4 - wind; 54 bytes
D5 - rain; 40 bytes
D6 - pressure; 46 bytes
DB - forecast; 32 bytes
DC - temperature/humidity ranges; 62 bytes

packet types from host:
A6 - heartbeat
41 - ACK
65 - ? each of these is ack-ed by the station
cd - ? start history request? last two bytes are one after most recent read
35 - ? finish history request? last two bytes are latest record count
72 - ?
73 - ?

notes:
WOP sends A6 message every 20 seconds
WOP requests history at startup, then again every 120 minutes
each A6 is followed by a 57 from the station
each data packet D* from the station is followed by an ack packet 41 from host
D2 (history) records are recorded every minute
D6 (pressure) packets seem to come every 15 minutes (900 seconds)
4,5 of 7x match 12,13 of 57


Message field decodings -------------------------------------------------------

Values are stored in 1 to 3 bytes in big endian order.  Negative numbers are
stored as Two's Complement (if the first byte starts with F it is a negative
number).

no data:
 7f ff

values for channel number:
0 - console sensor
1 - sensor 1
2 - sensor 2
...
8 - sensor 8

values for trend:
0 - steady
1 - rising
2 - falling

bitwise transformation for compass direction:
1000 0000 0000 0000 = NNW
0100 0000 0000 0000 = NW
0010 0000 0000 0000 = WNW
0001 0000 0000 0000 = W
0000 1000 0000 0000 = WSW
0000 0100 0000 0000 = SW
0000 0010 0000 0000 = SSW
0000 0001 0000 0000 = S
0000 0000 1000 0000 = SSE
0000 0000 0100 0000 = SE
0000 0000 0010 0000 = ESE
0000 0000 0001 0000 = E
0000 0000 0000 1000 = ENE
0000 0000 0000 0100 = NE
0000 0000 0000 0010 = NNE
0000 0000 0000 0001 = N 

values for forecast:
0x08 - cloudy
0x0c - rainy
0x1e - partly cloudy
0x0e - partly cloudy at night
0x70 - sunny
0x00 - clear night


Message decodings -------------------------------------------------------------

message: ACK
byte hex dec description                 decoded value
 0   41  A   acknowledgement             ACK
 1   43  C
 2   4b  K
 3   73
 4   e5
 5   0a
 6   26
 7   0e
 8   c1

examples:
 41 43 4b 73 e5 0a 26 0e c1
 41 43 4b 65 19 e5 04


message: station info
byte hex dec description                 decoded value
 0   57  W   station type                WMR300
 1   4d  M
 2   52  R
 3   33  3
 4   30  0
 5   30  0
 6   2c  ,
 7   41  A   station model               A002
 8   30  0
 9   30  0
10   32  2
11   2c  ,
12   0e
13   c1
14   00
15   00
16   2c  ,
17   67      lastest history record      26391 (0x67 0x17)
18   17
19   2c  ,
20   4b
21   2c  ,
22   52
23   2c  ,

examples:
 57 4d 52 33 30 30 2c 41 30 30 32 2c 0e c1 00 00 2c 67 17 2c 4b 2c 52 2c
 57 4d 52 33 30 30 2c 41 30 30 32 2c 88 8b 00 00 2c 2f b5 2c 4b 2c 52 2c
 57 4d 52 33 30 30 2c 41 30 30 34 2c 0e c1 00 00 2c 7f e0 2c 4b 2c 49 2c
 57 4d 52 33 30 30 2c 41 30 30 34 2c 88 8b 00 00 2c 7f e0 2c 4b 2c 49 2c

message: history
byte hex dec description                 decoded value
 0   d2      packet type
 1   80  128 packet length
 2   31      count                       12694
 3   96
 4   0f   15 year                        ee if not set
 5   08    8 month                       ee if not set
 6   0a   10 day                         ee if not set
 7   06    6 hour
 8   02    2 minute
 9   00      temperature 0               21.7 C
10   d9
11   00      temperature 1               25.4 C
12   fe
13   7f      temperature 2
14   ff
15   7f      temperature 3
16   ff
17   7f      temperature 4
18   ff
19   7f      temperature 5
20   ff
21   7f      temperature 6
22   ff
23   7f      temperature 7
24   ff
25   7f      temperature 8
26   ff        (a*256 + b)/10
27   26      humidity 0                  38 %
28   49      humidity 1                  73 %
29   7f      humidity 2
30   7f      humidity 3
31   7f      humidity 4
32   7f      humidity 5
33   7f      humidity 6
34   7f      humidity 7
35   7f      humidity 8
36   00      dewpoint 1                  20.0 C
37   c8        (a*256 + b)/10
38   7f      dewpoint 2
39   ff
40   7f      dewpoint 3
41   ff
42   7f      dewpoint 4
43   ff
44   7f      dewpoint 5
45   ff
46   7f      dewpoint 6
47   ff
48   7f      dewpoint 7
49   ff
50   7f      dewpoint 8
51   ff
52   7f      heat index 1               C
53   fd        (a*256 + b)/10
54   7f      heat index 2
55   ff
56   7f      heat index 3
57   ff
58   7f      heat index 4
59   ff
60   7f      heat index 5
61   ff
62   7f      heat index 6
63   ff
64   7f      heat index 7
65   ff
66   7f      heat index 8
67   ff
68   7f      wind chill                C
69   fd        (a*256 + b)/10
70   7f      unknown
71   ff
72   00      wind gust speed           0.0 m/s
73   00        (a*256 + b)/10
74   00      wind average speed        0.0 m/s
75   00        (a*256 + b)/10
76   01      wind gust direction       283 degrees
77   1b        (a*256 + b)
78   01      wind average direction    283 degrees
78   1b        (a*256 + b)
80   30      forecast
81   00      ?
82   00      ?
83   00      hourly rain              hundredths_of_inch
84   00        (a*256 + b)
85   00      ?
86   00      accumulated rain         hundredths_of_inch
87   03        (a*256 + b)
88   0f      accumulated rain start year
89   07      accumulated rain start month
90   09      accumulated rain start day
91   13      accumulated rain start hour
92   09      accumulated rain start minute
93   00      rain rate                hundredths_of_inch/hour
94   00        (a*256 + b)
95   26      pressure                 mbar
96   ab        (a*256 + b)/10
97   01      pressure trend
98   7f      ?
99   ff      ?
100  7f      ?
101  ff      ?
102  7f      ?
103  ff      ?
104  7f      ?
105  ff      ?
106  7f      ?
107  7f      ?
108  7f      ?
109  7f      ?
110  7f      ?
111  7f      ?
112  7f      ?
113  7f      ?
114  ff      ?
115  7f      ?
116  ff      ?
117  7f      ?
118  ff      ?
119  00      ?
120  00      ?
121  00      ?
122  00      ?
123  00      ?
124  00      ?
125  00      ?
126  f8      checksum
127  3b


message: temperature/humidity/dewpoint
byte hex dec description                 decoded value
 0   D3      packet type
 1   3D   61 packet length
 2   0E   14 year
 3   05    5 month
 4   09    9 day
 5   12   12 hour
 6   14   20 minute
 7   01    1 channel number
 8   00      temperature                 19.5 C
 9   C3 
10   2D      humidity                    45 %
11   00      dewpoint                    7.0 C
12   46
13   7F      heat index?                 N/A
14   FD 
15   00      temperature trend
16   00      humidity trend
17   0E   14 max dewpoint last day year
18   05    5 month
19   09    9 day
20   0A   10 hour
21   24   36 minute
22   00      max dewpoint last day       13.0 C
23   82 
24   0E   14 min dewpoint last day year
25   05    5 month
26   09    9 day
27   10   16 hour
28   1F   31 minute
29   00      min dewpoint last day       6.0 C
30   3C 
31   0E   14 max dewpoint last month year
32   05    5 month
33   01    1 day
34   0F   15 hour
35   1B   27 minute
36   00      max dewpoint last month     13.0 C
37   82 
38   0E   14 min dewpoint last month year
39   05    5 month
40   04    4 day
41   0B   11 hour
42   08    8 minute
43   FF      min dewpoint last month     -1.0 C
44   F6 
45   0E   14 max heat index? year
46   05    5 month
47   09    9 day
48   00    0 hour
49   00    0 minute
50   7F      max heat index?             N/A
51   FF 
52   0E   14 min heat index?
53   05    5 month
54   01    1 day
55   00    0 hour
56   00    0 minute
57   7F      min heat index?             N/A
58   FF 
59   0B      checksum
60   63 

 0   41      ACK
 1   43 
 2   4B 
 3   D3      packet type
 4   01      channel number
 5   8B                                  sometimes DF

examples:
 41 43 4b d3 01 20
 41 43 4b d3 00 20


message: wind
byte hex dec description                 decoded value
 0   D4      packet type
 1   36   54 packet length
 2   0E   14 year
 3   05    5 month
 4   09    9 day
 5   12   18 hour
 6   14   20 minute
 7   01    1 channel number
 8   00      gust speed                  1.4 m/s
 9   0E 
10   00      gust direction              168 degrees
11   A8 
12   00      average speed               2.9 m/s
13   1D 
14   00      average direction           13 degrees
15   0D 
16   00      compass direction           3 N/NNE
17   03 
18   7F      windchill                   32765 N/A
19   FD 
20   0E   14 gust today year
21   05    5 month
22   09    9 day
23   10   16 hour
24   3B   59 minute
25   00      gust today                  10 m/s
26   64 
27   00      gust direction today        39 degree
28   27 
29   0E   14 gust this month year
30   05    5 month
31   09    9 day
32   10   16 hour
33   3B   59 minute
34   00      gust this month             10 m/s
35   64 
36   00      gust direction this month   39 degree
37   27 
38   0E   14 wind chill today year
39   05    5 month
40   09    9 day
41   00    0 hour
42   00    0 minute
43   7F      windchill  today            N/A
44   FF 
45   0E   14 windchill this month year
46   05    5 month
47   03    3 day
48   09    9 hour
49   04    4 minute
50   00      windchill this month        2.9 C
51   1D 
52   07      checksum
53   6A 

 0   41      ACK
 1   43 
 2   4B 
 3   D4      packet type
 4   01      channel number
 5   8B 

examples:
 41 43 4b d4 01 20
 41 43 4b d4 01 16


message: rain
byte hex dec description                 decoded value
 0   D5      packet type
 1   28  40  packet length
 2   0E  14  year
 3   05   5  month
 4   09   9  day
 5   12  18  hour
 6   15  21  minute
 7   01   1  channel number
 8   00
 9   00      rainfall this hour          0 inch
10   00
11   00 
12   00      rainfall last 24 hours      0.12 inch
13   0C  12
14   00 
15   00      rainfall accumulated        1.61 inch
16   A1 161
17   00      rainfall rate               0 inch/hr
18   00
19   0E  14  accumulated start year
20   04   4  month
21   1D  29  day
22   12  18  hour
23   00   0  minute
24   0E  14  max rate last 24 hours year
25   05   5  month
26   09   9  day
27   01   1  hour
28   0C  12  minute
29   00   0  max rate last 24 hours      0.11 inch/hr ((0x00<<8)+0x0b)/100.0
30   0B  11
31   0E  14  max rate last month year
32   05   5  month
33   02   2  day
34   04   4  hour
35   0C  12  minute
36   00   0  max rate last month         1.46 inch/hr ((0x00<<8)+0x92)/100.0
37   92 146
38   03      checksum                    794 = (0x03<<8) + 0x1a
39   1A 

 0   41      ACK
 1   43 
 2   4B 
 3   D5      packet type
 4   01      channel number
 5   8B

examples:
 41 43 4b d5 01 20
 41 43 4b d5 01 16


message: pressure
byte hex dec description                 decoded value
 0   D6      packet type
 1   2E   46 packet length
 2   0E   14 year
 3   05    5 month
 4   0D   13 day
 5   0E   14 hour
 6   30   48 minute
 7   00    1 channel number
 8   26      station pressure            981.7 mbar  ((0x26<<8)+0x59)/10.0
 9   59
10   27      sea level pressure          1015.3 mbar ((0x27<<8)+0xa9)/10.0
11   A9 
12   01      altitude meter              300 m       (0x01<<8)+0x2c
13   2C 
14   03      ?
15   00 
16   0E   14 max pressure today year
17   05    5 max pressure today month
18   0D   13 max pressure today day
19   0C   12 max pressure today hour
20   33   51 max pressure today minute
21   27      max pressure today          1015.7 mbar
22   AD 
23   0E   14 min pressure today year
24   05    5 min pressure today month
25   0D   13 min pressure today day
26   00    0 min pressure today hour
27   06    6 min pressure today minute
28   27      min pressure today          1014.1 mbar
29   9D 
30   0E   14 max pressure month year
31   05    5 max pressure month month
32   04    4 max pressure month day
33   01    1 max pressure month hour
34   15   21 max pressure month minute
35   27      max pressure month          1022.5 mbar
36   F1 
37   0E   14 min pressure month year
38   05    5 min pressure month month
39   0B   11 min pressure month day
40   00    0 min pressure month hour
41   06    6 min pressure month minute
42   27      min pressure month          1007.8 mbar
43   5E 
44   06      checksum
45   EC 

 0   41      ACK
 1   43 
 2   4B 
 3   D6      packet type
 4   00      channel number
 5   8B 

examples:
 41 43 4b d6 00 20


message: forecast
byte hex dec description                 decoded value
 0   DB
 1   20
 2   0F  15  year
 3   07   7  month
 4   09   9  day
 5   12  18  hour
 6   23  35  minute
 7   00
 8   FA
 9   79
10   FC
11   40
12   01
13   4A
14   06
15   17
16   14
17   23
18   06
19   01
20   00
21   00
22   01
23   01
24   01
25   00
26   00
27   00
28   FE
29   00
30   05      checksum
31   A5

 0   41      ACK
 1   43 
 2   4B 
 3   D6      packet type
 4   00      channel number
 5   20

examples:
 41 43 4b db 00 20


message: temperature/humidity ranges
byte hex dec description                 decoded value
 0   DC      packet type
 1   3E   62 packet length
 2   0E   14 year
 3   05    5 month
 4   0D   13 day
 5   0E   14 hour
 6   30   48 minute
 7   00    0 channel number
 8   0E   14 max temp today year
 9   05    5 month
10   0D   13 day
11   00    0 hour
12   00    0 minute
13   00      max temp today              20.8 C
14   D0 
15   0E   14 min temp today year
16   05    5 month
17   0D   13 day
18   0B   11 hour
19   34   52 minute
20   00      min temp today              19.0 C
21   BE 
22   0E   14 max temp month year
23   05    5 month
24   0A   10 day
25   0D   13 hour
26   19   25 minute
27   00      max temp month              21.4 C
28   D6 
29   0E   14 min temp month year
30   05    5 month
31   04    4 day
32   03    3 hour
33   2A   42 minute
34   00      min temp month              18.1 C
35   B5 
36   0E   14 max humidity today year
37   05    5 month
38   0D   13 day
39   05    5 hour
40   04    4 minute
41   45      max humidity today          69 %
42   0E   14 min numidity today year
43   05    5 month
44   0D   13 day
45   0B   11 hour
46   32   50 minute
47   41      min humidity today          65 %
48   0E   14 max humidity month year
49   05    5 month
50   0C   12 day
51   13   19 hour
52   32   50 minute
53   46      max humidity month          70 %
54   0E   14 min humidity month year
55   05    5 month
56   04    4 day
57   14   20 hour
58   0E   14 minute
59   39      min humidity month          57 %
60   07      checksum
61   BF 

 0   41      ACK
 1   43 
 2   4B 
 3   DC      packet type
 4   00    0 channel number
 5   8B 

examples:
 41 43 4b dc 01 20
 41 43 4b dc 00 20
 41 43 4b dc 01 16
 41 43 4b dc 00 16

"""

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers
import weewx.wxformulas
from weeutil.weeutil import timestamp_to_string

DRIVER_NAME = 'WMR300'
DRIVER_VERSION = '0.9'

DEBUG_COMM = 0
DEBUG_LOOP = 0
DEBUG_COUNTS = 0
DEBUG_DECODE = 0
DEBUG_HISTORY = 0


def loader(config_dict, _):
    return WMR300Driver(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WMR300ConfEditor()


def logmsg(level, msg):
    syslog.syslog(level, 'wmr300: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

def _fmt_bytes(data):
    return ' '.join(['%02x' % x for x in data])

def _lo(x):
    return x - 256 * (x >> 8)

def _hi(x):
    return x >> 8


class WMR300Driver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with a WMR300 weather station."""

    # the default map is for the wview schema
    DEFAULT_MAP = {
        'pressure': 'pressure',
        'barometer': 'barometer',
        'wind_avg': 'windSpeed',
        'wind_dir': 'windDir',
        'wind_gust': 'windGust',
        'wind_gust_dir': 'windGustDir',
        'temperature_0': 'inTemp',
        'temperature_1': 'outTemp',
        'temperature_2': 'extraTemp1',
        'temperature_3': 'extraTemp2',
        'temperature_4': 'extraTemp3',
        'humidity_0': 'inHumidity',
        'humidity_1': 'outHumidity',
        'humidity_2': 'extraHumid1',
        'humidity_3': 'extraHumid2',
        'dewpoint_1': 'dewpoint',
        'heatindex_1': 'heatindex',
        'windchill': 'windchill',
        'rain_rate': 'rainRate'
        }

    def __init__(self, **stn_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        self.model = stn_dict.get('model', 'WMR300')
        self.obs_map = stn_dict.get('map', self.DEFAULT_MAP)
        self.heartbeat = 20 # how often to send a6 messages, in seconds
        self.history_retry = 60 # how often to retry history, in seconds
        global DEBUG_COMM
        DEBUG_COMM = int(stn_dict.get('debug_comm', DEBUG_COMM))
        global DEBUG_LOOP
        DEBUG_LOOP = int(stn_dict.get('debug_loop', DEBUG_LOOP))
        global DEBUG_COUNTS
        DEBUG_COUNTS = int(stn_dict.get('debug_counts', DEBUG_COUNTS))
        global DEBUG_DECODE
        DEBUG_DECODE = int(stn_dict.get('debug_decode', DEBUG_DECODE))
        global DEBUG_HISTORY
        DEBUG_HISTORY = int(stn_dict.get('debug_history', DEBUG_HISTORY))
        self.last_rain = None
        self.last_rain_historical = None
        self.cached = dict()
        self.last_a6 = 0
        self.last_65 = 0
        self.last_7x = 0
        self.last_record = 0
        self.station = Station()
        self.station.open()

    def closePort(self):
        self.station.close()
        self.station = None

    @property
    def hardware_name(self):
        return self.model

    def genLoopPackets(self):
        while True:
            try:
                buf = self.station.read()
                if buf:
                    pkt = Station.decode(buf)
                    if buf[0] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]:
                        # send ack for most data packets
                        # FIXME: what is last number in the ACK?
                        # observed: 0x00 0x20 0xc1 0xc7 0xa0 0x99
                        cmd = [0x41, 0x43, 0x4b, buf[0], buf[7], _lo(self.last_record)]
                        self.station.write(cmd)
                        packet = self.convert_loop(pkt)
                        self.cached.update(packet)
                        yield self.cached
                if time.time() - self.last_a6 > self.heartbeat:
                    logdbg("request station status: %s (%02x)" %
                           (self.last_record, _lo(self.last_record)))
                    cmd = [0xa6, 0x91, 0xca, 0x45, 0x52, _lo(self.last_record)]
                    self.station.write(cmd)
                    self.last_a6 = time.time()
                if self.last_7x == 0:
                    # FIXME: what are the 72/73 messages?
                    # observed:
                    # 73 e5 0a 26 0e c1
                    # 73 e5 0a 26 88 8b
                    # 72 a9 c1 60 52 00
#                    cmd = [0x72, 0xa9, 0xc1, 0x60, 0x52, 0x00]
                    cmd = [0x73, 0xe5, 0x0a, 0x26, 0x88, 0x8b]
#                    cmd = [0x73, 0xe5, 0x0a, 0x26, 0x0e, 0xc1]
                    self.station.write(cmd)
                    self.last_7x = time.time()
            except usb.USBError, e:
                if not e.args[0].find('No data available'):
                    raise weewx.WeeWxIOError(e)
            except (WrongLength, BadChecksum), e:
                loginf(e)
            time.sleep(0.001)

    def genStartupRecords(self, since_ts):
        loginf("reading records since %s" % timestamp_to_string(since_ts))
        hbuf = None
        last_ts = None
        cnt = 0
        while True:
            try:
                buf = self.station.read()
                if buf:
                    if buf[0] == 0xd2:
                        hbuf = buf
                        buf = None
                    elif buf[0] == 0x7f and hbuf is not None:
                        # FIXME: need better indicator of second half history
                        buf = hbuf + buf
                        hbuf = None
                if buf and buf[0] == 0xd2:
                    self.last_record = Station.get_record_index(buf)
                    ts = Station._extract_ts(buf[4:9])
                    if ts is not None and ts > since_ts:
                        keep = True if last_ts is not None else False
                        pkt = Station.decode(buf)
                        packet = self.convert_historical(pkt, ts, last_ts)
                        last_ts = ts
                        if keep:
                            logdbg("historical record: %s" % packet)
                            cnt += 1
                            yield packet
                if buf and buf[0] == 0x57:
                    idx = Station.get_latest_index(buf)
                    msg = "count=%s last_index=%s latest_index=%s" % (
                        cnt, self.last_record, idx)
                    if self.last_record + 1 >= idx:
                        loginf("catchup complete: %s" % msg)
                        break
                    loginf("catchup in progress: %s" % msg)
                if buf and buf[0] == 0x41 and buf[3] == 0x65:
                    nxtrec = Station.get_next_index(self.last_record)
                    logdbg("request records starting with %s" % nxtrec)
                    cmd = [0xcd, 0x18, 0x30, 0x62, _hi(nxtrec), _lo(nxtrec)]
                    self.station.write(cmd)
                if time.time() - self.last_a6 > self.heartbeat:
                    logdbg("request station status: %s (%02x)" %
                           (self.last_record, _lo(self.last_record)))
                    cmd = [0xa6, 0x91, 0xca, 0x45, 0x52, _lo(self.last_record)]
                    self.station.write(cmd)
                    self.last_a6 = time.time()
                if self.last_7x == 0:
                    # FIXME: what does 72/73 do?
                    cmd = [0x73, 0xe5, 0x0a, 0x26, 0x88, 0x8b]
                    self.station.write(cmd)
                    self.last_7x = time.time()
                if time.time() - self.last_65 > self.history_retry:
                    logdbg("initiate record request: %s (%02x)" %
                           (self.last_record, _lo(self.last_record)))
                    cmd = [0x65, 0x19, 0xe5, 0x04, 0x52, _lo(self.last_record)]
                    self.station.write(cmd)
                    self.last_65 = time.time()
            except usb.USBError, e:
                if not e.args[0].find('No data available'):
                    raise weewx.WeeWxIOError(e)
            except (WrongLength, BadChecksum), e:
                loginf(e)
            time.sleep(0.001)        

    def convert(self, pkt, ts):
        p = {'dateTime': ts, 'usUnits': weewx.METRICWX}
        for label in self.obs_map:
            if label in pkt:
                p[self.obs_map[label]] = pkt[label]
        return p

    def convert_historical(self, pkt, ts, last_ts):
        p = self.convert(pkt, ts)
        if last_ts is not None:
            p['interval'] = ts - last_ts
        if 'rain_total' in pkt:
            total = pkt['rain_total']
            p['rain'] = weewx.wxformulas.calculate_rain(
                total, self.last_rain_historical)
            self.last_rain_historical = total
        return p

    def convert_loop(self, pkt):
        p = self.convert(pkt, int(time.time() + 0.5))
        if 'rain_total' in pkt:
            total = pkt['rain_total']
            p['rain'] = weewx.wxformulas.calculate_rain(total, self.last_rain)
            self.last_rain = total
        # add all observations if we are debugging loop data.  ignore any
        # observations that are non-numeric.
        if DEBUG_LOOP:
            for label in pkt:
                if not label in p:
                    try:
                        p[label] = float(pkt[label])
                    except (ValueError, TypeError):
                        pass
        return p


class WMR300Error(weewx.WeeWxIOError):
    """map station errors to weewx io errors"""

class WrongLength(WMR300Error):
    """bad packet length"""

class BadChecksum(WMR300Error):
    """bogus checksum"""


class Station(object):
    # these identify the weather station on the USB
    VENDOR_ID = 0x0FDE
    PRODUCT_ID = 0xCA08
    MESSAGE_LENGTH = 64
    EP_IN = 0x81
    EP_OUT = 0x01
    MAX_RECORDS = 50000 # FIXME: what is maximum number of records?
    COMPASS = {
        32768: 337.5,
        16384: 315.0,
        8192: 292.5,
        4096: 270.0,
        2048: 247.5,
        1024: 225.0,
        512: 202.5,
        256: 180.0,
        128: 157.5,
        64: 135.0,
        32: 112.5,
        16: 90.0,
        8: 67.5,
        4: 45.0,
        2: 22.5,
        1: 0.0}

    def __init__(self, vend_id=VENDOR_ID, prod_id=PRODUCT_ID):
        self.vendor_id = vend_id
        self.product_id = prod_id
        self.handle = None
        self.timeout = 100
        self.interface = 0
        self.recv_counts = dict()
        self.send_counts = dict()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):  # @UnusedVariable
        self.close()

    def open(self):
        dev = self._find_dev(self.vendor_id, self.product_id)
        if not dev:
            raise WMR300Error("Unable to find station on USB: "
                              "cannot find device with "
                              "VendorID=0x%04x ProductID=0x%04x" %
                              (self.vendor_id, self.product_id))

        self.handle = dev.open()
        if not self.handle:
            raise WMR300Error('Open USB device failed')

        self.handle.reset()

        # for HID devices on linux, be sure kernel does not claim the interface
        try:
            self.handle.detachKernelDriver(self.interface)
        except (AttributeError, usb.USBError):
            pass

        # attempt to claim the interface
        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError, e:
            self.close()
            raise WMR300Error("Unable to claim interface %s: %s" %
                              (self.interface, e))

    def close(self):
        if self.handle is not None:
            try:
                self.handle.releaseInterface()
            except (ValueError, usb.USBError), e:
                loginf("Release interface failed: %s" % e)
            self.handle = None

    def reset(self):
        self.handle.reset()

    def read(self, count=True):
        buf = None
        try:
            buf = self.handle.interruptRead(
                Station.EP_IN, self.MESSAGE_LENGTH, self.timeout)
            if DEBUG_COMM:
                logdbg("read: %s" % _fmt_bytes(buf))
            if DEBUG_COUNTS and count:
                self.update_count(buf, self.recv_counts)
        except usb.USBError, e:
            if not e.args[0].find('No data available'):
                raise
        return buf

    def write(self, buf):
        if DEBUG_COMM:
            logdbg("write: %s" % _fmt_bytes(buf))
        # pad with zeros up to the standard message length
        while len(buf) < self.MESSAGE_LENGTH:
            buf.append(0x00)
        sent = self.handle.interruptWrite(Station.EP_OUT, buf, self.timeout)
        if DEBUG_COUNTS:
            self.update_count(buf, self.send_counts)
        return sent

    # keep track of the message types for debugging purposes
    @staticmethod
    def update_count(buf, count_dict):
        label = 'empty'
        if buf and len(buf) > 0:
            if buf[0] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]:
                # message type and channel for data packets
                label = '%02x:%d' % (buf[0], buf[7])
            elif (buf[0] in [0x41] and
                  buf[3] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]):
                # message type and channel for data ack packets
                label = '%02x:%02x:%d' % (buf[0], buf[3], buf[4])
            else:
                # otherwise just track the message type
                label = '%02x' % buf[0]
        if label in count_dict:
            count_dict[label] += 1
        else:
            count_dict[label] = 1
        cstr = []
        for k in sorted(count_dict):
            cstr.append('%s: %s' % (k, count_dict[k]))
        logdbg('counts: %s' % ''.join(cstr))

    @staticmethod
    def _find_dev(vendor_id, product_id):
        """Find the first device with vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    logdbg('Found station at bus=%s device=%s' %
                           (bus.dirname, dev.filename))
                    return dev
        return None

    @staticmethod
    def _verify_length(label, length, buf):
        if buf[1] != length:
            raise WrongLength("%s: wrong length: expected %02x, got %02x" %
                              (label, length, buf[1]))

    @staticmethod
    def _verify_checksum(label, buf, msb_first=True):
        """Calculate and compare checksum"""
        try:
            cs1 = Station._calc_checksum(buf)
            cs2 = Station._extract_checksum(buf, msb_first)
            if cs1 != cs2:
                raise BadChecksum("%s: bad checksum: %04x != %04x" %
                                  (label, cs1, cs2))
        except IndexError, e:
            raise BadChecksum("%s: not enough bytes for checksum: %s" %
                              (label, e))

    @staticmethod
    def _calc_checksum(buf):
        cs = 0
        for x in buf[:-2]:
            cs += x
        return cs

    @staticmethod
    def _extract_checksum(buf, msb_first):
        if msb_first:
            return (buf[-2] << 8) | buf[-1]
        return (buf[-1] << 8) | buf[-2]

    @staticmethod
    def _extract_ts(buf):
        if buf[0] == 0xee and buf[1] == 0xee and buf[2] == 0xee:
            # year, month, and day are 0xee when timestamp is unset
            return None
        try:
            year = int(buf[0]) + 2000
            month = int(buf[1])
            day = int(buf[2])
            hour = int(buf[3])
            minute = int(buf[4])
            return time.mktime((year, month, day, hour, minute, 0, -1, -1, -1))
        except IndexError:
            raise WMR300Error("buffer too short for timestamp")
        except (OverflowError, ValueError), e:
            raise WMR300Error(
                "cannot create timestamp from y:%s m:%s d:%s H:%s M:%s: %s" %
                (buf[0], buf[1], buf[2], buf[3], buf[4], e))

    @staticmethod
    def _extract_signed(hi, lo, m):
        if hi == 0x7f:
            return None
        s = 0
        if hi & 0xf0 == 0xf0:
            s = 0x10000
        return ((hi << 8) + lo - s) * m

    @staticmethod
    def _extract_value(buf, m):
        if buf[0] == 0x7f:
            return None
        if len(buf) == 2:
            return ((buf[0] << 8) + buf[1]) * m
        return buf[0] * m

    @staticmethod
    def _extract_heading(buf):
        if buf[0] == 0x7f:
            return None
        x = (buf[0] << 8) + buf[1]
        cnt = 0
        v = 0
        for c in Station.COMPASS:
            if x & c != 0:
                cnt += 1
                v += Station.COMPASS[c]
        if cnt:
            return v / cnt
        return None

    @staticmethod
    def get_latest_index(buf):
        # get the index of the most recent history record
        if buf[0] != 0x57:
            return None
        return (buf[17] << 8) + buf[18]

    @staticmethod
    def get_next_index(n):
        # return the index of the record after indicated index
        if n == 0:
            return 0x20
        if n + 1 > Station.MAX_RECORDS:
            return 0x20 # FIXME: verify the wraparound
        return n + 1

    @staticmethod
    def get_record_index(buf):
        # extract the index from the history record
        if buf[0] != 0xd2:
            return None
        return (buf[2] << 8) + buf[3]

    @staticmethod
    def decode(buf):
        try:
            pkt = getattr(Station, '_decode_%02x' % buf[0])(buf)
            if DEBUG_DECODE:
                logdbg('%s %s' % (_fmt_bytes(buf), pkt))
            return pkt
        except AttributeError:
            raise WMR300Error("unknown packet type %02x: %s" %
                              (buf[0], _fmt_bytes(buf)))

    @staticmethod
    def _decode_57(buf):
        """57 packet contains station information"""
        pkt = dict()
        pkt['station_type'] = ''.join("%s" % chr(x) for x in buf[0:6])
        pkt['station_model'] = ''.join("%s" % chr(x) for x in buf[7:11])
        if DEBUG_HISTORY:
            nrec = (buf[17] << 8) + buf[18]
            logdbg("history records: %s" % nrec)
        return pkt

    @staticmethod
    def _decode_41(_):
        """41 43 4b is ACK"""
        pkt = dict()
        return pkt

    @staticmethod
    def _decode_d2(buf):
        """D2 packet contains history data"""
        Station._verify_length("D2", 0x80, buf)
        Station._verify_checksum("D2", buf[:0x80], msb_first=False)
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[4:9])
        for i in range(0, 9):
            pkt['temperature_%d' % i] = Station._extract_signed(
                buf[9 + 2 * i], buf[10 + 2 * i], 0.1) # C
            pkt['humidity_%d' % i] = Station._extract_value(
                buf[27 + i:28 + i], 1.0) # %
        for i in range(1, 9):
            pkt['dewpoint_%d' % i] = Station._extract_signed(
                buf[36 + 2 * i], buf[37 + 2 * i], 0.1) # C
            pkt['heatindex_%d' % i] = Station._extract_signed(
                buf[52 + 2 * i], buf[53 + 2 * i], 0.1) # C
        pkt['windchill'] = Station._extract_signed(buf[68], buf[69], 0.1) # C
        pkt['wind_gust'] = Station._extract_value(buf[72:74], 0.1) # m/s
        pkt['wind_avg'] = Station._extract_value(buf[74:76], 0.1) # m/s
        pkt['wind_gust_dir'] = Station._extract_value(buf[76:78], 1.0) # degree
        pkt['wind_dir'] = Station._extract_value(buf[78:80], 1.0) # degree
        pkt['forecast'] = Station._extract_value(buf[80:81], 1.0)
        pkt['rain_hour'] = Station._extract_value(buf[83:85], 0.254) # mm
        pkt['rain_total'] = Station._extract_value(buf[86:88], 0.254) # mm
        pkt['rain_start_dateTime'] = Station._extract_ts(buf[88:93])
        pkt['rain_rate'] = Station._extract_value(buf[93:95], 0.254) # mm/hour
        pkt['pressure'] = Station._extract_value(buf[95:97], 0.1) # mbar
        pkt['pressure_trend'] = Station._extract_value(buf[97:98], 1.0)
        return pkt

    @staticmethod
    def _decode_d3(buf):
        """D3 packet contains temperature/humidity data"""
        Station._verify_length("D3", 0x3d, buf)
        Station._verify_checksum("D3", buf[:0x3d])
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['temperature_%d' % pkt['channel']] = Station._extract_signed(
            buf[8], buf[9], 0.1) # C
        pkt['humidity_%d' % pkt['channel']] = Station._extract_value(
            buf[10:11], 1.0) # %
        pkt['dewpoint_%d' % pkt['channel']] = Station._extract_signed(
            buf[11], buf[12], 0.1) # C
        return pkt

    @staticmethod
    def _decode_d4(buf):
        """D4 packet contains wind data"""
        Station._verify_length("D4", 0x36, buf)
        Station._verify_checksum("D4", buf[:0x36])
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['wind_gust'] = Station._extract_value(buf[8:10], 0.1) # m/s
        pkt['wind_gust_dir'] = Station._extract_value(buf[10:12], 1.0) # degree
        pkt['wind_avg'] = Station._extract_value(buf[12:14], 0.1) # m/s
        pkt['wind_avg_dir'] = Station._extract_value(buf[14:16], 1.0) # degree
        pkt['wind_dir'] = Station._extract_heading(buf[16:18])
        return pkt

    @staticmethod
    def _decode_d5(buf):
        """D5 packet contains rain data"""
        Station._verify_length("D5", 0x28, buf)
        Station._verify_checksum("D5", buf[:0x28])
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['rain_hour'] = Station._extract_value(buf[9:11], 0.254) # mm
        pkt['rain_24_hour'] = Station._extract_value(buf[12:14], 0.254) # mm
        pkt['rain_total'] = Station._extract_value(buf[15:17], 0.254) # mm
        pkt['rain_rate'] = Station._extract_value(buf[17:19], 0.254) # mm/hour
        return pkt

    @staticmethod
    def _decode_d6(buf):
        """D6 packet contains pressure data"""
        Station._verify_length("D6", 0x2e, buf)
        Station._verify_checksum("D6", buf[:0x2e])
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['pressure'] = Station._extract_value(buf[8:10], 0.1) # mbar
        pkt['barometer'] = Station._extract_value(buf[10:12], 0.1) # mbar
        pkt['altitude'] = Station._extract_value(buf[12:14], 1.0) # meter
        return pkt

    @staticmethod
    def _decode_dc(buf):
        """DC packet contains temperature/humidity range data"""
        Station._verify_length("DC", 0x3e, buf)
        Station._verify_checksum("DC", buf[:0x3e])
        pkt = dict()
        pkt['ts'] = Station._extract_ts(buf[2:7])
        return pkt

    @staticmethod
    def _decode_db(buf):
        """DB packet is forecast"""
        Station._verify_length("DB", 0x20, buf)
        Station._verify_checksum("DB", buf[:0x20])
        pkt = dict()
        return pkt


class WMR300ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR300]
    # This section is for WMR300 weather stations.

    # The station model, e.g., WMR300A
    model = WMR300

    # The driver to use:
    driver = weewx.drivers.wmr300
"""

    def modify_config(self, config_dict):
        print """
Setting rainRate, windchill, heatindex, and dewpoint calculations to hardware."""
        config_dict['StdWXCalculate']['rainRate'] = 'hardware'
        config_dict['StdWXCalculate']['windchill'] = 'hardware'
        config_dict['StdWXCalculate']['heatindex'] = 'hardware'
        config_dict['StdWXCalculate']['dewpoint'] = 'hardware'


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/user/wmr300.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    syslog.openlog('wmr300', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    (options, args) = parser.parse_args()

    if options.version:
        print "wmr300 driver version %s" % DRIVER_VERSION
        exit(0)

    stn_dict = {
        'debug_comm': 1,
        'debug_loop': 0,
        'debug_counts': 1,
        'debug_decode': 0
        }
    stn = WMR300Driver(**stn_dict)

    for packet in stn.genLoopPackets():
        print packet
