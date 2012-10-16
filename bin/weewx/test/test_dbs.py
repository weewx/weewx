# -*- coding: utf-8 -*-
#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 670 $
#    $Author: tkeffer $
#    $Date: 2012-10-11 16:55:54 -0700 (Thu, 11 Oct 2012) $
#
"""Test archive and stats database modules"""
import syslog
import unittest

import configobj

import weewx.archive
import weewx.stats
import weedb

class StatsTest(unittest.TestCase):
    
    def setUp(self):
        global config_path
        
        weewx.debug = 1

        syslog.openlog('test_stats', syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        try :
            self.config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % self.config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise


    def test_archive(self):
        archive_db      = self.config_dict['StdArchive']['archive_database']
        archive_db_dict = self.config_dict['Databases'][archive_db]        
        # First, make sure it does not exist:
        try:
            weedb.drop(archive_db_dict)
        except weedb.NoDatabase:
            pass
    
        # Now an effort to open it should result in an exception:
        archive = weewx.archive.Archive.fromDbDict(archive_db_dict)


#    def test_stats(self):
#        stats_db        = config_dict['StdArchive']['stats_database']
#        stats_db_dict   = config_dict['Databases'][stats_db]
        
        
if __name__ == '__main__':
    import sys
    global config_path
    
    if len(sys.argv) < 2 :
        print "Usage: python test_dbs.py path-to-configuration-file"
        exit()

    # Get the path to the configuration file, then delete it from the argument list:
    config_path = sys.argv[1]
    del sys.argv[1:]
    unittest.main()
    
