#
#    Copyright (c) 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Data structures and functions for dealing with units."""

#===============================================================================
# This logic makes heavy use of "value tuples". This is a 2-way tuple where
# the first element is a value, and the second element is the unit type. An
# example would be (21.2, 'degree_C').
# 
# There are functions for allowing value tuples to be converted between
# various units.
#===============================================================================

import time

import weewx
import weeutil.weeutil
from weewx.unitdicts import * 


#===============================================================================
#                        class ValueHelper
#===============================================================================
    
class ValueHelper(object):
    """A helper class that binds together everything needed to do a
    context sensitive formatting"""
    
    def __init__(self, value_t, context='current', unit_info=None):
        """Initialize a ValueHelper.
        
        value_t: The value tuple with the data. First element is the value,
        second element the unit type (or None if not known).
        
        context: The time context. Something like 'current', 'day', 'week', etc.
        [Optional. If not given, context 'current' will be used.]
        
        unit_info: An instance of UnitInfo. This will be used to determine what
        unit the value is to be displayed in, as well as any formatting and labeling
        information. [Optional. If not given, the default UnitInfo will be used]
        """
        self.value_t   = value_t
        self.context   = context
        self.unit_info = unit_info if unit_info else UnitInfo()
        
    def __str__(self):
        """Return as string"""
        return self.unit_info.toString(self.value_t, self.context)
    
    def string(self, NONE_string=None):
        """Return as string with an optional user specified string to be used if None"""
        return self.unit_info.toString(self.value_t, self.context, NONE_string=NONE_string)
    
    def format(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format."""
        return self.unit_info.toString(self.value_t, self.context, useThisFormat=format_string, NONE_string=NONE_string)
    
    def nolabel(self, format_string, NONE_string=None):
        """Return a formatted version of the data, using a user-supplied format. No label."""
        return self.unit_info.toString(self.value_t, self.context, addLabel=False, useThisFormat=format_string, NONE_string=NONE_string)

    @property
    def formatted(self):
        """Return a formatted version of the data. No label."""
        return self.unit_info.toString(self.value_t, self.context, addLabel=False)
        
    @property
    def raw(self):
        """Return the value in the target unit type.
        
        'Raw' does unit conversion, but does not apply any formatting.
        
        Returns: The value in the target unit type"""
        return self.value_tuple[0]
    
    @property
    def value_tuple(self):
        """Returns a value tuple with the value in the targeted unit type.
        
        Returns: A value tuple. First element is the value, second element the unit type"""
        
        return self.unit_info.convert(self.value_t)
        
#===============================================================================
#                            class ValueDict
#===============================================================================

class ValueDict(dict):
    """A dictionary that returns contents as a ValueHelper.
    
    This dictionary, when keyed, returns a ValueHelper object, which can then
    be used for context sensitive formatting. 
    """
    
    def __init__(self, d, unit_info=None):
        """Initialize the ValueDict from another dictionary.
        
        d: A dictionary containing the key-value pairs for observation types
        and their values. It must include an entry 'usUnits', giving the
        standard unit system the entries are in. An example would be:
        
            {'outTemp'   : 23.9,
             'barometer' : 1002.3,
             'usUnits'   : 2}

        In this case, the standard unit system being used is "2", or Metric.
        
        unit_info: An instance of UnitInfo. This will be passed on to
        the returned instance of ValueHelper. [Optional. If not given,
        the default UnitInfo will be used]
        """
        # Initialize my superclass, the dictionary:
        super(ValueDict, self).__init__(d)
        self.unit_info = unit_info if unit_info else UnitInfo()
        
    def __getitem__(self, obs_type):
        """Look up an observation type (eg, 'outTemp') and return it as a 
        value-tuple in the target unit system."""
        # Find out what standard unit system (US or Metric) I am in:
        std_unit_system = dict.__getitem__(self, 'usUnits')
        # Given this standard unit system, what is the unit type of this
        # particular observation type?
        unit_type = getStandardUnitType(std_unit_system, obs_type)
        # Form the value-tuple. First entry is a value, second the unit type:
        val_t = (dict.__getitem__(self, obs_type), unit_type)
        # Return the results as a ValueHelper
        vh = ValueHelper(val_t, unit_info=self.unit_info)
        return vh
        
#===============================================================================
#                            class UnitInfo
#===============================================================================

class UnitInfo(object):
    """Holds formatting, labels, and target types for units."""

    def __init__(self, 
                 unit_type_dict   = USUnits, 
                 unit_format_dict = default_unit_format_dict,  
                 unit_label_dict  = default_unit_label_dict,
                 time_format_dict = default_time_format_dict,
                 heatbase=None, coolbase=None):
        """
        unit_type_dict: Key is a unit_group (eg, 'group_pressure'), 
        value is the target unit type ('mbar')
        
        unit_format_dict: Key is unit type (eg, 'inHg'), 
        value is a string format ("%.1f")
        
        unit_label_dict: Key is unit type (eg, 'inHg'), 
        value is a label (" inHg")
        
        time_format_dict: Key is a context (eg, 'week'),
        value is a strftime format ("%d-%b-%Y %H:%M").
        
        heatbase: A value tuple. First element is the base temperature
        for heating degree days, second element the unit it is in.
        [Optional. If not given, (65.0, 'default_F') will be used.]
        
        coolbase: A value tuple. First element is the base temperature
        for cooling degree days, second element the unit it is in.
        [Optional. If not given, (65.0, 'default_F') will be used.]
        """
        self.unit_type_dict   = unit_type_dict
        self.unit_format_dict = unit_format_dict
        self.unit_label_dict  = unit_label_dict
        self.time_format_dict = time_format_dict
        self.heatbase = heatbase if heatbase is not None else default_heatbase
        self.coolbase = coolbase if coolbase is not None else default_coolbase
        
        # These are mostly used as template tags:
        self.format    = self.getObsFormatDict()
        self.label     = self.getObsLabelDict()
        self.unit_type = self.getObsUnitDict()

    @staticmethod
    def fromSkinDict(skin_dict):
        """Factory static method to initialize from a skin dictionary."""
        heatbase = skin_dict['Units']['DegreeDays'].get('heating_base')
        coolbase = skin_dict['Units']['DegreeDays'].get('heating_base')
        heatbase_t = (float(heatbase[0]), heatbase[1]) if heatbase else None
        coolbase_t = (float(coolbase[0]), coolbase[1]) if coolbase else None

        return UnitInfo(skin_dict['Units']['Groups'],
                        skin_dict['Units']['StringFormats'],
                        skin_dict['Units']['Labels'],
                        skin_dict['Units']['TimeFormats'],
                        heatbase_t,
                        coolbase_t)
    
    def toString(self, val_t, context='current', addLabel=True, 
                 useThisFormat=None, NONE_string=None):
        """Format the value as a string.
        
        val_t: The value to be formatted as a value tuple. First element
        is the value, the second element the unit type (eg, 'degree_F') it is in.
        
        context: A time context (eg, 'day'). 
        [Optional. If not given, context 'current' will be used.]
        
        addLabel: True to add a unit label (eg, 'mbar'), False to not.
        [Optional. If not given, a label will be added.]
        
        useThisFormat: An optional string or strftime format to be used. 
        [Optional. If not given, the format given in the initializer will be used.]
        
        NONE_string: A string to be used if the value val is None.
        [Optional. If not given, the string given unit_format_dict['NONE'] will be used.]
        """
        if val_t is None or val_t[0] is None:
            if NONE_string: 
                return NONE_string
            else:
                return self.unit_format_dict.get('NONE', 'N/A')
            
        # It's not a None value. Perform the type conversion to the internally
        # held target type:
        (target_val, target_unit_type) = self.convert(val_t)

        if target_unit_type == "unix_epoch":
            # Different formatting routines are used if the value is a time.
            try:
                if useThisFormat:
                    val_str = time.strftime(useThisFormat, time.localtime(target_val))
                else:
                    val_str = time.strftime(self.time_format_dict[context], time.localtime(target_val))
            except (KeyError, TypeError):
                # If all else fails, use this weeutil utility:
                val_str = weeutil.weeutil.timestamp_to_string(target_val)
        else:
            # It's not a time. It's a regular value.
            try:
                if useThisFormat:
                    val_str = useThisFormat % target_val
                else:
                    val_str = self.unit_format_dict[target_unit_type] % target_val
            except (KeyError, TypeError):
                # If all else fails, ask Python to convert to a string:
                val_str = str(target_val)

        if addLabel:
            val_str += self.unit_label_dict.get(target_unit_type,'')

        return val_str

    def getUnitType(self, obs_type, agg_type=None):
        """Given an observation type and an aggregation type,
        return the target unit type.
        
        Examples:
             obs_type  agg_type              Returns
             ________  ________              _______
            'outTemp',  None     returns --> 'degree_C'
            'outTemp', 'mintime' returns --> 'unix_epoch'
            'wind',    'avg'     returns --> 'meter_per_second'
            'wind',    'vecdir'  returns --> 'degree_compass'
        
        obs_type: An observation type. E.g., 'barometer'.
        
        agg_type: An aggregation type E.g., 'mintime', or 'avg'.
        
        Returns: the target unit type
        """
        unit_group = getUnitGroup(obs_type, agg_type)
        unit_type = self._getUnitTypeFromGroup(unit_group)
        return unit_type
        
    def getTargetType(self, old_unit_type):
        """Given an old unit type, return the target unit type.
        
        old_unit_type: A unit type such as 'inHg'.
        
        Returns: the target unit type, such as 'mbar'.
        """
        # If there is no unit attached, then the target can only be None:
        if not old_unit_type:
            return None
        unit_group= unit_type_dict[old_unit_type]
        unit_type = self._getUnitTypeFromGroup(unit_group)
        return unit_type
    
    def convert(self, val_t):
        """Convert a value from a given unit type to the target type.
        
        val_t: A value tuple with the data and a unit type. 
        Example: (30.02, 'inHg')
        
        returns: A value tuple in the new, target unit type 
        Example: (1016.5, 'mbar')"""
        new_unit_type = self.getTargetType(val_t[1])
        new_val_t = convert(val_t, new_unit_type)
        return new_val_t
        
    def getObsFormatDict(self):
        """Returns a dictionary with key an observation type, value a string or time format."""
        obs_format_dict = {}
        for obs_type in obs_group_dict:
            obs_format_dict[obs_type] = self.unit_format_dict.get(self.getUnitType(obs_type),'')
        return obs_format_dict
    
    def getObsLabelDict(self):
        """Returns a dictionary with key an observation type, value a label."""
        obs_label_dict = {}
        for obs_type in obs_group_dict:
            obs_label_dict[obs_type] = self.unit_label_dict.get(self.getUnitType(obs_type),'')
        return obs_label_dict
    
    def getObsUnitDict(self):
        """Returns a dictionary with key an observation type, value the target unit type."""
        obs_unit_dict = {}
        for obs_type in obs_group_dict:
            obs_unit_dict[obs_type] = self.getUnitType(obs_type)
        return obs_unit_dict
    
    def _getUnitTypeFromGroup(self, unit_group):
        unit_type = self.unit_type_dict.get(unit_group, USUnits[unit_group])
        return unit_type
        
    
def getUnitGroup(obs_type, agg_type=None):
    """Given an observation type and an aggregation type, what unit group does it belong to?
    
    Returns None if it cannot be determined."""
    if agg_type and agg_type in agg_group:
        unit_group = agg_group[agg_type]
    else:
        unit_group = obs_group_dict.get(obs_type)
    return unit_group
    
def getStandardUnitType(std_unit_system, obs_type, agg_type=None):
    """Given an observation type and an aggregation type, return the unit type
    within a standardized unit system.
    
    std_unit_system: Either weewx.US or weewx.METRIC
    
    obs_type: An observation type ('outTemp', 'rain', etc.)
    
    agg_type: Type of aggregation ('mintime', 'count', etc.)
    [Optional. default is no aggregation)
    
    returns the unit type of the given observation and aggregation type, 
    or None if it cannot be determined.
    """
    try:
        unit_group = getUnitGroup(obs_type, agg_type)
        unit_type  = StdUnitSystem[std_unit_system][unit_group]
    except KeyError:
        unit_type = None
    return unit_type
    
def convert(val_t, target_unit_type):
    """ Convert a value or a sequence of values between unit systems

    val_t: A value-tuple with the value to be converted. The first
    element is the value (either a scalar or iterable), the second element 
    the unit type (e.g., "foot", or "inHg") it is in.
    
    target_unit_type: The unit type (e.g., "meter", or "mbar") to
    which the value is to be converted. If None, it will not be converted.
    
    returns: A value tuple converted into the desired units.
    """
    if target_unit_type is None or val_t[1] == target_unit_type or val_t[0] is None:
        return val_t

    try:
        return (map(conversionDict[val_t[1]][target_unit_type], val_t[0]), target_unit_type)
    except TypeError:
        return (conversionDict[val_t[1]][target_unit_type](val_t[0]), target_unit_type)

def convertStd(val_t, target_std_unit_system):
    """Convert a value tuple to an appropriate unit in a target standardized
    unit system
    
        Example: convertStd((30.02, 'inHg'), weewx.METRIC)
        returns: (1016.5 'mbar')
    
    val_t: A value tuple. Example: (30.02, 'inHg')
    
    target_std_unit_system: A standardized unit system. 
    Example: weewx.US or weewx.METRIC.
    
    Returns: A value tuple in the given standardized unit system.
    """
    unit_group = unit_type_dict[val_t[1]]
    target_unit_type = StdUnitSystem[target_std_unit_system][unit_group]
    return convert(val_t, target_unit_type)
