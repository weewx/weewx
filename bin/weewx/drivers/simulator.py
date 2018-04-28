#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Console simulator for the weewx weather system"""

from __future__ import with_statement
import math
import time
import random

import weedb
import weewx.drivers
import weeutil.weeutil

DRIVER_NAME = 'Simulator'
DRIVER_VERSION = "4.0"

def loader(config_dict, engine):

    # This loader uses a bit of a hack to have the simulator resume at a later
    # time. It's not bad, but I'm not enthusiastic about having special
    # knowledge about the database in a driver, albeit just the loader.

    start_ts = resume_ts = None
    if 'start' in config_dict[DRIVER_NAME]:
        # A start has been specified. Extract the time stamp.
        start_tt = time.strptime(config_dict[DRIVER_NAME]['start'], "%Y-%m-%dT%H:%M")        
        start_ts = time.mktime(start_tt)
        # If the 'resume' keyword is present and True, then get the last
        # archive record out of the database and resume with that.
        if weeutil.weeutil.to_bool(config_dict[DRIVER_NAME].get('resume', False)):
            import weewx.manager
            try:
                # Resume with the last time in the database. If there is no such
                # time, then fall back to the time specified in the configuration
                # dictionary.
                with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as dbmanager:
                        resume_ts = dbmanager.lastGoodStamp()
            except weedb.OperationalError:
                pass
        else:
            # The resume keyword is not present. Start with the seed time:
            resume_ts = start_ts
            
    station = Simulator(start_time=start_ts, resume_time=resume_ts, **config_dict[DRIVER_NAME])
    
    return station
        
class Simulator(weewx.drivers.AbstractDevice):
    """Station simulator"""
    
    def __init__(self, **stn_dict):
        """Initialize the simulator
        
        NAMED ARGUMENTS:
        
        loop_interval: The time (in seconds) between emitting LOOP packets.
        [Optional. Default is 2.5]
        
        start_time: The start (seed) time for the generator in unix epoch time
        [Optional. If 'None', or not present, then present time will be used.]

        resume_time: The start time for the loop.
        [Optional. If 'None', or not present, then start_time will be used.]
        
        mode: Controls the frequency of packets.  One of either:
            'simulator': Real-time simulator - sleep between LOOP packets
            'generator': Emit packets as fast as possible (useful for testing)
        [Required. Default is simulator.]

        observations: Comma-separated list of observations that should be
                      generated.  If nothing is specified, then all
                      observations will be generated.
        [Optional. Default is not defined.]
        """

        self.loop_interval = float(stn_dict.get('loop_interval', 2.5))
        if 'start_time' in stn_dict and stn_dict['start_time'] is not None:
            # A start time has been specified. We are not in real time mode.
            self.real_time = False
            # Extract the generator start time:
            start_ts = float(stn_dict['start_time'])
            # If a resume time keyword is present (and it's not None), 
            # then have the generator resume with that time.
            if 'resume_time' in stn_dict and stn_dict['resume_time'] is not None:
                self.the_time = float(stn_dict['resume_time'])
            else:
                self.the_time = start_ts
        else:
            # No start time specified. We are in realtime mode.
            self.real_time = True
            start_ts = self.the_time = time.time()

        # default to simulator mode
        self.mode = stn_dict.get('mode', 'simulator')

        # whether to generate spikes
        spike = float(stn_dict.get('spike', 0))
        Spike.start_ts = start_ts
        
        # The following doesn't make much meteorological sense, but it is
        # easy to program!
        self.observations = {
            'outTemp'    : Observation(magnitude=20.0,  average= 50.0, period=24.0, phase_lag=14.0, start=start_ts, spike=spike),
            'inTemp'     : Observation(magnitude=5.0,   average= 68.0, period=24.0, phase_lag=12.0, start=start_ts, spike=spike),
            'barometer'  : Observation(magnitude=1.0,   average= 30.1, period=48.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'pressure'   : Observation(magnitude=1.0,   average= 30.1, period=48.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'windSpeed'  : Observation(magnitude=5.0,   average=  5.0, period=48.0, phase_lag=24.0, start=start_ts, spike=spike),
            'windDir'    : Observation(magnitude=180.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'windGust'   : Observation(magnitude=6.0,   average=  6.0, period=48.0, phase_lag=24.0, start=start_ts, spike=spike),
            'windGustDir': Observation(magnitude=180.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'outHumidity': Observation(magnitude=30.0,  average= 50.0, period=48.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'inHumidity' : Observation(magnitude=10.0,  average= 20.0, period=24.0, phase_lag= 0.0, start=start_ts, spike=spike),
            'radiation'  : Solar(magnitude=1000, solar_start=6, solar_length=12, spike=spike),
            'UV'         : Solar(magnitude=14,   solar_start=6, solar_length=12, spike=spike),
            'rain'       : Rain(rain_start=0, rain_length=3, total_rain=0.2, loop_interval=self.loop_interval, spike=spike),
            }

        # calculate only the specified observations, or all if none specified
        if 'observations' in stn_dict and stn_dict['observations'] is not None:
            desired = [x.strip() for x in stn_dict['observations'].split(',')]
            for obs in self.observations:
                if obs not in desired:
                    del self.observations[obs]

    def genLoopPackets(self):

        while True:

            # If we are in simulator mode, sleep first (as if we are gathering
            # observations). If we are in generator mode, don't sleep at all.
            if self.mode == 'simulator':
                # Determine how long to sleep
                if self.real_time:
                    # We are in real time mode. Try to keep synched up with the
                    # wall clock
                    sleep_time = self.the_time + self.loop_interval - time.time()
                    if sleep_time > 0: 
                        time.sleep(sleep_time)
                else:
                    # A start time was specified, so we are not in real time.
                    # Just sleep the appropriate interval
                    time.sleep(self.loop_interval)

            # Update the simulator clock:
            self.the_time += self.loop_interval
            
            # Because a packet represents the measurements observed over the
            # time interval, we want the measurement values at the middle
            # of the interval.
            avg_time = self.the_time - self.loop_interval/2.0
            
            _packet = {'dateTime': int(self.the_time+0.5),
                       'usUnits' : weewx.US }
            for obs_type in self.observations:
                _packet[obs_type] = self.observations[obs_type].value_at(avg_time)
            yield _packet

    def getTime(self):
        return self.the_time
    
    @property
    def hardware_name(self):
        return "Simulator"
        
class Observation(object):
    
    def __init__(self, magnitude=1.0, average=0.0, period=96.0, phase_lag=0.0, start=None, spike=0):
        """Initialize an observation function.
        
        magnitude: The value at max. The range will be twice this value
        average: The average value, averaged over a full cycle.
        period: The cycle period in hours.
        phase_lag: The number of hours after the start time when the
                     observation hits its max
        start: Time zero for the observation in unix epoch time.
        spike: Whether to generate spikes. A non-zero value generates 
                     spikes at the spike value times the magintude"""
         
        if not start:
            raise ValueError("No start time specified")
        self.magnitude = magnitude
        self.average   = average
        self.period    = period * 3600.0
        self.phase_lag = phase_lag * 3600.0
        self.start     = start
        self.spike     = Spike(magnitude * spike, period) 
        
    def value_at(self, time_ts):
        """Return the observation value at the given time.
        
        time_ts: The time in unix epoch time."""

        phase = 2.0 * math.pi * (time_ts - self.start - self.phase_lag) / self.period
        return self.magnitude * math.cos(phase) + self.average + self.spike.spike(time_ts)

class Rain(object):
    
    bucket_tip = 0.01

    def __init__(self, rain_start=0, rain_length=1, total_rain=0.1, loop_interval=None, spike=0):
        """Initialize a rain simulator"""
        npackets = 3600 * rain_length / loop_interval
        n_rain_packets = total_rain / Rain.bucket_tip
        self.period = int(npackets/n_rain_packets)
        self.rain_start = 3600* rain_start
        self.rain_end = self.rain_start + 3600 * rain_length
        self.packet_number = 0
        # Will generate spikes per rain_length period even when not in a rain period
        self.spike = Spike(total_rain * spike, rain_length)
        
    def value_at(self, time_ts):
        time_tt = time.localtime(time_ts)
        secs_since_midnight = time_tt.tm_hour * 3600 + time_tt.tm_min * 60.0 + time_tt.tm_sec
        if self.rain_start < secs_since_midnight <= self.rain_end:
            amt = Rain.bucket_tip if self.packet_number % self.period == 0 else 0.0
            self.packet_number += 1
        else:
            self.packet_number = 0
            amt = 0
        # Add a spike value if spike is due
        amt += self.spike.spike(time_ts)
        return amt
        

class Solar(object):
    
    def __init__(self, magnitude=10, solar_start=6, solar_length=12, spike=0):
        """Initialize a solar simulator
            Simulated ob will follow a single wave sine function starting at 0
            and ending at 0.  The solar day starts at time solar_start and
            finishes after solar_length hours.
                             
            magnitude:      the value at max, the range will be twice
                              this value
            solar_start:    decimal hour of day that obs start
                              (6.75=6:45am, 6:20=6:12am)
            solar_length:   length of day in decimal hours
                              (10.75=10hr 45min, 10:10=10hr 6min)
        """
        
        self.magnitude = magnitude
        self.solar_start = 3600 * solar_start
        self.solar_end = self.solar_start + 3600 * solar_length
        self.solar_length = 3600 * solar_length
        self.spike = Spike(magnitude * spike, solar_length)
        
    def value_at(self, time_ts):
        time_tt = time.localtime(time_ts)
        secs_since_midnight = time_tt.tm_hour * 3600 + time_tt.tm_min * 60.0 + time_tt.tm_sec
        if self.solar_start < secs_since_midnight <= self.solar_end:
            amt = self.magnitude * (1 + math.cos(math.pi * (1 + 2.0 * ((secs_since_midnight - self.solar_start) / self.solar_length - 1))))/2
        else:
            amt = 0
        # Add a spike value if spike is due
        amt += self.spike.spike(time_ts)
        return amt

class Spike(object):
    # Static variable to base time and seed
    start_ts = None

    def __init__(self, magnitude=1, period=1, frequency=4):
        """Initialize a spike generator
            Spikes will be generated based on random timings of a
            Poisson distribution. See http://bit.ly/1wNxBfg.

            Python random() module is guaranteed to return 
            repeatable random numbers given the same seed.
            Spike class also saves and restores the random
            state to main simulator spike predictability.

            If the static variable start_ts is set Spike class
            will use this as a base to regenerate spike times.
            So for a simulator that sets the same start_ts and 
            has the same obervation parameters the spikes will 
            be the same.

            magnitude: the magnitude of the spike

            period: the period over which to generate spikes
                    in hours

            frequency: the average frequency over the period.
                        On average there will be this many
                        spikes returned by the member function
                        spike()
        """

        if Spike.start_ts is None:
            raise ValueError("Spike class start_ts has not been primed")

        self.magnitude  = magnitude
        self.frequency  = frequency
        self.period     = period
        self.p_lambda   = frequency / (period * 3600.0)
        self.next_ts    = None
        self.random_state = None

    def spike(self, time_ts):
        """Return a spike value at a given time.
            If our magnitude is 0 we are not ever returning spikes
            
            time_ts: The time in unix epoch time."""
        return self._spike(time_ts) if self.magnitude > 0 else 0

    def _spike(self, time_ts):
        """Return a spike value at the given time
        Checks if a spike is due. If so returns the magnitude 
        as a value and regenerates the next spike time.

        time_ts: The time in unix epoch time."""
        spikeval = 0
        if self.next_ts is None:
            # The spike sequence may included this time 
            # So regenerate to just before this time
            self._regenerate(time_ts - 1)
      
        if time_ts >= self.next_ts:
            spikeval = self.magnitude
            self._regenerate(time_ts)
        return spikeval

    def _regenerate(self, time_ts):
        """Calculate the next spike time.

        time_ts: The time in unix epoch time
                    which is the base for the next spike time."""

        print_debug = False
        if self.next_ts is None:
            random.seed(Spike.start_ts + self.period * 3600 + self.magnitude)
            spike_ts = Spike.start_ts
        else:
            random.setstate(self.random_state)
            spike_ts = self.next_ts

        # Catch up and/or generate the next spike time
        while spike_ts <= time_ts:
            spike_ts = spike_ts + random.expovariate(self.p_lambda) 

        # Save our random state to make spikes deterministic
        self.random_state   = random.getstate()
        self.next_ts        = spike_ts

def confeditor_loader():
    return SimulatorConfEditor()

class SimulatorConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[Simulator]
    # This section is for the weewx weather station simulator

    # The time (in seconds) between LOOP packets.
    loop_interval = 2.5

    # The simulator mode can be either 'simulator' or 'generator'.
    # Real-time simulator. Sleep between each LOOP packet.
    mode = simulator
    # Generator.  Emit LOOP packets as fast as possible (useful for testing).
    #mode = generator

    # The start time. Format is YYYY-mm-ddTHH:MM. If not specified, the default 
    # is to use the present time.
    #start = 2011-01-01T00:00

    # Are we generating spikes?
    # A non-zero value will generate spikes at the multiplier of the simulated
    # observation magnitude
    #spike=2

    # The driver to use:
    driver = weewx.drivers.simulator
"""


if __name__ == "__main__":
    station = Simulator(mode='simulator',loop_interval=2.0)
    for packet in station.genLoopPackets():
        print weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet
