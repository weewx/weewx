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

# The default station information:
stn_info_defaults = {'station_type' : 'Simulator',
                     'driver'       : 'weewx.drivers.simulator'}

class ConfigEngine(object):
    
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

        # Can have only one of install, update, and merge:
        if sum(1 if x is True else 0 for x in [options.install, options.update, options.merge]) > 1:
            exit("Can have only one of install, update, or merge")
        
        # Check for missing --dist-config
        if (options.install or options.update or options.merge) and not options.dist_config:
                exit("Command requires option --dist-config to be specified.")
                
        # The install and merge options requires --output
        if (options.install or options.merge) and not options.output:
            sys.exit("Command requires option --output to be specified.")
            
        # The install option does not take an old config file
        if options.install and (options.config_path or len(args)):
            sys.exit("Command --install does not allow an old config file.")
    
        # Flag for whether the output needs to be saved:
        save_me = False
        
        if options.install or options.update or options.merge:
        
            # Open up and parse the distribution config file:
            try:        
                dist_config_dict = configobj.ConfigObj(options.dist_config, file_error=True)
            except IOError, e:
                sys.exit(str(e))
            except SyntaxError, e:
                sys.exit("Syntax error in distribution configuration file '%s': %s" % 
                         (options.dist_config, e))
                
            if options.install:
                config_dict = dist_config_dict
                config_path = options.output
            else:
                config_path, config_dict = weecfg.read_config(options.config_path, args)
                print "Using configuration file found at", config_path
    
                # Update the old configuration file:
                weecfg.update_config(config_dict)
                
                # Then merge it into the distribution file
                weecfg.merge_config(config_dict, dist_config_dict)
    
            save_me = True
            
        if options.install or options.modify:
    
            self.modify_config(config_dict, options)
            save_me = True
            
        if save_me:
            self.save_config(config_dict, config_path)
        else:
            print "Nothing done."
    
        return 0

    def modify_config(self, config_dict, options):
        """Modify the configuration dictionary according to any command
        line options. Give the user a chance too.
        """
        
        # Extract stn_info from the config_dict and command-line options:
        stn_info = self.get_stn_info(config_dict, options)

        return weecfg.modify_config(config_dict, stn_info, options.debug)
    
    def get_stn_info(self, config_dict, options):
        """Build the stn_info structure. This generally contains stuff
        that wee_config can inject into the config_dict."""
        
        # Get defaults out of the config file:
        stn_info = weecfg.get_station_info(config_dict)
    
        # Get command line overrides, and apply them to stn_info:
        for k in stn_info:
            # Override only if the option exists and is not None:
            if hasattr(options, k) and getattr(options,k) is not None:
                stn_info[k] = getattr(options, k)
    
        # If any are still None, replace them with defaults:
        for k in stn_info_defaults:
            if k not in stn_info or stn_info[k] is None:
                stn_info[k] = stn_info_defaults[k]
                
        # Unless --no-prompt has been specified, give the user a chance to change things:
        if not options.no_prompt:
            stn_info.update(weecfg.prompt_for_info(**stn_info))
    
            if not options.driver:
                driver = weecfg.prompt_for_driver(stn_info.get('driver'))
                stn_info['driver'] = driver
                stn_info.update(weecfg.prompt_for_driver_settings(driver))
                
        return stn_info
    
    def save_config(self, config_dict, config_path):
        """Save the config file, backing up as necessary."""

        backup_path = weecfg.save_config(config_dict, config_path)
        if backup_path:        
            print "Saved backup to %s" % backup_path
            
        print "Saved configuration file to %s" % config_path