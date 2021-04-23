#
#    Copyright (c) 2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the ultimeter driver using mock"""
import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
    from unittest.mock import patch
except ImportError:
    # Python 2 --- must have mock installed
    import mock
    from mock import patch

import six

import weewx.drivers.ultimeter


class StopTest(Exception):
    """Raised when it's time to stop the test"""


def gen_bytes():
    """Return bytes one-by-one

    Returns:
        byte: A byte string containing a single byte.
    """
    # This includes some leading nonsense bytes (b'01212'):
    for c in b'01212!!005100BE02EB0064277002A8023A023A0025005800000000\r\n':
        if six.PY2:
            # Under Python 2, c is already a byte string
            yield c
        else:
            # Under Python 3, c is an int. Convert to type bytes
            yield six.int2byte(c)
    # Because genLoopPackets() is intended to run forever, we need something to break the loop
    # and stop the test.
    raise StopTest


# Midnight, 1-Jan-2021 PST
KNOWN_TIME = 1609488000

expected_packet = {
    'daily_rain': 0.0, 'barometer': 29.81, 'wind_average': 0.0,
    'outHumidity': 57.0, 'day_of_year': 37, 'rain': None, 'dateTime': KNOWN_TIME,
    'windDir': 268.24, 'outTemp': 74.7, 'windSpeed': 5.03, 'inHumidity': 57.0,
    'inTemp': 68.0, 'minute_of_day': 88, 'rain_total': 1.0, 'usUnits': 1
}


class UltimeterTest(unittest.TestCase):

    def test_decode(self):
        self.assertEqual(weewx.drivers.ultimeter.decode(bytes(b'0123')), 291)
        self.assertIsNone(weewx.drivers.ultimeter.decode(bytes(b'----')))
        self.assertEqual(weewx.drivers.ultimeter.decode(bytes(b'FF85'), neg=True), -123)

    @patch('weewx.drivers.ultimeter.time')
    @patch('weewx.drivers.ultimeter.serial.Serial')
    def test_get_readings(self, mock_serial, mock_time):

        # This is so time.time() returns a known value.
        mock_time.time.return_value = KNOWN_TIME

        # Get a new UltimeterDriver(). It will have a mocked serial port.
        # That is, station_driver.serial_port will be a Mock object.
        station_driver = weewx.drivers.ultimeter.UltimeterDriver()
        with self.assertRaises(StopTest):

            # Serial port read() should return the values from gen_bytes()
            station_driver.station.serial_port.read.side_effect = gen_bytes()

            packets = 0
            # Get packets from the fake serial port.
            for packet in station_driver.genLoopPackets():
                packets += 1
                # Check to make sure all the observation types match
                for obs_type in packet:
                    self.assertAlmostEqual(packet[obs_type], expected_packet[obs_type], 2,
                                           "%s %s != %s within 2 decimal places"
                                           % (obs_type,
                                              packet[obs_type],
                                              expected_packet[obs_type]))
        self.assertEqual(packets, 1, "Function genLoopPackets() called %d times, "
                                     "instead of once and only once" % packets)

        station_driver.closePort()
        self.assertIsNone(station_driver.station)


if __name__ == '__main__':
    unittest.main()
