#!/usr/bin/python
# $Id: config_fousb.py 352 2013-01-04 15:48:17Z mwall $
#
# Copyright 2012 Matthew Wall
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/
"""Command line utility for configuring Fine Offset weather stations"""

import optparse
import configobj

import weewx.fousb
import weeutil.weeutil

description = """Configures Fine Offset weather stations."""

usage="""%prog: config_file [--help] [--info] [--debug]"""

epilog = """Mutating actions will request confirmation before proceeding."""

def main():

    # Create a command line parser:
    parser = optparse.OptionParser(description=description, usage=usage, epilog=epilog)
    
    # Add the various options:
    parser.add_option("--info", action="store_true", dest="info",
                        help="display weather station configuration")
    parser.add_option("--debug", action="store_true", dest="debug",
                        help="display all bits, not just known bits")
    
    # Now we are ready to parse the command line:
    (options, args) = parser.parse_args()
    if not args:
        parser.error("No configuration file specified")

    cfgfile = args[0]
    debug = options.debug or weewx.debug

    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(cfgfile, file_error=True)
    except IOError:
        print "Unable to open configuration file %s" % cfgfile
        exit(1)
    except configobj.ConfigObjError:
        print "Error wile parsing configuration file %s" % cfgfile
        exit(1)

    if debug:
        print "Using configuration file %s" % cfgfile

    # Open up the weather station:
    station = weewx.fousb.FineOffsetUSB(**config_dict['FineOffsetUSB'])

    if options.info or len(args) == 1:
        info(station)

def info(station):
    """Query the station and display the configuration and station"""

    print "Querying the station..."
    
    model = station.get_fixed_block(['model'])
    version = station.get_fixed_block(['version'])
    sid = station.get_fixed_block(['id'])
    values = getvalues(station, '', weewx.fousb.fixed_format)
    station.closePort()

    print 'Fine Offset station settings:'
    print '  Model:                          %s' % model
    print '  Version:                        %s' % version
    print '  ID:                             %s' % sid
    print ''
    for x in sorted(values.keys()):
        if type(values[x]) is dict:
            for y in values[x].keys():
                label = x + '.' + y
                printparam(label, values[x][y])
        else:
            printparam(x, values[x])

def printparam(label, value):
    fmt = '%s'
    if label in weewx.fousb.datum_display_formats.keys():
        fmt = weewx.fousb.datum_display_formats[label]
    fmt = '%s: ' + fmt
    print fmt % (label.rjust(30), value)

def getvalues(station, name, value):
    values = {}
    if type(value) is tuple:
        values[name] = station.get_fixed_block(name.split('.'))
    elif type(value) is dict:
        for x in value.keys():
            n = x
            if len(name) > 0:
                n = name + '.' + x
            values.update(getvalues(station, n, value[x]))
    return values

if __name__=="__main__" :
    main()
