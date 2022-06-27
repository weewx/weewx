#
#    Copyright (c) 2009-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""For uploading files to a remove server via FTP"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import ftplib
import logging
import os
import sys
import time

from six.moves import cPickle

try:
    import hashlib
    has_hashlib=True
except ImportError:
    has_hashlib=False
    
log = logging.getLogger(__name__)


class FtpUpload(object):
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of when a file was last uploaded, so it is uploaded only
    if its modification time is newer."""

    def __init__(self, server,
                 user, password,
                 local_root, remote_root,
                 port=21,
                 name="FTP",
                 passive=True,
                 secure=False,
                 debug=0,
                 secure_data=True,
                 reuse_ssl=False,
                 encoding='utf-8',
                 ciphers=None):
        """Initialize an instance of FtpUpload.
        
        After initializing, call method run() to perform the upload.
        
        server: The remote server to which the files are to be uploaded.
        
        user,
        password : The user name and password that are to be used.
        
        name: A unique name to be given for this FTP session. This allows more
        than one session to be uploading from the same local directory. [Optional.
        Default is 'FTP'.]
        
        passive: True to use passive mode; False to use active mode. [Optional.
        Default is True (passive mode)]
        
        secure: Set to True to attempt an FTP over TLS (FTPS) session.
        
        debug: Set to 1 for extra debug information, 0 otherwise.
        
        secure_data: If a secure session is requested (option secure=True),
        should we attempt a secure data connection as well? This option is useful
        due to a bug in the Python FTP client library. See Issue #284. 
        [Optional. Default is True]

        reuse_ssl: Work around a bug in the Python library that closes ssl sockets that should
        be reused. See https://bit.ly/3dKq4JY [Optional. Default is False]

        encoding: The vast majority of FTP servers chat using UTF-8. However, there are a few
        oddballs that use Latin-1.

        ciphers: Explicitly set the cipher(s) to be used by the ssl sockets.
        """
        self.server = server
        self.user = user
        self.password = password
        self.local_root = os.path.normpath(local_root)
        self.remote_root = os.path.normpath(remote_root)
        self.port = port
        self.name = name
        self.passive = passive
        self.secure = secure
        self.debug = debug
        self.secure_data = secure_data
        self.reuse_ssl = reuse_ssl
        self.encoding = encoding
        self.ciphers = ciphers

        if self.reuse_ssl and (sys.version_info.major < 3 or sys.version_info.minor < 6):
            raise ValueError("Reusing an SSL connection requires Python version 3.6 or greater")

    def run(self):
        """Perform the actual upload.
        
        returns: the number of files uploaded."""

        # Get the timestamp and members of the last upload:
        timestamp, fileset, hashdict = self.get_last_upload()

        n_uploaded = 0

        try:
            if self.secure:
                log.debug("Attempting secure connection to %s", self.server)
                if self.reuse_ssl:
                    # Activate the workaround for the Python ftplib library.
                    from ssl import SSLSocket

                    class ReusedSslSocket(SSLSocket):
                        def unwrap(self):
                            pass

                    class WeeFTPTLS(ftplib.FTP_TLS):
                        """Explicit FTPS, with shared TLS session"""

                        def ntransfercmd(self, cmd, rest=None):
                            conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
                            if self._prot_p:
                                conn = self.context.wrap_socket(conn,
                                                                server_hostname=self.host,
                                                                session=self.sock.session)
                                conn.__class__ = ReusedSslSocket
                            return conn, size
                    log.debug("Reusing SSL connections.")
                    # Python 3.8 and earlier do not support the encoding 
                    # parameter. Be prepared to catch the TypeError that may 
                    # occur with python 3.8 and earlier.
                    try:
                        ftp_server = WeeFTPTLS(encoding=self.encoding)
                    except TypeError:
                        # we likely have python 3.8 or earlier, so try again
                        # without encoding
                        ftp_server = WeeFTPTLS()
                        log.debug("FTP encoding not supported, ignoring.")
                else:
                    # Python 3.8 and earlier do not support the encoding 
                    # parameter. Be prepared to catch the TypeError that may 
                    # occur with python 3.8 and earlier.
                    try:
                        ftp_server = ftplib.FTP_TLS(encoding=self.encoding)
                    except TypeError:
                        # we likely have python 3.8 or earlier, so try again
                        # without encoding
                        ftp_server = ftplib.FTP_TLS()
                        log.debug("FTP encoding not supported, ignoring.")

                # If the user has specified one, set a customized cipher:
                if self.ciphers:
                    ftp_server.context.set_ciphers(self.ciphers)
                    log.debug("Set ciphers to %s", self.ciphers)

            else:
                log.debug("Attempting connection to %s", self.server)
                # Python 3.8 and earlier do not support the encoding parameter. 
                # Be prepared to catch the TypeError that may occur with 
                # python 3.8 and earlier.
                try:
                    ftp_server = ftplib.FTP(encoding=self.encoding)
                except TypeError:
                    # we likely have python 3.8 or earlier, so try again
                    # without encoding
                    ftp_server = ftplib.FTP()
                    log.debug("FTP encoding not supported, ignoring.")

            if self.debug >= 2:
                ftp_server.set_debuglevel(self.debug)

            ftp_server.set_pasv(self.passive)
            ftp_server.connect(self.server, self.port)
            ftp_server.login(self.user, self.password)
            if self.secure and self.secure_data:
                ftp_server.prot_p()
                log.debug("Secure data connection to %s", self.server)
            else:
                log.debug("Connected to %s", self.server)

            # Walk the local directory structure
            for (dirpath, unused_dirnames, filenames) in os.walk(self.local_root):

                # Strip out the common local root directory. What is left
                # will be the relative directory both locally and remotely.
                local_rel_dir_path = dirpath.replace(self.local_root, '.')
                if _skip_this_dir(local_rel_dir_path):
                    continue
                # This is the absolute path to the remote directory:
                remote_dir_path = os.path.normpath(os.path.join(self.remote_root,
                                                                local_rel_dir_path))

                # Make the remote directory if necessary:
                _make_remote_dir(ftp_server, remote_dir_path)

                # Now iterate over all members of the local directory:
                for filename in filenames:

                    full_local_path = os.path.join(dirpath, filename)

                    # calculate hash
                    if has_hashlib:
                        filehash=sha256sum(full_local_path)
                    else:
                        filehash=None

                    # See if this file can be skipped:
                    if _skip_this_file(timestamp, fileset, hashdict, full_local_path, filehash):
                        continue

                    full_remote_path = os.path.join(remote_dir_path, filename)
                    stor_cmd = "STOR %s" % full_remote_path

                    log.debug("%s %s/%s %s" % (n_uploaded,local_rel_dir_path,filename,filehash))

                    with open(full_local_path, 'rb') as fd:
                        try:
                            ftp_server.storbinary(stor_cmd, fd)
                        except ftplib.all_errors as e:
                            # Unsuccessful. Log it, then reraise the exception
                            log.error("Failed uploading %s to server %s. Reason: '%s'",
                                      full_local_path, self.server, e)
                            raise
                    # Success.
                    n_uploaded += 1
                    fileset.add(full_local_path)
                    hashdict[full_local_path]=filehash
                    log.debug("Uploaded file %s to %s", full_local_path, full_remote_path)
        finally:
            try:
                ftp_server.quit()
            except Exception:
                pass

        timestamp = time.time()
        self.save_last_upload(timestamp, fileset, hashdict)
        return n_uploaded

    def get_last_upload(self):
        """Reads the time and members of the last upload from the local root"""

        timestamp_file_path = os.path.join(self.local_root, "#%s.last" % self.name)

        # If the file does not exist, an IOError exception will be raised. 
        # If the file exists, but is truncated, an EOFError will be raised.
        # Either way, be prepared to catch it.
        try:
            with open(timestamp_file_path, "rb") as f:
                timestamp = cPickle.load(f)
                fileset = cPickle.load(f)
                hashdict = cPickle.load(f)
        except (IOError, EOFError, cPickle.PickleError, AttributeError):
            timestamp = 0
            fileset = set()
            hashdict = {}
            # Either the file does not exist, or it is garbled.
            # Either way, it's safe to remove it.
            try:
                os.remove(timestamp_file_path)
            except OSError:
                pass

        return timestamp, fileset, hashdict

    def save_last_upload(self, timestamp, fileset, hashdict):
        """Saves the time and members of the last upload in the local root."""
        timestamp_file_path = os.path.join(self.local_root, "#%s.last" % self.name)
        with open(timestamp_file_path, "wb") as f:
            cPickle.dump(timestamp, f)
            cPickle.dump(fileset, f)
            cPickle.dump(hashdict, f)


def _skip_this_file(timestamp, fileset, hashdict, full_local_path, filehash):
    """Determine whether to skip a specific file."""

    filename = os.path.basename(full_local_path)
    if filename[-1] == '~' or filename[0] == '#':
        return True

    if full_local_path not in fileset:
        return False

    if has_hashlib and filehash is not None:
        # use hash if available
        if full_local_path not in hashdict:
            return False
        if hashdict[full_local_path]!=filehash:
            return False
    else:
        # otherwise use file time
        if os.stat(full_local_path).st_mtime > timestamp:
            return False

    # Filename is in the set, and is up to date.
    return True


def _skip_this_dir(local_dir):
    """Determine whether to skip a directory."""

    return os.path.basename(local_dir) in ('.svn', 'CVS')


def _make_remote_dir(ftp_server, remote_dir_path):
    """Make a remote directory if necessary."""

    try:
        ftp_server.mkd(remote_dir_path)
    except ftplib.all_errors as e:
        # Got an exception. It might be because the remote directory already exists:
        if sys.exc_info()[0] is ftplib.error_perm:
            msg = str(e).strip()
            # If a directory already exists, some servers respond with a '550' ("Requested
            # action not taken") code, others with a '521' ("Access denied" or "Pathname
            # already exists") code.
            if msg.startswith('550') or msg.startswith('521'):
                # Directory already exists
                return
        # It's a real error. Log it, then re-raise the exception.
        log.error("Error creating directory %s", remote_dir_path)
        raise

    log.debug("Made directory %s", remote_dir_path)

# from https://stackoverflow.com/questions/22058048/hashing-a-file-in-python

def sha256sum(filename):
    h  = hashlib.sha256()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()
