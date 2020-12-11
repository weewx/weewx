#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the daily sums in the daily summary.

Ordinarily, these are tested in test_daily. However, gen_fake_data() speeds things up by inserting
a bunch of records in the archive table *then* building the daily summary. This does not test
adding things on the fly.
"""
import datetime
import logging
import os
import time
import unittest

import gen_fake_data
import weeutil.logger
import schemas.wview_small

log = logging.getLogger(__name__)

weeutil.logger.setup('test_manager', {})
os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

import weewx.manager

# Things go *much* faster if we use an abbreviated schema
schema = schemas.wview_small.schema

# Archive interval of one hour
interval = 3600
# Fifteen days worth of data.
start_dt = datetime.date(2019, 6, 1)
stop_dt = datetime.date(2019, 6, 15)
start_ts = int(time.mktime(start_dt.timetuple())) + interval
stop_ts = int(time.mktime(stop_dt.timetuple()))


class TestWeights(unittest.TestCase):
    """Test that inserting records get the weighted sums right. Regression test for issue #623.
    SQLite only --- it is so much faster.
    """

    def setUp(self):
        """Set up an in-memory sqlite database."""
        self.db_manager = weewx.manager.DaySummaryManager.open_with_create(
            {
                'database_name': ':memory:',
                'driver': 'weedb.sqlite'
            },
            schema=schema)

        # Populate the database
        for record in gen_fake_data.genFakeRecords(start_ts, stop_ts, interval=interval):
            self.db_manager.addRecord(record)

    def tearDown(self):
        pass

    def test_weights(self):
        for key in self.db_manager.daykeys:
            archive_key = key if key != 'wind' else 'windSpeed'
            result1 = self.db_manager.getSql("SELECT COUNT(%s) FROM archive" % archive_key)
            result2 = self.db_manager.getSql("SELECT SUM(count) FROM archive_day_%s;" % key)
            self.assertEqual(result1, result2)
            result3 = self.db_manager.getSql("SELECT COUNT(%s) * %d FROM archive"
                                             % (archive_key, interval))
            result4 = self.db_manager.getSql("SELECT SUM(sumtime) FROM archive_day_%s" % key)
            self.assertEqual(result3, result4)


if __name__ == '__main__':
    unittest.main()
