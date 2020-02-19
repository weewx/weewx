#!/usr/bin/env python
# Copyright 2015 Matthew Wall
# See the file LICENSE.txt for your rights.
#
# Credits:
# Thanks to Cameron for diving deep into USB timing issues
#
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

# TODO: figure out battery level for each sensor
# TODO: figure out signal strength for each sensor

# FIXME: These all seem to offer low value return and unlikely to be done.
#  In decreasing order of usefulness:
#   1. warn if altitude in pressure packet does not match weewx altitude
#   2. If rain is being accumulated when weewx is stopped, and we need to retrieve
#      the history record then the current code returns None for the rain in
#      the earliest new time interval and the rain increment for that time will
#      get added to and reported at the next interval.    
#   3. figure out unknown bytes in history packet (probably nothing useful)
#   4. decode the 0xdb (forecast) packets

"""Driver for Oregon Scientific WMR300 weather stations.

Sensor data transmission frequencies:
  wind: 2.5 to 3 seconds
    TH: 10 to 12 seconds
  rain: 20 to 24 seconds

The station supports 1 wind, 1 rain, 1 UV, and up to 8 temperature/humidity
sensors.

The station ships with "Weather OS PRO" software for windows.  This was used
for the USB sniffing.

Sniffing USB traffic shows all communication is interrupt.  The endpoint
descriptors for the device show this as well.  Response timing is 1.

It appears that communication must be initiated with an interrupted write.
After that, the station will spew data.  Sending commands to the station is
not reliable - like other Oregon Scientific hardware, there is a certain
amount of "send a command, wait to see what happens, then maybe send it again"
in order to communicate with the hardware.  Once the station does start sending
data, the driver basically just processes it based on the message type.  It
must also send "heartbeat" messages to keep the data flowing from the hardware.

Communication is confounded somewhat by the various libusb implementations.
Some communication "fails" with a "No data available" usb error.  But in other
libusb versions, this error does not appear.  USB timeouts are also tricky.
Since the WMR protocol seems to expect timeouts, it is necessary for the
driver to ignore them at some times, but not at others.  Since not every libusb
version includes a code/class to indicate that a USB error is a timeout, the
driver must do more work to figure it out.

The driver ignores USB timeouts.  It would seem that a timeout just means that
the station is not ready to communicate; it does not indicate a communication
failure.

Internal observation names use the convention name_with_specifier.  These are
mapped to the wview or other schema as needed with a configuration setting.
For example, for the wview schema, wind_speed maps to windSpeed, temperature_0
maps to inTemp, and humidity_1 maps to outHumidity.

Maximum value for rain counter is 400 in (10160 mm) (40000 = 0x9c 0x40).  The
counter does not wrap; it must be reset when it hits maximum value otherwise
rain data will not be recorded.


Message types -----------------------------------------------------------------

packet types from station:
57 - station type/model; history count + other status
41 - ACK
D2 - history; 128 bytes
D3 - temperature/humidity/dewpoint/heatindex; 61 bytes
D4 - wind/windchill; 54 bytes
D5 - rain; 40 bytes
D6 - pressure; 46 bytes
DB - forecast; 32 bytes
DC - temperature/humidity ranges; 62 bytes

packet types from host:
A6 - heartbeat - response is 57 (usually)
41 - ACK
65 - do not delete history when it is reported.  each of these is ack-ed by
       the station
b3 - delete history after you give it to me.
cd - start history request.  last two bytes are one after most recent read
35 - finish history request.  last two bytes are latest record index that
       was read.
73 - some sort of initialisation packet
72 - ? on rare occasions will be used in place of 73, in both observed cases
       the console was already free-running transmitting data

WOP sends A6 message every 20 seconds
WOP requests history at startup, then again every 120 minutes
each A6 is followed by a 57 from the station, except the one initiating history
each data packet D* from the station is followed by an ack packet 41 from host
D2 (history) records are recorded every minute
D6 (pressure) packets seem to come every 15 minutes (900 seconds)
4,5 of 7x match 12,13 of 57

examples of 72/73 initialization packets:
  73 e5 0a 26 0e c1
  73 e5 0a 26 88 8b
  72 a9 c1 60 52 00

---- cameron's extra notes:

Station will free-run transmitting data for about 100s without seeing an ACK.
a6 will always be followed by 91 ca 45 52 but final byte may be 0, 20, 32, 67,
8b, d6, df, or...
    0 - when first packet after connection or program startup.
    It looks like the final byte is just the last character that was previously
    written to a static output buffer.  and hence it is meaningless.
41 - ack in - 2 types
41 - ack out - numerous types. combinations of packet type, channel, last byte.
    For a6, it looks like the last byte is just uncleared residue.
b3 59 0a 17 01 <eb>   - when you give me history, delete afterwards
                      - final 2 bytes are probably ignored
    response: ACK b3 59 0a 17
65 19 e5 04 52 <b6>   - when you give me history, do not delete afterwards
                      - final 2 bytes are probably ignored
    response: ACK 65 19 e5 04
cd 18 30 62 nn mm  - start history, starting at record 0xnnmm
    response - if preceeded by 65, the ACK is the same string:  ACK 65 19 e5 04
             - if preceeded by b3 then there is NO ACK.

Initialisation:
out: a6 91 ca 45 52
     - note: null 6th byte.
in:  57:  WMR300,A004,<b13><b14>\0\0,<history index>,<b21>,<b23>,
     - where numbered bytes are unknown content
then either...
out: 73 e5 0a 26 <b5> <b6>
     - b5 is set to b13 of pkt 57, b6 <= b14
in:  41 43 4b 73 e5 0a 26 <b8> <b9>
     - this is the full packet 73 prefixed by "ACK"
or...
out: 72 a9 c1 60 52
     - occurs when console is already free-running (but how does WOsP know?)
NO ACK

Message field decodings -------------------------------------------------------

Values are stored in 1 to 3 bytes in big endian order.  Negative numbers are
stored as Two's Complement (if the first byte starts with F it is a negative
number). Count values are unsigned.

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
3 - no sensor data

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
byte hex dec description         decoded value
 0   41  A   acknowledgement     ACK
 1   43  C
 2   4b  K
 3   73                          command sent from PC
 4   e5
 5   0a
 6   26
 7   0e
 8   c1

examples:
 41 43 4b 73 e5 0a 26 0e c1      last 2 bytes differ
 41 43 4b 65 19 e5 04            always same


message: station info
byte hex dec description         decoded value
 0   57  W   station type        WMR300
 1   4d  M
 2   52  R
 3   33  3
 4   30  0
 5   30  0
 6   2c  ,
 7   41  A   station model       A002
 8   30  0
 9   30  0
10   32  2                       or 0x34
11   2c  ,
12   0e                          (3777 dec) or mine always 88 8b (34955)
13   c1
14   00                          always?
15   00
16   2c  ,
17   67      next history record 26391 (0x67*256 0x17) (0x7fe0 (32736) is full)
                                 The value at this index has not been used yet.
18   17
19   2c  ,
20   4b      usually 'K' (0x4b). occasionally was 0x43 when history is set to
  or 43      delete after downloading.  This is a 1-bit change (1<<3)
             NB: Does not return to 4b when latest history record is reset to
             0x20 after history is deleted. 
21   2c  ,
22   52      0x52 (82, 'R'), occasionally 0x49(73, 'G')
             0b 0101 0010   (0x52) vs
             0b 0100 1001   (0x49) lots of bits flipped!
  or 49      this maybe has some link with one or other battery, but does not
             make sense
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
 2   31      count (hi)                  12694  - index number of this packet
 3   96      count (lo)
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
70   7f      ?
71   ff      ?
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
13   7F      heat index                  N/A
14   FD 
15   00      temperature trend
16   00      humidity trend?             not sure - never saw a falling value
17   0E   14 max_dewpoint_last_day year
18   05    5 month
19   09    9 day
20   0A   10 hour
21   24   36 minute
22   00      max_dewpoint_last_day       13.0 C
23   82 
24   0E   14 min_dewpoint_last_day year
25   05    5 month
26   09    9 day
27   10   16 hour
28   1F   31 minute
29   00      min_dewpoint_last_day       6.0 C
30   3C 
31   0E   14 max_dewpoint_last_month year
32   05    5 month
33   01    1 day
34   0F   15 hour
35   1B   27 minute
36   00      max_dewpoint_last_month     13.0 C
37   82 
38   0E   14 min_dewpoint_last_month year
39   05    5 month
40   04    4 day
41   0B   11 hour
42   08    8 minute
43   FF      min_dewpoint_last_month     -1.0 C
44   F6 
45   0E   14 max_heat_index year
46   05    5 month
47   09    9 day
48   00    0 hour
49   00    0 minute
50   7F      max_heat_index              N/A
51   FF 
52   0E   14 min_heat_index year
53   05    5 month
54   01    1 day
55   00    0 hour
56   00    0 minute
57   7F      min_heat_index              N/A
58   FF 
59   0B      checksum
60   63 

 0   41      ACK
 1   43 
 2   4B 
 3   D3      packet type
 4   01      channel number
 5   8B                                  sometimes DF and others

examples:
 41 43 4b d3 00 20      - for last byte: 32, 67, 8b, d6
 41 43 4b d3 01 20      - for last byte: same + 20, df
 for unused temps, last byte always 8b (or is it byte 14 of pkt 57?)


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
 5   8B      variable

examples:
 41 43 4b d4 01 20      - last byte: 20, 32, 67, 8b, d6, df
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
 41 43 4b d5 01 20     - last byte: 20, 32, 67, 8b, d6, df
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
14   03      barometric trend            have seen 0,1,2, and 3
15   00      only ever observed 0 or 2.  is this battery?
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
 41 43 4b d6 00 20     - last byte: 32, 67, 8b


message: forecast
byte hex dec description                 decoded value
 0   DB
 1   20         pkt length
 2   0F  15  year
 3   07   7  month
 4   09   9  day
 5   12  18  hour
 6   23  35  minute
 7   00         below are alternate observations - little overlap
 8   FA         0a
 9   79         02, 22, 82, a2
10   FC         05
11   40         f9
12   01         fe
13   4A         fc
14   06         variable
15   17         variable
16   14         variable
17   23         variable
18   06         00 to 07 (no 01)
19   01 
20   00         00 or 01
21   00    remainder same     
22   01
23   01
24   01
25   00
26   00
27   00
28   FE
29   00
30   05      checksum (hi)
31   A5      checksum (lo)

 0   41      ACK
 1   43 
 2   4B 
 3   D6      packet type
 4   00      channel number
 5   20

examples:
 41 43 4b db 00 20     - last byte: 32, 67, 8b, d6


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
 41 43 4b dc 00 20     - last byte: 32, 67, 8b, d6
 41 43 4b dc 01 20     - last byte: 20, 32, 67, 8b, d6, df
 41 43 4b dc 00 16
 41 43 4b dc 01 16

"""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function
import logging
import time
import usb

import weewx.drivers
import weewx.wxformulas
from weeutil.weeutil import timestamp_to_string

log = logging.getLogger(__name__)

DRIVER_NAME = 'WMR300'
DRIVER_VERSION = '0.33'

DEBUG_COMM = 0
DEBUG_PACKET = 0
DEBUG_COUNTS = 0
DEBUG_DECODE = 0
DEBUG_HISTORY = 1
DEBUG_RAIN = 0
DEBUG_TIMING = 1


def loader(config_dict, _):
    return WMR300Driver(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WMR300ConfEditor()


def _fmt_bytes(data):
    return ' '.join(['%02x' % x for x in data])

def _lo(x):
    return x - 256 * (x >> 8)

def _hi(x):
    return x >> 8

# pyusb 0.4.x does not provide an errno or strerror with the usb errors that
# it wraps into USBError.  so we have to compare strings to figure out exactly
# what type of USBError we are dealing with.  unfortunately, those strings are
# localized, so we must compare in every language.
USB_NOERR_MESSAGES = [
    'No data available', 'No error',
    'Nessun dato disponibile', 'Nessun errore',
    'Keine Daten verf',
    'No hay datos disponibles',
    'Pas de donn',
    'Ingen data er tilgjengelige']

# these are the usb 'errors' that should be ignored
def is_noerr(e):
    errmsg = repr(e)
    for msg in USB_NOERR_MESSAGES:
        if msg in errmsg:
            return True
    return False

# strings for the timeout error
USB_TIMEOUT_MESSAGES = [
    'Connection timed out',
    'Operation timed out']

# detect usb timeout error (errno 110)
def is_timeout(e):
    if hasattr(e, 'errno') and e.errno == 110:
        return True
    errmsg = repr(e)
    for msg in USB_TIMEOUT_MESSAGES:
        if msg in errmsg:
            return True
    return False

def get_usb_info():
    pyusb_version = '0.4.x'
    try:
        pyusb_version = usb.__version__
    except AttributeError:
        pass
    return "pyusb_version=%s" % pyusb_version


class WMR300Driver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with a WMR300 weather station."""

    # map sensor values to the database schema fields
    # the default map is for the wview schema
    DEFAULT_MAP = {
        'pressure': 'pressure',
        'barometer': 'barometer',
        'windSpeed': 'wind_avg',
        'windDir': 'wind_dir',
        'windGust': 'wind_gust',
        'windGustDir': 'wind_gust_dir',
        'inTemp': 'temperature_0',
        'outTemp': 'temperature_1',
        'extraTemp1': 'temperature_2',
        'extraTemp2': 'temperature_3',
        'extraTemp3': 'temperature_4',
        'extraTemp4': 'temperature_5',
        'extraTemp5': 'temperature_6',
        'extraTemp6': 'temperature_7',
        'extraTemp7': 'temperature_8',
        'inHumidity': 'humidity_0',
        'outHumidity': 'humidity_1',
        'extraHumid1': 'humidity_2',
        'extraHumid2': 'humidity_3',
        'extraHumid3': 'humidity_4',
        'extraHumid4': 'humidity_5',
        'extraHumid5': 'humidity_6',
        'extraHumid6': 'humidity_7',
        'extraHumid7': 'humidity_8',
        'dewpoint': 'dewpoint_1',
        'extraDewpoint1': 'dewpoint_2',
        'extraDewpoint2': 'dewpoint_3',
        'extraDewpoint3': 'dewpoint_4',
        'extraDewpoint4': 'dewpoint_5',
        'extraDewpoint5': 'dewpoint_6',
        'extraDewpoint6': 'dewpoint_7',
        'extraDewpoint7': 'dewpoint_8',
        'heatindex': 'heatindex_1',
        'extraHeatindex1': 'heatindex_2',
        'extraHeatindex2': 'heatindex_3',
        'extraHeatindex3': 'heatindex_4',
        'extraHeatindex4': 'heatindex_5',
        'extraHeatindex5': 'heatindex_6',
        'extraHeatindex6': 'heatindex_7',
        'extraHeatindex7': 'heatindex_8',
        'windchill': 'windchill',
        'rainRate': 'rain_rate'}

    # threshold at which the history will be cleared, specified as an integer
    # between 5 and 95, inclusive.
    DEFAULT_HIST_LIMIT = 20

    # threshold at which warning will be emitted.  if the rain counter exceeds
    # this percentage, then a warning will be emitted to remind user to reset
    # the rain counter.
    DEFAULT_RAIN_WARNING = 90

    # if DEBUG_COUNTS is set then this defines how many seconds elapse between each print/reset of the counters
    COUNT_SUMMARY_INTERVAL = 20

    def __init__(self, **stn_dict):
        log.info('driver version is %s' % DRIVER_VERSION)
        log.info('usb info: %s' % get_usb_info())
        self.model = stn_dict.get('model', DRIVER_NAME)
        self.sensor_map = dict(self.DEFAULT_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        log.info('sensor map is %s' % self.sensor_map)
        hlimit = int(stn_dict.get('history_limit', self.DEFAULT_HIST_LIMIT))
        # clear history seems to fail if tried from below 5%
        # 1 day at 1 min intervals is ~4.5%
        if hlimit < 5:
            hlimit = 5
        if hlimit > 95:
            hlimit = 95
        self.history_limit_index = Station.get_history_pct_as_index(hlimit)
        log.info('history limit is %d%% at index %d' % (hlimit, self.history_limit_index) )
        frac = int(stn_dict.get('rain_warning', self.DEFAULT_RAIN_WARNING))
        self.rain_warn = frac / 100.0

        global DEBUG_COMM
        DEBUG_COMM = int(stn_dict.get('debug_comm', DEBUG_COMM))
        global DEBUG_PACKET
        DEBUG_PACKET = int(stn_dict.get('debug_packet', DEBUG_PACKET))
        global DEBUG_COUNTS
        DEBUG_COUNTS = int(stn_dict.get('debug_counts', DEBUG_COUNTS))
        global DEBUG_DECODE
        DEBUG_DECODE = int(stn_dict.get('debug_decode', DEBUG_DECODE))
        global DEBUG_HISTORY
        DEBUG_HISTORY = int(stn_dict.get('debug_history', DEBUG_HISTORY))
        global DEBUG_TIMING
        DEBUG_TIMING = int(stn_dict.get('debug_timing', DEBUG_TIMING))
        global DEBUG_RAIN
        DEBUG_RAIN = int(stn_dict.get('debug_rain', DEBUG_RAIN))

        self.logged_rain_counter = 0
        self.logged_history_usage = 0
        self.log_interval = 24 * 3600 # how often to log station status, in seconds

        self.heartbeat = 20 # how often to send a6 messages, in seconds
        self.history_retry = 60 # how often to retry history, in seconds
        self.last_rain = None # last rain total
        self.last_a6 = 0 # timestamp of last 0xa6 message
        self.data_since_heartbeat = 0       # packets of loop data seen
        self.last_65 = 0 # timestamp of last 0x65 message
        self.last_7x = 0 # timestamp of last 0x7x message
        self.last_record = Station.HISTORY_START_REC - 1
        self.pressure_cache = dict() # FIXME: make the cache values age
        self.station = Station()
        self.station.open()
        pkt = self.init_comm()
        log.info("communication established: %s" % pkt)
        self.history_end_index = pkt['history_end_index']
        self.magic0 = pkt['magic0']
        self.magic1 = pkt['magic1']
        self.mystery0 = pkt['mystery0']
        self.mystery1 = pkt['mystery1']
        if DEBUG_COUNTS:
            self.last_countsummary = time.time()

    def closePort(self):
        self.station.close()
        self.station = None

    @property
    def hardware_name(self):
        return self.model

    def init_comm(self, max_tries=3, max_read_tries=10):
        """initiate communication with the station:
        1 send a special a6 packet
        2 read the packet 57
        3 send a type 73 packet
        4 read the ack
        """

        cnt = 0
        while cnt < max_tries:
            cnt += 1
            try:
                buf = None
                self.station.flush_read_buffer()
                if DEBUG_COMM:
                    log.info("init_comm: send initial heartbeat 0xa6")
                self.send_heartbeat()
                if DEBUG_COMM:
                    log.info("init_comm: try to read 0x57")
                read_cnt = 0
                while read_cnt < max_read_tries:
                    buf = self.station.read()
                    read_cnt += 1
                    if buf and buf[0] == 0x57:
                        break
                if not buf or buf[0] != 0x57:
                    raise ProtocolError("failed to read pkt 0x57")
                pkt = Station._decode_57(buf)
                if DEBUG_COMM:
                    log.info("init_comm: send initialization 0x73")
                cmd = [0x73, 0xe5, 0x0a, 0x26, pkt['magic0'], pkt['magic1']]
                self.station.write(cmd)
                self.last_7x = time.time()
                if DEBUG_COMM:
                    log.info("init_comm: try to read 0x41")
                read_cnt = 0
                while read_cnt < max_read_tries:
                    buf = self.station.read()
                    read_cnt += 1
                    if buf and buf[0] == 0x41:
                        break
                if not buf or buf[0] != 0x41:
                    raise ProtocolError("failed to read ack 0x41 for pkt 0x73")
                if DEBUG_COMM:
                    log.info("initialization completed in %s tries" % cnt)
                return pkt
            except ProtocolError as e:
                if DEBUG_COMM:
                    log.info("init_comm: failed attempt %d of %d: %s" %
                             (cnt, max_tries, e))
            time.sleep(0.1)
        raise ProtocolError("Init comm failed after %d tries" % max_tries)

    def init_history(self, clear_logger=False, max_tries=5, max_read_tries=10):
        """initiate streaming of history records from the station:

        1 if clear logger:
          1a send 0xb3 packet
        1 if not clear logger:
          1a send special 0xa6 (like other 0xa6 packets, but no 0x57 reply)
          1b send 0x65 packet
        2 read the ACK
        3 send a 0xcd packet
        4 do not wait for ACK - it might not come

        then return to reading packets
        """

        cnt = 0
        while cnt < max_tries:
            cnt += 1
            try:
                if DEBUG_HISTORY:
                    log.info("init history attempt %d of %d" % (cnt, max_tries))
                # eliminate anything that might be in the buffer
                self.station.flush_read_buffer()
                # send the sequence for initiating history packets
                if clear_logger:
                    cmd = [0xb3, 0x59, 0x0a, 0x17, 0x01, 0xeb]
                    self.station.write(cmd)
                    # a partial read is sufficient. No need to read stuff we are not going to save
                    start_rec = Station.clip_index( self.history_end_index - 1200 )
                else:
                    self.send_heartbeat()
                    cmd = [0x65, 0x19, 0xe5, 0x04, 0x52, 0x8b]
                    self.station.write(cmd)
                    self.last_65 = time.time()
                    start_rec = self.last_record

                # read the ACK.  there might be regular packets here, so be
                # ready to read a few - just ignore them.
                read_cnt = 0
                while read_cnt < max_read_tries:
                    buf = self.station.read()
                    read_cnt += 1
                    if buf and buf[0] == 0x41 and buf[3] == cmd[0]:
                        break
                if not buf or buf[0] != 0x41:
                    raise ProtocolError("failed to read ack to %02x" % cmd[0])

                # send the request to start history packets
                nxt = Station.clip_index(start_rec)
                if DEBUG_HISTORY:
                    log.info("init history cmd=0x%02x rec=%d" % (cmd[0], nxt))
                cmd = [0xcd, 0x18, 0x30, 0x62, _hi(nxt), _lo(nxt)]
                self.station.write(cmd)

                # do NOT wait for an ACK.  the console should start spewing
                # history packets, and any ACK or 0x57 packets will be out of
                # sequence.  so just drop into the normal reading loop and
                # process whatever comes.
                if DEBUG_HISTORY:
                    log.info("init history completed after attempt %d of %d" %
                             (cnt, max_tries))
                return
            except ProtocolError as e:
                if DEBUG_HISTORY:
                    log.info("init_history: failed attempt %d of %d: %s" %
                             (cnt, max_tries, e))
            time.sleep(0.1)
        raise ProtocolError("Init history failed after %d tries" % max_tries)

    def finish_history(self, max_tries=3):
        """conclude reading of history records.
        1 final 0xa6 has been sent and 0x57 has been seen
        2 send 0x35 packet
        3 no ACK, but sometimes another 57:? - ignore it
        """

        cnt = 0
        while cnt < max_tries:
            cnt += 1
            try:
                if DEBUG_HISTORY:
                    log.info("finish history attempt %d of %d" % (cnt, max_tries))
                # eliminate anything that might be in the buffer
                self.station.flush_read_buffer()
                # send packet 0x35
                cmd = [0x35, 0x0b, 0x1a, 0x87,
                       _hi(self.last_record), _lo(self.last_record)]
                self.station.write(cmd)
                # do NOT wait for an ACK
                if DEBUG_HISTORY:
                    log.info("finish history completed after attempt %d of %d" %
                             (cnt, max_tries))
                return
            except ProtocolError as e:
                if DEBUG_HISTORY:
                    log.info("finish history failed attempt %d of %d: %s" %
                             (cnt, max_tries, e))
            time.sleep(0.1)
        raise ProtocolError("Finish history failed after %d tries" % max_tries)

    def dump_history(self):
        log.info("dump history")
        if DEBUG_HISTORY:
            reread_start_time = time.time()
        for rec in self.get_history(time.time(), clear_logger=True):
            pass
        if DEBUG_HISTORY:
            reread_duration = time.time() - reread_start_time
            log.info( "History clear completed in %.1f sec" % reread_duration )

    def get_history(self, since_ts, clear_logger=False):
        if self.history_end_index is None:
            log.info("read history skipped: index has not been set")
            return
        if self.history_end_index < 1:
            # this should never happen.  if it does, then either no 0x57 packet
            # was received or the index provided by the station was bogus.
            log.error("read history failed: bad index: %s" % self.history_end_index)
            return

        log.info("%s records since %s (last_index=%s history_end_index=%s)" %
                 ("Clearing" if clear_logger else "Reading",
                  timestamp_to_string(since_ts) if since_ts is not None else "the start",
                  self.last_record, self.history_end_index))
        self.init_history(clear_logger)
        half_buf = None
        last_ts = None
        processed = 0
        loop_ignored = 0
        state = "reading history"
            # there is sometimes a series of bogus history records reported
            # these are to keep a track of them
        bogus_count = 0
        bogus_first = 0
        bogus_last = 0
        # since_ts of None implies DB just created, so read all...
        if since_ts is None:
            since_ts = 0

        while True:
            try:
                buf = self.station.read()
                if buf:
                    # The message length is 64 bytes, but historical records
                    # are 128 bytes.  So we have to assemble the two 64-byte
                    # parts of each historical record into a single 128-byte
                    # message for processing.  We have to assume we do not get any
                    # non-historical records interspersed between parts.
                    # This code will fail if any user has 7 or 8
                    # temperature sensors installed, as it is relying on seeing
                    # 0x7f in byte 64, which just means "no data"
                    if buf[0] == 0xd2:
                        pktlength = buf[1]
                        if pktlength != 128:
                            raise WMR300Error("History record unexpected length: assumed 128, found %d" % pktlength )
                        half_buf = buf
                        buf = None
                        # jump immediately to read the 2nd half of the packet
                        # we don't want other possibilities intervening
                        continue
                    elif buf[0] == 0x7f and half_buf is not None:
                        buf = half_buf + buf
                        half_buf = None
                    if buf[0] == 0xd2:
                        next_record = Station.get_record_index(buf)
                        if last_ts is not None and next_record != self.last_record + 1:
                            log.info("missing record: skipped from %d to %d" %
                                     (self.last_record, next_record))
                        self.last_record = next_record
                        ts = Station._extract_ts(buf[4:9])
                        if ts is None:
                            if bogus_count == 0 :
                                bogus_first = next_record
                            bogus_count += 1
                            bogus_last = next_record
                            if DEBUG_HISTORY:
                                log.info("Bogus historical record index: %d " % (next_record))
                                    #log.info("    content: %s" % _fmt_bytes(buf))
                        else:
                            if ts > since_ts:
                                pkt = Station.decode(buf)
                                packet = self.convert_historical(pkt, ts, last_ts)
                                last_ts = ts
                                if 'interval' in packet:
                                    if DEBUG_HISTORY:
                                        log.info("New historical record for %s: %s: %s" %
                                                 (timestamp_to_string(ts), pkt['index'], packet))
                                    processed += 1
                                    yield packet
                            else:
                                last_ts = ts

                    elif buf[0] == 0x57:
                        self.history_end_index = Station.get_history_end_index(buf)
                        msg = " count=%s updated; last_index rcvd=%s; final_index=%s; state = %s" % (
                            processed, self.last_record, self.history_end_index, state)
                        if state == "wait57":
                            log.info("History read completed: %s" % msg)
                            break
                        else:
                            log.info("History read in progress: %s" % msg)

                    elif buf[0] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]:
                        # ignore any packets other than history records.  this
                        # means there will be no current data while the history
                        # is being read.
                        loop_ignored += 1
                        if DEBUG_HISTORY:
                            log.info("ignored packet type 0x%2x" % buf[0])
                        # do not ACK data packets.  the PC software does send ACKs
                        # here, but they are ignored anyway.  so we just ignore.
                    else:
                        log.error("get_history: unexpected packet, content: %s" % _fmt_bytes(buf))
                        
                if self.last_record + 1 >= self.history_end_index :
                    if state == "reading history":
                        if DEBUG_HISTORY:
                            msg = "count=%s kept, last_received=%s final=%s" % (
                                processed, self.last_record, self.history_end_index )
                            log.info("History read nearly complete: %s; state=%s" % (msg, state) )
                        state = "finishing"

                if (state == "finishing") or (time.time() - self.last_a6 > self.heartbeat):              
                    if DEBUG_HISTORY:
                        log.info("request station status at index: %s; state: %s" %
                               (self.last_record, state ) )
                    self.send_heartbeat()
                    if state == "finishing" :
                        # It is possible that another history packet has been created between the
                        # most recent 0x57 status and now. So, we have to stay in the loop
                        # to read the possible next packet.
                        # Evidence suggests that such history packet will arrive before the
                        # 0x57 reply to this request, so presumably it was already in some output queue.
                        state = "wait57"


            except usb.USBError as e:
                raise weewx.WeeWxIOError(e)
            except DecodeError as e:
                log.info("get_history: %s" % e)
            time.sleep(0.001)        
        if loop_ignored > 0 :
            log.info( "During history read, %d loop data packets were ignored" % loop_ignored )
        if bogus_count > 0 :
            log.info( "During history read, %d bogus entries found from %d to %d" %
                      (bogus_count, bogus_first, bogus_last))
        self.finish_history()

    def genLoopPackets(self):

        while True:
            try:
                read_enter_time = time.time()
                buf = self.station.read()
                read_return_delta = time.time() - read_enter_time
                if buf:
                    if buf[0] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]:
                        # compose ack for most data packets
                        # cmd = [0x41, 0x43, 0x4b, buf[0], buf[7]]
                        # do not bother to send the ACK - console does not care
                        #self.station.write(cmd)
                        # we only care about packets with loop data
                        if buf[0] in [0xd3, 0xd4, 0xd5, 0xd6]:
                            pkt = Station.decode(buf)
                            self.data_since_heartbeat += 1
                            packet = self.convert_loop(pkt)
                            if DEBUG_COUNTS:
                                if "Loop" in self.station.recv_counts:
                                    self.station.recv_counts["Loop"] += 1
                                else:
                                    self.station.recv_counts["Loop"] = 1
                            if DEBUG_TIMING:
                                yield_rtn_time = time.time()
                            yield packet
                            if DEBUG_TIMING:
                                yield_return_delta = time.time() - yield_rtn_time
                                if yield_return_delta > 5:
                                    log.info( "Yield delayed for = %d s" % yield_return_delta  )
                    elif buf[0] == 0x57:
                        self.history_end_index = Station.get_history_end_index(buf)
                        if time.time() - self.logged_history_usage > self.log_interval:
                            pct = Station.get_history_usage_pct(self.history_end_index)
                            log.info("history buffer at %.2f%% (%d)" % (pct, self.history_end_index))
                            self.logged_history_usage = time.time()
                if DEBUG_TIMING and read_return_delta > 5:
                    log.info( "USB Read delayed for = %d s" % read_return_delta  )

                if DEBUG_COUNTS:
                    now = time.time()
                    # we just print a summary each chosen interval
                    if (now - self.last_countsummary)  > self.COUNT_SUMMARY_INTERVAL:
                        Station.print_count( "read", self.station.recv_counts )
                        self.station.recv_counts.clear()
                        Station.print_count( "write", self.station.send_counts )
                        self.station.send_counts.clear()
                        self.last_countsummary = now

                time_since_heartbeat = time.time() - self.last_a6
                if time_since_heartbeat > self.heartbeat:
                    if DEBUG_TIMING and self.data_since_heartbeat < 10 :
                        log.info( "Loop data packets in heartbeat interval = %d" % self.data_since_heartbeat )
                    needs_restart = False
                    if time_since_heartbeat > 60:
                        log.error( "Excessive heartbeat delay: %ds, restarting" % (time_since_heartbeat) )
                        needs_restart = True
                    if self.data_since_heartbeat <= 0 :
                        log.error( "No loop data in heartbeat interval,  restarting" )
                        needs_restart = True

                    if needs_restart:
                        # I think the 0x73 starts the data transmission, but not sure if the
                        # a6 / 73 order is important.
                        cmd = [0x73, 0xe5, 0x0a, 0x26, self.magic0, self.magic1 ]
                        self.station.write(cmd)


                    self.send_heartbeat()
                if self.history_end_index is not None:
                    if self.history_end_index >= self.history_limit_index:
                        # if the logger usage exceeds the limit, clear it
                        self.dump_history()
                        self.history_end_index = None
            except usb.USBError as e:
                raise weewx.WeeWxIOError(e)
            except (DecodeError, ProtocolError) as e:
                log.info("genLoopPackets: %s" % e)
            time.sleep(0.001)

    def genStartupRecords(self, since_ts):
        for rec in self.get_history(since_ts):
            yield rec

    def convert(self, pkt, ts):
        # if debugging packets, log everything we got
        if DEBUG_PACKET:
            log.info("raw packet: %s" % pkt)
        # timestamp and unit system are the same no matter what
        p = {'dateTime': ts, 'usUnits': weewx.METRICWX}
        # map hardware names to the requested database schema names
        for label in self.sensor_map:
            if self.sensor_map[label] in pkt:
                p[label] = pkt[self.sensor_map[label]]
        # single variable to track last_rain assumes that any historical reads
        # will happen before any loop reads, and no historical reads will
        # happen after any loop reads.  Such double-counting of rain
        # events is avoided by deliberately ignoring all loop packets during history read.
        if 'rain_total' in pkt:
            p['rain'] = self.calculate_rain(pkt['rain_total'], self.last_rain)
            if DEBUG_RAIN and pkt['rain_total'] != self.last_rain:
                log.info("rain=%s rain_total=%s last_rain=%s" %
                         (p['rain'], pkt['rain_total'], self.last_rain))
            self.last_rain = pkt['rain_total']
            if pkt['rain_total'] == Station.MAX_RAIN_MM:
                if time.time() - self.logged_rain_counter > self.log_interval:
                    log.info("rain counter at maximum, reset required")
                    self.logged_rain_counter = time.time()
            if pkt['rain_total'] >= Station.MAX_RAIN_MM * self.rain_warn:
                if time.time() - self.logged_rain_counter > self.log_interval:
                    log.info("rain counter is above warning level, reset recommended")
                    self.logged_rain_counter = time.time()
        if DEBUG_PACKET:
            log.info("converted packet: %s" % p)
        return p

    def send_heartbeat( self ):
        cmd = [0xa6, 0x91, 0xca, 0x45, 0x52]
        self.station.write(cmd)
        self.last_a6 = time.time()
        self.data_since_heartbeat = 0

    def convert_historical(self, pkt, ts, last_ts):
        p = self.convert(pkt, ts)
        if last_ts is not None:
            x = (ts - last_ts) / 60 # interval is in minutes
            if x > 0:
                p['interval'] = x
            else:
                log.info("ignoring record: bad interval %s (%s)" % (x, p))
        return p

    def convert_loop(self, pkt):
        p = self.convert(pkt, int(time.time() + 0.5))
        if DEBUG_HISTORY and self.history_end_index is not None:
            p['rxCheckPercent'] = float(self.history_end_index)  # fake value as easiest way to return it.
        if 'pressure' in p:
            # cache any pressure-related values
            for x in ['pressure', 'barometer']:
                self.pressure_cache[x] = p[x]
        else:
            # apply any cached pressure-related values
            p.update(self.pressure_cache)
        return p

    @staticmethod
    def calculate_rain(newtotal, oldtotal):
        """Calculate the rain difference given two cumulative measurements."""
        if newtotal is not None and oldtotal is not None:
            if newtotal >= oldtotal:
                delta = newtotal - oldtotal
            else:
                log.info("rain counter decrement detected: new=%s old=%s" % (newtotal, oldtotal))
                delta = None
        else:
            log.info("possible missed rain event: new=%s old=%s" % (newtotal, oldtotal))
            delta = None
        return delta


class WMR300Error(weewx.WeeWxIOError):
    """map station errors to weewx io errors"""

class ProtocolError(WMR300Error):
    """communication protocol error"""

class DecodeError(WMR300Error):
    """decoding error"""

class WrongLength(DecodeError):
    """bad packet length"""

class BadChecksum(DecodeError):
    """bogus checksum"""

class BadTimestamp(DecodeError):
    """bogus timestamp"""

class BadBuffer(DecodeError):
    """bogus buffer"""

class UnknownPacketType(DecodeError):
    """unknown packet type"""

class Station(object):
    # these identify the weather station on the USB
    VENDOR_ID = 0x0FDE
    PRODUCT_ID = 0xCA08
    # standard USB endpoint identifiers
    EP_IN = 0x81
    EP_OUT = 0x01
    # all USB messages for this device have the same length
    MESSAGE_LENGTH = 64

    HISTORY_START_REC = 0x20  # index to first history record
    HISTORY_MAX_REC = 0x7fe0  # index to history record when full
    HISTORY_N_RECORDS = 32704 # maximum number of records (MAX_REC - START_REC)
    MAX_RAIN_MM = 10160       # maximum value of rain counter, in mm

    def __init__(self, vend_id=VENDOR_ID, prod_id=PRODUCT_ID):
        self.vendor_id = vend_id
        self.product_id = prod_id
        self.handle = None
        self.timeout = 500
        self.interface = 0          # device has only the one interface
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

        # FIXME: reset is actually a no-op for some versions of libusb/pyusb?
        self.handle.reset()

        # for HID devices on linux, be sure kernel does not claim the interface
        try:
            self.handle.detachKernelDriver(self.interface)
        except (AttributeError, usb.USBError):
            pass

        # attempt to claim the interface
        try:
            self.handle.claimInterface(self.interface)
        except usb.USBError as e:
            self.close()
            raise WMR300Error("Unable to claim interface %s: %s" %
                              (self.interface, e))

    def close(self):
        if self.handle is not None:
            try:
                self.handle.releaseInterface()
            except (ValueError, usb.USBError) as e:
                log.debug("Release interface failed: %s" % e)
            self.handle = None

    def reset(self):
        self.handle.reset()

    def _read(self, count=True, timeout=None):
        if timeout is None:
            timeout = self.timeout
        buf = self.handle.interruptRead(
            Station.EP_IN, self.MESSAGE_LENGTH, timeout)
        if DEBUG_COMM:
            log.info("read: %s" % _fmt_bytes(buf))
        if DEBUG_COUNTS and count:
            self.update_count(buf, self.recv_counts)
        return buf

    def read(self, count=True, timeout=None, ignore_non_errors=True, ignore_timeouts=True):
        try:
            return self._read(count, timeout)
        except usb.USBError as e:
            if DEBUG_COMM:
                log.info("read: e.errno=%s e.strerror=%s e.message=%s repr=%s" %
                         (e.errno, e.strerror, e.message, repr(e)))
            if ignore_timeouts and is_timeout(e):
                return []
            if ignore_non_errors and is_noerr(e):
                return []
            raise

    def _write(self, buf):
        if DEBUG_COMM:
            log.info("write: %s" % _fmt_bytes(buf))
        # pad with zeros up to the standard message length
        while len(buf) < self.MESSAGE_LENGTH:
            buf.append(0x00)
        sent = self.handle.interruptWrite(Station.EP_OUT, buf, self.timeout)
        if DEBUG_COUNTS:
            self.update_count(buf, self.send_counts)
        return sent

    def write(self, buf, ignore_non_errors=True, ignore_timeouts=True):
        try:
            return self._write(buf)
        except usb.USBError as e:
            if ignore_timeouts and is_timeout(e):
                return 0
            if ignore_non_errors and is_noerr(e):
                return 0
            raise

    def flush_read_buffer(self):
        """discard anything read from the device"""
        if DEBUG_COMM:
            log.info("flush buffer")
        cnt = 0
        buf = self.read(False, 100)
        while buf is not None and len(buf) > 0:
            cnt += len(buf)
            buf = self.read(False, 100)
        if DEBUG_COMM:
            log.info("flush: discarded %d bytes" % cnt)
        return cnt

    # keep track of the message types for debugging purposes
    @staticmethod
    def update_count(buf, count_dict):
        label = 'empty'
        if buf and len(buf) > 0:
            #if buf[0] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]:
                # message type and channel for data packets
                #label = '%02x_%d' % (buf[0], buf[7])
            if buf[0] == 0xd3:
                # message type and channel for data packets
                label = 'TH_%d' % (buf[7])
            elif buf[0] == 0xdc:
                label = 'THrng_%d' % (buf[7])
                # ignore this for the moment...
                return
            elif buf[0] == 0xd4:
                label = 'wind'
            elif buf[0] == 0xd5:
                label = 'rain'
            elif buf[0] == 0xd6:
                label = 'barom'
            elif buf[0] == 0xdb:
                label = 'forecast'
            elif (buf[0] in [0x41] and
                  buf[3] in [0xd3, 0xd4, 0xd5, 0xd6, 0xdb, 0xdc]):
                # message type and channel for data ack packets
                # these are no longer sent.
                label = '%02x_%02x_%d' % (buf[0], buf[3], buf[4])
            else:
                # otherwise just track the message type
                # prefix with x to place at end
                label = 'x%02x' % buf[0]
        if label in count_dict:
            count_dict[label] += 1
        else:
            count_dict[label] = 1
        #Station.print_count( "unknown", count_dict)

    # print the count type summary for debugging
    @staticmethod
    def print_count( direction, count_dict):
        cstr = []
        for k in sorted(count_dict):
            cstr.append('%s: %s' % (k, count_dict[k]))
        log.info('%s counts; %s' % ( direction, '; '.join(cstr)))

    @staticmethod
    def _find_dev(vendor_id, product_id):
        """Find the first device with vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    log.debug('Found station at bus=%s device=%s' %
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
        except IndexError as e:
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
            raise BadTimestamp("buffer too short for timestamp")
        except (OverflowError, ValueError) as e:
            raise BadTimestamp(
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
    def get_history_end_index(buf):
        """ get the index value reported in the 0x57 packet.
        It is the index of the first free history record,
        and so is one more than the most recent history record stored in the console
        """
        if buf[0] != 0x57:
            return None
        idx = (buf[17] << 8) + buf[18]
        #if idx < Station.HISTORY_START_REC:
        #    raise WMR300Error("History index: %d below limit of %d" % (idx, Station.HISTORY_START_REC) )
        #elif idx > Station.HISTORY_MAX_REC:
        #    raise WMR300Error("History index: %d above limit of %d" % (idx, Station.HISTORY_MAX_REC) )
        #self.history_pct=Station.get_history_usage( idx )
        return Station.clip_index(idx)

    @staticmethod
    def get_next_index(n):
        ## this code is currently UNUSED
        # return the index of the record after indicated index
        if n == 0:
            return 0x20
        if n + 1 > Station.MAX_RECORDS:
            return 0x20 # FIXME: verify the wraparound
        return n + 1

    @staticmethod
    def clip_index(n):
        # given a history record index, clip it to a valid value
        # the HISTORY_MAX_REC value is what it returned in packet 0x57 when the
        # buffer is full. You cannot ask for it, only the one before.
        if n < Station.HISTORY_START_REC:
            return Station.HISTORY_START_REC
        if n >= Station.HISTORY_MAX_REC - 1:
            return Station.HISTORY_MAX_REC - 1 # wraparound never happens
        return n

    @staticmethod
    def get_record_index(buf):
        # extract the index from the history record
        if buf[0] != 0xd2:
            return None
        return (buf[2] << 8) + buf[3]

    @staticmethod
    def get_history_pct_as_index( pct ):
        # return history buffer index corresponding to a given percentage
        if pct is None:
            return Station.HISTORY_START_REC
        return int(pct * 0.01 * Station.HISTORY_N_RECORDS + Station.HISTORY_START_REC)

    @staticmethod
    def get_history_usage_pct(index):
        """ return the console's history buffer use corresponding to the given index expressed as a percent
        index = index value in console's history buffer
                normally the next free history location as returned in 0x57 status packet
        """
        if index is None:
            return -1.0
        return 100.0 * float(index - Station.HISTORY_START_REC) / Station.HISTORY_N_RECORDS

    @staticmethod
    def decode(buf):
        try:
            pkt = getattr(Station, '_decode_%02x' % buf[0])(buf)
            if DEBUG_DECODE:
                log.info('decode: %s %s' % (_fmt_bytes(buf), pkt))
            return pkt
        except IndexError as e:
            raise BadBuffer("cannot decode buffer: %s" % e)
        except AttributeError:
            raise UnknownPacketType("unknown packet type %02x: %s" %
                                    (buf[0], _fmt_bytes(buf)))

    @staticmethod
    def _decode_57(buf):
        """57 packet contains station information"""
        pkt = dict()
        pkt['packet_type'] = 0x57
        pkt['station_type'] = ''.join("%s" % chr(x) for x in buf[0:6])
        pkt['station_model'] = ''.join("%s" % chr(x) for x in buf[7:11])
        pkt['magic0'] = buf[12]
        pkt['magic1'] = buf[13]
        pkt['history_cleared'] = (buf[20] == 0x43) # FIXME: verify this
        pkt['mystery0'] = buf[22]
        pkt['mystery1'] = buf[23]
        pkt['history_end_index'] = Station.get_history_end_index( buf )
        if DEBUG_HISTORY:
            log.info("history index: %s" % pkt['history_end_index'])
        return pkt

    @staticmethod
    def _decode_41(_):
        """41 43 4b is ACK"""
        pkt = dict()
        pkt['packet_type'] = 0x41
        return pkt

    @staticmethod
    def _decode_d2(buf):
        """D2 packet contains history data"""
        Station._verify_length("D2", 0x80, buf)
        Station._verify_checksum("D2", buf[:0x80], msb_first=False)
        pkt = dict()
        pkt['packet_type'] = 0xd2
        pkt['index'] = Station.get_record_index(buf)
        pkt['ts'] = Station._extract_ts(buf[4:9])
        for i in range(9):
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
        pkt['barometer'] = Station._extract_value(buf[95:97], 0.1) # mbar
        pkt['pressure_trend'] = Station._extract_value(buf[97:98], 1.0)
        return pkt

    @staticmethod
    def _decode_d3(buf):
        """D3 packet contains temperature/humidity data"""
        Station._verify_length("D3", 0x3d, buf)
        Station._verify_checksum("D3", buf[:0x3d])
        pkt = dict()
        pkt['packet_type'] = 0xd3
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['temperature_%d' % pkt['channel']] = Station._extract_signed(
            buf[8], buf[9], 0.1) # C
        pkt['humidity_%d' % pkt['channel']] = Station._extract_value(
            buf[10:11], 1.0) # %
        pkt['dewpoint_%d' % pkt['channel']] = Station._extract_signed(
            buf[11], buf[12], 0.1) # C
        pkt['heatindex_%d' % pkt['channel']] = Station._extract_signed(
            buf[13], buf[14], 0.1) # C
        return pkt

    @staticmethod
    def _decode_d4(buf):
        """D4 packet contains wind data"""
        Station._verify_length("D4", 0x36, buf)
        Station._verify_checksum("D4", buf[:0x36])
        pkt = dict()
        pkt['packet_type'] = 0xd4
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['wind_gust'] = Station._extract_value(buf[8:10], 0.1) # m/s
        pkt['wind_gust_dir'] = Station._extract_value(buf[10:12], 1.0) # degree
        pkt['wind_avg'] = Station._extract_value(buf[12:14], 0.1) # m/s
        pkt['wind_dir'] = Station._extract_value(buf[14:16], 1.0) # degree
        pkt['windchill'] = Station._extract_signed(buf[18], buf[19], 0.1) # C
        return pkt

    @staticmethod
    def _decode_d5(buf):
        """D5 packet contains rain data"""
        Station._verify_length("D5", 0x28, buf)
        Station._verify_checksum("D5", buf[:0x28])
        pkt = dict()
        pkt['packet_type'] = 0xd5
        pkt['ts'] = Station._extract_ts(buf[2:7])
        pkt['channel'] = buf[7]
        pkt['rain_hour'] = Station._extract_value(buf[9:11], 0.254) # mm
        pkt['rain_24_hour'] = Station._extract_value(buf[12:14], 0.254) # mm
        pkt['rain_total'] = Station._extract_value(buf[15:17], 0.254) # mm
        pkt['rain_rate'] = Station._extract_value(buf[17:19], 0.254) # mm/hour
        pkt['rain_start_dateTime'] = Station._extract_ts(buf[19:24])
        return pkt

    @staticmethod
    def _decode_d6(buf):
        """D6 packet contains pressure data"""
        Station._verify_length("D6", 0x2e, buf)
        Station._verify_checksum("D6", buf[:0x2e])
        pkt = dict()
        pkt['packet_type'] = 0xd6
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
        pkt['packet_type'] = 0xdc
        pkt['ts'] = Station._extract_ts(buf[2:7])
        return pkt

    @staticmethod
    def _decode_db(buf):
        """DB packet is forecast"""
        Station._verify_length("DB", 0x20, buf)
        Station._verify_checksum("DB", buf[:0x20])
        pkt = dict()
        pkt['packet_type'] = 0xdb
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

    # The console history buffer will be emptied each
    #    time it gets to this percent full
    # Allowed range 5 to 95.
    history_limit = 10

"""

    def modify_config(self, config_dict):
        print("""
Setting rainRate, windchill, heatindex calculations to hardware. 
Dewpoint from hardware is truncated to integer so use software""")
        config_dict.setdefault('StdWXCalculate', {})
        config_dict['StdWXCalculate'].setdefault('Calculations', {})
        config_dict['StdWXCalculate']['Calculations']['rainRate'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['windchill'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['heatindex'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['dewpoint'] = 'software'


# define a main entry point for basic testing of the station.
# invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/user/wmr300.py

if __name__ == '__main__':
    import optparse

    from weeutil.weeutil import to_sorted_string
    import weewx
    import weeutil.logger

    weewx.debug = 1

    weeutil.logger.setup('wmr300', {})

    usage = """%prog [options] [--help]"""

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', action='store_true',
                      help='display driver version')
    parser.add_option('--get-current', action='store_true',
                      help='get current packets')
    parser.add_option('--get-history', action='store_true',
                      help='get history records from station')
    (options, args) = parser.parse_args()

    if options.version:
        print("%s driver version %s" % (DRIVER_NAME, DRIVER_VERSION))
        exit(0)

    driver_dict = {
        'debug_comm': 0,
        'debug_packet': 0,
        'debug_counts': 0,
        'debug_decode': 0,
        'debug_history': 1,
        'debug_timing': 0,
        'debug_rain': 0}
    stn = WMR300Driver(**driver_dict)

    if options.get_history:
        ts = time.time() - 3600 # get last hour of data
        for pkt in stn.genStartupRecords(ts):
            print(to_sorted_string(pkt).encode('utf-8'))

    if options.get_current:
        for packet in stn.genLoopPackets():
            print(to_sorted_string(packet).encode('utf-8'))
