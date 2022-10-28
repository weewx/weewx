#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the xtypes example vaporpressure"""
import logging
import os
import sys
import time
import unittest

import configobj

import gen_fake_data
import weeutil.logger
import weewx
import weewx.xtypes
from weeutil.weeutil import TimeSpan

log = logging.getLogger(__name__)
weeutil.logger.setup('test_vaporpressure', {})

weewx.debug = 1

# Register vapor pressure with the xtypes system
sys.path.append('..')
import vaporpressure
weewx.xtypes.xtypes.append(vaporpressure.VaporPressure())

# Find the configuration file. Assume it is in the standard position:
config_path = os.path.join(os.path.dirname(__file__), '../../bin/weewx/tests', 'testgen.conf')
cwd = None

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# Test for 1-Mar-2010 in the synthetic database
day_start_tt = (2010, 3, 1, 0, 0, 0, 0, 0, -1)
day_stop_tt = (2010, 3, 2, 0, 0, 0, 0, 0, -1)
day_start_ts = time.mktime(day_start_tt)
day_stop_ts = time.mktime(day_stop_tt)


class CommonTests(object):
    """Test that inserting records get the weighted sums right. Regression test for issue #623. """

    expected_vapor_p = [1.5263, 1.434, 1.3643, 1.3157, 1.2873, 1.2784, 1.2887, 1.3186, 1.3686,
                        1.4401, 1.5343, 1.6532, 1.7987, 1.9728, 2.1773, 2.4137, 2.6826, 2.9833,
                        3.314, 3.6706, 4.0472, 4.4354, 4.825, 5.2035, 5.5573, 5.8724, 6.1351,
                        6.3333, 6.4576, 6.5017, 6.4635, 6.3449, 6.152, 5.8941, 5.5831, 5.2327,
                        4.8568, 4.4692, 4.0822, 3.7063, 3.3498, 3.0189, 2.7176, 2.4481, 2.2109,
                        2.0056, 1.8308, 1.6847]


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
            sys.stderr.write("Unable to open configuration file %s" % self.config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.config_dict, database_type=self.database_type)

    def tearDown(self):
        pass

    def test_series(self):
        """Check for calculating a series of vapor pressures."""
        with weewx.manager.open_manager_with_config(self.config_dict, 'wx_binding') as db_manager:
            start_vec, stop_vec, data_vec = weewx.xtypes.get_series(
                'vapor_p',
                TimeSpan(day_start_ts, day_stop_ts),
                db_manager)
            self.assertEqual([round(x, 4) for x in data_vec[0]], CommonTests.expected_vapor_p, 4)


class TestSqlite(CommonTests, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.database_type = "sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)


class TestMySQL(CommonTests, unittest.TestCase):

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
    tests = ['test_series', ]

    # Test both sqlite and MySQL:
    return unittest.TestSuite(list(map(TestSqlite, tests)) + list(map(TestMySQL, tests)))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
