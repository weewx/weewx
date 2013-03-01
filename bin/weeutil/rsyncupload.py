#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of ftpupload.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""For uploading files to a remove server via FTP"""

import os
import errno
import sys
import subprocess
import syslog

class RsyncUpload(object):
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of what files have changed, and only updates changed files."""

    def __init__(self, local_root, remote_root,
                 server, user=None, delete=False):
        """Initialize an instance of RsyncUpload.
        
        After initializing, call method run() to perform the upload.
        
        server: The remote server to which the files are to be uploaded.
        
        user: The user name that is to be used. [Optional, maybe]

        delete: delete remote files that don't match with local files. Use
        with caution.  [Optional.  Default is False.]
        """
        self.local_root  = os.path.normpath(local_root)
        self.remote_root = os.path.normpath(remote_root)
        self.server      = server
        self.user        = user
        self.delete      = delete

    def run(self):
        """Perform the actual upload."""

        # If the source path ends with a slash, rsync interprets
        # that as a request to copy all the directory's *contents*,
        # whereas if it doesn't, it copies the entire directory.
        # We want the former, so make it end with a slash.
        if self.local_root.endswith(os.sep):
            rsynclocalspec = self.local_root
        else:
            rsynclocalspec = self.local_root + os.sep

        if self.user is not None and len(self.user.strip()) > 0:
            rsyncremotespec = "%s@%s:%s" % (self.user, self.server, self.remote_root)
        else:
            rsyncremotespec = "%s:%s" % (self.server, self.remote_root)
        
        cmd = ['rsync']
        # archive means:
        #    recursive, copy symlinks as symlinks, preserve permissions,
        #    preserve modification times, preserve group and owner,
        #    preserve device files and special files, but not ACLs,
        #    no hardlinks, and no extended attributes
        cmd.extend(["--archive"])
        # Remove files remotely when they're removed locally
        cmd.extend(["--stats"])
        if self.delete:
            cmd.extend(["--delete"])
        cmd.extend(["-e", "ssh"])
        cmd.extend([rsynclocalspec])
        cmd.extend([rsyncremotespec])
        
        try:
            syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync invocation: %s" % " ".join(cmd))
            output = subprocess.check_output(cmd)
            stroutput = output.encode("utf-8")
            syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync reported:\n%s" % stroutput)
        except OSError, e:
            if e.errno == errno.ENOENT:
                syslog.syslog(syslog.LOG_ERR, "rsyncupload: rsync does not appear to be installed on this system. (errno %d, \"%s\")" % (e.errno, e.strerror))
            raise
        
        
if __name__ == '__main__':
    
    import weewx
    import configobj
    
    weewx.debug = 1
    syslog.openlog('wee_rsyncupload', syslog.LOG_PID|syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

    if len(sys.argv) < 2 :
        print """Usage: rsyncupload.py path-to-configuration-file [path-to-be-rsync'd]"""
        exit()
        
    try :
        config_dict = configobj.ConfigObj(sys.argv[1], file_error=True)
    except IOError:
        print "Unable to open configuration file ", sys.argv[1]
        raise

    if len(sys.argv) == 2:
        try:
            rsync_dir = os.path.join(config_dict['WEEWX_ROOT'],
                                   config_dict['StdReport']['HTML_ROOT'])
        except KeyError:
            print "No HTML_ROOT in configuration dictionary."
            exit()
    else:
        rsync_dir = sys.argv[2]

        
    rsync_upload = RsyncUpload(
                           rsync_dir,
                           config_dict['StdReport']['RSYNC']['path'],
                           config_dict['StdReport']['RSYNC']['server'],
                           config_dict['StdReport']['RSYNC']['user'])
    rsync_upload.run()
    
