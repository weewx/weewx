#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Utilities used by the setup and configure programs"""

from __future__ import with_statement

import errno
import glob
import os.path
import shutil
import sys
import StringIO
import tempfile

import configobj

import weeutil.weeutil
from weewx.engine import all_service_groups

minor_comment_block = [""]
major_comment_block = ["", "##############################################################################", ""]

#==============================================================================
#                  Section tuples
# Each ConfigObj section is recursively described by a "section tuple." This is
# a 3-way tuple with elements:
#
#   0: The name of the section;
#   1: A list of any subsection tuples;
#   2: A list of any scalar names.

canonical_order = ('',
[('Station', [], ['location', 'latitude', 'longitude', 'altitude',
                  'station_type', 'rain_year_start', 'week_start']), 
 ('AcuRite', [], []),
 ('CC3000', [], []),
 ('FineOffsetUSB', [], []),
 ('Simulator', [], []),
 ('TE923', [], []),
 ('Ultimeter', [], []),
 ('Vantage', [], []),
 ('WMR100', [], []),
 ('WMR200', [], []),
 ('WMR300', [], []),
 ('WMR9x8', [], []),
 ('WS1', [], []),
 ('WS23xx', [], []),
 ('WS28xx', [], []),
 ('StdRESTful', [('StationRegistry', [], ['register_this_station']), 
                 ('AWEKAS', [], ['enable', 'username', 'password']), 
                 ('CWOP', [], ['enable', 'station']), 
                 ('PWSweather', [], ['enable', 'station', 'password']), 
                 ('WOW', [], ['enable', 'station', 'password']), 
                 ('Wunderground', [], ['enable', 'station', 'password', 'rapidfire'])], []), 
 ('StdReport', [('StandardReport', [('Units', [('Groups', [], ['group_altitude', 'group_speed2', 'group_pressure', 'group_rain', 'group_rainrate', 'group_temperature', 'group_degree_day', 'group_speed'])], [])], ['skin']), 
                ('FTP', [], ['skin', 'secure_ftp', 'port', 'passive']), 
                ('RSYNC', [], ['skin', 'delete'])], 
  ['SKIN_ROOT', 'HTML_ROOT', 'data_binding']), 
 ('StdConvert', [], ['target_unit']), ('StdCalibrate', [('Corrections', [], [])], []), 
 ('StdQC', [('MinMax', [], ['barometer', 'outTemp', 'inTemp',
                            'outHumidity', 'inHumidity', 'windSpeed'])], []),
 ('StdWXCalculate', [], ['pressure', 'barometer', 'altimeter', 'windchill',
                         'heatindex', 'dewpoint', 'inDewpoint', 'rainRate']), 
 ('StdTimeSynch', [], ['clock_check', 'max_drift']), 
 ('StdArchive', [], ['archive_interval', 'archive_delay', 'record_generation',
                     'loop_hilo', 'data_binding']), 
 ('DataBindings', [('wx_binding', [], ['database', 'table_name', 'manager',
                                       'schema'])], []), 
 ('Databases', [('archive_sqlite', [], ['database_type', 'database_name']), 
                ('archive_mysql',  [], ['database_type', 'database_name'])], []),
 ('DatabaseTypes', [('SQLite', [], ['driver', 'SQLITE_ROOT']),
                    ('MySQL',  [], ['driver', 'host', 'user', 'password'])], []),
 ('Engine', [('Services', [], ['prep_services', 'data_services',
                               'process_services', 'archive_services',
                               'restful_services', 'report_services'])], [])], 
['debug', 'WEEWX_ROOT', 'socket_timeout', 'version'])

def get_section_tuple(c_dict, section_name=''):
    """ The above "canonical" ordering can be  generated from a config file
    by using this function:
    c = configobj.ConfigObj('weewx.conf')
    print get_section_tuple(c)"""

    subsections = [get_section_tuple(c_dict[ss], ss) for ss in c_dict.sections]
    section_tuple = (section_name, subsections, c_dict.scalars)
    return section_tuple
#==============================================================================

us_group = {'group_altitude': 'foot',
            'group_degree_day': 'degree_F_day',
            'group_pressure': 'inHg',
            'group_rain': 'inch',
            'group_rainrate': 'inch_per_hour',
            'group_speed': 'mile_per_hour',
            'group_speed2': 'mile_per_hour2',
            'group_temperature': 'degree_F'}

metric_group = {'group_altitude': 'meter',
                'group_degree_day': 'degree_C_day',
                'group_pressure': 'mbar',
                'group_rain': 'cm',
                'group_rainrate': 'cm_per_hour',
                'group_speed': 'km_per_hour',
                'group_speed2': 'km_per_hour2',
                'group_temperature': 'degree_C'}

metricwx_group = {'group_altitude': 'meter',
                  'group_degree_day': 'degree_C_day',
                  'group_pressure': 'mbar',
                  'group_rain': 'mm',
                  'group_rainrate': 'mm_per_hour',
                  'group_speed': 'meter_per_second',
                  'group_speed2': 'meter_per_second2',
                  'group_temperature': 'degree_C'}

class ExtensionError(IOError):
    """Errors when installing or uninstalling an extension"""
    
class Logger(object):
    def __init__(self, verbosity=0):
        self.verbosity = verbosity
    def log(self, msg, level=0):
        if self.verbosity >= level:
            print "%s%s" % ('  ' * (level - 1), msg)
    def set_verbosity(self, verbosity):
        self.verbosity = verbosity

#==============================================================================
#              Utilities that find and save ConfigObj objects
#==============================================================================

DEFAULT_LOCATIONS = ['../..', '/etc/weewx', '/home/weewx']

def find_file(file_path=None, args=None, locations=DEFAULT_LOCATIONS,
              file_name='weewx.conf'):
    """Find and return a path to a file, looking in "the usual places."
    
    General strategy:

    First, file_path is tried. If not found there, then the first element of
    args is tried.

    If those fail, try a path based on where the application is running.
    
    If that fails, then the list of directory locations is searched,
    looking for a file with file name file_name. 
    
    If after all that, the file still cannot be found, then an IOError
    exception will be raised.
    
    Parameters:

    file_path: A candidate path to the file.

    args: command-line arguments. If the file cannot be found in file_path,
    then the first element in args will be tried.
    
    locations: A list of directories to be searched. If they do not
    start with a slash ('/'), then they will be treated as relative to
    this file (bin/weecfg/__init__.py). 
    Default is ['../..', '/etc/weewx', '/home/weewx'].

    file_name: The name of the file to be found. This is used
    only if the directories must be searched. Default is 'weewx.conf'.

    returns: full path to the file
    """

    # Start by searching args (if available)
    if file_path is None and args:
        for i in range(len(args)):
            if not args[i].startswith('-'):
                file_path = args[i]
                del args[i]
                break

    if file_path is None:
        for directory in locations:
            # If this is a relative path, then prepend with the
            # directory this file is in:
            if not directory.startswith('/'):
                directory = os.path.join(os.path.dirname(__file__), directory)
            candidate = os.path.abspath(os.path.join(directory, file_name))
            if os.path.isfile(candidate):
                return candidate

    if file_path is None:
        raise IOError("Unable to find file '%s'. Tried directories %s" %
                      (file_name, locations))
    elif not os.path.isfile(file_path):
        raise IOError("%s is not a file" % file_path)

    return file_path

def read_config(config_path, args=None, locations=DEFAULT_LOCATIONS,
                file_name='weewx.conf'):
    """Read the specified configuration file, return an instance of ConfigObj
    with the file contents. If no file is specified, look in the standard
    locations for weewx.conf. Returns the filename of the actual configuration
    file, as well as the ConfigObj.

    config_path: configuration filename

    args: command-line arguments

    return: path-to-file, instance-of-ConfigObj
    
    Raises:
    
    SyntaxError: If there is a syntax error in the file
    
    IOError: If the file cannot be found
    """
    # Find and open the config file:
    config_path = find_file(config_path, args,
                            locations=locations, file_name=file_name)
    # Now open it up and parse it.
    config_dict = configobj.ConfigObj(config_path, file_error=True)
    return config_path, config_dict

def save_with_backup(config_dict, config_path):
    return save(config_dict, config_path, backup=True)

def save(config_dict, config_path, backup=False):
    """Save the config file, backing up as necessary."""
    
    # Check to see if the file exists and we are supposed to make backup:
    if os.path.exists(config_path) and backup:
        
        # Yes. We'll have to back it up.
        backup_path = weeutil.weeutil.move_with_timestamp(config_path)

        # Now we can save the file. Get a temporary file:
        tmpfile = tempfile.NamedTemporaryFile("w")
        
        # Write the configuration dictionary to it:
        config_dict.write(tmpfile)
        tmpfile.flush()
    
        # Now move the temporary file into the proper place:
        shutil.copyfile(tmpfile.name, config_path)

    else:
        
        # No existing file or no backup required. Just write.
        with open(config_path, 'w') as fd:
            config_dict.write(fd)
        backup_path = None

    return backup_path

#==============================================================================
#              Utilities that modify ConfigObj objects
#==============================================================================

def modify_config(config_dict, stn_info, logger, debug=False):
    """If a driver has a configuration editor, then use that to insert the
    stanza for the driver in the config_dict.  If there is no configuration
    editor, then inject a generic configuration, i.e., just the driver name
    with a single 'driver' element that points to the driver file.
    """
    driver_editor = None
    driver_name = None
    driver_version = None

    # Get the driver editor, name, and version:
    driver = stn_info.get('driver')
    if driver:
        try:
            # Look up driver info:
            driver_editor, driver_name, driver_version = \
                load_driver_editor(driver)
        except Exception, e:
            sys.exit("Driver %s failed to load: %s" % (driver, e))
        stn_info['station_type'] = driver_name
        if debug:
            logger.log('Using %s version %s (%s)' %
                       (driver_name, driver_version, driver), level=1)

    # Get a driver stanza, if possible
    stanza = None
    if driver_name is not None:
        if driver_editor is not None:
            orig_stanza_text = None

            # if a previous stanza exists for this driver, grab it
            if driver_name in config_dict:
                orig_stanza = configobj.ConfigObj(interpolation=False)
                orig_stanza[driver_name] = config_dict[driver_name]
                orig_stanza_text = '\n'.join(orig_stanza.write())

            # let the driver process the stanza or give us a new one
            stanza_text = driver_editor.get_conf(orig_stanza_text)
            stanza = configobj.ConfigObj(stanza_text.splitlines())

            # let the driver modify other parts of the configuration
            driver_editor.modify_config(config_dict)
        else:
            stanza = configobj.ConfigObj(interpolation=False)
            if driver_name in config_dict:
                stanza[driver_name] = config_dict[driver_name]
            else:
                stanza[driver_name] = {}

    # If we have a stanza, inject it into the configuration dictionary
    if stanza is not None and driver_name is not None:
        # Ensure that the driver field matches the path to the actual driver
        stanza[driver_name]['driver'] = driver
        # Insert the stanza in the configuration dictionary:
        config_dict[driver_name] = stanza[driver_name]
        # Add a major comment deliminator:
        config_dict.comments[driver_name] = major_comment_block
        # If we have a [Station] section, move the new stanza to just after it
        if 'Station' in config_dict:
            reorder_sections(config_dict, driver_name, 'Station', after=True)
            # make the stanza the station type
            config_dict['Station']['station_type'] = driver_name

    # Apply any overrides from the stn_info
    if stn_info:
        # Update driver stanza with any overrides from stn_info
        if driver_name is not None and driver_name in stn_info:
            for k in stn_info[driver_name]:
                config_dict[driver_name][k] = stn_info[driver_name][k]
        # Update station information with stn_info overrides
        for p in ['location', 'latitude', 'longitude', 'altitude']:
            if stn_info.get(p) is not None:
                if debug:
                    logger.log("Using %s for %s" % (stn_info[p], p), level=2)
                config_dict['Station'][p] = stn_info[p]
        # Update units display with any stn_info overrides
        if stn_info.get('units') is not None:
            if stn_info.get('units') in ['metric', 'metricwx']:
                if debug:
                    logger.log("Using Metric units for display", level=2)
                config_dict['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': metricwx_group}})
            elif stn_info.get('units') == 'us':
                if debug:
                    logger.log("Using US units for display", level=2)
                config_dict['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': us_group}})

#==============================================================================
#              Utilities that update and merge ConfigObj objects
#==============================================================================

def update_and_merge(config_dict, template_dict):
    
    update_config(config_dict)
    merge_config(config_dict, template_dict)
    
    # We use the number of comment lines for the 'Station' section as a
    # heuristic of whether the config dict has been updated to the new
    # comment structure
    if len(config_dict.comments['Station']) <= 3:
        transfer_comments(config_dict, template_dict)
    
def update_config(config_dict):
    """Update a (possibly old) configuration dictionary to the latest format.

    Raises exception of type ValueError if it cannot be done.
    """

    # Get the version number. If it does not appear at all, then
    # assume a very old version:
    config_version = config_dict.get('version') or '1.0.0'

    major, minor, _ = config_version.split('.')
    # Take care of the collation problem when comparing things like
    # version '1.9' to '1.10' by prepending a '0' to the former:
    if len(minor) < 2:
        minor = '0' + minor

    # I don't know how to merge older, V1.X configuration files, only
    # newer V2.X ones.
    if major == '1':
        raise ValueError("Cannot merge version %s. Too old" % config_version)

    if major == '2' and minor < '07':
        update_to_v27(config_dict)

    if major < '3':
        update_to_v30(config_dict)
        
    update_to_v32(config_dict)

def merge_config(config_dict, template_dict):
    """Merge the configuration dictionary into the template dictionary,
    overriding any options. Return the results.
    
    config_dict: An existing, older configuration dictionary.
    
    template_dict: A newer dictionary supplied by the installer.
    """

    # Turn off interpolation so what gets merged is the symbolic name
    # (such as WEEWX_ROOT), and not its interpolated value. 
    csave, config_dict.interpolation = config_dict.interpolation, False
    tsave, template_dict.interpolation = template_dict.interpolation, False

    # Merge new stuff from the template:
    weeutil.weeutil.conditional_merge(config_dict, template_dict)
    
    config_dict.interpolation = csave
    template_dict.interpolation = tsave

    # Finally, update the version number:
    config_dict['version'] = template_dict['version']

    return config_dict

def update_to_v27(config_dict):
    """Updates a configuration file to the latest V2.X version.
    Since V2.7 was the last 2.X version, that's our target"""

    service_map_v2 = {'weewx.wxengine.StdTimeSynch' : 'prep_services',
                      'weewx.wxengine.StdConvert'   : 'process_services',
                      'weewx.wxengine.StdCalibrate' : 'process_services',
                      'weewx.wxengine.StdQC'        : 'process_services',
                      'weewx.wxengine.StdArchive'   : 'archive_services',
                      'weewx.wxengine.StdPrint'     : 'report_services',
                      'weewx.wxengine.StdReport'    : 'report_services'}

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
            sys.exit("\n*** Configuration file has both a 'WMR-USB' "
                     "section and a 'WMR100' section. Aborting ***\n\n")
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
            sys.exit("\n*** Configuration file has both a 'WMR-918' "
                     "section and a 'WMR9x8' section. Aborting ***\n\n")
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
            config_dict['StdRESTful']['CWOP']['post_interval'] = \
                config_dict['StdRESTful']['CWOP']['interval']
            config_dict['StdRESTful']['CWOP'].pop('interval')
        # Option "server" has become "server_list". It is also no longer
        # included in the default weewx.conf, so just pop it.
        if 'server' in config_dict['StdRESTful']['CWOP']:
            config_dict['StdRESTful']['CWOP'].pop('server')

    # Remove the no longer needed "driver" from all the RESTful services:
    if 'StdRESTful' in config_dict:
        for section in config_dict['StdRESTful'].sections:
            config_dict['StdRESTful'][section].pop('driver', None)

    config_dict['version'] = '2.7.0'

def update_to_v30(config_dict):
    """Update a configuration file to V3.0"""
    old_database = None

    v3_additions = """[DataBindings]
    # This section binds a data store to a database

    [[wx_binding]]
        # The database must match one of the sections in [Databases] 
        database = archive_sqlite
        # The name of the table within the database
        table_name = archive
        # The manager handles aggregation of data for historical summaries
        manager = weewx.wxmanager.WXDaySummaryManager
        # The schema defines the structure of the database.
        # It is *only* used when the database is created.
        schema = schemas.wview.schema

"""

    if 'Databases' in config_dict:
        # The stats database no longer exists. Remove it from the [Databases]
        # section:
        config_dict['Databases'].pop('stats_sqlite', None)
        config_dict['Databases'].pop('stats_mysql', None)
        # The key "database" changed to "database_name"
        for stanza in config_dict['Databases']:
            if 'database' in config_dict['Databases'][stanza]:
                config_dict['Databases'][stanza].rename('database',
                                                        'database_name')

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
                # If service_list is not already a list (it could be just a
                # single name), then make it a list:
                if not hasattr(service_list, '__iter__'):
                    service_list = [service_list]
                config_dict['Engine']['Services'][list_name] = \
                    [this_item.replace('wxengine', 'engine') for this_item in service_list]
        try:
            # Finally, make sure the new StdWXCalculate service is in the list:
            if 'weewx.wxservices.StdWXCalculate' not in config_dict['Engine']['Services']['process_services']:
                config_dict['Engine']['Services']['process_services'].append('weewx.wxservices.StdWXCalculate')
        except KeyError:
            pass

    if 'DataBindings' not in config_dict:
        # Insert a [DataBindings] section. First create it
        c = configobj.ConfigObj(StringIO.StringIO(v3_additions))
        # Now merge it in:
        config_dict.merge(c)
        # For some reason, ConfigObj strips any leading comments. Put them back:
        config_dict.comments['DataBindings'] = major_comment_block
        # Move the new section to just before [Databases]
        reorder_sections(config_dict, 'DataBindings', 'Databases')
        # No comments between the [DataBindings] and [Databases] sections:
        config_dict.comments['Databases'] = [""]
        config_dict.inline_comments['Databases'] = []

        # If there was an old database, add it in the new, correct spot:
        if old_database:
            try:
                config_dict['DataBindings']['wx_binding']['database'] = old_database
            except KeyError:
                pass

    config_dict['version'] = '3.0.0'

def update_to_v32(config_dict):
    """Update a configuration file to V3.2"""
    
    # For interpolation to work, it's critical that WEEWX_ROOT not end
    # with a trailing slash ('/'). Convert it to the normative form:
    config_dict['WEEWX_ROOT'] = os.path.normpath(config_dict['WEEWX_ROOT'])
    
    # Add a default database-specific top-level stanzas if necessary
    if 'DatabaseTypes' not in config_dict:
        # Do SQLite first. Start with a sanity check:
        try:
            assert(config_dict['Databases']['archive_sqlite']['driver'] == 'weedb.sqlite')
        except KeyError:
            pass
        # Set the default [[SQLite]] section. Turn off interpolation first, so the
        # symbol for WEEWX_ROOT does not get lost.
        save, config_dict.interpolation = config_dict.interpolation, False
        config_dict['DatabaseTypes'] = {
            'SQLite': {'driver': 'weedb.sqlite',
                       'SQLITE_ROOT': '%(WEEWX_ROOT)s/archive'}}
        config_dict.interpolation = save
        try:
            root = config_dict['Databases']['archive_sqlite']['root']
            database_name = config_dict['Databases']['archive_sqlite']['database_name']
            fullpath = os.path.join(root, database_name)
            dirname = os.path.dirname(fullpath)
            # By testing to see if they end up resolving to the same thing,
            # we can keep the interpolation used to specify SQLITE_ROOT above.
            if dirname != config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT']:
                config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] = dirname
            config_dict['Databases']['archive_sqlite']['database_name'] = os.path.basename(fullpath)
            config_dict['Databases']['archive_sqlite']['database_type'] = 'SQLite'
            config_dict['Databases']['archive_sqlite'].pop('root', None)
            config_dict['Databases']['archive_sqlite'].pop('driver', None)
        except KeyError:
            pass
    
        # Now do MySQL. Start with a sanity check:
        try:
            assert(config_dict['Databases']['archive_mysql']['driver'] == 'weedb.mysql')
        except KeyError:
            pass
        config_dict['DatabaseTypes']['MySQL'] = {'driver': 'weedb.mysql',
                                                 'host': 'localhost',
                                                 'user': 'weewx',
                                                 'password': 'weewx'}
        try:
            config_dict['DatabaseTypes']['MySQL']['host'] = config_dict['Databases']['archive_mysql']['host']
            config_dict['DatabaseTypes']['MySQL']['user'] = config_dict['Databases']['archive_mysql']['user']
            config_dict['DatabaseTypes']['MySQL']['password'] = config_dict['Databases']['archive_mysql']['password']
            config_dict['Databases']['archive_mysql'].pop('host', None)
            config_dict['Databases']['archive_mysql'].pop('user', None)
            config_dict['Databases']['archive_mysql'].pop('password', None)
            config_dict['Databases']['archive_mysql'].pop('driver', None)
            config_dict['Databases']['archive_mysql']['database_type'] = 'MySQL'
        except KeyError:
            pass
            
    # Version 3.2 introduces the 'enable' keyword for RESTful protocols. Set
    # it appropriately
    def set_enable(c, service, keyword):
        # Check to see whether this config file has the service listed
        try:
            c['StdRESTful'][service]
        except KeyError:
            # It does not. Nothing to do.
            return

        # Now check to see whether it already has the option 'enable':
        if 'enable' in c['StdRESTful'][service]:
            # It does. No need to proceed
            return

        # The option 'enable' is not present. Add it,
        # and set based on whether the keyword is present:
        if keyword in c['StdRESTful'][service]:
            c['StdRESTful'][service]['enable'] = 'true'
        else:
            c['StdRESTful'][service]['enable'] = 'false'

    set_enable(config_dict, 'AWEKAS', 'username')
    set_enable(config_dict, 'CWOP', 'station')
    set_enable(config_dict, 'PWSweather', 'station')
    set_enable(config_dict, 'WOW', 'station')
    set_enable(config_dict, 'Wunderground', 'station')
    
    config_dict['version'] = '3.2.0'
        
def transfer_comments(config_dict, template_dict):
    
    # If this is the top-level, transfer the initial comments
    if config_dict.parent is config_dict:
        config_dict.initial_comment = template_dict.initial_comment
    
    # Now go through each section, transferring its comments
    for section in config_dict.sections:
        try:
            config_dict.comments[section] = template_dict.comments[section]
            # Recursively transfer the subsection comments:
            transfer_comments(config_dict[section], template_dict[section])
        except KeyError:
            pass

    # Finally, do the section's scalars:
    for scalar in config_dict.scalars:
        try:
            config_dict.comments[scalar] = template_dict.comments[scalar]
        except KeyError:
            pass

#==============================================================================
#              Utilities that extract from ConfigObj objects
#==============================================================================

def get_station_info(config_dict):
    """Extract station info from config dictionary."""
    stn_info = dict()
    if config_dict is not None:
        if 'Station' in config_dict:
            stn_info['location'] = weeutil.weeutil.list_as_string(config_dict['Station'].get('location'))
            stn_info['latitude'] = config_dict['Station'].get('latitude')
            stn_info['longitude'] = config_dict['Station'].get('longitude')
            stn_info['altitude'] = config_dict['Station'].get('altitude')
            if 'station_type' in config_dict['Station']:
                stn_info['station_type'] = config_dict['Station']['station_type']
                if stn_info['station_type'] in config_dict:
                    stn_info['driver'] = config_dict[stn_info['station_type']]['driver']
        if 'StdReport' in config_dict:
            stn_info['units'] = get_unit_info(config_dict)

    return stn_info

def get_unit_info(config_dict):
    """Intuit what unit system the reports are in."""
    try:
        group_dict = config_dict['StdReport']['StandardReport']['Units']['Groups']
        # Look for a strict superset of the group settings:
        if all(group_dict[group] == us_group[group] for group in us_group):
            return 'us'
        elif all(group_dict[group] == metric_group[group] for group in metric_group):
            return 'metric'
        elif all(group_dict[group] == metricwx_group[group] for group in metricwx_group):
            return 'metricwx'
    except KeyError:
        return None

#==============================================================================
#                Utilities that manipulate ConfigObj objects
#==============================================================================

# The following utility is probably not necessary any longer.
# reorder_to_ref() should be used instead.
def reorder_sections(config_dict, src, dst, after=False):
    """Move the section with key src to just before (after=False) or after
    (after=True) the section with key dst. """
    bump = 1 if after else 0
    # We need both keys to procede:
    if src not in config_dict.sections or dst not in config_dict.sections:
        return
    # If index raises an exception, we want to fail hard.
    # Find the source section (the one we intend to move):
    src_idx = config_dict.sections.index(src)
    # Remove it
    config_dict.sections.pop(src_idx)
    # Find the destination
    dst_idx = config_dict.sections.index(dst)
    # Now reorder the attribute 'sections', putting src just before dst:
    config_dict.sections = config_dict.sections[:dst_idx + bump] + [src] + \
                           config_dict.sections[dst_idx + bump:]

def reorder_to_ref(config_dict, section_tuple=canonical_order):
    """Reorder any sections in concordance with a reference ordering.
    
    See the definition for canonical_ordering for the details of the tuple
    used to describe a section.
    """
    if not len(section_tuple):
        return
    # Get the names of any subsections in the order they should be in:
    subsection_order = [x[0] for x in section_tuple[1]]
    # Reorder the subsections, then the scalars
    config_dict.sections = reorder(config_dict.sections, subsection_order)
    config_dict.scalars = reorder(config_dict.scalars, section_tuple[2])
    
    # Now recursively go through each of my subsections,
    # allowing them to reorder their contents
    for ss_tuple in section_tuple[1]:
        ss_name = ss_tuple[0]
        if ss_name in config_dict:
            reorder_to_ref(config_dict[ss_name], ss_tuple)
    
def reorder(name_list, ref_list):
    """Reorder the names in name_list, according to a reference list."""
    result = []
    # Use the ordering in ref_list, to reassemble the name list:
    for name in ref_list:
        # These always come at the end
        if name in ['FTP', 'RSYNC']:
            continue
        if name in name_list:
            result.append(name)
    # For any that were not in the reference list and are left over, tack
    # them on to the end:
    for name in name_list:
        if name not in ref_list:
            result.append(name)
            
    # Finally, add these, so they are at the very end
    for name in ref_list:
        if name in ['FTP', 'RSYNC']:
            result.append(name)
            
    # Make sure I have the same number I started with
    assert(len(name_list) == len(result))
    return result
    
def remove_and_prune(a_dict, b_dict):
    """Remove fields from a_dict that are present in b_dict"""
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if k in a_dict and type(a_dict[k]) is configobj.Section:
                remove_and_prune(a_dict[k], b_dict[k])
                if not a_dict[k].sections:
                    a_dict.pop(k)
        elif k in a_dict:
            a_dict.pop(k)

def prepend_path(a_dict, label, value):
    """Prepend the value to every instance of the label in dict a_dict"""
    for k in a_dict:
        if isinstance(a_dict[k], dict):
            prepend_path(a_dict[k], label, value)
        elif k == label:
            a_dict[k] = os.path.join(value, a_dict[k])

#def replace_string(a_dict, label, value):
#    for k in a_dict:
#        if isinstance(a_dict[k], dict):
#            replace_string(a_dict[k], label, value)
#        else:
#            a_dict[k] = a_dict[k].replace(label, value)

#==============================================================================
#                Utilities that work on drivers
#==============================================================================

def get_all_driver_infos():
    # first look in the drivers directory
    infos = get_driver_infos()
    # then add any drivers in the user directory
    infos.update(get_driver_infos('user'))
    return infos

def get_driver_infos(driver_pkg_name='weewx.drivers', excludes=['__init__.py']):
    """Scan the drivers folder, extracting information about each available
    driver. Return as a dictionary, keyed by the driver module name.
    
    Valid drivers must be importable, and must have attribute "DRIVER_NAME"
    defined.
    """

    __import__(driver_pkg_name)
    driver_package = sys.modules[driver_pkg_name]
    driver_pkg_directory = os.path.dirname(os.path.abspath(driver_package.__file__))
    driver_list = [os.path.basename(f) for f in glob.glob(os.path.join(driver_pkg_directory, "*.py"))]

    driver_info_dict = {}
    for filename in driver_list:
        if filename in excludes:
            continue

        # Get the driver module name. This will be something like
        # 'weewx.drivers.fousb'
        driver_module_name = os.path.splitext("%s.%s" % (driver_pkg_name,
                                                         filename))[0]
        
        try:
            # Try importing the module
            __import__(driver_module_name)
            driver_module = sys.modules[driver_module_name]

            # A valid driver will define the attribute "DRIVER_NAME"
            if hasattr(driver_module, 'DRIVER_NAME'):
                # A driver might define the attribute DRIVER_VERSION
                driver_module_version = driver_module.DRIVER_VERSION \
                    if hasattr(driver_module, 'DRIVER_VERSION') else '?'
                # Create an entry for it, keyed by the driver module name
                driver_info_dict[driver_module_name] = {
                    'module_name': driver_module_name,
                    'driver_name': driver_module.DRIVER_NAME,
                    'version': driver_module_version,
                    'status': ''}
        except ImportError, e:
            # If the import fails, report it in the status
            driver_info_dict[driver_module_name] = {
                'module_name': driver_module_name,
                'driver_name': '?',
                'version': '?',
                'status': e}
        except Exception, e:
            # Ignore anything else.  This might be a python file that is not
            # a driver, a python file with errors, or who knows what.
            pass

    return driver_info_dict

def print_drivers():
    """Get information about all the available drivers, then print it out."""
    driver_info_dict = get_all_driver_infos()
    keys = sorted(driver_info_dict)
    print "%-25s%-15s%-9s%-25s" % (
        "Module name", "Driver name", "Version", "Status")
    for d in keys:
        print "  %(module_name)-25s%(driver_name)-15s%(version)-9s%(status)-25s" % driver_info_dict[d]

def load_driver_editor(driver_module_name):
    """Load the configuration editor from the driver file
    
    driver_module_name: A string holding the driver name.
                        E.g., 'weewx.drivers.fousb'
    """
    __import__(driver_module_name)
    driver_module = sys.modules[driver_module_name]
    editor = None
    driver_name = None
    driver_version = 'undefined'
    if hasattr(driver_module, 'confeditor_loader'):
        loader_function = getattr(driver_module, 'confeditor_loader')
        editor = loader_function()
    if hasattr(driver_module, 'DRIVER_NAME'):
        driver_name = driver_module.DRIVER_NAME
    if hasattr(driver_module, 'DRIVER_VERSION'):
        driver_version = driver_module.DRIVER_VERSION
    return editor, driver_name, driver_version


#==============================================================================
#                Utilities that seek info from the command line
#==============================================================================

def prompt_for_info(location=None, latitude='90.000', longitude='0.000',
                    altitude=['0', 'meter'], units='metric', **kwargs):
    #
    #  Description
    #
    print "Enter a brief description of the station, such as its location.  For example:"
    print "Santa's Workshop, North Pole"
    loc = prompt_with_options("description", location)

    #
    #  Altitude
    #
    print "Specify altitude, with units 'foot' or 'meter'.  For example:"
    print "35, foot"
    print "12, meter"
    msg = "altitude [%s]: " % weeutil.weeutil.list_as_string(altitude) if altitude else "altitude: "
    alt = None
    while alt is None:
        ans = raw_input(msg).strip()
        if ans:
            parts = ans.split(',')
            if len(parts) == 2:
                try:
                    # Test whether the first token can be converted into a
                    # number. If not, an exception will be raised.
                    float(parts[0])
                    if parts[1].strip() in ['foot', 'meter']:
                        alt = [parts[0].strip(), parts[1].strip()]
                except (ValueError, TypeError):
                    pass
        elif altitude:
            alt = altitude

        if not alt:
            print "Unrecognized response. Try again."

    #
    # Latitude & Longitude
    #
    print "Specify latitude in decimal degrees, negative for south."
    lat = prompt_with_limits("latitude", latitude, -90, 90)
    print "Specify longitude in decimal degrees, negative for west."
    lon = prompt_with_limits("longitude", longitude, -180, 180)

    #
    # Display units
    #
    print "Indicate the preferred units for display: 'metric' or 'us'"
    uni = prompt_with_options("units", units, ['us', 'metric'])

    return {'location': loc,
            'altitude': alt,
            'latitude': lat,
            'longitude': lon,
            'units': uni}


def prompt_for_driver(dflt_driver=None):
    """Get the information about each driver, return as a dictionary."""
    infos = get_all_driver_infos()
    keys = sorted(infos)
    dflt_idx = None
    print "Installed drivers include:"
    for i, d in enumerate(keys):
        print " %2d) %-15s %-25s %s" % (i, infos[d].get('driver_name', '?'),
                                        "(%s)" % d, infos[d].get('status', ''))
        if dflt_driver == d:
            dflt_idx = i
    msg = "choose a driver [%d]: " % dflt_idx if dflt_idx is not None else "choose a driver: "
    idx = 0
    ans = None
    while ans is None:
        ans = raw_input(msg).strip()
        if not ans:
            ans = dflt_idx
        try:
            idx = int(ans)
            if not 0 <= idx < len(keys):
                ans = None
        except (ValueError, TypeError):
            ans = None
    return keys[idx]

def prompt_for_driver_settings(driver):
    """Let the driver prompt for any required settings.  If the driver does
    not define a method for prompting, return an empty dictionary."""
    settings = dict()
    try:
        __import__(driver)
        driver_module = sys.modules[driver]
        loader_function = getattr(driver_module, 'confeditor_loader')
        editor = loader_function()
        settings[driver_module.DRIVER_NAME] = editor.prompt_for_settings()
    except AttributeError:
        pass
    return settings

def prompt_with_options(prompt, default=None, options=None):
    """Ask the user for an input with an optional default value.
    
    prompt: A string to be used for a prompt.
    
    default: A default value. If the user simply hits <enter>, this
    is the value returned. Optional.
    
    options: A list of possible choices. The returned value must be in
    this list. Optional."""

    msg = "%s [%s]: " % (prompt, default) if default is not None else "%s: " % prompt
    value = None
    while value is None:
        value = raw_input(msg).strip()
        if value:
            if options and value not in options:
                value = None
        elif default is not None:
            value = default

    return value

def prompt_with_limits(prompt, default=None, low_limit=None, high_limit=None):
    """Ask the user for an input with an optional default value. The
    returned value must lie between optional upper and lower bounds.
    
    prompt: A string to be used for a prompt.
    
    default: A default value. If the user simply hits <enter>, this
    is the value returned. Optional.
    
    low_limit: The value must be equal to or greater than this value.
    Optional.
    
    high_limit: The value must be less than or equal to this value.
    Optional.
    """
    msg = "%s [%s]: " % (prompt, default) if default is not None else "%s: " % prompt
    value = None
    while value is None:
        value = raw_input(msg).strip()
        if value:
            try:
                v = float(value)
                if (low_limit is not None and v < low_limit) or \
                   (high_limit is not None and v > high_limit):
                    value = None
            except (ValueError, TypeError):
                value = None
        elif default is not None:
            value = default

    return value

#==============================================================================
#            Miscellaneous utilities
#==============================================================================

def extract_roots(config_path, config_dict, bin_root):
    """Get the location of the various root directories used by weewx."""
    
    root_dict = {'WEEWX_ROOT': config_dict['WEEWX_ROOT'],
                 'CONFIG_ROOT': os.path.dirname(config_path)}
    # If bin_root has not been defined, then figure out where it is using
    # the location of this file:
    if bin_root:
        root_dict['BIN_ROOT'] = bin_root
    else:
        root_dict['BIN_ROOT'] = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..'))
    # The user subdirectory:
    root_dict['USER_ROOT'] = os.path.join(root_dict['BIN_ROOT'], 'user')
    # The extensions directory is in the user directory:
    root_dict['EXT_ROOT'] = os.path.join(root_dict['USER_ROOT'], 'installer')
    # Add SKIN_ROOT if it can be found:
    try:
        root_dict['SKIN_ROOT'] = os.path.abspath(os.path.join(
                root_dict['WEEWX_ROOT'],
                config_dict['StdReport']['SKIN_ROOT']))
    except KeyError:
        pass
    
    return root_dict

def extract_tar(filename, target_dir, logger=None):
    """Extract files from a tar archive into a given directory
    
    Returns: A list of the extracted files
    """
    logger = logger or Logger()
    import tarfile
    logger.log("Extracting from tar archive %s" % filename, level=1)
    tar_archive = None
    try:
        tar_archive = tarfile.open(filename, mode='r')
        tar_archive.extractall(target_dir)
        member_names = [os.path.normpath(x.name) for x in tar_archive.getmembers()]
        return member_names
    finally:
        if tar_archive is not None:
            tar_archive.close()

def extract_zip(filename, target_dir, logger=None):
    """Extract files from a zip archive into the specified directory.

    Returns: a list of the extracted files
    """
    logger = logger or Logger()
    import zipfile
    logger.log("Extracting from zip archive %s" % filename, level=1)
    zip_archive = None
    try:
        zip_archive = zipfile.ZipFile(open(filename, mode='r'))
        member_names = zip_archive.namelist()
        # manually extract files since extractall is only in python 2.6+
#        zip_archive.extractall(target_dir)
        for f in member_names:
            if f.endswith('/'):
                dst = "%s/%s" % (target_dir, f)
                mkdir_p(dst)
        for f in member_names:
            if not f.endswith('/'):
                path = "%s/%s" % (target_dir, f)
                with open(path, 'wb') as dest_file:
                    dest_file.write(zip_archive.read(f))
        return member_names
    finally:
        if zip_archive is not None:
            zip_archive.close()

def mkdir_p(path):
    """equivalent to 'mkdir -p'"""
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_extension_installer(extension_installer_dir):
    """Get the installer in the given extension installer subdirectory"""
    old_path = sys.path
    try:
        # Inject the location of the installer directory into the path
        sys.path.insert(0, extension_installer_dir)
        try:
            # Now I can import the extension's 'install' module:
            __import__('install')
        except ImportError:
            raise ExtensionError("Cannot find 'install' module in %s" % extension_installer_dir)
        install_module = sys.modules['install']
        loader = getattr(install_module, 'loader')
        # Get rid of the module:
        sys.modules.pop('install', None)
        installer = loader()
    finally:
        # Restore the path
        sys.path = old_path

    return (install_module.__file__, installer)
