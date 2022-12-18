#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Install or reconfigure a configuration file"""

import importlib
import importlib.resources
import logging
import os.path

import configobj

import weecfg
import weeutil.config
import weeutil.weeutil
import weewx
from weeutil.weeutil import to_float, to_bool

log = logging.getLogger(__name__)


def create_station(config_path, *args, **kwargs):
    """Create a brand-new configuration file.

    Like config_station(), except it ensures that the config file does not already exist. It then
    retrieves the template config file from package resources and uses that.
    """

    # Make sure there is not already a configuration file at the designated location.
    if os.path.exists(config_path):
        raise weewx.ViolatedPrecondition(f"Config file {config_path} already exists")

    # Retrieve the configuration file as a ConfigObj
    with importlib.resources.open_text('wee_resources', 'weewx.conf', encoding='utf-8') as fd:
        dist_config_dict = configobj.ConfigObj(fd, encoding='utf-8', file_error=True)

    config_config(dist_config_dict, *args, **kwargs)

    # Save the results. No backup.
    weecfg.save(dist_config_dict, config_path)


def config_station(config_path, *args, **kwargs):
    "Reconfigure an existing station"

    config_dict = configobj.ConfigObj(config_path, encoding='utf-8', file_error=True)

    config_config(config_dict, *args, **kwargs)

    # Save the results with backup
    weecfg.save_with_backup(config_dict, config_path)


def config_config(config_dict, altitude=None, latitude=None, longitude=None,
                  register=None, unit_system=None, driver=None,
                  no_prompt=False):
    """Modify a configuration file."""
    config_altitude(config_dict, altitude=altitude, no_prompt=no_prompt)
    config_latlon(config_dict, latitude=latitude, longitude=longitude, no_prompt=no_prompt)
    config_registry(config_dict, register=register, no_prompt=no_prompt)
    config_units(config_dict, unit_system=unit_system, no_prompt=no_prompt)
    config_driver(config_dict, driver=driver, no_prompt=no_prompt)


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
                value, unit = ans.split(',')
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
        latitude (float|None): The latitude. If specified, no prompting will happen.
        longitude (float|None): The longitude. If specified no prompting will happen.
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
        print("in a map. You will need a unique URL to identify your station (such as a")
        print("website, or WeatherUnderground link).")
        ans = weecfg.prompt_with_options("Include station in the station registry (y/n)?",
                                         'y' if default_register else 'n',
                                         ['y', 'n'])
        final_register = to_bool(ans)
        if final_register:
            while True:
                print("\nNow give a unique URL for your station. A Weather Underground ")
                print("URL such as https://www.wunderground.com/dashboard/pws/KORPORT12 will do.")
                url = weecfg.prompt_with_options("Unique URL", default_station_url)
                if url:
                    if url.startswith('http://www.example.com'):
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
    if final_station_url:
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
        # Get what unit system the user wants
        options = ['us', 'metricwx', 'metric']
        print("\nIndicate the preferred units for display: %s" % options)
        final_unit_system = weecfg.prompt_with_options("unit system", default_unit_system, options)
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
            settings = weecfg.prompt_for_driver_settings(final_driver, config_dict)
            config_dict.merge(settings)

    if driver_editor:
        # One final chance for the driver to modify other parts of the configuration
        driver_editor.modify_config(config_dict)
