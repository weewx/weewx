#
#      Copyright (c) 2023-2026 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

import datetime

import pytest

from weectllib import parse_dates


def test_parse_default():
    from_val, to_val = parse_dates()
    assert from_val is None
    assert to_val is None


def test_parse_date():
    from_val, to_val = parse_dates(date="2021-05-13")
    assert isinstance(from_val, datetime.date)
    assert from_val == datetime.date(2021, 5, 13)
    assert from_val == to_val


def test_parse_datetime():
    from_valt, to_valt = parse_dates(date="2021-05-13", as_datetime=True)
    assert isinstance(from_valt, datetime.datetime)
    assert from_valt == datetime.datetime(2021, 5, 13)
    assert from_valt == to_valt

    from_valt, to_valt = parse_dates(date="2021-05-13T15:47:20", as_datetime=True)
    assert isinstance(from_valt, datetime.datetime)
    assert from_valt == datetime.datetime(2021, 5, 13, 15, 47, 20)


def test_parse_from():
    from_val, to_val = parse_dates(from_date="2021-05-13")
    assert isinstance(from_val, datetime.date)
    assert from_val == datetime.date(2021, 5, 13)
    assert to_val is None


def test_parse_to():
    from_val, to_val = parse_dates(to_date="2021-06-02")
    assert isinstance(to_val, datetime.date)
    assert to_val == datetime.date(2021, 6, 2)
    assert from_val is None


def test_parse_from_to():
    from_val, to_val = parse_dates(from_date="2021-05-13", to_date="2021-06-02")
    assert isinstance(from_val, datetime.date)
    assert from_val == datetime.date(2021, 5, 13)
    assert to_val == datetime.date(2021, 6, 2)


def test_parse_from_to_time():
    from_val, to_val = parse_dates(from_date="2021-05-13T08:30:05",
                                   to_date="2021-06-02T21:11:55",
                                   as_datetime=True)
    assert isinstance(from_val, datetime.datetime)
    assert from_val == datetime.datetime(2021, 5, 13, 8, 30, 5)
    assert to_val == datetime.datetime(2021, 6, 2, 21, 11, 55)
