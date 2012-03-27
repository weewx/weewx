#!/usr/bin/env python
#
#    Copyright (c) 2009, 2010, 2011, 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Configure the databases used by weewx"""

import argparse
import os.path
import sys
import syslog

import configobj

import user.extensions      #@UnusedImport
import weewx.archive
import weewx.stats

description="""Configures the weewx databases. Most of these functions are handled automatically
by weewx, but they may be useful as a utility in special cases. In particular, 
the reconfigure-database option can be useful if you decide to add or drop data types
from the database schema."""

def main():

    # Set defaults for the system logger:
    syslog.openlog('config_database', syslog.LOG_PID|syslog.LOG_CONS)

    # Create a command line parser:
    parser = argparse.ArgumentParser(description=description)
    
    # Add the various options:
    parser.add_argument("config_path",
                        help="Path to the configuration file (Required)")
    parser.add_argument("--create-database", dest="create_database", action='store_true',
                        help="Create the archive database.")
    parser.add_argument("--create-stats", dest="create_stats", action='store_true',
                        help="Create the statistical database.")
    parser.add_argument("--backfill-stats", dest="backfill_stats", action='store_true',
                        help="Backfill the statistical database using the archive database")
    parser.add_argument("--reconfigure-database", dest="reconfigure_database", action='store_true',
                        help="""Reconfigure the archive database. The schema found in bin/user/schemas.py will
                        be used for the new database. It will have the same name as the old database, but with
                        suffic '.new'. It will then be populated with the data from the old database. """)
    # Now we are ready to parse the command line:
    args = parser.parse_args()

    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(args.config_path, file_error=True)
    except IOError:
        print >>sys.stderr, "Unable to open configuration file ", args.config_path
        syslog.syslog(syslog.LOG_CRIT, "Unable to open configuration file %s" % args.config_path)
        exit(1)
    except configobj.ConfigObjError:
        print >>sys.stderr, "Error wile parsing configuration file %s" % args.config_path
        syslog.syslog(syslog.LOG_CRIT, "Error while parsing configuration file %s" % args.config_path)
        exit(1)

    syslog.syslog(syslog.LOG_INFO, "Using configuration file %s." % args.config_path)

    if args.create_database:
        createMainDatabase(config_dict)
    
    if args.create_stats:
        createStatsDatabase(config_dict)
        
    if args.backfill_stats:
        backfillStatsDatabase(config_dict)

    if args.reconfig_database:
        reconfigMainDatabase(config_dict)

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
    
if __name__=="__main__" :
    main()
