#!/usr/bin/env python
# $Id: te923.py 2775 2014-12-03 20:19:47Z mwall $
# Copyright 2015 Matthew Wall/Andrew Miles
# See the file LICENSE.txt for your full rights.
#
# Thanks to Sebastian John for the te923tool written in C (v0.6.1):
#   http://te923.fukz.org/
# Thanks to Mark Teel for the te923 implementation in wview:
#   http://www.wviewweather.com/
#
# History: 0.12 - Experimental version developed by Matthew Wall
#          0.13 - Added reading of latitude, longitude, altitude
#               - Added reading of data logger
#               - Automatic detection of memory size
#               - More data passed back to weewx even if schema doesn't use it
#               - Simplified sensor state to ok, no_link or invalid.  No evidence of out_of_range or error states present in te923tool code
#          0.14 - Improved read (based on 0.12)
#          0.15 - Added write to station
#               - Multiple options added to configurator

"""Classes and functions for interfacing with te923 weather stations.

These stations were made by Hideki and branded as Honeywell, Meade, IROX Pro X,
Mebus TE923, and TFA Nexus.  They date back to at least 2007 and are still
sold (sparsely in the US, more commonly in Europe) as of 2013.

Apparently there are at least two different memory sizes.  One version can
store about 200 records, a newer version can store about 3300 records.

The firmware version of each component can be read by talking to the station,
assuming that the component has a wireless connection to the station, of
course.

To force connection between station and sensors, press and hold DOWN button.

To reset all station parameters:
 - press and hold SNOOZE and UP for 4 seconds
 - press SET button; main unit will beep
 - wait until beeping stops
 - remove batteries and wait 10 seconds
 - reinstall batteries

From the Meade TE9233W manual (TE923W-M_IM(ENG)_BK_010511.pdf):

  Remote temperature/humidty sampling interval: 10 seconds
  Remote temperature/humidity transmit interval: about 47 seconds
  Indoor temperature/humidity sampling interval: 10 seconds
  Indoor pressure sampling interval: 20 minutes
  Rain counter transmitting interval: 183 seconds
  Wind direction transmitting interval: 33 seconds
  Wind/Gust speed display update interval: 33 seconds
  Wind/Gust sampling interval: 11 seconds
  UV transmitting interval: 300 seconds
  Rain counter resolution: 0.03 in (0.6578 mm)
  Battery status of each sensor is checked every hour

This implementation polls the station for data.  Use the polling_interval to
control the frequency of polling.  Default is 10 seconds.

The manual says that a single bucket tip is 0.03 inches.  In reality, a single
bucket tip is between 0.02 and 0.03 in (0.508 to 0.762 mm).  This driver uses
a value of 0.02589 in (0.6578 mm) per bucket tip.

The station has altitude, latitude, longitude, and time.

Notes From/About Other Implementations

Apparently te923tool came first, then wview copied a bit from it.  te923tool
provides more detail about the reason for invalid values, for example, values
out of range versus no link with sensors.  However, these values require
validation

There are some disagreements between the wview and te923tool implementations.

From the te923tool:
- reading from usb in 8 byte chunks instead of all at once
- length of buffer is 35, but reads are 32-byte blocks
- windspeed and windgust state can never be -1
- index 29 in rain count, also in wind dir

From wview:
- wview does the 8-byte reads using interruptRead
- wview ignores the windchill value from the station
- wview treats the pressure reading as barometer (SLP), then calculates the
    station pressure and altimeter pressure

Memory Map

0x20000 - Last sample:

[00] = Month (Bits 0-3), Weekday (1 = Monday) (Bits 7:4)
[01] = Day
[02] = Hour
[03] = Minute
[04] ... reading as below

0x020001 - Current readings:

[00] = Temp In Low BCD
[01] = Temp In High BCD (Bit 5 = 0.05 deg, Bit 7 = -ve)
[02] = Humidity In
[03] = Temp Channel 1 Low (No link = Xa)
[04] = Temp Channel 1 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[05] = Humidity Channel 1 (No link = Xa)
[06] = Temp Channel 2 Low (No link = Xa)
[07] = Temp Channel 2 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[08] = Humidity Channel 2 (No link = Xa)
[09] = Temp Channel 3 Low (No link = Xa)
[10] = Temp Channel 3 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[11] = Humidity Channel 3 (No link = Xa)
[12] = Temp Channel 4 Low (No link = Xa)
[13] = Temp Channel 4 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[14] = Humidity Channel 4 (No link = Xa)
[15] = Temp Channel 5 Low (No link = Xa)
[16] = Temp Channel 5 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[17] = Humidity Channel 5 (No link = Xa)
[18] = UV Low (No link = ff)
[19] = UV High (No link = ff)
[20] = Sea-Level Pressure Low
[21] = Sea-Level Pressure High
[22] = Forecast (Bits 0-2) Storm (Bit 3)
[23] = Wind Chill Low (No link = ff)
[24] = Wind Chill High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve, No link = ff)
[25] = Gust Low (No link = ff)
[26] = Gust High (No link = ff)
[27] = Wind Low (No link = ff)
[28] = Wind High (No link = ff)
[29] = Wind Dir (Bits 0-3)
[30] = Rain Low
[31] = Rain High

(1) Memory map values related to sensors use same coding as above
(2) Checksum are via subtraction: 0x100 - sum of all values, then add 0x100 until positive i.e. 0x100 - 0x70 - 0x80 - 0x28 = -0x18, 0x18 + 0x100 = 0xE8

--- SECTION 1: Date & Local location
0x000000 - Unknown - changes if date section is modified but still changes if same data is written so not a checksum
0x000001 - Unknown (always 0)
0x000002 - Day (Reverse BCD) (Changes at midday!)
0x000003 - Unknown
0x000004 - Year (Reverse BCD)
0x000005 - Month (Bits 7:4), Weekday (Bits 3:1)
0x000006 - Latitude (degrees) (reverse BCD)
0x000007 - Latitude (minutes) (reverse BCD)
0x000008 - Longitude (degrees) (reverse BCD)
0x000009 - Longitude (minutes) (reverse BCD)
0x00000A - Bit 7 - Set if Latitude southerly, Bit 6 - Set if Longitude easterly, Bit 4 - Set if DST is always on, Bit 3 - Set if -ve TZ, Bits 0 & 1 - Set if half-hour TZ
0x00000B - Longitude (100 degrees) (Bits 7:4), DST zone (Bits 3:0)
0x00000C - City code (High) (Bits 7:4), Language (0 - English, 1 - German, 2 - French, 3 - Italian, 4 - Spanish, 6 - Dutch) (Bits 3:0)
0x00000D - Timezone (hour) (Bits 7:4), City code (Low) (Bits 3:0)
0x00000E - Bit 2 - Set if 24hr time format, Bit 1 - Set if American style date format
0x00000F - Checksum of 00:0E

--- SECTION 2: Time Alarms
0x000010 - Weekday alarm (hour) (reverse BCD) (Bit 3 - Set if single alarm active, Bit 2 - Set if weekday-alarm active)
0x000011 - Weekday alarm (minute) (reverse BCD)
0x000012 - Single alarm (hour) (reverse BCD) (Bit 3 - Set if pre-alarm active)
0x000013 - Single alarm (minute) (reverse BCD)
0x000014 - Bits 7-4: Pre-alarm (1-5 = 15,30,45,60 or 90 mins), Bits 3-0: Snooze value
0x000015 - Checksum of 10:14

--- SECTION 3: Alternate Location
0x000016 - Latitude (degrees) (reverse BCD)
0x000017 - Latitude (minutes) (reverse BCD)
0x000018 - Longitude (degrees) (reverse BCD)
0x000019 - Longitude (minutes) (reverse BCD)
0x00001A - Bit 7 - Set if Latitude southerly, Bit 6 - Set if Longitude easterly, Bit 4 - Set if DST is always on, Bit 3 - Set if -ve TZ, Bits 0 & 1 - Set if half-hour TZ
0x00001B - Longitude (100 degrees) (Bits 7:4), DST zone (Bits 3:0)
0x00001C - City code (High) (Bits 7:4), Unknown (Bits 3:0)
0x00001D - Timezone (hour) (Bits 7:4), City code (Low) (Bits 3:0)
0x00001E - Checksum of 16:1D

--- SECTION 4: Temperature Alarms
0x00001F:20 - High Temp Alarm Value
0x000021:22 - Low Temp Alarm Value
0x000023 - Checksum of 1F:22

--- SECTION 5: Min/Max 1
0x000024:25 - Min In Temp
0x000026:27 - Max in Temp
0x000028 - Min In Humidity
0x000029 - Max In Humidity
0x00002A:2B - Min Channel 1 Temp
0x00002C:2D - Max Channel 1 Temp
0x00002E - Min Channel 1 Humidity
0x00002F - Max Channel 1 Humidity
0x000030:31 - Min Channel 2 Temp
0x000032:33 - Max Channel 2 Temp
0x000034 - Min Channel 2 Humidity
0x000035 - Max Channel 2 Humidity
0x000036:37 - Min Channel 3 Temp
0x000038:39 - Max Channel 3 Temp
0x00003A - Min Channel 3 Humidity
0x00003B - Max Channel 3 Humidity
0x00003C:3D - Min Channel 4 Temp
0x00003F - Checksum of 24:3E

--- SECTION 6: Min/Max 2
0x00003E,40 - Max Channel 4 Temp
0x000041 - Min Channel 4 Humidity
0x000042 - Max Channel 4 Humidity
0x000043:44 - Min Channel 4 Temp
0x000045:46 - Max Channel 4 Temp
0x000047 - Min Channel 4 Humidity
0x000048 - Max Channel 4 Humidity
0x000049 - ? Values rising/falling ? Bit 5 : Chan 1 temp falling, Bit 2 : In temp falling
0x00004A:4B - 0xFF (Unused)
0x00004C - Battery status - Bit 7: Rain, Bit 6: Wind, Bit 5: UV Bits 4:0: Channel 5:1
0x00004D:58 - 0xFF (Unused)
0x000059 - Checksum of 3E:58

--- SECTION 7: Altitude
0x00005A:5B - Altitude (Low:High)
0x00005C - Bit 3 - Set if altitude negative, Bit 2 - Pressure falling?, Bit 1 - Always set
0X00005D - Checksum of 5A:5C

0x00005E:5F - Unused (0xFF)

--- SECTION 8: Pressure 1
0x000060 - Month of last reading (Bits 0-3), Weekday (1 = Monday) (Bits 7:4)
0x000061 - Day of last reading
0x000062 - Hour of last reading
0x000063 - Minute of last reading
0x000064:65 - T -0 Hours
0x000066:67 - T -1 Hours
0x000068:69 - T -2 Hours
0x00006A:6B - T -3 Hours
0x00006C:6D - T -4 Hours
0x00006E:6F - T -5 Hours
0x000070:71 - T -6 Hours
0x000072:73 - T -7 Hours
0x000074:75 - T -8 Hours
0x000076:77 - T -9 Hours
0x000078:79 - T -10 Hours
0x00007B - Checksum of 60:7A

--- SECTION 9: Pressure 2
0x00007A,7C - T -11 Hours
0x00007D:7E - T -12 Hours
0x00007F:80 - T -13 Hours
0x000081:82 - T -14 Hours
0x000083:84 - T -15 Hours
0x000085:86 - T -16 Hours
0x000087:88 - T -17 Hours
0x000089:90 - T -18 Hours
0x00008B:8C - T -19 Hours
0x00008D:8E - T -20 Hours
0x00008f:90 - T -21 Hours
0x000091:92 - T -22 Hours
0x000093:94 - T -23 Hours
0x000095:96 - T -24 Hours
0x000097 - Checksum of 7C:96

--- SECTION 10: Versions
0x000098 - firmware versions (barometer)
0x000099 - firmware versions (uv)
0x00009A - firmware versions (rcc)
0x00009B - firmware versions (wind)
0x00009C - firmware versions (system)
0x00009D - Checksum of 98:9C

0x00009E:9F - 0xFF (Unused)

--- SECTION 11: Rain/Wind Alarms 1
0x0000A0 - Alarms, Bit2 - Set if rain alarm active, Bit 1 - Set if wind alarm active, Bit 0 - Set if gust alarm active
0x0000A1:A2 - Rain alarm value (High:Low) (BCD)
0x0000A3 - Unknown
0x0000A4:A5 - Wind speed alarm value
0x0000A6 - Unknown
0x0000A7:A8 - Gust alarm value
0x0000A9 - Checksum of A0:A8

--- SECTION 12: Rain/Wind Alarms 2
0x0000AA:AB - Max daily wind speed
0x0000AC:AD - Max daily gust speed
0x0000AE:AF - Rain bucket count (yesterday) (Low:High)
0x0000B0:B1 - Rain bucket count (week) (Low:High)
0x0000B2:B3 - Rain bucket count (month) (Low:High)
0x0000B4 - Checksum of AA:B3

0x0000B5:E0 - 0xFF (Unused)

--- SECTION 13: Unknownn
0x0000E1:F9 - 0x15 (Unknown)
0x0000FA  - Checksum of E1:F9

--- SECTION 14: Archiving
0c0000FB - Unknown
0x0000FC - Memory size (0 = 0x1fff, 2 = 0x20000)
0x0000FD - Number of records (High)
0x0000FE - Archive interval (1-11 = 5, 10, 20, 30, 60, 90, 120, 180, 240, 360, 1440 mins)
0x0000FF - Number of records (Low)
0x000100 - Checksum of FB:FF

Records start at 0x000101

Record:

[00] = Month (Bits 0-3), Weekday (1 = Monday) (Bits 7:4)
[01] = Day
[02] = Hour
[03] = Minute
[04] = Temp In Low BCD
[05] = Temp In High BCD (Bit 5 = 0.05 deg, Bit 7 = -ve)
[06] = Humidity In
[07] = Temp Channel 1 Low (No link = Xa)
[08] = Temp Channel 1 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[09] = Humidity Channel 1 (No link = Xa)
[10] = Temp Channel 2 Low (No link = Xa)
[11] = Temp Channel 2 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[12] = Humidity Channel 2 (No link = Xa)
[13] = Temp Channel 3 Low (No link = Xa)
[14] = Temp Channel 3 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[15] = Checksum of bytes 0:14

[16] = Humidity Channel 3 (No link = Xa)
[17] = Temp Channel 4 Low (No link = Xa)
[18] = Temp Channel 4 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[19] = Humidity Channel 4 (No link = Xa)
[20] = Temp Channel 5 Low (No link = Xa)
[21] = Temp Channel 5 High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve)
[22] = Humidity Channel 5 (No link = Xa)
[23] = UV Low (No link = ff)
[24] = UV High (No link = ff)
[25] = Sea-Level Pressure Low
[26] = Sea-Level Pressure High
[27] = Forecast (Bits 0-2) Storm (Bit 3)
[28] = Wind Chill Low (No link = ff)
[29] = Wind Chill High (Bit 6 = 1, Bit 5 = 0.05 deg, Bit 7 = +ve, No link = ee)
[30] = Gust Low (No link = ff)
[31] = Gust High (No link = ff)
[32] = Wind Low (No link = ff)
[33] = Wind High (No link = ff)
[34] = Wind Dir (Bits 0-3)
[35] = Rain Low
[36] = Rain High
[37] = Checksum of bytes 16:36

Schema Additions

The following are extra to the default weewx schema.  Add to record in database:

          ('extraTemp4',           'REAL'),
          ('extraHumid3',          'REAL'),
          ('extraHumid4',          'REAL'),
          ('extraBatteryStatus1',  'REAL'),
          ('extraBatteryStatus2',  'REAL'),
          ('extraBatteryStatus3',  'REAL'),
          ('extraBatteryStatus4',  'REAL'),
          ('txLinkStatus',         'REAL'),
          ('windLinkStatus',       'REAL'),
          ('rainLinkStatus',       'REAL'),
          ('outTempLinkStatus',    'REAL'),
          ('extraLinkStatus1',     'REAL'),
          ('extraLinkStatus2',     'REAL'),
          ('extraLinkStatus3',     'REAL'),
          ('extraLinkStatus4',     'REAL'),
          ('forecast',             'REAL'),
          ('storm',                'REAL'),


Random Notes

Here are some tidbits for usb putzing.  The documentation for reading/writing
USB in python is scarce.  Apparently there are (at least) two ways of reading
from USB - one using interruptRead, the other doing bulk reads.  Which you use
may depend on the device itself.

There are at least two Python interfaces, e.g. claim_interface vs
claimInterface.

  usb_control_msg(0x21,    # request type
                  0x09,    # request
                  0x0200,  # value
                  0x0000,  # index
                  buf,     # buffer
                  0x08,    # size
                  timeout) # timeout

Control packet is 8 bytes:
                  
Read from station = 0x05 (Length), 0xAF (Read), Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), CRC, Unused, Unused
Read Acknowledge  = 0x24 (Ack), 0xAF (Read), Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), CRC, Unused, Unused
Write to station  = 0x07 (Length), 0xAE (Write), Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), Data1, Data2, Data3
	            ... Data continue with 3 more packets of length 7 then....
                    0x02 (Length), Data32, CRC, Unused, Unused, Unused, Unused, Unused, Unused

Reads returns 32 bytes, Write expects 32 bytes as well but address must be aligned to a memory-map section start address and will only write to that section
"""

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'TE923'
DRIVER_VERSION = '0.15'

def loader(config_dict, engine):
    return TE923Driver(**config_dict[DRIVER_NAME])

def configurator_loader(config_dict):
    return TE923Configurator()

def confeditor_loader():
    return TE923ConfEditor()


DEBUG_READ = 0
DEBUG_WRITE = 0
DEBUG_DECODE = 0
DEBUG_MEMORY = 0
DEBUG_PRESSURE = 0

# map the 5 remote sensors to columns in the database schema
DEFAULT_SENSOR_MAP = {
    'outTemp':     't_1',
    'outHumidity': 'h_1',
    'extraTemp1':  't_2',
    'extraHumid1': 'h_2',
    'extraTemp2':  't_3',
    'extraHumid2': 'h_3',
    'extraTemp3':  't_4',
    # WARNING: the following are not in the default schema
    'extraHumid3': 'h_4',
    'extraTemp4':  't_5',
    'extraHumid4': 'h_5',
}

DEFAULT_BATTERY_MAP = {
    'txBatteryStatus':      'batteryUV',
    'windBatteryStatus':    'batteryWind',
    'rainBatteryStatus':    'batteryRain',
    'outTempBatteryStatus': 'battery1',
    # WARNING: the following are not in the default schema
    'extraBatteryStatus1':  'battery2',
    'extraBatteryStatus2':  'battery3',
    'extraBatteryStatus3':  'battery4',
    'extraBatteryStatus4':  'battery5',
}

def logmsg(dst, msg):
    syslog.syslog(dst, 'te923: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


class TE923ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[TE923]
    # This section is for the Hideki TE923 series of weather stations.

    # The station model, e.g., 'Meade TE923W' or 'TFA Nexus'
    model = TE923

    # The driver to use:
    driver = weewx.drivers.te923

    # The default configuration associates the channel 1 sensor with outTemp
    # and outHumidity.  To change this, or to associate other channels with
    # specific columns in the database schema, use the following maps.
    [[sensor_map]]
        # Map the remote sensors to columns in the database schema.
        outTemp =     t_1
        outHumidity = h_1
        extraTemp1 =  t_2
        extraHumid1 = h_2
        extraTemp2 =  t_3
        extraHumid2 = h_3
        extraTemp3 =  t_4
        # WARNING: the following are not in the default schema
        extraHumid3 = h_4
        extraTemp4 =  t_5
        extraHumid4 = h_5

    [[battery_map]]
        txBatteryStatus =      batteryUV
        windBatteryStatus =    batteryWind
        rainBatteryStatus =    batteryRain
        outTempBatteryStatus = battery1
        # WARNING: the following are not in the default schema
        extraBatteryStatus1 =  battery2
        extraBatteryStatus2 =  battery3
        extraBatteryStatus3 =  battery4
        extraBatteryStatus4 =  battery5
"""


class TE923Configurator(weewx.drivers.AbstractConfigurator):

    dst_dict = {
        0: ["NO", 'None'],
        1: ["SA", 'Australian'],
        2: ["SB", 'Brazilian'],
        3: ["SC", 'Chilian'],
        4: ["SE", 'European'],
        5: ["SG", 'Eqyptian'],
        6: ["SI", 'Cuban'],
        7: ["SJ", 'Iraq and Syria'],
        8: ["SK", 'Irkutsk and Moscow'],
        9: ["SM", 'Uruguayan'],
       10: ["SN", 'Nambian'],
       11: ["SP", 'Paraguayan'],
       12: ["SQ", 'Iranian'],
       13: ["ST", 'Tasmanian'],
       14: ["SU", 'American'],
       15: ["SZ", 'New Zealand'],
    }
    
    city_dict = {
        0 : ["ADD", 3, 0, 9, 01, "N", 38, 44, "E", "Addis Ababa, Ethiopia"],
        1 : ["ADL", 9.5, 1, 34, 55, "S", 138, 36, "E", "Adelaide, Australia"],
        2 : ["AKR", 2, 4, 39, 55, "N", 32, 55, "E", "Ankara, Turkey"],
        3 : ["ALG", 1, 0, 36, 50, "N", 3, 0, "E", "Algiers, Algeria"],
        4 : ["AMS", 1, 4, 52, 22, "N", 4, 53, "E", "Amsterdam, Netherlands"],
        5 : ["ARN", 1, 4, 59, 17, "N", 18, 3, "E", "Stockholm Arlanda, Sweden"],
        6 : ["ASU", -3, 11, 25, 15, "S", 57, 40, "W", "Asuncion, Paraguay"],
        7 : ["ATH", 2, 4, 37, 58, "N", 23, 43, "E", "Athens, Greece"],
        8 : ["ATL", -5, 14, 33, 45, "N", 84, 23, "W", "Atlanta, Ga."],
        9 : ["AUS", -6, 14, 30, 16, "N", 97, 44, "W", "Austin, Tex."],
       10 : ["BBU", 2, 4, 44, 25, "N", 26, 7, "E", "Bucharest, Romania"],
       11 : ["BCN", 1, 4, 41, 23, "N", 2, 9, "E", "Barcelona, Spain"],
       12 : ["BEG", 1, 4, 44, 52, "N", 20, 32, "E", "Belgrade, Yugoslavia"],
       13 : ["BEJ", 8, 0, 39, 55, "N", 116, 25, "E", "Beijing, China"],
       14 : ["BER", 1, 4, 52, 30, "N", 13, 25, "E", "Berlin, Germany"],
       15 : ["BHM", -6, 14, 33, 30, "N", 86, 50, "W", "Birmingham, Ala."],
       16 : ["BHX", 0, 4, 52, 25, "N", 1, 55, "W", "Birmingham, England"],
       17 : ["BKK", 7, 0, 13, 45, "N", 100, 30, "E", "Bangkok, Thailand"],
       18 : ["BNA", -6, 14, 36, 10, "N", 86, 47, "W", "Nashville, Tenn."],
       19 : ["BNE", 10, 0, 27, 29, "S", 153, 8, "E", "Brisbane, Australia"],
       20 : ["BOD", 1, 4, 44, 50, "N", 0, 31, "W", "Bordeaux, France"],
       21 : ["BOG", -5, 0, 4, 32, "N", 74, 15, "W", "Bogota, Colombia"],
       22 : ["BOS", -5, 14, 42, 21, "N", 71, 5, "W", "Boston, Mass."],
       23 : ["BRE", 1, 4, 53, 5, "N", 8, 49, "E", "Bremen, Germany"],
       24 : ["BRU", 1, 4, 50, 52, "N", 4, 22, "E", "Brussels, Belgium"],
       25 : ["BUA", -3, 0, 34, 35, "S", 58, 22, "W", "Buenos Aires, Argentina"],
       26 : ["BUD", 1, 4, 47, 30, "N", 19, 5, "E", "Budapest, Hungary"],
       27 : ["BWI", -5, 14, 39, 18, "N", 76, 38, "W", "Baltimore, Md."],
       28 : ["CAI", 2, 5, 30, 2, "N", 31, 21, "E", "Cairo, Egypt"],
       29 : ["CCS", -4, 0, 10, 28, "N", 67, 2, "W", "Caracas, Venezuela"],
       30 : ["CCU", 5.5, 0, 22, 34, "N", 88, 24, "E", "Calcutta, India (as Kolkata)"],
       31 : ["CGX", -6, 14, 41, 50, "N", 87, 37, "W", "Chicago, IL"],
       32 : ["CLE", -5, 14, 41, 28, "N", 81, 37, "W", "Cleveland, Ohio"],
       33 : ["CMH", -5, 14, 40, 0, "N", 83, 1, "W", "Columbus, Ohio"],
       34 : ["COR", -3, 0, 31, 28, "S", 64, 10, "W", "Cordoba, Argentina"],
       35 : ["CPH", 1, 4, 55, 40, "N", 12, 34, "E", "Copenhagen, Denmark"],
       36 : ["CPT", 2, 0, 33, 55, "S", 18, 22, "E", "Cape Town, South Africa"],
       37 : ["CUU", -6, 14, 28, 37, "N", 106, 5, "W", "Chihuahua, Mexico"],
       38 : ["CVG", -5, 14, 39, 8, "N", 84, 30, "W", "Cincinnati, Ohio"],
       39 : ["DAL", -6, 14, 32, 46, "N", 96, 46, "W", "Dallas, Tex."],
       40 : ["DCA", -5, 14, 38, 53, "N", 77, 2, "W", "Washington, D.C."],
       41 : ["DEL", 5.5, 0, 28, 35, "N", 77, 12, "E", "New Delhi, India"],
       42 : ["DEN", -7, 14, 39, 45, "N", 105, 0, "W", "Denver, Colo."],
       43 : ["DKR", 0, 0, 14, 40, "N", 17, 28, "W", "Dakar, Senegal"],
       44 : ["DTW", -5, 14, 42, 20, "N", 83, 3, "W", "Detroit, Mich."],
       45 : ["DUB", 0, 4, 53, 20, "N", 6, 15, "W", "Dublin, Ireland"],
       46 : ["DUR", 2, 0, 29, 53, "S", 30, 53, "E", "Durban, South Africa"],
       47 : ["ELP", -7, 14, 31, 46, "N", 106, 29, "W", "El Paso, Tex."],
       48 : ["FIH", 1, 0, 4, 18, "S", 15, 17, "E", "Kinshasa, Congo"],
       49 : ["FRA", 1, 4, 50, 7, "N", 8, 41, "E", "Frankfurt, Germany"],
       50 : ["GLA", 0, 4, 55, 50, "N", 4, 15, "W", "Glasgow, Scotland"],
       51 : ["GUA", -6, 0, 14, 37, "N", 90, 31, "W", "Guatemala City, Guatemala"],
       52 : ["HAM", 1, 4, 53, 33, "N", 10, 2, "E", "Hamburg, Germany"],
       53 : ["HAV", -5, 6, 23, 8, "N", 82, 23, "W", "Havana, Cuba"],
       54 : ["HEL", 2, 4, 60, 10, "N", 25, 0, "E", "Helsinki, Finland"],
       55 : ["HKG", 8, 0, 22, 20, "N", 114, 11, "E", "Hong Kong, China"],
       56 : ["HOU", -6, 14, 29, 45, "N", 95, 21, "W", "Houston, Tex."],
       57 : ["IKT", 8, 8, 52, 30, "N", 104, 20, "E", "Irkutsk, Russia"],
       58 : ["IND", -5, 0, 39, 46, "N", 86, 10, "W", "Indianapolis, Ind."],
       59 : ["JAX", -5, 14, 30, 22, "N", 81, 40, "W", "Jacksonville, Fla."],
       60 : ["JKT", 7, 0, 6, 16, "S", 106, 48, "E", "Jakarta, Indonesia"],
       61 : ["JNB", 2, 0, 26, 12, "S", 28, 4, "E", "Johannesburg, South Africa"],
       62 : ["KIN", -5, 0, 17, 59, "N", 76, 49, "W", "Kingston, Jamaica"],
       63 : ["KIX", 9, 0, 34, 32, "N", 135, 30, "E", "Osaka, Japan"],
       64 : ["KUL", 8, 0, 3, 8, "N", 101, 42, "E", "Kuala Lumpur, Malaysia"],
       65 : ["LAS", -8, 14, 36, 10, "N", 115, 12, "W", "Las Vegas, Nev."],
       66 : ["LAX", -8, 14, 34, 3, "N", 118, 15, "W", "Los Angeles, Calif."],
       67 : ["LIM", -5, 0, 12, 0, "S", 77, 2, "W", "Lima, Peru"],
       68 : ["LIS", 0, 4, 38, 44, "N", 9, 9, "W", "Lisbon, Portugal"],
       69 : ["LON", 0, 4, 51, 32, "N", 0, 5, "W", "London, England"],
       70 : ["LPB", -4, 0, 16, 27, "S", 68, 22, "W", "La Paz, Bolivia"],
       71 : ["LPL", 0, 4, 53, 25, "N", 3, 0, "W", "Liverpool, England"],
       72 : ["LYO", 1, 4, 45, 45, "N", 4, 50, "E", "Lyon, France"],
       73 : ["MAD", 1, 4, 40, 26, "N", 3, 42, "W", "Madrid, Spain"],
       74 : ["MEL", 10, 1, 37, 47, "S", 144, 58, "E", "Melbourne, Australia"],
       75 : ["MEM", -6, 14, 35, 9, "N", 90, 3, "W", "Memphis, Tenn."],
       76 : ["MEX", -6, 14, 19, 26, "N", 99, 7, "W", "Mexico City, Mexico"],
       77 : ["MIA", -5, 14, 25, 46, "N", 80, 12, "W", "Miami, Fla."],
       78 : ["MIL", 1, 4, 45, 27, "N", 9, 10, "E", "Milan, Italy"],
       79 : ["MKE", -6, 14, 43, 2, "N", 87, 55, "W", "Milwaukee, Wis."],
       80 : ["MNL", 8, 0, 14, 35, "N", 120, 57, "E", "Manila, Philippines"],
       81 : ["MOW", 3, 8, 55, 45, "N", 37, 36, "E", "Moscow, Russia"],
       82 : ["MRS", 1, 4, 43, 20, "N", 5, 20, "E", "Marseille, France"],
       83 : ["MSP", -6, 14, 44, 59, "N", 93, 14, "W", "Minneapolis, Minn."],
       84 : ["MSY", -6, 14, 29, 57, "N", 90, 4, "W", "New Orleans, La."],
       85 : ["MUC", 1, 4, 48, 8, "N", 11, 35, "E", "Munich, Germany"],
       86 : ["MVD", -3, 9, 34, 53, "S", 56, 10, "W", "Montevideo, Uruguay"],
       87 : ["NAP", 1, 4, 40, 50, "N", 14, 15, "E", "Naples, Italy"],
       88 : ["NBO", 3, 0, 1, 25, "S", 36, 55, "E", "Nairobi, Kenya"],
       89 : ["NKG", 8, 0, 32, 3, "N", 118, 53, "E", "Nanjing (Nanking), China"],
       90 : ["NYC", -5, 14, 40, 47, "N", 73, 58, "W", "New York, N.Y."],
       91 : ["ODS", 2, 4, 46, 27, "N", 30, 48, "E", "Odessa, Ukraine"],
       92 : ["OKC", -6, 14, 35, 26, "N", 97, 28, "W", "Oklahoma City, Okla."],
       93 : ["OMA", -6, 14, 41, 15, "N", 95, 56, "W", "Omaha, Neb."],
       94 : ["OSL", 1, 4, 59, 57, "N", 10, 42, "E", "Oslo, Norway"],
       95 : ["PAR", 1, 4, 48, 48, "N", 2, 20, "E", "Paris, France"],
       96 : ["PDX", -8, 14, 45, 31, "N", 122, 41, "W", "Portland, Ore."],
       97 : ["PER", 8, 0, 31, 57, "S", 115, 52, "E", "Perth, Australia"],
       98 : ["PHL", -5, 14, 39, 57, "N", 75, 10, "W", "Philadelphia, Pa."],
       99 : ["PHX", -7, 0, 33, 29, "N", 112, 4, "W", "Phoenix, Ariz."],
      100 : ["PIT", -5, 14, 40, 27, "N", 79, 57, "W", "Pittsburgh, Pa."],
      101 : ["PRG", 1, 4, 50, 5, "N", 14, 26, "E", "Prague, Czech Republic"],
      102 : ["PTY", -5, 0, 8, 58, "N", 79, 32, "W", "Panama City, Panama"],
      103 : ["RGN", 6.5, 0, 16, 50, "N", 96, 0, "E", "Rangoon, Myanmar"],
      104 : ["RIO", -3, 2, 22, 57, "S", 43, 12, "W", "Rio de Janeiro, Brazil"],
      105 : ["RKV", 0, 0, 64, 4, "N", 21, 58, "W", "Reykjavik, Iceland"],
      106 : ["ROM", 1, 4, 41, 54, "N", 12, 27, "E", "Rome, Italy"],
      107 : ["SAN", -8, 14, 32, 42, "N", 117, 10, "W", "San Diego, Calif."],
      108 : ["SAT", -6, 14, 29, 23, "N", 98, 33, "W", "San Antonio, Tex."],
      109 : ["SCL", -4, 3, 33, 28, "S", 70, 45, "W", "Santiago, Chile"],
      110 : ["SEA", -8, 14, 47, 37, "N", 122, 20, "W", "Seattle, Wash."],
      111 : ["SFO", -8, 14, 37, 47, "N", 122, 26, "W", "San Francisco, Calif."],
      112 : ["SHA", 8, 0, 31, 10, "N", 121, 28, "E", "Shanghai, China"],
      113 : ["SIN", 8, 0, 1, 14, "N", 103, 55, "E", "Singapore, Singapore"],
      114 : ["SJC", -8, 14, 37, 20, "N", 121, 53, "W", "San Jose, Calif."],
      115 : ["SOF", 2, 4, 42, 40, "N", 23, 20, "E", "Sofia, Bulgaria"],
      116 : ["SPL", -3, 2, 23, 31, "S", 46, 31, "W", "Sao Paulo, Brazil"],
      117 : ["SSA", -3, 0, 12, 56, "S", 38, 27, "W", "Salvador, Brazil"],
      118 : ["STL", -6, 14, 38, 35, "N", 90, 12, "W", "St. Louis, Mo."],
      119 : ["SYD", 10, 1, 34, 0, "S", 151, 0, "E", "Sydney, Australia"],
      120 : ["TKO", 9, 0, 35, 40, "N", 139, 45, "E", "Tokyo, Japan"],
      121 : ["TPA", -5, 14, 27, 57, "N", 82, 27, "W", "Tampa, Fla."],
      122 : ["TRP", 2, 0, 32, 57, "N", 13, 12, "E", "Tripoli, Libya"],
      123 : ["USR", 0, 0, 0, 0, "N", 0, 0, "W", "User defined city"],
      124 : ["VAC", -8, 14, 49, 16, "N", 123, 7, "W", "Vancouver, Canada"],
      125 : ["VIE", 1, 4, 48, 14, "N", 16, 20, "E", "Vienna, Austria"],
      126 : ["WAW", 1, 4, 52, 14, "N", 21, 0, "E", "Warsaw, Poland"],
      127 : ["YMX", -5, 14, 45, 30, "N", 73, 35, "W", "Montreal, Que., Can."],
      128 : ["YOW", -5, 14, 45, 24, "N", 75, 43, "W", "Ottawa, Ont., Can."],
      129 : ["YTZ", -5, 14, 43, 40, "N", 79, 24, "W", "Toronto, Ont., Can."],
      130 : ["YVR", -8, 14, 49, 13, "N", 123, 6, "W", "Vancouver, B.C., Can."],
      131 : ["YYC", -7, 14, 51, 1, "N", 114, 1, "W", "Calgary, Alba., Can."],
      132 : ["ZRH", 1, 4, 47, 21, "N", 8, 31, "E", "Zurich, Switzerland"]
    }
      
    @property
    def version(self):
        return DRIVER_VERSION

    # TODO: Set the date, location, altitude & alarms
    
    def add_options(self, parser):
        super(TE923Configurator, self).add_options(parser)
        parser.add_option("--info", dest="info", action="store_true",
                          help="display weather station configuration")
        parser.add_option("--current", dest="current", action="store_true",
                          help="get the current weather conditions")
        parser.add_option("--history", dest="nrecords", type=int, metavar="N",
                          help="display N history records")
        parser.add_option("--history-since", dest="recmin",
                          type=int, metavar="N",
                          help="display history records since N minutes ago")
        parser.add_option("--history-extra", dest="extra", action="store_true",
                          help="display extra history values")
        parser.add_option("--get-date", dest="getdate", action="store_true",
                          help="display date")
        parser.add_option("--set-date", dest="setdate", type=str, metavar="YEAR,MONTH,DAY",
                          help="writes date")
        parser.add_option("--get-location-local", dest="getloc_local", action="store_true",
                          help="display local location and timezone")
        parser.add_option("--set-location-local", dest="setloc_local", type=str, metavar="CITY or USR,LONG_DEG,LONG_MIN,E or W,LAT_DEG,LAT_MIN,N or S,TZ,DST",
                          help="writes local location and timezone")
        parser.add_option("--get-location-alt", dest="getloc_alt", action="store_true",
                          help="display alternate location and timezone")
        parser.add_option("--set-location-alt", dest="setloc_alt", type=str, metavar="CITY or USR,LONG_DEG,LONG_MIN,E or W,LAT_DEG,LAT_MIN,N or S,TZ,DST",
                          help="writes alternate location and timezone")
        parser.add_option("--get-altitude", dest="getalt", action="store_true",
                          help="display altitude")
        parser.add_option("--set-altitude", dest="setalt", type=int, metavar="ALT",
                          help="writes altitude")
        parser.add_option("--get-alarms", dest="getalarm", action="store_true",
                          help="display alarm state")
        parser.add_option("--set-alarms", dest="setalarm", type=str, metavar="WEEK,SINGLE,PRE,SNOOZE,MAXTEMP,MINTEMP,RAIN,WIND,GUST",
                          help="writes alarm state")
        parser.add_option("--get-interval", dest="getinterval", action="store_true",
                          help="display archive interval")
        parser.add_option("--set-interval", dest="setinterval", type=str, metavar="INTERVAL",
                          help="writes archive interval")
        parser.add_option("--format", dest="format",
                          type=str, metavar="FORMAT",
                          help="format for history: raw, table, or dict")

    def do_options(self, options, parser, config_dict, prompt):
        if options.format is None:
            options.format = 'table'
        elif (options.format.lower() != 'raw' and
              options.format.lower() != 'table' and
              options.format.lower() != 'dict'):
            parser.error("Unknown format '%s'.  Known formats include 'raw', 'table', and 'dict'." % options.format)

        self.station = TE923Driver(**config_dict[DRIVER_NAME])
        if options.current:
            self.show_current()
        elif options.nrecords is not None:
            self.show_history(count=options.nrecords, fmt=options.format)
        elif options.recmin is not None:
            ts = int(time.time()) - options.recmin * 60
            self.show_history(ts=ts, fmt=options.format)
        elif options.extra is not None:
            self.extra_history()
        elif options.getdate is not None:
            self.get_date()
        elif options.setdate is not None:
            self.set_date(options.setdate)
        elif options.getloc_local is not None:
            self.get_location(0)
        elif options.setloc_local is not None:
            self.set_location(0, options.setloc_local)
        elif options.getloc_alt is not None:
            self.get_location(1)
        elif options.setloc_alt is not None:
            self.set_location(1, options.setloc_alt)
        elif options.getalt is not None:
            self.get_altitude()
        elif options.setalt is not None:
            self.set_altitude(options.setalt)
        elif options.getalarm is not None:
            self.get_alarm()
        elif options.setalarm is not None:
            self.set_alarm(options.setalarm)
        elif options.getinterval is not None:
            self.get_interval()
        elif options.setinterval is not None:
            self.set_interval(options.setinterval)
        elif options.info is not None:
            self.show_info()
        self.station.closePort()

    def show_info(self):
        """Query the station then display the settings."""
        print 'Querying the station for the configuration...'
        config = self.station.getConfig()
        for key in sorted(config):
            print '%s: %s' % (key, config[key])

    def show_current(self):
        """Get current weather observation."""
        print 'Querying the station for current weather data...'
        for packet in self.station.genLoopPackets():
            print packet
            break

    def show_history(self, ts=0, count=0, fmt='raw'):
        """Show the indicated number of records or records since timestamp"""
        print "Querying the station for historical records..."
        for r in self.station.genStartupRecords(ts, count):
            if fmt.lower() == 'raw':
                self.print_raw(r)
            elif fmt.lower() == 'table':
                self.print_table(r)
            else:
                print r

    def extra_history(self):
        """Shows extra history values not used by weewx"""
        buf = self.station.get_extra_history()
        print "Querying the station for extra history data"
        print "Min Inside Temperature        : %s" % self.decode_temp(buf[1], buf[2], 0)
        print "Max Inside Temperature        : %s" % self.decode_temp(buf[3], buf[4], 0)
        print "Min Inside Humidity           : %s" % self.decode_humid(buf[5])
        print "Max Inside Humidity           : %s" % self.decode_humid(buf[6])
        for i in range(5):
            print "Min Channel %d Temperature     : %s" % (i + 1, self.decode_temp(buf[7 + i * 6], buf[8 + i * 6], 1))
            print "Max Channel %d Temperature     : %s" % (i + 1, self.decode_temp(buf[9 + i * 6], buf[10 + i * 6], 1))
            print "Min Channel %d Humidity        : %s" % (i + 1, self.decode_humid(buf[11 + i * 6]))
            print "Max Channel %d Humidity        : %s" % (i + 1, self.decode_humid(buf[12 + i * 6]))
        print "Max wind speed since midnight : %s" % self.decode_wind(buf[37], buf[38])
        print "Max wind gust  since midnight : %s" % self.decode_wind(buf[39], buf[40])
        print "Rain yesterday                : %s" % (buf[42] * 0x100 + buf[41] * 0.6578)
        print "Rain this week                : %s" % (buf[44] * 0x100 + buf[43] * 0.6578)
        print "Rain this month               : %s" % (buf[46] * 0x100 + buf[45] * 0.6578)
        print
        print "Last Barometer reading : %02d/%02d %02d:%02d" % (bcd2int(buf[48]), bcd2int(buf[47] & 0xf), bcd2int(buf[49]), bcd2int(buf[50]))
        for i in range(25):
            print "   T-%02d Hours      : %.1f" % (i, (buf[52 + i * 2] * 0x100 + buf[51 + i * 2]) * 0.0625)

    def checksum(self, buf):
        crc = 0x100
        for i in range(len(buf)):
           crc -= buf[i]
           if crc < 0:
               crc += 0x100
        return crc
  
    def get_date(self):
        tt = time.localtime()
        offset = 1 if tt[3] < 12 else 0
        buf = self.station.get_date()
        day = rev_bcd2int(buf[2])
        month = (buf[5] & 0xF0) / 0x10
        year = rev_bcd2int(buf[4]) + 2000
        ts = time.mktime((year, month, day + offset, 0, 0, 0, 0, 0, 0))
        tt = time.localtime(ts)
        print "Date: %02d/%02d/%d" % (tt[2], tt[1], tt[0])
        print "NB: If computer time is not aligned to station time then date may be incorrect by 1 day"

    def set_date(self, date):
        date_list = date.split(',')
        if len(date_list) != 3:
            print "Error: Incorrect date format - YEAR,MONTH,DAY"
            return
        if int(date_list[0]) < 2000 or int(date_list[0]) > 2099:
            print "Error: Year must be between 2000 and 2099 inclusive"
            return
        if int(date_list[1]) < 1 or int(date_list[1]) > 12:
            print "Error: Month must be between 1 and 12 inclusive"
            return
        if int(date_list[2]) < 1 or int(date_list[2]) > 31:
            print "Error: Day must be between 1 and 31 inclusive"
            return
        tt = time.localtime()
        offset = 1 if tt[3] < 12 else 0
        ts = time.mktime((int(date_list[0]), int(date_list[1]), int(date_list[2]) - offset, 0, 0, 0, 0, 0, 0))
        tt = time.localtime(ts)
        buf = self.station.get_date()
        buf[2] = rev_int2bcd(tt[2])
        buf[4] = rev_int2bcd(tt[0] - 2000)
        buf[5] = tt[1] * 0x10 + (tt[6] + 1) * 2 + (buf[5] & 1)
        buf[15] = self.checksum(buf[0:15])
        print "NB: If computer time is not aligned to station time then date may be incorrect by 1 day"
        self.station.set_date(buf)

    def get_location(self, loc_type):
        buf = self.station.get_loc(loc_type)
        if loc_type == 0:
            offset = 6
        else:
            offset = 0
        city_time = (buf[6 + offset] & 0xF0) + (buf[7 + offset] & 0xF)
        print "City     : %s (%s)" % (self.city_dict[city_time][9], self.city_dict[city_time][0])
        lat_deg = rev_bcd2int(buf[0 + offset])
        lat_min = rev_bcd2int(buf[1 + offset])
        lat_dir = "S" if buf[4 + offset] & 0x80 == 0x80 else "N"
        long_deg = (buf[5 + offset] & 0xF0) / 0x10 * 100 + rev_bcd2int(buf[2 + offset])
        long_min = rev_bcd2int(buf[3 + offset])
        long_dir = "E" if buf[4 + offset] & 0x40 == 0x40 else "W"
        degree_sign= u'\N{DEGREE SIGN}'
        print "Location : %03d%s%02d'%s, %02d%s%02d'%s" % (long_deg, degree_sign, long_min, long_dir, lat_deg, degree_sign, lat_min, lat_dir)
        tz_hr = (buf[7 + offset] & 0xF0) / 0x10
        if buf[4 + offset] & 0x8 == 0x8:
           tz_hr *= -1
        tz_min = 30 if buf[4 + offset] & 0x3 == 0x3 else 0
        print "Timezone : %02d:%02d" % (tz_hr, tz_min)
        if buf[4 + offset] & 0x10 == 0x10:
            print "DST      : Always on"
        else:
            print "DST      : %s (%s)" % (self.dst_dict[buf[5 + offset] & 0xF][1], self.dst_dict[buf[5 + offset] & 0xF][0])

    def set_location(self, loc_type, location):
        location_list = location.split(',')
        if len(location_list) == 1 and location_list[0] != "USR":
            found = 0
            for city_index in range(133):
                if self.city_dict[city_index][0] == location_list[0]:
                   found = 1
                   break
            if found != 1:
                print "Error: City code not found - consult station manual for valid city codes"
                return
            long_deg = self.city_dict[city_index][6]
            long_min = self.city_dict[city_index][7]
            long_dir = self.city_dict[city_index][8]
            lat_deg = self.city_dict[city_index][3]
            lat_min = self.city_dict[city_index][4]
            lat_dir = self.city_dict[city_index][5]
            tz_hr = int(self.city_dict[city_index][1])
            tz_min = 0 if self.city_dict[city_index][1] == int(self.city_dict[city_index][1]) else 30
            dst_on = 0
            dst_index = self.city_dict[city_index][2]
        elif len(location_list) == 9 and location_list[0] == "USR":
            if int(location_list[1]) < 0 or int(location_list[1]) > 180:
                print "Error: Longitude degrees must be between 0 and 180 inclusive"
                return
            if int(location_list[2]) < 0 or int(location_list[2]) > 180:
                print "Error: Longitude minutes must be between 0 and 59 inclusive"
                return
            if location_list[3] != "E" and location_list[3] != "W":
                print "Error: Longitude direction must be E or W"
                return
            if int(location_list[4]) < 0 or int(location_list[4]) > 180:
                print "Error: Latitude degrees must be between 0 and 90 inclusive"
                return
            if int(location_list[5]) < 0 or int(location_list[5]) > 180:
                print "Error: Latitude minutes must be between 0 and 59 inclusive"
                return
            if location_list[6] != "N" and location_list[6] != "S":
                print "Error: Longitude direction must be N or S"
                return
            tz_list = location_list[7].split(':')
            if len(tz_list) != 2:
                print "Error: Incorrect timezone format - HOUR:MINUTE"
                return
            if int(tz_list[0]) < -12 or int(tz_list[0]) > 12:
                print "Error: Timezone hours must be between -12 and 12 inclusive"
                return
            if int(tz_list[1]) != 0 and int(tz_list[1]) != 30:
                print "Error: Timezone minutes must be 0 or 30"
                return
            if location_list[8] != 'ON':
               dst_on = 0
               found = 0
               for dst_index in range(16):
                  if self.dst_dict[dst_index][0] == location_list[8]:
                     found = 1
                     break
               if found != 1:
                  print "Error: DST code not found - consult station manual for valid DST codes"
                  return
            else:
               dst_index = 0
               dst_on = 1
            city_index = 123
            long_deg = int(location_list[1])
            long_min = int(location_list[2])
            long_dir = location_list[3]
            lat_deg = int(location_list[4])
            lat_min = int(location_list[5])
            lat_dir = location_list[6]
            tz_hr = int(tz_list[0])
            tz_min = int(tz_list[1])
        else:
            print "Error: Incorrect location format - CITY or USR,LONGITUDE DEGREE,LONGITUDE MINUTE,E or W,LATATITUDE DEGREE,LATITUDE MINUTE,N or S,TIMEZONE,DST"
            return
            
        buf = self.station.get_loc(loc_type)
        if loc_type == 0:
            offset = 6
        else:
            offset = 0
        buf[0 + offset] = rev_int2bcd(lat_deg)
        buf[1 + offset] = rev_int2bcd(lat_min)
        buf[2 + offset] = rev_int2bcd(long_deg % 100)
        buf[3 + offset] = rev_int2bcd(long_min)
        buf[4 + offset] = (lat_dir == "S") * 0x80 + (long_dir == "E") * 0x40 + (tz_hr < 0) + dst_on * 0x10 * 0x8 + (tz_min == 30) * 3
        buf[5 + offset] = (long_deg > 99) * 0x10 + dst_index
        buf[6 + offset] = (buf[28] & 0x0F) + int(city_index / 0x10) * 0x10 
        buf[7 + offset] = city_index % 0x10 + abs(tz_hr) * 0x10
        if loc_type == 0:
           buf[15] = self.checksum(buf[0:15])
        else:
           buf[8] = self.checksum(buf[0:8])
        self.station.set_loc(loc_type, buf)

    def get_altitude(self):
         buf = self.station.get_alt()
         altitude = buf[1] * 0x100 + buf[0]
         if buf[3] & 0x8 == 0x8:
             altitude *= -1
         print "Altitude = %d m" % altitude

    def set_altitude(self, altitude):
         if altitude < -200 or altitude > 5000:
             print "Error: Altitude must be between -200 and 5000 inclusive"
             return
         buf = self.station.get_alt()
         buf[0] = abs(altitude) & 0xff
         buf[1] = abs(altitude) / 0x100
         buf[2] = buf[2] & 0x7 + (altitude < 0) * 0x8
         buf[3] = self.checksum(buf[0:3])
         self.station.set_alt(buf)
    
    def get_alarm(self):
        buf = self.station.get_alarms()
        weekday = "Active" if buf[0] & 0x4 == 0x4 else "Inactive"
        single = "Active" if buf[0] & 0x8 == 0x8 else "Inactive"
        prealarm = "Active" if buf[2] & 0x8 == 0x8 else "Inactive"
        print "Weekday alarm : %02d:%02d (%s)" % (rev_bcd2int(buf[0] & 0xF1), rev_bcd2int(buf[1]), weekday)
        print "Single  alarm : %02d:%02d (%s)" % (rev_bcd2int(buf[2] & 0xF1), rev_bcd2int(buf[3]), single)
        if (buf[4] & 0xF0) / 0x10 == 1:
            print "Pre-alarm     : 15 mins (%s)" % prealarm
        elif (buf[4] & 0xF0) / 0x10 == 2:
            print "Pre-alarm     : 30 mins (%s)" % prealarm
        elif (buf[4] & 0xF0) / 0x10 == 3:
            print "Pre-alarm     : 45 mins (%s)" % prealarm
        elif (buf[4] & 0xF0) / 0x10 == 4:
            print "Pre-alarm     : 60 mins (%s)" % prealarm
        elif (buf[4] & 0xF0) / 0x10 == 5:
            print "Pre-alarm     : 90 mins (%s)" % prealarm
        else:
            print "Pre-alarm     : Invalid (%s)" % prealarm
        if buf[4] & 0xF > 0:
            print "Snooze        : %d mins" % (buf[4] & 0xF)
        else:
            print "Snooze        : Invalid"
        print
        print "Max Temperature Alarm : %s" % self.decode_temp(buf[32], buf[33], 0)
        print "Min Temperature Alarm : %s" % self.decode_temp(buf[34], buf[35], 0)
        print "NB: Temperature alarms can only be activted/de-activated via station controls"
        rain = "Active" if buf[64] & 0x4 == 0x4 else "Inactive"
        wind = "Active" if buf[64] & 0x2 == 0x2 else "Inactive"
        gust = "Active" if buf[64] & 0x1 == 0x1 else "Inactive"
        print "Rain Alarm            : %d mm (%s)" % (bcd2int(buf[66]) * 100 + bcd2int(buf[65]), rain)
        print "Wind Speed Alarm      : %s (%s)" % (self.decode_wind(buf[68], buf[69]), wind)
        print "Wind Gust  Alarm      : %s (%s)" % (self.decode_wind(buf[71], buf[72]), gust)
         
    def set_alarm(self, alarm):
        alarm_list = alarm.split(',')
        if len(alarm_list) != 9:
            print "Error: Incorrect alarm format - WEEKDAY,SINGLE,PRE-ALARM,SNOOZE,MAX TEMPERATURE,MIN TEMPERATURE,RAIN,WIND SPEED,WIND GUST"
            return
        weekday = alarm_list[0]
        if weekday.lower() != 'off':
            weekday_list = weekday.split(':')
            if len(weekday_list) != 2:
                print "Error: Incorrect alarm format - HOUR:MINUTE or OFF"
                return
            if int(weekday_list[0]) < 0 or int(weekday_list[0]) > 23:
                print "Error: Alarm hours must be between 0 and 23 inclusive"
                return
            if int(weekday_list[1]) < 0 or int(weekday_list[1]) > 59:
                print "Error: Alarm minutes must be between 0 and 59 inclusive"
                return
        single = alarm_list[1]
        if single.lower() != 'off':
            single_list = single.split(':')
            if len(single_list) != 2:
                print "Error: Incorrect alarm format - HOUR:MINUTE or OFF"
                return
            if int(single_list[0]) < 0 or int(single_list[0]) > 23:
                print "Error: Alarm hours must be between 0 and 23 inclusive"
                return
            if int(single_list[1]) < 0 or int(single_list[1]) > 59:
                print "Error: Alarm minutes must be between 0 and 59 inclusive"
                return
        if alarm_list[2].lower() != 'off' and alarm_list[2] != '15' and alarm_list[2] != '30' and alarm_list[2] != '45' and alarm_list[2] != '60' and alarm_list[2] != '90':
            print "Error: Prealarm must be 15, 30, 45, 60, 90 or OFF"
            return
        if int(alarm_list[3]) < 1 or int(alarm_list[3]) > 15:
            print "Error: Snooze must be between 1 and 15 inclusive"
            return
        if float(alarm_list[4]) < -50 or float(alarm_list[4]) > 70:
            print "Error: Temperature alarm must be between -50 and 70 inclusive"
            return
        if float(alarm_list[5]) < -50 or float(alarm_list[5]) > 70:
            print "Error: Temperature alarm must be between -50 and 70 inclusive"
            return
        if alarm_list[6].lower() != 'off' and (int(alarm_list[6]) < 1 or int(alarm_list[6]) > 9999):
            print "Error: Rain alarm must be between 1 and 999 inclusive or OFF"
            return
        if alarm_list[7].lower() != 'off' and (float(alarm_list[7]) < 1 or float(alarm_list[7]) > 199):
            print "Error: Wind alarm must be between 1 and 199 inclusive or OFF"
            return
        if alarm_list[8].lower() != 'off' and (float(alarm_list[8]) < 1 or float(alarm_list[8]) > 199):
            print "Error: Wind alarm must be between 1 and 199 inclusive or OFF"
            return
        
        buf = self.station.get_alarms()
        if weekday.lower() != 'off':
            buf[0] = rev_int2bcd(int(weekday_list[0])) | 0x4
            buf[1] = rev_int2bcd(int(weekday_list[1]))
        else:
            buf[0] = buf[0] & 0xFB
        if single.lower() != 'off':
            buf[2] = rev_int2bcd(int(single_list[0]))
            buf[3] = rev_int2bcd(int(single_list[1]))
            buf[0] = buf[0] | 0x8
        else:
            buf[0] = buf[0] & 0xF7
        if alarm_list[2].lower() != 'off' and (weekday.lower() != 'off' or single.lower() != 'off'):
            if int(alarm_list[2]) == 15:
               buf[4] = 0x10
            elif int(alarm_list[2]) == 30:
               buf[4] = 0x20
            elif int(alarm_list[2]) == 45:
               buf[4] = 0x30
            elif int(alarm_list[2]) == 60:
               buf[4] = 0x40
            elif int(alarm_list[2]) == 90:
               buf[4] = 0x50
            buf[2] = buf[2] | 0x8
        else:
            buf[2] = buf[2] & 0xF7
        buf[4] = (buf[4] & 0xF0) + int(alarm_list[3])
        buf[5] = self.checksum(buf[0:5])

        buf[32] = int2bcd(int(abs(float(alarm_list[4])) * 10) % 100)
        buf[33] = int2bcd(int(abs(float(alarm_list[4])) / 10))
        if float(alarm_list[4]) >= 0:
            buf[33] = buf[33] | 0x80
        if (abs(float(alarm_list[4])) * 100) % 10 == 5:
            buf[33] = buf[33] | 0x20
        buf[34] = int2bcd(int(abs(float(alarm_list[5])) * 10) % 100)
        buf[35] = int2bcd(int(abs(float(alarm_list[5])) / 10))
        if float(alarm_list[5]) >= 0:
            buf[35] = buf[35] | 0x80
        if (abs(float(alarm_list[5])) * 100) % 10 == 5:
            buf[35] = buf[35] | 0x20
        buf[36] = self.checksum(buf[32:36])

        if alarm_list[6].lower() != 'off':
            buf[65] = int2bcd(int(alarm_list[6]) % 100)
            buf[66] = int2bcd(int(int(alarm_list[6]) / 100))
            buf[64] = buf[64] | 0x4
        else:
            buf[64] = buf[64] & 0xFB
        if alarm_list[7].lower() != 'off':
            buf[68] = int2bcd(int(float(alarm_list[7]) * 10) % 100)
            buf[69] = int2bcd(int(float(alarm_list[7]) / 10))
            buf[64] = buf[64] | 0x2
        else:
            buf[64] = buf[64] & 0xFD
        if alarm_list[8].lower() != 'off':
            buf[71] = int2bcd(int(float(alarm_list[8]) * 10) % 100)
            buf[72] = int2bcd(int(float(alarm_list[8]) / 10))
            buf[64] = buf[64] | 0x1
        else:
            buf[64] = buf[64] & 0xFE
        buf[73] = self.checksum(buf[64:73])
        self.station.set_alarms(buf)
        print "NB: Temperature alarms can only be activted/de-activated via station controls"
         
    def get_interval(self):
        buf = self.station.get_interval()
        if buf[0] == 1:
            interval = "5 mins"
        elif buf[0] == 2:
            interval = "10 mins"
        elif buf[0] == 3:
            interval = "20 mins"
        elif buf[0] == 4:
            interval = "30 mins"
        elif buf[0] == 5:
            interval = "60 mins"
        elif buf[0] == 6:
            interval = "90 mins"
        elif buf[0] == 7:
            interval = "2 hours"
        elif buf[0] == 8:
            interval = "3 hours"
        elif buf[0] == 9:
            interval = "4 hours"
        elif buf[0] == 10:
            interval = "6 hours"
        elif buf[0] == 11:
            interval = "1 day"
        else:
            interval = "Unknown"
        print "Archive Interval = %s" % interval

    def set_interval(self, interval):
        if interval == "5m":
            value = 1
        elif interval == "10m":
            value = 2
        elif interval == "20m":
            value = 3
        elif interval == "30m":
            value = 4
        elif interval == "60m":
            value = 5
        elif interval == "90m":
            value = 6
        elif interval == "2h":
            value = 7
        elif interval == "3h":
            value = 8
        elif interval == "4h":
            value = 9
        elif interval == "6h":
            value = 10
        elif interval == "1d":
            value = 11
        else:
            print "Error: Allowed archive intervals are 5m, 10m, 20m, 30m, 60m, 90m, 2h, 3h, 4h, 6h & 1d"
            return
        buf = self.station.get_interval()
        buf[0] = value
        self.station.set_interval(buf)
    
    def decode_temp(self, byte1, byte2, outside):
        if bcd2int(byte1 & 0x0f) > 9:
            if byte1 & 0x0f == 0x0a:
                return "No link"
            else:
                return "Invalid"
        if byte2 & 0x40 != 0x40 and outside:
            return "Invalid"

        value = bcd2int(byte1) / 10.0 + bcd2int(byte2 & 0x0f) * 10.0
        if byte2 & 0x20 == 0x20:
            value += 0.05
        if byte2 & 0x80 != 0x80:
            value *= -1
        return "%.2f C" % value

    def decode_humid(self, byte):
        if bcd2int(byte & 0x0f) > 9:
            if byte & 0x0f == 0x0a:
                return "No link"
            else:
                return "Invalid"

        return "%d%%" % bcd2int(byte)

    def decode_wind(self, byte1, byte2):
        if bcd2int(byte1 & 0xf0) > 90 or bcd2int(byte1 & 0x0f) > 9:
            if (byte1 == 0xee and byte2 == 0x8e) or (byte1 == 0xff and byte2 == 0xff):
                return "No link"
            else:
                return "Invalid"
        offset = 100 if byte2 & 0x10 == 0x10 else 0
        value = bcd2int(byte1) / 10.0 + bcd2int(byte2 & 0x0f) * 10.0 + offset

        return "%.1f mph" % value

    def decode_rain(self, byte1, byte2):
        value = (byte2 * 0x100 + byte1) * 0.6578
        return "%.1f mm" % value

    @staticmethod
    def print_raw(data):
        output = [str(data['dateTime'])]
        output.append(str(getvalue(1, data['inTemp'], '%0.2f')))
        output.append(str(getvalue(1, data['inHumidity'], '%d')))
        output.append(str(getvalue(data['outTempLinkStatus'], data['outTemp'], '%0.2f')))
        output.append(str(getvalue(data['outTempLinkStatus'], data['outHumidity'], '%d')))
        for i in range(1, 5):
            output.append(str(getvalue(data['extraLinkStatus%d' % i], data['extraTemp%d' % i], '%0.2f')))
            output.append(str(getvalue(data['extraLinkStatus%d' % i], data['extraHumid%d' % i], '%d')))

        output.append(str(getvalue(1, data['barometer'], '%0.1f')))
        output.append(str(getvalue(data['txLinkStatus'], data['UV'], '%0.1f')))
        output.append(str(getvalue(1, data['forecast'], '%d')))
        output.append(str(getvalue(1, data['storm'], '%d')))

        output.append(str(getvalue(data['windLinkStatus'], data['windDir'], '%d')))
        output.append(str(getvalue(data['windLinkStatus'], data['windSpeed'], '%0.1f')))
        output.append(str(getvalue(data['windLinkStatus'], data['windGust'], '%0.1f')))
        output.append(str(getvalue(data['windLinkStatus'], data['windchill'], '%0.1f')))
        output.append(str(getvalue(data['rainLinkStatus'], data['rain'], '%.4f')))

        print ':'.join(output)

    @staticmethod
    def print_table(data):
        for key in sorted(data):
            print "%s: %s" % (key.rjust(16), data[key])


class TE923Driver(weewx.drivers.AbstractDevice):
    """Driver for Hideki TE923 stations."""
    
    def __init__(self, **stn_dict):
        """Initialize the station object.

        polling_interval: How often to poll the station, in seconds.
        [Optional. Default is 10]

        model: Which station model is this?
        [Optional. Default is 'TE923']
        """
        self._last_rain_loop    = None
        self._last_rain_archive = None
        self._last_ts           = None

        global DEBUG_READ
        DEBUG_READ             = int(stn_dict.get('debug_read', 0))
        global DEBUG_WRITE
        DEBUG_WRITE            = int(stn_dict.get('debug_write', 0))
        global DEBUG_DECODE
        DEBUG_DECODE           = int(stn_dict.get('debug_decode', 0))
        global DEBUG_MEMORY
        DEBUG_MEMORY           = int(stn_dict.get('debug_memory', 0))
        global DEBUG_PRESSURE
        DEBUG_PRESSURE         = int(stn_dict.get('debug_pressure', 0))

        self.model             = stn_dict.get('model', 'TE923')
        self.max_tries         = int(stn_dict.get('max_tries', 5))
        self.retry_wait        = int(stn_dict.get('retry_wait', 30))
        self.polling_interval  = int(stn_dict.get('polling_interval', 10))
        self.sensor_map    = stn_dict.get('sensor_map', DEFAULT_SENSOR_MAP)
        self.battery_map   = stn_dict.get('battery_map', DEFAULT_BATTERY_MAP)

        vendor_id              = int(stn_dict.get('vendor_id',  '0x1130'), 0)
        product_id             = int(stn_dict.get('product_id', '0x6801'), 0)
        device_id              = stn_dict.get('device_id', None)

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('polling interval is %s' % str(self.polling_interval))
        loginf('sensor map is %s' % self.sensor_map)
        loginf('battery map is %s' % self.battery_map)

        self.station = TE923(vendor_id, product_id, device_id)
        self.station.open()
        self.station.read_params()

    @property
    def hardware_name(self):
        return self.model

    @property
    def archive_interval(self):
        """weewx api.  Time in seconds between archive intervals."""
        return int(self.station._archive_interval)

    def closePort(self):
        self.station.close()
        self.station = None

    def genLoopPackets(self):
        while True:
            data = self.station.get_readings()
            status = self.station.get_status()
            packet = data_to_packet(data, status=status,
                                    last_rain=self._last_rain_loop,
                                    sensor_map=self.sensor_map,
                                    battery_map=self.battery_map)
            packet['dateTime'] = int(time.time() + 0.5)
            packet['latitude'], packet['longitude'] = self.station.get_location()
            packet['altitude'] = self.station.get_altitude()
            self._last_rain_loop = packet['rainTotal']
            ntries = 0
            yield packet
            time.sleep(self.polling_interval)

    def genArchiveRecords(self, since_ts=0):
        """A generator function to present logged archive packets

        since_ts: local timestamp in seconds.  All data since (but not
                  including) this time will be returned.  A value of None
                  results in all data.

        yields: a sequence of dictionaries containing the data, each with
                local timestamp in seconds.
        """
        loginf("Retrieving archive records since %d" % since_ts)

        if DEBUG_MEMORY:
            self.station.dump_memory()

        latitude, longitude = self.station.get_location()
        altitude = self.station.get_altitude()
        status = self.station.get_status()
        for data in self.station.get_archive(since_ts):
            packet = data_to_packet(data, status=status,
                                    last_rain=self._last_rain_archive,
                                    sensor_map=self.sensor_map,
                                    battery_map=self.battery_map)
            packet['dateTime'] = data['dateTime']
            if self._last_ts:
                packet['interval'] = (packet['dateTime'] - self._last_ts) / 60
            else:
                packet['interval'] = self.station._archive_interval / 60
            packet['latitude'] = latitude
            packet['longitude'] = longitude
            packet['altitude'] = altitude
            self._last_rain_archive = packet['rainTotal']
            self._last_ts = packet['dateTime']
            yield packet

    def genStartupRecords(self, since_ts=0, count=0):
        """A generator function to present archive packets on start.

        since_ts: local timestamp in seconds.  All data since (but not
                  including) this time will be returned.  A value of None
                  results in all data.

        yields: a sequence of dictionaries containing the data, each with
                local timestamp in seconds.
        """
        loginf("Retrieving archive records since %d" % since_ts)
        
        for data in self.station.get_archive(since_ts, count):
            packet = data_to_packet(data, status=None,
                                    last_rain=self._last_rain_archive,
                                    sensor_map=self.sensor_map,
                                    battery_map=self.battery_map)
            packet['dateTime'] = data['dateTime']
            if self._last_ts:
                packet['interval'] = (packet['dateTime'] - self._last_ts) / 60
            else:
                packet['interval'] = self.station._archive_interval / 60
            self._last_rain_archive = packet['rainTotal']
            self._last_ts = packet['dateTime']
            yield packet

    def getConfig(self):
        data = self.station.get_status()
        return data

    def get_extra_history(self):
        buf = self.station._read(0x24)
        tmpbuf = self.station._read(0x40)
        buf[28:37] = tmpbuf[1:10]
        tmpbuf = self.station._read(0xaa)
        buf[37:47] = tmpbuf[1:11]
        tmpbuf = self.station._read(0x60)
        buf[47:74] = tmpbuf[1:28]
        tmpbuf = self.station._read(0x7c)
        buf[74:101] = tmpbuf[1:28]
        return buf

    def get_date(self):
        buf = self.station._read(0x0)
        return buf[1:33]
    
    def set_date(self, buf):
        self.station._write(0x00, buf)

    def get_loc(self, loc_type):
        if loc_type == 0:
            buf = self.station._read(0x0)
        else:
            buf = self.station._read(0x16)
        return buf[1:33]
    
    def set_loc(self, loc_type, buf):
        if loc_type == 0:
            self.station._write(0x00, buf)
        else:
            self.station._write(0x16, buf)
    
    def get_alt(self):
        buf = self.station._read(0x5a)
        return buf[1:33]
    
    def set_alt(self, buf):
        self.station._write(0x5a, buf)
    
    def get_alarms(self):
        buf = self.station._read(0x10)
        tmpbuf = self.station._read(0x1F)
        buf[33:65] = tmpbuf[1:33]
        tmpbuf = self.station._read(0xA0)
        buf[65:97] = tmpbuf[1:33]
        return buf[1:97]

    def set_alarms(self, buf):
        self.station._write(0x10, buf[0:32])
        self.station._write(0x1F, buf[32:64])
        self.station._write(0xA0, buf[64:96])

    def get_interval(self):
        buf = self.station._read(0xFE)
        return buf[1:33]
    
    def set_interval(self, buf):
        self.station._write(0xFE, buf)
    
def getvalue(status, data, fmt):
    if status == 0:
         return STATE_MISSING_LINK[0]
    else:
        if data is None:
            return STATE_INVALID[0]
        else:
            return fmt % data

def data_to_packet(data, status=None, last_rain=None,
                   sensor_map=DEFAULT_SENSOR_MAP,
                   battery_map=DEFAULT_BATTERY_MAP):
    """convert raw data to format and units required by weewx

                    station      weewx (metric)
    temperature     degree C     degree C
    humidity        percent      percent
    uv index        unitless     unitless
    slp             mbar         mbar
    wind speed      mile/h       km/h
    wind gust       mile/h       km/h
    wind dir        degree       degree
    rain            mm           cm
    rain rate                    cm/h
    """

    packet = {}
    packet['usUnits'] = weewx.METRIC

    packet['inTemp'] = data['t_in'] # T is degree C
    packet['inHumidity'] = data['h_in'] # H is percent
    packet['outTemp'] = data[sensor_map['outTemp']] \
        if 'outTemp' in sensor_map else None
    packet['outHumidity'] = data[sensor_map['outHumidity']] \
        if 'outHumidity' in sensor_map else None
    if data[sensor_map['outTemp'] + '_state'] == STATE_MISSING_LINK:
       packet['outTempLinkStatus'] = 0
    else:
       packet['outTempLinkStatus'] = 1

    packet['UV'] = data['uv']
    if data['uv_state'] == STATE_MISSING_LINK:
       packet['txLinkStatus'] = 0
    else:
       packet['txLinkStatus'] = 1

    packet['windSpeed'] = data['windspeed']
    if packet['windSpeed'] is not None:
        packet['windSpeed'] *= 1.60934 # speed is mph; weewx wants km/h
    if packet['windSpeed']:
        packet['windDir'] = data['winddir']
        if packet['windDir'] is not None:
            packet['windDir'] *= 22.5 # weewx wants degrees
    else:
        packet['windDir'] = None
    if data['windspeed_state'] == STATE_MISSING_LINK:
       packet['windLinkStatus'] = 0
    else:
       packet['windLinkStatus'] = 1

    packet['windGust'] = data['windgust']
    if packet['windGust'] is not None:
        packet['windGust'] *= 1.60934 # speed is mph; weewx wants km/h
    if packet['windGust']:
        packet['windGustDir'] = data['winddir']
        if packet['windGustDir'] is not None:
            packet['windGustDir'] *= 22.5 # weewx wants degrees
    else:
        packet['windGustDir'] = None

    packet['rainTotal'] = data['rain']
    if packet['rainTotal'] is not None:
        packet['rainTotal'] *= 0.06578 # weewx wants cm
    packet['rain'] = weewx.wxformulas.calculate_rain(
        packet['rainTotal'], last_rain)
    if data['rain_state'] == STATE_MISSING_LINK:
       packet['rainLinkStatus'] = 0
    else:
       packet['rainLinkStatus'] = 1

    # station calculates windchill
    packet['windchill'] = data['windchill']

    # station reports baromter (SLP)
    packet['barometer'] = data['slp']
    
    packet['forecast'] = data['forecast']
    packet['storm'] = data['storm']

    # insert values for extra sensors if they are available
    for label in sensor_map:
        packet[label] = data[sensor_map[label]]

    for i in range(1, 5):
       if data[sensor_map['extraTemp%d' % i] + '_state'] == STATE_MISSING_LINK:
          packet['extraLinkStatus%d' % i] = 0
       else:
          packet['extraLinkStatus%d' % i] = 1

    # insert values for battery status if they are available
    if status is not None:
        for label in battery_map:
            packet[label] = status[battery_map[label]]

    return packet

STATE_OK = 'ok'
STATE_INVALID = 'invalid'
STATE_MISSING_LINK = 'no_link'

forecast_dict = {
    0: 'Heavy snow',
    1: 'Light snow',
    2: 'Heavy rain',
    3: 'Light rain',
    4: 'Heavy cloud',
    5: 'Light cloud',
    6: 'Sunny',
    }

def bcd2int(bcd):
    return int(((bcd & 0xf0) >> 4) * 10) + int(bcd & 0x0f)

def rev_bcd2int(bcd):
    return int((bcd & 0xf0) >> 4) + int((bcd & 0x0f) * 10)

def int2bcd(num):
    return int(num / 10) * 0x10 + (num % 10) 

def rev_int2bcd(num):
    return (num % 10) * 0x10 + int(num / 10)

def decode(buf):
    data = {}
    for i in range(6):  # 5 channels plus indoor
        data.update(decode_th(buf, i))
    data.update(decode_uv(buf))
    data.update(decode_pressure(buf))
    data.update(decode_wind(buf))
    data.update(decode_rain(buf))
    data.update(decode_windchill(buf))
    data.update(decode_status(buf))
    return data

def decode_th(buf, i):
    """decode temperature and humidity from the indicated sensor."""

    if i == 0:
        tlabel = 't_in'
        tstate = 't_in_state'
        hlabel = 'h_in'
        hstate = 'h_in_state'
    else:
        tlabel = 't_%d' % i
        tstate = 't_%d_state' % i
        hlabel = 'h_%d' % i
        hstate = 'h_%d_state' % i

    offset = i * 3
    data = {}
    data[tstate] = STATE_OK
    if DEBUG_DECODE:
        loginf("TMP%d BUF[%02d]=%02x BUF[%02d]=%02x BUF[%02d]=%02x" %
               (i, 0+offset, buf[0+offset], 1+offset, buf[1+offset],
                2+offset, buf[2+offset]))
    if bcd2int(buf[0+offset] & 0x0f) > 9:
        if buf[0+offset] & 0x0f == 0x0a:
            data[tstate] = STATE_MISSING_LINK
        else:
            data[tstate] = STATE_INVALID
    if data[tstate] != STATE_MISSING_LINK and buf[1+offset] & 0x40 != 0x40 and i > 0:
        data[tstate] = STATE_INVALID

    if data[tstate] == STATE_OK:
        data[tlabel] = bcd2int(buf[0+offset]) / 10.0 \
            + bcd2int(buf[1+offset] & 0x0f) * 10.0
        if buf[1+offset] & 0x20 == 0x20:
            data[tlabel] += 0.05
        if buf[1+offset] & 0x80 != 0x80:
            data[tlabel] *= -1
    else:
        data[tlabel] = None

    data[hstate] = STATE_OK
    if bcd2int(buf[2+offset] & 0x0f) > 9:
        if buf[2+offset] & 0x0f == 0x0a:
            data[hstate] = STATE_MISSING_LINK
        else:
            data[hstate] = STATE_INVALID

    if data[hstate] == STATE_OK:
        data[hlabel] = bcd2int(buf[2+offset])
    else:
        data[hlabel] = None

    if DEBUG_DECODE:
        loginf("TMP%d %s %s %s %s" % (i, data[tlabel], data[tstate],
                                      data[hlabel], data[hstate]))
    return data

def decode_uv(buf):
    """decode data from uv sensor"""
    data = {}
    if DEBUG_DECODE:
        loginf("UVX  BUF[18]=%02x BUF[19]=%02x" % (buf[18], buf[19]))
    if (buf[18] == 0xaa and buf[19] == 0x0a) or (buf[18] == 0xff and buf[19] == 0xff):
        data['uv_state'] = STATE_MISSING_LINK
        data['uv'] = None
    elif bcd2int(buf[18]) > 99 or bcd2int(buf[19]) > 99:
        data['uv_state'] = STATE_INVALID
        data['uv'] = None
    else:
        data['uv_state'] = STATE_OK
        data['uv'] = bcd2int(buf[18] & 0x0f) / 10.0 \
            + bcd2int(buf[18] & 0xf0) \
            + bcd2int(buf[19] & 0x0f) * 10.0
    if DEBUG_DECODE:
        loginf("UVX  %s %s" % (data['uv'], data['uv_state']))
    return data

def decode_pressure(buf):
    """decode pressure data"""
    data = {}
    if DEBUG_DECODE:
        loginf("PRS  BUF[20]=%02x BUF[21]=%02x" % (buf[20], buf[21]))
    if buf[21] & 0xf0 == 0xf0:
        data['slp_state'] = STATE_INVALID
        data['slp'] = None
    else:
        data['slp_state'] = STATE_OK
        data['slp'] = int(buf[21] * 0x100 + buf[20]) * 0.0625
    if DEBUG_DECODE:
        loginf("PRS  %s %s" % (data['slp'], data['slp_state']))
    return data

# NB: te923tool divides speed/gust by 2.23694 (1 meter/sec = 2.23694 mile/hour)
# NB: wview does not divide speed/gust
# NB: wview multiplies winddir by 22.5, te923tool does not
def decode_wind(buf):
    """decode wind speed, gust, and direction"""
    data = {}
    if DEBUG_DECODE:
        loginf("WGS  BUF[25]=%02x BUF[26]=%02x" % (buf[25], buf[26]))
    if bcd2int(buf[25] & 0xf0) > 90 or bcd2int(buf[25] & 0x0f) > 9:
        if (buf[25] == 0xee and buf[26] == 0x8e) or (buf[25] == 0xff and buf[26] == 0xff):
            data['windgust_state'] = STATE_MISSING_LINK
        else:
            data['windgust_state'] = STATE_INVALID
        data['windgust'] = None
    else:
        data['windgust_state'] = STATE_OK
        offset = 100 if buf[26] & 0x10 == 0x10 else 0
        data['windgust'] = bcd2int(buf[25]) / 10.0 \
            + bcd2int(buf[26] & 0x0f) * 10.0 \
            + offset
    if DEBUG_DECODE:
        loginf("WGS  %s %s" % (data['windgust'], data['windgust_state']))

    if DEBUG_DECODE:
        loginf("WSP  BUF[27]=%02x BUF[28]=%02x" % (buf[27], buf[28]))
    if bcd2int(buf[27] & 0xf0) > 90 or bcd2int(buf[27] & 0x0f) > 9:
        if (buf[27] == 0xee and buf[28] == 0x8e) or (buf[27] == 0xff and buf[28] == 0xff):
            data['windspeed_state'] = STATE_MISSING_LINK
        else:
            data['windspeed_state'] = STATE_INVALID
        data['windspeed'] = None
    else:
        data['windspeed_state'] = STATE_OK
        offset = 100 if buf[28] & 0x10 == 0x10 else 0
        data['windspeed'] = bcd2int(buf[27]) / 10.0 \
            + bcd2int(buf[28] & 0x0f) * 10.0 \
            + offset
    if DEBUG_DECODE:
        loginf("WSP  %s %s" % (data['windspeed'], data['windspeed_state']))

    if DEBUG_DECODE:
        loginf("WDR  BUF[29]=%02x" % buf[29])
    if data['windspeed_state'] == STATE_MISSING_LINK:
        data['winddir_state'] = data['windspeed_state']
        data['winddir'] = None
    else:
        data['winddir_state'] = STATE_OK
        data['winddir'] = int(buf[29] & 0x0f)
    if DEBUG_DECODE:
        loginf("WDR  %s %s" % (data['winddir'], data['winddir_state']))
    
    return data

# FIXME: figure out how to detect link status between station and rain bucket
# FIXME: according to sebastian, the counter is in the station, not the rain
# bucket.  so if the link between rain bucket and station is lost, the station
# will miss rainfall and there is no way to know about it.

# NB: wview treats the raw rain count as millimeters
def decode_rain(buf):
    data = {}
    if DEBUG_DECODE:
        loginf("RAIN BUF[30]=%02x BUF[31]=%02x" % (buf[30], buf[31]))
    data['rain_state'] = STATE_OK
    data['rain'] = int(buf[31] * 0x100 + buf[30])
    if DEBUG_DECODE:
        loginf("RAIN %s %s" % (data['rain'], data['rain_state']))
    return data

def decode_windchill(buf):
    data = {}
    if DEBUG_DECODE:
        loginf("WCL  BUF[23]=%02x BUF[24]=%02x" % (buf[23], buf[24]))
    if bcd2int(buf[23] & 0xf0) > 90 or bcd2int(buf[23] & 0x0f) > 9:
        if (buf[23] == 0xee and buf[24] == 0x8e) or (buf[23] == 0xff and buf[24] == 0xff):
            data['windchill_state'] = STATE_MISSING_LINK
        else:
            data['windchill_state'] = STATE_INVALID
        data['windchill'] = None
    elif buf[24] & 0x40 != 0x40:
        data['windchill_state'] = STATE_INVALID
        data['windchill'] = None
    else:
        data['windchill_state'] = STATE_OK
        data['windchill'] = bcd2int(buf[23]) / 10.0 + bcd2int(buf[24] & 0x0f) * 10.0
        if buf[24] & 0x20 == 0x20:
            data['windchill'] += 0.05
        if buf[24] & 0x80 != 0x80:
            data['windchill'] *= -1
    if DEBUG_DECODE:
        loginf("WCL  %s %s" % (data['windchill'], data['windchill_state']))
    return data

def decode_status(buf):
    data = {}
    if DEBUG_DECODE:
        loginf("STT  BUF[22]=%02x" % buf[22])
    if buf[22] & 0x0f == 0x0f:
        data['storm'] = None
        data['forecast'] = None
    else:
        data['storm'] = buf[22] & 0x08 == 0x08
        data['forecast'] = int(buf[22] & 0x07)
    if DEBUG_DECODE:
        loginf("STT  %s %s" % (data['storm'], data['forecast']))
    return data

def _find_dev(vendor_id, product_id, device_id):
    """Find the vendor and product ID on the USB."""
    for bus in usb.busses():
        for dev in bus.devices:
            if dev.idVendor == vendor_id and dev.idProduct == product_id:
                if device_id is None or dev.filename == device_id:
                    loginf('Found device on USB bus=%s device=%s' % (bus.dirname, dev.filename))
                    return dev
    return None

class BadRead(weewx.WeeWxIOError):
    """Bogus data length, CRC, header block, or other read failure"""

class BadWrite(weewx.WeeWxIOError):
    """Bogus data length, header block, or other write failure"""

class TE923(object):
    ENDPOINT_IN = 0x81
    READ_LENGTH = 0x8
    TIMEOUT = 1000

    def __init__(self, vendor_id=0x1130, product_id=0x6801, dev_id=None):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device_id = dev_id
        self.devh = None

    def open(self, interface=0):
        dev = _find_dev(self.vendor_id, self.product_id, self.device_id)
        if not dev:
            logcrt("Cannot find USB device with VendorID=0x%04x ProductID=0x%04x DeviceID=%s" % (self.vendor_id, self.product_id, self.device_id))
            raise weewx.WeeWxIOError('Unable to find station on USB')

        self.devh = dev.open()
        if not self.devh:
            raise weewx.WeeWxIOError('Open USB device failed')

        # be sure kernel does not claim the interface
        try:
            self.devh.detachKernelDriver(interface)
        except Exception:
            pass

        # attempt to claim the interface
        try:
            self.devh.claimInterface(interface)
            self.devh.setAltInterface(interface)
        except usb.USBError, e:
            self.close()
            logcrt("Unable to claim USB interface %s: %s" % (interface, e))
            raise weewx.WeeWxIOError(e)

    def close(self):
        try:
            self.devh.releaseInterface()
        except Exception:
            pass
        self.devh = None

    def read_params(self):
        buf = self._read(0xfc)
        if buf[1] == 0:
            self.memory_size = 'small'
            self.num_rec = 208
            self.num_blk = 256
            loginf("Memory size set to small")
        elif buf[1] == 2:
            self.memory_size = 'large'
            self.num_rec = 3442
            self.num_blk = 4096
            loginf("Memory size set to large")
        else:
            self.memory_size = 'small'
            self.num_rec = 208
            self.num_blk = 256
            logerr("Unrecognised station memory size read - defaulting to small")
            
        if buf[3] == 1:
            self._archive_interval = 300
        elif buf[3] == 2:
            self._archive_interval = 600
        elif buf[3] == 3:
            self._archive_interval = 1200
        elif buf[3] == 4:
            self._archive_interval = 1800
        elif buf[3] == 5:
            self._archive_interval = 3600
        elif buf[3] == 6:
            self._archive_interval = 5400
        elif buf[3] == 7:
            self._archive_interval = 7200
        elif buf[3] == 8:
            self._archive_interval = 10800
        elif buf[3] == 9:
            self._archive_interval = 14400
        elif buf[3] == 10:
            self._archive_interval = 21600
        elif buf[3] == 11:
            self._archive_interval = 86400
        else:
            self._archive_interval = 3600
            logerr("Unrecognised archive interval read")

    def _raw_read(self, addr):
        reqbuf = [0x05, 0xAF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        reqbuf[4] = addr / 0x10000
        reqbuf[3] = (addr - (reqbuf[4] * 0x10000)) / 0x100
        reqbuf[2] = addr - (reqbuf[4] * 0x10000) - (reqbuf[3] * 0x100)
        reqbuf[5] = (reqbuf[1] ^ reqbuf[2] ^ reqbuf[3] ^ reqbuf[4])
        ret = self.devh.controlMsg(requestType=0x21,
                                   request=usb.REQ_SET_CONFIGURATION,
                                   value=0x0200,
                                   index=0x0000,
                                   buffer=reqbuf,
                                   timeout=self.TIMEOUT)
        if ret != 8:
            raise BadRead('Unexpected response to data request: %s != 8' % ret)

        time.sleep(0.1)  # te923tool is 0.3
        start_ts = time.time()
        rbuf = []
        while time.time() - start_ts < 5:
            try:
                buf = self.devh.interruptRead(self.ENDPOINT_IN,
                                              self.READ_LENGTH, self.TIMEOUT)
                if buf:
                    nbytes = buf[0]
                    if nbytes > 7 or nbytes > len(buf)-1:
                        raise BadRead("Bogus length during read: %d" % nbytes)
                    rbuf.extend(buf[1:1+nbytes])
                if len(rbuf) >= 34:
                    break
            except usb.USBError, e:
                # FIXME: If "No such device" we should bail out immediately
                # unfortunately there is no reliable way (?) to get the type
                # of USBError.  We often get an exception of "could not detach
                # kernel driver from interface 0: No data available" or
                # "No error", but this seems to indicate no more data, or a
                # usb timing/comm failure, not an actual error condition.
                #logdbg('usb error while reading: %s' % e)
                pass
            time.sleep(0.009)  # te923tool is 0.15
        else:
            raise BadRead("Timeout after %d bytes" % len(rbuf))

        if len(rbuf) < 34:
            raise BadRead("Not enough bytes: %d < 34" % len(rbuf))
        elif len(rbuf) != 34:
            loginf("Wrong number of bytes: %d != 34" % len(rbuf))
        if rbuf[0] != 0x5a:
            raise BadRead("Bad header byte: %02x != %02x" % (rbuf[0], 0x5a))

        crc = 0x00
        for x in rbuf[:33]:
            crc = crc ^ x
        if crc != rbuf[33]:
            raise BadRead("Bad crc: %02x != %02x" % (crc, rbuf[33]))

        # Send acknowledgement
        reqbuf = [0x24, 0xAF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        reqbuf[4] = addr / 0x10000
        reqbuf[3] = (addr - (reqbuf[4] * 0x10000)) / 0x100
        reqbuf[2] = addr - (reqbuf[4] * 0x10000) - (reqbuf[3] * 0x100)
        reqbuf[5] = (reqbuf[1] ^ reqbuf[2] ^ reqbuf[3] ^ reqbuf[4])
        ret = self.devh.controlMsg(requestType=0x21,
                                   request=usb.REQ_SET_CONFIGURATION,
                                   value=0x0200,
                                   index=0x0000,
                                   buffer=reqbuf,
                                   timeout=self.TIMEOUT)
        return rbuf

    def _raw_write(self, addr, buf):
        wbuf = [0 for i in range(38)]
        wbuf[0] = 0xAE
        wbuf[3] = addr / 0x10000
        wbuf[2] = (addr - (wbuf[3] * 0x10000)) / 0x100
        wbuf[1] = addr - (wbuf[3] * 0x10000) - (wbuf[2] * 0x100)
        crc = wbuf[0] ^ wbuf[1] ^ wbuf[2] ^ wbuf[3]
        for i in range(32):
            wbuf[i + 4] = buf[i]
            crc = crc ^ buf[i]
        wbuf[36] = crc
        for i in range(6):
            if i == 5:
                reqbuf = [0x2, wbuf[i * 7], wbuf[1 + i * 7], 0x00, 0x00, 0x00, 0x00, 0x00]
            else:
                reqbuf = [0x7, wbuf[i * 7], wbuf[1 + i * 7], wbuf[2 + i * 7], wbuf[3 + i * 7], wbuf[4 + i * 7], wbuf[5 + i * 7], wbuf[6 + i * 7]]
            if DEBUG_WRITE:
                print("WRITE  " + ' '.join(["%02x" % x for x in reqbuf]))
            ret = self.devh.controlMsg(requestType=0x21,
                                       request=usb.REQ_SET_CONFIGURATION,
                                       value=0x0200,
                                       index=0x0000,
                                       buffer=reqbuf,
                                       timeout=self.TIMEOUT)
            if ret != 8:
                raise BadWrite('Unexpected response to data request: %s != 8' % ret)
            
        # Wait for acknowledgement
        time.sleep(0.1)
        start_ts = time.time()
        rbuf = []
        while time.time() - start_ts < 5:
            try:
                tmpbuf = self.devh.interruptRead(self.ENDPOINT_IN,
                                              self.READ_LENGTH, self.TIMEOUT)
                if tmpbuf:
                    nbytes = tmpbuf[0]
                    if nbytes > 7 or nbytes > len(tmpbuf)-1:
                        raise BadRead("Bogus length during read: %d" % nbytes)
                    rbuf.extend(tmpbuf[1:1+nbytes])
                if len(rbuf) >= 1:
                    break
            except usb.USBError, e:
                pass
            time.sleep(0.009)
        else:
            raise BadWrite("Timeout after %d bytes" % len(rbuf))

        if len(rbuf) != 1:
            print("Wrong number of bytes: %d != 1" % len(rbuf))
        if rbuf[0] != 0x5a:
            raise BadWrite("Bad header byte: %02x != %02x" % (rbuf[0], 0x5a))
        if DEBUG_WRITE:
            print("ACK RECEIVED")

    def _read(self, addr, max_tries=10, retry_wait=5):
        if DEBUG_READ:
            logdbg("reading station at address 0x%06x" % addr)
        for cnt in range(max_tries):
            try:
                buf = self._raw_read(addr)
                if DEBUG_READ:
                    logdbg("BUF  " + ' '.join(["%02x" % x for x in buf]))
                return buf
            except (BadRead, usb.USBError), e:
                logerr("Failed attempt %d of %d to read data: %s" % (cnt+1, max_tries, e))
                logdbg("Waiting %d seconds before retry" % retry_wait)
                time.sleep(retry_wait)
        else:
            raise weewx.RetriesExceeded("No data after %d tries" % max_tries)

    def _write(self, addr, buf, max_tries=10, retry_wait=5):
        if DEBUG_WRITE:
            print("writing station at address 0x%06x" % addr)
        for cnt in range(max_tries):
            try:
                if DEBUG_WRITE:
                    print("BUF  " + ' '.join(["%02x" % x for x in buf]))
                self._raw_write(addr, buf)
                return
            except (BadWrite, usb.USBError), e:
                print("Failed attempt %d of %d to write data: %s" % (cnt+1, max_tries, e))
                print("Waiting %d seconds before retry" % retry_wait)
                time.sleep(retry_wait)
        else:
            print("Failed after %d tries" % max_tries)

    def gen_blocks(self, count=None):
        """generator that returns consecutive blocks of station memory"""
        if not count:
            count = self.num_blk
        for x in range(0, count*32, 32):
            buf = self._read(x)
            yield x, buf

    def get_status(self):
        """get station status"""
        status = {}

        buf = self._read(0x98)
        status['barVer']  = buf[1]
        status['uvVer']   = buf[2]
        status['rccVer']  = buf[3]
        status['windVer'] = buf[4]
        status['sysVer']  = buf[5]

        buf = self._read(0x4c)
        status['batteryRain'] = buf[1] & 0x80 == 0x80
        status['batteryWind'] = buf[1] & 0x40 == 0x40
        status['batteryUV']   = buf[1] & 0x20 == 0x20
        status['battery5']    = buf[1] & 0x10 == 0x10
        status['battery4']    = buf[1] & 0x08 == 0x08
        status['battery3']    = buf[1] & 0x04 == 0x04
        status['battery2']    = buf[1] & 0x02 == 0x02
        status['battery1']    = buf[1] & 0x01 == 0x01

        return status

    def get_altitude(self):
        """get altitude from station"""
        buf = self._read(0x5a)
        if DEBUG_DECODE:
           loginf("ALT  BUF[1]=%02x BUF[2]=%02x BUF[3]=%02x" % (buf[1], buf[2], buf[3]))
        altitude = buf[2] * 0x100 + buf[1]
        if buf[3] & 0x8 == 0x8:
           altitude *= -1
        if DEBUG_DECODE:
           loginf("ALT  %s" % altitude)
        return altitude

    def get_location(self):
        """get location from station"""
        buf = self._read(0x06)
        if DEBUG_DECODE:
           loginf("LOC  BUF[1]=%02x BUF[2]=%02x BUF[3]=%02x BUF[4]=%02x BUF[5]=%02x BUF[6]=%02x" % (buf[1], buf[2], buf[3], buf[4], buf[5], buf[6]))
        latitude = float(rev_bcd2int(buf[1])) + (float(rev_bcd2int(buf[2])) / 60)
        if buf[5] & 0x80 == 0x80:
          latitude *= -1
        longitude = float((buf[6] & 0xf0) / 0x10 * 100) + float(rev_bcd2int(buf[3])) + (float(rev_bcd2int(buf[4])) / 60)
        if buf[5] & 0x40 == 0x00:
           longitude *= -1
        if DEBUG_DECODE:
           loginf("LOC  %s %s" % (latitude, longitude))
        return latitude, longitude

    def get_readings(self):
        """get sensor readings from the station, return as dictionary"""
        buf = self._read(0x020001)
        data = decode(buf[1:])
        return data
        
    def get_archive(self, since_ts=0, count=0):
        """get logged readings from the station, return as dictionary"""
        
        tt = time.localtime(time.time())
        
        buf = self._read(0xfb)
        first_addr = (buf[3] * 0x100 + buf[5] - 1) * 0x26 + 0x101
        if first_addr < 0x101:
            if self.memory_size == 'large':
                addr = 0x01ffc7
            else:
                addr = 0x001fbb
        addr = first_addr

        first_read = 1
        packet = []
        while 1:
            if addr == first_addr and first_read == 0:
                break
            addr, data = self.get_record(addr, tt.tm_year, tt.tm_mon)
            firstread = 0
            if data:
                if data['dateTime'] > since_ts:
                   packet.append(data)
                else:
                   break
                if count > 0 and count <= len(packet):
                   break
            if not addr:
                break
                
        for i in range(len(packet)-1,-1,-1):
            yield packet[i]
            
    def dump_memory(self):
        for i in range(8):
           buf = self._read(i * 32)
           for j in range(4):
              loginf("%02x : %02x %02x %02x %02x %02x %02x %02x %02x" % (i * 32 + j * 8, buf[1 + j * 8], buf[2 + j * 8], buf[3 + j * 8], buf[4 + j * 8], buf[5 + j * 8], buf[6 + j * 8], buf[7 + j * 8], buf[8 + j * 8]))
        return None

    def gen_records(self, count=None):
        if not count:
            count = self.num_rec
        tt = time.localtime(time.time())

        buf = self._read(0xfb)
        first_addr = (buf[3] * 0x100 + buf[5] - 1) * 0x26 + 0x101
        if first_addr < 0x101:
            if self.memory_size == 'large':
                addr = 0x01ffc7
            else:
                addr = 0x001fbb
        addr = first_addr

        i = 0
        first_read = 1
        while i < count:
            if addr == first_addr and first_read == 0:
               break
            addr, record = self.get_record(addr, tt.tm_year, tt.tm_mon)
            first_read = 0
            if record:
               i += 1
               yield record
            if not addr:
               break

    def get_record(self, addr, now_year=None, now_month=None):
        """return a single record from station and address of the next

        Each historical record is 38 bytes (0x26) long.  Records start at
        memory address 0x101 (257).  The index of the record after the latest is at
        address 0xfc:0xff (253:255), indicating the offset from the starting address.

        On small memory stations, the last 32 bytes of memory are never used.
        On large memory stations, the last 20 bytes of memory are never used.
        """
        
        if now_year is None or now_month is None:
            now = int(time.time())
            tt = time.localtime(now)
            now_year = tt.tm_year
            now_month = tt.tm_mon

        buf = self._read(addr)
        if buf[1] == 0xff:
           # Out of records
           return None, None
        
        year = now_year
        month = buf[1] & 0x0f
        if month > now_month:
            year -= 1
        day = bcd2int(buf[2])
        hour = bcd2int(buf[3])
        minute = bcd2int(buf[4])
        ts = time.mktime((year, month, day, hour, minute, 0, 0, 0, -1))
        if DEBUG_DECODE:
            loginf("REC  %02x %02x %02x %02x" % (buf[1], buf[2], buf[3], buf[4]))
            loginf("REC  %02d/%02d/%d %02d:%02d = %d" % (day, month, year, hour, minute, ts))

        tmpbuf = buf[5:16]
        crc1 = buf[16]
        buf = self._read(addr + 0x10) 
        tmpbuf.extend(buf[1:22])
        crc2 = buf[22]
        if DEBUG_DECODE:
            loginf("CRC  %02x %02x" % (crc1, crc2))
        
        data = decode(tmpbuf)
        data['dateTime'] = int(ts)

        addr -= 0x26        
        if addr < 0x101:
            if self.memory_size == 'large':
                addr = 0x01ffc7
            else:
                addr = 0x001fbb

        return addr, data


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/te923.py
#
# by default, output matches that of te923tool
#    te923con                 display current weather readings
#    te923con -d              dump 208 memory records
#    te923con -s              display station status

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--debug] [--help]"""

    def main():
        FMT_TE923TOOL = 'te923tool'
        FMT_DICT = 'dict'
        FMT_TABLE = 'table'

        syslog.openlog('wee_te923', syslog.LOG_PID | syslog.LOG_CONS)
        parser = optparse.OptionParser(usage=usage)
        parser.add_option('--version', dest='version', action='store_true',
                          help='display driver version')
        parser.add_option('--debug', dest='debug', action='store_true',
                          help='display diagnostic information while running')
        parser.add_option('--status', dest='status', action='store_true',
                          help='display station status')
        parser.add_option('--readings', dest='readings', action='store_true',
                          help='display sensor readings')
        parser.add_option("--records", dest="records", type=int, metavar="N",
                          help="display N station records, oldest to newest")
        parser.add_option('--blocks', dest='blocks', type=int, metavar="N",
                          help='display N 32-byte blocks of station memory')
        parser.add_option("--format", dest="format", type=str,metavar="FORMAT",
                          help="format for output: te923tool, table, or dict")
        (options, _) = parser.parse_args()

        if options.version:
            print "te923 driver version %s" % DRIVER_VERSION
            exit(1)

        if options.debug is not None:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        else:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

        if options.format is None:
            options.format = FMT_TE923TOOL
        elif (options.format.lower() != FMT_TE923TOOL and
              options.format.lower() != FMT_TABLE and
              options.format.lower() != FMT_DICT):
            print "Unknown format '%s'.  Known formats include 'te923tool', 'table', and 'dict'." % options.format
            exit(1)

        station = None
        try:
            station = TE923()
            station.open()
            station.read_params()
            if options.status:
                data = station.get_status()
                if options.format.lower() == FMT_DICT:
                    print_dict(data)
                elif options.format.lower() == FMT_TABLE:
                    print_table(data)
                else:
                    print_status(data)
            if options.readings:
                data = station.get_readings()
                data['dateTime'] = int(time.time() + 0.5)
                if options.format.lower() == FMT_DICT:
                    print_dict(data)
                elif options.format.lower() == FMT_TABLE:
                    print_table(data)
                else:
                    print_readings(data)
            if options.records is not None:
                for data in station.gen_records(count=options.records):
                    if options.format.lower() == FMT_DICT:
                        print_dict(data)
                    elif options.format.lower() == FMT_TABLE:
                        print_table(data)
                    else:
                        print_readings(data)
            if options.blocks is not None:
                for ptr, block in station.gen_blocks(count=options.blocks):
                    print_hex(ptr, block)
        finally:
            if station is not None:
                station.close()

    def print_dict(data):
        """output entire dictionary contents"""
        print data

    def print_table(data):
        """output entire dictionary contents in two columns"""
        for key in sorted(data):
            print "%s: %s" % (key.rjust(16), data[key])

    def print_status(data):
        """output status fields in te923tool format"""
        print "0x%x:0x%x:0x%x:0x%x:0x%x:%d:%d:%d:%d:%d:%d:%d:%d" % (
            data['sysVer'], data['barVer'], data['uvVer'], data['rccVer'],
            data['windVer'], data['batteryRain'], data['batteryUV'],
            data['batteryWind'], data['battery5'], data['battery4'],
            data['battery3'], data['battery2'], data['battery1'])

    def print_readings(data):
        """output sensor readings in te923tool format"""
        try:
           data['dateTime']
        except:
           output = [str(time.time())]
        else:
           output = [str(data['dateTime'])]
        output.append(getvalue(data, 't_in', '%0.2f'))
        output.append(getvalue(data, 'h_in', '%d'))
        for i in range(1, 6):
            output.append(getvalue(data, 't_%d' % i, '%0.2f'))
            output.append(getvalue(data, 'h_%d' % i, '%d'))
        output.append(getvalue(data, 'slp', '%0.1f'))
        output.append(getvalue(data, 'uv', '%0.1f'))
        output.append(getvalue(data, 'forecast', '%d'))
        output.append(getvalue(data, 'storm', '%d'))
        output.append(getvalue(data, 'winddir', '%d'))
        output.append(getvalue(data, 'windspeed', '%0.1f'))
        output.append(getvalue(data, 'windgust', '%0.1f'))
        output.append(getvalue(data, 'windchill', '%0.1f'))
        output.append(getvalue(data, 'rain', '%d'))
        print ':'.join(output)

    def print_hex(ptr, data):
        print "0x%06x %s" % (ptr, ' '.join(["%02x" % x for x in data]))

    def getvalue(data, label, fmt):
        if label + '_state' in data:
            if data[label + '_state'] == STATE_OK:
                return fmt % data[label]
            else:
                return data[label + '_state'][0]
        else:
            if data[label] is None:
                return 'x'
            else:
                return fmt % data[label]

if __name__ == '__main__':
    main()
