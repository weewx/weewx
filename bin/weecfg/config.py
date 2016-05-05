#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com> and
#                            Matthew Wall
#
#    See the file LICENSE.txt for your full rights.
#
"""Utilities for managing the config file"""

import sys

import configobj

import weecfg
import weewx
from weecfg import Logger

# The default station information:
stn_info_defaults = {'station_type': 'Simulator',
                     'driver': 'weewx.drivers.simulator'}

class ConfigEngine(object):
    
    def __init__(self, logger=None):
        self.logger = logger or Logger()
    
    def run(self, args, options):
        if options.version:
            print weewx.__version__
            sys.exit(0)
    
        if options.list_drivers:
            weecfg.print_drivers()
            sys.exit(0)

        #
        # Check for errors in the options.
        #

        # Must have one, and only one, of install, upgrade, and reconfigure:
        if sum(1 if x is True else 0 for x in [options.install,
                                               options.upgrade,
                                               options.reconfigure]) != 1:
            sys.exit("No command specified.")

        # Check for missing --dist-config
        if (options.install or options.upgrade) and not options.dist_config:
            sys.exit("The commands --install and --upgrade require option --dist-config.")

        if options.install and not options.output:
            sys.exit("The --install command requires option --output.")

        # The install option does not take an old config file
        if options.install and (options.config_path or len(args)):
            sys.exit("The --install command does not require the config option.")
            
        #
        # Error checking done. Now run the commands.
        #
        
        # First, fiddle with option --altitude to convert it into a list:
        if options.altitude:
            options.altitude = options.altitude.split(",")

        if options.install or options.upgrade:
            # These options require a distribution config file. 
            # Open it up and parse it:
            try:        
                dist_config_dict = configobj.ConfigObj(options.dist_config,
                                                       file_error=True)
            except IOError, e:
                sys.exit("Unable to open distribution configuration file: %s" % e)
            except SyntaxError, e:
                sys.exit("Syntax error in distribution configuration file '%s': %s" %
                         (options.dist_config, e))

        # The install command uses the distribution config file as its input.
        # Other commands use an existing config file.
        if options.install:
            config_dict = dist_config_dict
        else:
            try:
                config_path, config_dict = weecfg.read_config(
                    options.config_path, args)
            except SyntaxError, e:
                sys.exit("Syntax error in configuration file: %s" % e)
            except IOError, e:
                sys.exit("Unable to open configuration file: %s" % e)
            self.logger.log("Using configuration file %s" % config_path)

        output_path = None

        if options.upgrade:
            # Update the config dictionary, then merge it with the distribution
            # dictionary
            weecfg.update_and_merge(config_dict, dist_config_dict)

            # Save to the specified output
            output_path = options.output
            
        if options.install or options.reconfigure:
            # Modify the configuration contents
            self.modify_config(config_dict, options)

            # Save to the specified output, or the original location if
            # output is not specified
            output_path = options.output if options.output else config_path

        if output_path is not None:
            # Save the file. First, pretty it up...
            weecfg.reorder_to_ref(config_dict)
            # ... then save
            self.save_config(config_dict, output_path, not options.no_backup)

    def modify_config(self, config_dict, options):
        """Modify the configuration dictionary according to any command
        line options. Give the user a chance too.
        """
        
        # Extract stn_info from the config_dict and command-line options:
        stn_info = self.get_stn_info(config_dict, options)

        weecfg.modify_config(config_dict, stn_info, self.logger, options.debug)
    
    def get_stn_info(self, config_dict, options):
        """Build the stn_info structure. This generally contains stuff
        that can be injected into the config_dict."""

        # Start with values from the config file:
        stn_info = weecfg.get_station_info(config_dict)

        # Get command line overrides, and apply them to stn_info:
        for k in stn_info:
            # Override only if the option exists and is not None:
            if hasattr(options, k) and getattr(options, k) is not None:
                stn_info[k] = getattr(options, k)

        # If any are still None, use defaults:
        for k in stn_info_defaults:
            if k not in stn_info or stn_info[k] is None:
                if hasattr(options, k) and getattr(options, k) is not None:
                    stn_info[k] = getattr(options, k)
                else:
                    stn_info[k] = stn_info_defaults[k]

        # Unless --no-prompt has been specified, give the user a chance
        # to change things:
        if not options.no_prompt:
            stn_info.update(weecfg.prompt_for_info(**stn_info))
            driver = weecfg.prompt_for_driver(stn_info.get('driver'))
            stn_info['driver'] = driver
            stn_info.update(weecfg.prompt_for_driver_settings(driver))

        return stn_info

    def save_config(self, config_dict, config_path, backup=True):
        """Save the config file, backing up as necessary."""

        backup_path = weecfg.save(config_dict, config_path, backup)
        if backup_path:        
            self.logger.log("Saved backup to %s" % backup_path)
            
        self.logger.log("Saved configuration to %s" % config_path)
