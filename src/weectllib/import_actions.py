#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Import command actions"""
import importlib
import logging

import weecfg
import weecfg.extension
import weeimport
import weeimport.weeimport
import weeutil.config
import weeutil.logger
import weewx
import weewx.manager
import weewx.units
import weewx.xtypes

from weeutil.weeutil import timestamp_to_string, TimeSpan, bcolors

log = logging.getLogger(__name__)

# minimum WeeWX version required for this version of wee_import
REQUIRED_WEEWX = "5.0.0b15"

def obs_import(config, import_config, **kwargs):
    """Generate information about the user's WeeWX environment

    Args:
        config_path (str): Path to the configuration file
        output (str|None): Path to where the output will be put. Default is stdout.
    """

    # check WeeWX version number for compatibility
    if weeutil.weeutil.version_compare(weewx.__version__, REQUIRED_WEEWX) < 0:
        print("WeeWX %s or greater is required, found %s. Nothing done, exiting."
              % (REQUIRED_WEEWX, weewx.__version__))
        exit(1)

    # get config_dict to use
    config_path, config_dict = weecfg.read_config(config)
    print("Using WeeWX configuration file %s" % config_path)

    # Now that we have the configuration dictionary, we can add the path to the user
    # directory to PYTHONPATH.
    weewx.add_user_path(config_dict)
    # Now we can import user extensions, we need user.extensions for any user
    # xtypes that may be used in (for example) StdWXCalculate()
    importlib.import_module('user.extensions')

    # Set weewx.debug as necessary:
    weewx.debug = weeutil.weeutil.to_int(config_dict.get('debug', 0))

    # Set up any customized logging:
    weeutil.logger.setup('wee_import', config_dict)

    # to do anything more we need an import config file, check if one was
    # provided
    if import_config:
        # we have something so try to start

        # advise the user we are starting up
        print("Starting weectl import...")
        log.info("Starting weectl import...")

        # If we got this far we must want to import something so get a Source
        # object from our factory and try to import. Be prepared to catch any
        # errors though.
        try:
            source_obj = weeimport.weeimport.Source.source_factory(config_path,
                                                                   config_dict,
                                                                   import_config,
                                                                   **kwargs)
            source_obj.run()
        except weeimport.weeimport.WeeImportOptionError as e:
            print(f"{bcolors.BOLD}**** Command line option error.{bcolors.ENDC}")
            log.info("**** Command line option error.")
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportIOError as e:
            print(f"{bcolors.BOLD}**** Unable to load source data.{bcolors.ENDC}")
            log.info("**** Unable to load source data.")
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportFieldError as e:
            print(f"{bcolors.BOLD}**** Unable to map source data.{bcolors.ENDC}")
            log.info("**** Unable to map source data.")
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportMapError as e:
            print(f"{bcolors.BOLD}**** Unable to parse source-to-WeeWX field map.{bcolors.ENDC}")
            log.info("**** Unable to parse source-to-WeeWX field map.")
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except (weewx.ViolatedPrecondition, weewx.UnsupportedFeature) as e:
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except SystemExit as e:
            print(e)
            exit(0)
        except (ValueError, weewx.UnitError) as e:
            print(f"{bcolors.BOLD}**** %s{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except IOError as e:
            print(f"{bcolors.BOLD}**** Unable to load config file.{bcolors.ENDC}")
            log.info("**** Unable to load config file.")
            print(f"{bcolors.BOLD}**** {e}{bcolors.ENDC}" % e)
            log.info(f"**** {e}")
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
    else:
        # we have no import config file so display a suitable message followed
        # by the help text then exit
        print(f"{bcolors.BOLD}**** No import config file specified.{bcolors.ENDC}")
        print("**** Nothing done.")
        exit(1)
