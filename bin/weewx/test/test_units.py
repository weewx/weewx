# -*- coding: utf-8 -*-
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.units"""

import unittest
import operator

import weewx.units
from weewx.units import ValueTuple

class ValueTupleTest(unittest.TestCase):
    
    def testVT(self):
        a=ValueTuple(68.0, "degree_F", "group_temperature")
        b=ValueTuple(18.0, "degree_F", "group_temperature")
        c=ValueTuple(None, "degree_F", "group_temperature")
        d=ValueTuple(1020.0, "mbar", "group_pressure")

        self.assertEqual(a + b, ValueTuple(86.0, "degree_F", "group_temperature"))
        self.assertEqual(a - b, ValueTuple(50.0, "degree_F", "group_temperature"))
        self.assertRaises(TypeError, operator.add, a, c)
        self.assertRaises(TypeError, operator.add, a, d)
        
class ConverterTest(unittest.TestCase):
    
    def testConvert(self):
        #Test the US converter:
        c = weewx.units.Converter()
        value_t_m  = (20.01,  "degree_C", "group_temperature")
        value_t_us = (68.018, "degree_F", "group_temperature")
        self.assertEqual(c.convert(value_t_m), value_t_us)
        
        # Test converting a sequence:
        value_t_m_seq = ([10.0, 20.0, 30.0], "degree_C", "group_temperature")
        value_t_us_seq= ([50.0, 68.0, 86.0], "degree_F", "group_temperature")
        self.assertEqual(c.convert(value_t_m_seq), value_t_us_seq)

        # Now the metric converter:
        cm = weewx.units.Converter(weewx.units.MetricUnits)
        self.assertEqual(cm.convert(value_t_us), value_t_m)
        self.assertEqual(cm.convert(value_t_us_seq), value_t_m_seq)
        # Test a no-op conversion (US to US):
        self.assertEqual(c.convert(value_t_us), value_t_us)
        
        # Test impossible conversions:
        self.assertRaises(KeyError, c.convert, (20.01, "foo", "group_temperature"))
        self.assertRaises(KeyError, c.convert, (None, "foo", "group_temperature"))
        self.assertRaises(KeyError, c.convert, (20.01, "degree_C", "group_foo"))
        self.assertRaises(KeyError, c.convert, (20.01, None, "group_temperature"))
        self.assertRaises(KeyError, c.convert, (20.01, "degree_C", None))
        self.assertEqual(c.convert((20.01, None, None)), (20.01, None, None))
        
        # Test mmHg
        value_t = (760.0, "mmHg", "group_pressure")
        converted = cm.convert(value_t)
        # Do a formatted comparison to compensate for small rounding errors: 
        self.assertEqual(("%.2f" % converted[0],)+converted[1:3], ("1013.25", "mbar", "group_pressure"))
        
        # Test second/minute/hour/day
        value_t = (1440.0, "minute", "group_deltatime")
        self.assertEqual(weewx.units.convert(value_t, "second"), (86400.0, 'second', 'group_deltatime'))
        self.assertEqual(weewx.units.convert(value_t, "hour"),   (24.0, 'hour', 'group_deltatime'))
        self.assertEqual(weewx.units.convert(value_t, "day"),    (1.0, 'day', 'group_deltatime'))
        
    def testConvertDict(self):
        d_m =  {'outTemp'   : 20.01,
                'barometer' : 1002.3,
                'usUnits'   : weewx.METRIC}
        d_us = {'outTemp'   : 68.018,
                'barometer' : 1002.3 * weewx.units.INHG_PER_MBAR,
                'usUnits'   : weewx.US}
        c = weewx.units.Converter()
        d_test = c.convertDict(d_m)
        self.assertEqual(d_test['outTemp'],   d_us['outTemp'])
        self.assertEqual(d_test['barometer'], d_us['barometer'])
        self.assertFalse(d_test.has_key('usUnits'))

        # Go the other way:
        cm = weewx.units.Converter(weewx.units.MetricUnits)
        d_test = cm.convertDict(d_us)
        self.assertEqual(d_test['outTemp'],   d_m['outTemp'])
        self.assertEqual(d_test['barometer'], d_m['barometer'])
        self.assertFalse(d_test.has_key('usUnits'))
        
        # Test impossible conversions:
        d_m['outTemp'] = (20.01, 'foo', 'group_temperature')
        self.assertRaises(KeyError, c.convert, d_m)
        d_m['outTemp'] = (20.01, 'degree_C', 'group_foo')
        self.assertRaises(KeyError, c.convert, d_m)
        
    def testTargetUnits(self):
        c = weewx.units.Converter()
        self.assertEqual(c.getTargetUnit('outTemp'),            ('degree_F', 'group_temperature'))
        self.assertEqual(c.getTargetUnit('outTemp', 'max'),     ('degree_F', 'group_temperature'))
        self.assertEqual(c.getTargetUnit('outTemp', 'maxtime'), ('unix_epoch', 'group_time'))
        self.assertEqual(c.getTargetUnit('outTemp', 'count'),   ('count', 'group_count'))
        self.assertEqual(c.getTargetUnit('outTemp', 'sum'),     ('degree_F', 'group_temperature'))
        self.assertEqual(c.getTargetUnit('wind', 'max'),        ('mile_per_hour', 'group_speed'))
        self.assertEqual(c.getTargetUnit('wind', 'vecdir'),     ('degree_compass', 'group_direction'))
        
class ValueHelperTest(unittest.TestCase):
    
    def testFormatting(self):
        value_t = (68.01, "degree_F", "group_temperature")
        vh = weewx.units.ValueHelper(value_t)
        self.assertEqual(vh.string(), "68.0°F")
        self.assertEqual(vh.nolabel("T=%.3f"), "T=68.010")
        self.assertEqual(vh.formatted, "68.0")
        self.assertEqual(vh.raw, 68.01)
        self.assertEqual(str(vh), "68.0°F")
        self.assertEqual(str(vh.degree_F), "68.0°F")
        self.assertEqual(str(vh.degree_C), "20.0°C")
        
    def testFormattingWithConversion(self):
        value_t = (68.01, "degree_F", "group_temperature")
        c_m = weewx.units.Converter(weewx.units.MetricUnits)
        vh = weewx.units.ValueHelper(value_t, converter=c_m)
        self.assertEqual(str(vh), "20.0°C")
        self.assertEqual(str(vh.degree_F), "68.0°F")
        self.assertEqual(str(vh.degree_C), "20.0°C")
        # Try an impossible conversion:
        self.assertRaises(AttributeError, getattr, vh, 'meter')

    def testExplicitConversion(self):
        value_t = (10.0, "meter_per_second", "group_speed")
        vh = weewx.units.ValueHelper(value_t)
        self.assertEqual(str(vh), "22 mph")
        self.assertEqual(str(vh.knot), "19 knots")

    def testNoneValue(self):
        value_t = (None, "degree_C", "group_temperature")
        converter = weewx.units.Converter()
        vh = weewx.units.ValueHelper(value_t, converter=converter)
        self.assertEqual(str(vh), "   N/A")
        self.assertEqual(str(vh.degree_C), "   N/A")
        
    def testElapsedTime(self):
        value_t = (2*86400 + 1*3600 + 5*60 + 12, "second", "group_deltatime")
        vh = weewx.units.ValueHelper(value_t)
        self.assertEqual(vh.string(), "2 days, 1 hour, 5 minutes")
        format_label = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s, %(second)d%(second_label)s"
        self.assertEqual(vh.format(format_label), "2 days, 1 hour, 5 minutes, 12 seconds")
        # Now try a 'None' value:
        vh = weewx.units.ValueHelper((None, "second", "group_deltatime"))
        self.assertEqual(vh.string(), "   N/A")
        
if __name__ == '__main__':
    unittest.main()
    
