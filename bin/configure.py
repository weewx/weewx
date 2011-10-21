#!/usr/bin/env python
#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Configure various resources used by weewx"""

import sys
import syslog
import os.path
from optparse import OptionParser
import configobj

import user.extensions      #@UnusedImport
import weewx.archive
import weewx.stats

usagestr = """%prog: config_path [Options]

Configuration program for the weewx weather system.

Arguments:
    config_path: Path to the configuration file to be used."""

def main():

    # Set defaults for the system logger:
    syslog.openlog('configure', syslog.LOG_PID|syslog.LOG_CONS)

    # This is a bit of a cludge. Get the path for the configuration file:
    for arg in sys.argv[1:]:
        if arg[0] != '-':
            config_path = arg
            break
    else:
        sys.stderr.write("Missing configuration file")
        sys.exit(weewx.CMD_ERROR)
        
    # Try to open up the given configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print "Unable to open configuration file ", config_path
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % config_path)
        sys.exit(weewx.CONFIG_ERROR)

    # Now put together the command options:
    parser = OptionParser(usage=usagestr)
    parser.add_option("--create-database",     action="store_true", dest="create_database",  help="To create the main database archive")
    parser.add_option("--create-stats",        action="store_true", dest="create_stats",     help="To create the statistical database")
    parser.add_option("--backfill-stats",      action="store_true", dest="backfill_stats",   help="To backfill the statistical database from the main database")
    parser.add_option("--reconfigure-database",action="store_true", dest="reconfig_database",help="To reconfigure the main database archive")

    # Get the hardware type from the configuration dictionary
    # (this will be a string such as "VantagePro"),
    # then import the appropriate module:
    stationType = config_dict['Station']['station_type']
    station_mod = __import__('weewx.'+ stationType)

    # Add its options to the list:
    getattr(station_mod, stationType).getOptionGroup(parser)
    
    # Now we are ready to parse the command line:
    (options, args) = parser.parse_args()
        
    if options.create_database:
        createMainDatabase(config_dict)
    
    if options.create_stats:
        createStatsDatabase(config_dict)
        
    if options.backfill_stats:
        backfillStatsDatabase(config_dict)

    if options.reconfig_database:
        reconfigMainDatabase(config_dict)

    # Now run any hardware specific options:
    getattr(station_mod, stationType).runOptions(config_dict, options, args)

def createMainDatabase(config_dict):
    """Create the main weewx archive database"""
    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    try:
        dummy_archive = weewx.archive.Archive(archiveFilename)
    except StandardError:
        # Configure it
        weewx.archive.config(archiveFilename)
        print "Created archive database %s" % archiveFilename
    else:
        print "The archive database %s already exists" % archiveFilename

def createStatsDatabase(config_dict):
    """Create the weewx statistical database"""
    # Open up the Stats database
    statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                 config_dict['Stats']['stats_file'])
    try:
        dummy_statsDb = weewx.stats.StatsDb(statsFilename)
    except StandardError:
        # Configure it:
        weewx.stats.config(statsFilename, config_dict['Stats'].get('stats_types'))
        print "Created statistical database %s" % statsFilename
    else:
        print "The statistical database %s already exists" % statsFilename

def backfillStatsDatabase(config_dict):
    """Use the main archive database to backfill the stats database."""

    # Configure if necessary. This will do nothing if the database
    # has already been configured:
    createStatsDatabase(config_dict)

    # Open up the Stats database
    statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                 config_dict['Stats']['stats_file'])
    statsDb = weewx.stats.StatsDb(statsFilename)
    
    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    archive = weewx.archive.Archive(archiveFilename)

    # Now backfill
    weewx.stats.backfill(archive, statsDb)
    print "Backfilled statistical database %s with archive data from %s" % (statsFilename, archiveFilename)
    
def reconfigMainDatabase(config_dict):
    """Change the schema of the old database"""
    
    # The old archive:
    oldArchiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                      config_dict['Archive']['archive_file'])
    newArchiveFilename = oldArchiveFilename + ".new"
    weewx.archive.reconfig(oldArchiveFilename, newArchiveFilename)
    
main()
