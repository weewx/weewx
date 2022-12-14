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
import sys

import configobj

import weecfg
import weeutil.weeutil
import weewx
from weeutil.weeutil import to_float

log = logging.getLogger(__name__)


def create_station(namespace):
    # def create_station(config_path,
    #                    driver='weewx.drivers.simulator',
    #                    station_name=None,
    #                    location = "My Little Town",
    #                    station_url=None,
    #                    latitude=0.0,
    #                    longitude = 0.0,
    #                    altitude = (0, "meter"),
    #                    lang= "en",
    #                    unit_system= "us",
    #                    register_this_station=False
    #                    ):
    """
    Steps:
    1. Check to see if configuration file already exists.
    2. Retrieve file from package resources.
    3. Update values from parameters
    4. Prompt for new values.
    5. Write to appropriate location.
    """

    # Fail hard if 'config' is missing
    config_path = namespace.config

    if os.path.exists(config_path):
        raise weewx.ViolatedPrecondition(f"Config file {config_path} already exists")

    # Retrieve the configuration file as a ConfigObj
    with importlib.resources.open_text('wee_resources', 'weewx.conf', encoding='utf-8') as fd:
        dist_config_dict = configobj.ConfigObj(fd, file_error=True)


def set_driver(config_dict, namespace):
    weecfg.configure_driver(config_dict, namespace.driver, namespace.no_prompt)


def set_latlon(config_dict, namespace):
    """Set a (possibly new) value for latitude and longitude"""

    if 'Station' in config_dict:
        # The existing value is the default
        latitude = to_float(config_dict['Station'].get('latitude', 0.0))
        # Was a new value provided on the command line?
        if namespace.latitude:
            # Yes. Use it
            latitude = namespace.latitude
        elif not namespace.no_prompt:
            # No. Prompt for a new value
            print("\nSpecify latitude in decimal degrees, negative for south.")
            latitude = weecfg.prompt_with_limits("latitude", latitude, -90, 90)
        config_dict['Station']['latitude'] = latitude

        # Similar, except for longitude
        longitude = to_float(config_dict['Station'].get('longitude', 0.0))
        # Was a new value provided on the command line?
        if namespace.longitude:
            # Yes. Use it
            longitude = namespace.longitude
        elif not namespace.no_prompt:
            # No. Prompt for a new value
            print("Specify longitude in decimal degrees, negative for west.")
            longitude = weecfg.prompt_with_limits("longitude", longitude, -180, 180)
        config_dict['Station']['longitude'] = longitude


def set_altitude(config_dict, namespace):
    """Set a (possibly new) value and unit for altitude"""
    if 'Station' in config_dict:
        # Get the default value from the config file:
        altitude = config_dict['Station'].get('altitude', ["0", 'foot'])
        # Was a new value provided on the command line?
        if namespace.altitude:
            # Yes. Extract and validate it, then use it
            value, unit = namespace.altitude.split(',')
            # Fail hard if the value cannot be converted to a float
            float(value)
            # Fail hard if the unit is unknown:
            unit = unit.strip().lower()
            if unit not in ['foot', 'meter']:
                raise ValueError(f"Unknown altitude unit {unit}")
            # All is good. Use it.
            altitude = [value, unit]
        elif not namespace.no_prompt:
            print("\nSpecify altitude, with units 'foot' or 'meter'.  For example:")
            print("35, foot")
            print("12, meter")
            if altitude:
                msg = "altitude [%s]: " % weeutil.weeutil.list_as_string(altitude)
            else:
                msg = "altitude: "
            alt = None
            while alt is None:
                ans = input(msg).strip()
                if ans:
                    parts = ans.split(',')
                    if len(parts) == 2:
                        try:
                            # Test whether the first token can be converted into a
                            # number. If not, an exception will be raised.
                            float(parts[0])
                            unit = parts[1].strip().lower()
                            if unit in ['foot', 'meter']:
                                alt = [parts[0].strip(), unit]
                        except (ValueError, TypeError):
                            pass
                elif altitude:
                    # ans is the null string. Use the default.
                    alt = altitude

                if not alt:
                    print("Unrecognized response. Try again.")
            altitude = alt
        config_dict['Station']['altitude'] = altitude
