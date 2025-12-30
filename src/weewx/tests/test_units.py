#
#    Copyright (c) 2009-2025 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.units"""

import pytest
import operator

import weewx.units
from weewx.units import ValueTuple


default_formatter = weewx.units.get_default_formatter()


def test_std_unit_systems():
    assert weewx.units.MetricUnits['group_rain'] == 'cm'
    assert weewx.units.MetricUnits['group_rainrate'] == 'cm_per_hour'
    assert weewx.units.MetricUnits['group_speed'] == 'km_per_hour'
    assert weewx.units.MetricUnits['group_speed2'] == 'km_per_hour2'

    assert weewx.units.MetricWXUnits['group_rain'] == 'mm'
    assert weewx.units.MetricWXUnits['group_rainrate'] == 'mm_per_hour'
    assert weewx.units.MetricWXUnits['group_speed'] == 'meter_per_second'
    assert weewx.units.MetricWXUnits['group_speed2'] == 'meter_per_second2'


def testVT():
    a = ValueTuple(68.0, "degree_F", "group_temperature")
    b = ValueTuple(18.0, "degree_F", "group_temperature")
    c = ValueTuple(None, "degree_F", "group_temperature")
    d = ValueTuple(1020.0, "mbar", "group_pressure")

    assert a + b == ValueTuple(86.0, "degree_F", "group_temperature")
    assert a - b == ValueTuple(50.0, "degree_F", "group_temperature")
    with pytest.raises(TypeError):
        operator.add(a, c)
    with pytest.raises(TypeError):
        operator.add(a, d)
        
def testConvert():
    #Test the US converter:
    c = weewx.units.Converter()
    value_t_m = (20.01, "degree_C", "group_temperature")
    value_t_us = (68.018, "degree_F", "group_temperature")
    assert c.convert(value_t_m) == value_t_us

    # Test converting mbar_per_hour to inHg_per_hour
    value_t = (1, "mbar_per_hour", "group_pressurerate")
    converted = c.convert(value_t)
    # Compensate for small rounding errors:
    assert converted[0] == pytest.approx(0.02953)
    assert converted[1] == "inHg_per_hour"
    assert converted[2] == "group_pressurerate"

    # Test converting a sequence:
    value_t_m_seq = ([10.0, 20.0, 30.0], "degree_C", "group_temperature")
    value_t_us_seq = ([50.0, 68.0, 86.0], "degree_F", "group_temperature")
    assert c.convert(value_t_m_seq) == value_t_us_seq

    # Now the metric converter:
    cm = weewx.units.Converter(weewx.units.MetricUnits)
    assert cm.convert(value_t_us) == value_t_m
    assert cm.convert(value_t_us_seq) == value_t_m_seq
    # Test a no-op conversion (US to US):
    assert c.convert(value_t_us) == value_t_us

    # Test converting inHg_per_hour to mbar_per_hour
    value_t = (0.6, "inHg_per_hour", "group_pressurerate")
    converted = cm.convert(value_t)
    assert converted[0] == pytest.approx(20.31833)
    assert converted[1] == "mbar_per_hour"
    assert converted[2] == "group_pressurerate"

    # Test impossible conversions:
    with pytest.raises(KeyError):
        c.convert((20.01, "foo", "group_temperature"))
    with pytest.raises(KeyError):
        c.convert((None, "foo", "group_temperature"))
    with pytest.raises(KeyError):
        c.convert((20.01, "degree_C", "group_foo"))
    with pytest.raises(KeyError):
        c.convert((20.01, None, "group_temperature"))
    with pytest.raises(KeyError):
        c.convert((20.01, "degree_C", None))
    assert c.convert((20.01, None, None)) == (20.01, None, None)

    # Test mmHg
    value_t = (760.0, "mmHg", "group_pressure")
    converted = cm.convert(value_t)
    assert converted[0] == pytest.approx(1013.25)
    assert converted[1] == "mbar"
    assert converted[2] == "group_pressure"

    # Test mmHg_per_hour
    value_t = (2.9, "mmHg_per_hour", "group_pressurerate")
    converted = cm.convert(value_t)
    assert converted[0] == pytest.approx(3.866349)
    assert converted[1] == "mbar_per_hour"
    assert converted[2] == "group_pressurerate"

    # Test second/minute/hour/day
    value_t = (1440.0, "minute", "group_deltatime")
    assert weewx.units.convert(value_t, "second") == (86400.0, 'second', 'group_deltatime')
    assert weewx.units.convert(value_t, "hour") == (24.0, 'hour', 'group_deltatime')
    assert weewx.units.convert(value_t, "day") == (1.0, 'day', 'group_deltatime')


def testConvertDict():
    d_m = {'outTemp': 20.01,
           'barometer': 1002.3,
           'usUnits': weewx.METRIC}
    d_us = {'outTemp': 68.018,
            'barometer': 1002.3 * weewx.units.INHG_PER_MBAR,
            'usUnits': weewx.US}
    c = weewx.units.Converter()
    d_test = c.convertDict(d_m)
    assert d_test['outTemp'] == d_us['outTemp']
    assert d_test['barometer'] == d_us['barometer']
    assert 'usUnits' not in d_test

    # Go the other way:
    cm = weewx.units.Converter(weewx.units.MetricUnits)
    d_test = cm.convertDict(d_us)
    assert d_test['outTemp'] == d_m['outTemp']
    assert d_test['barometer'] == d_m['barometer']
    assert 'usUnits' not in d_test

    # Test impossible conversions:
    d_m['outTemp'] = (20.01, 'foo', 'group_temperature')
    with pytest.raises(KeyError):
        c.convert(d_m)
    d_m['outTemp'] = (20.01, 'degree_C', 'group_foo')
    with pytest.raises(KeyError):
        c.convert(d_m)


def testTargetUnits():
    c = weewx.units.Converter()
    assert c.getTargetUnit('outTemp') == ('degree_F', 'group_temperature')
    assert c.getTargetUnit('outTemp', 'max') == ('degree_F', 'group_temperature')
    assert c.getTargetUnit('outTemp', 'maxtime') == ('unix_epoch', 'group_time')
    assert c.getTargetUnit('outTemp', 'count') == ('count', 'group_count')
    assert c.getTargetUnit('outTemp', 'sum') == ('degree_F', 'group_temperature')
    assert c.getTargetUnit('wind', 'max') == ('mile_per_hour', 'group_speed')
    assert c.getTargetUnit('wind', 'vecdir') == ('degree_compass', 'group_direction')
        
def testFormatting():
    value_t = (68.01, "degree_F", "group_temperature")
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter)
    assert vh.string() == "68.0°F"
    assert vh.nolabel("T=%.3f") == "T=68.010"
    assert vh.formatted == "68.0"
    assert vh.raw == 68.01
    assert str(vh) == "68.0°F"
    assert str(vh.degree_F) == "68.0°F"
    assert str(vh.degree_C) == "20.0°C"

    # Using .format() interface
    assert vh.format() == "68.0°F"
    assert vh.format("T=%.3f", add_label=False) == "T=68.010"

    # Test None_string
    value_t = (None, "degree_F", "group_temperature")
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter)
    assert vh.format(None_string='foo') == 'foo'
    assert isinstance(vh.format(None_string='foo'), str)
    # This one cannot be done with ASCII codec:
    assert vh.format(None_string='unknown °F') == 'unknown °F'
    assert isinstance(vh.format(None_string='unknown °F'), str)


def testFormattingWithConversion():
    value_t = (68.01, "degree_F", "group_temperature")
    c_m = weewx.units.Converter(weewx.units.MetricUnits)
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter, converter=c_m)
    assert str(vh) == "20.0°C"
    assert str(vh.degree_F) == "68.0°F"
    assert str(vh.degree_C) == "20.0°C"
    # Try an impossible conversion:
    with pytest.raises(AttributeError):
        getattr(vh, 'meter')


def testExplicitConversion():
    value_t = (10.0, "meter_per_second", "group_speed")
    # Default converter converts to US Units
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter, converter=weewx.units.Converter())
    assert str(vh) == "22 mph"
    # Now explicitly convert to knots:
    assert str(vh.knot) == "19 knots"


def testNoneValue():
    value_t = (None, "degree_C", "group_temperature")
    converter = weewx.units.Converter()
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter, converter=converter)
    assert str(vh) == "   N/A"
    assert str(vh.degree_C) == "   N/A"


def testUnknownObsType():
    value_t = weewx.units.UnknownObsType('foobar')
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter)
    assert str(vh) == "?'foobar'?"
    assert not vh.exists()
    assert not vh.has_data()
    with pytest.raises(TypeError):
        vh.raw


def testElapsedTime():
    value_t = (2 * 86400 + 1 * 3600 + 5 * 60 + 12, "second", "group_deltatime")
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter, context='month')
    assert vh.long_form() == "2 days, 1 hour, 5 minutes"
    format_label = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, " \
                   "%(minute)d%(minute_label)s, %(second)d%(second_label)s"
    assert vh.long_form(format_label) == "2 days, 1 hour, 5 minutes, 12 seconds"
    # Now try a 'None' value:
    vh = weewx.units.ValueHelper((None, "second", "group_deltatime"), formatter=default_formatter)
    assert vh.string() == "   N/A"
    assert vh.long_form() == "   N/A"
    assert vh.long_form(None_string="Nothing") == "Nothing"


def test_JSON():
    value_t = (68.1283, "degree_F", "group_temperature")
    vh = weewx.units.ValueHelper(value_t, formatter=default_formatter)
    assert vh.json() == "68.1283"
    assert vh.round(2).json() == "68.13"
    # Test sequence:
    vh = weewx.units.ValueHelper(([68.1283, 65.201, None, 69.911],
                                  "degree_F", "group_temperature"),
                                 formatter=default_formatter)
    assert vh.json() == "[68.1283, 65.201, null, 69.911]"
    assert vh.round(2).json() == "[68.13, 65.2, null, 69.91]"
    # Test sequence of complex
    vh = weewx.units.ValueHelper(([complex(1.234, 2.3456), complex(9.1891, 2.764), None],
                                  "degree_F", "group_temperature"),
                                 formatter=default_formatter)
    assert vh.json() == "[[1.234, 2.3456], [9.1891, 2.764], null]"
    assert vh.round(2).json() == "[[1.23, 2.35], [9.19, 2.76], null]"
