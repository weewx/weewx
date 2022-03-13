#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of ftpupload.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    Refactored by tk 3-Jan-2021
#
#    See the file LICENSE.txt for your full rights.
#
"""For uploading files to a remove server via Rsync"""

from __future__ import absolute_import
from __future__ import print_function

import errno
import logging
import os
import subprocess
import sys
import time

log = logging.getLogger(__name__)


class RsyncUpload(object):
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of what files have changed, and only updates changed files."""

    def __init__(self, local_root, remote_root,
                 server, user=None, delete=False, port=None,
                 ssh_options=None, compress=False,
                 log_success=True, log_failure=True,
                 timeout=None):
        """Initialize an instance of RsyncUpload.
        
        After initializing, call method run() to perform the upload.
        
        server: The remote server to which the files are to be uploaded.
        
        user: The user name that is to be used. [Optional, maybe]

        delete: delete remote files that don't match with local files. Use
        with caution.  [Optional.  Default is False.]
        """
        self.local_root = os.path.normpath(local_root)
        self.remote_root = os.path.normpath(remote_root)
        self.server = server
        self.user = user
        self.delete = delete
        self.port = port
        self.ssh_options = ssh_options
        self.compress = compress
        self.log_success = log_success
        self.log_failure = log_failure
        self.timeout = timeout

    def run(self):
        """Perform the actual upload."""

        t1 = time.time()

        # If the source path ends with a slash, rsync interprets
        # that as a request to copy all the directory's *contents*,
        # whereas if it doesn't, it copies the entire directory.
        # We want the former, so make it end with a slash.
        # Note: Don't add the slash if local_root isn't a directory
        if self.local_root.endswith(os.sep) or not os.path.isdir(self.local_root):
            rsynclocalspec = self.local_root
        else:
            rsynclocalspec = self.local_root + os.sep

        if self.user:
            rsyncremotespec = "%s@%s:%s" % (self.user, self.server, self.remote_root)
        else:
            rsyncremotespec = "%s:%s" % (self.server, self.remote_root)

        if self.port:
            rsyncsshstring = "ssh -p %d" % self.port
        else:
            rsyncsshstring = "ssh"

        if self.ssh_options:
            rsyncsshstring = rsyncsshstring + " " + self.ssh_options

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
        if self.compress:
            cmd.extend(["--compress"])
        if self.timeout is not None:
            cmd.extend(["--timeout=%s" % self.timeout])
        cmd.extend(["-e"])
        cmd.extend([rsyncsshstring])
        cmd.extend([rsynclocalspec])
        cmd.extend([rsyncremotespec])

        try:
            log.debug("rsyncupload: cmd: [%s]" % cmd)
            rsynccmd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            stdout = rsynccmd.communicate()[0]
            stroutput = stdout.decode("utf-8").strip()
        except OSError as e:
            if e.errno == errno.ENOENT:
                log.error("rsync does not appear to be installed on "
                          "this system. (errno %d, '%s')" % (e.errno, e.strerror))
            raise

        t2 = time.time()

        # we have some output from rsync so generate an appropriate message
        if 'rsync error' not in stroutput:
            # No rsync error message. Parse the status message for useful information.
            if self.log_success:
                # Create a dictionary of message and their values. kv_list is a list of
                # (key, value) tuples.
                kv_list = [line.split(':', 1) for line in stroutput.splitlines() if ':' in line]
                # Now convert to dictionary, while stripping the keys and values
                rsyncinfo = {k.strip(): v.strip() for k, v in kv_list}
                # Get number of files and bytes transferred, and produce an appropriate message
                N = rsyncinfo.get('Number of regular files transferred',
                                  rsyncinfo.get('Number of files transferred'))
                Nbytes = rsyncinfo.get('Total transferred file size')
                if N is not None and Nbytes is not None:
                    log.info("rsync'd %s files (%s) in %0.2f seconds", N.strip(),
                             Nbytes.strip(), t2 - t1)
                else:
                    log.info("rsync executed in %0.2f seconds", t2 - t1)
        else:
            # rsync error message found. If requested, log it
            if self.log_failure:
                log.error("rsync reported errors. Original command: %s", cmd)
                for line in stroutput.splitlines():
                    log.error("**** %s", line)


if __name__ == '__main__':
    import configobj

    import weewx
    import weeutil.logger

    weewx.debug = 1

    weeutil.logger.setup('rsyncupload', {})

    if len(sys.argv) < 2:
        print("""Usage: rsyncupload.py path-to-configuration-file [path-to-be-rsync'd]""")
        sys.exit(weewx.CMD_ERROR)

    try:
        config_dict = configobj.ConfigObj(sys.argv[1], file_error=True, encoding='utf-8')
    except IOError:
        print("Unable to open configuration file %s" % sys.argv[1])
        raise

    if len(sys.argv) == 2:
        try:
            rsync_dir = os.path.join(config_dict['WEEWX_ROOT'],
                                     config_dict['StdReport']['HTML_ROOT'])
        except KeyError:
            print("No HTML_ROOT in configuration dictionary.")
            sys.exit(1)
    else:
        rsync_dir = sys.argv[2]

    rsync_upload = RsyncUpload(rsync_dir, **config_dict['StdReport']['RSYNC'])
    rsync_upload.run()
