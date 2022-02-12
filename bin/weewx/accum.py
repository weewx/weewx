#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Statistical accumulators. They accumulate the highs, lows, averages, etc.,
of a sequence of records."""
#
# General strategy.
#
# Most observation types are scalars, so they can be treated simply. Values are added to a scalar
# accumulator, which keeps track of highs, lows, and a sum. When it comes time for extraction, the
# average over the archive period is typically produced.
#
# However, wind is a special case. It is a vector, which has been flatted over at least two
# scalars, windSpeed and windDir. Some stations, notably the Davis Vantage, add windGust and
# windGustDir. The accumulators cannot simply treat them individually as if they were just another
# scalar. Instead they must be grouped together. This is done by treating windSpeed as a 'special'
# scalar. When it appears, it is coupled with windDir and, if available, windGust and windGustDir,
# and added to a vector accumulator. When the other types ( windDir, windGust, and windGustDir)
# appear, they are ignored, having already been handled during the processing of type windSpeed.
#
# When it comes time to extract wind, vector averages are calculated, then the results are
# flattened again.
#
from __future__ import absolute_import

import logging
import math

import six

import weewx
from weeutil.weeutil import ListOfDicts, to_float
import weeutil.config

log = logging.getLogger(__name__)

#
# Default mappings from observation types to accumulator classes and functions
#

DEFAULTS_INI = """
[Accumulator]
    [[dateTime]]
        adder = noop
    [[dayET]]
        extractor = last
    [[dayRain]]
        extractor = last
    [[ET]]
        extractor = sum
    [[hourRain]]
        extractor = last
    [[rain]]
        extractor = sum
    [[rain24]]
        extractor = last
    [[monthET]]
        extractor = last
    [[monthRain]]
        extractor = last
    [[stormRain]]
        extractor = last
    [[totalRain]]
        extractor = last
    [[usUnits]]
        adder = check_units
    [[wind]]
        accumulator = vector
        extractor = wind
    [[windDir]]
        extractor = noop
    [[windGust]]
        extractor = noop
    [[windGustDir]]
        extractor = noop
    [[windGust10]]
        extractor = last
    [[windGustDir10]]
        extractor = last
    [[windrun]]
        extractor = sum
    [[windSpeed]]
        adder = add_wind
        merger = avg
        extractor = noop
    [[windSpeed2]]
        extractor = last
    [[windSpeed10]]
        extractor = last
    [[yearET]]
        extractor = last
    [[yearRain]]
        extractor = last
    [[lightning_strike_count]]
        extractor = sum
"""
defaults_dict = weeutil.config.config_from_str(DEFAULTS_INI)

accum_dict = ListOfDicts(defaults_dict['Accumulator'].dict())


class OutOfSpan(ValueError):
    """Raised when attempting to add a record outside of the timespan held by an accumulator"""


# ===============================================================================
#                             ScalarStats
# ===============================================================================

class ScalarStats(object):
    """Accumulates statistics (min, max, average, etc.) for a scalar value.
    
    Property 'last' is the last non-None value seen. Property 'lasttime' is
    the time it was seen. """

    default_init = (None, None, None, None, 0.0, 0, 0.0, 0)

    def __init__(self, stats_tuple=None):
        self.setStats(stats_tuple)
        self.last = None
        self.lasttime = None

    def setStats(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.wsum, self.sumtime) = stats_tuple if stats_tuple else ScalarStats.default_init

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics.
        This tuple can be used to update the stats database"""
        return (self.min, self.mintime, self.max, self.maxtime,
                self.sum, self.count, self.wsum, self.sumtime)

    def mergeHiLo(self, x_stats):
        """Merge the highs and lows of another accumulator into myself."""
        if x_stats.min is not None:
            if self.min is None or x_stats.min < self.min:
                self.min = x_stats.min
                self.mintime = x_stats.mintime
        if x_stats.max is not None:
            if self.max is None or x_stats.max > self.max:
                self.max = x_stats.max
                self.maxtime = x_stats.maxtime
        if x_stats.lasttime is not None:
            if self.lasttime is None or x_stats.lasttime >= self.lasttime:
                self.lasttime = x_stats.lasttime
                self.last = x_stats.last

    def mergeSum(self, x_stats):
        """Merge the sum and count of another accumulator into myself."""
        self.sum += x_stats.sum
        self.count += x_stats.count
        self.wsum += x_stats.wsum
        self.sumtime += x_stats.sumtime

    def addHiLo(self, val, ts):
        """Include a scalar value in my highs and lows.
        val: A scalar value
        ts:  The timestamp. """

        # If necessary, convert to float. Be prepared to catch an exception if not possible.
        try:
            val = to_float(val)
        except ValueError:
            val = None

        # Check for None and NaN:
        if val is not None and val == val:
            if self.min is None or val < self.min:
                self.min = val
                self.mintime = ts
            if self.max is None or val > self.max:
                self.max = val
                self.maxtime = ts
            if self.lasttime is None or ts >= self.lasttime:
                self.last = val
                self.lasttime = ts

    def addSum(self, val, weight=1):
        """Add a scalar value to my running sum and count."""

        # If necessary, convert to float. Be prepared to catch an exception if not possible.
        try:
            val = to_float(val)
        except ValueError:
            val = None

        # Check for None and NaN:
        if val is not None and val == val:
            self.sum += val
            self.count += 1
            self.wsum += val * weight
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
        self.last = (None, None)
        self.lasttime = None

    def setStats(self, stats_tuple=None):
        (self.min, self.mintime,
         self.max, self.maxtime,
         self.sum, self.count,
         self.wsum, self.sumtime,
         self.max_dir, self.xsum, self.ysum,
         self.dirsumtime, self.squaresum,
         self.wsquaresum) = stats_tuple if stats_tuple else VecStats.default_init

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics."""
        return (self.min, self.mintime,
                self.max, self.maxtime,
                self.sum, self.count,
                self.wsum, self.sumtime,
                self.max_dir, self.xsum, self.ysum,
                self.dirsumtime, self.squaresum, self.wsquaresum)

    def mergeHiLo(self, x_stats):
        """Merge the highs and lows of another accumulator into myself."""
        if x_stats.min is not None:
            if self.min is None or x_stats.min < self.min:
                self.min = x_stats.min
                self.mintime = x_stats.mintime
        if x_stats.max is not None:
            if self.max is None or x_stats.max > self.max:
                self.max = x_stats.max
                self.maxtime = x_stats.maxtime
                self.max_dir = x_stats.max_dir
        if x_stats.lasttime is not None:
            if self.lasttime is None or x_stats.lasttime >= self.lasttime:
                self.lasttime = x_stats.lasttime
                self.last = x_stats.last

    def mergeSum(self, x_stats):
        """Merge the sum and count of another accumulator into myself."""
        self.sum += x_stats.sum
        self.count += x_stats.count
        self.wsum += x_stats.wsum
        self.sumtime += x_stats.sumtime
        self.xsum += x_stats.xsum
        self.ysum += x_stats.ysum
        self.dirsumtime += x_stats.dirsumtime
        self.squaresum += x_stats.squaresum
        self.wsquaresum += x_stats.wsquaresum

    def addHiLo(self, val, ts):
        """Include a vector value in my highs and lows.
        val: A vector value. It is a 2-way tuple (mag, dir).
        ts:  The timestamp.
        """
        speed, dirN = val

        # If necessary, convert to float. Be prepared to catch an exception if not possible.
        try:
            speed = to_float(speed)
        except ValueError:
            speed = None
        try:
            dirN = to_float(dirN)
        except ValueError:
            dirN = None

        # Check for None and NaN:
        if speed is not None and speed == speed:
            if self.min is None or speed < self.min:
                self.min = speed
                self.mintime = ts
            if self.max is None or speed > self.max:
                self.max = speed
                self.maxtime = ts
                self.max_dir = dirN
            if self.lasttime is None or ts >= self.lasttime:
                self.last = (speed, dirN)
                self.lasttime = ts

    def addSum(self, val, weight=1):
        """Add a vector value to my sum and squaresum.
        val: A vector value. It is a 2-way tuple (mag, dir)
        """
        speed, dirN = val

        # If necessary, convert to float. Be prepared to catch an exception if not possible.
        try:
            speed = to_float(speed)
        except ValueError:
            speed = None
        try:
            dirN = to_float(dirN)
        except ValueError:
            dirN = None

        # Check for None and NaN:
        if speed is not None and speed == speed:
            self.sum += speed
            self.count += 1
            self.wsum += weight * speed
            self.sumtime += weight
            self.squaresum += speed ** 2
            self.wsquaresum += weight * speed ** 2
            if dirN is not None:
                self.xsum += weight * speed * math.cos(math.radians(90.0 - dirN))
                self.ysum += weight * speed * math.sin(math.radians(90.0 - dirN))
            # It's OK for direction to be None, provided speed is zero:
            if dirN is not None or speed == 0:
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
            return math.sqrt((self.xsum ** 2 + self.ysum ** 2) / self.sumtime ** 2)

    @property
    def vec_dir(self):
        if self.dirsumtime and (self.ysum or self.xsum):
            _result = 90.0 - math.degrees(math.atan2(self.ysum, self.xsum))
            if _result < 0.0:
                _result += 360.0
            return _result
        # Return the last known direction when our vector sum is 0
        return self.last[1]


# ===============================================================================
#                             FirstLastAccum
# ===============================================================================

class FirstLastAccum(object):
    """Minimal accumulator, suitable for strings.
    It can only return the first and last strings it has seen, along with their timestamps.
    """

    default_init = (None, None, None, None)

    def __init__(self, stats_tuple=None):
        self.first = None
        self.firsttime = None
        self.last = None
        self.lasttime = None

    def setStats(self, stats_tuple=None):
        self.first, self.firsttime, self.last, self.lasttime = stats_tuple \
            if stats_tuple else FirstLastAccum.default_init

    def getStatsTuple(self):
        """Return a stats-tuple. That is, a tuple containing the gathered statistics.
        This tuple can be used to update the stats database"""
        return self.first, self.firsttime, self.last, self.lasttime

    def mergeHiLo(self, x_stats):
        """Merge the highs and lows of another accumulator into myself."""
        if x_stats.firsttime is not None:
            if self.firsttime is None or x_stats.firsttime < self.firsttime:
                self.firsttime = x_stats.firsttime
                self.first = x_stats.first
        if x_stats.lasttime is not None:
            if self.lasttime is None or x_stats.lasttime >= self.lasttime:
                self.lasttime = x_stats.lasttime
                self.last = x_stats.last

    def mergeSum(self, x_stats):
        """Merge the count of another accumulator into myself."""
        pass

    def addHiLo(self, val, ts):
        """Include a value in my stats.
        val: A value of almost any type. It will be converted to a string before being accumulated.
        ts:  The timestamp.
        """
        if val is not None:
            string_val = str(val)
            if self.firsttime is None or ts < self.firsttime:
                self.first = string_val
                self.firsttime = ts
            if self.lasttime is None or ts >= self.lasttime:
                self.last = string_val
                self.lasttime = ts

    def addSum(self, val, weight=1):
        """Add a scalar value to my running count."""
        pass


# ===============================================================================
#                             Class Accum
# ===============================================================================

class Accum(dict):
    """Accumulates statistics for a set of observation types."""

    def __init__(self, timespan, unit_system=None):
        """Initialize a Accum.
        
        timespan: The time period over which stats will be accumulated.
        unit_system: The unit system used by the accumulator"""

        self.timespan = timespan
        # Set the accumulator's unit system. Usually left unspecified until the
        # first observation comes in for normal operation or pre-set if
        # obtaining a historical accumulator.
        self.unit_system = unit_system

    def addRecord(self, record, add_hilo=True, weight=1):
        """Add a record to my running statistics. 
        
        The record must have keys 'dateTime' and 'usUnits'."""

        # Check to see if the record is within my observation timespan 
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan("Attempt to add out-of-interval record (%s) to timespan (%s)"
                            % (record['dateTime'], self.timespan))

        for obs_type in record:
            # Get the proper function ...
            func = get_add_function(obs_type)
            # ... then call it.
            func(self, record, obs_type, add_hilo, weight)

    def updateHiLo(self, accumulator):
        """Merge the high/low stats of another accumulator into me."""
        if accumulator.timespan.start < self.timespan.start \
                or accumulator.timespan.stop > self.timespan.stop:
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
                  'usUnits': self.unit_system}

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
            assert (obs_type == 'windSpeed')

        # First add it to regular old 'windSpeed', then
        # treat it like a vector.
        self.add_value(record, obs_type, add_hilo, weight)

        # If the type has not been seen before, initialize it.
        self._init_type('wind')
        # Then add to highs/lows.
        if add_hilo:
            # If the station does not provide windGustDir, then substitute windDir.
            # See issue #320, https://bit.ly/2HSo0ju
            wind_gust_dir = record['windGustDir'] \
                if 'windGustDir' in record else record.get('windDir')
            # Do windGust first, so that the last value entered is windSpeed, not windGust
            # See Slack discussion https://bit.ly/3qV1nBV
            self['wind'].addHiLo((record.get('windGust'), wind_gust_dir),
                                 record['dateTime'])
            self['wind'].addHiLo((record.get('windSpeed'), record.get('windDir')),
                                 record['dateTime'])
        # Add to the running sum.
        self['wind'].addSum((record['windSpeed'], record.get('windDir')), weight=weight)

    def check_units(self, record, obs_type, add_hilo, weight):
        if weewx.debug:
            assert (obs_type == 'usUnits')
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
                self[obs_type].min = x_stats.min
                self[obs_type].mintime = x_stats.mintime
        if x_stats.avg is not None:
            if self[obs_type].max is None or x_stats.avg > self[obs_type].max:
                self[obs_type].max = x_stats.avg
                self[obs_type].maxtime = x_accumulator.timespan.stop
        if x_stats.lasttime is not None:
            if self[obs_type].lasttime is None or x_stats.lasttime >= self[obs_type].lasttime:
                self[obs_type].lasttime = x_stats.lasttime
                self[obs_type].last = x_stats.last

    #
    # Begin extraction functions. These extract a record out of the accumulator.
    #            

    def extract_wind(self, record, obs_type):
        """Extract wind values from myself, and put in a record."""
        # Wind records must be flattened into the separate categories:
        if 'windSpeed' not in record:
            record['windSpeed'] = self[obs_type].avg
        if 'windDir' not in record:
            record['windDir'] = self[obs_type].vec_dir
        if 'windGust' not in record:
            record['windGust'] = self[obs_type].max
        if 'windGustDir' not in record:
            record['windGustDir'] = self[obs_type].max_dir

    def extract_sum(self, record, obs_type):
        record[obs_type] = self[obs_type].sum if self[obs_type].count else None

    def extract_last(self, record, obs_type):
        record[obs_type] = self[obs_type].last

    def extract_avg(self, record, obs_type):
        record[obs_type] = self[obs_type].avg

    def extract_min(self, record, obs_type):
        record[obs_type] = self[obs_type].min

    def extract_max(self, record, obs_type):
        record[obs_type] = self[obs_type].max

    def extract_count(self, record, obs_type):
        record[obs_type] = self[obs_type].count

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


# ===============================================================================
#                            Configuration dictionaries
# ===============================================================================

#
# Mappings from convenient string nicknames, which can be used in a config file,
# to actual functions and classes
#

ACCUM_TYPES = {
    'scalar': ScalarStats,
    'vector': VecStats,
    'firstlast': FirstLastAccum
}

ADD_FUNCTIONS = {
    'add': Accum.add_value,
    'add_wind': Accum.add_wind_value,
    'check_units': Accum.check_units,
    'noop': Accum.noop
}

MERGE_FUNCTIONS = {
    'minmax': Accum.merge_minmax,
    'avg': Accum.merge_avg
}

EXTRACT_FUNCTIONS = {
    'avg': Accum.extract_avg,
    'count': Accum.extract_count,
    'last': Accum.extract_last,
    'max': Accum.extract_max,
    'min': Accum.extract_min,
    'noop': Accum.noop,
    'sum': Accum.extract_sum,
    'wind': Accum.extract_wind,
}

# The default actions for an individual observation type
OBS_DEFAULTS = {
    'accumulator': 'scalar',
    'adder': 'add',
    'merger': 'minmax',
    'extractor': 'avg'
}


def initialize(config_dict):
    # Add the configuration dictionary to the beginning of the list of maps.
    # This will cause it to override the defaults
    global accum_dict
    accum_dict.maps.insert(0, config_dict.get('Accumulator', {}))


def new_accumulator(obs_type):
    """Instantiate an accumulator, appropriate for type 'obs_type'."""
    global accum_dict
    # Get the options for this type. Substitute the defaults if they have not been specified
    obs_options = accum_dict.get(obs_type, OBS_DEFAULTS)
    # Get the nickname of the accumulator. Default is 'scalar'
    accum_nickname = obs_options.get('accumulator', 'scalar')
    # Instantiate and return the accumulator.
    # If we don't know this nickname, then fail hard with a KeyError
    return ACCUM_TYPES[accum_nickname]()


def get_add_function(obs_type):
    """Get an adder function appropriate for type 'obs_type'."""
    global accum_dict
    # Get the options for this type. Substitute the defaults if they have not been specified
    obs_options = accum_dict.get(obs_type, OBS_DEFAULTS)
    # Get the nickname of the adder. Default is 'add'
    add_nickname = obs_options.get('adder', 'add')
    # If we don't know this nickname, then fail hard with a KeyError
    return ADD_FUNCTIONS[add_nickname]


def get_merge_function(obs_type):
    """Get a merge function appropriate for type 'obs_type'."""
    global accum_dict
    # Get the options for this type. Substitute the defaults if they have not been specified
    obs_options = accum_dict.get(obs_type, OBS_DEFAULTS)
    # Get the nickname of the merger. Default is 'minmax'
    add_nickname = obs_options.get('merger', 'minmax')
    # If we don't know this nickname, then fail hard with a KeyError
    return MERGE_FUNCTIONS[add_nickname]


def get_extract_function(obs_type):
    """Get an extraction function appropriate for type 'obs_type'."""
    global accum_dict
    # Get the options for this type. Substitute the defaults if they have not been specified
    obs_options = accum_dict.get(obs_type, OBS_DEFAULTS)
    # Get the nickname of the extractor. Default is 'avg'
    add_nickname = obs_options.get('extractor', 'avg')
    # If we don't know this nickname, then fail hard with a KeyError
    return EXTRACT_FUNCTIONS[add_nickname]
