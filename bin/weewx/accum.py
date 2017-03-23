#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Statistical accumulators. They accumulate the highs, lows, averages,
etc., of a sequence of records."""

import math

import configobj

import weewx

class OutOfSpan(ValueError):
    """Raised when attempting to add a record outside of the timespan held by an accumulator"""

#===============================================================================
#                             ScalarStats
#===============================================================================

class ScalarStats(object):
    """Accumulates statistics (min, max, average, etc.) for a scalar value.
    
    Property 'last' is the last non-None value seen. Property 'lasttime' is
    the time it was seen. """
    
    default_init = (None, None, None, None, 0.0, 0, 0.0, 0)
    
    def __init__(self, stats_tuple=None):
        self.setStats(stats_tuple)
        self.last     = None
        self.lasttime = None
         
    def setStats(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.wsum,self.sumtime) = stats_tuple if stats_tuple else ScalarStats.default_init
         
    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics.
        This tuple can be used to update the stats database"""
        return (self.min, self.mintime, self.max, self.maxtime, 
                self.sum, self.count, self.wsum, self.sumtime)
    
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
        if x_stats.lasttime is not None:
            if self.lasttime is None or x_stats.lasttime >= self.lasttime:
                self.lasttime = x_stats.lasttime
                self.last     = x_stats.last

    def mergeSum(self, x_stats):
        """Merge the sum and count of another accumulator into myself."""
        self.sum     += x_stats.sum
        self.count   += x_stats.count
        self.wsum    += x_stats.wsum
        self.sumtime += x_stats.sumtime

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
            if self.lasttime is None or ts >= self.lasttime:
                self.last    = val
                self.lasttime= ts

    def addSum(self, val, weight=1):
        """Add a scalar value to my running sum and count."""
        if val is not None:
            self.sum     += val
            self.count   += 1
            self.wsum    += val * weight
            self.sumtime += weight
        
    @property
    def avg(self):
        return self.wsum / self.sumtime if self.count else None

class VecStats(object):
    """Accumulates statistics for a vector value.
     
    Property 'last' is the last non-None value seen. It is a two-way tuple (mag, dir).
    Property 'lasttime' is the time it was seen. """

    default_init = (None, None, None, None, 
                    0.0, 0, 0.0, 0, None, 0.0, 0.0, 0, 0.0, 0.0)
     
    def __init__(self, stats_tuple=None):
        self.setStats(stats_tuple)
        self.last     = (None, None)
        self.lasttime = None
 
    def setStats(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.wsum,self.sumtime,
         self.max_dir, self.xsum, self.ysum, 
         self.dirsumtime, self.squaresum, 
         self.wsquaresum) = stats_tuple if stats_tuple else VecStats.default_init
        
    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime,
                self.max, self.maxtime,
                self.sum, self.count,
                self.wsum,self.sumtime,
                self.max_dir, self.xsum, self.ysum, 
                self.dirsumtime,  self.squaresum, self.wsquaresum)
 
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
                self.max_dir = x_stats.max_dir
        if x_stats.lasttime is not None:
            if self.lasttime is None or x_stats.lasttime >= self.lasttime:
                self.lasttime = x_stats.lasttime
                self.last     = x_stats.last
 
    def mergeSum(self, x_stats):
        """Merge the sum and count of another accumulator into myself."""
        self.sum        += x_stats.sum
        self.count      += x_stats.count
        self.wsum       += x_stats.wsum
        self.sumtime    += x_stats.sumtime
        self.xsum       += x_stats.xsum
        self.ysum       += x_stats.ysum
        self.dirsumtime += x_stats.dirsumtime
        self.squaresum  += x_stats.squaresum
        self.wsquaresum += x_stats.wsquaresum
         
    def addHiLo(self, val, ts):
        """Include a vector value in my highs and lows.
        val: A vector value. It is a 2-way tuple (mag, dir).
        ts:  The timestamp.
        """
        speed, dirN = val
        if speed is not None:
            if self.min is None or speed < self.min:
                self.min = speed
                self.mintime = ts
            if self.max is None or speed > self.max:
                self.max = speed
                self.maxtime = ts
                self.max_dir = dirN
            if self.lasttime is None or ts >= self.lasttime:
                self.last    = (speed, dirN)
                self.lasttime= ts
         
    def addSum(self, val, weight=1):
        """Add a vector value to my sum and squaresum.
        val: A vector value. It is a 2-way tuple (mag, dir)
        """
        speed, dirN = val
        if speed is not None:
            self.sum         += speed
            self.count       += 1
            self.wsum        += weight * speed
            self.sumtime     += weight
            self.squaresum   += speed**2
            self.wsquaresum  += weight * speed**2
            if dirN is not None :
                self.xsum += weight * speed * math.cos(math.radians(90.0 - dirN))
                self.ysum += weight * speed * math.sin(math.radians(90.0 - dirN))
                self.dirsumtime += weight
             
    @property
    def avg(self):
        return self.wsum / self.sumtime if self.count else None
 
    @property
    def rms(self):
        return math.sqrt(self.wsquaresum / self.sumtime) if self.count else None
 
    @property
    def vec_avg(self):
        if self.count:
            return math.sqrt((self.xsum**2 + self.ysum**2) / self.sumtime**2)
 
    @property
    def vec_dir(self):
        if self.dirsumtime:
            _result = 90.0 - math.degrees(math.atan2(self.ysum, self.xsum))
            if _result < 0.0:
                _result += 360.0
            return _result

#===============================================================================
#                             Class Accum
#===============================================================================

class Accum(dict):
    """Accumulates statistics for a set of observation types."""
    
    def __init__(self, timespan):
        """Initialize a Accum.
        
        timespan: The time period over which stats will be accumulated."""
        
        self.timespan = timespan
        # The unit system is left unspecified until the first observation comes in.
        self.unit_system = None
        
    def addRecord(self, record, add_hilo=True, weight=1):
        """Add a record to my running statistics. 
        
        The record must have keys 'dateTime' and 'usUnits'."""
        
        # Check to see if the record is within my observation timespan 
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record"

        for obs_type in record:
            # Get the proper function ...
            func = get_add_function(obs_type)
            # ... then call it.
            func(self, record, obs_type, add_hilo, weight)
                            
    def updateHiLo(self, accumulator):
        """Merge the high/low stats of another accumulator into me."""
        if accumulator.timespan.start < self.timespan.start or accumulator.timespan.stop > self.timespan.stop:
            raise OutOfSpan("Attempt to merge an accumulator whose timespan is not a subset")

        self._check_units(accumulator.unit_system)
        
        for obs_type in accumulator:
            # Initialize the type if we have not seen it before
            self._init_type(obs_type)
            
            # Get the proper function ...
            func = get_merge_function(obs_type)
            # ... then call it
            func(self, accumulator, obs_type)

    def getRecord(self):
        """Extract a record out of the results in the accumulator."""
        
        # All records have a timestamp and unit type
        record = {'dateTime': self.timespan.stop,
                  'usUnits' : self.unit_system}
        
        return self.augmentRecord(record)
    
    def augmentRecord(self, record):
        
        # Go through all observation types.
        for obs_type in self:
            # If the type does not appear in the record, then add it:
            if obs_type not in record:
                # Get the proper extraction function...
                func = get_extract_function(obs_type)
                # ... then call it
                func(self, record, obs_type)

        return record

    def set_stats(self, obs_type, stats_tuple):
        
        self._init_type(obs_type)
        self[obs_type].setStats(stats_tuple)

    #
    # Begin add functions. These add a record to the accumulator.
    #
            
    def add_value(self, record, obs_type, add_hilo, weight):
        """Add a single observation to myself."""

        val = record[obs_type]

        # If the type has not been seen before, initialize it
        self._init_type(obs_type)
        # Then add to highs/lows, and to the running sum:
        if add_hilo: 
            self[obs_type].addHiLo(val, record['dateTime'])
        self[obs_type].addSum(val, weight=weight)

    def add_wind_value(self, record, obs_type, add_hilo, weight):
        """Add a single observation of type wind to myself."""

        if obs_type in ['windDir', 'windGust', 'windGustDir']:
            return
        if weewx.debug:
            assert(obs_type == 'windSpeed')
        
        # First add it to regular old 'windSpeed', then
        # treat it like a vector.
        self.add_value(record, obs_type, add_hilo, weight)
        
        # If the type has not been seen before, initialize it
        self._init_type('wind')
        # Then add to highs/lows, and to the running sum:
        if add_hilo:
            self['wind'].addHiLo((record.get('windGust'), record.get('windGustDir')), record['dateTime'])
            self['wind'].addHiLo((record.get('windSpeed'), record.get('windDir')), record['dateTime'])
        self['wind'].addSum((record['windSpeed'], record.get('windDir')), weight=weight)
        
    def check_units(self, record, obs_type, add_hilo, weight):  # @UnusedVariable
        if weewx.debug:
            assert(obs_type == 'usUnits')
        self._check_units(record['usUnits'])

    def noop(self, record, obs_type, add_hilo=True, weight=1):
        pass

    #
    # Begin hi/lo merge functions. These are called when merging two accumulators
    #
    
    def merge_minmax(self, x_accumulator, obs_type):
        """Merge value in another accumulator, using min/max"""

        self[obs_type].mergeHiLo(x_accumulator[obs_type])

    def merge_avg(self, x_accumulator, obs_type):
        """Merge value in another accumulator, using avg for max"""
        x_stats = x_accumulator[obs_type]
        if x_stats.min is not None:
            if self[obs_type].min is None or x_stats.min < self[obs_type].min:
                self[obs_type].min     = x_stats.min
                self[obs_type].mintime = x_stats.mintime
        if x_stats.avg is not None:
            if self[obs_type].max is None or x_stats.avg > self[obs_type].max:
                self[obs_type].max     = x_stats.avg
                self[obs_type].maxtime = x_accumulator.timespan.stop
        if x_stats.lasttime is not None:
            if self[obs_type].lasttime is None or x_stats.lasttime >= self[obs_type].lasttime:
                self[obs_type].lasttime = x_stats.lasttime
                self[obs_type].last     = x_stats.last

    #
    # Begin extraction functions. These extract a record out of the accumulator.
    #            

    def extract_wind(self, record, obs_type):
        """Extract wind values from myself, and put in a record."""
        # Wind records must be flattened into the separate categories:
        record['windSpeed']   = self[obs_type].avg
        record['windDir']     = self[obs_type].vec_dir
        record['windGust']    = self[obs_type].max
        record['windGustDir'] = self[obs_type].max_dir
        
    def extract_sum(self, record, obs_type):
        record[obs_type] = self[obs_type].sum
        
    def extract_last(self, record, obs_type):
        record[obs_type] = self[obs_type].last
        
    def extract_avg(self, record, obs_type):
        record[obs_type] = self[obs_type].avg

    #
    # Miscellaneous, utility functions
    #
    
    def _init_type(self, obs_type):
        """Add a given observation type to my dictionary."""
        # Do nothing if this type has already been initialized:
        if obs_type in self:
            return

        # Get a new accumulator of the proper type
        self[obs_type] = new_accumulator(obs_type)

    def _check_units(self, new_unit_system):
        # If no unit system has been specified for me yet, adopt the incoming
        # system
        if self.unit_system is None:
            self.unit_system = new_unit_system
        else:
            # Otherwise, make sure they match
            if self.unit_system != new_unit_system:
                raise ValueError("Unit system mismatch %d v. %d" % (self.unit_system, 
                                                                    new_unit_system))

    @property
    def isEmpty(self):
        return self.unit_system is None
            
#===============================================================================
#                            Configuration dictionaries
#===============================================================================

#
# Mappings from convenient string names, which can be used in a config file,
# to actual functions and classes
#

accum_types = {'scalar' : ScalarStats,
               'vector' : VecStats}

add_functions = {'add'         : Accum.add_value,
                 'add_wind'    : Accum.add_wind_value,
                 'check_units' : Accum.check_units,
                 'noop'        : Accum.noop}

merge_functions = {'minmax' : Accum.merge_minmax,
                   'avg'    : Accum.merge_avg}

extract_functions = {'avg'  : Accum.extract_avg,
                     'sum'  : Accum.extract_sum,
                     'last' : Accum.extract_last,
                     'wind' : Accum.extract_wind,
                     'noop' : Accum.noop}

#
# Default mappings from observation types to accumulator classes and functions
#

defaults_ini = """
[Accumulator]
    [[dateTime]]
        adder = noop
    [[usUnits]]
        adder = check_units
    [[rain]]
        extractor = sum
    [[ET]]
        extractor = sum
    [[dayET]]
        extractor = last
    [[monthET]]
        extractor = last
    [[yearET]]
        extractor = last
    [[hourRain]]
        extractor = last
    [[dayRain]]
        extractor = last
    [[rain24]]
        extractor = last
    [[monthRain]]
        extractor = last
    [[yearRain]]
        extractor = last
    [[totalRain]]
        extractor = last
    [[wind]]
        accumulator = vector
        extractor = wind
    [[windSpeed]]
        adder = add_wind
        merger = avg
        extractor = noop
    [[windDir]]
        extractor = noop
    [[windGust]]
        extractor = noop
    [[windGustDir]]
        extractor = noop
"""
import StringIO
defaults = configobj.ConfigObj(StringIO.StringIO(defaults_ini))
del StringIO

accum_type_dict = None
add_dict        = None
merge_dict      = None
extract_dict    = None

def initialize(config_dict):
    """Must be called before using any of the accumulators"""
    
    global defaults, accum_type_dict, merge_dict, add_dict, extract_dict

    accum_type_dict = {}
    add_dict        = {}
    merge_dict      = {}
    extract_dict    = {}
    
    # Initialize with the default values:    
    _initialize(defaults)

    # Now do the overrides from the config file
    _initialize(config_dict)
    
def _initialize(config_dict):
    global accum_type_dict, add_dict, merge_dict, extract_dict

    extras = config_dict.get('Accumulator', configobj.ConfigObj({}))
    for obs_type in extras.sections:
        # Get the accumulator type
        accum_type = extras[obs_type].get('accumulator', 'scalar').lower()
        # Fail hard if this is an unknown accumulator type
        accum_type_dict[obs_type] = accum_types[accum_type]
        
        # Get the adder function to use
        add_function = extras[obs_type].get('adder', 'add').lower()
        # Fail hard if this is an unknown adder function
        add_dict[obs_type] = add_functions[add_function]

        # Get the Hi/Lo function to use
        hilo_function = extras[obs_type].get('merger', 'minmax').lower()
        # Fail hard if this is an unknown Hi/Lo function
        merge_dict[obs_type] = merge_functions[hilo_function]
        
        # Get the type of extraction function to use
        extract_function = extras[obs_type].get('extractor', 'avg').lower()
        # Fail hard if this is an unknown extraction type:
        extract_dict[obs_type] = extract_functions[extract_function]
    
def new_accumulator(obs_type):
    global accum_type_dict
    # If the dictionaries have not been initialized, do so with the defaults
    if accum_type_dict is None:
        initialize(defaults)
    return accum_type_dict.get(obs_type, ScalarStats)()

def get_add_function(obs_type):
    global add_dict
    # If the dictionaries have not been initialized, do so with the defaults
    if add_dict is None:
        initialize(defaults)
    return add_dict.get(obs_type, Accum.add_value)
    
def get_merge_function(obs_type):
    global merge_dict
    # If the dictionary has not been initialized, do so with the defaults
    if merge_dict is None:
        initialize(defaults)
    return merge_dict.get(obs_type, Accum.merge_minmax)

def get_extract_function(obs_type):
    global extract_dict
    # If the dictionaries have not been initialized, do so with the defaults
    if extract_dict is None:
        initialize(defaults)
    return extract_dict.get(obs_type, Accum.extract_avg)
