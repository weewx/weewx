#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision $
#    $Author$
#    $Date$
#
"""Statistical accumulators"""

import math

class OutOfSpan(ValueError):
    """Raised when a record is outside of a timespan"""

#===============================================================================
#                    Class StdAccum
#===============================================================================
class StdAccum(object):
    """Holds statistics (min, max, avg, etc.) for a type.
    
    For a given type ('outTemp', 'wind', etc.), keeps track of the min and max
    encountered and when. It also keeps a running sum and count, so averages can
    be calculated.""" 

    def __init__(self, obs_type, timespan, stats_tuple=None):
        """Initialize an instance of StdAccum.
        
        obs_type: A string containing the observation type 
        (e.g., 'outTemp', 'rain', etc.)
        
        timespan. The timespan over which the stats are being accumulated. 
        Must not be None

        stats_tuple: An iterable holding the initialization values in the order:
            (min, mintime, max, maxtime, sum, count)
        [Optional. If not given, default values will be used]"""
        self.obs_type = obs_type
        self.timespan = timespan
        (self.min, self.mintime, 
         self.max, self.maxtime, 
         self.sum, self.count) = stats_tuple if stats_tuple else (None, None, None, None, 0.0, 0)
         
    def addToHiLow(self, rec):
        """Add a new record to the running hi/low tally for my type.
        
        rec: A dictionary holding a record. The dictionary keys are
        measurement types (eg 'outTemp') and the values the
        corresponding values. The dictionary must have value
        'dateTime'. It may or may not have my type in it. If it does,
        the value for my type is extracted and used to update my
        high/lows.  If it does not, nothing is done."""
        
        if not self.timespan.includesArchiveTime(rec['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record to hi/low"

        val = rec.get(self.obs_type)
        if val is None :
            # Either the type doesn't exist in this record, or it's bad.
            # Ignore.
            return
        if self.min is None or val < self.min:
            self.min = val
            self.mintime = rec['dateTime']
        if self.max is None or val > self.max:
            self.max = val
            self.maxtime = rec['dateTime']
    
    def addToSum(self, rec):
        """Add a new record to the running sum and count for my type.
        
        rec: A dictionary holding a record. The dictionary keys are
        measurement types (eg 'outTemp') and the values the
        corresponding values. The dictionary may or may not have my
        type in it. If it does, the value for my type is extracted and
        used to update my sum and count. If it does not, nothing is
        done."""

        if not self.timespan.includesArchiveTime(rec['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record to hi/low"

        val = rec.get(self.obs_type)
        if val is None :
            # Either the type doesn't exist in this record, or it's bad.
            # Ignore.
            return
        self.sum += val
        self.count += 1

    @property
    def avg(self):
        return self.sum/self.count if self.count else None
    
    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the
        gathered statistics."""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count)
    

#===============================================================================
#                    Class WindAccum
#===============================================================================

class WindAccum(StdAccum):
    """Specialized version of StdAccum to be used for wind data. 
    
    It includes some extra statistics such as gust direction, rms speeds, etc."""
        
    def __init__(self, obs_type, timespan, stats_tuple=None):
        """Initialize an instance of WindAccum.
        
        obs_type: A string containing the observation type 
        (e.g., 'outTemp', 'rain', etc.)
        
        timespan. The timespan over which the stats are being accumulated. 
        Must not be None

        stats_tuple: An iterable holding the initialization values in the order:
            (min, mintime, max, maxtime, sum, count,
            gustdir, xsum, ysum, squaresum, squarecount)
        [Optional. If not given, default values will be used]"""

        if stats_tuple:
            super(WindAccum, self).__init__(obs_type, timespan, stats_tuple[0:6])
            (self.gustdir, self.xsum, self.ysum,
             self.squaresum, self.squarecount) = stats_tuple[6:11]
        else:
            super(WindAccum, self).__init__(obs_type, timespan)
            self.gustdir = None
            self.xsum = self.ysum = self.squaresum = 0.0
            self.squarecount = 0
            
    def addToHiLow(self, rec):
        """Specialized version for wind data. It differs from
        the standard addToHiLow in that it takes advantage of 
        wind gust data if it's available. It also keeps track
        of the *direction* of the high wind, as well as its time 
        and magnitude."""
        # Sanity check:
        assert(self.obs_type == 'wind')

        if not self.timespan.includesArchiveTime(rec['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record to hi/low"

        # Get the wind speed & direction, breaking them down into vector
        # components.
        v      = rec.get('windSpeed')
        vHi    = rec.get('windGust')
        vHiDir = rec.get('windGustDir')
        if vHi is None:
            # This typically happens because a LOOP packet is being added, which
            # does not have windGust data.
            vHi    = v
            vHiDir = rec.get('windDir')

        if v is not None and (self.min is None or v < self.min):
            self.min = v
            self.mintime = rec['dateTime']
        if vHi is not None and (self.max is None or vHi > self.max):
            self.max = vHi
            self.maxtime = rec['dateTime']
            self.gustdir = vHiDir
    
    def addToSum(self, rec):
        """Specialized version for wind data. It differs from
        the standard addToSum in that it calculates a vector
        average as well."""
        # Sanity check:
        assert(self.obs_type == 'wind')

        if not self.timespan.includesArchiveTime(rec['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record to hi/low"

        # Get the wind speed & direction, breaking them down into vector
        # components.
        speed = rec.get('windSpeed')
        theta = rec.get('windDir')
        if speed is not None:
            self.sum   += speed
            self.count += 1
            # Note that there is no separate 'count' for theta. We use the
            # 'count' for sum. This means if there are
            # a significant number of bad theta's (equal to None), then vecavg
            # could be off slightly.  
            if theta is not None :
                self.xsum      += speed * math.cos(math.radians(90.0 - theta))
                self.ysum      += speed * math.sin(math.radians(90.0 - theta))
    
    def addToRms(self, rec):
        """Add a record to the wind-specific rms stats"""
        # Sanity check:
        assert(self.obs_type == 'wind')

        if not self.timespan.includesArchiveTime(rec['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record to hi/low"

        speed = rec.get('windSpeed')
        if speed is not None:
            self.squaresum   += speed**2
            self.squarecount += 1

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (StdAccum.getStatsTuple(self) +
                (self.gustdir, self.xsum, self.ysum, self.squaresum, self.squarecount))
