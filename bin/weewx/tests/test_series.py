#
#    Copyright (c) 2018-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weewx.xtypes.get_series"""

import os.path
import sys
import time
import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

import weewx
import weewx.wxformulas
import weewx.xtypes
import weewx.units
from weeutil.weeutil import TimeSpan

import configobj

import gen_fake_data

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")
cwd = None

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()
month_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
month_stop_tt = (2010, 4, 1, 0, 0, 0, 0, 0, -1)
start_ts = time.mktime(month_start_tt)
stop_ts = time.mktime(month_stop_tt)


class Common(unittest.TestCase):

    def setUp(self):
        global config_path
        global cwd

        # Save and set the current working directory in case some service changes it.
        if cwd:
            os.chdir(cwd)
        else:
            cwd = os.getcwd()

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

    def test_get_series_archive(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('outTemp',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager)
            self.assertEqual(len(start_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
            self.assertEqual(len(stop_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)
            self.assertEqual(len(data_vec[0]), (stop_ts - start_ts) / gen_fake_data.interval + 1)

    def test_get_series_archive_agg(self):
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series('outTemp',
                                                                    TimeSpan(start_ts, stop_ts),
                                                                    db_manager,
                                                                    'avg',
                                                                    24 * 3600)
            # March has 30 days.
            self.assertEqual(len(start_vec[0]), 30 + 1)
            self.assertEqual(len(stop_vec[0]), 30 + 1)
            self.assertEqual(len(data_vec[0]), 30 + 1)


class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(Common):

    def __init__(self, *args, **kwargs):
        self.database_type = "mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)

    def setUp(self):
        try:
            import MySQLdb
        except ImportError as e:
            raise unittest.case.SkipTest(e)
        super(TestMySQL, self).setUp()


def suite():
    tests = ['test_get_series_archive', 'test_get_series_archive_agg']
    #    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))
    return unittest.TestSuite(list(map(TestSqlite, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
