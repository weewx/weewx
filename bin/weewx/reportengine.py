#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Engine for generating reports"""

# System imports:
import ftplib
import glob
import os.path
import shutil
import socket
import sys
import syslog
import threading
import time
import traceback

# 3rd party imports:
import configobj

# Weewx imports:
import weeutil.weeutil
from weeutil.weeutil import to_bool
import weewx.manager

#===============================================================================
#                    Class StdReportEngine
#===============================================================================

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
        
    def run(self):
        """This is where the actual work gets done.
        
        Runs through the list of reports. """
        
        if self.gen_ts:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for time %s" % 
                          weeutil.weeutil.timestamp_to_string(self.gen_ts))
        else:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for latest time in the database.")

        # Iterate over each requested report
        for report in self.config_dict['StdReport'].sections:
            
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running report %s" % report)
            
            # Figure out where the configuration file is for the skin used for
            # this report:
            skin_config_path = os.path.join(self.config_dict['WEEWX_ROOT'],
                                            self.config_dict['StdReport']['SKIN_ROOT'],
                                            self.config_dict['StdReport'][report].get('skin', 'Standard'),
                                            'skin.conf')
            # Retrieve the configuration dictionary for the skin. Wrap it in
            # a try block in case we fail
            try :
                skin_dict = configobj.ConfigObj(skin_config_path, file_error=True)
                syslog.syslog(syslog.LOG_DEBUG, "reportengine: Found configuration file %s for report %s" %
                              (skin_config_path, report))
            except IOError, e:
                syslog.syslog(syslog.LOG_ERR, "reportengine: Cannot read skin configuration file %s for report %s: %s" % (skin_config_path, report, e))
                syslog.syslog(syslog.LOG_ERR, "        ****  Report ignored...")
                continue
            except SyntaxError, e:
                syslog.syslog(syslog.LOG_ERR, "reportengine: Failed to read skin configuration file %s for report %s: %s" % (skin_config_path, report, e))
                syslog.syslog(syslog.LOG_ERR, "        ****  Report ignored...")
                continue

            # Add the default database binding:
            skin_dict.setdefault('data_binding', 'wx_binding')

            # If not already specified, default to logging each successful run
            skin_dict.setdefault('log_success', True)

            # Inject any overrides the user may have specified in the
            # weewx.conf configuration file for all reports:
            for scalar in self.config_dict['StdReport'].scalars:
                skin_dict[scalar] = self.config_dict['StdReport'][scalar]
            
            # Now inject any overrides for this specific report:
            skin_dict.merge(self.config_dict['StdReport'][report])
            
            # Finally, add the report name:
            skin_dict['REPORT_NAME'] = report
            
            for generator in weeutil.weeutil.option_as_list(skin_dict['Generators'].get('generator_list')):

                try:
                    # Instantiate an instance of the class.
                    obj = weeutil.weeutil._get_object(generator)(self.config_dict, 
                                                                 skin_dict, 
                                                                 self.gen_ts, 
                                                                 self.first_run,
                                                                 self.stn_info)
                except Exception, e:
                    syslog.syslog(syslog.LOG_CRIT, "reportengine: Unable to instantiate generator %s." % generator)
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % e)
                    weeutil.weeutil.log_traceback("        ****  ")
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator ignored...")
                    traceback.print_exc()
                    continue
    
                try:
                    # Call its start() method
                    obj.start()
                    
                except Exception, e:
                    # Caught unrecoverable error. Log it, continue on to the next generator.
                    syslog.syslog(syslog.LOG_CRIT, "reportengine: Caught unrecoverable exception in generator %s" % (generator,))
                    syslog.syslog(syslog.LOG_CRIT, "        ****  %s" % str(e))
                    weeutil.weeutil.log_traceback("        ****  ")
                    syslog.syslog(syslog.LOG_CRIT, "        ****  Generator terminated...")
                    traceback.print_exc()
                    continue
                    
                finally:
                    obj.finalize()
        
#===============================================================================
#                    Class ReportGenerator
#===============================================================================


class ReportGenerator(object):
    """Base class for all report generators."""
    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info):
        self.config_dict = config_dict
        self.skin_dict   = skin_dict
        self.gen_ts      = gen_ts
        self.first_run   = first_run
        self.stn_info    = stn_info
        self.db_binder   = weewx.manager.DBBinder(self.config_dict)
        
    def start(self):
        self.run()
    
    def run(self):
        pass
    
    def finalize(self):
        self.db_binder.close()

#===============================================================================
#                    Class FtpGenerator
#===============================================================================

class FtpGenerator(ReportGenerator):
    """Class for managing the "FTP generator".
    
    This will ftp everything in the public_html subdirectory to a webserver."""

    def run(self):
        import weeutil.ftpupload

        # determine how much logging is desired
        log_success = to_bool(self.skin_dict.get('log_success', True))

        t1 = time.time()
        if self.skin_dict.has_key('HTML_ROOT'):
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict['HTML_ROOT'])
        else:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.config_dict['StdReport']['HTML_ROOT'])

        try:
            ftpData = weeutil.ftpupload.FtpUpload(server      = self.skin_dict['server'],
                                                  user        = self.skin_dict['user'],
                                                  password    = self.skin_dict['password'],
                                                  local_root  = local_root,
                                                  remote_root = self.skin_dict['path'],
                                                  port        = int(self.skin_dict.get('port', 21)),
                                                  name        = self.skin_dict['REPORT_NAME'],
                                                  passive     = to_bool(self.skin_dict.get('passive', True)),
                                                  max_tries   = int(self.skin_dict.get('max_tries', 3)),
                                                  secure      = to_bool(self.skin_dict.get('secure_ftp', False)),
                                                  debug       = int(self.skin_dict.get('debug', 0)))
        except Exception:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: FTP upload not requested. Skipped.")
            return

        try:
            N = ftpData.run()
        except (socket.timeout, socket.gaierror, ftplib.all_errors, IOError), e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "reportengine: Caught exception %s in FtpGenerator; %s." % (cl, e))
            weeutil.weeutil.log_traceback("        ****  ")
            return
        
        t2= time.time()
        if log_success:
            syslog.syslog(syslog.LOG_INFO, """reportengine: ftp'd %d files in %0.2f seconds""" % (N, (t2-t1)))
            
                
#===============================================================================
#                    Class RsynchGenerator
#===============================================================================

class RsyncGenerator(ReportGenerator):
    """Class for managing the "rsync generator".
    
    This will rsync everything in the public_html subdirectory to a webserver."""

    def run(self):
        import weeutil.rsyncupload
        # We don't try to collect performance statistics about rsync, because rsync
        # will report them for us.  Check the debug log messages.
        try:
            if self.skin_dict.has_key('HTML_ROOT'):
                html_root = self.skin_dict['HTML_ROOT']
            else:
                html_root = self.config_dict['StdReport']['HTML_ROOT']
            rsyncData = weeutil.rsyncupload.RsyncUpload(
                local_root  = os.path.join(self.config_dict['WEEWX_ROOT'], html_root),
                remote_root = self.skin_dict['path'],
                server      = self.skin_dict['server'],
                user        = self.skin_dict.get('user'),
                port        = self.skin_dict.get('port'),
                ssh_options = self.skin_dict.get('ssh_options'),
                compress    = to_bool(self.skin_dict.get('compress', False)),
                delete      = to_bool(self.skin_dict.get('delete', False)),
                log_success = to_bool(self.skin_dict.get('log_success', True)))
        except Exception:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: rsync upload not requested. Skipped.")
            return

        try:
            rsyncData.run()
        except (IOError), e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "reportengine: Caught exception %s in RsyncGenerator; %s." % (cl, e))
            
                
#===============================================================================
#                    Class CopyGenerator
#===============================================================================

class CopyGenerator(ReportGenerator):
    """Class for managing the 'copy generator.'
    
    This will copy files from the skin subdirectory to the public_html
    subdirectory."""
    
    def run(self):
        copy_dict = self.skin_dict['CopyGenerator']
        # determine how much logging is desired
        log_success = to_bool(copy_dict.get('log_success', True))
        
        copy_list = []

        if self.first_run:
            # Get the list of files to be copied only once, at the first invocation of
            # the generator. Wrap in a try block in case the list does not exist.
            try:
                copy_list += weeutil.weeutil.option_as_list(copy_dict['copy_once'])
            except KeyError:
                pass

        # Get the list of files to be copied everytime. Again, wrap in a try block.
        try:
            copy_list += weeutil.weeutil.option_as_list(copy_dict['copy_always'])
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

        if log_success:
            syslog.syslog(syslog.LOG_INFO, "reportengine: copied %d files to %s" % (ncopy, html_dest_dir))
