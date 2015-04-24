#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com> and
#                            Matthew Wall
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities for installing and removing extensions"""
import os
import shutil
import sys

import weecfg
from weecfg import Logger
from weewx import all_service_groups
import weeutil.weeutil

class InstallError(Exception):
    """Exception thrown when installing an extension."""

class ExtensionInstaller(dict):
    """Base class for extension installers."""

class ExtensionEngine(object):
    """Engine that manages extensions."""
    # Extension components can be installed to these locations
    target_dirs = {
        'bin': 'BIN_ROOT',
        'skins': 'SKIN_ROOT'}

    def __init__(self, config_path, config_dict, tmpdir=None, bin_root=None, 
                 dry_run=False, logger=None):
        """Initializer for ExtensionEngine. 
        
        config_path: Path to the configuration file. (Something like /home/weewx/weewx.conf)

        config_dict: The configuration dictionary (the contents of the file at config_path).

        tmpdir: A temporary directory to be used for extracting tarballs and the like [Optional]

        bin_root: A path to the root of the weewx binary files (Something like /home/weewx/bin).
        Optional. If not given, it will be determined from the location of this file.
        
        dry_run: If True, all the steps will be printed out, but nothing will actually be done.
        
        logger: An instance of weecfg.Logger. This will be used to print things to the console.        
        """
        self.config_path = config_path
        self.config_dict = config_dict
        self.logger = logger or Logger()
        self.tmpdir = tmpdir or '/var/tmp'
        # BIN_ROOT does not normally appear in the configuration dictionary. Set a
        # default (which could be 'None')
        self.config_dict.setdefault('BIN_ROOT', bin_root)
        self.dry_run = dry_run

        self.root_dict = weecfg.extract_roots(self.config_path, self.config_dict)
        self.logger.log("root dictionary: %s" % self.root_dict, 4)
        
    def enumerate_extensions(self):
        """Print info about all installed extensions to the logger."""
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
        """Install the extension that can be found at a given path."""
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
        """Install the extension that can be found in a given directory"""
        self.logger.log("Request to install extension found in directory %s" % extension_dir, level=2)
        
        old_path = sys.path
        try:
            # Inject the location of the extension into the path:
            sys.path.insert(0, extension_dir)
            # Now I can import the extension's 'install' module:
            __import__('install')
        finally:
            # Restore the path
            sys.path = old_path
            
        install_module = sys.modules['install']
        loader = getattr(install_module, 'loader')
        installer = loader()
        extension_name = installer.get('name', 'Unknown')
        self.logger.log("Found extension with name '%s'" % extension_name, level=2)

        # Go through all the files used by the extension. A "source tuple" is something
        # like (bin, [user/myext.py, user/otherext.py]). The first element is the
        # directory the files go in, the second element is a list of files to be put
        # in that directory
        for source_tuple in installer['files']:
            # For each set of sources, check and see if it's a type we know about
            for directory in ExtensionEngine.target_dirs:
                # This will be something like 'bin', or 'skins':
                source_type = os.path.commonprefix((source_tuple[0], directory))
                # If there is a match, source_type will be something other than an empty string:
                if source_type:
                    # This will be something like 'BIN_ROOT' or 'SKIN_ROOT':
                    root_type = ExtensionEngine.target_dirs[source_type]
                    # Now go through all the files of the source tuple
                    for install_file in source_tuple[1]:
                        source_path = os.path.join(extension_dir, install_file)
                        destination_path = os.path.abspath(os.path.join(self.root_dict[root_type], '..', install_file))
                        self.logger.log("Copying from '%s' to '%s'" % (source_path, destination_path), level=3)
                        if not self.dry_run:
                            try:
                                os.makedirs(os.path.dirname(destination_path))
                            except OSError:
                                pass
                            shutil.copy(source_path, destination_path)
                    break
            else:
                sys.exit("Unknown destination for file %s" % source_tuple)

        save_config = False
        new_top_level = []
        # Look for options that have to be injected into the configuration file
        if 'config' in installer:
            # Remember any new top-level sections (so we can inject a major comment block):
            for top_level in installer['config']:
                if top_level not in self.config_dict:
                    new_top_level.append(top_level)
                    
            # Inject any new config data into the configuration file
            weecfg.conditional_merge(self.config_dict, installer['config'])
            
            # Now include the major comment block for any new top level sections
            for new_section in new_top_level:
                self.config_dict.comments[new_section] = weecfg.major_comment_block + \
                            ["# Options for extension '%s'" % extension_name]
                
            save_config = True
        
        # Go through all the possible service groups and see if the extension provides
        # a new one
        for service_group in all_service_groups:
            if service_group in installer:
                extension_svcs = weeutil.weeutil.option_as_list(installer[service_group])
                for svc in extension_svcs:
                    # See if this service is already in the service group
                    if svc not in self.config_dict['Engine']['Services'][service_group]:
                        # Add the new service into the appropriate service group
                        self.config_dict['Engine']['Services'][service_group].append(svc)
                        save_config = True

        # Save the extension's install.py file
        try:
            os.makedirs(self.root_dict['EXT_ROOT'])
        except OSError:
            pass
        shutil.copy2(install_module.__file__, self.root_dict['EXT_ROOT'])
                                
        if save_config:
            weecfg.save_with_backup(self.config_dict, self.config_path)
