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
import os.path
import sys
import shutil

import distutils.dir_util
import configobj

import weecfg.extension
import weeutil.weeutil

try:
    from mock import patch
    import __builtin__  # @UnusedImport
    have_mock = True
except ImportError:
    print "Module 'mock' not installed. Testing will be restricted."
    have_mock = False

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

current_config_dict_path = "../../../weewx.conf"

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

    def test_utilities(self):
        global x_str, y_str

        xio = StringIO.StringIO(x_str)
        x_dict = configobj.ConfigObj(xio)
        weecfg.reorder_sections(x_dict, 'section_c', 'section_b')
        self.assertEqual("{'section_a': {'a': '1'}, 'section_c': {'c': '3'}, "
                         "'section_b': {'b': '2'}, 'section_d': {'d': '4'}}", str(x_dict))

        xio.seek(0)
        x_dict = configobj.ConfigObj(xio)
        weecfg.reorder_sections(x_dict, 'section_c', 'section_b', after=True)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, "
                         "'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))

        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        weeutil.weeutil.conditional_merge(x_dict, y_dict)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, 'section_c': {'c': '3'}, "
                         "'section_d': {'d': '4'}, 'section_e': {'c': '15'}}", str(x_dict))


        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        weecfg.remove_and_prune(x_dict, y_dict)
        self.assertEqual("{'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))

    report_start_str = """[StdReport]
        SKIN_ROOT = skins
        HTML_ROOT = public_html
        data_binding = wx_binding
        [[XtraReport]]
            skin = Foo
            
        [[StandardReport]]
            skin = Standard
    
        [[FTP]]
            skin = Ftp
    
        [[RSYNC]]
            skin = Rsync
"""
            
    report_expected_str = """[StdReport]
        SKIN_ROOT = skins
        HTML_ROOT = public_html
        data_binding = wx_binding
        
        [[StandardReport]]
                skin = Standard
        [[XtraReport]]
                skin = Foo
        
        [[FTP]]
                skin = Ftp
        
        [[RSYNC]]
                skin = Rsync
""" 
     
    def test_reorder(self):
        """Test the utility reorder_to_ref"""
        xio = StringIO.StringIO(ConfigTest.report_start_str)
        x_dict = configobj.ConfigObj(xio)
        weecfg.reorder_to_ref(x_dict)
        x_result = StringIO.StringIO()
        x_dict.write(x_result)
        check_fileend(x_result)
        self.assertEqual(ConfigTest.report_expected_str, x_result.getvalue())

    if have_mock:

        def test_prompt_for_info(self):

            # Suppress stdout by temporarily assigning it to /dev/null
            save_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            try:

                # Test a normal input
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a default input
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '', '45.0', '180.0', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['0', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for an out-of-bounds latitude
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '95.0', '45.0', '180.0', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a bad length unit type
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, foo', '100,meter', '45.0', '180.0', 'us']):
                    stn_info = weecfg.prompt_for_info()
                    self.assertEqual(stn_info, {'altitude': ['100', 'meter'],
                                                'latitude': '45.0',
                                                'location': 'Anytown',
                                                'longitude': '180.0',
                                                'units': 'us'})

                # Test for a bad display unit
                with patch('__builtin__.raw_input',
                           side_effect=['Anytown', '100, meter', '45.0', '180.0', 'foo', 'us']):
                    stn_info = weecfg.prompt_for_info()
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
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('__builtin__.raw_input', return_value="no"):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "no")
                with patch('__builtin__.raw_input', return_value=""):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
                    self.assertEqual(response, "yes")
                with patch('__builtin__.raw_input', side_effect=["make me", "no"]):
                    response = weecfg.prompt_with_options("Say yes or no", "yes", ["yes", "no"])
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
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "45")
                with patch('__builtin__.raw_input', return_value=""):
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "0.0")
                with patch('__builtin__.raw_input', side_effect=["-120", "-45"]):
                    response = weecfg.prompt_with_limits("latitude", "0.0", -90, 90)
                    self.assertEqual(response, "-45")
            finally:
                # Restore stdout:
                sys.stdout = save_stdout

    def test_upgrade_v27(self):

        # Start with the Version 2.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx20.conf')

        # Upgrade the V2.0 configuration dictionary to V2.7:
        weecfg.update_to_v27(config_dict)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)
        check_fileend(out_str)
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
        weecfg.update_to_v30(config_dict)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)
        check_fileend(out_str)
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

    def test_upgrade_36(self):

        # Start with the Version 3.5 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx35.conf')

        # Upgrade to V3.6
        weecfg.update_to_v36(config_dict)

        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)
        check_fileend(out_str)
        out_str.seek(0)

        fd_expected = open('expected/weewx36_expected.conf')
        N = 0
        for expected in fd_expected:
            actual = out_str.readline()
            N += 1
            self.assertEqual(actual, expected, "[%d] '%s' vs '%s'" % (N, actual, expected))

        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '', "Unexpected additional lines")

    def test_driver_info(self):
        """Test the discovery and listing of drivers."""
        driver_info_dict = weecfg.get_driver_infos()
        self.assertEqual(driver_info_dict['weewx.drivers.wmr100']['module_name'], 'weewx.drivers.wmr100')
        # Test for the driver name
        self.assertEqual(driver_info_dict['weewx.drivers.wmr100']['driver_name'], 'WMR100')
        # Cannot really test for version numbers of all drivers. Pick one. Import it...
        import weewx.drivers.wmr100
        # ... and see if the version number matches
        self.assertEqual(driver_info_dict['weewx.drivers.wmr100']['version'], weewx.drivers.wmr100.DRIVER_VERSION)
        del weewx.drivers.wmr100
        
    def test_merge(self):

        # Start with a typical V2.0 user file:
        config_dict = configobj.ConfigObj('weewx_user.conf')

        # The current config file becomes the template:
        template = configobj.ConfigObj(current_config_dict_path)

        # First update, then merge:
        weecfg.update_and_merge(config_dict, template)
        
        # Reorder to make the comparisons more predictable:
        weecfg.reorder_to_ref(config_dict)
        
        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config_dict.write(out_str)
        check_fileend(out_str)
        out_str.seek(0)

        fd_expected = open('expected/weewx_user_expected.conf')
        N = 0
        for expected in fd_expected:
            actual = out_str.readline()
            N += 1
            if actual.startswith('version ='):
                actual = actual[:10]
                expected = expected[:10]
            else:
                self.assertEqual(actual, expected, "[%d] '%s' vs '%s'" % (N, actual, expected))

        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '')

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
        self.bin_dir  = os.path.join(self.weewx_root, 'bin')
        distutils.dir_util.copy_tree('../../../bin/user', self.user_dir)
        distutils.dir_util.copy_tree('../../../skins/Standard', os.path.join(self.skin_dir, 'Standard'))
        shutil.copy(current_config_dict_path, self.weewx_root)
        
    def tearDown(self):
        "Remove any installed test configuration"
        try:
            distutils.dir_util.remove_tree(self.weewx_root)
        except OSError:
            pass

    def test_install(self):
        # Find and read the test configuration
        config_path = os.path.join(self.weewx_root,'weewx.conf')
        config_dict = configobj.ConfigObj(config_path)
        
        # Note that the actual location of the "mini-weewx" is over in /var/tmp
        config_dict['WEEWX_ROOT'] = self.weewx_root

        # Initialize the install engine. Note that we want the bin root in /var/tmp, not here:
        engine = weecfg.extension.ExtensionEngine(config_path, config_dict, 
                                                  bin_root=self.bin_dir,
                                                  logger= weecfg.Logger(verbosity=-1)) 
        
        # Make sure the root dictionary got calculated correctly:
        self.assertEqual(engine.root_dict, {'WEEWX_ROOT' : '/var/tmp/wee_test',
                                            'BIN_ROOT'   : '/var/tmp/wee_test/bin',
                                            'USER_ROOT'  : '/var/tmp/wee_test/bin/user',
                                            'EXT_ROOT'   : '/var/tmp/wee_test/bin/user/installer',
                                            'SKIN_ROOT'  : '/var/tmp/wee_test/skins',
                                            'CONFIG_ROOT': '/var/tmp/wee_test'})
        
        # Now install the extension...
        engine.install_extension('./pmon.tgz')
        
        # ... and assert that it got installed correctly
        self.assertTrue(os.path.isfile(os.path.join(self.user_dir, 'pmon.py')))
        self.assertTrue(os.path.isfile(os.path.join(self.user_dir, 'installer', 'pmon', 'install.py')))
        self.assertTrue(os.path.isdir(os.path.join(self.skin_dir, 'pmon')))
        self.assertTrue(os.path.isfile(os.path.join(self.skin_dir, 'pmon','index.html.tmpl')))
        self.assertTrue(os.path.isfile(os.path.join(self.skin_dir, 'pmon','skin.conf')))
        
        # Get, then check the new config dict:
        test_dict = configobj.ConfigObj(config_path)
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
        
        self.assertTrue('user.pmon.ProcessMonitor' in test_dict['Engine']['Services']['process_services'])
        
    def test_uninstall(self):
        # Find and read the test configuration
        config_path = os.path.join(self.weewx_root,'weewx.conf')
        config_dict = configobj.ConfigObj(config_path)
        
        # Note that the actual location of the "mini-weewx" is over in /var/tmp
        config_dict['WEEWX_ROOT'] = self.weewx_root

        # Initialize the install engine. Note that we want the bin root in /var/tmp, not here:
        engine = weecfg.extension.ExtensionEngine(config_path, config_dict, 
                                                  bin_root=self.bin_dir,
                                                  logger= weecfg.Logger(verbosity=-1)) 
        # First install...
        engine.install_extension('./pmon.tgz')
        # ... then uninstall it:
        engine.uninstall_extension('pmon')
        
        # Assert that everything got removed correctly:
        self.assertTrue(not os.path.exists(os.path.join(self.user_dir, 'pmon.py')))
        self.assertTrue(not os.path.exists(os.path.join(self.user_dir, 'installer', 'pmon', 'install.py')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon','index.html.tmpl')))
        self.assertTrue(not os.path.exists(os.path.join(self.skin_dir, 'pmon','skin.conf')))
        
        # Get the modified config dict, which had the extension removed from it
        test_dict = configobj.ConfigObj(config_path)

        # It should be the same as our original:
        self.assertEqual(test_dict, config_dict)
unittest.main()
