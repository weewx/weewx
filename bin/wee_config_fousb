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

import configobj
import optparse
import time

import weewx.fousb
import weewx.units
import weeutil.weeutil

description = """Configures Fine Offset weather stations.

For now this utility is read-only - it reports all of the station settings
but does not provide a mechanism to modify them.

The station model, version, and id are supposed to be reported by these
instruments, but so far (04jan2013) my testing shows bogus values for these
fields.

If you have a Fine Offset station and use this utility, it would be helpful
to know:

1) the model, version, and id

2) the stations model as indicated on the packaging, for example
   'Ambient WS-2080', 'National Geographic 265NE, or 'Watson W8681'

Output from a 308x-series station would be particularly helpful.
"""

# TODO:
# set station archive interval

usage="""%prog: config_file [--help | --info | --check-pressures] [--debug]"""

epilog = """Mutating actions will request confirmation before proceeding."""

def main():

    # Create a command line parser:
    parser = optparse.OptionParser(description=description, usage=usage, epilog=epilog)
    
    # Add the various options:
    parser.add_option("--info", action="store_true", dest="info",
                        help="display weather station configuration")
    parser.add_option("--check-pressures", action="store_true", dest="chkpres",
                        help="query station for pressure sensor data")
    parser.add_option("--debug", action="store_true", dest="debug",
                        help="display additional information while running")
    
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

    # The driver needs the altitude in meters in order to calculate relative
    # pressure. Get it from the Station data and do any necessary conversions.
    altitude_t = weeutil.weeutil.option_as_list(config_dict['Station'].get('altitude', (None, None)))
    # Form a value-tuple:
    altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
    # Now convert to meters, using only the first element of the value-tuple:
    altitude_m = weewx.units.convert(altitude_vt, 'meter')[0]
    
    station = weewx.fousb.FineOffsetUSB(altitude=altitude_m,
                                        **config_dict['FineOffsetUSB'])

    if options.chkpres:
        checkpressures(station)
    elif options.info or len(args) == 1:
        info(station)

def info(station):
    """Query the station then display the settings."""

    print "Querying the station..."
    val = getvalues(station, '', weewx.fousb.fixed_format)
    station.closePort()

    print 'Fine Offset station settings:'
    print '%s: %s' % ('local time'.rjust(30),
                      time.strftime('%Y.%m.%d %H:%M:%S %Z', time.localtime()))

    slist = {'values':[], 'minmax_values':[],
             'settings':[], 'display_settings':[], 'alarm_settings':[]}
    for x in sorted(val.keys()):
        if type(val[x]) is dict:
            for y in val[x].keys():
                label = x + '.' + y
                s = fmtparam(label, val[x][y])
                slist = stash(slist, s)
        else:
            s = fmtparam(x, val[x])
            slist = stash(slist, s)
    for k in ('values','minmax_values','settings','display_settings','alarm_settings'):
        print ''
        for s in slist[k]:
            print s

def checkpressures(station):
    """Query the station then display sensor readings."""
    print "Querying the station..."
    val = getvalues(station, '', weewx.fousb.fixed_format)
    station.closePort()

    for packet in station.genLoopPackets():
        print packet
        rp = station.get_fixed_block(['rel_pressure'])
        sp = packet['pressure']
        ap1 = weewx.wxformulas.altimeter_pressure_Metric(sp, station.altitude)
        ap2 = weewx.fousb.sp2ap(sp, station.altitude)
        bp2 = weewx.fousb.sp2bp(sp, station.altitude, packet['outTemp'])
        print 'relative pressure: %s' % rp
        print 'station pressure: %s' % sp
        print 'altimeter pressure (davis): %s' % ap1
        print 'altimeter pressure (noaa): %s' % ap2
        print 'barometer pressure (weewx): ?'
        print 'barometer pressure (wview): %s' % bp2

def stash(slist, s):
    if s.find('settings') != -1:
        slist['settings'].append(s)
    elif s.find('display') != -1:
        slist['display_settings'].append(s)
    elif s.find('alarm') != -1:
        slist['alarm_settings'].append(s)
    elif s.find('min.') != -1 or s.find('max.') != -1:
        slist['minmax_values'].append(s)
    else:
        slist['values'].append(s)
    return slist

def fmtparam(label, value):
    fmt = '%s'
    if label in weewx.fousb.datum_display_formats.keys():
        fmt = weewx.fousb.datum_display_formats[label]
    fmt = '%s: ' + fmt
    return fmt % (label.rjust(30), value)

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
