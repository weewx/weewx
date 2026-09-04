#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the datetimes the FineOffset USB driver works with.

The driver uses aware UTC throughout. An earlier attempt at dropping the
deprecated datetime calls made four of its values aware and left three of them
naive, which broke synchronisation with "can't subtract offset-naive and
offset-aware datetimes" and had to be reverted (commit 2202248b). These tests
cover the arithmetic that failed then, and the conversion back to epoch seconds
that genArchiveRecords() does.
"""
import datetime
import os
import time
import unittest

from weewx.drivers.fousb import DT_MAX, DT_MIN, UTC, FineOffsetUSB

# Neither UTC nor free of daylight saving, so a conversion that went through
# local time would show up in the timestamps below.
os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()


def make_station(records):
    """A FineOffsetUSB object with just enough filled in to yield archive records.

    Built without __init__, which would go looking for a USB device.
    """
    station = FineOffsetUSB.__new__(FineOffsetUSB)
    station._last_rain_arc = None
    station._last_rain_ts_arc = None
    station.max_rain_rate = 10
    station.get_records = lambda since_ts: records
    return station


def record(dt):
    """One entry of the kind get_records() returns, carrying nothing but its time."""
    return {'datetime': dt, 'data': {}, 'interval': 5, 'ptr': 0x0100}


def make_syncing_station(idx, delay=1):
    """A FineOffsetUSB object whose live_data() yields one packet, then stops.

    One packet is enough to reach the break in sync(): with the delay unchanged
    from the one get_data() reported, the estimate lands inside 15 seconds on the
    first pass through the loop.
    """
    packet = {'idx': idx, 'delay': delay}
    station = FineOffsetUSB.__new__(FineOffsetUSB)
    station._station_clock = None
    station.data_format = '1080'  # what dec_ptr() steps by
    station.current_pos = lambda: 0x0100
    station.get_data = lambda ptr, unbuffered=False: packet
    station.live_data = lambda logged_only=False: iter([(packet, 0x0100, False)])
    return station


class ArchiveTimestampTest(unittest.TestCase):

    def test_known_value(self):
        """genArchiveRecords() yields the epoch time of the record's datetime."""
        station = make_station([record(datetime.datetime(2009, 2, 13, 23, 31, 30,
                                                         tzinfo=UTC))])
        self.assertEqual([r['dateTime'] for r in station.genArchiveRecords(0)],
                         [1234567890])

    def test_daylight_saving_boundary(self):
        """The local hour that comes round twice still gives two timestamps.

        Daylight saving ends in America/Los_Angeles on 1-Nov-2026, so 01:30 happens
        twice there. These two records are an hour apart in UTC, and that is the
        difference that has to reach the archive.
        """
        first = datetime.datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
        station = make_station([record(first),
                                record(first + datetime.timedelta(hours=1))])
        self.assertEqual([r['dateTime'] for r in station.genArchiveRecords(0)],
                         [1793521800, 1793525400])


class SyncBoundsTest(unittest.TestCase):

    def test_bounds_carry_utc(self):
        """The two bounds sync() starts out with are aware, and still the extremes."""
        self.assertEqual(DT_MIN.tzinfo, UTC)
        self.assertEqual(DT_MAX.tzinfo, UTC)
        self.assertEqual(DT_MIN.replace(tzinfo=None), datetime.datetime.min)
        self.assertEqual(DT_MAX.replace(tzinfo=None), datetime.datetime.max)

    def test_sync_estimates_from_the_bounds(self):
        """The estimate sync() arrives at, over the comparisons the revert was about.

        The packet is 60 seconds old and its delay is unchanged, which puts the
        window 108 to 120 seconds back, so the estimate is 114. Getting there means
        comparing against both bounds and subtracting one datetime from another,
        which is where a naive value among the aware ones raised TypeError.
        """
        idx = datetime.datetime.fromtimestamp(1234567890, UTC)
        station = make_syncing_station(idx)

        last_date = station.sync(quality=0)[0]

        self.assertEqual(last_date, idx - datetime.timedelta(seconds=114))
        self.assertEqual(last_date.tzinfo, UTC)


if __name__ == '__main__':
    unittest.main()
