#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009, 2010, 2011, 2012, 2013 Tom Keffer <tkeffer@gmail.com>
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
    
 4. It sets the option ['WEEWX_ROOT'] in weewx.conf to reflect
    the actual installation directory (as set in setup.cfg or specified
    in the command line to setup.py install)
    
 5. In a similar manner, it sets WEEWX_ROOT in the daemon startup script.

 6. It saves any pre-existing bin subdirectory.
 
 7. It saves the ./bin/user subdirectory.
"""

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
from distutils.command.install_scripts import install_scripts
from distutils.command.sdist import sdist
import distutils.dir_util

# Find the install bin subdirectory:
this_file = os.path.join(os.getcwd(), __file__)
bin_dir = os.path.abspath(os.path.join(os.path.dirname(this_file), 'bin'))

# Get the version:
save_syspath = list(sys.path)
sys.path.insert(0, bin_dir)
import weewx
VERSION = weewx.__version__
del weewx
sys.path = save_syspath

start_scripts = ['util/init.d/weewx.bsd',
                 'util/init.d/weewx.debian',
                 'util/init.d/weewx.redhat',
                 'util/init.d/weewx.suse']

#===============================================================================
#                            weewx_install_lib
#===============================================================================

class weewx_install_lib(install_lib):
    """Specialized version of install_lib""" 

    def run(self):
        # Determine whether the user is still using an old-style schema
        schema_type = check_schema_type(self.install_dir)

        # Save any existing 'bin' subdirectory:
        if os.path.exists(self.install_dir):
            bin_savedir = save_path(self.install_dir)
            print "Saved bin subdirectory as %s" % bin_savedir
        else:
            bin_savedir = None

        # Run the superclass's version. This will install all incoming files.
        install_lib.run(self)
        
        # If the bin subdirectory previously existed, and if it included
        # a 'user' subsubdirectory, then restore it
        if bin_savedir:
            user_backupdir = os.path.join(bin_savedir, 'user')
            if os.path.exists(user_backupdir):
                user_dir = os.path.join(self.install_dir, 'user')
                distutils.dir_util.copy_tree(user_backupdir, user_dir)

        # But, there is one exception: if the old user subdirectory included an
        # old-style schema, then it should be overwritten with the new version.
        if schema_type == 'old':
            incoming_schema_path = os.path.join(bin_dir, 'user/schemas.py')
            target_path = os.path.join(self.install_dir, 'user/schemas.py')
            distutils.file_util.copy_file(incoming_schema_path, target_path)

#===============================================================================
#                         install_data
#===============================================================================

class weewx_install_data(install_data):
    """Specialized version of install_data """
    
    def copy_file(self, f, install_dir, **kwargs):
        rv = None

        # If this is the configuration file, then merge it instead
        # of copying it
        if f == 'weewx.conf':
            rv = self.process_config_file(f, install_dir, **kwargs)
        elif f in start_scripts:
            rv = self.massageStartFile(f, install_dir, **kwargs)
        else:
            rv = install_data.copy_file(self, f, install_dir, **kwargs)
        return rv
    
    def run(self):
        # If there is an existing skins subdirectory, do not overwrite it.
        if os.path.exists(os.path.join(self.install_dir, 'skins')):
            # Do this by filtering it out of the list of subdirectories to be installed:
            self.data_files = filter(lambda dat : not dat[0].startswith('skins/'), self.data_files)

        remove_obsolete_files(self.install_dir)
        
        # Run the superclass's run():
        install_data.run(self)
       
    def process_config_file(self, f, install_dir, **kwargs):

        # The path where the weewx.conf configuration file will be installed
        install_path = os.path.join(install_dir, os.path.basename(f))
    
        new_config = merge_config_files(f, install_path, install_dir, VERSION)        
        # Get a temporary file:
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        
        # Write the new configuration file to it:
        new_config.write(tmpfile)
        
        # Save the old config file if it exists:
        if os.path.exists(install_path):
            backup_path = save_path(install_path)
            print "Saved old configuration file as %s" % backup_path
            
        # Now install the temporary file (holding the merged config data)
        # into the proper place:
        rv = install_data.copy_file(self, tmpfile.name, install_path, **kwargs)
        
        # Set the permission bits unless this is a dry run:
        if not self.dry_run:
            shutil.copymode(f, install_path)

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
#                         install_scripts
#===============================================================================

class weewx_install_scripts(install_scripts):
    
    def run(self):
    
        # run the superclass's version:
        install_scripts.run(self)
        
        # Add a symbolic link for weewxd.py to weewxd:
        source = './weewxd'
        dest   = os.path.join(self.install_dir, 'weewxd.py')
        os.symlink(source, dest)
        
#===============================================================================
#                                  sdist
#===============================================================================

class weewx_sdist(sdist):
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
def remove_obsolete_files(install_dir):
    """Remove no longer needed files from the installation
    directory, nominally /home/weewx."""
    
    # If the file #upstream.last exists, delete it, as it is no longer used.
    try:
        os.remove(os.path.join(install_dir, 'public_html/#upstream.last'))
    except OSError:
        pass
        
    # If the file $WEEWX_INSTALL/readme.htm exists, delete it. It's
    # the old readme (since replaced with README)
    try:
        os.remove(os.path.join(install_dir, 'readme.htm'))
    except OSError:
        pass
    
    # If the file $WEEWX_INSTALL/CHANGES.txt exists, delete it. It's
    # been moved to the docs subdirectory and renamed
    try:
        os.remove(os.path.join(install_dir, 'CHANGES.txt'))
    except OSError:
        pass
    
    # The directory start_scripts is no longer used
    shutil.rmtree(os.path.join(install_dir, 'start_scripts'), True)
    
    # The file docs/README.txt is now gone
    try:
        os.remove(os.path.join(install_dir, 'docs/README.txt'))
    except OSError:
        pass
    
    # If the file docs/CHANGES.txt exists, delete it. It's been renamed
    # to docs/changes.txt
    try:
        os.remove(os.path.join(install_dir, 'docs/CHANGES.txt'))
    except OSError:
        pass

def check_schema_type(bin_dir):
    """Checks whether the schema in user.schemas is a new style or old style schema.
    
    bin_dir: The directory to be checked. This is nominally /home/weewx/bin.
    
    Returns:
      'none': There is no schema at all.
      'old' : It is an old-style schema.
      'new' : It is a new-style schema
    """
    save_path = list(sys.path)
    sys.path.insert(0, bin_dir)
    
    try:
        import user.schemas
    except ImportError:
        # There is no existing schema at all.
        result = 'none'
    else:
        # There is a schema. Determine if it is old-style or new-style
        try:
            # Try the old style 'drop_list'. If it fails, it must be a new-style schema
            drop_list = user.schemas.drop_list # @UnusedVariable @UndefinedVariable
        except AttributeError:
            # New style schema 
            result = 'new'
        else:
            # It did not fail. Must be an old-style schema
            result = 'old'
        finally:
            del user.schemas

    # Restore the path        
    sys.path = save_path
    
    return result
    
def merge_config_files(new_config_path, old_config_path, weewx_root, version_number):
    """Merges any old config file into the new one, and sets WEEWX_ROOT.
    
    If an old configuration file exists, it will merge the contents
    into the new file. It also sets variable ['WEEWX_ROOT']
    to reflect the installation directory.
    
    new_config_path: Path where the new configuration file can be found.
    
    old_config_path: Path where the old configuration file can be found.
    
    weewx_root: What WEEWX_ROOT should be set to.
    
    version_number: The version number of the new configuration file.
    
    RETURNS:
    
    The (possibly) merged new configuration file.    
    """

    # Create a ConfigObj using the new contents:
    new_config = configobj.ConfigObj(new_config_path)
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
    if os.path.exists(old_config_path):
        old_config = configobj.ConfigObj(old_config_path)
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
            # Update the old version to reflect any changes made since it
            # was created:
            update_config_file(old_config)
            # Now merge the old configuration file into the new file, thus
            # saving any user modifications. First, turn interpolation off:
            old_config.interpolation = False
            # Now merge the old version into the new:
            new_config.merge(old_config)
                    
    # Make sure WEEWX_ROOT reflects the choice made in setup.cfg:
    new_config['WEEWX_ROOT'] = weewx_root
    # Add the version:
    new_config['version'] = version_number
    
    return new_config

def update_config_file(config_dict):
    """Updates a configuration file to reflect any recent changes."""
    
    # Option stats_types is no longer used. Get rid of it.
    config_dict['StdArchive'].pop('stats_types', None)
    
    # Name changes for the Davis Vantage series:
    try:
        if config_dict['Vantage']['driver'].strip() == 'weewx.VantagePro':
            config_dict['Vantage']['driver'] = 'weewx.vantage'
    except KeyError:
        pass
    
    # --- Name changes for the WMR9x8 series ---
    
    # The section name has changed from WMR-918 to WMR9x8
    if config_dict.has_key('WMR-918'):
        if config_dict.has_key('WMR9x8'):
            sys.stderr.write("\n*** Configuration file has both a 'WMR-918' section and a 'WMR9x8' section. Aborting ***\n\n")
            exit()
        config_dict.rename('WMR-918', 'WMR9x8')
    # If necessary, reflect the section name in the station type:
    try:
        if config_dict['Station']['station_type'].strip() == 'WMR-918':
            config_dict['Station']['station_type'] = 'WMR9x8'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if config_dict['WMR9x8']['driver'].strip() == 'weewx.WMR918':
            config_dict['WMR9x8']['driver'] = 'weewx.wmr9x8'
    except KeyError:
        pass

    # --- Name changes for the WMR100 ---
    
    # The section name has changed from WMR-USB to WMR100
    if config_dict.has_key('WMR-USB'):
        if config_dict.has_key('WMR100'):
            sys.stderr.write("\n*** Configuration file has both a 'WMR-USB' section and a 'WMR100' section. Aborting ***\n\n")
            exit()
        config_dict.rename('WMR-USB', 'WMR100')
    # If necessary, reflect the section name in the station type:
    try:
        if config_dict['Station']['station_type'].strip() == 'WMR-USB':
            config_dict['Station']['station_type'] = 'WMR100'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if config_dict['WMR100']['driver'].strip() == 'weewx.wmrx':
            config_dict['WMR100']['driver'] = 'weewx.wmr100'
    except KeyError:
        pass
        
def save_path(filepath):
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    shutil.move(filepath, newpath)
    return newpath

#===============================================================================
#                               setup
#===============================================================================
if __name__ == "__main__":

    setup(name='weewx',
          version=VERSION,
          description='weather software',
          long_description="""weewx interacts with a weather station to produce graphs, reports, and HTML pages.  weewx can upload data to the WeatherUnderground, PWSweather.com, or CWOP.""",
          author='Tom Keffer',
          author_email='tkeffer@gmail.com',
          url='http://www.weewx.com',
          license = 'GPLv3',
          classifiers = ['Development Status :: 5 - Production/Stable',
                         'Intended Audience :: End Users/Desktop',
                         'License :: GPLv3',
                         'Operating System :: OS Independent',
                         'Programming Language :: Python',
                         'Programming Language :: Python :: 2',
                         ],
          platforms = ['any'],
          package_dir = {'' : 'bin'},
          packages    = ['weedb',
                         'examples',
                         'user',
                         'weeplot',
                         'weeutil',
                         'weewx'],
          py_modules  = ['daemon'],
          scripts     = ['bin/wee_config_database',
                         'bin/wee_config_fousb',
                         'bin/wee_config_vantage',
                         'bin/weewxd',
                         'bin/wee_reports'],
          data_files  = [('',
                          ['LICENSE.txt',
                           'README',
                           'weewx.conf']),
                         ('docs',
                          ['docs/changes.txt',
                           'docs/copyright.htm',
                           'docs/customizing.htm',
                           'docs/day-gap-not-shown.png',
                           'docs/day-gap-showing.png',
                           'docs/daytemp_with_avg.png',
                           'docs/debian.htm',
                           'docs/ferrites.jpg',
                           'docs/logo-apple.png',
                           'docs/logo-centos.png',
                           'docs/logo-debian.png',
                           'docs/logo-fedora.png',
                           'docs/logo-linux.png',
                           'docs/logo-mint.png',
                           'docs/logo-redhat.png',
                           'docs/logo-suse.png',
                           'docs/logo-ubuntu.png',
                           'docs/readme.htm',
                           'docs/redhat.htm',
                           'docs/samaxesjs.toc-1.5.js',
                           'docs/samaxesjs.toc-1.5.min.js',
                           'docs/setup.htm',
                           'docs/sheeva.htm',
                           'docs/upgrading.htm',
                           'docs/usersguide.htm',
                           'docs/weekgustoverlay.png',
                           'docs/weewx_docs.css',
                           'docs/yearhilow.png']),
                         ('skins/Ftp',
                          ['skins/Ftp/skin.conf']),
                         ('skins/Rsync',
                          ['skins/Rsync/skin.conf']),
                         ('skins/Standard/backgrounds',
                          ['skins/Standard/backgrounds/band.gif']),
                         ('skins/Standard/NOAA',
                          ['skins/Standard/NOAA/NOAA-YYYY.txt.tmpl',
                           'skins/Standard/NOAA/NOAA-YYYY-MM.txt.tmpl']),
                         ('skins/Standard/RSS',
                          ['skins/Standard/RSS/weewx_rss.xml.tmpl']),
                         ('skins/Standard/smartphone',
                          ['skins/Standard/smartphone/barometer.html.tmpl',
                           'skins/Standard/smartphone/custom.js',
                           'skins/Standard/smartphone/humidity.html.tmpl',
                           'skins/Standard/smartphone/index.html.tmpl',
                           'skins/Standard/smartphone/radar.html.tmpl',
                           'skins/Standard/smartphone/rain.html.tmpl',
                           'skins/Standard/smartphone/temp_outside.html.tmpl',
                           'skins/Standard/smartphone/wind.html.tmpl']),
                         ('skins/Standard/smartphone/icons',
                          ['skins/Standard/smartphone/icons/icon_ipad_x1.png',
                           'skins/Standard/smartphone/icons/icon_ipad_x2.png',
                           'skins/Standard/smartphone/icons/icon_iphone_x1.png',
                           'skins/Standard/smartphone/icons/icon_iphone_x2.png']),
                         ('skins/Standard',
                          ['skins/Standard/favicon.ico',
                           'skins/Standard/mobile.css',
                           'skins/Standard/mobile.html.tmpl',
                           'skins/Standard/index.html.tmpl',
                           'skins/Standard/month.html.tmpl',
                           'skins/Standard/skin.conf',
                           'skins/Standard/week.html.tmpl',
                           'skins/Standard/weewx.css',
                           'skins/Standard/year.html.tmpl']),
                         ('util/apache/conf.d',
                          ['util/apache/conf.d/weewx.conf']),
                         ('util/init.d',
                          ['util/init.d/weewx.bsd',
                           'util/init.d/weewx.debian',
                           'util/init.d/weewx.redhat',
                           'util/init.d/weewx.suse']),
                         ('util/logrotate.d',
                          ['util/logrotate.d/weewx']),
                         ('util/logwatch/conf/logfiles',
                          ['util/logwatch/conf/logfiles/weewx.conf']),
                         ('util/logwatch/conf/services',
                          ['util/logwatch/conf/services/weewx.conf']),
                         ('util/logwatch/scripts/services',
                          ['util/logwatch/scripts/services/weewx']),
                         ('util/rsyslog.d',
                          ['util/rsyslog.d/weewx.conf'])],
          requires    = ['configobj(>=4.5)',
                         'serial(>=2.3)',
                         'Cheetah(>=2.0)',
                         'sqlite3(>=2.5)',
                         'PIL(>=1.1.6)'],
          cmdclass    = {"install_data" : weewx_install_data,
                         "install_lib"  : weewx_install_lib,
                         "sdist"        : weewx_sdist,
                         "install_scripts" : weewx_install_scripts}
          )
