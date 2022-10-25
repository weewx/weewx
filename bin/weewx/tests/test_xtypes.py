#
#      Copyright (c) 2019-2022 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import locale
import logging
import os.path
import sys
import time
import unittest

import configobj
from six.moves import map

import gen_fake_data
import weeutil.logger
import weeutil.weeutil
import weewx.units
import weewx.xtypes

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('test_xtypes', {})

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# This will use the locale specified by the environment variable 'LANG'
# Other options are possible. See:
# http://docs.python.org/2/library/locale.html#locale.setlocale
locale.setlocale(locale.LC_ALL, '')

# Find the configuration file. It's assumed to be in the same directory as me, so first figure
# out where that is.
my_dir = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# The full path to the configuration file:
config_path = os.path.join(my_dir, "testgen.conf")

month_timespan = weeutil.weeutil.TimeSpan(1283324400, 1285916400)


class Common(object):

    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass

    def test_daily_vecdir(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                           month_timespan,
                                                           'vecdir',
                                                           db_manager)
        self.assertAlmostEqual(vt[0], 60.52375, 5)
        self.assertEqual(vt[1], 'degree_compass', 'group_direction')

    def test_daily_vecavg(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                           month_timespan,
                                                           'vecavg',
                                                           db_manager)
        self.assertAlmostEqual(vt[0], 8.13691, 5)
        self.assertEqual(vt[1], 'mile_per_hour', 'group_speed')

    def test_archive_table_vecdir(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.ArchiveTable.get_aggregate('wind',
                                                         month_timespan,
                                                         'vecdir',
                                                         db_manager)
        self.assertAlmostEqual(vt[0], 60.52375, 5)
        self.assertEqual(vt[1], 'degree_compass', 'group_direction')

    def test_archive_table_vecavg(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.ArchiveTable.get_aggregate('wind',
                                                         month_timespan,
                                                         'vecavg',
                                                         db_manager)
        self.assertAlmostEqual(vt[0], 8.13691, 5)
        self.assertEqual(vt[1], 'mile_per_hour', 'group_speed')

    def test_archive_table_long_vecdir(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.ArchiveTable.get_wind_aggregate_long('wind',
                                                                   month_timespan,
                                                                   'vecdir',
                                                                   db_manager)
        self.assertAlmostEqual(vt[0], 60.52375, 5)
        self.assertEqual(vt[1], 'degree_compass', 'group_direction')

    def test_archive_table_long_vecavg(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            vt = weewx.xtypes.ArchiveTable.get_wind_aggregate_long('wind',
                                                                   month_timespan,
                                                                   'vecavg',
                                                                   db_manager)
        self.assertAlmostEqual(vt[0], 8.13691, 5)
        self.assertEqual(vt[1], 'mile_per_hour', 'group_speed')


class TestSqlite(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
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
    tests = ['test_daily_vecdir', 'test_daily_vecavg',
             'test_archive_table_vecdir', 'test_archive_table_vecavg',
             'test_archive_table_long_vecdir', 'test_archive_table_long_vecavg']
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=1).run(suite())
