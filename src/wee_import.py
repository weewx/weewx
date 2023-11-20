#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Gary Roderick
#
#    See the file LICENSE.txt for your rights.
#
"""Import WeeWX observation data from an external source.

Compatibility:

    wee_import can import from:
        - a Comma Separated Values (CSV) format file
        - the historical records of a Weather Underground Personal
          Weather Station
        - one or more Cumulus monthly log files
        - one or more Weather Display monthly log files
        - one or more WeatherCat monthly .cat files

Design

    wee_import utilises an import config file and a number of command line
    options to control the import. The import config file defines the type of
    input to be performed and the import data source as well as more advanced
    options such as field maps etc. Details of the supported command line
    parameters/options can be viewed by entering wee_import --help at the
    command line. Details of the wee_import import config file settings can be
    found in the example import config files distributed in the
    util/import directory.

    wee_import utilises an base class Source that defines the majority of the
    wee_import functionality. The base class and other supporting structures
    are in weeimport/weeimport.py. Child classes are created from the base
    class for each different import type supported bybwee_import. The child
    classes set a number of import type specific properties as well as defining
    get_data() and period_generator() methods tha read the raw data to be
    imported and generates a sequence of objects to be imported (e.g., monthly
    log files) respectively. This way wee_import can be extended to support
    other sources by defining a new child class, its specific properties as
    well as get_data() and period_generator() methods. The child class for a
    given import type are defined in the weeimport/xxximport.py files.

    As with other WeeWX utilities, wee_import advises the user of basic
    configuration, action taken and results via the console. However, since
    wee_import can make substantial changes to the WeeWX archive, wee_import
    also logs to WeeWX log system file. Console and log output can be controlled
    via a number of command line options.

Prerequisites

    wee_import uses a number of WeeWX API calls and therefore must have a
    functional WeeWX installation. wee_import requires WeeWX 4.0.0 or later.

Configuration

    A number of parameters to be used during the import must be defined in the
    import config file. Refer to the wee_import guide for details of the import
    config file.

Adding a New Import Source

    To add a new import source:

    -   Create a new file weeimport/xxximport.py that defines a new class for
        the xxx source that is a child of class Source. The new class must meet
        the following minimum requirements:

        -   __init__() must define:

            -   self.raw_datetime_format: Format of date time data field from
                                          which observation timestamp is to be
                                          derived. String comprising Python
                                          strptime() format codes.
            -   self.map: The field map to be used to map the xxx source fields
                          to WeeWX archive fields.
            -   self.wind_dir: The range of values in degrees that will be
                               accepted as a valid wind direction. Two way
                               tuple of the format (lower, upper) where lower
                               is the lower inclusive limit and upper is the
                               upper inclusive limit.

        -   Define a period_generator() method that:

            -   Accepts no parameters and generates (yields) a sequence of
                objects (eg file names, dates for a http request etc) that are
                passed to the get_raw_data() method to obtain a sequence of raw
                data records.

        -   Define a get_raw_data() method that:

            -   Accepts a single parameter 'period' that is provided by the
                period_generator() method.

            -   Returns an iterable of raw source data records.

    -   Modify weeimport/weeimport.py as follows:

        -   Add a new entry to the list of supported services defined in
            SUPPORTED_SERVICES.

    -   Create a wee_import import config file for importing from the new
        source. The import config file must:

        -   Add a new source name to the source parameter. The new source name
            must be the same (case sensitive) as the entry added to
            weeimport.py SUPPORTED_SERVICES.

        -   Define a stanza for the new import type. The stanza must be the
            same (case sensitive) as the entry added to weeimport.py
            SUPPORTED_SERVICES.
"""

# Python imports
import argparse
import importlib
import logging

# WeeWX imports
import weecfg
import weewx
import weeimport
import weeimport.weeimport
import weeutil.logger
import weeutil.weeutil
from weeutil.weeutil import bcolors
log = logging.getLogger(__name__)

# minimum WeeWX version required for this version of wee_import
REQUIRED_WEEWX = "4.0.0"

description = """Import observation data into a WeeWX archive."""

usage = f"""{bcolors.BOLD}%(prog)s --help
       %(prog)s --import-config=IMPORT_CONFIG_FILE
            [--config=CONFIG_FILE]
            [--date=YYYY-mm-dd | --from=YYYY-mm-dd[THH:MM] --to=YYYY-mm-dd[THH:MM]]
            [--dry-run]
            [--verbose]
            [--no-prompt]
            [--suppress-warnings]{bcolors.ENDC}"""

epilog = """%(prog)s will import data from an external source into a WeeWX
            archive. Daily summaries are updated as each archive record is
            imported so there should be no need to separately rebuild the daily
            summaries."""


def main():
    """The main routine that kicks everything off."""

    # Create a command line parser:
    parser = argparse.ArgumentParser(description=description, usage=usage, epilog=epilog,
                                     prog='wee_import')

    # Add the various arguments:
    parser.add_argument("--config", dest="config_option", type=str,
                        metavar="CONFIG_FILE",
                        help="Use configuration file CONFIG_FILE.")
    parser.add_argument("--import-config", dest="import_config_option", type=str,
                        metavar="IMPORT_CONFIG_FILE",
                        help="Use import configuration file IMPORT_CONFIG_FILE.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Print what would happen but do not do it.")
    parser.add_argument("--date", dest="date", type=str, metavar="YYYY-mm-dd",
                        help="Import data for this date. Format is YYYY-mm-dd.")
    parser.add_argument("--from", dest="date_from", type=str, metavar="YYYY-mm-dd[THH:MM]",
                        help="Import data starting at this date or date-time. "
                             "Format is YYYY-mm-dd[THH:MM].")
    parser.add_argument("--to", dest="date_to", type=str, metavar="YYYY-mm-dd[THH:MM]",
                        help="Import data up until this date or date-time. Format "
                             "is YYYY-mm-dd[THH:MM].")
    parser.add_argument("--verbose", action="store_true", dest="verbose",
                        help="Print and log useful extra output.")
    parser.add_argument("--no-prompt", action="store_true", dest="no_prompt",
                        help="Do not prompt. Accept relevant defaults and all y/n prompts.")
    parser.add_argument("--suppress-warnings", action="store_true", dest="suppress",
                        help="Suppress warnings to stdout. Warnings are still logged.")

    # Now we are ready to parse the command line:
    namespace = parser.parse_args()

    # check WeeWX version number for compatibility
    if weeutil.weeutil.version_compare(weewx.__version__, REQUIRED_WEEWX) < 0:
        print("WeeWX %s or greater is required, found %s. Nothing done, exiting."
              % (REQUIRED_WEEWX, weewx.__version__))
        exit(1)

    # get config_dict to use
    config_path, config_dict = weecfg.read_config(namespace.config_option)
    print("Using WeeWX configuration file %s" % config_path)

    # Now that we have the configuration dictionary, we can add the path to the user
    # directory to PYTHONPATH.
    weewx.add_user_path(config_dict)
    # Now we can import user extensions
    importlib.import_module('user.extensions')

    # Set weewx.debug as necessary:
    weewx.debug = weeutil.weeutil.to_int(config_dict.get('debug', 0))

    # Set up any customized logging:
    weeutil.logger.setup('wee_import', config_dict)

    # to do anything more we need an import config file, check if one was
    # provided
    if namespace.import_config_option:
        # we have something so try to start

        # advise the user we are starting up
        print("Starting wee_import...")
        log.info("Starting wee_import...")

        # If we got this far we must want to import something so get a Source
        # object from our factory and try to import. Be prepared to catch any
        # errors though.
        try:
            source_obj = weeimport.weeimport.Source.source_factory(namespace)
            source_obj.run()
        except weeimport.weeimport.WeeImportOptionError as e:
            print("**** Command line option error.")
            log.info("**** Command line option error.")
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportIOError as e:
            print("**** Unable to load source data.")
            log.info("**** Unable to load source data.")
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportFieldError as e:
            print("**** Unable to map source data.")
            log.info("**** Unable to map source data.")
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except weeimport.weeimport.WeeImportMapError as e:
            print("**** Unable to parse source-to-WeeWX field map.")
            log.info("**** Unable to parse source-to-WeeWX field map.")
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except (weewx.ViolatedPrecondition, weewx.UnsupportedFeature) as e:
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            print()
            parser.print_help()
            exit(1)
        except SystemExit as e:
            print(e)
            exit(0)
        except (ValueError, weewx.UnitError) as e:
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
        except IOError as e:
            print("**** Unable to load config file.")
            log.info("**** Unable to load config file.")
            print("**** %s" % e)
            log.info("**** %s" % e)
            print("**** Nothing done, exiting.")
            log.info("**** Nothing done.")
            exit(1)
    else:
        # we have no import config file so display a suitable message followed
        # by the help text then exit
        print("**** No import config file specified.")
        print("**** Nothing done.")
        print()
        parser.print_help()
        exit(1)


# execute our main code
if __name__ == "__main__":
    main()
