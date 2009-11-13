#!/usr/bin/python
#
# upload.py -- a script to upload files to FTP server only as-needed
#
# Copyright (c) 2002, Silverback Software, LLC
#
# Brian St. Pierre, <brian @ silverback-software.com>
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose, without fee, and without a written agreement
# is hereby granted, provided that the above copyright notice and this
# paragraph and the following two paragraphs appear in all copies.
#
# IN NO EVENT SHALL THE AUTHOR BE LIABLE TO ANY PARTY FOR DIRECT,
# INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST
# PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION,
# EVEN IF THE AUTHOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# THE AUTHOR SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE.  THE SOFTWARE PROVIDED HEREUNDER IS ON AN "AS IS"
# BASIS, AND THE AUTHOR HAS NO OBLIGATIONS TO PROVIDE MAINTENANCE,
# SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
#

#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$

# HISTORY:
#
# 2002-12-20 -- Original
# 2004-05-25 -- Fixed bug creating new dirs where parent did not exist
# 2004-06-15 -- Put ".svn" in default ignore list.
# 2006-09-24 -- Handle FTP error during 'quit'.
# 2009-04-23 -- Modified the member function 'upstream' to return the number
#               of files uploaded. -Tom Keffer
# 2009-08-25 -- Added an optional passive mode. -Tom Keffer
# 2009-10-12 -- Allows up to max_retries attempts at uploading a file to the
#               server before giving up. Logs a failed transfer to syslog. -Tom Keffer
#

####
#
# How this works:
#
# 1. There is a file called #upstream.xml in the root directory.
#    This file contains information about how and where to put files
#    on the FTP server.
#    We don't look for #upstream.xml in subdirectories -- there is no
#    way to override the root file.
#    #upstream.xml is based on Radio UserLand's #upstream.xml, except
#    that we store passwords in plaintext in the <password> element.
#    This is insecure, but it works.
#
# 2. We look for #upstream.last in the root directory.
#    This is a data file that contains the time each file was last
#    uploaded.
#
# 3. We compare every file's timestamp to the info in
#    .upload-last. If the file is newer, it needs to be uploaded.
#    If the .upload-last does not exist, all files need to be
#    uploaded.
#
# 4. We gather all the files to upload and then send everything at the
#    end when we've had a chance to walk the entire directory tree.
#
# 5. We skip the following:
#    - anything ending with ~ (emacs backups)
#    - anything begginning with # (control files)
#    - directories named CVS (don't examine them at all)
#    - this script (which we assume is named upload.py)
#
# From http://bstpierre.org/Projects/upload.py

import ftplib
import os
import os.path
import pickle
import socket
import sys
import time
import syslog
from xml.dom import minidom

class UpstreamerFactory:
    def create(self):
        self.doc = minidom.parse(open('#upstream.xml', 'r'))
        upstream = self.doc.getElementsByTagName('upstream')[0]
        self.type = upstream.getAttribute('type')
        server = self._get_simple_text('server')
        user = self._get_simple_text('username')
        password = self._get_simple_text('password')
        path = self._get_simple_text('path')
        url = self._get_simple_text('url')
        if self.type == 'ftp':
            u = Upstreamer(server, user, password, path)
        elif self.type == 'copy':
            u = LocalUpstreamer(path)

        return u

    def _get_simple_text(self, tag):
        elems = self.doc.getElementsByTagName(tag)
        if len(elems) > 0 and len(elems[0].childNodes) > 0:
            return elems[0].childNodes[0].data
        return ''

class Upstreamer:
    def __init__(self, server, user, password, path, passive=False, max_retries = 3):
        self.server = server
        self.user = user
        self.password = password
        self.path = path
        self.passive = passive
        self.max_retries = max_retries
        self._normalize_path()
        return

    def _normalize_path(self):
        self.path = self.path.replace('\\', '/')
        if self.path[-1] == '/':
            self.path = self.path[:-1]
        return

    def get_dest_dir(self, destfile):
        return destfile[:destfile.rfind('/')]

    def check_dir_and_create(self, ftp, dir):
        dir = dir.replace(self.path, '')
        path = self.path
        for d in dir.split('/'):
            if d == '':
                continue
            cur = path + '/' + d
            try:
                ftp.cwd(cur)
                path = cur
            except ftplib.error_perm:
#                print 'MKD', cur
                ftp.mkd(cur)
                ftp.cwd(cur)
            path = cur
        try:
            ftp.cwd(self.path)
        except ftplib.error_perm:
#            print 'MKD', self.path
            ftp.mkd(self.path)
            ftp.cwd(self.path)
        return

    def upstream(self, files):
        n_uploaded = 0
        if len(files) == 0:
            return n_uploaded
        ftp = ftplib.FTP(self.server)
        #ftp.set_debuglevel(1)
        ftp.login(self.user, self.password)
        ftp.set_pasv(self.passive)
        self.check_dir_and_create(ftp, self.path)
        for file in files:
            if file[0] == '.':
                destfile = file[1:].replace('\\', '/')
            if destfile[0] == '/':
                destfile = destfile[1:]
            destfile = self.path + '/' + destfile
            cmd = 'STOR ' + destfile
            f = open(file, 'r')
            
            for _count in range(self.max_retries):
                try:
                    self.check_dir_and_create(ftp,
                                              self.get_dest_dir(destfile))
                except (socket.error, ftplib.Error), e:
                    syslog.syslog(syslog.LOG_ERR, "upload: attempt #%d; got exception while changing/making directory. Reason: %s" % (_count+1, e,))
                    if _count == self.max_retries-1:
                        syslog.syslog(syslog.LOG_ERR, "upload: max retries (%d) exceeded while changing/making directory. Giving up." % (self.max_retries,))
                        raise
                else:
                    break

            for _count in range(self.max_retries):
                try:
                    ftp.storbinary(cmd, f)
                except socket.error, e:
                    syslog.syslog(syslog.LOG_ERR, "upload: attempt #%d. failed uploading %s. Reason: %s" % (_count+1, destfile, e))
                else:
                    n_uploaded += 1
                    syslog.syslog(syslog.LOG_DEBUG, "upload: attempt #%d. uploaded file %s." % (_count+1, destfile))
                    break
            else:
                syslog.syslog(syslog.LOG_ERR, 
                          "upload: max retries (%d) exceeded while ftp'ing file %s. Giving up." % (self.max_retries,file))
        try:
            ftp.quit()
        except socket.error:
            # My FTP server started causing "connection reset"
            # errors. I think it is closing the far end socket too
            # quickly.
            pass
        return n_uploaded

class LocalUpstreamer(Upstreamer):
    """This Upstreamer uses a local file copy rather than FTP."""
    def __init__(self, path):
        Upstreamer.__init__(self, '', '', '', path)
        return
    
    def check_dir_and_create(self, ftp, dir):
        if not os.path.isdir(dir):
            print 'mkdir', dir
            os.makedirs(dir)
        return

    def upstream(self, files):
        if len(files) == 0:
            return
        self.check_dir_and_create(None, self.path)
        for file in files:
            if file[0] == '.':
                destfile = file[1:].replace('\\', '/')
            if destfile[0] == '/':
                destfile = destfile[1:]
            destfile = os.path.join(self.path, destfile)
            self.check_dir_and_create(None,
                                      self.get_dest_dir(destfile))
            print 'copy %s' % (file, )
            destfd = open(destfile, 'w')
            srcfd = open(file, 'r')
            destfd.write(srcfd.read())
            srcfd.close()
            destfd.close()
        return

class Finder:
    def __init__(self):
        if os.access('#upstream.last', os.R_OK):
            self.last = pickle.load(open('#upstream.last', 'r'))
        else:
            self.last = {}
        self.now = {}
        self.find_all_files()
        return

    def _os_walk_callback(self, dummy, dir, names):
        if dir[-3:] == 'CVS' or dir.find('.svn') != -1:
            return
        if dir.find('/#') != -1:
            return
        for name in names:
            filename = os.path.join(dir, name)
            if name in ['CVS', '.svn']:
                continue
            elif name[-1] == '~':
                continue
            elif name[0] == '#':
                continue
            elif name == 'upload.py':
                continue
            elif os.path.isdir(filename):
                continue
            else:
                stamp = os.stat(filename).st_mtime
                self.now[filename] = stamp
        return

    def find_all_files(self):
        os.path.walk('.', self._os_walk_callback, None)
        return

    def get_new_files(self):
        new = []
        for file in self.now.keys():
            if not self.last.has_key(file):
                new.append(file)
            elif self.last[file] < self.now[file]:
                new.append(file)
        return new

    def reset_stamp(self, when):
        for file in self.now.keys():
            self.now[file] = when
        return

    def save(self):
        pickle.dump(self.now, open('#upstream.last', 'w'))
        return


if __name__ == '__main__':
    f = UpstreamerFactory()
    upstr = f.create()
    finder = Finder()
    finder.find_all_files()
    if len(sys.argv) == 2:
        if sys.argv[1] == '-t': ## test
            print finder.get_new_files()
        if sys.argv[1] == '-f': ## fake
            print finder.get_new_files()
            finder.reset_stamp(time.time())
            finder.save()
            print "No upload: timestamps reset."
    else:
        upstr.upstream(finder.get_new_files())
        finder.reset_stamp(time.time())
        finder.save()
