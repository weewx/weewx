#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities used by the setup and configure programs"""

import copy
import os
import time
import shutil
import sys
import StringIO

import configobj

class ConfigPathError(IOError):
    """Error in path to config file."""

minor_comment_block = [""]
major_comment_block = ["", "##############################################################################", ""]

def find_file(file_path=None, args=None, 
                locations=['/etc/weewx', '/home/weewx'], file_name='weewx.conf'):
    """Find and return a path to a file, looking in "the usual places."
    
    If the file cannot be found in file_path, then
    the command line arguments are searched. If it cannot be found
    there, then a list of path locations is searched. If it still
    cannot be found, then returns None. 

    file_path: A candidate path to the file.

    args: command-line arguments
    
    locations: A list of directories to be searched. 
    Default is ['etc/weewx', '/home/weewx'].

    file_name: The name of the file to be found. Default is 'weewx.conf'

    returns: path to the file
    """

    if file_path is None:
        if args and not args[0].startswith('-'):
            file_path = args[0]
            # Shift args to the left:
            del args[0]
    if file_path is None:
        for directory in locations:
            candidate = os.path.join(directory, file_name)
            if os.path.isfile(candidate):
                file_path = candidate
                break

    if file_path is None:
        raise ConfigPathError("Unable to find file '%s'. Tried directories %s" % (file_name, locations))
    elif not os.path.isfile(file_path):
        raise ConfigPathError("%s is not a file" % file_path)

    return file_path

def read_config(config_path, args=None, 
                locations=['/etc/weewx', '/home/weewx'], file_name='weewx.conf'):
    """Read the specified configuration file, return a dictionary of the
    file contents. If no file is specified, look in the standard locations
    for weewx.conf. Returns the filename of the actual configuration file
    as well as dictionary of the elements from the configuration file.

    config_path: configuration filename

    args: command-line arguments

    return: path-to-file, dictionary
    """
    try:
        # Find the config file:
        final_config_path = find_file(config_path, args, locations=locations, file_name=file_name)
    except IOError, e:
        print >>sys.stdout, e
        exit(1)

    try:        
        # Now open it up and parse it.
        config_dict = configobj.ConfigObj(final_config_path, file_error=True)
    except SyntaxError, e:
        print >>sys.stdout, "Syntax error in file '%s': %s" % (final_config_path, e)
        exit(1)

    return final_config_path, config_dict

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

def _as_string(option):
    if option is None: return None
    if hasattr(option, '__iter__'):
        return ', '.join(option)
    return option

def merge_config(config_dict, template_dict):
    """Merge the configuration dictionary into the template dictionary,
    overriding any options. Return the results.
    
    Raises exception of type ValueError if it cannot be done.
    
    config_dict: This is usually the existing, older configuration dictionary.
    
    template_dict: This is usually the newer dictionary supplied by the installer.
    It will be used as the starting point.
    """
    
    # Get the version number:
    old_version = config_dict.get('version')
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
        raise ValueError("Cannot merge version %s. Too old" % old_version)

    # First update to the latest v2
    config_dict = update_to_v27(config_dict)

    # Now update to V3.X
    config_dict = update_to_v3(config_dict)

    # Copy the template config file --- we will be modifying it.
    output_dict = copy.deepcopy(template_dict)
    output_dict.indent_type = '    '
    
    # Now merge the updated old configuration file into the template,
    # thus saving any user modifications.
    # First, turn interpolation off:
    output_dict.interpolation = False

    # Then do the merge
    output_dict.merge(config_dict)
    
    # Finally, update the version number:
    output_dict['version'] = template_dict['version']
    
    return output_dict

def update_to_v27(old_config_dict):
    """Updates a configuration file to the latest V2.X version.
    Since V2.7 was the last 2.X version, that's our target"""

    service_map_v2 = {'weewx.wxengine.StdTimeSynch' : 'prep_services', 
                      'weewx.wxengine.StdConvert'   : 'process_services', 
                      'weewx.wxengine.StdCalibrate' : 'process_services', 
                      'weewx.wxengine.StdQC'        : 'process_services', 
                      'weewx.wxengine.StdArchive'   : 'archive_services',
                      'weewx.wxengine.StdPrint'     : 'report_services', 
                      'weewx.wxengine.StdReport'    : 'report_services'}

    # Make a deep copy of the old config dictionary, then start modifying it:
    new_config_dict = copy.deepcopy(old_config_dict)

    # webpath is now station_url
    webpath = new_config_dict['Station'].get('webpath', None)
    station_url = new_config_dict['Station'].get('station_url', None)
    if webpath is not None and station_url is None:
        new_config_dict['Station']['station_url'] = webpath
    new_config_dict['Station'].pop('webpath', None)
    
    if 'StdArchive' in new_config_dict:
        # Option stats_types is no longer used. Get rid of it.
        new_config_dict['StdArchive'].pop('stats_types', None)
    
    # --- Davis Vantage series ---
    if 'Vantage' in new_config_dict:
        try:
            if new_config_dict['Vantage']['driver'].strip() == 'weewx.VantagePro':
                new_config_dict['Vantage']['driver'] = 'weewx.drivers.vantage'
        except KeyError:
            pass
    
    # --- Oregon Scientific WMR100 ---
    
    # The section name has changed from WMR-USB to WMR100
    if 'WMR-USB' in new_config_dict:
        if 'WMR100' in new_config_dict:
            sys.stderr.write("\n*** Configuration file has both a 'WMR-USB' section and a 'WMR100' section. Aborting ***\n\n")
            exit()
        new_config_dict.rename('WMR-USB', 'WMR100')
    # If necessary, reflect the section name in the station type:
    try:
        if new_config_dict['Station']['station_type'].strip() == 'WMR-USB':
            new_config_dict['Station']['station_type'] = 'WMR100'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if new_config_dict['WMR100']['driver'].strip() == 'weewx.wmrx':
            new_config_dict['WMR100']['driver'] = 'weewx.drivers.wmr100'
    except KeyError:
        pass
        
    # --- Oregon Scientific WMR9x8 series ---
    
    # The section name has changed from WMR-918 to WMR9x8
    if 'WMR-918' in new_config_dict:
        if 'WMR9x8' in new_config_dict:
            sys.stderr.write("\n*** Configuration file has both a 'WMR-918' section and a 'WMR9x8' section. Aborting ***\n\n")
            exit()
        new_config_dict.rename('WMR-918', 'WMR9x8')
    # If necessary, reflect the section name in the station type:
    try:
        if new_config_dict['Station']['station_type'].strip() == 'WMR-918':
            new_config_dict['Station']['station_type'] = 'WMR9x8'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if new_config_dict['WMR9x8']['driver'].strip() == 'weewx.WMR918':
            new_config_dict['WMR9x8']['driver'] = 'weewx.drivers.wmr9x8'
    except KeyError:
        pass
    
    # --- Fine Offset instruments ---

    try:
        if new_config_dict['FineOffsetUSB']['driver'].strip() == 'weewx.fousb':
            new_config_dict['FineOffsetUSB']['driver'] = 'weewx.drivers.fousb'
    except KeyError:
        pass

    #--- The weewx Simulator ---

    try:
        if new_config_dict['Simulator']['driver'].strip() == 'weewx.simulator':
            new_config_dict['Simulator']['driver'] = 'weewx.drivers.simulator'
    except KeyError:
        pass

    # See if the engine configuration section has the old-style "service_list":
    if 'Engines' in new_config_dict and 'service_list' in new_config_dict['Engines']['WxEngine']:
        # It does. Break it up into five, smaller lists. If a service
        # does not appear in the dictionary "service_map_v2", meaning we
        # do not know what it is, then stick it in the last group we
        # have seen. This should get its position about right.
        last_group = 'prep_services'
        
        # Set up a bunch of empty groups in the right order
        for group in ['prep_services', 'process_services', 'archive_services', 
                      'restful_services', 'report_services']:
            new_config_dict['Engines']['WxEngine'][group] = list()

        # Now map the old service names to the right group
        for _svc_name in new_config_dict['Engines']['WxEngine']['service_list']:
            svc_name = _svc_name.strip()
            # Skip the no longer needed StdRESTful service:
            if svc_name == 'weewx.wxengine.StdRESTful':
                continue
            # Do we know about this service?
            if svc_name in service_map_v2:
                # Yes. Get which group it belongs to, and put it there
                group = service_map_v2[svc_name]
                new_config_dict['Engines']['WxEngine'][group].append(svc_name)
                last_group = group
            else:
                # No. Put it in the last group.
                new_config_dict['Engines']['WxEngine'][last_group].append(svc_name)

        # Now add the restful services, using the old driver name to help us
        for section in new_config_dict['StdRESTful'].sections:
            svc = new_config_dict['StdRESTful'][section]['driver']
            # weewx.restful has changed to weewx.restx
            if svc.startswith('weewx.restful'):
                svc = 'weewx.restx.Std' + section
            # awekas is in weewx.restx since 2.6
            if svc.endswith('AWEKAS'):
                svc = 'weewx.restx.AWEKAS'
            new_config_dict['Engines']['WxEngine']['restful_services'].append(svc)

        # Depending on how old a version the user has, the station registry
        # may have to be included:
        if 'weewx.restx.StdStationRegistry' not in new_config_dict['Engines']['WxEngine']['restful_services']:
            new_config_dict['Engines']['WxEngine']['restful_services'].append('weewx.restx.StdStationRegistry')
        
        # Get rid of the no longer needed service_list:
        new_config_dict['Engines']['WxEngine'].pop('service_list')

    # Clean up the CWOP configuration
    if 'StdRESTful' in new_config_dict and 'CWOP' in new_config_dict['StdRESTful']:
        # Option "interval" has changed to "post_interval"
        if 'interval' in new_config_dict['StdRESTful']['CWOP']:
            new_config_dict['StdRESTful']['CWOP']['post_interval'] = new_config_dict['StdRESTful']['CWOP']['interval']
            new_config_dict['StdRESTful']['CWOP'].pop('interval')
        # Option "server" has become "server_list". It is also no longer
        # included in the default weewx.conf, so just pop it.
        if 'server' in new_config_dict['StdRESTful']['CWOP']:
            new_config_dict['StdRESTful']['CWOP'].pop('server')

    # Remove the no longer needed "driver" from all the RESTful services:
    if 'StdRESTful' in new_config_dict:
        for section in new_config_dict['StdRESTful'].sections:
            new_config_dict['StdRESTful'][section].pop('driver', None)

    return new_config_dict

def update_to_v3(old_config_dict):
    """Update a configuration file to V3.X"""
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
    
    # Make a deep copy of the old config dictionary, then start modifying it:
    new_config_dict = copy.deepcopy(old_config_dict)

    if 'Databases' in new_config_dict:
        # The stats database no longer exists. Remove it from the [Databases]
        # section:
        new_config_dict['Databases'].pop('stats_sqlite', None)
        new_config_dict['Databases'].pop('stats_mysql', None)
        # The key "database" changed to "database_name"
        for stanza in new_config_dict['Databases']:
            if 'database' in new_config_dict['Databases'][stanza]:
                new_config_dict['Databases'][stanza].rename('database', 'database_name')
        
    if 'StdReport' in new_config_dict:
        # The key "data_binding" is now used instead of these:
        new_config_dict['StdReport'].pop('archive_database', None)
        new_config_dict['StdReport'].pop('stats_database', None)
        
    if 'StdArchive' in new_config_dict:
        old_database = new_config_dict['StdArchive'].pop('archive_database', None)
        new_config_dict['StdArchive'].pop('stats_database', None)
        new_config_dict['StdArchive'].pop('archive_schema', None)
        new_config_dict['StdArchive'].pop('stats_schema', None)
        
    # Section ['Engines'] got renamed to ['Engine']
    if 'Engine' not in new_config_dict and 'Engines' in new_config_dict:
        new_config_dict.rename('Engines', 'Engine')
        # Subsection [['WxEngine']] got renamed to [['Services']]
        if 'WxEngine' in new_config_dict['Engine']:
            new_config_dict['Engine'].rename('WxEngine', 'Services')

            # Finally, module "wxengine" got renamed to "engine". Go through
            # each of the service lists, making the change
            for list_name in new_config_dict['Engine']['Services']:
                service_list = new_config_dict['Engine']['Services'][list_name]
                # If service_list is not already a list (it could be just a single name),
                # then make it a list:
                if not hasattr(service_list, '__iter__'):
                    service_list = [service_list]
                new_config_dict['Engine']['Services'][list_name] = [this_item.replace('wxengine', 'engine') for this_item in service_list]
        try:
            # Finally, make sure the new StdWXCalculate service is in the list:
            if 'weewx.wxservices.StdWXCalculate' not in new_config_dict['Engine']['Services']['process_services']:
                new_config_dict['Engine']['Services']['process_services'].append('weewx.wxservices.StdWXCalculate')
        except KeyError:
            pass
        
    if 'DataBindings' not in new_config_dict:
        # Insert a [DataBindings] section. First create it
        c = configobj.ConfigObj(StringIO.StringIO(v3_additions))
        # Now merge it in:
        new_config_dict.merge(c)
        # For some reason, ConfigObj strips any leading comments. Add them back in:
        new_config_dict.comments['DataBindings'] = major_comment_block 
        # Move the new section to just before [Databases]
        reorder_sections(new_config_dict, 'DataBindings', 'Databases')
        # No comments between the [DataBindings] and [Databases] sections:
        new_config_dict.comments['Databases'] = [""]

        # If there was an old database, add it in the new, correct spot:
        if old_database:
            try:
                new_config_dict['DataBindings']['wx_binding']['database'] = old_database
            except KeyError:
                pass

    return new_config_dict

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

def reorder_sections(config_dict, src, dst):
    """Move the section with key src to just before the
    section with key dst.
    
    Example:
    >>> config_dict = configobj.ConfigObj({'a':1, 'b':2, 'c':3, 'd':4})
    >>> reorder_sections(config_dict, 'c', 'b')
    >>> print config_dict
    {'a': 1, 'c': 3, 'b': 2, 'd': 4}
    """
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
    config_dict.sections = config_dict.sections[:dst_idx] + [src] + config_dict.sections[dst_idx:]

def conditional_merge(a_dict, b_dict):
    """Merge fields from b_dict into a_dict, but only if they do not yet exist in a_dict
    
    Example:
    >>> # Use StringIOs to keep the ordering:
    >>> a_dict = configobj.ConfigObj(StringIO.StringIO("a=1\\nb=2\\nc=3\\nd=4\\n"))
    >>> b_dict = configobj.ConfigObj(StringIO.StringIO("a=11\\nb=12\\ne=15\\n"))
    >>> conditional_merge(a_dict, b_dict)
    >>> print a_dict
    {'a': '1', 'b': '2', 'c': '3', 'd': '4', 'e': '15'}
    """
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if not k in a_dict:
                a_dict[k] = {}
            conditional_merge(a_dict[k], b_dict[k])
        elif not k in a_dict:
            a_dict[k] = b_dict[k]

def remove_and_prune(a_dict, b_dict):
    """Remove fields from a that are present in b
    Example:
    >>> a_dict = configobj.ConfigObj({'a':1, 'b':2, 'c':3, 'd':4})
    >>> b_dict = configobj.ConfigObj({'a':11, 'b':12, 'e':1})
    >>> remove_and_prune(a_dict, b_dict)
    >>> print a_dict
    {'c': 3, 'd': 4}
    """
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if k in a_dict and type(a_dict[k]) is configobj.Section:
                remove_and_prune(a_dict[k], b_dict[k])
                if not a_dict[k].sections:
                    a_dict.pop(k)
        elif k in a_dict:
            a_dict.pop(k)

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

# def move_section_up(config, before):
#     """Moves the last section in a ConfigObj so it is just before
#     the given section"""
#     
#     # Find the given section:
#     loc = config.sections.index(before)
#     # Now move the last section so it sits just before it.
#     # Get a shorthand name to reduce the typing involved:
#     s = config.sections
#     config.sections = s[:loc] + s[-1:] + s[loc:-1]
if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print("PASSED")
