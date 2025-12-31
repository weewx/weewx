#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test routines for weeutil.weeutil."""

import pytest

from weeutil.weeutil import *
from weewx.tags import TimespanBinder

# Check for backwards compatiblity shim:
from weeutil.weeutil import accumulateLeaves, search_up

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()


def timestamp_to_local(ts):
    """Return a string in local time"""
    return timestamp_to_string(ts, "%Y-%m-%d %H:%M:%S")


def test_convertToFloat():
    assert convertToFloat(['1.0', '2.0', 'None', 'none', '5.0', '6.0']) == [1.0, 2.0, None, None,
                                                                            5.0, 6.0]
    assert convertToFloat(None) is None


def test_rounder():
    assert rounder(1.2345, 2) == 1.23
    assert rounder(1.2345, 0) == 1
    assert isinstance(rounder(1.2345, 0), int)
    assert rounder([1.2345, 6.73848, 4.2901], 2) == [1.23, 6.74, 4.29]
    assert rounder(complex(1.2345, -2.1191), 2) == complex(1.23, -2.12)
    assert rounder([complex(1.2345, -2.1191), complex(5.1921, 11.2092)], 2) == [
        complex(1.23, -2.12), complex(5.19, 11.21)]
    assert rounder(None, 2) is None
    assert rounder(1.2345, None) == 1.2345
    assert rounder(Polar(1.2345, 6.7890), 2) == Polar(1.23, 6.79)
    assert rounder('abc', 2) == 'abc'


def test_option_as_list():
    assert option_as_list("abc") == ['abc']
    assert option_as_list(['a', 'b']) == ['a', 'b']
    assert option_as_list(None) is None
    assert option_as_list('') == ['']


def test_list_as_string():
    assert list_as_string('a string') == "a string"
    assert list_as_string(['a', 'string']) == "a, string"
    assert list_as_string('Reno, NV') == "Reno, NV"


def test_stampgen():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Test the start of DST using a 30-minute increment:
    start = time.mktime((2013, 3, 10, 0, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 3, 10, 6, 0, 0, 0, 0, -1))
    result = list(stampgen(start, stop, 1800))
    assert result == [1362902400, 1362904200, 1362906000, 1362907800,
                      1362909600, 1362911400, 1362913200, 1362915000,
                      1362916800, 1362918600, 1362920400]

    # Test the ending of DST using a 30-minute increment:
    start = time.mktime((2013, 11, 3, 0, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 11, 3, 6, 0, 0, 0, 0, -1))
    result = list(stampgen(start, stop, 1800))
    assert result == [1383462000, 1383463800, 1383465600, 1383467400,
                      1383472800, 1383474600, 1383476400, 1383478200,
                      1383480000, 1383481800, 1383483600, 1383485400,
                      1383487200]

    # Test the start of DST using a 3-hour increment
    start = time.mktime((2013, 3, 9, 12, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 3, 10, 11, 0, 0, 0, 0, -1))
    result = list(stampgen(start, stop, 10800))
    assert result == [1362859200, 1362870000, 1362880800, 1362891600,
                      1362902400, 1362909600, 1362920400, 1362931200]

    # Test the end of DST using a 3-hour increment
    start = time.mktime((2013, 11, 2, 12, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 11, 3, 12, 0, 0, 0, 0, -1))
    result = list(stampgen(start, stop, 10800))
    assert result == [1383418800, 1383429600, 1383440400, 1383451200,
                      1383462000, 1383476400, 1383487200, 1383498000, 1383508800]

    # Test for month increment
    start = time.mktime((2013, 1, 1, 0, 0, 0, 0, 0, -1))
    stop = time.mktime((2014, 1, 1, 0, 0, 0, 0, 0, -1))
    result = list(stampgen(start, stop, 365.25 / 12 * 24 * 3600))
    assert result == [1357027200, 1359705600, 1362124800, 1364799600, 1367391600,
                      1370070000, 1372662000, 1375340400, 1378018800, 1380610800,
                      1383289200, 1385884800, 1388563200]


def test_nominal_spans():
    assert nominal_spans(1800) == 1800
    assert nominal_spans('1800') == 1800
    assert nominal_spans('hour') == 3600
    assert nominal_spans('HOUR') == 3600
    assert nominal_spans('60M') == 3600
    assert nominal_spans('3h') == 3 * 3600
    assert nominal_spans('3d') == 3 * 3600 * 24
    assert nominal_spans('2w') == 14 * 3600 * 24
    assert nominal_spans('12m') == 365.25 * 24 * 3600
    assert nominal_spans('1y') == 365.25 * 24 * 3600
    assert nominal_spans(None) is None
    with pytest.raises(ValueError):
        nominal_spans('foo')
    with pytest.raises(ValueError):
        nominal_spans('1800.0')


def test_intervalgen():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Test the start of DST using a 30-minute increment:
    start = time.mktime((2013, 3, 10, 0, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 3, 10, 5, 0, 0, 0, 0, -1))
    result = list(intervalgen(start, stop, 1800))
    assert result == list(map(lambda t: TimeSpan(t[0], t[1]), [(1362902400, 1362904200),
                                                               (1362904200, 1362906000),
                                                               (1362906000, 1362907800),
                                                               (1362907800, 1362909600),
                                                               (1362909600, 1362911400),
                                                               (1362911400, 1362913200),
                                                               (1362913200, 1362915000),
                                                               (1362915000, 1362916800)]))

    # Test the ending of DST using a 30-minute increment:
    start = time.mktime((2013, 11, 3, 0, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 11, 3, 6, 0, 0, 0, 0, -1))
    result = list(intervalgen(start, stop, 1800))
    assert result == list(map(lambda t: TimeSpan(t[0], t[1]), [(1383462000, 1383463800),
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
                                                               (1383485400, 1383487200)]))

    # Test the start of DST using a 3-hour increment:
    start = time.mktime((2013, 3, 9, 12, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 3, 10, 11, 0, 0, 0, 0, -1))
    result = list(intervalgen(start, stop, 10800))
    assert result == list(map(lambda t: TimeSpan(t[0], t[1]), [(1362859200, 1362870000),
                                                               (1362870000, 1362880800),
                                                               (1362880800, 1362891600),
                                                               (1362891600, 1362902400),
                                                               (1362902400, 1362909600),
                                                               (1362909600, 1362920400),
                                                               (1362920400, 1362931200),
                                                               (1362931200, 1362938400)]))

    # Test the ending of DST using a 3-hour increment:
    start = time.mktime((2013, 11, 2, 12, 0, 0, 0, 0, -1))
    stop = time.mktime((2013, 11, 3, 12, 0, 0, 0, 0, -1))
    result = list(intervalgen(start, stop, 10800))
    assert result == list(map(lambda t: TimeSpan(t[0], t[1]), [(1383418800, 1383429600),
                                                               (1383429600, 1383440400),
                                                               (1383440400, 1383451200),
                                                               (1383451200, 1383462000),
                                                               (1383462000, 1383476400),
                                                               (1383476400, 1383487200),
                                                               (1383487200, 1383498000),
                                                               (1383498000, 1383508800)]))

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
    assert result == expected


def test_archiveHoursAgoSpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    time_ts = time.mktime(time.strptime("2013-07-04 01:57:35", "%Y-%m-%d %H:%M:%S"))
    assert str(archiveHoursAgoSpan(time_ts, hours_ago=0)) \
           == "[2013-07-04 01:00:00 PDT (1372924800) -> 2013-07-04 02:00:00 PDT (1372928400)]"
    assert str(archiveHoursAgoSpan(time_ts, hours_ago=2)) == \
           "[2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]"
    time_ts = time.mktime(datetime.date(2013, 7, 4).timetuple())
    assert str(archiveHoursAgoSpan(time_ts, hours_ago=0)) \
           == "[2013-07-03 23:00:00 PDT (1372917600) -> 2013-07-04 00:00:00 PDT (1372921200)]"
    assert str(archiveHoursAgoSpan(time_ts, hours_ago=24)) == \
           "[2013-07-02 23:00:00 PDT (1372831200) -> 2013-07-03 00:00:00 PDT (1372834800)]"
    assert archiveHoursAgoSpan(None, hours_ago=24) is None


def test_archiveSpanSpan():
    """Test archiveSpanSpan() using Brisbane time"""
    os.environ['TZ'] = 'Australia/Brisbane'
    time.tzset()
    time_ts = int(time.mktime(time.strptime("2015-07-21 09:05:35", "%Y-%m-%d %H:%M:%S")))
    assert time_ts == 1437433535
    assert archiveSpanSpan(time_ts, time_delta=3600) == TimeSpan(1437429935, 1437433535)
    assert archiveSpanSpan(time_ts, hour_delta=6) == TimeSpan(1437411935, 1437433535)
    assert archiveSpanSpan(time_ts, day_delta=1) == TimeSpan(1437347135, 1437433535)
    assert archiveSpanSpan(time_ts, time_delta=3600, day_delta=1) == TimeSpan(1437343535,
                                                                              1437433535)
    assert archiveSpanSpan(time_ts, week_delta=4) == TimeSpan(1435014335, 1437433535)
    assert archiveSpanSpan(time_ts, month_delta=1) == TimeSpan(1434841535, 1437433535)
    assert archiveSpanSpan(time_ts, year_delta=1) == TimeSpan(1405897535, 1437433535)
    assert archiveSpanSpan(time_ts) == TimeSpan(1437433534, 1437433535)

    # Test forcing to midnight boundary:
    assert archiveSpanSpan(time_ts, hour_delta=6, boundary='midnight') == TimeSpan(1437400800,
                                                                                   1437433535)
    assert archiveSpanSpan(time_ts, day_delta=1, boundary='midnight') == TimeSpan(1437314400,
                                                                                  1437433535)
    assert archiveSpanSpan(time_ts, time_delta=3600, day_delta=1,
                           boundary='midnight') == TimeSpan(1437314400, 1437433535)
    assert archiveSpanSpan(time_ts, week_delta=4, boundary='midnight') == TimeSpan(1434981600,
                                                                                   1437433535)
    with pytest.raises(ValueError):
        archiveSpanSpan(time_ts, hour_delta=6, boundary='foo')

    # Test over a DST boundary. Because Brisbane does not observe DST, we need to
    # switch timezones.
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    time_ts = time.mktime(time.strptime("2016-03-13 10:00:00", "%Y-%m-%d %H:%M:%S"))
    assert time_ts == 1457888400
    span = archiveSpanSpan(time_ts, day_delta=1)
    assert span == TimeSpan(1457805600, 1457888400)
    # Note that there is not 24 hours of time over this span:
    assert span.stop - span.start == 23 * 3600
    assert archiveSpanSpan(None, day_delta=1) is None


def test_isMidnight():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    assert not isMidnight(time.mktime(time.strptime("2013-07-04 01:57:35",
                                                    "%Y-%m-%d %H:%M:%S")))
    assert isMidnight(time.mktime(time.strptime("2013-07-04 00:00:00",
                                                "%Y-%m-%d %H:%M:%S")))


def test_isStartOfDay():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    assert not isStartOfDay(time.mktime(time.strptime("2013-07-04 01:57:35",
                                                      "%Y-%m-%d %H:%M:%S")))
    assert isStartOfDay(time.mktime(time.strptime("2013-07-04 00:00:00",
                                                  "%Y-%m-%d %H:%M:%S")))

    # Brazilian DST starts at midnight
    os.environ['TZ'] = 'America/Sao_Paulo'
    time.tzset()
    # This time is the start of DST and considered the start of the day: 4-11-2018 0100
    assert isStartOfDay(1541300400)
    assert not isStartOfDay(1541300400 - 10)


def test_startOfInterval():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    t_length = 1 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 57, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 5 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 55, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 1 * 60
    t_test = time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 0, 59, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 5 * 60
    t_test = time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 0, 55, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 10 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 50, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 15 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 45, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 20 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 40, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 30 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 30, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 60 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 0, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    t_length = 120 * 60
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 0, 0, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Do a test over the spring DST boundary
    # This is 03:22:05 DST, just after the change over.
    # The correct answer is 03:00:00 DST.
    t_length = 120 * 60
    t_test = time.mktime((2009, 3, 8, 3, 22, 5, 0, 0, 1))
    t_ans = int(time.mktime((2009, 3, 8, 3, 0, 0, 0, 0, 1)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Do a test over the spring DST boundary, but this time
    # on an archive interval boundary, 01:00:00 ST, the
    # instant of the change over.
    # Correct answer is 00:59:00 ST.
    t_length = 60
    t_test = time.mktime((2009, 3, 8, 1, 0, 0, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 8, 0, 59, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Do a test over the fall DST boundary.
    # This is 01:22:05 DST, just before the change over.
    # The correct answer is 01:00:00 DST.
    t_length = 120 * 60
    t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 1))
    t_ans = int(time.mktime((2009, 11, 1, 1, 0, 0, 0, 0, 1)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Do it again, except after the change over
    # This is 01:22:05 ST, just after the change over.
    # The correct answer is 00:00:00 ST (which is 01:00:00 DST).
    t_length = 120 * 60
    t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
    t_ans = int(time.mktime((2009, 11, 1, 0, 0, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Once again at 01:22:05 ST, just before the change over, but w/shorter interval
    t_length = 5 * 60
    t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 1))
    t_ans = int(time.mktime((2009, 11, 1, 1, 20, 0, 0, 0, 1)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Once again at 01:22:05 ST, just after the change over, but w/shorter interval
    t_length = 5 * 60
    t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
    t_ans = int(time.mktime((2009, 11, 1, 1, 20, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Once again at 01:22:05 ST, just after the change over, but with 1 hour interval
    t_length = 60 * 60
    t_test = time.mktime((2009, 11, 1, 1, 22, 5, 0, 0, 0))
    t_ans = int(time.mktime((2009, 11, 1, 1, 0, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Once again, but an archive interval boundary
    # This is 01:00:00 DST, the instant of the changeover
    # The correct answer is 00:59:00 DST.
    t_length = 1 * 60
    t_test = time.mktime((2009, 11, 1, 1, 0, 0, 0, 0, 1))
    t_ans = int(time.mktime((2009, 11, 1, 0, 59, 0, 0, 0, 1)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans

    # Oddball archive interval
    t_length = 480
    t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
    t_ans = int(time.mktime((2009, 3, 4, 1, 52, 0, 0, 0, 0)))
    t_start = startOfInterval(t_test, t_length)
    assert t_start == t_ans


def test_TimeSpans():
    t = TimeSpan(1230000000, 1231000000)
    # Reflexive test:
    assert t == t
    tsub = TimeSpan(1230500000, 1230600000)
    assert t.includes(tsub)
    assert not tsub.includes(t)
    tleft = TimeSpan(1229000000, 1229100000)
    assert not t.includes(tleft)
    tright = TimeSpan(1232000000, 1233000000)
    assert not t.includes(tright)

    # Test dictionary lookups. This will test hash and equality.
    dic = {t: 't', tsub: 'tsub', tleft: 'tleft', tright: 'tright'}
    assert dic[t] == 't'

    assert t.includesArchiveTime(1230000001)
    assert not t.includesArchiveTime(1230000000)

    assert t.length == 1231000000 - 1230000000

    with pytest.raises(ValueError):
        _ = TimeSpan(1231000000, 1230000000)


def test_genYearSpans():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Should generate years 2007 through 2008:"
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 3, 1, 0, 0, 0, 0, 0, -1))

    yearlist = [span for span in genYearSpans(start_ts, stop_ts)]

    expected = [
        "[2007-01-01 00:00:00 PST (1167638400) -> 2008-01-01 00:00:00 PST (1199174400)]",
        "[2008-01-01 00:00:00 PST (1199174400) -> 2009-01-01 00:00:00 PST (1230796800)]"]

    for got, expect in zip(yearlist, expected):
        assert str(got) == expect


def test_genMonthSpans():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Should generate months 2007-12 through 2008-02:
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 3, 1, 0, 0, 0, 0, 0, -1))

    monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

    expected = [
        "[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
        "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
        "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]"]

    for got, expect in zip(monthlist, expected):
        assert str(got) == expect

    # Add a second to the stop time. This should generate months 2007-12 through 2008-03:"
    start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 3, 1, 0, 0, 1, 0, 0, -1))

    monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

    expected = [
        "[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
        "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
        "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]",
        "[2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]"]

    for got, expect in zip(monthlist, expected):
        assert str(got) == expect


def test_genDaySpans():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Should generate 2007-12-23 through 2008-1-5:"
    start_ts = time.mktime((2007, 12, 23, 10, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2008, 1, 5, 9, 22, 0, 0, 0, -1))

    daylist = [span for span in genDaySpans(start_ts, stop_ts)]

    expected = [
        "[2007-12-23 00:00:00 PST (1198396800) -> 2007-12-24 00:00:00 PST (1198483200)]",
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
        assert str(got) == expect

    # Should generate the single date 2007-12-1:"
    daylist = [span for span in genDaySpans(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                            time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)))]

    expected = [
        "[2007-12-01 00:00:00 PST (1196496000) -> 2007-12-02 00:00:00 PST (1196582400)]"]
    for got, expect in zip(daylist, expected):
        assert str(got) == expect


def test_genHourSpans():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Should generate throught 2007-12-23 20:00:00 throught 2007-12-24 4:00:00
    start_ts = time.mktime((2007, 12, 23, 20, 15, 0, 0, 0, -1))
    stop_ts = time.mktime((2007, 12, 24, 3, 45, 0, 0, 0, -1))

    hourlist = [span for span in genHourSpans(start_ts, stop_ts)]

    expected = [
        "[2007-12-23 20:00:00 PST (1198468800) -> 2007-12-23 21:00:00 PST (1198472400)]",
        "[2007-12-23 21:00:00 PST (1198472400) -> 2007-12-23 22:00:00 PST (1198476000)]",
        "[2007-12-23 22:00:00 PST (1198476000) -> 2007-12-23 23:00:00 PST (1198479600)]",
        "[2007-12-23 23:00:00 PST (1198479600) -> 2007-12-24 00:00:00 PST (1198483200)]",
        "[2007-12-24 00:00:00 PST (1198483200) -> 2007-12-24 01:00:00 PST (1198486800)]",
        "[2007-12-24 01:00:00 PST (1198486800) -> 2007-12-24 02:00:00 PST (1198490400)]",
        "[2007-12-24 02:00:00 PST (1198490400) -> 2007-12-24 03:00:00 PST (1198494000)]",
        "[2007-12-24 03:00:00 PST (1198494000) -> 2007-12-24 04:00:00 PST (1198497600)]", ]

    for got, expect in zip(hourlist, expected):
        assert str(got) == expect

    # Should generate the single hour 2007-12-1 03:00:00
    hourlist = [span for span in genHourSpans(time.mktime((2007, 12, 1, 3, 0, 0, 0, 0, -1)),
                                              time.mktime((2007, 12, 1, 4, 0, 0, 0, 0, -1)))]

    expected = [
        "[2007-12-01 03:00:00 PST (1196506800) -> 2007-12-01 04:00:00 PST (1196510400)]"]

    for got, expect in zip(hourlist, expected):
        assert str(got) == expect


def test_daySpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # 2007-12-13 10:15:00
    assert daySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1)))
    # 2007-12-13 00:00:00
    assert daySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1)))
    # 2007-12-13 00:00:01
    assert daySpan(time.mktime((2007, 12, 13, 0, 0, 1, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1)))

    assert daySpan(None) is None


def test_archiveDaySpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # 2007-12-13 10:15:00
    assert archiveDaySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1)))
    # 2007-12-13 00:00:00
    assert archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 12, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)))
    # 2007-12-13 00:00:01
    assert archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 1, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1)))

    assert archiveDaySpan(None) is None


def test_archiveWeekSpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Week around 2007-12-13 10:15:00 (Thursday 10:15)
    assert archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1)))

    # Week around 2007-12-13 00:00:00 (midnight Thursday)
    assert archiveWeekSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1)))

    # Week around 2007-12-9 00:00:00 (midnight Sunday)
    assert archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)))

    # Week around 2007-12-9 00:00:01 (one second after midnight on Sunday)
    assert archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 1, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1)))

    # Week around 2007-12-13 10:15:00 (Thursday 10:15) where the week starts on Monday
    assert archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)),
                           startOfWeek=0) == TimeSpan(
        time.mktime((2007, 12, 10, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 17, 0, 0, 0, 0, 0, -1)))

    # Previous week around 2007-12-13 10:15:00 (Thursday 10:15) where the week starts on Monday
    assert archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)),
                           startOfWeek=0,
                           weeks_ago=1) == TimeSpan(time.mktime((2007, 12, 3, 0, 0, 0, 0, 0, -1)),
                                                    time.mktime((2007, 12, 10, 0, 0, 0, 0, 0, -1)))

    assert archiveWeekSpan(None) is None


def test_archiveMonthSpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # 2007-12-13 10:15:00
    assert archiveMonthSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    # 2007-12-01 00:00:00
    assert archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 11, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)))
    # 2007-12-01 00:00:01
    assert archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 1, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    # 2008-01-01 00:00:00
    assert archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))

    # One month ago from 2008-01-01 00:00:00
    assert archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)),
                            months_ago=1) == TimeSpan(
        time.mktime((2007, 11, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)))

    # One month ago from 2008-01-01 00:00:01
    assert archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 1, 0, 0, -1)),
                            months_ago=1) == TimeSpan(
        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))

    assert archiveMonthSpan(None) is None


def test_archiveYearSpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    assert archiveYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))) == TimeSpan(
        time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 1, 0, 0, -1))) == TimeSpan(
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2009, 1, 1, 0, 0, 0, 0, 0, -1)))

    assert archiveYearSpan(None) is None


def test_archiveRainYearSpan():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Rain year starts 1-Jan
    assert archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 1) == TimeSpan(
        time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveRainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 1) == TimeSpan(
        time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)))
    # Rain year starts 1-Oct
    assert archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 10) == TimeSpan(
        time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 10,
                               years_ago=1) == TimeSpan(
        time.mktime((2005, 10, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveRainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 10) == TimeSpan(
        time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2008, 10, 1, 0, 0, 0, 0, 0, -1)))
    assert archiveRainYearSpan(time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)), 10) == TimeSpan(
        time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)),
        time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)))

    assert archiveRainYearSpan(None, 1) is None


def test_DST():
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()

    # Test start-of-day routines around a DST boundary:
    start_ts = time.mktime((2007, 3, 11, 1, 0, 0, 0, 0, -1))
    start_of_day = startOfDay(start_ts)
    start2 = startOfArchiveDay(start_of_day)

    # Check that this is, in fact, a DST boundary:
    assert start_of_day == int(time.mktime((2007, 3, 11, 0, 0, 0, 0, 0, -1)))
    assert start2 == int(time.mktime((2007, 3, 10, 0, 0, 0, 0, 0, -1)))


def test_start_of_archive_day():
    """Test the function startOfArchiveDay()"""
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    # Exactly midnight 1-July-2022:
    start_dt = datetime.datetime(2022, 7, 1)
    start_ts = time.mktime(start_dt.timetuple())
    assert startOfArchiveDay(start_ts) == 1656572400.0
    # Now try it at a smidge after midnight. Should be the next day
    assert startOfArchiveDay(start_ts + 0.1) == 1656658800.0


def test_dnt():
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

    assert times == [(1325462400, 1325548800), (1325541600, 1325628000)]

    for i, t in enumerate(times):
        for j, l in enumerate(locs):
            os.environ['TZ'] = l[3]
            time.tzset()
            first, values = getDayNightTransitions(t[0], t[1], l[0], l[1])

            assert "lat: %s lon: %s %s first: %s" % (l[0], l[1], l[2], first) == expected[i][j][
                0], "times=%s; location=%s" % (t, l)
            assert "%s %s" % (timestamp_to_gmtime(t[0]), timestamp_to_local(t[0])) == \
                   expected[i][j][1], "times=%s; location=%s" % (t, l)
            assert "%s %s" % (timestamp_to_gmtime(values[0]),
                              timestamp_to_local(values[0])) == expected[i][j][
                       2], "times=%s; location=%s" % (t, l)
            assert "%s %s" % (timestamp_to_gmtime(values[1]),
                              timestamp_to_local(values[1])) == expected[i][j][
                       3], "times=%s; location=%s" % (t, l)
            assert "%s %s" % (timestamp_to_gmtime(t[1]), timestamp_to_local(t[1])) == \
                   expected[i][j][4], "times=%s; location=%s" % (t, l)


def test_utc_conversions():
    assert utc_to_ts(2009, 3, 27, 14.5) == 1238164200.5
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    tt = utc_to_local_tt(2009, 3, 27, 14.5)
    assert tt[0:5] == (2009, 3, 27, 7, 30)


def test_genWithPeek():
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
                # We can get a peek at the next object without disturbing the wrapped generator
                yield "peek: %d" % g.peek()

    seq = [x for x in tester(g_with_peek)]
    assert seq == ["0", "1", "peek: 2", "2", "3", "peek: 4", "4"]


def test_GenByBatch():
    # Define a generator function:
    def genfunc(N):
        for i in range(N):
            yield i

    # Now wrap it with the GenByBatch object. First fetch everything in one batch:
    seq = [x for x in GenByBatch(genfunc(10), 0)]
    assert seq == list(range(10))
    # Now try it again, fetching in batches of 2:
    seq = [x for x in GenByBatch(genfunc(10), 2)]
    assert seq == list(range(10))
    # Oddball batch size
    seq = [x for x in GenByBatch(genfunc(10), 3)]
    assert seq == list(range(10))


def test_to_bool():
    assert to_bool('TRUE')
    assert to_bool('true')
    assert to_bool(1)
    assert not to_bool('FALSE')
    assert not to_bool('false')
    assert not to_bool(0)
    with pytest.raises(ValueError):
        to_bool(None)
    with pytest.raises(ValueError):
        to_bool('foo')


def test_to_int():
    assert to_int(123) == 123
    assert to_int('123') == 123
    assert to_int('-5') == -5
    assert to_int('-5.2') == -5
    assert to_int(None) is None
    assert to_int('NONE') is None


def test_to_float():
    assert isinstance(to_float(123), float)
    assert isinstance(to_float(123.0), float)
    assert isinstance(to_float('123'), float)
    assert to_float(123) == 123.0
    assert to_float('123') == 123.0
    assert to_float(None) is None
    assert to_float('NONE') is None


def test_to_complex():
    assert to_complex(1.0, 0.0) == pytest.approx(complex(0.0, 1.0))
    assert to_complex(1.0, 90) == pytest.approx(complex(1.0, 0.0))
    assert to_complex(None, 90.0) is None
    assert to_complex(0.0, 90.0) == complex(0.0, 0.0)
    assert to_complex(1.0, None) is None


def test_Polar():
    p = Polar(1.0, 90.0)
    assert p.mag == 1.0
    assert p.dir == 90.0
    p = Polar.from_complex(complex(1.0, 0.0))
    assert p.mag == 1.0
    assert p.dir == 90.0
    assert str(p) == '(1.0, 90.0)'


def test_min_with_none():
    assert min_with_none([1, 2, None, 4]) == 1


def test_max_with_none():
    assert max_with_none([1, 2, None, 4]) == 4
    assert max_with_none([-1, -2, None, -4]) == -1


def test_ListOfDicts():
    # Try an empty dictionary:
    lod = ListOfDicts()
    assert lod.get('b') is None
    # Now initialize with a starting dictionary, using an overlap:
    lod = ListOfDicts({'a': 1, 'b': 2, 'c': 3, 'd': 5}, {'d': 4, 'e': 5, 'f': 6})
    # Look up some keys known to be in there:
    assert lod['b'] == 2
    assert lod['e'] == 5
    assert lod['d'] == 5
    # Look for a non-existent key
    assert lod.get('g') is None
    # Now extend the dictionary some more:
    lod.extend({'g': 7, 'h': 8})
    # And try the lookup:
    assert lod['g'] == 7
    # Explicitly add a new key to the dictionary:
    lod['i'] = 9
    # Try it:
    assert lod['i'] == 9

    # Now check .keys()
    lod2 = ListOfDicts({k: str(k) for k in range(5)},
                       {k: str(k) for k in range(5, 10)})
    assert set(lod2.keys()) == set(range(10))
    assert 3 in lod2.keys()
    assert 6 in lod2.keys()
    assert 11 not in lod2.keys()
    s = set(lod2.keys())
    assert 3 in s
    assert 6 in s
    assert 11 not in s

    # ... and check .values()
    assert set(lod2.values()) == set(str(i) for i in range(10))
    assert '3' in lod2.values()
    assert '6' in lod2.values()
    assert '11' not in lod2.values()
    s = set(lod2.values())
    assert '3' in s
    assert '6' in s
    assert '11' not in s


def test_KeyDict():
    a_dict = {'a': 1, 'b': 2}
    kd = KeyDict(a_dict)
    assert kd['a'] == 1
    assert kd['bad_key'] == 'bad_key'


def test_is_iterable():
    assert not is_iterable('abc')
    assert is_iterable([1, 2, 3])
    i = iter([1, 2, 3])
    assert is_iterable(i)


def test_latlon_string():
    assert latlon_string(-12.3, ('N', 'S'), 'lat') == ('12', '18.00', 'S')
    assert latlon_string(-123.3, ('E', 'W'), 'long') == ('123', '18.00', 'W')


def test_timespanbinder_length():
    t = ((1667689200, 1667775600, 'day', 86400),
         (1667257200, 1669849200, 'month', 86400 * 30),
         (1640991600, 1672527600, 'year', 31536000))
    for i in t:
        ts = TimeSpan(i[0], i[1])
        tsb = TimespanBinder(ts, None, context=i[2])
        assert tsb.length.raw == i[3]


def test_version_compare():
    from weeutil.weeutil import version_compare
    assert version_compare('1.2.3', '1.2.2') == 1
    assert version_compare('1.2.3', '1.2.3') == 0
    assert version_compare('1.2.2', '1.2.3') == -1
    assert version_compare('1.3', '1.2.2') == 1
    assert version_compare('1.3.0a1', '1.3.0a2') == -1
    assert version_compare('10.3.0', '2.3.0') == 1
    assert version_compare('10.3.0', '10.10.0') == -1
    assert version_compare('2.3.0', '10.3.0') == -1
    assert version_compare('12.0.2-MariaDB-ubu2404', '5.5') == 1


def test_natural_sort_keys():
    from weeutil.weeutil import natural_sort_keys
    a = {'5foo': 'a', '6foo': 'b', '10foo': 'c', '1foo': 'd', '01foo': 'e'}
    assert natural_sort_keys(a) == ['1foo', '01foo', '5foo', '6foo', '10foo']


def test_natural_compare():
    from weeutil.weeutil import natural_compare
    assert natural_compare('5foo', '10foo') == -1
    assert natural_compare('10foo', '5foo') == 1
    assert natural_compare('10foo', '1foo') == 1
    assert natural_compare('10foo', '10foo') == 0
    assert natural_compare('10foo', '11foo') == -1
