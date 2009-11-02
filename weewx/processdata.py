#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Main function for generating reports and HTML files"""

import os.path
import time

import weewx.archive
import weewx.stats
import weewx.station
import weewx.genfiles
import weewx.genimages
import weewx.ftpdata
import weeutil.weeutil
import weeutil.Almanac

def processData(config_dict, stop_ts = None):
    """
    For a given time, this function calculates statistics for the day, week, month, year, 
    and rain year. It passes this information, along with some station information,
    to the HTML templating engine, as well as to the image (plot) generation engine.
    
    stop_ts: The time of the last data archive to be used. [Optional. Default is
    to use the last data in the archive database.]
    """

    # Open up the main database archive
    archiveFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                   config_dict['Archive']['archive_file'])
    archive = weewx.archive.Archive(archiveFilename)

    # If a time has not been given, use the last timestamp in the main
    # database archive.
    if not stop_ts:
        stop_ts = archive.lastGoodStamp()
    start_ts = archive.firstGoodStamp()

    currentRec = archive.getRecord(stop_ts)
    
    genFiles = weewx.genfiles.GenFiles(config_dict)
        
    # Generate the NOAA summaries:
    genFiles.generateNoaa(start_ts, stop_ts)
    # Generate the HTML pages
    genFiles.generateHtml(currentRec, stop_ts)

    # Generate any images
    genImages = weewx.genimages.GenImages(config_dict)
    genImages.genImages(archive, stop_ts)
    
    # Check to see if there is an 'FTP' section in the configuration
    # dictionary. If so, FTP the data up to a server.
    ftp_dict = config_dict.get('FTP')
    if ftp_dict:
        html_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                config_dict['HTML']['html_root'])
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
        processData(config_dict)

        
    if len(sys.argv) < 2 :
        print "Usage: processdata.py path-to-configuration-file"
        exit()
        
    gen_all(sys.argv[1])
