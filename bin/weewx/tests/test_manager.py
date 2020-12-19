#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the weighted sums in the daily summary.

Ordinarily, these are tested in test_daily. However, gen_fake_data.configDatabase() speeds things
up by inserting a bunch of records in the archive table *then* building the daily summary. This
does not test adding things on the fly.

This file also tests reweighting the weighted sums.

It also tests the V4.3 patch.
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
# Fifteen days worth of data.
start_d = datetime.date(2020, 10, 26)
stop_d = datetime.date(2020, 11, 11)
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

    def setUp(self):
        """Set up the database."""
        try:
            # Drop the old database
            weedb.drop(self.db_dict)
        except weedb.NoDatabaseError:
            pass
        # Get a new database by initializing with the schema
        self.db_manager = weewx.manager.DaySummaryManager.open_with_create(self.db_dict,
                                                                           schema=schema)

        # Populate the database
        self.db_manager.addRecord(
            gen_fake_data.genFakeRecords(start_ts, stop_ts, interval=interval_secs))

    def tearDown(self):
        pass

    def test_weights(self):
        """Check that the weighted sums were done correctly."""
        self.check_weights()

    def test_reweight(self):
        """Check that recalculating the weighted sums was done correctly"""
        self.db_manager.recalculate_weights()
        self.check_weights()

    def check_weights(self):
        for key in self.db_manager.daykeys:
            archive_key = key if key != 'wind' else 'windSpeed'
            result1 = self.db_manager.getSql("SELECT COUNT(%s) FROM archive" % archive_key)
            result2 = self.db_manager.getSql("SELECT SUM(count) FROM archive_day_%s;" % key)
            self.assertEqual(result1, result2)
            result3 = self.db_manager.getSql("SELECT COUNT(%s) * %d FROM archive"
                                             % (archive_key, interval_secs))
            result4 = self.db_manager.getSql("SELECT SUM(sumtime) FROM archive_day_%s" % key)
            self.assertEqual(result3, result4)


class CommonPatchTest(CommonWeightTests):
    """Test patching the flawed databases from V4.2."""

    def setUp(self):
        # Set up the database
        super(CommonPatchTest, self).setUp()
        with weedb.Transaction(self.db_manager.connection) as cursor:
            # Bugger up roughly half the database
            for key in self.db_manager.daykeys:
                sql_update = "UPDATE %s_day_%s SET wsum=sum, sumtime=count WHERE dateTime >?" \
                             % (self.db_manager.table_name, key)
                cursor.execute(sql_update, (mid_ts,))
        self.db_manager.version = '2.0'

    def test_patch(self):
        self.db_manager.patch_sums()
        self.check_weights()
        self.assertEqual(self.db_manager.version, weewx.manager.DaySummaryManager.version)


class TestSqliteWeights(CommonWeightTests, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.db_dict = db_dict_sqlite
        super(TestSqliteWeights, self).__init__(*args, **kwargs)


class TestSqlitePatch(CommonPatchTest, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.db_dict = db_dict_sqlite
        super(CommonPatchTest, self).__init__(*args, **kwargs)


class TestMySQLWeights(CommonWeightTests, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.db_dict = db_dict_mysql
        super(TestMySQLWeights, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super(TestMySQLWeights, self).setUp()


def suite():
    tests = ['test_weights', 'test_reweight']

    # Test both sqlite and MySQL:
    return unittest.TestSuite(list(map(TestSqliteWeights, tests))
                              + list(map(TestMySQLWeights, tests))
                              + list(map(TestSqlitePatch, ['test_patch'])))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
