#!/usr/bin/env python
#
# Copyright 2013-2015 Matthew Wall, Andrew Miles
# See the file LICENSE.txt for your full rights.
#
# Thanks to Andrew Miles for figuring out how to read history records
#   and many station parameters.
# Thanks to Sebastian John for the te923tool written in C (v0.6.1):
#   http://te923.fukz.org/
# Thanks to Mark Teel for the te923 implementation in wview:
#   http://www.wviewweather.com/

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

Setting the time does not persist.  If you set the station time using weewx,
the station initially indicates that it is set to the new time, but then it
reverts.

Notes From/About Other Implementations

Apparently te923tool came first, then wview copied a bit from it.  te923tool
provides more detail about the reason for invalid values, for example, values
out of range versus no link with sensors.  However, these error states have not
yet been corroborated.

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

0x020000 - Last sample:

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
(2) Checksum are via subtraction: 0x100 - sum of all values, then add 0x100
    until positive i.e. 0x100 - 0x70 - 0x80 - 0x28 = -0x18, 0x18 + 0x100 = 0xE8

SECTION 1: Date & Local location

0x000000 - Unknown - changes if date section is modified but still changes if
           same data is written so not a checksum
0x000001 - Unknown (always 0)
0x000002 - Day (Reverse BCD) (Changes at midday!)
0x000003 - Unknown
0x000004 - Year (Reverse BCD)
0x000005 - Month (Bits 7:4), Weekday (Bits 3:1)
0x000006 - Latitude (degrees) (reverse BCD)
0x000007 - Latitude (minutes) (reverse BCD)
0x000008 - Longitude (degrees) (reverse BCD)
0x000009 - Longitude (minutes) (reverse BCD)
0x00000A - Bit 7 - Set if Latitude southerly
           Bit 6 - Set if Longitude easterly
           Bit 4 - Set if DST is always on
           Bit 3 - Set if -ve TZ
           Bits 0 & 1 - Set if half-hour TZ
0x00000B - Longitude (100 degrees) (Bits 7:4), DST zone (Bits 3:0)
0x00000C - City code (High) (Bits 7:4)
           Language (Bits 3:0)
            0 - English
            1 - German
            2 - French
            3 - Italian
            4 - Spanish
            6 - Dutch
0x00000D - Timezone (hour) (Bits 7:4), City code (Low) (Bits 3:0)
0x00000E - Bit 2 - Set if 24hr time format
           Bit 1 - Set if 12hr time format
0x00000F - Checksum of 00:0E

SECTION 2: Time Alarms

0x000010 - Weekday alarm (hour) (reverse BCD)
           Bit 3 - Set if single alarm active
           Bit 2 - Set if weekday-alarm active
0x000011 - Weekday alarm (minute) (reverse BCD)
0x000012 - Single alarm (hour) (reverse BCD) (Bit 3 - Set if pre-alarm active)
0x000013 - Single alarm (minute) (reverse BCD)
0x000014 - Bits 7-4: Pre-alarm (1-5 = 15,30,45,60 or 90 mins)
           Bits 3-0: Snooze value
0x000015 - Checksum of 10:14

SECTION 3: Alternate Location

0x000016 - Latitude (degrees) (reverse BCD)
0x000017 - Latitude (minutes) (reverse BCD)
0x000018 - Longitude (degrees) (reverse BCD)
0x000019 - Longitude (minutes) (reverse BCD)
0x00001A - Bit 7 - Set if Latitude southerly
           Bit 6 - Set if Longitude easterly
           Bit 4 - Set if DST is always on
           Bit 3 - Set if -ve TZ
           Bits 0 & 1 - Set if half-hour TZ
0x00001B - Longitude (100 degrees) (Bits 7:4), DST zone (Bits 3:0)
0x00001C - City code (High) (Bits 7:4), Unknown (Bits 3:0)
0x00001D - Timezone (hour) (Bits 7:4), City code (Low) (Bits 3:0)
0x00001E - Checksum of 16:1D

SECTION 4: Temperature Alarms

0x00001F:20 - High Temp Alarm Value
0x000021:22 - Low Temp Alarm Value
0x000023 - Checksum of 1F:22

SECTION 5: Min/Max 1

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

SECTION 6: Min/Max 2

0x00003E,40 - Max Channel 4 Temp
0x000041 - Min Channel 4 Humidity
0x000042 - Max Channel 4 Humidity
0x000043:44 - Min Channel 4 Temp
0x000045:46 - Max Channel 4 Temp
0x000047 - Min Channel 4 Humidity
0x000048 - Max Channel 4 Humidity
0x000049 - ? Values rising/falling ?
           Bit 5 : Chan 1 temp falling
           Bit 2 : In temp falling
0x00004A:4B - 0xFF (Unused)
0x00004C - Battery status
           Bit 7: Rain
           Bit 6: Wind
           Bit 5: UV
           Bits 4:0: Channel 5:1
0x00004D:58 - 0xFF (Unused)
0x000059 - Checksum of 3E:58

SECTION 7: Altitude

0x00005A:5B - Altitude (Low:High)
0x00005C - Bit 3 - Set if altitude negative
           Bit 2 - Pressure falling?
           Bit 1 - Always set
0X00005D - Checksum of 5A:5C

0x00005E:5F - Unused (0xFF)

SECTION 8: Pressure 1

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

SECTION 9: Pressure 2

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

SECTION 10: Versions

0x000098 - firmware versions (barometer)
0x000099 - firmware versions (uv)
0x00009A - firmware versions (rcc)
0x00009B - firmware versions (wind)
0x00009C - firmware versions (system)
0x00009D - Checksum of 98:9C

0x00009E:9F - 0xFF (Unused)

SECTION 11: Rain/Wind Alarms 1

0x0000A0 - Alarms
           Bit2 - Set if rain alarm active
           Bit 1 - Set if wind alarm active
           Bit 0 - Set if gust alarm active
0x0000A1:A2 - Rain alarm value (High:Low) (BCD)
0x0000A3 - Unknown
0x0000A4:A5 - Wind speed alarm value
0x0000A6 - Unknown
0x0000A7:A8 - Gust alarm value
0x0000A9 - Checksum of A0:A8

SECTION 12: Rain/Wind Alarms 2

0x0000AA:AB - Max daily wind speed
0x0000AC:AD - Max daily gust speed
0x0000AE:AF - Rain bucket count (yesterday) (Low:High)
0x0000B0:B1 - Rain bucket count (week) (Low:High)
0x0000B2:B3 - Rain bucket count (month) (Low:High)
0x0000B4 - Checksum of AA:B3

0x0000B5:E0 - 0xFF (Unused)

SECTION 13: Unknownn

0x0000E1:F9 - 0x15 (Unknown)
0x0000FA  - Checksum of E1:F9

SECTION 14: Archiving

0c0000FB - Unknown
0x0000FC - Memory size (0 = 0x1fff, 2 = 0x20000)
0x0000FD - Number of records (High)
0x0000FE - Archive interval 
           1-11 = 5, 10, 20, 30, 60, 90, 120, 180, 240, 360, 1440 mins
0x0000FF - Number of records (Low)
0x000100 - Checksum of FB:FF

0x000101 - Start of historical records:

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

USB Protocol

The station shows up on the USB as a HID.  Control packet is 8 bytes.

Read from station:
 0x05 (Length)
 0xAF (Read)
 Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), CRC, Unused, Unused

Read acknowledge:
 0x24 (Ack)
 0xAF (Read)
 Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), CRC, Unused, Unused

Write to station:
 0x07 (Length)
 0xAE (Write)
 Addr (Bit 17:16), Addr (Bits 15:8), Addr (Bits (7:0), Data1, Data2, Data3
 ... Data continue with 3 more packets of length 7 then ...
 0x02 (Length), Data32, CRC, Unused, Unused, Unused, Unused, Unused, Unused

Reads returns 32 bytes.  Write expects 32 bytes as well, but address must be
aligned to a memory-map section start address and will only write to that
section.

Schema Additions

The station emits more sensor data than the default schema (wview schema) can
handle.  This driver includes a mapping between the sensor data and the wview
schema, plus additional fields.  To use the default mapping with the wview
schema, these are the additional fields that must be added to the schema:

          ('extraTemp4',           'REAL'),
          ('extraHumid3',          'REAL'),
          ('extraHumid4',          'REAL'),
          ('extraBatteryStatus1',  'REAL'),
          ('extraBatteryStatus2',  'REAL'),
          ('extraBatteryStatus3',  'REAL'),
          ('extraBatteryStatus4',  'REAL'),
          ('windLinkStatus',       'REAL'),
          ('rainLinkStatus',       'REAL'),
          ('uvLinkStatus',         'REAL'),
          ('outLinkStatus',        'REAL'),
          ('extraLinkStatus1',     'REAL'),
          ('extraLinkStatus2',     'REAL'),
          ('extraLinkStatus3',     'REAL'),
          ('extraLinkStatus4',     'REAL'),
          ('forecast',             'REAL'),
          ('storm',                'REAL'),
"""

# TODO: figure out how to read station pressure from station
# TODO: figure out how to clear station memory
# TODO: clear rain total

# FIXME: set-date and sync-date do not work - something reverts the clock
# FIXME: is there any way to get rid of the bad header byte on first read?

from __future__ import with_statement
import syslog
import time
import usb

import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'TE923'
DRIVER_VERSION = '0.17'

def loader(config_dict, engine):  # @UnusedVariable
    return TE923Driver(**config_dict[DRIVER_NAME])

def configurator_loader(config_dict):  # @UnusedVariable
    return TE923Configurator()

def confeditor_loader():
    return TE923ConfEditor()

DEBUG_READ = 1
DEBUG_WRITE = 1
DEBUG_DECODE = 1

# map the station data to the default database schema, plus extensions
DEFAULT_OBSERVATION_MAP = {
    'link_wind': 'windLinkStatus',
    'bat_wind': 'windBatteryStatus',
    'link_rain': 'rainLinkStatus',
    'bat_rain': 'rainBatteryStatus',
    'link_uv': 'uvLinkStatus',
    'bat_uv': 'uvBatteryStatus',
    'uv': 'UV',
    't_in': 'inTemp',
    'h_in': 'inHumidity',
    't_1': 'outTemp',
    'h_1': 'outHumidity',
    'bat_1': 'outBatteryStatus',
    'link_1': 'outLinkStatus',
    't_2': 'extraTemp1',
    'h_2': 'extraHumid1',
    'bat_2': 'extraBatteryStatus1',
    'link_2': 'extraLinkStatus1',
    't_3': 'extraTemp2',
    'h_3': 'extraHumid3',
    'bat_3': 'extraBatteryStatus2',
    'link_3': 'extraLinkStatus2',
    't_4': 'extraTemp3',
    'h_4': 'extraHumid3',
    'bat_4': 'extraBatteryStatus3',
    'link_4': 'extraLinkStatus3',
    't_5': 'extraTemp4',
    'h_5': 'extraHumid4',
    'bat_5': 'extraBatteryStatus4',
    'link_5': 'extraLinkStatus4',
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
    # specific columns in the database schema, use the following map.
    [[map]]
%s
""" % "\n".join(["        %s = %s" % (x, DEFAULT_OBSERVATION_MAP[x]) for x in DEFAULT_OBSERVATION_MAP])


class TE923Configurator(weewx.drivers.AbstractConfigurator):
    LOCSTR = "CITY|USR,LONG_DEG,LONG_MIN,E|W,LAT_DEG,LAT_MIN,N|S,TZ,DST"
    ALMSTR = "WEEKDAY,SINGLE,PRE_ALARM,SNOOZE,MAXTEMP,MINTEMP,RAIN,WIND,GUST"

    idx_to_interval = {
        1: "5 min", 2: "10 min", 3: "20 min", 4: "30 min", 5: "60 min",
        6: "90 min", 7: "2 hour", 8: "3 hour", 9: "4 hour", 10: "6 hour",
        11: "1 day"}

    interval_to_idx = {
        "5m": 1, "10m": 2, "20m": 3, "30m": 4, "60m": 5, "90m": 6,
        "2h": 7, "3h": 8, "4h": 9, "6h": 10, "1d": 11}

    forecast_dict = {
        0: 'heavy snow',
        1: 'light snow',
        2: 'heavy rain',
        3: 'light rain',
        4: 'heavy clouds',
        5: 'light clouds',
        6: 'sunny',
    }

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
        0: ["ADD", 3, 0, 9, 01, "N", 38, 44, "E", "Addis Ababa, Ethiopia"],
        1: ["ADL", 9.5, 1, 34, 55, "S", 138, 36, "E", "Adelaide, Australia"],
        2: ["AKR", 2, 4, 39, 55, "N", 32, 55, "E", "Ankara, Turkey"],
        3: ["ALG", 1, 0, 36, 50, "N", 3, 0, "E", "Algiers, Algeria"],
        4: ["AMS", 1, 4, 52, 22, "N", 4, 53, "E", "Amsterdam, Netherlands"],
        5: ["ARN", 1, 4, 59, 17, "N", 18, 3, "E", "Stockholm Arlanda, Sweden"],
        6: ["ASU", -3, 11, 25, 15, "S", 57, 40, "W", "Asuncion, Paraguay"],
        7: ["ATH", 2, 4, 37, 58, "N", 23, 43, "E", "Athens, Greece"],
        8: ["ATL", -5, 14, 33, 45, "N", 84, 23, "W", "Atlanta, Ga."],
        9: ["AUS", -6, 14, 30, 16, "N", 97, 44, "W", "Austin, Tex."],
       10: ["BBU", 2, 4, 44, 25, "N", 26, 7, "E", "Bucharest, Romania"],
       11: ["BCN", 1, 4, 41, 23, "N", 2, 9, "E", "Barcelona, Spain"],
       12: ["BEG", 1, 4, 44, 52, "N", 20, 32, "E", "Belgrade, Yugoslavia"],
       13: ["BEJ", 8, 0, 39, 55, "N", 116, 25, "E", "Beijing, China"],
       14: ["BER", 1, 4, 52, 30, "N", 13, 25, "E", "Berlin, Germany"],
       15: ["BHM", -6, 14, 33, 30, "N", 86, 50, "W", "Birmingham, Ala."],
       16: ["BHX", 0, 4, 52, 25, "N", 1, 55, "W", "Birmingham, England"],
       17: ["BKK", 7, 0, 13, 45, "N", 100, 30, "E", "Bangkok, Thailand"],
       18: ["BNA", -6, 14, 36, 10, "N", 86, 47, "W", "Nashville, Tenn."],
       19: ["BNE", 10, 0, 27, 29, "S", 153, 8, "E", "Brisbane, Australia"],
       20: ["BOD", 1, 4, 44, 50, "N", 0, 31, "W", "Bordeaux, France"],
       21: ["BOG", -5, 0, 4, 32, "N", 74, 15, "W", "Bogota, Colombia"],
       22: ["BOS", -5, 14, 42, 21, "N", 71, 5, "W", "Boston, Mass."],
       23: ["BRE", 1, 4, 53, 5, "N", 8, 49, "E", "Bremen, Germany"],
       24: ["BRU", 1, 4, 50, 52, "N", 4, 22, "E", "Brussels, Belgium"],
       25: ["BUA", -3, 0, 34, 35, "S", 58, 22, "W", "Buenos Aires, Argentina"],
       26: ["BUD", 1, 4, 47, 30, "N", 19, 5, "E", "Budapest, Hungary"],
       27: ["BWI", -5, 14, 39, 18, "N", 76, 38, "W", "Baltimore, Md."],
       28: ["CAI", 2, 5, 30, 2, "N", 31, 21, "E", "Cairo, Egypt"],
       29: ["CCS", -4, 0, 10, 28, "N", 67, 2, "W", "Caracas, Venezuela"],
       30: ["CCU", 5.5, 0, 22, 34, "N", 88, 24, "E", "Calcutta, India (as Kolkata)"],
       31: ["CGX", -6, 14, 41, 50, "N", 87, 37, "W", "Chicago, IL"],
       32: ["CLE", -5, 14, 41, 28, "N", 81, 37, "W", "Cleveland, Ohio"],
       33: ["CMH", -5, 14, 40, 0, "N", 83, 1, "W", "Columbus, Ohio"],
       34: ["COR", -3, 0, 31, 28, "S", 64, 10, "W", "Cordoba, Argentina"],
       35: ["CPH", 1, 4, 55, 40, "N", 12, 34, "E", "Copenhagen, Denmark"],
       36: ["CPT", 2, 0, 33, 55, "S", 18, 22, "E", "Cape Town, South Africa"],
       37: ["CUU", -6, 14, 28, 37, "N", 106, 5, "W", "Chihuahua, Mexico"],
       38: ["CVG", -5, 14, 39, 8, "N", 84, 30, "W", "Cincinnati, Ohio"],
       39: ["DAL", -6, 14, 32, 46, "N", 96, 46, "W", "Dallas, Tex."],
       40: ["DCA", -5, 14, 38, 53, "N", 77, 2, "W", "Washington, D.C."],
       41: ["DEL", 5.5, 0, 28, 35, "N", 77, 12, "E", "New Delhi, India"],
       42: ["DEN", -7, 14, 39, 45, "N", 105, 0, "W", "Denver, Colo."],
       43: ["DKR", 0, 0, 14, 40, "N", 17, 28, "W", "Dakar, Senegal"],
       44: ["DTW", -5, 14, 42, 20, "N", 83, 3, "W", "Detroit, Mich."],
       45: ["DUB", 0, 4, 53, 20, "N", 6, 15, "W", "Dublin, Ireland"],
       46: ["DUR", 2, 0, 29, 53, "S", 30, 53, "E", "Durban, South Africa"],
       47: ["ELP", -7, 14, 31, 46, "N", 106, 29, "W", "El Paso, Tex."],
       48: ["FIH", 1, 0, 4, 18, "S", 15, 17, "E", "Kinshasa, Congo"],
       49: ["FRA", 1, 4, 50, 7, "N", 8, 41, "E", "Frankfurt, Germany"],
       50: ["GLA", 0, 4, 55, 50, "N", 4, 15, "W", "Glasgow, Scotland"],
       51: ["GUA", -6, 0, 14, 37, "N", 90, 31, "W", "Guatemala City, Guatemala"],
       52: ["HAM", 1, 4, 53, 33, "N", 10, 2, "E", "Hamburg, Germany"],
       53: ["HAV", -5, 6, 23, 8, "N", 82, 23, "W", "Havana, Cuba"],
       54: ["HEL", 2, 4, 60, 10, "N", 25, 0, "E", "Helsinki, Finland"],
       55: ["HKG", 8, 0, 22, 20, "N", 114, 11, "E", "Hong Kong, China"],
       56: ["HOU", -6, 14, 29, 45, "N", 95, 21, "W", "Houston, Tex."],
       57: ["IKT", 8, 8, 52, 30, "N", 104, 20, "E", "Irkutsk, Russia"],
       58: ["IND", -5, 0, 39, 46, "N", 86, 10, "W", "Indianapolis, Ind."],
       59: ["JAX", -5, 14, 30, 22, "N", 81, 40, "W", "Jacksonville, Fla."],
       60: ["JKT", 7, 0, 6, 16, "S", 106, 48, "E", "Jakarta, Indonesia"],
       61: ["JNB", 2, 0, 26, 12, "S", 28, 4, "E", "Johannesburg, South Africa"],
       62: ["KIN", -5, 0, 17, 59, "N", 76, 49, "W", "Kingston, Jamaica"],
       63: ["KIX", 9, 0, 34, 32, "N", 135, 30, "E", "Osaka, Japan"],
       64: ["KUL", 8, 0, 3, 8, "N", 101, 42, "E", "Kuala Lumpur, Malaysia"],
       65: ["LAS", -8, 14, 36, 10, "N", 115, 12, "W", "Las Vegas, Nev."],
       66: ["LAX", -8, 14, 34, 3, "N", 118, 15, "W", "Los Angeles, Calif."],
       67: ["LIM", -5, 0, 12, 0, "S", 77, 2, "W", "Lima, Peru"],
       68: ["LIS", 0, 4, 38, 44, "N", 9, 9, "W", "Lisbon, Portugal"],
       69: ["LON", 0, 4, 51, 32, "N", 0, 5, "W", "London, England"],
       70: ["LPB", -4, 0, 16, 27, "S", 68, 22, "W", "La Paz, Bolivia"],
       71: ["LPL", 0, 4, 53, 25, "N", 3, 0, "W", "Liverpool, England"],
       72: ["LYO", 1, 4, 45, 45, "N", 4, 50, "E", "Lyon, France"],
       73: ["MAD", 1, 4, 40, 26, "N", 3, 42, "W", "Madrid, Spain"],
       74: ["MEL", 10, 1, 37, 47, "S", 144, 58, "E", "Melbourne, Australia"],
       75: ["MEM", -6, 14, 35, 9, "N", 90, 3, "W", "Memphis, Tenn."],
       76: ["MEX", -6, 14, 19, 26, "N", 99, 7, "W", "Mexico City, Mexico"],
       77: ["MIA", -5, 14, 25, 46, "N", 80, 12, "W", "Miami, Fla."],
       78: ["MIL", 1, 4, 45, 27, "N", 9, 10, "E", "Milan, Italy"],
       79: ["MKE", -6, 14, 43, 2, "N", 87, 55, "W", "Milwaukee, Wis."],
       80: ["MNL", 8, 0, 14, 35, "N", 120, 57, "E", "Manila, Philippines"],
       81: ["MOW", 3, 8, 55, 45, "N", 37, 36, "E", "Moscow, Russia"],
       82: ["MRS", 1, 4, 43, 20, "N", 5, 20, "E", "Marseille, France"],
       83: ["MSP", -6, 14, 44, 59, "N", 93, 14, "W", "Minneapolis, Minn."],
       84: ["MSY", -6, 14, 29, 57, "N", 90, 4, "W", "New Orleans, La."],
       85: ["MUC", 1, 4, 48, 8, "N", 11, 35, "E", "Munich, Germany"],
       86: ["MVD", -3, 9, 34, 53, "S", 56, 10, "W", "Montevideo, Uruguay"],
       87: ["NAP", 1, 4, 40, 50, "N", 14, 15, "E", "Naples, Italy"],
       88: ["NBO", 3, 0, 1, 25, "S", 36, 55, "E", "Nairobi, Kenya"],
       89: ["NKG", 8, 0, 32, 3, "N", 118, 53, "E", "Nanjing (Nanking), China"],
       90: ["NYC", -5, 14, 40, 47, "N", 73, 58, "W", "New York, N.Y."],
       91: ["ODS", 2, 4, 46, 27, "N", 30, 48, "E", "Odessa, Ukraine"],
       92: ["OKC", -6, 14, 35, 26, "N", 97, 28, "W", "Oklahoma City, Okla."],
       93: ["OMA", -6, 14, 41, 15, "N", 95, 56, "W", "Omaha, Neb."],
       94: ["OSL", 1, 4, 59, 57, "N", 10, 42, "E", "Oslo, Norway"],
       95: ["PAR", 1, 4, 48, 48, "N", 2, 20, "E", "Paris, France"],
       96: ["PDX", -8, 14, 45, 31, "N", 122, 41, "W", "Portland, Ore."],
       97: ["PER", 8, 0, 31, 57, "S", 115, 52, "E", "Perth, Australia"],
       98: ["PHL", -5, 14, 39, 57, "N", 75, 10, "W", "Philadelphia, Pa."],
       99: ["PHX", -7, 0, 33, 29, "N", 112, 4, "W", "Phoenix, Ariz."],
      100: ["PIT", -5, 14, 40, 27, "N", 79, 57, "W", "Pittsburgh, Pa."],
      101: ["PRG", 1, 4, 50, 5, "N", 14, 26, "E", "Prague, Czech Republic"],
      102: ["PTY", -5, 0, 8, 58, "N", 79, 32, "W", "Panama City, Panama"],
      103: ["RGN", 6.5, 0, 16, 50, "N", 96, 0, "E", "Rangoon, Myanmar"],
      104: ["RIO", -3, 2, 22, 57, "S", 43, 12, "W", "Rio de Janeiro, Brazil"],
      105: ["RKV", 0, 0, 64, 4, "N", 21, 58, "W", "Reykjavik, Iceland"],
      106: ["ROM", 1, 4, 41, 54, "N", 12, 27, "E", "Rome, Italy"],
      107: ["SAN", -8, 14, 32, 42, "N", 117, 10, "W", "San Diego, Calif."],
      108: ["SAT", -6, 14, 29, 23, "N", 98, 33, "W", "San Antonio, Tex."],
      109: ["SCL", -4, 3, 33, 28, "S", 70, 45, "W", "Santiago, Chile"],
      110: ["SEA", -8, 14, 47, 37, "N", 122, 20, "W", "Seattle, Wash."],
      111: ["SFO", -8, 14, 37, 47, "N", 122, 26, "W", "San Francisco, Calif."],
      112: ["SHA", 8, 0, 31, 10, "N", 121, 28, "E", "Shanghai, China"],
      113: ["SIN", 8, 0, 1, 14, "N", 103, 55, "E", "Singapore, Singapore"],
      114: ["SJC", -8, 14, 37, 20, "N", 121, 53, "W", "San Jose, Calif."],
      115: ["SOF", 2, 4, 42, 40, "N", 23, 20, "E", "Sofia, Bulgaria"],
      116: ["SPL", -3, 2, 23, 31, "S", 46, 31, "W", "Sao Paulo, Brazil"],
      117: ["SSA", -3, 0, 12, 56, "S", 38, 27, "W", "Salvador, Brazil"],
      118: ["STL", -6, 14, 38, 35, "N", 90, 12, "W", "St. Louis, Mo."],
      119: ["SYD", 10, 1, 34, 0, "S", 151, 0, "E", "Sydney, Australia"],
      120: ["TKO", 9, 0, 35, 40, "N", 139, 45, "E", "Tokyo, Japan"],
      121: ["TPA", -5, 14, 27, 57, "N", 82, 27, "W", "Tampa, Fla."],
      122: ["TRP", 2, 0, 32, 57, "N", 13, 12, "E", "Tripoli, Libya"],
      123: ["USR", 0, 0, 0, 0, "N", 0, 0, "W", "User defined city"],
      124: ["VAC", -8, 14, 49, 16, "N", 123, 7, "W", "Vancouver, Canada"],
      125: ["VIE", 1, 4, 48, 14, "N", 16, 20, "E", "Vienna, Austria"],
      126: ["WAW", 1, 4, 52, 14, "N", 21, 0, "E", "Warsaw, Poland"],
      127: ["YMX", -5, 14, 45, 30, "N", 73, 35, "W", "Montreal, Que., Can."],
      128: ["YOW", -5, 14, 45, 24, "N", 75, 43, "W", "Ottawa, Ont., Can."],
      129: ["YTZ", -5, 14, 43, 40, "N", 79, 24, "W", "Toronto, Ont., Can."],
      130: ["YVR", -8, 14, 49, 13, "N", 123, 6, "W", "Vancouver, B.C., Can."],
      131: ["YYC", -7, 14, 51, 1, "N", 114, 1, "W", "Calgary, Alba., Can."],
      132: ["ZRH", 1, 4, 47, 21, "N", 8, 31, "E", "Zurich, Switzerland"]
    }
      
    @property
    def version(self):
        return DRIVER_VERSION

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
        parser.add_option("--minmax", dest="minmax", action="store_true",
                          help="display historical min/max data")
        parser.add_option("--get-date", dest="getdate", action="store_true",
                          help="display station date")
        parser.add_option("--set-date", dest="setdate",
                          type=str, metavar="YEAR,MONTH,DAY",
                          help="set station date")
        parser.add_option("--sync-date", dest="syncdate", action="store_true",
                          help="set station date using system clock")
        parser.add_option("--get-location-local", dest="loc_local",
                          action="store_true",
                          help="display local location and timezone")
        parser.add_option("--set-location-local", dest="setloc_local",
                          type=str, metavar=self.LOCSTR,
                          help="set local location and timezone")
        parser.add_option("--get-location-alt", dest="loc_alt",
                          action="store_true",
                          help="display alternate location and timezone")
        parser.add_option("--set-location-alt", dest="setloc_alt",
                          type=str, metavar=self.LOCSTR,
                          help="set alternate location and timezone")
        parser.add_option("--get-altitude", dest="getalt", action="store_true",
                          help="display altitude")
        parser.add_option("--set-altitude", dest="setalt", type=int,
                          metavar="ALT", help="set altitude (meters)")
        parser.add_option("--get-alarms", dest="getalarms",
                          action="store_true", help="display alarms")
        parser.add_option("--set-alarms", dest="setalarms", type=str,
                          metavar=self.ALMSTR, help="set alarm state")
        parser.add_option("--get-interval", dest="getinterval",
                          action="store_true", help="display archive interval")
        parser.add_option("--set-interval", dest="setinterval",
                          type=str, metavar="INTERVAL",
                          help="set archive interval (seconds)")
        parser.add_option("--format", dest="format",
                          type=str, metavar="FORMAT", default='table',
                          help="formats include: table, dict")

    def do_options(self, options, parser, config_dict, prompt):  # @UnusedVariable
        if (options.format.lower() != 'table' and
            options.format.lower() != 'dict'):
            parser.error("Unknown format '%s'.  Known formats include 'table' and 'dict'." % options.format)

        with TE923Station() as station:
            if options.info is not None:
                self.show_info(station, fmt=options.format)
            elif options.current is not None:
                self.show_current(station, fmt=options.format)
            elif options.nrecords is not None:
                self.show_history(station, count=options.nrecords,
                                  fmt=options.format)
            elif options.recmin is not None:
                ts = int(time.time()) - options.recmin * 60
                self.show_history(station, ts=ts, fmt=options.format)
            elif options.minmax is not None:
                self.show_minmax(station)
            elif options.getdate is not None:
                self.show_date(station)
            elif options.setdate is not None:
                self.set_date(station, options.setdate)
            elif options.syncdate:
                self.set_date(station, None)
            elif options.loc_local is not None:
                self.show_location(station, 0)
            elif options.setloc_local is not None:
                self.set_location(station, 0, options.setloc_local)
            elif options.loc_alt is not None:
                self.show_location(station, 1)
            elif options.setloc_alt is not None:
                self.set_location(station, 1, options.setloc_alt)
            elif options.getalt is not None:
                self.show_altitude(station)
            elif options.setalt is not None:
                self.set_altitude(station, options.setalt)
            elif options.getalarms is not None:
                self.show_alarms(station)
            elif options.setalarms is not None:
                self.set_alarms(station, options.setalarms)
            elif options.getinterval is not None:
                self.show_interval(station)
            elif options.setinterval is not None:
                self.set_interval(station, options.setinterval)

    @staticmethod
    def show_info(station, fmt='dict'):
        print 'Querying the station for the configuration...'
        data = station.get_config()
        TE923Configurator.print_data(data, fmt)

    @staticmethod
    def show_current(station, fmt='dict'):
        print 'Querying the station for current weather data...'
        data = station.get_readings()
        TE923Configurator.print_data(data, fmt)

    @staticmethod
    def show_history(station, ts=0, count=0, fmt='dict'):
        print "Querying the station for historical records..."
        for r in station.gen_records(ts, count):
            TE923Configurator.print_data(r, fmt)

    @staticmethod
    def show_minmax(station):
        print "Querying the station for historical min/max data"
        data = station.get_minmax()
        print "Console Temperature Min : %s" % data['t_in_min']
        print "Console Temperature Max : %s" % data['t_in_max']
        print "Console Humidity Min    : %s" % data['h_in_min']
        print "Console Humidity Max    : %s" % data['h_in_max']
        for i in range(1, 6):
            print "Channel %d Temperature Min : %s" % (i, data['t_%d_min' % i])
            print "Channel %d Temperature Max : %s" % (i, data['t_%d_max' % i])
            print "Channel %d Humidity Min    : %s" % (i, data['h_%d_min' % i])
            print "Channel %d Humidity Max    : %s" % (i, data['h_%d_max' % i])
        print "Wind speed max since midnight : %s" % data['windspeed_max']
        print "Wind gust max since midnight  : %s" % data['windgust_max']
        print "Rain yesterday  : %s" % data['rain_yesterday']
        print "Rain this week  : %s" % data['rain_week']
        print "Rain this month : %s" % data['rain_month']
        print "Last Barometer reading : %s" % time.strftime(
            "%Y %b %d %H:%M", time.localtime(data['barometer_ts']))
        for i in range(25):
            print "   T-%02d Hours : %.1f" % (i, data['barometer_%d' % i])

    @staticmethod
    def show_date(station):
        ts = station.get_date()
        tt = time.localtime(ts)
        print "Date: %02d/%02d/%d" % (tt[2], tt[1], tt[0])
        TE923Configurator.print_alignment()

    @staticmethod
    def set_date(station, datestr):
        if datestr is not None:
            date_list = datestr.split(',')
            if len(date_list) != 3:
                print "Bad date '%s', format is YEAR,MONTH,DAY" % datestr
                return
            if int(date_list[0]) < 2000 or int(date_list[0]) > 2099:
                print "Year must be between 2000 and 2099 inclusive"
                return
            if int(date_list[1]) < 1 or int(date_list[1]) > 12:
                print "Month must be between 1 and 12 inclusive"
                return
            if int(date_list[2]) < 1 or int(date_list[2]) > 31:
                print "Day must be between 1 and 31 inclusive"
                return
            tt = time.localtime()
            offset = 1 if tt[3] < 12 else 0
            ts = time.mktime((int(date_list[0]), int(date_list[1]), int(date_list[2]) - offset, 0, 0, 0, 0, 0, 0))
        else:
            ts = time.time()
        station.set_date(ts)
        TE923Configurator.print_alignment()

    def show_location(self, station, loc_type):
        data = station.get_loc(loc_type)
        print "City     : %s (%s)" % (self.city_dict[data['city_time']][9],
                                      self.city_dict[data['city_time']][0])
        degree_sign= u'\N{DEGREE SIGN}'.encode('iso-8859-1')
        print "Location : %03d%s%02d'%s %02d%s%02d'%s" % (
            data['long_deg'], degree_sign, data['long_min'], data['long_dir'],
            data['lat_deg'], degree_sign, data['lat_min'], data['lat_dir'])
        if data['dst_always_on']:
            print "DST      : Always on"
        else:
            print "DST      : %s (%s)" % (self.dst_dict[data['dst']][1],
                                          self.dst_dict[data['dst']][0])

    def set_location(self, station, loc_type, location):
        dst_on = 1
        dst_index = 0
        location_list = location.split(',')
        if len(location_list) == 1 and location_list[0] != "USR":
            city_index = None
            for idx in range(len(self.city_dict)):
                if self.city_dict[idx][0] == location_list[0]:
                    city_index = idx
                    break
            if city_index is None:
                print "City code '%s' not recognized - consult station manual for valid city codes" % location_list[0]
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
                print "Longitude degrees must be between 0 and 180 inclusive"
                return
            if int(location_list[2]) < 0 or int(location_list[2]) > 180:
                print "Longitude minutes must be between 0 and 59 inclusive"
                return
            if location_list[3] != "E" and location_list[3] != "W":
                print "Longitude direction must be E or W"
                return
            if int(location_list[4]) < 0 or int(location_list[4]) > 180:
                print "Latitude degrees must be between 0 and 90 inclusive"
                return
            if int(location_list[5]) < 0 or int(location_list[5]) > 180:
                print "Latitude minutes must be between 0 and 59 inclusive"
                return
            if location_list[6] != "N" and location_list[6] != "S":
                print "Longitude direction must be N or S"
                return
            tz_list = location_list[7].split(':')
            if len(tz_list) != 2:
                print "Bad timezone '%s', format is HOUR:MINUTE" % location_list[7]
                return
            if int(tz_list[0]) < -12 or int(tz_list[0]) > 12:
                print "Timezone hour must be between -12 and 12 inclusive"
                return
            if int(tz_list[1]) != 0 and int(tz_list[1]) != 30:
                print "Timezone minute must be 0 or 30"
                return
            if location_list[8].lower() != 'on':
                dst_on = 0
                dst_index = None
                for idx in range(16):
                    if self.dst_dict[idx][0] == location_list[8]:
                        dst_index = idx
                        break
                if dst_index is None:
                    print "DST code '%s' not recognized - consult station manual for valid DST codes" % location_list[8]
                    return
            else:
                dst_on = 1
                dst_index = 0
            city_index = 123 # user-defined city
            long_deg = int(location_list[1])
            long_min = int(location_list[2])
            long_dir = location_list[3]
            lat_deg = int(location_list[4])
            lat_min = int(location_list[5])
            lat_dir = location_list[6]
            tz_hr = int(tz_list[0])
            tz_min = int(tz_list[1])
        else:
            print "Bad location '%s'" % location
            print "Location format is: %s" % self.LOCSTR
            return
        station.set_loc(loc_type, city_index, dst_on, dst_index, tz_hr, tz_min,
                        lat_deg, lat_min, lat_dir,
                        long_deg, long_min, long_dir)

    @staticmethod
    def show_altitude(station):
        altitude = station.get_alt()
        print "Altitude: %d meters" % altitude

    @staticmethod
    def set_altitude(station, altitude):
        if altitude < -200 or altitude > 5000:
            print "Altitude must be between -200 and 5000 inclusive"
            return
        station.set_alt(altitude)

    @staticmethod
    def show_alarms(station):
        data = station.get_alarms()
        print "Weekday alarm : %02d:%02d (%s)" % (
            data['weekday_hour'], data['weekday_min'], data['weekday_active'])
        print "Single  alarm : %02d:%02d (%s)" % (
            data['single_hour'], data['single_min'], data['single_active'])
        print "Pre-alarm     : %s (%s)" % (
            data['prealarm_period'], data['prealarm_active'])
        if data['snooze'] > 0:
            print "Snooze        : %d mins" % data['snooze']
        else:
            print "Snooze        : Invalid"
        print "Max Temperature Alarm : %s" % data['max_temp']
        print "Min Temperature Alarm : %s" % data['min_temp']
        print "Rain Alarm            : %d mm (%s)" % (
            data['rain'], data['rain_active'])
        print "Wind Speed Alarm      : %s (%s)" % (
            data['windspeed'], data['windspeed_active'])
        print "Wind Gust  Alarm      : %s (%s)" % (
            data['windgust'], data['windgust_active'])

    @staticmethod
    def set_alarms(station, alarm):
        alarm_list = alarm.split(',')
        if len(alarm_list) != 9:
            print "Bad alarm '%s'" % alarm
            print "Alarm format is: %s" % TE923Configurator.ALMSTR
            return
        weekday = alarm_list[0]
        if weekday.lower() != 'off':
            weekday_list = weekday.split(':')
            if len(weekday_list) != 2:
                print "Bad alarm '%s', expected HOUR:MINUTE or OFF" % weekday
                return
            if int(weekday_list[0]) < 0 or int(weekday_list[0]) > 23:
                print "Alarm hours must be between 0 and 23 inclusive"
                return
            if int(weekday_list[1]) < 0 or int(weekday_list[1]) > 59:
                print "Alarm minutes must be between 0 and 59 inclusive"
                return
        single = alarm_list[1]
        if single.lower() != 'off':
            single_list = single.split(':')
            if len(single_list) != 2:
                print "Bad alarm '%s', expected HOUR:MINUTE or OFF" % single
                return
            if int(single_list[0]) < 0 or int(single_list[0]) > 23:
                print "Alarm hours must be between 0 and 23 inclusive"
                return
            if int(single_list[1]) < 0 or int(single_list[1]) > 59:
                print "Alarm minutes must be between 0 and 59 inclusive"
                return
        if alarm_list[2].lower() != 'off' and alarm_list[2] not in ['15', '30', '45', '60', '90']:
            print "Prealarm must be 15, 30, 45, 60, 90 or OFF"
            return
        if int(alarm_list[3]) < 1 or int(alarm_list[3]) > 15:
            print "Snooze must be between 1 and 15 inclusive"
            return
        if float(alarm_list[4]) < -50 or float(alarm_list[4]) > 70:
            print "Temperature alarm must be between -50 and 70 inclusive"
            return
        if float(alarm_list[5]) < -50 or float(alarm_list[5]) > 70:
            print "Temperature alarm must be between -50 and 70 inclusive"
            return
        if alarm_list[6].lower() != 'off' and (int(alarm_list[6]) < 1 or int(alarm_list[6]) > 9999):
            print "Rain alarm must be between 1 and 999 inclusive or OFF"
            return
        if alarm_list[7].lower() != 'off' and (float(alarm_list[7]) < 1 or float(alarm_list[7]) > 199):
            print "Wind alarm must be between 1 and 199 inclusive or OFF"
            return
        if alarm_list[8].lower() != 'off' and (float(alarm_list[8]) < 1 or float(alarm_list[8]) > 199):
            print "Wind alarm must be between 1 and 199 inclusive or OFF"
            return
        station.set_alarms(alarm_list[0], alarm_list[1], alarm_list[2],
                           alarm_list[3], alarm_list[4], alarm_list[5],
                           alarm_list[6], alarm_list[7], alarm_list[8])
        print "Temperature alarms can only be modified via station controls"

    @staticmethod
    def show_interval(station):
        idx = station.get_interval()
        print "Interval: %s" % TE923Configurator.idx_to_interval.get(idx, 'unknown')

    @staticmethod
    def set_interval(station, interval):
        """accept 30s|2h|1d format or raw seconds, but only known intervals"""
        idx = TE923Configurator.interval_to_idx.get(interval)
        if idx is None:
            try:
                ival = int(interval)
                for i in TE923Station.idx_to_interval_sec:
                    if ival == TE923Station.idx_to_interval_sec[i]:
                        idx = i
            except ValueError:
                pass
        if idx is None:
            print "Bad interval '%s'" % interval
            print "Valid intervals are %s" % ','.join(TE923Configurator.interval_to_idx.keys())
            return
        station.set_interval(idx)

    @staticmethod
    def print_data(data, fmt):
        if fmt.lower() == 'table':
            TE923Configurator.print_table(data)
        else:
            print data

    @staticmethod
    def print_table(data):
        for key in sorted(data):
            print "%s: %s" % (key.rjust(16), data[key])

    @staticmethod
    def print_alignment():
        print "  If computer time is not aligned to station time then date"
        print "  may be incorrect by 1 day"


class TE923Driver(weewx.drivers.AbstractDevice):
    """Driver for Hideki TE923 stations."""
    
    def __init__(self, **stn_dict):
        """Initialize the station object.

        polling_interval: How often to poll the station, in seconds.
        [Optional. Default is 10]

        model: Which station model is this?
        [Optional. Default is 'TE923']
        """
        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', DEBUG_READ))
        global DEBUG_WRITE
        DEBUG_WRITE = int(stn_dict.get('debug_write', DEBUG_WRITE))
        global DEBUG_DECODE
        DEBUG_DECODE = int(stn_dict.get('debug_decode', DEBUG_DECODE))

        self._last_rain_loop = None
        self._last_rain_archive = None
        self._last_ts = None

        self.model = stn_dict.get('model', 'TE923')
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 3))
        self.polling_interval = int(stn_dict.get('polling_interval', 10))
        self.obs_map = stn_dict.get('map', DEFAULT_OBSERVATION_MAP)

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('polling interval is %s' % str(self.polling_interval))
        loginf('observation map is %s' % self.obs_map)

        self.station = TE923Station(max_tries=self.max_tries,
                                    retry_wait=self.retry_wait)
        self.station.open()
        loginf('logger capacity %s records' % self.station.get_memory_size())

    def closePort(self):
        if self.station is not None:
            self.station.close()
            self.station = None

    @property
    def hardware_name(self):
        return self.model

#    @property
#    def archive_interval(self):
#        return self.station.get_interval_seconds()

    def genLoopPackets(self):
        while True:
            data = self.station.get_readings()
            status = self.station.get_status()
            packet = self.data_to_packet(data, status=status,
                                         last_rain=self._last_rain_loop,
                                         obs_map=self.obs_map)
            self._last_rain_loop = packet['rainTotal']
            yield packet
            time.sleep(self.polling_interval)

    # same as genStartupRecords, but insert battery status on the last record.
    # when record_generation is hardware, this results in a full suit of sensor
    # data, but with the archive interval calculations done by the hardware.
#    def genArchiveRecords(self, since_ts=0):
#        for data in self.station.gen_records(since_ts):
#            # FIXME: insert battery status on the last record
#            packet = self.data_to_packet(data, status=None,
#                                         last_rain=self._last_rain_archive,
#                                         obs_map=self.obs_map)
#            self._last_rain_archive = packet['rainTotal']
#            if self._last_ts:
#                packet['interval'] = (packet['dateTime'] - self._last_ts) / 60
#                yield packet
#            self._last_ts = packet['dateTime']

    # there is no battery status for historical records.
    def genStartupRecords(self, since_ts=0):
        for data in self.station.gen_records(since_ts):
            packet = self.data_to_packet(data, status=None,
                                         last_rain=self._last_rain_archive,
                                         obs_map=self.obs_map)
            self._last_rain_archive = packet['rainTotal']
            if self._last_ts:
                packet['interval'] = (packet['dateTime'] - self._last_ts) / 60
                yield packet
            self._last_ts = packet['dateTime']

    @staticmethod
    def data_to_packet(data, status=None, last_rain=None,
                       obs_map=DEFAULT_OBSERVATION_MAP):
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

        packet = dict()
        packet['usUnits'] = weewx.METRIC
        packet['dateTime'] = data['dateTime']

        # insert values for T/H sensors based on observation map
        for label in obs_map:
            packet[obs_map[label]] = data.get(label)

        # insert values for battery status if they are available
        if status is not None:
            for label in obs_map:
                if label in status:
                    packet[obs_map[label]] = int(status[label])

        # include the link status - 0 indicates ok, 1 indicates no link
        packet['link_wind'] = 0 if data['windspeed_state'] == STATE_OK else 1
        packet['link_rain'] = 0 if data['rain_state'] == STATE_OK else 1
        packet['link_uv'] = 0 if data['uv_state'] == STATE_OK else 1
        packet['link_1'] = 0 if data['t_1_state'] == STATE_OK else 1
        packet['link_2'] = 0 if data['t_2_state'] == STATE_OK else 1
        packet['link_3'] = 0 if data['t_3_state'] == STATE_OK else 1
        packet['link_4'] = 0 if data['t_4_state'] == STATE_OK else 1
        packet['link_5'] = 0 if data['t_5_state'] == STATE_OK else 1

        packet['windSpeed'] = data.get('windspeed')
        if packet['windSpeed'] is not None:
            packet['windSpeed'] *= 1.60934 # speed is mph; weewx wants km/h
        packet['windDir'] = data.get('winddir')
        if packet['windDir'] is not None:
            packet['windDir'] *= 22.5 # weewx wants degrees

        packet['windGust'] = data.get('windgust')
        if packet['windGust'] is not None:
            packet['windGust'] *= 1.60934 # speed is mph; weewx wants km/h
        packet['windGustDir'] = data.get('winddir')
        if packet['windGustDir'] is not None:
            packet['windGustDir'] *= 22.5 # weewx wants degrees

        packet['rainTotal'] = data['rain']
        if packet['rainTotal'] is not None:
            packet['rainTotal'] *= 0.06578 # weewx wants cm
        packet['rain'] = weewx.wxformulas.calculate_rain(
            packet['rainTotal'], last_rain)

        # some stations report uv
        packet['UV'] = data['uv']

        # station calculates windchill
        packet['windchill'] = data['windchill']

        # station reports baromter (SLP)
        packet['barometer'] = data['slp']

        # forecast and storm fields use the station's algorithms
        packet['forecast'] = data['forecast']
        packet['storm'] = data['storm']

        return packet


STATE_OK = 'ok'
STATE_INVALID = 'invalid'
STATE_NO_LINK = 'no_link'

def _fmt(buf):
    if buf:
        return ' '.join(["%02x" % x for x in buf])
    return ''

def bcd2int(bcd):
    return int(((bcd & 0xf0) >> 4) * 10) + int(bcd & 0x0f)

def rev_bcd2int(bcd):
    return int((bcd & 0xf0) >> 4) + int((bcd & 0x0f) * 10)

def int2bcd(num):
    return int(num / 10) * 0x10 + (num % 10)

def rev_int2bcd(num):
    return (num % 10) * 0x10 + int(num / 10)

def decode(buf):
    data = dict()
    for i in range(6):  # console plus 5 remote channels
        data.update(decode_th(buf, i))
    data.update(decode_uv(buf))
    data.update(decode_pressure(buf))
    data.update(decode_forecast(buf))
    data.update(decode_windchill(buf))
    data.update(decode_wind(buf))
    data.update(decode_rain(buf))
    return data

def decode_th(buf, i):
    if i == 0:
        tlabel = 't_in'
        hlabel = 'h_in'
    else:
        tlabel = 't_%d' % i
        hlabel = 'h_%d' % i
    tstate = '%s_state' % tlabel
    hstate = '%s_state' % hlabel
    offset = i * 3

    if DEBUG_DECODE:
        logdbg("TH%d  BUF[%02d]=%02x BUF[%02d]=%02x BUF[%02d]=%02x" %
               (i, 0 + offset, buf[0 + offset], 1 + offset, buf[1 + offset],
                2 + offset, buf[2 + offset]))
    data = dict()
    data[tlabel], data[tstate] = decode_temp(buf[0 + offset], buf[1 + offset],
                                             i != 0)
    data[hlabel], data[hstate] = decode_humid(buf[2 + offset])
    if DEBUG_DECODE:
        logdbg("TH%d  %s %s %s %s" % (i, data[tlabel], data[tstate],
                                      data[hlabel], data[hstate]))
    return data

def decode_temp(byte1, byte2, remote):
    """decode temperature.  result is degree C."""
    if bcd2int(byte1 & 0x0f) > 9:
        if byte1 & 0x0f == 0x0a:
            return None, STATE_NO_LINK
        else:
            return None, STATE_INVALID
    if byte2 & 0x40 != 0x40 and remote:
        return None, STATE_INVALID
    value = bcd2int(byte1) / 10.0 + bcd2int(byte2 & 0x0f) * 10.0
    if byte2 & 0x20 == 0x20:
        value += 0.05
    if byte2 & 0x80 != 0x80:
        value *= -1
    return value, STATE_OK

def decode_humid(byte):
    """decode humidity.  result is percentage."""
    if bcd2int(byte & 0x0f) > 9:
        if byte & 0x0f == 0x0a:
            return None, STATE_NO_LINK
        else:
            return None, STATE_INVALID
    return bcd2int(byte), STATE_OK

def decode_uv(buf):
    """decode data from uv sensor"""
    data = dict()
    if DEBUG_DECODE:
        logdbg("UVX  BUF[18]=%02x BUF[19]=%02x" % (buf[18], buf[19]))
    if ((buf[18] == 0xaa and buf[19] == 0x0a) or
        (buf[18] == 0xff and buf[19] == 0xff)):
        data['uv_state'] = STATE_NO_LINK
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
        logdbg("UVX  %s %s" % (data['uv'], data['uv_state']))
    return data

def decode_pressure(buf):
    """decode pressure data"""
    data = dict()
    if DEBUG_DECODE:
        logdbg("PRS  BUF[20]=%02x BUF[21]=%02x" % (buf[20], buf[21]))
    if buf[21] & 0xf0 == 0xf0:
        data['slp_state'] = STATE_INVALID
        data['slp'] = None
    else:
        data['slp_state'] = STATE_OK
        data['slp'] = int(buf[21] * 0x100 + buf[20]) * 0.0625
    if DEBUG_DECODE:
        logdbg("PRS  %s %s" % (data['slp'], data['slp_state']))
    return data

# NB: te923tool divides speed/gust by 2.23694 (1 meter/sec = 2.23694 mile/hour)
# NB: wview does not divide speed/gust
# NB: wview multiplies winddir by 22.5, te923tool does not
def decode_wind(buf):
    """decode wind speed, gust, and direction"""
    data = dict()
    if DEBUG_DECODE:
        logdbg("WGS  BUF[25]=%02x BUF[26]=%02x" % (buf[25], buf[26]))
    data['windgust'], data['windgust_state'] = decode_ws(buf[25], buf[26])
    if DEBUG_DECODE:
        logdbg("WGS  %s %s" % (data['windgust'], data['windgust_state']))

    if DEBUG_DECODE:
        logdbg("WSP  BUF[27]=%02x BUF[28]=%02x" % (buf[27], buf[28]))
    data['windspeed'], data['windspeed_state'] = decode_ws(buf[27], buf[28])
    if DEBUG_DECODE:
        logdbg("WSP  %s %s" % (data['windspeed'], data['windspeed_state']))

    if DEBUG_DECODE:
        logdbg("WDR  BUF[29]=%02x" % buf[29])
    data['winddir_state'] = data['windspeed_state']
    data['winddir'] = int(buf[29] & 0x0f)
    if DEBUG_DECODE:
        logdbg("WDR  %s %s" % (data['winddir'], data['winddir_state']))
    
    return data

def decode_ws(byte1, byte2):
    """decode wind speed, result is mph"""
    if bcd2int(byte1 & 0xf0) > 90 or bcd2int(byte1 & 0x0f) > 9:
        if ((byte1 == 0xee and byte2 == 0x8e) or
            (byte1 == 0xff and byte2 == 0xff)):
            return None, STATE_NO_LINK
        else:
            return None, STATE_INVALID
    offset = 100 if byte2 & 0x10 == 0x10 else 0
    value = bcd2int(byte1) / 10.0 + bcd2int(byte2 & 0x0f) * 10.0 + offset
    return value, STATE_OK

# FIXME: figure out how to detect link status between station and rain bucket
# FIXME: according to sebastian, the counter is in the station, not the rain
#        bucket.  so if the link between rain bucket and station is lost, the
#        station will miss rainfall and there is no way to know about it.
# NB: wview treats the raw rain count as millimeters
def decode_rain(buf):
    """rain counter is number of bucket tips, each tip is about 0.03 inches"""
    data = dict()
    if DEBUG_DECODE:
        logdbg("RAIN BUF[30]=%02x BUF[31]=%02x" % (buf[30], buf[31]))
    data['rain_state'] = STATE_OK
    data['rain'] = int(buf[31] * 0x100 + buf[30])
    if DEBUG_DECODE:
        logdbg("RAIN %s %s" % (data['rain'], data['rain_state']))
    return data

def decode_windchill(buf):
    data = dict()
    if DEBUG_DECODE:
        logdbg("WCL  BUF[23]=%02x BUF[24]=%02x" % (buf[23], buf[24]))
    if bcd2int(buf[23] & 0xf0) > 90 or bcd2int(buf[23] & 0x0f) > 9:
        if ((buf[23] == 0xee and buf[24] == 0x8e) or
            (buf[23] == 0xff and buf[24] == 0xff)):
            data['windchill_state'] = STATE_NO_LINK
        else:
            data['windchill_state'] = STATE_INVALID
        data['windchill'] = None
    elif buf[24] & 0x40 != 0x40:
        data['windchill_state'] = STATE_INVALID
        data['windchill'] = None
    else:
        data['windchill_state'] = STATE_OK
        data['windchill'] = bcd2int(buf[23]) / 10.0 \
            + bcd2int(buf[24] & 0x0f) * 10.0
        if buf[24] & 0x20 == 0x20:
            data['windchill'] += 0.05
        if buf[24] & 0x80 != 0x80:
            data['windchill'] *= -1
    if DEBUG_DECODE:
        logdbg("WCL  %s %s" % (data['windchill'], data['windchill_state']))
    return data

def decode_forecast(buf):
    data = dict()
    if DEBUG_DECODE:
        logdbg("STT  BUF[22]=%02x" % buf[22])
    if buf[22] & 0x0f == 0x0f:
        data['storm'] = None
        data['forecast'] = None
    else:
        data['storm'] = 1 if buf[22] & 0x08 == 0x08 else 0
        data['forecast'] = int(buf[22] & 0x07)
    if DEBUG_DECODE:
        logdbg("STT  %s %s" % (data['storm'], data['forecast']))
    return data


class BadRead(weewx.WeeWxIOError):
    """Bogus data length, CRC, header block, or other read failure"""

class BadWrite(weewx.WeeWxIOError):
    """Bogus data length, header block, or other write failure"""

class BadHeader(weewx.WeeWxIOError):
    """Bad header byte"""

class TE923Station(object):
    ENDPOINT_IN = 0x81
    READ_LENGTH = 0x8
    TIMEOUT = 1000

    idx_to_interval_sec = {
        1: 300, 2: 600, 3: 1200, 4: 1800, 5: 3600, 6: 5400, 7: 7200,
        8: 10800, 9: 14400, 10: 21600, 11: 86400}

    def __init__(self, vendor_id=0x1130, product_id=0x6801,
                 max_tries=10, retry_wait=5):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.devh = None
        self.max_tries = max_tries
        self.retry_wait = retry_wait

        self._num_rec = None
        self._num_blk = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type_, value, traceback):  # @UnusedVariable
        self.close()

    def open(self, interface=0):
        dev = self._find_dev(self.vendor_id, self.product_id)
        if not dev:
            logcrt("Cannot find USB device with VendorID=0x%04x ProductID=0x%04x" % (self.vendor_id, self.product_id))
            raise weewx.WeeWxIOError('Unable to find station on USB')

        self.devh = dev.open()
        if not self.devh:
            raise weewx.WeeWxIOError('Open USB device failed')
        self.devh.reset()

        # be sure kernel does not claim the interface
        try:
            self.devh.detachKernelDriver(interface)
        except (AttributeError, usb.USBError):
            pass

        # attempt to claim the interface
        try:
            self.devh.claimInterface(interface)
            self.devh.setAltInterface(interface)
        except usb.USBError, e:
            self.close()
            logcrt("Unable to claim USB interface %s: %s" % (interface, e))
            raise weewx.WeeWxIOError(e)

        # figure out which type of memory this station has
        self.read_memory_size()

    def close(self):
        try:
            self.devh.releaseInterface()
        except (ValueError, usb.USBError), e:
            logerr("release interface failed: %s" % e)
        self.devh = None

    @staticmethod
    def _find_dev(vendor_id, product_id):
        """Find the vendor and product ID on the USB."""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    loginf('Found device on USB bus=%s device=%s' %
                           (bus.dirname, dev.filename))
                    return dev
        return None

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
        while time.time() - start_ts < 1:
            try:
                buf = self.devh.interruptRead(
                    self.ENDPOINT_IN, self.READ_LENGTH, self.TIMEOUT)
                if buf:
                    nbytes = buf[0]
                    if nbytes > 7 or nbytes > len(buf) - 1:
                        raise BadRead("Bogus length during read: %d" % nbytes)
                    rbuf.extend(buf[1:1 + nbytes])
                if len(rbuf) >= 34:
                    break
            except usb.USBError, e:
                if (not e.args[0].find('No data available') and
                    not e.args[0].find('No error')):
                    raise weewx.WeeWxIOError(e)
            time.sleep(0.009) # te923tool is 0.15
        else:
            logdbg("timeout while reading: ignoring bytes: %s" % _fmt(rbuf))
            raise BadRead("Timeout after %d bytes" % len(rbuf))

        if len(rbuf) < 34:
            raise BadRead("Not enough bytes: %d < 34" % len(rbuf))
        elif len(rbuf) != 34:
            loginf("read: wrong number of bytes: %d != 34" % len(rbuf))
        if rbuf[0] != 0x5a:
            raise BadHeader("Bad header byte: %02x != %02x" % (rbuf[0], 0x5a))

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
        wbuf = [0] * 38
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
                reqbuf = [0x2,
                          wbuf[i * 7], wbuf[1 + i * 7],
                          0x00, 0x00, 0x00, 0x00, 0x00]
            else:
                reqbuf = [0x7,
                          wbuf[i * 7], wbuf[1 + i * 7], wbuf[2 + i * 7],
                          wbuf[3 + i * 7], wbuf[4 + i * 7], wbuf[5 + i * 7],
                          wbuf[6 + i * 7]]
            if DEBUG_WRITE:
                logdbg("write: %s" % _fmt(reqbuf))
            ret = self.devh.controlMsg(requestType=0x21,
                                       request=usb.REQ_SET_CONFIGURATION,
                                       value=0x0200,
                                       index=0x0000,
                                       buffer=reqbuf,
                                       timeout=self.TIMEOUT)
            if ret != 8:
                raise BadWrite('Unexpected response: %s != 8' % ret)
            
        # Wait for acknowledgement
        time.sleep(0.1)
        start_ts = time.time()
        rbuf = []
        while time.time() - start_ts < 5:
            try:
                tmpbuf = self.devh.interruptRead(
                    self.ENDPOINT_IN, self.READ_LENGTH, self.TIMEOUT)
                if tmpbuf:
                    nbytes = tmpbuf[0]
                    if nbytes > 7 or nbytes > len(tmpbuf) - 1:
                        raise BadRead("Bogus length during read: %d" % nbytes)
                    rbuf.extend(tmpbuf[1:1 + nbytes])
                if len(rbuf) >= 1:
                    break
            except usb.USBError, e:
                if (not e.args[0].find('No data available') and
                    not e.args[0].find('No error')):
                    raise weewx.WeeWxIOError(e)
            time.sleep(0.009)
        else:
            raise BadWrite("Timeout after %d bytes" % len(rbuf))

        if len(rbuf) != 1:
            loginf("write: ack got wrong number of bytes: %d != 1" % len(rbuf))
        if len(rbuf) == 0:
            raise BadWrite("Bad ack: zero length response")
        elif rbuf[0] != 0x5a:
            raise BadHeader("Bad header byte: %02x != %02x" % (rbuf[0], 0x5a))

    def _read(self, addr):
        if DEBUG_READ:
            logdbg("read: address 0x%06x" % addr)
        for cnt in range(self.max_tries):
            try:
                buf = self._raw_read(addr)
                if DEBUG_READ:
                    logdbg("read: %s" % _fmt(buf))
                return buf
            except (BadRead, BadHeader, usb.USBError), e:
                logerr("Failed attempt %d of %d to read data: %s" %
                       (cnt + 1, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            raise weewx.RetriesExceeded("Read failed after %d tries" %
                                        self.max_tries)

    def _write(self, addr, buf):
        if DEBUG_WRITE:
            logdbg("write: address 0x%06x: %s" % (addr, _fmt(buf)))
        for cnt in range(self.max_tries):
            try:
                self._raw_write(addr, buf)
                return
            except (BadWrite, BadHeader, usb.USBError), e:
                logerr("Failed attempt %d of %d to write data: %s" %
                       (cnt + 1, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            raise weewx.RetriesExceeded("Write failed after %d tries" %
                                        self.max_tries)

    def read_memory_size(self):
        buf = self._read(0xfc)
        if buf[1] == 0:
            self._num_rec = 208
            self._num_blk = 256
            logdbg("detected small memory size")
        elif buf[1] == 2:
            self._num_rec = 3442
            self._num_blk = 4096
            logdbg("detected large memory size")
        else:
            msg = "Unrecognised memory size '%s'" % buf[1]
            logerr(msg)
            raise weewx.WeeWxIOError(msg)

    def get_memory_size(self):
        return self._num_rec

    def gen_blocks(self, count=None):
        """generator that returns consecutive blocks of station memory"""
        if not count:
            count = self._num_blk
        for x in range(0, count * 32, 32):
            buf = self._read(x)
            yield x, buf

    def dump_memory(self):
        for i in range(8):
            buf = self._read(i * 32)
            for j in range(4):
                loginf("%02x : %02x %02x %02x %02x %02x %02x %02x %02x" %
                       (i * 32 + j * 8, buf[1 + j * 8], buf[2 + j * 8],
                        buf[3 + j * 8], buf[4 + j * 8], buf[5 + j * 8],
                        buf[6 + j * 8], buf[7 + j * 8], buf[8 + j * 8]))

    def get_config(self):
        data = dict()
        data.update(self.get_versions())
        data.update(self.get_status())
        data['latitude'], data['longitude'] = self.get_location()
        data['altitude'] = self.get_altitude()
        return data

    def get_versions(self):
        data = dict()
        buf = self._read(0x98)
        data['version_bar']  = buf[1]
        data['version_uv']   = buf[2]
        data['version_rcc']  = buf[3]
        data['version_wind'] = buf[4]
        data['version_sys']  = buf[5]
        return data

    def get_status(self):
        status = dict()
        buf = self._read(0x4c)
        status['bat_rain'] = buf[1] & 0x80 == 0x80
        status['bat_wind'] = buf[1] & 0x40 == 0x40
        status['bat_uv']   = buf[1] & 0x20 == 0x20
        status['bat_5']    = buf[1] & 0x10 == 0x10
        status['bat_4']    = buf[1] & 0x08 == 0x08
        status['bat_3']    = buf[1] & 0x04 == 0x04
        status['bat_2']    = buf[1] & 0x02 == 0x02
        status['bat_1']    = buf[1] & 0x01 == 0x01
        return status

    # FIXME: is this any different than get_alt?
    def get_altitude(self):
        buf = self._read(0x5a)
        if DEBUG_DECODE:
            logdbg("ALT  BUF[1]=%02x BUF[2]=%02x BUF[3]=%02x" %
                   (buf[1], buf[2], buf[3]))
        altitude = buf[2] * 0x100 + buf[1]
        if buf[3] & 0x8 == 0x8:
            altitude *= -1
        if DEBUG_DECODE:
            logdbg("ALT  %s" % altitude)
        return altitude

    # FIXME: is this any different than get_loc?
    def get_location(self):
        buf = self._read(0x06)
        if DEBUG_DECODE:
            logdbg("LOC  BUF[1]=%02x BUF[2]=%02x BUF[3]=%02x BUF[4]=%02x BUF[5]=%02x BUF[6]=%02x" % (buf[1], buf[2], buf[3], buf[4], buf[5], buf[6]))
        latitude = float(rev_bcd2int(buf[1])) + (float(rev_bcd2int(buf[2])) / 60)
        if buf[5] & 0x80 == 0x80:
            latitude *= -1
        longitude = float((buf[6] & 0xf0) / 0x10 * 100) + float(rev_bcd2int(buf[3])) + (float(rev_bcd2int(buf[4])) / 60)
        if buf[5] & 0x40 == 0x00:
            longitude *= -1
        if DEBUG_DECODE:
            logdbg("LOC  %s %s" % (latitude, longitude))
        return latitude, longitude

    def get_readings(self):
        """get sensor readings from the station, return as dictionary"""
        buf = self._read(0x020001)
        data = decode(buf[1:])
        data['dateTime'] = int(time.time() + 0.5)
        return data

    def gen_records(self, since_ts=0, count=None):
        """return requested records from station from oldest to newest.  If
        since_ts is specified, then all records since that time.  If count
        is specified, then at most the count most recent records.  If both
        are specified then at most count records newer than the timestamp."""
        if not count:
            count = self._num_rec
        if count > self._num_rec:
            count = self._num_rec

        buf = self._read(0xfb)
        latest_addr = 0x101 + (buf[3] * 0x100 + buf[5] - 1) * 0x26
        oldest_addr = latest_addr - count * 0x26

        n = 0
        tt = time.localtime(time.time())
        while n < count and oldest_addr + n * 0x26 < latest_addr:
            addr = oldest_addr + n * 0x26
            if addr < 0x101:
                addr += self._num_rec * 0x26
            record = self.get_record(addr, tt.tm_year, tt.tm_mon)
            if record and record['dateTime'] > since_ts:
                yield record
            n += 1

    def get_record(self, addr=None, now_year=None, now_month=None):
        """Return a single record from station and the address of the record
        immediately preceding the single record.

        Each historical record is 38 bytes (0x26) long.  Records start at
        memory address 0x101 (257).  The index of the record after the latest
        is at address 0xfc:0xff (253:255), indicating the offset from the
        starting address.

        On small memory stations, the last 32 bytes of memory are never used.
        On large memory stations, the last 20 bytes of memory are never used.
        """
        buf = self._read(addr)
        if buf[1] == 0xff:
            # no data at this address
            return None

        if now_year is None or now_month is None:
            now = int(time.time())
            tt = time.localtime(now)
            now_year = tt.tm_year
            now_month = tt.tm_mon
        
        year = now_year
        month = buf[1] & 0x0f
        if month > now_month:
            year -= 1
        day = bcd2int(buf[2])
        hour = bcd2int(buf[3])
        minute = bcd2int(buf[4])
        ts = time.mktime((year, month, day, hour, minute, 0, 0, 0, -1))
        if DEBUG_DECODE:
            logdbg("REC  %02x %02x %02x %02x" %
                   (buf[1], buf[2], buf[3], buf[4]))
            logdbg("REC  %d/%02d/%02d %02d:%02d = %d" %
                   (year, month, day, hour, minute, ts))

        tmpbuf = buf[5:16]
        crc1 = buf[16]
        buf = self._read(addr + 0x10) 
        tmpbuf.extend(buf[1:22])
        crc2 = buf[22]
        if DEBUG_DECODE:
            logdbg("CRC  %02x %02x" % (crc1, crc2))
        
        data = decode(tmpbuf)
        data['dateTime'] = int(ts)
        return data

    def _read_minmax(self):
        buf = self._read(0x24)
        tmpbuf = self._read(0x40)
        buf[28:37] = tmpbuf[1:10]
        tmpbuf = self._read(0xaa)
        buf[37:47] = tmpbuf[1:11]
        tmpbuf = self._read(0x60)
        buf[47:74] = tmpbuf[1:28]
        tmpbuf = self._read(0x7c)
        buf[74:101] = tmpbuf[1:28]
        return buf

    def get_minmax(self):
        buf = self._read_minmax()
        data = dict()
        data['t_in_min'], _ = decode_temp(buf[1], buf[2], 0)
        data['t_in_max'], _ = decode_temp(buf[3], buf[4], 0)
        data['h_in_min'], _ = decode_humid(buf[5])
        data['h_in_max'], _ = decode_humid(buf[6])
        for i in range(5):
            label = 't_%d_%%s' % (i + 1)
            data[label % 'min'], _ = decode_temp(buf[7+i*6], buf[8 +i*6], 1)
            data[label % 'max'], _ = decode_temp(buf[9+i*6], buf[10+i*6], 1)
            label = 'h_%d_%%s' % (i + 1)
            data[label % 'min'], _ = decode_humid(buf[11+i*6])
            data[label % 'max'], _ = decode_humid(buf[12+i*6])
        data['windspeed_max'], _ = decode_ws(buf[37], buf[38])
        data['windgust_max'], _ = decode_ws(buf[39], buf[40])
        data['rain_yesterday'] = (buf[42] * 0x100 + buf[41]) * 0.6578
        data['rain_week'] = (buf[44] * 0x100 + buf[43]) * 0.6578
        data['rain_month'] = (buf[46] * 0x100 + buf[45]) * 0.6578
        tt = time.localtime()
        offset = 1 if tt[3] < 12 else 0
        month = bcd2int(buf[47] & 0xf)
        day = bcd2int(buf[48])
        hour = bcd2int(buf[49])
        minute = bcd2int(buf[50])
        year = tt.tm_year
        if month > tt.tm_mon:
            year -= 1
        ts = time.mktime((year, month, day - offset, hour, minute, 0, 0, 0, 0))
        data['barometer_ts'] = ts
        for i in range(25):
            data['barometer_%d' % i] = (buf[52+i*2]*0x100 + buf[51+i*2])*0.0625
        return data

    def _read_date(self):
        buf = self._read(0x0)
        return buf[1:33]

    def _write_date(self, buf):
        self._write(0x0, buf)

    def get_date(self):
        tt = time.localtime()
        offset = 1 if tt[3] < 12 else 0
        buf = self._read_date()
        day = rev_bcd2int(buf[2])
        month = (buf[5] & 0xF0) / 0x10
        year = rev_bcd2int(buf[4]) + 2000
        ts = time.mktime((year, month, day + offset, 0, 0, 0, 0, 0, 0))
        return ts

    def set_date(self, ts):
        tt = time.localtime(ts)
        buf = self._read_date()
        buf[2] = rev_int2bcd(tt[2])
        buf[4] = rev_int2bcd(tt[0] - 2000)
        buf[5] = tt[1] * 0x10 + (tt[6] + 1) * 2 + (buf[5] & 1)
        buf[15] = self._checksum(buf[0:15])
        self._write_date(buf)

    def _read_loc(self, loc_type):
        if loc_type == 0:
            buf = self._read(0x0)
        else:
            buf = self._read(0x16)
        return buf[1:33]
    
    def _write_loc(self, loc_type, buf):
        if loc_type == 0:
            self._write(0x00, buf)
        else:
            self._write(0x16, buf)

    def get_loc(self, loc_type):
        buf = self._read_loc(loc_type)
        offset = 6 if loc_type == 0 else 0
        data = dict()
        data['city_time'] = (buf[6 + offset] & 0xF0) + (buf[7 + offset] & 0xF)
        data['lat_deg'] = rev_bcd2int(buf[0 + offset])
        data['lat_min'] = rev_bcd2int(buf[1 + offset])
        data['lat_dir'] = "S" if buf[4 + offset] & 0x80 == 0x80 else "N"
        data['long_deg'] = (buf[5 + offset] & 0xF0) / 0x10 * 100 + rev_bcd2int(buf[2 + offset])
        data['long_min'] = rev_bcd2int(buf[3 + offset])
        data['long_dir'] = "E" if buf[4 + offset] & 0x40 == 0x40 else "W"
        data['tz_hr'] = (buf[7 + offset] & 0xF0) / 0x10
        if buf[4 + offset] & 0x8 == 0x8:
            data['tz_hr'] *= -1
        data['tz_min'] = 30 if buf[4 + offset] & 0x3 == 0x3 else 0
        if buf[4 + offset] & 0x10 == 0x10:
            data['dst_always_on'] = True
        else:
            data['dst_always_on'] = False
            data['dst'] = buf[5 + offset] & 0xf
        return data

    def set_loc(self, loc_type, city_index, dst_on, dst_index, tz_hr, tz_min,
                lat_deg, lat_min, lat_dir, long_deg, long_min, long_dir):
        buf = self._read_loc(loc_type)
        offset = 6 if loc_type == 0 else 0
        buf[0 + offset] = rev_int2bcd(lat_deg)
        buf[1 + offset] = rev_int2bcd(lat_min)
        buf[2 + offset] = rev_int2bcd(long_deg % 100)
        buf[3 + offset] = rev_int2bcd(long_min)
        buf[4 + offset] = (lat_dir == "S") * 0x80 + (long_dir == "E") * 0x40 + (tz_hr < 0) + dst_on * 0x10 * 0x8 + (tz_min == 30) * 3
        buf[5 + offset] = (long_deg > 99) * 0x10 + dst_index
        buf[6 + offset] = (buf[28] & 0x0F) + int(city_index / 0x10) * 0x10 
        buf[7 + offset] = city_index % 0x10 + abs(tz_hr) * 0x10
        if loc_type == 0:
            buf[15] = self._checksum(buf[0:15])
        else:
            buf[8] = self._checksum(buf[0:8])
        self._write_loc(loc_type, buf)

    def _read_alt(self):
        buf = self._read(0x5a)
        return buf[1:33]

    def _write_alt(self, buf):
        self._write(0x5a, buf)

    def get_alt(self):
        buf = self._read_alt()
        altitude = buf[1] * 0x100 + buf[0]
        if buf[3] & 0x8 == 0x8:
            altitude *= -1
        return altitude

    def set_alt(self, altitude):
        buf = self._read_alt()
        buf[0] = abs(altitude) & 0xff
        buf[1] = abs(altitude) / 0x100
        buf[2] = buf[2] & 0x7 + (altitude < 0) * 0x8
        buf[3] = self._checksum(buf[0:3])
        self._write_alt(buf)

    def _read_alarms(self):
        buf = self._read(0x10)
        tmpbuf = self._read(0x1F)
        buf[33:65] = tmpbuf[1:33]
        tmpbuf = self._read(0xA0)
        buf[65:97] = tmpbuf[1:33]
        return buf[1:97]

    def _write_alarms(self, buf):
        self._write(0x10, buf[0:32])
        self._write(0x1F, buf[32:64])
        self._write(0xA0, buf[64:96])
        
    def get_alarms(self):
        buf = self._read_alarms()
        data = dict()
        data['weekday_active'] = buf[0] & 0x4 == 0x4
        data['single_active'] = buf[0] & 0x8 == 0x8
        data['prealarm_active'] = buf[2] & 0x8 == 0x8
        data['weekday_hour'] = rev_bcd2int(buf[0] & 0xF1)
        data['weekday_min'] = rev_bcd2int(buf[1])
        data['single_hour'] = rev_bcd2int(buf[2] & 0xF1)
        data['single_min'] = rev_bcd2int(buf[3])
        data['prealarm_period'] = (buf[4] & 0xF0) / 0x10
        data['snooze'] = buf[4] & 0xF
        data['max_temp'], _ = decode_temp(buf[32], buf[33], 0)
        data['min_temp'], _ = decode_temp(buf[34], buf[35], 0)
        data['rain_active'] = buf[64] & 0x4 == 0x4
        data['windspeed_active'] = buf[64] & 0x2 == 0x2
        data['windgust_active'] = buf[64] & 0x1 == 0x1
        data['rain'] = bcd2int(buf[66]) * 100 + bcd2int(buf[65])
        data['windspeed'], _ = decode_ws(buf[68], buf[69])
        data['windgust'], _ = decode_ws(buf[71], buf[72])
        return data

    def set_alarms(self, weekday, single, prealarm, snooze,
                   maxtemp, mintemp, rain, wind, gust):
        buf = self._read_alarms()
        if weekday.lower() != 'off':
            weekday_list = weekday.split(':')
            buf[0] = rev_int2bcd(int(weekday_list[0])) | 0x4
            buf[1] = rev_int2bcd(int(weekday_list[1]))
        else:
            buf[0] &= 0xFB
        if single.lower() != 'off':
            single_list = single.split(':')
            buf[2] = rev_int2bcd(int(single_list[0]))
            buf[3] = rev_int2bcd(int(single_list[1]))
            buf[0] |= 0x8
        else:
            buf[0] &= 0xF7
        if (prealarm.lower() != 'off' and
            (weekday.lower() != 'off' or single.lower() != 'off')):
            if int(prealarm) == 15:
                buf[4] = 0x10
            elif int(prealarm) == 30:
                buf[4] = 0x20
            elif int(prealarm) == 45:
                buf[4] = 0x30
            elif int(prealarm) == 60:
                buf[4] = 0x40
            elif int(prealarm) == 90:
                buf[4] = 0x50
            buf[2] |= 0x8
        else:
            buf[2] &= 0xF7
        buf[4] = (buf[4] & 0xF0) + int(snooze)
        buf[5] = self._checksum(buf[0:5])

        buf[32] = int2bcd(int(abs(float(maxtemp)) * 10) % 100)
        buf[33] = int2bcd(int(abs(float(maxtemp)) / 10))
        if float(maxtemp) >= 0:
            buf[33] |= 0x80
        if (abs(float(maxtemp)) * 100) % 10 == 5:
            buf[33] |= 0x20
        buf[34] = int2bcd(int(abs(float(mintemp)) * 10) % 100)
        buf[35] = int2bcd(int(abs(float(mintemp)) / 10))
        if float(mintemp) >= 0:
            buf[35] |= 0x80
        if (abs(float(mintemp)) * 100) % 10 == 5:
            buf[35] |= 0x20
        buf[36] = self._checksum(buf[32:36])

        if rain.lower() != 'off':
            buf[65] = int2bcd(int(rain) % 100)
            buf[66] = int2bcd(int(int(rain) / 100))
            buf[64] |= 0x4
        else:
            buf[64] = buf[64] & 0xFB
        if wind.lower() != 'off':
            buf[68] = int2bcd(int(float(wind) * 10) % 100)
            buf[69] = int2bcd(int(float(wind) / 10))
            buf[64] |= 0x2
        else:
            buf[64] = buf[64] & 0xFD
        if gust.lower() != 'off':
            buf[71] = int2bcd(int(float(gust) * 10) % 100)
            buf[72] = int2bcd(int(float(gust) / 10))
            buf[64] |= 0x1
        else:
            buf[64] |= 0xFE
        buf[73] = self._checksum(buf[64:73])
        self._write_alarms(buf)

    def get_interval(self):
        buf = self._read(0xFE)
        return buf[1]

    def get_interval_seconds(self):
        idx = self.get_interval()
        interval = self.idx_to_interval_sec.get(idx)
        if interval is None:
            msg = "Unrecognized archive interval '%s'" % idx
            logerr(msg)
            raise weewx.WeeWxIOError(msg)
        return interval

    # FIXME: check this - the logic seems dodgey as it drops first element
    def set_interval(self, idx):
        buf = self._read(0xFE)
        buf = buf[1:33]
        buf[0] = idx
        self._write(0xFE, buf)

    @staticmethod
    def _checksum(buf):
        crc = 0x100
        for i in range(len(buf)):
            crc -= buf[i]
            if crc < 0:
                crc += 0x100
        return crc


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/te923.py
#
# by default, output matches that of te923tool
#    te923con                 display current weather readings
#    te923con -d              dump 208 memory records
#    te923con -s              display station status
#
# date; PYTHONPATH=bin python bin/user/te923.py --records 0 > c; date
# 91s
# Thu Dec 10 00:12:59 EST 2015
# Thu Dec 10 00:14:30 EST 2015
# date; PYTHONPATH=bin python bin/weewx/drivers/te923.py --records 0 > b; date
# 531s
# Tue Nov 26 10:37:36 EST 2013
# Tue Nov 26 10:46:27 EST 2013
# date; /home/mwall/src/te923tool-0.6.1/te923con -d > a; date
# 53s
# Tue Nov 26 10:46:52 EST 2013
# Tue Nov 26 10:47:45 EST 2013

if __name__ == '__main__':
    import optparse

    FMT_TE923TOOL = 'te923tool'
    FMT_DICT = 'dict'
    FMT_TABLE = 'table'

    usage = """%prog [options] [--debug] [--help]"""

    def main():
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
                          default=FMT_TE923TOOL,
                          help="format for output: te923tool, table, or dict")
        (options, _) = parser.parse_args()

        if options.version:
            print "te923 driver version %s" % DRIVER_VERSION
            exit(1)

        if options.debug is not None:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        else:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

        if (options.format.lower() != FMT_TE923TOOL and
            options.format.lower() != FMT_TABLE and
            options.format.lower() != FMT_DICT):
            print "Unknown format '%s'.  Known formats include: %s" % (
                options.format, ','.join([FMT_TE923TOOL, FMT_TABLE, FMT_DICT]))
            exit(1)

        with TE923Station() as station:
            if options.status:
                data = station.get_versions()
                data.update(station.get_status())
                if options.format.lower() == FMT_TE923TOOL:
                    print_status(data)
                else:
                    print_data(data, options.format)
            if options.readings:
                data = station.get_readings()
                if options.format.lower() == FMT_TE923TOOL:
                    print_readings(data)
                else:
                    print_data(data, options.format)
            if options.records is not None:
                for data in station.gen_records(count=options.records):
                    if options.format.lower() == FMT_TE923TOOL:
                        print_readings(data)
                    else:
                        print_data(data, options.format)
            if options.blocks is not None:
                for ptr, block in station.gen_blocks(count=options.blocks):
                    print_hex(ptr, block)

    def print_data(data, fmt):
        if fmt.lower() == FMT_TABLE:
            print_table(data)
        else:
            print data

    def print_hex(ptr, data):
        print "0x%06x %s" % (ptr, _fmt(data))

    def print_table(data):
        """output entire dictionary contents in two columns"""
        for key in sorted(data):
            print "%s: %s" % (key.rjust(16), data[key])

    def print_status(data):
        """output status fields in te923tool format"""
        print "0x%x:0x%x:0x%x:0x%x:0x%x:%d:%d:%d:%d:%d:%d:%d:%d" % (
            data['version_sys'], data['version_bar'], data['version_uv'],
            data['version_rcc'], data['version_wind'],
            data['bat_rain'], data['bat_uv'], data['bat_wind'], data['bat_5'],
            data['bat_4'], data['bat_3'], data['bat_2'], data['bat_1'])

    def print_readings(data):
        """output sensor readings in te923tool format"""
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

    def getvalue(data, label, fmt):
        if label + '_state' in data:
            if data[label + '_state'] == STATE_OK:
                return fmt % data[label]
            else:
                return data[label + '_state']
        else:
            if data[label] is None:
                return 'x'
            else:
                return fmt % data[label]

if __name__ == '__main__':
    main()
