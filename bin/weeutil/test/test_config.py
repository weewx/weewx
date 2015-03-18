#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the configuration utilities."""

import StringIO
import unittest
import configobj

import weeutil.config

class ConfigTest(unittest.TestCase):
    
    def test_upgrade_v27(self):

        # Start with the Version 2.0 weewx.conf file:
        config20_dict = configobj.ConfigObj('weewx20.conf')
        
        # Upgrade the V2.0 configuration dictionary to V2.7:
        config27_dict = weeutil.config.update_to_v27(config20_dict)
        
        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config27_dict.write(out_str)

        out_str.seek(0)
        fd_expected = open('expected/weewx27_expected.conf')
        for expected in fd_expected:
            actual = out_str.readline()
            self.assertEqual(actual, expected)
            
        # Make sure there are no extra lines in the updated config:
        more = out_str.readline()
        self.assertEqual(more, '')
        
        out_str.close()
        
    def test_upgrade_30(self):
        
        # Start with the Version 2.7 weewx.conf file:
        config27_dict = configobj.ConfigObj('weewx27.conf')  

        # Upgrade to V3.0
        config30_dict = weeutil.config.update_to_v3(config27_dict)
        
        # Write it out to a StringIO, then start checking it against the expected
        out_str = StringIO.StringIO()
        config30_dict.write(out_str)

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
        
        out_str.close()
        
#     def test_merge(self):
#         
#         # Start with a typical V2.0 user file:
#         
#         config_user_dict = configobj.ConfigObj('weewx_user.conf')
#         
#         # The V3.1 config file becomes the template:
#         template = configobj.ConfigObj('weewx31.conf')
#         
#         out_dict = weeutil.config.merge_config(config_user_dict, template)
#         
#         fd = open('expected/weewx_user_expected.conf', 'w')
#         out_dict.write(fd)
#         fd.close()
        
if __name__ == '__main__':
    unittest.main()
        