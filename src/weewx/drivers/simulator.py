#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Console simulator for the weewx weather system"""

import math
import random
import time

import weewx.drivers
import weeutil.weeutil

DRIVER_NAME = 'Simulator'
DRIVER_VERSION = "3.3"


def loader(config_dict, engine):

    start_ts, resume_ts = extract_starts(config_dict, DRIVER_NAME)

    stn = Simulator(start_time=start_ts, resume_time=resume_ts, **config_dict[DRIVER_NAME])

    return stn


def extract_starts(config_dict, driver_name):
    """Extract the start and resume times out of the configuration dictionary.

    Args:
        config_dict (dict): The configuration dictionary
        driver_name (str): The name of the driver. Something like 'Simulator'

    Returns
        tuple(float|None, float|None): A two-way tuple, start time and the resume time.
    """

    # This uses a bit of a hack to have the simulator resume at a later
    # time. It's not bad, but I'm not enthusiastic about having special
    # knowledge about the database in a driver, albeit just the loader.

    start_ts = resume_ts = None
    if 'start' in config_dict[driver_name]:
        # A start has been specified. Extract the time stamp.
        start_tt = time.strptime(config_dict[driver_name]['start'], "%Y-%m-%dT%H:%M")
        start_ts = time.mktime(start_tt)
        # If the 'resume' keyword is present and True, then get the last
        # archive record out of the database and resume with that.
        if weeutil.weeutil.to_bool(config_dict[driver_name].get('resume', False)):
            import weewx.manager
            import weedb
            try:
                # Resume with the last time in the database. If there is no such
                # time, then fall back to the time specified in the configuration
                # dictionary.
                with weewx.manager.open_manager_with_config(config_dict,
                                                            'wx_binding') as dbmanager:
                    resume_ts = dbmanager.lastGoodStamp()
            except weedb.OperationalError:
                pass
        else:
            # The resume keyword is not present. Start with the seed time:
            resume_ts = start_ts

    return start_ts, resume_ts


class Simulator(weewx.drivers.AbstractDevice):
    """Station simulator"""
    
    def __init__(self, **stn_dict):
        """Initialize the simulator
        
        NAMED ARGUMENTS:
        
        loop_interval (float|None): The time (in seconds) between emitting LOOP packets.
            Default is 2.5.
        
        start_time (float|None): The start (seed) time for the generator in unix epoch time
            If 'None', or not present, then present time will be used.

        resume_time (float|None): The start time for the loop.
            If 'None', or not present, then start_time will be used.
        
        mode (str): Controls the frequency of packets.  One of either:
            'simulator': Real-time simulator - sleep between LOOP packets
            'generator': Emit packets as fast as possible (useful for testing)
            Default is 'simulator'

        observations (list[str]|None): A list of observation types that should be generated.
            If nothing is specified (the default), then all observations will be generated.
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
        
        # The following doesn't make much meteorological sense, but it is
        # easy to program!
        self.observations = {
            'outTemp'    : Observation(magnitude=20.0,  average= 50.0, period=24.0, phase_lag=14.0, start=start_ts),
            'inTemp'     : Observation(magnitude=5.0,   average= 68.0, period=24.0, phase_lag=12.0, start=start_ts),
            'barometer'  : Observation(magnitude=1.0,   average= 30.1, period=48.0, phase_lag= 0.0, start=start_ts),
            'pressure'   : Observation(magnitude=1.0,   average= 30.1, period=48.0, phase_lag= 0.0, start=start_ts),
            'windSpeed'  : Observation(magnitude=5.0,   average=  5.0, period=48.0, phase_lag=24.0, start=start_ts),
            'windDir'    : Observation(magnitude=180.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts),
            'windGust'   : Observation(magnitude=6.0,   average=  6.0, period=48.0, phase_lag=24.0, start=start_ts),
            'windGustDir': Observation(magnitude=180.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts),
            'outHumidity': Observation(magnitude=30.0,  average= 50.0, period=48.0, phase_lag= 0.0, start=start_ts),
            'inHumidity' : Observation(magnitude=10.0,  average= 20.0, period=24.0, phase_lag= 0.0, start=start_ts),
            'radiation'  : Solar(magnitude=1000, solar_start=6, solar_length=12),
            'UV'         : Solar(magnitude=14,   solar_start=6, solar_length=12),
            'rain'       : Rain(rain_start=0, rain_length=3, total_rain=0.2, loop_interval=self.loop_interval),
            'txBatteryStatus': BatteryStatus(),
            'windBatteryStatus': BatteryStatus(),
            'rainBatteryStatus': BatteryStatus(),
            'outTempBatteryStatus': BatteryStatus(),
            'inTempBatteryStatus': BatteryStatus(),
            'consBatteryVoltage': BatteryVoltage(),
            'heatingVoltage': BatteryVoltage(),
            'supplyVoltage': BatteryVoltage(),
            'referenceVoltage': BatteryVoltage(),
            'rxCheckPercent': SignalStrength()}

        self.trim_observations(stn_dict)

    def trim_observations(self, stn_dict):
        """Calculate only the specified observations, or all if none specified"""
        if stn_dict.get('observations'):
            desired = {x.strip() for x in stn_dict['observations']}
            for obs in list(self.observations):
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
    
    def __init__(self, magnitude=1.0, average=0.0, period=96.0, phase_lag=0.0, start=None):
        """Initialize an observation function.

        Args:
            magnitude (float): The value at max. The range will be twice this value
            average (float): The average value, averaged over a full cycle.
            period (float): The cycle period in hours.
            phase_lag (float): The number of hours after the start time when the
                observation hits its max
            start (float|None): Time zero for the observation in unix epoch time."""
         
        if not start:
            raise ValueError("No start time specified")
        self.magnitude = magnitude
        self.average   = average
        self.period    = period * 3600.0
        self.phase_lag = phase_lag * 3600.0
        self.start     = start
        
    def value_at(self, time_ts):
        """Return the observation value at the given time.
        
        time_ts: The time in unix epoch time."""

        phase = 2.0 * math.pi * (time_ts - self.start - self.phase_lag) / self.period
        return self.magnitude * math.cos(phase) + self.average


class Rain(object):

    bucket_tip = 0.01

    def __init__(self, rain_start=0, rain_length=1, total_rain=0.1, loop_interval=2.5):
        """Initialize a rain simulator

        Args:
            rain_start (float): When the rain should start in hours, relative to midnight.
            rain_length (float): How long it should rain in hours.
            total_rain (float): How much rain should fall.
            loop_interval (float): Interval between LOOP packets.
        """
        npackets = 3600 * rain_length / loop_interval
        n_rain_packets = total_rain / Rain.bucket_tip
        self.period = int(npackets/n_rain_packets)
        self.rain_start = 3600* rain_start
        self.rain_end = self.rain_start + 3600 * rain_length
        self.packet_number = 0

    def value_at(self, time_ts):
        time_tt = time.localtime(time_ts)
        secs_since_midnight = time_tt.tm_hour * 3600 + time_tt.tm_min * 60.0 + time_tt.tm_sec
        if self.rain_start < secs_since_midnight <= self.rain_end:
            amt = Rain.bucket_tip if self.packet_number % self.period == 0 else 0.0
            self.packet_number += 1
        else:
            self.packet_number = 0
            amt = 0
        return amt


class Solar(object):

    def __init__(self, magnitude=10, solar_start=6, solar_length=12):
        """Initialize a solar simulator. The simulator will follow a simple wave sine function
         starting and ending at 0.  The solar day starts at time solar_start and
            finishes after solar_length hours.

        Args:
            magnitude (float):  The value at max, the range will be twice this value
            solar_start (float): The decimal hour of day that observation will start
                (6.75=6:45am, 6:20=6:12am)
            solar_length (float): The ength of day in decimal hours
                (10.75=10hr 45min, 10:10=10hr 6min)
        """

        self.magnitude = magnitude
        self.solar_start = 3600 * solar_start
        self.solar_end = self.solar_start + 3600 * solar_length
        self.solar_length = 3600 * solar_length

    def value_at(self, time_ts):
        time_tt = time.localtime(time_ts)
        secs_since_midnight = time_tt.tm_hour * 3600 + time_tt.tm_min * 60.0 + time_tt.tm_sec
        if self.solar_start < secs_since_midnight <= self.solar_end:
            amt = self.magnitude * (1 + math.cos(math.pi * (1 + 2.0 * ((secs_since_midnight - self.solar_start) / self.solar_length - 1))))/2
        else:
            amt = 0
        return amt


class BatteryStatus(object):
    
    def __init__(self, chance_of_failure=None, min_recovery_time=None):
        """Initialize a battery status.

        Args:
            chance_of_failure (float|None): Likeliness that the battery should fail [0,1]. If
                None, then use 0.05% (about once every 30 minutes).
            min_recovery_time (float|None): Minimum time until the battery recovers in seconds.
                Default is to pick a random time between 300 and 1800 seconds (5-60 minutes).
        """
        if chance_of_failure is None:
            chance_of_failure = 0.0005 # about once every 30 minutes
        if min_recovery_time is None:
            min_recovery_time = random.randint(300, 1800) # 5 to 15 minutes
        self.chance_of_failure = chance_of_failure
        self.min_recovery_time = min_recovery_time
        self.state = 0
        self.fail_ts = 0
        
    def value_at(self, time_ts):
        if self.state == 1:
            # recover if sufficient time has passed
            if time_ts - self.fail_ts > self.min_recovery_time:
                self.state = 0
        else:
            # see if we need a failure
            if random.random() < self.chance_of_failure:
                self.state = 1
                self.fail_ts = time_ts
        return self.state


class BatteryVoltage(object):

    def __init__(self, nominal_value=None, max_variance=None):
        """Initialize a battery voltage.

        Args:
            nominal_value (float|None): The voltage averaged over time. Default is 12
            max_variance (float|None): How much it should fluctuate in volts. Default is 10% of
                the nominal_value.
        """
        if nominal_value is None:
            nominal_value = 12.0
        if max_variance is None:
            max_variance = 0.1 * nominal_value
        self.nominal = nominal_value
        self.variance = max_variance

    def value_at(self, time_ts):
        return self.nominal + self.variance * random.random() * random.randint(-1, 1)


class SignalStrength(object):

    def __init__(self, minval=0.0, maxval=100.0):
        """Initialize a signal strength simulator.

        Args:
            minval (float): The minimum signal strength in percent.
            maxval (float): The maximum signal strength in percent.
        """
        self.minval = minval
        self.maxval = maxval
        self.max_variance = 0.1 * (self.maxval - self.minval)
        self.value = self.minval + random.random() * (self.maxval - self.minval)

    def value_at(self, time_ts):
        newval = self.value + self.max_variance * random.random() * random.randint(-1, 1)
        newval = max(self.minval, newval)
        newval = min(self.maxval, newval)
        self.value = newval
        return self.value


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

    # The driver to use:
    driver = weewx.drivers.simulator
"""


if __name__ == "__main__":
    station = Simulator(mode='simulator',loop_interval=2.0)
    for packet in station.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)
