#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of ftpupload.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    3-Jan-2021. Refactored by tk
#    3-Apr-2024. Added option rsync_options.
#    17-Apr-2026. Added option record_stats to capture upload metrics.
#
#    See the file LICENSE.txt for your full rights.
#
"""For uploading files to a remote server via Rsync"""

import errno
import logging
import os
import subprocess
import sys
import time
import threading

from weeutil.weeutil import option_as_list

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level store for rsync stats, shared with RsyncMetricsService.
# Protected by a lock since RsyncUpload runs in the StdReport thread and
# RsyncMetricsService.new_archive_record() runs in the main weewx thread.
# ---------------------------------------------------------------------------

_stats_lock = threading.Lock()
_stats = {}


def get_rsync_stats():
    """Return a copy of the most recently recorded rsync stats, or {}."""
    with _stats_lock:
        return dict(_stats)


def _set_rsync_stats(files, nbytes, duration):
    """Store rsync stats. Called internally after a successful upload."""
    with _stats_lock:
        _stats.update({
            'rsyncFiles':    files,
            'rsyncBytes':    nbytes,
            'rsyncDuration': duration,
            'timestamp':     time.time(),
        })


def _clear_rsync_stats():
    """Clear stats after a failed upload so stale values are not injected."""
    with _stats_lock:
        _stats.clear()


class RsyncUpload:
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of what files have changed, and only updates changed files."""

    def __init__(self, local_root, remote_root,
                 server, user=None, delete=False, port=None,
                 ssh_options=None, rsync_options=None,
                 compress=False,
                 log_success=True, log_failure=True,
                 timeout=None,
                 record_stats=False):
        """Initialize an instance of RsyncUpload.
        
        After initializing, call method run() to perform the upload.

        Args:
            local_root (str): Path to the local directory to be transferred. Required.
            remote_root (str): The root of its destination. Required.
            server (str): The remote server to which the files are to be uploaded.
            user (str|None): The username that is to be used. [Optional, maybe]
            delete (bool): delete remote files that don't match with local files.
                Use with caution.
            port (int|None): The port to be used. Default is to use the default ssh port.
            ssh_options (str|None): Any extra options to be passed on to the ssh command.
            rsync_options(list[str]|None): Any extra options to be passed to the rsync command.
            log_success (bool): True to log any successful transfers.
            log_failure (bool): True to log any unsuccessful transfers
            timeout (int|none): How long to wait for giving up on a transfer.
            record_stats (bool): True to record transfer statistics (file count, bytes,
                duration) in the module-level store for use by RsyncMetricsService.
                When True, stats are available via get_rsync_stats() after each
                successful upload and are cleared on failure so stale values are
                never injected into archive records. Default is False.
        """
        self.local_root = os.path.normpath(local_root)
        self.remote_root = os.path.normpath(remote_root)
        self.server = server
        self.user = user
        self.delete = delete
        self.port = port
        self.ssh_options = ssh_options
        self.rsync_options = rsync_options
        self.compress = compress
        self.log_success = log_success
        self.log_failure = log_failure
        self.timeout = timeout
        self.record_stats = record_stats

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
        if self.rsync_options:
            cmd += option_as_list(self.rsync_options)
        cmd.extend(["-e"])
        cmd.extend([rsyncsshstring])
        cmd.extend([rsynclocalspec])
        cmd.extend([rsyncremotespec])

        try:
            log.debug("rsyncupload: cmd: [%s]", cmd)
            rsynccmd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            stdout = rsynccmd.communicate()[0]
            stroutput = stdout.decode("utf-8").strip()
        except OSError as e:
            if e.errno == errno.ENOENT:
                log.error("rsync does not appear to be installed on "
                          "this system. (errno %d, '%s')" % (e.errno, e.strerror))
            if self.record_stats:
                _clear_rsync_stats()
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

            # Record stats if requested. We reuse the already-parsed rsyncinfo
            # dict if available, otherwise re-parse from stroutput.
            if self.record_stats:
                try:
                    if 'rsyncinfo' not in dir():
                        kv_list = [line.split(':', 1) for line in stroutput.splitlines() if ':' in line]
                        rsyncinfo = {k.strip(): v.strip() for k, v in kv_list}
                    N = rsyncinfo.get('Number of regular files transferred',
                                      rsyncinfo.get('Number of files transferred'))
                    Nbytes = rsyncinfo.get('Total transferred file size')
                    if N is not None and Nbytes is not None:
                        # Strip any trailing annotations e.g. "28 (reg: 27, dir: 1)"
                        files = int(N.split()[0].replace(',', ''))
                        nbytes = int(Nbytes.split()[0].replace(',', ''))
                        _set_rsync_stats(files, nbytes, t2 - t1)
                        log.debug("rsyncupload: recorded stats: files=%d bytes=%d duration=%.2fs",
                                  files, nbytes, t2 - t1)
                    else:
                        log.debug("rsyncupload: record_stats=True but could not parse "
                                  "file count or byte count from rsync output")
                        _clear_rsync_stats()
                except (ValueError, AttributeError) as e:
                    log.warning("rsyncupload: record_stats parse error: %s", e)
                    _clear_rsync_stats()
        else:
            # rsync error message found. If requested, log it
            if self.log_failure:
                log.error("rsync reported errors. Original command: %s", cmd)
                for line in stroutput.splitlines():
                    log.error("**** %s", line)
            # Clear stats so a previous successful run's values are not
            # injected into the archive record as if this run succeeded.
            if self.record_stats:
                _clear_rsync_stats()
