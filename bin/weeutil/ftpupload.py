#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""For uploading files to a remove server via FTP"""

from __future__ import with_statement
import os
import sys
import ftplib
import cPickle
import time
import syslog

class FtpUpload(object):
    """Uploads a directory and all its descendants to a remote server.
    
    Keeps track of when a file was last uploaded, so it is uploaded only
    if its modification time is newer."""

    def __init__(self, server, 
                 user, password, 
                 local_root, remote_root, 
                 port      = 21,
                 name      = "FTP", 
                 passive   = True, 
                 max_tries = 3,
                 secure    = False,
                 debug     = 0):
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
        
        max_tries: How many times to try creating a directory or uploading
        a file before giving up [Optional. Default is 3]
        
        secure: Set to True to attempt a secure FTP (SFTP) session.
        
        debug: Set to 1 for extra debug information, 0 otherwise.
        """
        self.server      = server
        self.user        = user
        self.password    = password
        self.local_root  = os.path.normpath(local_root)
        self.remote_root = os.path.normpath(remote_root)
        self.port        = port
        self.name        = name
        self.passive     = passive
        self.max_tries   = max_tries
        self.secure      = secure
        self.debug       = debug

    def run(self):
        """Perform the actual upload.
        
        returns: the number of files uploaded."""
        
        if self.secure:
            try:
                FTPClass = ftplib.FTP_TLS
            except AttributeError:
                FTPClass = ftplib.FTP
                syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Your version of Python does not support SFTP. Using unsecure connection.")
                self.secure = False
        else:
            FTPClass = ftplib.FTP
        
        # Get the timestamp and members of the last upload:
        (timestamp, fileset) = self.getLastUpload()

        n_uploaded = 0
        # Try to connect to the ftp server up to max_tries times:
        
        try:
            if self.secure:
                syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Attempting secure connection to %s" % self.server)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Attempting connection to %s" % self.server)
            for count in range(self.max_tries):
                try:
                    ftp_server = FTPClass()
                    ftp_server.connect(self.server, self.port)
        
                    if self.debug:
                        ftp_server.set_debuglevel(self.debug)
        
                    ftp_server.login(self.user, self.password)
                    ftp_server.set_pasv(self.passive)
                    if self.secure:
                        ftp_server.prot_p()
                        syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Secure connection to %s" % self.server)
                    else:
                        syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Connected to %s" % self.server)
                    break
                except ftplib.all_errors, e:
                    syslog.syslog(syslog.LOG_NOTICE, "ftpupload: Unable to connect or log into server : %s" % e)
            else:
                # This is executed only if the loop terminates naturally (without a break statement),
                # meaning the ftp connection failed max_tries times. Abandon ftp upload
                syslog.syslog(syslog.LOG_CRIT, 
                                  "ftpupload: Attempted %d times to connect to server %s. Giving up." % 
                                  (self.max_tries, self.server))
                return n_uploaded
            
            # Walk the local directory structure
            for (dirpath, unused_dirnames, filenames) in os.walk(self.local_root):
    
                # Strip out the common local root directory. What is left
                # will be the relative directory both locally and remotely.
                local_rel_dir_path = dirpath.replace(self.local_root, '.')
                if self._skipThisDir(local_rel_dir_path):
                    continue
                # This is the absolute path to the remote directory:
                remote_dir_path = os.path.normpath(os.path.join(self.remote_root, local_rel_dir_path))
    
                # Make the remote directory if necessary:
                self._make_remote_dir(ftp_server, remote_dir_path)
                    
                # Now iterate over all members of the local directory:
                for filename in filenames:
    
                    full_local_path = os.path.join(dirpath, filename)
                    # See if this file can be skipped:
                    if self._skipThisFile(timestamp, fileset, full_local_path):
                        continue
    
                    full_remote_path = os.path.join(remote_dir_path, filename)
                    STOR_cmd = "STOR %s" % full_remote_path
                    # Retry up to max_tries times:
                    for count in range(self.max_tries):
                        try:
                            # If we have to retry, we should probably reopen the file as well.
                            # Hence, the open is in the inner loop:
                            fd = open(full_local_path, "r")
                            ftp_server.storbinary(STOR_cmd, fd)
                        except ftplib.all_errors, e:
                            # Unsuccessful. Log it and go around again.
                            syslog.syslog(syslog.LOG_ERR, "ftpupload: Attempt #%d. Failed uploading %s to %s. Reason: %s" %
                                                          (count+1, full_remote_path, self.server, e))
                            ftp_server.set_pasv(self.passive)
                        else:
                            # Success. Log it, break out of the loop
                            n_uploaded += 1
                            fileset.add(full_local_path)
                            syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Uploaded file %s" % full_remote_path)
                            break
                        finally:
                            # This is always executed on every loop. Close the file.
                            try:
                                fd.close()
                            except:
                                pass
                    else:
                        # This is executed only if the loop terminates naturally (without a break statement),
                        # meaning the upload failed max_tries times. Log it, move on to the next file.
                        syslog.syslog(syslog.LOG_ERR, "ftpupload: Failed to upload file %s" % full_remote_path)
        finally:
            try:
                ftp_server.quit()
            except:
                pass
        
        timestamp = time.time()
        self.saveLastUpload(timestamp, fileset)
        return n_uploaded
    
    def getLastUpload(self):
        """Reads the time and members of the last upload from the local root"""
        
        timeStampFile = os.path.join(self.local_root, "#%s.last" % self.name )

        # If the file does not exist, an IOError exception will be raised. 
        # If the file exists, but is truncated, an EOFError will be raised.
        # Either way, be prepared to catch it.
        try:
            with open(timeStampFile, "r") as f:
                timestamp = cPickle.load(f)
                fileset   = cPickle.load(f) 
        except (IOError, EOFError, cPickle.PickleError):
            timestamp = 0
            fileset = set()
            # Either the file does not exist, or it is garbled.
            # Either way, it's safe to remove it.
            try:
                os.remove(timeStampFile)
            except OSError:
                pass

        return (timestamp, fileset)

    def saveLastUpload(self, timestamp, fileset):
        """Saves the time and members of the last upload in the local root."""
        timeStampFile = os.path.join(self.local_root, "#%s.last" % self.name )
        with open(timeStampFile, "w") as f:
            cPickle.dump(timestamp, f)
            cPickle.dump(fileset,   f)
                
    def _make_remote_dir(self, ftp_server, remote_dir_path):
        """Make a remote directory if necessary."""
        # Try to make the remote directory up max_tries times, then give up.
        for unused_count in range(self.max_tries):
            try:
                ftp_server.mkd(remote_dir_path)
            except ftplib.all_errors, e:
                # Got an exception. It might be because the remote directory already exists:
                if sys.exc_info()[0] is ftplib.error_perm:
                    msg =str(e).strip()
                    # If a directory already exists, some servers respond with a '550' ("Requested action not taken") code,
                    # others with a '521' ("Access denied" or "Pathname already exists") code.
                    if msg.startswith('550') or msg.startswith('521'):
                        # Directory already exists
                        return
                syslog.syslog(syslog.LOG_ERR, "ftpupload: Got error while attempting to make remote directory %s" % remote_dir_path)
                syslog.syslog(syslog.LOG_ERR, "     ****  Error: %s" % e)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "ftpupload: Made directory %s" % remote_dir_path)
                return
        else:
            syslog.syslog(syslog.LOG_ERR, "ftpupload: Unable to create remote directory %s" % remote_dir_path)
            raise IOError, "Unable to create remote directory %s" % remote_dir_path
            
    def _skipThisDir(self, local_dir):
        
        return os.path.basename(local_dir) in ('.svn', 'CVS')

    def _skipThisFile(self, timestamp, fileset, full_local_path):
        
        filename = os.path.basename(full_local_path)
        if filename[-1] == '~' or filename[0] == '#' :
            return True
        
        if full_local_path not in fileset:
            return False
        
        if os.stat(full_local_path).st_mtime > timestamp:
            return False
        
        # Filename is in the set, and is up to date. 
        return True
        
        
if __name__ == '__main__':
    
    import weewx
    import socket
    import configobj
    
    weewx.debug = 1
    syslog.openlog('wee_ftpupload', syslog.LOG_PID|syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

    if len(sys.argv) < 2 :
        print """Usage: ftpupload.py path-to-configuration-file [path-to-be-ftp'd]"""
        sys.exit(weewx.CMD_ERROR)
        
    try :
        config_dict = configobj.ConfigObj(sys.argv[1], file_error=True)
    except IOError:
        print "Unable to open configuration file ", sys.argv[1]
        raise

    if len(sys.argv) == 2:
        try:
            ftp_dir = os.path.join(config_dict['WEEWX_ROOT'],
                                   config_dict['StdReport']['HTML_ROOT'])
        except KeyError:
            print "No HTML_ROOT in configuration dictionary."
            sys.exit(1)
    else:
        ftp_dir = sys.argv[2]

        
    socket.setdefaulttimeout(10)


    ftp_upload = FtpUpload(config_dict['StdReport']['FTP']['server'],
                           config_dict['StdReport']['FTP']['user'],
                           config_dict['StdReport']['FTP']['password'],
                           ftp_dir,
                           config_dict['StdReport']['FTP']['path'],
                           'FTP',
                           config_dict['StdReport']['FTP'].as_bool('passive'),
                           config_dict['StdReport']['FTP'].as_int('max_tries'))
    ftp_upload.run()
    