#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the utilities that upgrade the configuration file."""
import io
import os.path
import unittest
import tempfile

import configobj

import weecfg.update_config


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


current_config_dict_path = "../../weewx_data/weewx.conf"


class ConfigTest(unittest.TestCase):

    def test_upgrade_v25(self):
        # Start with the Version 2.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx20.conf', encoding='utf-8')

        # Upgrade the V2.0 configuration dictionary to V2.5:
        weecfg.update_config.update_to_v25(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx25_expected.conf')

    def test_upgrade_v26(self):
        # Start with the Version 2.5 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx25.conf', encoding='utf-8')

        # Upgrade the V2.5 configuration dictionary to V2.6:
        weecfg.update_config.update_to_v26(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx26_expected.conf')

    def test_upgrade_v30(self):
        # Start with the Version 2.7 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx27.conf', encoding='utf-8')

        # Upgrade the V2.7 configuration dictionary to V3.0:
        weecfg.update_config.update_to_v30(config_dict)

        # with open('expected/weewx30_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx30_expected.conf')

    def test_upgrade_v32(self):
        # Start with the Version 3.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx30.conf', encoding='utf-8')

        # Upgrade the V3.0 configuration dictionary to V3.2:
        weecfg.update_config.update_to_v32(config_dict)

        # with open('expected/weewx32_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx32_expected.conf')

    def test_upgrade_v36(self):
        # Start with the Version 3.2 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx32.conf', encoding='utf-8')

        # Upgrade the V3.2 configuration dictionary to V3.6:
        weecfg.update_config.update_to_v36(config_dict)

        self._check_against_expected(config_dict, 'expected/weewx36_expected.conf')

    def test_upgrade_v39(self):
        # Start with the Version 3.8 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx38.conf', encoding='utf-8')

        # Upgrade the V3.8 configuration dictionary to V3.9:
        weecfg.update_config.update_to_v39(config_dict)

        # with open('expected/weewx39_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx39_expected.conf')

    def test_upgrade_v40(self):
        """Test an upgrade of the stock v3.9 weewx.conf to V4.0"""

        # Start with the Version 3.9 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx39.conf', encoding='utf-8')

        # Upgrade the V3.9 configuration dictionary to V4.0:
        weecfg.update_config.update_to_v40(config_dict)

        # with open('expected/weewx40_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx40_expected.conf')

    def test_upgrade_v42(self):
        """Test an upgrade of the stock v4.1 weewx.conf to V4.2"""

        # Start with the Version 4.1 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx41.conf', encoding='utf-8')

        # Upgrade the V4.1 configuration dictionary to V4.2:
        weecfg.update_config.update_to_v42(config_dict)

        # with open('expected/weewx42_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx42_expected.conf')

    def test_upgrade_v43(self):
        """Test an upgrade of the stock v4.1 weewx.conf to V4.2"""

        # Start with the Version 4.2 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx42.conf', encoding='utf-8')

        # Upgrade the V4.2 configuration dictionary to V4.3:
        weecfg.update_config.update_to_v43(config_dict)

        # with open('expected/weewx43_expected.conf', 'wb') as fd:
        #     config_dict.write(fd)

        self._check_against_expected(config_dict, 'expected/weewx43_expected.conf')

    def test_merge(self):
        """Test an upgrade against a typical user's configuration file"""

        # Start with a typical V2.0 user file:
        _, config_dict = weecfg.read_config('weewx20_user.conf')
        # The current config file becomes the template:
        _, template = weecfg.read_config(current_config_dict_path)

        # First update, then merge:
        weecfg.update_config.update_and_merge(config_dict, template)

        with tempfile.NamedTemporaryFile() as fd:
            # Save it to the temporary file:
            weecfg.save(config_dict, fd.name)
            # Now read it back in again:
            check_dict = configobj.ConfigObj(fd, encoding='utf-8')

        # with open('expected/weewx43_user_expected.conf', 'wb') as fd:
        #     check_dict.write(fd)

        # Check the results.
        self._check_against_expected(check_dict, 'expected/weewx43_user_expected.conf')

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


if __name__ == "__main__":
    unittest.main()
