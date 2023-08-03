#
#      Copyright (c) 2019-2021 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

#
#
#      See the file LICENSE.txt for your full rights.
#
"""weectl device actions"""
import importlib
import logging
import sys

import configobj

import weecfg
import weeutil.logger
import weewx
from weeutil.weeutil import to_int

log = logging.getLogger(__name__)


def device():
    # Load the configuration file
    try:
        config_fn, config_dict = weecfg.read_config(None, sys.argv[2:])
    except (OSError, configobj.ConfigObjError) as e:
        sys.exit(e)
    print(f'Using configuration file {config_fn}')

    # Set weewx.debug as necessary:
    weewx.debug = to_int(config_dict.get('debug', 0))

    # Customize the logging with user settings.
    weeutil.logger.setup('weectl', config_dict)

    try:
        # Find the device driver
        device_type = config_dict['Station']['station_type']
        driver = config_dict[device_type]['driver']
    except KeyError as e:
        sys.exit(f"Unable to determine driver: {e}")

    print(f"Using driver {driver}.")

    # Try to load the driver
    try:
        driver_module = importlib.import_module(driver)
        loader_function = getattr(driver_module, 'configurator_loader')
    except ImportError as e:
        msg = f"Unable to import driver {driver}: {e}."
        log.error(msg)
        sys.exit(msg)
    except AttributeError as e:
        msg = f"The driver {driver} does not include a configuration tool."
        log.info(f"{msg}: {e}")
        sys.exit(msg)
    except Exception as e:
        msg = f"Cannot load configurator for {device_type}."
        log.error(f"{msg}: {e}")
        sys.exit(msg)

    configurator = loader_function(config_dict)

    # Try to determine driver name and version.
    try:
        driver_name = driver_module.DRIVER_NAME
    except AttributeError:
        driver_name = '?'
    try:
        driver_vers = driver_module.DRIVER_VERSION
    except AttributeError:
        driver_vers = '?'
    print(f'Using {driver_name} driver version {driver_vers} ({driver})')

    configurator.configure(config_dict)
