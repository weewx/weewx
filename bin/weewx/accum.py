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
         
    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime, self.max, self.maxtime, self.sum, self.count)
    
    def mergeHiLo(self, x_stats):
        if x_stats.min is not None:
            if self.min is None or x_stats.min < self.min:
                self.min     = x_stats.min
                self.mintime = x_stats.mintime
        if x_stats.max is not None:
            if self.max is None or x_stats.max > self.max:
                self.max     = x_stats.max
                self.maxtime = x_stats.maxtime

    def mergeSum(self, x_stats):
        self.sum   += x_stats.sum
        self.count += x_stats.count

    def addHiLo(self, val, ts):
        if val is not None:
            if self.min is None or val < self.min:
                self.min     = val
                self.mintime = ts
            if self.max is None or val > self.max:
                self.max     = val
                self.maxtime = ts

    def addSum(self, val):
        if val is not None:
            self.sum += val
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
        
    def addHiLo(self, val, ts):
        (speed, dirN) = val
        if speed is not None:
            if self.min is None or speed < self.min:
                self.min = speed
                self.mintime = ts
            if self.max is None or speed > self.max:
                self.max = speed
                self.maxtime = ts
                self.max_dir = dirN
        
    def addSum(self, val):
        (speed, dirN) = val
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
        
    def addRecord(self, record):
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record"

        for obs_type in record:
            if obs_type=='dateTime':
                continue
            if obs_type=='windGust':
                self.initStats('wind')
                self['wind'].addHiLo(record['windGust'], record['dateTime'])
            else:
                self.initStats(obs_type)
                self[obs_type].addHiLo(record[obs_type], record['dateTime'])
                self[obs_type].addSum(record[obs_type])
                
    def mergeStats(self, accumulator):
        """Merge the stats of another accumulator into me."""
        if accumulator.timespan.start < self.timespan.start or accumulator.timespan.stop > self.timespan.stop:
            raise OutOfSpan("Attempt to merge an accumulator whose timespan is not a subset")

        for obs_type in accumulator:
            self.initStats(obs_type)
            self[obs_type].mergeHiLo(accumulator[obs_type])
                    
    def getRecord(self):
        
        record = {'dateTime': self.timespan.stop}
        for obs_type in self:
            record[obs_type] = self[obs_type].avg
            if obs_type == 'wind':
                record['windDir']     = self[obs_type].vec_dir
                record['windGust']    = self[obs_type].max
                record['windGustDir'] = self[obs_type].max_dir
        return record
            
    def initStats(self, obs_type, stats_tuple=None):
        # 
        if obs_type in ['dateTime', 'windGust'] or obs_type in self:
            return
        if obs_type == 'wind':
            self[obs_type] = VecStats(stats_tuple)
        else:
            self[obs_type] = ScalarStats(stats_tuple)
    