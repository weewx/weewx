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

import os.path
import syslog
import threading

import weewx.archive
import weewx.genfiles
import weewx.genimages
import weewx.ftpdata
import weeutil.weeutil

class StdReportEngine(threading.Thread):
    """Reporting engine for weewx.
    
    This engine runs zero or more reports. Each report is a class, which
    should inherit from class StdReport. The initializer for the class
    will be handed a variable bound to this engine.
    The work for the report should be done in member function run().
    
    It inherits from threading.Thread, so it will be run in a separate
    thread.
    
    See below for examples of reports.
    """
    
    def __init__(self, config_dict, gen_ts = None):
        """Initializer for the report engine. 
        
        The only argument is the configuration dictionary."""
        threading.Thread.__init__(self, name="ReportThread")
        self.config_dict = config_dict
        self.gen_ts = gen_ts
        
    def setup(self):
        if self.gen_ts:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for time %s" % 
                          weeutil.weeutil.timestamp_to_string(self.gen_ts))
        else:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running reports for latest time in the database.")
        
    
    def run(self):
        """This is where the actual work gets done.
        
        Runs through the list of reports."""
        
        self.setup()
        
        for report in self.config_dict['Reports'].sections:
            
            report_config_path = os.path.join(self.config_dict['Station']['WEEWX_ROOT'],
                                              self.config_dict['Reports']['REPORT_ROOT'],
                                              self.config_dict['Reports'][report].get('skin', 'standard'),
                                              'skin.conf')
            print "report_config_path=", report_config_path
            try :
                report_dict = configobj.ConfigObj(report_config_path, file_error=True)
                syslog.syslog(syslog.LOG_DEBUG, "reportengine: Found configuration file %s for report %s" % (report_config_path, report))
                report_dict.merge(self.config_dict['Reports'][report])
            except IOError:
                report_dict = None
                syslog.syslog(syslog.LOG_DEBUG, "reportengine: No report configuration file for report %s" % report)
                report_dict = self.config_dict['Reports'][report]
            print report_dict['Images']['image_width']
                
#            try:
#            
#                for report in report_list:
#                    syslog.syslog(syslog.LOG_DEBUG, "reportengine: Running report %s" % skin)
#                    # Instantiate an instance of the class
#                    obj = weeutil.weeutil._get_object(report, self)
#                    # Call its start() method
#                    obj.start()
#    
#            except Exception, ex:
#                # Caught unrecoverable error. Log it, exit
#                syslog.syslog(syslog.LOG_CRIT, "reportengine: Caught unrecoverable exception while running report %s" % report)
#                syslog.syslog(syslog.LOG_CRIT, "reportengine: ** %s" % ex)
#                syslog.syslog(syslog.LOG_CRIT, "reportengine: ** Thread exiting.")
#                # Reraise the exception (this will eventually cause the thread to terminate)
#                raise

class Report(object):
    """Base class for all reports."""
    def __init__(self, engine):
        self.engine = engine
        
    def setup(self):
        pass

    def start(self):
        self.run()
        
class SkinReport(object):
    pass

class MonthlySummary(Report):
    """Creates monthly reports, such as NOAA reports"""
    
class YearlySummary(Report):
    """Creates yearly reports, such as NOAA reports."""
    
#class ImageGen(Report):
#    """Creates images (plots) used by reports."""
    
class StatsToDateReport(Report):
    """Creates snapshot statistical reports."""
    
class FileGen(Report):
    """ Generates HTML and NOAA files."""
    def __init__(self, engine):
        Report.__init__(self, engine)
        
    def run(self):
        # Open up the main database archive
        archiveFilename = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'], 
                                       self.engine.config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
    
        stop_ts    = archive.lastGoodStamp() if self.engine.gen_ts is None else self.engine.gen_ts
        start_ts   = archive.firstGoodStamp()
        currentRec = archive.getRecord(stop_ts, weewx.units.getUnitTypeDict(self.engine.config_dict))
        
        genFiles = weewx.genfiles.GenFiles(self.engine.config_dict)
            
        # Generate the NOAA summaries:
        genFiles.generateNoaa(start_ts, stop_ts)
        # Generate the HTML pages
        genFiles.generateHtml(currentRec, stop_ts)
        
class ImageGen(Report):
    """Generates all images listed in the configuration dictionary."""
    
    def __init__(self, engine):
        Report.__init__(self, engine)
        
    def run(self):
        # Open up the main database archive
        archiveFilename = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'], 
                                       self.engine.config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
    
        stop_ts = archive.lastGoodStamp() if self.engine.gen_ts is None else self.engine.gen_ts

        # Generate any images
        genImages = weewx.genimages.GenImages(self.engine.config_dict)
        genImages.genImages(archive, stop_ts)
        
class Ftp(Report):
    """Ftps everything in the public_html subdirectory to a webserver."""
    def __init__(self, engine):
        Report.__init__(self, engine)
        
    def run(self):
        # Check to see if there is an 'FTP' section in the configuration
        # dictionary and that all necessary options are present. 
        # If so, FTP the data up to a server.
        ftp_dict = self.engine.config_dict.get('FTP')
        if ftp_dict and (ftp_dict.has_key('server')   and 
                         ftp_dict.has_key('password') and 
                         ftp_dict.has_key('user')     and
                         ftp_dict.has_key('path')):
            html_dir = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'],
                                    self.engine.config_dict['HTML']['html_root'])
            ftpData = weewx.ftpdata.FtpData(source_dir = html_dir, **ftp_dict)
            ftpData.ftpData()
                
if __name__ == '__main__':
    
    # ===============================================================================
    # This module can be called as a main program to generate reports, etc.,
    # that are current as of the last archive record in the archive database.
    # ===============================================================================
    import sys
    import configobj
    import socket

    def gen_all(config_path, gen_ts = None):
        
        weewx.debug = 1
        syslog.openlog('reportengine', syslog.LOG_PID|syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        socket.setdefaulttimeout(10)
        
        t = StdReportEngine(config_dict, gen_ts)
        t.start()
        t.join()

        
    if len(sys.argv) < 2 :
        print "Usage: reportengine.py path-to-configuration-file [timestamp-to-be-generated]"
        exit()
    gen_ts = int(sys.argv[2]) if len(sys.argv)>=3 else None
        
    gen_all(sys.argv[1], gen_ts)
