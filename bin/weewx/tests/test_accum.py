#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.accum"""
import math
import time
import unittest

import gen_fake_data
import weewx.accum
from gen_fake_data import genFakeRecords
from weeutil.weeutil import TimeSpan

# 30 minutes worth of data:
start_ts = int(time.mktime((2009, 1, 1, 0, 0, 0, 0, 0, -1)))
stop_ts = int(time.mktime((2009, 1, 1, 0, 30, 0, 0, 0, -1)))


class ScalarStatsTest(unittest.TestCase):

    def setUp(self):

        # The data set is a list of faked records at 5 second intervals
        self.dataset = list(genFakeRecords(start_ts=start_ts + 5, stop_ts=stop_ts, interval=5))

    def test_scalarStats(self):

        ss = weewx.accum.ScalarStats()

        # Make sure the default values work:
        self.assertEqual(ss.min, None)
        self.assertEqual(ss.last, None)

        tmin = tmintime = None
        tsum = tcount = 0
        N = 0
        for rec in self.dataset:
            # Make a copy. We may be changing it.
            record = dict(rec)
            if record['outTemp'] is not None:
                tsum += record['outTemp']
                tcount += 1
                if tmin is None or record['outTemp'] < tmin:
                    tmin = record['outTemp']
                    tmintime = record['dateTime']

            # Every once in a while, try to insert a string.
            N += 1
            if N % 20 == 0 and record['outTemp'] is not None:
                record['outTemp'] = str(record['outTemp'])

            ss.addHiLo(record['outTemp'], record['dateTime'])
            ss.addSum(record['outTemp'])

        # Some of these tests look for "almost equal", because of the rounding errors introduced by
        # conversion to a string and back
        self.assertAlmostEqual(ss.min, tmin, 6)
        self.assertEqual(ss.mintime, tmintime)

        # Assumes the last data point is not None:
        self.assertAlmostEqual(ss.last, self.dataset[-1]['outTemp'], 6)
        self.assertEqual(ss.lasttime, self.dataset[-1]['dateTime'])

        self.assertAlmostEqual(ss.sum, tsum, 6)
        self.assertEqual(ss.count, tcount)
        self.assertAlmostEqual(ss.avg, tsum / tcount, 6)

        # Merge ss into its self. Should leave highs and lows unchanged, but double counts:
        ss.mergeHiLo(ss)
        ss.mergeSum(ss)

        self.assertAlmostEqual(ss.min, tmin, 6)
        self.assertEqual(ss.mintime, tmintime)

        self.assertAlmostEqual(ss.last, self.dataset[-1]['outTemp'], 6)
        self.assertEqual(ss.lasttime, self.dataset[-1]['dateTime'])

        self.assertAlmostEqual(ss.sum, 2 * tsum, 6)
        self.assertEqual(ss.count, 2 * tcount)


class AccumTest(unittest.TestCase):

    def setUp(self):
        # The data set is a list of faked records at 5 second intervals. The stage of the weather cycle
        # is set so that some rain will appear.
        self.dataset = list(genFakeRecords(start_ts=start_ts + 5, stop_ts=stop_ts, interval=5,
                                           weather_phase_offset=gen_fake_data.weather_cycle * math.pi / 2.0))

    def test_Accum_getRecord(self):
        """Test extraction of record from an accumulator."""
        accum = weewx.accum.Accum(TimeSpan(start_ts, stop_ts))
        for record in self.dataset:
            accum.addRecord(record)
        extracted = accum.getRecord()

        self.assertEqual(extracted['dateTime'], self.dataset[-1]['dateTime'])
        self.assertEqual(extracted['usUnits'], weewx.US)

        sum_t = 0
        count_t = 0
        for rec in self.dataset:
            if rec['outTemp'] is not None:
                sum_t += rec['outTemp']
                count_t += 1
        self.assertEqual(extracted['outTemp'], sum_t / count_t)

        max_wind = 0
        max_dir = None
        for rec in self.dataset:
            if rec['windGust'] is not None and rec['windGust'] > max_wind:
                max_wind = rec['windGust']
                max_dir = rec['windGustDir']
        self.assertEqual(extracted['windGust'], max_wind)
        self.assertEqual(extracted['windGustDir'], max_dir)

        rain_sum = 0
        for rec in self.dataset:
            if rec['rain'] is not None:
                rain_sum += rec['rain']
        self.assertEqual(extracted['rain'], rain_sum)

    def test_Accum_with_string(self):
        """Test records with string literals in them."""
        for i, record in enumerate(self.dataset):
            record['stringType'] = "AString%d" % i

        # Trying to add a string to the default accumulators should result in an exception
        with self.assertRaises(ValueError):
            accum = weewx.accum.Accum(TimeSpan(start_ts, stop_ts))
            for record in self.dataset:
                accum.addRecord(record)
        # Try it again, but this time specifying a FirstLast accumulator for type 'stringType':
        weewx.accum.accum_dict.extend({'stringType': {'accumulator': 'firstlast', 'extractor': 'last'}})
        accum = weewx.accum.Accum(TimeSpan(start_ts, stop_ts))
        for record in self.dataset:
            accum.addRecord(record)
        # The value extracted for the string should be the last one seen
        rec = accum.getRecord()
        self.assertEqual(rec['stringType'], "AString%d" % (len(self.dataset) - 1))

    def test_Accum_unit_change(self):

        # Change the units used by a record mid-stream
        self.dataset[5]['usUnits'] = weewx.METRICWX
        # This should result in a ValueError
        with self.assertRaises(ValueError):
            accum = weewx.accum.Accum(TimeSpan(start_ts, stop_ts))
            for record in self.dataset:
                accum.addRecord(record)


if __name__ == '__main__':
    unittest.main()
