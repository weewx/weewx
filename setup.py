#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
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
    password information in the configuration file weewx.conf

 2. It merges any existing weewx.conf configuration files into the new, thus
    preserving any user changes.
    
 3. It merges any existing Standard/skin.conf configuration file into the new, thus
    preserving any user changes.
    
 4. It sets the option ['Station']['WEEWX_ROOT'] in weewx.conf to reflect
    the actual installation directory (as set in setup.cfg or specified
    in the command line to setup.py install)
    
 5. In a similar manner, it sets WEEWX_ROOT in the daemon startup script.

 6. It backs up any pre-existing skin subdirectory
 
 7. It backs up any pre-existing bin subdirectory.
"""

import sys
import os
import os.path
import re
import time
import tempfile
import shutil
import configobj

from distutils.core import setup
from distutils.command.install_data import install_data
from distutils.command.install_lib  import install_lib
from distutils.command.sdist import sdist

# Make sure we can find the bin subdirectory:
this_file = os.path.join(os.getcwd(), __file__)
bin_dir = os.path.abspath(os.path.join(os.path.dirname(this_file), 'bin'))
sys.path.insert(0, bin_dir)

from weewx import __version__ as VERSION

class My_install_lib(install_lib):
    """Specialized version of install_lib
    
    This version:
    
    - Backs up the old ./bin subdirectory before installing.
    """ 

    def run(self):
        if os.path.exists(self.install_dir):
            bin_backupdir = backup(self.install_dir)
            print "Backed up bin subdirectory to %s" % bin_backupdir

        # Run the superclass's run:
        install_lib.run(self)
        
class My_install_data(install_data):
    """Specialized version of install_data 
    
    This version: 
    
      - Sets WEEWX_ROOT in the configuration file to reflect the
        the location of the install directory;
      - Merges an old week.conf configuration file into a new,
        thus preserving any changes made by the user;
      - Merges an old skin.conf file into a new, thus preserving
        any changes;
      - Backs up the old skin directory;
      - Massages the daemon start up script to reflect the choice
        of WEEWX_ROOT        
    """
    
    def copy_file(self, f, install_dir, **kwargs):
        rv = None
        # If this is the configuration file, then merge it instead
        # of copying it
        if f == 'weewx.conf':
            rv = self.massageWeewxConfigFile(f, install_dir, **kwargs)
        elif f == 'skins/Standard/skin.conf':
            rv = self.massageSkinConfigFile(f, install_dir, **kwargs)
        elif f in ('start_scripts/Debian/weewx', 'start_scripts/SuSE/weewx'):
            rv = self.massageStartFile(f, install_dir, **kwargs)
        else:
            rv = install_data.copy_file(self, f, install_dir, **kwargs)
        return rv
    
    def run(self):
            
        # Back up the old skin directory if it exists
        skin_dir = os.path.join(self.install_dir, 'skins')
        if os.path.exists(skin_dir):
            self.skin_backupdir = backup(skin_dir)
            print "Backed up skins subdirectory to %s" % self.skin_backupdir
            
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
        
        # Shut off the debug flag:
        new_config['debug'] = 0

        # Check to see if there is an existing config file.
        # If so, merge its contents with the new one
        if os.path.exists(config_path):
            old_config = configobj.ConfigObj(config_path)
            old_version = old_config.get('version')
            # If the version number does not appear at all, then
            # assume a very old version:
            if not old_version: old_version = '1.0.0'
            old_version_number = old_version.split('.')
            # Do the merge only for versions >= 1.7
            if old_version_number[0:2] >= ['1','7']:
                new_svc_list = new_config['Engines']['WxEngine']['service_list']
                old_svc_list = old_config['Engines']['WxEngine']['service_list']
                for svc in old_svc_list:
                    if svc not in new_svc_list and svc not in ['weewx.wxengine.StdCatchUp', 
                                                               'weewx.wxengine.StdWunderground']:
                        new_svc_list.append(svc)
                # Any user changes in old_config will overwrite values in new_config
                # with this merge
                new_config.merge(old_config)
                # Now correct the new service list:
                new_config['Engines']['WxEngine']['service_list'] = new_svc_list
                        
        # Make sure WEEWX_ROOT reflects the choice made in setup.cfg:
        new_config['Station']['WEEWX_ROOT'] = self.install_dir
        # Add the version:
        new_config['version'] = VERSION

        # Options heating_base and cooling_base have moved.
        new_config['Station'].pop('heating_base', None)
        new_config['Station'].pop('cooling_base', None)
        # Wunderground has been put under section ['RESTful']:
        new_config.pop('Wunderground', None)
        # Name change from StdWunderground to StdRESTful:
        new_config['Engines']['WxEngine']['service_list'] =\
            [svc.replace('StdWunderground', 'StdRESTful') for svc in\
             new_config['Engines']['WxEngine']['service_list']]
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
        
    def massageSkinConfigFile(self, f, install_dir, **kwargs):
        """Merges an old skin.conf file into the new one"""
        
        # The path name of the final output file:
        new_skin_config_path = os.path.join(install_dir, os.path.basename(f))
        
        # Create a ConfigObj using the new contents:
        new_skin_config = configobj.ConfigObj(f)
        new_skin_config.indent_type = '    '
        
        # If the backed up skin directory doesn't exist, we'll get
        # an attribute error. Skip the merge in this case.
        try:
            old_skin_config_path = os.path.join(self.skin_backupdir, 'Standard/skin.conf')
            # Check to see if there is an existing skin.conf file.
            # If so, merge its contents with the new one
            if os.path.exists(old_skin_config_path):
                old_skin_config = configobj.ConfigObj(old_skin_config_path)
                # Any user changes in the old skin.conf will overwrite
                # values in the new skin.conf file with this merge
                new_skin_config.merge(old_skin_config)
        except AttributeError:
            pass
        
        # Add the version:
        new_skin_config['version'] = VERSION

        # Get a temporary file:
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        
        # Write the new configuration file to it:
        new_skin_config.write(tmpfile)
        
        # Now install the temporary file (holding the merged config data)
        # into the proper place:
        rv = install_data.copy_file(self, tmpfile.name, new_skin_config_path, **kwargs)
        
        # Set the permission bits unless this is a dry run:
        if not self.dry_run:
            shutil.copymode(f, new_skin_config_path)

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

def backup(filepath):
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    os.rename(filepath, newpath)
    return newpath

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
            # If we're working with the configuration file, make sure it doesn't
            # have any private data in it.
            config = configobj.ConfigObj(f)

            if config.has_key('Reports') and config['Reports'].has_key('FTP') and config['Reports']['FTP'].has_key('password'):
                sys.stderr.write("\n*** FTP password found in configuration file. Aborting ***\n\n")
                exit()

            rest_dict = config['RESTful']
            if rest_dict.has_key('Wunderground') and rest_dict['Wunderground'].has_key('password'):
                sys.stderr.write("\n*** Wunderground password found in configuration file. Aborting ***\n\n")
                exit()
            if rest_dict.has_key('PWSweather') and rest_dict['PWSweather'].has_key('password'):
                sys.stderr.write("\n*** PWSweather password found in configuration file. Aborting ***\n\n")
                exit()
                
        # Pass on to my superclass:
        return sdist.copy_file(self, f, install_dir, **kwargs)

setup(name='weewx',
      version=VERSION,
      description='The weewx weather system',
      long_description="The weewx weather system manages a Davis VantagePro "
      "weather station. It generates plots, statistics, and HTML pages of the "
      "current and historical weather",
      author='Tom Keffer',
      author_email='tkeffer@gmail.com',
      url='http://www.weewx.com',
      package_dir = {'' : 'bin'},
      packages    = ['weewx', 'weeplot', 'weeutil', 'examples'],
      py_modules  = ['daemon'],
      scripts     = ['bin/configure.py', 'bin/weewxd.py'],
      data_files  = [('',                           ['CHANGES.txt', 'LICENSE.txt', 'README', 'weewx.conf']),
                     ('docs',                       ['docs/customizing.htm', 'docs/readme.htm', 
                                                     'docs/sheeva.htm', 'docs/upgrading.htm',
                                                     'docs/daytemp_with_avg.png', 'docs/weekgustoverlay.png']),
                     ('skins/Ftp',                  ['skins/Ftp/skin.conf']),
                     ('skins/Standard/backgrounds', ['skins/Standard/backgrounds/band.gif']),
                     ('skins/Standard/NOAA',        ['skins/Standard/NOAA/NOAA-YYYY.txt.tmpl', 'skins/Standard/NOAA/NOAA-YYYY-MM.txt.tmpl']),
                     ('skins/Standard/RSS',         ['skins/Standard/RSS/weewx_rss.xml.tmpl']),
                     ('skins/Standard',             ['skins/Standard/index.html.tmpl', 'skins/Standard/month.html.tmpl',
                                                     'skins/Standard/skin.conf', 'skins/Standard/week.html.tmpl',
                                                     'skins/Standard/weewx.css', 'skins/Standard/year.html.tmpl']), 
                     ('start_scripts/Debian',       ['start_scripts/Debian/weewx']),
                     ('start_scripts/SuSE',          ['start_scripts/SuSE/weewx'])],
      requires    = ['configobj(>=4.5)', 'pyserial(>=2.3)', 'Cheetah(>=2.0)', 'pysqlite(>=2.5)', 'PIL(>=1.1.6)'],
      cmdclass    = {"install_data" : My_install_data,
                     "install_lib"  : My_install_lib,
                     "sdist" :        My_sdist}
      )
