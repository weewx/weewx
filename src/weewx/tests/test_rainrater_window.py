import pytest

import weewx
import weewx.manager
import weewx.wxxtypes


@pytest.mark.parametrize('units,rain', [(weewx.US, 0.1), (weewx.METRICWX, 1.0)])
def test_archive_rate_excludes_later_loop_packets(units, rain):
    rater = weewx.wxxtypes.RainRater()
    rater.augmented = True
    for stamp, amount in ((100, 4), (101, 2), (1000, 3), (1010, 5)):
        rater.add_loop_packet({'dateTime': stamp, 'usUnits': units, 'rain': amount * rain})
    # Retain the beginning of the archive window while later LOOP packets
    # arrive during archive_delay, and exclude their rain from this record.
    result = rater.get_scalar('rainRate', {'dateTime': 1000}, None)
    assert result.value == pytest.approx(20 * rain)
    assert rater.get_scalar('rainRate', {'dateTime': 1010}, None).value == pytest.approx(32 * rain)


def test_future_event_alone_does_not_create_archive_rain():
    rater = weewx.wxxtypes.RainRater()
    rater.augmented = True
    rater.add_loop_packet({'dateTime': 1010, 'usUnits': weewx.METRICWX, 'rain': 1})
    assert rater.get_scalar('rainRate', {'dateTime': 1000}, None).value == 0


def test_rate_window_is_open_at_start_and_closed_at_stop():
    rater = weewx.wxxtypes.RainRater()
    rater.augmented = True
    for stamp, rain in ((100, 8), (101, 2), (1000, 3)):
        rater.add_loop_packet({'dateTime': stamp, 'usUnits': weewx.METRICWX, 'rain': rain})
    assert rater.get_scalar('rainRate', {'dateTime': 1000}, None).value == 20


@pytest.mark.parametrize('rain_period,retain_period,expected',
                         [(1800, 930, 6), (900, 1800, 8), (900, 600, 8)])
def test_retention_covers_the_rain_window(rain_period, retain_period, expected):
    rater = weewx.wxxtypes.RainRater(rain_period, retain_period)
    rater.augmented = True
    for stamp in (0, 1000, 1500):
        rater.add_loop_packet({'dateTime': stamp, 'usUnits': weewx.METRICWX, 'rain': 1})
    assert rater.get_scalar('rainRate', {'dateTime': 1500}, None).value == expected


def test_initial_database_history_covers_long_rain_window():
    schema = [('dateTime', 'INTEGER NOT NULL PRIMARY KEY'), ('usUnits', 'INTEGER'),
              ('interval', 'INTEGER'), ('rain', 'REAL')]
    with weewx.manager.Manager.open_with_create(
            {'driver': 'weedb.sqlite', 'database_name': ':memory:'}, schema=schema) as manager:
        manager.addRecord([{'dateTime': stamp, 'usUnits': weewx.METRICWX, 'interval': 5, 'rain': 1}
                           for stamp in (0, 1000, 1500)], log_success=False)
        rater = weewx.wxxtypes.RainRater(rain_period=1800, retain_period=930)
        assert rater.get_scalar('rainRate', {'dateTime': 1500}, manager).value == 6
