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
 
 7. It saves the bin/user subdirectory.
"""

import os.path
import re
import shutil
import sys
import tempfile
import time
import configobj
from subprocess import Popen, PIPE

from distutils.core import setup
from distutils.command.install_data import install_data
from distutils.command.install_lib  import install_lib
from distutils.command.install_scripts import install_scripts
from distutils.command.sdist import sdist
import distutils.dir_util

# Find the install bin subdirectory:
this_file = os.path.join(os.getcwd(), __file__)
this_dir = os.path.abspath(os.path.dirname(this_file))
bin_dir = os.path.abspath(os.path.join(this_dir, 'bin'))

# Get the version:
save_syspath = list(sys.path)
sys.path.insert(0, bin_dir)
import weewx
VERSION = weewx.__version__
del weewx
sys.path = save_syspath

start_scripts = ['util/init.d/weewx.bsd',
                 'util/init.d/weewx.debian',
                 'util/init.d/weewx.lsb',
                 'util/init.d/weewx.redhat',
                 'util/init.d/weewx.suse']

service_map = {'weewx.wxengine.StdTimeSynch' : 'prep_services', 
               'weewx.wxengine.StdConvert'   : 'process_services', 
               'weewx.wxengine.StdCalibrate' : 'process_services', 
               'weewx.wxengine.StdQC'        : 'process_services', 
               'weewx.wxengine.StdArchive'   : 'archive_services',
               'weewx.wxengine.StdPrint'     : 'report_services', 
               'weewx.wxengine.StdReport'    : 'report_services'}

all_service_groups = ['prep_services', 'process_services', 'archive_services', 
                      'restful_services', 'report_services']

#==============================================================================
# install_lib
#==============================================================================

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

#==============================================================================
# install_data
#==============================================================================

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
            # Do this by filtering it out of the list of subdirectories to
            # be installed:
            self.data_files = filter(lambda dat : not dat[0].startswith('skins/'), self.data_files)

        remove_obsolete_files(self.install_dir)
        
        # Run the superclass's run():
        install_data.run(self)
       
    def process_config_file(self, f, install_dir, **kwargs):

        # The path where the weewx.conf configuration file will be installed
        install_path = os.path.join(install_dir, os.path.basename(f))
    
        new_config = merge_config_files(f, install_path, install_dir)
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

#==============================================================================
# install_scripts
#==============================================================================

class weewx_install_scripts(install_scripts):
    
    def run(self):
    
        # run the superclass's version:
        install_scripts.run(self)
        
        # Add a symbolic link for weewxd.py to weewxd:
        source = './weewxd'
        dest   = os.path.join(self.install_dir, 'weewxd.py')
        os.symlink(source, dest)
        
#==============================================================================
# sdist
#==============================================================================

class weewx_sdist(sdist):
    """Specialized version of sdist which checks for password information in
    the configuration file before creating the distribution.

    For other sdist methods, see:
 http://epydoc.sourceforge.net/stdlib/distutils.command.sdist.sdist-class.html
    """

    def copy_file(self, f, install_dir, **kwargs):
        """Specialized version of copy_file.

        Return a tuple (dest_name, copied): 'dest_name' is the actual name of
        the output file, and 'copied' is true if the file was copied (or would
        have been copied, if 'dry_run' true)."""
        # If this is the configuration file, then massage it to eliminate
        # the password info
        if f == 'weewx.conf':
            config = configobj.ConfigObj(f)

            # If we're working with the configuration file, make sure it
            # does not have any private data in it.

            if (config.has_key('StdReport') and
                config['StdReport'].has_key('FTP') and
                config['StdReport']['FTP'].has_key('password')):
                sys.stderr.write("\n*** FTP password found in configuration file. Aborting ***\n\n")
                exit()

            rest_dict = config['StdRESTful']
            if (rest_dict.has_key('Wunderground') and
                rest_dict['Wunderground'].has_key('password')):
                sys.stderr.write("\n*** Wunderground password found in configuration file. Aborting ***\n\n")
                exit()
            if (rest_dict.has_key('PWSweather') and
                rest_dict['PWSweather'].has_key('password')):
                sys.stderr.write("\n*** PWSweather password found in configuration file. Aborting ***\n\n")
                exit()
                
        # Pass on to my superclass:
        return sdist.copy_file(self, f, install_dir, **kwargs)

#==============================================================================
# utility functions
#==============================================================================

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
    """Checks whether the schema in user.schemas is a new style or old style
    schema.
    
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
            # Try the old style 'drop_list'. If it fails, it must be
            # a new-style schema
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
    
def merge_config_files(new_config_path, old_config_path, weewx_root,
                       version_number=VERSION):
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
    # FIXME: new_version_number is not used
    new_version_number = version_number.split('.')
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
    
    global service_map, all_service_groups, service_lists

    # webpath is now station_url
    webpath = config_dict['Station'].get('webpath', None)
    station_url = config_dict['Station'].get('station_url', None)
    if webpath is not None and station_url is None:
        config_dict['Station']['station_url'] = webpath
    config_dict['Station'].pop('webpath', None)
    
    if config_dict.has_key('StdArchive'):
        # Option stats_types is no longer used. Get rid of it.
        config_dict['StdArchive'].pop('stats_types', None)
    
    # --- Davis Vantage series ---
    if config_dict.has_key('Vantage'):
        try:
            if config_dict['Vantage']['driver'].strip() == 'weewx.VantagePro':
                config_dict['Vantage']['driver'] = 'weewx.drivers.vantage'
        except KeyError:
            pass
    
    # --- Oregon Scientific WMR100 ---
    
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
            config_dict['WMR100']['driver'] = 'weewx.drivers.wmr100'
    except KeyError:
        pass
        
    # --- Oregon Scientific WMR9x8 series ---
    
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
            config_dict['WMR9x8']['driver'] = 'weewx.drivers.wmr9x8'
    except KeyError:
        pass
    
    # --- Fine Offset instruments ---

    try:
        if config_dict['FineOffsetUSB']['driver'].strip() == 'weewx.fousb':
            config_dict['FineOffsetUSB']['driver'] = 'weewx.drivers.fousb'
    except KeyError:
        pass

    #--- The weewx Simulator ---

    try:
        if config_dict['Simulator']['driver'].strip() == 'weewx.simulator':
            config_dict['Simulator']['driver'] = 'weewx.drivers.simulator'
    except KeyError:
        pass

    # See if the engine configuration section has the old-style "service_list":
    if config_dict['Engines']['WxEngine'].has_key('service_list'):
        # It does. Break it up into five, smaller lists. If a service
        # does not appear in the dictionary "service_map", meaning we
        # do not know what it is, then stick it in the last group we
        # have seen. This should get its position about right.
        last_group = 'prep_services'
        
        # Set up a bunch of empty groups in the right order
        for group in all_service_groups:
            config_dict['Engines']['WxEngine'][group] = list()

        # Now map the old service names to the right group
        for _svc_name in config_dict['Engines']['WxEngine']['service_list']:
            svc_name = _svc_name.strip()
            # Skip the no longer needed StdRESTful service:
            if svc_name == 'weewx.wxengine.StdRESTful':
                continue
            # Do we know about this service?
            if service_map.has_key(svc_name):
                # Yes. Get which group it belongs to, and put it there
                group = service_map[svc_name]
                config_dict['Engines']['WxEngine'][group].append(svc_name)
                last_group = group
            else:
                # No. Put it in the last group.
                config_dict['Engines']['WxEngine'][last_group].append(svc_name)

        # Now add the restful services, using the old driver name to help us
        for section in config_dict['StdRESTful'].sections:
            svc = config_dict['StdRESTful'][section]['driver']
            # weewx.restful has changed to weewx.restx
            if svc.startswith('weewx.restful'):
                svc = 'weewx.restx.Std' + section
            # awekas is in weewx.restx since 2.6
            if svc.endswith('AWEKAS'):
                svc = 'weewx.restx.AWEKAS'
            config_dict['Engines']['WxEngine']['restful_services'].append(svc)

        # Depending on how old a version the user has, the station registry
        # may have to be included:
        if 'weewx.restx.StdStationRegistry' not in config_dict['Engines']['WxEngine']['restful_services']:
            config_dict['Engines']['WxEngine']['restful_services'].append('weewx.restx.StdStationRegistry')
        
        # Get rid of the no longer needed service_list:
        config_dict['Engines']['WxEngine'].pop('service_list')

    if config_dict.has_key('StdRESTful') and config_dict['StdRESTful'].has_key('CWOP'):
        # Option "interval" has changed to "post_interval"
        if config_dict['StdRESTful']['CWOP'].has_key('interval'):
            config_dict['StdRESTful']['CWOP']['post_interval'] = config_dict['StdRESTful']['CWOP']['interval']
            config_dict['StdRESTful']['CWOP'].pop('interval')
        # Option "server" has become "server_list". It is also no longer included in
        # the default weewx.conf, so just pop it.
        config_dict['StdRESTful']['CWOP'].pop('server')

    # Remove the no longer needed "driver" from all the RESTful services:
    if config_dict.has_key('StdRESTful'):
        for section in config_dict['StdRESTful'].sections:
            config_dict['StdRESTful'][section].pop('driver', None)


def save_path(filepath):
    # Sometimes the target has a trailing '/'. This will take care of it:
    filepath = os.path.normpath(filepath)
    newpath = filepath + time.strftime(".%Y%m%d%H%M%S")
    shutil.move(filepath, newpath)
    return newpath

#==============================================================================
# extension installer
#
# An extension package is simply a tarball with files in a structure that
# mirrors that of weewx itself.
#
# extension components must be in a single directory
# extension must have same layout as weewx source tree
# extension must have an install.py
#
# There are no tests for prerequisites, so each extension should fail
# gracefully if it does not have what it needs to run.
#
# Each extension should include a readme that explains how the extension
# operates and how to manually install the extension.  The readme is not
# copied from the extension source.  Additional documentation may be included
# in a docs directory in the extension source, but it will not be copied into
# the weewx weewx installation.
#==============================================================================

# FIXME: need to prune from weewx.conf on uninstall: skin, service
# FIXME: delete .pyc files on uninstall
# FIXME: do not overwrite fields in weewx.conf if they already exist

class Logger(object):
    def __init__(self, verbosity=0):
        self.verbosity = verbosity
    def log(self, msg, level=0):
        if self.verbosity >= level:
            print msg
    def set_verbosity(self, verbosity):
        self.verbosity = verbosity

class Extension(Logger):
    """Encapsulation of a weewx extension package.  Knows how to verify,
    extract, load, and run the extension installer, then cleanup when done."""

    _layouts = {
        'pkg': {
            'WEEWX_ROOT':  '/',
            'BIN_ROOT':    '/usr/share/weewx',
            'CONFIG_ROOT': '/etc/weewx',
            'SKIN_ROOT':   '/etc/weewx/skins',
            },
        'py': {
            'WEEWX_ROOT':  '/home/weewx',
            'BIN_ROOT':    'bin',
            'CONFIG_ROOT': '',
            'SKIN_ROOT':   'skins',
            }
        }

    def __init__(self, filename, layout_type=None, tmpdir='/var/tmp'):
        self.filename = filename # could be dir, tarball, or extname
        self.tmpdir = tmpdir
        self.layout_type = layout_type
        self.dryrun = False
        self.installer = None
        self.extdir = None
        self.archive = None
        self.basename = None
        self.layout = None

    def set_dryrun(self, dryrun):
        self.dryrun = dryrun

    def install(self):
        self.layout_type = self.guess_type(self.layout_type)
        self.layout = self.verify_layout(self.layout_type)
        (self.archive, self.basename, self.extdir) = \
            self.verify_installer(self.filename, self.tmpdir)
        self.verify_src(self.extdir)
        # everything is ok, so use the extdir
        self.layout['EXTRACT_ROOT'] = self.extdir
        self.load_installer(self.extdir, self.basename, self.layout)
        self.installer.install()
        self.cleanup()

    def uninstall(self):
        self.layout_type = self.guess_type(self.layout_type)
        self.layout = self.verify_layout(self.layout_type)
        self.hisdir = self.verify_uninstaller(self.layout, self.filename)
        self.basename = self.filename
        self.load_installer(self.hisdir, self.basename, self.layout)
        self.installer.uninstall()

    def verify_installer(self, filename, tmpdir):
        if os.path.isdir(filename):
            archive = None
            basename = os.path.basename(filename)
            extdir = filename
        elif os.path.isfile(filename):
            (archive, basename) = self.verify_tarball(filename)
            extdir = self.extract_tarball(archive, tmpdir, basename)
        else:
            raise Exception, "cannot install from %s" % filename
        return (archive, basename, extdir)

    def verify_uninstaller(self, layout, basename):
        d = os.path.join(layout['BIN_ROOT'], 'user')
        d = os.path.join(d, 'installer')
        d = os.path.join(d, basename)
        return d

    def guess_type(self, layout_type):
        '''figure out what kind of installation this is'''

        # FIXME: bail out if multiple installation types on a single system

        # is this a debian installation?
        if layout_type is None:
            try:
                cmd = 'dpkg-query -s weewx'
                p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                (o,e) = p.communicate()
                for line in o.split('\n'):
                    if line.startswith('Package: weewx'):
                        layout_type = 'deb'
            except:
                pass

        # is this a redhat/suse installation?
        if layout_type is None:
            try:
                cmd = 'rpm -q weewx'
                p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                (o,e) = p.communicate()
                for line in o.split('\n'):
                    if line.find('weewx') >= 0:
                        layout_type = 'rpm'
            except:
                pass

        # it must be a setup installation
        if layout_type is None:
            layout_type = 'py'

        self.log("layout type is %s" % layout_type, level=2)

        return layout_type

    def verify_layout(self, layout_type):
        errors = []

        if layout_type == 'deb':
            layout = dict(self._layouts['pkg'])
        elif layout_type == 'rpm':
            layout = dict(self._layouts['pkg'])
        elif layout_type == 'py':
            layout = dict(self._layouts['py'])
            # be sure we get the installed location, not the source location
            fn = os.path.join(this_dir, 'setup.cfg')
            try:
                # if there is a setup.cfg we are running from source
                config = configobj.ConfigObj(fn)
                weewx_root = config['install']['home']
            except:
                # otherwise we are running from destination
                weewx_root = this_dir
            # adjust all of the paths
            for f in layout:
                layout[f] = os.path.join(weewx_root, layout[f])
            layout['WEEWX_ROOT'] = weewx_root
        else:
            errors.append("unknown layout type '%s'" % layout_type)

        # be sure each destination directory exists
        for x in layout:
            if not os.path.isdir(layout[x]):
                errors.append("no directory %s" % x)
        if errors:
            raise Exception, '\n'.join(errors)

        self.log("layout is %s" % layout, level=3)

        return layout

    def verify_src(self, extdir):
        '''ensure that the extension is something we can work with'''
        ifile = os.path.join(extdir, 'install.py')
        if not os.path.exists(ifile):
            raise Exception, "no install.py found in %s" % extdir

    def verify_tarball(self, filename):
        '''do some basic checks on the tarball'''
        self.log("verify tarball", level=2)
        import tarfile
        archive = tarfile.open(filename, mode='r')
        root = None
        has_install = False
        errors = []
        for f in archive.getmembers():
            if f.name.endswith('install.py'):
                has_install = True
            idx = f.name.find('/')
            if idx >= 0:
                r = f.name[0:idx]
                if root is None:
                    root = r
                elif root != r:
                    errors.append("multiple roots %s != %s" % (root, r))
            else:
                if root is None:
                    root = f.name
                else:
                    errors.append("non-rooted asset %s" % f.name)
            if ( f.name.startswith('.')
                 or f.name.startswith('/')
                 or f.name.find('..') >= 0 ):
                errors.append("suspect file '%s'" % f.name)
        if not has_install:
            errors.append("package has no install.py")
        if errors:
            raise Exception, "\n".join(errors)
        return (archive, root)

    def extract_tarball(self, archive, tmpdir, basename):
        '''extract the tarball contents, return path to the extracted files'''
        self.log("extracting tarball", level=2)
        archive.extractall(path=tmpdir)
        return os.path.join(tmpdir, basename)

    def load_installer(self, dirname, basename, layout):
        '''load the extension's installer'''
        self.log("import install.py from %s" % dirname, level=2)
        sys.path.append(dirname)
        ifile = 'install'
        __import__(ifile)
        module = sys.modules[ifile]
        loader = getattr(module, 'loader')
        self.installer = loader()
        self.installer.set_verbosity(self.verbosity)
        self.installer.set_dryrun(self.dryrun)
        self.installer.set_layout(layout)
        self.installer.set_basename(basename)

    def cleanup(self):
        if self.archive is not None:
            self.log("clean up files extracted from archive", level=2)
            try:
                shutil.rmtree(self.extdir)
            except:
                pass

class ExtensionInstaller(Logger):
    """Base class for extension installers."""

    # extension components can be installed to these locations
    dirs = {
        'bin': 'BIN_ROOT',
        'skins': 'SKIN_ROOT',
        }

    def __init__(self, **kwargs):
        self.version = kwargs.get('version')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.author = kwargs.get('author')
        self.author_email = kwargs.get('author_email')
        self.files = kwargs.get('files', [])
        self.config = kwargs.get('config', {})
        self.services = {}
        global all_service_groups
        for sg in all_service_groups:
            v = kwargs.get(sg, [])
            if not isinstance(v, list):
                v = [v]
            self.services[sg] = v
        self.layout = None
        self.basename = None
        self.doit = True

    def set_dryrun(self, dryrun):
        self.doit = not dryrun

    def set_layout(self, layout):
        self.layout = layout

    def set_basename(self, basename):
        self.basename = basename

    def install(self):
        self.install_files()
        self.merge_config_options()
        self.install_history()

    def uninstall(self):
        self.uninstall_files()
        self.unmerge_config_options()
        self.uninstall_history()

    def prepend_layout_path(self, path):
        '''prepend installed path to local path'''
        for d in self.dirs:
            if path.startswith(d):
                return path.replace(d, self.layout[self.dirs[d]])
        return path

    def install_files(self):
        '''copy files from extracted package, make backup if already exist'''
        self.log("install_files", level=1)
        for t in self.files:
            dstdir = self.prepend_layout_path(t[0])
            try:
                self.log("  mkdir %s" % dstdir, level=2)
                if self.doit:
                    os.makedirs(dstdir)
            except:
                pass
            for f in t[1]:
                src = os.path.join(self.layout['EXTRACT_ROOT'], f)
                dst = self.prepend_layout_path(f)
                if os.path.exists(dst):
                    self.log("  save existing file %s" % dst, level=2)
                    if self.doit:
                        save_path(dst)
                self.log("  copy %s to %s" % (src, dst), level=2)
                if self.doit:
                    distutils.file_util.copy_file(src, dst)

    def uninstall_files(self):
        '''delete files that were installed for this extension'''
        self.log("uninstall_files", level=1)
        for t in self.files:
            dstdir = self.prepend_layout_path(t[0])
            for f in t[1]:
                dst = self.prepend_layout_path(f)
                if os.path.exists(dst):
                    self.log("  delete file %s" % dst, level=2)
                    if self.doit:
                        os.remove(dst)
                else:
                    self.log("  missing file %s" % dst, level=2)
            # if the directory is empty, delete it
            try:
                if empty(dstdir):
                    self.log("  delete directory %s" % dstdir, level=2)
                    if self.doit:
                        shutil.rmtree(dstdir, True)
                else:
                    self.log("  directory not empty: %s" % dstdir, level=2)
            except:
                pass

    def merge_config_options(self):
        self.log("merge_config_options", level=1)

        # make a copy of the new config
        cfg = dict(self.config)

        # get the old config
        fn = os.path.join(self.layout['CONFIG_ROOT'], 'weewx.conf')
        config = configobj.ConfigObj(fn)

        # prepend any html paths with existing HTML_ROOT
        prepend_path(cfg, 'HTML_ROOT', config['StdReport']['HTML_ROOT'])

        # massage the database dictionaries for this extension
        try:
            sqlitecfg = config['Databases'].get('archive_sqlite', None)
            mysqlcfg = config['Databases'].get('archive_mysql', None)
            for k in cfg['Databases']:
                db = cfg['Databases'][k]
                if db['driver'] == 'weedb.sqlite' and sqlitecfg:
                    db['database'] = os.path.join(os.path.dirname(sqlitecfg['database']), db['database'])
                    db['root'] = sqlitecfg['root']
                elif db['driver'] == 'weedb.mysql' and mysqlcfg:
                    db['host'] = mysqlcfg['host']
                    db['user'] = mysqlcfg['user']
                    db['password'] = mysqlcfg['password']
        except:
            pass

        # merge the new options into the old config
        config.merge(cfg)

        # append services to appropriate lists
        global all_service_groups
        for sg in all_service_groups:
            for s in self.services[sg]:
                if not isinstance(config['Engines']['WxEngine'][sg], list):
                    config['Engines']['WxEngine'][sg] = [config['Engines']['WxEngine'][sg]]
                config['Engines']['WxEngine'][sg].append(s)

        self.log("  merged configuration:", level=3)
        self.log('\n'.join(formatdict(config)), level=3)

        self.save_config(config)

    def unmerge_config_options(self):
        self.log("unmerge_config_options", level=1)

        # get the old config
        fn = os.path.join(self.layout['CONFIG_ROOT'], 'weewx.conf')
        config = configobj.ConfigObj(fn)

        # remove any services we added
        global all_service_groups
        for sg in all_service_groups:
            if self.services[sg]:
                newlist = []
                for s in config['Engines']['WxEngine'][sg]:
                    if s not in self.services[sg]:
                        newlist.append(s)
                config['Engines']['WxEngine'][sg] = newlist

        self.log("  unmerged configuration:", level=3)
        self.log('\n'.join(formatdict(config)), level=3)

        self.save_config(config)

    def save_config(self, config):
        # backup the old configuration
        self.log("  save old configuration", level=2)
        if self.doit:
            bup = save_path(config.filename)

        # save the new configuration
        self.log("  save new config %s" % config.filename, level=2)
        if self.doit:
            config.write()

    def install_history(self):
        '''copy the installer to a location where we can find it later'''
        self.log("install_history", level=1)
        dstdir = os.path.join(self.layout['BIN_ROOT'], 'user')
        dstdir = os.path.join(dstdir, 'installer')
        dstdir = os.path.join(dstdir, self.basename)
        self.log("  mkdir %s" % dstdir, level=2)
        if self.doit:
            os.makedirs(dstdir)
        src = os.path.join(self.layout['EXTRACT_ROOT'], 'install.py')
        self.log("  copy %s to %s" % (src, dstdir), level=2)
        if self.doit:
            distutils.file_util.copy_file(src, dstdir)

    def uninstall_history(self):
        '''remove the installer cache'''
        self.log("uninstall_history", level=1)
        dstdir = os.path.join(self.layout['BIN_ROOT'], 'user')
        dstdir = os.path.join(dstdir, 'installer')
        dstdir = os.path.join(dstdir, self.basename)
        self.log("  delete %s" % dstdir, level=2)
        if self.doit:
            shutil.rmtree(dstdir, True)

def prepend_path(d, label, value):
    '''prepend the value to every instance of the label in config_dict'''
    for k in d.keys():
        if isinstance(d[k], dict):
            prepend_path(d[k], label, value)
        elif k == label:
            d[k] = os.path.join(value, d[k])    

def do_ext():
    import optparse
    description = "install weewx extension"
    usage = "%prog (--install-extension [filename|directory] | --uninstall-extension extname)"
    parser = optparse.OptionParser(description=description, usage=usage)
    parser.add_option('--install-extension', dest='i_ext', type=str,
                      metavar="FILE_OR_DIR", help='install extension')
    parser.add_option('--uninstall-extension', dest='u_ext', type=str,
                      metavar="NAME", help='uninstall extension')
    parser.add_option('--layout', dest='layout', type=str,
                      metavar='LAYOUT', help='specify the type of install')
    parser.add_option('--tmpdir', dest='tmpdir', type=str,
                      metavar="DIR", help='temporary directory')
    parser.add_option('--dryrun', dest='dryrun', action='store_true',
                      help='print what would happen but do not do it')
    parser.add_option('--verbosity', dest='verbosity', type=int,
                      metavar="N", help='how much status to spew, 0-3')
    (options, _args) = parser.parse_args()

    if options.i_ext:
        ext = Extension(options.i_ext, options.layout, options.tmpdir)
        ext.set_verbosity(options.verbosity)
        ext.set_dryrun(options.dryrun)
        ext.install()
    elif options.u_ext:
        ext = Extension(options.u_ext, options.layout, options.tmpdir)
        ext.set_verbosity(options.verbosity)
        ext.set_dryrun(options.dryrun)
        ext.uninstall()
    return 0

#==============================================================================
# configuration file merging
#==============================================================================

def formatdict(d, indent=0):
    lines = []
    for k in d.keys():
        line = []
        if type(d[k]) is configobj.Section:
            for _i in range(indent):
                line.append('  ')
            line.append(k)
            lines.append(''.join(line))
            lines.extend(formatdict(d[k], indent=indent+1))
        else:
            for _i in range(indent):
                line.append('  ')
            line.append(k)
            line.append('=')
            line.append(str(d[k]))
            lines.append(''.join(line))
    return lines

def printdict(d, indent=0):
    for k in d.keys():
        if type(d[k]) is configobj.Section:
            for _i in range(indent):
                print ' ',
            print k
            printdict(d[k], indent=indent+1)
        else:
            for _i in range(indent):
                print ' ',
            print k, '=', d[k]

def do_merge():
    import optparse
    description = "merge weewx configuration file"
    usage = "%prog --merge-config --install-dir dir --a file --b file --c file"
    parser = optparse.OptionParser(description=description, usage=usage)
    parser.add_option('--merge-config', dest='mc', action='store_true',
                      help='merge configuration files')
    parser.add_option('--install-dir', dest='idir', type=str,metavar='DIR',
                      help='installation directory DIR')
    parser.add_option('--a', dest='filea', type=str, metavar='FILE',
                      help='first file FILE')
    parser.add_option('--b', dest='fileb', type=str, metavar='FILE',
                      help='second file FILE')
    parser.add_option('--c', dest='filec', type=str, metavar='FILE',
                      help='merged file FILE')
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display contents of merged file to stdout')
    (options, _args) = parser.parse_args()
    errmsg = []
    if options.idir is None:
        errmsg.append('no installation directory specified')
    if options.filea is None:
        errmsg.append('no first filename specified')
    if options.fileb is None:
        errmsg.append('no second filename specified')
    if options.filec is None:
        errmsg.append('no merged filename specified')
    if len(errmsg) > 0:
        print '\n'.join(errmsg)
        return 1
    merged_cfg = merge_config_files(options.filea, options.fileb, options.idir)
    if options.debug:
        printdict(merged_cfg)
    else:
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        merged_cfg.write(tmpfile)
        if os.path.exists(options.filec):
            _bup_cfg = save_path(options.filec)
        shutil.copyfile(tmpfile.name, options.filec)
    return 0

#==============================================================================
# main entry point
#==============================================================================

if __name__ == "__main__":
    if '--merge-config' in sys.argv:
        exit(do_merge())
    if '--install-extension' in sys.argv:
        exit(do_ext())
    if '--uninstall-extension' in sys.argv:
        exit(do_ext())

    setup(name='weewx',
          version=VERSION,
          description='weather software',
          long_description="""weewx interacts with a weather station to produce graphs, reports, and HTML pages.  weewx can upload data to services such as the WeatherUnderground, PWSweather.com, or CWOP.""",
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
          requires    = ['configobj(>=4.5)',
                         'serial(>=2.3)',
                         'Cheetah(>=2.0)',
                         'sqlite3(>=2.5)',
                         'PIL(>=1.1.6)'],
          cmdclass    = {"install_data" : weewx_install_data,
                         "install_lib"  : weewx_install_lib,
                         "sdist"        : weewx_sdist,
                         "install_scripts" : weewx_install_scripts},
          platforms   = ['any'],
          package_dir = {'' : 'bin'},
          packages    = ['weedb',
                         'examples',
                         'user',
                         'weeplot',
                         'weeutil',
                         'weewx',
                         'weewx.drivers'],
          py_modules  = ['daemon'],
          scripts     = ['bin/wee_config_database',
                         'bin/wee_config_fousb',
                         'bin/wee_config_te923',
                         'bin/wee_config_vantage',
                         'bin/wee_config_ws23xx',
                         'bin/wee_config_ws28xx',
                         'bin/weewxd',
                         'bin/wee_reports'],
          data_files  = [
            ('',
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
              'docs/jquery.min.js',
              'docs/jquery.toc-1.1.4.min.js',
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
              'docs/suse.htm',
              'docs/setup.htm',
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
              'util/init.d/weewx.lsb',
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
             ['util/rsyslog.d/weewx.conf'])]
          )
