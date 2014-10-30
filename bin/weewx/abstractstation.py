# $Id$
# Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
# See the file LICENSE.txt for your full rights.

"""Abstract base class for hardware."""

class AbstractStation(object):
    """Station drivers should inherit from this class."""    

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


class DeviceConfigurator(object):
    @property
    def version(self):
        raise NotImplementedError("method 'version' is not implemented")

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
        (options, args) = parser.parse_args()
        if options.debug is not None:
            weewx.debug = options.debug
        self.do_config(options, config_dict)

    def do_config(self, options, config_dict):
        raise NotImplementedError("Method 'do_config' not implemented")

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
