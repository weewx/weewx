#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Utilities used by the setup and configure programs"""

from __future__ import with_statement

import glob
import os
import shutil
import sys
import StringIO
import tempfile

import configobj

import weeutil.weeutil
from weewx.engine import all_service_groups

minor_comment_block = [""]
major_comment_block = ["", "##############################################################################", ""]

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

def find_file(file_path=None, args=None, locations=None,
              file_name='weewx.conf'):
    """Find and return a path to a file, looking in "the usual places."
    
    General strategy:

    First, file_path is tried. If not found there, then the first element of
    args is tried. 
    
    If those both fail, then the list of directory locations is searched,
    looking for a file with file name file_name. 
    
    If after all that, the file still cannot be found, then an IOError
    exception will be raised.
    
    Parameters:

    file_path: A candidate path to the file.

    args: command-line arguments. If the file cannot be found in file_path,
    then the first element in args will be tried.
    
    locations: A list of directories to be searched. 
    Default is [rundir, '/etc/weewx', '/home/weewx'], where rundir is the
    WEEWX_ROOT based on the location from which this is running.

    file_name: The name of the file to be found. This is used
    only if the directories must be searched. Default is 'weewx.conf'.

    returns: full path to the file
    """

    if file_path is None:
        if args and not args[0].startswith('-'):
            file_path = args[0]
            # Shift args to the left:
            del args[0]

    if file_path is None:
        # Try a location based on the current run directory, but only if it
        # looks like a setup.py installation (possibly to a non-standard
        # location).
        this_file = os.path.join(os.getcwd(), __file__)
        rundir = os.path.abspath(os.path.dirname(this_file))
        (rundir, _) = os.path.split(rundir) # peel off the weewxcfg dir
        (rundir, subdir) = os.path.split(rundir) # next up is the bin dir
        if subdir == 'bin':
            # if it really is the bin directory, then look for the conf file
            candidate = os.path.join(rundir, file_name)
            if os.path.isfile(candidate):
                return candidate

    if file_path is None:
        if locations is None:
            # Use the standard locations if nothing was specified
            locations = ['/etc/weewx', '/home/weewx']

        for directory in locations:
            candidate = os.path.join(directory, file_name)
            if os.path.isfile(candidate):
                return candidate

    if file_path is None:
        raise IOError("Unable to find file '%s'. Tried directories %s" %
                      (file_name, locations))
    elif not os.path.isfile(file_path):
        raise IOError("%s is not a file" % file_path)

    return file_path

def read_config(config_path, args=None, locations=None,
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

def modify_config(config_dict, stn_info, debug=False):
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
            print 'Using %s version %s (%s)' % (stn_info['station_type'],
                                                driver_version, driver)

    # Get a driver stanza, if possible
    stanza = None
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

    # If we have a stanza, inject it into the configuration dictionary
    if stanza is not None:
        # Insert the stanza in the configuration dictionary:
        config_dict[driver_name] = stanza[driver_name]
        # Add a major comment deliminator:
        config_dict.comments[driver_name] = major_comment_block
        # If we have a [Station] section, the move the new stanza to just
        # after it
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
                    print "Using %s for %s" % (stn_info[p], p)
                config_dict['Station'][p] = stn_info[p]
        # Update units display with any stn_info overrides
        if stn_info.get('units') is not None:
            if stn_info.get('units') in ['metric', 'metricwx']:
                if debug:
                    print "Using Metric units for display"
                config_dict['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': metricwx_group}})
            elif stn_info.get('units') == 'us':
                if debug:
                    print "Using US units for display"
                config_dict['StdReport']['StandardReport'].update({
                        'Units': {
                            'Groups': us_group}})

#==============================================================================
#              Utilities that update ConfigObj objects
#==============================================================================

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
    
    config_dict: This is usually the existing, older configuration dictionary.
    
    template_dict: This is usually the newer dictionary supplied by the installer.
    """

    config_dict.interpolate = False

    # Merge new stuff from the template:
    conditional_merge(config_dict, template_dict)

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
        # For some reason, ConfigObj strips any leading comments. Add them back in:
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
    # The only difference is that we are no longer using SVN, so get rid
    # of its ident
    for i in range(len(config_dict.initial_comment)):
        if config_dict.initial_comment[i].find("$Id") >= 0:
            config_dict.initial_comment[i] = "#                                                                            #"

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

# def prettify(config, src):
#     """clean up the config file:
# 
#     - put any global stanzas just before StdRESTful
#     - prepend any global stanzas with a line of comment characters
#     - put any StdReport stanzas before ftp and rsync
#     - prepend any StdReport stanzas with a single empty line
#     - prepend any database or databinding stanzas with a single empty line
#     - prepend any restful stanzas with a single empty line
#     """
#     for k in src:
#         if k in ['StdRESTful', 'DataBindings', 'Databases', 'StdReport']:
#             for j in src[k]:
#                 if k == 'StdReport':
#                     reorder_sections(config[k], j, 'RSYNC')
#                     reorder_sections(config[k], j, 'FTP')
#                 config[k].comments[j] = minor_comment_block
#         else:
#             reorder_sections(config, k, 'StdRESTful')
#             config.comments[k] = major_comment_block

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

def conditional_merge(a_dict, b_dict):
    """Merge fields from b_dict into a_dict, but only if they do not yet
    exist in a_dict"""
    # Go through each key in b_dict
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if not k in a_dict:
                # It's a new section. Initialize it...
                a_dict[k] = {}
                # ... and transfer over the section comments, if available
                try:
                    a_dict.comments[k] = b_dict.comments[k]
                except AttributeError:
                    pass
            conditional_merge(a_dict[k], b_dict[k])
        elif not k in a_dict:
            # It's a scalar. Transfer over the value...
            a_dict[k] = b_dict[k]
            # ... then its comments, if available:
            try:
                a_dict.comments[k] = b_dict.comments[k]
            except AttributeError:
                pass

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

# def prepend_path(a_dict, label, value):
#     """Prepend the value to every instance of the label in dict a_dict"""
#     for k in a_dict:
#         if isinstance(a_dict[k], dict):
#             prepend_path(a_dict[k], label, value)
#         elif k == label:
#             a_dict[k] = os.path.join(value, a_dict[k])

# def replace_string(a_dict, label, value):
#     for k in a_dict:
#         if isinstance(a_dict[k], dict):
#             replace_string(a_dict[k], label, value)
#         else:
#             a_dict[k] = a_dict[k].replace(label, value)

#==============================================================================
#                Utilities that work on drivers
#==============================================================================

def get_driver_infos(driver_dir='weewx.drivers'):
    """Scan the drivers folder, extracting information about each available driver.
    Return as a dictionary, keyed by driver name."""

    __import__(driver_dir)
    driver_package = sys.modules[driver_dir]
    driver_directory = os.path.dirname(os.path.abspath(driver_package.__file__))
    driver_list = [ os.path.basename(f) for f in glob.glob(os.path.join(driver_directory, "*.py"))]

    driver_info_dict = {}
    for driver_file in driver_list:
        if driver_file == '__init__.py':
            continue
        # Get the driver module name. This will be something like 'weewx.drivers.fousb'
        driver = os.path.splitext("weewx.drivers.%s" % driver_file)[0]
        # Create an entry for it
        driver_info_dict[driver] = dict()
        try:
            # Now import the driver, and extract info about it
            __import__(driver)
            driver_module = sys.modules[driver]
            driver_info_dict[driver]['name'] = driver_module.DRIVER_NAME
            driver_info_dict[driver]['version'] = driver_module.DRIVER_VERSION
            del driver_module
        except Exception, e:
            driver_info_dict[driver]['name'] = driver
            driver_info_dict[driver]['fail'] = str(e)

    return driver_info_dict

def load_driver_editor(driver):
    """Load the configuration editor from the driver file"""
    __import__(driver)
    driver_module = sys.modules[driver]
    loader_function = getattr(driver_module, 'confeditor_loader')
    editor = loader_function()
    return editor, driver_module.DRIVER_NAME, driver_module.DRIVER_VERSION

def print_drivers():
    """Get information about all the available drivers, then print it out."""
    driver_info_dict = get_driver_infos()
    keys = sorted(driver_info_dict)
    for d in keys:
        msg = "%-25s" % d
        for x in ['name', 'version', 'fail']:
            if x in driver_info_dict[d]:
                msg += " %-15s" % driver_info_dict[d][x]
        print msg

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
                    # Test whether the first token can be converted into a number.
                    # If not, an exception will be raised.
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

    return {'location' : loc,
            'altitude' : alt,
            'latitude' : lat,
            'longitude': lon,
            'units'    : uni}


def prompt_for_driver(dflt_driver=None):
    """Get the information about each driver, return as a dictionary."""
    infos = get_driver_infos()
    keys = sorted(infos)
    dflt_idx = None
    print "Installed drivers include:"
    for i, d in enumerate(keys):
        print " %2d) %-15s (%s)" % (i, infos[d].get('name', '?'), d)
        if dflt_driver == d:
            dflt_idx = i
    msg = "choose a driver [%d]: " % dflt_idx if dflt_idx is not None else "choose a driver: "
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
    """Let the driver prompt for any required settings."""
    settings = dict()
    __import__(driver)
    driver_module = sys.modules[driver]
    loader_function = getattr(driver_module, 'confeditor_loader')
    editor = loader_function()
    settings[driver_module.DRIVER_NAME] = editor.prompt_for_settings()
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

def extract_roots(config_path, config_dict):
    """Get the location of the various root directories used by weewx."""
    
    root_dict = {'WEEWX_ROOT' : config_dict['WEEWX_ROOT'],
                 'CONFIG_ROOT' : os.path.dirname(config_path),
                 'BIN_ROOT' : config_dict.get('BIN_ROOT')}
    # If there is no BIN_ROOT in the configuration dictionary, then set it
    # to the location of this file:
    if root_dict['BIN_ROOT'] is None:
        root_dict['BIN_ROOT'] = os.path.dirname(__file__)
    # The user subdirectory:
    root_dict['USER_ROOT'] = os.path.join(root_dict['BIN_ROOT'], 'user')
    # The extensions directory can be found off of USER_ROOT:
    root_dict['EXT_ROOT'] = os.path.join(root_dict['BIN_ROOT'], 'user', 'installer')
    # Add SKIN_ROOT if it can be found:
    try:
        root_dict['SKIN_ROOT'] = os.path.abspath(os.path.join(root_dict['WEEWX_ROOT'],
                                                              config_dict['StdReport']['SKIN_ROOT']))
    except KeyError:
        pass
    
    return root_dict

def extract_tarball(filename, target_dir, logger=None):
    """Extract a tarball into a given directory
    
    Returns: A list containing the member files
    """
    logger = logger or Logger()
    import tarfile
    logger.log("Extracting from tarball %s" % filename, level=1)
    tar_archive = tarfile.open(filename, mode='r')
    try:
        tar_archive.extractall(target_dir)
        member_names = [x.name for x in tar_archive.getmembers()]
        return member_names
    finally:
        tar_archive.close()
        
def get_extension_installer(extension_installer_dir):
    """Get the installer in the given extension installer subdirectory"""
    old_path = sys.path
    try:
        # Inject the location of the installer directory into the path
        sys.path.insert(0, extension_installer_dir)
        # Now I can import the extension's 'install' module:
        __import__('install')
        install_module = sys.modules['install']
        loader = getattr(install_module, 'loader')
        installer = loader()
    finally:
        # Restore the path
        sys.path = old_path
        # Get rid of the module:
        sys.modules.pop('install')

    return (install_module.__file__, installer)
