#!/usr/bin/env python
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Configure various resources used by weewx"""

import syslog
import os.path
from optparse import OptionParser
import configobj
import weewx.archive
import weewx.stats
import weewx.VantagePro

usagestr = """%prog: config_path

Configuration program for the weewx weather system.

Arguments:
    config_path: Path to the configuration file to be used."""

def main():
    parser = OptionParser(usage=usagestr)
    parser.add_option("--create-database", action="store_true", dest="create_database", help="To create the SQL database wview-archive.sdb")
    parser.add_option("--create-stats",    action="store_true", dest="create_stats",    help="To create the statistical statistical database stats.sdb")
    parser.add_option("--backfill-stats",  action="store_true", dest="backfill_stats",  help="To backfill the statistical database from the main database")
    parser.add_option("--configure-WxStation", action="store_true", dest="configure_VP", help="To configure a WxStation weather station")
    
    (options, args) = parser.parse_args()
    
    if len(args) < 1:
        print "Missing argument(s)."
        print parser.parse_args(["--help"])
        exit()
    
    config_path = args[0]
    
    # Set defaults for the system logger:
    syslog.openlog('configure', syslog.LOG_PID|syslog.LOG_CONS)
    
    # Try to open up the given configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print "Unable to open configuration file ", config_path
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % config_path)
        exit()
        
    if options.create_database:
        createMainDatabase(config_dict)
    
    if options.create_stats:
        createStatsDatabase(config_dict)
        
    if options.backfill_stats:
        backfillStatsDatabase(config_dict)
    
    if options.configure_VP:
        configureVP(config_dict)


def createMainDatabase(config_dict):
    """Create the main weewx archive database"""
    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    archive = weewx.archive.Archive(archiveFilename)
    # Configure it if necessary (this will do nothing if the database has
    # already been configured):
    archive.config()
    print "created archive database %s" % archiveFilename

def createStatsDatabase(config_dict):
    """Create the weewx statistical database"""
    # Open up the Stats database
    statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                 config_dict['Stats']['stats_file'])
    statsDb = weewx.stats.StatsDb(statsFilename)
    # Configure it if necessary (this will do nothing if the database has
    # already been configured):
    statsDb.config(config_dict['Stats'].get('stats_types'))
    print "created statistical database %s" % statsFilename

def backfillStatsDatabase(config_dict):
    """Use the main archive database to backfill the stats database."""
    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    archive = weewx.archive.Archive(archiveFilename)

    # Open up the Stats database
    statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                 config_dict['Stats']['stats_file'])
    statsDb = weewx.stats.StatsDb(statsFilename,
                                  int(config_dict['Station'].get('heating_base', 65)),
                                  int(config_dict['Station'].get('cooling_base', 65)))
    
    weewx.stats.backfill(archive, statsDb)
    print "backfilled statistical database %s with archive data from %s" % (statsFilename, archiveFilename)
    
def configureVP(config_dict):
    """Configure a WxStation as per the configuration file."""
    
    print "Configuring WxStation..."
    # Open up the weather station:
    station = weewx.WxStation.WxStation(config_dict['WxStation'])

    old_archive_interval = station.archive_interval
    new_archive_interval = config_dict['WxStation'].as_int('archive_interval')
    
    if old_archive_interval == new_archive_interval:
        print "Old archive interval matches new archive interval (%d seconds). Nothing done" % old_archive_interval
    else:
        print "WxStation old archive interval is %d seconds, new one is %d" % (old_archive_interval, new_archive_interval)
        print "Proceeding will erase old archive records."
        ans = raw_input("Are you sure you want to proceed? (y/n) ")
        if ans == 'y' :
            station.setArchiveInterval(new_archive_interval)
            print "Archive interval now set to %d." % (new_archive_interval,)
            # The Davis documentation implies that the log is cleared after
            # changing the archive interval, but that doesn't seem to be the
            # case. Clear it explicitly:
            station.clearLog()
            print "Archive records cleared."
        else:
            print "Nothing done."
main()
