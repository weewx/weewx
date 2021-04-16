#
#    Copyright (c) 2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the ultimeter driver"""
import unittest

from weewx.drivers.ultimeter import Station

class UltimeterTest(unittest.TestCase):

    def test_decode(self):
        self.assertEqual(Station._decode(bytes(b'0123')), 291)
        self.assertIsNone(Station._decode(bytes(b'----')))
        self.assertEqual(Station._decode(bytes(b'FF85'), neg=True), -123)



if __name__ == '__main__':
    unittest.main()

