#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com> and
#                            Matthew Wall
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities for installing and removing extensions"""
from __future__ import with_statement

import os
import shutil
import sys

import weecfg
from weecfg import Logger

class InstallError(Exception):
    """Exception thrown when installing an extension."""

class ExtensionEngine(object):
    """Engine that manages extensions."""
    # Extension components can be installed to these locations
    target_dirs = {
        'bin': 'BIN_ROOT',
        'skins': 'SKIN_ROOT'}

    def __init__(self, config_path, config_dict, tmpdir=None, bin_root=None, 
                 dry_run=None, logger=None):

        self.logger = logger or Logger()
        self.config_path = config_path
        self.config_dict = config_dict
        self.tmpdir = tmpdir or '/var/tmp'
        # BIN_ROOT does not normally appear in the configuration dictionary. Set a
        # default (which could be 'None')
        self.config_dict.setdefault('BIN_ROOT', bin_root)
        self.dry_run = dry_run

        self.root_dict = weecfg.extract_roots(self.config_path, self.config_dict)
        self.logger.log("root dictionary: %s" % self.root_dict, 4)
        
    def enumerate_extensions(self):
        ext_root = self.root_dict['EXT_ROOT']
        try:
            exts = os.listdir(ext_root)
            if exts:
                for f in exts:
                    self.logger.log(f, level=0)
            else:
                self.logger.log("Extension cache is '%s'" % ext_root, level=2)
                self.logger.log("No extensions installed", level=0)
        except OSError:
            self.logger.log("No extension cache '%s'" % ext_root, level=2)
            self.logger.log("No extensions installed", level=0)
            
    def install_extension(self, extension_path):
        self.logger.log("Request to install '%s'" % extension_path)
        if os.path.isfile(extension_path):
            # It's a file, hopefully a tarball. Extract it, then install
            try:
                member_names = weecfg.extract_tarball(extension_path, self.tmpdir, self.logger)
                extension_reldir = os.path.commonprefix(member_names)
                if extension_reldir == '':
                    raise InstallError("No common path in tarfile '%s'. Unable to install." % extension_path)
                extension_dir = os.path.join(self.tmpdir, extension_reldir)
                self.install_from_dir(extension_dir)
            finally:
                shutil.rmtree(extension_dir, ignore_errors=True)
        elif os.path.isdir(extension_path):
            # It's a directory, presumably containing the extension. Install directly
            self.install_from_dir(extension_path)
        else:
            raise InstallError("Extension '%s' not found or cannot be identified." % extension_path)
    
        self.logger.log("Finished installing extension '%s'" % extension_path)

    def install_from_dir(self, extension_dir):
        self.logger.log("Request to install extension found in directory %s" % extension_dir, level=2)
        old_path = sys.path
        try:
            # Inject both the location of the extension, and my parent directory (so the extension
            # can find setup.py) into the path:
            sys.path[0:0] = [extension_dir, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))]
            __import__('install')
            module = sys.modules['install']
            loader = getattr(module, 'loader')
            installer = loader()
            self.logger.log("Found extension with name '%s'" % installer.get('name', 'Unknown'), level=2)

            # Go through all the files used by the extension:
            for file_path in installer['files']:
                # For each file, check and see if it's a type we know about
                for directory in ExtensionEngine.target_dirs:
                    # This will be something like 'bin', or 'skins':
                    source_type = os.path.commonprefix((file_path[0], directory))
                    if source_type:
                        # This will be something like 'BIN_ROOT' or 'SKIN_ROOT':
                        root_type = ExtensionEngine.target_dirs[source_type]
                        for install_file in file_path[1]:
                            source = os.path.join(extension_dir, install_file)
                            destination = os.path.abspath(os.path.join(self.root_dict[root_type], '..', install_file))
                            self.logger.log("Copying from '%s' to '%s'" % (source, destination), level=3)
                            if not self.dry_run:
                                try:
                                    os.makedirs(os.path.dirname(destination))
                                except OSError:
                                    pass
                                shutil.copy(source, destination)
                        break
                else:
                    sys.exit("Unknown destination for file %s" % file_path)
        finally:
            # Restore the path
            sys.path = old_path

        if 'config' in installer:
            weecfg.conditional_merge(self.config_dict, installer['config'])
            weecfg.save_config(self.config_dict, self.config_path)
