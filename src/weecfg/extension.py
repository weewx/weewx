#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities for installing and removing extensions"""

import glob
import os
import shutil
import sys
import tempfile

import configobj

import weecfg
import weeutil.config
import weeutil.startup
import weeutil.weeutil
import weewx
from weeutil.printer import Printer

# Very old extensions did:
#   from setup import ExtensionInstaller
# Redirect references to 'setup' to me instead.
sys.modules['setup'] = sys.modules[__name__]


class InstallError(Exception):
    """Exception raised when installing an extension."""


class ExtensionInstaller(dict):
    """Base class for extension installers."""

    def configure(self, engine):
        """Can be overridden by installers. It should return True if the installer modifies
        the configuration dictionary."""
        return False


class ExtensionEngine(object):
    """Engine that manages extensions."""
    # Extension components can be installed to these locations
    target_dirs = {
        'bin': 'BIN_DIR',
        'skins': 'SKIN_DIR'
    }

    def __init__(self, config_path, config_dict, dry_run=False, printer=None):
        """Initializer for ExtensionEngine.

        Args:
            config_path (str): Path to the configuration file.  For example, something
                like /home/weewx/weewx.conf.
            config_dict (dict): The configuration dictionary, i.e., the contents of the
                file at config_path.
            dry_run (bool): If Truthy, all the steps will be printed out, but nothing will
                actually be done.
            printer (Printer): An instance of weeutil.printer.Printer. This will be used to print
                things to the console while honoring verbosity levels.
        """
        self.config_path = config_path
        self.config_dict = config_dict
        self.printer = printer or Printer()
        self.dry_run = dry_run

        self.root_dict = weeutil.startup.extract_roots(self.config_dict)
        self.printer.out("root dictionary: %s" % self.root_dict, 4)

    def enumerate_extensions(self):
        """Print info about all installed extensions to the logger."""
        ext_dir = self.root_dict['EXT_DIR']
        try:
            exts = sorted(os.listdir(ext_dir))
            if exts:
                self.printer.out("%-18s%-10s%s" % ("Extension Name", "Version", "Description"),
                                 level=0)
                for f in exts:
                    info = self.get_extension_info(f)
                    msg = "%(name)-18s%(version)-10s%(description)s" % info
                    self.printer.out(msg, level=0)
            else:
                self.printer.out("Extension cache is '%s'." % ext_dir, level=2)
                self.printer.out("No extensions installed.", level=0)
        except OSError:
            self.printer.out("No extension cache '%s'." % ext_dir, level=2)
            self.printer.out("No extensions installed.", level=0)

    def get_extension_info(self, ext_name):
        ext_cache_dir = os.path.join(self.root_dict['EXT_DIR'], ext_name)
        _, installer = weecfg.get_extension_installer(ext_cache_dir)
        return installer

    def install_extension(self, extension_path, no_confirm=False):
        """Install an extension.

        Args:
            extension_path(str): Either a file path, a directory path, or an URL.
            no_confirm(bool): If False, ask for a confirmation before installing. Otherwise,
                just do it.
        """
        ans = weeutil.weeutil.y_or_n(f"Install extension '{extension_path}'? ",
                                     noprompt=no_confirm)
        if ans == 'n':
            self.printer.out("Nothing done.")
            return

        # Figure out what extension_path is
        if extension_path.startswith('http'):
            # It's an URL. Download, then install
            import urllib.request
            import tempfile
            # Download the file into a temporary file
            with tempfile.NamedTemporaryFile() as test_fd:
                filename, info = urllib.request.urlretrieve(extension_path, test_fd.name)
                # Now install the temporary file. The file type can be found in the download
                # header's "subtype". This will be something like "zip".
                extension_name = self._install_from_file(test_fd.name, info.get_content_subtype())
        elif os.path.isfile(extension_path):
            # It's a file. Figure out what kind, then install. If it's not a zipfile, assume
            # it's a tarfile.
            if extension_path[-4:] == '.zip':
                filetype = 'zip'
            else:
                filetype = 'tar'
            extension_name = self._install_from_file(extension_path, filetype)
        elif os.path.isdir(extension_path):
            # It's a directory. Install directly.
            extension_name = self.install_from_dir(extension_path)
        else:
            raise InstallError(f"Unrecognized type for {extension_path}")

        self.printer.out(f"Finished installing extension {extension_name} from {extension_path}.")

    def _install_from_file(self, filepath, filetype):
        """Install an extension from a file.

        Args:
            filepath(str): A path to the file holding the extension.
            filetype(str): The type of file. If 'zip', it's assumed to be a zipfile. Anything else,
                and it's assumed to be a tarfile.
        """
        # Make a temporary directory into which to extract the file.
        with tempfile.TemporaryDirectory() as dir_name:
            if filetype == 'zip':
                member_names = weecfg.extract_zip(filepath, dir_name, self.printer)
            else:
                # Assume it's a tarfile
                member_names = weecfg.extract_tar(filepath, dir_name, self.printer)
            extension_reldir = os.path.commonprefix(member_names)
            if not extension_reldir:
                raise InstallError(f"Unable to install from {filepath}: no common path "
                                   "(the extension archive contains more than a "
                                   "single root directory)")
            extension_dir = os.path.join(dir_name, extension_reldir)
            extension_name = self.install_from_dir(extension_dir)

        return extension_name

    def install_from_dir(self, extension_dir):
        """Install the extension whose components are in extension_dir"""
        self.printer.out(f"Request to install extension found in directory {extension_dir}.",
                         level=2)

        # The "installer" is actually a dictionary containing what is to be installed and where.
        # The "installer_path" is the path to the file containing that dictionary.
        installer_path, installer = weecfg.get_extension_installer(extension_dir)
        extension_name = installer.get('name', 'Unknown')
        self.printer.out(f"Found extension with name '{extension_name}'.", level=2)

        # Install any files:
        if 'files' in installer:
            self._install_files(installer['files'], extension_dir)

        save_config = False

        # Go through all the possible service groups and see if the extension
        # includes any services that belong in any of them.
        self.printer.out("Adding services to service lists.", level=2)
        for service_group in weewx.all_service_groups:
            if service_group in installer:
                extension_svcs = weeutil.weeutil.option_as_list(installer[service_group])
                # Check to make sure the service group is in the configuration dictionary
                if service_group not in self.config_dict['Engine']['Services']:
                    self.config_dict['Engine']['Services'][service_group] = []
                # Be sure it's actually a list
                svc_list = weeutil.weeutil.option_as_list(
                    self.config_dict['Engine']['Services'][service_group])
                for svc in extension_svcs:
                    # See if this service is already in the service group
                    if svc not in svc_list:
                        if not self.dry_run:
                            # Add the new service into the appropriate service group
                            svc_list.append(svc)
                            self.config_dict['Engine']['Services'][service_group] = svc_list
                            save_config = True
                        self.printer.out(f"Added new service {svc} to {service_group}.", level=3)

        # Give the installer a chance to do any customized configuration
        save_config |= installer.configure(self)

        # Look for options that have to be injected into the configuration file
        if 'config' in installer:
            save_config |= self._inject_config(installer['config'], extension_name)

        # Save the extension's install.py file in the extension's installer
        # directory for later use enumerating and uninstalling
        extension_installer_dir = os.path.join(self.root_dict['EXT_DIR'], extension_name)
        self.printer.out(f"Saving installer file to {extension_installer_dir}.")
        if not self.dry_run:
            try:
                os.makedirs(os.path.join(extension_installer_dir))
            except OSError:
                pass
            shutil.copy2(installer_path, extension_installer_dir)

        if save_config:
            backup_path = weecfg.save_with_backup(self.config_dict, self.config_path)
            self.printer.out(f"Saved configuration dictionary. Backup copy at {backup_path}.")

        return extension_name

    def _install_files(self, file_list, extension_dir):
        """ Install any files included in the extension

        Args:
            file_list (list[tuple]): A list of two-way tuples. The first element of each tuple is
                the relative path to a destination directory, the second element is a list of
                relative paths to files to be put in that directory. For example,
                (bin/user/, [src/foo.py, ]) means the relative path for the destination directory
                is 'bin/user'. The file foo.py can be found in src/foo.py, and should be put
                in bin/user/foo.py.
            extension_dir (str): Path to the directory holding the downloaded extension.

        Returns:
            int: How many files were installed.
        """

        self.printer.out("Copying new files...", level=2)
        N = 0

        for source_path, destination_path in ExtensionEngine._gen_file_paths(
                self.root_dict['WEEWX_ROOT'],
                extension_dir,
                file_list):

            if self.dry_run:
                self.printer.out(f"Fake copying from '{source_path}' to '{destination_path}'",
                                 level=3)
            else:
                self.printer.out(f"Copying from '{source_path}' to '{destination_path}'",
                                 level=3)
                try:
                    os.makedirs(os.path.dirname(destination_path))
                except OSError:
                    pass
                shutil.copy(source_path, destination_path)
            N += 1

        if self.dry_run:
            self.printer.out(f"Fake copied {N:d} files.", level=2)
        else:
            self.printer.out(f"Copied {N:d} files.", level=2)
        return N

    @staticmethod
    def _gen_file_paths(weewx_root, extension_dir, file_list):
        """Generate tuples of (source, destination) from a file_list"""

        # Go through all the files used by the extension. A "source tuple" is something like
        # (bin, [user/myext.py, user/otherext.py]).
        for source_tuple in file_list:
            # Expand the source tuple
            dest_dir, source_files = source_tuple
            for source_file in source_files:
                common = os.path.commonpath([dest_dir, source_file])
                rest = os.path.relpath(source_file, common)
                abs_source_path = os.path.join(extension_dir, source_file)
                abs_dest_path = os.path.abspath(os.path.join(weewx_root,
                                                             dest_dir,
                                                             rest))

                yield abs_source_path, abs_dest_path

    def get_lang_code(self, skin_path, default_code):
        """Convenience function for picking a language code

        Args:
            skin_path (str): The path to the directory holding the skin.
            default_code (str): In the absence of a locale directory, what language to pick.
        """
        languages = weecfg.get_languages(skin_path)
        code = weecfg.pick_language(languages, default_code)
        return code

    def _inject_config(self, extension_config, extension_name):
        """Injects any additions to the configuration file that the extension might have.
        
        Returns True if it modified the config file, False otherwise.
        """
        self.printer.out("Adding sections to configuration file", level=2)
        # Make a copy, so we can modify the sections to fit the existing configuration
        if isinstance(extension_config, configobj.Section):
            cfg = weeutil.config.deep_copy(extension_config)
        else:
            cfg = dict(extension_config)

        save_config = False

        # Extensions can specify where their HTML output goes relative to HTML_ROOT. So, we must
        # prepend the installation's HTML_ROOT to get a final location that the reporting engine
        # can use. For example, if an extension specifies "HTML_ROOT=forecast", the final location
        # might be public_html/forecast, or /var/www/html/forecast, depending on the installation
        # method.
        ExtensionEngine.prepend_path(cfg, 'HTML_ROOT', self.config_dict['StdReport']['HTML_ROOT'])

        # If the extension uses a database, massage it so that it's compatible with the new V3.2
        # way of specifying database options
        if 'Databases' in cfg:
            for db in cfg['Databases']:
                db_dict = cfg['Databases'][db]
                # Does this extension use the V3.2+ 'database_type' option?
                if 'database_type' not in db_dict:
                    # There is no database type specified. In this case, the driver type better
                    # appear. Fail hard, with a KeyError, if it does not. Also, if the driver is
                    # not for sqlite or MySQL, then we don't know anything about it. Assume the
                    # extension author knows what s/he is doing, and leave it be.
                    if db_dict['driver'] == 'weedb.sqlite':
                        db_dict['database_type'] = 'SQLite'
                        db_dict.pop('driver')
                    elif db_dict['driver'] == 'weedb.mysql':
                        db_dict['database_type'] = 'MySQL'
                        db_dict.pop('driver')

        if not self.dry_run:
            # Inject any new config data into the configuration file
            weeutil.config.conditional_merge(self.config_dict, cfg)

            self._reorder(cfg)
            save_config = True

        self.printer.out("Merged extension settings into configuration file", level=3)
        return save_config

    def _reorder(self, cfg):
        """Reorder the resultant config_dict"""
        # Patch up the location of any reports so that they appear before FTP/RSYNC

        # First, find the FTP or RSYNC reports. This has to be done on the basis of the skin type,
        # rather than the report name, in case there are multiple FTP or RSYNC reports to be run.
        try:
            for report in self.config_dict['StdReport'].sections:
                if self.config_dict['StdReport'][report]['skin'] in ['Ftp', 'Rsync']:
                    target_name = report
                    break
            else:
                # No FTP or RSYNC. Nothing to do.
                return
        except KeyError:
            return

        # Now shuffle things so any reports that appear in the extension appear just before FTP (or
        # RSYNC) and in the same order they appear in the extension manifest.
        try:
            for report in cfg['StdReport']:
                weecfg.reorder_sections(self.config_dict['StdReport'], report, target_name)
        except KeyError:
            pass

    def uninstall_extension(self, extension_name, no_confirm=False):
        """Uninstall an extension.
        Args:
            extension_name(str): The name of the extension. Use 'weectl extension list' to find
                its name.
            no_confirm(bool): If False, ask for a confirmation before uninstalling. Otherwise,
                just do it.
        """

        ans = weeutil.weeutil.y_or_n(f"Uninstall extension '{extension_name}'? (y/n) ",
                                     noprompt=no_confirm)
        if ans == 'n':
            self.printer.out("Nothing done.")
            return

        # Find the subdirectory containing this extension's installer
        extension_installer_dir = os.path.join(self.root_dict['EXT_DIR'], extension_name)
        try:
            # Retrieve it
            _, installer = weecfg.get_extension_installer(extension_installer_dir)
        except weecfg.ExtensionError:
            sys.exit(f"Unable to find extension '{extension_name}'.")

        # Remove any files that were added:
        if 'files' in installer:
            self.uninstall_files(installer['files'])

        save_config = False

        # Remove any services we added
        for service_group in weewx.all_service_groups:
            if service_group in installer:
                new_list = [x for x in self.config_dict['Engine']['Services'][service_group] \
                            if x not in installer[service_group]]
                if not self.dry_run:
                    self.config_dict['Engine']['Services'][service_group] = new_list
                    save_config = True

        # Remove any sections we added
        if 'config' in installer and not self.dry_run:
            weecfg.remove_and_prune(self.config_dict, installer['config'])
            save_config = True

        if not self.dry_run:
            # Finally, remove the extension's installer subdirectory:
            shutil.rmtree(extension_installer_dir)

        if save_config:
            weecfg.save_with_backup(self.config_dict, self.config_path)

        self.printer.out(f"Finished removing extension '{extension_name}'")

    def uninstall_files(self, file_list):
        """Delete files that were installed for this extension
        Args:
            file_list (list[tuple]): A list of two-way tuples. The first element of each tuple is
                the relative path to the destination directory, the second element is a list of
                relative paths to files that are used by the extension.
        """

        self.printer.out("Removing files.", level=2)

        directory_set = set()
        N = 0
        # Go through all the listed files
        for _, destination_path in ExtensionEngine._gen_file_paths(
                self.root_dict['WEEWX_ROOT'],
                '',
                file_list):
            file_name = os.path.basename(destination_path)
            # There may be a versioned skin.conf. Delete it by adding a wild card.
            # Similarly, be sure to delete Python files with .pyc or .pyo extensions.
            if file_name == 'skin.conf' or file_name.endswith('py'):
                destination_path += "*"
            # Delete the file
            N += self.delete_file(destination_path)
            # Add its directory to the set of directories we've encountered
            directory_set.add(os.path.dirname(destination_path))

        self.printer.out(f"Removed {N:d} files.", level=2)

        N_dir = 0
        # Now delete all the empty directories. Start by finding the directory closest to root
        most_root = os.path.commonprefix(list(directory_set))
        # Now delete the directories under it, from the bottom up.
        for dirpath, _, _ in os.walk(most_root, topdown=False):
            if dirpath in directory_set:
                N_dir += self.delete_directory(dirpath)
        self.printer.out(f"Removed {N_dir:d} directores.", level=2)

    def delete_file(self, filename, report_errors=True):
        """
        Delete files from the file system.

        Args:
            filename (str): The path to the file(s) to be deleted. Can include wildcards.

            report_errors (bool): If truthy, report an error if the file is missing or cannot be
                deleted. Otherwise, don't. In neither case will an exception be raised.
        Returns:
            int: The number of files deleted
        """
        n_deleted = 0
        for fn in glob.glob(filename):
            self.printer.out("Deleting file %s" % fn, level=2)
            if not self.dry_run:
                try:
                    os.remove(fn)
                    n_deleted += 1
                except OSError as e:
                    if report_errors:
                        self.printer.out("Delete failed: %s" % e, level=4)
        return n_deleted

    def delete_directory(self, directory, report_errors=True):
        """
        Delete the given directory from the file system.

        Args:

            directory (str): The path to the directory to be deleted. If the directory is not
                empty, nothing is done.

            report_errors (bool); If truthy, report an error. Otherwise, don't. In neither case will
                an exception be raised.
        """
        n_deleted = 0
        try:
            if os.listdir(directory):
                self.printer.out(f"Directory '{directory}' not empty.", level=2)
            else:
                self.printer.out(f"Deleting directory '{directory}'.", level=2)
                if not self.dry_run:
                    shutil.rmtree(directory)
                    n_deleted += 1
        except OSError as e:
            if report_errors:
                self.printer.out(f"Delete failed on directory '{directory}': {e}", level=2)
        return n_deleted

    @staticmethod
    def _strip_leading_dir(path):
        idx = path.find('/')
        if idx >= 0:
            return path[idx + 1:]

    @staticmethod
    def prepend_path(a_dict: dict, label: str, value: str) -> None:
        """Prepend the value to every instance of the label in dict a_dict"""
        for k in a_dict:
            if isinstance(a_dict[k], dict):
                ExtensionEngine.prepend_path(a_dict[k], label, value)
            elif k == label:
                a_dict[k] = os.path.join(value, a_dict[k])

    # def transfer(self, root_src_dir):
    #     """For transfering contents of an old 'user' directory into the new one."""
    #     if not os.path.isdir(root_src_dir):
    #         sys.exit(f"{root_src_dir} is not a directory")
    #     root_dst_dir = self.root_dict['USER_DIR']
    #     self.printer.out(f"Transferring contents of {root_src_dir} to {root_dst_dir}", 1)
    #     if self.dry_run:
    #         self.printer.out(f"This is a {bcolors.BOLD}dry run{bcolors.ENDC}. "
    #                         f"Nothing will actually be done.")
    #
    #     for dirpath, dirnames, filenames in os.walk(root_src_dir):
    #         if os.path.basename(dirpath) in {'__pycache__', '.init'}:
    #             self.printer.out(f"Skipping {dirpath}.", 3)
    #             continue
    #         dst_dir = dirpath.replace(root_src_dir, root_dst_dir, 1)
    #         self.printer.out(f"Making directory {dst_dir}", 3)
    #         if not self.dry_run:
    #             os.makedirs(dst_dir, exist_ok=True)
    #         for f in filenames:
    #             if ".pyc" in f:
    #                 self.printer.out(f"Skipping {f}", 3)
    #                 continue
    #             dst_file = os.path.join(dst_dir, f)
    #             if os.path.exists(dst_file):
    #                 self.printer.out(f"File {dst_file} already exists. Not replacing.", 2)
    #             else:
    #                 src_file = os.path.join(dirpath, f)
    #                 self.printer.out(f"Copying file {src_file} to {dst_dir}", 3)
    #                 if not self.dry_run:
    #                     shutil.copy(src_file, dst_dir)
    #     if self.dry_run:
    #         self.printer.out("This was a dry run. Nothing was actually done")
