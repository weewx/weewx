#
#    Copyright (c) 2009, 2010, 2012 Tom Keffer <tkeffer@gmail.com>
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
    """Raised when attempting to add a record outside of the timespan held by an accumulator"""

class ScalarStats(object):
    """Accumulates statistics (min, max, average, etc.) for a scalar value."""    
    def __init__(self, stats_tuple=None):
        (self.min, self.mintime, 
         self.max, self.maxtime, 
         self.sum, self.count) = stats_tuple if stats_tuple else (None, None, None, None, 0.0, 0)
         
    @property
    def avg(self):
        return self.sum / self.count if self.count else None

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count)

class VecStats(object):
    """Accumulates statistics for a vector value."""
    def __init__(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.vecMaxDir, self.xsum, self.ysum, 
         self.squaresum, self.squarecount) = stats_tuple if stats_tuple else (None, None, None, None, 0.0, 0,
                                                                              None, 0.0, 0.0, 0.0, 0)

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count,
                self.vecMaxDir, self.xsum, self.ysum, self.squaresum, self.squarecount)

class DictAccum(dict):
    """Accumulates statistics for a set of observation types."""
    def __init__(self, timespan):
        self.timespan = timespan
        
    def initObservation(self, obs_type, stats_tuple):
        # An exception will get thrown if the stats_tuple is of the wrong length. 
        # First try a scalar:
        try:
            self[obs_type] = ScalarStats(stats_tuple)
        except ValueError:
            # That didn't work. Assume it's a vector.
            self[obs_type] = VecStats(stats_tuple)
        
    def addRecord(self, record):
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record"

        for obs_type in record:
            if obs_type=='dateTime':
                continue
            if obs_type not in self:
                # The observation type does not exist in me yet. Initialize a new stats holder.
                # But, which type? Scalar or vector? 
                try:
                    # Test whether the observation is indexable, which would indicate
                    # it's a tuple holding (magnitude, direction).
                    record[obs_type][0]
                except TypeError:
                    # We got a TypeError. It must be a simple scalar.
                    self[obs_type] = ScalarStats()
                else:
                    # Well, that worked. It must be a vector.
                    self[obs_type] = VecStats()
            try:
                self._addVector(record, obs_type)
            except TypeError:
                self._addScalar(record, obs_type)
                
    def mergeStats(self, accumulator):
        """Merge the stats of another accumulator into me."""
        if accumulator.timespan.start < self.timespan.start or accumulator.timespan.stop > self.timespan.stop:
            raise OutOfSpan("Attempt to merge an accumulator whose timespan is not a subset")

        for obs_type in accumulator:
            if self[obs_type].min is None or accumulator[obs_type].min < self[obs_type].min:
                self[obs_type].min = accumulator[obs_type].min
                self[obs_type].mintime = accumulator[obs_type].mintime
                
                blah, blah!
                
    def getRecord(self):
        
        record = {}
        for obs_type in self:
            # TODO: What about 'wind'?
            record[obs_type] = self[obs_type].avg
            
    def _addVector(self, record, obs_type):
        (speed, theta) = record[obs_type]
        if speed is None:
            return
        if self[obs_type].min is None or speed < self[obs_type].min:
            self[obs_type].min = speed
            self[obs_type].mintime = record['dateTime']
        if self[obs_type].max is None or speed > self[obs_type].max:
            self[obs_type].max = speed
            self[obs_type].maxtime = record['dateTime']
            self[obs_type].vecMaxDir = theta
        # This is a bit of a cludge and requires special knowledge of the observation types:
        if obs_type != 'windGust':
            self[obs_type].sum         += speed
            self[obs_type].count       += 1
            self[obs_type].squaresum   += speed**2
            self[obs_type].squarecount += 1
            # Note that there is no separate 'count' for theta. We use the
            # 'count' for sum. This means if there are
            # a significant number of bad theta's (equal to None), then vecavg
            # could be off slightly.  
            if theta is not None :
                self[obs_type].xsum += speed * math.cos(math.radians(90.0 - theta))
                self[obs_type].ysum += speed * math.sin(math.radians(90.0 - theta))

    def _addScalar(self, record, obs_type):
        v = record[obs_type]
        if v is None:
            return
        if self[obs_type].min is None or v < self[obs_type].min:
            self[obs_type].min = v
            self[obs_type].mintime = record['dateTime']
        if self[obs_type].max is None or v > self[obs_type].max:
            self[obs_type].max = v
            self[obs_type].maxtime = record['dateTime']
        self[obs_type].sum   += v
        self[obs_type].count += 1

