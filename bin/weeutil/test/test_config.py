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
    
    def test_upgrade_v27(self):

        # Start with the Version 2.0 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx20.conf')
        
        # Upgrade the V2.0 configuration dictionary to V2.7:
        weeutil.config.update_to_v27(config_dict)
        
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
        
        out_str.close()
        
    def test_upgrade_30(self):
        
        # Start with the Version 2.7 weewx.conf file:
        config_dict = configobj.ConfigObj('weewx27.conf')  

        # Upgrade to V3.0
        weeutil.config.update_to_v30(config_dict)
        
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
        
        out_str.close()
        
    def test_utilities(self):
        global x_str, y_str
        
        xio = StringIO.StringIO(x_str)
        x_dict = configobj.ConfigObj(xio)
        weeutil.config.reorder_sections(x_dict, 'section_c', 'section_b')
        self.assertEqual("{'section_a': {'a': '1'}, 'section_c': {'c': '3'}, "
                         "'section_b': {'b': '2'}, 'section_d': {'d': '4'}}", str(x_dict))
        
        xio.seek(0)
        x_dict = configobj.ConfigObj(xio)
        weeutil.config.reorder_sections(x_dict, 'section_c', 'section_b', after=True)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, "
                         "'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))
        
        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        weeutil.config.conditional_merge(x_dict, y_dict)
        self.assertEqual("{'section_a': {'a': '1'}, 'section_b': {'b': '2'}, 'section_c': {'c': '3'}, "
                         "'section_d': {'d': '4'}, 'section_e': {'c': '15'}}", str(x_dict))

  
        xio = StringIO.StringIO(x_str)
        yio = StringIO.StringIO(y_str)
        x_dict = configobj.ConfigObj(xio)
        y_dict = configobj.ConfigObj(yio)
        weeutil.config.remove_and_prune(x_dict, y_dict)
        self.assertEqual("{'section_c': {'c': '3'}, 'section_d': {'d': '4'}}", str(x_dict))

    def test_merge(self):
         
        # Start with a typical V2.0 user file:
        config_dict = configobj.ConfigObj('weewx_user.conf')
         
        # The V3.1 config file becomes the template:
        template = configobj.ConfigObj('weewx31.conf')
         
        weeutil.config.merge_config(config_dict, template)
        
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
        
        out_str.close()
        
if __name__ == '__main__':
    unittest.main()
        