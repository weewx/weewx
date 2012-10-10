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

import optparse
import sys
import syslog

import configobj

import user.extensions      #@UnusedImport
import weedb
import weewx.archive
import weewx.stats

description="""Configures the weewx databases. Most of these functions are handled automatically
by weewx, but they may be useful as a utility in special cases. In particular, 
the reconfigure-database option can be useful if you decide to add or drop data types
from the database schema."""
 
usage="""%prog: config_path [--help] [--create-database] 
                            [--create-stats] [--backfill-stats] [--reconfigure-database]"""

def main():

    # Set defaults for the system logger:
    syslog.openlog('config_database', syslog.LOG_PID|syslog.LOG_CONS)

    # Create a command line parser:
    parser = optparse.OptionParser(description=description, usage=usage)
    
    # Add the various options:
    parser.add_option("--create-archive", dest="create_archive", action='store_true',
                        help="Create the archive database.")
    parser.add_option("--create-stats", dest="create_stats", action='store_true',
                        help="Create the statistical database.")
    parser.add_option("--backfill-stats", dest="backfill_stats", action='store_true',
                        help="Backfill the statistical database using the archive database")
    parser.add_option("--reconfigure-database", dest="new_database", action='store', type='string', metavar='NEW-DATABASE',
                        help="""Reconfigure the archive database and put the results in NEW-DATABASE, which must appear """\
                        """in the [Databases] section of the configuration file. The schema found in bin/user/schemas.py will """\
                        """be used for the new database.""")
    # Now we are ready to parse the command line:
    (options, args) = parser.parse_args()

    if not args:
        parser.error("Missing configuration file.")

    config_path = args[0]
    
    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print >>sys.stderr, "Unable to open configuration file ", config_path
        syslog.syslog(syslog.LOG_CRIT, "Unable to open configuration file %s" % config_path)
        exit(1)
    except configobj.ConfigObjError:
        print >>sys.stderr, "Error wile parsing configuration file %s" % config_path
        syslog.syslog(syslog.LOG_CRIT, "Error while parsing configuration file %s" % config_path)
        exit(1)

    syslog.syslog(syslog.LOG_INFO, "Using configuration file %s." % config_path)

    if options.create_archive:
        createMainDatabase(config_dict)
    
    if options.create_stats:
        createStatsDatabase(config_dict)
        
    if options.backfill_stats:
        backfillStatsDatabase(config_dict)

    if options.new_database:
        reconfigMainDatabase(config_dict, options.new_database)

def createMainDatabase(config_dict):
    """Create the main weewx archive database"""
    archive_db = config_dict['StdArchive']['archive_database']
    archive_db_dict = config_dict['Databases'][archive_db]
    # Try to open up the database. If it doesn't exist or has not been
    # initialized, an exception will be thrown. Catch it, configure the
    # database, and then try again.
    try:
        archive = weewx.archive.Archive(archive_db_dict) #@UnusedVariable
    except (StandardError, weedb.OperationalError):
        # It's uninitialized. Configure it:
        weewx.archive.config(archive_db_dict)
        print "Created archive database '%s'" % (archive_db,)
    else:
        print "The archive database '%s' already exists" % (archive_db,)

def createStatsDatabase(config_dict):
    """Create the weewx statistical database"""
    stats_db = config_dict['StdArchive']['stats_database']
    stats_db_dict = config_dict['Databases'][stats_db]
    # Try to open up the database. If it doesn't exist or has not been
    # initialized, an exception will be thrown. Catch it, configure the
    # database, and then try again.
    try:
        statsDb = weewx.stats.StatsDb(stats_db_dict) #@UnusedVariable
    except (StandardError, weedb.OperationalError):
        # It's uninitialized. Configure it:
        weewx.stats.config(stats_db_dict, 
                           stats_types=config_dict['StdArchive'].get('stats_types'))
        print "Created statistical database '%s'" % (stats_db,)
    else:
        print "The statistical database '%s' already exists" % (stats_db,)

def backfillStatsDatabase(config_dict):
    """Use the main archive database to backfill the stats database."""

    # Open up the main database archive
    archive = weewx.archive.Archive.fromConfigDict(config_dict)

    # Configure the stats database if necessary. This will do nothing if the
    # database has already been configured:
    createStatsDatabase(config_dict)

    # Open up the Stats database
    statsDb = weewx.stats.StatsDb.fromConfigDict(config_dict)
    
    # Now backfill
    nrecs = statsDb.backfillFrom(archive)
    print "Backfilled %d records from the archive database '%s' into the statistical database '%s'" % (nrecs, archive.database, statsDb.database)
    
def reconfigMainDatabase(config_dict, new_archive_db):
    """Change the schema of the old database"""

    old_archive_db_dict = config_dict['Databases'][config_dict['StdArchive']['archive_database']]
    new_archive_db_dict = config_dict['Databases'][new_archive_db]
    
    weewx.archive.reconfig(old_archive_db_dict, new_archive_db_dict)
    
if __name__=="__main__" :
    main()
