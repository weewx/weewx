#!/usr/bin/python
# $Id$
#
# Copyright 2013 Matthew Wall
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
#
# Thanks to Eddie De Pieri for the first Python implementation for WS-28xx.
# Eddie did the difficult work of decompiling HeavyWeather then converting
# and reverse engineering into a functional Python implementation.  Eddie's
# work was based on reverse engineering of HeavyWeather 2800 v 1.54
#
# Thanks to Luc for enumerating the console message types and for debugging
# the transceiver/console communication timing issues.

"""Classes and functions for interfacing with WS-28xx weather stations.

LaCrosse makes a number of stations in the 28xx series, including:

  WS-2810, WS-2810U-IT
  WS-2811, WS-2811SAL-IT,  WS-2811BRN-IT,  WS-2811OAK-IT
  WS-2812, WS-2812U-IT
  WS-2813
  WS-2814, WS-2814U-IT
  WS-2815, WS-2815U-IT
  C86234

The station is also sold as the TFA Primus, TFA Opus, and TechnoLine.

HeavyWeather is the software provided by LaCrosse.

There are two versions of HeavyWeather for the WS-28xx series: 1.5.4 and 1.5.4b
Apparently there is a difference between TX59UN-1-IT and TX59U-IT models (this
identifier is printed on the thermo-hygro sensor).

   HeavyWeather Version    Firmware Version    Thermo-Hygro Model
   1.54                    333 or 332          TX59UN-1-IT
   1.54b                   288, 262, 222       TX59U-IT

HeavyWeather provides the following weather station settings:

  time display: 12|24 hour
  temperature display: C|F
  air pressure display: inhg|hpa
  wind speed display: m/s|knos|bft|km/h|mph
  rain display: mm|inch
  recording interval: 1m
  keep weather station in hi-speed communication mode: true/false

According to the HeavyWeatherPro User Manual (1.54, rev2), "Hi speed mode wears
down batteries on your display much faster, and similarly consumes more power
on the PC.  We do not believe most users need to enable this setting.  It was
provided at the request of users who prefer ultra-frequent uploads."

The HeavyWeatherPro 'CurrentWeather' view is updated as data arrive from the
console.  The consonle sends current weather data approximately every 13
seconds.

Historical data are updated less frequently - every 2 hours in the default
HeavyWeatherPro configuration.

According to the User Manual, "The 2800 series weather station uses the
'original' wind chill calculation rather than the 2001 'North American'
formula because the original formula is international."

Apparently the station console determines when data will be sent, and, once
paired, the transceiver is always listening.  The station console sends a
broadcast on the hour.  If the transceiver responds, the station console may
continue to broadcast data, depending on the transceiver response and the
timing of the transceiver response.

According to the C86234 Operations Manual (Revision 7):
 - Temperature and humidity data are sent to the console every 13 seconds.
 - Wind data are sent to the temperature/humidity sensor every 17 seconds.
 - Rain data are sent to the temperature/humidity sensor every 19 seconds.
 - Air pressure is measured every 15 seconds.

Each tip of the rain bucket is 0.26 mm of rain.

The following information was obtained by logging messages from the ws28xx.py
driver in weewx and by capturing USB messages between Heavy Weather Pro for
ws2800 and the TFA Primus Weather Station via windows program USB sniffer
busdog64_v0.2.1.

Pairing

The transceiver must be paired with a console before it can receive data.  Each
frame sent by the console includes the device identifier of the transceiver
with which it is paired.

Synchronizing

When the console and transceiver stop communicating, they can be synchronized
by one of the following methods:

- Push the SET button on the console
- Wait till the next full hour when the console sends a clock message

In each case a Request Time message is received by the transceiver from the
console. The 'Send Time to WS' message should be sent within ms (10 ms
typical). The transceiver should handle the 'Time SET' message about 125 ms
after the 'Send Time to WS' message. When complete, the console and transceiver
will have been synchronized.

Timing

Outstanding history messages follow each other after 300 - 2600 ms (typical
500 ms). The best polling period appears to be 50 ms, with an average duration
of the polling loop of 3 - 4 ms. This will catch both Clock SET and History
messages. A longer polling period will catch some messages, but often misses
History messages and results in console and transceiver becoming out of synch.

Message Types

The first byte of a message determines the message type.

ID   Type               Length

01   ?                  0x0f  (15)
d0   SetRX              0x15  (21)
d1   SetTX              0x15  (21)
d5   SetFrame           0x111 (273)
d6   GetFrame           0x111 (273)
d7   SetState           0x15  (21)
d8   SetPreamblePattern 0x15  (21)
d9   Execute            0x0f  (15)
dc   ReadConfigFlash<   0x15  (21)
dd   ReadConfigFlash>   0x15  (21)
de   GetState           0x0a  (10)
f0   WriteReg           0x05  (5)

In the following sections, some messages are decomposed using the following
structure:

  start   position in message buffer
  hi-lo   data starts on first (hi) or second (lo) nibble
  chars   data length in characters (nibbles)
  rem     remark
  name    variable

-------------------------------------------------------------------------------
1. 01 message (15 bytes)

000:  01 15 00 0b 08 58 3f 53 00 00   00 00 ff 15 0b (detected via USB sniffer)
000:  01 15 00 57 01 92 3f 53 00 00   00 00 ff 15 0a (detected via USB sniffer)

00:    messageID
02-15: ??

-------------------------------------------------------------------------------
2. SetRX message (21 bytes)

000:  d0 00 00 00 00 00 00 00 00 00   00 00 00 00 00 00 00 00 00 00
020:  00 
  
00:    messageID
01-20: 00

-------------------------------------------------------------------------------
3. SetTX message (21 bytes)

000: d1 00 00 00 00 00 00 00 00 00   00 00 00 00 00 00 00 00 00 00
020: 00 
  
00:    messageID
01-20: 00

-------------------------------------------------------------------------------
4. SetFrame message (273 bytes)

Action:
00: rtGetHistory - Ask for History message
01: rtSetTime    - Ask for Request Time message
02: rtSetConfig  - Send Config to WS
03: rtGetConfig  - Ask for Request Config message
05: rtGetCurrent - Ask for Current Weather message
c0: Send Time    - Send Time to WS
40: Send Config  - Send Config to WS

000:  d5 00 09 DevID 00 CfgCS cIntThisIdx xx xx xx  rtGetHistory 
000:  d5 00 09 DevID 01 CfgCS cIntThisIdx xx xx xx  rtReqSetTime
000:  d5 00 09 DevID 02 CfgCS cIntThisIdx xx xx xx  rtReqSetConfig
000:  d5 00 09 DevID 03 CfgCS cIntThisIdx xx xx xx  rtGetConfig
000:  d5 00 09 DevID 05 CfgCS cIntThisIdx xx xx xx  rtGetCurrent
000:  d5 00 0c DevID c0 CfgCS [TimeData . .. .. ..  Send Time
000:  d5 00 30 DevID 40 CfgCS [ConfigData .. .. ..  Send Config

All SetFrame messages:
00:    messageID
01:    00
02:    Message Length (starting with next byte)
03-04: DeviceID           [DevID]
05:    Action
06-07: Config checksum    [CfgCS]

Additional bytes rtGetCurrent, rtGetHistory, rtSetTime messages:
08-09hi: ComInt           [cINT]    1.5 bytes (high byte first)
09lo-11: ThisHistoryIndex [ThisIdx] 2.5 bytes (high byte first)

Additional bytes Send Time message:
08:    seconds
09:    minutes
10:    hours
11hi:  DayOfWeek
11lo:  day_lo         (low byte)
12hi:  month_lo       (low byte)
12lo:  day_hi         (high byte)
13hi:  (year-2000)_lo (low byte)
13lo:  month_hi       (high byte)
14lo:  (year-2000)_hi (high byte)

-------------------------------------------------------------------------------
5. GetFrame message

Response type:
20: WS SetTime / SetConfig - Data written
40: GetConfig
60: Current Weather
80: Actual / Outstanding History
a1: Request First-Time Config
a2: Request SetConfig
a3: Request SetTime

000:  00 00 06 DevID 20 64 CfgCS xx xx xx xx xx xx xx xx xx  Time/Config written
000:  00 00 30 DevID 40 64 [ConfigData .. .. .. .. .. .. ..  GetConfig
000:  00 00 d7 DevID 60 64 CfgCS [CurData .. .. .. .. .. ..  Current Weather
000:  00 00 1e DevID 80 64 CfgCS 0LateIdx 0ThisIdx [HisData  Outstanding History
000:  00 00 1e DevID 80 64 CfgCS 0ThisIdx 0ThisIdx [HisData  Actual History
000:  00 00 06 DevID a1 64 CfgCS xx xx xx xx xx xx xx xx xx  Request FirstConfig
000:  00 00 06 DevID a2 64 CfgCS xx xx xx xx xx xx xx xx xx  Request SetConfig
000:  00 00 06 DevID a3 64 CfgCS xx xx xx xx xx xx xx xx xx  Request SetTime

ReadConfig example:  
000: 01 2e 40 5f 36 53 02 00 00 00  00 81 00 04 10 00 82 00 04 20
020: 00 71 41 72 42 00 05 00 00 00  27 10 00 02 83 60 96 01 03 07
040: 21 04 01 00 00 00 CfgCS

WriteConfig example:
000: 01 2e 40 64 36 53 02 00 00 00  00 00 10 04 00 81 00 20 04 00
020: 82 41 71 42 72 00 00 05 00 00  00 10 27 01 96 60 83 02 01 04
040: 21 07 03 10 00 00 CfgCS

00:    messageID
01:    00
02:    Message Length (starting with next byte)
03-04: DeviceID [devID]
05hi:  responseType
06:    Quality (in steps of 5)

Additional byte GetFrame messages except Request SetConfig and Request SetTime:
05lo:  BatteryStat 8=WS bat low; 4=TMP bat low; 2=RAIN bat low; 1=WIND bat low

Additional byte Request SetConfig and Request SetTime:
05lo:  RequestID

Additional bytes all GetFrame messages except ReadConfig and WriteConfig
07-08: Config checksum [CfgCS]

Additional bytes Outstanding History:
09lo-11: LatestHistoryIndex [LateIdx] 2.5 bytes (Latest to sent)
12lo-14: ThisHistoryIndex   [ThisIdx] 2.5 bytes (Outstanding)

Additional bytes Actual History:
09lo-11: LatestHistoryIndex [ThisIdx] 2.5 bytes (LatestHistoryIndex is the same
12lo-14: ThisHistoryIndex   [ThisIdx] 2.5 bytes  as ThisHistoryIndex)

Additional bytes ReadConfig and WriteConfig
43-45: ResetMinMaxFlags (Output only; not included in checksum calculation)
46-47: Config checksum [CfgCS] (CheckSum = sum of bytes (00-42) + 7)

-------------------------------------------------------------------------------
6. SetState message

000:  d7 00 00 00 00 00 00 00 00 00 00 00 00 00 00

00:    messageID
01-14: 00

-------------------------------------------------------------------------------
7. SetPreablePattern message

000:  d8 aa 00 00 00 00 00 00 00 00 00 00 00 00 00

00:    messageID
01:    ??
02-14: 00

-------------------------------------------------------------------------------
8. Execute message

000:  d9 05 00 00 00 00 00 00 00 00 00 00 00 00 00

00:    messageID
01:    ??
02-14: 00

-------------------------------------------------------------------------------
9. ReadConfigFlash in - receive data

000: dc 0a 01 f5 00 01 78 a0 01 02  0a 0c 0c 01 2e ff ff ff ff ff - freq correction
000: dc 0a 01 f9 01 02 0a 0c 0c 01  2e ff ff ff ff ff ff ff ff ff - transceiver data

00:    messageID
01:    length
02-03: address

Additional bytes frequency correction
05lo-07hi: frequency correction

Additional bytes transceiver data
05-10:     serial number
09-10:     DeviceID [devID]

-------------------------------------------------------------------------------
10. ReadConfigFlash out - ask for data

000: dd 0a 01 f5 cc cc cc cc cc cc  cc cc cc cc cc - Ask for freq correction
000: dd 0a 01 f9 cc cc cc cc cc cc  cc cc cc cc cc - Ask for transceiver data

00:    messageID
01:    length
02-03: address
04-14: cc

-------------------------------------------------------------------------------
11. GetState message

000:  de 14 00 00 00 00 (between SetPreamblePattern and first de16 message)
000:  de 15 00 00 00 00 Idle message
000:  de 16 00 00 00 00 Normal message
000:  de 0b 00 00 00 00 (detected via USB sniffer)

00:    messageID
01:    stateID
02-05: 00

-------------------------------------------------------------------------------
12. Writereg message

000: f0 08 01 00 00 - AX5051RegisterNames.IFMODE
000: f0 10 01 41 00 - AX5051RegisterNames.MODULATION
000: f0 11 01 07 00 - AX5051RegisterNames.ENCODING
...
000: f0 7b 01 88 00 - AX5051RegisterNames.TXRATEMID 
000: f0 7c 01 23 00 - AX5051RegisterNames.TXRATELO
000: f0 7d 01 35 00 - AX5051RegisterNames.TXDRIVER

00:    messageID
01:    register address
02:    01
03:    AX5051RegisterName
04:    00

-------------------------------------------------------------------------------
13. Current Weather message

start  hi-lo  chars  rem  name
0      hi     4           DevID
2      hi     2           Action
3      hi     2           Quality
4      hi     4           DeviceCS
6      hi     4      6    _AlarmRingingFlags
8      hi     1           _WeatherTendency
8      lo     1           _WeatherState
9      hi     1           not used
9      lo     10          _TempIndoorMinMax._Max._Time
14     lo     10          _TempIndoorMinMax._Min._Time
19     lo     5           _TempIndoorMinMax._Max._Value
22     hi     5           _TempIndoorMinMax._Min._Value
24     lo     5           _TempIndoor
27     lo     10          _TempOutdoorMinMax._Max._Time
32     lo     10          _TempOutdoorMinMax._Min._Time
37     lo     5           _TempOutdoorMinMax._Max._Value
40     hi     5           _TempOutdoorMinMax._Min._Value
42     lo     5           _TempOutdoor
45     hi     1           not used
45     lo     10     1    _WindchillMinMax._Max._Time
50     lo     10     2    _WindchillMinMax._Min._Time
55     lo     5      1    _WindchillMinMax._Max._Value
57     hi     5      1    _WindchillMinMax._Min._Value
60     lo     6           _Windchill
63     hi     1           not used
63     lo     10          _DewpointMinMax._Max._Time
68     lo     10          _DewpointMinMax._Min._Time
73     lo     5           _DewpointMinMax._Max._Value
76     hi     5           _DewpointMinMax._Min._Value
78     lo     5           _Dewpoint
81     hi     10          _HumidityIndoorMinMax._Max._Time
86     hi     10          _HumidityIndoorMinMax._Min._Time
91     hi     2           _HumidityIndoorMinMax._Max._Value
92     hi     2           _HumidityIndoorMinMax._Min._Value
93     hi     2           _HumidityIndoor
94     hi     10          _HumidityOutdoorMinMax._Max._Time
99     hi     10          _HumidityOutdoorMinMax._Min._Time
104    hi     2           _HumidityOutdoorMinMax._Max._Value
105    hi     2           _HumidityOutdoorMinMax._Min._Value
106    hi     2           _HumidityOutdoor
107    hi     10     3    _RainLastMonthMax._Time
112    hi     6      3    _RainLastMonthMax._Max._Value
115    hi     6           _RainLastMonth
118    hi     10     3    _RainLastWeekMax._Time
123    hi     6      3    _RainLastWeekMax._Max._Value
126    hi     6           _RainLastWeek
129    hi     10          _Rain24HMax._Time
134    hi     6           _Rain24HMax._Max._Value
137    hi     6           _Rain24H
140    hi     10          _Rain24HMax._Time
145    hi     6           _Rain24HMax._Max._Value
148    hi     6           _Rain24H
151    hi     1           not used
152    lo     10          _LastRainReset
158    lo     7           _RainTotal
160    hi     1           _WindDirection5
160    lo     1           _WindDirection4
161    hi     1           _WindDirection3
161    lo     1           _WindDirection2
162    hi     1           _WindDirection1
162    lo     1           _WindDirection
163    hi     18          unknown data
172    hi     6           _WindSpeed
175    hi     1           _GustDirection5
175    lo     1           _GustDirection4
176    hi     1           _GustDirection3
176    lo     1           _GustDirection2
177    hi     1           _GustDirection1
177    lo     1           _GustDirection
178    hi     2           not used
179    hi     10          _GustMax._Max._Time
184    hi     6           _GustMax._Max._Value
187    hi     6           _Gust
190    hi     10     4    _PressureRelative_MinMax._Max/Min._Time
195    hi     5      5    _PressureRelative_inHgMinMax._Max._Value
197    lo     5      5    _PressureRelative_hPaMinMax._Max._Value
200    hi     5           _PressureRelative_inHgMinMax._Max._Value
202    lo     5           _PressureRelative_hPaMinMax._Max._Value
205    hi     5           _PressureRelative_inHgMinMax._Min._Value
207    lo     5           _PressureRelative_hPaMinMax._Min._Value
210    hi     5           _PressureRelative_inHg
212    lo     5           _PressureRelative_hPa

214    lo     430         end

Remarks
  1 since factory reset
  2 since software reset
  3 not used?
  4 should be: _PressureRelative_MinMax._Max._Time
  5 should be: _PressureRelative_MinMax._Min._Time
  6 _AlarmRingingFlags (values in hex)
    80 00 = Hi Al Gust
    40 00 = Al WindDir
    20 00 = One or more WindDirs set
    10 00 = Hi Al Rain24H
    08 00 = Hi Al Outdoor Humidity
    04 00 = Lo Al Outdoor Humidity
    02 00 = Hi Al Indoor Humidity
    01 00 = Lo Al Indoor Humidity
    00 80 = Hi Al Outdoor Temp
    00 40 = Lo Al Outdoor Temp
    00 20 = Hi Al Indoor Temp
    00 10 = Lo Al Indoor Temp
    00 08 = Hi Al Pressure
    00 04 = Lo Al Pressure
    00 02 = not used
    00 01 = not used

-------------------------------------------------------------------------------
14. History Message

start  hi-lo  chars  rem  name
0      hi     4           DevID
2      hi     2           Action
3      hi     2           Quality
4      hi     4           DeviceCS
6      hi     6           LatestIndex
9      hi     6           ThisIndex
12     hi     1           not used
12     lo     3           Gust
14     hi     1           WindDirection
14     lo     3           WindSpeed
16     hi     3           RainCounterRaw
17     lo     2           HumidityOutdoor
18     lo     2           HumidityIndoor
19     lo     5           PressureRelative
22     hi     3           TempOutdoor
23     lo     3           TempIndoor
25     hi     10          Time

29     lo     60   end

-------------------------------------------------------------------------------
15. Set Config Message

start  hi-lo  chars  rem  name
0      hi     4           DevID
2      hi     2           Action
3      hi     2           Quality
4      hi     1       1   _WindspeedFormat
4      lo     0,25    2   _RainFormat
4      lo     0,25    3   _PressureFormat
4      lo     0,25    4   _TemperatureFormat
4      lo     0,25    5   _ClockMode
5      hi     1           _WeatherThreshold
5      lo     1           _StormThreshold
6      hi     1           _LowBatFlags
6      lo     1       6   _LCDContrast
7      hi     4       7   _WindDirAlarmFlags (reverse group 1)
9      hi     4       8   _OtherAlarmFlags   (reverse group 1)
11     hi     10          _TempIndoorMinMax._Min._Value (reverse group 2)
                          _TempIndoorMinMax._Max._Value (reverse group 2)
16     hi     10          _TempOutdoorMinMax._Min._Value (reverse group 3)
                          _TempOutdoorMinMax._Max._Value (reverse group 3)
21     hi     2           _HumidityIndoorMinMax._Min._Value
22     hi     2           _HumidityIndoorMinMax._Max._Value
23     hi     2           _HumidityOutdoorMinMax._Min._Value
24     hi     2           _HumidityOutdoorMinMax._Max._Value
25     hi     1           not used
25     lo     7           _Rain24HMax._Max._Value (reverse bytes)
29     hi     2           _HistoryInterval
30     hi     1           not used
30     lo     5           _GustMax._Max._Value (reverse bytes)
33     hi     10          _PressureRelative_hPaMinMax._Min._Value (rev grp4)
                          _PressureRelative_inHgMinMax._Min._Value(rev grp4)
38     hi     10          _PressureRelative_hPaMinMax._Max._Value (rev grp5)
                          _PressureRelative_inHgMinMax._Max._Value(rev grp5)
43     hi     6       9   _ResetMinMaxFlags
46     hi     4       10  _InBufCS

47     lo     96          end

Remarks 
  1 0=m/s 1=knots 2=bft 3=km/h 4=mph
  2 0=mm   1=inch
  3 0=inHg 2=hPa
  4 0=F    1=C
  5 0=24h  1=12h
  6 values 0-7 => LCD contrast 1-8
  7 WindDir Alarms (not-reversed values in hex)
    80 00 = NNW
    40 00 = NW
    20 00 = WNW
    10 00 = W
    08 00 = WSW
    04 00 = SW
    02 00 = SSW
    01 00 = S
    00 80 = SSE
    00 40 = SE
    00 20 = ESE
    00 10 = E
    00 08 = ENE
    00 04 = NE
    00 02 = NNE
    00 01 = N
  8 Other Alarms (not-reversed values in hex)
    80 00 = Hi Al Gust
    40 00 = Al WindDir
    20 00 = One or more WindDirs set
    10 00 = Hi Al Rain24H
    08 00 = Hi Al Outdoor Humidity
    04 00 = Lo Al Outdoor Humidity
    02 00 = Hi Al Indoor Humidity
    01 00 = Lo Al Indoor Humidity
    00 80 = Hi Al Outdoor Temp
    00 40 = Lo Al Outdoor Temp
    00 20 = Hi Al Indoor Temp
    00 10 = Lo Al Indoor Temp
    00 08 = Hi Al Pressure
    00 04 = Lo Al Pressure
    00 02 = not used
    00 01 = not used
  9 ResetMinMaxFlags (not-reversed values in hex)
    "Output only; not included in checksum calc"
    80 00 00 =  Reset DewpointMax
    40 00 00 =  Reset DewpointMin
    20 00 00 =  not used
    10 00 00 =  Reset WindchillMin*
    "*Reset dateTime only; Min._Value is preserved"
    08 00 00 =  Reset TempOutMax
    04 00 00 =  Reset TempOutMin
    02 00 00 =  Reset TempInMax
    01 00 00 =  Reset TempInMin
    00 80 00 =  Reset Gust
    00 40 00 =  not used
    00 20 00 =  not used
    00 10 00 =  not used
    00 08 00 =  Reset HumOutMax
    00 04 00 =  Reset HumOutMin
    00 02 00 =  Reset HumInMax
    00 01 00 =  Reset HumInMin
    00 00 80 =  not used
    00 00 40 =  Reset Rain Total
    00 00 20 =  Reset last month?
    00 00 10 =  Reset lastweek?
    00 00 08 =  Reset Rain24H
    00 00 04 =  Reset Rain1H
    00 00 02 =  Reset PresRelMax
    00 00 01 =  Reset PresRelMin
  10 Checksum = sum bytes (0-42) + 7 

-------------------------------------------------------------------------------
16. Get Config Message

start  hi-lo  chars  rem  name
0      hi     4           DevID
2      hi     2           Action
3      hi     2           Quality
4      hi     1      1    _WindspeedFormat
4      lo     0,25   2    _RainFormat
4      lo     0,25   3    _PressureFormat
4      lo     0,25   4    _TemperatureFormat
4      lo     0,25   5    _ClockMode
5      hi     1           _WeatherThreshold
5      lo     1           _StormThreshold
6      hi     1           _LowBatFlags
6      lo     1      6    _LCDContrast
7      hi     4      7    _WindDirAlarmFlags
9      hi     4      8    _OtherAlarmFlags
11     hi     5           _TempIndoorMinMax._Min._Value
13     lo     5           _TempIndoorMinMax._Max._Value
16     hi     5           _TempOutdoorMinMax._Min._Value
18     lo     5           _TempOutdoorMinMax._Max._Value
21     hi     2           _HumidityIndoorMinMax._Max._Value
22     hi     2           _HumidityIndoorMinMax._Min._Value
23     hi     2           _HumidityOutdoorMinMax._Max._Value
24     hi     2           _HumidityOutdoorMinMax._Min._Value
25     hi     1           not used
25     lo     7           _Rain24HMax._Max._Value
29     hi     2           _HistoryInterval
30     hi     5           _GustMax._Max._Value
32     lo     1           not used
33     hi     5           _PressureRelative_hPaMinMax._Min._Value
35     lo     5           _PressureRelative_inHgMinMax._Min._Value
38     hi     5           _PressureRelative_hPaMinMax._Max._Value
40     lo     5           _PressureRelative_inHgMinMax._Max._Value
43     hi     6      9    _ResetMinMaxFlags
46     hi     4      10   _InBufCS

47     lo     96          end

Remarks
  1 0=m/s 1=knots 2=bft 3=km/h 4=mph
  2 0=mm   1=inch
  3 0=inHg 2=hPa
  4 0=F    1=C
  5 0=24h  1=12h
  6 values 0-7 => LCD contrast 1-8
  7 WindDir Alarms (values in hex)
    80 00 = NNW
    40 00 = NW
    20 00 = WNW
    10 00 = W
    08 00 = WSW
    04 00 = SW
    02 00 = SSW
    01 00 = S
    00 80 = SSE
    00 40 = SE
    00 20 = ESE
    00 10 = E
    00 08 = ENE
    00 04 = NE
    00 02 = NNE
    00 01 = N
  8 Other Alarms (values in hex)
    80 00 = Hi Al Gust
    40 00 = Al WindDir
    20 00 = One or more WindDirs set
    10 00 = Hi Al Rain24H
    08 00 = Hi Al Outdoor Humidity
    04 00 = Lo Al Outdoor Humidity
    02 00 = Hi Al Indoor Humidity
    01 00 = Lo Al Indoor Humidity
    00 80 = Hi Al Outdoor Temp
    00 40 = Lo Al Outdoor Temp
    00 20 = Hi Al Indoor Temp
    00 10 = Lo Al Indoor Temp
    00 08 = Hi Al Pressure
    00 04 = Lo Al Pressure
    00 02 = not used
    00 01 = not used
  9 ResetMinMaxFlags (values in hex)
    "Output only; input =  00 00 00"
  10 Checksum = sum bytes (0-42) + 7 


-------------------------------------------------------------------------------
Examples of messages

readCurrentWeather
Cur   000: 01 2e 60 5f 05 1b 00 00 12 01  30 62 21 54 41 30 62 40 75 36  
Cur   020: 59 00 60 70 06 35 00 01 30 62  31 61 21 30 62 30 55 95 92 00  
Cur   040: 53 10 05 37 00 01 30 62 01 90  81 30 62 40 90 66 38 00 49 00  
Cur   060: 05 37 00 01 30 62 21 53 01 30  62 22 31 75 51 11 50 40 05 13  
Cur   080: 80 13 06 22 21 40 13 06 23 19  37 67 52 59 13 06 23 06 09 13  
Cur   100: 06 23 16 19 91 65 86 00 00 00  00 00 00 00 00 00 00 00 00 00  
Cur   120: 00 00 00 00 00 00 00 00 00 13  06 23 09 59 00 06 19 00 00 51  
Cur   140: 13 06 22 20 43 00 01 54 00 00  00 01 30 62 21 51 00 00 38 70  
Cur   160: a7 cc 7b 50 09 01 01 00 00 00  00 00 00 fc 00 a7 cc 7b 14 13  
Cur   180: 06 23 14 06 0e a0 00 01 b0 00  13 06 23 06 34 03 00 91 01 92  
Cur   200: 03 00 91 01 92 02 97 41 00 74  03 00 91 01 92
 
WeatherState: Sunny(Good)  WeatherTendency: Rising(Up)  AlarmRingingFlags: 0000
TempIndoor      23.500 Min:20.700 2013-06-24 07:53 Max:25.900 2013-06-22 15:44
HumidityIndoor  59.000 Min:52.000 2013-06-23 19:37 Max:67.000 2013-06-22 21:40
TempOutdoor     13.700 Min:13.100 2013-06-23 05:59 Max:19.200 2013-06-23 16:12
HumidityOutdoor 86.000 Min:65.000 2013-06-23 16:19 Max:91.000 2013-06-23 06:09
Windchill       13.700 Min: 9.000 2013-06-24 09:06 Max:23.800 2013-06-20 19:08
Dewpoint        11.380 Min:10.400 2013-06-22 23:17 Max:15.111 2013-06-22 15:30
WindSpeed        2.520
Gust             4.320                             Max:37.440 2013-06-23 14:06
WindDirection    WSW    GustDirection    WSW
WindDirection1   SSE    GustDirection1   SSE
WindDirection2     W    GustDirection2     W
WindDirection3     W    GustDirection3     W
WindDirection4   SSE    GustDirection4   SSE
WindDirection5    SW    GustDirection5    SW
RainLastMonth    0.000                             Max: 0.000 1900-01-01 00:00
RainLastWeek     0.000                             Max: 0.000 1900-01-01 00:00
Rain24H          0.510                             Max: 6.190 2013-06-23 09:59
Rain1H           0.000                             Max: 1.540 2013-06-22 20:43
RainTotal        3.870                    LastRainReset       2013-06-22 15:10
PresRelhPa 1019.200 Min:1007.400 2013-06-23 06:34 Max:1019.200 2013-06-23 06:34
PresRel_inHg 30.090 Min:  29.740 2013-06-23 06:34 Max:  30.090 2013-06-23 06:34
Bytes with unknown meaning at 157-165: 50 09 01 01 00 00 00 00 00 

-------------------------------------------------------------------------------
readHistory
His   000: 01 2e 80 5f 05 1b 00 7b 32 00  7b 32 00 0c 70 0a 00 08 65 91  
His   020: 01 92 53 76 35 13 06 24 09 10 
 
Time           2013-06-24 09:10:00
TempIndoor=          23.5
HumidityIndoor=        59
TempOutdoor=         13.7
HumidityOutdoor=       86
PressureRelative=  1019.2
RainCounterRaw=       0.0
WindDirection=        SSE
WindSpeed=            1.0
Gust=                 1.2

-------------------------------------------------------------------------------
readConfig
In   000: 01 2e 40 5f 36 53 02 00 00 00  00 81 00 04 10 00 82 00 04 20  
In   020: 00 71 41 72 42 00 05 00 00 00  27 10 00 02 83 60 96 01 03 07  
In   040: 21 04 01 00 00 00 05 1b

-------------------------------------------------------------------------------
writeConfig
Out  000: 01 2e 40 64 36 53 02 00 00 00  00 00 10 04 00 81 00 20 04 00  
Out  020: 82 41 71 42 72 00 00 05 00 00  00 10 27 01 96 60 83 02 01 04  
Out  040: 21 07 03 10 00 00 05 1b 

OutBufCS=             051b
ClockMode=            0
TemperatureFormat=    1
PressureFormat=       1
RainFormat=           0
WindspeedFormat=      3
WeatherThreshold=     3
StormThreshold=       5
LCDContrast=          2
LowBatFlags=          0
WindDirAlarmFlags=    0000
OtherAlarmFlags=      0000
HistoryInterval=      0
TempIndoor_Min=       1.0
TempIndoor_Max=       41.0
TempOutdoor_Min=      2.0
TempOutdoor_Max=      42.0
HumidityIndoor_Min=   41
HumidityIndoor_Max=   71
HumidityOutdoor_Min=  42
HumidityOutdoor_Max=  72
Rain24HMax=           50.0
GustMax=              100.0
PressureRel_hPa_Min=  960.1
PressureRel_inHg_Min= 28.36
PressureRel_hPa_Max=  1040.1
PressureRel_inHg_Max= 30.72
ResetMinMaxFlags=     100000 (Output only; Input always 00 00 00)

-------------------------------------------------------------------------------
class EHistoryInterval:
Constant         ValueMessage received at
hi01Min          = 000:00, 00:01, 00:02, 00:03 ... 23:59
hi05Min          = 100:00, 00:05, 00:10, 00:15 ... 23:55
hi10Min          = 200:00, 00:10, 00:20, 00:30 ... 23:50
hi15Min          = 300:00, 00:15, 00:30, 00:45 ... 23:45
hi20Min          = 400:00, 00:20, 00:40, 01:00 ... 23:40
hi30Min          = 500:00, 00:30, 01:00, 01:30 ... 23:30
hi60Min          = 600:00, 01:00, 02:00, 03:00 ... 23:00
hi02Std          = 700:00, 02:00, 04:00, 06:00 ... 22:00
hi04Std          = 800:00, 04:00, 08:00, 12:00 ... 20:00
hi06Std          = 900:00, 06:00, 12:00, 18:00
hi08Std          = 0xA00:00, 08:00, 16:00
hi12Std          = 0xB00:00, 12:00
hi24Std          = 0xC00:00

-------------------------------------------------------------------------------
WS SetTime - Send time to WS
Time  000: 01 2e c0 05 1b 19 14 12 40 62  30 01
time sent: 2013-06-24 12:14:19 

-------------------------------------------------------------------------------
ReadConfigFlash data

Ask for frequency correction 
rcfo  000: dd 0a 01 f5 cc cc cc cc cc cc  cc cc cc cc cc

readConfigFlash frequency correction
rcfi  000: dc 0a 01 f5 00 01 78 a0 01 02  0a 0c 0c 01 2e ff ff ff ff ff
frequency correction: 96416 (178a0)
adjusted frequency: 910574957 (3646456d)

Ask for transceiver data 
rcfo  000: dd 0a 01 f9 cc cc cc cc cc cc  cc cc cc cc cc

readConfigFlash serial number and DevID
rcfi  000: dc 0a 01 f9 01 02 0a 0c 0c 01  2e ff ff ff ff ff ff ff ff ff
transceiver ID: 302 (12e)
transceiver serial: 01021012120146

"""

# TODO: how often is currdat.lst modified with/without hi-speed mode?
# TODO: during weewx startup, do 'catchup' of old history records
# TODO: thread locking around observation data
# TODO: eliminate polling, make MainThread get data as soon as RFThread updates
# TODO: eliminate pressure_offset and use StdCalibrate instead?
# TODO: get rid of Length/Buffer construct, replace with a Buffer class or obj

from datetime import datetime
from datetime import timedelta
from configobj import ConfigObj

import StringIO
import copy
import math
import platform
import syslog
import threading
import time
import traceback
import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.units
import weewx.wxengine

DRIVER_VERSION = '0.13'

# flags for enabling/disabling debug verbosity
DEBUG_WRITES = 0
DEBUG_COMM = 0
DEBUG_CONFIG_DATA = 0
DEBUG_WEATHER_DATA = 0
DEBUG_HISTORY_DATA = 0
DEBUG_DUMP_FORMAT = 'short'

def logmsg(dst, msg):
    syslog.syslog(dst, 'ws28xx: %s: %s' %
                  (threading.currentThread().getName(), msg))

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def log_traceback(dst=syslog.LOG_INFO, prefix='**** '):
    sfd = StringIO.StringIO()
    traceback.print_exc(file=sfd)
    sfd.seek(0)
    for line in sfd:
        logmsg(dst, prefix+line)
    del sfd

def log_frame(n, buf):
    logdbg('frame length is %d' % n)
    strbuf = ''
    for i in xrange(0,n):
        strbuf += str('%02x ' % buf[i])
        if (i+1) % 16 == 0:
            logdbg(strbuf)
            strbuf = ''
    if strbuf:
        logdbg(strbuf)

def get_datum_diff(v, np):
    if abs(np - v) > 0.001:
        return v
    return None

def get_datum_match(v, np):
    if np != v:
        return v
    return None

def calc_checksum(buf, start, end=None):
    if end is None:
        end = len(buf[0]) - start
    cs = 0
    for i in xrange(0, end):
        cs += buf[0][i+start]
    return cs

# noaa definitions for station pressure, altimeter setting, and sea level
# http://www.crh.noaa.gov/bou/awebphp/definitions_pressure.php

# FIXME: this goes in wxformulas
# implementation copied from wview
def sp2ap(sp_mbar, elev_meter):
    """Convert station pressure to sea level pressure.
    http://www.wrh.noaa.gov/slc/projects/wxcalc/formulas/altimeterSetting.pdf

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    ap - sea level pressure (altimeter) in millibars
    """

    if sp_mbar is None or elev_meter is None:
        return None
    N = 0.190284
    slp = 1013.25
    ct = (slp ** N) * 0.0065 / 288
    vt = elev_meter / ((sp_mbar - 0.3) ** N)
    ap_mbar = (sp_mbar - 0.3) * ((ct * vt + 1) ** (1/N))
    return ap_mbar

# FIXME: this goes in wxformulas
# implementation copied from wview
def sp2bp(sp_mbar, elev_meter, t_C):
    """Convert station pressure to sea level pressure.

    sp_mbar - station pressure in millibars

    elev_meter - station elevation in meters

    t_C - temperature in degrees Celsius

    bp - sea level pressure (barometer) in millibars
    """

    if sp_mbar is None or elev_meter is None or t_C is None:
        return None
    t_K = t_C + 273.15
    pt = math.exp( - elev_meter / (t_K * 29.263))
    bp_mbar = sp_mbar / pt if pt != 0 else 0
    return bp_mbar

# FIXME: this goes in weeutil.weeutil or weewx.units
def getaltitudeM(config_dict):
    # The driver needs the altitude in meters in order to calculate relative
    # pressure. Get it from the Station data and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(
        config_dict['Station'].get('altitude', (None, None)))
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    return altitude_m

# FIXME: this goes in weeutil.weeutil
# let QC handle rainfall that is too big
def calculate_rain(newtotal, oldtotal):
    """Calculate the rain differential given two cumulative measurements."""
    if newtotal is not None and oldtotal is not None:
        if newtotal >= oldtotal:
            delta = newtotal - oldtotal
        else:  # wraparound
            logerr('rain counter wraparound detected: new: %s old: %s' % (newtotal, oldtotal))
            delta = None
    else:
        delta = None
    return delta

def loader(config_dict, engine):
    altitude_m = getaltitudeM(config_dict)
    station = WS28xx(altitude=altitude_m, **config_dict['WS28xx'])
    return station

class WS28xx(weewx.abstractstation.AbstractStation):
    """Driver for LaCrosse WS28xx stations."""
    
    def __init__(self, **stn_dict) :
        """Initialize the station object.

        altitude: Altitude of the station
        [Required. No default]

        pressure_offset: Calibration offset in millibars for the station
        pressure sensor.  This offset is added to the station sensor output
        before barometer and altimeter pressures are calculated.
        [Optional. No Default]

        model: Which station model is this?
        [Optional. Default is 'LaCrosse WS28xx']

        transceiver_frequency: Frequency for transceiver-to-console.  Specify
        either US or EU.
        [Required. Default is US]

        polling_interval: How often to sample the USB interface for data.
        [Optional. Default is 30 seconds]

        cache_file: file in which to cache connection status, station config
        [Optional. Default is None]

        vendor_id: The USB vendor ID for the transceiver.
        [Optional. Default is 6666]

        product_id: The USB product ID for the transceiver.
        [Optional. Default is 5555]

        device_id: The USB device ID for the transceiver.  If there are
        multiple devices with the same vendor and product IDs on the bus,
        each will have a unique device identifier.  Use this identifier
        to indicate which device should be used.
        [Optional. Default is None]
        """

        self.altitude          = stn_dict['altitude']
        self.model             = stn_dict.get('model', 'LaCrosse WS28xx')
        self.cache_file        = stn_dict.get('cache_file', None)
        self.polling_interval  = int(stn_dict.get('polling_interval', 30))
        self.frequency         = stn_dict.get('transceiver_frequency', 'US')
        self.vendor_id         = int(stn_dict.get('vendor_id',  '0x6666'), 0)
        self.product_id        = int(stn_dict.get('product_id', '0x5555'), 0)
        self.device_id         = stn_dict.get('device_id', None)
        self.pressure_offset   = stn_dict.get('pressure_offset', None)
        if self.pressure_offset is not None:
            self.pressure_offset = float(self.pressure_offset)

        self._service = None
        self._last_rain = None
        self._last_obs_ts = None

        global DEBUG_WRITES
        DEBUG_WRITES = int(stn_dict.get('debug_writes', 0))
        global DEBUG_COMM
        DEBUG_COMM = int(stn_dict.get('debug_comm', 0))
        global DEBUG_CONFIG_DATA
        DEBUG_CONFIG_DATA = int(stn_dict.get('debug_config_data', 0))
        global DEBUG_WEATHER_DATA
        DEBUG_WEATHER_DATA = int(stn_dict.get('debug_weather_data', 0))
        global DEBUG_HISTORY_DATA
        DEBUG_HISTORY_DATA = int(stn_dict.get('debug_history_data', 0))
        global DEBUG_DUMP_FORMAT
        DEBUG_DUMP_FORMAT = stn_dict.get('debug_dump_format', 'short')

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('frequency is %s' % self.frequency)
        loginf('altitude is %s meters' % str(self.altitude))
        loginf('pressure offset is %s' % str(self.pressure_offset))

    @property
    def hardware_name(self):
        return self.model

    def openPort(self):
        # FIXME: init the usb here
        pass

    def closePort(self):
        # FIXME: shutdown the usb port here
        pass

    def genLoopPackets(self):
        """Generator function that continuously returns decoded packets"""

        self.startup()
        maxnodata = 20
        nodata = 0
        while True:
            try:
                packet = self.get_observation()
                if packet is not None:
                    yield packet
                    nodata = 0
                else:
                    nodata += 1
                if nodata >= maxnodata:
                    dur = nodata * self.polling_interval
                    logerr('no new data after %d seconds' % dur)
                    nodata = 0
                time.sleep(self.polling_interval)
            except (KeyboardInterrupt, weewx.wxengine.Terminate), e:
                self.shutdown()
                raise
            except Exception, e:
                logerr('exception in genLoopPackets: %s' % e)
                if weewx.debug:
                    log_traceback(dst=syslog.LOG_DEBUG)
                raise

    def startup(self):
        if self._service is not None:
            return
        self._service = CCommunicationService(self.cache_file)
        self._service.setup(self.frequency, self.vendor_id, self.product_id, self.device_id)
        self._service.startRFThread()

    def shutdown(self):
        self._service.stopRFThread()
        self._service.teardown()
        self._service = None

    def pair(self, msg_to_console=False, maxtries=0):
        ntries = 0
        while ntries < maxtries or maxtries == 0:
            if self._service.transceiverIsRegistered():
                return
            ntries += 1
            msg = 'press [v] key on station console'
            if maxtries > 0:
                msg += ' (attempt %d of %d)' % (ntries, maxtries)
            else:
                msg += ' (attempt %d)' % ntries
            if msg_to_console:
                print msg
            logerr(msg)
            timeout = 30000 # milliseconds
            self._service.pairTransceiver(timeout)
        else:
            raise Exception('Transceiver not paired to console.')

    def check_transceiver(self, msg_to_console=False, maxtries=3):
        ntries = 0
        while ntries < maxtries:
            ntries += 1
            t = self._service.transceiverIsPresent()
            if t:
                msg = 'transceiver is present'
            else:
                msg = 'transceiver not found (attempt %d of %d)' % (
                    ntries, maxtries)
            if msg_to_console:
                print msg
            loginf(msg)
            if t:
                return
            time.sleep(5)
        else:
            raise Exception('Transceiver not responding.')

    def get_observation(self):
        data = self._service.getWeatherData()
        ts = data._timestamp
        if ts is None:
            return None
        if self._last_obs_ts is not None and self._last_obs_ts == ts:
            return None
        self._last_obs_ts = ts

        # add elements required for weewx LOOP packets
        packet = {}
        packet['usUnits'] = weewx.METRIC
        packet['dateTime'] = int(ts + 0.5)

        # data from the station sensors
        packet['inTemp']      = get_datum_diff(data._TempIndoor,
                                               CWeatherTraits.TemperatureNP())
        packet['inHumidity']  = get_datum_diff(data._HumidityIndoor,
                                               CWeatherTraits.HumidityNP())
        packet['outTemp']     = get_datum_diff(data._TempOutdoor,
                                               CWeatherTraits.TemperatureNP())
        packet['outHumidity'] = get_datum_diff(data._HumidityOutdoor,
                                               CWeatherTraits.HumidityNP())
        packet['pressure']    = get_datum_diff(data._PressureRelative_hPa,
                                               CWeatherTraits.PressureNP())
        packet['windSpeed']   = get_datum_diff(data._WindSpeed,
                                               CWeatherTraits.WindNP())
        packet['windGust']    = get_datum_diff(data._Gust,
                                               CWeatherTraits.WindNP())

        if packet['windSpeed'] is not None and packet['windSpeed'] > 0:
            packet['windDir'] = data._WindDirection * 360 / 16
        else:
            packet['windDir'] = None

        if packet['windGust'] is not None and packet['windGust'] > 0:
            packet['windGustDir'] = data._GustDirection * 360 / 16
        else:
            packet['windGustDir'] = None

        # calculated elements not directly reported by station
        packet['rainRate'] = get_datum_match(data._Rain1H,
                                             CWeatherTraits.RainNP())
        if packet['rainRate'] is not None:
            packet['rainRate'] /= 10 # weewx wants cm/hr
        rain_total = get_datum_match(data._RainTotal, CWeatherTraits.RainNP())
        delta = calculate_rain(rain_total, self._last_rain)
        self._last_rain = rain_total
        packet['rain'] = delta
        if packet['rain'] is not None:
            packet['rain'] /= 10 # weewx wants cm

        packet['heatindex'] = weewx.wxformulas.heatindexC(
            packet['outTemp'], packet['outHumidity'])
        packet['dewpoint'] = weewx.wxformulas.dewpointC(
            packet['outTemp'], packet['outHumidity'])
        packet['windchill'] = weewx.wxformulas.windchillC(
            packet['outTemp'], packet['windSpeed'])

        # station reports gauge pressure, must calculate other pressures
        adjp = packet['pressure']
        if self.pressure_offset is not None and adjp is not None:
            adjp += self.pressure_offset
        packet['barometer'] = sp2bp(adjp, self.altitude, packet['outTemp'])
        packet['altimeter'] = sp2ap(adjp, self.altitude)

        # track the signal strength and battery levels
        laststat = self._service.getLastStat()
        packet['signal'] = laststat.LastLinkQuality
        packet['battery'] = laststat.LastBatteryStatus

        return packet

    def get_config(self):
        logdbg('get station configuration')
        return self._service.getConfig()

    def get_history(self):
        logdbg('get historical records')
        return self._service.getHistory()

# The following classes and methods are adapted from the implementation by
# eddie de pieri, which is in turn based on the HeavyWeather implementation.

class BadResponse(Exception):
    '''raised when unexpected data found in frame buffer'''
    pass

class DataWritten(Exception):
    '''raised when message 'data written' in frame buffer'''
    pass

class BitHandling:
    # return a nonzero result, 2**offset, if the bit at 'offset' is one.
    @staticmethod
    def testBit(int_type, offset):
        mask = 1 << offset
        return(int_type & mask)

    # return an integer with the bit at 'offset' set to 1.
    @staticmethod
    def setBit(int_type, offset):
        mask = 1 << offset
        return(int_type | mask)

    # return an integer with the bit at 'offset' set to 1.
    @staticmethod
    def setBitVal(int_type, offset, val):
        mask = val << offset
        return(int_type | mask)

    # return an integer with the bit at 'offset' cleared.
    @staticmethod
    def clearBit(int_type, offset):
        mask = ~(1 << offset)
        return(int_type & mask)

    # return an integer with the bit at 'offset' inverted, 0->1 and 1->0.
    @staticmethod
    def toggleBit(int_type, offset):
        mask = 1 << offset
        return(int_type ^ mask)

class EHistoryInterval:
    hi01Min          = 0
    hi05Min          = 1
    hi10Min          = 2
    hi15Min          = 3
    hi20Min          = 4
    hi30Min          = 5
    hi60Min          = 6
    hi02Std          = 7
    hi04Std          = 8
    hi06Std          = 9
    hi08Std          = 0xA
    hi12Std          = 0xB
    hi24Std          = 0xC

class EWindspeedFormat:
    wfMs             = 0
    wfKnots          = 1
    wfBFT            = 2
    wfKmh            = 3
    wfMph            = 4

class ERainFormat:
    rfMm             = 0
    rfInch           = 1

class EPressureFormat:
    pfinHg           = 0
    pfHPa            = 1

class ETemperatureFormat:
    tfFahrenheit     = 0
    tfCelsius        = 1

class EClockMode:
    ct24H            = 0
    ctAmPm           = 1

class EWeatherTendency:
    TREND_NEUTRAL    = 0
    TREND_UP         = 1
    TREND_DOWN       = 2
    TREND_ERR        = 3

class EWeatherState:
    WEATHER_BAD      = 0
    WEATHER_NEUTRAL  = 1
    WEATHER_GOOD     = 2
    WEATHER_ERR      = 3

class EWindDirection:
    wdN              = 0
    wdNNE            = 1
    wdNE             = 2
    wdENE            = 3
    wdE              = 4
    wdESE            = 5
    wdSE             = 6
    wdSSE            = 7
    wdS              = 8
    wdSSW            = 9
    wdSW             = 0x0A
    wdWSW            = 0x0B
    wdW              = 0x0C
    wdWNW            = 0x0D
    wdNW             = 0x0E
    wdNNW            = 0x0F
    wdERR            = 0x10
    wdInvalid        = 0x11

class EResetMinMaxFlags:
    rmTempIndoorHi   = 0
    rmTempIndoorLo   = 1
    rmTempOutdoorHi  = 2
    rmTempOutdoorLo  = 3
    rmWindchillHi    = 4
    rmWindchillLo    = 5
    rmDewpointHi     = 6
    rmDewpointLo     = 7
    rmHumidityIndoorLo  = 8
    rmHumidityIndoorHi  = 9
    rmHumidityOutdoorLo = 0x0A
    rmHumidityOutdoorHi = 0x0B
    rmWindspeedHi    = 0x0C
    rmWindspeedLo    = 0x0D
    rmGustHi         = 0x0E
    rmGustLo         = 0x0F
    rmPressureLo     = 0x10
    rmPressureHi     = 0x11
    rmRain1hHi       = 0x12
    rmRain24hHi      = 0x13
    rmRainLastWeekHi  = 0x14
    rmRainLastMonthHi = 0x15
    rmRainTotal      = 0x16
    rmInvalid        = 0x17

class ERequestType:
    rtGetCurrent     = 0
    rtGetHistory     = 1
    rtGetConfig      = 2
    rtSetConfig      = 3
    rtSetTime        = 4
    rtFirstConfig    = 5
    rtINVALID        = 6

class EAction:
    aGetHistory      = 0
    aReqSetTime      = 1
    aReqSetConfig    = 2
    aGetConfig       = 3
    aGetCurrent      = 5
    aSendTime        = 0xc0
    aSendConfig      = 0x40

class ERequestState:
    rsQueued         = 0
    rsRunning        = 1
    rsFinished       = 2
    rsPreamble       = 3
    rsWaitDevice     = 4
    rsWaitConfig     = 5
    rsError          = 6
    rsChanged        = 7
    rsINVALID        = 8

class EResponseType:
    rtDataWritten       = 0x20
    rtGetConfig         = 0x40
    rtGetCurrentWeather = 0x60
    rtGetHistory        = 0x80
    rtRequest           = 0xa0
    rtReqFirstConfig    = 0xa1
    rtReqSetConfig      = 0xa2
    rtReqSetTime        = 0xa3

# frequency standards and their associated transmission frequencies
class EFrequency:
    fsUS             = 'US'
    tfUS             = 905000000
    fsEU             = 'EU'
    tfEU             = 868300000

def getFrequency(standard):
    if standard == EFrequency.fsUS:
        return EFrequency.tfUS
    elif standard == EFrequency.fsEU:
        return EFrequency.tfEU
    logerr("unknown frequency standard '%s', using US" % standard)
    return EFrequency.tfUS

def getFrequencyStandard(frequency):
    if frequency == EFrequency.tfUS:
        return EFrequency.fsUS
    elif frequency == EFrequency.tfEU:
        return EFrequency.fsEU
    logerr("unknown frequency '%s', using US" % frequency)
    return EFrequency.fsUS

class CWeatherTraits(object):
    windDirMap = {
        0:"N", 1:"NNE", 2:"NE", 3:"ENE", 4:"E", 5:"ESE", 6:"SE", 7:"SSE",
        8:"S", 9:"SSW", 10:"SW", 11:"WSW", 12:"W", 13:"WNW", 14:"NW",
        15:"NWN", 16:"err", 17:"inv", 18:"None" }
    forecastMap = {
        0:"Rainy(Bad)", 1:"Cloudy(Neutral)", 2:"Sunny(Good)",  3:"Error" }
    trends = {
        0:"Stable(Neutral)", 1:"Rising(Up)", 2:"Falling(Down)", 3:"Error" }

    @staticmethod
    def TemperatureNP():
        return 81.099998

    @staticmethod
    def TemperatureOFL():
        return 136.0

    @staticmethod
    def PressureNP():
        return 10101010.0

    @staticmethod
    def PressureOFL():
        return 16666.5

    @staticmethod
    def HumidityNP():
        return 110.0

    @staticmethod
    def HumidityOFL():
        return 121.0

    @staticmethod
    def RainNP():
        return -0.2

    @staticmethod
    def RainOFL():
        return 16666.664

    @staticmethod
    def WindNP():
        return 183.6 # km/h = 51.0 m/s

    @staticmethod
    def WindOFL():
        return 183.96 # km/h = 51.099998 m/s

    @staticmethod
    def TemperatureOffset():
        return 40.0

class CMeasurement:
    _Value = 0.0
    _ResetFlag = 23
    _IsError = 1
    _IsOverflow = 1
    _Time = time.time()

    def Reset(self):
        self._Value = 0.0
        self._ResetFlag = 23
        self._IsError = 1
        self._IsOverflow = 1

class CMinMaxMeasurement(object):
    def __init__(self):
        self._Min = CMeasurement()
        self._Max = CMeasurement()

# firmware XXX has bogus date values for these fields
_bad_labels = ['RainLastMonthMax','RainLastWeekMax','PressureRelativeMin']

class USBHardware(object):
    @staticmethod
    def isOFL2(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =   (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+0] & 0xF) == 15
        else:
            result =   (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15
        return result

    @staticmethod
    def isOFL3(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =   (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15
        else:
            result =   (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15
        return result

    @staticmethod
    def isOFL5(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =     (buf[0][start+0] >>  4) == 15 \
                or (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15 \
                or (buf[0][start+2] >>  4) == 15
        else:
            result =     (buf[0][start+0] & 0xF) == 15 \
                or (buf[0][start+1] >>  4) == 15 \
                or (buf[0][start+1] & 0xF) == 15 \
                or (buf[0][start+2] >>  4) == 15 \
                or (buf[0][start+2] & 0xF) == 15
        return result

    @staticmethod
    def isErr2(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =    (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or  (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15
        else:
            result =    (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15
        return result
        
    @staticmethod
    def isErr3(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =     (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or  (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15
        else:
            result =     (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15 \
                or  (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15
        return result
        
    @staticmethod
    def isErr5(buf, start, StartOnHiNibble):
        if StartOnHiNibble :
            result =     (buf[0][start+0] >>  4) >= 10 \
                and (buf[0][start+0] >>  4) != 15 \
                or  (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15 \
                or  (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15 \
                or  (buf[0][start+2] >>  4) >= 10 \
                and (buf[0][start+2] >>  4) != 15
        else:
            result =     (buf[0][start+0] & 0xF) >= 10 \
                and (buf[0][start+0] & 0xF) != 15 \
                or  (buf[0][start+1] >>  4) >= 10 \
                and (buf[0][start+1] >>  4) != 15 \
                or  (buf[0][start+1] & 0xF) >= 10 \
                and (buf[0][start+1] & 0xF) != 15 \
                or  (buf[0][start+2] >>  4) >= 10 \
                and (buf[0][start+2] >>  4) != 15 \
                or  (buf[0][start+2] & 0xF) >= 10 \
                and (buf[0][start+2] & 0xF) != 15
        return result

    @staticmethod
    def reverseByteOrder(buf, start, Count):
        nbuf=buf[0]
        for i in xrange(0, Count >> 1):
            tmp = nbuf[start + i]
            nbuf[start + i] = nbuf[start + Count - i - 1]
            nbuf[start + Count - i - 1 ] = tmp
        buf[0]=nbuf

    @staticmethod
    def readWindDirectionShared(buf, start):
        return (buf[0][0+start] & 0xF, buf[0][start] >> 4)

    @staticmethod
    def toInt_2(buf, start, StartOnHiNibble):
        '''read 2 nibbles'''
        if StartOnHiNibble:
            rawpre  = (buf[0][start+0] >>  4)* 10 \
                + (buf[0][start+0] & 0xF)* 1
        else:
            rawpre  = (buf[0][start+0] & 0xF)* 10 \
                + (buf[0][start+1] >>  4)* 1
        return rawpre

    @staticmethod
    def toRain_7_3(buf, start, StartOnHiNibble):
        '''read 7 nibbles, presentation with 3 decimals; units of mm'''
        if ( USBHardware.isErr2(buf, start+0, StartOnHiNibble) or
            USBHardware.isErr5(buf, start+1, StartOnHiNibble)):
            result = CWeatherTraits.RainNP()
        elif ( USBHardware.isOFL2(buf, start+0, StartOnHiNibble) or
                USBHardware.isOFL5(buf, start+1, StartOnHiNibble) ):
            result = CWeatherTraits.RainOFL()
        elif StartOnHiNibble:
            result  = (buf[0][start+0] >>  4)*  1000 \
                + (buf[0][start+0] & 0xF)* 100    \
                + (buf[0][start+1] >>  4)*  10    \
                + (buf[0][start+1] & 0xF)*   1    \
                + (buf[0][start+2] >>  4)*   0.1  \
                + (buf[0][start+2] & 0xF)*   0.01 \
                + (buf[0][start+3] >>  4)*   0.001
        else:
            result  = (buf[0][start+0] & 0xF)*  1000 \
                + (buf[0][start+1] >>  4)* 100    \
                + (buf[0][start+1] & 0xF)*  10    \
                + (buf[0][start+2] >>  4)*   1    \
                + (buf[0][start+2] & 0xF)*   0.1  \
                + (buf[0][start+3] >>  4)*   0.01 \
                + (buf[0][start+3] & 0xF)*   0.001
        return result

    @staticmethod
    def toRain_6_2(buf, start, StartOnHiNibble):
        '''read 6 nibbles, presentation with 2 decimals; units of mm'''
        if ( USBHardware.isErr2(buf, start+0, StartOnHiNibble) or
                USBHardware.isErr2(buf, start+1, StartOnHiNibble) or
                USBHardware.isErr2(buf, start+2, StartOnHiNibble) ):
            result = CWeatherTraits.RainNP()
        elif ( USBHardware.isOFL2(buf, start+0, StartOnHiNibble) or
                USBHardware.isOFL2(buf, start+1, StartOnHiNibble) or
                USBHardware.isOFL2(buf, start+2, StartOnHiNibble) ):
            result = CWeatherTraits.RainOFL()
        elif StartOnHiNibble:
            result  = (buf[0][start+0] >>  4)*  1000 \
                + (buf[0][start+0] & 0xF)* 100   \
                + (buf[0][start+1] >>  4)*  10   \
                + (buf[0][start+1] & 0xF)*   1   \
                + (buf[0][start+2] >>  4)*   0.1 \
                + (buf[0][start+2] & 0xF)*   0.01
        else:
            result  = (buf[0][start+0] & 0xF)*  1000 \
                + (buf[0][start+1] >>  4)* 100   \
                + (buf[0][start+1] & 0xF)*  10   \
                + (buf[0][start+2] >>  4)*   1   \
                + (buf[0][start+2] & 0xF)*   0.1 \
                + (buf[0][start+3] >>  4)*   0.01
        return result

    @staticmethod
    def toRain_3_1(buf, start, StartOnHiNibble):
        '''read 3 nibbles, presentation with 1 decimal; units of mm'''
        if StartOnHiNibble :
            hibyte = buf[0][start+0]
            lobyte = (buf[0][start+1] >> 4) & 0xF
        else:
            hibyte = 16*(buf[0][start+0] & 0xF) + ((buf[0][start+1] >> 4) & 0xF)
            lobyte = buf[0][start+1] & 0xF            
        if hibyte == 0xFF and lobyte == 0xE :
            result = CWeatherTraits.RainNP()
        elif hibyte == 0xFF and lobyte == 0xF :
            result = CWeatherTraits.RainOFL()
        else:
            val = USBHardware.toFloat_3_1(buf, start, StartOnHiNibble)
            result = val
        return result

    @staticmethod  
    def toFloat_3_1(buf, start, StartOnHiNibble):
        '''read 3 nibbles, presentation with 1 decimal'''
        if StartOnHiNibble:
            result = (buf[0][start+0] >>  4)*16**2 \
                + (buf[0][start+0] & 0xF)*   16**1 \
                + (buf[0][start+1] >>  4)*   16**0
        else:
            result = (buf[0][start+0] & 0xF)*16**2 \
                + (buf[0][start+1] >>  4)*   16**1 \
                + (buf[0][start+1] & 0xF)*   16**0
        result = result / 10.0
        return result

    @staticmethod
    def toDateTime(buf, start, StartOnHiNibble, label):
        '''read 10 nibbles, presentation as DateTime'''
        result = None
        if ( USBHardware.isErr2(buf, start+0, StartOnHiNibble)
             or USBHardware.isErr2(buf, start+1, StartOnHiNibble)
             or USBHardware.isErr2(buf, start+2, StartOnHiNibble)
             or USBHardware.isErr2(buf, start+3, StartOnHiNibble)
             or USBHardware.isErr2(buf, start+4, StartOnHiNibble) ):
            logerr('ToDateTime: bogus date for %s: error status in buffer' %
                   label)
        else:
            year    = USBHardware.toInt_2(buf, start+0, StartOnHiNibble) + 2000
            month   = USBHardware.toInt_2(buf, start+1, StartOnHiNibble)
            days    = USBHardware.toInt_2(buf, start+2, StartOnHiNibble)
            hours   = USBHardware.toInt_2(buf, start+3, StartOnHiNibble)
            minutes = USBHardware.toInt_2(buf, start+4, StartOnHiNibble)
            try:
                result = datetime(year, month, days, hours, minutes)
            except ValueError:
                if label not in _bad_labels:
                    logerr(('ToDateTime: bogus date for %s:'
                            ' bad date conversion from'
                            ' %s %s %s %s %s') %
                           (label, minutes, hours, days, month, year))
        if result is None:
            # FIXME: use None instead of a really old date to indicate invalid
            result = datetime(1900, 01, 01, 00, 00)
        return result

    @staticmethod
    def toHumidity_2_0(buf, start, StartOnHiNibble):
        '''read 2 nibbles, presentation with 0 decimal'''
        if USBHardware.isErr2(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.HumidityNP()
        elif USBHardware.isOFL2(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.HumidityOFL()
        else:
            result = USBHardware.toInt_2(buf, start, StartOnHiNibble)
        return result

    @staticmethod
    def toTemperature_5_3(buf, start, StartOnHiNibble):
        '''read 5 nibbles, presentation with 3 decimals; units of degree C'''
        if USBHardware.isErr5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.TemperatureNP()
        elif USBHardware.isOFL5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.TemperatureOFL()
        else:
            if StartOnHiNibble:
                rawtemp = (buf[0][start+0] >>  4)* 10 \
                    + (buf[0][start+0] & 0xF)*  1     \
                    + (buf[0][start+1] >>  4)*  0.1   \
                    + (buf[0][start+1] & 0xF)*  0.01  \
                    + (buf[0][start+2] >>  4)*  0.001
            else:
                rawtemp = (buf[0][start+0] & 0xF)* 10 \
                    + (buf[0][start+1] >>  4)*  1     \
                    + (buf[0][start+1] & 0xF)*  0.1   \
                    + (buf[0][start+2] >>  4)*  0.01  \
                    + (buf[0][start+2] & 0xF)*  0.001
            result = rawtemp - CWeatherTraits.TemperatureOffset()
        return result

    @staticmethod
    def toTemperature_3_1(buf, start, StartOnHiNibble):
        '''read 3 nibbles, presentation with 1 decimal; units of degree C'''
        if USBHardware.isErr3(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.TemperatureNP()
        elif USBHardware.isOFL3(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.TemperatureOFL()
        else:
            if StartOnHiNibble :
                rawtemp   =  (buf[0][start+0] >>  4)*  10 \
                    +  (buf[0][start+0] & 0xF)*  1   \
                    +  (buf[0][start+1] >>  4)*  0.1
            else:
                rawtemp   =  (buf[0][start+0] & 0xF)*  10 \
                    +  (buf[0][start+1] >>  4)*  1   \
                    +  (buf[0][start+1] & 0xF)*  0.1 
            result = rawtemp - CWeatherTraits.TemperatureOffset()
        return result

    @staticmethod
    def toWindspeed_6_2(buf, start):
        '''read 6 nibbles, presentation with 2 decimals; units of km/h'''
        result = (buf[0][start+0] >> 4)* 16**5 \
            + (buf[0][start+0] & 0xF)*   16**4 \
            + (buf[0][start+1] >>  4)*   16**3 \
            + (buf[0][start+1] & 0xF)*   16**2 \
            + (buf[0][start+2] >>  4)*   16**1 \
            + (buf[0][start+2] & 0xF)
        result = result / 256.0
        result = result / 100.0             # km/h
        return result

    @staticmethod
    def toWindspeed_3_1(buf, start, StartOnHiNibble):
        '''read 3 nibbles, presentation with 1 decimal; units of km/h'''
        if StartOnHiNibble :
            hibyte = buf[0][start+0]
            lobyte = (buf[0][start+1] >> 4) & 0xF
        else:
            hibyte = 16*(buf[0][start+0] & 0xF) + ((buf[0][start+1] >> 4) & 0xF)
            lobyte = buf[0][start+1] & 0xF            
        if hibyte == 0xFF and lobyte == 0xE :
            result = CWeatherTraits.WindNP()
        elif hibyte == 0xFF and lobyte == 0xF :
            result = CWeatherTraits.WindOFL()
        else:
            result = USBHardware.toFloat_3_1(buf, start, StartOnHiNibble)
            result = result / 10.0          # km/h
        return result

    @staticmethod
    def readPressureShared(buf, start, StartOnHiNibble):
        return (USBHardware.toPressure_hPa_5_1(buf,start+2,1-StartOnHiNibble),
                USBHardware.toPressure_inHg_5_2(buf,start,StartOnHiNibble))

    @staticmethod
    def toPressure_hPa_5_1(buf, start, StartOnHiNibble):
        '''read 5 nibbles, presentation with 1 decimal; units of hPa (mbar)'''
        if USBHardware.isErr5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.PressureNP()
        elif USBHardware.isOFL5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.PressureOFL()
        elif StartOnHiNibble :
            result = (buf[0][start+0] >> 4)* 1000 \
                + (buf[0][start+0] & 0xF)* 100  \
                + (buf[0][start+1] >>  4)*  10  \
                + (buf[0][start+1] & 0xF)*  1   \
                + (buf[0][start+2] >>  4)*  0.1
        else:
            result = (buf[0][start+0] & 0xF)* 1000 \
                + (buf[0][start+1] >>  4)* 100  \
                + (buf[0][start+1] & 0xF)*  10  \
                + (buf[0][start+2] >>  4)*  1   \
                + (buf[0][start+2] & 0xF)*  0.1
        return result

    @staticmethod
    def toPressure_inHg_5_2(buf, start, StartOnHiNibble):
        '''read 5 nibbles, presentation with 2 decimals; units of inHg'''
        if USBHardware.isErr5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.PressureNP()
        elif USBHardware.isOFL5(buf, start+0, StartOnHiNibble) :
            result = CWeatherTraits.PressureOFL()
        elif StartOnHiNibble :
            result = (buf[0][start+0] >> 4)* 100 \
                + (buf[0][start+0] & 0xF)* 10   \
                + (buf[0][start+1] >>  4)*  1   \
                + (buf[0][start+1] & 0xF)*  0.1 \
                + (buf[0][start+2] >>  4)*  0.01
        else:
            result = (buf[0][start+0] & 0xF)* 100 \
                + (buf[0][start+1] >>  4)* 10   \
                + (buf[0][start+1] & 0xF)*  1   \
                + (buf[0][start+2] >>  4)*  0.1 \
                + (buf[0][start+2] & 0xF)*  0.01
        return result


class CCurrentWeatherData(object):

    def __init__(self):
        self._timestamp = None
        self._checksum = None
        self._PressureRelative_hPa = CWeatherTraits.PressureNP()
        self._PressureRelative_hPaMinMax = CMinMaxMeasurement()
        self._PressureRelative_inHg = CWeatherTraits.PressureNP()
        self._PressureRelative_inHgMinMax = CMinMaxMeasurement()
        self._WindSpeed = CWeatherTraits.WindNP()
        self._WindDirection = EWindDirection.wdERR
        self._WindDirection1 = EWindDirection.wdERR
        self._WindDirection2 = EWindDirection.wdERR
        self._WindDirection3 = EWindDirection.wdERR
        self._WindDirection4 = EWindDirection.wdERR
        self._WindDirection5 = EWindDirection.wdERR
        self._Gust = CWeatherTraits.WindNP()
        self._GustMax = CMinMaxMeasurement()
        self._GustDirection = EWindDirection.wdERR
        self._GustDirection1 = EWindDirection.wdERR
        self._GustDirection2 = EWindDirection.wdERR
        self._GustDirection3 = EWindDirection.wdERR
        self._GustDirection4 = EWindDirection.wdERR
        self._GustDirection5 = EWindDirection.wdERR
        self._Rain1H = CWeatherTraits.RainNP()
        self._Rain1HMax = CMinMaxMeasurement()
        self._Rain24H = CWeatherTraits.RainNP()
        self._Rain24HMax = CMinMaxMeasurement()
        self._RainLastWeek = CWeatherTraits.RainNP()
        self._RainLastWeekMax = CMinMaxMeasurement()
        self._RainLastMonth = CWeatherTraits.RainNP()
        self._RainLastMonthMax = CMinMaxMeasurement()
        self._RainTotal = CWeatherTraits.RainNP()
        self._LastRainReset = None
        self._TempIndoor = CWeatherTraits.TemperatureNP()
        self._TempIndoorMinMax = CMinMaxMeasurement()
        self._TempOutdoor = CWeatherTraits.TemperatureNP()
        self._TempOutdoorMinMax = CMinMaxMeasurement()
        self._HumidityIndoor = CWeatherTraits.HumidityNP()
        self._HumidityIndoorMinMax = CMinMaxMeasurement()
        self._HumidityOutdoor = CWeatherTraits.HumidityNP()
        self._HumidityOutdoorMinMax = CMinMaxMeasurement()
        self._Dewpoint = CWeatherTraits.TemperatureNP()
        self._DewpointMinMax = CMinMaxMeasurement()
        self._Windchill = CWeatherTraits.TemperatureNP()
        self._WindchillMinMax = CMinMaxMeasurement()
        self._WeatherState = EWeatherState.WEATHER_ERR
        self._WeatherTendency = EWeatherTendency.TREND_ERR
        self._AlarmRingingFlags = 0
        self._AlarmMarkedFlags = 0
        self._PresRel_hPa_Max = 0.0
        self._PresRel_inHg_Max = 0.0

    @staticmethod
    def calcChecksum(buf):
        return calc_checksum(buf, 6)

    def checksum(self):
        return self._checksum

    def read(self, buf):
        logdbg('CCurrentWeatherData.read')

        self._timestamp = time.time()
        self._checksum = CCurrentWeatherData.calcChecksum(buf)

        nbuf = [0]
        nbuf[0] = buf[0]
        self._StartBytes = nbuf[0][6]*0xF + nbuf[0][7] # FIXME: what is this?
        self._WeatherTendency = (nbuf[0][8] >> 4) & 0xF
        if self._WeatherTendency > 3:
            self._WeatherTendency = 3 
        self._WeatherState = nbuf[0][8] & 0xF
        if self._WeatherState > 3:
            self._WeatherState = 3 

        self._TempIndoorMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 19, 0)
        self._TempIndoorMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 22, 1)
        self._TempIndoor = USBHardware.toTemperature_5_3(nbuf, 24, 0)
        self._TempIndoorMinMax._Min._IsError = (self._TempIndoorMinMax._Min._Value == CWeatherTraits.TemperatureNP())
        self._TempIndoorMinMax._Min._IsOverflow = (self._TempIndoorMinMax._Min._Value == CWeatherTraits.TemperatureOFL())
        self._TempIndoorMinMax._Max._IsError = (self._TempIndoorMinMax._Max._Value == CWeatherTraits.TemperatureNP())
        self._TempIndoorMinMax._Max._IsOverflow = (self._TempIndoorMinMax._Max._Value == CWeatherTraits.TemperatureOFL())
        self._TempIndoorMinMax._Max._Time = None if self._TempIndoorMinMax._Max._IsError or self._TempIndoorMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 9, 0, 'TempIndoorMax')
        self._TempIndoorMinMax._Min._Time = None if self._TempIndoorMinMax._Min._IsError or self._TempIndoorMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 14, 0, 'TempIndoorMin')

        self._TempOutdoorMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 37, 0)
        self._TempOutdoorMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 40, 1)
        self._TempOutdoor = USBHardware.toTemperature_5_3(nbuf, 42, 0)
        self._TempOutdoorMinMax._Min._IsError = (self._TempOutdoorMinMax._Min._Value == CWeatherTraits.TemperatureNP())
        self._TempOutdoorMinMax._Min._IsOverflow = (self._TempOutdoorMinMax._Min._Value == CWeatherTraits.TemperatureOFL())
        self._TempOutdoorMinMax._Max.IsError = (self._TempOutdoorMinMax._Max._Value == CWeatherTraits.TemperatureNP())
        self._TempOutdoorMinMax._Max.IsOverflow = (self._TempOutdoorMinMax._Max._Value == CWeatherTraits.TemperatureOFL())
        self._TempOutdoorMinMax._Max._Time = None if self._TempOutdoorMinMax._Max._IsError or self._TempOutdoorMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 27, 0, 'TempOutdoorMax')
        self._TempOutdoorMinMax._Min._Time = None if self._TempOutdoorMinMax._Min._IsError or self._TempOutdoorMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 32, 0, 'TempOutdoorMin')

        self._WindchillMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 55, 0)
        self._WindchillMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 58, 1)
        self._Windchill = USBHardware.toTemperature_5_3(nbuf, 60, 0)
        self._WindchillMinMax._Min._IsError = (self._WindchillMinMax._Min._Value == CWeatherTraits.TemperatureNP())
        self._WindchillMinMax._Min._IsOverflow = (self._WindchillMinMax._Min._Value == CWeatherTraits.TemperatureOFL())
        self._WindchillMinMax._Max._IsError = (self._WindchillMinMax._Max._Value == CWeatherTraits.TemperatureNP())
        self._WindchillMinMax._Max._IsOverflow = (self._WindchillMinMax._Max._Value == CWeatherTraits.TemperatureOFL())
        self._WindchillMinMax._Max._Time = None if self._WindchillMinMax._Max._IsError or self._WindchillMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 45, 0, 'WindchillMax')
        self._WindchillMinMax._Min._Time = None if self._WindchillMinMax._Min._IsError or self._WindchillMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 50, 0, 'WindchillMin')

        self._DewpointMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 73, 0)
        self._DewpointMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 76, 1)
        self._Dewpoint = USBHardware.toTemperature_5_3(nbuf, 78, 0)
        self._DewpointMinMax._Min.IsError = (self._DewpointMinMax._Min._Value == CWeatherTraits.TemperatureNP())
        self._DewpointMinMax._Min._IsOverflow = (self._DewpointMinMax._Min._Value == CWeatherTraits.TemperatureOFL())
        self._DewpointMinMax._Max._IsError = (self._DewpointMinMax._Max._Value == CWeatherTraits.TemperatureNP())
        self._DewpointMinMax._Max._IsOverflow = (self._DewpointMinMax._Max._Value == CWeatherTraits.TemperatureOFL())
        self._DewpointMinMax._Min._Time = None if self._DewpointMinMax._Min._IsError or self._DewpointMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 68, 0, 'DewpointMin')
        self._DewpointMinMax._Max._Time = None if self._DewpointMinMax._Max._IsError or self._DewpointMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 63, 0, 'DewpointMax')

        self._HumidityIndoorMinMax._Max._Value = USBHardware.toHumidity_2_0(nbuf, 91, 1)
        self._HumidityIndoorMinMax._Min._Value = USBHardware.toHumidity_2_0(nbuf, 92, 1)
        self._HumidityIndoor = USBHardware.toHumidity_2_0(nbuf, 93, 1)
        self._HumidityIndoorMinMax._Min._IsError = (self._HumidityIndoorMinMax._Min._Value == CWeatherTraits.HumidityNP())
        self._HumidityIndoorMinMax._Min._IsOverflow = (self._HumidityIndoorMinMax._Min._Value == CWeatherTraits.HumidityOFL())
        self._HumidityIndoorMinMax._Max._IsError = (self._HumidityIndoorMinMax._Max._Value == CWeatherTraits.HumidityNP())
        self._HumidityIndoorMinMax._Max._IsOverflow = (self._HumidityIndoorMinMax._Max._Value == CWeatherTraits.HumidityOFL())
        self._HumidityIndoorMinMax._Max._Time = None if self._HumidityIndoorMinMax._Max._IsError or self._HumidityIndoorMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 81, 1, 'HumidityIndoorMax')
        self._HumidityIndoorMinMax._Min._Time = None if self._HumidityIndoorMinMax._Min._IsError or self._HumidityIndoorMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 86, 1, 'HumidityIndoorMin')

        self._HumidityOutdoorMinMax._Max._Value = USBHardware.toHumidity_2_0(nbuf, 104, 1)
        self._HumidityOutdoorMinMax._Min._Value = USBHardware.toHumidity_2_0(nbuf, 105, 1)
        self._HumidityOutdoor = USBHardware.toHumidity_2_0(nbuf, 106, 1)
        self._HumidityOutdoorMinMax._Min._IsError = (self._HumidityOutdoorMinMax._Min._Value == CWeatherTraits.HumidityNP())
        self._HumidityOutdoorMinMax._Min._IsOverflow = (self._HumidityOutdoorMinMax._Min._Value == CWeatherTraits.HumidityOFL())
        self._HumidityOutdoorMinMax._Max._IsError = (self._HumidityOutdoorMinMax._Max._Value == CWeatherTraits.HumidityNP())
        self._HumidityOutdoorMinMax._Max._IsOverflow = (self._HumidityOutdoorMinMax._Max._Value == CWeatherTraits.HumidityOFL())
        self._HumidityOutdoorMinMax._Max._Time = None if self._HumidityOutdoorMinMax._Max._IsError or self._HumidityOutdoorMinMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 94, 1, 'HumidityOutdoorMax')
        self._HumidityOutdoorMinMax._Min._Time = None if self._HumidityOutdoorMinMax._Min._IsError or self._HumidityOutdoorMinMax._Min._IsOverflow else USBHardware.toDateTime(nbuf, 99, 1, 'HumidityOutdoorMin')

        self._RainLastMonthMax._Max._Time = USBHardware.toDateTime(nbuf, 107, 1, 'RainLastMonthMax')
        self._RainLastMonthMax._Max._Value = USBHardware.toRain_6_2(nbuf, 112, 1)
        self._RainLastMonth = USBHardware.toRain_6_2(nbuf, 115, 1)

        self._RainLastWeekMax._Max._Time = USBHardware.toDateTime(nbuf, 118, 1, 'RainLastWeekMax')
        self._RainLastWeekMax._Max._Value = USBHardware.toRain_6_2(nbuf, 123, 1)
        self._RainLastWeek = USBHardware.toRain_6_2(nbuf, 126, 1)

        self._Rain24HMax._Max._Time = USBHardware.toDateTime(nbuf, 129, 1, 'Rain24HMax')
        self._Rain24HMax._Max._Value = USBHardware.toRain_6_2(nbuf, 134, 1)
        self._Rain24H = USBHardware.toRain_6_2(nbuf, 137, 1)
        
        self._Rain1HMax._Max._Time = USBHardware.toDateTime(nbuf, 140, 1, 'Rain1HMax')
        self._Rain1HMax._Max._Value = USBHardware.toRain_6_2(nbuf, 145, 1)
        self._Rain1H = USBHardware.toRain_6_2(nbuf, 148, 1)

        self._LastRainReset = USBHardware.toDateTime(nbuf, 151, 0, 'LastRainReset')
        self._RainTotal = USBHardware.toRain_7_3(nbuf, 156, 0)

        (w ,w1) = USBHardware.readWindDirectionShared(nbuf, 162)
        (w2,w3) = USBHardware.readWindDirectionShared(nbuf, 161)
        (w4,w5) = USBHardware.readWindDirectionShared(nbuf, 160)
        self._WindDirection = w
        self._WindDirection1 = w1
        self._WindDirection2 = w2
        self._WindDirection3 = w3
        self._WindDirection4 = w4
        self._WindDirection5 = w5

        if DEBUG_WEATHER_DATA > 0:
            unknownbuf = [0]
            unknownbuf[0] = [0]*9
            for i in xrange(0,9):
                unknownbuf[0][i] = nbuf[0][163+i]
            strbuf = ""
            for i in unknownbuf[0]:
                strbuf += str("%.2x " % i)
            logdbg('Bytes with unknown meaning at 157-165: %s' % strbuf)

        self._WindSpeed = USBHardware.toWindspeed_6_2(nbuf, 172)

        # FIXME: read the WindErrFlags
        (g ,g1) = USBHardware.readWindDirectionShared(nbuf, 177)
        (g2,g3) = USBHardware.readWindDirectionShared(nbuf, 176)
        (g4,g5) = USBHardware.readWindDirectionShared(nbuf, 175)
        self._GustDirection = g
        self._GustDirection1 = g1
        self._GustDirection2 = g2
        self._GustDirection3 = g3
        self._GustDirection4 = g4
        self._GustDirection5 = g5

        self._GustMax._Max._Value = USBHardware.toWindspeed_6_2(nbuf, 184)
        self._GustMax._Max._IsError = (self._GustMax._Max._Value == CWeatherTraits.WindNP())
        self._GustMax._Max._IsOverflow = (self._GustMax._Max._Value == CWeatherTraits.WindOFL())
        self._GustMax._Max._Time = None if self._GustMax._Max._IsError or self._GustMax._Max._IsOverflow else USBHardware.toDateTime(nbuf, 179, 1, 'GustMax')
        self._Gust = USBHardware.toWindspeed_6_2(nbuf, 187)

        # Apparently the station returns only ONE date time for both hPa/inHg
        # Min Time Reset and Max Time Reset
        self._PressureRelative_hPaMinMax._Max._Time = USBHardware.toDateTime(nbuf, 190, 1, 'PressureRelative_hPaMax')
        self._PressureRelative_inHgMinMax._Max._Time = self._PressureRelative_hPaMinMax._Max._Time
        self._PressureRelative_hPaMinMax._Min._Time  = self._PressureRelative_hPaMinMax._Max._Time # firmware bug, should be: USBHardware.toDateTime(nbuf, 195, 1)
        self._PressureRelative_inHgMinMax._Min._Time = self._PressureRelative_hPaMinMax._Min._Time        

        (self._PresRel_hPa_Max, self._PresRel_inHg_Max) = USBHardware.readPressureShared(nbuf, 195, 1) # firmware bug, should be: self._PressureRelative_hPaMinMax._Min._Time
        (self._PressureRelative_hPaMinMax._Max._Value, self._PressureRelative_inHgMinMax._Max._Value) = USBHardware.readPressureShared(nbuf, 200, 1)
        (self._PressureRelative_hPaMinMax._Min._Value, self._PressureRelative_inHgMinMax._Min._Value) = USBHardware.readPressureShared(nbuf, 205, 1)
        (self._PressureRelative_hPa, self._PressureRelative_inHg) = USBHardware.readPressureShared(nbuf, 210, 1)

        if DEBUG_WEATHER_DATA > 0:
            self.logWeatherData()

    def logWeatherData(self):
        logdbg("_WeatherState=%s _WeatherTendency=%s _AlarmRingingFlags %04x" % (CWeatherTraits.forecastMap[self._WeatherState], CWeatherTraits.trends[self._WeatherTendency], self._AlarmRingingFlags))
        logdbg("_TempIndoor=     %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._TempIndoor, self._TempIndoorMinMax._Min._Value, self._TempIndoorMinMax._Min._Time, self._TempIndoorMinMax._Max._Value, self._TempIndoorMinMax._Max._Time))
        logdbg("_HumidityIndoor= %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._HumidityIndoor, self._HumidityIndoorMinMax._Min._Value, self._HumidityIndoorMinMax._Min._Time, self._HumidityIndoorMinMax._Max._Value, self._HumidityIndoorMinMax._Max._Time))
        logdbg("_TempOutdoor=    %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._TempOutdoor, self._TempOutdoorMinMax._Min._Value, self._TempOutdoorMinMax._Min._Time, self._TempOutdoorMinMax._Max._Value, self._TempOutdoorMinMax._Max._Time))
        logdbg("_HumidityOutdoor=%8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._HumidityOutdoor, self._HumidityOutdoorMinMax._Min._Value, self._HumidityOutdoorMinMax._Min._Time, self._HumidityOutdoorMinMax._Max._Value, self._HumidityOutdoorMinMax._Max._Time))
        logdbg("_Windchill=      %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._Windchill, self._WindchillMinMax._Min._Value, self._WindchillMinMax._Min._Time, self._WindchillMinMax._Max._Value, self._WindchillMinMax._Max._Time))
        logdbg("_Dewpoint=       %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s)" % (self._Dewpoint, self._DewpointMinMax._Min._Value, self._DewpointMinMax._Min._Time, self._DewpointMinMax._Max._Value, self._DewpointMinMax._Max._Time))
        logdbg("_WindSpeed=      %8.3f" % self._WindSpeed)
        logdbg("_Gust=           %8.3f                                      _Max=%8.3f (%s)" % (self._Gust, self._GustMax._Max._Value, self._GustMax._Max._Time))
        logdbg('_WindDirection=    %3s    _GustDirection=    %3s' % (CWeatherTraits.windDirMap[self._WindDirection],  CWeatherTraits.windDirMap[self._GustDirection]))
        logdbg('_WindDirection1=   %3s    _GustDirection1=   %3s' % (CWeatherTraits.windDirMap[self._WindDirection1], CWeatherTraits.windDirMap[self._GustDirection1]))
        logdbg('_WindDirection2=   %3s    _GustDirection2=   %3s' % (CWeatherTraits.windDirMap[self._WindDirection2], CWeatherTraits.windDirMap[self._GustDirection2]))
        logdbg('_WindDirection3=   %3s    _GustDirection3=   %3s' % (CWeatherTraits.windDirMap[self._WindDirection3], CWeatherTraits.windDirMap[self._GustDirection3]))
        logdbg('_WindDirection4=   %3s    _GustDirection4=   %3s' % (CWeatherTraits.windDirMap[self._WindDirection4], CWeatherTraits.windDirMap[self._GustDirection4]))
        logdbg('_WindDirection5=   %3s    _GustDirection5=   %3s' % (CWeatherTraits.windDirMap[self._WindDirection5], CWeatherTraits.windDirMap[self._GustDirection5]))
        if (self._RainLastMonth > 0) or (self._RainLastWeek > 0):
            logdbg("_RainLastMonth=  %8.3f                                      _Max=%8.3f (%s)" % (self._RainLastMonth, self._RainLastMonthMax._Max._Value, self._RainLastMonthMax._Max._Time))
            logdbg("_RainLastWeek=   %8.3f                                      _Max=%8.3f (%s)" % (self._RainLastWeek, self._RainLastWeekMax._Max._Value, self._RainLastWeekMax._Max._Time))
        logdbg("_Rain24H=        %8.3f                                      _Max=%8.3f (%s)" % (self._Rain24H, self._Rain24HMax._Max._Value, self._Rain24HMax._Max._Time))
        logdbg("_Rain1H=         %8.3f                                      _Max=%8.3f (%s)" % (self._Rain1H, self._Rain1HMax._Max._Value, self._Rain1HMax._Max._Time))
        logdbg("_RainTotal=      %8.3f                            _LastRainReset=         (%s)" % (self._RainTotal,  self._LastRainReset))
        logdbg("PressureRel_hPa= %8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s) " % (self._PressureRelative_hPa, self._PressureRelative_hPaMinMax._Min._Value, self._PressureRelative_hPaMinMax._Min._Time, self._PressureRelative_hPaMinMax._Max._Value, self._PressureRelative_hPaMinMax._Max._Time))                       
        logdbg("PressureRel_inHg=%8.3f _Min=%8.3f (%s)  _Max=%8.3f (%s) " % (self._PressureRelative_inHg, self._PressureRelative_inHgMinMax._Min._Value, self._PressureRelative_inHgMinMax._Min._Time, self._PressureRelative_inHgMinMax._Max._Value, self._PressureRelative_inHgMinMax._Max._Time))                       
        ###logdbg('(* Bug in Weather Station: PressureRelative._Min._Time is written to location of _PressureRelative._Max._Time')
        ###logdbg('Instead of PressureRelative._Min._Time we get: _PresRel_hPa_Max= %8.3f, _PresRel_inHg_max =%8.3f;' % (self._PresRel_hPa_Max, self._PresRel_inHg_Max))


class CWeatherStationConfig(object):
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self._InBufCS = 0  # checksum of received config
        self._OutBufCS = 0 # calculated config checksum from outbuf config
        self._DeviceCS = 0 # config checksum received via messages
        self._ClockMode = 0
        self._TemperatureFormat = 0
        self._PressureFormat = 0
        self._RainFormat = 0
        self._WindspeedFormat = 0
        self._WeatherThreshold = 0
        self._StormThreshold = 0
        self._LCDContrast = 0
        self._LowBatFlags = 0
        self._WindDirAlarmFlags = 0
        self._OtherAlarmFlags = 0
        self._ResetMinMaxFlags = 0 # output only
        self._HistoryInterval = 0
        self._TempIndoorMinMax = CMinMaxMeasurement()
        self._TempOutdoorMinMax = CMinMaxMeasurement()
        self._HumidityIndoorMinMax = CMinMaxMeasurement()
        self._HumidityOutdoorMinMax = CMinMaxMeasurement()
        self._Rain24HMax = CMinMaxMeasurement()
        self._GustMax = CMinMaxMeasurement()
        self._PressureRelative_hPaMinMax = CMinMaxMeasurement()
        self._PressureRelative_inHgMinMax = CMinMaxMeasurement()

    def readAlertFlags(self,buf):
        logdbg('readAlertFlags')

    def setTemps(self,TempFormat,InTempLo,InTempHi,OutTempLo,OutTempHi):
        logdbg('setTemps')
        f1 = TempFormat
        t1 = InTempLo
        t2 = InTempHi
        t3 = OutTempLo
        t4 = OutTempHi
        if (f1 == ETemperatureFormat.tfFahrenheit) or (f1 == ETemperatureFormat.tfCelsius):
            if ((t1 >= -40.0) and (t1 <= 59.9) and (t2 >= -40.0) and (t2 <= 59.9) and \
                (t3 >= -40.0) and (t3 <= 59.9) and (t4 >= -40.0) and (t4 <= 59.9)):
                self._TemperatureFormat = f1
            else:
                logerr('setTemps: one or more values out of range')
                return 0
        else:
            logerr('setTemps: unknown temperature format %s' % TempFormat)
            return 0
        self._TempIndoorMinMax._Min._Value = t1
        self._TempIndoorMinMax._Max._Value = t2
        self._TempOutdoorMinMax._Min._Value = t3
        self._TempOutdoorMinMax._Max._Value = t4
        return 1     
    
    def setHums(self,InHumLo,InHumHi,OutHumLo,OutHumHi):
        h1 = InHumLo
        h2 = InHumHi
        h3 = OutHumLo
        h4 = OutHumHi 
        if not ((h1 >= 1) and (h1 <= 99) and (h2 >= 1) and (h2 <= 99) and \
            (h3 >= 1) and (h3 <= 99) and (h4 >= 1) and (h4 <= 99)):
            logerr('setHums: one or more values out of range')
            return 0
        self._HumidityIndoorMinMax._Min._Value = h1
        self._HumidityIndoorMinMax._Max._Value = h2
        self._HumidityOutdoorMinMax._Min._Value = h3
        self._HumidityOutdoorMinMax._Max._Value = h4
        return 1
    
    def setRain24H(self,RainFormat,Rain24hHi):
        f1 = RainFormat
        r1 = Rain24hHi 
        if (f1 == ERainFormat.rfMm) or (f1 == ERainFormat.rfInch):
            if (r1>=0.0) and (r1 <= 9999.9):
                self._RainFormat = f1
            else:
                logerr('setRain24: value outside range')
                return 0
        else:
            logerr('setRain24: unknown format %s' % RainFormat)
            return 0
        self._Rain24HMax._Max._Value = r1
        return 1
    
    def setGust(self,WindSpeedFormat,GustHi):
        logdbg('setGust: not yet implemented')
        if True:
            return 1
        f1 = WindSpeedFormat
        g1 = GustHi
        if (f1 >= EWindspeedFormat.wfMs) and (f1 <= EWindspeedFormat.wfMph):
            if (g1>=0.0) and (g1 <= 180.0):
                self._WindSpeedFormat = f1
            else:
                logerr('setGust: value outside range')
                return 0 
        else:
            logerr('setGust: unknown format %s' % WindSpeedFormat)
            return 0
        self._GustMax._Max._Value = int(g1) # apparently gust value is always an integer
        return 1
    
    def setPresRels(self,PressureFormat,PresRelhPaLo,PresRelhPaHi,PresRelinHgLo,PresRelinHgHi):
        f1 = PressureFormat
        p1 = PresRelhPaLo
        p2 = PresRelhPaHi
        p3 = PresRelinHgLo
        p4 = PresRelinHgHi
        if (f1 == EPressureFormat.pfinHg) or (f1 == EPressureFormat.pfHPa):
            if ((p1>=920.0) and (p1 <= 1080.0) and (p2>=920.0) and (p2 <= 1080.0) and \
                (p3>=27.10) and (p3 <= 31.90) and (p4>=27.10) and (p4 <= 31.90)):
                self._RainFormat = f1
            else:
                logerr('setPresRel: value outside range')
                return 0
        else:
            logerr('setPresRel: unknown format %s' % PressureFormat)
            return 0
        self._PressureRelative_hPaMinMax._Min._Value = p1
        self._PressureRelative_hPaMinMax._Max._Value = p2
        self._PressureRelative_inHgMinMax._Min._Value = p3
        self._PressureRelative_inHgMinMax._Max._Value = p4
        return 1
    
    def getOutBufCS(self):
        return self._OutBufCS
             
    def getInBufCS(self):
        return self._InBufCS
    
    def setDeviceCS(self, deviceCS):
        logdbg('setDeviceCS: %04x' % deviceCS)
        self._DeviceCS = deviceCS
        
    def getDeviceCS(self):
        return self._DeviceCS
    
    def setResetMinMaxFlags(self, resetMinMaxFlags):
        logdbg('setResetMinMaxFlags: %s' % resetMinMaxFlags)
        self._ResetMinMaxFlags = resetMinMaxFlags

    def parseRain_3(self, number, buf, start, StartOnHiNibble, numbytes):
        '''Parse 7-digit number with 3 decimals'''
        num = int(number*1000)
        parsebuf=[0]*7
        for i in xrange(7-numbytes,7):
            parsebuf[i] = num%10
            num = num//10
        if StartOnHiNibble:
                buf[0][0+start] = parsebuf[6]*16 + parsebuf[5]
                buf[0][1+start] = parsebuf[4]*16 + parsebuf[3]
                buf[0][2+start] = parsebuf[2]*16 + parsebuf[1]
                buf[0][3+start] = parsebuf[0]*16 + (buf[0][3+start] & 0xF)
        else:
                buf[0][0+start] = (buf[0][0+start] & 0xF0) + parsebuf[6]
                buf[0][1+start] = parsebuf[5]*16 + parsebuf[4]
                buf[0][2+start] = parsebuf[3]*16 + parsebuf[2]
                buf[0][3+start] = parsebuf[1]*16 + parsebuf[0]
                        
    def parseWind_6(self, number, buf, start):
        '''Parse float number to 6 bytes'''
        num = int(number*100*256)
        parsebuf=[0]*6
        for i in xrange(0,6):
            parsebuf[i] = num%16
            num = num//16
        buf[0][0+start] = parsebuf[5]*16 + parsebuf[4]
        buf[0][1+start] = parsebuf[3]*16 + parsebuf[2]
        buf[0][2+start] = parsebuf[1]*16 + parsebuf[0]
        
    def parse_0(self, number, buf, start, StartOnHiNibble, numbytes):
        '''Parse 5-digit number with 0 decimals'''
        num = int(number)
        nbuf=[0]*5
        for i in xrange(5-numbytes,5):
            nbuf[i] = num%10
            num = num//10
        if StartOnHiNibble:
            buf[0][0+start] = nbuf[4]*16 + nbuf[3]
            buf[0][1+start] = nbuf[2]*16 + nbuf[1]
            buf[0][2+start] = nbuf[0]*16 + (buf[0][2+start] & 0x0F)
        else:
            buf[0][0+start] = (buf[0][0+start] & 0xF0) + nbuf[4]
            buf[0][1+start] = nbuf[3]*16 + nbuf[2]
            buf[0][2+start] = nbuf[1]*16 + nbuf[0]

    def parse_1(self, number, buf, start, StartOnHiNibble, numbytes):
        '''Parse 5 digit number with 1 decimal'''
        self.parse_0(number*10.0, buf, start, StartOnHiNibble, numbytes)
    
    def parse_2(self, number, buf, start, StartOnHiNibble, numbytes):
        '''Parse 5 digit number with 2 decimals'''
        self.parse_0(number*100.0, buf, start, StartOnHiNibble, numbytes)
    
    def parse_3(self, number, buf, start, StartOnHiNibble, numbytes):
        '''Parse 5 digit number with 3 decimals'''
        self.parse_0(number*1000.0, buf, start, StartOnHiNibble, numbytes)

    def write(self):
        if self.cache_file is None:
            return
        config = ConfigObj(self.cache_file)
        config.filename = self.cache_file
        config['Station'] = {}
        config['Station']['DeviceCS'] = str(self._DeviceCS)
        config['Station']['ClockMode'] = str(self._ClockMode)
        config['Station']['TemperatureFormat'] = str(self._TemperatureFormat)
        config['Station']['PressureFormat'] = str(self._PressureFormat)
        config['Station']['RainFormat'] = str(self._RainFormat)
        config['Station']['WindspeedFormat'] = str(self._WindspeedFormat)
        config['Station']['WeatherThreshold'] = str(self._WeatherThreshold)
        config['Station']['StormThreshold'] = str(self._StormThreshold)
        config['Station']['LCDContrast'] = str(self._LCDContrast)
        config['Station']['LowBatFlags'] = str(self._LowBatFlags)
        config['Station']['WindDirAlarmFlags'] = str(self._WindDirAlarmFlags)
        config['Station']['OtherAlarmFlags'] = str(self._OtherAlarmFlags)
        config['Station']['HistoryInterval'] = str(self._HistoryInterval)
        config['Station']['ResetMinMaxFlags'] = str(self._ResetMinMaxFlags)
        config['Station']['TempIndoor_Min'] = str(self._TempIndoorMinMax._Min._Value)
        config['Station']['TempIndoor_Max'] = str(self._TempIndoorMinMax._Max._Value)
        config['Station']['Outdoor_Min'] = str(self._TempOutdoorMinMax._Min._Value)
        config['Station']['TempOutdoorMax'] = str(self._TempOutdoorMinMax._Max._Value)
        config['Station']['HumidityIndoor_Min'] = str(self._HumidityIndoorMinMax._Min._Value)
        config['Station']['HumidityIndoor_Max'] = str(self._HumidityIndoorMinMax._Max._Value)
        config['Station']['HumidityOutdoor_Min'] = str(self._HumidityOutdoorMinMax._Min._Value)
        config['Station']['HumidityOutdoor_Max'] = str(self._HumidityOutdoorMinMax._Max._Value)
        config['Station']['Rain24HMax'] = str(self._Rain24HMax._Max._Value)
        config['Station']['GustMax'] = str(self._GustMax._Max._Value)
        config['Station']['PressureRel_hPa_Min'] = str(self._PressureRelative_hPaMinMax._Min._Value)
        config['Station']['PressureRel_inHg_Min'] = str(self._PressureRelative_inHgMinMax._Min._Value)
        config['Station']['PressureRel_hPa_Max'] = str(self._PressureRelative_hPaMinMax._Max._Value)
        config['Station']['PressureRel_inHg_Max'] = str(self._PressureRelative_inHgMinMax._Max._Value)
        if DEBUG_WRITES > 0:
            logdbg('WeatherStationConfig.write: write to %s' % self.cache_file)
        config.write()
        
    def read(self,buf):
        logdbg('CWeatherStationConfig.read')
        nbuf=[0]
        nbuf[0]=buf[0]
        self._WindspeedFormat = (nbuf[0][4] >> 4) & 0xF  
        self._RainFormat = (nbuf[0][4] >> 3) & 1
        self._PressureFormat = (nbuf[0][4] >> 2) & 1
        self._TemperatureFormat = (nbuf[0][4] >> 1) & 1
        self._ClockMode = nbuf[0][4] & 1
        self._StormThreshold = (nbuf[0][5] >> 4) & 0xF
        self._WeatherThreshold = nbuf[0][5] & 0xF
        self._LowBatFlags = (nbuf[0][6] >> 4) & 0xF
        self._LCDContrast = nbuf[0][6] & 0xF
        self._WindDirAlarmFlags = (nbuf[0][7] << 8) | nbuf[0][8]
        self._OtherAlarmFlags = (nbuf[0][9] << 8) | nbuf[0][10]
        self._TempIndoorMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 11, 1)
        self._TempIndoorMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 13, 0)
        self._TempOutdoorMinMax._Max._Value = USBHardware.toTemperature_5_3(nbuf, 16, 1)
        self._TempOutdoorMinMax._Min._Value = USBHardware.toTemperature_5_3(nbuf, 18, 0)
        self._HumidityIndoorMinMax._Max._Value = USBHardware.toHumidity_2_0(nbuf, 21, 1)
        self._HumidityIndoorMinMax._Min._Value = USBHardware.toHumidity_2_0(nbuf, 22, 1)
        self._HumidityOutdoorMinMax._Max._Value = USBHardware.toHumidity_2_0(nbuf, 23, 1)
        self._HumidityOutdoorMinMax._Min._Value = USBHardware.toHumidity_2_0(nbuf, 24, 1)
        self._Rain24HMax._Max._Value = USBHardware.toRain_7_3(nbuf, 25, 0)
        self._HistoryInterval = nbuf[0][29]
        self._GustMax._Max._Value = USBHardware.toWindspeed_6_2(nbuf, 30)
        (self._PressureRelative_hPaMinMax._Min._Value, self._PressureRelative_inHgMinMax._Min._Value) = USBHardware.readPressureShared(nbuf, 33, 1)
        (self._PressureRelative_hPaMinMax._Max._Value, self._PressureRelative_inHgMinMax._Max._Value) = USBHardware.readPressureShared(nbuf, 38, 1)
        self._ResetMinMaxFlags = (nbuf[0][43]) <<16 | (nbuf[0][44] << 8) | (nbuf[0][45])
        self._InBufCS = (nbuf[0][46] << 8) | nbuf[0][47]
        self._OutBufCS = calc_checksum(buf, 4, end=39) + 7
        if DEBUG_CONFIG_DATA > 0:
            self.logConfigData()
        self.write()

        ###self._ResetMinMaxFlags = 0x000000
        ###logdbg('set _ResetMinMaxFlags to %06x' % self._ResetMinMaxFlags)
        """
        #Reset DewpointMax    80 00 00
        #Reset DewpointMin    40 00 00 
        #not used             20 00 00 
        #Reset WindchillMin*  10 00 00  *Reset dateTime only; Min._Value is preserved
                
        #Reset TempOutMax     08 00 00
        #Reset TempOutMin     04 00 00
        #Reset TempInMax      02 00 00
        #Reset TempInMin      01 00 00 
         
        #Reset Gust           00 80 00
        #not used             00 40 00
        #not used             00 20 00
        #not used             00 10 00 
         
        #Reset HumOutMax      00 08 00
        #Reset HumOutMin      00 04 00 
        #Reset HumInMax       00 02 00 
        #Reset HumInMin       00 01 00 
          
        #not used             00 00 80
        #Reset Rain Total     00 00 40
        #Reset last month?    00 00 20
        #Reset last week?     00 00 10 
         
        #Reset Rain24H        00 00 08
        #Reset Rain1H         00 00 04 
        #Reset PresRelMax     00 00 02 
        #Reset PresRelMin     00 00 01                 
        """

        ###logdbg('Preset Config data')
        """
        setTemps(self,TempFormat,InTempLo,InTempHi,OutTempLo,OutTempHi) 
        setHums(self,InHumLo,InHumHi,OutHumLo,OutHumHi)
        setPresRels(self,PressureFormat,PresRelhPaLo,PresRelhPaHi,PresRelinHgLo,PresRelinHgHi)  
        setGust(self,WindSpeedFormat,GustHi) # (not yet implemented)
        setRain24H(self,RainFormat,Rain24hHi)
        """
        # Examples:
        ###self.setTemps(ETemperatureFormat.tfCelsius,1.0,41.0,2.0,42.0) 
        ###self.setHums(41,71,42,72)
        ###self.setPresRels(EPressureFormat.pfHPa,960.1,1040.1,28.36,30.72)
        ###self.setGust(EWindspeedFormat.wfMph,008.0) # setGust not yet implemented
        ##self.setRain24H(ERainFormat.rfMm,50.0)        

        # Preset historyInterval to 1 minute (default: 2 hours)
        self._HistoryInterval = EHistoryInterval.hi60Min
        # Clear all alarm flags, otherwise the datastream from the weather
        # station will pause during an alarm and connection will be lost.
        ###self._WindDirAlarmFlags = 0x0000
        ###self._OtherAlarmFlags   = 0x0000
        return 1
    
    def testConfigChanged(self,buf):
        nbuf = [0]
        nbuf[0] = buf[0]
        nbuf[0][0] = 16*(self._WindspeedFormat & 0xF) + 8*(self._RainFormat & 1) + 4*(self._PressureFormat & 1) + 2*(self._TemperatureFormat & 1) + (self._ClockMode & 1)
        nbuf[0][1] = self._WeatherThreshold & 0xF | 16 * self._StormThreshold & 0xF0
        nbuf[0][2] = self._LCDContrast & 0xF | 16 * self._LowBatFlags & 0xF0
        nbuf[0][3] = (self._OtherAlarmFlags >> 0) & 0xFF
        nbuf[0][4] = (self._OtherAlarmFlags >> 8) & 0xFF
        nbuf[0][5] = (self._WindDirAlarmFlags >> 0) & 0xFF
        nbuf[0][6] = (self._WindDirAlarmFlags >> 8) & 0xFF
        # reverse buf from here
        self.parse_2(self._PressureRelative_inHgMinMax._Max._Value, nbuf, 7, 1, 5)
        self.parse_1(self._PressureRelative_hPaMinMax._Max._Value, nbuf, 9, 0, 5)
        self.parse_2(self._PressureRelative_inHgMinMax._Min._Value, nbuf, 12, 1, 5)
        self.parse_1(self._PressureRelative_hPaMinMax._Min._Value, nbuf, 14, 0, 5)
        self.parseWind_6(self._GustMax._Max._Value, nbuf, 17)
        nbuf[0][20] = self._HistoryInterval & 0xF
        self.parseRain_3(self._Rain24HMax._Max._Value, nbuf, 21, 0, 7)
        self.parse_0(self._HumidityOutdoorMinMax._Max._Value, nbuf, 25, 1, 2)
        self.parse_0(self._HumidityOutdoorMinMax._Min._Value, nbuf, 26, 1, 2)
        self.parse_0(self._HumidityIndoorMinMax._Max._Value, nbuf, 27, 1, 2)
        self.parse_0(self._HumidityIndoorMinMax._Min._Value, nbuf, 28, 1, 2)
        self.parse_3(self._TempOutdoorMinMax._Max._Value + CWeatherTraits.TemperatureOffset(), nbuf, 29, 1, 5)
        self.parse_3(self._TempOutdoorMinMax._Min._Value + CWeatherTraits.TemperatureOffset(), nbuf, 31, 0, 5)
        self.parse_3(self._TempIndoorMinMax._Max._Value + CWeatherTraits.TemperatureOffset(), nbuf, 34, 1, 5)
        self.parse_3(self._TempIndoorMinMax._Min._Value + CWeatherTraits.TemperatureOffset(), nbuf, 36, 0, 5)
        # reverse buf to here
        USBHardware.reverseByteOrder(nbuf, 7, 32)
        # do not include the ResetMinMaxFlags bytes when calculating checksum
        nbuf[0][39] = (self._ResetMinMaxFlags >> 16) & 0xFF
        nbuf[0][40] = (self._ResetMinMaxFlags >>  8) & 0xFF
        nbuf[0][41] = (self._ResetMinMaxFlags >>  0) & 0xFF
        self._OutBufCS = calc_checksum(nbuf, 0, end=39) + 7
        nbuf[0][42] = (self._OutBufCS >> 8) & 0xFF
        nbuf[0][43] = (self._OutBufCS >> 0) & 0xFF
        buf[0] = nbuf[0]   
        if (self._OutBufCS == self._InBufCS) and (self._ResetMinMaxFlags  == 0):
            logdbg('testConfigChanged: checksum not changed: OutBufCS=%04x' % self._OutBufCS)
            State = 0
        else:
            logdbg('testConfigChanged: checksum or resetMinMaxFlags changed: OutBufCS=%04x InBufCS=%04x _ResetMinMaxFlags=%06x' % (self._OutBufCS, self._InBufCS, self._ResetMinMaxFlags))
            if DEBUG_CONFIG_DATA > 1:
                self.logConfigData()
            self.write()
            State = 1
        return State

    def logConfigData(self):
        logdbg('OutBufCS=             %04x' % self._OutBufCS)
        logdbg('InBufCS=              %04x' % self._InBufCS)
        logdbg('DeviceCS=             %04x' % self._DeviceCS)
        logdbg('ClockMode=            %s' % self._ClockMode)
        logdbg('TemperatureFormat=    %s' % self._TemperatureFormat)
        logdbg('PressureFormat=       %s' % self._PressureFormat)
        logdbg('RainFormat=           %s' % self._RainFormat)
        logdbg('WindspeedFormat=      %s' % self._WindspeedFormat)
        logdbg('WeatherThreshold=     %s' % self._WeatherThreshold)
        logdbg('StormThreshold=       %s' % self._StormThreshold)
        logdbg('LCDContrast=          %s' % self._LCDContrast)
        logdbg('LowBatFlags=          %01x' % self._LowBatFlags)
        logdbg('WindDirAlarmFlags=    %04x' % self._WindDirAlarmFlags)
        logdbg('OtherAlarmFlags=      %04x' % self._OtherAlarmFlags)
        logdbg('HistoryInterval=      %s' % self._HistoryInterval)
        logdbg('TempIndoor_Min=       %s' % self._TempIndoorMinMax._Min._Value)
        logdbg('TempIndoor_Max=       %s' % self._TempIndoorMinMax._Max._Value)
        logdbg('TempOutdoor_Min=      %s' % self._TempOutdoorMinMax._Min._Value)
        logdbg('TempOutdoor_Max=      %s' % self._TempOutdoorMinMax._Max._Value)
        logdbg('HumidityIndoor_Min=   %s' % self._HumidityIndoorMinMax._Min._Value)
        logdbg('HumidityIndoor_Max=   %s' % self._HumidityIndoorMinMax._Max._Value)
        logdbg('HumidityOutdoor_Min=  %s' % self._HumidityOutdoorMinMax._Min._Value)
        logdbg('HumidityOutdoor_Max=  %s' % self._HumidityOutdoorMinMax._Max._Value)
        logdbg('Rain24HMax=           %s' % self._Rain24HMax._Max._Value)
        logdbg('GustMax=              %s' % self._GustMax._Max._Value)
        logdbg('PressureRel_hPa_Min=  %s' % self._PressureRelative_hPaMinMax._Min._Value)
        logdbg('PressureRel_inHg_Min= %s' % self._PressureRelative_inHgMinMax._Min._Value)
        logdbg('PressureRel_hPa_Max=  %s' % self._PressureRelative_hPaMinMax._Max._Value)
        logdbg('PressureRel_inHg_Max= %s' % self._PressureRelative_inHgMinMax._Max._Value) 
        logdbg('ResetMinMaxFlags=     %06x (Output only)' % self._ResetMinMaxFlags) 


class CHistoryDataSet(object):

    def __init__(self):
        self.Time = None
        self.TempIndoor = CWeatherTraits.TemperatureNP()
        self.HumidityIndoor = CWeatherTraits.HumidityNP()
        self.TempOutdoor = CWeatherTraits.TemperatureNP()
        self.HumidityOutdoor = CWeatherTraits.HumidityNP()
        self.PressureRelative = None
        self.WindDirection = EWindDirection.wdERR #16
        self.RainCounterRaw = 0
        self.WindSpeed = CWeatherTraits.WindNP()
        self.Gust = CWeatherTraits.WindNP()

    def read(self, buf):
        logdbg('CHistoryDataSet.read')

        nbuf = [0]
        nbuf[0] = buf[0]
        self.Gust = USBHardware.toWindspeed_3_1(nbuf, 12, 0)
        # FIXME: what about gust direction?
        self.WindDirection = (nbuf[0][14] >> 4) & 0xF
        self.WindSpeed = USBHardware.toWindspeed_3_1(nbuf, 14, 0)
        if (self.WindSpeed == CWeatherTraits.WindNP() or self.WindSpeed == 0):
            self.WindDirection = None
        if (self.WindDirection < 0 and self.WindDirection > 16):
            self.WindDirection = 16 
        self.RainCounterRaw = USBHardware.toRain_3_1(nbuf, 16, 1)
        self.HumidityOutdoor = USBHardware.toHumidity_2_0(nbuf, 17, 0)
        self.HumidityIndoor = USBHardware.toHumidity_2_0(nbuf, 18, 0)    
        self.PressureRelative = USBHardware.toPressure_hPa_5_1(nbuf, 19, 0)
        self.TempIndoor = USBHardware.toTemperature_3_1(nbuf, 23, 0)
        self.TempOutdoor = USBHardware.toTemperature_3_1(nbuf, 22, 1)
        self.Time = USBHardware.toDateTime(nbuf, 25, 1, 'HistoryDataSet')
        if DEBUG_HISTORY_DATA > 0:
            self.logHistoryData()

    def logHistoryData(self):
        logdbg("Time              %s"    % self.Time)
        logdbg("TempIndoor=       %7.1f" % self.TempIndoor)
        logdbg("HumidityIndoor=   %7.0f" % self.HumidityIndoor)
        logdbg("TempOutdoor=      %7.1f" % self.TempOutdoor)
        logdbg("HumidityOutdoor=  %7.0f" % self.HumidityOutdoor)
        logdbg("PressureRelative= %7.1f" % self.PressureRelative)
        logdbg("RainCounterRaw=   %7.1f" % self.RainCounterRaw)
        logdbg("WindDirection=    %s" % CWeatherTraits.windDirMap[self.WindDirection])
        logdbg("WindSpeed=        %7.1f" % self.WindSpeed)
        logdbg("Gust=             %7.1f" % self.Gust)


class CDataStore(object):

    class TTransceiverSettings(object): 
        def __init__(self):
            self.VendorId       = 0x6666
            self.ProductId      = 0x5555
            self.VersionNo      = 1
            self.manufacturer   = "LA CROSSE TECHNOLOGY"
            self.product        = "Weather Direct Light Wireless Device"
            self.FrequencyStandard = EFrequency.fsUS
            self.Frequency      = getFrequency(self.FrequencyStandard)
            self.SerialNumber   = None
            self.DeviceID       = None

    class TRequest(object):
        def __init__(self):
            self.Type = ERequestType.rtINVALID
            self.State = ERequestState.rsError
            self.TTL = 90000
            self.Lock = threading.Lock()
            self.CondFinish = threading.Condition()

    class TLastStat(object):
        def __init__(self, cache_file):
            self.LastBatteryStatus = None
            self.LastLinkQuality = None
            self.OutstandingHistorySets = -1
            self.LastCurrentWeatherTime = datetime(1900, 01, 01, 00, 00)
            self.LastHistoryDataTime = datetime(1900, 01, 01, 00, 00)
            self.LastConfigTime = datetime(1900, 01, 01, 00, 00)
            self.LastSeen = None
            self.LastHistoryIndex = 0xffff

    class TSettings(object):
        def __init__(self):
            self.CommModeInterval = 3
            self.PreambleDuration = 5000
            self.RegisterWaitTime = 20000
            self.DeviceID = None

    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.BufferCheck = 0
        self.transceiverPresent = False

        self.Request = CDataStore.TRequest()
        self.LastStat = CDataStore.TLastStat(self.cache_file)
        self.Settings = CDataStore.TSettings()
        self.TransceiverSettings = CDataStore.TTransceiverSettings()
        self.DeviceConfig = CWeatherStationConfig(self.cache_file)
        self.HistoryData = CHistoryDataSet()
        self.CurrentWeather = CCurrentWeatherData()

    def writeLastStat(self):
        if self.cache_file is None:
            return
        config = ConfigObj(self.cache_file)
        config.filename = self.cache_file
        config['LastStat'] = {}
        config['LastStat']['LastSeen'] = str(self.LastStat.LastSeen)
        config['LastStat']['LinkQuality'] = str(self.LastStat.LastLinkQuality)
        config['LastStat']['BatteryStatus'] = str(self.LastStat.LastBatteryStatus)
        config['LastStat']['HistoryIndex'] = str(self.LastStat.LastHistoryIndex)
        config['LastStat']['CurrentWeatherTime'] = str(self.LastStat.LastCurrentWeatherTime)
        config['LastStat']['HistoryDataTime'] = str(self.LastStat.LastHistoryDataTime)
        config['LastStat']['ConfigTime'] = str(self.LastStat.LastConfigTime)
        if DEBUG_WRITES > 0:
            logdbg('writeLastStat: write to %s' % self.cache_file)
        config.write()

    def writeTransceiverSettings(self):
        if self.cache_file is None:
            return
        config = ConfigObj(self.cache_file)
        config.filename = self.cache_file
        config['TransceiverSettings'] = {}
        config['TransceiverSettings']['SerialNumber'] = self.TransceiverSettings.SerialNumber
        config['TransceiverSettings']['DeviceID'] = self.TransceiverSettings.DeviceID
        config['TransceiverSettings']['FrequencyStandard'] = self.TransceiverSettings.FrequencyStandard
        if DEBUG_WRITES > 0:
            logdbg('writeTransceiverSettings: write to %s' % self.cache_file)
        config.write()

    def getFrequencyStandard(self):
        return self.TransceiverSettings.FrequencyStandard

    def setFrequencyStandard(self, val):
        logdbg('setFrequency: %s' % val)
        self.TransceiverSettings.FrequencyStandard = val
        self.TransceiverSettings.Frequency = getFrequency(val)
        self.writeTransceiverSettings()

    def getDeviceID(self):
        return self.TransceiverSettings.DeviceID

    def setDeviceID(self,val):
        logdbg("setDeviceID: %x" % val)
        self.TransceiverSettings.DeviceID = val
        self.writeTransceiverSettings()

    def getRegisteredDeviceID(self):
        return self.Settings.DeviceID

    def setRegisteredDeviceID(self, val):
        if val != self.Settings.DeviceID:
            loginf("console is paired to device with ID %x" % val)
        self.Settings.DeviceID = val

    def getFastCurrentWeather(self):
        return False

    def getTransceiverPresent(self):
        return self.transceiverPresent

    def setTransceiverPresent(self, val):
        self.transceiverPresent = val

    def setLastStatCache(self, seen=None,
                         quality=None, battery=None,
                         currentWeatherTime=None):
        logdbg('setLastStatCache: seen=%s quality=%s battery=%s cwt=%s' %
               (seen, quality, battery, currentWeatherTime))
        if seen is not None:
            self.LastStat.LastSeen = seen
        if quality is not None:
            self.LastStat.LastLinkQuality = quality
        if battery is not None:
            self.LastStat.LastBatteryStatus = battery
        if currentWeatherTime is not None:
            self.LastStat.LastCurrentWeatherTime = currentWeatherTime
        self.writeLastStat()

    def setLastLinkQuality(self, val):
        logdbg("setLastLinkQuality: quality=%d" % val)
        self.LastStat.LastLinkQuality = val
        self.writeLastStat()

    def setLastSeen(self, val):
        logdbg("setLastSeen: time=%s" % val)
        self.LastStat.LastSeen = val
        self.writeLastStat()

    def getLastSeen(self):
        return self.LastStat.LastSeen

    def setLastBatteryStatus(self, status):
        # HWPro presents as WS/TH/RAIN/WIND
        # 0 - wind
        # 1 - rain
        # 2 - thermo-hygro
        # 3 - console
        logdbg('setLastBatteryStatus: WS=%d WIND=%d RAIN=%d TH=%d' %
               (BitHandling.testBit(status,3),
                BitHandling.testBit(status,0),
                BitHandling.testBit(status,1),
                BitHandling.testBit(status,2)))
        self.LastStat.LastBatteryStatus = status
        self.writeLastStat()

    def setCurrentWeather(self, data):
        logdbg('setCurrentWeather')
        self.CurrentWeather = data

    def setHistoryData(self, data):
        logdbg('setHistoryData')
        self.HistoryData = data

    def getHistoryData(self,clear):
        logdbg('getHistoryData')
        self.Request.Lock.acquire()
        History = copy.copy(self.HistoryData)
        self.Request.Lock.release()
        return History

    def setLastCurrentWeatherTime(self, val):
        logdbg("setLastCurrentWeatherTime to %s" % val)
        self.LastStat.LastCurrentWeatherTime = val
        self.writeLastStat()

    def setLastHistoryDataTime(self, val):
        logdbg("setLastHistoryDataTime to %s" % val)
        self.LastStat.LastHistoryDataTime = val
        self.writeLastStat()

    def setLastConfigTime(self, val):
        logdbg("setLastConfigTime to %s" % val)
        self.LastStat.LastConfigTime = val
        self.writeLastStat()

    def getBufferCheck(self):
        return self.BufferCheck

    def setBufferCheck(self, val):
        logdbg("setBufferCheck to %x" % val)
        self.BufferCheck = val

    def getDeviceRegistered(self):
        if ( self.Settings.DeviceID is None
             or self.TransceiverSettings.DeviceID is None
             or self.Settings.DeviceID != self.TransceiverSettings.DeviceID ):
            return False
        return True

    def getRequestType(self):
        return self.Request.Type

    def setRequestType(self, val):
        logdbg('setRequestType to %s' % val)
        self.Request.Type = val

    def getRequestState(self):
        return self.Request.State

    def setRequestState(self,state):
        logdbg("setRequestState to %x" % state)
        self.Request.State = state

    def getPreambleDuration(self):
        return self.Settings.PreambleDuration

    def getRegisterWaitTime(self):
        return self.Settings.RegisterWaitTime

    def getCommModeInterval(self):
        return self.Settings.CommModeInterval

    def setCommModeInterval(self,val):
        logdbg("setCommModeInterval to %x" % val)
        self.Settings.CommModeInterval = val

    def setOutstandingHistorySets(self,val):
        logdbg("setOutstandingHistorySets to %d" % val)
        self.LastStat.OutstandingHistorySets = val

    def setTransceiverSerNo(self,val):
        logdbg("setTransceiverSerialNumber to %s" % val)
        self.TransceiverSettings.SerialNumber = val
        self.writeTransceiverSettings()

    def getTransceiverSerNo(self):
        return self.TransceiverSettings.SerialNumber

    def setLastHistoryIndex(self,val):
        logdbg("setLastHistoryIndex to %i (0x%x)" % (val, val))
        self.LastStat.LastHistoryIndex = val
        self.writeLastStat()

    def getLastHistoryIndex(self):
        return self.LastStat.LastHistoryIndex

    def getCurrentWeather(self, data, timeout):
        logdbg('getCurrentWeather: timeout=%s' % timeout)
        if not self.getTransceiverPresent():
            logerr('getCurrentWeather: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('getCurrentWeather: transceiver is not paired')
            return

        self.Request.Type = ERequestType.rtGetCurrent
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

        try:
            self.Request.CondFinish.acquire()
        except Exception:
            pass

        if self.Request.CondFinish.wait(timedelta(milliseconds=timeout).seconds):
            # FIXME: implement getCurrentWeather
            #CDataStore::getCurrentWeather(thisa, Weather);
            pass
        else:
            pass
        self.Request.Type = ERequestType.rtINVALID
        self.Request.State = ERequestState.rsINVALID
        
        self.Request.CondFinish.release()

    def getHistory(self, data, timeout):
        logdbg('getHistory: timeout=%s' % timeout)
        if not self.getTransceiverPresent():
            logerr('getHistory: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('getHistory: transceiver is not paired')
            return

# FIXME: temporarily ignore history, replace with get current
#        self.Request.Type = ERequestType.rtGetHistory
        self.Request.Type = ERequestType.rtGetCurrent
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

        try:
            self.Request.CondFinish.acquire()
        except Exception:
            pass
        if self.Request.CondFinish.wait(timedelta(milliseconds=timeout).seconds):
            # FIXME: implement getHistory
            #CDataStore::getHistoryData(thisa, History, 1);
            pass
        else:
            pass
        self.Request.Type = ERequestType.rtINVALID
        self.Request.State = ERequestState.rsINVALID

        self.Request.CondFinish.release()

    def getConfig(self):
        logdbg('getConfig')
        if not self.getTransceiverPresent():
            logerr('getConfig: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('getConfig: transceiver is not paired')
            return

        # FIXME: implement getConfig

        self.Request.Type = ERequestType.rtGetConfig
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

    def setConfig(self):
        logdbg('setConfig')
        if not self.getTransceiverPresent():
            logerr('setConfig: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('setConfig: transceiver is not paired')
            return

        self.Request.Type = ERequestType.rtSetConfig
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000

    def setTime(self):
        logdbg('setTime')
        if not self.getTransceiverPresent():
            logerr('setTime: no transceiver')
            return
        if not self.getDeviceRegistered():
            logerr('setTime: transceiver is not paired')
            return

        # FIXME: implement setTime

        self.Request.Type = ERequestType.rtSetTime
        self.Request.State = ERequestState.rsQueued
        self.Request.TTL = 90000


class sHID(object):
    """USB driver abstraction"""

    def __init__(self):
        self.devh = None
        self.timeout = 1000
        self.last_dump = None

    def open(self, vid, pid, did):
        device = self._find_device(vid, pid, did)
        if device is None:
            logcrt('Cannot find USB device with Vendor=0x%04x ProdID=0x%04x Device=%s' % (vid, pid, did))
            raise weewx.WeeWxIOError('Unable to find USB device')
        self._open_device(device)

    def close(self):
        self._close_device()

    def _find_device(self, vid, pid, did):
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vid and dev.idProduct == pid:
                    if did is None or dev.filename == did:
                        loginf('found transceiver on USB bus=%s device=%s' % (bus.dirname, dev.filename))
                        return dev
        return None

    def _open_device(self, device, interface=0, configuration=1):
        self._device = device
        self._configuration = device.configurations[0]
        self._interface = self._configuration.interfaces[0][0]
        self._endpoint = self._interface.endpoints[0]
        self.devh = device.open()
        loginf('manufacturer: %s' % self.devh.getString(device.iManufacturer,30))
        loginf('product: %s' % self.devh.getString(device.iProduct,30))
        loginf('interface: %d' % self._interface.interfaceNumber)

        # detach any old claimed interfaces
        try:
            self.devh.detachKernelDriver(self._interface.interfaceNumber)
        except Exception:
            pass

        # FIXME: this seems to be specific to ws28xx?
        usbWait = 0.05
        self.devh.getDescriptor(0x1, 0, 0x12)
        time.sleep(usbWait)
        self.devh.getDescriptor(0x2, 0, 0x9)
        time.sleep(usbWait)
        self.devh.getDescriptor(0x2, 0, 0x22)
        time.sleep(usbWait)

        # attempt to claim the interface
        try:
            if platform.system() is 'Windows':
                loginf('set USB device configuration to %d' % configuration)
                self.devh.setConfiguration(configuration)
            logdbg('claiming USB interface %d' % interface)
            self.devh.claimInterface(interface)
            self.devh.setAltInterface(interface)
        except usb.USBError, e:
            self._close_device()
            raise weewx.WeeWxIOError(e)

        # FIXME: this seems to be specific to ws28xx?
        # FIXME: check return value
        self.devh.controlMsg(
            usb.TYPE_CLASS + usb.RECIP_INTERFACE,
            0x000000a, [], 0x0000000, 0x0000000, 1000)
        time.sleep(0.05)
        self.devh.getDescriptor(0x22, 0, 0x2a9)
        time.sleep(usbWait)

    def _close_device(self):
        try:
            logdbg('release USB interface')
            self.devh.releaseInterface()
        except Exception:
            pass
        try:
            logdbg('detach kernel driver')
            self.devh.detachKernelDriver(self._interface.interfaceNumber)
        except Exception:
            pass

    def setTX(self):
        buf = [0]*0x15
        buf[0] = 0xD1
        if DEBUG_COMM > 0:
            self.dump('setTX', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d1,
                             index=0x0000000,
                             timeout=self.timeout)

    def setRX(self):
        buf = [0]*0x15
        buf[0] = 0xD0
        if DEBUG_COMM > 0:
            self.dump('setRX', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d0,
                             index=0x0000000,
                             timeout=self.timeout)

    def getState(self,StateBuffer):
        buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                   usb.RECIP_INTERFACE | usb.ENDPOINT_IN,
                                   request=usb.REQ_CLEAR_FEATURE,
                                   buffer=0x0a,
                                   value=0x00003de,
                                   index=0x0000000,
                                   timeout=self.timeout)
        if DEBUG_COMM > 0:
            self.dump('getState', buf, fmt=DEBUG_DUMP_FORMAT)
        StateBuffer[0]=[0]*0x2
        StateBuffer[0][0]=buf[1]
        StateBuffer[0][1]=buf[2]

    def readConfigFlash(self,addr,numBytes,data):
        if numBytes > 512:
            raise Exception('bad number of bytes')

        while numBytes:
            buf=[0xcc]*0x0f #0x15
            buf[0] = 0xdd
            buf[1] = 0x0a
            buf[2] = (addr >>8)  & 0xFF
            buf[3] = (addr >>0)  & 0xFF
            if DEBUG_COMM > 0:
                self.dump('readCfgFlash>', buf, fmt=DEBUG_DUMP_FORMAT)
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                                 request=0x0000009,
                                 buffer=buf,
                                 value=0x00003dd,
                                 index=0x0000000,
                                 timeout=self.timeout)
            buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                       usb.RECIP_INTERFACE |
                                       usb.ENDPOINT_IN,
                                       request=usb.REQ_CLEAR_FEATURE,
                                       buffer=0x15,
                                       value=0x00003dc,
                                       index=0x0000000,
                                       timeout=self.timeout)
            new_data=[0]*0x15
            if ( numBytes < 16 ):
                for i in xrange(0, numBytes):
                    new_data[i] = buf[i+4]
                numBytes = 0
            else:
                for i in xrange(0, 16):
                    new_data[i] = buf[i+4]
                numBytes -= 16
                addr += 16
            if DEBUG_COMM > 0:
                self.dump('readCfgFlash<', buf, fmt=DEBUG_DUMP_FORMAT)
        data[0] = new_data

    def setState(self,state):
        buf = [0]*0x15
        buf[0] = 0xd7
        buf[1] = state
        if DEBUG_COMM > 0:
            self.dump('setState', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d7,
                             index=0x0000000,
                             timeout=self.timeout)

    def setFrame(self,data,numBytes):
        buf = [0]*0x111
        buf[0] = 0xd5
        buf[1] = numBytes >> 8
        buf[2] = numBytes
        for i in xrange(0, numBytes):
            buf[i+3] = data[i]
        if DEBUG_COMM > 0:
            self.dump('setFrame', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d5,
                             index=0x0000000,
                             timeout=self.timeout)

    def getFrame(self,data,numBytes):
        buf = self.devh.controlMsg(requestType=usb.TYPE_CLASS |
                                   usb.RECIP_INTERFACE |
                                   usb.ENDPOINT_IN,
                                   request=usb.REQ_CLEAR_FEATURE,
                                   buffer=0x111,
                                   value=0x00003d6,
                                   index=0x0000000,
                                   timeout=self.timeout)
        new_data=[0]*0x131
        new_numBytes=(buf[1] << 8 | buf[2])& 0x1ff
        for i in xrange(0, new_numBytes):
            new_data[i] = buf[i+3]
        if DEBUG_COMM > 0:
            self.dump('getFrame', buf, fmt=DEBUG_DUMP_FORMAT)
        data[0] = new_data
        numBytes[0] = new_numBytes

    def writeReg(self,regAddr,data):
        buf = [0]*0x05
        buf[0] = 0xf0
        buf[1] = regAddr & 0x7F
        buf[2] = 0x01
        buf[3] = data
        buf[4] = 0x00
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003f0,
                             index=0x0000000,
                             timeout=self.timeout)

    def execute(self,command):
        buf = [0]*0x0f #*0x15
        buf[0] = 0xd9
        buf[1] = command
        if DEBUG_COMM > 0:
            self.dump('execute', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d9,
                             index=0x0000000,
                             timeout=self.timeout)

    def setPreamblePattern(self,pattern):
        buf = [0]*0x15
        buf[0] = 0xd8
        buf[1] = pattern
        if DEBUG_COMM > 0:
            self.dump('setPreamPattern', buf, fmt=DEBUG_DUMP_FORMAT)
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,
                             request=0x0000009,
                             buffer=buf,
                             value=0x00003d8,
                             index=0x0000000,
                             timeout=self.timeout)

    # two formats, long and short.  short shows only the first 16 bytes.
    def dump(self, cmd, buf, fmt='short'):
        strbuf = ''
        for i,x in enumerate(buf):
            strbuf += str('%02x ' % x)
            if (i+1) % 16 == 0:
                self.dumpstr(cmd, strbuf)
                strbuf = ''
            if fmt == 'short' and i+1 >= 16:
                break
        if strbuf:
            self.dumpstr(cmd, strbuf)

    # filter output that we do not care about, pad the command string.
    def dumpstr(self, cmd, strbuf):
        pad = ' ' * (15-len(cmd))
        # de15 is idle, de14 is intermediate
        if strbuf in ['de 15 00 00 00 00 ','de 14 00 00 00 00 ']:
            if strbuf != self.last_dump or DEBUG_COMM > 1:
                logdbg('%s: %s%s' % (cmd, pad, strbuf))
            self.last_dump = strbuf
        else:
            logdbg('%s: %s%s' % (cmd, pad, strbuf))
            self.last_dump = None

class CCommunicationService(object):

    reg_names = dict()

    class AX5051RegisterNames:
        REVISION         = 0x0
        SCRATCH          = 0x1
        POWERMODE        = 0x2
        XTALOSC          = 0x3
        FIFOCTRL         = 0x4
        FIFODATA         = 0x5
        IRQMASK          = 0x6
        IFMODE           = 0x8
        PINCFG1          = 0x0C
        PINCFG2          = 0x0D
        MODULATION       = 0x10
        ENCODING         = 0x11
        FRAMING          = 0x12
        CRCINIT3         = 0x14
        CRCINIT2         = 0x15
        CRCINIT1         = 0x16
        CRCINIT0         = 0x17
        FREQ3            = 0x20
        FREQ2            = 0x21
        FREQ1            = 0x22
        FREQ0            = 0x23
        FSKDEV2          = 0x25
        FSKDEV1          = 0x26
        FSKDEV0          = 0x27
        IFFREQHI         = 0x28
        IFFREQLO         = 0x29
        PLLLOOP          = 0x2C
        PLLRANGING       = 0x2D
        PLLRNGCLK        = 0x2E
        TXPWR            = 0x30
        TXRATEHI         = 0x31
        TXRATEMID        = 0x32
        TXRATELO         = 0x33
        MODMISC          = 0x34
        FIFOCONTROL2     = 0x37
        ADCMISC          = 0x38
        AGCTARGET        = 0x39
        AGCATTACK        = 0x3A
        AGCDECAY         = 0x3B
        AGCCOUNTER       = 0x3C
        CICDEC           = 0x3F
        DATARATEHI       = 0x40
        DATARATELO       = 0x41
        TMGGAINHI        = 0x42
        TMGGAINLO        = 0x43
        PHASEGAIN        = 0x44
        FREQGAIN         = 0x45
        FREQGAIN2        = 0x46
        AMPLGAIN         = 0x47
        TRKFREQHI        = 0x4C
        TRKFREQLO        = 0x4D
        XTALCAP          = 0x4F
        SPAREOUT         = 0x60
        TESTOBS          = 0x68
        APEOVER          = 0x70
        TMMUX            = 0x71
        PLLVCOI          = 0x72
        PLLCPEN          = 0x73
        PLLRNGMISC       = 0x74
        AGCMANUAL        = 0x78
        ADCDCLEVEL       = 0x79
        RFMISC           = 0x7A
        TXDRIVER         = 0x7B
        REF              = 0x7C
        RXMISC           = 0x7D

    def __init__(self, cache_file, interval=3):
        logdbg('CCommunicationService.init')
        now = datetime.now()

        self.RepeatSize = 0
        self.RepeatInterval = None
        self.RepeatTime = now #ptime

        self.Regenerate = 0
        self.GetConfig = 0

        self.TimeSent = 0
        self.TimeUpdate = 0
        self.TimeUpdateComplete = 0

        self.DataStore = CDataStore(cache_file)
        self.DataStore.setCommModeInterval(interval)
        self.running = False
        self.TimeDifSec = 0
        self.DifHis = 0
        self.shid = sHID()

        self.firstSleep = 5.980
        self.nextSleep = 0.020
        self.pollCount = 0

        self.child = None
        self.thread_wait = 60.0 # seconds

    def buildFirstConfigFrame(self,Buffer):
        logdbg('buildFirstConfigFrame')
        newBuffer = [0]
        newBuffer[0] = [0]*9
        cs = Buffer[0][5] | (Buffer[0][4] << 8)
        self.DataStore.DeviceConfig.setDeviceCS(cs)
        comInt = self.DataStore.getCommModeInterval()
        historyAddress = 0xFFFFFF
        newBuffer[0][0] = 0xf0
        newBuffer[0][1] = 0xf0
        newBuffer[0][2] = EAction.aGetConfig
        newBuffer[0][3] = (cs >> 8) & 0xff
        newBuffer[0][4] = (cs >> 0) & 0xff
        newBuffer[0][5] = (comInt >> 4) & 0xff
        newBuffer[0][6] = (historyAddress >> 16) & 0x0f | 16 * (comInt & 0xf)
        newBuffer[0][7] = (historyAddress >> 8 ) & 0xff
        newBuffer[0][8] = (historyAddress >> 0 ) & 0xff
        Buffer[0] = newBuffer[0]
        Length = 0x09
        return Length

    def buildConfigFrame(self,Buffer):
        logdbg("buildConfigFrame")
        newBuffer = [0]
        newBuffer[0] = [0]*48
        cfgBuffer = [0]
        cfgBuffer[0] = [0]*44
        changed = self.DataStore.DeviceConfig.testConfigChanged(cfgBuffer)
        if changed:
            self.shid.dump('OutBuf', cfgBuffer[0], fmt='long')
            newBuffer[0][0] = Buffer[0][0]
            newBuffer[0][1] = Buffer[0][1]
            newBuffer[0][2] = EAction.aSendConfig # 0x40 # change this value if we won't store config
            newBuffer[0][3] = Buffer[0][3]
            for i in xrange(0,44):
                newBuffer[0][i+4] = cfgBuffer[0][i]
            Buffer[0] = newBuffer[0]
            Length = 48 # 0x30
        else: # current config not up to date; do not write yet
            Length = 0
        return Length

    def buildTimeFrame(self,Buffer,deviceCS,checkMinuteOverflow):
        logdbg("buildTimeFrame: deviceCS=%04x checkMinuteOverflow=%s" % 
               (deviceCS, checkMinuteOverflow))

        now = time.time()
        tm = time.localtime(now)

        newBuffer=[0]
        newBuffer[0]=Buffer[0]
        sec = tm[5]
        if sec > 59:
            sec = 0 # I don't know if La Crosse support leap seconds...
        if ( checkMinuteOverflow and (sec <= 5 or sec >= 55) ):
            if ( sec < 55 ):
                sec = 6 - sec
            else:
                sec = 60 - sec + 6
            logdbg('buildTimeFrame: second=%s' % sec)
            idx = self.DataStore.getLastHistoryIndex()
            self.DataStore.setRequestType(ERequestType.rtGetCurrent)
            self.setSleep(0.380,0.200)
            Length = self.buildACKFrame(newBuffer, EAction.aGetCurrent, deviceCS, idx, sec)
            Buffer[0]=newBuffer[0]
        else:
            #00000000: d5 00 0c 00 32 c0 00 8f 45 25 15 91 31 20 01 00
            #00000000: d5 00 0c 00 32 c0 06 c1 47 25 15 91 31 20 01 00
            #                             3  4  5  6  7  8  9 10 11
            newBuffer[0][2] = EAction.aSendTime # 0xc0
            newBuffer[0][3] = (deviceCS >>8)  & 0xFF
            newBuffer[0][4] = (deviceCS >>0)  & 0xFF
            newBuffer[0][5] = (tm[5] % 10) + 0x10 * (tm[5] // 10) #sec
            newBuffer[0][6] = (tm[4] % 10) + 0x10 * (tm[4] // 10) #min
            newBuffer[0][7] = (tm[3] % 10) + 0x10 * (tm[3] // 10) #hour
            #DayOfWeek = tm[6] - 1; #ole from 1 - 7 - 1=Sun... 0-6 0=Sun
            DayOfWeek = tm[6]       #py  from 0 - 6 - 0=Mon
            newBuffer[0][8] = DayOfWeek % 10 + 0x10 *  (tm[2] % 10)          #DoW + Day
            newBuffer[0][9] =  (tm[2] // 10) + 0x10 *  (tm[1] % 10)          #day + month
            newBuffer[0][10] = (tm[1] // 10) + 0x10 * ((tm[0] - 2000) % 10)  #month + year
            newBuffer[0][11] = (tm[0] - 2000) // 10                          #year
            self.Regenerate = 1
            self.TimeSent = 1
            Buffer[0]=newBuffer[0]
            Length = 0x0c
        return Length

    def buildACKFrame(self,Buffer, action, deviceCS, historyIndex, comInt):
        logdbg("buildACKFrame: action=%x deviceCS=%04x historyIndex=%i comInt=%x"
               % (action, deviceCS, historyIndex, comInt))
        now = datetime.now()
        newBuffer = [0]
        newBuffer[0] = [0]*9
        for i in xrange(0,2):
            newBuffer[0][i] = Buffer[0][i]

        # when last weather is stale, change action to get current weather
        age = now - self.DataStore.LastStat.LastCurrentWeatherTime
        if action != 5 and age >= timedelta(seconds=30):
            logdbg('morphing action from %d to 5 (age=%s)' % (action, age))
            action = 5
        # FIXME: for now, never ask for historical records
        if action == 0:
            logdbg('morphing action from %d to 5' % action)
            action = 5

        newBuffer[0][2] = action & 0xF
        if ( historyIndex >= 0x705 ):
            historyAddress = 0xffffff
        else:
            if ( self.DataStore.getBufferCheck() != 1
                 and self.DataStore.getBufferCheck() != 2 ):
                historyAddress = 18 * historyIndex + 0x1a0
            else:
                if historyIndex != 0xffff:
                    historyAddress = 18 * (historyIndex - 1) + 0x1a0
                else:
                    historyAddress = 0x7fe8
#                self.DataStore.setBufferCheck( 2)
        newBuffer[0][3] = (deviceCS >> 8) &0xFF
        newBuffer[0][4] = (deviceCS >> 0) &0xFF
        if ( comInt == 0xFFFFFFFF ):
            comInt = self.DataStore.getCommModeInterval()
        newBuffer[0][5] = (comInt >> 4) & 0xFF
        newBuffer[0][6] = (historyAddress >> 16) & 0x0F | 16 * (comInt & 0xF)
        newBuffer[0][7] = (historyAddress >> 8 ) & 0xFF
        newBuffer[0][8] = (historyAddress >> 0 ) & 0xFF

        #d5 00 09 f0 f0 03 00 32 00 3f ff ff
        Buffer[0]=newBuffer[0]
        self.Regenerate = 0
        self.TimeSent = 0
        return 9

    def handleWsAck(self,Buffer,Length):
        logdbg('handleWsAck')
        self.DataStore.setLastStatCache(seen=datetime.now(),
                                        quality=(Buffer[0][3] & 0x7f), 
                                        battery=(Buffer[0][2] & 0xf))

    def handleConfig(self,Buffer,Length):
        logdbg('handleConfig: %s' % self.timing())
        self.shid.dump('InBuf', Buffer[0], fmt='long')
        newBuffer=[0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        now = datetime.now()
        self.DataStore.setLastStatCache(seen=now,
                                        quality=(Buffer[0][3] & 0x7f), 
                                        battery=(Buffer[0][2] & 0xf))
        self.DataStore.DeviceConfig.read(newBuffer)
        idx = self.DataStore.getLastHistoryIndex()
        cs = newBuffer[0][47] | (newBuffer[0][46] << 8)
        self.DataStore.DeviceConfig.setDeviceCS(cs)

        self.DataStore.setLastConfigTime(now)
        self.DataStore.setRequestType(ERequestType.rtGetCurrent)
        self.setSleep(0.380,0.200)
        newLength[0] = self.buildACKFrame(newBuffer, EAction.aGetCurrent, cs, idx, 0xFFFFFFFF)

        Buffer[0] = newBuffer[0]
        Length[0] = newLength[0]

    def handleCurrentData(self,Buffer,Length):
        logdbg('handleCurrentData: %s' % self.timing())

        now = datetime.now()

        # update the weather data cache if changed or stale
        chksum = CCurrentWeatherData.calcChecksum(Buffer)
        age = now - self.DataStore.LastStat.LastCurrentWeatherTime
        if (age >= timedelta(seconds=10)
            or chksum != self.DataStore.CurrentWeather.checksum()):
            data = CCurrentWeatherData()
            data.read(Buffer)
            self.shid.dump('CurWea', Buffer[0], fmt='long')
            self.DataStore.setCurrentWeather(data)

        # update the connection cache
        self.DataStore.setLastStatCache(seen=now,
                                        quality=(Buffer[0][3] & 0x7f), 
                                        battery=(Buffer[0][2] & 0xf),
                                        currentWeatherTime=now)

        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]

        cs = newBuffer[0][5] | (newBuffer[0][4] << 8)
        self.DataStore.DeviceConfig.setDeviceCS(cs)

        cfgBuffer = [0]
        cfgBuffer[0] = [0]*44
        idx = self.DataStore.getLastHistoryIndex()
        changed = self.DataStore.DeviceConfig.testConfigChanged(cfgBuffer)
        inBufCS = self.DataStore.DeviceConfig.getInBufCS()
        if inBufCS == 0 or inBufCS != cs:
            logdbg('handleCurrentData: inBufCS of station not actual')
            self.DataStore.setRequestType(ERequestType.rtGetConfig)
            self.setSleep(0.400,0.400)
            newLength[0] = self.buildACKFrame(newBuffer, EAction.aGetConfig, cs, idx, 0xFFFFFFFF)
        elif changed:
            logdbg('handleCurrentData: outBufCS of station changed')
            self.DataStore.setRequestType(ERequestType.rtSetConfig)
            self.setSleep(0.420,0.005)
            newLength[0] = self.buildACKFrame(newBuffer, EAction.aReqSetConfig, cs, idx, 0xFFFFFFFF)
        else:
            self.DataStore.setRequestType(ERequestType.rtGetCurrent)
            self.setSleep(0.380,0.200)
            newLength[0] = self.buildACKFrame(newBuffer, EAction.aGetCurrent, cs, idx, 0xFFFFFFFF)

        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def handleHistoryData(self,Buffer,Length):
        logdbg('handleHistoryData: %s' % self.timing())
        now = datetime.now()
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        data = CHistoryDataSet()
        data.read(newBuffer)
        cs = newBuffer[0][5] | (newBuffer[0][4] << 8)
        self.DataStore.DeviceConfig.setDeviceCS(cs)
        self.DataStore.setLastStatCache(seen=now,
                                        quality=(Buffer[0][3] & 0x7f),
                                        battery=(Buffer[0][2] & 0xf))
        LatestHistoryAddres = ((((Buffer[0][6] & 0xF) << 8) | Buffer[0][7]) << 8) | Buffer[0][8]
        ThisHistoryAddres = ((((Buffer[0][9] & 0xF) << 8) | Buffer[0][10]) << 8) | Buffer[0][11]
        ThisHistoryIndex = (ThisHistoryAddres - 415) / 0x12
        LatestHistoryIndex = (LatestHistoryAddres - 415) / 0x12

        if ( LatestHistoryIndex >= ThisHistoryIndex ):
            self.DifHis = LatestHistoryIndex - ThisHistoryIndex
        else:
            self.DifHis = LatestHistoryIndex + 1797 - ThisHistoryIndex

        if self.DifHis > 0:
            logdbg('handleHistoryData: Time=%s OutstandingHistorySets=%4i' %
                   (data.Time, self.DifHis))

        # FIXME: for now skip the history records
        if self.DifHis > 0:
            ThisHistoryIndex = LatestHistoryIndex
            self.DifHis = 0
            self.DataStore.setLastHistoryIndex(ThisHistoryIndex)
        else:
            if ThisHistoryIndex == self.DataStore.getLastHistoryIndex():
                pass
            else:
                self.DataStore.setHistoryData(data)
                self.DataStore.setLastHistoryIndex(ThisHistoryIndex)
        self.DataStore.setLastHistoryDataTime(now)

        if ThisHistoryIndex == LatestHistoryIndex:
            self.TimeDifSec = (data.Time - now).seconds
            if self.TimeDifSec > 43200:
                self.TimeDifSec = self.TimeDifSec - 86400 + 1
            logdbg('handleHistoryData: timeDifSec=%4s Time=%s' %
                   (self.TimeDifSec, data.Time))
        else:
            logdbg('handleHistoryData: no recent history data: Time=%s' %
                   data.Time)

        self.DataStore.setRequestType(ERequestType.rtGetCurrent)
        self.setSleep(0.380,0.200)
        idx = ThisHistoryIndex
        newLength[0] = self.buildACKFrame(newBuffer, EAction.aGetCurrent, cs, idx, 0xFFFFFFFF)

        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def handleNextAction(self,Buffer,Length):
        logdbg('handleNextAction')
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        newLength[0] = Length[0]
        self.DataStore.setLastStatCache(seen=datetime.now(),
                                        quality=(Buffer[0][3] & 0x7f))
        cs = newBuffer[0][5] | (newBuffer[0][4] << 8)
        self.DataStore.DeviceConfig.setDeviceCS(cs)
        if (Buffer[0][2] & 0xEF) == EResponseType.rtReqFirstConfig:
            logdbg('handleNextAction: a1 (first-time config)')
            newLength[0] = self.buildFirstConfigFrame(newBuffer)
            self.setSleep(0.085,0.005)
        elif (Buffer[0][2] & 0xEF) == EResponseType.rtReqSetConfig:
            logdbg('handleNextAction: a2 (set config data)')
            newLength[0] = self.buildConfigFrame(newBuffer)
            self.setSleep(0.085,0.005)
        elif (Buffer[0][2] & 0xEF) == EResponseType.rtReqSetTime:
            logdbg('handleNextAction: a3 (set time data)')
            newLength[0] = self.buildTimeFrame(newBuffer, cs, True)
            self.setSleep(0.085,0.005)
        else:
            logdbg('handleNextAction: %02x' % (Buffer[0][2] & 0xEF))
            idx = self.DataStore.getLastHistoryIndex()
            self.DataStore.setRequestType(ERequestType.rtGetCurrent)
            self.setSleep(0.380,0.200)
            newLength[0] = self.buildACKFrame(newBuffer, EAction.aGetCurrent, cs, idx, 0xFFFFFFFF)

        Length[0] = newLength[0]
        Buffer[0] = newBuffer[0]

    def generateResponse(self, Buffer, Length):
        logdbg('generateResponse: %s' % self.timing())
        newBuffer = [0]
        newBuffer[0] = Buffer[0]
        newLength = [0]
        newLength[0] = Length[0]
        reqType = self.DataStore.getRequestType()
        if Length[0] == 0:
            raise BadResponse('zero length for requestType=%x' % reqType)

        bufferID = (Buffer[0][0] <<8) | Buffer[0][1]
        respType = (Buffer[0][2] & 0xE0)
        logdbg("generateResponse: id=%04x resp=%x req=%x length=%x" %
               (bufferID, respType, reqType, Length[0]))
        deviceID = self.DataStore.getDeviceID()
        self.DataStore.setRegisteredDeviceID(bufferID)

        if bufferID == 0xF0F0:
            loginf('generateResponse: console not paired, attempting to pair to 0x%04x' % deviceID)
            #    00000000: dd 0a 01 fe 18 f6 aa 01 2a a2 4d 00 00 87 16
            newLength[0] = self.buildACKFrame(newBuffer, EAction.aReqSetConfig, deviceID, 0xFFFF, 0xFFFFFFFF)
        elif bufferID == deviceID:
            if respType == EResponseType.rtDataWritten:
                #    00000000: 00 00 06 00 32 20
                if Length[0] == 0x06:
                    self.DataStore.DeviceConfig.setResetMinMaxFlags(0)
                    self.shid.setRX()
                    raise DataWritten()
                    #self.DataStore.setRequestType(ERequestType.rtGetCurrent)
                    #self.setSleep(0.380,0.200)
                    #self.handleWsAck(newBuffer, newLength)
                else:
                    raise BadResponse('length=%x respType=%x' %
                                      (Length[0], respType))
            elif respType == EResponseType.rtGetConfig:
                #    00000000: 00 00 30 00 32 40
                if Length[0] == 0x30:
                    self.handleConfig(newBuffer, newLength)
                else:
                    raise BadResponse('length=%x respType=%x' %
                                      (Length[0], respType))
            elif respType == EResponseType.rtGetCurrentWeather:
                #    00000000: 00 00 d7 00 32 60
                if Length[0] == 0xd7: #215
                    self.handleCurrentData(newBuffer, newLength)
                else:
                    raise BadResponse('length=%x respType=%x' %
                                      (Length[0], respType))
            elif respType == EResponseType.rtGetHistory:
                #    00000000: 00 00 1e 00 32 80
                if Length[0] == 0x1e:
                    self.handleHistoryData(newBuffer, newLength)
                else:
                    raise BadResponse('length=%x respType=%x' %
                                      (Length[0], respType))
            elif respType == EResponseType.rtRequest:
                #    00000000: 00 00 06 f0 f0 a1
                #    00000000: 00 00 06 00 32 a3
                #    00000000: 00 00 06 00 32 a2
                if Length[0] == 0x06:
                    self.handleNextAction(newBuffer, newLength)
                else:
                    raise BadResponse('length=%x respType=%x' %
                                      (Length[0], respType))
            else:
                msg = 'unrecognized response type %x' % respType
                loginf(msg)
                raise BadResponse(msg)
        else:
            msg = 'message from console contains unknown device ID (id=%04x resp=%x req=%x)' % (bufferID, respType, reqType)
            loginf(msg)
            log_frame(Length[0],Buffer[0])
            raise BadResponse(msg)

        Buffer[0] = newBuffer[0]
        Length[0] = newLength[0]

    def configureRegisterNames(self):
        self.reg_names[self.AX5051RegisterNames.IFMODE]    =0x00
        self.reg_names[self.AX5051RegisterNames.MODULATION]=0x41 #fsk
        self.reg_names[self.AX5051RegisterNames.ENCODING]  =0x07
        self.reg_names[self.AX5051RegisterNames.FRAMING]   =0x84 #1000:0100 ##?hdlc? |1000 010 0
        self.reg_names[self.AX5051RegisterNames.CRCINIT3]  =0xff
        self.reg_names[self.AX5051RegisterNames.CRCINIT2]  =0xff
        self.reg_names[self.AX5051RegisterNames.CRCINIT1]  =0xff
        self.reg_names[self.AX5051RegisterNames.CRCINIT0]  =0xff
        self.reg_names[self.AX5051RegisterNames.FREQ3]     =0x38
        self.reg_names[self.AX5051RegisterNames.FREQ2]     =0x90
        self.reg_names[self.AX5051RegisterNames.FREQ1]     =0x00
        self.reg_names[self.AX5051RegisterNames.FREQ0]     =0x01
        self.reg_names[self.AX5051RegisterNames.PLLLOOP]   =0x1d
        self.reg_names[self.AX5051RegisterNames.PLLRANGING]=0x08
        self.reg_names[self.AX5051RegisterNames.PLLRNGCLK] =0x03
        self.reg_names[self.AX5051RegisterNames.MODMISC]   =0x03
        self.reg_names[self.AX5051RegisterNames.SPAREOUT]  =0x00
        self.reg_names[self.AX5051RegisterNames.TESTOBS]   =0x00
        self.reg_names[self.AX5051RegisterNames.APEOVER]   =0x00
        self.reg_names[self.AX5051RegisterNames.TMMUX]     =0x00
        self.reg_names[self.AX5051RegisterNames.PLLVCOI]   =0x01
        self.reg_names[self.AX5051RegisterNames.PLLCPEN]   =0x01
        self.reg_names[self.AX5051RegisterNames.RFMISC]    =0xb0
        self.reg_names[self.AX5051RegisterNames.REF]       =0x23
        self.reg_names[self.AX5051RegisterNames.IFFREQHI]  =0x20
        self.reg_names[self.AX5051RegisterNames.IFFREQLO]  =0x00
        self.reg_names[self.AX5051RegisterNames.ADCMISC]   =0x01
        self.reg_names[self.AX5051RegisterNames.AGCTARGET] =0x0e
        self.reg_names[self.AX5051RegisterNames.AGCATTACK] =0x11
        self.reg_names[self.AX5051RegisterNames.AGCDECAY]  =0x0e
        self.reg_names[self.AX5051RegisterNames.CICDEC]    =0x3f
        self.reg_names[self.AX5051RegisterNames.DATARATEHI]=0x19
        self.reg_names[self.AX5051RegisterNames.DATARATELO]=0x66
        self.reg_names[self.AX5051RegisterNames.TMGGAINHI] =0x01
        self.reg_names[self.AX5051RegisterNames.TMGGAINLO] =0x96
        self.reg_names[self.AX5051RegisterNames.PHASEGAIN] =0x03
        self.reg_names[self.AX5051RegisterNames.FREQGAIN]  =0x04
        self.reg_names[self.AX5051RegisterNames.FREQGAIN2] =0x0a
        self.reg_names[self.AX5051RegisterNames.AMPLGAIN]  =0x06
        self.reg_names[self.AX5051RegisterNames.AGCMANUAL] =0x00
        self.reg_names[self.AX5051RegisterNames.ADCDCLEVEL]=0x10
        self.reg_names[self.AX5051RegisterNames.RXMISC]    =0x35
        self.reg_names[self.AX5051RegisterNames.FSKDEV2]   =0x00
        self.reg_names[self.AX5051RegisterNames.FSKDEV1]   =0x31
        self.reg_names[self.AX5051RegisterNames.FSKDEV0]   =0x27
        self.reg_names[self.AX5051RegisterNames.TXPWR]     =0x03
        self.reg_names[self.AX5051RegisterNames.TXRATEHI]  =0x00
        self.reg_names[self.AX5051RegisterNames.TXRATEMID] =0x51
        self.reg_names[self.AX5051RegisterNames.TXRATELO]  =0xec
        self.reg_names[self.AX5051RegisterNames.TXDRIVER]  =0x88

    def initTransceiver(self, frequency_standard):
        logdbg('initTransceiver: frequency_standard=%s' % frequency_standard)

        self.DataStore.setFrequencyStandard(frequency_standard)
        self.configureRegisterNames()

        # calculate the frequency then set frequency registers
        freq = self.DataStore.TransceiverSettings.Frequency
        loginf('base frequency: %d' % freq)
        freqVal =  long(freq / 16000000.0 * 16777216.0)
        corVec = [None]
        self.shid.readConfigFlash(0x1F5, 4, corVec)
        corVal = corVec[0][0] << 8
        corVal |= corVec[0][1]
        corVal <<= 8
        corVal |= corVec[0][2]
        corVal <<= 8
        corVal |= corVec[0][3]
        loginf('frequency correction: %d (0x%x)' % (corVal,corVal))
        freqVal += corVal
        if not (freqVal % 2):
            freqVal += 1
        loginf('adjusted frequency: %d (0x%x)' % (freqVal,freqVal))
        self.reg_names[self.AX5051RegisterNames.FREQ3] = (freqVal >>24) & 0xFF
        self.reg_names[self.AX5051RegisterNames.FREQ2] = (freqVal >>16) & 0xFF
        self.reg_names[self.AX5051RegisterNames.FREQ1] = (freqVal >>8)  & 0xFF
        self.reg_names[self.AX5051RegisterNames.FREQ0] = (freqVal >>0)  & 0xFF
        logdbg('frequency registers: %x %x %x %x' % (
                self.reg_names[self.AX5051RegisterNames.FREQ3],
                self.reg_names[self.AX5051RegisterNames.FREQ2],
                self.reg_names[self.AX5051RegisterNames.FREQ1],
                self.reg_names[self.AX5051RegisterNames.FREQ0]))

        # figure out the transceiver id
        buf = [None]
        self.shid.readConfigFlash(0x1F9, 7, buf)
        tid  = buf[0][5] << 8
        tid += buf[0][6]
        loginf('transceiver identifier: %d (0x%04x)' % (tid,tid))
        self.DataStore.setDeviceID(tid)

        # figure out the transceiver serial number
        sn  = str("%02d"%(buf[0][0]))
        sn += str("%02d"%(buf[0][1]))
        sn += str("%02d"%(buf[0][2]))
        sn += str("%02d"%(buf[0][3]))
        sn += str("%02d"%(buf[0][4]))
        sn += str("%02d"%(buf[0][5]))
        sn += str("%02d"%(buf[0][6]))
        loginf('transceiver serial: %s' % sn)
        self.DataStore.setTransceiverSerNo(sn)
            
        for r in self.reg_names:
            self.shid.writeReg(r, self.reg_names[r])

        self.shid.execute(5)
        self.shid.setPreamblePattern(0xaa)
        self.shid.setState(0x1e)
        time.sleep(1) # FIXME: is this necessary?
        self.shid.setRX()

    def setup(self, frequency_standard, vendor_id, product_id, device_id):
        self.shid.open(vendor_id, product_id, device_id)
        self.initTransceiver(frequency_standard)
        self.DataStore.setTransceiverPresent(True)

    def teardown(self):
        self.shid.close()

    # FIXME: make this thread-safe
    def getWeatherData(self):
        return self.DataStore.CurrentWeather

    # FIXME: make this thread-safe
    def getLastStat(self):
        return self.DataStore.LastStat

    # FIXME: make this thread-safe
    def getConfig(self):
        return self.DataStore.DeviceConfig

    # FIXME: make this thread-safe
    def getHistory(self):
        return self.DataStore.HistoryData

    def transceiverIsPresent(self):
        return self.DataStore.getTransceiverPresent()

    def transceiverIsRegistered(self):
        return self.DataStore.getDeviceRegistered()

    # FIXME: implement pairTransceiver
    def pairTransceiver(self):
#        self.DataStore.firstTimeConfig(timeout)
        pass

    def startRFThread(self):
        if self.child is not None:
            return
        logdbg('startRFThread: spawning RF thread')
        self.running = True
        self.child = threading.Thread(target=self.doRF)
        self.child.setName('RFComm')
        self.child.setDaemon(True)
        self.child.start()

    def stopRFThread(self):
        self.running = False
        logdbg('stopRFThread: waiting for RF thread to terminate')
        self.child.join(self.thread_wait)
        if self.child.isAlive():
            logerr('unable to terminate RF thread after %d seconds' %
                   self.thread_wait)
        else:
            self.child = None

    def isRunning(self):
        return self.running

    def doRF(self):
        try:
            logdbg('starting rf communication')
            while self.running:
                self.doRFCommunication()
        except Exception, e:
            logerr('exception in doRF: %s' % e)
            if weewx.debug:
                log_traceback(dst=syslog.LOG_DEBUG)
            self.running = False
            raise
        finally:
            logdbg('stopping rf communication')

    def doRFCommunication(self):
        time.sleep(self.firstSleep)
        self.pollCount = 0
        while self.running:
            StateBuffer = [None]
            self.shid.getState(StateBuffer)
            self.pollCount += 1
            if StateBuffer[0][0] == 0x16:
                break
            else:
                time.sleep(self.nextSleep)
        else:
            return

        DataLength = [0]
        DataLength[0] = 0
        FrameBuffer=[0]
        FrameBuffer[0]=[0]*0x03
        self.shid.getFrame(FrameBuffer, DataLength)
        try:
            self.generateResponse(FrameBuffer, DataLength)
            self.shid.setState(0)
            self.shid.setFrame(FrameBuffer[0], DataLength[0])
        except BadResponse, e:
            logerr('generateResponse failed: %s' % e)
        except DataWritten, e:
            logdbg('SetTime/SetConfig data written')
        self.shid.setTX()

    # these are for diagnostics and debugging
    def setSleep(self, firstsleep, nextsleep):
        self.firstSleep = firstsleep
        self.nextSleep = nextsleep

    def timing(self):
        s = self.firstSleep + self.nextSleep * (self.pollCount - 1)
        return 'sleep=%s first=%s next=%s count=%s' % (
            s, self.firstSleep, self.nextSleep, self.pollCount)
