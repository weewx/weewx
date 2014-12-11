#!/usr/bin/env python
# $Id$
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
from distutils.command.install_lib import install_lib
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

service_map_v2 = {'weewx.wxengine.StdTimeSynch' : 'prep_services', 
                  'weewx.wxengine.StdConvert'   : 'process_services', 
                  'weewx.wxengine.StdCalibrate' : 'process_services', 
                  'weewx.wxengine.StdQC'        : 'process_services', 
                  'weewx.wxengine.StdArchive'   : 'archive_services',
                  'weewx.wxengine.StdPrint'     : 'report_services', 
                  'weewx.wxengine.StdReport'    : 'report_services'}

minor_comment_block = [""]
major_comment_block = ["", "##############################################################################", ""]

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
        # If this is the configuration file, then merge it instead
        # of copying it
        if f == 'weewx.conf':
            rv = self.process_config_file(f, install_dir, **kwargs)
        elif f in start_scripts:
            rv = self.massage_start_file(f, install_dir, **kwargs)
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
        
    def massage_start_file(self, f, install_dir, **kwargs):

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
        dest = os.path.join(self.install_dir, 'weewxd.py')
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

            if ('StdReport' in config and
                'FTP' in config['StdReport'] and
                'password' in config['StdReport']['FTP']):
                sys.stderr.write("\n*** FTP password found in configuration file. Aborting ***\n\n")
                exit()

            rest_dict = config['StdRESTful']
            if ('Wunderground' in rest_dict and
                'password' in rest_dict['Wunderground']):
                sys.stderr.write("\n*** Wunderground password found in configuration file. Aborting ***\n\n")
                exit()
            if ('PWSweather' in rest_dict and
                'password' in rest_dict['PWSweather']):
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
    tmp_path = list(sys.path)
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
            _ = user.schemas.drop_list # @UnusedVariable @UndefinedVariable
        except AttributeError:
            # New style schema 
            result = 'new'
        else:
            # It did not fail. Must be an old-style schema
            result = 'old'
        finally:
            del user.schemas

    # Restore the path        
    sys.path = tmp_path
    
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
    new_version_number = version_number.split('.')
    if len(new_version_number[1]) < 2: 
        new_version_number[1] = '0' + new_version_number[1]
    
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
        if not old_version:
            old_version = '1.0.0'
        old_version_number = old_version.split('.')
        # Take care of the collation problem when comparing things like 
        # version '1.9' to '1.10' by prepending a '0' to the former:
        if len(old_version_number[1]) < 2: 
            old_version_number[1] = '0' + old_version_number[1]

        # I don't know how to merge older, V1.X configuration files, only
        # newer V2.X ones.
        if old_version_number[0] == '1':
            print >>sys.stderr, "Don't know how to merge old Version %s weewx.conf" % old_version
            print >>sys.stderr, "You will have to do it manually."
            
        else:
            # First update to the latest v2
            if old_version_number[0:2] >= ['2', '00']:
                update_to_v27(old_config)

            # Now update to V3.X
            old_database = update_to_v3(old_config)

            # Now merge the updated old configuration file into the new file,
            # thus saving any user modifications.
            # First, turn interpolation off:
            old_config.interpolation = False
            # Then do the merge
            new_config.merge(old_config)
            if old_database:
                try:
                    new_config['DataBindings']['wx_binding']['database'] = old_database
                except KeyError:
                    pass
                    
    # Make sure WEEWX_ROOT reflects the choice made in setup.cfg:
    new_config['WEEWX_ROOT'] = weewx_root
    # Add the version:
    new_config['version'] = version_number
    
    return new_config

def update_to_v27(config_dict):
    """Updates a configuration file to the latest V2.X version.
    Since V2.7 was the last 2.X version, that's our target"""

    # webpath is now station_url
    webpath = config_dict['Station'].get('webpath', None)
    station_url = config_dict['Station'].get('station_url', None)
    if webpath is not None and station_url is None:
        config_dict['Station']['station_url'] = webpath
    config_dict['Station'].pop('webpath', None)
    
    if 'StdArchive' in config_dict:
        # Option stats_types is no longer used. Get rid of it.
        config_dict['StdArchive'].pop('stats_types', None)
    
    # --- Davis Vantage series ---
    if 'Vantage' in config_dict:
        try:
            if config_dict['Vantage']['driver'].strip() == 'weewx.VantagePro':
                config_dict['Vantage']['driver'] = 'weewx.drivers.vantage'
        except KeyError:
            pass
    
    # --- Oregon Scientific WMR100 ---
    
    # The section name has changed from WMR-USB to WMR100
    if 'WMR-USB' in config_dict:
        if 'WMR100' in config_dict:
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
    if 'WMR-918' in config_dict:
        if 'WMR9x8' in config_dict:
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
    if 'Engines' in config_dict and 'service_list' in config_dict['Engines']['WxEngine']:
        # It does. Break it up into five, smaller lists. If a service
        # does not appear in the dictionary "service_map_v2", meaning we
        # do not know what it is, then stick it in the last group we
        # have seen. This should get its position about right.
        last_group = 'prep_services'
        
        # Set up a bunch of empty groups in the right order
        for group in ['prep_services', 'process_services', 'archive_services', 
                      'restful_services', 'report_services']:
            config_dict['Engines']['WxEngine'][group] = list()

        # Now map the old service names to the right group
        for _svc_name in config_dict['Engines']['WxEngine']['service_list']:
            svc_name = _svc_name.strip()
            # Skip the no longer needed StdRESTful service:
            if svc_name == 'weewx.wxengine.StdRESTful':
                continue
            # Do we know about this service?
            if svc_name in service_map_v2:
                # Yes. Get which group it belongs to, and put it there
                group = service_map_v2[svc_name]
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

    # Clean up the CWOP configuration
    if 'StdRESTful' in config_dict and 'CWOP' in config_dict['StdRESTful']:
        # Option "interval" has changed to "post_interval"
        if 'interval' in config_dict['StdRESTful']['CWOP']:
            config_dict['StdRESTful']['CWOP']['post_interval'] = config_dict['StdRESTful']['CWOP']['interval']
            config_dict['StdRESTful']['CWOP'].pop('interval')
        # Option "server" has become "server_list". It is also no longer
        # included in the default weewx.conf, so just pop it.
        if 'server' in config_dict['StdRESTful']['CWOP']:
            config_dict['StdRESTful']['CWOP'].pop('server')

    # Remove the no longer needed "driver" from all the RESTful services:
    if 'StdRESTful' in config_dict:
        for section in config_dict['StdRESTful'].sections:
            config_dict['StdRESTful'][section].pop('driver', None)

def update_to_v3(config_dict):
    """Update a configuration file to V3.X"""
    old_database = None
    
    if 'Databases' in config_dict:
        # The stats database no longer exists. Remove it from the [Databases]
        # section:
        config_dict['Databases'].pop('stats_sqlite', None)
        config_dict['Databases'].pop('stats_mysql', None)
        # The key "database" changed to "database_name"
        for stanza in config_dict['Databases']:
            if 'database' in config_dict['Databases'][stanza]:
                config_dict['Databases'][stanza].rename('database', 'database_name')
        
    if 'StdReport' in config_dict:
        # The key "data_binding" is now used instead of these:
        config_dict['StdReport'].pop('archive_database', None)
        config_dict['StdReport'].pop('stats_database', None)
        
    if 'StdArchive' in config_dict:
        old_database = config_dict['StdArchive'].pop('archive_database', None)
        config_dict['StdArchive'].pop('stats_database', None)
        config_dict['StdArchive'].pop('archive_schema', None)
        config_dict['StdArchive'].pop('stats_schema', None)
        
    # Section ['Engines'] got renamed to ['Engine']
    if 'Engine' not in config_dict and 'Engines' in config_dict:
        config_dict.rename('Engines', 'Engine')
        # Subsection [['WxEngine']] got renamed to [['Services']]
        if 'WxEngine' in config_dict['Engine']:
            config_dict['Engine'].rename('WxEngine', 'Services')

            # Finally, module "wxengine" got renamed to "engine". Go through
            # each of the service lists, making the change
            for list_name in config_dict['Engine']['Services']:
                service_list = config_dict['Engine']['Services'][list_name]
                # If service_list is not already a list (it could be just a single name),
                # then make it a list:
                if not hasattr(service_list, '__iter__'):
                    service_list = [service_list]
                config_dict['Engine']['Services'][list_name] = [this_item.replace('wxengine', 'engine') for this_item in service_list]
        try:
            # Finally, make sure the new StdWXCalculate service is in the list:
            if 'weewx.wxservices.StdWXCalculate' not in config_dict['Engine']['Services']['process_services']:
                config_dict['Engine']['Services']['process_services'].append('weewx.wxservices.StdWXCalculate')
        except KeyError:
            pass
        
    return old_database

def save_path(filepath):
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

def mkdir(dirpath):
    try:
        os.makedirs(dirpath)
    except OSError:
        pass


#==============================================================================
# configure the configuration file
#
# Inject the configuration stanza for a driver into the configuration file
# and set the station_type to the driver.
#
# If no driver is specified, either prompt for a driver or use the Simulator.
#
# If station info is specified, put that into the [Station] section.
#
# If metric units are specified, override the [[StandardReport]][[[Units]]]
#==============================================================================

def do_cfg():
    import optparse
    description = "configure the configuration file"
    usage = "%prog configure [--config=FILE] [--driver=DRIVER]"
    parser = optparse.OptionParser(description=description, usage=usage)
    parser.add_option('--quiet', dest='noprompt', action='store_true',
                      help='do not prompt')
    parser.add_option('--config', dest='cfgfn', type=str, metavar='FILE',
                      help='modify the configuration file FILE')
    parser.add_option('--driver', dest='driver', type=str, metavar='DRIVER',
                      help='use the driver DRIVER, e.g., weewx.driver.vantage')
    parser.add_option('--units', dest='units', type=str, metavar='UNITS',
                      help='preferred units for display, either METRIC or US')
    parser.add_option('--skip-previous', dest='skip_prev', action='store_true',
                      help='ignore any existing configuration options')
    parser.add_option('--dry-run', dest='dryrun', action='store_true',
                      help='print what would happen but do not do it')
    (options, _args) = parser.parse_args()

    info = dict()
    if not options.skip_prev:
        if not options.cfgfn:
            options.cfgfn = get_conf_filename()
        if options.cfgfn:
            config_dict = configobj.ConfigObj(options.cfgfn)
            info.update(get_station_info(config_dict))
    if options.units is not None:
        info['units'] = options.units.lower()
    if options.driver is not None:
        info['driver'] = options.driver
    if not options.noprompt:
        info.update(prompt_for_info(dflt_loc=info.get('location'),
                                    dflt_lat=info.get('latitude'),
                                    dflt_lon=info.get('longitude'),
                                    dflt_alt=info.get('altitude'),
                                    dflt_units=info.get('units')))
        if options.driver is None:
            info['driver'] = prompt_for_driver(info.get('driver'))
            info.update(prompt_for_driver_settings(info['driver']))

    configure_conf(options.cfgfn, info, options.dryrun)
    return 0

def _as_string(option):
    if option is None: return None
    if hasattr(option, '__iter__'):
        return ', '.join(option)
    return option

def configure_conf(config_fn, info, dryrun=False):
    """Configure the configuration file with station info and driver details"""
    # FIXME: this emits a functional config file, but the comments and indents
    # may be messed up.

    # Load the configuration file.  If we cannot find it, complain and bail.
    if config_fn is None:
        config_fn = get_conf_filename()
    if config_fn is None:
        print "Cannot determine location of configuration file"
        return
    print 'Using configuration file %s' % config_fn

    # Try to load the driver so we can use its configuration editor.  If that
    # fails for any reason, complain about it and bail out.
    driver = info.get('driver') if info is not None else None

    editor = driver_name = driver_vers = None
    if driver is not None:
        # adjust system path so we can load the driver
        tmp_path = list(sys.path)
        sys.path.insert(0, bin_dir)

        try:
            editor, driver_name, driver_vers = load_editor(driver)
        except Exception, e:
            print "Driver %s failed to load: %s" % (driver, e)
            return
        print 'Using %s version %s (%s)' % (driver_name, driver_vers, driver)

        # reset the system path
        sys.path = tmp_path

    # read the original configuration
    config = configobj.ConfigObj(config_fn, interpolation=False)

    # determine what driver-specific stanza we will need
    stanza = None
    if editor is not None:
        orig_stanza_text = None

        # if a previous stanza exists for this driver, grab it
        if driver_name in config:
            orig_stanza = configobj.ConfigObj(interpolation=False)
            orig_stanza[driver_name] = config[driver_name]
            orig_stanza_text = '\n'.join(orig_stanza.write())

        # let the driver process the stanza or give us a new one
        stanza_text = editor.get_conf(orig_stanza_text)
        stanza = configobj.ConfigObj(stanza_text.splitlines())

    # put the new stanza immediately after [Station]
    if stanza is not None and 'Station' in config:
        # insert the stanza
        config[driver_name] = stanza[driver_name]
        config.comments[driver_name] = major_comment_block
        # reorder the sections
        idx = config.sections.index(driver_name)
        config.sections.pop(idx)
        idx = config.sections.index('Station')
        config.sections = config.sections[0:idx+1] + [driver_name] + config.sections[idx+1:]
        # make the stanza the station type
        config['Station']['station_type'] = driver_name

    # apply any overrides from the info
    if info is not None:
        # update driver stanza with any overrides from info
        if driver_name in info:
            for k in info[driver_name]:
                config[driver_name][k] = info[driver_name][k]
        # update station information with info overrides
        for p in ['location', 'latitude', 'longitude', 'altitude']:
            if info.get(p) is not None:
                config['Station'][p] = info[p]
        # update units display with any info overrides
        if info.get('units') is not None:
            if info.get('units') == 'metric':
                print "Using Metric units for display"
                config['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': {
                                'group_altitude': 'meter',
                                'group_degree_day': 'degree_C_day',
                                'group_pressure': 'mbar',
                                'group_rain': 'mm',
                                'group_rainrate': 'mm_per_hour',
                                'group_speed': 'meter_per_second',
                                'group_speed2': 'meter_per_second2',
                                'group_temperature': 'degree_C'}}})
            elif info.get('units') == 'us':
                print "Using US units for display"
                config['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': {
                                'group_altitude': 'foot',
                                'group_degree_day': 'degree_F_day',
                                'group_pressure': 'inHg',
                                'group_rain': 'inch',
                                'group_rainrate': 'inch_per_hour',
                                'group_speed': 'mile_per_hour',
                                'group_speed2': 'mile_per_hour2',
                                'group_temperature': 'degree_F'}}})

    # save the new configuration
    config.filename = "%s.tmp" % config_fn
    config.write()

    # move the original aside
    if not dryrun:
        save_path(config_fn)
        shutil.move(config.filename, config_fn)

def load_editor(driver):
    """Load the configuration editor from the driver file"""
    __import__(driver)
    driver_module = sys.modules[driver]
    loader_function = getattr(driver_module, 'confeditor_loader')
    editor = loader_function()
    return editor, driver_module.DRIVER_NAME, driver_module.DRIVER_VERSION

def prompt_for_driver(dflt_driver=None):
    """Get the information about each driver, return as a dictionary."""
    infos = get_driver_infos()
    keys = sorted(infos)
    dflt_idx = None
    for i, d in enumerate(keys):
        print " %2d) %-15s (%s)" % (i, infos[d].get('name', '?'), d)
        if dflt_driver == d:
            dflt_idx = i
    msg = "choose a driver [%d]: " % dflt_idx if dflt_idx is not None else "choose a driver: "
    ans = None
    while ans is None:
        ans = raw_input(msg)
        if len(ans.strip()) == 0:
            ans = dflt_idx
        try:
            idx = int(ans)
            if idx < 0 or idx >= len(keys):
                ans = None
        except (ValueError, TypeError):
            ans = None
    return keys[idx]

def prompt_for_driver_settings(driver):
    """Let the driver prompt for any required settings."""
    settings = dict()
    __import__(driver)
    driver_module = sys.modules[driver]
    loader_function = getattr(driver_module, 'confeditor_loader')
    editor = loader_function()
    settings[driver_module.DRIVER_NAME] = editor.prompt_for_settings()
    return settings

def get_driver_infos():
    """scan the drivers folder and list each driver with its package"""
    from os import listdir
    from os.path import isfile, join
    ddir = 'bin/weewx/drivers'
    drivers = [ f for f in listdir(ddir) if isfile(join(ddir, f)) and f != '__init__.py' and f[-3:] == '.py' ]

    # adjust system path so we can load the drivers
    tmp_path = list(sys.path)
    sys.path.insert(0, bin_dir)

    infos = dict()
    for fn in drivers:
        driver = "weewx.drivers.%s" % fn[:-3]
        infos[driver] = dict()
        try:
            __import__(driver)
            driver_module = sys.modules[driver]
            infos[driver]['name'] = driver_module.DRIVER_NAME
            infos[driver]['version'] = driver_module.DRIVER_VERSION
        except Exception, e:
            infos[driver]['name'] = fn[:-3]
            infos[driver]['fail'] = "%s" % e

    # reset the system path
    sys.path = tmp_path
    return infos

def list_drivers():
    infos = get_driver_infos()
    keys = sorted(infos)
    for d in keys:
        msg = "%-25s" % d
        for x in ['name', 'version', 'fail']:
            if x in infos[d]:
                msg += " %-15s" % infos[d][x]
        print msg

def prompt_for_info(dflt_loc=None, dflt_lat='90.000', dflt_lon='0.000',
                    dflt_alt=['0', 'meter'], dflt_units='metric'):
    print "Enter a brief description of the station, such as its location.  For example:"
    print "Santa's Workshop, North Pole"
    msg = "description: [%s]: " % dflt_loc if dflt_loc is not None else "description: "
    loc = None
    while loc is None:
        ans = raw_input(msg)
        if len(ans.strip()) > 0:
            loc = ans
        elif dflt_loc is not None:
            loc = dflt_loc
        else:
            loc = None
    print "Specify altitude, with units 'foot' or 'meter'.  For example:"
    print "35, foot"
    print "12, meter"
    msg = "altitude: "
    if dflt_alt is not None:
        msg = "altitude [%s]: " % _as_string(dflt_alt)
    alt = None
    while alt is None:
        ans = raw_input(msg)
        if len(ans.strip()) == 0:
            alt = dflt_alt
        elif ans.find(',') >= 0:
            parts = ans.split(',')
            try:
                float(parts[0])
                if parts[1].strip() in ['foot', 'meter']:
                    alt = [parts[0].strip(), parts[1].strip()]
                else:
                    alt = None
            except (ValueError, TypeError):
                alt = None
        else:
            alt = None
    print "Specify latitude in decimal degrees, negative for south."
    msg = "latitude [%s]: " % dflt_lat if dflt_lat is not None else "latitude: "
    lat = None
    while lat is None:
        ans = raw_input(msg)
        if len(ans.strip()) == 0:
            ans = dflt_lat
        try:
            lat = float(ans)
            if lat < -90 or lat > 90:
                lat = None
        except (ValueError, TypeError):
            lat = None
    print "Specify longitude in decimal degrees, negative for west."
    msg = "longitude [%s]: " % dflt_lon if dflt_lon is not None else "longitude: "
    lon = None
    while lon is None:
        ans = raw_input(msg)
        if len(ans.strip()) == 0:
            ans = dflt_lon
        try:
            lon = float(ans)
            if lon < -180 or lon > 180:
                lon = None
        except (ValueError, TypeError):
            lon = None
    print "Indicate the preferred units for display: 'metric' or 'us'"
    msg = "units [%s]: " % dflt_units if dflt_units is not None else "units: "
    units = None
    while units is None:
        ans = raw_input(msg)
        if len(ans.strip()) == 0 and dflt_units is not None:
            units = dflt_units
        elif ans.lower() in ['metric', 'us']:
            units = ans.lower()
        else:
            units = None
    return {'location': loc,
            'altitude': alt,
            'latitude': lat,
            'longitude': lon,
            'units': units}

def get_station_info(config_dict):
    """Extract station info from config dictionary."""
    info = dict()
    if config_dict is not None and 'Station' in config_dict:
        info['location'] = _as_string(config_dict['Station'].get('location'))
        info['latitude'] = config_dict['Station'].get('latitude')
        info['longitude'] = config_dict['Station'].get('longitude')
        info['altitude'] = config_dict['Station'].get('altitude')
        if 'station_type' in config_dict['Station']:
            info['station_type'] = config_dict['Station']['station_type']
            if info['station_type'] in config_dict:
                info['driver'] = config_dict[info['station_type']]['driver']
    return info

def get_conf_filename():
    """Find the full path to weewx.conf.  First look for a setup.cfg file in
    the same directory from which setup.py was run.  If we find one, use
    the contents to determine the location of weewx.conf.  If no setup.cfg,
    then use the location of setup.py to guess the location of weewx.conf.
    If setup.py is in /usr/share/weewx then this is a deb/rpm install, so
    weewx.conf is in /etc/weewx.conf.  Anywhere else and the weewx.conf will
    be in the same directory as setup.py.  Anything other than that we do
    not recognize, and the weewx.conf must be specified explicitly."""
    # FIXME: if someone specifies --home or --prefix then this will break

    # try to find the directory in which weewx.conf is or will be installed
    idir = None
    fn = os.path.join(this_dir, 'setup.cfg')
    if os.path.exists(fn):
        # look in the location specified by setup.cfg
        setup_dict = configobj.ConfigObj(fn)
        if ('install' in setup_dict and
            setup_dict['install'].get('home') is not None):
            idir = setup_dict['install'].get('home')
    elif this_dir == '/usr/share/weewx' or this_dir == '/usr/bin':
        # this is a deb or rpm install
        idir = '/etc/weewx'
    else:
        idir = this_dir
    if idir is None:
        return None
    return "%s/weewx.conf" % idir


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
# the weewx installation.
#
# The installer copies the install.py file from the extension to a directory
# bin/user/installer/EXTNAME/install.py so it can be used to uninstall the
# extension at some later time.
#==============================================================================

# FIXME: consider start/stop of weewx as part of the process

class Logger(object):
    def __init__(self, verbosity=0):
        self.verbosity = verbosity
    def log(self, msg, level=0):
        if self.verbosity >= level:
            print "%s%s" % ('  ' * (level - 1), msg)
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

    def __init__(self, filename=None, layout_type=None, tmpdir='/var/tmp',
                 **kwargs):
        super(Extension, self).__init__()
        self.filename = filename # could be dir, tarball, or extname
        self.tmpdir = tmpdir
        self.layout_type = layout_type
        self.dryrun = False
        self.installer = None
        self.extdir = None
        self.basename = None
        self.layout = None
        self.delete_extdir = False
        self.hisdir = None

    def set_extension(self, filename):
        self.filename = filename

    def set_dryrun(self, dryrun):
        self.dryrun = dryrun

    def enumerate_extensions(self):
        self.layout_type = self.guess_type(self.layout_type)        
        self.layout = self.verify_layout(self.layout_type)
        d = self.get_cache_dir(self.layout)
        try:
            exts = os.listdir(d)
            if exts:
                for f in exts:
                    self.log(f, level=0)
            else:
                self.log("no extensions installed", level=0)
                self.log("extension cache is %s" % d, level=2)
        except OSError, e:
            self.log("listdir failed: %s" % e, level=2)

    def install(self):
        self.log("request to install %s" % self.filename)
        self.layout_type = self.guess_type(self.layout_type)
        self.layout = self.verify_layout(self.layout_type)
        (self.basename, self.extdir, self.delete_extdir) = \
            self.verify_installer(self.filename, self.tmpdir)
        self.verify_src(self.extdir)
        # everything is ok, so use the extdir
        self.layout['EXTRACT_ROOT'] = self.extdir
        self.load_installer(self.extdir, self.basename, self.layout)
        self.installer.install()
        self.cleanup()

    def uninstall(self):
        self.log("request to uninstall %s" % self.filename)
        self.layout_type = self.guess_type(self.layout_type)
        self.layout = self.verify_layout(self.layout_type)
        self.basename = self.filename
        self.hisdir = self.get_uninstaller_dir(self.layout, self.basename)
        self.verify_src(self.hisdir)
        self.load_installer(self.hisdir, self.basename, self.layout)
        self.installer.uninstall()

    def verify_installer(self, filename, tmpdir):
        if os.path.isdir(filename):
            basename = os.path.basename(filename)
            extdir = filename
            delete_when_finished = False
        elif os.path.isfile(filename):
            (basename, extdir) = self.extract_tarball(filename, tmpdir)
            delete_when_finished = True
        else:
            raise Exception("cannot install from %s" % filename)
        return basename, extdir, delete_when_finished

    @staticmethod
    def get_cache_dir(layout):
        d = os.path.join(layout['BIN_ROOT'], 'user')
        d = os.path.join(d, 'installer')
        return d

    def get_uninstaller_dir(self, layout, basename):
        d = self.get_cache_dir(layout)
        d = os.path.join(d, basename)
        return d

    def guess_type(self, layout_type):
        """figure out what kind of installation this is"""

        # FIXME: bail out if multiple installation types on a single system

        # is this a debian installation?
        if layout_type is None:
            try:
                cmd = 'dpkg-query -s weewx'
                p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                (o, _) = p.communicate()
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
                (o, _) = p.communicate()
                for line in o.split('\n'):
                    if line.find('weewx') >= 0:
                        layout_type = 'rpm'
            except:
                pass

        # it must be a setup installation
        if layout_type is None:
            layout_type = 'py'

        self.log("layout type is %s" % layout_type, level=1)

        return layout_type

    def verify_layout(self, layout_type):
        if layout_type == 'deb' or layout_type == 'rpm':
            layout = dict(self._layouts['pkg'])
        elif layout_type == 'py':
            layout = dict(self._layouts['py'])
            # be sure we get the installed location, not the source location
            try:
                # if there is a setup.cfg we are running from source
                fn = os.path.join(this_dir, 'setup.cfg')
                config = configobj.ConfigObj(fn)
                weewx_root = config['install']['home']
            except Exception:
                # otherwise we are running from destination
                weewx_root = this_dir
            # adjust all of the paths
            for f in layout:
                layout[f] = os.path.join(weewx_root, layout[f])
            layout['WEEWX_ROOT'] = weewx_root
        else:
            raise Exception("unknown layout type '%s'" % layout_type)

        errors = []

        # be sure each destination directory exists
        for x in layout:
            if not os.path.isdir(layout[x]):
                errors.append("missing directory %s (%s)" % (x, layout[x]))

        # be sure weewx.conf exists
        fn = os.path.join(layout['CONFIG_ROOT'], 'weewx.conf')
        if not os.path.exists(fn):
            errors.append("no weewx.conf at %s" % fn)

        if errors:
            raise Exception("verify layout failed:\n%s" % '\n'.join(errors))

        self.log("layout is \n  %s" % '\n  '.join(formatdict(layout)), level=1)

        return layout

    @staticmethod
    def verify_src(extdir):
        """ensure that the extension is something we can work with"""
        ifile = os.path.join(extdir, 'install.py')
        if not os.path.exists(ifile):
            raise Exception("no install.py found in %s" % extdir)

    def extract_tarball(self, filename, tmpdir):
        """do some basic checks on the tarball then extract it"""
        self.log("verify tarball %s" % filename, level=1)
        import tarfile
        root = None
        has_install = False
        errors = []
        archive = tarfile.open(filename, mode='r')
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
            if (f.name.startswith('.')
                or f.name.startswith('/')
                or f.name.find('..') >= 0):
                errors.append("suspect file '%s'" % f.name)
        if not has_install:
            errors.append("package has no install.py")
        if errors:
            raise Exception("verify tarball failed: %s" % '\n'.join(errors))

        self.log("extracting tarball %s" % filename, level=1)
        archive.extractall(path=tmpdir)
        archive.close()
        return root, os.path.join(tmpdir, root)

    def load_installer(self, dirname, basename, layout):
        """load the extension's installer"""
        self.log("import install.py from %s" % dirname, level=1)
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
        if self.delete_extdir:
            self.log("clean up files extracted from archive", level=1)
            shutil.rmtree(self.extdir, ignore_errors=True)

class ExtensionInstaller(Logger):
    """Base class for extension installers."""

    # extension components can be installed to these locations
    dirs = {
        'bin': 'BIN_ROOT',
        'skins': 'SKIN_ROOT',
        }

    def __init__(self, **kwargs):
        super(ExtensionInstaller, self).__init__()
        self.version = kwargs.get('version')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.author = kwargs.get('author')
        self.author_email = kwargs.get('author_email')
        self.files = kwargs.get('files', [])
        self.config = kwargs.get('config', {})
        self.service_groups = {}
        for sg in ['prep_services', 'data_services', 'process_services',
                   'archive_services', 'restful_services', 'report_services']:
            v = kwargs.get(sg, [])
            if not isinstance(v, list):
                v = [v]
            self.service_groups[sg] = v
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
        """prepend installed path to local path"""
        for d in self.dirs:
            if path.startswith(d):
                return path.replace(d, self.layout[self.dirs[d]])
        return path

    def install_files(self):
        """copy files from extracted package, make backup if already exist"""
        self.log("install_files", level=1)
        for t in self.files:
            dstdir = self.prepend_layout_path(t[0])
            try:
                self.log("mkdir %s" % dstdir, level=2)
                if self.doit:
                    mkdir(dstdir)
            except os.error:
                pass
            for f in t[1]:
                src = os.path.join(self.layout['EXTRACT_ROOT'], f)
                dst = self.prepend_layout_path(f)
                if os.path.exists(dst):
                    self.log("save existing file %s" % dst, level=2)
                    if self.doit:
                        save_path(dst)
                self.log("copy %s to %s" % (src, dst), level=2)
                if self.doit:
                    distutils.file_util.copy_file(src, dst)

    def uninstall_files(self):
        """delete files that were installed for this extension"""
        self.log("uninstall_files", level=1)
        for t in self.files:
            dstdir = self.prepend_layout_path(t[0])
            for f in t[1]:
                dst = self.prepend_layout_path(f)
                self.delete_file(dst)
                # if it is python source, delete any pyc and pyo as well
                if dst.endswith(".py"):
                    self.delete_file(dst.replace('.py', '.pyc'), False)
                    self.delete_file(dst.replace('.py', '.pyo'), False)
            # if the directory is empty, delete it
            try:
                if not os.listdir(dstdir):
                    self.log("delete directory %s" % dstdir, level=2)
                    if self.doit:
                        shutil.rmtree(dstdir, True)
                else:
                    self.log("directory not empty: %s" % dstdir, level=2)
            except OSError, e:
                self.log("delete failed: %s" % e, level=2)

    def delete_file(self, filename, report_errors=True):
        try:
            self.log("delete file %s" % filename, level=2)
            if self.doit:
                os.remove(filename)
        except OSError, e:
            if report_errors:
                self.log("delete failed: %s" % e, level=2)

    # FIXME: guard against weewx.conf that has no StdReport or HTML_ROOT
    def merge_config_options(self):
        self.log("merge_config_options", level=1)

        # make a copy of the new config
        cfg = dict(self.config)

        # get the old config
        fn = os.path.join(self.layout['CONFIG_ROOT'], 'weewx.conf')
        config = configobj.ConfigObj(fn)

        # prepend any html paths with existing HTML_ROOT
        prepend_path(cfg, 'HTML_ROOT', config['StdReport']['HTML_ROOT'])

        # if any variable begins with SKIN_DIR, replace with effective skin
        # directory (absolute or relative) from weewx.conf
        replace_string(cfg, 'INST_SKIN_ROOT', get_skin_dir(config))

        # massage the database dictionaries for this extension
        # FIXME: use parameterized root if possible
        try:
            sqlitecfg = config['Databases'].get('archive_sqlite', None)
            mysqlcfg = config['Databases'].get('archive_mysql', None)
            for k in cfg['Databases']:
                db = cfg['Databases'][k]
                if db['driver'] == 'weedb.sqlite' and sqlitecfg:
                    db['database_name'] = os.path.join(os.path.dirname(sqlitecfg['database_name']), db['database_name'])
                    db['root'] = sqlitecfg['root']
                elif db['driver'] == 'weedb.mysql' and mysqlcfg:
                    db['host'] = mysqlcfg['host']
                    db['user'] = mysqlcfg['user']
                    db['password'] = mysqlcfg['password']
        except:
            pass

        # merge the new options into the old config.  we cannot simply do
        # config.merge(cfg) because that would overwrite any existing fields.
        # so do a conditional merge instead.
        conditional_merge(config, cfg)

        # make the formatting match that of the default weewx.conf
        prettify(config, cfg)

        # append services to appropriate lists...
        for sg in self.service_groups:
            if not sg in config['Engine']['Services']:
                config['Engine']['Services'][sg] = []
            elif not isinstance(config['Engine']['Services'][sg], list):
                config['Engine']['Services'][sg] = [config['Engine']['Services'][sg]]
            # ... but only if not already there
            for s in self.service_groups[sg]:
                if s not in config['Engine']['Services'][sg]:
                    config['Engine']['Services'][sg].append(s)

        self.log("merged configuration:", level=3)
        self.log('\n'.join(formatdict(config)), level=3)

        self.save_config(config)

    def unmerge_config_options(self):
        self.log("unmerge_config_options", level=1)

        # get the old config
        fn = os.path.join(self.layout['CONFIG_ROOT'], 'weewx.conf')
        config = configobj.ConfigObj(fn)

        # remove any services we added
        for sg in self.service_groups:
            if sg in config['Engine']['Services']:
                newlist = []
                for s in config['Engine']['Services'][sg]:
                    if s not in self.service_groups[sg]:
                        newlist.append(s)
                config['Engine']['Services'][sg] = newlist

        # remove any sections we added
        remove_and_prune(config, self.config)

        self.log("unmerged configuration:", level=3)
        self.log('\n'.join(formatdict(config)), level=3)

        self.save_config(config)

    def save_config(self, config):
        # backup the old configuration
        self.log("save old configuration", level=2)
        if self.doit:
            _ = save_path(config.filename)

        # save the new configuration
        self.log("save new config %s" % config.filename, level=2)
        if self.doit:
            config.write()

    def install_history(self):
        """copy the installer to a location where we can find it later"""
        self.log("install_history", level=1)
        dstdir = os.path.join(self.layout['BIN_ROOT'], 'user')
        dstdir = os.path.join(dstdir, 'installer')
        dstdir = os.path.join(dstdir, self.basename)
        self.log("mkdir %s" % dstdir, level=2)
        if self.doit:
            mkdir(dstdir)
        src = os.path.join(self.layout['EXTRACT_ROOT'], 'install.py')
        self.log("copy %s to %s" % (src, dstdir), level=2)
        if self.doit:
            distutils.file_util.copy_file(src, dstdir)

    def uninstall_history(self):
        """remove the installer cache"""
        self.log("uninstall_history", level=1)
        dstdir = os.path.join(self.layout['BIN_ROOT'], 'user')
        dstdir = os.path.join(dstdir, 'installer')
        dstdir = os.path.join(dstdir, self.basename)
        self.log("delete %s" % dstdir, level=2)
        if self.doit:
            shutil.rmtree(dstdir, True)

def prettify(config, src):
    """clean up the config file:

    - put any global stanzas just before StdRESTful
    - prepend any global stanzas with a line of comment characters
    - put any StdReport stanzas before ftp and rsync
    - prepend any StdReport stanzas with a single empty line
    - prepend any database or databinding stanzas with a single empty line
    - prepend any restful stanzas with a single empty line
    """
    for k in src:
        if k in ['StdRESTful', 'DataBindings', 'Databases', 'StdReport']:
            for j in src[k]:
                if k == 'StdReport':
                    reorder_sections(config[k], j, 'RSYNC')
                    reorder_sections(config[k], j, 'FTP')
                config[k].comments[j] = minor_comment_block
        else:
            reorder_sections(config, k, 'StdRESTful')
            config.comments[k] = major_comment_block

def reorder_sections(c, src, dst):
    if src not in c.sections or dst not in c.sections:
        return
    src_idx = c.sections.index(src)
    c.sections.pop(src_idx)
    dst_idx = c.sections.index(dst)
    c.sections = c.sections[0:dst_idx] + [src] + c.sections[dst_idx:]
    # if index raises an exception, we want to fail hard

def conditional_merge(a, b):
    """merge fields from b into a, but only if they do not yet exist in a"""
    for k in b:
        if isinstance(b[k], dict):
            if not k in a:
                a[k] = {}
            conditional_merge(a[k], b[k])
        elif not k in a:
            a[k] = b[k]

def remove_and_prune(a, b):
    """remove fields from a that are present in b"""
    for k in b:
        if isinstance(b[k], dict):
            if k in a and type(a[k]) is configobj.Section:
                remove_and_prune(a[k], b[k])
                if not a[k].sections:
                    a.pop(k)
        elif k in a:
            a.pop(k)

def prepend_path(d, label, value):
    """prepend the value to every instance of the label in dict d"""
    for k in d:
        if isinstance(d[k], dict):
            prepend_path(d[k], label, value)
        elif k == label:
            d[k] = os.path.join(value, d[k])    

def replace_string(d, label, value):
    for k in d:
        if isinstance(d[k], dict):
            replace_string(d[k], label, value)
        else:
            d[k] = d[k].replace(label, value)

def get_skin_dir(config):
    """figure out the effective SKIN_DIR from a weewx configuration"""
    weewx_root = config['WEEWX_ROOT']
    skin_root = config['StdReport']['SKIN_ROOT']
    return os.path.join(weewx_root, skin_root)

def do_ext(action=None):
    import optparse
    description = "install/remove/list extensions to weewx"
    usage = """%prog install --extension (filename|directory)
                uninstall --extension extension_name
                list-extensions"""
    parser = optparse.OptionParser(description=description, usage=usage)
    parser.add_option('--extension', dest='ext', type=str, default=None,
                      metavar='EXT',
                      help='extension name, archive file, or directory')
    parser.add_option('--layout', dest='layout', type=str, default=None,
                      metavar='LAYOUT', help='layout is deb, rpm, or py')
    parser.add_option('--tmpdir', dest='tmpdir', type=str, default='/var/tmp',
                      metavar="DIR", help='temporary directory')
    parser.add_option('--dry-run', dest='dryrun', action='store_true',
                      help='print what would happen but do not do it')
    parser.add_option('--verbosity', dest='verbosity', type=int, default=1,
                      metavar="N", help='how much status to spew, 0-3')
    (options, _args) = parser.parse_args()

    ext = Extension(layout_type=options.layout, tmpdir=options.tmpdir)
    ext.set_verbosity(options.verbosity)
    ext.set_dryrun(options.dryrun)
    if action == 'list-extensions':
        ext.enumerate_extensions()
    elif action == 'install':
        ext.set_extension(options.ext)
        ext.install()
    elif action == 'uninstall':
        ext.set_extension(options.ext)
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
            lines.extend(formatdict(d[k], indent=indent + 1))
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
            printdict(d[k], indent=indent + 1)
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
    parser.add_option('--install-dir', dest='idir', type=str, metavar='DIR',
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
            _ = save_path(options.filec)
        shutil.copyfile(tmpfile.name, options.filec)
    return 0


#==============================================================================
# main entry point
#==============================================================================

if __name__ == "__main__":
    # options for dealing with extensions
    if 'list-extensions' in sys.argv:
        exit(do_ext('list-extensions'))
    if '--extension' in [f[:11] for f in sys.argv]:
        if 'install' in sys.argv:
            exit(do_ext('install'))
        elif 'uninstall' in sys.argv:
            exit(do_ext('uninstall'))
        else:
            exit(do_ext())

    # used by deb and rpm installers
    if '--merge-config' in sys.argv:
        exit(do_merge())
    # used by deb and rpm installers, or for manual post-install configure
    if 'configure' in sys.argv:
        exit(do_cfg())

    # for testing purposes
    if '--list-drivers' in sys.argv:
        list_drivers()
        exit(0)
    if '--prompt-for-driver' in sys.argv:
        print prompt_for_driver()
        exit(0)
    if '--prompt-for-info' in sys.argv:
        print prompt_for_info()
        exit(0)

    # inject weewx-specific help before the standard help message
    if '--help' in sys.argv:
        prog = os.path.basename(sys.argv[0])
        print "Commands for installing/upgrading weewx:"
        print ""
        print "  %s install [--quiet]" % prog
        print ""
        print "Commands for configuring weewx:"
        print ""
        print "  %s configure [--driver=DRIVER]" % prog
        print "  %s configure --help" % prog
        print ""
        print "Commands for installing/removing/listing weewx extensions:"
        print ""
        print "  %s list-extensions" % prog
        print "  %s install --extension forecast.tar.gz" % prog
        print "  %s uninstall --extension forecast" %prog
        print "  %s --help --extension" % prog
        print ""

    # try to get the configuration for this install/upgrade.  do this before
    # setup so that bailing out during prompts will result in no actions that
    # we might have to undo.
    info = None
    cfgfn = None
    if 'install' in sys.argv and '--help' not in sys.argv:
        cfgfn = get_conf_filename()
        if cfgfn is not None and os.path.exists(cfgfn):
            # if there is already a conf file, then this is an upgrade
            config_dict = configobj.ConfigObj(cfgfn)
            info = get_station_info(config_dict)
        if info is None:
            if '--quiet' in sys.argv:
                # for silent installs, do not prompt but end up with a fully
                # functional installation.
                info = {'driver': 'weewx.drivers.simulator'}
            else:
                # this must be a new install, so prompt for station info,
                # driver type, and driver-specific parameters, but only if
                # '--quiet' is not specified.
                info = prompt_for_info()
                info['driver'] = prompt_for_driver()
                info.update(prompt_for_driver_settings(info['driver']))

    # if someone tries to do an install from other than the source tree,
    # complain about it and bail out.
    if 'install' in sys.argv and not os.path.exists("%s/setup.cfg" % this_dir):
        print "The 'install' option can be used to install weewx only when"
        print "invoked from the source tree.  To install an extension, use"
        print "the '--extension' option."
        exit(1)

    # now invoke the standard python setup
    setup(name='weewx',
          version=VERSION,
          description='weather software',
          long_description="""weewx interacts with a weather station to produce graphs, reports, and HTML pages.  weewx can upload data to services such as the WeatherUnderground, PWSweather.com, or CWOP.""",
          author='Tom Keffer',
          author_email='tkeffer@gmail.com',
          url='http://www.weewx.com',
          license='GPLv3',
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
          cmdclass    = {"install_data": weewx_install_data,
                         "install_lib": weewx_install_lib,
                         "sdist": weewx_sdist,
                         "install_scripts": weewx_install_scripts},
          platforms   = ['any'],
          package_dir = {'': 'bin'},
          packages    = ['examples',
                         'schemas',
                         'user',
                         'weedb',
                         'weeplot',
                         'weeutil',
                         'weewx',
                         'weewx.drivers'],
          py_modules  = ['daemon'],
          scripts     = ['bin/wee_config_database',
                         'bin/wee_config_device',
                         'bin/weewxd',
                         'bin/wee_reports'],
          data_files  = [
            ('',
             ['LICENSE.txt',
              'README',
              'setup.py',
              'weewx.conf']),
            ('docs',
             ['docs/changes.txt',
              'docs/copyright.htm',
              'docs/customizing.htm',
              'docs/debian.htm',
              'docs/readme.htm',
              'docs/redhat.htm',
              'docs/setup.htm',
              'docs/suse.htm',
              'docs/upgrading.htm',
              'docs/usersguide.htm',
              'docs/images/daycompare.png',
              'docs/images/day-gap-not-shown.png',
              'docs/images/day-gap-showing.png',
              'docs/images/daytemp_with_avg.png',
              'docs/images/daywindvec.png',
              'docs/images/ferrites.jpg',
              'docs/images/funky_degree.png',
              'docs/images/image_parts.png',
              'docs/images/logo-apple.png',
              'docs/images/logo-centos.png',
              'docs/images/logo-debian.png',
              'docs/images/logo-fedora.png',
              'docs/images/logo-linux.png',
              'docs/images/logo-mint.png',
              'docs/images/logo-opensuse.png',
              'docs/images/logo-redhat.png',
              'docs/images/logo-suse.png',
              'docs/images/logo-ubuntu.png',
              'docs/images/logo-weewx.png',
              'docs/images/sample_monthrain.png',
              'docs/images/weekgustoverlay.png',
              'docs/images/weektempdew.png',
              'docs/images/yearhilow.png']),
            ('docs/css',
             ['docs/css/weewx_docs.css',
              'docs/css/jquery.tocify.css']),
            ('docs/css/ui-lightness',
             ['docs/css/ui-lightness/jquery-ui-1.10.4.custom.min.css']),
            ('docs/js',
             ['docs/js/jquery.tocify-1.9.0.min.js',
              'docs/js/jquery-1.11.1.min.js',
              'docs/js/jquery-ui-1.10.4.custom.min.js',
              'docs/js/weewx.js']),
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
             ['util/rsyslog.d/weewx.conf']),
            ('util/systemd',
             ['util/systemd/weewx.service'])]
          )

    # configure the station info and driver for both new install and upgrade
    if 'install' in sys.argv and '--help' not in sys.argv:
        configure_conf(cfgfn, info)
