#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Install or reconfigure a configuration file"""

import getpass
import grp
import importlib
import importlib.resources
import logging
import os
import os.path
import re
import shutil
import sys

import configobj

import weecfg.update_config
import weeutil.config
import weeutil.weeutil
import weewx
from weeutil.weeutil import to_float, to_bool, bcolors

log = logging.getLogger(__name__)


def station_create(config_path, *args,
                   docs_root=None,
                   examples_root=None,
                   user_root=None,
                   dry_run=False,
                   **kwargs):
    """Create a brand-new station by creating a new configuration file.

    WEEWX_ROOT is defined as the directory the resultant configuration file is in.

    This function first checks whether the configuration file already exists. If it does, then
    an exception is raised.

    It then:
      1. If no_prompt is false, it creates the configuration file by prompting the user. If true,
       it uses defaults.
      2. It then copies the documentation out of package resources and into WEEWX_ROOT.
      3. Same with the examples and utility files.
    """

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    if not config_path:
        config_path = weecfg.default_config_path

    weewx_root = os.path.dirname(config_path)

    # Make sure there is not already a configuration file at the designated location.
    if os.path.exists(config_path):
        raise weewx.ViolatedPrecondition(f"Config file {config_path} already exists")

    print(f"The configuration file will be created "
          f"at {bcolors.BOLD}{config_path}{bcolors.ENDC}.")

    # Retrieve the configuration file as a ConfigObj
    with importlib.resources.open_text('wee_resources', 'weewx.conf', encoding='utf-8') as fd:
        dist_config_dict = configobj.ConfigObj(fd, encoding='utf-8', file_error=True)

    config_config(config_path, dist_config_dict, weewx_root=weewx_root, dry_run=dry_run,
                  *args, **kwargs)
    copy_docs(dist_config_dict, docs_root=docs_root, dry_run=dry_run)
    copy_examples(dist_config_dict, examples_root=examples_root, dry_run=dry_run)
    copy_user(dist_config_dict, user_root=user_root, dry_run=dry_run)

    print(f"Save the configuration file to {config_path}.")
    if dry_run:
        print("This was a dry run. Nothing was actually done.")
    else:
        # Save the results. No backup.
        weecfg.save(dist_config_dict, config_path)


def station_reconfigure(config_path, dry_run=False, *args, **kwargs):
    "Reconfigure an existing station"

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    config_config(config_path, config_dict, dry_run=dry_run, *args, **kwargs)

    print(f"Save the configuration file to {config_path}.")
    if dry_run:
        print("This was a dry run. Nothing was actually done.")
    else:
        # Save the results with backup
        backup = weecfg.save_with_backup(config_dict, config_path)
        print(f"Saved backup to {backup}.")


def config_config(config_path, config_dict,
                  driver=None, location=None,
                  altitude=None, latitude=None, longitude=None,
                  register=None, unit_system=None,
                  weewx_root=None, skin_root=None,
                  html_root=None, sqlite_root=None,
                  user_root=None,
                  no_prompt=False,
                  dry_run=False):
    """Modify a configuration file."""
    print(f"Processing configuration file {config_path}.")
    weewx.add_user_path(config_dict)
    config_location(config_dict, location=location, no_prompt=no_prompt)
    config_altitude(config_dict, altitude=altitude, no_prompt=no_prompt)
    config_latlon(config_dict, latitude=latitude, longitude=longitude, no_prompt=no_prompt)
    config_registry(config_dict, register=register, no_prompt=no_prompt)
    config_units(config_dict, unit_system=unit_system, no_prompt=no_prompt)
    config_driver(config_dict, driver=driver, no_prompt=no_prompt)
    config_roots(config_dict, weewx_root, skin_root, html_root, sqlite_root, user_root)
    copy_skins(config_dict, dry_run=dry_run)
    copy_util(config_path, config_dict, dry_run=dry_run)


def config_location(config_dict, location=None, no_prompt=False):
    """Set the location option. """
    if 'Station' not in config_dict:
        return

    default_location = config_dict['Station'].get('location', "WeeWX station")

    if location is not None:
        final_location = location
    elif not no_prompt:
        print("\nGive a description of your station. This will be used for the title "
              "of any reports.")
        ans = input(f"Description [{default_location}]: ").strip()
        final_location = ans if ans else default_location
    else:
        final_location = default_location
    config_dict['Station']['location'] = final_location


def config_altitude(config_dict, altitude=None, no_prompt=False):
    """Set a (possibly new) value and unit for altitude.

    Args:
        config_dict (configobj.ConfigObj): The configuration dictionary.
        altitude (str): A string with value and unit, separated with a comma.
            For example, "50, meter". Optional.
        no_prompt(bool):  Do not prompt the user for a value.
    """
    if 'Station' not in config_dict:
        return

    # Start with assuming the existing value:
    default_altitude = config_dict['Station'].get('altitude', ["0", 'foot'])
    # Was a new value provided as an argument?
    if altitude is not None:
        # Yes. Extract and validate it.
        value, unit = altitude.split(',')
        # Fail hard if the value cannot be converted to a float
        float(value)
        # Fail hard if the unit is unknown:
        unit = unit.strip().lower()
        if unit not in ['foot', 'meter']:
            raise ValueError(f"Unknown altitude unit {unit}")
        # All is good. Use it.
        final_altitude = [value, unit]
    elif not no_prompt:
        print("\nSpecify altitude, with units 'foot' or 'meter'.  For example:")
        print("35, foot")
        print("12, meter")
        msg = "altitude [%s]: " % weeutil.weeutil.list_as_string(default_altitude)
        final_altitude = None

        while final_altitude is None:
            ans = input(msg).strip()
            if ans:
                try:
                    value, unit = ans.split(',')
                except ValueError:
                    print("You must specify a value and unit. For example: 200, meter")
                    continue
                try:
                    # Test whether the first token can be converted into a
                    # number. If not, an exception will be raised.
                    float(value)
                    unit = unit.strip().lower()
                    if unit in ['foot', 'meter']:
                        final_altitude = [value.strip(), unit]
                except (ValueError, TypeError):
                    pass
            else:
                # The user gave the null string. We're done
                final_altitude = default_altitude
    else:
        # If we got here, there was no value in the args and we cannot prompt. Use the default.
        final_altitude = default_altitude

    config_dict['Station']['altitude'] = final_altitude


def config_latlon(config_dict, latitude=None, longitude=None, no_prompt=False):
    """Set a (possibly new) value for latitude and longitude

    Args:
        config_dict (configobj.ConfigObj): The configuration dictionary.
        latitude (str|None): The latitude. If specified, no prompting will happen.
        longitude (str|None): The longitude. If specified no prompting will happen.
        no_prompt(bool):  Do not prompt the user for a value.
    """

    if "Station" not in config_dict:
        return

    # Use the existing value, if any, as the default:
    default_latitude = to_float(config_dict['Station'].get('latitude', 0.0))
    # Was a new value provided as an argument?
    if latitude is not None:
        # Yes. Use it
        final_latitude = latitude
    elif not no_prompt:
        # No value provided as an argument. Prompt for a new value
        print("\nSpecify latitude in decimal degrees, negative for south.")
        final_latitude = weecfg.prompt_with_limits("latitude", default_latitude, -90, 90)
    else:
        # If we got here, there was no value provided as an argument, yet we cannot prompt.
        # Use the default.
        final_latitude = default_latitude

    # Make sure we have something that can convert to a float:
    float(final_latitude)

    # Set the value in the config file
    config_dict['Station']['latitude'] = final_latitude

    # Similar, except for longitude
    default_longitude = to_float(config_dict['Station'].get('longitude', 0.0))
    # Was a new value provided on the command line?
    if longitude is not None:
        # Yes. Use it
        final_longitude = longitude
    elif not no_prompt:
        # No command line value. Prompt for a new value
        print("Specify longitude in decimal degrees, negative for west.")
        final_longitude = weecfg.prompt_with_limits("longitude", default_longitude, -180, 180)
    else:
        # If we got here, there was no value provided as an argument, yet we cannot prompt.
        # Use the default.
        final_longitude = default_longitude

    # Make sure we have something that can convert to a float:
    float(final_longitude)

    # Set the value in the config file
    config_dict['Station']['longitude'] = final_longitude


def config_registry(config_dict, register=None, station_url=None, no_prompt=False):
    """Configure whether to include the station in the weewx.com registry."""

    if 'Station' not in config_dict:
        return

    try:
        default_register = to_bool(
            config_dict['StdRESTful']['StationRegistry']['register_this_station'])
    except KeyError:
        default_register = False

    default_station_url = config_dict['Station'].get('station_url')

    if register is not None:
        final_register = to_bool(register)
        final_station_url = station_url or default_station_url
    elif not no_prompt:
        print("\nYou can register your station on weewx.com, where it will be included")
        print("in a map. If you choose to do so, you will also need a unique URL to identify ")
        print("your station (such as a website, or a WeatherUnderground link).")
        ans = weeutil.weeutil.y_or_n("Include station in the station registry [n]? ",
                                     default=default_register)
        final_register = to_bool(ans)
        if final_register:
            while True:
                print("\nNow give a unique URL for your station. A Weather Underground ")
                print("URL such as https://www.wunderground.com/dashboard/pws/KORPORT12 will do.")
                url = weecfg.prompt_with_options("Unique URL", default_station_url)
                if url:
                    if 'example.com' in url:
                        print("Unique please!")
                    else:
                        final_station_url = url
                        break
    else:
        final_register = default_register
        final_station_url = default_station_url

    if final_register and not final_station_url:
        raise weewx.ViolatedPrecondition("Registering the station requires "
                                         "option 'station_url'.")

    config_dict['StdRESTful']['StationRegistry']['register_this_station'] = final_register
    if final_register and final_station_url:
        weecfg.inject_station_url(config_dict, final_station_url)


def config_units(config_dict, unit_system=None, no_prompt=False):
    """Determine the unit system to use"""

    default_unit_system = None
    try:
        # Look for option 'unit_system' in [StdReport]
        default_unit_system = config_dict['StdReport']['unit_system']
    except KeyError:
        try:
            default_unit_system = config_dict['StdReport']['Defaults']['unit_system']
        except KeyError:
            # Not there. It's a custom unit system
            pass

    if unit_system:
        final_unit_system = unit_system
    elif not no_prompt:
        print("\nChoose a unit system for your reports. Possible choices are:")
        print(f"  '{bcolors.BOLD}us{bcolors.ENDC}' (ºF, inHg, in, mph)")
        print(f"  '{bcolors.BOLD}metricwx{bcolors.ENDC}' (ºC, mbar, mm, m/s)")
        print(f"  '{bcolors.BOLD}metric{bcolors.ENDC}' (ºC, mbar, cm, km/h)")
        print("Later, you can modify your choice, or choose a combination of units.")
        # Get what unit system the user wants
        options = ['us', 'metricwx', 'metric']
        final_unit_system = weecfg.prompt_with_options(f"Your choice",
                                                       default_unit_system, options)
    else:
        final_unit_system = default_unit_system

    if 'StdReport' in config_dict and final_unit_system:
        # Make sure the default unit system sits under [[Defaults]]. First, get rid of anything
        # under [StdReport]
        config_dict['StdReport'].pop('unit_system', None)
        # Then add it under [[Defaults]]
        config_dict['StdReport']['Defaults']['unit_system'] = final_unit_system


def config_driver(config_dict, driver=None, no_prompt=False):
    """Do what's necessary to create or reconfigure a driver in the configuration file.

    Args:
        config_dict (configobj.ConfigObj): The configuration dictionary
        driver (str): The driver to use. Something like 'weewx.drivers.fousb'.
            Usually this comes from the command line. Default is None, which means prompt the user.
            If no_prompt has been specified, then use the simulator.
        no_prompt (bool): False to prompt the user. True to not allow prompts. Default is False.
    """
    # The existing driver is the default. If there is no existing driver, use the simulator.
    try:
        station_type = config_dict['Station']['station_type']
        default_driver = config_dict[station_type]['driver']
    except KeyError:
        default_driver = 'weewx.drivers.simulator'

    # Was a driver specified in the args?
    if driver is not None:
        # Yes. Use it
        final_driver = driver
    elif not no_prompt:
        # Prompt for a suitable driver
        final_driver = weecfg.prompt_for_driver(default_driver)
    else:
        # If we got here, a driver was not specified in the args, and we can't prompt the user.
        # So, use the default.
        final_driver = default_driver

    # We've selected a driver. Now we need to get a stanza to go along with it.
    # Look up driver info, and get the driver editor. The editor provides a default stanza,
    # and allows prompt-based editing of the stanza. Fail hard if the driver fails to load.
    driver_editor, driver_name, driver_version = weecfg.load_driver_editor(final_driver)
    # If the user has supplied a name for the driver stanza, then use it. Otherwise, use the one
    # supplied by the driver.
    log.info(f'Using {driver_name} version {driver_version} ({driver})')

    # Get a driver stanza, if possible
    stanza = None
    if driver_name:
        if driver_editor:
            # if a previous stanza exists for this driver, grab it
            if driver_name in config_dict:
                # We must get the original stanza as a long string with embedded newlines.
                orig_stanza = configobj.ConfigObj(interpolation=False)
                orig_stanza[driver_name] = config_dict[driver_name]
                orig_stanza_text = '\n'.join(orig_stanza.write())
            else:
                orig_stanza_text = None

            # let the driver process the stanza or give us a new one
            stanza_text = driver_editor.get_conf(orig_stanza_text)
            stanza = configobj.ConfigObj(stanza_text.splitlines())
        else:
            # No editor. If the original config_dict has the stanza use that. Otherwise, a blank
            # stanza.
            stanza = configobj.ConfigObj(interpolation=False)
            stanza[driver_name] = config_dict.get(driver_name, {})

    # If we have a stanza, inject it into the configuration dictionary
    if stanza and driver_name:
        # Ensure that the driver field matches the path to the actual driver
        stanza[driver_name]['driver'] = final_driver
        # Insert the stanza in the configuration dictionary:
        config_dict[driver_name] = stanza[driver_name]
        # Add a major comment deliminator:
        config_dict.comments[driver_name] = weecfg.major_comment_block
        # If we have a [Station] section, move the new stanza to just after it
        if 'Station' in config_dict:
            weecfg.reorder_sections(config_dict, driver_name, 'Station', after=True)
            # make the stanza the station type
            config_dict['Station']['station_type'] = driver_name
        # Give the user a chance to modify the stanza:
        if not no_prompt:
            settings = weecfg.prompt_for_driver_settings(final_driver,
                                                         config_dict.get(driver_name, {}))
            config_dict[driver_name].merge(settings)

    if driver_editor:
        # One final chance for the driver to modify other parts of the configuration
        driver_editor.modify_config(config_dict)


def config_roots(config_dict,
                 weewx_root=None,
                 skin_root=None,
                 html_root=None,
                 sqlite_root=None,
                 user_root=None):
    """Set the location of various root directories in the configuration dictionary."""
    if weewx_root:
        config_dict['WEEWX_ROOT'] = weewx_root
    if user_root:
        config_dict['USER_ROOT'] = user_root

    if 'StdReport' in config_dict:
        if skin_root:
            config_dict['StdReport']['SKIN_ROOT'] = skin_root
        elif 'SKIN_ROOT' not in config_dict['StdReport']:
            config_dict['StdReport']['SKIN_ROOT'] = 'skins'
        if html_root:
            config_dict['StdReport']['HTML_ROOT'] = html_root
        elif 'HTML_ROOT' not in config_dict['StdReport']:
            config_dict['StdReport']['HTML_ROOT'] = 'public_html'

    if 'DatabaseTypes' in config_dict and 'SQLite' in config_dict['DatabaseTypes']:
        # Temporarily turn off interpolation
        hold, config_dict.interpolation = config_dict.interpolation, False
        if sqlite_root:
            config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] = sqlite_root
        elif 'SQLITE_ROOT' not in config_dict['DatabaseTypes']['SQLite']:
            config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] = 'archive'
        # Turn interpolation back on.
        config_dict.interpolation = hold


def copy_skins(config_dict, dry_run=False):
    """Copy any missing skins from the resource package to the skins directory"""
    if 'StdReport' not in config_dict:
        return

    # SKIN_ROOT is the location of the skins relative to WEEWX_ROOT. Find it's absolute location
    skin_dir = os.path.join(config_dict['WEEWX_ROOT'], config_dict['StdReport']['SKIN_ROOT'])
    if not dry_run:
        # Make it if it doesn't already exist
        print(f"Making directory {skin_dir}.")
        os.makedirs(skin_dir, exist_ok=True)

    # Find the skins we already have
    if dry_run or not os.path.exists(skin_dir):
        existing_skins = set()
    else:
        with os.scandir(skin_dir) as existing_contents:
            existing_skins = {os.path.basename(d.path) for d in existing_contents if d.is_dir()}

    with weeutil.weeutil.path_to_resource('wee_resources', 'skins') as skin_resources:
        # Find which skins are available in the resource package
        with os.scandir(skin_resources) as resource_contents:
            available_skins = {os.path.basename(d.path) for d in resource_contents if d.is_dir()}

        missing_skins = available_skins - existing_skins

        # Copy over any missing skins
        for skin in missing_skins:
            src = os.path.join(skin_resources, skin)
            dest = os.path.join(skin_dir, skin)
            print(f"Copying skin {skin} into {dest}.")
            if not dry_run:
                shutil.copytree(src, dest)


def copy_docs(config_dict, docs_root=None, dry_run=False):
    """Copy documentation from package resources to the DOCS_ROOT directory."""

    # If the user didn't specify a value, use a default
    if not docs_root:
        docs_root = 'docs'

    # DOCS_ROOT is relative to WEEWX_PATH. Join them to get the absolute path.
    docs_dir = os.path.join(config_dict['WEEWX_ROOT'], docs_root)

    print(f"Removing {docs_dir}.")
    if not dry_run:
        shutil.rmtree(docs_dir, ignore_errors=True)
    with weeutil.weeutil.path_to_resource('wee_resources', 'docs') as docs_resources:
        print(f"Copying new docs into {docs_dir}.")
        if not dry_run:
            shutil.copytree(docs_resources, docs_dir)
    return docs_dir


def copy_examples(config_dict, examples_root=None, dry_run=False):
    """Copy the examples to the EXAMPLES_ROOT directory."""

    # If the user didn't specify a value, use a default
    if not examples_root:
        examples_root = 'examples'

    # examples_root is relative to WEEWX_PATH. Join them to get the absolute path.
    examples_dir = os.path.join(config_dict['WEEWX_ROOT'], examples_root)

    print(f"Removing directory {examples_dir}.")
    if not dry_run:
        shutil.rmtree(examples_dir, ignore_errors=True)
    with weeutil.weeutil.path_to_resource('wee_resources', 'examples') as examples_resources:
        print(f"Copying new examples into {examples_dir}.")
        if not dry_run:
            shutil.copytree(examples_resources, examples_dir)
    return examples_dir


def copy_user(config_dict, user_root=None, dry_run=False):
    """Copy the user directory to USER_ROOT"""

    # If the user didn't specify a value, use a default
    if not user_root:
        user_root = config_dict.get('USER_ROOT', 'bin/user')

    # USER_ROOT is relative to WEEWX_PATH. Join them to get the absolute path.
    user_dir = os.path.join(config_dict['WEEWX_ROOT'], user_root)

    # Don't clobber an existing user subdirectory
    if not os.path.isdir(user_dir):
        with weeutil.weeutil.path_to_resource('wee_resources', 'bin') as lib_resources:
            print(f"Creating a new 'user' directory at {user_dir}.")
            if not dry_run:
                shutil.copytree(os.path.join(lib_resources, 'user'),
                                user_dir,
                                ignore=shutil.ignore_patterns('*.pyc', '__pycache__', ))


def copy_util(config_path, config_dict, dry_run=False):
    weewxd_path = shutil.which('weewxd')
    if not weewxd_path:
        print(f"{bcolors.FAIL}Unable to find the WeeWX executable 'weewxd'.{bcolors.ENDC}",
              file=sys.stderr)
        print(f"{bcolors.FAIL}No daemon utility files will be created.{bcolors.ENDC}",
              file=sys.stderr)
        print(f"{bcolors.FAIL}Make sure the pip user directory (typically ~/.local/bin) "
              f"is in your PATH, then retry.{bcolors.ENDC}",
              file=sys.stderr)
        return
    username = getpass.getuser()
    groupname = grp.getgrgid(os.getgid()).gr_name
    # This is the set of substitutions to be performed. The key is a regular expression. If a
    # match is found, the value will be substituted for the matched expression.
    re_dict = {
        # For systemd
        r"^#User=.*": rf"User={username}",
        # For systemd
        r"^#Group=.*": rf"Group={groupname}",
        # For systemd
        r"^ExecStart=.*": rf"ExecStart={weewxd_path} {config_path}",
        # For init.d, redhat, bsd, suse
        r"^WEEWX_BIN=.*": rf"WEEWX_BIN={weewxd_path}",
        # For init.d, redhat, bsd, suse
        r"^WEEWX_CFG=.*": rf"WEEWX_CFG={config_path}",
        # For init.d
        r"^WEEWX_USER=.*": rf"WEEWX_USER={groupname}",
        # For multi
        r"^WEEWX_BINDIR=.*": rf"WEEWX_BINDIR={os.path.dirname(weewxd_path)}",
        # For multi
        r"^WEEWX_CFGDIR=.*": rf"WEEWX_CFGDIR={os.path.dirname(config_path)}",
        # For macOS:
        r"<string>/Users/Shared/weewx/bin/weewxd</string>": rf"<string>{weewxd_path}<string>",
        # For macOS:
        r"<string>/Users/Shared/weewx/weewx.conf</string>": rf"<string>{config_path}<string>",
    }
    # Convert to a list of two-way tuples.
    re_list = [(re.compile(key), re_dict[key]) for key in re_dict]

    with weeutil.weeutil.path_to_resource('wee_resources', 'util') as util_resources:
        dstdir = os.path.join(config_dict['WEEWX_ROOT'], 'util')
        print(f"Creating daemon utility files in {dstdir}.")
        if not dry_run:
            _process_files(util_resources, dstdir, re_list)

    return dstdir


def _process_files(srcdir, dstdir, re_list, exclude={'__pycache__'}):
    """Process all the utility files found in srcdir. Put them in dstdir"""
    if os.path.basename(srcdir) in exclude:
        return
    # If the destination directory doesn't exist yet, make it
    if not os.path.exists(dstdir):
        os.mkdir(dstdir)

    for f in os.listdir(srcdir):
        if ".pyc" in f:
            continue
        srcpath = os.path.join(srcdir, f)
        dstpath = os.path.join(dstdir, f)
        # If this entry is a directory, descend into it using recursion
        if os.path.isdir(srcpath):
            _process_files(srcpath, dstpath, re_list, exclude)
        else:
            # Otherwise, it's a file. Patch it.
            _patch_file(srcpath, dstpath, re_list)


def _patch_file(srcpath, dstpath, re_list):
    """Patch an individual file using the list of regular expressions re_list"""
    with open(srcpath, 'r') as rd, open(dstpath, 'w') as wd:
        for line in rd:
            # Lines starting with "#&" are comment lines. Ignore them.
            if line.startswith("#&"):
                continue
            # Go through all the regular expressions, substituting the value for the key
            for key, value in re_list:
                line = key.sub(value, line)
            wd.write(line)


def station_update(config_path, docs_root=None, examples_root=None,
                   no_prompt=False, dry_run=False):
    """Upgrade the user data for the configuration file found at config_path"""

    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    ans = weeutil.weeutil.y_or_n(f"\nUpgrade station at {config_path}? (Y/n) ",
                                 noprompt=no_prompt,
                                 default='y')
    if ans != 'y':
        print("Nothing done.")
        return

    # Retrieve the new configuration file as a ConfigObj:
    with importlib.resources.open_text('wee_resources', 'weewx.conf', encoding='utf-8') as fd:
        dist_config_dict = configobj.ConfigObj(fd, encoding='utf-8', file_error=True)
    # Retrieve the old configuration file as a ConfigObj:
    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    weecfg.update_config.update_and_merge(config_dict, dist_config_dict)
    print(f"Finished upgrading the configuration file found at {config_path}.")
    docs_dir = copy_docs(config_dict, docs_root=docs_root, dry_run=dry_run)
    print(f"Finished upgrading docs found at {docs_dir}.")
    examples_dir = copy_examples(config_dict, examples_root=examples_root, dry_run=dry_run)
    print(f"Finished upgrading examples found at {examples_dir}.")
    util_dir = copy_util(config_path, config_dict, dry_run=dry_run)
    if util_dir:
        print(f"Finished upgrading utilities directory found at {util_dir}.")
    else:
        print("Could not upgrade the utilities directory.")

    # Save the updated config file with backup
    print(f"Saving configuration file to {config_path}.")
    if dry_run:
        print("This was a dry run. Nothing was actually done.")
    else:
        backup_path = weecfg.save_with_backup(config_dict, config_path)
        print(f"Backed up configuration file to {backup_path}.")
        print("Done")


def upgrade_skins(config_path, skin_root=None, no_prompt=False, dry_run=False):
    """Make a backup of the old skins, then copy over new skins."""
    if dry_run:
        print("This is a dry run. Nothing will actually be done.")

    ans = weeutil.weeutil.y_or_n(f"\nUpgrade skins at {config_path}?\n"
                                 "A backup copy will be made first. (Y/n) ",
                                 noprompt=no_prompt,
                                 default='y')
    if ans != 'y':
        print("Nothing done.")
        return

    # Retrieve the configuration file as a ConfigObj:
    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    if not skin_root:
        try:
            skin_root = config_dict['StdReport']['SKIN_ROOT']
        except KeyError:
            skin_root = 'skins'

    # SKIN_ROOT is the location of the skins relative to WEEWX_ROOT. Find it's absolute location
    skin_dir = os.path.join(config_dict['WEEWX_ROOT'], skin_root)

    if os.path.exists(skin_dir):
        if not dry_run:
            backup = weeutil.weeutil.move_with_timestamp(skin_dir)
            print(f"Old skin directory saved to {backup}.")
    else:
        print(f"No skin directory found at {skin_dir}.")

    copy_skins(config_dict, dry_run)

    if dry_run:
        print("This was a dry run. Nothing was actually done.")
