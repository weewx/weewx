#!/usr/bin/env python
#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Command line utility for configuring the Davis VantagePro"""

import syslog
import argparse
import sys
import time

import configobj

import weewx.VantagePro

description = """Configures the VantagePro weather station."""

epilog = """Mutating actions will request confirmation before proceeding."""

def main():

    # Set defaults for the system logger:
    syslog.openlog('vpconfig', syslog.LOG_PID|syslog.LOG_CONS)

    # Create a command line parser:
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    
    # Add the various options:
    parser.add_argument("config_path",
                        help="Path to the configuration file (weewx.conf)")
    parser.add_argument("--info", action="store_true", dest="info",
                        help="To print configuration, reception, and barometer calibration information about your weather station.")
    parser.add_argument("--clear", action="store_true", dest="clear",
                        help="To clear the memory of your weather station.")
    parser.add_argument("--set_interval", type=int,
                        help="Sets the archive interval to the specified value in seconds. "\
                        "Valid values are 60, 300, 600, 900, 1800, 3600, or 7200.",
                        metavar="SECONDS")
    parser.add_argument("--set_altitude", type=float, 
                        help="Sets the altitude of the station to the specified number of feet.", 
                        metavar="FEET")
    parser.add_argument("--set_barometer", type=float, 
                        help="Sets the barometer reading of the station to a known correct value in inches of mercury. "\
                        "Specify 0 (zero) to have the console pick a sensible value.", 
                        metavar="INHG")
    parser.add_argument("--set_bucket", type=int,
                        help="Set the type of rain bucket. "\
                        "Specify '0' for 0.01 inches; '1' for 0.2 MM; '2' for 0.1 MM",
                        metavar="CODE")
    parser.add_argument("--set_rain_year_start", type=int,
                        choices=[i for i in range(1,13)],
                        help="Set the rain year start (1=Jan, 2=Feb, etc.)",
                        metavar="MM")
    
    # Now we are ready to parse the command line:
    args = parser.parse_args()

    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(args.config_path, file_error=True)
    except IOError:
        print >>sys.stderr, "Unable to open configuration file ", args.config_path
        syslog.syslog(syslog.LOG_CRIT, "main: Unable to open configuration file %s" % args.config_path)
        raise
    except configobj.ConfigObjError:
        print >>sys.stderr, "Error wile parsing configuration file %s" % args.config_path
        syslog.syslog(syslog.LOG_CRIT, "Error while parsing configuration file %s" % args.config_path)
        raise

    syslog.syslog(syslog.LOG_INFO, "Using configuration file %s." % args.config_path)

    # Open up the weather station:
    station = weewx.VantagePro.VantagePro(**config_dict['VantagePro'])

    if args.info:
        info(station)
    if args.clear:
        clear(station)
    if args.set_interval:
        set_interval(station, args.set_interval)
    if args.set_altitude is not None:
        set_altitude(station, args.set_altitude)
    if args.set_barometer is not None:
        set_barometer(station, args.set_barometer)
    if args.set_bucket:
        set_bucket(station, args.set_bucket)
    if args.set_rain_year_start:
        set_rain_year_start(station, args.set_rain_year_start)
           
def info(station):
    """Query the configuration of the VantagePro, printing out status information"""
    
    print "Querying..."
    
    try:
        _firmware_date = station.getFirmwareDate()
    except:
        _firmware_date = "<Unavailable>"
    
    console_time = time.strftime("%x %X", station.getTime())
    
    print  """VantagePro EEPROM settings:
    
    CONSOLE FIRMWARE DATE: %s
    
    CONSOLE SETTINGS:
      Archive interval: %d (seconds)
      Altitude:         %d (%s)
      Wind cup type:    %s
      Rain bucket type: %s
      Rain year start:  %d
      Onboard time:     %s
      
    CONSOLE DISPLAY UNITS:
      Barometer:   %s
      Temperature: %s
      Rain:        %s
      Wind:        %s
      """ % (_firmware_date,
             station.archive_interval, station.elevation, station.elevation_unit,
             station.wind_cup_size, station.rain_bucket_size, station.rain_season_start, console_time,
             station.barometer_unit, station.temperature_unit, 
             station.rain_unit, station.wind_unit)
    
    # Add reception statistics if we can:
    try:
        _rx_list = station.getRX()
        print """    RECEPTION STATS:
      Total packets received:       %d
      Total packets missed:         %d
      Number of resynchronizations: %d
      Longest good stretch:         %d
      Number of CRC errors:         %d
      """ % _rx_list
    except:
        pass

    # Add barometer calibration data if we can.
    try:
        _bar_list = station.getBarData()
        print """    BAROMETER CALIBRATION DATA:
      Current barometer reading:    %.3f inHg
      Altitude:                     %.0f feet
      Dew point:                    %.0f F
      Virtual temperature:          %.0f F
      Humidity correction factor:   %.0f
      Correction ratio:             %.3f
      Correction constant:          %+.3f inHg
      Gain:                         %.3f
      Offset:                       %.3f
      """   % _bar_list
    except:
        pass

def set_interval(station, new_interval_seconds):
    """Set the console archive interval."""
    
    print "Old archive interval is %d seconds, new one will be %d seconds." % (station.archive_interval, new_interval_seconds)
    if station.archive_interval == new_interval_seconds:
        print "Old and new archive intervals are the same. Nothing done."
    else:
        print "Proceeding will change the archive interval as well as erase all old archive records."
        ans = raw_input("Are you sure you want to proceed? (Y/n) ")
        if ans == 'Y' :
            station.setArchiveInterval(new_interval_seconds)
            print "Archive interval now set to %d seconds." % (station.archive_interval,)
            # The Davis documentation implies that the log is cleared after
            # changing the archive interval, but that doesn't seem to be the
            # case. Clear it explicitly:
            station.clearLog()
            print "Archive records cleared."
        else:
            print "Nothing done."
    
def set_altitude(station, altitude_ft):
    """Set the console station elevation"""
    # Hit the console to get the current barometer calibration data:
    _bardata = station.getBarData()
    
    print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (_bardata[0], altitude_ft)
    ans = raw_input("Are you sure you wish to proceed? (Y/n) ")
    if ans == 'Y':
        station.setBarData(_bardata[0], altitude_ft)
    else:
        print "Nothing done."

def set_barometer(station, barometer_inHg):
    """Set the barometer reading to a known correct value."""
    # Hit the console to get the current barometer calibration data:
    _bardata = station.getBarData()
    
    if barometer_inHg:
        print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (barometer_inHg, _bardata[1])
    else:
        print "Proceeding will have the console pick a sensible barometer calibration and set the station altitude to %.1f feet," % (_bardata[1],)
    ans = raw_input("Are you sure you wish to proceed? (Y/n) ")
    if ans == 'Y':
        station.setBarData(barometer_inHg, _bardata[1])
    else:
        print "Nothing done."
    
def clear(station):
    """Clear the archive memory of a VantagePro"""
    
    print "Clearing the archive memory ..."
    print "Proceeding will erase old archive records."
    ans = raw_input("Are you sure you wish to proceed? (Y/n) ")
    if ans == 'Y':
        station.clearLog()
        print "Archive records cleared."
    else:
        print "Nothing done."

def set_bucket(station, new_bucket_type):
    """Set the bucket type on the console."""

    print "Old rain bucket type is %d (%s), new one is %d (%s)." % (station.rain_bucket_type, 
                                                                    station.rain_bucket_size,
                                                                    new_bucket_type, 
                                                                    weewx.VantagePro.VantagePro.rain_bucket_dict[new_bucket_type])
    if station.rain_bucket_type == new_bucket_type:
        print "Old and new bucket types are the same. Nothing done."
    else:
        print "Proceeding will change the rain bucket type."
        ans = raw_input("Are you sure you want to proceed? (Y/n) ")
        if ans == 'Y' :
            station.setBucketType(new_bucket_type)
            print "Bucket type now set to %d." % (station.rain_bucket_type,)
        else:
            print "Nothing done."

def set_rain_year_start(station, rain_year_start):
    print "Old rain season start is %d, new one is %d." % (station.rain_season_start, rain_year_start)

    if station.rain_season_start == rain_year_start:
        print "Old and new rain season starts are the same. Nothing done."
    else:
        print "Proceeding will change the rain season start."
        ans = raw_input("Are you sure you want to proceed? (Y/n) ")
        if ans == 'Y' :
            station.setRainSeasonStart(rain_year_start)
            print "Rain season start now set to %d." % (station.rain_season_start,)
        else:
            print "Nothing done."

if __name__=="__main__" :
    main()
    
