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
"""Command line utility for configuring the Davis Vantage series of weather stations"""

import optparse
import syslog
import sys
import time

import configobj

import weewx.VantagePro
import weeutil.weeutil

description = """Configures the Davis Vantage weather station."""

usage="""%prog: config_path [--help] [--info] [--clear] [--set-interval=SECONDS] [--set-altitude=FEET]
                            [--set-barometer=inHg] [--set-bucket=CODE] [--set-rain-year-start=MM] [--set-time]
                            [--start | --stop]"""

epilog = """Mutating actions will request confirmation before proceeding."""

def main():

    # Set defaults for the system logger:
    syslog.openlog('config_vp', syslog.LOG_PID|syslog.LOG_CONS)

    # Create a command line parser:
    parser = optparse.OptionParser(description=description, usage=usage, epilog=epilog)
    
    # Add the various options:
    parser.add_option("--info", action="store_true", dest="info",
                        help="To print configuration, reception, and barometer calibration information about your weather station.")
    parser.add_option("--clear", action="store_true", dest="clear",
                        help="To clear the memory of your weather station.")
    parser.add_option("--set-interval", type=int, dest="set_interval", metavar="SECONDS",
                        help="Sets the archive interval to the specified number of seconds. "\
                        "Valid values are 60, 300, 600, 900, 1800, 3600, or 7200.")
    parser.add_option("--set-altitude", type=float, dest="set_altitude", metavar="FEET",
                        help="Sets the altitude of the station to the specified number of feet.") 
    parser.add_option("--set-barometer", type=float, dest="set_barometer", metavar="inHg",
                        help="Sets the barometer reading of the station to a known correct value in inches of mercury. "\
                        "Specify 0 (zero) to have the console pick a sensible value.")
    parser.add_option("--set-bucket", type=int, dest="set_bucket", metavar="CODE",
                        help="Set the type of rain bucket. "\
                        "Specify '0' for 0.01 inches; '1' for 0.2 MM; '2' for 0.1 MM")
    parser.add_option("--set-rain-year-start", type=int, dest="set_rain_year_start", metavar="MM", 
                        help="Set the rain year start (1=Jan, 2=Feb, etc.).")
    parser.add_option("--set-time", action="store_true", dest="set_time", help="Set the onboard clock to the current time.")
    parser.add_option("--start", action="store_true", help="Start the logger.")
    parser.add_option("--stop",  action="store_true", help="Stop the logger.")
    
    # Now we are ready to parse the command line:
    (options, args) = parser.parse_args()
    if not args:
        parser.error("Missing configuration file.")
        
    if options.start and options.stop:
        parser.error("Cannot specify both --start and --stop")

    config_path = args[0]
    
    # Try to open up the configuration file. Declare an error if unable to.
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print >>sys.stderr, "Unable to open configuration file ", config_path
        syslog.syslog(syslog.LOG_CRIT, "Unable to open configuration file %s" % config_path)
        exit(1)
    except configobj.ConfigObjError:
        print >>sys.stderr, "Error wile parsing configuration file %s" % config_path
        syslog.syslog(syslog.LOG_CRIT, "Error while parsing configuration file %s" % config_path)
        exit(1)

    syslog.syslog(syslog.LOG_INFO, "Using configuration file %s." % config_path)

    # Open up the weather station:
    station = weewx.VantagePro.Vantage(**config_dict['Vantage'])

    if options.info:
        info(station)
    if options.clear:
        clear(station)
    if options.set_interval is not None:
        set_interval(station, options.set_interval)
    if options.set_altitude is not None:
        set_altitude(station, options.set_altitude)
    if options.set_barometer is not None:
        set_barometer(station, options.set_barometer)
    if options.set_bucket is not None:
        set_bucket(station, options.set_bucket)
    if options.set_rain_year_start is not None:
        set_rain_year_start(station, options.set_rain_year_start)
    if options.set_time:
        set_time(station)
    if options.start:
        start_logger(station)
    if options.stop:
        stop_logger(station)
           
def info(station):
    """Query the configuration of the Vantage, printing out status information"""
    
    print "Querying..."
    
    try:
        _firmware_date = station.getFirmwareDate()
    except Exception:
        _firmware_date = "<Unavailable>"
        
    try:
        _firmware_version = station.getFirmwareVersion()
    except Exception:
        _firmware_version = '<Unavailable>'
    
    console_time = station.getConsoleTime()
    
    print  """Davis Vantage EEPROM settings:
    
    CONSOLE TYPE:                   %s
    
    CONSOLE FIRMWARE:
      Date:                         %s
      Version:                      %s
    
    CONSOLE SETTINGS:
      Archive interval:             %d (seconds)
      Altitude:                     %d (%s)
      Wind cup type:                %s
      Rain bucket type:             %s
      Rain year start:              %d
      Onboard time:                 %s
      
    CONSOLE DISPLAY UNITS:
      Barometer:                    %s
      Temperature:                  %s
      Rain:                         %s
      Wind:                         %s
      """ % (station.hardware_name, _firmware_date, _firmware_version,
             station.archive_interval, station.altitude, station.altitude_unit,
             station.wind_cup_size, station.rain_bucket_size, station.rain_year_start, console_time,
             station.barometer_unit, station.temperature_unit, 
             station.rain_unit, station.wind_unit)
    try:
        (stnlat, stnlon, time_zone, man_or_auto, dst, gmt_offset, gmt_or_zone) = station.getStnInfo()
        print """    CONSOLE STATION INFO:
      Latitude (onboard):           %0.1f
      Longitude (onboard):          %0.1f
      Time zone code:               %s
      Use manual or auto DST?       %s
      DST setting:                  %s
      GMT offset:                   %+.1f hours
      Use GMT offset or time zone?  %s
        """ % (stnlat, stnlon, time_zone, man_or_auto, dst, gmt_offset, gmt_or_zone)
    except:
        pass
    
    
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
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will change the archive interval as well as erase all old archive records."
            ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if ans == 'y' :
                try:
                    station.setArchiveInterval(new_interval_seconds)
                except StandardError, e:
                    print >>sys.stderr, "Unable to set new archive interval. Reason:\n\t****", e
                else:
                    print "Archive interval now set to %d seconds." % (station.archive_interval,)
                    # The Davis documentation implies that the log is cleared after
                    # changing the archive interval, but that doesn't seem to be the
                    # case. Clear it explicitly:
                    station.clearLog()
                    print "Archive records cleared."
            elif ans == 'n':
                print "Nothing done."
    
def set_altitude(station, altitude_ft):
    """Set the console station altitude"""
    # Hit the console to get the current barometer calibration data:
    _bardata = station.getBarData()

    ans = None
    while ans not in ['y', 'n']:    
        print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (_bardata[0], altitude_ft)
        ans = raw_input("Are you sure you wish to proceed (y/n)? ")
        if ans == 'y':
            station.setBarData(_bardata[0], altitude_ft)
        elif ans == 'n':
            print "Nothing done."

def set_barometer(station, barometer_inHg):
    """Set the barometer reading to a known correct value."""
    # Hit the console to get the current barometer calibration data:
    _bardata = station.getBarData()
    
    ans = None
    while ans not in ['y', 'n']:
        if barometer_inHg:
            print "Proceeding will set the barometer value to %.3f and the station altitude to %.1f feet." % (barometer_inHg, _bardata[1])
        else:
            print "Proceeding will have the console pick a sensible barometer calibration and set the station altitude to %.1f feet," % (_bardata[1],)
        ans = raw_input("Are you sure you wish to proceed (y/n)? ")
        if ans == 'y':
            station.setBarData(barometer_inHg, _bardata[1])
        elif ans == 'n':
            print "Nothing done."
    
def clear(station):
    """Clear the archive memory of a VantagePro"""
    
    ans = None
    while ans not in ['y', 'n']:
        print "Clearing the archive memory ..."
        print "Proceeding will erase old archive records."
        ans = raw_input("Are you sure you wish to proceed (y/n)? ")
        if ans == 'y':
            station.clearLog()
            print "Archive records cleared."
        elif ans == 'n':
            print "Nothing done."

def set_bucket(station, new_bucket_type):
    """Set the bucket type on the console."""

    print "Old rain bucket type is %d (%s), new one is %d (%s)." % (station.rain_bucket_type, 
                                                                    station.rain_bucket_size,
                                                                    new_bucket_type, 
                                                                    weewx.VantagePro.Vantage.rain_bucket_dict[new_bucket_type])
    if station.rain_bucket_type == new_bucket_type:
        print "Old and new bucket types are the same. Nothing done."
    else:
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will change the rain bucket type."
            ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if ans == 'y' :
                try:
                    station.setBucketType(new_bucket_type)
                except StandardError, e:
                    print >>sys.stderr, "Unable to set new bucket type. Reason:\n\t****", e
                else:
                    print "Bucket type now set to %d." % (station.rain_bucket_type,)
            elif ans == 'n':
                print "Nothing done."

def set_rain_year_start(station, rain_year_start):
        
    print "Old rain season start is %d, new one is %d." % (station.rain_year_start, rain_year_start)

    if station.rain_year_start == rain_year_start:
        print "Old and new rain season starts are the same. Nothing done."
    else:
        ans = None
        while ans not in ['y', 'n']:
            print "Proceeding will change the rain season start."
            ans = raw_input("Are you sure you want to proceed (y/n)? ")
            if ans == 'y' :
                try:
                    station.setRainYearStart(rain_year_start)
                except StandardError, e:
                    print >>sys.stderr, "Unable to set new rain year start. Reason:\n\t****", e
                else:
                    print "Rain year start now set to %d." % (station.rain_year_start,)
            elif ans == 'n':
                print "Nothing done."

def set_time(station):
    print "Setting time on console..."
    station.setTime(time.time())
    newtime_ts = station.getTime()
    print "Current console time is %s" % weeutil.weeutil.timestamp_to_string(newtime_ts)

def start_logger(station):
    print "Starting logger ..."
    station.startLogger()
    print "Logger started"
    
def stop_logger(station):
    print "Stopping logger ..."
    station.stopLogger()
    print "Logger stopped"
    
if __name__=="__main__" :
    main()
