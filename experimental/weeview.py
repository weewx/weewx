#!/usr/bin/env python
import npyscreen, curses

# Simple client app for PyMeteostation
# Receive UDP packets transmitted by a broadcasting service

MYPORT = 50000

import sys, json
import socket as sck
import struct
sys.path.append('../bin/')

import weewx
import weewx.units
import weeutil.weeutil
import textwrap
import errno
import math


class MyTestApp(npyscreen.NPSAppManaged):

    keypress_timeout_default = 1

    # socket code
    def onStart(self):
        self.addForm("MAIN", MainForm, name="WeeView", color="IMPORTANT",)
        self.s = sck.socket(sck.AF_INET, sck.SOCK_DGRAM, sck.IPPROTO_UDP)
        self.s.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
        self.s.bind(('', MYPORT))
        mreq = struct.pack("4sl", sck.inet_aton('224.1.1.1'), sck.INADDR_ANY) 
        self.s.setsockopt(sck.IPPROTO_IP, sck.IP_ADD_MEMBERSHIP, mreq)           

    def onCleanExit(self):
        npyscreen.notify_wait("Goodbye!")        
        self.s.close()

class MainForm(npyscreen.SplitForm):

    BAROMETER      = 'Barometer'        ## description of pressure types is on http://www.weewx.com/docs/customizing.htm#Implement_the_driver
    PRESSURE      = 'Raw Pressure'
    ALTIMETER   = 'QNH'
    DEWPOINT      = 'Dew Point'
    outHumidity    = 'Outside Humidity'
    outTemp        = 'Outside Temperature'
    radiation      = 'Radiation'
    rain           = 'Rain'
    rainRate       = 'Rain Rate'
    windDir        = 'Wind Direction'
    windGust       = 'Gust Speed'
    windGustDir    = 'Gust Direction'
    windSpeed      = 'Wind Speed'
    windchill      = 'Wind Chill'
    windgustvec    = 'Gust Vector'
    windvec        = 'Wind Vector'
    winddir        = 'Wind Direction'

    def create(self):

        self.clock = self.add(npyscreen.TitleText, name = 'Time:', value="--", editable=False)
        self.pressure = self.add(npyscreen.TitleText, name = self.PRESSURE +':', value="--", editable=False)
        self.barometer = self.add(npyscreen.TitleText, name = self.BAROMETER +':', value="--", editable=False)
        self.altimeter = self.add(npyscreen.TitleText, name = self.ALTIMETER +':', value="--", editable=False)
        self.dewpoint = self.add(npyscreen.TitleText, name = self.DEWPOINT +':', value="--", editable=False)
        self.windspeed = self.add(npyscreen.TitleText, name = self.windSpeed +':', value="--", editable=False)
        self.winddir = self.add(npyscreen.TitleText, name = self.winddir +':', value="--", editable=False)
        self.outtemp = self.add(npyscreen.TitleText, name = self.outTemp +':', value="--", editable=False)
        self.nextrely = self.get_half_way() +1
        self.messages = self.add(npyscreen.BufferPager, name ='Raw Data',maxlen= 10000, editable=False)
                

    def while_waiting(self):

        packet = '{}'
        try:
            packet, wherefrom = self.parentApp.s.recvfrom(4096)
        except sck.error as (code, msg):
            if code != errno.EINTR:
                raise

        self.data = json.loads(packet)

        if 'pressure' in self.data:
            pressure_data = (self.data['pressure'], 'inHg', 'group_pressure')
            pressure_data = weewx.units.ValueHelper(pressure_data)
            self.pressure.value = pressure_data.hPa

        if 'barometer' in self.data:
            barometer_data = (self.data['barometer'], 'inHg', 'group_pressure')
            barometer_data = weewx.units.ValueHelper(barometer_data)
            self.barometer.value = barometer_data.hPa

        if 'altimeter' in self.data:
            altimeter_data = (self.data['altimeter'], 'inHg', 'group_pressure')
            altimeter_data = weewx.units.ValueHelper(altimeter_data)
            self.altimeter.value = str(int(altimeter_data.hPa.raw)) + " hPa"		## QNH value is rounded down deliberatery.

        if 'dewpoint' in self.data:
            dewpoint_data = (self.data['dewpoint'], "degree_F",  "group_temperature")
            dewpoint_data = weewx.units.ValueHelper(dewpoint_data)
            self.dewpoint.value = dewpoint_data.degree_C

        if 'windSpeed' in self.data:
            windspeed_data = (self.data['windSpeed'], "mile_per_hour",  "group_speed")
            windspeed_data = weewx.units.ValueHelper(windspeed_data)
            self.windspeed.value = windspeed_data.knot

        if 'windDir' in self.data:
            windspeed_data = (self.data['windDir'], "degree_compass", "group_direction")
            windspeed_data = weewx.units.ValueHelper(windspeed_data)
            self.winddir.value = windspeed_data.degree_compass

        if 'outTemp' in self.data:
            outtemp_data = (self.data['outTemp'], "degree_F",  "group_temperature")
            outtemp_data = weewx.units.ValueHelper(outtemp_data)
            self.outtemp.value = outtemp_data.degree_C

        if 'dateTime' in self.data:
            self.clock.value = weeutil.weeutil.timestamp_to_gmtime(self.data['dateTime'])


        self.messages.buffer(textwrap.wrap(str(packet), self.messages.width), scroll_end=True, scroll_if_editing=False)

        self.display()

    def on_ok(self):
        # Exit the application if the OK button is pressed.
        self.parentApp.switchForm(None)

def main():
    TA = MyTestApp()
    TA.run()


if __name__ == '__main__':
    main()
