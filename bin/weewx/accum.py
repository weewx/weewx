#
#    Copyright (c) 2009, 2010, 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision $
#    $Author$
#    $Date$
#
"""Statistical accumulators. They accumulate the highs, lows, averages,
etc., of a sequence of records."""

import math

class OutOfSpan(ValueError):
    """Raised when attempting to add a record outside of the timespan held by an accumulator"""

class ScalarStats(object):
    """Accumulates statistics (min, max, average, etc.) for a scalar value."""    
    def __init__(self, stats_tuple=None):
        (self.min, self.mintime, 
         self.max, self.maxtime, 
         self.sum, self.count) = stats_tuple if stats_tuple else (None, None, None, None, 0.0, 0)
         
    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics.
        This tuple can be used to update the stats database"""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count)
    
    def mergeHiLo(self, x_stats):
        """Merge the highs and lows of another accumulator into myself."""
        if x_stats.min is not None:
            if self.min is None or x_stats.min < self.min:
                self.min     = x_stats.min
                self.mintime = x_stats.mintime
        if x_stats.max is not None:
            if self.max is None or x_stats.max > self.max:
                self.max     = x_stats.max
                self.maxtime = x_stats.maxtime

    def mergeSum(self, x_stats):
        """Merge the sum and count of another accumulator into myself."""
        self.sum   += x_stats.sum
        self.count += x_stats.count

    def addHiLo(self, val, ts):
        """Include a scalar value in my highs and lows.
        val: A scalar value
        ts:  The timestamp.
        """
        if val is not None:
            if self.min is None or val < self.min:
                self.min     = val
                self.mintime = ts
            if self.max is None or val > self.max:
                self.max     = val
                self.maxtime = ts

    def addSum(self, val):
        """Add a scalar value to my running sum and count."""
        if val is not None:
            self.sum   += val
            self.count += 1
        
    @property
    def avg(self):
        return self.sum / self.count if self.count else None

class VecStats(object):
    """Accumulates statistics for a vector value."""
    def __init__(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.max_dir, self.xsum, self.ysum, 
         self.squaresum, self.squarecount) = stats_tuple if stats_tuple else (None, None, None, None, 0.0, 0,
                                                                              None, 0.0, 0.0, 0.0, 0)

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count,
                self.max_dir, self.xsum, self.ysum, self.squaresum, self.squarecount)

    def mergeHiLo(self, x_stats):
        if x_stats.min is not None:
            if self.min is None or x_stats.min < self.min:
                self.min     = x_stats.min
                self.mintime = x_stats.mintime
        if x_stats.max is not None:
            if self.max is None or x_stats.max > self.max:
                self.max     = x_stats.max
                self.maxtime = x_stats.maxtime
                self.max_dir = x_stats.max_dir

    def mergeSum(self, x_stats):
        self.sum         += x_stats.sum
        self.count       += x_stats.count
        self.xsum        += x_stats.xsum
        self.ysum        += x_stats.ysum
        self.squaresum   += x_stats.squaresum
        self.squarecount += x_stats.squarecount
        
    def addHiLo(self, speed, dirN, ts):
        if speed is not None:
            if self.min is None or speed < self.min:
                self.min = speed
                self.mintime = ts
            if self.max is None or speed > self.max:
                self.max = speed
                self.maxtime = ts
                self.max_dir = dirN
        
    def addSum(self, speed, dirN):
        if speed is not None:
            self.sum         += speed
            self.count       += 1
            self.squaresum   += speed**2
            if dirN is not None :
                self.xsum += speed * math.cos(math.radians(90.0 - dirN))
                self.ysum += speed * math.sin(math.radians(90.0 - dirN))
                self.squarecount += 1
            
    @property
    def avg(self):
        return self.sum / self.count if self.count else None

    @property
    def vec_avg(self):
        if self.count:
            return math.sqrt((self.xsum**2 + self.ysum**2) / self.count**2)

    @property
    def vec_dir(self):
        if self.squarecount:
            _result = 90.0 - math.degrees(math.atan2(self.ysum, self.xsum))
            if _result < 0.0:
                _result += 360.0
            return _result
        
class DictAccum(dict):
    """Accumulates statistics for a set of observation types."""
    def __init__(self, timespan):
        
        self.timespan = timespan
        # The unit system is left unspecified until the first observation comes in.
        self.unit_system = None
        
    def addRecord(self, record):
        """Add a record to my running statistics. 
        
        record: A dictionary with key observation type (eg, 'outTemp'),
        and value the observation value (eg, 75.2). Either LOOP packets
        or archive records satisfy this requirement."""
        
        # Check to see if the record is within my observation timespan 
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record"

        # For each type...
        for obs_type in record:
            if obs_type in ['dateTime', 'windDir', 'windGust', 'windGustDir']:
                continue
            elif obs_type=='windSpeed':
                self.initStats('wind')
                self['wind'].addHiLo(record['windSpeed'], record.get('windDir'), record['dateTime'])
                self['wind'].addHiLo(record.get('windGust'), record.get('windGustDir'), record['dateTime'])
                self['wind'].addSum(record['windSpeed'], record.get('windDir'))
            elif obs_type=='usUnits':
                self._check_units(record['usUnits'])
            else:
                # Most observation types end up here. If the type has
                # not been seen before, initialize it
                self.initStats(obs_type)
                self[obs_type].addHiLo(record[obs_type], record['dateTime'])
                self[obs_type].addSum(record[obs_type])
                
    def updateHiLo(self, accumulator):
        """Merge the stats of another accumulator into me."""
        if accumulator.timespan.start < self.timespan.start or accumulator.timespan.stop > self.timespan.stop:
            raise OutOfSpan("Attempt to merge an accumulator whose timespan is not a subset")

        self._check_units(accumulator.unit_system)
        
        for obs_type in accumulator:
            self.initStats(obs_type)
            self[obs_type].mergeHiLo(accumulator[obs_type])
                    
    def getRecord(self):
        """Extract a record out of the results in the accumulator."""
        # All records have a timestamp and unit type
        record = {'dateTime': self.timespan.stop,
                  'usUnits' : self.unit_system}
        # Go through all observation types.
        for obs_type in self:
            if obs_type == 'wind':
                # Wind records must be flattened into the separate categories:
                record['windSpeed']   = self[obs_type].avg
                record['windDir']     = self[obs_type].vec_dir
                record['windGust']    = self[obs_type].max
                record['windGustDir'] = self[obs_type].max_dir
            elif obs_type == 'rain':
                # We need total rain during the timespan, not the average:
                record['rain']        = self[obs_type].sum
            elif obs_type in ['hourRain', 'dayRain', 'totalRain']:
                # This assumes no reset happened in the archive period:
                record[obs_type]      = self[obs_type].max
            else:
                # For most observations, we want the average seen
                # during the timespan:
                record[obs_type]      = self[obs_type].avg
        return record
            
    def initStats(self, obs_type, stats_tuple=None):
        # Do nothing for these types.
        if obs_type in ['dateTime', 'windDir', 'windGust', 'windGustDir'] or obs_type in self:
            return
        if obs_type == 'wind':
            # Observation 'wind' requires a special vector accumulator
            self['wind'] = VecStats(stats_tuple)
        else:
            # All others use a scalar accumulator:
            self[obs_type] = ScalarStats(stats_tuple)
    
    def _check_units(self, other_system):

        # If no unit system has been specified for me yet,
        # adopt the other system        
        if self.unit_system is None:
            self.unit_system = other_system
        else:
            # Otherwise, make sure they match
            if self.unit_system != other_system:
                raise ValueError("Unit system mismatch %d v. %d" % (self.unit_system, other_system))


