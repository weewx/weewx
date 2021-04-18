#!/usr/bin/env python
#
# Copyright 2014-2020 Matthew Wall
# See the file LICENSE.txt for your rights.

"""Driver for ADS WS1 weather stations.

Thanks to Kevin and Paul Caccamo for adding the serial-to-tcp capability.

Thanks to Steve (sesykes71) for the testing that made this driver possible.

Thanks to Jay Nugent (WB8TKL) and KRK6 for weather-2.kr6k-V2.1
  http://server1.nuge.com/~weather/
"""

from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

import logging
import time

from six import byte2int

import weewx.drivers
from weewx.units import INHG_PER_MBAR, MILE_PER_KM
import weewx.wxformulas

log = logging.getLogger(__name__)

DRIVER_NAME = 'WS1'
DRIVER_VERSION = '0.5'


def loader(config_dict, _):
    return WS1Driver(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WS1ConfEditor()


DEFAULT_SER_PORT = '/dev/ttyS0'
DEFAULT_TCP_ADDR = '192.168.36.25'
DEFAULT_TCP_PORT = 3000
PACKET_SIZE = 50
DEBUG_READ = 0


class WS1Driver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with an ADS-WS1 station

    mode - Communication mode - TCP, UDP, or Serial.
    [Required. Default is serial]

    port - Serial port or network address.
    [Required. Default is /dev/ttyS0 for serial,
     and 192.168.36.25:3000 for TCP/IP]

    max_tries - how often to retry serial communication before giving up.
    [Optional. Default is 5]

    wait_before_retry - how long to wait, in seconds, before retrying after a failure.
    [Optional. Default is 10]

    timeout - The amount of time, in seconds, before the connection fails if
    there is no response.
    [Optional. Default is 3]

    debug_read - The level of message logging. The higher this number, the more
    information is logged.
    [Optional. Default is 0]
    """
    def __init__(self, **stn_dict):
        log.info('driver version is %s' % DRIVER_VERSION)

        con_mode = stn_dict.get('mode', 'serial').lower()
        if con_mode == 'tcp' or con_mode == 'udp':
            port = stn_dict.get('port', '%s:%d' % (DEFAULT_TCP_ADDR, DEFAULT_TCP_PORT))
        elif con_mode == 'serial':
            port = stn_dict.get('port', DEFAULT_SER_PORT)
        else:
            raise ValueError("Invalid driver connection mode %s" % con_mode)

        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 10))
        timeout = int(stn_dict.get('timeout', 3))

        self.last_rain = None

        log.info('using %s port %s' % (con_mode, port))

        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', DEBUG_READ))

        if con_mode == 'tcp' or con_mode == 'udp':
            self.station = StationSocket(port, protocol=con_mode, 
                                         timeout=timeout,
                                         max_tries=self.max_tries, 
                                         wait_before_retry=self.wait_before_retry)
        else:
            self.station = StationSerial(port, timeout=timeout)
        self.station.open()

    def closePort(self):
        if self.station is not None:
            self.station.close()
            self.station = None

    @property
    def hardware_name(self):
        return "WS1"

    def genLoopPackets(self):
        while True:
            packet = {'dateTime': int(time.time() + 0.5),
                      'usUnits': weewx.US}
            readings = self.station.get_readings_with_retry(self.max_tries,
                                                            self.wait_before_retry)
            data = StationData.parse_readings(readings)
            packet.update(data)
            self._augment_packet(packet)
            yield packet

    def _augment_packet(self, packet):
        # calculate the rain delta from rain total
        packet['rain'] = weewx.wxformulas.calculate_rain(packet.get('rain_total'), self.last_rain)
        self.last_rain = packet.get('rain_total')


# =========================================================================== #
#       Station data class - parses and validates data from the device        #
# =========================================================================== #


class StationData(object):
    def __init__(self):
        pass

    @staticmethod
    def validate_string(buf):
        if len(buf) != PACKET_SIZE:
            raise weewx.WeeWxIOError("Unexpected buffer length %d" % len(buf))
        if buf[0:2] != b'!!':
            raise weewx.WeeWxIOError("Unexpected header bytes '%s'" % buf[0:2])
        return buf

    @staticmethod
    def parse_readings(raw):
        """WS1 station emits data in PeetBros format:

        http://www.peetbros.com/shop/custom.aspx?recid=29

        Each line has 50 characters - 2 header bytes and 48 data bytes:

        !!000000BE02EB000027700000023A023A0025005800000000
          SSSSXXDDTTTTLLLLPPPPttttHHHHhhhhddddmmmmRRRRWWWW

          SSSS - wind speed (0.1 kph)
          XX   - wind direction calibration
          DD   - wind direction (0-255)
          TTTT - outdoor temperature (0.1 F)
          LLLL - long term rain (0.01 in)
          PPPP - barometer (0.1 mbar)
          tttt - indoor temperature (0.1 F)
          HHHH - outdoor humidity (0.1 %)
          hhhh - indoor humidity (0.1 %)
          dddd - date (day of year)
          mmmm - time (minute of day)
          RRRR - daily rain (0.01 in)
          WWWW - one minute wind average (0.1 kph)
        """
        # FIXME: peetbros could be 40 bytes or 44 bytes, what about ws1?
        # FIXME: peetbros uses two's complement for temp, what about ws1?
        buf = raw[2:].decode('ascii')
        data = dict()
        data['windSpeed'] = StationData._decode(buf[0:4], 0.1 * MILE_PER_KM) # mph
        data['windDir'] = StationData._decode(buf[6:8], 1.411764)  # compass deg
        data['outTemp'] = StationData._decode(buf[8:12], 0.1, True)  # degree_F
        data['rain_total'] = StationData._decode(buf[12:16], 0.01)  # inch
        data['barometer'] = StationData._decode(buf[16:20], 0.1 * INHG_PER_MBAR)  # inHg
        data['inTemp'] = StationData._decode(buf[20:24], 0.1, True)  # degree_F
        data['outHumidity'] = StationData._decode(buf[24:28], 0.1)  # percent
        data['inHumidity'] = StationData._decode(buf[28:32], 0.1)  # percent
        data['day_of_year'] = StationData._decode(buf[32:36])
        data['minute_of_day'] = StationData._decode(buf[36:40])
        data['daily_rain'] = StationData._decode(buf[40:44], 0.01)  # inch
        data['wind_average'] = StationData._decode(buf[44:48], 0.1 * MILE_PER_KM)  # mph
        return data

    @staticmethod
    def _decode(s, multiplier=None, neg=False):
        v = None
        try:
            v = int(s, 16)
            if neg:
                bits = 4 * len(s)
                if v & (1 << (bits - 1)) != 0:
                    v -= (1 << bits)
            if multiplier is not None:
                v *= multiplier
        except ValueError as e:
            if s != '----':
                log.debug("decode failed for '%s': %s" % (s, e))
        return v


# =========================================================================== #
#          Station Serial class - Gets data through a serial port             #
# =========================================================================== #


class StationSerial(object):
    def __init__(self, port, timeout=3):
        self.port = port
        self.baudrate = 2400
        self.timeout = timeout
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):  # @UnusedVariable
        self.close()

    def open(self):
        import serial
        log.debug("open serial port %s" % self.port)
        self.serial_port = serial.Serial(self.port, self.baudrate,
                                         timeout=self.timeout)

    def close(self):
        if self.serial_port is not None:
            log.debug("close serial port %s" % self.port)
            self.serial_port.close()
            self.serial_port = None

    # FIXME: use either CR or LF as line terminator.  apparently some ws1
    # hardware occasionally ends a line with only CR instead of the standard
    # CR-LF, resulting in a line that is too long.
    def get_readings(self):
        buf = self.serial_port.readline()
        if DEBUG_READ >= 2:
            log.debug("bytes: '%s'" % ' '.join(["%0.2X" % byte2int(c) for c in buf]))
        buf = buf.strip()
        return buf

    def get_readings_with_retry(self, max_tries=5, wait_before_retry=10):
        import serial
        for ntries in range(max_tries):
            try:
                buf = self.get_readings()
                StationData.validate_string(buf)
                return buf
            except (serial.serialutil.SerialException, weewx.WeeWxIOError) as e:
                log.info("Failed attempt %d of %d to get readings: %s" %
                         (ntries + 1, max_tries, e))
                time.sleep(wait_before_retry)
        else:
            msg = "Max retries (%d) exceeded for readings" % max_tries
            log.error(msg)
            raise weewx.RetriesExceeded(msg)


# =========================================================================== #
#          Station TCP class - Gets data through a TCP/IP connection          #
#                  For those users with a serial->TCP adapter                 #
# =========================================================================== #


class StationSocket(object):
    def __init__(self, addr, protocol='tcp', timeout=3, max_tries=5,
                 wait_before_retry=10):
        import socket

        self.max_tries = max_tries
        self.wait_before_retry = wait_before_retry

        if addr.find(':') != -1:
            self.conn_info = addr.split(':')
            self.conn_info[1] = int(self.conn_info[1], 10)
            self.conn_info = tuple(self.conn_info)
        else:
            self.conn_info = (addr, DEFAULT_TCP_PORT)

        try:
            if protocol == 'tcp':
                self.net_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM)
            elif protocol == 'udp':
                self.net_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM)
        except (socket.error, socket.herror) as ex:
            log.error("Cannot create socket for some reason: %s" % ex)
            raise weewx.WeeWxIOError(ex)

        self.net_socket.settimeout(timeout)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):  # @UnusedVariable
        self.close()

    def open(self):
        import socket

        log.debug("Connecting to %s:%d." % (self.conn_info[0], self.conn_info[1]))

        for conn_attempt in range(self.max_tries):
            try:
                if conn_attempt > 1:
                    log.debug("Retrying connection...")
                self.net_socket.connect(self.conn_info)
                break
            except (socket.error, socket.timeout, socket.herror) as ex:
                log.error("Cannot connect to %s:%d for some reason: %s. %d tries left." % (
                    self.conn_info[0], self.conn_info[1], ex,
                    self.max_tries - (conn_attempt + 1)))
                log.debug("Will retry in %.2f seconds..." % self.wait_before_retry)
                time.sleep(self.wait_before_retry)
        else:
            log.error("Max tries (%d) exceeded for connection." % self.max_tries)
            raise weewx.RetriesExceeded("Max tries exceeding while attempting connection")

    def close(self):
        import socket

        log.debug("Closing connection to %s:%d." % (self.conn_info[0], self.conn_info[1]))
        try:
            self.net_socket.close()
        except (socket.error, socket.herror, socket.timeout) as ex:
            log.error("Cannot close connection to %s:%d. Reason: %s"
                      % (self.conn_info[0], self.conn_info[1], ex))
            raise weewx.WeeWxIOError(ex)

    def get_data(self, num_bytes=8):
        """Get data from the socket connection
        Args:
            num_bytes: The number of bytes to request.
        Returns:
            bytes: The data from the remote device.
        """

        import socket
        try:
            data = self.net_socket.recv(num_bytes, socket.MSG_WAITALL)
        except Exception as ex:
            raise weewx.WeeWxIOError(ex)
        else:
            if len(data) == 0:
                raise weewx.WeeWxIOError("No data recieved")

            return data

    def find_record_start(self):
        """Find the start of a data record by requesting data from the remote
           device until we find it.
        Returns:
            bytes: The start of a data record from the remote device.
        """
        if DEBUG_READ >= 2:
            log.debug("Attempting to find record start..")

        buf = bytes("", "utf-8")
        while True:
            data = self.get_data()

            if DEBUG_READ >= 2:
                log.debug("(searching...) buf: %s" % buf.decode('utf-8'))
            # split on line breaks and take everything after the line break
            data = data.splitlines()[-1]
            if b"!!" in data:
                # if it contains !!, take everything after the last occurance of !! (we sometimes see a whole bunch of !)
                buf = data.rpartition(b"!!")[-1]
                if len(buf) > 0:
                    # if there is anything left, add the !! back on and break
                    # we have effectively found everything between a line break and !!
                    buf = b"!!" + buf
                    if DEBUG_READ >= 2:
                        log.debug("Record start found!")
                    break
        return buf


    def fill_buffer(self, buf):
        """Get the remainder of the data record from the remote device.
        Args:
            buf: The beginning of the data record.
        Returns:
            bytes: The data from the remote device.
        """
        if DEBUG_READ >= 2:
            log.debug("filling buffer with rest of record")
        while True:
            data = self.get_data()

            # split on line breaks and take everything before it
            data = data.splitlines()[0]
            buf = buf + data
            if DEBUG_READ >= 2:
                log.debug("buf is %s" % buf.decode('utf-8'))
            if len(buf) == 50:
                if DEBUG_READ >= 2:
                    log.debug("filled record %s" % buf.decode('utf-8'))
                break
        return buf

    def get_readings(self):
        buf = self.find_record_start()
        if DEBUG_READ >= 2:
            log.debug("record start: %s" % buf.decode('utf-8'))
        buf = self.fill_buffer(buf)
        if DEBUG_READ >= 1:
            log.debug("Got data record: %s" % buf.decode('utf-8'))
        return buf

    def get_readings_with_retry(self, max_tries=5, wait_before_retry=10):
        for _ in range(max_tries):
            buf = bytes("", "utf-8")
            try:
                buf = self.get_readings()
                StationData.validate_string(buf)
                return buf
            except (weewx.WeeWxIOError) as e:
                log.debug("Failed to get data. Reason: %s" % e)

                # NOTE: WeeWx IO Errors may not always occur because of
                # invalid data. These kinds of errors are also caused by socket
                # errors and timeouts.

                if DEBUG_READ >= 1:
                    log.debug("buf: %s (%d bytes)" % (buf.decode('utf-8'), len(buf)))

                time.sleep(wait_before_retry)
        else:
            msg = "Max retries (%d) exceeded for readings" % max_tries
            log.error(msg)
            raise weewx.RetriesExceeded(msg)


class WS1ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WS1]
    # This section is for the ADS WS1 series of weather stations.

    # Driver mode - tcp, udp, or serial
    mode = serial

    # If serial, specify the serial port device. (ex. /dev/ttyS0, /dev/ttyUSB0,
    # or /dev/cuaU0)
    # If TCP, specify the IP address and port number. (ex. 192.168.36.25:3000)
    port = /dev/ttyUSB0

    # The amount of time, in seconds, before the connection fails if there is
    # no response
    timeout = 3

    # The driver to use:
    driver = weewx.drivers.ws1
"""

    def prompt_for_settings(self):
        print("How is the station connected? tcp, udp, or serial.")
        con_mode = self._prompt('mode', 'serial')
        con_mode = con_mode.lower()

        if con_mode == 'serial':
            print("Specify the serial port on which the station is connected, ")
            "for example: /dev/ttyUSB0 or /dev/ttyS0."
            port = self._prompt('port', '/dev/ttyUSB0')
        elif con_mode == 'tcp' or con_mode == 'udp':
            print("Specify the IP address and port of the station. For ")
            "example: 192.168.36.40:3000."
            port = self._prompt('port', '192.168.36.40:3000')

        print("Specify how long to wait for a response, in seconds.")
        timeout = self._prompt('timeout', 3)

        return {'mode': con_mode, 'port': port, 'timeout': timeout}


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/ws1.py
# PYTHONPATH=/usr/share/weewx python3 /usr/share/weewx/weewx/drivers/ws1.py

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
                      help='serial port to which the station is connected to use Serial mode',
                      default=DEFAULT_SER_PORT)
    parser.add_option('--addr', dest='addr', metavar='ADDR',
                      help='ip address and port to use TCP mode',
                      default=DEFAULT_TCP_ADDR)
    
    (options, args) = parser.parse_args()

    if options.version:
        print("ADS WS1 driver version %s" % DRIVER_VERSION)
        exit(0)

    if options.debug:
        weewx.debug = 2
        DEBUG_READ = 2

    weeutil.logger.setup('ws1', {})

    Station = StationSerial
    if options.addr is not None:
        Station = StationSocket

    with Station(options.addr) as s:
        while True:
            print(time.time(), s.get_readings().decode("utf-8"))
