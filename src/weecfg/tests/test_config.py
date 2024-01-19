#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""
import contextlib
import io
import os.path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import configobj

import weecfg.extension
import weecfg.update_config
import weeutil.config
import weeutil.weeutil
from weeutil.printer import Printer

# Redirect the import of setup:
sys.modules['setup'] = weecfg.extension

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

import weewx_data

RESOURCE_DIR = os.path.dirname(weewx_data.__file__)
current_config_dict_path = os.path.join(RESOURCE_DIR, 'weewx.conf')


def suppress_stdout(func):
    def wrapper(*args, **kwargs):
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                return func(*args, **kwargs)

    return wrapper


class ConfigTest(unittest.TestCase):

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
            with self.assertRaises(IOError):
                weecfg.find_file(full_path + "foo")
            # Find the file using the "args" optional list:
            result = weecfg.find_file(None, [full_path])
            self.assertEqual(result, full_path)
            # Find the file using the "args" optional list, but with a wrong name:
            with self.assertRaises(IOError):
                weecfg.find_file(None, [full_path + "foo"])
            # Now search a list of directory locations given a file name:
            result = weecfg.find_file(None, file_name=filename, locations=['/usr/bin', dir_path])
            self.assertEqual(result, full_path)
            # Do the same, but with a non-existent file name:
            with self.assertRaises(IOError):
                weecfg.find_file(None, file_name=filename + "foo",
                                 locations=['/usr/bin', dir_path])

    def test_reorder_before(self):
        global X_STR

        xio = io.StringIO(X_STR)
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

        xio = io.StringIO(X_STR)
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

        xio = io.StringIO(X_STR)
        yio = io.StringIO(Y_STR)
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

        xio = io.StringIO(X_STR)
        yio = io.StringIO(Y_STR)
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

    @suppress_stdout
    def test_prompt_with_options(self):
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

    @suppress_stdout
    def test_prompt_with_limits(self):
        with patch('weecfg.input', return_value="45"):
            response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
            self.assertEqual(response, "45")
        with patch('weecfg.input', return_value=""):
            response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
            self.assertEqual(response, "0.0")
        with patch('weecfg.input', side_effect=["-120", "-45"]):
            response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
            self.assertEqual(response, "-45")

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

    def test_gen_file_paths_common(self):
        file_list = [
            ('skins/Basic',
             ['skins/Basic/index.html.tmpl',
              'skins/Basic/skin.conf',
              'skins/Basic/lang/en.conf',
              'skins/Basic/lang/fr.conf',
              ])]
        out_list = [x for x in weecfg.extension.ExtensionEngine._gen_file_paths('/etc/weewx',
                                                                                '/bar/baz',
                                                                                file_list)]
        self.assertEqual(out_list, [('/bar/baz/skins/Basic/index.html.tmpl',
                                     '/etc/weewx/skins/Basic/index.html.tmpl'),
                                    ('/bar/baz/skins/Basic/skin.conf',
                                     '/etc/weewx/skins/Basic/skin.conf'),
                                    ('/bar/baz/skins/Basic/lang/en.conf',
                                     '/etc/weewx/skins/Basic/lang/en.conf'),
                                    ('/bar/baz/skins/Basic/lang/fr.conf',
                                     '/etc/weewx/skins/Basic/lang/fr.conf')])

    def test_gen_file_paths_user(self):
        file_list = [
            ('bin/user',
             ['bin/user/foo.py',
              'bin/user/bar.py'])]
        out_list = [x for x in weecfg.extension.ExtensionEngine._gen_file_paths('/etc/weewx',
                                                                                '/bar/baz',
                                                                                file_list)]
        self.assertEqual(out_list, [('/bar/baz/bin/user/foo.py', '/etc/weewx/bin/user/foo.py'),
                                    ('/bar/baz/bin/user/bar.py', '/etc/weewx/bin/user/bar.py')])


class ExtensionInstallTest(unittest.TestCase):
    """Tests of the extension installer."""

    @staticmethod
    def _build_mini_weewx(weewx_root):
        """Build a "mini-WeeWX" in the given root directory.

        This function makes a simple version of weewx that looks like
            weewx_root
            ├── skins
            ├── user
            │   ├── __init__.py
            │   └── extensions.py
            └── weewx.conf
        """

        # First remove anything there
        shutil.rmtree(weewx_root, ignore_errors=True)
        os.makedirs(os.path.join(weewx_root, 'skins'))
        # Copy over the current version of the 'user' package
        shutil.copytree(os.path.join(RESOURCE_DIR, 'bin/user'),
                        os.path.join(weewx_root, 'user'))
        # Copy over the current version of weewx.conf
        shutil.copy(current_config_dict_path, weewx_root)

    def setUp(self):
        self.weewx_root = '/var/tmp/wee_test'

        # Install the "mini-weewx"
        ExtensionInstallTest._build_mini_weewx(self.weewx_root)

        # Retrieve the configuration file from the mini-weewx
        config_path = os.path.join(self.weewx_root, 'weewx.conf')
        self.config_path, self.config_dict = weecfg.read_config(config_path)

        # Initialize the install engine.
        self.engine = weecfg.extension.ExtensionEngine(self.config_path,
                                                       self.config_dict,
                                                       printer=Printer(verbosity=-1))

    def tearDown(self):
        "Remove any installed test configuration"
        shutil.rmtree(self.weewx_root, ignore_errors=True)

    def test_file_install(self):
        # Make sure the root dictionary got calculated correctly:
        self.assertEqual(self.engine.root_dict['WEEWX_ROOT'], '/var/tmp/wee_test')
        self.assertEqual(self.engine.root_dict['USER_DIR'], '/var/tmp/wee_test/bin/user')
        self.assertEqual(self.engine.root_dict['EXT_DIR'], '/var/tmp/wee_test/bin/user/installer')
        self.assertEqual(self.engine.root_dict['SKIN_DIR'], '/var/tmp/wee_test/skins')

        # Now install the extension...
        self.engine.install_extension('./pmon.tgz', no_confirm=True)

        # ... and assert that it got installed correctly
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['USER_DIR'],
                                                    'pmon.py')))
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['USER_DIR'],
                                                    'installer',
                                                    'pmon',
                                                    'install.py')))
        self.assertTrue(os.path.isdir(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                   'pmon')))
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                    'pmon',
                                                    'index.html.tmpl')))
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                    'pmon',
                                                    'skin.conf')))

        # Get, then check the new config dict:
        test_dict = configobj.ConfigObj(self.config_path, encoding='utf-8')
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

    def test_http_install(self):
        self.engine.install_extension(
            'https://github.com/chaunceygardiner/weewx-loopdata/releases/download/v3.3.2/weewx-loopdata-3.3.2.zip',
            no_confirm=True)
        # Test that it got installed correctly
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['USER_DIR'],
                                                    'loopdata.py')))
        self.assertTrue(os.path.isfile(os.path.join(self.engine.root_dict['USER_DIR'],
                                                    'installer',
                                                    'loopdata',
                                                    'install.py')))

    def test_uninstall(self):
        # First install...
        self.engine.install_extension('./pmon.tgz', no_confirm=True)
        # ... then uninstall it:
        self.engine.uninstall_extension('pmon', no_confirm=True)

        # Assert that everything got removed correctly:
        self.assertFalse(os.path.exists(os.path.join(self.engine.root_dict['USER_DIR'],
                                                     'pmon.py')))
        self.assertFalse(os.path.exists(os.path.join(self.engine.root_dict['USER_DIR'],
                                                     'installer',
                                                     'pmon',
                                                     'install.py')))
        self.assertFalse(os.path.exists(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                     'pmon')))
        self.assertFalse(os.path.exists(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                     'pmon',
                                                     'index.html.tmpl')))
        self.assertFalse(os.path.exists(os.path.join(self.engine.root_dict['SKIN_DIR'],
                                                     'pmon',
                                                     'skin.conf')))

        # Get the modified config dict, which had the extension removed from it
        test_path, test_dict = weecfg.read_config(self.config_path)

        # It should be the same as our original:
        self.assertEqual(test_dict, self.config_dict)


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
