#
# Copyright (c) 2020 John Ronan <jronan@tssg.org>
# Copyright (c) 2020 Dylan Gore <dgore@tssg.org>
#   
# Part funded by the ERDF through the Ireland Wales Programme
#
#    See the file LICENSE.txt for your full rights.
#
# Credits to
# Dan Armistead for assistance with RS-485 issues.
#
# Thanks to GILL for publishing the communications protocols.

"""Classes and functions for interfacing with a Gill Metpak Pro

This driver assumes the MetPak Pro message mode is polled. Tested 

Resources for the MetPak Pro station

GILL MetPak PRO, MetPak RG, MetPak User Manual
  http://www.gillinstruments.com/data/manuals/1723-PS-022%20MetPak%20MetPak%20RG%20MetPak%20Pro%20Manual%20Issue%201.pdf

"""


from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

import logging
import serial
import time

import weewx.drivers

# Dictionary containing all MetPak status codes and their meanings except those related to NEMA mode
status_codes = {
    "01": "Wind Sensor Axis 1 failed - U Axis blocked or faulty.",
    "02": "Wind Sensor Axis 2 failed - V Axis blocked or faulty.",
    "04": "Wind Sensor Axis 1 and 2 failed - U and V axis blocked or faulty.",
    "08": "Wind Sensor NVM error - Non Volatile Memory checksum failed, data could be uncalibrated.",
    "09": "Wind Sensor ROM error - Read Only Memory checksum failed, data could be uncalibrated.",
    "0B": "Wind Sensor reading failed - Wind Sensor faulty.",
    "10": "Hygroclip error - Hygroclip faulty.",
    "20": "Dewpoint error - Hub Pec faulty.",
    "40": "Humidity error - Hygroclip faulty.",
    "66": "Wind Sensor Power - Check Wind Sensor is powered.",
    "67": "Wind Sensor RS232 Communications - Check Wind Sensor RS232 wiring",
    "80": "Pressure Sensor Warning - Pressure sensor reading not available/unit faulty.",
}

log = logging.getLogger(__name__)

DRIVER_NAME = 'MetpakPro'
DRIVER_VERSION = '0.1'


def loader(config_dict, _):
    return MetpakProDriver(**config_dict[DRIVER_NAME])


def confeditor_loader():
    return MetpakProConfEditor()


def _fmt(x):
    return ' '.join(["%0.2X" % c for c in x])


class MetpakProDriver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with a Gill Instruments Metpak Pro weather station

    port - serial port
    [Required. Default is /dev/ttyUSB0]

    baudrate - the baudrate the station is configured for
    [Required. Default is 19200]

    mode - what mode the station is in (polled/continuous)
    [Optional. Default is polled]

    node_id - the node ID of the weather station
    [Required. Default is 'Q']

    loop_interval - the time (in seconds) between LOOP packets. (polled mode only)
    [Optional. Default is '2.5']

    max_tries - how often to retry serial communication before giving up
    [Optional. Default is 5]
    """

    def __init__(self, **stn_dict):
        self.model = stn_dict.get('model', 'MetpakPro')
        self.port = stn_dict.get('port', Station.DEFAULT_PORT)
        self.baudrate = int(stn_dict.get('baudrate', Station.DEFAULT_BAUDRATE))
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 3))
        self.mode = stn_dict.get('mode', Station.DEFAULT_MODE)
        self.node_id = stn_dict.get('node_id', Station.DEFAULT_NODE_ID)
        self.loop_interval = float(stn_dict.get('loop_interval', Station.DEFAULT_LOOP_INTERVAL))
        debug_serial = int(stn_dict.get('debug_serial', 0))
        self.last_rain = None

        log.info('Driver version is %s', DRIVER_VERSION)
        log.info('Using serial port %s', self.port)
        self.station = Station(self.port, self.baudrate, self.mode, self.node_id, self.loop_interval, debug_serial=debug_serial)
        self.station.open()

    def closePort(self):
        if self.station:
            self.station.close()
            self.station = None

    @property
    def hardware_name(self):
        return self.model

    def genLoopPackets(self):
        while True:
            packet = dict()
            packet['dateTime'] = int(time.time() + 0.5)
            packet['usUnits'] = weewx.METRICWX
            readings = self.station.get_readings_with_retry(self.max_tries, self.retry_wait)
            data = Station.parse_readings(readings)
            packet.update(data)
            yield packet
            if self.mode != "continuous":
                log.debug("Going to sleep for " + str(self.loop_interval) + " seconds")
                time.sleep(self.loop_interval)


class Station(object):
    # Default config options
    DEFAULT_PORT = '/dev/ttyUSB0'
    DEFAULT_MODE = 'polled'
    DEFAULT_BAUDRATE = 19200
    DEFAULT_NODE_ID = 'Q'
    DEFAULT_LOOP_INTERVAL = 2.5

    def __init__(self, port, baudrate, mode, node_id, loop_interval=0, debug_serial=0):
        self._debug_serial = debug_serial
        self.port = port
        self.baudrate = baudrate
        self.mode = mode
        self.node_id = node_id
        self.timeout = 3  # seconds
        self.loop_interval = loop_interval
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):
        self.close()

    def open(self):
        log.debug("Open serial port %s", self.port)
        self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.serial_port.flushInput()

    def close(self):
        if self.serial_port:
            log.debug("Close serial port %s", self.port)
            self.serial_port.close()
            self.serial_port = None

    def get_readings(self):
        if self.mode != 'continuous':
            # Run in polled mode
            self.serial_port.flushInput()
            self.serial_port.write(b"?Q")
            log.debug("Requested update, waiting for response...")
            time.sleep(1)
            c = self.serial_port.readline()
            if c == b'':
                return None
            else:
                return c
        else:
            # Run in continuous mode
            # Search for the character 'Q', which marks the beginning of a "sentence":
            while True:
                c = self.serial_port.read(2)
                if c == b'\x02Q':
                    break
            # Save the first '!' ...
            buf = bytearray(c)
            # ... then read until we get to a '\r' or '\n'
            while True:
                c = self.serial_port.read(1)
                if c == b'\n' or c == b'\r':
                    break
                buf += c
            if self._debug_serial:
                log.debug("Station said: %s", _fmt(buf))
            return buf

    @staticmethod
    def validate_string(buf):
        """Method to ensure incoming data is valid and the checksum is correct"""
        if buf is not None:
            dataStr = buf.decode()
            # Remove any trailing whitespace/CR chars
            dataStr = dataStr.strip()
            # Print the data string to debug log
            log.debug(dataStr)
            # Get checksum sent by station
            checksum = dataStr[-2:]
            # Remove STX, ETX and checksum from the string
            dataStr = dataStr.replace('\x02', '').replace('\x03'+checksum, '')
            # Calculate checksum
            calc_cksum = 0
            for s in dataStr:
                calc_cksum ^= ord(s)
            # Convert calculated checksum to HEX
            calc_cksum = str(hex(calc_cksum)).lstrip("0").lstrip("x").upper()
            # Compare calculated checksum against the checksum sent by the station
            if calc_cksum != checksum:
                raise weewx.WeeWxIOError("Invalid Checksum %s, expected %s" % (calc_cksum, checksum))
            return buf
        else:
            raise serial.serialutil.SerialException()

    def get_readings_with_retry(self, max_tries=5, retry_wait=3):
        for ntries in range(max_tries):
            try:
                buf = self.get_readings()
                self.validate_string(buf)
                return buf
            except (serial.serialutil.SerialException, weewx.WeeWxIOError) as e:
                log.info("Failed attempt %d of %d to get readings: %s", ntries + 1, max_tries, e)
                time.sleep(retry_wait)
        else:
            msg = "Max retries (%d) exceeded for readings" % max_tries
            log.error(msg)
            raise weewx.RetriesExceeded(msg)

    @staticmethod
    def parse_readings(raw):
        """
        From MetPak Pro Manual. Doc. No. 1723-PS-0022 Page 40

        MetPak Pro Factory Default Data String:
        NODE, DIR,SPEED,PRESS, RH, TEMP, DEWPOINT,PRT,AN1,AN2,DIG1,VOLT, STATUS

        <STX>Q,358,000.03,1008.5,057.1,+017.5,+008.9,,+99998.0006,+99998.0004,0000.000,+04.9,00,<ETX>47

        <STX>       Start of String character (ASCII value 2)
        Q           Default Node Letter 
        358         Wind Direction
        000.03      Wind Speed
        1008.5      Pressure
        057.1       Humidity
        +23.0       Temperature
        +009.4      Dewpoint
        ,,          PRT (PRT not configured)
        +99998.0006 Analogue Input 1 (not configured)
        +99998.0004 Analogue Input 2 (not configured)
        0000.000    Digital Input 1 (not configured)
        +04.9       Supply Voltage
        00          Status code
        <ETX>       End of String character (ASCII value 3)
        47          Checksum

        """
        dataArr = raw.decode('utf-8').replace('+', '').split(',')
        try:
            data = dict()
            data['windDir'] = float(dataArr[1])  # degree_compass
            data['windSpeed'] = float(dataArr[2])  # meter_per_second
            data['pressure'] = float(dataArr[3])  # mbar
            data['outHumidity'] = float(dataArr[4])  # percent
            data['outTemp'] = float(dataArr[5])  # degree_C
            data['dewpoint'] = float(dataArr[6])  # degree_c
            data['rain'] = float(dataArr[10])  # mm
            data['supplyVoltage'] = float(dataArr[11])  # volt

            # Log the status code if there is any issues reported by the station
            status = dataArr[12].upper()
            # If status is not "OK"
            if status != "00":
                if status in status_codes:
                    log.error("Station status: " + status + " " + status_codes[status])
                else:
                    hStatus = int(status, 16)  # convert hex string to int
                    for code in status_codes:
                        if hStatus & int(code, 16) != 0:
                            log.error("Combined Status: " + status + " " + code + " " + status_codes[code])

            return data
        except (weewx.WeeWxIOError, Exception) as e:
            log.error(e)


class MetpakProConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[MetpakPro]
    # This section is for the Gill Metpak Pro weather station.

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cua0
    port = %s
    
    # Baudrate
    baudrate = %s

    # MetPak Pro message mode (either continuous or polled)
    mode = %s
    
    # Node ID (default: Q)
    node_id = %s

    # The time (in seconds) between LOOP packets. (Only used in polled mode)
    loop_interval = %s

    # The driver to use:
    driver = weewx.drivers.metpak_pro
""" % (Station.DEFAULT_PORT, Station.DEFAULT_BAUDRATE, Station.DEFAULT_MODE, Station.DEFAULT_NODE_ID, Station.DEFAULT_LOOP_INTERVAL)

    def prompt_for_settings(self):
        print("Specify the serial port to which the station is connected, for")
        print("example: /dev/ttyUSB0 or /dev/ttyS0 or /dev/cua0.")
        port = self._prompt('port', Station.DEFAULT_PORT)
        print("Choose the baudrate that the MetPak Pro is configured for")
        baudrate = self._prompt('baudrate', Station.DEFAULT_BAUDRATE)
        print("Choose the message mode that the MetPak Pro is configured for")
        mode = self._prompt('mode', Station.DEFAULT_MODE)
        print("Choose MetPak Pro Node ID")
        node_id = self._prompt('node_id', Station.DEFAULT_NODE_ID)
        print("Choose interval between loop packets (seconds)")
        loop_interval = self._prompt('loop_interval', Station.DEFAULT_LOOP_INTERVAL)
        return {'port': port, 'baudrate': baudrate, 'mode': mode, 'node_id': node_id, 'loop_interval': loop_interval}


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python3 bin/weewx/drivers/metpak_pro.py

if __name__ == '__main__':
    import optparse

    import weewx
    import weeutil.logger

    usage = """%prog [options] [--help]"""

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='provide additional debug output in log')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='serial port to which the station is connected',
                      default=Station.DEFAULT_PORT)
    parser.add_option('--baudrate', dest='baudrate', metavar='BAUDRATE',
                      help='station baudrate',
                      default=Station.DEFAULT_BAUDRATE)
    parser.add_option('--mode', dest='mode', metavar='MODE',
                      help='message mode that the station is configured for',
                      default=Station.DEFAULT_MODE)
    parser.add_option('--nodeid', dest='node_id', metavar='NODE_ID',
                      help='station node ID',
                      default=Station.DEFAULT_NODE_ID)
    parser.add_option('--loopinterval', dest='loop_interval', metavar='LOOP_INTERVAL',
                      help='time in seconds between each loop packet',
                      default=Station.DEFAULT_NODE_ID)
    (options, args) = parser.parse_args()

    if options.version:
        print("metpak_pro driver version %s" % DRIVER_VERSION)
        exit(0)

    if options.debug:
        weewx.debug = 1

    weeutil.logger.setup('metpak_pro', {})

    with Station(options.port, options.baudrate, options.mode, options.node_id, options.loop_interval, debug_serial=options.debug) as station:
        while True:
            reading = station.get_readings_with_retry()
            if reading != None:
                print(time.time(), reading.decode('ascii'))
                print(station.parse_readings(reading))
                time.sleep(2)
