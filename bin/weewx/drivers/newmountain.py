"""A weewx driver for New Mountain NMEA-0183-based stations."""

import serial
import re
import time
import weewx
import weewx.drivers
import weewx.units
import pynmea2

DRIVER_NAME = 'NewMountain'
DRIVER_VERSION = "0.1"

def loader(config_dict, engine):
    return NewMountain(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return NewMountainConfEditor()

class NewMountain(weewx.drivers.AbstractDevice):
    def __init__(self, **kwargs):
        self.port = kwargs.get('port', '/dev/ttyUSB0')
        self.baudrate = 4800
        self.timeout = 3 # seconds
        self.serial_port = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout
                )
        
    def closePort(self):
        if self.serial_port is not None:
            self.serial_port.close()

    def genLoopPackets(self):
        while True:
            try:
                wimda_packet = self.get_wimda_packet()
                wimda = pynmea2.parse(wimda_packet)
                packet = {}
                packet['usUnits'] = weewx.US
                packet['dateTime'] = int(time.time() + 0.5)
                packet['barometer'] = float(wimda.b_pressure_inch)
                degree_C = (float(wimda.air_temp), 'degree_C', 'group_temperature')
                degree_F = weewx.units.convert(degree_C, 'degree_F')[0]
                packet['outTemp'] = degree_F
                wind_speed_knots = (float(mda.wind_speed_knots), 'knot', 'group_speed')
                wind_speed_mph = weewx.units.convert(wind_speed_knots, 'mile_per_hour')[0]
                packet['windSpeed'] = wind_speed_mph
                packet['windDir'] = float(mda.direction_true)
            except:
                next
            yield packet

    def get_wimda_packet(self):
        buf = ''
        while True:
            chunk = self.serial_port.read(70)
            chunk = chunk.strip('\00')
            buf = buf + chunk
            matches = re.search(r'(\$WIMDA,.*)\n', buf)
            if matches:
                return matches.group(1)

class NewMountainConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[NewMountain]
    # This section is for the NewMountain weather station.
    port = /dev/ttyUSB0
    driver = weewx.drivers.NewMountain
"""

    def prompt_for_settings(self):
        print "Specify the serial device NMEA-0183 data is coming in on."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}

    def get_conf(self, orig_stanza=None):
        if orig_stanza is None:
            return self.default_stanza
        else:
            return orig_stanza

if __name__ == "__main__":
    with NewMountain(
            port = '/dev/ttyUSB4'
            ) as s:
        for packet in s.genLoopPackets():
            print repr(packet)
