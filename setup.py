#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    $Revision$
#    $Author$
#    $Date$
#
""" Customized weewx setup script.

    In addition to the normal setup script duties, this script does the
    following:

 1. When building a source distribution ('sdist') it checks for
    password information in the configuration file weewx.conf and
    that US units are the standard units.

 2. It merges any existing weewx.conf configuration files into the new, thus
    preserving any user changes.
    
 3. It installs the skins subdirectory only if the user doesn't already 
    have one.
    
 4. It sets the option ['Station']['WEEWX_ROOT'] in weewx.conf to reflect
    the actual installation directory (as set in setup.cfg or specified
    in the command line to setup.py install)
    
 5. In a similar manner, it sets WEEWX_ROOT in the daemon startup script.

 6. It backs up any pre-existing bin subdirectory.
 
 7. It conserves the ./bin/user subdirectory.
"""

import os
import os.path
import re
import shutil
import sys
import tempfile
import time
import configobj

from distutils.core import setup
from distutils.command.install_data import install_data
from distutils.command.install_lib  import install_lib
from distutils.command.sdist import sdist
import distutils.dir_util

# Make sure we can find the bin subdirectory:
this_file = os.path.join(os.getcwd(), __file__)
bin_dir = os.path.abspath(os.path.join(os.path.dirname(this_file), 'bin'))
sys.path.insert(0, bin_dir)

from weewx import __version__ as VERSION

#===============================================================================
#                            My_install_lib
#===============================================================================

class My_install_lib(install_lib):
    """Specialized version of install_lib
    
    This version:
    
    - Backs up the old ./bin subdirectory before installing.
    - Conserves the ./bin/user subdirectory
    """ 

    def run(self):
        # Back up any existing 'bin' subdirectory:
        if os.path.exists(self.install_dir):
            bin_backupdir = backup(self.install_dir)
            print "Backed up bin subdirectory to %s" % bin_backupdir
        else:
            bin_backupdir = None

        # Run the superclass's version:
        install_lib.run(self)
        
        # If the bin subdirectory previously existed, and if it included
        # a 'user' subsubdirectory, then restore it
        if bin_backupdir:
            user_backupdir = os.path.join(bin_backupdir, 'user')
            if os.path.exists(user_backupdir):
                user_dir = os.path.join(self.install_dir, 'user')
                distutils.dir_util.copy_tree(user_backupdir, user_dir)

        # Remove weeutil/Almanac, which is no longer in the distribution:
        try:
            os.remove(os.path.join(self.install_dir, 'weeutil/Almanac.py'))
            os.remove(os.path.join(self.install_dir, 'weeutil/Almanac.pyc'))
        except:
            pass
       
            
#===============================================================================
#                         install_data
#===============================================================================

class My_install_data(install_data):
    """Specialized version of install_data 
    
    This version: 
    
      - Sets WEEWX_ROOT in the configuration file to reflect the
        the location of the install directory;
      - Merges an old week.conf configuration file into a new,
        thus preserving any changes made by the user;
      - Massages the daemon start up script to reflect the choice
        of WEEWX_ROOT;
      - Installs the skins subdirectory only if the user doesn't
        already have one.
    """
    
    def copy_file(self, f, install_dir, **kwargs):
        rv = None

        # If this is the configuration file, then merge it instead
        # of copying it
        if f == 'weewx.conf':
            rv = self.massageWeewxConfigFile(f, install_dir, **kwargs)
        elif f in ('start_scripts/Debian/weewx', 'start_scripts/SuSE/weewx'):
            rv = self.massageStartFile(f, install_dir, **kwargs)
        else:
            rv = install_data.copy_file(self, f, install_dir, **kwargs)
        return rv
    
    def run(self):
        # If there is an existing skins subdirectory, do not overwrite it.
        if os.path.exists(os.path.join(self.install_dir, 'skins')):
            # Do this by filtering it out of the list of subdirectories to be installed:
            self.data_files = filter(lambda dat : not dat[0].startswith('skins/'), self.data_files)

        # If the file #upstream.last exists, delete it, as it is no longer used.
        try:
            os.remove(os.path.join(self.install_dir, 'public_html/#upstream.last'))
        except:
            pass
            
        # If the file $WEEWX_INSTALL/readme.htm exists, delete it. It's
        # the old readme (since replaced with docs/readme.htm)
        try:
            os.remove(os.path.join(self.install_dir, 'readme.htm'))
        except:
            pass
        
        # If the file $WEEWX_INSTALL/CHANGES.txt exists, delete it. It's
        # been moved to the docs subdirectory
        try:
            print os.path.join(self.install_dir, 'CHANGES.txt')
            os.remove(os.path.join(self.install_dir, 'CHANGES.txt'))
        except:
            pass
        
        # Clean up after a bad install from earlier versions of setup.py:
        try:
            os.remove(os.path.join(self.install_dir, 'start_scripts/weewx'))
        except:
            pass

        # Run the superclass's run():
        install_data.run(self)
        
       
    def massageWeewxConfigFile(self, f, install_dir, **kwargs):
        """Merges any old config file into the new one, and sets WEEWX_ROOT
        
        If an old configuration file exists, it will merge the contents
        into the new file. It also sets variable ['Station']['WEEWX_ROOT']
        to reflect the installation directory"""
        
        # The path name of the weewx.conf configuration file:
        config_path = os.path.join(install_dir, os.path.basename(f))
        
        # Create a ConfigObj using the new contents:
        new_config = configobj.ConfigObj(f)
        new_config.indent_type = '    '
        new_version_number = VERSION.split('.')
        if len(new_version_number[1]) < 2: 
            new_version_number[1] = '0'+new_version_number[1]
        
        # Sometimes I forget to turn the debug flag off:
        new_config['debug'] = 0
        
        # And forget that while my rain year starts in October, 
        # for most people it starts in January!
        new_config['Station']['rain_year_start'] = 1

        # The default target conversion units should be 'US':
        new_config['StdConvert']['target_unit'] = 'US'
                
        # Check to see if there is an existing config file.
        # If so, merge its contents with the new one
        if os.path.exists(config_path):
            old_config = configobj.ConfigObj(config_path)
            old_version = old_config.get('version')
            # If the version number does not appear at all, then
            # assume a very old version:
            if not old_version: old_version = '1.0.0'
            old_version_number = old_version.split('.')
            # Take care of the collation problem when comparing things like 
            # version '1.9' to '1.10' by prepending a '0' to the former:
            if len(old_version_number[1]) < 2: 
                old_version_number[1] = '0'+old_version_number[1]

            # I don't know how to merge older, V1.X configuration files, only
            # newer V2.X ones.
            if old_version_number[0:2] >= ['2','00']:
                # Any user changes in old_config will overwrite values in new_config
                # with this merge
                new_config.merge(old_config)
                        
        # Make sure WEEWX_ROOT reflects the choice made in setup.cfg:
        new_config['Station']['WEEWX_ROOT'] = self.install_dir
        # Add the version:
        new_config['version'] = VERSION

        # Get a temporary file:
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        
        # Write the new configuration file to it:
        new_config.write(tmpfile)
        
        # Back up the old config file if it exists:
        if os.path.exists(config_path):
            backup_path = backup(config_path)
            print "Backed up old configuration file as %s" % backup_path
            
        # Now install the temporary file (holding the merged config data)
        # into the proper place:
        rv = install_data.copy_file(self, tmpfile.name, config_path, **kwargs)
        
        # Set the permission bits unless this is a dry run:
        if not self.dry_run:
            shutil.copymode(f, config_path)

        return rv

    def massageStartFile(self, f, install_dir, **kwargs):

        outname = os.path.join(install_dir, os.path.basename(f))
        sre = re.compile(r"WEEWX_ROOT\s*=")

        infile = open(f, "r")
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        
        for line in infile:
            if sre.match(line):
                tmpfile.writelines("WEEWX_ROOT=%s\n" % self.install_dir)
            else:
                tmpfile.writelines(line)
        
        rv = install_data.copy_file(self, tmpfile.name, outname, **kwargs)

        # Set the permission bits unless this is a dry run:
        if not self.dry_run:
            shutil.copymode(f, outname)

        return rv

#===============================================================================
#                                  sdist
#===============================================================================

class My_sdist(sdist):
    """Specialized version of sdist which checks for password information in distribution

    See http://epydoc.sourceforge.net/stdlib/distutils.command.sdist.sdist-class.html
    for possible sdist instance methods."""

    def copy_file(self, f, install_dir, **kwargs):
        """Specialized version of copy_file.

        Return a tuple (dest_name, copied): 'dest_name' is the actual name of
        the output file, and 'copied' is true if the file was copied (or would
        have been copied, if 'dry_run' true)."""
        # If this is the configuration file, then massage it to eliminate
        # the password info
        if f == 'weewx.conf':
            config = configobj.ConfigObj(f)

            # If we're working with the configuration file, make sure it doesn't
            # have any private data in it.

            if config.has_key('StdReport') and config['StdReport'].has_key('FTP') and config['StdReport']['FTP'].has_key('password'):
                sys.stderr.write("\n*** FTP password found in configuration file. Aborting ***\n\n")
                exit()

            rest_dict = config['StdRESTful']
            if rest_dict.has_key('Wunderground') and rest_dict['Wunderground'].has_key('password'):
                sys.stderr.write("\n*** Wunderground password found in configuration file. Aborting ***\n\n")
                exit()
            if rest_dict.has_key('PWSweather') and rest_dict['PWSweather'].has_key('password'):
                sys.stderr.write("\n*** PWSweather password found in configuration file. Aborting ***\n\n")
                exit()
                
        # Pass on to my superclass:
        return sdist.copy_file(self, f, install_dir, **kwargs)

#===============================================================================
#                         utility functions
#===============================================================================
def backup(filepath):
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    if os.path.isdir(filepath):
        distutils.dir_util.copy_tree(filepath, newpath)
    else:
        distutils.file_util.copy_file(filepath, newpath)
    return newpath

setup(name='weewx',
      version=VERSION,
      description='The weewx weather system',
      long_description="""The weewx weather system manages a Davis VantagePro
      weather station. It generates plots, statistics, and HTML pages of the
      current and historical weather""",
      author='Tom Keffer',
      author_email='tkeffer@gmail.com',
      url='http://www.weewx.com',
      package_dir = {'' : 'bin'},
      packages    = ['weewx', 'weeplot', 'weeutil', 'examples', 'user'],
      py_modules  = ['daemon'],
      scripts     = ['bin/config_database.py', 'bin/config_vp.py', 'bin/weewxd.py', 'bin/runreports.py'],
      data_files  = [('',                           ['LICENSE.txt', 'README', 'weewx.conf']),
                     ('docs',                       ['docs/CHANGES.txt', 'docs/customizing.htm', 
                                                     'docs/daytemp_with_avg.png', 'docs/debian.htm', 
                                                     'docs/readme.htm', 'docs/samaxesjs.toc-1.5.min.js', 
                                                     'docs/sheeva.htm', 'docs/upgrading.htm',
                                                     'docs/usersguide.htm', 'docs/weekgustoverlay.png', 
                                                     'docs/weewx_docs.css']),
                     ('skins/Ftp',                  ['skins/Ftp/skin.conf']),
                     ('skins/Standard/backgrounds', ['skins/Standard/backgrounds/band.gif']),
                     ('skins/Standard/NOAA',        ['skins/Standard/NOAA/NOAA-YYYY.txt.tmpl', 'skins/Standard/NOAA/NOAA-YYYY-MM.txt.tmpl']),
                     ('skins/Standard/RSS',         ['skins/Standard/RSS/weewx_rss.xml.tmpl']),
                     ('skins/Standard/smartphone',  ['skins/Standard/smartphone/barometer.html.tmpl',    'skins/Standard/smartphone/custom.js',
                                                     'skins/Standard/smartphone/humidity.html.tmpl',     'skins/Standard/smartphone/index.html.tmpl',
                                                     'skins/Standard/smartphone/radar.html.tmpl',        'skins/Standard/smartphone/rain.html.tmpl',
                                                     'skins/Standard/smartphone/temp_outside.html.tmpl', 'skins/Standard/smartphone/wind.html.tmpl']),
                     ('skins/Standard/smartphone/icons',['skins/Standard/smartphone/icons/icon_ipad_x1.png', 'skins/Standard/smartphone/icons/icon_ipad_x2.png',
                                                     'skins/Standard/smartphone/icons/icon_iphone_x1.png','skins/Standard/smartphone/icons/icon_iphone_x2.png']),
                     ('skins/Standard',             ['skins/Standard/favicon.ico',
                                                     'skins/Standard/mobile.css', 'skins/Standard/mobile.html.tmpl',
                                                     'skins/Standard/index.html.tmpl', 'skins/Standard/month.html.tmpl',
                                                     'skins/Standard/skin.conf', 'skins/Standard/week.html.tmpl',
                                                     'skins/Standard/weewx.css', 'skins/Standard/year.html.tmpl']), 
                     ('start_scripts/Debian',       ['start_scripts/Debian/weewx']),
                     ('start_scripts/SuSE',         ['start_scripts/SuSE/weewx'])],
      requires    = ['configobj(>=4.5)', 'serial(>=2.3)', 'Cheetah(>=2.0)', 'sqlite3(>=2.5)', 'PIL(>=1.1.6)'],
      cmdclass    = {"install_data" : My_install_data,
                     "install_lib"  : My_install_lib,
                     "sdist" :        My_sdist}
      )
