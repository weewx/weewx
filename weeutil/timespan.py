#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
'''
Created on Sep 19, 2009

@author: tkeffer
'''

import weeutil

class TimeSpan(object):
    '''
    Represents a time span, exclusive on the left, inclusive on the right.
    '''

    def __init__(self, start_ts, stop_ts):
        '''
        Initialize a new instance of TimeSpan to the interval start_ts, stop_ts.
        
        start_ts: The starting time stamp of the interval.
        
        stop_ts: The stopping time stamp of the interval
        '''
        
        if start_ts >= stop_ts :
            raise ValueError, "start time must be less than stop time"
        self.start = int(start_ts)
        self.stop  = int(stop_ts)
        
    def includesArchiveTime(self, timestamp):
        """
        Returns True if the span includes the time timestamp, otherwise False.
        
        timestamp: The timestamp to be tested.
        """
        return self.start < timestamp <= self.stop
    
    def includes(self, span):
        
        return self.start <= span.start <= self.stop and self.start <= span.stop <= self.stop
    
    def __eq__(self, other):
        return self.start == other.start and self.stop == other.stop
    
    def __str__(self):
        return "[%s -> %s]" % ( weeutil.timestamp_to_string(self.start),
                                weeutil.timestamp_to_string(self.stop) )
        
    def __hash__(self):
        return hash(self.start) ^ hash(self.stop)
    
    def __cmp__(self, other):
        if self.start < other.start :
            return -1
        return 0 if self.start==other.start else 1

if __name__ == '__main__':
    t = TimeSpan(1230000000, 1231000000)
    print t
    assert(t==t)
    tsub = TimeSpan(1230500000, 1230600000)
    assert(t.includes(tsub))
    assert(not tsub.includes(t))
    tleft = TimeSpan(1229000000, 1229100000)
    assert(not t.includes(tleft))
    tright = TimeSpan(1232000000, 1233000000)
    assert(not t.includes(tright))
    
    dic={}
    dic[t] = 't'
    dic[tsub] = 'tsub'
    dic[tleft] = 'tleft'
    dic[tright] = 'tright'
    
    assert(dic[t] == 't')