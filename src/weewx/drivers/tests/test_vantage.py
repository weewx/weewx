#
#    Copyright (c) 2026 the WeeWX contributors
#
#    See the file LICENSE.txt for your full rights.
#
"""Test how the Vantage driver downloads archive records.

These tests stand a fake serial port in front of the driver, so they need no
hardware. What they are mostly about is telling apart the two reasons the
download loop can stop early: reaching the end of the data, which is normal, and
a logger whose memory has gone bad, which is not.
"""
import struct
import time
import unittest
from unittest.mock import patch

import weewx.drivers.vantage
from weewx.drivers.vantage import Vantage

# Midnight, 1-Jan-2024, local time
START_TS = int(time.mktime((2024, 1, 1, 0, 0, 0, 0, 0, -1)))
INTERVAL = 300


def make_record(ts):
    """Build one 52 byte Rev B archive record carrying the given timestamp.

    Every other field is left at zero, which the driver decodes without
    complaint. Only the date and time stamp, and the record type in byte 42,
    matter here.
    """
    tt = time.localtime(ts)
    date_stamp = tt.tm_mday + (tt.tm_mon << 5) + ((tt.tm_year - 2000) << 9)
    time_stamp = tt.tm_hour * 100 + tt.tm_min
    record = bytearray(52)
    record[0:4] = struct.pack("<HH", date_stamp, time_stamp)
    record[42] = 0x00  # Rev B
    return bytes(record)


def make_page(records):
    """Assemble a 267 byte archive page out of up to five records.

    Layout: one sequence byte, five 52 byte records, four unused bytes, then the
    two byte CRC that get_data_with_crc16() leaves on the end.
    """
    assert len(records) <= 5
    page = bytearray(267)
    for i, record in enumerate(records):
        page[1 + 52 * i:53 + 52 * i] = record
    return bytes(page)


def unused_record():
    """A record the console has never written to. Reads as 0xff throughout."""
    return b'\xff' * 52


class FakePort:
    """Stands in for VantageSerialWrapper, handing out canned responses.

    It answers the six byte DMPAFT reply with whatever page count it was given,
    then hands over the pages one at a time. The page count is deliberately not
    tied to the number of pages supplied: a console that says one thing and does
    another is exactly what is being tested.
    """

    def __init__(self, npages, start_index, pages):
        self.npages = npages
        self.start_index = start_index
        self.pages = list(pages)
        self.pages_read = 0

    def wakeup_console(self, max_tries=3):
        pass

    def send_data(self, data):
        pass

    def send_data_with_crc16(self, data, max_tries=3):
        pass

    def get_data_with_crc16(self, nbytes, prompt=None, max_tries=3):
        if nbytes == 6:
            # The reply to DMPAFT: page count, starting index, then the CRC.
            return struct.pack("<HH", self.npages, self.start_index) + b'\x00\x00'
        self.pages_read += 1
        return self.pages.pop(0)


def make_station(port):
    """A Vantage object with just enough filled in to decode archive records.

    Built without __init__, which would go looking for a console.
    """
    station = Vantage.__new__(Vantage)
    station.port = port
    station.max_tries = 3
    station.max_dst_jump = 7200
    station.archive_interval_ = INTERVAL  # what the archive_interval property reads
    station.rain_bucket_type = 0
    station.model_type = 2
    station.iss_id = 1
    station.hardware_type = 16
    return station


def rendered(mock_log):
    """The log calls as logging would render them.

    Indexed rather than .args, which is Python 3.8 and later.
    """
    return "\n".join(c[0][0] % c[0][1:] for c in mock_log.call_args_list)


class ArchiveDownloadTest(unittest.TestCase):

    def test_full_pages(self):
        """A console that delivers everything it promised."""
        timestamps = [START_TS + i * INTERVAL for i in range(10)]
        records = [make_record(ts) for ts in timestamps]
        port = FakePort(2, 0, [make_page(records[0:5]), make_page(records[5:10])])
        station = make_station(port)

        with patch.object(weewx.drivers.vantage.log, 'error') as mock_error:
            got = list(station.genDavisArchiveRecords(START_TS - INTERVAL))

        self.assertEqual([r['dateTime'] for r in got], timestamps)
        mock_error.assert_not_called()

    def test_wrap_around_within_final_page(self):
        """The normal way a download ends.

        The logger memory wraps part way through the last page, so the records
        after the wrap are old ones and the loop stops. Some of the promised
        records are therefore never returned, and that is not an error.
        """
        timestamps = [START_TS + i * INTERVAL for i in range(7)]
        records = [make_record(ts) for ts in timestamps]
        # The third record of the second page is from two weeks ago: the wrap.
        stale = make_record(START_TS - 14 * 24 * 3600)
        port = FakePort(2, 0, [make_page(records[0:5]),
                               make_page(records[5:7] + [stale] * 3)])
        station = make_station(port)

        with patch.object(weewx.drivers.vantage.log, 'error') as mock_error:
            got = list(station.genDavisArchiveRecords(START_TS - INTERVAL))

        self.assertEqual([r['dateTime'] for r in got], timestamps)
        mock_error.assert_not_called()

    def test_corrupt_memory(self):
        """Corrupt logger memory, in the shape the wiki describes.

        The console announces many pages, then the very first record it sends is
        already older than the time that was asked for. Nothing is returned, and
        without a message that is hard to tell from "there was no new data".
        """
        stale = make_record(START_TS - 14 * 24 * 3600)
        port = FakePort(45, 1, [make_page([stale] * 5)])
        station = make_station(port)

        with patch.object(weewx.drivers.vantage.log, 'error') as mock_error:
            got = list(station.genDavisArchiveRecords(START_TS))

        self.assertEqual(got, [])
        text = rendered(mock_error)
        # It says how far apart the promise and the delivery were...
        self.assertIn("promised 224 archive records, but returned 0", text)
        # ... and where to go next.
        self.assertIn(weewx.drivers.vantage.CORRUPT_MEMORY_URL, text)

    def test_unused_records_are_not_corruption(self):
        """A logger that was cleared recently.

        Its pages hold records that have never been written, which read as 0xff.
        The loop stops there with most of the promised records outstanding, but
        the memory is fine: this is what a station looks like just after
        'weectl device --clear-memory'. Complaining here would send people
        chasing a fix they had only just applied.
        """
        timestamps = [START_TS + i * INTERVAL for i in range(2)]
        records = [make_record(ts) for ts in timestamps]
        port = FakePort(20, 0, [make_page(records + [unused_record()] * 3)])
        station = make_station(port)

        with patch.object(weewx.drivers.vantage.log, 'error') as mock_error:
            got = list(station.genDavisArchiveRecords(START_TS - INTERVAL))

        self.assertEqual([r['dateTime'] for r in got], timestamps)
        mock_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
