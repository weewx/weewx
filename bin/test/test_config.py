#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
from __future__ import with_statement

import StringIO
import unittest
import tempfile
import os
import os.path
import sys

import configobj

try:
    from mock import patch
    import __builtin__  # @UnusedImport
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

    def test_find_file(self):
        # Test the utility function config_util.find_file()

        with tempfile.NamedTemporaryFile() as test_fd:
            # Get info about the temp file:
            full_path = test_fd.name
            dir_path = os.path.dirname(full_path)
            filename = os.path.basename(full_path)
            # Find the file with an explicit path:
            result = config_util.find_file(full_path)
            self.assertEqual(result, full_path)
            # Find the file with an explicit, but wrong, path:
            self.assertRaises(IOError, config_util.find_file, full_path + "foo")
            # Find the file using the "args" optional list:
            result = config_util.find_file(None, [full_path])
            self.assertEqual(result, full_path)
            # Find the file using the "args" optional list, but with a wrong name:
            self.assertRaises(IOError, config_util.find_file,
                              None, [full_path + "foo"])
            # Now search a list of directory locations given a file name:
            result = config_util.find_file(None, file_name=filename, locations=['/usr/bin', dir_path])
            self.assertEqual(result, full_path)
            # Do the same, but with a non-existent file name:
            self.assertRaises(IOError, config_util.find_file,
                              None, file_name=filename + "foo", locations=['/usr/bin', dir_path])

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

        def test_prompt_for_info(self):

            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            try:

                # Test a normal input
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'us']):
                    stn_info = config_util.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a default input
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '', '45.0', '180.0', 'us']):
                    stn_info = config_util.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['0', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for an out-of-bounds latitude
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '95.0', '45.0', '180.0', 'us']):
                    stn_info = config_util.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a bad length unit type
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, foo', '100,meter', '45.0', '180.0', 'us']):
                    stn_info = config_util.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a bad display unit
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'foo', 'us']):
                    stn_info = config_util.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})
            finally:
                # Restore stdout:
                sys.stdout = save_stdout

    if have_mock:
        def test_prompt_with_options(self):
            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            try:
                with patch('__builtin__.raw_input', return_value="yes"):
                    response = config_util.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('__builtin__.raw_input', return_value="no"):
                    response = config_util.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "no")
                with patch('__builtin__.raw_input', return_value=""):
                    response = config_util.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('__builtin__.raw_input', side_effect=["make me", "no"]):
                    response = config_util.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "no")
            finally:
                # Restore stdout:
                sys.stdout = save_stdout

    if have_mock:
        def test_prompt_with_limits(self):
            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            try:
                with patch('__builtin__.raw_input', return_value="45"):
                    response = config_util.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "45")
                with patch('__builtin__.raw_input', return_value=""):
                    response = config_util.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "0.0")
                with patch('__builtin__.raw_input', side_effect=["-120", "-45"]):
                    response = config_util.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "-45")
            finally:
                # Restore stdout:
                sys.stdout = save_stdout

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
