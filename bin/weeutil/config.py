#
#    Copyright (c) 2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id$
#

"""Utilities used by the setup and configure programs"""

import os
import time
import shutil
import syslog
import sys

import configobj

class ConfigPathError(IOError):
    """Error in path to config file."""

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
        raise ConfigPathError("Unable to find %s" % file_name)
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


