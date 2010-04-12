#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Almanac data

"""

import datetime
import time
import Sun
import Moon

class Almanac(object):
    """Almanac data.
    
    time_ts: A timestamp within the date for which sunrise/sunset is desired.
    
    lat, lon: Location for which sunrise/sunset is desired.
    
    moon_phases: An array of 8 strings with descriptions of the moon 
    phase. [optional. If not given, then weeutil.Moon.moon_phases will be used]
    
    timeformat: A strftime style format to be used to format any returned 
    times. [optional. If not given, then "%H:%M" will be used.
    
    Useful attributes, available after initialization:
    
        sunrise_loc_tt: A time tuple containing the time of sunrise in local time.
        
        sunrise: A string version of the above, formatted using the format 'timeformat'
        
        sunset_loc_tt: A time tuple containing the time of sunset in local time.
        
        sunset: A string version of the above, formatted using the format 'timeformat'.
        
        moon_phase: A description of the moon phase(eg. "new moon", Waxing crescent", etc.)
        
        moon_fullness: Percent fullness of the moon (0=new moon, 100=full moon)
    """
    def __init__(self, time_ts, lat, lon, moon_phases = None, timeformat = "%H:%M"):
        self.lat = lat
        self.lon = lon
        self.timeformat = timeformat
        self.date_tt = (0, 0, 0)
        self.sunrise_loc_tt = None
        self.sunset_loc_tt  = None
        self.sunrise = ''
        self.sunset  = ''
        self.moon_phases = moon_phases if moon_phases else Moon.moon_phases
        
        self.moon_phase = ''
        self.moon_fullness = None
        
        self.setTime(time_ts)
        
    def setTime(self, time_ts):
        """Reset the observer's time for the almanac. 
        
        If the date differs from the previous date, then it will
        recalculate the astronomical data.
        
        """
        _newdate_tt = time.localtime(time_ts)
        if _newdate_tt[0:3] != self.date_tt[0:3] :
            (y,m,d) = _newdate_tt[0:3]
            (sunrise_utc, sunset_utc) = Sun.sunRiseSet(y, m, d, self.lon, self.lat)
            # The above function returns its results in UTC hours. Convert
            # to a local time tuple
            self.sunrise_loc_tt = Almanac._adjustTime(y, m, d, sunrise_utc)
            self.sunset_loc_tt  = Almanac._adjustTime(y, m, d, sunset_utc)
            
            self.sunrise = time.strftime(self.timeformat, self.sunrise_loc_tt)
            self.sunset  = time.strftime(self.timeformat, self.sunset_loc_tt)

            (moon_index, self.moon_fullness) = Moon.moon_phase(y, m, d)
            self.moon_phase = self.moon_phases[moon_index] if self.moon_phases is not None else ''
            self.date_tt = _newdate_tt
            

    @staticmethod
    def _adjustTime(y, m, d, hrs_utc):
        """Take a time as y, m, d and floating point hours utc and adjust
        it to a local time. Returns results as a time tuple in local time.
        
        """
        # Subtract off the timezone delta
        hrs_loc = hrs_utc - time.timezone/3600.0
        # Now get the hours, minutes, and seconds
        hours = int(hrs_loc)
        minutes_f = (hrs_loc - hours) * 60.0
        minutes = int(minutes_f)
        seconds = int((minutes_f - minutes) * 60.0 + 0.5)
        # We now have the local y, m, d, hours, minutes, and seconds,
        # but they are in standard time. We need to apply DST, if necessary. The easy
        # way to do that is run it through time.mktime, then convert back to
        # local time:
        time_utc_ts = time.mktime((y, m, d, hours, minutes, seconds, 0, 0, 0))
        time_loc_tt = time.localtime(time_utc_ts)
        # Return the results as a time tuple
        return time_loc_tt
        
        

if __name__ == '__main__':
    day = datetime.datetime(2009, 3, 27)
    day_ts = time.mktime(day.timetuple())
    
    almanac = Almanac(day_ts, 45.5, -122.7)
    
    print almanac.sunrise_loc_tt
    print almanac.sunset_loc_tt
    print almanac.moon_phase
    print almanac.moon_fullness

    # Assert the correct answers, according to NOAA
    assert(almanac.sunrise_loc_tt[3:5] == (6, 59))
    assert(almanac.sunset_loc_tt[3:5] == (19, 32))
    # Assert correct answers according to the navy 
    # (CF: http://aa.usno.navy.mil/data/docs/RS_OneDay.php)
    # Difference from the correct answer (1%) should be less than 1%
    assert(abs(almanac.moon_fullness - 1.0) < 1.0)
    
