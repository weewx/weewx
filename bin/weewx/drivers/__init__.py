# $Id$
# Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
# See the file LICENSE.txt for your full rights.
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
        return "Mutating actions will request confirmation before proceeding."

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
        """Return a plain text stanza"""
        raise NotImplementedError("property 'default_stanza' is not defined")

    def get_conf(self, orig_stanza=None):
        """Given a configuration stanza, return a possibly modified copy
        that will work with the current version of the device driver.

        The default behavior is to return the original stanza, unmodified.

        Derived classes should override this if they need to modify previous
        configuration options or warn about deprecated or harmful options."""
        if orig_stanza is not None:
            return orig_stanza
        return self.default_stanza

    def prompt_for_settings(self):
        """Prompt for settings required for proper operation of this driver.
        """
        return dict()

    def _prompt(self, label, dflt=None, opts=None):
        value = None
        msg = "%s: " % label
        if dflt is not None:
            msg = "%s [%s]: " % (label, dflt)
        while value is None:
            ans = raw_input(msg)
            x = ans.strip()
            if len(x) == 0:
                if dflt is not None:
                    value = dflt
            elif opts is not None:
                if x in opts:
                    value = x
            else:
                value = x
        return value
