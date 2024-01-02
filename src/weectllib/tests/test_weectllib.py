#
#      Copyright (c) 2023-2024 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

import datetime
import unittest

from weectllib import parse_dates


class ParseTest(unittest.TestCase):

    def test_parse_default(self):
        from_val, to_val = parse_dates()
        self.assertIsNone(from_val)
        self.assertIsNone(to_val)

    def test_parse_date(self):
        from_val, to_val = parse_dates(date="2021-05-13")
        self.assertIsInstance(from_val, datetime.date)
        self.assertEqual(from_val, datetime.date(2021, 5, 13))
        self.assertEqual(from_val, to_val)

    def test_parse_datetime(self):
        from_valt, to_valt = parse_dates(date="2021-05-13", as_datetime=True)
        self.assertIsInstance(from_valt, datetime.datetime)
        self.assertEqual(from_valt, datetime.datetime(2021, 5, 13))
        self.assertEqual(from_valt, to_valt)

        from_valt, to_valt = parse_dates(date="2021-05-13T15:47:20", as_datetime=True)
        self.assertIsInstance(from_valt, datetime.datetime)
        self.assertEqual(from_valt, datetime.datetime(2021, 5, 13, 15, 47, 20))

    def test_parse_from(self):
        from_val, to_val = parse_dates(from_date="2021-05-13")
        self.assertIsInstance(from_val, datetime.date)
        self.assertEqual(from_val, datetime.date(2021, 5, 13))
        self.assertIsNone(to_val)

    def test_parse_to(self):
        from_val, to_val = parse_dates(to_date="2021-06-02")
        self.assertIsInstance(to_val, datetime.date)
        self.assertEqual(to_val, datetime.date(2021, 6, 2))
        self.assertIsNone(from_val)

    def test_parse_from_to(self):
        from_val, to_val = parse_dates(from_date="2021-05-13", to_date="2021-06-02")
        self.assertIsInstance(from_val, datetime.date)
        self.assertEqual(from_val, datetime.date(2021, 5, 13))
        self.assertEqual(to_val, datetime.date(2021, 6, 2))

    def test_parse_from_to_time(self):
        from_val, to_val = parse_dates(from_date="2021-05-13T08:30:05",
                                       to_date="2021-06-02T21:11:55",
                                       as_datetime=True)
        self.assertIsInstance(from_val, datetime.datetime)
        self.assertEqual(from_val, datetime.datetime(2021, 5, 13, 8, 30, 5))
        self.assertEqual(to_val, datetime.datetime(2021, 6, 2, 21, 11, 55))
