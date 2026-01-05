#
#      Copyright (c) 2019-2026 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

import locale
import logging
import os.path
import time

import pytest

import weeutil.logger
import weeutil.weeutil
import weewx.manager
import weewx.xtypes

# Do not delete the following line. The module is used by an underlying xtype
import misc

weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('weetest_xtypes')

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# This will use the locale specified by the environment variable 'LANG'
# Other options are possible. See:
# https://docs.python.org/3/library/locale.html#locale.setlocale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Month of September 2010:
month_timespan = weeutil.weeutil.TimeSpan(1283324400, 1285916400)


def test_daily_scalar(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt_min = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                           month_timespan,
                                                           'min',
                                                           db_manager)
        vt_mintime = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                               month_timespan,
                                                               'mintime',
                                                               db_manager)
        vt_avg = weewx.xtypes.DailySummaries.get_aggregate('outTemp',
                                                           month_timespan,
                                                           'avg',
                                                           db_manager)

    assert vt_min[0] == pytest.approx(38.922, abs=1e-3)
    assert vt_avg[0] == pytest.approx(57.128, abs=1e-3)
    assert vt_mintime[0] == 1283511600


def test_daily_vecdir(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                       month_timespan,
                                                       'vecdir',
                                                       db_manager)
    assert vt[0] == pytest.approx(60.52375, abs=1e-5)
    assert vt[1] == 'degree_compass'
    assert vt[2] == 'group_direction'


def test_daily_vecavg(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.DailySummaries.get_aggregate('wind',
                                                       month_timespan,
                                                       'vecavg',
                                                       db_manager)
    assert vt[0] == pytest.approx(8.13691, abs=1e-5)
    assert vt[1] == 'mile_per_hour'
    assert vt[2] == 'group_speed'


def test_archive_table_vecdir(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.ArchiveTable.get_aggregate('wind',
                                                     month_timespan,
                                                     'vecdir',
                                                     db_manager)
    assert vt[0] == pytest.approx(60.52375, abs=1e-5)
    assert vt[1] == 'degree_compass'
    assert vt[2] == 'group_direction'


def test_archive_table_vecavg(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.ArchiveTable.get_aggregate('wind',
                                                     month_timespan,
                                                     'vecavg',
                                                     db_manager)
    assert vt[0] == pytest.approx(8.13691, abs=1e-5)
    assert vt[1] == 'mile_per_hour'
    assert vt[2] == 'group_speed'


def test_archive_table_long_vecdir(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.ArchiveTable.get_wind_aggregate_long('wind',
                                                               month_timespan,
                                                               'vecdir',
                                                               db_manager)
    assert vt[0] == pytest.approx(60.52375, abs=1e-5)
    assert vt[1] == 'degree_compass'
    assert vt[2] == 'group_direction'


def test_archive_table_long_vecavg(config_dict):
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.ArchiveTable.get_wind_aggregate_long('wind',
                                                               month_timespan,
                                                               'vecavg',
                                                               db_manager)
    assert vt[0] == pytest.approx(8.13691, abs=1e-5)
    assert vt[1] == 'mile_per_hour'
    assert vt[2] == 'group_speed'


def test_has_data_true(config_dict):
    """Test has_data() with a type known to have data"""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        result = weewx.xtypes.has_data('testTemp', month_timespan, db_manager)
        assert result


def test_has_data_false(config_dict):
    """Test has_dataconfig_dict) with a type that is known, but cannot be calculated"""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        result = weewx.xtypes.has_data('fooTemp', month_timespan, db_manager)
        assert not result


def test_has_data_unknown(config_dict):
    """Test has_data() with a type that is not known"""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        result = weewx.xtypes.has_data('otherTemp', month_timespan, db_manager)
        assert not result


def test_get_aggregate_none(config_dict):
    """Test get_aggregate() with a type that is known, but cannot be calculated"""
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as db_manager:
        vt = weewx.xtypes.get_aggregate('fooTemp', month_timespan, 'mintime', db_manager)
        assert vt[0] is None
        assert vt[1] == 'unix_epoch'
        assert vt[2] == 'group_time'
