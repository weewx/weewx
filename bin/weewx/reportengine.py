#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Engine for generating reports"""

import ftplib
import glob
import os.path
import shutil
import socket
import sys
import syslog
import threading
import time

import configobj

import weeutil.ftpupload
import weeutil.weeutil
import weewx.archive
import weewx.stats

class StdReportEngine(threading.Thread):
    """Reporting engine for weewx.
    
    This engine runs zero or more reports. Each report uses a skin. A skin
    has its own configuration file specifying things such as which 'generators'
    should be run, which templates are to be used, what units are to be used, etc.. 
    A 'generator' is a class inheriting from class ReportGenerator, that produces the parts
    of the report, such as image plots, HTML files. 
    
    StdReportEngine inherits from threading.Thread, so it will be run in a separate
    thread.
    
    See below for examples of generators.
    """
    
    def __init__(self, config_dict, stn_info, gen_ts=None, first_run=True):
        """Initializer for the report engine. 
        
        config_dict: The configuration dictionary.
        
        stn_info: An instance of weewx.station.StationInfo, with static station information.
        
        gen_ts: The timestamp for which the output is to be current [Optional; default
        is the last time in the database]
        
        first_run: True if this is the first time the report engine has been run.
        If this is the case, then any 'one time' events should be done.
        """
        threading.Thread.__init__(self, name="ReportThread")

        self.config_dict = config_dict
        self.stn_info    = stn_info
        self.gen_ts      = gen_ts
        self.first_run   = first_run
        
    def setup(self):
        if self.gen_ts:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for time %s" % 
                          weeutil.weeutil.timestamp_to_string(self.gen_ts))
        else:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for latest time in the database.")
        
    
    def run(self):
        """This is where the actual work gets done.
        
        Runs through the list of reports. """
        
        self.setup()

        # Iterate over each requested report
        for report in self.config_dict['StdReport'].sections:
            
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running report %s" % report)
            
            # Figure out where the configuration file is for the skin used for this report:
            skin_config_path = os.path.join(self.config_dict['WEEWX_ROOT'],
                                            self.config_dict['StdReport']['SKIN_ROOT'],
                                            self.config_dict['StdReport'][report].get('skin', 'Standard'),
                                            'skin.conf')
            # Retrieve the configuration dictionary for the skin. Wrap it in a try
            # block in case we fail
            try :
                skin_dict = configobj.ConfigObj(skin_config_path, file_error=True)
                syslog.syslog(syslog.LOG_DEBUG, "reportengine: Found configuration file %s for report %s" % (skin_config_path, report))
            except IOError:
                syslog.syslog(syslog.LOG_ERR, "reportengine: No skin configuration file for report %s" % report)
                syslog.syslog(syslog.LOG_ERR, "        ****  Tried path %s" % skin_config_path)
                syslog.syslog(syslog.LOG_ERR, "        ****  Report ignored...")
                continue
                
            # Add the default archive and stats databases:
            skin_dict['archive_database'] = self.config_dict['StdArchive']['archive_database']
            skin_dict['stats_database']   = self.config_dict['StdArchive']['stats_database']

            # Inject any overrides the user may have specified in the weewx.conf
            # configuration file for all reports:
            for scalar in self.config_dict['StdReport'].scalars:
                skin_dict[scalar] = self.config_dict['StdReport'][scalar]
            
            # Now inject any overrides for this specific report:
            skin_dict.merge(self.config_dict['StdReport'][report])
            
            # Finally, add the report name:
            skin_dict['REPORT_NAME'] = report
            
            for generator in weeutil.weeutil.option_as_list(skin_dict['Generators'].get('generator_list')):
                try:
                    # Instantiate an instance of the class.
                    obj = weeutil.weeutil._get_object(generator, 
                                                      self.config_dict, 
                                                      skin_dict, 
                                                      self.gen_ts, 
                                                      self.first_run,
                                                      self.stn_info)
                except Exception, e:
                    syslog.syslog(syslog.LOG_CRIT, "reportengine: Unable to instantiate generator %s." % generator)
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % e)
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator ignored...")
                    continue
    
                try:
                    # Call its start() method
                    obj.start()
                    
                except Exception, e:
                    # Caught unrecoverable error. Log it, exit
                    syslog.syslog(syslog.LOG_CRIT, "reportengine: Caught unrecoverable exception in generator %s" % (generator,))
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % e)
                    weeutil.weeutil.log_traceback("        ****  ")
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator terminated...")
                    
                finally:
                    obj.finalize()


class ReportGenerator(object):
    """Base class for all report generators."""
    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info):
        self.config_dict = config_dict
        self.skin_dict   = skin_dict
        self.gen_ts      = gen_ts
        self.first_run   = first_run
        self.stn_info    = stn_info
        
    def start(self):
        self.run()
    
    def run(self):
        pass
    
    def finalize(self):
        pass

class FtpGenerator(ReportGenerator):
    """Class for managing the "FTP generator".
    
    This will ftp everything in the public_html subdirectory to a webserver."""

    def run(self):

        t1 = time.time()

        try:
            ftpData = weeutil.ftpupload.FtpUpload(server      = self.skin_dict['server'],
                                                  user        = self.skin_dict['user'],
                                                  password    = self.skin_dict['password'],
                                                  local_root  = os.path.join(self.config_dict['WEEWX_ROOT'],
                                                                             self.config_dict['StdReport']['HTML_ROOT']),
                                                  remote_root = self.skin_dict['path'],
                                                  name        = self.skin_dict['REPORT_NAME'],
                                                  passive     = bool(self.skin_dict.get('passive', True)),
                                                  max_tries   = int(self.skin_dict.get('max_tries', 3)))
        except Exception:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: FTP upload not requested. Skipped.")
            return

        try:
            N = ftpData.run()
        except (socket.timeout, socket.gaierror, ftplib.all_errors, IOError), e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "reportengine: Caught exception %s in FtpGenerator; %s." % (cl, e))
            return
        
        t2= time.time()
        syslog.syslog(syslog.LOG_INFO, """reportengine: ftp'd %d files in %0.2f seconds""" % (N, (t2-t1)))
            
                
class CopyGenerator(ReportGenerator):
    """Class for managing the 'copy generator.'
    
    This will copy files from the skin subdirectory to the public_html
    subdirectory."""
    
    def run(self):
        
        copy_list = []

        if self.first_run:
            # Get the list of files to be copied only once, at the first invocation of
            # the generator. Wrap in a try block in case the list does not exist.
            try:
                copy_list += weeutil.weeutil.option_as_list(self.skin_dict['CopyGenerator']['copy_once'])
            except KeyError:
                pass

        # Get the list of files to be copied everytime. Again, wrap in a try block.
        try:
            copy_list += weeutil.weeutil.option_as_list(self.skin_dict['CopyGenerator']['copy_always'])
        except KeyError:
            pass

        # Change directory to the skin subdirectory:
        os.chdir(os.path.join(self.config_dict['WEEWX_ROOT'],
                              self.skin_dict['SKIN_ROOT'],
                              self.skin_dict['skin']))
        # Figure out the destination of the files
        html_dest_dir = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     self.skin_dict['HTML_ROOT'])
        
        # The copy list can contain wildcard characters. Go through the
        # list globbing any character expansions
        ncopy = 0
        for pattern in copy_list:
            # Glob this pattern; then go through each resultant filename:
            for _file in glob.glob(pattern):
                # Final destination is the join of the html destination directory
                # and any relative subdirectory on the filename:
                dest_dir = os.path.join(html_dest_dir, os.path.dirname(_file))
                # Make the destination directory, wrapping it in a try block in
                # case it already exists:
                try:
                    os.makedirs(dest_dir)
                except OSError:
                    pass
                # This version of copy does not copy over modification time,
                # so it will look like a new file, causing it to be (for example)
                # ftp'd to the server:
                shutil.copy(_file, dest_dir)
                ncopy += 1
        
        syslog.syslog(syslog.LOG_DEBUG, "reportengine: copied %d files to %s" % (ncopy, html_dest_dir))
        

class CachedReportGenerator(ReportGenerator):
    """Report generator that can cache archive and stats database connections."""
    
    def start(self):
        self._initArchiveCache()
        self._initStatsCache()
        self.run()
    
    def finalize(self):
        self._closeStatsCache()
        self._closeArchiveCache()

    def _initArchiveCache(self):
        self.archive_cache = {}
        
    def _closeArchiveCache(self):
        try:
            for archive in self.archive_cache.values():
                try:
                    archive.close()
                    del archive
                except:
                    pass
        except:
            pass
        self.archive_cache = {}
            
    def _getArchive(self, archive_name):
        if archive_name not in self.archive_cache:
            archive_dict = self.config_dict['Databases'][archive_name]
            self.archive_cache[archive_name] = weewx.archive.Archive.open(archive_dict)
        return self.archive_cache[archive_name]
        
    def _initStatsCache(self):
        self.stats_cache = {}
        
    def _closeStatsCache(self):
        try:
            for stats in self.stats_cache.values():
                try:
                    stats.close()
                    del stats
                except:
                    pass
        except:
            pass
        self.stats_cache = {}
            
    def _getStats(self, stats_name):
        if stats_name not in self.stats_cache:
            stats_dict = self.config_dict['Databases'][stats_name]
            self.stats_cache[stats_name] = weewx.stats.StatsDb.open(stats_dict)
        return self.stats_cache[stats_name]
