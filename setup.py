#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Customized setup file for weewx.

For more debug information, set the environment variable DISTUTILS_DEBUG
before running.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import fnmatch
import os
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
from distutils import log
from distutils.command.install import install
from distutils.command.install_data import install_data
from distutils.command.install_lib import install_lib
from distutils.core import setup
from distutils.debug import DEBUG

VERSION = "4.8.0"

if sys.version_info < (2, 7):
    log.fatal('WeeWX requires Python V2.7 or greater.')
    log.fatal('For earlier versions of Python, use WeeWX V3.9.')
    sys.exit("Python version unsupported.")

this_file = os.path.join(os.getcwd(), __file__)
this_dir = os.path.abspath(os.path.dirname(this_file))


# ==============================================================================
# install
# ==============================================================================

class weewx_install(install):
    """Specialized version of install, which adds a '--no-prompt' option, and which runs a
    wee_config post-install script"""

    # Add an option for --no-prompt. This will be passed on to wee_config
    user_options = install.user_options + [('no-prompt', None, 'Do not prompt for station info')]

    def initialize_options(self, *args, **kwargs):
         install.initialize_options(self, *args, **kwargs)
         self.no_prompt = None

    def finalize_options(self):
        # Call my superclass's version
        install.finalize_options(self)
        # Unless the --force flag has been explicitly set, default to True. This will
        # cause files to be installed even if they are older than their target."""
        if self.force is None:
            self.force = 1
        if self.no_prompt is None:
            self.no_prompt = 0

    def run(self):
        """Specialized version of run, which runs post-install commands"""

        # First run the install.
        rv = install.run(self)

        # Now the post-install
        update_and_install_config(self.install_data, self.install_scripts, self.install_lib,
                                  self.no_prompt)

        return rv


# ==============================================================================
# install_lib
# ==============================================================================

class weewx_install_lib(install_lib):
    """Specialized version of install_lib, which saves and restores the 'user' subdirectory."""

    def run(self):
        """Specialized version of run that saves, then restores, the 'user' subdirectory."""

        # Save any existing 'user' subdirectory:
        user_dir = os.path.join(self.install_dir, 'user')
        if not self.dry_run and os.path.exists(user_dir):
            user_backup_dir = user_dir + ".bak"
            shutil.move(user_dir, user_backup_dir)
        else:
            user_backup_dir = None

        # Run the superclass's version. This will install a new 'user' subdirectory.
        install_lib.run(self)

        # Restore the 'user' subdirectory
        if user_backup_dir:
            # Delete the freshly installed user subdirectory
            shutil.rmtree(user_dir)
            # Replace it with our saved version.
            shutil.move(user_backup_dir, user_dir)


# ==============================================================================
# install_data
# ==============================================================================

class weewx_install_data(install_data):
    """Specialized version of install_data."""

    def run(self):
        # If there is a skins directory already, just install what the user doesn't already have.
        if os.path.exists(os.path.join(self.install_dir, 'skins')):
            # A skins directory already exists. Build a list of skins that are missing and should
            # be added to it.
            install_files = []
            for skin_name in ['Ftp', 'Mobile', 'Rsync', 'Seasons', 'Smartphone', 'Standard']:
                rel_name = 'skins/' + skin_name
                if not os.path.exists(os.path.join(self.install_dir, rel_name)):
                    # The skin has not already been installed. Include it.
                    install_files += [dat for dat in self.data_files if
                                      dat[0].startswith(rel_name)]
            # Exclude all the skins files...
            other_files = [dat for dat in self.data_files if not dat[0].startswith('skins')]
            # ... then add the needed skins back in
            self.data_files = other_files + install_files

        # Run the superclass's run():
        return install_data.run(self)

    def copy_file(self, f, install_dir, **kwargs):
        # If this is the configuration file, then process it separately
        if f == 'weewx.conf':
            rv = self.process_config_file(f, install_dir, **kwargs)
        else:
            rv = install_data.copy_file(self, f, install_dir, **kwargs)
        return rv

    def process_config_file(self, f, install_dir, **kwargs):
        """Process the configuration file weewx.conf by inserting the proper path into WEEWX_ROOT,
        then install as weewx.conf.X.Y.Z, where X.Y.Z is the version number."""

        # The install directory. The normalization is necessary because sometimes there
        # is a trailing '/'.
        norm_install_dir = os.path.normpath(install_dir)

        # The path to the destination configuration file. It will look
        # something like '/home/weewx/weewx.conf.4.0.0'
        weewx_install_path = os.path.join(norm_install_dir, os.path.basename(f) + '.' + VERSION)

        if self.dry_run:
            return weewx_install_path, 0

        # This RE is for finding the assignment to WEEWX_ROOT.
        # It matches the assignment, plus an optional comment. For example, for the string
        #   '  WEEWX_ROOT = foo  # A comment'
        # it matches 3 groups:
        #   Group 1: '  WEEWX_ROOT '
        #   Group 2: ' foo'
        #   Group 3: '  # A comment'
        pattern = re.compile(r'(^\s*WEEWX_ROOT\s*)=(\s*\S+)(\s*#?.*)')

        done = 0

        if self.verbose:
            log.info("massaging %s -> %s", f, weewx_install_path)

        # Massage the incoming file, assigning the right value for WEEWX_ROOT. Use a temporary
        # file. This will help in making the operatioin atomic.
        try:
            # Open up the incoming configuration file
            with open(f, mode='rt') as incoming_fd:
                # Open up a temporary file
                tmpfd, tmpfn = tempfile.mkstemp()
                with os.fdopen(tmpfd, 'wt') as tmpfile:
                    # Go through the incoming template file line by line, inserting a value for
                    # WEEWX_ROOT. There's only one per file, so stop looking after the first one.
                    for line in incoming_fd:
                        if not done:
                            line, done = pattern.subn("\\1 = %s\\3" % norm_install_dir, line)
                        tmpfile.write(line)

            if not self.dry_run:
                # If not a dry run, install the temporary file in the right spot
                rv = install_data.copy_file(self, tmpfn, weewx_install_path, **kwargs)
                # Set the permission bits:
                shutil.copymode(f, weewx_install_path)
        finally:
            # Get rid of the temporary file
            os.remove(tmpfn)

        return rv


# ==============================================================================
# utilities
# ==============================================================================
def find_files(directory, file_excludes=['*.pyc', "junk*"], dir_excludes=['*/__pycache__']):
    """Find all files under a directory, honoring some exclusions.

    Returns:
        A list of two-way tuples (directory_path, file_list), where file_list is a list
        of relative file paths.
    """
    # First recursively create a list of all the directories
    dir_list = []
    for dirpath, _, _ in os.walk(directory):
        # Make sure the directory name doesn't match the excluded pattern
        if not any(fnmatch.fnmatch(dirpath, d) for d in dir_excludes):
            dir_list.append(dirpath)

    data_files = []
    # Now search each directory for all files
    for d_path in dir_list:
        file_list = []
        # Find all the files in this directory
        for fn in os.listdir(d_path):
            filepath = os.path.join(d_path, fn)
            # Make sure it's a file, and that its name doesn't match the excluded pattern
            if os.path.isfile(filepath) \
                    and not any(fnmatch.fnmatch(filepath, f) for f in file_excludes):
                file_list.append(filepath)
        # Add the directory and the list of files in it, to the list of all files.
        data_files.append((d_path, file_list))
    return data_files


def update_and_install_config(install_dir, install_scripts, install_lib, no_prompt=False,
                              config_name='weewx.conf'):
    """Install the configuration file, weewx.conf, updating it if necessary.

    install_dir: the directory containing the configuration file.

    install_scripts: the directory containing the weewx executables.

    install_lib: the directory containing the weewx packages.

    no_prompt: Pass a '--no-prompt' flag on to wee_config.

    config_name: the name of the configuration file. Defaults to 'weewx.conf'
    """

    # This is where the weewx.conf file will go
    config_path = os.path.join(install_dir, config_name)

    # Is there an existing file?
    if os.path.isfile(config_path):
        # Yes, so this is an upgrade
        args = [sys.executable,
                os.path.join(install_scripts, 'wee_config'),
                '--upgrade',
                '--config=%s' % config_path,
                '--dist-config=%s' % config_path + '.' + VERSION,
                '--output=%s' % config_path,
                ]
    else:
        # No existing config file, so this is a fresh install.
        args = [sys.executable,
                os.path.join(install_scripts, 'wee_config'),
                '--install',
                '--dist-config=%s' % config_path + '.' + VERSION,
                '--output=%s' % config_path,
                ]
        # Add the --no-prompt flag if the user requested it.
        if no_prompt:
            args += ['--no-prompt']

    if DEBUG:
        log.info("Command used to invoke wee_config: %s" % args)

    # Add the freshly installed WeeWX modules to PYTHONPATH, so wee_config can find them.
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] = install_lib + os.pathsep + os.environ['PYTHONPATH']
    else:
        os.environ['PYTHONPATH'] = install_lib
    # Run wee_config in a subprocess.
    proc = subprocess.Popen(args,
                            stdin=sys.stdin,
                            stdout=sys.stdout,
                            stderr=sys.stderr)
    out, err = proc.communicate()
    if DEBUG and out:
        log.info('out=', out.decode())
    if DEBUG and err:
        log.info('err=', err.decode())


# ==============================================================================
# main entry point
# ==============================================================================

if __name__ == "__main__":
    setup(name='weewx',
          version=VERSION,
          description='The WeeWX weather software system',
          long_description="WeeWX interacts with a weather station to produce graphs, reports, "
                           "and HTML pages.  WeeWX can upload data to services such as the "
                           "WeatherUnderground, PWSweather.com, or CWOP.",
          author='Tom Keffer',
          author_email='tkeffer@gmail.com',
          url='http://www.weewx.com',
          license='GPLv3',
          py_modules=['daemon', 'six'],
          package_dir={'': 'bin'},
          packages=['schemas',
                    'user',
                    'weecfg',
                    'weedb',
                    'weeimport',
                    'weeplot',
                    'weeutil',
                    'weewx',
                    'weewx.drivers'],
          scripts=['bin/wee_config',
                   'bin/wee_database',
                   'bin/wee_debug',
                   'bin/wee_device',
                   'bin/wee_extension',
                   'bin/wee_import',
                   'bin/wee_reports',
                   'bin/weewxd',
                   'bin/wunderfixer'],
          data_files=[('', ['LICENSE.txt', 'README.md', 'weewx.conf']), ]
                     + find_files('docs')
                     + find_files('examples')
                     + find_files('skins')
                     + find_files('util'),
          cmdclass={
              "install": weewx_install,
              "install_data": weewx_install_data,
              "install_lib": weewx_install_lib,
          },
          )
