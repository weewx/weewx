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
start_dt = datetime.date(2019, 6, 1)
stop_dt = datetime.date(2019, 6, 15)
# This starts and ends on day boundaries:
start_ts = int(time.mktime(start_dt.timetuple())) + interval_secs
stop_ts = int(time.mktime(stop_dt.timetuple()))
# Add a little data to both ends, so the data do not start and end on day boundaries:
start_ts -= 4 * interval_secs
stop_ts += 4 * interval_secs

db_dict_sqlite = {
    'driver': 'weedb.sqlite',
    # Use an in-memory database:
    'database_name': ':memory:',
    # Can be useful for testing:
    'SQLITE_ROOT': '/var/tmp/weewx_test',
    # 'database_name': 'testmgr.sdb',
}

db_dict_mysql = {
    'host': 'localhost',
    'user': 'weewx',
    'password': 'weewx',
    'database_name': 'test_scratch',
    'driver': 'weedb.mysql',
}


class Common(object):
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


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.db_dict = db_dict_sqlite
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.db_dict = db_dict_mysql
        super(TestMySQL, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError:
            try:
                import pymysql as MySQLdb
            except ImportError as e:
                raise unittest.case.SkipTest(e)
        super(TestMySQL, self).setUp()


def suite():
    tests = ['test_weights', 'test_reweight']

    # Test both sqlite and MySQL:
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
