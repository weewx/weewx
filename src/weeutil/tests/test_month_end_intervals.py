import datetime
import os
import time

import pytest

import weeutil.weeutil


@pytest.mark.parametrize('zone', ['UTC', 'Europe/Berlin'])
@pytest.mark.parametrize('year,february', [(2023, 28), (2024, 29)])
@pytest.mark.parametrize('day', [1, 28, 29, 30, 31])
def test_month_boundaries_keep_original_day_after_short_month(monkeypatch, zone, year, february, day):
    old_zone = os.environ.get('TZ')
    monkeypatch.setenv('TZ', zone)
    time.tzset()
    start = datetime.datetime(year, 1, day, 12, 30)
    stop = datetime.datetime(year, 3, day, 12, 30)
    try:
        spans = list(weeutil.weeutil.intervalgen(start.timestamp(), stop.timestamp(), 'month'))
        ends = [datetime.datetime.fromtimestamp(span.stop) for span in spans]
        assert ends == [datetime.datetime(year, 2, min(day, february), 12, 30),
                        stop]
        assert spans[0].start == start.timestamp()
        assert all(a.stop == b.start for a, b in zip(spans, spans[1:]))
        stamps = list(weeutil.weeutil.stampgen(start.timestamp(), stop.timestamp(),
                                              365.25 / 12 * 24 * 3600))
        assert stamps == [start.timestamp()] + [span.stop for span in spans]
    finally:
        if old_zone is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = old_zone
        time.tzset()


def test_month_interval_truncates_at_stop_and_crosses_year():
    start = datetime.datetime(2023, 12, 31, 12)
    stop = datetime.datetime(2024, 2, 15, 12)
    spans = list(weeutil.weeutil.intervalgen(start.timestamp(), stop.timestamp(), 'month'))
    assert [datetime.datetime.fromtimestamp(span.stop) for span in spans] == [
        datetime.datetime(2024, 1, 31, 12), stop]
