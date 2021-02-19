#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the weighted sums in the daily summary. Most of tests for the daily summaries are in module
test_daily. However, gen_fake_data.configDatabase() speeds things up by inserting a bunch of
records in the archive table *then* building the daily summary, which means it does not test
building the daily summaries by using addRecord().

The tests in this module take a different strategy by using addRecord() directly. This takes a lot
longer, so the tests use a more abbreviated database.

This file also tests reweighting the weighted sums.

It also tests the V4.3 and v4.4 patches.
"""
import datetime
import logging
import os
import time
import unittest

import gen_fake_data
import schemas.wview_small
import weedb
import weeutil.logger
import weewx.manager

log = logging.getLogger(__name__)

weeutil.logger.setup('test_manager', {})
os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# Things go *much* faster if we use an abbreviated schema
schema = schemas.wview_small.schema

# Archive interval of one hour
interval_secs = 3600
# Twelve days worth of data.
start_d = datetime.date(2020, 10, 26)
stop_d = datetime.date(2020, 11, 7)
# This starts and ends on day boundaries:
start_ts = int(time.mktime(start_d.timetuple())) + interval_secs
stop_ts = int(time.mktime(stop_d.timetuple()))
# Add a little data to both ends, so the data do not start and end on day boundaries:
start_ts -= 4 * interval_secs
stop_ts += 4 * interval_secs

# Find something roughly near the half way mark
mid_d = datetime.date(2020, 11, 1)
mid_ts = int(time.mktime(mid_d.timetuple()))

db_dict_sqlite = {
    'driver': 'weedb.sqlite',
    # Use an in-memory database:
    'database_name': ':memory:',
    # Can be useful for testing:
    # 'SQLITE_ROOT': '/var/tmp/weewx_test',
    # 'database_name': 'testmgr.sdb',
}

db_dict_mysql = {
    'host': 'localhost',
    'user': 'weewx',
    'password': 'weewx',
    'database_name': 'test_scratch',
    'driver': 'weedb.mysql',
}


class CommonWeightTests(object):
    """Test that inserting records get the weighted sums right. Regression test for issue #623. """

    def test_weights(self):
        """Check that the weighted sums were done correctly."""
        self.check_weights()

    def test_reweight(self):
        """Check that recalculating the weighted sums was done correctly"""
        self.db_manager.recalculate_weights()
        self.check_weights()

    def check_weights(self):
        # check weights for scalar types
        for key in self.db_manager.daykeys:
            archive_key = key if key != 'wind' else 'windSpeed'
            result1 = self.db_manager.getSql("SELECT COUNT(%s) FROM archive" % archive_key)
            result2 = self.db_manager.getSql("SELECT SUM(count) FROM archive_day_%s;" % key)
            self.assertEqual(result1, result2)
            result3 = self.db_manager.getSql("SELECT COUNT(%s) * %d FROM archive"
                                             % (archive_key, interval_secs))
            result4 = self.db_manager.getSql("SELECT SUM(sumtime) FROM archive_day_%s" % key)
            self.assertEqual(result3, result4)

            result5 = self.db_manager.getSql("SELECT SUM(%s * `interval` * 60) FROM archive"
                                             % archive_key)
            result6 = self.db_manager.getSql("SELECT SUM(wsum) FROM archive_day_%s" % key)
            if result5[0] is None:
                self.assertEqual(result6[0], 0.0)
            else:
                self.assertAlmostEqual(result5[0], result6[0], 3)
        # check weights for vector types, for now that is just type wind
        result7 = self.db_manager.getSql("SELECT SUM(xsum), SUM(ysum), SUM(dirsumtime) FROM archive_day_wind")
        self.assertAlmostEqual(result7[0], 5032317.021, 3)
        self.assertAlmostEqual(result7[1], -2600.126, 3)
        self.assertEqual(result7[2], 1040400)


class TestSqliteWeights(CommonWeightTests, unittest.TestCase):
    """Test using the SQLite database"""

    def setUp(self):
        self.db_manager = setup_database(db_dict_sqlite)

    # The patch test is done with sqlite only, because it is so much faster
    def test_patch(self):
        # Sanity check that the original database is at V4.0
        self.assertEqual(self.db_manager.version, weewx.manager.DaySummaryManager.version)

        # Bugger up roughly half the database
        with weedb.Transaction(self.db_manager.connection) as cursor:
            for key in self.db_manager.daykeys:
                sql_update = "UPDATE %s_day_%s SET wsum=sum, sumtime=count WHERE dateTime >?" \
                             % (self.db_manager.table_name, key)
                cursor.execute(sql_update, (mid_ts,))

        # Force the patch (could use '2.0' or '3.0':
        self.db_manager.version = '2.0'

        self.db_manager.patch_sums()
        self.check_weights()

        # Make sure the version was set to V4.0 after the patch
        self.assertEqual(self.db_manager.version, weewx.manager.DaySummaryManager.version)


class TestMySQLWeights(CommonWeightTests, unittest.TestCase):
    """Test using the MySQL database"""

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)

        self.db_manager = setup_database(db_dict_mysql)


def setup_database(db_dict):
    """Set up a database by using addRecord()"""
    try:
        # Drop the old database
        weedb.drop(db_dict)
    except weedb.NoDatabaseError:
        pass
    # Get a new database by initializing with the schema
    db_manager = weewx.manager.DaySummaryManager.open_with_create(db_dict, schema=schema)

    # Populate the database. By passing in a generator, it is all done as one transaction.
    db_manager.addRecord(gen_fake_data.genFakeRecords(start_ts, stop_ts, interval=interval_secs))

    return db_manager


if __name__ == '__main__':
    unittest.main()
