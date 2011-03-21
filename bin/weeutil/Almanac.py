#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Almanac data"""

import datetime
import calendar
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
    def _adjustTime(y, m, d,  hrs_utc):
        """Converts from a UTC time to a local time.
        
        y,m,d: The year, month, day for which the conversion is desired.
        
        hrs_tc: Floating point number with the number of hours since midnight in UTC.
        
        Returns: A timetuple with the local time."""
        # Construct a time tuple with the time at midnight, UTC:
        daystart_utc_tt = (y,m,d,0,0,0,0,0,-1)
        # Convert the time tuple to a time stamp and add on the number of seconds since midnight:
        time_ts = int(calendar.timegm(daystart_utc_tt) + hrs_utc * 3600.0 + 0.5)
        # Convert to local time:
        time_local_tt = time.localtime(time_ts)
        return time_local_tt

if __name__ == '__main__':
    # NB: DST is on for 27-Mar-2009
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
    
