#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
from __future__ import with_statement
from __future__ import absolute_import
from __future__ import print_function

import distutils.dir_util
import io
import os.path
import shutil
import sys
import tempfile
import unittest

import configobj
from six.moves import StringIO

import weecfg.extension
import weeutil.config
import weeutil.weeutil

try:
    try:
        # Python 2 requires PyPi module mock
        from mock import patch
    except ImportError:
        # Python 3 comes with it:
        from unittest.mock import patch
    have_mock = True
except ImportError:
    print("Module 'mock' not installed. Testing will be restricted.")
    have_mock = False

TMPDIR = '/var/tmp/weewx_test'

# Redirect the import of setup:
sys.modules['setup'] = weecfg.extension


def check_fileend(out_str):
    """Early versions of ConfigObj did not terminate files with a newline.
    This function will add one if it's missing"""
    if configobj.__version__ <= '4.4.0':
        out_str.seek(-1, os.SEEK_END)
        x = out_str.read(1)
        if x != '\n':
            out_str.write('\n')


# Change directory so we can find things dependent on the location of
# this file, such as config files and expected values:
this_file = os.path.join(os.getcwd(), __file__)
this_dir = os.path.abspath(os.path.dirname(this_file))
os.chdir(this_dir)

X_STR = """
        [section_a]
          a = 1
        [section_b]
          b = 2
        [section_c]
          c = 3
        [section_d]
          d = 4"""

Y_STR = """
        [section_a]
          a = 11
        [section_b]
          b = 12
        [section_e]
          c = 15"""

current_config_dict_path = "../../../weewx.conf"


class LineTest(unittest.TestCase):

    def _check_against_expected(self, config_dict, expected):
        """Check a ConfigObj against an expected version

        config_dict: The ConfigObj that is to be checked

        expected: The name of a file holding the expected version
        """
        # Writing a ConfigObj to a file-like object always writes in bytes,
        # so we cannot write to a StringIO (which accepts only Unicode under Python 3).
        # Use a BytesIO object instead, which accepts byte strings.
        with io.BytesIO() as fd_actual:
            config_dict.write(fd_actual)
            check_fileend(fd_actual)
            fd_actual.seek(0)

            # When we read the BytesIO object back in, the results will be in byte strings.
            # To compare apples-to-apples, we need to open the file with expected
            # strings in binary, so when we read it, we get byte-strings:
            with open(expected, 'rb') as fd_expected:
                N = 0
                for expected in fd_expected:
                    actual = fd_actual.readline()
                    N += 1
                    self.assertEqual(actual.strip(), expected.strip(),
                                     "[%d] '%s' vs '%s'" % (N, actual, expected))

                # Make sure there are no extra lines in the updated config:
                more = fd_actual.readline()
                self.assertEqual(more, b'')


class ConfigTest(LineTest):

    def test_find_file(self):
        # Test the utility function weecfg.find_file()

        with tempfile.NamedTemporaryFile() as test_fd:
            # Get info about the temp file:
            full_path = test_fd.name
            dir_path = os.path.dirname(full_path)
            filename = os.path.basename(full_path)
            # Find the file with an explicit path:
            result = weecfg.find_file(full_path)
            self.assertEqual(result, full_path)
            # Find the file with an explicit, but wrong, path:
            self.assertRaises(IOError, weecfg.find_file, full_path + "foo")
            # Find the file using the "args" optional list:
            result = weecfg.find_file(None, [full_path])
            self.assertEqual(result, full_path)
            # Find the file using the "args" optional list, but with a wrong name:
            self.assertRaises(IOError, weecfg.find_file,
                              None, [full_path + "foo"])
            # Now search a list of directory locations given a file name:
            result = weecfg.find_file(None, file_name=filename, locations=['/usr/bin', dir_path])
            self.assertEqual(result, full_path)
            # Do the same, but with a non-existent file name:
            self.assertRaises(IOError, weecfg.find_file,
                              None, file_name=filename + "foo", locations=['/usr/bin', dir_path])

    def test_reorder_before(self):
        global X_STR

        xio = StringIO(X_STR)
        x_dict = configobj.ConfigObj(xio, encoding='utf-8')
        weecfg.reorder_sections(x_dict, 'section_c', 'section_b')
        x_dict_str = convert_to_str(x_dict)
        self.assertEqual(x_dict_str, u"""
[section_a]
        a = 1
[section_c]
        c = 3
[section_b]
        b = 2
[section_d]
        d = 4
""")

    def test_reorder_after(self):
        global X_STR

        xio = StringIO(X_STR)
        x_dict = configobj.ConfigObj(xio, encoding='utf-8')
        weecfg.reorder_sections(x_dict, 'section_c', 'section_b', after=True)
        x_dict_str = convert_to_str(x_dict)
        self.assertEqual(x_dict_str, u"""
[section_a]
        a = 1
[section_b]
        b = 2
[section_c]
        c = 3
[section_d]
        d = 4
""")

    def test_conditional_merge(self):
        global X_STR, Y_STR

        xio = StringIO(X_STR)
        yio = StringIO(Y_STR)
        x_dict = configobj.ConfigObj(xio, encoding='utf-8')
        y_dict = configobj.ConfigObj(yio, encoding='utf-8')
        weeutil.config.conditional_merge(x_dict, y_dict)
        x_dict_str = convert_to_str(x_dict)
        self.assertEqual(x_dict_str, u"""
[section_a]
        a = 1
[section_b]
        b = 2
[section_c]
        c = 3
[section_d]
        d = 4
[section_e]
        c = 15
""")

    def test_remove_and_prune(self):
        global X_STR, Y_STR

        xio = StringIO(X_STR)
        yio = StringIO(Y_STR)
        x_dict = configobj.ConfigObj(xio, encoding='utf-8')
        y_dict = configobj.ConfigObj(yio, encoding='utf-8')
        weecfg.remove_and_prune(x_dict, y_dict)
        x_dict_str = convert_to_str(x_dict)
        self.assertEqual(x_dict_str, u"""
[section_c]
        c = 3
[section_d]
        d = 4
""")

    def test_reorder_scalars(self):
        test_list = ['a', 'b', 'd', 'c']
        weecfg.reorder_scalars(test_list, 'c', 'd')
        self.assertEqual(test_list, ['a', 'b', 'c', 'd'])

        test_list = ['a', 'b', 'c', 'd']
        weecfg.reorder_scalars(test_list, 'c', 'e')
        self.assertEqual(test_list, ['a', 'b', 'd', 'c'])

        test_list = ['a', 'b', 'd']
        weecfg.reorder_scalars(test_list, 'x', 'd')
        self.assertEqual(test_list, ['a', 'b', 'd'])

    if have_mock:
        def test_prompt_for_info(self):
            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            with open(os.devnull, 'w') as sys.stdout:
                # Test a normal input
                with patch('weecfg.input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'y',
                                        'weewx.com', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'register_this_station': 'true',
                                                'station_url': 'weewx.com',
                                                'unit_system': 'us',
                                                })

                # Test for a default input
                with patch('weecfg.input',
                           side_effect=['Anytown', '', '', '', '', '']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['0', 'meter'],
                                                'latitude': '0.000',
                                                'location': 'Anytown',
                                                'longitude': '0.000',
                                                'register_this_station': 'false',
                                                'unit_system': 'metricwx',
                                                })

                # Test for an out-of-bounds latitude with retry
                with patch('weecfg.input',
                           side_effect=['Anytown', '100, meter', '95.0', '45.0', '180.0', 'n',
                                        'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'register_this_station': 'false',
                                                'unit_system': 'us'})

                # Test for a bad length unit type with retry
                with patch('weecfg.input',
                           side_effect=['Anytown', '100, foo', '100,meter', '45.0', '180.0',
                                        'n', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'register_this_station': 'false',
                                                'unit_system': 'us'})

                # Test for a bad display unit with retry
                with patch('weecfg.input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'n', 'foo',
                                        'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'register_this_station': 'false',
                                                'unit_system': 'us'})
            # Restore stdout:
            sys.stdout = save_stdout

    if have_mock:
        def test_prompt_with_options(self):
            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            with open(os.devnull, 'w') as sys.stdout:
                with patch('weecfg.input', return_value="yes"):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('weecfg.input', return_value="no"):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "no")
                with patch('weecfg.input', return_value=""):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('weecfg.input', side_effect=["make me", "no"]):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "no")
            # Restore stdout:
            sys.stdout = save_stdout

    if have_mock:
        def test_prompt_with_limits(self):
            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            with open(os.devnull, 'w') as sys.stdout:
                with patch('weecfg.input', return_value="45"):
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "45")
                with patch('weecfg.input', return_value=""):
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "0.0")
                with patch('weecfg.input', side_effect=["-120", "-45"]):
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "-45")
            # Restore stdout:
            sys.stdout = save_stdout

    def test_upgrade_v25(self):

        # Start with the Version 2.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx20.conf', encoding='utf-8')

        # Upgrade the V2.0 configuration dictionary to V2.5:
        weecfg.update_to_v25(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx25_expected.conf')

    def test_upgrade_v26(self):

        # Start with the Version 2.5 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx25.conf', encoding='utf-8')

        # Upgrade the V2.5 configuration dictionary to V2.6:
        weecfg.update_to_v26(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx26_expected.conf')

    def test_upgrade_v30(self):

        # Start with the Version 2.7 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx27.conf', encoding='utf-8')

        # Upgrade the V2.7 configuration dictionary to V3.0:
        weecfg.update_to_v30(config_dict)

        # with open('expected/weewx30_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx30_expected.conf')

    def test_upgrade_v32(self):

        # Start with the Version 3.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx30.conf', encoding='utf-8')

        # Upgrade the V3.0 configuration dictionary to V3.2:
        weecfg.update_to_v32(config_dict)

        # with open('expected/weewx32_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx32_expected.conf')

    def test_upgrade_v36(self):

        # Start with the Version 3.2 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx32.conf', encoding='utf-8')

        # Upgrade the V3.2 configuration dictionary to V3.6:
        weecfg.update_to_v36(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx36_expected.conf')

    def test_upgrade_v39(self):

        # Start with the Version 3.8 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx38.conf', encoding='utf-8')

        # Upgrade the V3.8 configuration dictionary to V3.9:
        weecfg.update_to_v39(config_dict)

        # with open('expected/weewx39_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx39_expected.conf')

    def test_upgrade_v40(self):
        """Test an upgrade of the stock v3.9 weewx.conf to V4.0"""

        # Start with the Version 3.9 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx39.conf', encoding='utf-8')

        # Upgrade the V3.9 configuration dictionary to V4.0:
        weecfg.update_to_v40(config_dict)

        # with open('expected/weewx40_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx40_expected.conf')

    def test_upgrade_v42(self):
        """Test an upgrade of the stock v4.1 weewx.conf to V4.2"""

        # Start with the Version 4.1 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx41.conf', encoding='utf-8')

        # Upgrade the V4.1 configuration dictionary to V4.2:
        weecfg.update_to_v42(config_dict)

        # with open('expected/weewx42_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx42_expected.conf')

    def test_upgrade_v43(self):
        """Test an upgrade of the stock v4.1 weewx.conf to V4.2"""

        # Start with the Version 4.1 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx42.conf', encoding='utf-8')

        # Upgrade the V4.2 configuration dictionary to V4.3:
        weecfg.update_to_v43(config_dict)

        # with open('expected/weewx43_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx43_expected.conf')

    def test_merge(self):
        """Test an upgrade against a typical user's configuration file"""

        # Start with a typical V2.0 user file:
        config_dict = configobj.ConfigObj('weewx20_user.conf', encoding='utf-8')

        # The current config file becomes the template:
        template = configobj.ConfigObj(current_config_dict_path, encoding='utf-8')

        # First update, then merge:
        weecfg.update_and_merge(config_dict, template)

        # with open('expected/weewx43_user_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx43_user_expected.conf')

    def test_driver_info(self):
        """Test the discovery and listing of drivers."""
        driver_info_dict = weecfg.get_driver_infos()
        self.assertEqual(driver_info_dict['weewx.drivers.ws1']['module_name'], 'weewx.drivers.ws1')
        # Test for the driver name
        self.assertEqual(driver_info_dict['weewx.drivers.ws1']['driver_name'], 'WS1')
        # Cannot really test for version numbers of all drivers. Pick one. Import it...
        import weewx.drivers.ws1
        # ... and see if the version number matches
        self.assertEqual(driver_info_dict['weewx.drivers.ws1']['version'],
                         weewx.drivers.ws1.DRIVER_VERSION)
        del weewx.drivers.ws1

    def test_modify_config(self):

        # Use the current weewx.conf
        config_dict = configobj.ConfigObj(current_config_dict_path, encoding='utf-8')

        stn_info = weecfg.get_station_info_from_config(config_dict)

        self.assertEqual(stn_info,
                         {'station_type': 'unspecified', 'altitude': ['700', 'foot'],
                          'longitude': '0.00', 'unit_system': 'us', 'location': 'My Little Town, Oregon',
                          'latitude': '0.00', 'register_this_station': 'false', 'lang': 'en'})

        # Modify the station info, to reflect a hardware choice
        stn_info['station_type'] = 'Vantage'
        stn_info['driver'] = 'weewx.drivers.vantage'

        # Now modify the config_dict.
        weecfg.modify_config(config_dict, stn_info, None)

        # Make sure the driver stanza got injected correctly
        import weewx.drivers.vantage
        vcf = weewx.drivers.vantage.VantageConfEditor()
        default_config = configobj.ConfigObj(StringIO(vcf.default_stanza), encoding='utf-8')

        self.assertEqual(config_dict['Vantage'], default_config['Vantage'])


class ExtensionUtilityTest(unittest.TestCase):
    """Tests of utility functions used by the extension installer."""

    INSTALLED_NAMES = ['/var/tmp/pmon/bin/user/pmon.py',
                       '/var/tmp/pmon/changelog',
                       '/var/tmp/pmon/install.py',
                       '/var/tmp/pmon/readme.txt',
                       '/var/tmp/pmon/skins/pmon/index.html.tmpl',
                       '/var/tmp/pmon/skins/pmon/skin.conf']

    def setUp(self):
        shutil.rmtree('/var/tmp/pmon', ignore_errors=True)

    def tearDown(self):
        shutil.rmtree('/var/tmp/pmon', ignore_errors=True)

    def test_tar_extract(self):
        shutil.rmtree('/var/tmp/pmon', ignore_errors=True)
        member_names = weecfg.extract_tar('./pmon.tar', '/var/tmp')
        self.assertEqual(member_names, ['pmon',
                                        'pmon/readme.txt',
                                        'pmon/skins',
                                        'pmon/skins/pmon',
                                        'pmon/skins/pmon/index.html.tmpl',
                                        'pmon/skins/pmon/skin.conf',
                                        'pmon/changelog',
                                        'pmon/install.py',
                                        'pmon/bin',
                                        'pmon/bin/user',
                                        'pmon/bin/user/pmon.py'])
        actual_files = []
        for direc in os.walk('/var/tmp/pmon'):
            for filename in direc[2]:
                actual_files.append(os.path.join(direc[0], filename))
        self.assertEqual(sorted(actual_files), self.INSTALLED_NAMES)

    def test_tgz_extract(self):
        shutil.rmtree('/var/tmp/pmon', ignore_errors=True)
        member_names = weecfg.extract_tar('./pmon.tgz', '/var/tmp')
        self.assertEqual(member_names, ['pmon',
                                        'pmon/bin',
                                        'pmon/bin/user',
                                        'pmon/bin/user/pmon.py',
                                        'pmon/changelog',
                                        'pmon/install.py',
                                        'pmon/readme.txt',
                                        'pmon/skins',
                                        'pmon/skins/pmon',
                                        'pmon/skins/pmon/index.html.tmpl',
                                        'pmon/skins/pmon/skin.conf'])
        actual_files = []
        for direc in os.walk('/var/tmp/pmon'):
            for filename in direc[2]:
                actual_files.append(os.path.join(direc[0], filename))
        self.assertEqual(sorted(actual_files), self.INSTALLED_NAMES)

    def test_zip_extract(self):
        shutil.rmtree('/var/tmp/pmon', ignore_errors=True)
        member_names = weecfg.extract_zip('./pmon.zip', '/var/tmp')
        self.assertEqual(member_names, ['pmon/',
                                        'pmon/bin/',
                                        'pmon/bin/user/',
                                        'pmon/bin/user/pmon.py',
                                        'pmon/changelog',
                                        'pmon/install.py',
                                        'pmon/readme.txt',
                                        'pmon/skins/',
                                        'pmon/skins/pmon/',
                                        'pmon/skins/pmon/index.html.tmpl',
                                        'pmon/skins/pmon/skin.conf'])
        actual_files = []
        for direc in os.walk('/var/tmp/pmon'):
            for filename in direc[2]:
                actual_files.append(os.path.join(direc[0], filename))
        self.assertEqual(sorted(actual_files), self.INSTALLED_NAMES)


class ExtensionInstallTest(unittest.TestCase):
    """Tests of the extension installer."""

    def setUp(self):
        # We're going to install a "mini-weewx" in this temporary directory:
        self.weewx_root = '/var/tmp/wee_test'
        # NB: If we use distutils to copy trees, we have to use it to remove
        # them because it caches directories it has created.
        try:
            distutils.dir_util.remove_tree(self.weewx_root)
        except OSError:
            pass

        # Now build a new configuration
        self.user_dir = os.path.join(self.weewx_root, 'bin', 'user')
        self.skin_dir = os.path.join(self.weewx_root, 'skins')
        self.bin_dir = os.path.join(self.weewx_root, 'bin')
        distutils.dir_util.copy_tree('../../../bin/user', self.user_dir)
        distutils.dir_util.copy_tree('../../../skins/Standard',
                                     os.path.join(self.skin_dir, 'Standard'))
        shutil.copy(current_config_dict_path, self.weewx_root)

    def tearDown(self):
        "Remove any installed test configuration"
        try:
            distutils.dir_util.remove_tree(self.weewx_root)
        except OSError:
            pass

    def test_install(self):
        # Find and read the test configuration
        config_path = os.path.join(self.weewx_root, 'weewx.conf')
        config_dict = configobj.ConfigObj(config_path, encoding='utf-8')

        # Note that the actual location of the "mini-weewx" is over in /var/tmp
        config_dict['WEEWX_ROOT'] = self.weewx_root

        # Initialize the install engine. Note that we want the bin root in /var/tmp, not here:
        engine = weecfg.extension.ExtensionEngine(config_path, config_dict,
                                                  bin_root=self.bin_dir,
                                                  logger=weecfg.Logger(verbosity=-1))

        # Make sure the root dictionary got calculated correctly:
        self.assertEqual(engine.root_dict, {'WEEWX_ROOT': '/var/tmp/wee_test',
                                            'BIN_ROOT': '/var/tmp/wee_test/bin',
                                            'USER_ROOT': '/var/tmp/wee_test/bin/user',
                                            'EXT_ROOT': '/var/tmp/wee_test/bin/user/installer',
                                            'SKIN_ROOT': '/var/tmp/wee_test/skins',
                                            'CONFIG_ROOT': '/var/tmp/wee_test'})

        # Now install the extension...
        engine.install_extension('./pmon.tgz')

        # ... and assert that it got installed correctly
        self.assertTrue(os.path.isfile(os.path.join(self.user_dir, 'pmon.py')))
        self.assertTrue(
            os.path.isfile(os.path.join(self.user_dir, 'installer', 'pmon', 'install.py')))
        self.assertTrue(os.path.isdir(os.path.join(self.skin_dir, 'pmon')))
        self.assertTrue(os.path.isfile(os.path.join(self.skin_dir, 'pmon', 'index.html.tmpl')))
        self.assertTrue(os.path.isfile(os.path.join(self.skin_dir, 'pmon', 'skin.conf')))

        # Get, then check the new config dict:
        test_dict = configobj.ConfigObj(config_path, encoding='utf-8')
        self.assertEqual(test_dict['StdReport']['pmon'],
                         {'HTML_ROOT': 'public_html/pmon', 'skin': 'pmon'})
        self.assertEqual(test_dict['Databases']['pmon_sqlite'],
                         {'database_name': 'pmon.sdb',
                          'database_type': 'SQLite'})
        self.assertEqual(test_dict['DataBindings']['pmon_binding'],
                         {'manager': 'weewx.manager.DaySummaryManager',
                          'schema': 'user.pmon.schema',
                          'table_name': 'archive',
                          'database': 'pmon_sqlite'})
        self.assertEqual(test_dict['ProcessMonitor'],
                         {'data_binding': 'pmon_binding',
                          'process': 'weewxd'})

        self.assertTrue(
            'user.pmon.ProcessMonitor' in test_dict['Engine']['Services']['process_services'])

    def test_uninstall(self):
        # Find and read the test configuration
        config_path = os.path.join(self.weewx_root, 'weewx.conf')
        config_dict = configobj.ConfigObj(config_path, encoding='utf-8')

        # Note that the actual location of the "mini-weewx" is over in /var/tmp
        config_dict['WEEWX_ROOT'] = self.weewx_root

        # Initialize the install engine. Note that we want the bin root in /var/tmp, not here:
        engine = weecfg.extension.ExtensionEngine(config_path, config_dict,
                                                  bin_root=self.bin_dir,
                                                  logger=weecfg.Logger(verbosity=-1))
        # First install...
        engine.install_extension('./pmon.tgz')
        # ... then uninstall it:
        engine.uninstall_extension('pmon')

        # Assert that everything got removed correctly:
        self.assertTrue(not os.path.exists(os.path.join(self.user_dir, 'pmon.py')))
        self.assertTrue(
            not os.path.exists(os.path.join(self.user_dir, 'installer', 'pmon', 'install.py')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon', 'index.html.tmpl')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon', 'skin.conf')))

        # Get the modified config dict, which had the extension removed from it
        test_dict = configobj.ConfigObj(config_path, encoding='utf-8')

        # It should be the same as our original:
        self.assertEqual(test_dict, config_dict)


# ############# Utilities #################

def convert_to_str(x_dict):
    """Convert a ConfigObj to a unicode string, using its write function."""
    with io.BytesIO() as s:
        x_dict.write(s)
        s.seek(0)
        x = s.read().decode()
    return x


if __name__ == "__main__":
    unittest.main()
