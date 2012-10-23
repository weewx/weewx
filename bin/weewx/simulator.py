#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Console simulator for the weewx weather system"""

import math
import time

import weeutil.weeutil
import weewx.abstractstation

def loader(config_dict):

    if config_dict['Simulator'].has_key('start'):
        start_tt = time.strptime(config_dict['Simulator']['start'], "%Y-%m-%d %H:%M")
        start_ts = time.mktime(start_tt)
    else:
        start_ts = None
    station = Simulator(start_ts=start_ts, **config_dict['Simulator'])
    
    return station
        
class Simulator(weewx.abstractstation.AbstractStation):
    """Station simulator"""
    
    def __init__(self, **stn_dict):
        """Initialize the simulator
        
        NAMED ARGUMENTS:
        
        altitude: The altitude in meters. Required.
        
        loop_interval: The time (in seconds) between emitting LOOP packets.
        
        mode: One of either:
            'simulator': Real-time simulator. It will sleep between emitting LOOP packets.
            'generator': Emit packets as fast as it can (useful for testing).
            
        start_ts: The start time in unix epoch time [Optional. Default is to use the present time.]
        """

        self.mode = stn_dict['mode']
        self.loop_interval = stn_dict.get('loop_interval', 2.5)
        self.start_ts = stn_dict.get('start_ts')
        self.the_time = self.start_ts if self.start_ts else time.time()
        
        sod = weeutil.weeutil.startOfDay(self.the_time)
                
        self.observations = {'outTemp'   : Observation(magnitude=20.0, average=50.0, period=24.0, phase_lag=14.0, start=sod),
                             'inTemp'    : Observation(magnitude=5.0,  average=68.0, period=24.0, phase_lag=12.0, start=sod),
                             'barometer' : Observation(magnitude=1.0,  average=30.1, period=96.0, phase_lag=48.0, start=sod)}

    def genLoopPackets(self):

        while True:
            _packet = {'dateTime': int(self.the_time+0.5)}
            for obs_type in self.observations:
                _packet[obs_type] = self.observations[obs_type].value_at(self.the_time)
            yield _packet

            if self.mode == 'simulator':
                if self.start_ts:
                    # A start time was specified, so we are not in realtime. Just sleep
                    # the appropriate interval
                    time.sleep(self.loop_interval)
                    self.the_time += self.loop_interval
                else:
                    # No start time was specified, so we are in real time. Try to keep
                    # synched up with the wall clock
                    time.sleep(self.the_time + self.loop_interval - time.time())
                    self.the_time = time.time()
            elif self.mode == 'generator':
                self.the_time += self.loop_interval
                
                
    def getTime(self):
        return self.the_time
    
    def setTime(self, newtime_ts):
        self.the_time = newtime_ts
        
    @property
    def hardware_name(self):
        return "Simulator"
        
class Observation(object):
    
    def __init__(self, magnitude=1.0, average=0.0, period=96.0, phase_lag=0.0, start=None):
        """Initialize an observation function.
        
        magnitude: The value at max. The range will be twice this value
        average: The average value, averaged over a full cycle.
        period: The cycle period in hours.
        phase_lag: The number of hours after the start time when the observation hits its max
        start: Time zero for the observation in unix epoch time."""
         
        self.magnitude = magnitude
        self.average = average
        self.period = period * 3660.0
        self.phase_lag = phase_lag * 3660.0
        self.start = start
        
    def value_at(self, time_ts):
        """Return the observation value at the given time.
        
        time_ts: The time in unix epoch time."""

        phase = 2.0 * math.pi * (time_ts - self.start - self.phase_lag) / self.period
        return self.magnitude * math.cos(phase) + self.average
        



if __name__ == "__main__":

    station = Simulator(mode='generator',loop_interval=2.0)
    for packet in station.genLoopPackets():
        print weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet
        
    