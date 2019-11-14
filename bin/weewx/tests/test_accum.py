#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.accum"""
import time
import unittest

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

        self.assertEqual(ss.min, tmin)
        self.assertEqual(ss.mintime, tmintime)

        # Assumes the last data point is not None:
        self.assertEqual(ss.last, self.dataset[-1]['outTemp'])
        self.assertEqual(ss.lasttime, self.dataset[-1]['dateTime'])

        self.assertEqual(ss.sum, tsum)
        self.assertEqual(ss.count, tcount)
        self.assertEqual(ss.avg, tsum / tcount)

        # Merge ss into its self. Should leave highs and lows unchanged, but double counts:
        ss.mergeHiLo(ss)
        ss.mergeSum(ss)

        self.assertEqual(ss.min, tmin)
        self.assertEqual(ss.mintime, tmintime)

        self.assertEqual(ss.last, self.dataset[-1]['outTemp'])
        self.assertEqual(ss.lasttime, self.dataset[-1]['dateTime'])

        self.assertEqual(ss.sum, 2 * tsum)
        self.assertEqual(ss.count, 2 * tcount)

    class AccumTest(unittest.TestCase):

        def setUp(self):
            # The data set is a list of faked records at 5 second intervals
            self.dataset = list(genFakeRecords(start_ts=start_ts + 5, stop_ts=stop_ts, interval=5))

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
