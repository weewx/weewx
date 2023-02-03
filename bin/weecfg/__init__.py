# coding: utf-8
#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Utilities used by the setup and configure programs"""

import errno
import importlib
import os.path
import pkgutil
import shutil
import sys
import tempfile

import configobj

import weeutil.config
import weeutil.weeutil
from weeutil.weeutil import bcolors

major_comment_block = ["",
                       "#######################################"
                       "#######################################",
                       ""]

default_weewx_root = os.path.expanduser('~/weewx-data')
default_config_path = os.path.join(default_weewx_root, 'weewx.conf')


class ExtensionError(IOError):
    """Errors when installing or uninstalling an extension"""


class Logger(object):
    def __init__(self, verbosity=0):
        self.verbosity = verbosity

    def log(self, msg, level=0):
        if self.verbosity >= level:
            print("%s%s" % ('  ' * (level - 1), msg))

    def set_verbosity(self, verbosity):
        self.verbosity = verbosity


# ==============================================================================
#              Utilities that find and save ConfigObj objects
# ==============================================================================

if sys.platform == "darwin":
    DEFAULT_LOCATIONS = [default_weewx_root, '/etc/weewx', '/Users/Shared/weewx']
else:
    DEFAULT_LOCATIONS = [default_weewx_root, '/etc/weewx', '/home/weewx']


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

    Args:
        file_path (str): A candidate path to the file.
        args (list[str]): command-line arguments. If the file cannot be found in file_path,
            then the members of args will be tried.
        locations (list[str]): A list of directories to be searched. If they do not
            start with a slash ('/'), then they will be treated as relative to
            this file (bin/weecfg/__init__.py).
            Default is ['../..', '/etc/weewx', '/home/weewx'].
        file_name (str): The name of the file to be found. This is used
            only if the directories must be searched. Default is 'weewx.conf'.

    Returns:
        str: full path to the file

    Raises:
        IOError: If the configuration file cannot be found, or is not a file.
    """

    # Start by searching args (if available)
    if file_path is None and args:
        for i in range(len(args)):
            # Ignore empty strings and None values:
            if not args[i]:
                continue
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
        raise IOError("Unable to find file '%s'. Tried directories %s"
                      % (file_name, locations))
    elif not os.path.isfile(file_path):
        raise IOError("%s is not a file" % file_path)

    return file_path


def read_config(config_path, args=None, locations=DEFAULT_LOCATIONS,
                file_name='weewx.conf', interpolation='ConfigParser'):
    """Read the specified configuration file, return an instance of ConfigObj
    with the file contents. If no file is specified, look in the standard
    locations for weewx.conf. Returns the filename of the actual configuration
    file, as well as the ConfigObj.

    Args:

        config_path (str): configuration filename.
        args (list[str]): command-line arguments.
        locations (list[str]): A list of directories to search.
        file_name (str): The name of the config file. Default is 'weewx.conf'
        interpolation (str): The type of interpolation to use when reading the config file.
            Default is 'ConfigParser'. See the ConfigObj documentation https://bit.ly/3L593vH

    Returns:
        (str, configobj.ConfigObj): path-to-file, instance-of-ConfigObj

    Raises:
        SyntaxError: If there is a syntax error in the file
        IOError: If the file cannot be found
    """
    # Find and open the config file:
    config_path = find_file(config_path, args,
                            locations=locations, file_name=file_name)
    try:
        # Now open it up and parse it.
        config_dict = configobj.ConfigObj(config_path,
                                          interpolation=interpolation,
                                          file_error=True,
                                          encoding='utf-8',
                                          default_encoding='utf-8')
    except configobj.ConfigObjError as e:
        # Add on the path of the offending file, then reraise.
        e.msg += " File '%s'." % config_path
        raise

    # Remember where we found the config file
    config_dict['config_path'] = os.path.realpath(config_path)

    return config_path, config_dict


def save_with_backup(config_dict, config_path):
    return save(config_dict, config_path, backup=True)


def save(config_dict, config_path, backup=False):
    """Save the config file, backing up as necessary.

    Args:
        config_dict(dict): A configuration dictionary.
        config_path(str): Path to where the dictionary should be saved.
        backup(bool): True to save a timestamped version of the old config file, False otherwise.
    Returns:
        str|None: The path to the backed up old config file. None otherwise
    """

    # We need to pop 'config_path' off the dictionary before writing. WeeWX v4.9.1 wrote
    # 'entry_path' to the config file as well, so we need to get rid of that in case it snuck in.
    # Make a deep copy first --- we're going to be modifying the dictionary.
    write_dict = weeutil.config.deep_copy(config_dict)
    write_dict.pop('config_path', None)
    write_dict.pop('entry_path', None)

    # Check to see if the file exists, and we are supposed to make backup:
    if os.path.exists(config_path) and backup:

        # Yes. We'll have to back it up.
        backup_path = weeutil.weeutil.move_with_timestamp(config_path)

        # Now we can save the file. Get a temporary file:
        with tempfile.NamedTemporaryFile() as tmpfile:
            # Write the configuration dictionary to it:
            write_dict.write(tmpfile)
            tmpfile.flush()

            # Now move the temporary file into the proper place:
            shutil.copyfile(tmpfile.name, config_path)

    else:

        # No existing file or no backup required. Just write.
        with open(config_path, 'wb') as fd:
            write_dict.write(fd)
        backup_path = None

    return backup_path


def inject_station_url(config_dict, url):
    """Inject the option station_url into the [Station] section"""

    if 'station_url' in config_dict['Station']:
        # Already injected. Just set the value
        config_dict['Station']['station_url'] = url
        return

    # Isolate just the [Station] section. This simplifies what follows
    station_dict = config_dict['Station']

    # In the configuration file that ships with WeeWX, station_url is commented out, so its
    # comments are part of the following option, which is 'rain_year_start'. So, just set
    # the comments for 'rain_year_start' to something sensible, which will make the 'station_url'
    # comment go away.
    station_dict.comments['rain_year_start'] = [
        "",
        "The start of the rain year (1=January; 10=October, etc.). This is",
        "downloaded from the station if the hardware supports it."
    ]

    # Add the new station_url, plus its comments
    station_dict['station_url'] = url
    station_dict.comments['station_url'] \
        = ['', 'If you have a website, you may specify an URL']

    # Reorder to match the canonical ordering.
    reorder_scalars(station_dict.scalars, 'station_url', 'rain_year_start')


# ==============================================================================
#              Utilities that extract from ConfigObj objects
# ==============================================================================

def get_version_info(config_dict):
    # Get the version number. If it does not appear at all, then
    # assume a very old version:
    config_version = config_dict.get('version') or '1.0.0'

    # Updates only care about the major and minor numbers
    parts = config_version.split('.')
    major = parts[0]
    minor = parts[1]

    # Take care of the collation problem when comparing things like
    # version '1.9' to '1.10' by prepending a '0' to the former:
    if len(minor) < 2:
        minor = '0' + minor

    return major, minor


# ==============================================================================
#                Utilities that manipulate ConfigObj objects
# ==============================================================================

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
    # Save the key
    src_key = config_dict.sections[src_idx]
    # Remove it
    config_dict.sections.pop(src_idx)
    # Find the destination
    dst_idx = config_dict.sections.index(dst)
    # Now reorder the attribute 'sections', putting src just before dst:
    config_dict.sections = config_dict.sections[:dst_idx + bump] + [src_key] + \
                           config_dict.sections[dst_idx + bump:]


def reorder_scalars(scalars, src, dst):
    """Reorder so the src item is just before the dst item"""
    try:
        src_index = scalars.index(src)
    except ValueError:
        return
    scalars.pop(src_index)
    # If the destination cannot be found, but the src object at the end
    try:
        dst_index = scalars.index(dst)
    except ValueError:
        dst_index = len(scalars)

    scalars.insert(dst_index, src)


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


# ==============================================================================
#                Utilities that work on drivers
# ==============================================================================


def get_all_driver_infos():
    # first look in the drivers directory
    infos = get_driver_infos()
    # then add any drivers in the user directory
    user_drivers = get_driver_infos('user')
    infos.update(user_drivers)
    return infos


def get_driver_infos(driver_pkg_name='weewx.drivers'):
    """Scan the driver's folder, extracting information about each available
    driver. Return as a dictionary, keyed by the driver module name.

    Valid drivers must be importable, and must have attribute "DRIVER_NAME"
    defined.

    Args:
        driver_pkg_name (str): The name of the package holder the drivers.
            Default is 'weewx.drivers'

    Returns
        dict: The key is the driver module name, value is information about the driver.
            Typical entry:
            'weewx.drivers.acurite': {'module_name': 'weewx.drivers.acurite',
                                      'driver_name': 'AcuRite',
                                      'version': '0.4',
                                      'status': ''}

    """
    driver_info_dict = {}
    # Import the package, so we can find the modules contained within it. It's possible we are
    # trying to import the not-yet-created 'user' subdirectory, which would cause a
    # ModuleNotFoundError. Be prepared to catch it.
    try:
        driver_pkg = importlib.import_module(driver_pkg_name)
    except ModuleNotFoundError:
        return driver_info_dict

    # This guards against namespace packages.
    if not driver_pkg or not driver_pkg.__file__:
        return {}

    driver_path = os.path.dirname(driver_pkg.__file__)

    # Iterate over all the modules in the package.
    for driver_module_info in pkgutil.iter_modules([driver_path]):
        # Form the importable name of the module. This will be something
        # like 'weewx.drivers.acurite'
        driver_module_name = f"{driver_pkg_name}.{driver_module_info.name}"

        # Try importing the module. Be prepared for an exception if the import fails.
        try:
            driver_module = importlib.import_module(driver_module_name)
        except (SyntaxError, ImportError) as e:
            # If the import fails, report it in the status
            driver_info_dict[driver_module_name] = {
                'module_name': driver_module_name,
                'driver_name': '?',
                'version': '?',
                'status': e}
        else:
            # The import succeeded.
            # A valid driver will define the attribute "DRIVER_NAME"
            if hasattr(driver_module, 'DRIVER_NAME'):
                # A driver might define the attribute DRIVER_VERSION
                driver_module_version = getattr(driver_module, 'DRIVER_VERSION', '?')
                # Create an entry for it, keyed by the driver module name
                driver_info_dict[driver_module_name] = {
                    'module_name': driver_module_name,
                    'driver_name': driver_module.DRIVER_NAME,
                    'version': driver_module_version,
                    'status': ''}

    return driver_info_dict


def print_drivers():
    """Get information about all the available drivers, then print it out."""
    driver_info_dict = get_all_driver_infos()
    keys = sorted(driver_info_dict)
    print("%-25s%-15s%-9s%-25s" % ("Module name", "Driver name", "Version", "Status"))
    for d in keys:
        print("  %(module_name)-25s%(driver_name)-15s%(version)-9s%(status)-25s"
              % driver_info_dict[d])


def load_driver_editor(driver_module_name):
    """Load the configuration editor from the driver file

    Args:
        driver_module_name (str): A string holding the driver name, for
            example, 'weewx.drivers.fousb'

    Returns:
        tuple: A 3-way tuple: (editor, driver_name, driver_version)
    """
    driver_module = importlib.import_module(driver_module_name)
    editor = None
    if hasattr(driver_module, 'confeditor_loader'):
        # Retrieve the loader function
        loader_function = getattr(driver_module, 'confeditor_loader')
        # Call it to get the actual editor
        editor = loader_function()
    driver_name = getattr(driver_module, 'DRIVER_NAME', None)
    driver_version = getattr(driver_module, 'DRIVER_VERSION', 'undefined')
    return editor, driver_name, driver_version


# ==============================================================================
#                Utilities that seek info from the command line
# ==============================================================================


def prompt_for_driver(dflt_driver=None):
    """Get the information about each driver, return as a dictionary.

    Args:
        dflt_driver (str): The default driver to offer. If not given, 'weewx.drivers.simulator'
            will be used

    Returns:
        str: The selected driver. This will be something like 'weewx.drivers.vantage'.
    """

    if dflt_driver is None:
        dflt_driver = 'weewx.drivers.simulator'
    infos = get_all_driver_infos()
    keys = sorted(infos)
    dflt_idx = None
    print("\nInstalled drivers include:")
    for i, d in enumerate(keys):
        print(" %s%2d%s) %-15s %-25s %s" % (bcolors.BOLD, i, bcolors.ENDC,
                                            infos[d].get('driver_name', '?'),
                                            "(%s)" % d, infos[d].get('status', '')))
        if dflt_driver == d:
            dflt_idx = i
    if dflt_idx is None:
        msg = "choose a driver: "
    else:
        msg = f"choose a driver [{dflt_idx:d}]: "
    idx = 0
    ans = None
    while ans is None:
        ans = input(msg).strip()
        if not ans:
            ans = dflt_idx
        try:
            idx = int(ans)
            if not 0 <= idx < len(keys):
                ans = None
        except (ValueError, TypeError):
            ans = None
    return keys[idx]


def prompt_for_driver_settings(driver, stanza_dict):
    """Let the driver prompt for any required settings.  If the driver does
    not define a method for prompting, return an empty dictionary."""
    settings = configobj.ConfigObj(interpolation=False)
    try:
        driver_module = importlib.import_module(driver)
        loader_function = getattr(driver_module, 'confeditor_loader')
        editor = loader_function()
        editor.existing_options = stanza_dict
        settings = editor.prompt_for_settings()
    except AttributeError:
        pass
    return settings


def get_languages(skin_dir):
    """ Return all languages supported by the skin

    Args:
        skin_dir (str): The path to the skin subdirectory.

    Returns:
        dict|None: A dictionary where the key is the language code, and the value is the natural
            language name of the language. The value 'None' is returned if skin_dir does not exist.
    """
    # Get the path to the "./lang" subdirectory
    lang_dir = os.path.join(skin_dir, './lang')
    # Get all the files in the subdirectory. If the subdirectory does not exist, an exception
    # will be raised. Be prepared to catch it.
    try:
        lang_files = os.listdir(lang_dir)
    except OSError:
        # No 'lang' subdirectory. Return None
        return None

    languages = {}

    # Go through the files...
    for lang_file in lang_files:
        # ... get its full path ...
        lang_full_path = os.path.join(lang_dir, lang_file)
        # ... make sure it's a file ...
        if os.path.isfile(lang_full_path):
            # ... then get the language code for that file.
            code = lang_file.split('.')[0]
            # Retrieve the ConfigObj for this language
            lang_dict = configobj.ConfigObj(lang_full_path, encoding='utf-8')
            # See if it has a natural language version of the language code:
            try:
                language = lang_dict['Texts']['Language']
            except KeyError:
                # It doesn't. Just label it 'Unknown'
                language = 'Unknown'
            # Add the code, plus the language
            languages[code] = language
    return languages


def pick_language(languages, default='en'):
    """
    Given a choice of languages, pick one.

    Args:
        languages (dict): As returned by function get_languages() above
        default (str): The language code of the default

    Returns:
        str: The chosen language code
    """
    keys = sorted(languages.keys())
    if default not in keys:
        default = None
    msg = "Available languages\nCode  | Language\n"
    for code in keys:
        msg += "%4s  | %-20s\n" % (code, languages[code])
    msg += "Pick a code"
    value = prompt_with_options(msg, default, keys)

    return value


def prompt_with_options(prompt, default=None, options=None):
    """Ask the user for an input with an optional default value.

    Args:
        prompt(str): A string to be used for a prompt.
        default(str|None): A default value. If the user simply hits <enter>, this
            is the value returned. Optional.
        options(list[str]|None): A list of possible choices. The returned value must be in
            this list. Optional.

    Returns:
        str: The chosen option
    """

    msg = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "
    value = None
    while value is None:
        value = input(msg).strip()
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
        value = input(msg).strip()
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


# ==============================================================================
#            Miscellaneous utilities
# ==============================================================================

def extract_roots(config_dict):
    """Get the location of the various root directories used by weewx.
    The extracted paths are *absolute* paths. That is, they are no longer relative to WEEWX_ROOT.
    """
    root_dict = dict()
    root_dict['WEEWX_ROOT'] = config_dict['WEEWX_ROOT']
    root_dict['USER_DIR'] = os.path.join(config_dict['WEEWX_ROOT'],
                                         config_dict.get('USER_ROOT', 'bin/user'))
    root_dict['BIN_DIR'] = os.path.abspath(os.path.join(root_dict['USER_DIR'], '..'))
    root_dict['EXT_DIR'] = os.path.join(root_dict['USER_DIR'], 'installer')

    # Add SKIN_ROOT if it can be found:
    try:
        root_dict['SKIN_DIR'] = os.path.abspath(os.path.join(
            root_dict['WEEWX_ROOT'],
            config_dict['StdReport']['SKIN_ROOT']))
    except KeyError:
        pass

    return root_dict


def extract_tar(filename, target_dir, logger=None):
    """Extract files from a tar archive into a given directory

    Args:
        filename (str): Path to the tarfile
        target_dir (str): Path to the directory to which the contents will be extracted
        logger (weecfg.Logger): Logger to use

    Returns:
        list[str]: A list of the extracted files
    """
    import tarfile
    logger = logger or Logger()
    logger.log(f"Extracting from tar archive {filename}", level=1)

    with tarfile.open(filename, mode='r') as tar_archive:
        member_names = [os.path.normpath(x.name) for x in tar_archive.getmembers()]
        tar_archive.extractall(target_dir)

    del tarfile
    return member_names


def extract_zip(filename, target_dir, logger=None):
    """Extract files from a zip archive into the specified directory.

    Args:
        filename (str): Path to the zip file
        target_dir (str): Path to the directory to which the contents will be extracted
        logger (weecfg.Logger): Logger to use

    Returns:
        list[str]: A list of the extracted files
    """
    import zipfile
    logger = logger or Logger()
    logger.log(f"Extracting from zip archive {filename}", level=1)

    with zipfile.ZipFile(filename) as zip_archive:
        member_names = zip_archive.namelist()
        zip_archive.extractall(target_dir)

    del zipfile
    return member_names


def mkdir_p(path):
    """equivalent to 'mkdir -p'"""
    try:
        os.makedirs(path)
    except OSError as e:
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

    return install_module.__file__, installer
