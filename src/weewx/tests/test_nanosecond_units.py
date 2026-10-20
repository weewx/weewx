import time

import pytest

import weewx.units


@pytest.mark.parametrize('stamp', [0, 1, -1, 1704110400.25])
@pytest.mark.parametrize('unit,scale', [('unix_epoch', 1), ('unix_epoch_ms', 1000)])
def test_nanoseconds_have_si_scale(stamp, unit, scale):
    result = weewx.units.convert((stamp * scale, unit, 'group_time'), 'unix_epoch_ns')
    assert result.value == pytest.approx(stamp * 10**9)
    restored = weewx.units.convert((stamp * 10**9, 'unix_epoch_ns', 'group_time'), unit)
    assert restored.value == pytest.approx(stamp * scale)


def test_julian_conversions_and_time_formatting():
    julian = weewx.units.epoch_to_dublin(1704110400)
    result = weewx.units.convert((julian, 'dublin_jd', 'group_time'), 'unix_epoch_ns')
    assert result.value == pytest.approx(1704110400 * 10**9)
    restored = weewx.units.convert((1704110400 * 10**9, 'unix_epoch_ns', 'group_time'), 'dublin_jd')
    assert restored.value == pytest.approx(julian)
    formatter = weewx.units.Formatter()
    assert formatter.toString((1704110400 * 10**9, 'unix_epoch_ns', 'group_time'),
                              useThisFormat='%Y-%m-%d %H:%M:%S') == time.strftime(
                                  '%Y-%m-%d %H:%M:%S', time.localtime(1704110400))
