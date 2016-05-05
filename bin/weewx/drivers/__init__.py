#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Device drivers for the weewx weather system."""

import syslog
import weewx

class AbstractDevice(object):
    """Device drivers should inherit from this class."""    

    @property
    def hardware_name(self):
        raise NotImplementedError("Property 'hardware_name' not implemented")
    
    @property
    def archive_interval(self):
        raise NotImplementedError("Property 'archive_interval' not implemented")

    def genStartupRecords(self, last_ts):
        return self.genArchiveRecords(last_ts)
    
    def genLoopPackets(self):
        raise NotImplementedError("Method 'genLoopPackets' not implemented")
    
    def genArchiveRecords(self, lastgood_ts):
        raise NotImplementedError("Method 'genArchiveRecords' not implemented")
        
    def getTime(self):
        raise NotImplementedError("Method 'getTime' not implemented")
    
    def setTime(self):
        raise NotImplementedError("Method 'setTime' not implemented")
    
    def closePort(self):
        pass


class AbstractConfigurator(object):
    """The configurator class defines an interface for configuring devices.
    Inherit from this class to provide a comman-line interface for setting
    up a device, querying device status, and other setup/maintenance
    operations."""

    @property
    def description(self):
        return "Configuration utility for weewx devices."

    @property
    def usage(self):
        return "%prog [config_file] [options] [--debug] [--help]"

    @property
    def epilog(self):
        return "Be sure to stop weewx first before using. Mutating actions will"\
            " request confirmation before proceeding.\n"
                

    def configure(self, config_dict):
        parser = self.get_parser()
        self.add_options(parser)
        options, _ = parser.parse_args()
        if options.debug is not None:
            weewx.debug = options.debug
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        prompt = False if options.noprompt else True
        self.do_options(options, parser, config_dict, prompt)

    def get_parser(self):
        import optparse
        return optparse.OptionParser(description=self.description,
                                     usage=self.usage, epilog=self.epilog)

    def add_options(self, parser):
        """Add command line options.  Derived classes should override this
        method to add more options."""

        parser.add_option("--debug", dest="debug",
                          action="store_true",
                          help="display diagnostic information while running")
        parser.add_option("-y", dest="noprompt",
                          action="store_true",
                          help="answer yes to every prompt")

    def do_options(self, options, parser, config_dict, prompt):
        """Derived classes must implement this to actually do something."""
        raise NotImplementedError("Method 'do_options' not implemented")


class AbstractConfEditor(object):
    """The conf editor class provides methods for producing and updating
    configuration stanzas for use in configuration file.
    """

    @property
    def default_stanza(self):
        """Return a plain text stanza. This will look something like:
        
[Acme]
    # This section is for the Acme weather station 

    # The station model
    model = acme100

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The driver to use:
    driver = weewx.drivers.acme
        """
        raise NotImplementedError("property 'default_stanza' is not defined")

    def get_conf(self, orig_stanza=None):
        """Given a configuration stanza, return a possibly modified copy
        that will work with the current version of the device driver.

        The default behavior is to return the original stanza, unmodified.
        
        Derived classes should override this if they need to modify previous
        configuration options or warn about deprecated or harmful options.
        
        The return value should be a long string. See default_stanza above
        for an example string stanza."""
        return self.default_stanza if orig_stanza is None else orig_stanza

    def prompt_for_settings(self):
        """Prompt for settings required for proper operation of this driver.
        """
        return dict()

    def _prompt(self, label, dflt=None, opts=None):
        import weecfg
        val = weecfg.prompt_with_options(label, dflt, opts)
        del weecfg
        return val

    def modify_config(self, config_dict):
        """Given a configuration dictionary, make any modifications required
        by the driver.

        The default behavior is to make no changes.

        This method gives a driver the opportunity to modify configuration
        settings that affect its performance.  For example, if a driver can
        support hardware archive record generation, but software archive record
        generation is preferred, the driver can change that parameter using
        this method.
        """
        pass
