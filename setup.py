#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
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

import distutils.dir_util
import distutils.file_util
import fnmatch
import os.path
import shutil
import subprocess
import sys
from distutils.command.install_data import install_data
from distutils.command.install_lib import install_lib
from distutils.debug import DEBUG

from setuptools import setup, find_packages
from setuptools.command.install import install

if sys.version_info < (2, 7):
    print('WeeWX requires Python V2.7 or greater.')
    print('For earlier versions of Python, use WeeWX V3.9.')
    sys.exit("Python version unsupported.")

# Find the subdirectory in the distribution that contains the weewx libraries:
this_file = os.path.join(os.getcwd(), __file__)
this_dir = os.path.abspath(os.path.dirname(this_file))
lib_dir = os.path.abspath(os.path.join(this_dir, 'bin'))

# Now that we've found where the libraries are, inject it into the path:
sys.path.insert(0, lib_dir)

# Now we can get the weewx version
import weewx

VERSION = weewx.__version__


# ==============================================================================
# install
# ==============================================================================

class weewx_install(install):
    """Specialized version of install, which runs a post-install script"""

    def run(self):
        """Specialized version of run, which runs post-install commands"""

        # First run the install.
        rv = install.run(self)

        # Now the post-install
        update_and_install_config(self.install_data, self.install_scripts, self.install_lib)

        return rv


# ==============================================================================
# install_lib
# ==============================================================================

class weewx_install_lib(install_lib):
    """Specialized version of install_lib, which saves the user subdirectory."""

    def run(self):
        # Location of the user subdirectory, if it exists.
        user_dir = os.path.join(self.install_dir, 'user')
        if os.path.exists(user_dir):
            # It exists. Save it under a timestamp
            user_savedir = move_with_timestamp(user_dir)
        else:
            user_savedir = None

        # Run the superclass's version. This will install all incoming files, including
        # a new user subdirectory
        rv = install_lib.run(self)

        # If we set aside an old user subdirectory, restore it
        if user_savedir:
            # Remove the user directory we just installed...
            distutils.dir_util.remove_tree(user_dir)
            # ... then move the saved version back:
            shutil.move(user_savedir, user_dir)
            try:
                # The file schemas.py is no longer used, and can interfere with schema
                # imports. See issue #54.
                os.rename(os.path.join(user_dir, 'schemas.py'),
                          os.path.join(user_dir, 'schemas.py.old'))
            except OSError:
                pass
            try:
                os.remove(os.path.join(user_dir, 'schemas.pyc'))
            except OSError:
                pass

        return rv


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
        """Process weewx.conf separately"""

        # Location of the incoming weewx.conf file
        install_path = os.path.join(install_dir, os.path.basename(f))

        if self.dry_run:
            rv = None
        else:
            # Install the config file using the template name. Later, we will merge
            # it with any old config file.
            template_name = install_path + "." + VERSION
            rv = install_data.copy_file(self, f, template_name, **kwargs)
            shutil.copymode(f, template_name)

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
            # Make sure it's a file, and that it's name doesn't match the excluded pattern
            if os.path.isfile(filepath) \
                    and not any(fnmatch.fnmatch(filepath, f) for f in file_excludes):
                file_list.append(filepath)
        # Add the directory and the list of files in it, to the list of all files.
        data_files.append((d_path, file_list))
    return data_files


def move_with_timestamp(filepath):
    """Save a file to a path with a timestamp."""
    import shutil
    import time
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    # Check to see if this name already exists
    if os.path.exists(newpath):
        # It already exists. Stick a version number on it:
        version = 1
        while os.path.exists(newpath + '-' + str(version)):
            version += 1
        newpath = newpath + '-' + str(version)
    shutil.move(filepath, newpath)
    return newpath


def update_and_install_config(install_dir, install_scripts, install_lib, config_name='weewx.conf'):
    """Install the configuration file, weewx.conf, updating it if necessary.

    install_dir: the directory containing the configuration file.

    install_scripts: the directory containing the weewx executables.

    install_lib: the directory containing the weewx packages.

    config_name: the name of the configuration file. Defaults to 'weewx.conf'
    """

    # This is where the weewx.conf file will go
    destination = os.path.join(install_dir, config_name)

    # Is there an existing file? If so, use it as the source. Otherwise,
    # use the file that came with the distribution.
    if os.path.isfile(destination):
        source = destination
        no_prompt = True
    else:
        source = os.path.join(install_dir, config_name + '.' + VERSION)
        no_prompt = False

    # Command used to invoke wee_config:
    args = [sys.executable,
            os.path.join(install_scripts, 'wee_config'),
            '--install',
            '--dist-config=%s' % source,
            '--output=%s' % destination,
            ]
    if no_prompt:
        # If we are doing an upgrade, don't prompt.
        args += ['--no-prompt']

    if DEBUG:
        print("Incoming weewx.conf path=%s" % source)
        print("Outgoing weewx.conf path=%s" % destination)
        print("Command used to invoke wee_config: %s" % args)
        print("install_scripts=%s" % install_scripts)
        print("install_lib=%s" % install_lib)
        
    proc = subprocess.Popen(args,
                            env={'PYTHONPATH' : install_lib},
                            stdin=sys.stdin,
                            stdout=sys.stdout,
                            stderr=sys.stderr)
    out, err = proc.communicate()
    if DEBUG and out:
        print('out=', out.decode())
    if DEBUG and err:
        print('err=', err.decode())


# ==============================================================================
# main entry point
# ==============================================================================

if __name__ == "__main__":
    # Use the README.md for the long description:
    with open(os.path.join(this_dir, "README.md"), "r") as fd:
        long_description = fd.read()

    setup(name='weewx',
          version=VERSION,
          description='The WeeWX weather software system',
          long_description=long_description,
          long_description_content_type="text/markdown",
          author='Tom Keffer',
          author_email='tkeffer@gmail.com',
          url='http://www.weewx.com',
          license='GPLv3',
          classifiers=[
              'Development Status :: 5 - Production/Stable',
              'Intended Audience :: End Users/Desktop',
              'Intended Audience :: Science/Research',
              'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
              'Operating System :: POSIX :: Linux',
              'Operating System :: Unix',
              'Programming Language :: Python',
              'Programming Language :: Python :: 2.7',
              'Programming Language :: Python :: 3.5',
              'Programming Language :: Python :: 3.6',
              'Programming Language :: Python :: 3.7',
              'Programming Language :: Python :: 3.8',
              'Topic :: Scientific/Engineering :: Physics'
          ],
          platforms=['any'],
          python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, <4',
          install_requires=[
              'cheetah>=2.4; python_version=="2.7"',
              'cheetah3>=3.2<4.0; python_version>="3.5"',
              'pillow>=2<7; python_version=="2.7"',
              'pillow>=5.2; python_version>="3.5" and python_version<"3.8"',
              'pillow>=7; python_version>="3.8"',
              'configobj>=4.7',
              'pyephem>=3.7',
              'pyserial>=3.4',
              'pyusb>=1.0.2',
              'six>=1'
          ],
          py_modules=['daemon', 'six'],
          package_dir={'': 'bin'},
          packages=find_packages('bin'),
          scripts=[
              'bin/wee_config',
              'bin/wee_database',
              'bin/wee_debug',
              'bin/wee_device',
              'bin/wee_extension',
              'bin/wee_import',
              'bin/wee_reports',
              'bin/weewxd',
              'bin/wunderfixer'
          ],
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
