#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""

import StringIO
import unittest

import configobj

try:
    from mock import patch
    import __builtin__
    have_mock = True
except ImportError:
    print "Module 'mock' not installed. Testing will be restricted."
    have_mock = False

import config_util

x_str = """
        [section_a]
          a = 1
        [section_b]
          b = 2
        [section_c]
          c = 3
        [section_d]
          d = 4"""

y_str = """
        [section_a]
          a = 11
        [section_b]
          b = 12
        [section_e]
          c = 15"""

class ConfigTest(unittest.TestCase):

    def test_utilities(self):
        global x_str, y_str

        xio = StringIO.StringIO(x_str)
        x_dict = configobj.ConfigObj(xio)
        config_util.reorder_sections(x_dict, 'section_c', 'section_b')
        self.assertEqual("{'section_a': {'a': '1'}, 'section_c': {'c': '3'}, "
                         "'section_b': {'b': '2'}, 'section_d': {'d': '4'}}", str(x_dict))

        xio.seek(0)
        x_dict = configobj.ConfigObj(xio)
        config_util.reorder_sections(x_dict, 'section_c', 'section_b', after=True)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, "
                         "'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))

        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        config_util.conditional_merge(x_dict, y_dict)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, 'section_c': {'c': '3'}, "
                         "'section_d': {'d': '4'}, 'section_e': {'c': '15'}}", str(x_dict))


        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        config_util.remove_and_prune(x_dict, y_dict)
        self.assertEqual("{'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))

    if have_mock:

        # Test a normal input
        @patch('__builtin__.raw_input', side_effect=['Anytown', '100, meter', '45.0', '180.0', 'us'])
        def test_prompt1(self, input):
            stn_info = config_util.prompt_for_info()
            self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                        'latitude': '45.0',
                                        'location': 'Anytown',
                                        'longitude': '180.0',
                                        'units': 'us'})

        # Test for a default input
        @patch('__builtin__.raw_input', side_effect=['Anytown', '', '45.0', '180.0', 'us'])
        def test_prompt2(self, input):
            stn_info = config_util.prompt_for_info()
            self.assertEqual(stn_info, {'altitude': ['0', 'meter'],
                                        'latitude': '45.0',
                                        'location': 'Anytown',
                                        'longitude': '180.0',
                                        'units': 'us'})

        # Test for an out-of-bounds latitude
        @patch('__builtin__.raw_input', side_effect=['Anytown', '100, meter', '95.0', '45.0', '180.0', 'us'])
        def test_prompt3(self, input):
            stn_info = config_util.prompt_for_info()
            self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                        'latitude': '45.0',
                                        'location': 'Anytown',
                                        'longitude': '180.0',
                                        'units': 'us'})

        # Test for a bad length unit type
        @patch('__builtin__.raw_input', side_effect=['Anytown', '100, foo', '100,meter', '45.0', '180.0', 'us'])
        def test_prompt4(self, input):
            stn_info = config_util.prompt_for_info()
            self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                        'latitude': '45.0',
                                        'location': 'Anytown',
                                        'longitude': '180.0',
                                        'units': 'us'})

        # Test for a bad display unit
        @patch('__builtin__.raw_input', side_effect=['Anytown', '100, meter', '45.0', '180.0', 'foo', 'us'])
        def test_prompt5(self, input):
            stn_info = config_util.prompt_for_info()
            self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                        'latitude': '45.0',
                                        'location': 'Anytown',
                                        'longitude': '180.0',
                                        'units': 'us'})

    def test_upgrade_v27(self):

        # Start with the Version 2.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx20.conf')

        # Upgrade the V2.0 configuration dictionary to V2.7:
        config_util.update_to_v27(config_dict)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)

        out_str.seek(0)
        fd_expected = open('expected/weewx27_expected.conf')
        N = 0
        for expected in fd_expected:
            actual = out_str.readline()
            N += 1
            self.assertEqual(actual, expected, "[%d] '%s' vs '%s'" % (N, actual, expected))

        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '')

    def test_upgrade_30(self):

        # Start with the Version 2.7 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx27.conf')

        # Upgrade to V3.0
        config_util.update_to_v30(config_dict)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)

        out_str.seek(0)
        fd_expected = open('expected/weewx30_expected.conf')
        N = 0
        for expected in fd_expected:
            actual = out_str.readline()
            N += 1
            self.assertEqual(actual, expected, "[%d] '%s' vs '%s'" % (N, actual, expected))

        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '', "Unexpected additional lines")

    def test_merge(self):

        # Start with a typical V2.0 user file:
        config_dict = configobj.ConfigObj('weewx_user.conf')

        # The V3.1 config file becomes the template:
        template = configobj.ConfigObj('weewx31.conf')

        # First update, then merge:
        config_util.update_config(config_dict)
        config_util.merge_config(config_dict, template)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)

        out_str.seek(0)
        fd_expected = open('expected/weewx_user_expected.conf')
        N = 0
        for expected in fd_expected:
            actual = out_str.readline()
            N += 1
            self.assertEqual(actual, expected, "[%d] '%s' vs '%s'" % (N, actual, expected))

        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '')

unittest.main()
