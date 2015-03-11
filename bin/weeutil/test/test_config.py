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

        # Start by upgrading to V2.7:
        weeutil.config.update_to_v27(config20_dict)
        
        out_str = StringIO.StringIO()
        config20_dict.write(out_str)

        out_str.seek(0)
        fd_expected = open('expected/weewx27.conf')
        for expected in fd_expected:
            actual = out_str.readline()
            self.assertEqual(actual, expected)
        
        # Now upgrade to V3.x:
        
        
        
if __name__ == '__main__':
    unittest.main()
        