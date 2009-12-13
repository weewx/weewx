#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

import os
import time
import syslog
import socket

import upload

class FtpData(object):
    """Synchronize local files with the web server"""

    def __init__(self, source_dir, server, user, password, path, passive = 1, max_retries = 3):
        self.source_dir = source_dir
        self.server     = server
        self.user       = user
        self.password   = password
        self.path       = path
        self.passive    = int(passive)
        self.max_retries= int(max_retries)

    def ftpData(self):
        """FTP the contents of the HTML directory to your web server. It uses
        module 'upload' to do the heavy lifting.
        """
        t1 = time.time()
    
        # While 'upload' is a nice simple utility, it assumes that the
        # root directory is the current directory. So, change directory to there:
        os.chdir(self.source_dir)
        
        # Now we can use the utility
        upstr = upload.Upstreamer(self.server, self.user, self.password, self.path, 
                                  self.passive, self.max_retries)
        finder = upload.Finder()
        finder.find_all_files()
        try:
            n_uploaded = upstr.upstream(finder.get_new_files())
            finder.reset_stamp(time.time())
            finder.save()
            
            t2=time.time()
            syslog.syslog(syslog.LOG_INFO, 
                          "ftp: uploaded %d files in %0.2f seconds" % (n_uploaded, (t2-t1)))
        except socket.error, e:
            syslog.syslog(syslog.LOG_ERR, "ftp: FTP failed. Reason: %s" % e)

if __name__ == '__main__':
    import configobj
    
    def test(config_path):
        
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        ftp_dict = config_dict.get('FTP')
        if ftp_dict:
            html_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                    config_dict['HTML']['html_root'])
            ftpData = FtpData(source_dir = html_dir, **ftp_dict)
            ftpData.ftpData()
        else:
            print "No FTP section in configuration file. Nothing done."

    test('/home/weewx/weewx.conf')
        
