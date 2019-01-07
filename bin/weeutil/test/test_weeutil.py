# This Python file uses the following encoding: utf-8
#
#    Copyright (c) 2009-2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test routines for weeutil.weeutil."""

from __future__ import with_statement

import unittest

from weeutil.weeutil import *  # @UnusedWildImport

os.environ['TZ'] = 'America/Los_Angeles'


def timestamp_to_local(ts):
    """Return a string in local time"""
    return timestamp_to_string(ts, "%Y-%m-%d %H:%M:%S")


class WeeutilTest(unittest.TestCase):

    def test_convertToFloat(self):

        self.assertEqual(convertToFloat(['1.0', '2.0', 'None', 'none', '5.0', '6.0']),
                         [1.0, 2.0, None, None, 5.0, 6.0])
        self.assertIsNone(convertToFloat(None))

    def test_option_as_list(self):

        self.assertEqual(option_as_list("abc"), ['abc'])
        self.assertEqual(option_as_list(['a', 'b']), ['a', 'b'])
        self.assertEqual(option_as_list(None), None)
        self.assertEqual(option_as_list(''), [''])

    def test_list_as_string(self):
        self.assertEqual(list_as_string('a string'), "a string")
        self.assertEqual(list_as_string(['a', 'string']), "a, string")
        self.assertEqual(list_as_string('Reno, NV'), "Reno, NV")

    def test_stampgen(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Test the start of DST using a 30 minute increment:
        start = time.mktime((2013, 3, 10, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 3, 10, 6, 0, 0, 0, 0, -1))
        result = list(stampgen(start, stop, 1800))
        self.assertEqual(result, [1362902400, 1362904200, 1362906000, 1362907800,
                                  1362909600, 1362911400, 1362913200, 1362915000,
                                  1362916800, 1362918600, 1362920400])

        # Test the ending of DST using a 30 minute increment:
        start = time.mktime((2013, 11, 3, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 11, 3, 6, 0, 0, 0, 0, -1))
        result = list(stampgen(start, stop, 1800))
        self.assertEqual(result, [1383462000, 1383463800, 1383465600, 1383467400,
                                  1383472800, 1383474600, 1383476400, 1383478200,
                                  1383480000, 1383481800, 1383483600, 1383485400,
                                  1383487200])

        # Test the start of DST using a 3 hour increment
        start = time.mktime((2013, 3, 9, 12, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 3, 10, 11, 0, 0, 0, 0, -1))
        result = list(stampgen(start, stop, 10800))
        self.assertEqual(result, [1362859200, 1362870000, 1362880800, 1362891600,
                                  1362902400, 1362909600, 1362920400, 1362931200])

        # Test the end of DST using a 3 hour increment
        start = time.mktime((2013, 11, 2, 12, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 11, 3, 12, 0, 0, 0, 0, -1))
        result = list(stampgen(start, stop, 10800))
        self.assertEqual(result, [1383418800, 1383429600, 1383440400, 1383451200,
                                  1383462000, 1383476400, 1383487200, 1383498000, 1383508800])

        # Test for month increment
        start = time.mktime((2013, 1, 1, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2014, 1, 1, 0, 0, 0, 0, 0, -1))
        result = list(stampgen(start, stop, 365.25 / 12 * 24 * 3600))
        self.assertEqual(result, [1357027200, 1359705600, 1362124800, 1364799600, 1367391600,
                                  1370070000, 1372662000, 1375340400, 1378018800, 1380610800,
                                  1383289200, 1385884800, 1388563200])

    def test_intervalgen(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Test the start of DST using a 30 minute increment:
        start = time.mktime((2013, 3, 10, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 3, 10, 5, 0, 0, 0, 0, -1))
        result = list(intervalgen(start, stop, 1800))
        self.assertEqual(result,
                         list(map(lambda t: TimeSpan(t[0], t[1]), [(1362902400, 1362904200),
                                                                   (1362904200, 1362906000),
                                                                   (1362906000, 1362907800),
                                                                   (1362907800, 1362909600),
                                                                   (1362909600, 1362911400),
                                                                   (1362911400, 1362913200),
                                                                   (1362913200, 1362915000),
                                                                   (1362915000, 1362916800)])))

        # Test the ending of DST using a 30 minute increment:
        start = time.mktime((2013, 11, 3, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 11, 3, 6, 0, 0, 0, 0, -1))
        result = list(intervalgen(start, stop, 1800))
        self.assertEqual(result,
                         list(map(lambda t: TimeSpan(t[0], t[1]), [(1383462000, 1383463800),
                                                                   (1383463800, 1383465600),
                                                                   (1383465600, 1383467400),
                                                                   (1383467400, 1383472800),
                                                                   (1383472800, 1383474600),
                                                                   (1383474600, 1383476400),
                                                                   (1383476400, 1383478200),
                                                                   (1383478200, 1383480000),
                                                                   (1383480000, 1383481800),
                                                                   (1383481800, 1383483600),
                                                                   (1383483600, 1383485400),
                                                                   (1383485400, 1383487200)])))

        # Test the start of DST using a 3 hour increment:
        start = time.mktime((2013, 3, 9, 12, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 3, 10, 11, 0, 0, 0, 0, -1))
        result = list(intervalgen(start, stop, 10800))
        self.assertEqual(result,
                         list(map(lambda t: TimeSpan(t[0], t[1]), [(1362859200, 1362870000),
                                                                   (1362870000, 1362880800),
                                                                   (1362880800, 1362891600),
                                                                   (1362891600, 1362902400),
                                                                   (1362902400, 1362909600),
                                                                   (1362909600, 1362920400),
                                                                   (1362920400, 1362931200),
                                                                   (1362931200, 1362938400)])))

        # Test the ending of DST using a 3 hour increment:
        start = time.mktime((2013, 11, 2, 12, 0, 0, 0, 0, -1))
        stop = time.mktime((2013, 11, 3, 12, 0, 0, 0, 0, -1))
        result = list(intervalgen(start, stop, 10800))
        self.assertEqual(result,
                         list(map(lambda t: TimeSpan(t[0], t[1]), [(1383418800, 1383429600),
                                                                   (1383429600, 1383440400),
                                                                   (1383440400, 1383451200),
                                                                   (1383451200, 1383462000),
                                                                   (1383462000, 1383476400),
                                                                   (1383476400, 1383487200),
                                                                   (1383487200, 1383498000),
                                                                   (1383498000, 1383508800)])))

        # Test a monthly increment:
        start = time.mktime((2013, 1, 1, 0, 0, 0, 0, 0, -1))
        stop = time.mktime((2014, 1, 1, 0, 0, 0, 0, 0, -1))
        result = list(intervalgen(start, stop, 365.25 / 12 * 24 * 3600))
        expected = list(map(lambda t: TimeSpan(t[0], t[1]), [(1357027200, 1359705600),
                                                             (1359705600, 1362124800),
                                                             (1362124800, 1364799600),
                                                             (1364799600, 1367391600),
                                                             (1367391600, 1370070000),
                                                             (1370070000, 1372662000),
                                                             (1372662000, 1375340400),
                                                             (1375340400, 1378018800),
                                                             (1378018800, 1380610800),
                                                             (1380610800, 1383289200),
                                                             (1383289200, 1385884800),
                                                             (1385884800, 1388563200)]))
        self.assertEqual(result, expected)

    #    The "roundTS" feature has been removed. Keep the tests. tk 1/24/2017.
    #         # Test roundTS = True
    #         start = time.mktime((2017,1,14,10,38,35,0,0,-1))
    #         stop  = time.mktime((2017,1,15,10,37,36,0,0,-1))
    #         for s, check_s in zip(intervalgen(start, stop, 10800, True), [(1484413200, 1484424000), (1484424000, 1484434800),
    #                                                                       (1484434800, 1484445600), (1484445600, 1484456400),
    #                                                                       (1484456400, 1484467200), (1484467200, 1484478000),
    #                                                                       (1484478000, 1484488800), (1484488800, 1484499600),
    #                                                                       (1484499600, 1484510400)]):
    #             self.assertEqual(s, TimeSpan(check_s[0], check_s[1]))

    def test_archiveHoursAgoSpan(self):
        os.environ['TZ'] = 'America/Los_Angeles'
        time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
        self.assertEqual(str(archiveHoursAgoSpan(time_ts, hours_ago=0)),
                         "[2013-07-04 01:00:00 PDT (1372924800) -> 2013-07-04 02:00:00 PDT (1372928400)]")
        self.assertEqual(str(archiveHoursAgoSpan(time_ts, hours_ago=2)),
                         "[2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]")
        time_ts = time.mktime(datetime.date(2013, 7, 4).timetuple())
        self.assertEqual(str(archiveHoursAgoSpan(time_ts, hours_ago=0)),
                         "[2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]")
        self.assertEqual(str(archiveHoursAgoSpan(time_ts, hours_ago=24)),
                         "[2013-07-02 23:00:00 PDT (1372831200) -> 2013-07-03 00:00:00 PDT (1372834800)]")
        self.assertIsNone(archiveHoursAgoSpan(None, hours_ago=24))

    def test_archiveSpanSpan(self):
        os.environ['TZ'] = 'Australia/Brisbane'
        time_ts = time.mktime(time.strptime("2015-07-21 09:05:35", "%Y-%m-%d %H:%M:%S"))
        self.assertEqual(time_ts, 1437433535)
        self.assertEqual(archiveSpanSpan(time_ts, time_delta=3600), TimeSpan(1437429935, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, hour_delta=6), TimeSpan(1437411935, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, day_delta=1), TimeSpan(1437347135, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, time_delta=3600, day_delta=1), TimeSpan(1437343535, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, week_delta=4), TimeSpan(1435014335, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, month_delta=1), TimeSpan(1434841535, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts, year_delta=1), TimeSpan(1405897535, 1437433535))
        self.assertEqual(archiveSpanSpan(time_ts), TimeSpan(1437433534, 1437433535))

        # Test over a DST boundary. Because Brisbane does not observe DST, we need to
        # switch timezones.
        os.environ['TZ'] = 'America/Los_Angeles'
        time_ts = time.mktime(time.strptime("2016-03-13 10:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertEqual(time_ts, 1457888400)
        span = archiveSpanSpan(time_ts, day_delta=1)
        self.assertEqual(span, TimeSpan(1457805600, 1457888400))
        # Note that there is not 24 hours of time over this span:
        self.assertEqual(span.stop - span.start, 23 * 3600)
        self.assertIsNone(archiveSpanSpan(None, day_delta=1))

    def test_isMidnight(self):
        os.environ['TZ'] = 'America/Los_Angeles'
        self.assertFalse(isMidnight(time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))))
        self.assertTrue(isMidnight(time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))))

    def test_isStartOfDay(self):
        os.environ['TZ'] = 'America/Los_Angeles'
        self.assertFalse(isStartOfDay(time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))))
        self.assertTrue(isStartOfDay(time.mktime(time.strptime("2013-07-04 00:00:00", "%Y-%m-%d %H:%M:%S"))))

        # Brazilian DST starts at midnight
        os.environ['TZ'] = 'America/Sao_Paulo'
        # This time is the start of DST and considered the start of the day: 4-11-2018 0100
        self.assertTrue(isStartOfDay(1541300400))
        self.assertFalse(isStartOfDay(1541300400 - 10))

    def test_startOfInterval(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        t_length = 1 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 57, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 5 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 55, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 1 * 60
        t_test = time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 0, 59, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 5 * 60
        t_test = time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 0, 55, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 10 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 50, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 15 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 45, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 20 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 40, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 30 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 30, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 60 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        t_length = 120 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 4, 0, 0, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Do a test over the spring DST boundary
        # This is 03:22:05 DST, just after the change over.
        # The correct answer is 02:00:00 DST.
        t_length = 120 * 60
        t_test = time.mktime((2009, 3, 8, 3, 22, 5, 0, 0, 1))
        t_ans = time.mktime((2009, 3, 8, 2, 0, 0, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Do a test over the spring DST boundary, but this time
        # on an archive interval boundary, 01:00:00 ST, the
        # instant of the change over.
        # Correct answer is 00:59:00 ST.
        t_length = 60
        t_test = time.mktime((2009, 3, 8, 1, 0, 0, 0, 0, 0))
        t_ans = time.mktime((2009, 3, 8, 0, 59, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Do a test over the fall DST boundary.
        # This is 01:22:05 DST, just before the change over.
        # The correct answer is 00:00:00 DST.
        t_length = 120 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 1))
        t_ans = time.mktime((2009, 11, 1, 0, 0, 0, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Do it again, except after the change over
        # This is 01:22:05 ST, just after the change over.
        # The correct answer is 00:00:00 ST (which is 01:00:00 DST).
        t_length = 120 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
        t_ans = time.mktime((2009, 11, 1, 0, 0, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Once again at 01:22:05 ST, just before the change over, but w/shorter interval
        t_length = 5 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 1))
        t_ans = time.mktime((2009, 11, 1, 1, 20, 0, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Once again at 01:22:05 ST, just after the change over, but w/shorter interval
        t_length = 5 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
        t_ans = time.mktime((2009, 11, 1, 1, 20, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Once again at 01:22:05 ST, just after the change over, but with 1 hour interval
        t_length = 60 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
        t_ans = time.mktime((2009, 11, 1, 1, 0, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

        # Once again, but an an archive interval boundary
        # This is 01:00:00 DST, the instant of the changeover
        # The correct answer is 00:59:00 DST.
        t_length = 1 * 60
        t_test = time.mktime((2009, 11, 1, 1, 0, 0, 0, 0, 1))
        t_ans = time.mktime((2009, 11, 1, 0, 59, 0, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)

    def test_TimeSpans(self):

        t = TimeSpan(1230000000, 1231000000)
        # Reflexive test:
        self.assertEqual(t, t)
        tsub = TimeSpan(1230500000, 1230600000)
        self.assertTrue(t.includes(tsub))
        self.assertFalse(tsub.includes(t))
        tleft = TimeSpan(1229000000, 1229100000)
        self.assertFalse(t.includes(tleft))
        tright = TimeSpan(1232000000, 1233000000)
        self.assertFalse(t.includes(tright))

        dic = {}
        dic[t] = 't'
        dic[tsub] = 'tsub'
        dic[tleft] = 'tleft'
        dic[tright] = 'tright'

        self.assertEqual(dic[t], 't')

    def test_genYearSpans(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Should generate years 2007 through 2008:"
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2008, 3, 1, 0, 0, 0, 0, 0, -1))

        yearlist = [span for span in genYearSpans(start_ts, stop_ts)]

        expected = ["[2007-01-01 00:00:00 PST (1167638400) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2009-01-01 00:00:00 PST (1230796800)]"]

        for got, expect in zip(yearlist, expected):
            self.assertEqual(str(got), expect)

    def test_genMonthSpans(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Should generate months 2007-12 through 2008-02:
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2008, 3, 1, 0, 0, 0, 0, 0, -1))

        monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
                    "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]"]

        for got, expect in zip(monthlist, expected):
            self.assertEqual(str(got), expect)

        # Add a second to the stop time. This should generate months 2007-12 through 2008-03:"
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2008, 3, 1, 0, 0, 1, 0, 0, -1))

        monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
                    "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]",
                    "[2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]"]

        for got, expect in zip(monthlist, expected):
            self.assertEqual(str(got), expect)

    def test_genDaySpans(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Should generate 2007-12-23 through 2008-1-5:"
        start_ts = time.mktime((2007, 12, 23, 10, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2008, 1, 5, 9, 22, 0, 0, 0, -1))

        daylist = [span for span in genDaySpans(start_ts, stop_ts)]

        expected = ["[2007-12-23 00:00:00 PST (1198396800) -> 2007-12-24 00:00:00 PST (1198483200)]",
                    "[2007-12-24 00:00:00 PST (1198483200) -> 2007-12-25 00:00:00 PST (1198569600)]",
                    "[2007-12-25 00:00:00 PST (1198569600) -> 2007-12-26 00:00:00 PST (1198656000)]",
                    "[2007-12-26 00:00:00 PST (1198656000) -> 2007-12-27 00:00:00 PST (1198742400)]",
                    "[2007-12-27 00:00:00 PST (1198742400) -> 2007-12-28 00:00:00 PST (1198828800)]",
                    "[2007-12-28 00:00:00 PST (1198828800) -> 2007-12-29 00:00:00 PST (1198915200)]",
                    "[2007-12-29 00:00:00 PST (1198915200) -> 2007-12-30 00:00:00 PST (1199001600)]",
                    "[2007-12-30 00:00:00 PST (1199001600) -> 2007-12-31 00:00:00 PST (1199088000)]",
                    "[2007-12-31 00:00:00 PST (1199088000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-01-02 00:00:00 PST (1199260800)]",
                    "[2008-01-02 00:00:00 PST (1199260800) -> 2008-01-03 00:00:00 PST (1199347200)]",
                    "[2008-01-03 00:00:00 PST (1199347200) -> 2008-01-04 00:00:00 PST (1199433600)]",
                    "[2008-01-04 00:00:00 PST (1199433600) -> 2008-01-05 00:00:00 PST (1199520000)]",
                    "[2008-01-05 00:00:00 PST (1199520000) -> 2008-01-06 00:00:00 PST (1199606400)]"]

        for got, expect in zip(daylist, expected):
            self.assertEqual(str(got), expect)

        # Should generate the single date 2007-12-1:"
        daylist = [span for span in genDaySpans(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                                time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)))]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2007-12-02 00:00:00 PST (1196582400)]"]
        for got, expect in zip(daylist, expected):
            self.assertEqual(str(got), expect)

    def test_genHourSpans(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Should generate throught 2007-12-23 20:00:00 throught 2007-12-24 4:00:00
        start_ts = time.mktime((2007, 12, 23, 20, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2007, 12, 24, 3, 45, 0, 0, 0, -1))

        hourlist = [span for span in genHourSpans(start_ts, stop_ts)]

        expected = ["[2007-12-23 20:00:00 PST (1198468800) -> 2007-12-23 21:00:00 PST (1198472400)]",
                    "[2007-12-23 21:00:00 PST (1198472400) -> 2007-12-23 22:00:00 PST (1198476000)]",
                    "[2007-12-23 22:00:00 PST (1198476000) -> 2007-12-23 23:00:00 PST (1198479600)]",
                    "[2007-12-23 23:00:00 PST (1198479600) -> 2007-12-24 00:00:00 PST (1198483200)]",
                    "[2007-12-24 00:00:00 PST (1198483200) -> 2007-12-24 01:00:00 PST (1198486800)]",
                    "[2007-12-24 01:00:00 PST (1198486800) -> 2007-12-24 02:00:00 PST (1198490400)]",
                    "[2007-12-24 02:00:00 PST (1198490400) -> 2007-12-24 03:00:00 PST (1198494000)]",
                    "[2007-12-24 03:00:00 PST (1198494000) -> 2007-12-24 04:00:00 PST (1198497600)]", ]

        for got, expect in zip(hourlist, expected):
            self.assertEqual(str(got), expect)

        # Should generate the single hour 2007-12-1 03:00:00
        hourlist = [span for span in genHourSpans(time.mktime((2007, 12, 1, 3, 0, 0, 0, 0, -1)),
                                                  time.mktime((2007, 12, 1, 4, 0, 0, 0, 0, -1)))]

        expected = ["[2007-12-01 03:00:00 PST (1196506800) -> 2007-12-01 04:00:00 PST (1196510400)]"]

        for got, expect in zip(hourlist, expected):
            self.assertEqual(str(got), expect)

    def test_archiveDaySpan(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 12, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))))
        # Try it again with grace=0
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)), grace=0),
                         TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 1, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))

        self.assertIsNone(archiveDaySpan(None))

    def test_archiveWeekSpan(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 1, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))

        self.assertIsNone(archiveWeekSpan(None))

    def test_archiveMonthSpan(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 11, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 1, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))

        self.assertIsNone(archiveMonthSpan(None))

    def test_archiveYearSpan(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        self.assertEqual(archiveYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))),
                         TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 1, 0, 0, -1))),
                         TimeSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2009, 1, 1, 0, 0, 0, 0, 0, -1))))

        self.assertIsNone(archiveYearSpan(None))

    def test_archiveRainYearSpan(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        self.assertEqual(archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 10),
                         TimeSpan(time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveRainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 10),
                         TimeSpan(time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)),
                                  time.mktime((2008, 10, 1, 0, 0, 0, 0, 0, -1))))

        self.assertIsNone(archiveRainYearSpan(None, 1))

    def test_DST(self):

        os.environ['TZ'] = 'America/Los_Angeles'

        # Test start-of-day routines around a DST boundary:
        start_ts = time.mktime((2007, 3, 11, 1, 0, 0, 0, 0, -1))
        start_of_day = startOfDay(start_ts)
        start2 = startOfArchiveDay(start_of_day)

        # Check that this is, in fact, a DST boundary:
        self.assertEqual(start_of_day, int(time.mktime((2007, 3, 11, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(start2, int(time.mktime((2007, 3, 10, 0, 0, 0, 0, 0, -1))))

    def test_dnt(self):
        """test day/night transitions"""

        times = [(calendar.timegm((2012, 1, 2, 0, 0, 0, 0, 0, -1)),
                  calendar.timegm((2012, 1, 3, 0, 0, 0, 0, 0, -1))),
                 (calendar.timegm((2012, 1, 2, 22, 0, 0, 0, 0, -1)),
                  calendar.timegm((2012, 1, 3, 22, 0, 0, 0, 0, -1)))]
        locs = [(-33.86, 151.21, 'sydney', 'Australia/Sydney'),  # UTC+10:00
                (35.6895, 139.6917, 'seoul', 'Asia/Seoul'),  # UTC+09:00
                (-33.93, 18.42, 'cape town', 'Africa/Johannesburg'),  # UTC+02:00
                (51.4791, 0, 'greenwich', 'Europe/London'),  # UTC 00:00
                (42.358, -71.060, 'boston', 'America/New_York'),  # UTC-05:00
                (21.3, -157.8167, 'honolulu', 'Pacific/Honolulu'),  # UTC-10:00
                ]
        expected = [
            (
                ('lat: -33.86 lon: 151.21 sydney first: day',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-02 11:00:00 (1325462400)',
                 '2012-01-02 09:09:22 UTC (1325495362) 2012-01-02 20:09:22 (1325495362)',
                 '2012-01-02 18:48:02 UTC (1325530082) 2012-01-03 05:48:02 (1325530082)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-03 11:00:00 (1325548800)'
                 ),
                ('lat: 35.6895 lon: 139.6917 seoul first: day',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-02 09:00:00 (1325462400)',
                 '2012-01-02 07:38:01 UTC (1325489881) 2012-01-02 16:38:01 (1325489881)',
                 '2012-01-02 21:50:59 UTC (1325541059) 2012-01-03 06:50:59 (1325541059)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-03 09:00:00 (1325548800)'
                 ),
                ('lat: -33.93 lon: 18.42 cape town first: night',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-02 02:00:00 (1325462400)',
                 '2012-01-02 03:38:32 UTC (1325475512) 2012-01-02 05:38:32 (1325475512)',
                 '2012-01-02 18:00:47 UTC (1325527247) 2012-01-02 20:00:47 (1325527247)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-03 02:00:00 (1325548800)'
                 ),
                ('lat: 51.4791 lon: 0 greenwich first: night',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-02 00:00:00 (1325462400)',
                 '2012-01-02 08:05:24 UTC (1325491524) 2012-01-02 08:05:24 (1325491524)',
                 '2012-01-02 16:01:20 UTC (1325520080) 2012-01-02 16:01:20 (1325520080)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-03 00:00:00 (1325548800)'
                 ),
                ('lat: 42.358 lon: -71.06 boston first: night',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-01 19:00:00 (1325462400)',
                 '2012-01-02 12:13:21 UTC (1325506401) 2012-01-02 07:13:21 (1325506401)',
                 '2012-01-02 21:22:02 UTC (1325539322) 2012-01-02 16:22:02 (1325539322)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-02 19:00:00 (1325548800)'
                 ),
                ('lat: 21.3 lon: -157.8167 honolulu first: day',
                 '2012-01-02 00:00:00 UTC (1325462400) 2012-01-01 14:00:00 (1325462400)',
                 '2012-01-02 04:00:11 UTC (1325476811) 2012-01-01 18:00:11 (1325476811)',
                 '2012-01-02 17:08:52 UTC (1325524132) 2012-01-02 07:08:52 (1325524132)',
                 '2012-01-03 00:00:00 UTC (1325548800) 2012-01-02 14:00:00 (1325548800)'
                 )),
            (
                ('lat: -33.86 lon: 151.21 sydney first: day',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-03 09:00:00 (1325541600)',
                 '2012-01-03 09:09:34 UTC (1325581774) 2012-01-03 20:09:34 (1325581774)',
                 '2012-01-03 18:48:48 UTC (1325616528) 2012-01-04 05:48:48 (1325616528)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-04 09:00:00 (1325628000)'
                 ),
                ('lat: 35.6895 lon: 139.6917 seoul first: day',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-03 07:00:00 (1325541600)',
                 '2012-01-03 07:38:47 UTC (1325576327) 2012-01-03 16:38:47 (1325576327)',
                 '2012-01-03 21:51:09 UTC (1325627469) 2012-01-04 06:51:09 (1325627469)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-04 07:00:00 (1325628000)'
                 ),
                ('lat: -33.93 lon: 18.42 cape town first: night',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-03 00:00:00 (1325541600)',
                 '2012-01-03 03:39:17 UTC (1325561957) 2012-01-03 05:39:17 (1325561957)',
                 '2012-01-03 18:00:58 UTC (1325613658) 2012-01-03 20:00:58 (1325613658)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-04 00:00:00 (1325628000)'
                 ),
                ('lat: 51.4791 lon: 0 greenwich first: night',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-02 22:00:00 (1325541600)',
                 '2012-01-03 08:05:17 UTC (1325577917) 2012-01-03 08:05:17 (1325577917)',
                 '2012-01-03 16:02:23 UTC (1325606543) 2012-01-03 16:02:23 (1325606543)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-03 22:00:00 (1325628000)'
                 ),
                ('lat: 42.358 lon: -71.06 boston first: night',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-02 17:00:00 (1325541600)',
                 '2012-01-03 12:13:26 UTC (1325592806) 2012-01-03 07:13:26 (1325592806)',
                 '2012-01-03 21:22:54 UTC (1325625774) 2012-01-03 16:22:54 (1325625774)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-03 17:00:00 (1325628000)'
                 ),
                ('lat: 21.3 lon: -157.8167 honolulu first: day',
                 '2012-01-02 22:00:00 UTC (1325541600) 2012-01-02 12:00:00 (1325541600)',
                 '2012-01-03 04:00:48 UTC (1325563248) 2012-01-02 18:00:48 (1325563248)',
                 '2012-01-03 17:09:11 UTC (1325610551) 2012-01-03 07:09:11 (1325610551)',
                 '2012-01-03 22:00:00 UTC (1325628000) 2012-01-03 12:00:00 (1325628000)'
                 )
            )
        ]

        self.assertEqual(times, [(1325462400, 1325548800), (1325541600, 1325628000)])

        for i, t in enumerate(times):
            for j, l in enumerate(locs):
                os.environ['TZ'] = l[3]
                first, values = getDayNightTransitions(t[0], t[1], l[0], l[1])

                self.assertEqual("lat: %s lon: %s %s first: %s" % (l[0], l[1], l[2], first),
                                 expected[i][j][0],
                                 msg="times=%s; location=%s" % (t, l))
                self.assertEqual("%s %s" % (timestamp_to_gmtime(t[0]), timestamp_to_local(t[0])),
                                 expected[i][j][1],
                                 msg="times=%s; location=%s" % (t, l))
                self.assertEqual("%s %s" % (timestamp_to_gmtime(values[0]), timestamp_to_local(values[0])),
                                 expected[i][j][2],
                                 msg="times=%s; location=%s" % (t, l))
                self.assertEqual("%s %s" % (timestamp_to_gmtime(values[1]), timestamp_to_local(values[1])),
                                 expected[i][j][3],
                                 msg="times=%s; location=%s" % (t, l))
                self.assertEqual("%s %s" % (timestamp_to_gmtime(t[1]), timestamp_to_local(t[1])),
                                 expected[i][j][4],
                                 msg="times=%s; location=%s" % (t, l))

    def test_utc_conversions(self):
        self.assertEqual(utc_to_ts(2009, 3, 27, 14.5), 1238164200)
        os.environ['TZ'] = 'America/Los_Angeles'
        tt = utc_to_local_tt(2009, 3, 27, 14.5)
        self.assertEqual(tt[0:5], (2009, 3, 27, 7, 30))

    def test_genWithPeek(self):
        # Define a generator function:
        def genfunc(N):
            for i in range(N):
                yield i

        # Now wrap it with the GenWithPeek object:
        g_with_peek = GenWithPeek(genfunc(5))

        # Define a generator function to test it
        def tester(g):
            for i in g:
                yield str(i)
                # Every second object, let's take a peek ahead
                if i % 2:
                    # We can get a peek at the next object without disturbing the wrapped generator:
                    yield "peek: %d" % g.peek()

        seq = [x for x in tester(g_with_peek)]
        self.assertEqual(seq, ["0", "1", "peek: 2", "2", "3", "peek: 4", "4"])

    def test_to_bool(self):

        self.assertTrue(to_bool('TRUE'))
        self.assertTrue(to_bool('true'))
        self.assertTrue(to_bool(1))
        self.assertFalse(to_bool('FALSE'))
        self.assertFalse(to_bool('false'))
        self.assertFalse(to_bool(0))
        with self.assertRaises(ValueError):
            to_bool(None)
        with self.assertRaises(ValueError):
            to_bool('foo')

    def test_to_int(self):
        self.assertEqual(to_int(123), 123)
        self.assertEqual(to_int('123'), 123)
        self.assertEqual(to_int('-5'), -5)
        self.assertEqual(to_int('-5.2'), -5)
        self.assertIsNone(to_int(None))
        self.assertIsNone(to_int('NONE'))

    def test_to_unicode(self):

        # To get a utf-8 byte string that we can convert, start with a unicode
        # string, then encode it.
        unicode_string = u"degree sign: °"
        byte_string = unicode_string.encode('utf8')
        # Now use the byte string to test:
        self.assertEqual(to_unicode(byte_string), unicode_string)
        # Identity test
        self.assertEqual(unicode_string, unicode_string)
        self.assertIsNone(to_unicode(None))

    def test_min_with_none(self):

        self.assertEqual(min_with_none([1, 2, None, 4]), 1)

    def test_max_with_none(self):

        self.assertEqual(max_with_none([1, 2, None, 4]), 4)
        self.assertEqual(max_with_none([-1, -2, None, -4]), -1)

    def test_ListOfDicts(self):
        # Try an empty dictionary:
        lod = ListOfDicts()
        self.assertEqual(lod.get('b'), None)
        # Now initialize with a starting dictionary:
        lod = ListOfDicts({'a': 1, 'b': 2, 'c': 3})
        # Look up a key known to be in there:
        self.assertEqual(lod['b'], 2)
        # Look for a non-existent key
        self.assertEqual(lod.get('d'), None)
        # Now extend the dictionary:
        lod.extend({'d': 4, 'e': 5})
        # And try the lookup:
        self.assertEqual(lod['d'], 4)
        # Explicitly add a new key to the dictionary:
        lod['f'] = 6
        # Try it:
        self.assertEqual(lod['f'], 6)

    def test_KeyDict(self):
        a_dict = {'a': 1, 'b': 2}
        kd = KeyDict(a_dict)
        self.assertEqual(kd['a'], 1)
        self.assertEqual(kd['bad_key'], 'bad_key')


if __name__ == '__main__':
    unittest.main()
