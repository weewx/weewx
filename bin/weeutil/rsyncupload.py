#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of ftpupload.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#
"""For uploading files to a remove server via Rsync"""

import os
import errno
import sys
import subprocess
import syslog
import time

class RsyncUpload(object):
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of what files have changed, and only updates changed files."""

    def __init__(self, local_root, remote_root,
                 server, user=None, delete=False, port=None):
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
        self.port        = port

    def run(self):
        """Perform the actual upload."""

        t1 = time.time()
        
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
        
        if self.port is not None and len(self.port.strip()) > 0:
            rsyncsshstring = "ssh -p %s" % (self.port,)
        else:
            rsyncsshstring = "ssh"

        cmd = ['rsync']
        # archive means:
        #    recursive, copy symlinks as symlinks, preserve permissions,
        #    preserve modification times, preserve group and owner,
        #    preserve device files and special files, but not ACLs,
        #    no hardlinks, and no extended attributes
        cmd.extend(["--archive"])
        # provide some stats on the transfer
        cmd.extend(["--stats"])
        # Remove files remotely when they're removed locally
        if self.delete:
            cmd.extend(["--delete"])
        cmd.extend(["-e %s" % rsyncsshstring])
        cmd.extend([rsynclocalspec])
        cmd.extend([rsyncremotespec])
        
        try:
            rsynccmd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
            stdout = rsynccmd.communicate()[0]
            stroutput = stdout.encode("utf-8").strip()
        except OSError, e:
            if e.errno == errno.ENOENT:
                syslog.syslog(syslog.LOG_ERR, "rsyncupload: rsync does not appear to be installed on this system. (errno %d, \"%s\")" % (e.errno, e.strerror))
            raise
        
        # we have some output from rsync so generate an appropriate message
        if stroutput.find('rsync error:') < 0:
            # no rsync error message so parse rsync --stats results
            rsyncinfo = {}
            for line in iter(stroutput.splitlines()):
                if line.find(':') >= 0:
                    (n,v) = line.split(':', 1)
                    rsyncinfo[n.strip()] = v.strip()
            # get number of files and bytes transferred and produce an
            # appropriate message
            try:
                N = rsyncinfo['Number of files transferred']
                Nbytes = rsyncinfo['Total transferred file size']
                if N is not None and Nbytes is not None:
                    rsync_message = "rsync'd %d files (%s) in %%0.2f seconds" % (int(N), Nbytes)
                else:
                    rsync_message = "rsync executed in %0.2f seconds"
            except:
                rsync_message = "rsync executed in %0.2f seconds"
        else:
            # suspect we have an rsync error so tidy stroutput
            # and display a message
            stroutput = stroutput.replace("\n", ". ")
            stroutput = stroutput.replace("\r", "")
            syslog.syslog(syslog.LOG_INFO, "rsyncupload: rsync reported errors: %s" % stroutput)
            rsync_message = "rsync executed in %0.2f seconds"
        
        t2= time.time()
        syslog.syslog(syslog.LOG_INFO, "rsyncupload: "  + rsync_message % (t2-t1))
        
        
if __name__ == '__main__':
    
    import weewx
    import configobj
    
    weewx.debug = 1
    syslog.openlog('rsyncupload', syslog.LOG_PID|syslog.LOG_CONS)
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
                           config_dict['StdReport']['RSYNC']['user'],
                           config_dict['StdReport']['RSYNC']['port'])
    rsync_upload.run()
    
