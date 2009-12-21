#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
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
    
    def __init__(self, config_dict):
        """Initializer for the report engine. 
        
        The only argument is the configuration dictionary."""
        threading.Thread.__init__(self, name="ReportThread")
        self.config_dict = config_dict
        
        self.report_list = self.config_dict['Engines']['ReportEngine'].get('report_list', 
                                                                           ['weewx.reportengine.FileGen', 
                                                                            'weewx.reportengine.ImageGen',
                                                                            'weewx.reportengine.Ftp'])
        syslog.syslog(syslog.LOG_DEBUG, "reportengine: List of reports to be run:")
        for report in self.report_list:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: ** %s" % report)
            
    def run(self):
        """This is where the actual work gets done.
        
        Runs through the list of report classes, instantiating each one,
        then calling its "start()" method."""
        
        # Put the whole thing in a try block so we can log any exceptions that
        # might bubble up
        try:
        
            for report in self.report_list:
                # Instantiate an instance of the class
                obj = weeutil.weeutil._get_object(report, self)
                # Call its start() method
                obj.start()

        except Exception, ex:
            # Caught unrecoverable error. Log it, exit
            syslog.syslog(syslog.LOG_CRIT, "reportengine: Caught unrecoverable exception while running report %s" % report)
            syslog.syslog(syslog.LOG_CRIT, "reportengine: ** %s" % ex)
            syslog.syslog(syslog.LOG_CRIT, "reportengine: ** Thread exiting.")
            # Reraise the exception (this will eventually cause the thread to terminate)
            raise

class Report(object):
    """Base class for all reports."""
    def __init__(self, engine):
        self.engine = engine

    def start(self):
        self.run()

class FileGen(Report):
    """ Generates HTML and NOAA files."""
    def __init__(self, engine):
        Report.__init__(self, engine)
        
    def run(self):
        # Open up the main database archive
        archiveFilename = os.path.join(self.engine.config_dict['Station']['WEEWX_ROOT'], 
                                       self.engine.config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
    
        stop_ts    = archive.lastGoodStamp()
        start_ts   = archive.firstGoodStamp()
        currentRec = archive.getRecord(stop_ts)
        
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
    
        stop_ts = archive.lastGoodStamp()

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

    def gen_all(config_path):
        
        weewx.debug = 1
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        socket.setdefaulttimeout(10)
        
        t = StdReportEngine(config_dict)
        t.start()
        t.join()

        
    if len(sys.argv) < 2 :
        print "Usage: processdata.py path-to-configuration-file"
        exit()
        
    gen_all(sys.argv[1])
